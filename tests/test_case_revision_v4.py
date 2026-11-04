from concurrent.futures import ThreadPoolExecutor
import sqlite3
import pytest
from hypothesis import given, strategies as st
from uptime.storage import initialize, save_cases, stored_cases, case_versions, database


def test_reimport_and_reinstall_keep_complete_history(tmp_path):
    p=tmp_path/"state.sqlite"
    initialize(p)
    for amount in ("10.00","20.00","20.00","10.00"):
        save_cases(p,"a",[{"id":"case","amount":amount}])
    initialize(p)
    history=case_versions(p,"a","case")
    assert [r["revision"] for r in history]==[1,2,3]
    assert [r["payload"]["amount"] for r in history]==["10.00","20.00","10.00"]
    assert stored_cases(p,"a")[0]["amount"]=="10.00"
    with pytest.raises(KeyError):case_versions(p,"b","case")
    with database(p) as db, pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE case_revision SET digest='bad'")


def test_identical_concurrent_observation_adds_one_revision(tmp_path):
    p=tmp_path/"state.sqlite";initialize(p)
    save_cases(p,"a",[{"id":"case","amount":"1.00"}])
    def send(_):save_cases(p,"a",[{"id":"case","amount":"2.00"}])
    with ThreadPoolExecutor(8) as workers:list(workers.map(send,range(24)))
    assert len(case_versions(p,"a","case"))==2


@given(st.lists(st.integers(0,10000),min_size=1,max_size=25))
def test_content_revisions_preserve_every_distinct_successive_value(values):
    from tempfile import TemporaryDirectory
    from pathlib import Path
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/"case.db";initialize(p)
        for v in values:save_cases(p,"a",[{"id":"case","cents":v}])
        distinct=[v for i,v in enumerate(values) if i==0 or values[i-1]!=v]
        assert [r["payload"]["cents"] for r in case_versions(p,"a","case")]==distinct
