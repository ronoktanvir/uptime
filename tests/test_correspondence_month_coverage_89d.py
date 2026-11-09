"""D07 / W5 F3 (narrow option): one status record cannot establish that the availability target was met."""
from datetime import timedelta

from uptime.contracts import Principal
from uptime.correspondence_types import Delivery
from test_correspondence import BODIES, ID, REVIEWER, env  # noqa: F401  (fixture)

SHORT = dict(start="2026-10-18T13:11:00Z", end="2026-10-18T13:14:00Z")  # three minutes
COVERAGE = dict(kind="coverage", start="2026-10-01T00:00:00Z", end="2026-11-01T00:00:00Z", complete=True,
                exclusions_removed=True, incident_ids=["evt-411"])


def short_incident(env):
    env.send("status", data=dict(kind="status", **SHORT))
    env.send("impact", data=dict(kind="impact", **SHORT, affected=True, exclusion="none"))
    env.send("invoice")


def coverage(env, minutes):
    env.desk.receive(Principal("bears", "status-fixture", "service"), ID,
                     Delivery(event_id="month-report", scope=env.scope, body=dict(COVERAGE, total_eligible_minutes=minutes)))


def test_target_met_from_one_status_record_is_missing_evidence(env):
    short_incident(env)
    row = env.get()
    assert row["preflight"]["outcome"] == "INSUFFICIENT_EVIDENCE" and not row["actions"]
    assert "complete-month coverage report" in row["preflight"]["missing"][0]


def test_signed_month_report_lets_the_target_be_concluded_met(env):
    short_incident(env)
    coverage(env, 3)
    row = env.get()
    assert row["preflight"]["outcome"] == "INELIGIBLE" and row["amount"] is None and not row["actions"]


def test_breach_from_a_lower_bound_still_yields_the_fixed_rate_credit(env):
    env.build()
    row = env.get()
    assert row["preflight"]["outcome"] == "ELIGIBLE" and row["amount"] == "62.13"


def test_substantiated_maintenance_exclusion_is_unchanged(env):
    env.build()
    env.send("notice")
    assert env.get()["preflight"]["outcome"] == "INELIGIBLE"
