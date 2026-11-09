"""Reproduce decision-91 evidence findings outside the W5-owned signed grant boundary.

Read-only against a fresh temporary database. Every record is authored synthetic data. The
probe prints observed behavior; it does not assert what the owning workstream should choose.
Run: uv run --locked python scripts/probe_evidence_findings_91.py
"""
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.contracts import Principal  # noqa: E402
from uptime.correspondence import CorrespondenceDesk  # noqa: E402
from uptime.correspondence_types import Claim, Delivery, Scope  # noqa: E402
from uptime.source_config import event_in_scope  # noqa: E402

SCOPE = Scope(account="account-71", vendor="Twilio", contract="agreement-X", service="Twilio Messaging API",
              component="api-east", invoice="oct-invoice", incident="evt-411", currency="USD",
              month="2026-10", region="east")
REVIEWER = Principal("bears", "operator", "reviewer")
NOW = datetime(2026, 11, 2, 9, tzinfo=UTC)
SOURCES = dict(status="status", impact="customer", invoice="billing", coverage="status")
INVOICE = dict(kind="invoice", lines=[dict(id="a", kind="affected_api", amount="621.30"),
                                      dict(id="b", kind="tax", amount="90.00")])


def interval(start, end):
    return dict(start=start, end=end)


def desk(directory, name):
    d = CorrespondenceDesk(Path(directory) / f"{name}.db", clock=lambda: NOW)
    d.provision("bears", SCOPE.account, SCOPE.vendor, SCOPE.contract, SCOPE.service, SCOPE.component, SCOPE.region)
    for source in set(SOURCES.values()):
        d.bind_sender("bears", SCOPE.account, source, source + "-fixture")
    d.create(REVIEWER, Claim(claim_id="inbox-probe", scope=SCOPE))
    return d


def send(d, kind, body, event_id):
    event = Delivery(event_id=event_id, scope=SCOPE, body=body)
    try:
        d.receive(Principal("bears", SOURCES[kind] + "-fixture", "service"), "inbox-probe", event)
        stored = "stored"
    except (PermissionError, ValueError) as exc:
        stored = type(exc).__name__ + ": " + str(exc)
    return dict(event_id=event_id, kind=kind, embedded_desk=stored,
                signed_grant_admits=event_in_scope(event, SOURCES[kind], SCOPE))


def view(d):
    row = d.case(REVIEWER, "inbox-probe")
    return dict(outcome=str(row["preflight"]["outcome"]), trace=row["preflight"]["trace"], amount=row["amount"])


def wrong_period_occupies_the_single_status_record(directory):
    d = desk(directory, "period")
    steps = [send(d, "status", dict(kind="status", **interval("2026-09-18T13:11:00Z", "2026-09-18T13:40:00Z")), "status.september")]
    first = view(d)
    october = interval("2026-10-18T13:11:00Z", "2026-10-18T13:40:00Z")
    steps.append(send(d, "status", dict(kind="status", **october), "status.october"))
    steps.append(send(d, "impact", dict(kind="impact", **october, affected=True, exclusion="none"), "impact"))
    steps.append(send(d, "invoice", INVOICE, "invoice"))
    return dict(owner="W4 disputes (uptime/correspondence.py receive path)", deliveries=steps,
                after_wrong_period=first, after_correct_records=view(d))


def single_status_record_is_treated_as_complete_month(directory):
    results = {}
    for name, with_coverage in (("without_coverage", False), ("with_coverage", True)):
        d = desk(directory, "complete-" + name)
        brief = interval("2026-10-18T13:11:00Z", "2026-10-18T13:13:00Z")
        send(d, "status", dict(kind="status", **brief), "status")
        send(d, "impact", dict(kind="impact", **brief, affected=True, exclusion="none"), "impact")
        send(d, "invoice", INVOICE, "invoice")
        if with_coverage:
            send(d, "coverage", dict(kind="coverage", **interval("2026-10-01T00:00:00Z", "2026-11-01T00:00:00Z"),
                                     complete=True, exclusions_removed=True, incident_ids=[SCOPE.incident],
                                     total_eligible_minutes=2), "coverage")
        results[name] = view(d)
    return dict(owner="W4 disputes / W2 Twilio rules (uptime/correspondence_rules.py ordinary profile)",
                record="one signed two-minute status interval for a per-incident grant", **results)


def foreign_account_row_is_stored_on_embedded_channel(directory):
    d = desk(directory, "nested")
    body = dict(kind="invoice", lines=[dict(id="a", kind="affected_api", amount="84.00", account="someone-else")])
    return dict(owner="W4 disputes (embedded and HMAC fixture channels)", delivery=send(d, "invoice", body, "invoice.foreign"),
                after=view(d))


def main():
    with tempfile.TemporaryDirectory() as directory:
        report = dict(probe="decision-91 evidence applicability findings", clock=NOW.isoformat(),
                      wrong_period=wrong_period_occupies_the_single_status_record(directory),
                      implicit_completeness=single_status_record_is_treated_as_complete_month(directory),
                      nested_foreign_account=foreign_account_row_is_stored_on_embedded_channel(directory))
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
