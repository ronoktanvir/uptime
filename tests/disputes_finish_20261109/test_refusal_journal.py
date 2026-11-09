"""record_verified_source_refusal: append-only, first-seen, bounded, tenant- and signer-isolated."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
import threading

import pytest

from uptime.correspondence_refusals import COLUMNS, REASON, record_verified_source_refusal

UTC = timezone.utc
FIRST = datetime(2026, 11, 9, 10, 0, 0, tzinfo=UTC)
PACIFIC = timezone(timedelta(hours=-8))
GOOD_PATH = "/api/correspondence/claims/inbox-c1/events"
KEY_A = "ed25519-sha256:" + "a" * 64


def call(**overrides):
    values = dict(tenant="bears", subject="carrier-feed", key_id=KEY_A, grant_id="b" * 64,
                  request_path=GOOD_PATH, body_sha256="c" * 64, received_at=FIRST)
    values.update(overrides)
    return values


def rows(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in db.execute("SELECT * FROM source_refusal_audit ORDER BY rowid")]
    finally:
        db.close()


def test_first_seen_wins_even_with_later_timestamp(tmp_path):
    path = tmp_path / "w.db"
    assert record_verified_source_refusal(path, **call()) is True
    assert record_verified_source_refusal(path, **call(received_at=FIRST + timedelta(days=3))) is False
    assert record_verified_source_refusal(path, **call(received_at=FIRST - timedelta(days=3))) is False
    stored = rows(path)
    assert len(stored) == 1
    assert stored[0]["received_at"] == FIRST.isoformat()


def test_offset_is_preserved_not_normalized(tmp_path):
    path = tmp_path / "w.db"
    stamp = datetime(2026, 11, 9, 2, 0, tzinfo=PACIFIC)
    assert record_verified_source_refusal(path, **call(received_at=stamp))
    assert rows(path)[0]["received_at"] == "2026-11-09T02:00:00-08:00"


def test_bounded_metadata_only_and_no_raw_payload_columns(tmp_path):
    path = tmp_path / "w.db"
    record_verified_source_refusal(path, **call())
    db = sqlite3.connect(path)
    try:
        names = tuple(row[1] for row in db.execute("PRAGMA table_info(source_refusal_audit)"))
    finally:
        db.close()
    assert names == COLUMNS
    forbidden = ("raw", "proof", "signature", "nonce", "message", "payload", "scope", "claim", "account")
    assert not any(word in name for word in forbidden for name in names)
    assert "body" not in names
    row = rows(path)[0]
    assert row["reason"] == REASON == "OUT_OF_SCOPE"
    assert (row["tenant"], row["subject"], row["source_key_id"], row["source_grant_id"],
            row["request_path"], row["body_sha256"]) == ("bears", "carrier-feed", KEY_A, "b" * 64,
                                                          GOOD_PATH, "c" * 64)
    assert len(row["refusal_digest"]) == 64


def test_rejects_raw_material_arguments(tmp_path):
    path = tmp_path / "w.db"
    for extra in ({"body": b"{}"}, {"proof": "x"}, {"nonce": "n"}, {"reason": "OTHER"}):
        with pytest.raises(TypeError):
            record_verified_source_refusal(path, **call(), **extra)
    assert not path.exists()


@pytest.mark.parametrize("change", [
    {"tenant": "other"},
    {"subject": "other-feed"},
    {"key_id": "ed25519-sha256:" + "d" * 64},
    {"grant_id": "e" * 64},
    {"request_path": "/api/correspondence/claims/inbox-c2/events"},
    {"body_sha256": "f" * 64},
])
def test_each_identity_field_is_a_distinct_key(tmp_path, change):
    path = tmp_path / "w.db"
    assert record_verified_source_refusal(path, **call())
    assert record_verified_source_refusal(path, **call(**change))
    stored = rows(path)
    assert len(stored) == 2
    assert stored[0]["refusal_digest"] != stored[1]["refusal_digest"]


def test_tenant_and_signer_isolation(tmp_path):
    path = tmp_path / "w.db"
    other_key = "ed25519-sha256:" + "9" * 64
    assert record_verified_source_refusal(path, **call(tenant="bears"))
    assert record_verified_source_refusal(path, **call(tenant="lions"))
    assert record_verified_source_refusal(path, **call(tenant="bears", key_id=other_key))
    assert not record_verified_source_refusal(path, **call(tenant="lions", received_at=FIRST + timedelta(hours=1)))
    stored = rows(path)
    assert [(r["tenant"], r["source_key_id"]) for r in stored] == [
        ("bears", KEY_A), ("lions", KEY_A), ("bears", other_key)]
    assert len({r["refusal_digest"] for r in stored}) == 3


@pytest.mark.parametrize("change", [
    {"tenant": ""}, {"tenant": "b" * 97}, {"tenant": "be ars"}, {"tenant": b"bears"}, {"tenant": None},
    {"subject": ""}, {"subject": "x" * 97}, {"subject": " feed"},
    {"subject": "fe" + "e" + chr(0x301) + "d"},  # decomposed form, not NFC; refused, never rewritten
    {"subject": "feed\n"}, {"subject": 7},
    {"key_id": "a" * 64}, {"key_id": "ed25519-sha256:" + "A" * 64}, {"key_id": "ed25519-sha256:" + "a" * 63},
    {"key_id": KEY_A + "\n"}, {"key_id": "hmac-sha256:" + "a" * 64},
    {"grant_id": "b" * 63}, {"grant_id": "B" * 64}, {"grant_id": "g" * 64}, {"grant_id": "b" * 65},
    {"body_sha256": "c" * 63}, {"body_sha256": "C" * 64}, {"body_sha256": b"c" * 64},
    {"request_path": "/api/correspondence/claims/inbox-c1"},
    {"request_path": GOOD_PATH + "/"},
    {"request_path": "/api/correspondence/claims//events"},
    {"request_path": "/api/correspondence/claims/events"},
    {"request_path": "/api/correspondence/claims/c1/events"},
    {"request_path": "/api/correspondence/claims/inbox-c1/../inbox-c2/events"},
    {"request_path": "/api/correspondence/claims/inbox-c1\n/events"},
    {"request_path": "/API/correspondence/claims/inbox-c1/events"},
    {"request_path": GOOD_PATH + "?x=1"},
    {"request_path": "/api/correspondence/claims/inbox-" + "a" * 70 + "/events"},
    {"received_at": datetime(2026, 11, 9, 10, 0)},
    {"received_at": "2026-11-09T10:00:00+00:00"},
    {"received_at": 1762682400},
])
def test_invalid_metadata_raises_and_writes_nothing(tmp_path, change):
    path = tmp_path / "w.db"
    assert record_verified_source_refusal(path, **call())
    with pytest.raises(ValueError):
        record_verified_source_refusal(path, **call(**change))
    assert len(rows(path)) == 1


def test_invalid_metadata_never_opens_database(tmp_path):
    path = tmp_path / "w.db"
    with pytest.raises(ValueError):
        record_verified_source_refusal(path, **call(grant_id="nope"))
    assert not path.exists()


def test_no_claim_source_evidence_or_approval_mutation(tmp_path):
    path = tmp_path / "w.db"
    tables = ("inbox_claim", "source_grant", "evidence", "approval")
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE inbox_claim (tenant TEXT, id TEXT, scope TEXT, state TEXT);
        CREATE TABLE source_grant (tenant TEXT, grant_id TEXT, scope TEXT);
        CREATE TABLE evidence (tenant TEXT, claim TEXT, digest TEXT);
        CREATE TABLE approval (tenant TEXT, claim TEXT, actor TEXT);
        INSERT INTO inbox_claim VALUES ('bears', 'inbox-c1', '{"account":"acme"}', 'OPEN');
        INSERT INTO inbox_claim VALUES ('lions', 'inbox-c1', '{"account":"other"}', 'OPEN');
        INSERT INTO source_grant VALUES ('bears', 'bbbb', '{"account":"acme"}');
        INSERT INTO evidence VALUES ('bears', 'inbox-c1', 'dddd');
        INSERT INTO approval VALUES ('bears', 'inbox-c1', 'reviewer');
    """)
    db.commit()
    before = {t: db.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in tables}
    schema_before = set(db.execute("SELECT type, name FROM sqlite_master").fetchall())
    db.close()

    assert record_verified_source_refusal(path, **call())
    assert record_verified_source_refusal(path, **call(tenant="lions"))

    db = sqlite3.connect(path)
    try:
        assert {t: db.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in tables} == before
        added = set(db.execute("SELECT type, name FROM sqlite_master").fetchall()) - schema_before
    finally:
        db.close()
    assert {name for _, name in added} <= {
        "source_refusal_audit", "sqlite_autoindex_source_refusal_audit_1",
        "source_refusal_audit_no_update", "source_refusal_audit_no_delete"}
    # The route names a claim, but no column links the row to it or to any claimed scope.
    assert not any("claim" in column or "scope" in column for column in COLUMNS)


def test_independent_connection_and_restart_keep_first_seen(tmp_path):
    path = tmp_path / "w.db"
    assert record_verified_source_refusal(path, **call())
    # A separate raw connection sees the committed row.
    assert rows(path)[0]["received_at"] == FIRST.isoformat()
    # As after a restart: a fresh call against the same file finds the row and keeps it unchanged.
    assert record_verified_source_refusal(path, **call(received_at=FIRST + timedelta(weeks=1))) is False
    assert [r["received_at"] for r in rows(path)] == [FIRST.isoformat()]


def test_rows_are_append_only(tmp_path):
    path = tmp_path / "w.db"
    record_verified_source_refusal(path, **call())
    db = sqlite3.connect(path)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE source_refusal_audit SET received_at='2030-01-01T00:00:00+00:00'")
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("DELETE FROM source_refusal_audit")
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("INSERT INTO source_refusal_audit VALUES (?,?,?,?,?,?,?,?,?)",
                       ("0" * 64, "bears", "s", KEY_A, "b" * 64, GOOD_PATH, "c" * 64,
                        "OTHER_REASON", FIRST.isoformat()))
        db.rollback()
    finally:
        db.close()
    assert len(rows(path)) == 1


def test_persistence_errors_propagate(tmp_path):
    # A directory is not a database file; the sqlite error must reach the caller.
    with pytest.raises(sqlite3.Error):
        record_verified_source_refusal(tmp_path, **call())
    corrupt = tmp_path / "corrupt.db"
    corrupt.write_bytes(b"not a sqlite database" * 100)
    with pytest.raises(sqlite3.Error):
        record_verified_source_refusal(corrupt, **call())


def test_concurrent_first_insert_on_fresh_database(tmp_path):
    path = tmp_path / "w.db"
    workers = 8
    barrier = threading.Barrier(workers)

    def attempt(offset):
        barrier.wait()
        return record_verified_source_refusal(path, **call(received_at=FIRST + timedelta(seconds=offset)))

    with ThreadPoolExecutor(workers) as pool:
        results = list(pool.map(attempt, range(workers)))
    assert results.count(True) == 1
    stored = rows(path)
    assert len(stored) == 1
    assert stored[0]["received_at"] == (FIRST + timedelta(seconds=results.index(True))).isoformat()
