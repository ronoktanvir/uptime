"""Read-only re-verification that stored adapter citations still trace to their exact source.

A stored vendor artifact keeps the exact source text, the document's SHA-256 and the
character-offset citations its rules rely on. After storage the application rechecks the
whole-text hash. This auditor also re-slices every citation from the stored text and checks
any quote digest, so each clause a result relies on is shown to come from that document at
that place. It reads the database in SQLite immutable mode and never writes. Rows still in an
uncheckpointed write-ahead log are not visible in that mode; the report says when one exists.

Traceable here means the cited words are present at the stated offsets of the stored source.
It does not establish that the interpretation of those words is correct.
"""
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote


def citations(value, path="$"):
    """Yield (path, citation) for every object carrying integer offsets and a quote."""
    if isinstance(value, dict):
        if {"start", "end", "quote"} <= value.keys():
            yield path, value
        for key, child in value.items():
            if key != "source_text":
                yield from citations(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from citations(child, f"{path}[{index}]")


def audit_artifact(payload: dict) -> dict:
    text = payload.get("source_text")
    document = (payload.get("manifest") or {}).get("document") or {}
    declared = document.get("sha256")
    problems, count = [], 0
    if not isinstance(text, str):
        problems.append("No stored source text.")
        text = ""
    elif sha256(text.encode()).hexdigest() != declared:
        problems.append("Stored source text does not match the document hash.")
    for path, cite in citations(payload):
        count += 1
        start, end, cited = cite["start"], cite["end"], cite["quote"]
        if type(start) is not int or type(end) is not int or not isinstance(cited, str) or not 0 <= start < end <= len(text):
            problems.append(f"{path}: offsets lie outside the stored source.")
        elif text[start:end] != cited:
            problems.append(f"{path}: quote does not re-slice from the stored source.")
        if "block_sha256" in cite and sha256(str(cited).encode()).hexdigest() != cite["block_sha256"]:
            problems.append(f"{path}: quote digest differs.")
    if count == 0:
        problems.append("No citation is available to trace.")
    return dict(document=document.get("name"), uri=document.get("uri"), sha256=declared,
                citations=count, traceable=not problems, problems=problems)


def audit_database(path) -> dict:
    location = Path(path).resolve(strict=True)
    uri = "file:" + quote(str(location)) + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        present = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v4_vendor_artifact'").fetchone()
        rows = connection.execute("SELECT tenant,vendor,version,payload FROM v4_vendor_artifact "
                                  "ORDER BY tenant,vendor,version").fetchall() if present else []
    finally:
        connection.close()
    wal = location.with_name(location.name + "-wal")
    artifacts = [dict(tenant=t, vendor=v, version=ver, **audit_artifact(json.loads(p))) for t, v, ver, p in rows]
    # An empty catalog has nothing to trace; it is not reported as traceable.
    return dict(database_sha256=sha256(location.read_bytes()).hexdigest(), artifacts=artifacts,
                traceable=bool(artifacts) and all(a["traceable"] for a in artifacts),
                uncheckpointed_log=wal.exists() and wal.stat().st_size > 0)
