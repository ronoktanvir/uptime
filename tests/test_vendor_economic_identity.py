"""Contract cardinality through signed intake, activation, evaluation and dashboard.

All documents and observations are explicitly synthetic committed fixtures.
These controls cover portfolio arithmetic and alias deduplication together.
"""
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
import socket

import pytest

from uptime.claim_identity import claim_key, resource_remedy, vendor_economic_identity
from uptime.storage import case_versions, database, save_cases
from test_correspondence_resource import install, reports
from test_v4_routes_integration import App
from test_vendor_resource import FACTS, OVERLAY, compiled
from test_vendor_resource_scoped import ROW, subscription, facts as regional_facts


@pytest.fixture
def env(tmp_path, monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Synthetic economic identity tests cannot contact a provider")
    monkeypatch.setattr(socket.socket, "connect", deny)
    app = App(tmp_path / "economic.sqlite", extra_roles={"custody-fixture":"customer"})
    app.now = datetime(2026, 7, 4, tzinfo=UTC)
    yield app
    app.client.close()


def resource_inputs(resource, cents=10004):
    overlay, facts = deepcopy(OVERLAY), deepcopy(FACTS)
    overlay["resource_id"] = facts["resource_id"] = resource
    for group in ("intervals", "exclusions", "fee_lines"):
        for row in facts[group]:
            if row["resource_id"] == OVERLAY["resource_id"]:
                row["resource_id"] = resource
                if row.get("kind") == "resource_service":
                    row["amount_cents"] = cents
    facts["filing_proof"]["resource_id"] = resource
    facts["filing_proof"]["fields"]["station identifier"] = resource
    return overlay, facts


def dispatch(env, tmp_path, monkeypatch, slot, overlay, facts, expected="12.51", extra_terms=()):
    install(env, tmp_path, monkeypatch, installation=slot, overlay_override=overlay,
            shadow=facts, expected=expected, extra_terms=extra_terms)
    return env.post(f"/api/vendors/{slot}/evaluate", {"facts":facts})


def metric(env, key="estimated"):
    response = env.client.get("/api/dashboard", headers=env.human.headers)
    assert response.status_code == 200, response.text
    return next(m for m in response.json()["cohorts"]["portfolio"]["metrics"] if m["key"] == key)


@pytest.mark.parametrize(("second_fee", "second_credit", "total"), [(10004, "12.51", "25.02"), (20008, "25.01", "37.52")])
def test_separate_resources_add_with_original_fee_basis(env, tmp_path, monkeypatch, second_fee, second_credit, total):
    first = dispatch(env, tmp_path, monkeypatch, "resource-first", *resource_inputs("station-A"))
    second = dispatch(env, tmp_path, monkeypatch, "resource-second", *resource_inputs("station-B", second_fee), expected=second_credit)
    assert first["affected_fee_cents"] == 10004 and second["affected_fee_cents"] == second_fee
    assert first["id"] != second["id"] and first["obligation_id"] != second["obligation_id"]
    result = metric(env)
    assert result["amount"] == total
    assert {c["obligation_id"] for c in result["contributions"]} == {first["obligation_id"], second["obligation_id"]}
    assert sum(Decimal(c["amount"]) for c in result["contributions"]) == Decimal(total)


@pytest.mark.parametrize(("alias_fee", "alias_credit", "total"), [(10004, "12.51", "12.51"), (20008, "25.01", None)])
def test_installation_aliases_cannot_duplicate_or_silently_choose_entitlement(env, tmp_path, monkeypatch, alias_fee, alias_credit, total):
    original = dispatch(env, tmp_path, monkeypatch, "original", *resource_inputs("same-station"))
    alias = dispatch(env, tmp_path, monkeypatch, "alias", *resource_inputs("same-station", alias_fee), expected=alias_credit)
    assert original["id"] != alias["id"]
    assert original["obligation_id"] == alias["obligation_id"]
    result = metric(env)
    assert len(result["contributions"]) == 2 and result["amount"] == total
    if total is None:
        assert result["value"] == "Not additive"


def test_reissued_version_and_historical_snapshots_keep_economic_identity(env, tmp_path, monkeypatch):
    overlay, facts = resource_inputs("stable-station")
    original = dispatch(env, tmp_path, monkeypatch, "stable", overlay, facts)
    # Emulate a pre-correction persisted snapshot, whose key included its slot.
    historical = deepcopy(original)
    historical.pop("economic_identity")
    historical["obligation_id"] = "legacy-installation-obligation"
    path = env.app.state.bench.path
    save_cases(path, "bears", [historical])
    assert metric(env)["contributions"][0]["obligation_id"] == original["obligation_id"]
    versions = case_versions(path, "bears", original["id"])
    assert versions[-1]["payload"] == historical
    assert metric(env)["contributions"][0]["obligation_id"] == original["obligation_id"]
    assert case_versions(path, "bears", original["id"]) == versions
    renewed = dispatch(env, tmp_path, monkeypatch, "stable", overlay | {"effective_until":"2028-12-31"}, facts)
    assert renewed["version"] != original["version"]
    assert renewed["id"] == original["id"] and renewed["obligation_id"] == original["obligation_id"]
    assert metric(env)["amount"] == "12.51"
    # Reading archived scope never rewrites the earlier receipt or version.
    assert case_versions(path, "bears", original["id"])[1]["payload"] == historical


def replace_region(value, region):
    if isinstance(value, dict):
        return {k:region if k == "region" else replace_region(v, region) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_region(v, region) for v in value]
    return value


def test_separately_signed_regions_contribute_for_the_same_resource(env, tmp_path, monkeypatch):
    cases = []
    for region in ("North", "South"):
        data = replace_region(regional_facts(), region)
        overlay = replace_region(subscription(), region)
        case = dispatch(env, tmp_path, monkeypatch, "regional-" + region.lower(), overlay, data,
                        expected="15.03", extra_terms=ROW)
        assert case["affected_fee_cents"] == 12020
        cases.append(case)
    assert cases[0]["obligation_id"] != cases[1]["obligation_id"]
    assert metric(env)["amount"] == "30.06"


def test_measurement_scope_preserves_whole_service_and_excludes_version_alias():
    manifest = compiled()
    first = vendor_economic_identity("bears", manifest, OVERLAY, "2026-06", "version-1")
    assert claim_key(**first) == claim_key(**(first | {"agreement_version":"version-2", "vendor":manifest["vendor"].upper()}))
    assert resource_remedy({"family":"monthly-availability/1"}, OVERLAY) == "availability"
    aggregate = manifest | {"aggregate_monitor":"authoritative_vendor_minutes"}
    assert resource_remedy(aggregate, OVERLAY) == "resource-month/aggregate-service"
    assert resource_remedy(aggregate, OVERLAY | {"resource_id":"other-resource"}) == resource_remedy(aggregate, OVERLAY)


def test_evaluation_and_claim_views_share_one_obligation_before_and_after_filing(env, tmp_path, monkeypatch):
    import json

    expected_keys = set()
    for resource in ("station-21", "station-22"):
        estimate = dispatch(env, tmp_path, monkeypatch, resource, *resource_inputs(resource))
        env.id = "inbox-" + resource
        env.url = "/api/correspondence/claims/" + env.id
        env.scope.update(vendor="Copper Mesa Networks", account=OVERLAY["account"], contract=OVERLAY["agreement"],
                         service=OVERLAY["product"], component=resource, month="2026-06")
        env.provision()
        env.create()
        # Every exact resource reference in the synthetic signed source is rebound.
        rows = json.loads(json.dumps(reports()).replace('"station-21"', json.dumps(resource)))
        for source, body in rows:
            delivered = env.source(source, body, event_id=env.id + "-" + body["kind"])
            assert delivered.status_code == 200, delivered.text
        claim = env.read()
        assert claim["amount"] == "12.51" and claim["obligation_id"] == estimate["obligation_id"]
        expected_keys.add(estimate["obligation_id"])
        assert metric(env)["amount"] == ("12.51" if len(expected_keys) == 1 else "25.02")
        env.action("approve-claim")
        filed = env.action("submit-claim")
        submitted = filed["submissions"][0]
        assert filed["obligation_id"] == estimate["obligation_id"]
        with database(env.app.state.bench.path) as db:
            reservation = db.execute("SELECT obligation FROM claim_dispatch_identity_v2 WHERE receipt_id=?",
                                     (submitted["id"],)).fetchone()
        assert reservation["obligation"] == estimate["obligation_id"]
    result = metric(env)
    assert len(result["contributions"]) == 4
    assert {row["obligation_id"] for row in result["contributions"]} == expected_keys
    assert result["amount"] == metric(env, "claimed")["amount"] == "25.02"
    assert metric(env, "awarded")["amount"] == "0.00"
    assert metric(env, "posted")["amount"] == metric(env, "applied")["amount"] == "0.00"
