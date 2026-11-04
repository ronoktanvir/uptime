from datetime import datetime, timedelta, UTC
import json

import pytest

from uptime.contracts import Outcome
from uptime.other_obligations import ROOT, demo_cases, evaluate_notice, evaluate_rebate, notice_cutoff


@pytest.fixture
def examples():
    return json.loads((ROOT / "examples.json").read_text())


def test_rebate_inclusive_threshold_after_returns(examples):
    data = examples["rebate"]
    result = evaluate_rebate(data)
    assert result.outcome == Outcome.ELIGIBLE
    assert str(result.amount.amount) == "1500.00"
    assert "100000.00 net" in result.trace[0]
    assert "500.00 already credited" in result.trace[2]
    data["charges"][2]["amount"] = "10000.01"
    below = evaluate_rebate(data)
    assert below.outcome == Outcome.INELIGIBLE and below.amount is None


def test_rebate_dedup_and_credit_allocation(examples):
    data = examples["rebate"]
    data["charges"] += [data["charges"][0].copy(), data["charges"][2].copy()]
    data["credits"] += [data["credits"][0].copy(), dict(data["credits"][0], id="CN-X", clause="N-2")]
    assert str(evaluate_rebate(data).amount.amount) == "1500.00"
    data["credits"][-1]["id"] = "CM-7"
    result = evaluate_rebate(data)
    assert result.outcome == Outcome.MISSING and result.amount is None


@pytest.mark.parametrize("previous", ["2000.00", "3100.00"])
def test_prior_credit_never_produces_negative_recovery(examples, previous):
    data = examples["rebate"]
    data["credits"][0]["amount"] = previous
    assert evaluate_rebate(data).outcome == Outcome.INELIGIBLE


def test_period_edges_and_ineligible_products_are_scoped_before_currency(examples):
    data = examples["rebate"]
    data["charges"][3]["currency"] = data["charges"][4]["currency"] = "EUR"
    assert str(evaluate_rebate(data).amount.amount) == "1500.00"
    data["charges"][1]["date"] = "2026-10-01"
    assert evaluate_rebate(data).outcome == Outcome.INELIGIBLE


@pytest.mark.parametrize("column,patch,expected", [
    ("charges", {"currency":"EUR"}, Outcome.UNSUPPORTED),
    ("credits", {"currency":"CAD"}, Outcome.UNSUPPORTED),
    ("charges", {"amount":"NaN"}, Outcome.MISSING),
    ("charges", {"amount":"-10.00"}, Outcome.MISSING),
    ("charges", {"amount":2.55}, Outcome.MISSING),
    ("charges", {"amount":"1.234"}, Outcome.MISSING),
    ("charges", {"date":"unknown"}, Outcome.MISSING),
    ("charges", {"product":None}, Outcome.MISSING),
    ("charges", {"kind":"unmapped fee"}, Outcome.UNSUPPORTED),
    ("credits", {"year_end":None}, Outcome.MISSING),
])
def test_unverified_numeric_or_scope_inputs_do_not_become_estimates(examples, column, patch, expected):
    data = examples["rebate"]
    data[column][0].update(patch)
    result = evaluate_rebate(data)
    assert result.outcome == expected and result.amount is None and result.clauses


@pytest.mark.parametrize("patch", [{"complete":False}, {"through":"2026-09-29"}, {"credits":None}])
def test_missing_annual_data(examples, patch):
    data = {**examples["rebate"], **patch}
    assert evaluate_rebate(data).outcome == Outcome.MISSING


def test_rounding_at_award_only(examples):
    data = examples["rebate"]
    data["charges"][0]["amount"] = "65000.25"
    assert str(evaluate_rebate(data).amount.amount) == "1500.01"


def test_notice_weekend_holiday_timezone_and_exact_receipt(examples):
    data = examples["notice"]
    deadline = notice_cutoff(data["calendar"])
    assert deadline.isoformat() == "2026-11-03T17:00:00-08:00"
    assert deadline.astimezone(UTC).isoformat() == "2026-11-04T01:00:00+00:00"
    result = evaluate_notice(data)
    assert result.outcome == Outcome.ELIGIBLE and result.amount is None
    data["receipt"]["received_at"] = (deadline.astimezone(UTC) + timedelta(microseconds=1)).isoformat()
    late = evaluate_notice(data)
    assert late.outcome == Outcome.INELIGIBLE and late.amount is None


@pytest.mark.parametrize("calendar", [None, {"id":"other"}, {}, {"id":"NB-OFFICE-2026"}])
def test_unknown_calendar_has_no_deadline(examples, calendar):
    result = evaluate_notice({**examples["notice"], "calendar":calendar})
    assert result.outcome == Outcome.MISSING and result.missing and result.amount is None


@pytest.mark.parametrize("patch", [{"closed":[]}, {"from":"2026-11-04"}, {"through":"2026-11-01"}])
def test_incomplete_or_conflicting_calendar(examples, patch):
    data = examples["notice"]
    data["calendar"].update(patch)
    assert evaluate_notice(data).outcome == Outcome.MISSING


@pytest.mark.parametrize("patch", [{"channel":"email"}, {"renewal":"2027-11-09"},
                                  {"received_at":"2026-11-03T16:00:00"}, {"id":None}])
def test_dispatch_or_another_renewal_is_not_receipt(examples, patch):
    data = examples["notice"]
    data["receipt"].update(patch)
    assert evaluate_notice(data).outcome == Outcome.MISSING
    data["receipt"] = {"sent_at":datetime.now(UTC).isoformat()}
    assert evaluate_notice(data).outcome == Outcome.MISSING


def test_views_are_cited_and_expose_no_external_action_or_award():
    rows = {r["id"]:r for r in demo_cases()}
    assert len(rows) == 3 and rows["rebate-annual"]["amount"] == "1500.00"
    for row in rows.values():
        assert row["actions"] == [] and row["sources"] == ["SYNTHETIC_CUSTOMER","DETERMINISTIC_REPLAY"]
        assert row["clauses"][0]["uri"] == "/fixtures/other_obligations/agreement.txt"
        assert row["evidence"][0]["detail"] in (ROOT / "agreement.txt").read_text()
        assert row["timeline"][0]["sources"] == row["sources"]
        assert "ledger" not in row
    notice = rows["notice-renewal"]
    assert notice["stage"] == "NOTICE_RECEIVED_ON_TIME" and notice["amount"] is None and not notice["financials"]
    mfn = rows["mfn-comparator"]
    assert mfn["outcome"] == Outcome.UNSUPPORTED and mfn["amount"] is None and "authorized" in mfn["trace"][0]
