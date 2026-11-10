"""Demo line: several verified Ramp bills, their walkthrough match and Uptime's notes on the bill.

Only a simulated comment provider is used. No credential, network or Ramp request.
"""
import json
import shutil
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from ramp_demo_sample import NORTHWIND_BILL, SAMPLE, northwind_sample
from scripts import setup_northwind as setup
from uptime import ramp_demo
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.ramp import Token
from uptime.ramp_context import verified_record
from uptime.ramp_workflow import SimulatedWorkflowProvider

POSSIBLE = ("Uptime: this bill may be eligible for a USD 2,400.00 service credit under agreement NW-2026-001 "
            "(January 2026 availability). A claim is being prepared in Uptime.")
APPLIED = ("Uptime: the vendor awarded a USD 2,400.00 service credit and it has been applied to this invoice in "
           "Uptime. Remaining balance USD 8,600.00.")
CLAUSE = ("For Cloud Hosting on the Business plan, the monthly uptime target is 99.9%; each completed 0.1 percentage "
          "point of shortfall below the target earns a 10% service credit, capped at 100%.")


class Providers:
    def __init__(self):
        self.made, self.sim = [], None

    def __call__(self, business_id):
        if self.sim is None:
            self.sim = SimulatedWorkflowProvider(business_id=business_id, records={})
        assert self.sim.business_id == business_id
        self.made.append(business_id)
        return self.sim


@pytest.fixture(scope="module")
def walk(tmp_path_factory):
    """One walkthrough with the sample folder and notes on; observations at every stage."""
    base = tmp_path_factory.mktemp("ramp-demo")
    records = base / "records"
    records.mkdir()
    shutil.copy(SAMPLE, records / SAMPLE.name)
    providers = Providers()
    directory = base / "ws"
    app, private, events = setup.prepare(directory, DEFAULT_ORIGIN, routine_automation=True,
                                         ramp_records=records, ramp_notes=providers)
    seen = []
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        setup.seed(client, app, private, events)
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        ramp = lambda: client.get("/api/ramp/workspace", headers=actor.headers).json()
        note = lambda bill, kind: actor.post("/api/ramp/notes", {"bill_id": bill, "kind": kind})
        first = ramp()
        early = {"applied_too_soon": note(NORTHWIND_BILL, "credit_applied"),
                 "possible": note(NORTHWIND_BILL, "possible_credit"),
                 "again": note(NORTHWIND_BILL, "possible_credit"),
                 "docusign": note(first["verified_record"]["ramp_context"]["object_id"], "possible_credit"),
                 "unknown": note("00000000-0000-0000-0000-0000000000ff", "possible_credit"),
                 "bad_kind": actor.post("/api/ramp/notes", {"bill_id": NORTHWIND_BILL, "kind": "anything"})}
        calls_after_possible = len(providers.sim.calls)
        while True:
            view = setup.checked(client.get("/api/workspace/workflow", headers=actor.headers))["workflow"]
            seen.append(ramp()["verified_records"][1]["match"])
            if not view["next_actions"]:
                break
            setup.checked(actor.post("/api/workspace/workflow/actions/" + view["next_actions"][0]["id"], {}))
        late = {"applied": note(NORTHWIND_BILL, "credit_applied"), "applied_again": note(NORTHWIND_BILL, "credit_applied")}
        # A non-matching copy dropped into <workspace>/ramp/ loads but never matches.
        (directory / "ramp").mkdir()
        (directory / "ramp" / "other.json").write_text(json.dumps(northwind_sample(total=1100001)))
        final = ramp()
    return dict(first=first, early=early, late=late, seen=seen, final=final, providers=providers,
                calls_after_possible=calls_after_possible, directory=directory, records=records)


def test_several_verified_bills_load_and_the_single_record_is_unchanged(walk):
    first = walk["first"]
    assert first["verified_record"] == verified_record()
    records = first["verified_records"]
    assert len(records) == 2
    docusign, northwind = records
    assert {k: v for k, v in docusign.items() if k not in ("match", "notes", "read")} == verified_record()
    assert docusign["read"] == {"at": verified_record()["capture"]["observed_at"], "live": False}
    assert northwind["ramp_context"]["object_id"] == NORTHWIND_BILL
    assert northwind["ramp_context"]["vendor_name"] == "Northwind Cloud"
    assert northwind["kind"] == "SAVED_VERIFIED_RECORD" and northwind["live_read"] is False
    assert len(walk["final"]["verified_records"]) == 3  # plus the <workspace>/ramp/ copy


def test_the_northwind_sample_matches_and_the_docusign_bill_does_not(walk):
    docusign, northwind = walk["first"]["verified_records"]
    assert docusign["match"] is None
    assert docusign["notes"] == [{"id": docusign["ramp_context"]["discussion"][0]["comment_id"],
                                  "at": docusign["ramp_context"]["discussion"][0]["created_at"],
                                  "by": "RAMP", "kind": None}]
    assert northwind["match"] == {
        "kind": "service_credit",
        "basis": ["vendor_name", "invoice_number", "amount"],
        "invoice": {"id": "NW-2026-04", "vendor": "Northwind Cloud", "total": "11000.00", "currency": "USD"},
        "credit": {"amount": "2400.00", "currency": "USD", "service_month": "2026-01", "stage": "ESTIMATED"},
        "agreement": {"id": "NW-2026-001", "clause": CLAUSE, "citation": "Clause 6 · urn:northwind:NW-2026-001:sla",
                      "read_by": "deterministic_document_parser"},
        "inputs": [{"label": "Eligible downtime minutes", "value": "135"},
                   {"label": "Completed steps below target", "value": "2"},
                   {"label": "Credit percent", "value": "20%"},
                   {"label": "Governing monthly fee", "value": "USD 12000.00"}],
        "balance": {"invoice": "11000.00", "credit_applied": "0.00", "remaining": "11000.00"},
        "ramp_credit": {"status": "NONE", "amount": None},
        "next_action": {"label": "Approve January claim"},
        "route": "recovery"}
    assert walk["final"]["verified_records"][2]["match"] is None  # amount differs by one cent


def test_the_match_follows_the_credit_lifecycle(walk):
    stages = [m["credit"]["stage"] for m in walk["seen"]]
    assert stages == ["ESTIMATED", "CLAIMED", "AWARDED", "POSTED", "APPLIED"]
    assert all(m["credit"]["amount"] == "2400.00" for m in walk["seen"])
    assert [m["next_action"] and m["next_action"]["label"] for m in walk["seen"]] == [
        "Approve January claim", "Approve response", "Post to Local ledger", "Apply credit to eligible invoice", None]
    assert walk["seen"][-2]["balance"] == {"invoice": "11000.00", "credit_applied": "0.00", "remaining": "11000.00"}
    assert walk["seen"][-1]["balance"] == {"invoice": "11000.00", "credit_applied": "2400.00", "remaining": "8600.00"}


def test_the_note_posts_once_reads_back_and_is_marked_as_uptime(walk):
    early, late, sim = walk["early"], walk["late"], walk["providers"].sim
    assert early["possible"].status_code == 200
    posted = early["possible"].json()
    assert posted["status"] == "POSTED" and posted["text"] == POSSIBLE and posted["comment_id"] and posted["at"]
    assert early["again"].json() == posted
    assert walk["calls_after_possible"] == 1
    assert late["applied"].json()["text"] == APPLIED and late["applied_again"].json() == late["applied"].json()
    assert [c for c in sim.calls] == [("POST", "/developer/v1/comments/bills/" + NORTHWIND_BILL)] * 2
    thread = sim.threads[("bills", NORTHWIND_BILL)]
    assert [t["message"] for t in thread] == [POSSIBLE, APPLIED]
    notes = walk["final"]["verified_records"][1]["notes"]
    assert notes == [{"id": posted["comment_id"], "at": posted["at"], "by": "UPTIME", "kind": "possible_credit"},
                     {"id": late["applied"].json()["comment_id"], "at": late["applied"].json()["at"], "by": "UPTIME",
                      "kind": "credit_applied"}]
    assert set(walk["providers"].made) == {northwind_sample()["association"]["business_id"]}


def test_refusals_are_plain_sentences(walk):
    early = walk["early"]
    assert early["applied_too_soon"].status_code == 409
    assert early["applied_too_soon"].json() == {"detail": "The credit has not been applied to this invoice in Uptime yet."}
    assert early["docusign"].status_code == 409
    assert early["docusign"].json()["detail"] == ("This Ramp bill does not match a walkthrough invoice, "
                                                  "so Uptime has no note for it.")
    assert early["unknown"].status_code == 404
    assert early["bad_kind"].status_code == 422


def test_the_note_route_is_absent_without_the_option(walk):
    app, private, _ = setup.open_workspace(walk["directory"], ramp_records=walk["records"])
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        refused = actor.post("/api/ramp/notes", {"bill_id": NORTHWIND_BILL, "kind": "possible_credit"})
        records = client.get("/api/ramp/workspace", headers=actor.headers).json()["verified_records"]
    assert refused.status_code in (404, 405)
    assert not any(getattr(r, "path", None) == "/api/ramp/notes" for r in app.routes)
    # Recorded notes still show as Uptime's on the bill.
    assert [n["by"] for n in records[1]["notes"]] == ["UPTIME", "UPTIME"]


def test_the_committed_sample_is_the_packaging_output():
    assert json.loads(SAMPLE.read_text()) == northwind_sample()
    raw = SAMPLE.read_text().lower()
    assert not any(word in raw for word in ("token", "secret", "password", "bearer", "client_id"))


def test_missing_credential_or_scope_answers_with_one_sentence(monkeypatch, tmp_path):
    monkeypatch.delenv("RAMP_ENV", raising=False)
    with pytest.raises(ramp_demo.NoteRefused, match="RAMP_ENV=sandbox"):
        ramp_demo.sandbox_provider(NORTHWIND_BILL)
    monkeypatch.setenv("RAMP_ENV", "sandbox")
    monkeypatch.setenv("UPTIME_RAMP_CREDENTIAL_FILE", str(tmp_path / "absent.json"))
    with pytest.raises(ramp_demo.NoteRefused, match="UPTIME_RAMP_CREDENTIAL_FILE"):
        ramp_demo.sandbox_provider(NORTHWIND_BILL)

    class ReadOnly:
        def token(self, scopes):
            return Token("FAKE", frozenset({"bills:read"}), frozenset(scopes))

    import uptime.ramp
    monkeypatch.setattr(uptime.ramp, "SandboxRampProvider", ReadOnly)
    with pytest.raises(ramp_demo.NoteRefused) as refused:
        ramp_demo.sandbox_provider(NORTHWIND_BILL)
    assert str(refused.value) == "The Ramp credential was not granted bills:write, so Uptime cannot post the note."


def test_ramp_notes_requires_serve(tmp_path):
    result = subprocess.run([sys.executable, str(setup.ROOT / "scripts/setup_northwind.py"), "--directory",
                             str(tmp_path / "ws"), "--ramp-notes"], capture_output=True, text=True, timeout=120,
                            cwd=setup.ROOT)
    assert result.returncode == 2 and result.stderr.strip().splitlines()[-1].endswith("--ramp-notes requires --serve")
    assert not (tmp_path / "ws").exists()
