"""Document custody audit: stored citations must re-slice from the exact stored source text.

New W5 controls under decision 91. The adapter is installed through the real catalog route
with the existing authored synthetic catalog fixture; tampered variants are payload copies,
because stored catalog rows are immutable by trigger.
"""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3

import pytest

from tests.test_vendor_catalog import api, install  # noqa: F401  (fixture reuse)
from uptime.evidence_custody import audit_artifact, audit_database


def stored(tmp_path):
    with sqlite3.connect(tmp_path / "catalog.sqlite") as db:
        return [json.loads(p) for (p,) in db.execute("SELECT payload FROM v4_vendor_artifact")]


def test_installed_adapter_citations_re_slice_from_the_stored_source(api, tmp_path):
    c, _, _, _ = api
    install(c)
    report = audit_database(tmp_path / "catalog.sqlite")
    assert report["traceable"] and report["artifacts"]
    artifact = report["artifacts"][0]
    payload = stored(tmp_path)[0]
    assert artifact["citations"] > 0 and artifact["problems"] == []
    assert artifact["sha256"] == sha256(payload["source_text"].encode()).hexdigest()


def first_citation(payload):
    from uptime.evidence_custody import citations
    return next(c for _, c in citations(payload))


@pytest.mark.parametrize("tamper,expected", [
    ("text", "does not match the document hash"),
    ("shift", "does not re-slice"),
    ("bounds", "outside the stored source"),
    ("quote", "does not re-slice"),
    ("missing", "No stored source text"),
])
def test_tampered_or_detached_citations_are_reported(api, tmp_path, tamper, expected):
    c, _, _, _ = api
    install(c)
    payload = deepcopy(stored(tmp_path)[0])
    cite = first_citation(payload)
    if tamper == "text":
        payload["source_text"] = payload["source_text"].replace("12 calendar days", "21 calendar days")
    elif tamper == "shift":
        cite["start"], cite["end"] = cite["start"] + 1, cite["end"] + 1
    elif tamper == "bounds":
        cite["end"] = len(payload["source_text"]) + 5
    elif tamper == "quote":
        cite["quote"] = cite["quote"].replace(cite["quote"][:1], "#", 1)
    else:
        payload.pop("source_text")
    result = audit_artifact(payload)
    assert not result["traceable"]
    assert any(expected in problem for problem in result["problems"]), result["problems"]


def test_quote_digest_and_absent_citations_are_reported():
    text = "Claims must be received within 12 calendar days after month end."
    payload = dict(source_text=text, manifest=dict(document=dict(sha256=sha256(text.encode()).hexdigest()),
                   citations=[dict(start=0, end=6, quote="Claims", block_sha256="0" * 64)]))
    assert "quote digest differs" in audit_artifact(payload)["problems"][0]
    payload["manifest"]["citations"][0]["block_sha256"] = sha256(b"Claims").hexdigest()
    assert audit_artifact(payload)["traceable"]
    payload["manifest"]["citations"] = []
    assert audit_artifact(payload)["problems"] == ["No citation is available to trace."]


def test_audit_never_writes_and_an_empty_catalog_is_not_traceable(api, tmp_path):
    c, _, _, _ = api
    install(c)
    path = tmp_path / "catalog.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = sorted(p.name for p in tmp_path.iterdir()), path.read_bytes()
    audit_database(path)
    assert (sorted(p.name for p in tmp_path.iterdir()), path.read_bytes()) == before
    empty = tmp_path / "empty.sqlite"
    sqlite3.connect(empty).close()
    assert audit_database(empty) == dict(database_sha256=sha256(empty.read_bytes()).hexdigest(), artifacts=[],
                                         traceable=False, uncheckpointed_log=False)


def test_rows_still_in_the_write_ahead_log_are_disclosed(tmp_path):
    path = tmp_path / "wal.sqlite"
    writer = sqlite3.connect(path)
    try:
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("CREATE TABLE v4_vendor_artifact (tenant TEXT, vendor TEXT, version TEXT, payload TEXT)")
        writer.commit()
        report = audit_database(path)
        assert report["uncheckpointed_log"] is True
        # Immutable mode reads only the main file, so the report cannot claim these rows were traced.
        assert report["traceable"] is False
    finally:
        writer.close()
