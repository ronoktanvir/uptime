"""Ambiguous delimiters cannot authorize conflated financial obligations."""
import sqlite3
from hashlib import sha256
import json
from datetime import UTC, datetime
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

from uptime.claim_identity import claim_key, resource_remedy, reserve_claim
from uptime.contracts import fingerprint
from uptime.correspondence_types import Scope
from uptime.vendor_terms import Overlay, bind_overlay
from uptime.vendor_model import MODEL
from test_vendor_resource import DOC, OVERLAY, PROPOSAL, compiled
from test_v4_routes_integration import App
from test_correspondence_regional import regional, original as regional_original
from test_correspondence_service import service, reports as service_reports
from test_correspondence_resource import deliver


@pytest.mark.parametrize("resource,region", [
    ("cell/a", "North"), ("cell", "a/North"), ("cell/North", None), ("aggregate-service", None),
])
def test_ambiguous_measurement_tuple_is_refused_without_minting_an_alternative_key(resource, region):
    manifest = compiled()
    overlay = OVERLAY | {"resource_id":resource}
    if region is not None:
        manifest["subscription"] = {"scope":"account_product_region"}
        overlay["subscription_record"] = {"region":region}
    with pytest.raises(ValueError, match="ambiguous|reserved"):
        resource_remedy(manifest, overlay)


def test_source_overlay_binding_rejects_ambiguous_resource_before_financial_publication():
    with pytest.raises(ValueError, match="ambiguous|reserved"):
        bind_overlay(compiled(), Overlay(**(OVERLAY | {"resource_id":"cell/North"})))


def test_normal_candidate_intake_quarantines_ambiguous_measurement_identity(tmp_path, monkeypatch):
    source_hash = sha256(DOC["text"].encode()).hexdigest()
    capture = dict(model=MODEL, source_sha256=source_hash, session="synthetic-identity-delimiter-control",
                   at="2026-07-01T06:00:00Z", proposal=PROPOSAL, proposal_sha256=fingerprint(PROPOSAL))
    (tmp_path / (source_hash + ".json")).write_text(json.dumps(capture))
    monkeypatch.setenv("UPTIME_PUBLIC_EXTRACTIONS", str(tmp_path))
    monkeypatch.setenv("UPTIME_MODEL_PROPOSITIONS", "1")
    env = App(tmp_path / "intake.db")
    try:
        result = env.post("/api/vendors/ambiguous-resource/candidates",
                          dict(document=DOC, overlay=OVERLAY | {"resource_id":"cell/North"}))
        assert result["state"] == "QUARANTINED" and result["outcome"] == "UNSUPPORTED_RULE"
        assert result["active_version"] is None and result["actions"] == []
        assert "manual reconciliation" in result["reason"]
        assert "cell/North" not in result["reason"]
    finally:
        env.client.close()


def test_safe_legacy_keys_and_reservation_bytes_survive_retry(tmp_path):
    manifest = compiled()
    assert resource_remedy(manifest, OVERLAY) == "resource-month/station-21"
    assert resource_remedy(manifest | {"subscription":{}}, OVERLAY) == "resource-month/station-21"
    regional = manifest | {"subscription":{"scope":"account_product_region"}}
    assert resource_remedy(regional, OVERLAY | {"subscription_record":{"region":"North"}}) == "resource-month/station-21/North"
    assert resource_remedy(manifest | {"aggregate_monitor":"authoritative_vendor_minutes"}, {}) == "resource-month/aggregate-service"
    args = dict(tenant="bears", vendor="Provider", account="account-71", agreement_id="agreement-71",
                agreement_version="old-version", service="Service", month="2026-06", remedy="resource-month/station-21/North",
                route="correspondence", case_id="inbox-old", packet_digest=fingerprint({"packet":"old"}),
                scope={"component":"station-21","region":"North"}, receipt_id="old-receipt", at="2026-07-01T00:00:00Z")
    key = claim_key(**{k:args[k] for k in ("tenant","vendor","account","agreement_id","agreement_version","service","month","remedy")})
    with sqlite3.connect(tmp_path / "old-reservation.db") as db:
        db.execute("BEGIN IMMEDIATE")
        before = reserve_claim(db, **args)
        saved = db.execute("SELECT * FROM claim_dispatch_identity_v2").fetchall()
        assert before["obligation"] == key
        assert reserve_claim(db, **(args | {"agreement_version":"new-version"}))["created"] is False
        assert db.execute("SELECT * FROM claim_dispatch_identity_v2").fetchall() == saved


@pytest.mark.parametrize("legacy_resource,new_resource,region,aggregate", [
    ("cell/North", "cell", "North", False),
    ("aggregate-service", "ordinary-service-label", "North", True),
])
def test_historical_shadow_reservation_refuses_before_mutation_and_survives_restart(
        tmp_path, legacy_resource, new_resource, region, aggregate):
    manifest = compiled() | ({"aggregate_monitor":"authoritative_vendor_minutes"} if aggregate
                             else {"subscription":{"scope":"account_product_region"}})
    safe_remedy = resource_remedy(manifest, OVERLAY | {"resource_id":new_resource,
                                                     "subscription_record":{"region":region}})
    assert safe_remedy == "resource-month/" + legacy_resource
    args = dict(tenant="bears", vendor="Provider", account="account-71", agreement_id="agreement-71",
        agreement_version="old-version", service="Service", month="2026-06", remedy=safe_remedy,
        route="correspondence", case_id="historical-owner", packet_digest=fingerprint({"packet":"old"}),
        scope={"component":legacy_resource,"region":"old-region"}, receipt_id="original-receipt", at="2026-07-01T00:00:00Z")
    path = tmp_path / "historical-shadow.db"
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        reserve_claim(db, **args)
        saved = db.execute("SELECT * FROM claim_dispatch_identity_v2").fetchall()
    # A restarted current writer must not adopt the old key by copying its owner
    # or by treating a changed full scope as a supplement.
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        for changes in (
            {"case_id":"new-owner"},
            {"scope":{"component":new_resource,"region":region}},
            {"scope":{"component":new_resource,"region":region}, "initial_receipt_id":"original-receipt"},
        ):
            before = db.total_changes
            with pytest.raises(ValueError, match="belongs|scope differs"):
                reserve_claim(db, **(args | changes | {"agreement_version":"current-version"}))
            assert db.total_changes == before
            assert db.execute("SELECT * FROM claim_dispatch_identity_v2").fetchall() == saved
        assert not reserve_claim(db, **args)["created"]
        supplement = args | dict(receipt_id="one-supplement", initial_receipt_id="original-receipt",
                                 packet_digest=fingerprint({"packet":"supplement"}))
        result = reserve_claim(db, **supplement)
        assert result["obligation"] == saved[0][0] and result["step"] == "supplement"
        assert db.execute("SELECT * FROM claim_dispatch_identity_v2 WHERE step='initial'").fetchall() == saved
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE claim_dispatch_identity_v2 SET scope='{}'")


def seed_shadow(env, *, aggregate=False):
    scope = dict(env.scope)
    old_scope = scope | {"component":"aggregate-service" if aggregate else scope["component"] + "/" + scope["region"],
                        "region":"historical-region"}
    remedy = "resource-month/aggregate-service" if aggregate else "resource-month/" + old_scope["component"]
    current = env.inbox._assess("bears", Scope(**scope), dict(evidence=[], submissions=[]), env.now)
    assert current.remedy == remedy
    with sqlite3.connect(env.inbox.path) as db:
        db.execute("BEGIN IMMEDIATE")
        return reserve_claim(db, tenant="bears", vendor=scope["vendor"], account=scope["account"],
            agreement_id=current.agreement_id, agreement_version="historical-semantic-version", service=scope["service"],
            month=scope["month"], remedy=remedy, route="correspondence", case_id="old-delimiter-owner",
            packet_digest=fingerprint({"synthetic":"archived-old-writer-packet"}), scope=old_scope,
            receipt_id="legacy-original", at=env.now.isoformat())


def financial_rows(env):
    with sqlite3.connect(env.inbox.path) as db:
        return {table:db.execute("SELECT * FROM " + table + " ORDER BY 1,2").fetchall()
                for table in ("inbox_claim", "inbox_delivery", "claim_dispatch_identity_v2")}


def test_signed_historical_receipt_collision_rolls_back_before_delivery_or_claim_event(regional):
    seed_shadow(regional)
    saved = financial_rows(regional)
    response = regional.source("vendor-fixture", regional_original(), event_id="independent-history-shadow")
    assert response.status_code == 409 and "belongs" in response.text
    assert financial_rows(regional) == saved
    assert regional.read()["evidence"] == []


def test_aggregate_legacy_collision_refuses_local_submission_without_partial_writes(service):
    deliver(service, service_reports())
    service.action("approve-claim")
    seed_shadow(service, aggregate=True)
    saved = financial_rows(service)
    response = service.human.post(service.url + "/actions/submit-claim", {})
    assert response.status_code == 409 and "belongs" in response.text
    assert financial_rows(service) == saved
    assert service.read()["submissions"] == []


@pytest.mark.parametrize("fixture,aggregate", [("regional", False), ("service", True)])
def test_historical_shadow_also_refuses_new_draft_before_inbox_audit(request, fixture, aggregate):
    env = request.getfixturevalue(fixture)
    # Preserve the earlier valid scope but choose an otherwise separate draft
    # component, so the old draft-ID checks alone would not catch the collision.
    if not aggregate:
        with sqlite3.connect(env.inbox.path) as db:
            db.execute("DELETE FROM inbox_claim")  # Synthetic unfiled fixture, before seeding immutable history.
    else:
        env.scope["component"] = "another-service-label"
        env.provision()
    seed_shadow(env, aggregate=aggregate)
    saved = financial_rows(env)
    response = env.human.post("/api/correspondence/claims", dict(claim_id="inbox-new-shadow", scope=env.applicable_scope()))  # D04-C client
    # D04-C (2026-11-09): a whole-service claim has no component alias, so it collides earlier as the same obligation.
    assert response.status_code == 409 and ("obligation already exists" if aggregate else "already reserved") in response.text
    assert financial_rows(env) == saved


@pytest.mark.parametrize("resource", ["cell/", "/cell", "a//b"])
def test_ascii_delimiters_are_refused_at_edges(resource):
    with pytest.raises(ValueError, match="ambiguous"):
        resource_remedy(compiled(), OVERLAY | {"resource_id":resource})


def test_allowed_identity_domain_is_injective_and_nonregional_location_is_not_a_remedy():
    from itertools import product
    names = ["cell", "CELL", "café", "cafe\u0301", "a%2Fb", "cell\u2215North", "cell\uff0fNorth", "North"]
    seen = {}
    for resource, region in product(names, [None, *names]):
        manifest = compiled()
        overlay = OVERLAY | {"resource_id":resource, "subscription_record":{"region":region or "unused/location"}}
        if region is not None:
            manifest["subscription"] = {"scope":"account_product_region"}
        key = resource_remedy(manifest, overlay)
        assert key not in seen or seen[key] == (resource, region)
        seen[key] = (resource, region)
    assert resource_remedy(compiled(), OVERLAY | {"subscription_record":{"region":"unused/location"}}) == "resource-month/station-21"
    for resource, region in [("", None), ("cell", "")]:
        manifest = compiled() | ({"subscription":{"scope":"account_product_region"}} if region is not None else {})
        with pytest.raises(ValueError, match="nonempty"):
            resource_remedy(manifest, OVERLAY | {"resource_id":resource,"subscription_record":{"region":region}})


@pytest.mark.parametrize("resource", ["cell/North", "aggregate-service"])
def test_archived_ambiguous_evaluation_is_readable_without_inventing_a_portfolio_total(tmp_path, monkeypatch, resource):
    from uptime import claim_identity, vendor_terms
    from uptime.storage import case_versions
    from test_vendor_economic_identity import dispatch, resource_inputs
    env = App(tmp_path / "archived.db")
    env.now = datetime(2026, 7, 4, tzinfo=UTC)
    try:
        # Seed a content-bound historical artifact using exactly the prior
        # resource representation, without changing any stored evidence later.
        with monkeypatch.context() as historical:
            historical.setattr(claim_identity, "resource_remedy", lambda manifest, overlay: "resource-month/" + overlay["resource_id"])
            historical.setitem(vendor_terms.SEMANTICS_REVISIONS, "resource-month/1", "1" * 64)
            original = dispatch(env, tmp_path, historical, "old-resource", *resource_inputs(resource))
        safe = dispatch(env, tmp_path, monkeypatch, "current-resource", *resource_inputs("safe-cell"))
        path = env.app.state.bench.path
        versions = case_versions(path, "bears", original["id"])
        with sqlite3.connect(path) as db:
            archived = db.execute("SELECT * FROM v4_vendor_artifact").fetchall()
        view = env.client.get("/api/cases/" + original["id"], headers=env.human.headers)
        assert view.status_code == 200, view.text
        detail = view.json()
        assert detail["stage"] == detail["financial_scope_status"] == "REVIEW_REQUIRED"
        assert detail["amount"] is None and detail["recorded_amount"] == "12.51"
        assert detail["obligation_id"] is None and detail["actions"] == []
        dashboard = env.client.get("/api/dashboard", headers=env.human.headers)
        assert dashboard.status_code == 200, dashboard.text
        metrics = {m["key"]:m for m in dashboard.json()["cohorts"]["portfolio"]["metrics"]}
        assert metrics["estimated"]["amount"] is None
        assert metrics["estimated"]["financial_scope_status"] == "REVIEW_REQUIRED"
        contributions = {row["case_id"]:row for row in metrics["estimated"]["contributions"]}
        assert contributions[original["id"]]["recorded_amount"] == "12.51"
        assert contributions[original["id"]]["amount"] is None
        assert contributions[safe["id"]]["amount"] == "12.51"
        assert all(metrics[key]["amount"] == "0.00" for key in ("claimed", "awarded", "posted", "applied"))
        assert case_versions(path, "bears", original["id"]) == versions
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT * FROM v4_vendor_artifact").fetchall() == archived
    finally:
        env.client.close()


def test_identity_source_bytes_change_reviewed_evaluator_hash_in_fresh_process(tmp_path):
    import uptime
    from uptime.vendor_terms import semantics_revision
    package = Path(uptime.__file__).parent
    copy = tmp_path / "uptime"
    shutil.copytree(package, copy, ignore=shutil.ignore_patterns("__pycache__"))
    command = [sys.executable, "-c", "from uptime.vendor_terms import semantics_revision; print(semantics_revision({'family':'resource-month/1'}))"]
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    before = subprocess.check_output(command, cwd=tmp_path, env=environment, text=True).strip()
    assert before == semantics_revision(compiled())
    with (copy / "claim_identity.py").open("a") as stream:
        stream.write("\n# Synthetic deployment hash mutation control.\n")
    after = subprocess.check_output(command, cwd=tmp_path, env=environment, text=True).strip()
    assert after != before


def test_original_source_pin_and_reservation_survive_evaluator_deployment(regional, monkeypatch):
    from uptime.vendor_terms import SEMANTICS_REVISIONS
    before = regional.read()
    pins = {key:before[key] for key in ("contract_version", "contract_source_sha256")}
    receipt = regional_original() | pins
    result = regional.source("vendor-fixture", receipt, event_id="pinned-before-deployment")
    assert result.status_code == 200, result.text
    saved = financial_rows(regional)
    original = regional.read()["evidence"][0]
    monkeypatch.setitem(SEMANTICS_REVISIONS, "resource-month/1", "2" * 64)
    publication = regional.client.get("/api/vendors/altitude-service", headers=regional.human.headers).json()
    assert publication["state"] == "REVIEW_REQUIRED" and publication["active_version"] is None
    assert publication["actions"] == []
    after = regional.read()
    assert after["contract_version"] is None and after["actions"] == []
    assert after["evidence"][0] == original
    assert all(after["evidence"][0][key] == value for key, value in pins.items())
    assert financial_rows(regional) == saved
