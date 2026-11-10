"""Demo line, round two: the March price exception, automatic notes, a read-only refresh and
the credit as Ramp shows it. Only simulated providers; no credential, network or Ramp request.
"""
from datetime import timedelta
import json
import shutil

from fastapi.testclient import TestClient
import pytest

from ramp_demo_sample import (BUSINESS, MARCH_BILL, MARCH_SAMPLE, NORTHWIND_BILL, SAMPLE, fake_ramp, march_sample,
                              northwind_bill, northwind_credit, northwind_sample)
from scripts import setup_northwind as setup
from uptime import ramp_demo
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.ramp_context import verified_record_from
from uptime.ramp_workflow import SimulatedWorkflowProvider

POSSIBLE = ("Uptime: this bill may be eligible for a USD 2,400.00 service credit under agreement NW-2026-001 "
            "(January 2026 availability). A claim is being prepared in Uptime.")
APPLIED = ("Uptime: the vendor awarded a USD 2,400.00 service credit and it has been applied to this invoice in "
           "Uptime. Remaining balance USD 8,600.00.")


class Providers:
    """One simulated Ramp discussion; ``fail`` makes the next posts refuse like a missing credential."""

    def __init__(self):
        self.sim, self.fail = None, False

    def __call__(self, business_id):
        if self.fail:
            raise ramp_demo.NoteRefused("No Ramp sandbox credential is available to this server; start it with "
                                        "UPTIME_RAMP_CREDENTIAL_FILE set to the credential file.")
        if self.sim is None:
            self.sim = SimulatedWorkflowProvider(business_id=business_id, records={})
        return self.sim

    def thread(self, bill):
        return [t["message"] for t in self.sim.threads.get(("bills", bill), [])]


class Reader:
    """Read-only Ramp double for the refresh: the records reader plus the business read."""

    def __init__(self):
        self.ramp, self.made = None, 0

    def set(self, bills, credits=()):
        self.ramp = fake_ramp(bills, credits)
        self.ramp._basic = "FAKE"
        self.ramp._http = lambda method, path, headers, body=None: (
            {"access_token": "FAKE", "token_type": "bearer", "scope": "business:read"} if path == "token"
            else {"id": BUSINESS})

    def __call__(self):
        self.made += 1
        return self.ramp


def workspace(base, *, notes, providers, reader=None):
    records = base / "records"
    records.mkdir()
    for sample in (SAMPLE, MARCH_SAMPLE):
        shutil.copy(sample, records / sample.name)
    app, private, events = setup.prepare(base / "ws", DEFAULT_ORIGIN, routine_automation=True, ramp_records=records,
                                         ramp_notes=notes, ramp_provider=providers, ramp_reader=reader)
    return app, private, events


def by_bill(payload):
    return {r["ramp_context"]["object_id"]: r for r in payload["verified_records"]}


@pytest.fixture(scope="module")
def auto(tmp_path_factory):
    providers = Providers()
    app, private, events = workspace(tmp_path_factory.mktemp("auto"), notes="auto", providers=providers)
    out = {"providers": providers}
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        setup.seed(client, app, private, events)
        out["startup"] = app.state.ramp_demo.auto_sync()       # what setup_northwind runs before serving
        out["after_startup"] = {b: providers.thread(b) for b in (NORTHWIND_BILL, MARCH_BILL)}
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        ramp = lambda: client.get("/api/ramp/workspace", headers=actor.headers).json()
        out["first"] = ramp()
        decisions = []
        while (view := setup.checked(client.get("/api/workspace/workflow", headers=actor.headers))["workflow"])["next_actions"]:
            if view["next_actions"][0]["label"] == "Apply credit to eligible invoice":
                providers.fail = True                           # the credit_applied post will be refused
            decisions.append(actor.post("/api/workspace/workflow/actions/" + view["next_actions"][0]["id"], {}).status_code)
        out["decisions"] = decisions
        out["failed"] = ramp()
        out["thread_while_failing"] = providers.thread(NORTHWIND_BILL)
        providers.fail = False
        app.state.ramp_demo._failed_at -= timedelta(seconds=61)  # the retry is due again
        out["retried"] = ramp()
    return out


def test_the_march_bill_matches_as_a_price_exception(auto):
    march = by_bill(auto["first"])[MARCH_BILL]["match"]
    assert march["kind"] == "price_exception" and march["route"] == "recovery"
    assert march["invoice"] == {"id": "NW-2026-03", "vendor": "Northwind Cloud", "total": "12000.00", "currency": "USD"}
    exception = march["exception"]
    assert {k: exception[k] for k in ("amount", "currency", "billed", "expected", "state")} == {
        "amount": "1000.00", "currency": "USD", "billed": "12000.00", "expected": "11000.00", "state": "OPEN"}
    assert exception["review_stage"] == "PREPAYMENT_REVIEW"
    assert exception["basis"].endswith("amendment-2026-03.txt:3")
    assert march["agreement"]["id"] == "NW-2026-001"
    assert march["agreement"]["clause"].startswith("2. Governing fee and ceiling.")
    assert march["agreement"]["citation"] == exception["basis"] + " · urn:northwind:NW-2026-001:amendment-2026-03.txt"
    assert march["balance"] == {"invoice": "12000.00", "credit_applied": "0.00", "remaining": "12000.00"}
    assert march["next_action"] is None
    april = by_bill(auto["first"])[NORTHWIND_BILL]["match"]
    assert april["kind"] == "service_credit" and april["route"] == "recovery"


def test_auto_notes_post_at_start_up_and_when_the_stage_changes(auto):
    assert auto["first"]["notes_mode"] == "auto"
    assert sorted(auto["startup"]["posted"]) == sorted([(NORTHWIND_BILL, "possible_credit"), (MARCH_BILL, "price_exception")])
    assert auto["after_startup"][NORTHWIND_BILL] == [POSSIBLE]
    basis = by_bill(auto["first"])[MARCH_BILL]["match"]["exception"]["basis"]
    assert auto["after_startup"][MARCH_BILL] == [
        f"Uptime: this bill is USD 1,000.00 above the contracted rate ({basis}). Review it in Uptime before payment."]
    marks = {b: [(n["by"], n["kind"]) for n in r["notes"]] for b, r in by_bill(auto["first"]).items()}
    assert marks[NORTHWIND_BILL] == [("UPTIME", "possible_credit")] and marks[MARCH_BILL] == [("UPTIME", "price_exception")]
    # Later stages posted nothing new until APPLIED; each kind is posted once.
    assert auto["providers"].thread(NORTHWIND_BILL) == [POSSIBLE, APPLIED]
    assert len(auto["providers"].thread(MARCH_BILL)) == 1


def test_a_failed_note_never_breaks_a_decision_and_is_recorded(auto):
    assert auto["decisions"] == [200, 200, 200, 200]
    assert auto["thread_while_failing"] == [POSSIBLE]
    errors = auto["failed"]["notes_errors"]
    assert [(e["bill_id"], e["kind"]) for e in errors] == [(NORTHWIND_BILL, "credit_applied")]
    assert errors[0]["sentence"].startswith("No Ramp sandbox credential is available")
    assert auto["retried"]["notes_errors"] == []
    kinds = [n["kind"] for n in by_bill(auto["retried"])[NORTHWIND_BILL]["notes"]]
    assert kinds == ["possible_credit", "credit_applied"]


def test_manual_mode_posts_a_price_exception_only_on_its_own_bill(tmp_path):
    providers = Providers()
    app, private, events = workspace(tmp_path, notes="manual", providers=providers)
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        setup.seed(client, app, private, events)
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        first = client.get("/api/ramp/workspace", headers=actor.headers).json()
        wrong = actor.post("/api/ramp/notes", {"bill_id": MARCH_BILL, "kind": "possible_credit"})
        right = actor.post("/api/ramp/notes", {"bill_id": MARCH_BILL, "kind": "price_exception"})
    assert first["notes_mode"] == "manual" and providers.sim is not None
    assert wrong.status_code == 409 and wrong.json() == {"detail": "That note does not apply to this bill."}
    assert right.status_code == 200 and "above the contracted rate" in right.json()["text"]
    assert providers.thread(NORTHWIND_BILL) == []  # manual mode posts nothing by itself


def test_notes_mode_is_off_without_the_option(tmp_path):
    app, private, _ = setup.prepare(tmp_path / "ws", DEFAULT_ORIGIN)
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        body = client.get("/api/ramp/workspace", headers=actor.headers).json()
        refresh = actor.post("/api/ramp/refresh", {})
    assert body["notes_mode"] == "off" and body["notes_errors"] == []
    assert refresh.status_code in (404, 405)


def test_refresh_reads_ramp_again_and_shows_a_both_sided_credit(tmp_path):
    reader = Reader()
    app, private, events = workspace(tmp_path, notes=False, providers=None, reader=reader)
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        setup.seed(client, app, private, events)
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        before = by_bill(client.get("/api/ramp/workspace", headers=actor.headers).json())
        # Ramp now shows the vendor credit applied to the April bill on both sides.
        reader.set([northwind_bill(credit=240000),
                    northwind_bill(MARCH_BILL, invoice_number="NW-2026-03", total=1200000,
                                   issued="2026-03-01T00:00:00+00:00")], [northwind_credit()])
        refreshed = actor.post("/api/ramp/refresh", {})
        after = by_bill(client.get("/api/ramp/workspace", headers=actor.headers).json())
    assert before[NORTHWIND_BILL]["read"]["live"] is False
    assert before[NORTHWIND_BILL]["match"]["ramp_credit"] == {"status": "NONE", "amount": None}
    assert refreshed.status_code == 200 and refreshed.json()["read_errors"] == []
    assert by_bill(refreshed.json()) .keys() == after.keys()
    for bill in (NORTHWIND_BILL, MARCH_BILL):
        assert after[bill]["read"]["live"] is True and after[bill]["read"]["at"] == after[bill]["capture"]["observed_at"]
    assert after[NORTHWIND_BILL]["match"]["ramp_credit"] == {"status": "APPLIED_CONFIRMED", "amount": "2400.00"}
    docusign = next(r for b, r in after.items() if b not in (NORTHWIND_BILL, MARCH_BILL))
    assert docusign["read"]["live"] is False  # only matched bills are read again


def test_ramp_credit_is_confirmed_only_on_both_sides():
    def credit(**sample):
        body = northwind_sample(**sample)
        return ramp_demo.ramp_credit(body, verified_record_from(body))
    assert credit() == {"status": "NONE", "amount": None}
    assert credit(credit=240000, credits=[northwind_credit()]) == {"status": "APPLIED_CONFIRMED", "amount": "2400.00"}
    # Credit side only (the bill does not list it): not confirmed.
    assert credit(credits=[northwind_credit()])["status"] != "APPLIED_CONFIRMED"
    # Bill side only (the credit does not list the bill): not confirmed.
    assert credit(credit=240000, credits=[northwind_credit(bill_side=False)])["status"] != "APPLIED_CONFIRMED"


def test_refresh_without_the_credential_answers_with_one_sentence(tmp_path, monkeypatch):
    monkeypatch.delenv("RAMP_ENV", raising=False)
    app, private, events = workspace(tmp_path, notes=False, providers=None, reader=ramp_demo.sandbox_reader)
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        setup.seed(client, app, private, events)
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        refused = actor.post("/api/ramp/refresh", {})
    assert refused.status_code == 409
    assert refused.json() == {"detail": "This server was not started with RAMP_ENV=sandbox, so Uptime cannot reach Ramp."}


def test_the_committed_march_sample_is_the_packaging_output():
    assert json.loads(MARCH_SAMPLE.read_text()) == march_sample()
