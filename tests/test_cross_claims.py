"""Real local route integration; all source inputs and receipts are synthetic.

These assertions concern ownership, availability and effects, not legal entitlement
or recovered money. Source authentication is covered separately by the API suites.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
import json
import sqlite3

import pytest

from uptime import disputes_vendor
from uptime.claim_identity import TABLE, reserve_claim
from uptime.contracts import Principal
from uptime.correspondence import CorrespondenceDesk
from uptime.correspondence_types import Claim, Delivery, Scope
from uptime.disputes import DisputeDesk

P = Principal("bears", "synthetic-reviewer", "reviewer")
AT = datetime(2026, 11, 2, 10, tzinfo=UTC)
LEGACY = "dispute-partial"
INBOX = "inbox-independent-intake"


def setup(path):
    legacy = DisputeDesk(path, clock=lambda: AT)
    legacy.seed(P.tenant)
    with sqlite3.connect(path) as db:
        dossier = json.loads(db.execute("SELECT dossier FROM dispute_cases WHERE id=?", (LEGACY,)).fetchone()[0])
    inbox = CorrespondenceDesk(path, clock=lambda: AT)
    scope = Scope(account=dossier["account"], vendor="Twilio", contract="synthetic-contract-alias",
                  service=dossier["product"], component="synthetic-component", region=dossier["region"],
                  invoice="independent-invoice-ref", incident="independent-incident-ref", currency="USD", month=dossier["month"])
    inbox.provision(P.tenant, scope.account, scope.vendor, scope.contract, scope.service, scope.component, scope.region)
    for role in ("status", "customer", "billing", "vendor"):
        inbox.bind_sender(P.tenant, scope.account, role, "synthetic-" + role, scope=scope)
    inbox.create(P, Claim(claim_id=INBOX, scope=scope))
    for source, body in (
        ("status", dict(kind="status", start=dossier["start"], end=dossier["end"])),
        ("customer", dict(kind="impact", start=dossier["start"], end=dossier["end"], affected=True, exclusion="none")),
        ("billing", dict(kind="invoice", lines=[dict(id="synthetic-fee", kind="affected_api", amount="417.30")]))):
        inbox.receive(Principal(P.tenant, "synthetic-" + source, "service"), INBOX,
                      Delivery(event_id=body["kind"], scope=scope, body=body))
    legacy.act(P, LEGACY, "approve-claim")
    inbox.act(P, INBOX, "approve-claim")
    return legacy, inbox, scope


def submissions(legacy, inbox):
    return len(legacy.case(P, LEGACY)["submissions"]) + len(inbox.case(P, INBOX)["submissions"])


@pytest.mark.parametrize("winner", ["legacy", "correspondence"])
def test_both_route_orders_restart_and_repeat_have_one_effect(tmp_path, monkeypatch, winner):
    path = tmp_path / "both.db"
    legacy, inbox, _ = setup(path)
    calls = []
    review = disputes_vendor.review
    def capture(ticket, now):
        calls.append(ticket.digest)
        return review(ticket, now)
    monkeypatch.setattr(disputes_vendor, "review", capture)
    first, first_id, second, second_id = ((legacy, LEGACY, inbox, INBOX) if winner == "legacy"
                                         else (inbox, INBOX, legacy, LEGACY))
    first.act(P, first_id, "submit-claim")
    ledger = first.case(P, first_id)["ledger"].copy()
    for _ in range(3):
        first.act(P, first_id, "submit-claim")
        with pytest.raises(ValueError, match="obligation"):
            second.act(P, second_id, "submit-claim")
    assert first.case(P, first_id)["ledger"] == ledger
    legacy = DisputeDesk(path, clock=lambda: AT.astimezone(timezone(timedelta(hours=-12))))
    inbox = CorrespondenceDesk(path, clock=lambda: AT.astimezone(timezone(timedelta(hours=14))))
    first, first_id, second, second_id = ((legacy, LEGACY, inbox, INBOX) if winner == "legacy"
                                         else (inbox, INBOX, legacy, LEGACY))
    first.act(P, first_id, "submit-claim")
    with pytest.raises(ValueError, match="obligation"):
        second.act(P, second_id, "submit-claim")
    assert submissions(legacy, inbox) == 1
    assert len(calls) == (1 if winner == "legacy" else 0)
    with sqlite3.connect(path) as db:
        assert db.execute(f"SELECT count(*) FROM {TABLE} WHERE step='initial'").fetchone()[0] == 1


def test_simultaneous_intake_repeat_and_restart(tmp_path, monkeypatch):
    path = tmp_path / "race.db"
    legacy, inbox, _ = setup(path)
    calls = []
    review = disputes_vendor.review
    def capture(ticket, now):
        calls.append(ticket.digest)
        return review(ticket, now)
    monkeypatch.setattr(disputes_vendor, "review", capture)
    def submit(index):
        desk, case = (legacy, LEGACY) if index % 2 else (inbox, INBOX)
        try:
            return desk.act(P, case, "submit-claim")
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit, range(24)))
    assert len([r for r in results if r is not None]) == 12
    assert submissions(legacy, inbox) == 1
    assert len(calls) <= 1
    legacy = DisputeDesk(path, clock=lambda: AT)
    inbox = CorrespondenceDesk(path, clock=lambda: AT)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(submit, range(24)))
    assert submissions(legacy, inbox) == 1 and len(calls) <= 1


def test_unknown_reservation_survives_restart_and_blocks_opposite_route(tmp_path):
    path = tmp_path / "unknown.db"
    legacy, inbox, scope = setup(path)
    packet = dict(tenant=P.tenant, vendor=scope.vendor, account=scope.account, agreement_id="twilio-apis",
                  agreement_version="2026-04-09", service=scope.service, month=scope.month, remedy="availability",
                  route="uncertain-delivery", case_id="unreconciled", packet_digest="1" * 64,
                  scope=scope.model_dump(), receipt_id="uncertain", at=AT.isoformat())
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        assert reserve_claim(db, **packet)["created"]
    for desk, case in ((DisputeDesk(path, clock=lambda: AT), LEGACY),
                       (CorrespondenceDesk(path, clock=lambda: AT), INBOX)):
        with pytest.raises(ValueError, match="obligation"):
            desk.act(P, case, "submit-claim")
    assert submissions(legacy, inbox) == 0


def test_historical_legacy_submission_backfills_without_loading_fixture_truth(tmp_path, monkeypatch):
    path = tmp_path / "historical.db"
    legacy, inbox, _ = setup(path)
    legacy.act(P, LEGACY, "submit-claim")
    # Model an old installation whose durable receipts predate the shared registry.
    with sqlite3.connect(path) as db:
        db.execute(f"DROP TABLE IF EXISTS {TABLE}")
    def unavailable(*args, **kwargs):
        raise AssertionError("Backfill must not call a simulator or recompute a monetary award")
    monkeypatch.setattr(disputes_vendor, "review", unavailable)
    with pytest.raises(ValueError, match="obligation"):
        inbox.act(P, INBOX, "submit-claim")
    assert submissions(legacy, inbox) == 1


def test_missing_evidence_and_correct_refusal_never_reserve(tmp_path):
    path = tmp_path / "closed.db"
    _, inbox, scope = setup(path)
    # A new, independently scoped customer with no delivered evidence.
    new_scope = scope.model_copy(update={"account": "no-evidence"})
    inbox.provision(P.tenant, new_scope.account, new_scope.vendor, new_scope.contract,
                    new_scope.service, new_scope.component, new_scope.region)
    inbox.bind_sender(P.tenant, new_scope.account, "status", "controlled-empty-status", scope=new_scope)
    inbox.create(P, Claim(claim_id="inbox-empty", scope=new_scope))
    assert not inbox.case(P, "inbox-empty")["actions"]
    with pytest.raises(ValueError):
        inbox.act(P, "inbox-empty", "approve-claim")
    # Authenticated matching maintenance that was available before filing.
    inbox.receive(Principal(P.tenant, "synthetic-customer", "service"), INBOX,
                  Delivery(event_id="known-maintenance", scope=scope,
                           body=dict(kind="notice", start="2026-10-14T12:00:00Z", end="2026-10-14T12:30:00Z",
                                     issued_at="2026-10-13T10:00:00Z")))
    row = inbox.case(P, INBOX)
    assert not row["actions"]
    with pytest.raises(ValueError):
        inbox.act(P, INBOX, "submit-claim")
    assert not row["submissions"] and row["ledger"]["claimed"] == "0.00"


def test_unknown_vendor_reply_cannot_enable_a_second_route(tmp_path):
    legacy, inbox, scope = setup(tmp_path / "unknown-reply.db")
    original = inbox.act(P, INBOX, "submit-claim")["submissions"][0]
    inbox.receive(Principal(P.tenant, "synthetic-vendor", "service"), INBOX,
                  Delivery(event_id="unrecognized-reply", scope=scope,
                           body=dict(kind="message", receipt_id=original["id"],
                                     text="The service-position committee issued a proprietary review code.")))
    row = inbox.case(P, INBOX)
    assert row["stage"] == "HUMAN_REVIEW" and not row["actions"]
    with pytest.raises(ValueError):
        inbox.act(P, INBOX, "approve-response")
    with pytest.raises(ValueError, match="obligation"):
        legacy.act(P, LEGACY, "submit-claim")
    assert submissions(legacy, inbox) == 1 and row["ledger"]["awarded"] == "0.00"


def test_definite_pure_simulator_failure_has_no_effect_and_retry_cannot_double_file(tmp_path, monkeypatch):
    legacy, inbox, _ = setup(tmp_path / "definite-failure.db")
    with monkeypatch.context() as context:
        def unavailable(*args):
            raise TimeoutError("Synthetic pure-function failure")
        context.setattr(disputes_vendor, "review", unavailable)
        row = legacy.act(P, LEGACY, "submit-claim")
    assert not row["submissions"] and row["ledger"]["claimed"] == "0.00"
    inbox.act(P, INBOX, "submit-claim")
    with pytest.raises(ValueError, match="obligation"):
        legacy.act(P, LEGACY, "submit-claim")
    assert submissions(legacy, inbox) == 1
