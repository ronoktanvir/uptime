"""The strict join's observation through the unchanged deterministic evaluator.

The manifests come from the production compiler (vendor_terms.compile_terms) over authored synthetic text.
The evaluator ignores the opt-in marker, so these tests do not need the onboarding compiler patch: they show
that the strict join supplies only existing observations and that the existing engines compute every amount,
rate, filing window and stepped-credit base. No frozen corpus, oracle or private expected answer is read.
"""
from datetime import UTC, datetime
from hashlib import sha256
import json

import pytest

from uptime.correspondence_monthly import monthly_observation
from uptime.correspondence_types import SOURCE, Delivery, Scope
from uptime.vendor_eval import evaluate
from uptime.vendor_terms import Document, compile_terms

WHOLE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
             currency="USD", month="2026-10")
SCOPE = Scope(**WHOLE)
OVERLAY = dict(agreement="BR-74", account="north-612", product="Message Store", plan="Team",
               fee_line_ref="monthly-store", currency="USD", effective_from="2026-01-01", effective_until="2026-12-31")
TIERED = """Synthetic public test contract
Vendor: Boreal Relay
Agreement: BR-74
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
For Message Store on the Team plan, monthly availability below 99.9% earns a 12.5% service credit.
Claims must be received within 13 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""
STEPPED = TIERED.replace(
    "For Message Store on the Team plan, monthly availability below 99.9% earns a 12.5% service credit.",
    "For Message Store on the Team plan, the monthly uptime target is 99.9%; each completed 0.1 percentage point "
    "of shortfall below the target earns a 5% service credit, capped at 50%.\n"
    "Round the resulting service credit once to the nearest cent, with half cents rounded up; do not round "
    "availability or shortfall before counting completed increments.")
AT = datetime(2026, 11, 3, tzinfo=UTC)


def compiled(text):
    return compile_terms(Document(name="Boreal availability agreement", uri="urn:synthetic:boreal-agreement",
                                  classification="synthetic_public", text=text))


def fact(raw, received="2026-11-02T00:00:00+00:00"):
    kind = raw["kind"]
    source = SOURCE[kind]
    body = Delivery.model_validate(dict(event_id="evt-1", scope=WHOLE, body=raw)).body.model_dump(exclude_unset=True)
    return dict(event_id=kind, source=source, subject=source + "-fixture", kind=kind, body=body,
                digest=sha256(json.dumps([kind, body], sort_keys=True).encode()).hexdigest(),
                source_key_id="fixture-hmac:" + source, source_grant_id="grant:" + source,
                received_at=received, known_at=received)


def month(minutes, amount="417.36"):
    reports = [fact(dict(kind=kind, source_ref=kind + "-ref", observed_at="2026-11-01T06:00:00Z",
                         start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z", plan="Team", complete=True,
                         exclusions_removed=True, gaps=[], unresolved_exclusions=[], eligible_downtime_minutes=minutes))
               for kind in ("monthly_coverage", "monthly_attribution")]
    return reports + [fact(dict(kind="invoice", lines=[dict(id="monthly-store", kind="affected_api", amount=amount),
                                                       dict(id="tax-11", kind="tax", amount="0.00")]))]


def evaluated(minutes, *, text=TIERED, amount="417.36", filed=AT, at=AT):
    observation = monthly_observation(SCOPE, month(minutes, amount), OVERLAY, filed, at)
    return evaluate(compiled(text), OVERLAY, observation, "bears")


def test_breach_month_is_priced_only_by_the_existing_tier_evaluator():
    raw = evaluated(45)
    assert (raw["outcome"], raw["amount"], raw["rate_units"]) == ("ELIGIBLE", "52.17", 12_500_000)
    assert raw["filing_status"] == "TIMELY" and raw["claim_cutoff_exclusive"] == "2026-11-14T00:00:00+00:00"
    assert raw["trace"][0].startswith("44595/44640 UTC minutes available")


@pytest.mark.parametrize("minutes", [0, 44])
def test_complete_month_can_establish_that_the_target_was_met(minutes):
    raw = evaluated(minutes)
    assert raw["outcome"] == "INELIGIBLE" and raw["amount"] is None and not raw["missing"]
    assert raw["trace"][0].startswith(f"{44640 - minutes}/44640 UTC minutes available")


def test_month_end_filing_window_and_cutoff_are_unchanged():
    late = datetime(2026, 11, 14, tzinfo=UTC)
    raw = evaluated(45, filed=late, at=late)
    assert raw["outcome"] == "INELIGIBLE" and raw["filing_status"] == "OUTSIDE_WINDOW"
    assert raw["claim_cutoff_exclusive"] == "2026-11-14T00:00:00+00:00"
    assert evaluated(45, filed=datetime(2026, 11, 13, 23, 59, tzinfo=UTC), at=late)["outcome"] == "ELIGIBLE"


def test_verified_zero_fee_yields_no_positive_credit():
    raw = evaluated(45, amount="0.00")
    assert raw["outcome"] == "INELIGIBLE" and raw["issuance_status"] == "NO_POSITIVE_CREDIT"


def test_stepped_credit_base_is_delegated_to_the_governing_fee_resolver():
    # 500 minutes: 44140/44640 available, ten completed 0.1-point steps, 50% after the cap.
    raw = evaluated(500, text=STEPPED)
    assert raw["outcome"] == "INSUFFICIENT_EVIDENCE" and raw["missing"] == ["governing_fee_context"]
    assert raw["amount"] is None and raw["rate_units"] == 50_000_000 and raw["completed_steps"] == 10
