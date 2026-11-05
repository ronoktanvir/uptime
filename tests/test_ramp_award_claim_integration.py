"""Exercise persisted platform claims, not replacement claim tables.

All people, independent custody attestations and provider captures are generated
TEST EVIDENCE. ACTUAL_NATIVE tests exercise a trust protocol; no fixture is a real
claim, vendor communication, credit, or commercially authorized recovery.
"""
from datetime import datetime
import json
import sqlite3

import pytest

from uptime import claim_identity
from uptime.claim_identity import TABLE, reserve_claim
from uptime.contracts import Citation, EvaluationResult, Outcome, Principal, fingerprint
from uptime.correspondence import CorrespondenceDesk
from uptime.correspondence_rules import ActiveRemedy
from uptime.correspondence_types import Claim, Delivery, Scope
from uptime.ramp_award_attribution import AttributionError, AwardAttributionStore, digest
from test_cross_claims import setup, P, LEGACY, INBOX
from test_ramp_award_attribution import Harness, NOW, BILL, BUSINESS, evidence, later, scope, uid


def register(h, claim, sc, *, local_contract=None, external=None, roles=None, dispatch=None, bill=BILL):
    body = dict(claim_id=claim, dispatch_sha256=dispatch or h.store.filing_identity(claim),
                local_contract_id=local_contract or sc["contract_id"], claimant_operator_id="fixture-claimant",
                scope=sc, scope_verification=evidence("independent-scope"),
                bills=[dict(bill_id=bill, eligible_minor=1000, evidence=evidence("bill"))])
    if external is not None:
        body["external_filing"] = external
    signed = h.signed("filed_claim", "register-" + claim, body,
                      roles or (["claim_registrar", "vendor_verifier"] if h.config["evidence_mode"] == "ACTUAL_NATIVE" else ["claim_registrar"]))
    result = h.store.register_claim(signed, at=NOW)
    h.claim_hashes[claim], h.claim_scopes[claim] = result["claim_sha256"], sc
    return signed


def twilio(path, route, *, mode="MOCK", versions=()):
    legacy, inbox, local = setup(path)
    claim = LEGACY if route == "legacy" else INBOX
    (legacy if route == "legacy" else inbox).act(P, claim, "submit-claim")
    sc = scope() | dict(vendor_name=local.vendor, account_id=local.account, contract_id="twilio-apis",
                        contract_version="2026-04-09", service_name=local.service, month=local.month, remedy="availability")
    h = Harness(path, tenant=P.tenant, mode=mode, extra_scopes=[sc, *(sc | {"contract_version": v} for v in versions)])
    return h, claim, sc, "twilio-apis" if route == "legacy" else local.contract


def downgrade_to_v1(path):
    """Exact historical schema/hash, derived from an actual platform receipt.

    Used ONLY to test a pre-v2 database. Normal tests retain the real v2 schema.
    """
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        rows = [dict(r) for r in db.execute(f"SELECT * FROM {TABLE}")]
        db.execute("""CREATE TABLE claim_dispatch_identity (
            obligation TEXT NOT NULL, step TEXT NOT NULL, route TEXT NOT NULL, case_id TEXT NOT NULL,
            scope TEXT NOT NULL, packet_digest TEXT NOT NULL, receipt_id TEXT NOT NULL UNIQUE, at TEXT NOT NULL,
            PRIMARY KEY(obligation,step))""")
        for r in rows:
            if r["route"] == "legacy":
                receipt = json.loads(db.execute("SELECT body FROM dispute_receipts WHERE id=?", (r["receipt_id"],)).fetchone()[0])
                identity, _ = claim_identity._legacy(receipt["payload"])
            else:
                state = json.loads(db.execute("SELECT state FROM inbox_claim WHERE id=?", (r["case_id"],)).fetchone()[0])
                receipt = next(s for s in state["submissions"] if s["id"] == r["receipt_id"])
                p = receipt["packet"]
                local = p["scope"]
                identity = dict(tenant=p["tenant"], vendor=local["vendor"], account=local["account"],
                    agreement_id=p["agreement_id"], agreement_version=p["version"], service=local["service"],
                    month=local["month"], remedy=json.loads(r["identity"])[-1])
            db.execute("INSERT INTO claim_dispatch_identity VALUES(?,?,?,?,?,?,?,?)",
                       (claim_identity._v1_key(identity), *(r[k] for k in
                        ("step", "route", "case_id", "scope", "packet_digest", "receipt_id", "at"))))
        db.execute(f"DROP TABLE {TABLE}")


@pytest.mark.parametrize("route", ["legacy", "correspondence"])
@pytest.mark.parametrize("v1", [False, True])
def test_real_local_routes_register_mock_and_preserve_history(tmp_path, route, v1):
    h, claim, sc, local = twilio(tmp_path / "db", route)
    if v1:
        downgrade_to_v1(h.path)
    register(h, claim, sc, local_contract=local)
    h.award(claim=claim)
    snap, _ = h.observe()
    h.store.attribute(h.binding(snap, claim=claim), at=NOW)
    assert h.summary()["credits"][0]["stage"] == "MOCK_APPLIED_ATTRIBUTED"
    with sqlite3.connect(h.path) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert (TABLE in tables) is not v1
        assert ("claim_dispatch_identity" in tables) is v1
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM award_observation_claim")


@pytest.mark.parametrize("route", ["legacy", "correspondence"])
@pytest.mark.parametrize("v1", [False, True])
def test_actual_cannot_use_simulated_dispatch_even_with_witness(tmp_path, route, v1):
    h, claim, sc, local = twilio(tmp_path / "db", route, mode="ACTUAL_NATIVE")
    if v1:
        downgrade_to_v1(h.path)
    forged = dict(evidence_mode="ACTUAL_EXTERNAL", receipt_id="invented", receipt_sha256="a"*64,
                  received_at=later(-30), submitted_to="fixture.invalid", channel="VENDOR_PORTAL",
                  verification=evidence("invented"), authority_verification=evidence("invented-authority"),
                  independence_verification=evidence("invented-independence"))
    with pytest.raises(AttributionError, match="ACTUAL_EXTERNAL_FILING_REQUIRED"):
        register(h, claim, sc, local_contract=local, external=forged)
    assert not h.store.history()
    assert h.summary()["verified_award_count"] == 0


def test_bare_canonical_reservation_is_not_an_actual_claim(tmp_path):
    h = Harness(tmp_path / "db", mode="ACTUAL_NATIVE")
    # Harness.file uses the public reserve_claim API, but deliberately has no
    # receipt or independent external filing. Even valid witnesses cannot fix it.
    with pytest.raises(AttributionError, match="SIGNATURE"):
        h.file()
    with pytest.raises(AttributionError, match="ACTUAL_EXTERNAL_FILING_REQUIRED"):
        register(h, "claim-1", scope(), local_contract="local-contract")


@pytest.mark.parametrize("route", ["legacy", "correspondence"])
@pytest.mark.parametrize("raw_hash", [False, True])
def test_v1_registration_survives_additive_canonical_migration(tmp_path, route, raw_hash):
    h, claim, sc, local = twilio(tmp_path / "db", route)
    downgrade_to_v1(h.path)
    hashed = None
    if raw_hash:
        with sqlite3.connect(h.path) as db:
            db.row_factory = sqlite3.Row
            hashed = digest(dict(db.execute("SELECT * FROM claim_dispatch_identity").fetchone()))
    envelope = register(h, claim, sc, local_contract=local, dispatch=hashed)
    before = h.store.filing_identity(claim)
    with sqlite3.connect(h.path) as db:
        db.execute("BEGIN IMMEDIATE")
        # The real migration runs before the deliberately rejected duplicate.
        with pytest.raises(ValueError, match="another claim"):
            reserve_claim(db, tenant=P.tenant, vendor=sc["vendor_name"], account=sc["account_id"],
                agreement_id=sc["contract_id"], agreement_version="republished-version", service=sc["service_name"],
                month=sc["month"], remedy=sc["remedy"], route="new-route", case_id="duplicate",
                packet_digest="f"*64, scope={"explicit": "different"}, receipt_id="new", at=NOW)
    assert h.store.filing_identity(claim) == before
    assert h.store.register_claim(envelope, at=NOW)["duplicate"]
    h.award(claim=claim)


def test_v1_orphan_never_authorizes_award(tmp_path):
    h, claim, sc, local = twilio(tmp_path / "db", "correspondence")
    downgrade_to_v1(h.path)
    with sqlite3.connect(h.path) as db:
        db.execute("DELETE FROM inbox_claim WHERE id=?", (claim,))
    with pytest.raises(AttributionError, match="HISTORICAL_FILING_UNRESOLVED"):
        register(h, claim, sc, local_contract=local)


def test_v1_version_alias_double_filing_is_not_two_awards(tmp_path):
    h, claim, sc, local = twilio(tmp_path / "db", "correspondence")
    downgrade_to_v1(h.path)
    with sqlite3.connect(h.path) as db:
        db.row_factory = sqlite3.Row
        original = dict(db.execute("SELECT * FROM inbox_claim WHERE id=?", (claim,)).fetchone())
        row = dict(db.execute("SELECT * FROM claim_dispatch_identity").fetchone())
        state = json.loads(original["state"])
        receipt = state["submissions"][0]
        receipt["id"] = "second-receipt"
        receipt["packet"]["claim"] = "alias"
        receipt["packet"]["version"] = "republished"
        receipt["digest"] = receipt["approval"]["digest"] = fingerprint(receipt["packet"])
        identity = dict(tenant=P.tenant, vendor=sc["vendor_name"], account=sc["account_id"],
            agreement_id=sc["contract_id"], agreement_version="republished", service=sc["service_name"],
            month=sc["month"], remedy=sc["remedy"])
        db.execute("INSERT INTO inbox_claim VALUES(?,?,?,?,?)", (P.tenant,"alias","alias-intake",original["scope"],json.dumps(state)))
        db.execute("INSERT INTO claim_dispatch_identity VALUES(?,?,?,?,?,?,?,?)",
            (claim_identity._v1_key(identity),"initial","correspondence","alias",row["scope"],receipt["digest"],receipt["id"],row["at"]))
    with pytest.raises(AttributionError, match="CANONICAL_FILING_CONFLICT"):
        register(h, claim, sc, local_contract=local)


def test_version_is_not_part_of_v2_key_but_is_part_of_filed_packet(tmp_path):
    h, claim, sc, local = twilio(tmp_path / "db", "correspondence", versions=["new-version"])
    wrong = sc | {"contract_version": "new-version"}
    with pytest.raises(AttributionError, match="LOCAL_FILING_SCOPE_CONFLICT"):
        register(h, claim, wrong, local_contract=local)


def historical(h, *, claim="inbox-external", sc=None, receipt="external-original", supplement=False, pin_version=True):
    sc = sc or scope() | {"remedy": "resource-month/station-1"}
    local = Scope(account=sc["account_id"], vendor=sc["vendor_name"], contract="local-contract", service=sc["service_name"],
                  component="station-1", region="west", invoice="invoice-1", incident="incident-1", currency="USD", month=sc["month"])
    # A bounded resolver fixture supplies a reviewed lineage to the REAL intake;
    # it grants no award/filing authority. The separate office signatures do.
    def resolver(tenant, requested, events, at):
        return ActiveRemedy(tenant, requested, fingerprint([[e["source"],e["digest"]] for e in events]),
            sc["contract_version"], datetime.fromisoformat(later(60)), EvaluationResult(Outcome.MISSING, (Citation("Test fixture", "v1", "scope", "urn:fixture:scope"),), ("Test fixture",), ("No entitlement attested",)),
            agreement_id=sc["contract_id"], remedy=sc["remedy"])
    desk = CorrespondenceDesk(h.path, clock=lambda: datetime.fromisoformat(later(-10)), active_resolver=resolver)
    tenant = h.config["tenant"]
    desk.provision(tenant, *(getattr(local,k) for k in ("account","vendor","contract","service","component","region")))
    desk.bind_sender(tenant, local.account, "vendor", "fixture-inbound-vendor", scope=local)
    desk.create(Principal(tenant, "fixture-claimant", "reviewer"), Claim(claim_id=claim, scope=local))
    original = dict(kind="original_filing_receipt", source_ref="test-custody-document", receipt_id=receipt,
                    received_at=later(-30), observed_at=later(-20), submitted_to="https://fixture.invalid/claims", fields=[])
    if pin_version and not supplement:
        original["contract_version"] = sc["contract_version"]
    body = original if not supplement else original | dict(kind="supplement_filing_receipt", original_ref=receipt, receipt_id="supplement")
    desk.receive(Principal(tenant, "fixture-inbound-vendor", "service"), claim, Delivery(event_id="original", scope=local, body=body))
    return desk, local, sc


def witness(h, claim="inbox-external", *, mode="ACTUAL_EXTERNAL"):
    with sqlite3.connect(h.path) as db:
        state = json.loads(db.execute("SELECT state FROM inbox_claim WHERE tenant=? AND id=?", (h.config["tenant"], claim)).fetchone()[0])
    fact = next(e for e in state["evidence"] if e["kind"] == "original_filing_receipt")
    return dict(evidence_mode=mode, receipt_id=fact["body"]["receipt_id"], receipt_sha256=digest(fact),
                received_at=fact["body"]["received_at"], submitted_to=fact["body"]["submitted_to"], channel="VENDOR_PORTAL",
                verification=evidence("independent-external-custody"), authority_verification=evidence("external-authority"),
                independence_verification=evidence("external-independence"))


def external_harness(tmp_path, *, extra=(), pin_version=True):
    sc = scope() | {"remedy":"resource-month/station-1"}
    h = Harness(tmp_path / "db", mode="ACTUAL_NATIVE", extra_scopes=[sc, *extra])
    desk, local, _ = historical(h, sc=sc, pin_version=pin_version)
    return h, desk, local, sc


def test_independently_witnessed_external_receipt_to_native_credit_protocol(tmp_path):
    h, desk, local, sc = external_harness(tmp_path)
    register(h, "inbox-external", sc, local_contract=local.contract, external=witness(h))
    h.award(claim="inbox-external")
    snap, _ = h.observe()
    binding = h.binding(snap, claim="inbox-external")
    h.store.attribute(binding, at=NOW)
    h.store = AwardAttributionStore(h.path, h.config)
    assert h.store.attribute(binding, at=NOW)["duplicate"]
    row = h.summary()
    assert row["credits"][0]["stage"] == "RAMP_APPLIED_ATTRIBUTED"
    assert row["credits"][0]["attributed_applied_minor"] == 50
    assert row["actual_recovered_cash"] is None
    case = desk.case(Principal(h.config["tenant"], "fixture-claimant", "reviewer"), "inbox-external")
    assert case["stage"] == "HISTORICAL_FILING" and case["submissions"] == []
    assert case["ledger"]["awarded"] == "0.00"


@pytest.mark.parametrize("fault", ["missing", "mock", "receipt", "digest", "time", "destination", "one-signer"])
def test_external_intake_cannot_authorize_actual_without_exact_independent_witness(tmp_path, fault):
    h, _, local, sc = external_harness(tmp_path)
    proof = witness(h)
    roles = None
    if fault == "missing":
        proof = None
    elif fault == "mock":
        proof["evidence_mode"] = "MOCK"
    elif fault == "one-signer":
        roles = ["claim_registrar"]
    else:
        key, value = {"receipt": ("receipt_id", "another"), "digest": ("receipt_sha256", "a"*64),
                      "time": ("received_at", later(-29)), "destination": ("submitted_to", "another.invalid")}[fault]
        proof[key] = value
    with pytest.raises(AttributionError):
        register(h, "inbox-external", sc, local_contract=local.contract, external=proof, roles=roles)
    assert h.store.history() == []


def test_supplement_is_not_an_original_external_filing(tmp_path):
    sc = scope() | {"remedy":"resource-month/station-1"}
    h = Harness(tmp_path / "db", mode="ACTUAL_NATIVE", extra_scopes=[sc])
    historical(h, sc=sc, supplement=True)
    with pytest.raises(AttributionError, match="ORIGINAL_EXTERNAL_RECEIPT_REQUIRED"):
        h.store.filing_identity("inbox-external")


def test_original_external_receipt_cannot_fan_out_to_another_account(tmp_path):
    sc2 = scope() | {"remedy":"resource-month/station-1", "account_id":"another-account"}
    h, _, local, sc = external_harness(tmp_path, extra=[sc2])
    register(h, "inbox-external", sc, local_contract=local.contract, external=witness(h))
    historical(h, claim="inbox-second", sc=sc2)
    with pytest.raises(AttributionError, match="IMMUTABILITY_OR_CAPACITY_CONFLICT"):
        register(h, "inbox-second", sc2, local_contract=local.contract, external=witness(h, "inbox-second"), bill=uid(42))
    assert len(h.store.history()) == 1


@pytest.mark.parametrize("fault", ["receipt", "delivery", "grant"])
def test_later_external_evidence_changes_suspend_current_attribution(tmp_path, fault):
    h, _, local, sc = external_harness(tmp_path)
    register(h, "inbox-external", sc, local_contract=local.contract, external=witness(h))
    h.award(claim="inbox-external")
    snap, _ = h.observe()
    h.store.attribute(h.binding(snap, claim="inbox-external"), at=NOW)
    with sqlite3.connect(h.path) as db:
        if fault == "delivery":
            db.execute("DELETE FROM inbox_delivery")
        else:
            state = json.loads(db.execute("SELECT state FROM inbox_claim").fetchone()[0])
            if fault == "receipt":
                state["evidence"][0]["body"]["receipt_id"] = "substituted"
            else:
                state["evidence"][0]["source_grant_id"] = "substituted"
            db.execute("UPDATE inbox_claim SET state=?", (json.dumps(state),))
    summary = h.summary()
    assert summary["active_binding_count"] == 0
    assert summary["credits"][0]["stage"] == "APPLIED_UNATTRIBUTED"
    assert summary["credits"][0]["observed_total_minor"] == 100
    assert summary["issues"]
    with pytest.raises(AttributionError):
        h.award(name="another-award", claim="inbox-external")


def test_summary_and_identity_are_read_only(tmp_path, monkeypatch):
    h, claim, sc, local = twilio(tmp_path / "db", "correspondence")
    downgrade_to_v1(h.path)
    register(h, claim, sc, local_contract=local)
    h.award(claim=claim)
    snap, _ = h.observe()
    h.store.attribute(h.binding(snap, claim=claim), at=NOW)
    connect = sqlite3.connect
    def read_only(*args, **kwargs):
        db = connect(*args, **kwargs)
        db.execute("PRAGMA query_only=ON")
        return db
    monkeypatch.setattr(sqlite3, "connect", read_only)
    h.store.filing_identity(claim)
    assert h.summary()["active_binding_count"] == 1
    assert h.store.summary(h.config["tenant"], BUSINESS, at=NOW)["actual_recovery"] is None


@pytest.mark.parametrize("change", ["version", "labels", "incident"])
def test_v2_canonical_duplicates_remain_locked_after_award_registration(tmp_path, change):
    h, claim, sc, local = twilio(tmp_path / "db", "correspondence")
    register(h, claim, sc, local_contract=local)
    with sqlite3.connect(h.path) as db:
        local_scope = json.loads(db.execute(f"SELECT scope FROM {TABLE} WHERE step='initial'").fetchone()[0])
        identity = dict(tenant=P.tenant, vendor=sc["vendor_name"], account=sc["account_id"],
            agreement_id=sc["contract_id"], agreement_version=sc["contract_version"], service=sc["service_name"],
            month=sc["month"], remedy=sc["remedy"])
        if change == "version":
            identity["agreement_version"] = "republished"
        elif change == "labels":
            identity.update(vendor="TWILIO", service="twilio messaging api")
        else:
            local_scope["incident"] = "alias"
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="another claim"):
            reserve_claim(db, **identity, route="another-route", case_id="alias", packet_digest="f"*64,
                          scope=local_scope, receipt_id="duplicate", at=NOW)
    h.award(claim=claim)


def test_old_writer_unindexed_receipt_cannot_be_ignored(tmp_path):
    h, claim, sc, local = twilio(tmp_path / "db", "correspondence")
    register(h, claim, sc, local_contract=local)
    with sqlite3.connect(h.path) as db:
        row = db.execute("SELECT scope,state FROM inbox_claim WHERE id=?", (claim,)).fetchone()
        state = json.loads(row[1])
        receipt = state["submissions"][0]
        receipt["id"] = "unindexed"
        receipt["packet"]["claim"] = "old-writer"
        receipt["digest"] = receipt["approval"]["digest"] = fingerprint(receipt["packet"])
        db.execute("INSERT INTO inbox_claim VALUES(?,?,?,?,?)", (P.tenant,"old-writer","old-intake",row[0],json.dumps(state)))
    with pytest.raises(AttributionError, match="UNINDEXED_HISTORICAL_FILING"):
        h.award(claim=claim)


def test_read_only_cli_smoke(tmp_path):
    import subprocess
    import sys
    h, claim, _, _ = twilio(tmp_path / "db", "correspondence")
    config = tmp_path / "office.json"
    config.write_text(json.dumps(h.config))
    config.chmod(0o600)
    command = [sys.executable, "scripts/ramp_match_award.py", "--db", str(h.path), "--office-config", str(config)]
    with sqlite3.connect(h.path) as db:
        before = list(db.iterdump())
    result = subprocess.run(command + ["filing-identity", claim], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)["dispatch_sha256"] == h.store.filing_identity(claim)
    result = subprocess.run(command + ["summary"], check=True, capture_output=True, text=True)
    summary = json.loads(result.stdout)
    assert summary["status"] == "UNAVAILABLE" and summary["actual_recovered_cash"] is None
    with sqlite3.connect(h.path) as db:
        assert list(db.iterdump()) == before
