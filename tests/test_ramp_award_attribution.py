"""All records, identities, witnesses and signatures here are generated fixtures.

Tests of the ACTUAL_NATIVE branch prove gate behavior, not a real Ramp capture or
an affiliated vendor award. No test reads credentials or opens a network client.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import sqlite3
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from uptime.claim_identity import TABLE, reserve_claim
from uptime.ramp_award_attribution import (
    AttributionError, AwardAttributionStore, DOMAIN, OfficeConfig,
    canonical_json, digest, load_office_config, signing_bytes,
)


NOW = "2026-11-04T12:00:00+00:00"


def later(minutes):
    return (datetime.fromisoformat(NOW) + timedelta(minutes=minutes)).isoformat()


def uid(number):
    return str(UUID(int=number))


VENDOR, BUSINESS, CREDIT, BILL, ENTITY = map(uid, (1, 2, 3, 4, 5))


def evidence(name):
    return dict(reference="fixture:" + name, sha256=sha256(name.encode()).hexdigest(),
                method="TEST_FIXTURE_ONLY_" + name)


def money(value, currency="USD", rate=100):
    return dict(amount=value, currency_code=currency, minor_unit_conversion_rate=rate)


def scope(**changes):
    return dict(vendor_id=VENDOR, vendor_name="Fixture Vendor", account_id="account-1",
                beneficiary_id="beneficiary-1", contract_id="agreement-1", contract_version="v1",
                product_id="product-1", service_name="Fixture Service", month="2026-10",
                remedy="sla", currency="USD", minor_unit_conversion_rate=100, **changes)


class Harness:
    def __init__(self, path, *, mode="MOCK", extra_scopes=(), authority_sources=(), tenant="fixture-tenant"):
        self.path = path
        self.keys = {r: Ed25519PrivateKey.generate() for r in
                     ("claim_registrar", "vendor_verifier", "finance_approver", "ramp_observer")}
        self.config = dict(version="uptime-ramp-award-office/1", installation_id="fixture-install",
            tenant=tenant, business_id=BUSINESS, environment="sandbox", evidence_mode=mode,
            review=evidence("office-review"), authority_sources=list(authority_sources), witnesses=[
                dict(subject=role, public_key=key.public_key().public_bytes_raw().hex(), role=role,
                     operator_id="fixture-person-" + role, operator_key_sha256=digest(role),
                     association=evidence("association-" + role), source_verification=evidence("source-" + role),
                     valid_from=later(-60), valid_until=later(1440),
                     scopes=[] if role == "ramp_observer" else [scope(), *extra_scopes])
                for role, key in self.keys.items()])
        self.store = AwardAttributionStore(path, self.config)
        self.claim_hashes = {}
        self.claim_scopes = {}

    def signed(self, kind, name, body, roles, *, when=NOW, config=None):
        cfg = config or self.config
        statement = {k: cfg[k] for k in ("installation_id", "tenant", "business_id", "environment", "evidence_mode")}
        statement.update(version=DOMAIN, kind=kind, id=name, issued_at=when,
            expires_at=(datetime.fromisoformat(when) + timedelta(hours=2)).isoformat(), body=deepcopy(body))
        return dict(statement=statement, endorsements=[dict(subject=role,
            signature=self.keys[role].sign(signing_bytes(cfg, statement, role)).hex()) for role in roles])

    def file(self, claim="claim-1", *, sc=None, bill_ids=(BILL,), eligible=1000, when=NOW):
        sc = sc or scope()
        local = dict(account=sc["account_id"], vendor=sc["vendor_name"], contract="local-contract",
                     service=sc["service_name"], currency=sc["currency"], month=sc["month"])
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            reserve_claim(db, tenant=self.config["tenant"], vendor=sc["vendor_name"], account=sc["account_id"],
                agreement_id=sc["contract_id"], agreement_version=sc["contract_version"], service=sc["service_name"],
                month=sc["month"], remedy=sc["remedy"], route="fixture-route", case_id=claim, packet_digest=digest(claim),
                scope=local, receipt_id="receipt:" + claim, at=later(-10))
        body = dict(claim_id=claim, dispatch_sha256=self.store.filing_identity(claim), local_contract_id="local-contract",
                    claimant_operator_id="fixture-claimant", scope=sc, scope_verification=evidence("contract-beneficiary"),
                    bills=[dict(bill_id=b, eligible_minor=eligible, evidence=evidence("bill-scope-" + b)) for b in bill_ids])
        env = self.signed("filed_claim", "register-" + claim, body, ["claim_registrar"], when=when)
        receipt = self.store.register_claim(env, at=when)
        self.claim_hashes[claim], self.claim_scopes[claim] = receipt["claim_sha256"], sc
        return env

    def award(self, name="award-1", amount=100, claim="claim-1", *, when=NOW):
        body = dict(claim_id=claim, claim_sha256=self.claim_hashes[claim], scope=self.claim_scopes[claim],
                    vendor_award_ref="vendor:" + name, amount_minor=amount,
                    confirmation=dict(**evidence("independent-vendor-" + name), channel="VENDOR_SIGNED_DOCUMENT",
                        authority_verification=evidence("vendor-signer-authority"),
                        independence_verification=evidence("source-independent-of-claimant-and-ramp")))
        env = self.signed("vendor_award", name, body, ["vendor_verifier", "finance_approver"], when=when)
        self.store.import_award(env, at=when)
        return env

    def snapshot(self, *, name="capture-1", total=100, applied=50, when=NOW, credit=CREDIT, bill=BILL):
        body = dict(id=name, observed_at=when,
                    source="LIVE_RAMP_SANDBOX" if self.config["evidence_mode"] == "ACTUAL_NATIVE" else "DETERMINISTIC_REPLAY",
                    provenance_ref="fixture:" + name, capture=evidence("native-readback-" + name),
                    scopes=["vendors:read", "bills:read"], available=True, list_complete=True,
                    credits=[dict(id=credit, vendor_id=VENDOR, entity_id=ENTITY, reference_bill_id=bill,
                        accounting_date="2026-11-04", archived_at=None, total_amount=money(total),
                        remaining_amount=money(total-applied), total_applied_amount=money(applied),
                        applied_bills=[dict(bill_id=bill, amount=money(applied))] if applied else [], applied_draft_bills=[])],
                    bills=[dict(id=bill, vendor=dict(id=VENDOR), entity_id=ENTITY, status="OPEN", archived_at=None,
                        amount=money(1000), applied_vendor_credits=[dict(id=credit, amount=money(applied))] if applied else [])])
        return body

    def observe(self, body=None, *, when=None):
        body = body or self.snapshot()
        when = when or body["observed_at"]
        env = self.signed("native_snapshot", body["id"], body, ["ramp_observer"], when=when)
        return self.store.observe(env, at=when), env

    def binding(self, snap, *, name="binding-1", award="award-1", claim="claim-1", credit=CREDIT,
                bill=BILL, posted=100, applied=50, when=NOW):
        return self.signed("attribution", name, dict(award_id=award, claim_sha256=self.claim_hashes[claim],
            snapshot_sha256=snap["snapshot_sha256"], credit_id=credit, posted_minor=posted,
            currency="USD", minor_unit_conversion_rate=100, applications=[dict(bill_id=bill, amount_minor=applied)],
            basis="EXACT_EXPLICIT_ALLOCATION", scope_verification=evidence("explicit-split-" + name)),
            ["finance_approver"], when=when)

    def ready(self, *, amount=100, total=100, applied=50):
        self.file()
        self.award(amount=amount)
        snap, _ = self.observe(self.snapshot(total=total, applied=applied))
        return snap

    def summary(self, when=NOW):
        return self.store.summary(self.config["tenant"], BUSINESS, at=when)


@pytest.fixture
def h(tmp_path):
    return Harness(tmp_path / "observation.sqlite")


def test_empty_actual_capture_reports_no_awards_or_cash(tmp_path):
    h = Harness(tmp_path / "db", mode="ACTUAL_NATIVE")
    assert h.summary()["captured_credits"] is None
    snap = h.snapshot()
    snap["credits"] = []
    snap["bills"] = []
    h.observe(snap)
    result = h.summary()
    assert result["status"] == "EMPTY"
    assert result["captured_credits"] == 0
    assert result["verified_award_count"] == 0
    assert result["actual_recovered_cash"] is None
    assert result["credits"] == []


@pytest.mark.parametrize("mode,stage", [("MOCK", "MOCK_APPLIED_ATTRIBUTED")])
def test_signed_observation_is_idempotent_durable_and_not_cash(tmp_path, mode, stage):
    h = Harness(tmp_path / "db", mode=mode)
    snap = h.ready()
    binding = h.binding(snap)
    assert h.store.attribute(binding, at=NOW)["duplicate"] is False
    assert h.store.attribute(binding, at=NOW)["duplicate"] is True
    h.store = AwardAttributionStore(h.path, h.config)
    result = h.summary()
    assert result["active_binding_count"] == result["historical_binding_count"] == 1
    credit = result["credits"][0]
    assert credit["stage"] == stage
    assert (credit["attributed_posted_minor"], credit["attributed_applied_minor"]) == (100, 50)
    assert credit["actual_recovered_cash"] is None
    with sqlite3.connect(h.path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'allocation_%'").fetchone()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM award_observation_allocation")


def test_award_and_bill_missing_keeps_native_financial_facts(h):
    body = h.snapshot()
    body["bills"] = None
    h.observe(body)
    row = h.summary()["credits"][0]
    assert row["stage"] == "APPLIED_UNATTRIBUTED"
    assert row["observed_total_minor"] == 100
    assert row["unattributed_applied_minor"] == 50
    assert h.summary()["verified_award_count"] == 0


@pytest.mark.parametrize("field", ["total_amount", "remaining_amount", "total_applied_amount", "applied_bills", "applied_draft_bills"])
def test_sparse_native_fields_are_unknown_not_zero(h, field):
    h.file()
    h.award()
    body = h.snapshot()
    body["credits"][0][field] = None
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError, match="UNKNOWN"):
        h.store.attribute(h.binding(snap), at=NOW)
    row = h.summary()["credits"][0]
    mapping = dict(total_amount="observed_total_minor", remaining_amount="observed_remaining_minor",
                   applied_bills="observed_applied_bills_minor", applied_draft_bills="observed_applied_drafts_minor")
    if field in mapping:
        assert row[mapping[field]] is None
    assert row["attributed_posted_minor"] == 0


@pytest.mark.parametrize("scopes", [None, [], ["vendors:read"]])
def test_unknown_or_insufficient_scopes_preserve_observation_but_not_attribution(h, scopes):
    h.file()
    h.award()
    body = h.snapshot()
    body["scopes"] = scopes
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError):
        h.store.attribute(h.binding(snap), at=NOW)
    assert h.summary()["credits"][0]["observed_total_minor"] == 100


def test_claim_must_exist_locally_and_scope_cannot_be_supplied_by_applicant(h):
    body = dict(claim_id="claim-1", dispatch_sha256=digest("pretend"), local_contract_id="local-contract",
        claimant_operator_id="fixture-claimant", scope=scope(), scope_verification=evidence("pretend"),
        bills=[dict(bill_id=BILL, eligible_minor=100, evidence=evidence("pretend"))])
    env = h.signed("filed_claim", "register", body, ["claim_registrar"])
    with pytest.raises(AttributionError, match="PREEXISTING_LOCAL_FILING"):
        h.store.register_claim(env, at=NOW)
    original = h.file()
    original["statement"]["body"]["scope"]["beneficiary_id"] = "applicant-fabrication"
    with pytest.raises(AttributionError):
        h.store.register_claim(original, at=NOW)


def test_signed_claim_scope_must_match_the_preexisting_economic_filing(tmp_path):
    other = {**scope(), "account_id": "account-2"}
    h = Harness(tmp_path / "db", extra_scopes=[other])
    env = h.file()
    body = deepcopy(env["statement"]["body"])
    body["scope"] = other
    changed = h.signed("filed_claim", "different-registration", body, ["claim_registrar"])
    with pytest.raises(AttributionError, match="LOCAL_FILING_SCOPE_CONFLICT"):
        h.store.register_claim(changed, at=NOW)


def test_scope_and_dispatch_are_immutable_after_registration(h):
    env = h.file()
    body = deepcopy(env["statement"]["body"])
    body["bills"][0]["eligible_minor"] += 1
    with pytest.raises(AttributionError, match="IMMUTABLE_CLAIM_SCOPE"):
        h.store.register_claim(h.signed("filed_claim", "new", body, ["claim_registrar"]), at=NOW)
    with sqlite3.connect(h.path) as db:
        db.execute(f"DROP TRIGGER {TABLE}_no_update")  # Explicit filesystem-owner tamper, beyond ordinary writes.
        db.execute(f"UPDATE {TABLE} SET packet_digest=?", (digest("changed"),))
    with pytest.raises(AttributionError, match="LOCAL_FILING_CHANGED"):
        h.award()


def test_native_record_equality_does_not_establish_contract_or_beneficiary(h):
    h.file(bill_ids=(uid(99),))
    h.award()
    body = h.snapshot()
    # Matching entity, reference bill, vendor and money still do not bind BILL to this claim.
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError, match="PREEXISTING_BILL_SCOPE_REQUIRED"):
        h.store.attribute(h.binding(snap), at=NOW)


@pytest.mark.parametrize("field,value", [("installation_id", "another-install"), ("tenant", "another-tenant"),
    ("business_id", uid(99)), ("kind", "filed_claim"), ("evidence_mode", "ACTUAL_NATIVE")])
def test_signature_audience_and_purpose_reflection_rejected(h, field, value):
    snap = h.ready()
    binding = h.binding(snap)
    binding["statement"][field] = value
    with pytest.raises(AttributionError, match="SIGNATURE_(AUDIENCE|PURPOSE)_CONFLICT"):
        h.store.attribute(binding, at=NOW)


def test_modified_signed_body_and_wrong_role_are_rejected(h):
    snap = h.ready()
    binding = h.binding(snap)
    binding["statement"]["body"]["posted_minor"] = 1
    with pytest.raises(AttributionError, match="INVALID_SIGNATURE"):
        h.store.attribute(binding, at=NOW)
    body = h.binding(snap)["statement"]["body"]
    wrong = h.signed("attribution", "wrong-role", body, ["vendor_verifier"])
    with pytest.raises(AttributionError, match="WRONG_PURPOSE"):
        h.store.attribute(wrong, at=NOW)


def test_expired_signatures_and_unregistered_vendor_verifier_fail(h):
    h.file()
    award = h.award()
    with pytest.raises(AttributionError, match="EXPIRED_OR_FUTURE_SIGNATURE"):
        h.store.import_award(award, at=later(121))
    award["endorsements"][0]["subject"] = "applicant-verifier"
    with pytest.raises(AttributionError, match="UNREGISTERED"):
        h.store.import_award(award, at=NOW)
    award = h.award()
    award["endorsements"] = award["endorsements"][:1]
    with pytest.raises(AttributionError, match="REQUIRED_INDEPENDENT_SIGNATURE"):
        h.store.import_award(award, at=NOW)


def test_office_rejects_same_person_same_key_and_previous_source_authority(h):
    for field in ("operator_id", "operator_key_sha256", "public_key", "subject"):
        cfg = deepcopy(h.config)
        cfg["witnesses"][2][field] = cfg["witnesses"][1][field]
        with pytest.raises(AttributionError, match="INDEPENDENT_WITNESSES"):
            AwardAttributionStore(h.path, cfg)
    cfg = deepcopy(h.config)
    cfg["authority_sources"] = [{k: cfg["witnesses"][1][k] for k in ("subject", "public_key")}]
    with pytest.raises(AttributionError, match="API_SOURCE"):
        AwardAttributionStore(h.path, cfg)
    with sqlite3.connect(h.path) as db:
        db.execute("CREATE TABLE authority_source(subject TEXT,public_key TEXT)")
        w = h.config["witnesses"][1]
        db.execute("INSERT INTO authority_source VALUES(?,?)", (w["subject"], w["public_key"]))
    with pytest.raises(AttributionError, match="API_SOURCE"):
        h.summary()


def test_reviewed_office_configuration_cannot_be_replaced_or_promoted(h):
    cfg = deepcopy(h.config)
    cfg["evidence_mode"] = "ACTUAL_NATIVE"
    with pytest.raises(AttributionError, match="OFFICE_CONFIGURATION_CHANGED"):
        AwardAttributionStore(h.path, cfg)


def test_native_label_cannot_be_attached_to_a_mock_capture(h):
    body = h.snapshot()
    body["source"] = "LIVE_RAMP_SANDBOX"
    with pytest.raises(AttributionError, match="MOCK_AND_NATIVE"):
        h.observe(body)


def test_cumulative_n_to_m_explicit_allocations_keep_unknown_remainder(h):
    h.file(bill_ids=(BILL, uid(6)))
    h.award(amount=70)
    h.award("award-2", amount=40)
    body = h.snapshot(total=100, applied=70)
    body["credits"][0]["applied_bills"] = [dict(bill_id=BILL, amount=money(40)), dict(bill_id=uid(6), amount=money(30))]
    body["bills"][0]["applied_vendor_credits"] = [dict(id=CREDIT, amount=money(40))]
    second = h.snapshot(total=30, applied=10, credit=uid(7), bill=uid(6))
    body["credits"] += second["credits"]
    body["bills"] += second["bills"]
    body["bills"][1]["applied_vendor_credits"].append(dict(id=CREDIT, amount=money(30)))
    snap, _ = h.observe(body)
    first = h.binding(snap, posted=50, applied=30)
    first_body = first["statement"]["body"]
    first_body["applications"].append(dict(bill_id=uid(6), amount_minor=10))
    h.store.attribute(h.signed("attribution", "a1-c1", first_body, ["finance_approver"]), at=NOW)
    h.store.attribute(h.binding(snap, name="a2-c1", award="award-2", posted=40, applied=10), at=NOW)
    h.store.attribute(h.binding(snap, name="a1-c2", credit=uid(7), bill=uid(6), posted=20, applied=10), at=NOW)
    result = h.summary()
    assert result["active_binding_count"] == 3
    assert [c["attributed_posted_minor"] for c in result["credits"]] == [90, 20]
    assert [c["attributed_applied_minor"] for c in result["credits"]] == [50, 10]
    assert [c["unattributed_applied_minor"] for c in result["credits"]] == [20, 0]


def test_split_without_explicit_basis_is_unsupported(h):
    snap = h.ready()
    binding = h.binding(snap, posted=30, applied=10)
    del binding["statement"]["body"]["basis"]
    with pytest.raises(AttributionError, match="SPLIT_BASIS_REQUIRED"):
        h.store.attribute(binding, at=NOW)


def test_one_minor_unit_and_partial_unrelated_residual(h):
    snap = h.ready(amount=1, total=2, applied=1)
    h.store.attribute(h.binding(snap, posted=1, applied=1), at=NOW)
    row = h.summary()["credits"][0]
    assert row["attributed_applied_minor"] == 1
    assert row["unattributed_posted_minor"] == 1


@pytest.mark.parametrize("posted,applied,error", [(101, 50, "CAPACITY"), (100, 51, "NATIVE_PAIR"), (25, 50, "APPLICATION_CAP")])
def test_amount_caps_roll_back_whole_binding(h, posted, applied, error):
    snap = h.ready()
    count = len(h.store.history())
    with pytest.raises(AttributionError, match=error):
        h.store.attribute(h.binding(snap, posted=posted, applied=applied), at=NOW)
    assert len(h.store.history()) == count
    assert h.summary()["historical_binding_count"] == 0


def test_competing_connections_cannot_overallocate_credit(h):
    snap = h.ready(amount=80)
    h.award("award-2", amount=80)
    envs = [h.binding(snap, name=f"bind-{i}", award=f"award-{i}", posted=80, applied=25) for i in (1, 2)]
    def allocate(env):
        store = AwardAttributionStore(h.path, h.config)
        try:
            store.attribute(env, at=NOW)
            return "ok"
        except AttributionError as exc:
            return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(allocate, envs))
    assert results.count("ok") == 1
    assert results.count("IMMUTABILITY_OR_CAPACITY_CONFLICT") == 1
    assert h.summary()["credits"][0]["attributed_posted_minor"] == 80


def test_new_snapshot_requires_fresh_explicit_approval_never_delta_adds(h):
    first = h.ready()
    old = h.binding(first)
    h.store.attribute(old, at=NOW)
    second, _ = h.observe(h.snapshot(name="capture-2", applied=70, when=later(1)))
    result = h.summary(later(1))
    assert result["credits"][0]["observed_applied_bills_minor"] == 70
    assert result["credits"][0]["attributed_applied_minor"] == 0
    with pytest.raises(AttributionError, match="CURRENT_EXACT_SNAPSHOT"):
        h.store.attribute(old, at=later(1))
    h.store.attribute(h.binding(second, name="approval-2", applied=70, when=later(1)), at=later(1))
    assert h.summary(later(1))["credits"][0]["attributed_applied_minor"] == 70
    assert h.summary(later(1))["historical_binding_count"] == 2


@pytest.mark.parametrize("change,expected", [("unapply", "UNAPPLICATION"), ("total", "IDENTITY_CHANGED"),
    ("void", "VOIDED"), ("archive", "ARCHIVED"), ("missing", "DISAPPEARED"), ("reciprocal", "RECIPROCAL")])
def test_conflicting_snapshots_invalidate_attribution_and_stay_quarantined(h, change, expected):
    first = h.ready()
    h.store.attribute(h.binding(first), at=NOW)
    body = h.snapshot(name="changed", when=later(1), applied=10 if change == "unapply" else 50,
                      total=110 if change == "total" else 100)
    if change == "void":
        body["bills"][0]["status"] = "VOIDED"
    elif change == "archive":
        body["credits"][0]["archived_at"] = later(1)
    elif change == "missing":
        body["credits"] = []
    elif change == "reciprocal":
        body["bills"][0]["applied_vendor_credits"][0]["amount"] = money(49)
    receipt, _ = h.observe(body)
    assert receipt["status"] == "QUARANTINED"
    assert expected in ",".join(receipt["issues"])
    h.observe(h.snapshot(name="looks-good-again", applied=70, when=later(2)))
    h.store = AwardAttributionStore(h.path, h.config)
    result = h.summary(later(2))
    assert result["status"] == "QUARANTINED"
    assert result["active_binding_count"] == 0
    assert result["credits"][0]["observed_applied_bills_minor"] == 70


def test_out_of_order_unapplication_conflict_is_not_ignored(h):
    h.observe(h.snapshot(name="later", applied=20, when=later(2)))
    receipt, _ = h.observe(h.snapshot(name="earlier", applied=50), when=later(2))
    assert receipt["status"] == "QUARANTINED"
    assert h.summary(later(2))["active_binding_count"] == 0


def test_same_event_id_with_conflicting_snapshot_cannot_leave_old_approval_active(h):
    first = h.ready()
    h.store.attribute(h.binding(first), at=NOW)
    receipt, _ = h.observe(h.snapshot(applied=20))
    assert receipt["status"] == "QUARANTINED"
    assert h.summary()["active_binding_count"] == 0


def test_vendor_award_reuse_or_changed_amount_quarantines(h):
    first = h.ready()
    h.store.attribute(h.binding(first), at=NOW)
    award = h.award()
    body = award["statement"]["body"]
    body["amount_minor"] = 101
    result = h.store.import_award(h.signed("vendor_award", "award-1", body,
        ["vendor_verifier", "finance_approver"]), at=NOW)
    assert result["status"] == "QUARANTINED"
    assert h.summary()["active_binding_count"] == 0


def test_stale_summary_retains_historical_observation_without_current_attribution(h):
    snap = h.ready()
    h.store.attribute(h.binding(snap), at=NOW)
    result = h.summary(later(1500))
    assert result["active_binding_count"] == 0
    assert result["credits"][0]["observed_total_minor"] == 100
    assert result["freshness"] == "STALE_OR_FUTURE"


def test_cross_account_fanout_is_rejected_even_with_equal_provider_fields(tmp_path):
    other = {**scope(), "account_id": "account-2", "beneficiary_id": "beneficiary-2"}
    h = Harness(tmp_path / "db", extra_scopes=[other])
    snap = h.ready()
    h.store.attribute(h.binding(snap, posted=50, applied=20), at=NOW)
    with pytest.raises(AttributionError, match="IMMUTABLE_BILL_SCOPE_CONFLICT"):
        h.file("claim-2", sc=other)
    # Retry registration of the SAME reserved claim with the correct separate
    # bill. Failed award registration cannot release a canonical filing lock.
    h.file("claim-2", sc=other, bill_ids=(uid(6),))
    h.award("award-2", claim="claim-2")
    body = h.snapshot(name="expanded", applied=70, when=later(1))
    body["credits"][0]["applied_bills"] = [dict(bill_id=BILL, amount=money(50)), dict(bill_id=uid(6), amount=money(20))]
    body["bills"][0]["applied_vendor_credits"] = [dict(id=CREDIT, amount=money(50))]
    body["bills"].append(dict(id=uid(6), vendor=dict(id=VENDOR), entity_id=ENTITY, status="OPEN",
        archived_at=None, amount=money(1000), applied_vendor_credits=[dict(id=CREDIT, amount=money(20))]))
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError, match="CROSS_ACCOUNT_OR_CONTRACT_FANOUT"):
        h.store.attribute(h.binding(snap, name="fanout", award="award-2", claim="claim-2",
            bill=uid(6), posted=50, applied=20, when=later(1)), at=later(1))


def test_existing_simulated_ledger_is_preserved_and_reserved_credit_not_stolen(h):
    from uptime.allocations import AllocationLedger
    snap = h.ready()
    ledger = AllocationLedger(h.path)
    base = dict(vendor_id=VENDOR, account_id="fixture-sim-account", product_id="fixture-sim-product",
        contract_id="fixture-sim-contract", contract_version="v1", currency="USD",
        amount_cents=99, effective_date="2026-11-04", memo_ref="fixture-sim-memo")
    ledger.record_award(h.config["tenant"], "fixture-sim-case", dict(base, id="fixture-sim-award",
        source_ref="fixture-sim-award", confirmed=True, source="SIMULATED_VENDOR"))
    ledger.record_credit(h.config["tenant"], dict(base, id=CREDIT, source_ref="fixture-sim-credit",
        award_id="fixture-sim-award", source="DETERMINISTIC_REPLAY"))
    before = ledger.history(h.config["tenant"])
    with pytest.raises(AttributionError, match="SIMULATED_LEDGER_CREDIT_RESERVED"):
        h.store.attribute(h.binding(snap), at=NOW)
    assert ledger.history(h.config["tenant"]) == before
    assert ledger.reconcile(h.config["tenant"], "fixture-sim-award")["posted_cents"] == 99


def test_office_config_loader_requires_protected_file(h, tmp_path):
    path = tmp_path / "office.json"
    path.write_text(canonical_json(h.config))
    path.chmod(0o600)
    assert load_office_config(path) == OfficeConfig.model_validate(h.config)
    path.chmod(0o644)
    with pytest.raises(AttributionError, match="PROTECTED_CONFIG"):
        load_office_config(path)


def test_finance_witness_must_match_current_real_operator_association(h):
    with sqlite3.connect(h.path) as db:
        db.execute("CREATE TABLE authority_user(subject TEXT,role TEXT,public_key BLOB)")
    with pytest.raises(AttributionError, match="ENROLLED_HUMAN_FINANCE_OPERATOR"):
        h.summary()


def test_small_order_public_key_rejected(h):
    cfg = deepcopy(h.config)
    cfg["witnesses"][0]["public_key"] = "00" * 32
    with pytest.raises(AttributionError, match="INVALID_OFFICECONFIG"):
        AwardAttributionStore(h.path, cfg)


def test_draft_utilization_is_separate_and_cannot_be_attributed(h):
    h.file()
    h.award()
    body = h.snapshot()
    body["credits"][0]["applied_draft_bills"] = body["credits"][0]["applied_bills"]
    body["credits"][0]["applied_bills"] = []
    body["bills"][0]["applied_vendor_credits"] = []
    snap, _ = h.observe(body)
    row = h.summary()["credits"][0]
    assert row["observed_applied_drafts_minor"] == 50
    assert row["observed_applied_bills_minor"] == 0
    with pytest.raises(AttributionError, match="DRAFT_APPLICATION_UNSUPPORTED"):
        h.store.attribute(h.binding(snap, applied=0), at=NOW)


def test_unapplied_posted_credit_requires_exact_scoped_bill(h):
    snap = h.ready(applied=0)
    assert h.summary()["credits"][0]["stage"] == "POSTED_UNATTRIBUTED"
    h.store.attribute(h.binding(snap, applied=0), at=NOW)
    row = h.summary()["credits"][0]
    assert row["attributed_posted_minor"] == 100
    assert row["attributed_applied_minor"] == 0


def test_missing_bill_readback_does_not_hide_posted_credit(h):
    h.file()
    h.award()
    body = h.snapshot()
    body["bills"] = []
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError, match="BILL_READBACK_MISSING"):
        h.store.attribute(h.binding(snap), at=NOW)
    assert h.summary()["credits"][0]["stage"] == "APPLIED_UNATTRIBUTED"


@pytest.mark.parametrize("field,value", [("list_complete", False), ("available", None), ("available", False)])
def test_incomplete_or_unavailable_capture_is_not_attributable(h, field, value):
    h.file()
    h.award()
    body = h.snapshot()
    body[field] = value
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError, match="COMPLETE_NATIVE_OBSERVATION"):
        h.store.attribute(h.binding(snap), at=NOW)
    assert h.summary()["credits"][0]["observed_total_minor"] == 100


@pytest.mark.parametrize("amount", [True, 1.0, "1", -1])
def test_native_money_accepts_only_nonnegative_exact_integer_units(h, amount):
    body = h.snapshot()
    body["credits"][0]["total_amount"]["amount"] = amount
    with pytest.raises(AttributionError, match="INVALID_NATIVESNAPSHOT"):
        h.observe(body)


def test_rate_bool_and_cross_currency_fail_closed(h):
    body = h.snapshot()
    body["credits"][0]["total_amount"]["minor_unit_conversion_rate"] = True
    with pytest.raises(AttributionError, match="INVALID_NATIVESNAPSHOT"):
        h.observe(body)
    body = h.snapshot()
    body["bills"][0]["amount"] = money(1000, "EUR")
    receipt, _ = h.observe(body)
    assert receipt["status"] == "QUARANTINED"
    assert receipt["issues"] == ["CROSS_CURRENCY"]


def test_unknown_archival_state_cannot_be_treated_as_active(h):
    h.file()
    h.award()
    body = h.snapshot()
    del body["credits"][0]["archived_at"]
    snap, _ = h.observe(body)
    with pytest.raises(AttributionError, match="ACTIVE_CREDIT_UNCONFIRMED"):
        h.store.attribute(h.binding(snap), at=NOW)


def test_same_time_snapshot_conflict_invalidates_current_approval(h):
    first = h.ready()
    h.store.attribute(h.binding(first), at=NOW)
    receipt, _ = h.observe(h.snapshot(name="same-time", applied=60))
    assert receipt["status"] == "QUARANTINED"
    assert "SAME_TIME_CONFLICT" in receipt["issues"]
    assert h.summary()["active_binding_count"] == 0


def test_award_cap_across_multiple_credits_and_claim_bill_cap(h):
    h.file(eligible=40)
    h.award(amount=100)
    body = h.snapshot()
    second = h.snapshot(credit=uid(8))
    body["credits"] += second["credits"]
    body["bills"][0]["applied_vendor_credits"] += second["bills"][0]["applied_vendor_credits"]
    snap, _ = h.observe(body)
    h.store.attribute(h.binding(snap, posted=80, applied=30), at=NOW)
    with pytest.raises(AttributionError, match="CAPACITY"):
        h.store.attribute(h.binding(snap, name="too-much-award", credit=uid(8), posted=30, applied=10), at=NOW)
    with pytest.raises(AttributionError, match="CLAIM_BILL_CAP"):
        h.store.attribute(h.binding(snap, name="too-much-bill", credit=uid(8), posted=20, applied=11), at=NOW)
    assert h.summary()["historical_binding_count"] == 1


def test_pair_cap_across_awards_rejects_double_use(h):
    snap = h.ready()
    h.award("award-2")
    h.store.attribute(h.binding(snap, posted=50, applied=30), at=NOW)
    with pytest.raises(AttributionError, match="CAPACITY"):
        h.store.attribute(h.binding(snap, name="pair-overrun", award="award-2", posted=50, applied=21), at=NOW)


def test_claim_and_snapshot_must_preexist_signed_confirmation(h):
    h.file(when=later(1))
    with pytest.raises(AttributionError, match="CLAIM_MUST_PREEXIST_SIGNATURE"):
        h.award(when=NOW)
    h.award(when=later(1))
    snap, _ = h.observe(h.snapshot(when=later(2)))
    with pytest.raises(AttributionError, match="EVIDENCE_MUST_PREEXIST_APPROVAL"):
        h.store.attribute(h.binding(snap, when=later(1)), at=later(2))


def test_registered_scope_is_rechecked_in_current_summary(h):
    snap = h.ready()
    h.store.attribute(h.binding(snap), at=NOW)
    with sqlite3.connect(h.path) as db:
        db.execute(f"DROP TRIGGER {TABLE}_no_update")
        db.execute(f"UPDATE {TABLE} SET packet_digest=?", (digest("changed-after-binding"),))
    result = h.summary()
    assert result["active_binding_count"] == 0
    assert "LOCAL_FILING_CHANGED" in result["issues"]
    assert result["credits"][0]["observed_total_minor"] == 100


def test_independent_vendor_channel_cannot_be_replaced_with_ramp_posting(h):
    h.file()
    env = h.award()
    body = env["statement"]["body"]
    body["confirmation"]["channel"] = "RAMP_READBACK"
    changed = h.signed("vendor_award", "award-from-ramp", body, ["vendor_verifier", "finance_approver"])
    with pytest.raises(AttributionError, match="INVALID_VENDORAWARD"):
        h.store.import_award(changed, at=NOW)


def test_successful_offline_human_association_and_changed_enrollment(h):
    cfg = deepcopy(h.config)
    # New store/config for a fixture login key with an explicitly reviewed association.
    login_key = b"FIXTURE LOGIN PUBLIC KEY"
    finance = cfg["witnesses"][2]
    finance["operator_key_sha256"] = sha256(login_key).hexdigest()
    path = h.path.with_name("associated.sqlite")
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE authority_user(subject TEXT,role TEXT,public_key BLOB)")
        db.execute("INSERT INTO authority_user VALUES(?,?,?)", (finance["operator_id"], "reviewer", login_key))
    store = AwardAttributionStore(path, cfg)
    assert store.summary(cfg["tenant"], BUSINESS, at=NOW)["status"] == "UNAVAILABLE"
    with sqlite3.connect(path) as db:
        db.execute("UPDATE authority_user SET public_key=?", (b"changed fixture key",))
    with pytest.raises(AttributionError, match="FINANCE_OPERATOR_ASSOCIATION_CHANGED"):
        store.summary(cfg["tenant"], BUSINESS, at=NOW)


def test_concurrent_exact_retries_record_only_one_allocation(h):
    snap = h.ready()
    envelope = h.binding(snap)
    def submit(_):
        return AwardAttributionStore(h.path, h.config).attribute(envelope, at=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(submit, range(2)))
    assert sorted(r["duplicate"] for r in result) == [False, True]
    assert h.summary()["historical_binding_count"] == 1


@pytest.mark.parametrize("role", ["vendor_verifier", "claim_registrar", "ramp_observer"])
def test_previous_expired_grants_cannot_support_current_attribution(h, role):
    cfg = deepcopy(h.config)
    next(w for w in cfg["witnesses"] if w["role"] == role)["valid_until"] = later(30)
    h.path = h.path.with_name("short-lived-authority.sqlite")
    h.config = cfg
    h.store = AwardAttributionStore(h.path, cfg)
    snap = h.ready()
    old = h.binding(snap)
    h.store.attribute(old, at=NOW)
    with pytest.raises(AttributionError, match="EXPIRED_WITNESS_GRANT"):
        h.store.attribute(old, at=later(31))
    result = h.summary(later(31))
    assert result["active_binding_count"] == 0
    assert "EXPIRED_WITNESS_GRANT" in result["issues"]
    assert result["credits"][0]["observed_total_minor"] == 100


@pytest.mark.parametrize("field", ["account_id", "beneficiary_id", "contract_id", "contract_version", "product_id"])
def test_unknown_scope_sentinels_cannot_be_registered(h, field):
    cfg = deepcopy(h.config)
    cfg["witnesses"][0]["scopes"][0][field] = "UNKNOWN"
    with pytest.raises(AttributionError, match="INVALID_OFFICECONFIG"):
        AwardAttributionStore(h.path, cfg)
