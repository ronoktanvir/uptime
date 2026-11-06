"""Decision72 business-scope falsification. Temporary databases and authored data only.

No fixtures, customer captures, credentials, transport or native delivery are used.
Legacy rows are raw INSERTs of hand-authored pre-Decision72 normalized shapes.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3
from threading import Barrier
from types import SimpleNamespace

import pytest

from test_ramp_credit_sync_v4 import (
    AT, BILL, BUSINESS, CREDIT, DRAFT, ENTITY, SCOPE, VENDOR, binding, link, seed, snapshot, uid,
)
from uptime.ramp import RampError, uuid_text
from uptime.ramp_credit_sync import CreditSyncError, RampCreditSync, _normalize
from uptime.ramp_workspace import credit_observation
from uptime.ramp_workspace import RampWorkspace
from uptime.ramp_records import ORIGIN, RESOURCE_SCOPES, SCHEMA, seal_snapshot

OTHER = uid(0xC73)
LATER = "2026-11-04T13:00:00+00:00"
LATEST = "2026-11-04T14:00:00+00:00"
CUSTODY = "CALLER_ASSERTED_BUSINESS_CONTEXT_NOT_OAUTH_PROOF"


def _text(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unscoped(*args, **kwargs):
    s = snapshot(*args, **kwargs)
    s.pop("provider_business_id")
    return s


def unscoped_binding(s=None):
    b = binding(s)
    b.pop("provider_business_id")
    return b


def legacy_payload(s):
    """Hand-authored pre-Decision72 normalized snapshot: no business key, UTC microsecond instant, sorted scopes."""
    p = deepcopy(s)
    p.pop("provider_business_id", None)
    assert p["observed_at"].endswith("+00:00")
    p["observed_at"] = p["observed_at"].replace("+00:00", ".000000+00:00")
    p["scopes"] = sorted(set(p["scopes"]))
    return p


def raw_snapshot(path, tenant, payload, status, issues=()):
    text = _text(payload)
    digest = sha256(text.encode()).hexdigest()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""INSERT INTO ramp_credit_snapshot(tenant,id,observed_at,payload,digest,status,issues)
            VALUES(?,?,?,?,?,?,?)""", (tenant, payload["id"], payload["observed_at"], text, digest, status,
                                       _text(list(issues))))
    return digest


def raw_binding(path, tenant, old_binding):
    assert "provider_business_id" not in old_binding
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("INSERT INTO ramp_credit_binding VALUES(?,?,?)", (tenant, old_binding["credit_id"], _text(old_binding)))


def legacy_ledger(sync, applied=200):
    """Recreate the ledger rows an old unscoped projection wrote, via the unchanged ledger API."""
    sync.ledger.record_credit("t", dict(SCOPE, id=CREDIT, source="LIVE_RAMP_SANDBOX", source_ref=CREDIT,
        memo_ref="synthetic:memo", award_id="award", amount_cents=1000, effective_date="2026-10-01"))
    sync.ledger.observe_application("t", dict(id="credit-sync:legacy", credit_id=CREDIT, bill_id=BILL,
        source="LIVE_RAMP_SANDBOX", source_ref=f"ramp:{CREDIT}:{BILL}", amount_cents=applied,
        observed_at=AT, effective_date=AT[:10]))


def test_cross_business_same_ids_reject_and_leave_prior_application(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    before = sync.ledger.history("t")
    foreign = dict(snapshot("foreign", applied=500, at=LATER), provider_business_id=OTHER)
    with pytest.raises(CreditSyncError, match="^BUSINESS_CONFLICT$"):
        sync.import_snapshot("t", foreign, as_of=LATER)
    with pytest.raises(CreditSyncError, match="^BUSINESS_CONFLICT$"):
        sync.link_award("t", dict(binding(foreign), credit_id=uid(40), provider_business_id=OTHER), as_of=LATER)
    assert [h["id"] for h in sync.history("t")] == ["snapshot-1"]
    assert sync.ledger.history("t") == before
    state = sync.summary("t", as_of=LATER)
    assert (state["applied_cents"], state["quarantined"], state["provider_business_id"]) == (200, False, BUSINESS)
    # Not a quarantine: the pinned business still advances afterwards.
    own = snapshot("own", applied=500, at=LATER)
    assert sync.import_snapshot("t", own, as_of=LATER) == dict(id="own", status="RECORDED", issues=[], actual_recovery=None, provider_business_id=BUSINESS)
    assert sync.summary("t", as_of=LATER)["applied_cents"] == 500


def test_parallel_first_pin_race_admits_exactly_one_business(tmp_path):
    path = tmp_path / "db"
    sync = RampCreditSync(path)
    candidates = [snapshot("pin-a"), dict(snapshot("pin-b"), provider_business_id=OTHER)]
    workers = [RampCreditSync(path) for _ in candidates]
    barrier = Barrier(len(candidates))

    def run(pair):
        worker, s = pair
        barrier.wait(timeout=10)
        try:
            return worker.import_snapshot("t", s, as_of=AT)["status"]
        except CreditSyncError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        results = list(pool.map(run, zip(workers, candidates)))
    assert sorted(results) == ["BUSINESS_CONFLICT", "RECORDED"]
    winner = candidates[results.index("RECORDED")]
    assert sync.summary("t", as_of=AT)["provider_business_id"] == winner["provider_business_id"]
    assert [(h["id"], h["provider_business_id"]) for h in sync.history("t")] == [
        (winner["id"], winner["provider_business_id"])]
    with closing(sqlite3.connect(path)) as db:
        for statement in ("UPDATE ramp_credit_scope SET provider_business_id='x'", "DELETE FROM ramp_credit_scope"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(statement)


def test_unscoped_advance_after_scoped_link_is_factual_but_never_projects(tmp_path):
    sync = seed(tmp_path / "db")
    link(sync)
    before = sync.ledger.history("t")
    later = unscoped("unscoped-later", applied=500, at=LATER)
    assert sync.import_snapshot("t", later, as_of=LATER) == dict(
        id="unscoped-later", status="RECORDED", issues=["BUSINESS_SCOPE_MISSING"], actual_recovery=None, provider_business_id=None)
    assert sync.ledger.history("t") == before
    state = sync.summary("t", as_of=LATER)
    assert (state["status"], state["issues"], state["applied_cents"]) == ("RECORDED", ["BUSINESS_SCOPE_MISSING"], 200)
    assert state["scope_status"] == "SCOPED" and state["observation_provider_business_id"] is None
    assert state["unmatched_credits"] == 1  # A scoped binding never matches an unscoped observation.
    with pytest.raises(CreditSyncError, match="^BUSINESS_SCOPE_MISSING$"):
        sync.link_award("t", unscoped_binding(later), as_of=LATER)
    # Post-repair unscoped evidence is marked, so it does not freeze later scoped evidence.
    scoped = snapshot("scoped-latest", applied=500, at=LATEST)
    assert sync.import_snapshot("t", scoped, as_of=LATEST)["issues"] == []
    assert sync.summary("t", as_of=LATEST)["applied_cents"] == 500


def test_latest_unscoped_observation_blocks_new_link(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot()
    sync.import_snapshot("t", s, as_of=AT)
    later = unscoped("unscoped-current", at=LATER)
    sync.import_snapshot("t", later, as_of=LATER)
    before = sync.ledger.history("t")
    for b in (binding(later), binding(s)):
        with pytest.raises(CreditSyncError, match="^CURRENT_COMPLETE_OBSERVATION_REQUIRED$"):
            sync.link_award("t", b, as_of=LATER)
    assert sync.ledger.history("t") == before


def test_unscoped_only_tenant_cannot_pin_or_link(tmp_path):
    sync = seed(tmp_path / "db")
    s = unscoped()
    assert sync.import_snapshot("t", s, as_of=AT)["issues"] == ["BUSINESS_SCOPE_MISSING"]
    state = sync.summary("t", as_of=AT)
    assert (state["provider_business_id"], state["scope_status"], state["recorded_cents"]) == (None, "UNSCOPED", None)
    before = sync.ledger.history("t")
    for b in (binding(s), unscoped_binding(s)):
        with pytest.raises(CreditSyncError, match="^BUSINESS_SCOPE_MISSING$"):
            sync.link_award("t", b, as_of=AT)
    assert sync.ledger.history("t") == before


@pytest.mark.parametrize("status,issues,changes", [
    ("RECORDED", [], {}),
    ("PARTIAL", ["INCOMPLETE_LIST"], {"list_complete": False}),
    ("STALE", ["STALE_OR_FUTURE_OBSERVATION"], {"observed_at": "2026-11-01T00:00:00+00:00"}),
])
def test_legacy_nonempty_evidence_without_bindings_freezes_scoped_projection(tmp_path, status, issues, changes):
    path = tmp_path / "db"
    sync = seed(path)
    old = unscoped("legacy-1")
    old.update(changes)
    raw_snapshot(path, "t", legacy_payload(old), status, issues)
    before = sync.ledger.history("t")
    assert sync.summary("t", as_of=AT)["scope_status"] == "LEGACY_UNSCOPED"
    s = snapshot("scoped-after-legacy", at=LATER)
    assert sync.import_snapshot("t", s, as_of=LATER) == dict(
        id=s["id"], status="RECORDED", issues=["LEGACY_UNSCOPED_HISTORY"], actual_recovery=None, provider_business_id=BUSINESS)
    with pytest.raises(CreditSyncError, match="^LEGACY_UNSCOPED_HISTORY$"):
        sync.link_award("t", binding(s), as_of=LATER)
    assert sync.ledger.history("t") == before
    state = sync.summary("t", as_of=LATER)
    assert (state["quarantined"], state["scope_status"], state["provider_business_id"]) == (False, "LEGACY_UNSCOPED", BUSINESS)
    assert state["recorded_cents"] is state["applied_cents"] is state["actual_recovery"] is None


@pytest.mark.parametrize("with_snapshot", [True, False])
def test_legacy_binding_and_ledger_amounts_retained_never_advanced(tmp_path, with_snapshot):
    path = tmp_path / "db"
    sync = seed(path)
    old = unscoped("legacy-linked")
    if with_snapshot:
        raw_snapshot(path, "t", legacy_payload(old), "RECORDED")
    legacy_ledger(sync)
    raw_binding(path, "t", unscoped_binding(old))
    before = sync.ledger.history("t")
    state = sync.summary("t", as_of=AT)
    assert (state["recorded_cents"], state["applied_cents"], state["linked_credits"]) == (1000, 200, 1)
    assert state["scope_status"] == "LEGACY_UNSCOPED"
    later = snapshot("scoped-advance", applied=500, at=LATER)
    assert sync.import_snapshot("t", later, as_of=LATER)["issues"] == ["LEGACY_UNSCOPED_HISTORY"]
    assert sync.ledger.history("t") == before
    state = sync.summary("t", as_of=LATER)
    assert (state["recorded_cents"], state["applied_cents"], state["quarantined"]) == (1000, 200, False)
    assert state["actual_recovery"] is None and state["amounts_are_historical"] is True
    # A prior unscoped binding retry never reports LINKED; a scoped retry is not the same binding.
    with pytest.raises(CreditSyncError, match="^BUSINESS_SCOPE_MISSING$"):
        sync.link_award("t", unscoped_binding(old), as_of=LATER)
    with pytest.raises(CreditSyncError, match="^BINDING_CONFLICT$"):
        sync.link_award("t", binding(old), as_of=LATER)
    assert sync.ledger.history("t") == before


def test_empty_legacy_observations_do_not_block_scoped_link(tmp_path):
    path = tmp_path / "db"
    sync = seed(path)
    empty = unscoped("legacy-empty", at="2026-11-04T11:00:00+00:00")
    empty.update(credits=[], bills=[])
    raw_snapshot(path, "t", legacy_payload(empty), "EMPTY")
    partial = unscoped("legacy-partial-empty", at="2026-11-04T11:30:00+00:00")
    partial.update(credits=[], bills=[], list_complete=False)
    raw_snapshot(path, "t", legacy_payload(partial), "PARTIAL", ["INCOMPLETE_LIST"])
    unavailable = unscoped("legacy-unavailable", at="2026-11-04T11:45:00+00:00")
    unavailable.update(available=False)
    raw_snapshot(path, "t", legacy_payload(unavailable), "UNAVAILABLE", ["UNAVAILABLE"])
    assert sync.summary("t", as_of=AT)["scope_status"] == "UNSCOPED"
    assert link(sync) == dict(credit_id=CREDIT, status="LINKED", actual_recovery=None, provider_business_id=BUSINESS)
    state = sync.summary("t", as_of=AT)
    assert (state["applied_cents"], state["scope_status"]) == (200, "SCOPED")


def test_legacy_duplicate_digest_and_unknown_scope_preserved(tmp_path):
    path = tmp_path / "db"
    sync = RampCreditSync(path)
    old = unscoped("legacy-dup")
    digest = raw_snapshot(path, "t", legacy_payload(old), "RECORDED")
    receipt = dict(id="legacy-dup", status="RECORDED", issues=[], actual_recovery=None, provider_business_id=None)
    assert sync.import_snapshot("t", old, as_of=AT) == receipt
    assert sync.import_snapshot("t", dict(old, provider_business_id=None), as_of=AT) == receipt
    assert [(h["digest"], h["provider_business_id"]) for h in sync.history("t")] == [(digest, None)]
    with pytest.raises(CreditSyncError, match="^OBSERVATION_ID_CONFLICT$"):
        sync.import_snapshot("t", snapshot("legacy-dup"), as_of=AT)
    assert sync.summary("t", as_of=AT)["provider_business_id"] is None
    # Current normalization of an unscoped read reproduces the authored legacy digest.
    sync.import_snapshot("fresh", old, as_of=AT)
    assert sync.history("fresh")[0]["digest"] == digest


@pytest.mark.parametrize("value", [
    0, 1.5, True, b"00000000-0000-0000-0000-000000000b72", ["x"], {"id": BUSINESS}, "", "not-a-uuid",
    uid(0), "00000000000000000000000000000000", BUSINESS + "0", " " + BUSINESS,
])
def test_invalid_business_types_and_zero_uuid_rejected_before_storage(tmp_path, value):
    sync = seed(tmp_path / "db")
    with pytest.raises(CreditSyncError, match="^INVALID_BUSINESS$"):
        sync.import_snapshot("t", dict(snapshot(), provider_business_id=value), as_of=AT)
    assert sync.history("t") == []
    assert sync.summary("t", as_of=AT)["provider_business_id"] is None
    sync.import_snapshot("t", snapshot(), as_of=AT)
    with pytest.raises(CreditSyncError, match="^INVALID_BUSINESS$"):
        sync.link_award("t", dict(binding(), provider_business_id=value), as_of=AT)
    assert sync.ledger.reconcile("t", "award")["posted_cents"] == 0


def test_business_uuid_is_normalized_and_null_is_unknown(tmp_path):
    sync = seed(tmp_path / "db")
    assert BUSINESS.upper() != BUSINESS
    first = sync.import_snapshot("t", dict(snapshot(), provider_business_id=BUSINESS.upper()), as_of=AT)
    assert first == sync.import_snapshot("t", snapshot(), as_of=AT)  # Same normalized digest.
    assert [h["provider_business_id"] for h in sync.history("t")] == [BUSINESS]
    linked = sync.link_award("t", dict(binding(), provider_business_id="{" + BUSINESS + "}"), as_of=AT)
    assert linked["provider_business_id"] == BUSINESS
    assert sync.link_award("t", binding(), as_of=AT) == linked
    assert _normalize(dict(unscoped(), provider_business_id=None)) == _normalize(unscoped())
    assert "provider_business_id" not in _normalize(unscoped())


def test_missing_or_wrong_binding_scope_cannot_link(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot()
    sync.import_snapshot("t", s, as_of=AT)
    before = sync.ledger.history("t")
    for b, code in ((unscoped_binding(s), "BUSINESS_SCOPE_MISSING"),
                    (dict(binding(s), provider_business_id=None), "BUSINESS_SCOPE_MISSING"),
                    (dict(binding(s), provider_business_id=OTHER), "BUSINESS_CONFLICT")):
        with pytest.raises(CreditSyncError, match=f"^{code}$"):
            sync.link_award("t", b, as_of=AT)
    assert sync.ledger.history("t") == before
    assert sync.summary("t", as_of=AT)["linked_credits"] == 0
    receipt = dict(credit_id=CREDIT, status="LINKED", actual_recovery=None, provider_business_id=BUSINESS)
    assert sync.link_award("t", binding(s), as_of=AT) == receipt
    assert sync.link_award("t", binding(s), as_of=AT) == receipt  # Scoped retry stays idempotent.
    with pytest.raises(CreditSyncError, match="^BUSINESS_SCOPE_MISSING$"):
        sync.link_award("t", unscoped_binding(s), as_of=AT)


def test_projection_defensively_requires_exact_explicit_business(tmp_path):
    sync = RampCreditSync(tmp_path / "db")
    with pytest.raises(CreditSyncError, match="^BUSINESS_CONFLICT$"):
        sync._project(None, "t", dict(binding(), provider_business_id=OTHER), _normalize(snapshot()), {}, {})
    with pytest.raises(CreditSyncError, match="^BUSINESS_SCOPE_MISSING$"):
        sync._project(None, "t", binding(), _normalize(unscoped()), {}, {})
    with pytest.raises(CreditSyncError, match="^BUSINESS_SCOPE_MISSING$"):
        sync._project(None, "t", unscoped_binding(), _normalize(snapshot()), {}, {})


def test_receipt_history_summary_source_custody(tmp_path):
    path = tmp_path / "db"
    sync = seed(path)
    empty = sync.summary("t", as_of=AT)
    assert (empty["provider_business_id"], empty["scope_status"], empty["business_scope_custody"]) == (None, "UNSCOPED", CUSTODY)
    assert empty["recorded_cents"] is empty["applied_cents"] is None
    assert link(sync) == dict(credit_id=CREDIT, status="LINKED", actual_recovery=None, provider_business_id=BUSINESS)
    sync.import_snapshot("t", unscoped("u", at=LATER), as_of=LATER)
    history = sync.history("t")
    assert [(h["id"], h["provider_business_id"]) for h in history] == [("snapshot-1", BUSINESS), ("u", None)]
    assert all(h["business_scope_custody"] == CUSTODY and h["actual_recovery"] is None for h in history)
    state = sync.summary("t", as_of=LATER)
    assert (state["provider_business_id"], state["scope_status"], state["business_scope_custody"]) == (BUSINESS, "SCOPED", CUSTODY)
    assert state["observation_provider_business_id"] is None
    assert state["actual_recovery"] is None and state["external_writes"] is False
    with closing(sqlite3.connect(path)) as db:
        snap = db.execute("SELECT payload FROM ramp_credit_snapshot WHERE id='snapshot-1'").fetchone()[0]
        bound = db.execute("SELECT payload FROM ramp_credit_binding").fetchone()[0]
    assert json.loads(snap)["provider_business_id"] == json.loads(bound)["provider_business_id"] == BUSINESS


def test_linked_zero_application_remains_zero(tmp_path):
    sync = seed(tmp_path / "db")
    s = snapshot("zero", applied=0)
    assert link(sync, s)["status"] == "LINKED"
    state = sync.summary("t", as_of=AT)
    assert state["recorded_cents"] == 1000
    assert state["applied_cents"] == 0 and state["applied_cents"] is not None
    assert state["actual_recovery"] is None


def _native_money(amount):
    return dict(amount_minor=amount, currency="USD", minor_unit_conversion_rate=100)


def _authored_capture():
    """Pure authored canonical workspace capture; not a fixture or provider record."""
    return {"checksum": "a" * 64, "observed_at": AT, "resources": {
        "credits": {"status": "COMPLETE", "complete": True, "grant": {"granted": ["vendors:read"]}, "records": [dict(
            id=CREDIT, vendor_id=VENDOR, entity_id=ENTITY, reference_bill_id=None, accounting_date="2026-10-01",
            archived_at=None, total=_native_money(1000), remaining=_native_money(700),
            total_applied=_native_money(300), applied_bills=[dict(bill_id=BILL, amount=_native_money(200))],
            applied_drafts=[dict(bill_id=DRAFT, amount=_native_money(100))])]},
        "bills": {"status": "COMPLETE", "complete": True, "grant": {"granted": ["bills:read"]}, "records": [dict(
            id=BILL, kind="bill", vendor_id=VENDOR, entity_id=ENTITY, issued_at="2026-11-01", archived_at=None,
            status="OPEN", amount=_native_money(2000),
            applied_credits=[dict(credit_id=CREDIT, amount=_native_money(200))])]}}}


def test_workspace_adapter_passes_known_business_and_omits_unknown(tmp_path):
    capture = _authored_capture()
    unknown = credit_observation(capture)
    assert "provider_business_id" not in unknown
    assert credit_observation(capture, None) == unknown
    known = credit_observation(capture, BUSINESS)
    assert known == dict(unknown, provider_business_id=BUSINESS)
    assert uuid_text(BUSINESS) is BUSINESS
    for bad in (BUSINESS.upper(), "{" + BUSINESS + "}", BUSINESS.replace("-", ""), None, 72):
        with pytest.raises(RampError):
            uuid_text(bad)
    sync = RampCreditSync(tmp_path / "db")
    assert sync.import_snapshot("t", known, as_of=AT) == dict(id="a" * 64, status="RECORDED", issues=[], actual_recovery=None, provider_business_id=BUSINESS)
    assert sync.summary("t", as_of=AT)["provider_business_id"] == BUSINESS
    assert sync.import_snapshot("u", unknown, as_of=AT)["issues"] == ["BUSINESS_SCOPE_MISSING"]


def _empty_workspace_capture():
    """A complete empty capture built in the test; no provider or packaged file."""
    resources = {name: dict(status="EMPTY", records=[], complete=True, issues=[],
        grant=dict(granted=[scope], requested=[scope], scope_reported=True, state="GRANTED"),
        coverage={"LINKED": {"list_complete": True}}) for name, scope in RESOURCE_SCOPES.items()}
    return seal_snapshot(dict(schema=SCHEMA, origin=ORIGIN, observed_at=AT,
                              completed_at=AT, resources=resources))


def test_workspace_import_persists_business_through_credit_projection(tmp_path):
    path = tmp_path / "workspace.db"
    workspace = RampWorkspace(SimpleNamespace(path=path, tenant="authored", mode="sandbox"))
    capture = _empty_workspace_capture()
    result = workspace.import_observation(capture, BUSINESS)
    assert result["status"] == "ready"
    history = workspace.credits.history("authored")
    assert len(history) == 1 and history[0]["provider_business_id"] == BUSINESS
    assert workspace.credits.summary("authored")["provider_business_id"] == BUSINESS
    assert workspace.import_observation(capture, BUSINESS)["duplicate"] is True
    assert len(workspace.credits.history("authored")) == 1
    assert workspace.credits.summary("authored")["actual_recovery"] is None


def test_workspace_zero_business_rejects_before_partial_installation(tmp_path):
    path = tmp_path / "workspace.db"
    workspace = RampWorkspace(SimpleNamespace(path=path, tenant="authored", mode="sandbox"))
    with pytest.raises(ValueError, match="Nonzero Ramp business required"):
        workspace.import_observation(_empty_workspace_capture(), uid(0))
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT COUNT(*) FROM native_installation").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM native_capture").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM ramp_credit_scope").fetchone()[0] == 0
    assert workspace.credits.history("authored") == []
