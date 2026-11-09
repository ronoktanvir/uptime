"""Scope selection must ignore non-overlapping versions, without selecting within a split month."""
from contextlib import closing
import json
import sqlite3

import pytest

from uptime.claim_scope import IncidentScope, InvalidClaimScope, ServiceMonthScope, admit
from uptime.correspondence_types import Scope
from uptime.vendor_terms import Document, compile_terms, candidate_version

TEXT = """Synthetic public test contract
Vendor: Boreal Relay
Agreement: BR-74
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
For Message Store on the Team plan, monthly availability below 99.9% earns a 12.5% service credit.
Claims must be received within 13 calendar days after month end.
Service credits apply to affected monthly fees on a future invoice."""
BASIS = "Claims are based on a complete UTC calendar-month report for the entire service; incident identifiers are not required."
BASE = dict(account="north-612", vendor="Boreal Relay", contract="BR-74", service="Message Store",
            currency="USD", month="2026-10")
OVERLAY = dict(agreement="BR-74", account="north-612", product="Message Store", plan="Team",
               fee_line_ref="monthly-store", currency="USD", effective_from="2026-01-01", effective_until="2026-12-31")


def artifact(start="2026-01-01", end="2026-12-31", *, whole=False, overlay_start=None, overlay_end=None):
    period = start + (" through " + end if end else "")
    text = TEXT.replace("2026-01-01 through 2026-12-31", period) + ("\n" + BASIS if whole else "")
    manifest = compile_terms(Document(name="Public period control", uri="urn:synthetic:period-control",
                                      classification="synthetic_public", text=text))
    overlay = dict(OVERLAY, effective_from=overlay_start or start, effective_until=overlay_end or end or "2026-12-31")
    extraction = {}
    return dict(manifest=manifest, overlay=overlay, extraction=extraction, source_text=text)


def setup(db, active, candidate=None):
    """Public in-memory storage shape; real compiler artifacts, no authority or review impersonation."""
    db.executescript("""CREATE TABLE v4_vendor_event(tenant TEXT,vendor TEXT,revision INTEGER,payload TEXT);
        CREATE TABLE v4_vendor_artifact(tenant TEXT,vendor TEXT,version TEXT,payload TEXT);""")
    for installation, value, state_name in [("period-active", active, "ACTIVE")] + (
            [("period-shadow", candidate, "SHADOW")] if candidate is not None else []):
        version = candidate_version(value["manifest"], value["overlay"], value["extraction"])
        db.execute("INSERT INTO v4_vendor_artifact VALUES(?,?,?,?)", ("bears", installation, version, json.dumps(value)))
        state = dict(state=state_name, version=version, active_version=version if state_name == "ACTIVE" else None)
        db.execute("INSERT INTO v4_vendor_event VALUES(?,?,?,?)", ("bears", installation, 1, json.dumps(state)))


def selected(active, candidate=None, *, whole=False, month="2026-10"):
    scope = Scope(**dict(BASE, month=month), **({} if whole else {"incident": "period-incident"}))
    with closing(sqlite3.connect(":memory:")) as db:
        setup(db, active, candidate)
        return admit(db, "bears", scope)


def test_future_shadow_does_not_change_scope_of_current_month():
    assert type(selected(artifact(end="2026-10-31"), artifact(start="2026-11-01", whole=True))) is IncidentScope


def test_expired_candidate_does_not_change_scope_of_current_whole_month():
    assert type(selected(artifact(start="2026-11-01", whole=True), artifact(end="2026-10-31"),
                         whole=True, month="2026-11")) is ServiceMonthScope


@pytest.mark.parametrize("changes", [
    dict(start="2026-11-01", overlay_start="2026-01-01"),
    dict(overlay_start="2026-11-01"),
    dict(end="2026-09-30", overlay_end="2026-12-31"),
    dict(overlay_end="2026-09-30"),
])
def test_scope_uses_intersection_of_source_and_overlay_periods(changes):
    assert type(selected(artifact(), artifact(whole=True, **changes))) is IncidentScope


@pytest.mark.parametrize("start,end", [
    ("2026-09-01", "2026-11-30"),  # genuine overlap
    ("2026-10-01", "2026-10-01"),  # first day still overlaps
    ("2026-10-31", "2026-10-31"),  # inclusive last day still overlaps
    ("2026-10-15", "2026-10-16"),  # partial-month overlap
])
def test_any_overlap_retains_ambiguity_between_different_scope_variants(start, end):
    with pytest.raises(InvalidClaimScope, match="ambiguous"):
        selected(artifact(), artifact(start, end, whole=True))


def test_split_month_cannot_choose_a_scope_variant_from_either_half():
    with pytest.raises(InvalidClaimScope, match="ambiguous"):
        selected(artifact(start="2026-10-01", end="2026-10-15"),
                 artifact(start="2026-10-16", end="2026-10-31", whole=True))


def test_open_ended_source_uses_its_bounded_overlay():
    assert type(selected(artifact(), artifact(start="2026-01-01", end=None, whole=True,
                                             overlay_start="2026-11-01"))) is IncidentScope


def test_no_applicable_contract_does_not_inherit_an_expired_scope():
    with pytest.raises(InvalidClaimScope, match="unknown family"):
        selected(artifact(end="2026-09-30"))


@pytest.mark.parametrize("mutate", ["source_missing", "source_bad_date", "source_reversed", "overlay_missing", "overlay_reversed"])
def test_malformed_effective_period_cannot_be_silently_ignored(mutate):
    bad = artifact(whole=True)
    if mutate == "source_missing": del bad["manifest"]["effective"]
    elif mutate == "source_bad_date": bad["manifest"]["effective"][0] = "2026-02-30"
    elif mutate == "source_reversed": bad["manifest"]["effective"] = ["2026-12-31", "2026-01-01"]
    elif mutate == "overlay_missing": del bad["overlay"]["effective_from"]
    elif mutate == "overlay_reversed": bad["overlay"].update(effective_from="2026-12-31", effective_until="2026-01-01")
    with pytest.raises(InvalidClaimScope, match="effective period"):
        selected(artifact(), bad)


def test_future_shadow_cannot_change_scope_through_ordinary_claim_route(tmp_path, monkeypatch):
    from test_mf1109_route import App, TEXT as ROUTE_TEXT, BASIS_CLAUSE, INCIDENT, WHOLE

    monkeypatch.delenv("UPTIME_PUBLIC_EXTRACTIONS", raising=False)
    app = App(tmp_path / "period-routes.db")
    try:
        prior = ROUTE_TEXT.replace("2026-01-01 through 2026-12-31", "2026-01-01 through 2026-10-31")
        replacement = ROUTE_TEXT.replace("2026-01-01 through 2026-12-31", "2026-11-01 through 2026-12-31")
        app.activate(app.install(prior))
        shadow = app.post("/api/vendors/future-period-install/candidates", dict(
            document=dict(name="Future period agreement", uri="urn:synthetic:future-period-agreement",
                          classification="synthetic_public", text=replacement + "\n" + BASIS_CLAUSE),
            overlay=OVERLAY))
        assert shadow["state"] == "SHADOW"
        app.provision(WHOLE)
        wrong = app.create(WHOLE)
        assert wrong.status_code == 409 and "requires incident" in wrong.text
        app.provision(INCIDENT)
        correct = app.create(INCIDENT)
        assert correct.status_code == 200 and correct.json()["scope"] == INCIDENT
    finally:
        app.client.close()


def test_leap_day_remains_an_overlap_and_march_first_does_not():
    current = artifact(start="2028-02-01", end="2028-02-29")
    future = artifact(start="2028-03-01", end="2028-12-31", whole=True)
    assert type(selected(current, future, month="2028-02")) is IncidentScope
    leap_day = artifact(start="2028-02-29", end="2028-02-29", whole=True)
    with pytest.raises(InvalidClaimScope, match="ambiguous"):
        selected(current, leap_day, month="2028-02")
