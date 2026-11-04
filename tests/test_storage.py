from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from uptime.contracts import Principal
from uptime.storage import database, initialize, save_cases, settlement_events, stored_cases, transition_settlement


def test_restart_and_corruption(tmp_path):
    path = tmp_path / "cases.db"
    initialize(path)
    save_cases(path,"a",[{"id":"e","amount":"10.00"}])
    save_cases(path,"a",[{"id":"e","amount":"99.00"}])
    initialize(path)
    assert stored_cases(path,"a")[0]["amount"] == "10.00"
    assert stored_cases(path,"b") == []
    with database(path) as db, db:
        db.execute("UPDATE case_snapshot SET payload='{}'")
    with pytest.raises(ValueError):
        stored_cases(path,"a")


def test_concurrent_reconciliation_and_restart(tmp_path):
    path=tmp_path / "events.db"
    initialize(path)
    reviewer=Principal("a","case-reviewer","reviewer")
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: transition_settlement(path,reviewer,"c","record-credit","50.00"), range(12)))
    initialize(path)
    assert len(settlement_events(path,"a","c")) == 1
    with pytest.raises(ValueError):
        transition_settlement(path,reviewer,"c","apply-balance","50.00")
    with pytest.raises(PermissionError):
        transition_settlement(path,Principal("a","reader","viewer"),"c","apply-partial","50.00")
    assert settlement_events(path,"b","c") == []


def test_schema_mismatch_fails_closed(tmp_path):
    path=tmp_path / "future.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=20")
    with pytest.raises(ValueError):
        initialize(path)
