"""Audit counterexamples plus deterministic generated variants of legacy boundaries.

Expected outcomes were frozen in oracle/v2.json before runtime edits (8626fa8).
These tests exercise real claimant, simulator and transactional SQLite code.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from pathlib import Path
import json
import sqlite3

from hypothesis import given, settings, strategies as st
import pytest

from uptime import disputes, disputes_claimant as claimant, disputes_vendor as vendor
from uptime.contracts import Outcome, Principal, fingerprint
from uptime.disputes import DisputeConflict, DisputeDesk, START
from uptime.disputes_wire import Document, FIXTURES, Reply, deadline

REVIEWER = Principal("bears", "v4-test-reviewer", "reviewer")
CURE = "dispute-cure"
PARTIAL = "dispute-partial"


def dossiers():
    return json.loads((FIXTURES / "claimant/dossiers.json").read_text())


def repin(d):
    """Explicit trusted source provisioning, never an HTTP or runtime operation."""
    d["artifact_registry"] = {doc["ref"]: fingerprint(doc) for group in claimant.GROUPS
                              for doc in d[group] if doc.get("ref") is not None}
    d["invoice_registry"] = {line["id"]: fingerprint(line) for line in d["invoice_lines"]}


def provision(tmp_path, monkeypatch, name=CURE, mutate=lambda d: None):
    ds = dossiers()
    mutate(ds[name])
    repin(ds[name])
    (tmp_path / "claimant").mkdir(exist_ok=True)
    (tmp_path / "claimant/dossiers.json").write_text(json.dumps(ds))
    monkeypatch.setattr(disputes, "FIXTURES", tmp_path)
    desk = DisputeDesk(tmp_path / "v4.sqlite")
    desk.seed("bears")
    return desk, ds[name]


def complete(desk, case):
    for _ in range(10):
        row = desk.case(REVIEWER, case)
        if not row["actions"]:
            return row
        desk.act(REVIEWER, case, row["actions"][0]["id"])
    pytest.fail("unbounded action sequence")


def test_old_governing_date_rejected_before_approval(tmp_path, monkeypatch):
    def old(d):
        for key in ("start", "end", "month"):
            d[key] = d[key].replace("2026", "2025")
    desk, d = provision(tmp_path, monkeypatch, mutate=old)
    desk.clock = lambda: datetime(2025, 11, 2, tzinfo=UTC)
    row = desk.case(REVIEWER, CURE)
    assert row["outcome"] == Outcome.UNSUPPORTED
    assert not row["actions"] and not row["submissions"]
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, CURE, "approve-claim")


@pytest.mark.parametrize("group", claimant.GROUPS)
def test_available_maintenance_in_every_archive_prevents_claim(tmp_path, monkeypatch, group):
    def known(d):
        notice = d["customer_notice_archive"].pop()
        notice.update(observed_at=notice["issued_at"], available_at=notice["issued_at"])
        d[group].append(notice)
    desk, _ = provision(tmp_path, monkeypatch, "dispute-denial", known)
    row = desk.case(REVIEWER, "dispute-denial")
    assert row["outcome"] == Outcome.INELIGIBLE
    assert not row["actions"]
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, "dispute-denial", "approve-claim")
    assert not desk.case(REVIEWER, "dispute-denial")["submissions"]


def test_notice_without_arrival_metadata_is_known_not_silently_future():
    d = dossiers()["dispute-denial"]
    notice = d["customer_notice_archive"][0]
    notice.pop("observed_at"); notice.pop("available_at")
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.INELIGIBLE


def test_later_notice_is_observably_after_submission_and_before_reply(tmp_path):
    desk = DisputeDesk(tmp_path / "later.db"); desk.seed("bears")
    row = complete(desk, "dispute-denial")
    notice = dossiers()["dispute-denial"]["customer_notice_archive"][0]
    assert row["stage"] == "DENIAL_ACCEPTED"
    assert row["submissions"][0]["at"] < notice["available_at"] <= row["replies"][0]["received_at"]
    assert row["ledger"]["claimed"] == "100.00"


@pytest.mark.parametrize("field,value", [("account", "other"), ("currency", "CAD"), ("month", "2024-08"),
    ("region", "EU1"), ("product", "Other API"), ("invoice_id", "other-invoice"),
    ("evidence_ref", "   "), ("id", "msg-1-a ")])
def test_even_authentic_invoice_lines_require_actual_scope(field, value):
    d = dossiers()[CURE]
    d["invoice_lines"][0][field] = value
    repin(d)  # The authentic source can still contain semantically wrong data.
    assert claimant.preflight(d, START).outcome == Outcome.MISSING


@pytest.mark.parametrize("field", ["account", "currency", "month", "region", "product", "invoice_id", "evidence_ref"])
def test_missing_invoice_scope_is_not_assumed(field):
    d = dossiers()[CURE]
    d["invoice_lines"][0].pop(field)
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.MISSING


@pytest.mark.parametrize("value", [None, "", " ", "\n", "status-1-summary "])
def test_bad_document_reference_is_safe_and_unclaimable(tmp_path, monkeypatch, value):
    def bad(d):
        if value is None:
            d["initial_documents"][0].pop("ref")
        else:
            d["initial_documents"][0]["ref"] = value
    # Missing references must fail in preflight rather than crash in ticket construction.
    d = dossiers()[CURE]; bad(d)
    assert claimant.preflight(d, START).outcome == Outcome.MISSING


@pytest.mark.parametrize("component", [None, "", " ", "other-component"])
def test_authentic_component_without_identity_fails_both_parties(component):
    d = dossiers()[PARTIAL]
    doc = d["initial_documents"][1]
    if component is None:
        doc.pop("component_id")
    else:
        doc["component_id"] = component
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.MISSING
    good = dossiers()[PARTIAL]
    packet = claimant.ticket_for("bears", good, [], at=START)
    bad = Document.minimized("bears", doc)
    packet = replace(packet, documents=(packet.documents[0], bad))
    record = json.loads((FIXTURES / "simulator/records.json").read_text())[packet.account]
    record["document_registry"][bad.fact.ref] = bad.fact.digest
    assert vendor.decide(packet, record, START).code == "UNVERIFIED_DOCUMENT"


def test_minimization_precedes_simulator_and_approval_hashes_wire(tmp_path, monkeypatch):
    marker = "SYNTHETIC-SENSITIVE-MARKER-DO-NOT-SEND"
    desk, d = provision(tmp_path, monkeypatch, PARTIAL,
                        lambda d: d["initial_documents"][0].update(private_notes=marker, status_subject=marker))
    seen = []
    review = vendor.review
    def capture(packet, at):
        seen.append(json.dumps(asdict(packet)))
        assert marker not in seen[-1]
        return review(packet, at)
    monkeypatch.setattr(vendor, "review", capture)
    desk.act(REVIEWER, PARTIAL, "approve-claim")
    row = desk.act(REVIEWER, PARTIAL, "submit-claim")
    assert seen and row["stage"] == "PARTIAL_AWARD_REVIEW"
    receipt = row["submissions"][0]
    assert receipt["digest"] == fingerprint(receipt["payload"]) == receipt["approval"]["digest"]
    assert marker not in json.dumps(row)


def test_artifact_bodies_and_durable_receipts_are_immutable(tmp_path):
    d = dossiers()[PARTIAL]
    doc = Document.minimized("bears", d["initial_documents"][0])
    original = doc.fact.digest
    with pytest.raises(TypeError):
        doc.body["account"] = "other"
    d["initial_documents"][0]["account"] = "other"
    assert fingerprint(doc.body) == original
    desk = DisputeDesk(tmp_path / "immutable.db"); desk.seed("bears")
    complete(desk, PARTIAL)
    with sqlite3.connect(desk.path) as db:
        for table in ("dispute_artifacts", "dispute_manifests", "dispute_receipts", "dispute_obligations"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(f"DELETE FROM {table}")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE dispute_artifacts SET digest='forged'")


def test_rehashing_changed_local_artifact_cannot_replace_source_pin(tmp_path):
    desk = DisputeDesk(tmp_path / "pins.db"); desk.seed("bears")
    with sqlite3.connect(desk.path) as db:
        d = json.loads(db.execute("SELECT dossier FROM dispute_cases WHERE id=?", (PARTIAL,)).fetchone()[0])
        d["invoice_lines"][0]["usd"] = "9000.00"
        repin(d)
        db.execute("UPDATE dispute_cases SET dossier=? WHERE id=?", (json.dumps(d), PARTIAL))
    assert not desk.case(REVIEWER, PARTIAL)["actions"]
    with pytest.raises(DisputeConflict, match="immutable"):
        desk.act(REVIEWER, PARTIAL, "approve-claim")


@pytest.mark.parametrize("field,value", [("tenant", "other"), ("account", "other"), ("vendor", "other"),
                                         ("governing_version", "2025-01-01")])
def test_vendor_independently_binds_scope(field, value):
    d = dossiers()[PARTIAL]
    ticket = claimant.ticket_for("bears", d, [], at=START)
    ticket = replace(ticket, **{field: value})
    if field == "tenant":
        ticket = replace(ticket, documents=tuple(Document.from_archive(value, doc.body) for doc in ticket.documents))
    assert vendor.review(ticket, START).code == "CONTESTED_SCOPE"


def test_cross_case_obligation_reservation_survives_races_and_restart(tmp_path, monkeypatch):
    desk = DisputeDesk(tmp_path / "duplicates.db"); desk.seed("bears")
    names = [PARTIAL] + [f"alias-{i}" for i in range(7)]
    with sqlite3.connect(desk.path) as db:
        for alias in names[1:]:
            db.execute("INSERT INTO dispute_cases SELECT tenant,?,dossier,state FROM dispute_cases WHERE id=?", (alias, PARTIAL))
    for name in names:
        desk.act(REVIEWER, name, "approve-claim")
    calls = []
    review = vendor.review
    def capture(packet, at):
        calls.append(packet.obligation_key)
        return review(packet, at)
    monkeypatch.setattr(vendor, "review", capture)
    def submit(name):
        try:
            return desk.act(REVIEWER, name, "submit-claim")
        except DisputeConflict:
            return None
    with ThreadPoolExecutor(max_workers=8) as workers:
        results = list(workers.map(submit, names))
    assert len(calls) == sum(row is not None for row in results) == 1
    winner = next(row for row in results if row)
    again = DisputeDesk(desk.path).act(REVIEWER, winner["id"], "submit-claim")
    assert again["submissions"] == winner["submissions"]
    with sqlite3.connect(desk.path) as db:
        assert db.execute("SELECT count(*) FROM dispute_receipts").fetchone()[0] == 1


def test_changed_case_and_incident_do_not_change_monthly_obligation():
    d = dossiers()[PARTIAL]
    ticket = claimant.ticket_for("bears", d, [], at=START)
    for change in ({"start": "2026-10-15T12:00:00+00:00"}, {"requested": "500.00"}, {"documents": ()}):
        revised = replace(ticket, **change)
        assert revised.digest != ticket.digest
        assert revised.obligation_key == ticket.obligation_key


def test_mistaken_time_bar_preserves_timely_initial_receipt(tmp_path, monkeypatch):
    desk = DisputeDesk(tmp_path / "timebar.db"); desk.seed("bears")
    monkeypatch.setattr(vendor, "review", lambda packet, at: Reply("WINDOW_CLOSED", "Late", "§3"))
    row = complete(desk, PARTIAL)
    assert row["stage"] == "HUMAN_REVIEW" and row["outcome"] == Outcome.MISSING
    assert row["ledger"]["claimed"] == row["ledger"]["disputed_remainder"] == "100.00"
    assert row["submissions"][0]["at"] < deadline("2026-10").isoformat()


def test_fractional_contractual_entitlement_is_not_rounded_or_sent(tmp_path, monkeypatch):
    def small(d):
        d["invoice_lines"] = [d["invoice_lines"][0]]
        d["invoice_lines"][0]["usd"] = "0.01"
    desk, d = provision(tmp_path, monkeypatch, mutate=small)
    result = claimant.preflight(d, START)
    assert result.outcome == Outcome.ELIGIBLE and result.amount.amount == Decimal("0.001")
    row = desk.case(REVIEWER, CURE)
    assert row["stage"] == "HUMAN_REVIEW" and row["amount"] == "0.001"
    assert not row["actions"] and not row["policy_dispatchable"] and not row["submissions"]
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, CURE, "approve-claim")


def test_complete_only_auto_policy_and_later_arrival_refresh(tmp_path, monkeypatch):
    desk, d = provision(tmp_path, monkeypatch)
    approved = desk.act(REVIEWER, CURE, "approve-claim")
    assert not approved["policy_dispatchable"]
    # One-minute no-receipt failure advances to the explicit component arrival.
    def unavailable(*args):
        raise TimeoutError
    with monkeypatch.context() as context:
        context.setattr(vendor, "review", unavailable)
        desk.act(REVIEWER, CURE, "submit-claim")
    row = desk.case(REVIEWER, CURE)
    assert row["actions"][0]["id"] == "refresh-claim"
    desk.act(REVIEWER, CURE, "refresh-claim")
    approved = desk.act(REVIEWER, CURE, "approve-claim")
    assert approved["policy_dispatchable"]
    submitted = desk.act(REVIEWER, CURE, "submit-claim")
    assert submitted["stage"] == "AWARDED" and submitted["replies"][0]["code"] != "DOCUMENTATION_NEEDED"
    assert len(submitted["submissions"]) == 1


def test_valid_new_account_and_417_30_fee_control(tmp_path, monkeypatch):
    def novel(d):
        d.update(account="novel-account", invoice_id="novel-invoice", start="2026-10-22T01:21:00+00:00",
                 end="2026-10-22T01:47:00+00:00")
        d["invoice_lines"] = [dict(d["invoice_lines"][0], id="novel-line", usd="417.30", evidence_ref="novel-invoice/novel-line")]
        for line in d["invoice_lines"]:
            line.update({key:d[key] for key in ("account", "invoice_id")})
        for group in claimant.GROUPS:
            for doc in d[group]:
                doc.update(ref="novel-"+doc["kind"], **{key:d[key] for key in ("account", "start", "end")})
    desk, d = provision(tmp_path, monkeypatch, mutate=novel)
    records = json.loads((FIXTURES / "simulator/records.json").read_text())
    record = deepcopy(records["sim-acct-101"])
    record.update({key:d[key] for key in ("account", "invoice_id", "start", "end")})
    record["lines"] = deepcopy(d["invoice_lines"])
    record["document_registry"] = {doc["ref"]:Document.minimized("bears", doc).fact.digest
                                    for group in ("initial_documents", "supplemental_archive") for doc in d[group]}
    records[d["account"]] = record
    (tmp_path / "simulator").mkdir()
    (tmp_path / "simulator/records.json").write_text(json.dumps(records))
    monkeypatch.setattr(vendor, "FIXTURES", tmp_path)
    row = complete(desk, CURE)
    assert row["stage"] == "AWARDED" and row["ledger"]["awarded"] == "41.73"
    assert len(row["submissions"]) == 2


@settings(max_examples=100, derandomize=True, deadline=None)
@given(cents=st.integers(min_value=1, max_value=10**10), precision=st.integers(min_value=3, max_value=50))
def test_property_exact_entitlement_and_settlement_boundary(cents, precision):
    d = dossiers()[CURE]
    d["invoice_lines"] = [d["invoice_lines"][0]]
    d["invoice_lines"][0]["usd"] = f"{cents // 100}.{cents % 100:02d}"
    repin(d)
    expected = Decimal(cents) / Decimal(1000)
    with localcontext() as context:
        context.prec = precision
        result = claimant.preflight(d, START)
        assert result.outcome == Outcome.ELIGIBLE and result.amount.amount == expected
        assert claimant.settlement_expressible(str(result.amount.amount)) == (cents % 10 == 0)


@settings(max_examples=60, derandomize=True, deadline=None)
@given(offset=st.integers(min_value=-12, max_value=14), minutes=st.integers(min_value=1, max_value=1000))
def test_property_equivalent_instants_preserve_claimant_threshold(offset, minutes):
    d = dossiers()[CURE]
    start = datetime(2026, 10, 14, 12, tzinfo=UTC)
    end = start + timedelta(minutes=minutes)
    zone = timezone(timedelta(hours=offset))
    for key, at in (("start", start), ("end", end)):
        d[key] = at.astimezone(zone).isoformat()
        d["initial_documents"][0][key] = d[key]
    repin(d)
    result = claimant.preflight(d, START.astimezone(zone))
    assert result.outcome == (Outcome.ELIGIBLE if minutes >= 23 else Outcome.INELIGIBLE)


@settings(max_examples=50, derandomize=True, deadline=None)
@given(padding=st.sampled_from([" ", "\t", "\n", "\u00a0", "\u2003"]), before=st.booleans())
def test_property_provider_line_aliases_never_inflate_entitlement(padding, before):
    d = dossiers()[CURE]
    alias = dict(d["invoice_lines"][0])
    alias["id"] = padding + alias["id"] if before else alias["id"] + padding
    d["invoice_lines"].append(alias)
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.MISSING


@pytest.mark.parametrize("field,value", [("period", "2024-08"), ("service_start", "2024-08-01"),
                                        ("currency_code", "CAD"), ("source_line", "other")])
def test_unknown_invoice_scope_fields_are_not_silently_ignored(field, value):
    d = dossiers()[CURE]
    d["invoice_lines"][0][field] = value
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.MISSING


def test_equivalent_document_and_vendor_instants_do_not_change_scope():
    d = dossiers()[PARTIAL]
    for doc in d["initial_documents"]:
        for key in ("start", "end"):
            doc[key] = datetime.fromisoformat(doc[key]).astimezone(timezone(timedelta(hours=-7))).isoformat()
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.ELIGIBLE
    packet = claimant.ticket_for("bears", d, [], at=START)
    record = json.loads((FIXTURES / "simulator/records.json").read_text())[packet.account]
    record["document_registry"] = {doc.fact.ref:doc.fact.digest for doc in packet.documents}
    assert vendor.decide(packet, record, START).code == "PARTIAL_AWARD"


def test_deleting_required_document_reference_does_not_crash_case_view(tmp_path):
    desk = DisputeDesk(tmp_path / "missing-ref.db"); desk.seed("bears")
    with sqlite3.connect(desk.path) as db:
        d = json.loads(db.execute("SELECT dossier FROM dispute_cases WHERE id=?", (CURE,)).fetchone()[0])
        d["initial_documents"][0].pop("ref")
        db.execute("UPDATE dispute_cases SET dossier=? WHERE id=?", (json.dumps(d), CURE))
    row = desk.case(REVIEWER, CURE)
    assert row["outcome"] == Outcome.MISSING and not row["actions"]


def test_pinned_tax_only_invoice_is_ineligible_without_losing_old_negative_check(tmp_path, monkeypatch):
    desk, d = provision(tmp_path, monkeypatch, mutate=lambda d: d.update(
        invoice_lines=[line for line in d["invoice_lines"] if line["kind"] == "tax"]))
    assert claimant.preflight(d, START).outcome == Outcome.INELIGIBLE
    assert not desk.case(REVIEWER, CURE)["actions"]


def test_low_decimal_context_preserves_complete_financial_workflow(tmp_path):
    desk = DisputeDesk(tmp_path / "low-precision.db"); desk.seed("bears")
    with localcontext() as context:
        context.prec = 3
        row = complete(desk, PARTIAL)
    assert row["ledger"]["claimed"] == "100.00"
    assert row["ledger"]["awarded"] == "80.00" and row["ledger"]["disputed_remainder"] == "20.00"


def test_vendor_exclusion_without_ever_provisioned_notice_still_escalates(tmp_path, monkeypatch):
    desk, d = provision(tmp_path, monkeypatch, "dispute-denial", lambda d: d.update(customer_notice_archive=[]))
    row = complete(desk, "dispute-denial")
    assert row["replies"][0]["code"] == "MAINTENANCE_EXCLUDED"
    assert row["stage"] == "HUMAN_REVIEW" and len(row["submissions"]) == 1


def test_no_supplement_ever_provisioned_stops_without_appeal(tmp_path, monkeypatch):
    desk, d = provision(tmp_path, monkeypatch, mutate=lambda d: d.update(supplemental_archive=[]))
    row = complete(desk, CURE)
    assert row["stage"] == "HUMAN_REVIEW" and len(row["submissions"]) == 1


def test_v4_expectations_were_pinned_before_implementation():
    from hashlib import sha256
    assert sha256((FIXTURES / "oracle/v2.json").read_bytes()).hexdigest() == "7c03ad35241f9756beb00c2c6c244f7429ac4914105aa8549895bae13cad8041"


def test_pinned_unknown_charge_remains_unsupported():
    d = dossiers()[CURE]
    d["invoice_lines"][0]["kind"] = "unknown_fee"
    repin(d)
    assert claimant.preflight(d, START).outcome == Outcome.UNSUPPORTED


def test_provisioned_restricted_document_cannot_leave_claimant(tmp_path, monkeypatch):
    desk, d = provision(tmp_path, monkeypatch, mutate=lambda d: d["initial_documents"][0].update(classification="restricted"))
    assert claimant.preflight(d, START).outcome == Outcome.ELIGIBLE
    row = desk.case(REVIEWER, CURE)
    assert not row["actions"] and not row["policy_dispatchable"]
    with pytest.raises(DisputeConflict):
        desk.act(REVIEWER, CURE, "approve-claim")


def test_receipt_preserves_observation_and_source_to_minimized_payload_link(tmp_path):
    desk = DisputeDesk(tmp_path / "provenance.db"); desk.seed("bears")
    row = complete(desk, CURE)
    receipt = row["submissions"][-1]
    d = dossiers()[CURE]
    component = next(doc for doc in receipt["payload"]["documents"] if doc["fact"]["kind"] == "component_record")
    assert component["fact"]["observed_at"] == d["supplemental_archive"][0]["observed_at"]
    assert component["fact"]["observed_at"] > row["submissions"][0]["at"]
    assert receipt["source_artifact_digests"][component["fact"]["ref"]] == fingerprint(d["supplemental_archive"][0])


def test_multiple_provisioned_manifests_for_one_account_preserve_each_source_root(tmp_path, monkeypatch):
    ds = dossiers()
    revision = deepcopy(ds[PARTIAL])
    for group in claimant.GROUPS:
        for doc in revision[group]:
            doc["ref"] = "revision-" + doc["ref"]
    for line in revision["invoice_lines"]:
        line["id"] = "revision-" + line["id"]
        line["evidence_ref"] = "revision-" + line["evidence_ref"]
    repin(revision)
    ds["revised-case"] = revision
    (tmp_path / "claimant").mkdir()
    (tmp_path / "claimant/dossiers.json").write_text(json.dumps(ds))
    monkeypatch.setattr(disputes, "FIXTURES", tmp_path)
    desk = DisputeDesk(tmp_path / "roots.db"); desk.seed("bears")
    assert desk.act(REVIEWER, PARTIAL, "approve-claim")["stage"] == "CLAIM_APPROVED"
    assert desk.act(REVIEWER, "revised-case", "approve-claim")["stage"] == "CLAIM_APPROVED"
    desk.act(REVIEWER, PARTIAL, "submit-claim")
    with pytest.raises(DisputeConflict, match="already reserved"):
        desk.act(REVIEWER, "revised-case", "submit-claim")


def test_removing_notice_and_its_hash_cannot_hide_an_original_source_fact(tmp_path):
    desk = DisputeDesk(tmp_path / "hide-notice.db"); desk.seed("bears")
    with sqlite3.connect(desk.path) as db:
        d = json.loads(db.execute("SELECT dossier FROM dispute_cases WHERE id='dispute-denial'").fetchone()[0])
        d["customer_notice_archive"] = []
        repin(d)
        db.execute("UPDATE dispute_cases SET dossier=? WHERE id='dispute-denial'", (json.dumps(d),))
    assert not desk.case(REVIEWER, "dispute-denial")["actions"]
    with pytest.raises(DisputeConflict, match="immutable"):
        desk.act(REVIEWER, "dispute-denial", "approve-claim")
