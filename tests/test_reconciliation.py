from decimal import Decimal

import pytest

from uptime.reconciliation import demo_reconciliation, reconcile


def records():
    base = {"tenant": "one", "currency": "USD", "vendor_id": "vendor"}
    award = {**base, "id": "award", "confirmed": True, "memo_ref": "memo", "amount": "30",
             "source": "SIMULATED_VENDOR"}
    credit = {**base, "id": "credit", "amount": "15", "award_id": "award", "memo_ref": "memo",
              "source": "DETERMINISTIC_REPLAY"}
    app = {**base, "id": "app", "amount": "10.25", "credit_id": "credit", "bill_id": "bill",
           "source": "DETERMINISTIC_REPLAY"}
    bill = {**base, "id": "bill", "amount": "12", "source": "SYNTHETIC_CUSTOMER"}
    return award, credit, app, bill


def test_partial_posting_and_partial_utilization():
    a, c, x, b = records()
    r = reconcile("one", a, [c, c], [x, x], [b, b])
    assert [r[k] for k in ("awarded", "posted", "applied", "unposted", "unapplied_posted",
                            "outstanding")] == ["30.00", "15.00", "10.25", "15.00", "4.75", "19.75"]
    assert r["application_ids"] == ["app"] and r["bill_ids"] == ["bill"]


@pytest.mark.parametrize("idx,patch", [(0, {"confirmed": False}), (2, {"source": "UNAVAILABLE"}), (1, {"memo_ref": "unknown"}),
    (1, {"award_id": "another"}), (2, {"currency": "EUR"}), (2, {"tenant": "two"}),
    (2, {"bill_id": ""}), (2, {"credit_id": "unknown"}), (3, {"vendor_id": "wrong"}),
    (2, {"id": None}), (2, {"amount": "15"}), (1, {"amount": "31"}),
    (0, {"amount": "NaN"}), (0, {"amount": 30.0}), (1, {"amount": ".001"})])
def test_mismatch_or_overcount_fails_closed(idx, patch):
    r = list(records())
    r[idx] = {**r[idx], **patch}
    a, c, x, b = r
    with pytest.raises(ValueError):
        reconcile("one", a, [c], [x], [b])


def test_duplicate_or_conflicting_observations_cannot_inflate_money():
    a, c, x, b = records()
    for more in ({**x, "id": "x2"}, {**x, "amount": "1"}):
        with pytest.raises(ValueError): reconcile("one", a, [c], [x, more], [b])


def test_multiple_bills_cannot_use_one_credit_twice():
    a, c, x, b = records()
    with pytest.raises(ValueError):
        reconcile("one", a, [c], [x, {**x, "id": "x2", "bill_id": "b2"}], [b, {**b, "id": "b2"}])


def test_demo_awards_and_utilization_have_independent_provenance():
    values = [demo_reconciliation("10.09", s) for s in
              ("AWARDED", "POSTED", "PARTIALLY_APPLIED", "APPLIED")]
    assert [v["applied"] for v in values] == ["0.00", "0.00", "5.04", "10.09"]
    assert [v["posted"] for v in values] == ["0.00", "10.09", "10.09", "10.09"]
    assert all("LIVE_RAMP_SANDBOX" not in v["sources"] for v in values)
    assert values[0]["sources"] == ["SIMULATED_VENDOR"]
    assert demo_reconciliation(Decimal(0), "NONE")["award_id"] is None
    with pytest.raises(ValueError):
        demo_reconciliation("10", "NONE")
