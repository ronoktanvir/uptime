"""Demo line, round three: a Ramp bill matched to another vendor's estimated credit (Corvid Data
Cooperative), its automatic note, and who read each agreement. Simulated provider only; no
credential, network or Ramp request.
"""
import json
import shutil

from fastapi.testclient import TestClient
import pytest

from ramp_demo_sample import CORVID_BILL, CORVID_SAMPLE, MARCH_SAMPLE, NORTHWIND_BILL, SAMPLE, corvid_sample
from scripts import setup_northwind as setup
from test_ramp_demo_round2 import Providers, by_bill
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient

OTHER_CORVID_BILL = "00000000-0000-0000-0000-000020261001"
CORVID_NOTE = ("Uptime: this bill may be eligible for a USD 2,000.00 service credit under agreement CDC-SLA-07 "
               "(October 2026 availability). The estimate is waiting for review in Uptime.")


@pytest.fixture(scope="module")
def corvid(tmp_path_factory):
    base = tmp_path_factory.mktemp("corvid")
    records = base / "records"
    records.mkdir()
    for sample in (SAMPLE, MARCH_SAMPLE, CORVID_SAMPLE):
        shutil.copy(sample, records / sample.name)
    (records / "corvid-one-cent-off.json").write_text(json.dumps(corvid_sample(OTHER_CORVID_BILL, total=1000001)))
    providers = Providers()
    app, private, events = setup.prepare(base / "ws", DEFAULT_ORIGIN, routine_automation=True, ramp_records=records,
                                         ramp_notes="auto", ramp_provider=providers)
    with TestClient(app, base_url=private["origin"], client=("127.0.0.1", 1234)) as client:
        setup.seed(client, app, private, events)
        startup = app.state.ramp_demo.auto_sync()
        actor = ReviewerClient(client, private["origin"], SCRIPT, private["rehearsal_secret"])
        workspace = client.get("/api/ramp/workspace", headers=actor.headers).json()
        opportunity = setup.checked(client.get("/api/workspace/workflow", headers=actor.headers))["workflow"]["opportunities"][0]
    return dict(startup=startup, workspace=workspace, opportunity=opportunity, providers=providers)


def test_the_corvid_bill_matches_its_opportunity(corvid):
    match, opportunity = by_bill(corvid["workspace"])[CORVID_BILL]["match"], corvid["opportunity"]
    assert match == {
        "kind": "service_credit", "basis": ["vendor_name", "invoice_number", "amount"],
        "invoice": {"id": "CDC-2026-10-0117", "vendor": "Corvid Data Cooperative", "total": "10000.00", "currency": "USD"},
        "credit": {"amount": "2000.00", "currency": "USD", "service_month": "2026-10", "stage": "ESTIMATED"},
        "agreement": {"id": "CDC-SLA-07", "clause": opportunity["agreement"]["clause"],
                      "citation": opportunity["agreement"]["citation"], "read_by": "claude-opus-5-5"},
        "inputs": opportunity["inputs"],
        "balance": {"invoice": "10000.00", "credit_applied": "0.00", "remaining": "10000.00"},
        "ramp_credit": {"status": "NONE", "amount": None},
        "next_action": None, "route": "agreements"}


def test_northwind_matches_name_who_read_their_agreement(corvid):
    records = by_bill(corvid["workspace"])
    assert records[NORTHWIND_BILL]["match"]["agreement"]["read_by"] == "deterministic_document_parser"
    march = next(r for r in records.values() if r["match"] and r["match"]["kind"] == "price_exception")
    assert march["match"]["agreement"]["read_by"] == "deterministic_document_parser"


def test_auto_mode_posts_the_corvid_note_once(corvid):
    assert (CORVID_BILL, "possible_credit") in corvid["startup"]["posted"]
    assert corvid["providers"].thread(CORVID_BILL) == [CORVID_NOTE]
    notes = by_bill(corvid["workspace"])[CORVID_BILL]["notes"]
    assert [(n["by"], n["kind"]) for n in notes] == [("UPTIME", "possible_credit")]


def test_a_corvid_bill_one_cent_off_does_not_match(corvid):
    other = by_bill(corvid["workspace"])[OTHER_CORVID_BILL]
    assert other["ramp_context"]["invoice_number"] == "CDC-2026-10-0117" and other["match"] is None
    assert corvid["providers"].thread(OTHER_CORVID_BILL) == []


def test_the_committed_corvid_sample_is_the_packaging_output():
    assert json.loads(CORVID_SAMPLE.read_text()) == corvid_sample()
