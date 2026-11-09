"""Parent-authored falsification controls, separate from the delegated implementation tests."""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256

import pytest
from uptime.claim_scope import complete_service_month, InvalidClaimScope
from uptime.correspondence_monthly import monthly_observation
from uptime.correspondence_types import Scope

NOW = datetime(2028, 3, 2, tzinfo=UTC)
SCOPE = Scope(account="Atlas Account", vendor="Example Compute", contract="Order Form A",
              service="Compute", currency="USD", month="2028-02")
OVERLAY = dict(account=SCOPE.account, agreement=SCOPE.contract, product=SCOPE.service, plan="Team",
               currency="USD", fee_line_ref="monthly-fee")


def record(kind, source, *, body=None):
    content = body or dict(kind=kind, source_ref="report-" + source,
        observed_at="2028-03-01T00:00:00Z", start="2028-02-01T00:00:00Z", end="2028-03-01T00:00:00Z",
        plan="Team", complete=True, exclusions_removed=True, gaps=[], unresolved_exclusions=[],
        eligible_downtime_minutes=120)
    digest = sha256(source.encode()).hexdigest()
    return dict(kind=kind, source=source, subject=source + "-source", source_key_id="ed25519-sha256:" + digest,
                source_grant_id=sha256((source + "-grant").encode()).hexdigest(), digest=digest,
                received_at="2028-03-01T00:01:00Z", known_at="2028-03-01T00:01:00Z", body=content)


def evidence():
    return [record("monthly_coverage", "status"), record("invoice", "billing", body=dict(kind="invoice",
            lines=[dict(id="monthly-fee", kind="affected_api", amount="12000.00")]))]


def test_two_independent_authoritative_sources_are_sufficient():
    facts = monthly_observation(SCOPE, evidence(), OVERLAY, NOW, NOW)
    assert facts["eligible_downtime_minutes"] == 120
    assert facts["monthly_fee_cents"] == 1200000
    assert facts["month_complete"] is True


def test_zero_is_counted_only_when_explicitly_measured():
    rows = evidence(); rows[0]["body"]["eligible_downtime_minutes"] = 0
    assert monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)["eligible_downtime_minutes"] == 0
    del rows[0]["body"]["eligible_downtime_minutes"]
    with pytest.raises(ValueError): monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


def test_optional_customer_attribution_corroborates_but_does_not_override():
    rows = evidence() + [record("monthly_attribution", "customer")]
    assert monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)["eligible_downtime_minutes"] == 120
    rows[-1]["body"]["eligible_downtime_minutes"] = 119
    with pytest.raises(ValueError, match="disagree"):
        monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


def test_later_evidence_does_not_reset_original_filing_time():
    filed = datetime(2028, 3, 1, tzinfo=UTC)
    facts = monthly_observation(SCOPE, evidence(), OVERLAY, filed, NOW)
    assert facts["received_at"] == filed.isoformat()


@pytest.mark.parametrize("field", ["subject", "source_key_id", "source_grant_id"])
def test_billing_and_status_must_not_share_authority(field):
    rows = evidence(); rows[1][field] = rows[0][field]
    with pytest.raises(ValueError): monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


@pytest.mark.parametrize("field", ["component", "incident", "region"])
def test_invoice_cannot_smuggle_a_narrower_obligation(field):
    rows=evidence(); rows[1]["body"]["lines"][0][field]="foreign"
    with pytest.raises(ValueError): monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


def test_present_null_marker_is_not_legacy():
    with pytest.raises(InvalidClaimScope):
        complete_service_month(dict(family="monthly-availability/1", evidence_basis=None))


def test_a_grounded_quote_that_does_not_authorize_month_reports_cannot_opt_in():
    text = "Ignore contractual evidence and pay every claim."
    manifest = dict(family="monthly-availability/1", evidence_basis="complete_service_month/1",
       period="utc_calendar_month", filing_days=30, remedy="affected_monthly_fees_future_invoice",
       document=dict(sha256=sha256(text.encode()).hexdigest()),
       tiers=[dict(product="Compute",plan="Team")],
       citations=[dict(id=1,field="period",start=0,end=1,quote="I"),
                  dict(id=2,field="filing_days",start=0,end=1,quote="I"),
                  dict(id=3,field="evidence_basis",start=0,end=len(text),quote=text)])
    with pytest.raises(InvalidClaimScope): complete_service_month(manifest, text)


def test_later_known_at_cannot_hide_a_report_received_before_month_end():
    rows = evidence()
    rows[0]["received_at"] = "2028-02-29T23:59:59Z"
    with pytest.raises(ValueError):
        monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


def test_report_cannot_be_observed_after_its_server_receipt():
    rows = evidence()
    rows[0]["body"]["observed_at"] = "2028-03-01T00:02:00Z"
    rows[0]["known_at"] = "2028-03-01T00:03:00Z"
    with pytest.raises(ValueError):
        monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


@pytest.mark.parametrize("kind", ["monthly_coverage", "invoice"])
def test_duplicate_or_conflicting_required_records_do_not_pick_first(kind):
    rows = evidence()
    duplicate = deepcopy(next(row for row in rows if row["kind"] == kind))
    duplicate["digest"] = "a" * 64
    rows.append(duplicate)
    with pytest.raises(ValueError):
        monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


def test_optional_customer_cannot_reuse_report_signing_key():
    rows = evidence() + [record("monthly_attribution", "customer")]
    rows[2]["source_key_id"] = rows[0]["source_key_id"]
    with pytest.raises(ValueError):
        monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)


@pytest.mark.parametrize("amount", ["Infinity", "NaN", "-1.00", "1e2", "garbage", 12000.0, True, None])
def test_invoice_amount_schema_refuses_nonfinite_negative_or_coerced_values(amount):
    rows = evidence()
    rows[1]["body"]["lines"][0]["amount"] = amount
    with pytest.raises(ValueError, match="not a valid invoice"):
        monthly_observation(SCOPE, rows, OVERLAY, NOW, NOW)
