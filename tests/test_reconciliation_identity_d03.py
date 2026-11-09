"""Reconciliation scope identities follow source-identity/1 (team decision D03, 2026-11-09).

Account and contract identities on award, credit, bill and application records are
accepted only inside the bounded exact domain, exactly as the claim and ledger paths
accept them. Nothing is trimmed or normalized; a value another path would refuse is
refused here too.
"""
import pytest

from uptime.reconciliation import reconcile
from uptime.source_identity import refusal


def scoped(account, contract):
    base = {"tenant": "one", "currency": "USD", "vendor_id": "vendor",
            "account_id": account, "product_id": "api", "contract_id": contract, "contract_version": "v1"}
    award = {**base, "id": "award", "confirmed": True, "memo_ref": "memo", "amount": "30",
             "source": "SIMULATED_VENDOR"}
    credit = {**base, "id": "credit", "amount": "15", "award_id": "award", "memo_ref": "memo",
              "source": "DETERMINISTIC_REPLAY"}
    app = {**base, "id": "app", "amount": "10", "credit_id": "credit", "bill_id": "bill",
           "source": "DETERMINISTIC_REPLAY"}
    bill = {**base, "id": "bill", "amount": "12", "source": "SYNTHETIC_CUSTOMER"}
    return award, [credit], [app], [bill]


@pytest.mark.parametrize("account,contract", [
    ("harborline-001", "nw-msa-2025"),
    ("Cedar Orrery Studio", "Talus Signal Availability Agreement"),
    ("O'Neil & Sons (US)", "Acme, Inc. Order Form 2+"),
])
def test_bounded_exact_source_identities_reconcile_unchanged(account, contract):
    award, credits, apps, bills = scoped(account, contract)
    result = reconcile("one", award, credits, apps, bills)
    # outstanding = awarded 30 - applied 10, as in tests/test_reconciliation.py
    assert result["applied"] == "10.00" and result["outstanding"] == "20.00"


@pytest.mark.parametrize("field", ["account_id", "contract_id"])
@pytest.mark.parametrize("value", [
    "Harborline ",          # trailing space: previously refused too
    "Harborline  Labs",     # repeated space
    "North—wind",      # em dash: accepted by the old printable check
    "Café",           # not NFC
    "x" * 97,               # too long
    "---",                  # no letter or digit
])
def test_identities_outside_source_identity_are_refused_on_every_record(field, value):
    assert refusal(value) is not None
    award, credits, apps, bills = scoped("harborline-001", "nw-msa-2025")
    for row in (award, *credits, *apps, *bills):
        row[field] = value
    with pytest.raises(ValueError):
        reconcile("one", award, credits, apps, bills)


def test_identities_are_compared_exactly_never_folded():
    award, credits, apps, bills = scoped("Cedar Orrery Studio", "nw-msa-2025")
    bills[0]["account_id"] = "cedar orrery studio"
    with pytest.raises(ValueError, match="Mismatched account_id"):
        reconcile("one", award, credits, apps, bills)
