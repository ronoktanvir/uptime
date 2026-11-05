"""Acceptance harness controls; deliberately contain no holdout records."""
from pathlib import Path

import pytest

from scripts.blind_acceptance import BoundaryError, local_path, money_check, select_records


def test_unknown_unavailable_and_wrong_money_are_distinct():
    assert money_check("0.00", None, available=False) == "UNAVAILABLE"
    assert money_check("0.00", None, available=True) == "UNKNOWN_MISMATCH"
    assert money_check(None, "0.00", available=True) == "UNKNOWN_MISMATCH"
    assert money_check("1.01", "1.00", available=True) == "WRONG_MONEY"
    assert money_check("1.00", "1.000", available=True) == "PASS"


def test_case_selection_never_imports_global_or_future_evidence():
    rows = [dict(id="a", available_at="2028-01-01T00:00:00Z"),
            dict(id="b", available_at="2028-01-02T00:00:00Z"),
            dict(id="c", available_at="2028-01-01T00:00:00Z")]
    ready, future = select_records(rows, ["a", "b"], "2028-01-01T00:00:00Z")
    assert [r["id"] for r in ready] == ["a"]
    assert [r["id"] for r in future] == ["b"]
    with pytest.raises(BoundaryError, match="MISSING_INPUT_ID"):
        select_records(rows, ["absent"], "2028-01-01T00:00:00Z")


def test_fixture_cannot_escape_root(tmp_path):
    with pytest.raises(BoundaryError, match="FIXTURE_PATH_INVALID"):
        local_path(tmp_path, "../outside.json")
