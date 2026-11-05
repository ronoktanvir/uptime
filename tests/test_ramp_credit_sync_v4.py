"""Synthetic offline observations; no customer records, transport or credentials."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sqlite3
from threading import Barrier
from uuid import UUID

import pytest

from uptime.allocations import AllocationLedger
from uptime.ramp_credit_sync import RampCreditSync, main


def uid(n):
    return str(UUID(int=n))


CREDIT, BILL, VENDOR, ENTITY, DRAFT = map(uid, range(1, 6))
AT = "2026-11-04T12:00:00+00:00"
SCOPE = dict(vendor_id=VENDOR, account_id="synthetic-account", product_id="synthetic-product",
             contract_id="synthetic-contract", contract_version="v1", currency="USD")


def money(amount, currency="USD", rate=100):
    return dict(amount=amount, currency_code=currency, minor_unit_conversion_rate=rate)


def snapshot(ident="snapshot-1", applied=200, draft=100, at=AT):
    return dict(id=ident, observed_at=at, source="LIVE_RAMP_SANDBOX", provenance_ref="synthetic:receipt:"+ident,
        scopes=["vendors:read", "bills:read"], available=True, list_complete=True,
        credits=[dict(id=CREDIT, vendor_id=VENDOR, entity_id=ENTITY, reference_bill_id=None,
            accounting_date="2026-10-01", archived_at=None, total_amount=money(1000),
            remaining_amount=money(1000-applied-draft), total_applied_amount=money(applied+draft),
            applied_bills=[dict(bill_id=BILL, amount=money(applied))] if applied else [],
            applied_draft_bills=[dict(bill_id=DRAFT, amount=money(draft))] if draft else [])],
        bills=[dict(id=BILL, vendor={"id": VENDOR}, entity_id=ENTITY, issued_at="2026-11-01",
            archived_at=None, status="OPEN", amount=money(2000),
            applied_vendor_credits=[dict(id=CREDIT, amount=money(applied))] if applied else [])])


def seed(path, *, eligible=1500, award=True, bill=True):
    sync = RampCreditSync(path)
    if award:
        sync.ledger.record_award("t", "synthetic-case", dict(SCOPE, id="award", source="SIMULATED_VENDOR",
            source_ref="synthetic:award", amount_cents=1000, memo_ref="synthetic:memo", confirmed=True,
            effective_date="2026-09-01"))
    if bill:
        sync.ledger.record_bill("t", dict(SCOPE, id=BILL, source_ref=BILL, source="LIVE_RAMP_SANDBOX",
            amount_cents=2000, eligible_cents=eligible, effective_date="2026-11-01"))
    return sync


def binding(s=None):
    s = s or snapshot()
    return dict(SCOPE, credit_id=CREDIT, award_id="award", bill_id=BILL,
        observation_id=s["id"], provider_provenance_ref=s["provenance_ref"],
        provenance_ref="synthetic:independent-scope-confirmation", award_source="SIMULATED_VENDOR",
        award_source_ref="synthetic:award", memo_ref="synthetic:memo")


def link(sync, s=None):
    s = s or snapshot()
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == "RECORDED"
    return sync.link_award("t", binding(s), as_of=AT)


def test_official_fields_unmatched_and_draft_are_not_attributed(tmp_path):
    sync = seed(tmp_path / "db")
    sync.import_snapshot("t", snapshot(), as_of=AT)
    state = sync.summary("t", as_of=AT)
    assert state["captured_credits"] == state["unmatched_credits"] == 1
    assert state["recorded_cents"] == state["applied_cents"] == 0
    assert state["awards_without_native_credit"] == 1
    assert state["actual_recovery"] is state["claimed_only"] is None
    assert state["observed_totals"] == [dict(currency="USD", minor_unit_conversion_rate=100,
        recorded_minor=1000, provider_applied_minor=300, applied_bills_minor=200,
        applied_drafts_minor=100, remaining_minor=700, archived_credits=0)]


def test_explicit_link_records_only_reciprocal_bill_amount_and_preserves_simulation(tmp_path):
    path = tmp_path / "db"
    sync = seed(path)
    before = sync.ledger.list_bills("t")
    link(sync)
    state = RampCreditSync(path).summary("t", as_of=AT)
    assert (state["recorded_cents"], state["applied_cents"], state["unmatched_credits"]) == (1000, 200, 0)
    assert state["actual_recovery"] is None
    award = sync.ledger.reconcile("t", "award")
    assert set(award["sources"]) == {"SIMULATED_VENDOR", "LIVE_RAMP_SANDBOX"}
    assert award["actual_recovery"] is None
    assert sync.ledger.list_bills("t")[0]["eligible_cents"] == before[0]["eligible_cents"]
    assert len(sync.ledger.list_bills("t")) == 1


def test_cumulative_deltas_repeated_and_parallel_delivery(tmp_path):
    path = tmp_path / "db"
    sync = seed(path)
    link(sync)
    workers = [RampCreditSync(path) for _ in range(6)]
    barrier = Barrier(6)
    later = snapshot("later", applied=500, at="2026-11-04T13:00:00+00:00")

    def run(worker):
        barrier.wait(timeout=10)
        return worker.import_snapshot("t", later, as_of=later["observed_at"])

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert all(r["status"] == "RECORDED" for r in pool.map(run, workers))
    assert sync.summary("t", as_of=later["observed_at"])["applied_cents"] == 500
    assert len(sync.history("t")) == 2
    assert len([r for r in sync.ledger.history("t") if r["kind"] == "application"]) == 2
    another = deepcopy(later)
    another.update(id="another-delivery", provenance_ref="synthetic:another")
    assert sync.import_snapshot("t", another, as_of=later["observed_at"])["status"] == "RECORDED"
    assert sync.summary("t")["applied_cents"] == 500


def test_parallel_link_is_idempotent(tmp_path):
    path = tmp_path / "db"
    sync = seed(path)
    sync.import_snapshot("t", snapshot(), as_of=AT)
    workers = [RampCreditSync(path) for _ in range(4)]
    barrier = Barrier(4)

    def run(worker):
        barrier.wait(timeout=10)
        return worker.link_award("t", binding(), as_of=AT)

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert all(r["status"] == "LINKED" for r in pool.map(run, workers))
    assert sync.summary("t")["applied_cents"] == 200


@pytest.mark.parametrize("field", ["account_id", "product_id", "contract_id", "contract_version", "memo_ref",
                                   "award_source", "award_source_ref", "provider_provenance_ref"])
def test_exact_binding_fields_required(tmp_path, field):
    sync = seed(tmp_path / "db")
    sync.import_snapshot("t", snapshot(), as_of=AT)
    b = binding()
    b[field] = "wrong"
    with pytest.raises(ValueError):
        sync.link_award("t", b, as_of=AT)
    assert sync.ledger.reconcile("t", "award")["posted_cents"] == 0


@pytest.mark.parametrize("parent", ["award", "bill"])
def test_no_synthetic_award_or_bill_created_from_provider_observation(tmp_path, parent):
    sync = seed(tmp_path / "db", **{parent: False})
    sync.import_snapshot("t", snapshot(), as_of=AT)
    before = sync.ledger.history("t")
    with pytest.raises(ValueError):
        sync.link_award("t", binding(), as_of=AT)
    assert sync.ledger.history("t") == before


@pytest.mark.parametrize("change,code", [
    (lambda s: s["credits"][0]["total_applied_amount"].update(amount=301), "CREDIT_TOTAL_CONFLICT"),
    (lambda s: s["bills"][0]["applied_vendor_credits"][0]["amount"].update(amount=201), "RECIPROCAL_CONFLICT"),
    (lambda s: s["credits"][0]["applied_bills"][0]["amount"].update(currency_code="EUR"), "CROSS_CURRENCY"),
    (lambda s: s["bills"][0]["amount"].update(currency_code="EUR"), "CROSS_CURRENCY"),
    (lambda s: s["bills"][0]["vendor"].update(id=uid(99)), "VENDOR_CONFLICT"),
    (lambda s: s["bills"][0].update(entity_id=uid(99)), "ENTITY_CONFLICT"),
    (lambda s: s["bills"][0]["amount"].update(amount=100), "BILL_OVERCAPACITY"),
    (lambda s: s["credits"][0]["total_amount"].update(amount=True), "INVALID_MONEY"),
    (lambda s: s["credits"][0]["total_amount"].update(amount=1000.0), "INVALID_MONEY"),
    (lambda s: s["credits"][0]["total_amount"].update(minor_unit_conversion_rate=1), "INVALID_MONEY"),
])
def test_conflicts_durably_quarantined_without_ledger_mutation(tmp_path, change, code):
    path = tmp_path / "db"
    sync = seed(path)
    s = snapshot()
    change(s)
    before = sync.ledger.history("t")
    assert sync.import_snapshot("t", s, as_of=AT) == dict(id=s["id"], status="CONFLICT", issues=[code], actual_recovery=None)
    assert RampCreditSync(path).history("t")[0]["issues"] == [code]
    assert sync.ledger.history("t") == before


def test_decrease_after_link_preserves_previous_history_but_never_current_confirmation(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    later = snapshot("decrease", applied=199, at="2026-11-04T13:00:00+00:00")
    assert sync.import_snapshot("t", later, as_of=later["observed_at"])["issues"] == ["DECREASING_APPLICATION"]
    state = sync.summary("t", as_of=later["observed_at"])
    assert state["status"] == "CONFLICT"
    assert state["applied_cents"] == 200
    assert state["amounts_are_historical"] and state["actual_recovery"] is None
    assert state["observed_totals"] == []


def test_removed_applied_bill_is_a_decrease_even_if_total_is_unchanged(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    s = snapshot("moved-to-draft", applied=0, draft=300, at="2026-11-04T13:00:00+00:00")
    assert sync.import_snapshot("t", s, as_of=s["observed_at"])["issues"] == ["DECREASING_APPLICATION"]


def test_archive_and_unknown_bill_state_cannot_link(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot()
    s["credits"][0]["archived_at"] = AT
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == "RECORDED"
    assert sync.summary("t", as_of=AT)["observed_totals"][0]["archived_credits"] == 1
    with pytest.raises(ValueError, match="ARCHIVED_CREDIT"):
        sync.link_award("t", binding(s), as_of=AT)


def test_archived_after_link_quarantines_new_confirmation(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    s = snapshot("archive", at="2026-11-04T13:00:00+00:00")
    s["credits"][0]["archived_at"] = s["observed_at"]
    assert sync.import_snapshot("t", s, as_of=s["observed_at"])["issues"] == ["ARCHIVED_CREDIT"]
    assert sync.summary("t")["applied_cents"] == 200


@pytest.mark.parametrize("mutate", [
    lambda s: s["credits"][0].pop("total_amount"),
    lambda s: s["credits"][0].update(applied_bills=None),
    lambda s: s["credits"][0]["total_amount"].update(minor_unit_conversion_rate=None),
    lambda s: s.pop("scopes"),
    lambda s: s.update(scopes=[]),
    lambda s: s.update(credits=None),
])
def test_sparse_inputs_are_unknown_not_zero(tmp_path, mutate):
    sync = seed(tmp_path / "db")
    s = snapshot()
    mutate(s)
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == "INSUFFICIENT_EVIDENCE"
    state = sync.summary("t", as_of=AT)
    assert state["observed_totals"] == []
    assert state["claims_balance"] is None
    with pytest.raises(ValueError):
        sync.link_award("t", binding(s), as_of=AT)


def test_scope_string_and_empty_list_are_genuine_zero_records_not_zero_claims(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot()
    s.update(credits=[], bills=[], scopes="vendors:read bills:read")
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == "EMPTY"
    state = sync.summary("t", as_of=AT)
    assert state["captured_credits"] == 0
    assert state["awards_without_native_credit"] == 1
    assert state["claims_balance"] is state["claimed_only"] is state["actual_recovery"] is None


@pytest.mark.parametrize("changes,status", [
    ({"available": False}, "UNAVAILABLE"), ({"list_complete": False}, "PARTIAL"),
    ({"observed_at": "2026-11-01T00:00:00+00:00"}, "STALE"),
    ({"observed_at": "2026-11-05T00:00:00+00:00"}, "STALE"),
])
def test_unavailable_partial_stale_future_no_confirmation(tmp_path, changes, status):
    sync = seed(tmp_path / "db")
    s = snapshot()
    s.update(changes)
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == status
    with pytest.raises(ValueError):
        sync.link_award("t", binding(s), as_of=AT)
    assert sync.summary("t")["recorded_cents"] == 0


def test_late_compatible_readback_does_not_add_again(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    old = snapshot("older", applied=100, at="2026-11-04T11:00:00+00:00")
    assert sync.import_snapshot("t", old, as_of=AT)["status"] == "RECORDED"
    assert sync.summary("t", as_of=AT)["applied_cents"] == 200


def test_duplicate_ids_conflicting_payload_and_tenant_isolation(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    with pytest.raises(ValueError, match="OBSERVATION_ID_CONFLICT"):
        sync.import_snapshot("t", snapshot(applied=201), as_of=AT)
    assert sync.summary("other", as_of=AT)["captured_credits"] is None
    assert sync.summary("other", as_of=AT)["recorded_cents"] == 0
    sync.import_snapshot("other", snapshot(), as_of=AT)
    with pytest.raises(ValueError, match="INDEPENDENT_AWARD_REQUIRED"):
        sync.link_award("other", binding(), as_of=AT)


def test_capacity_failure_rolls_back_credit_post_and_binding(tmp_path):
    sync = seed(tmp_path / "db", eligible=100)
    sync.import_snapshot("t", snapshot(), as_of=AT)
    before = sync.ledger.history("t")
    with pytest.raises(ValueError, match="BILL_ELIGIBLE_OVERCAPACITY"):
        sync.link_award("t", binding(), as_of=AT)
    assert sync.ledger.history("t") == before
    assert sync.summary("t", as_of=AT)["linked_credits"] == 0


def test_unmatched_provider_applications_also_consume_capacity(tmp_path):
    sync = seed(tmp_path / "db", eligible=300)
    s = snapshot()
    s["bills"][0]["applied_vendor_credits"].append(dict(id=uid(30), amount=money(200)))
    sync.import_snapshot("t", s, as_of=AT)
    with pytest.raises(ValueError, match="BILL_ELIGIBLE_OVERCAPACITY"):
        sync.link_award("t", binding(s), as_of=AT)


def test_replay_cannot_be_relabelled_as_native(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot()
    s["source"] = "DETERMINISTIC_REPLAY"
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == "RECORDED"
    with pytest.raises(ValueError, match="REPLAY_CANNOT_CONFIRM_NATIVE_LINK"):
        sync.link_award("t", binding(s), as_of=AT)
    live = snapshot("relabeled")
    assert sync.import_snapshot("t", live, as_of=AT)["issues"] == ["PROVENANCE_CONFLICT"]


def test_non_usd_observed_without_currency_conversion_or_allocation(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot()

    def convert(obj):
        if isinstance(obj, dict):
            if "currency_code" in obj:
                obj["currency_code"] = "EUR"
            for value in obj.values():
                convert(value)
        if isinstance(obj, list):
            for value in obj:
                convert(value)

    convert(s)
    assert sync.import_snapshot("t", s, as_of=AT)["status"] == "RECORDED"
    assert sync.summary("t", as_of=AT)["observed_totals"][0]["currency"] == "EUR"
    with pytest.raises(ValueError, match="CROSS_CURRENCY"):
        sync.link_award("t", binding(s), as_of=AT)


def test_durable_minimized_history_and_offline_cli(tmp_path, capsys, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: pytest.fail("network forbidden"))
    path, data = tmp_path / "db", tmp_path / "input.json"
    s = snapshot()
    s["credits"][0]["reference_number"] = "private memo excluded"
    s["bills"][0]["vendor"]["name"] = "private vendor excluded"
    data.write_text(json.dumps(s))
    assert main(["--db", str(path), "--tenant", "t", "--as-of", AT, "import", str(data)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "RECORDED"
    assert main(["--db", str(path), "--tenant", "t", "--as-of", AT, "summary"]) == 0
    assert json.loads(capsys.readouterr().out)["external_writes"] is False
    with sqlite3.connect(path) as db:
        payload = db.execute("SELECT payload FROM ramp_credit_snapshot").fetchone()[0]
        assert "private" not in payload
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("DELETE FROM ramp_credit_snapshot")
