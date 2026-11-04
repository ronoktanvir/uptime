"""Credential-free transport, grant, canonical capture, and mutation-boundary tests."""
import copy
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from hypothesis import given, strategies as st

from uptime.ramp import (ORIGIN, WRITE_SCOPES, RampError, RampHTTPError, SandboxRampProvider,
                         Token, capture, ramp_snapshot, sanitize_bill, seal_capture, scope_probe,
                         uuid_text, verify_draft, money)
from test_ramp import FakeProvider, token


@pytest.fixture
def draft_gate(monkeypatch):
    monkeypatch.setenv("RAMP_ENV", "sandbox")
    monkeypatch.setenv("RAMP_BASE_URL", ORIGIN)
    monkeypatch.setenv("RAMP_ENABLE_DRAFT_WRITE", "1")


def currency(amount):
    return {"amount": amount, "currency_code": "USD", "minor_unit_conversion_rate": 100}


def bill():
    return {"id": str(uuid4()), "vendor": {"id": str(uuid4()), "name": "PRIVATE NAME"},
            "entity_id": str(uuid4()), "status": "OPEN", "approval_status": "PENDING",
            "issued_at": "2026-10-31T12:00:00-07:00", "amount": currency(7500),
            "memo": "PRIVATE MEMO", "inventory_line_items": [{"id": str(uuid4()),
                "quantity": "2", "unit_price": currency(3750), "amount": currency(7500)}]}


class Reader:
    def __init__(self):
        self.scopes = []
        self.reads = []
        self.vendor = str(uuid4())
        self.bill = bill()
        self.bill["vendor"]["id"] = self.vendor

    def token(self, scopes):
        self.scopes.append(frozenset(scopes))
        return Token("PRIVATE_TOKEN", frozenset(scopes), frozenset(scopes))

    def request(self, tok, method, path, query=None):
        self.reads.append((method, path, query))
        assert method == "GET"
        if path == "vendors":
            rows = [{"id": self.vendor, "name": "PRIVATE NAME"}]
        elif path == "bills":
            rows = [self.bill]
        elif path == "vendors/credits":
            rows = []
        else:
            assert path == "bills/" + self.bill["id"]
            return copy.deepcopy(self.bill)
        return {"data": copy.deepcopy(rows), "page": {"next": None}}


def test_default_capture_is_read_only_and_sanitized():
    provider = Reader()
    proof = capture(provider)
    assert provider.scopes == [frozenset({"vendors:read"}), frozenset({"vendors:read"}), frozenset({"bills:read"})]
    assert proof["capabilities"]["draft_write"]["state"] == "NOT_REQUESTED"
    assert "PRIVATE" not in json.dumps(proof)
    row = proof["bills"][0]
    assert row["vendor_id"] == provider.vendor
    assert row["entity_id"] == provider.bill["entity_id"]
    assert row["account_id"] is None
    assert row["lines"][0]["quantity_rate_check"] == "MATCH"
    assert row["issued_at"] == "2026-10-31T19:00:00+00:00"


def test_token_only_probe_diagnoses_omission_without_records():
    class Grants:
        def token(self, scopes):
            return Token("SECRET", frozenset(scopes - {"bills:write"}), frozenset(scopes))
        def request(self, *args):
            pytest.fail("scope-only must not read records")
    proof = scope_probe(Grants(), include_write=True)
    assert len(proof["requests"]) == 4
    assert proof["requests"][2]["missing"] == ["bills:write"]
    assert proof["requests"][3]["granted"] == []
    assert proof["requests"][2]["diagnosis"] == "MISSING_GRANTS"
    assert proof["app_allowed_scopes"] == "NOT_OBSERVABLE_FROM_TOKEN_RESPONSE"
    assert "SECRET" not in json.dumps(proof)


@pytest.mark.parametrize(("grants", "reported", "diagnosis"), [
    ({"vendors:read", "vendors:write"}, True, "UNEXPECTED_GRANTS"),
    ({"bills:read"}, True, "MISSING_AND_UNEXPECTED_GRANTS"),
    (set(), False, "SCOPE_FIELD_ABSENT"),
])
def test_exact_scope_diagnosis(grants, reported, diagnosis):
    class Grants:
        def token(self, scopes): return Token("secret", frozenset(grants), frozenset(scopes), reported)
    assert scope_probe(Grants())["requests"][0]["diagnosis"] == diagnosis


@pytest.mark.parametrize(("status", "expected"), [(401, "AUTHENTICATION_REJECTED"), (403, "ACCESS_REJECTED"), (429, "HTTP_ERROR")])
def test_auth_failures_do_not_guess_app_config(status, expected):
    class Rejected:
        def token(self, scopes): raise RampHTTPError(status)
    proof = scope_probe(Rejected())
    assert all(r["state"] == expected and r["http_status"] == status for r in proof["requests"])
    assert proof["admin_configuration"] == "NOT_INSPECTED"


def test_missing_read_grants_perform_no_record_requests():
    provider = Reader()
    provider.token = lambda scopes: Token("unused", frozenset(), frozenset(scopes))
    proof = capture(provider)
    assert not provider.reads
    assert proof["capabilities"]["bills"]["missing"] == ["bills:read"]


@pytest.mark.parametrize("metadata", [None, [], {"scope": []}, {"scope": "bills:read", "access_token": "secret\nvalue", "token_type": "bearer"}])
def test_token_metadata_errors_are_sanitized(metadata):
    provider = SandboxRampProvider.__new__(SandboxRampProvider)
    provider._basic = "unused"
    provider._http = lambda *args: metadata
    with pytest.raises(RampError, match="Unexpected token metadata"):
        provider.token({"bills:read"})


class Paged(Reader):
    def __init__(self, next_url=None):
        super().__init__()
        self.next_url = next_url
    def request(self, tok, method, path, query=None):
        if path != "vendors":
            return super().request(tok, method, path, query)
        self.reads.append((method, path, query))
        ident = self.vendor if "start" not in query else str(uuid4())
        next_url = self.next_url or f"{ORIGIN}/developer/v1/vendors?page_size=2&start={ident}"
        return {"data": [{"id": ident}], "page": {"next": next_url}}


def test_pagination_has_hard_bounds_and_explicit_partial_status():
    provider = Paged()
    proof = capture(provider, page_size=2, max_pages=2)
    cap = proof["capabilities"]["vendors"]
    assert cap["pages_read"] == 2 and cap["has_next"] and not cap["list_complete"]
    assert len(proof["vendor_ids"]) == 2
    assert len([r for r in provider.reads if r[1] == "vendors"]) == 2


@pytest.mark.parametrize("suffix", [
    "https://attacker.example/developer/v1/vendors?start=x",
    "https://api.ramp.com/developer/v1/vendors?start=x",
    "https://demo-api.ramp.com@attacker.example/developer/v1/vendors?start=x",
    ORIGIN + "/developer/v1/bills?start=x",
    ORIGIN + "/developer/v1/vendors?start=x&start=y",
    ORIGIN + "/developer/v1/vendors?start=x&page_size=100",
    ORIGIN + "/developer/v1/vendors?start=x&token=secret",
    ORIGIN + "/developer/v1/vendors?start=x#fragment",
    ORIGIN + "/developer/v1/vendors?start=",
])
def test_untrusted_next_urls_never_followed(suffix):
    provider = Paged(suffix)
    proof = capture(provider, page_size=2, max_pages=2)
    assert proof["capabilities"]["vendors"]["state"] == "PROVIDER_ERROR"
    assert len([r for r in provider.reads if r[1] == "vendors"]) == 1
    assert "attacker" not in json.dumps(proof) and "secret" not in json.dumps(proof)


def test_repeated_cursor_rejected():
    provider = Paged(ORIGIN + "/developer/v1/vendors?page_size=2&start=fixed")
    proof = capture(provider, page_size=2, max_pages=5)
    assert proof["capabilities"]["vendors"]["state"] == "PROVIDER_ERROR"
    assert len([r for r in provider.reads if r[1] == "vendors"]) == 2


@pytest.mark.parametrize("bounds", [{"page_size": 101}, {"page_size": True}, {"max_pages": 0}, {"max_pages": 11}, {"detail_limit": 101}])
def test_bad_bounds_rejected_before_auth(bounds):
    p = Reader()
    with pytest.raises(RampError): capture(p, **bounds)
    assert not p.scopes


def test_detail_read_budget():
    p = Reader()
    original = p.request
    def request(tok, method, path, query=None):
        if path == "bills":
            return {"data": [p.bill, {**p.bill, "id": str(uuid4())}], "page": {"next": None}}
        return original(tok, method, path, query)
    p.request = request
    proof = capture(p, detail_limit=1)
    assert len(proof["bills"]) == 1
    assert proof["capabilities"]["bills"]["list_complete"]
    assert not proof["capabilities"]["bills"]["detail_complete"]


def test_checksum_age_and_tampering(tmp_path):
    proof = capture(Reader())
    path = tmp_path / "capture.json"
    path.write_text(json.dumps(proof))
    observed = datetime.fromisoformat(proof["observed_at"])
    fresh = ramp_snapshot(path, at=observed + timedelta(seconds=5))
    assert fresh["capture_status"]["usable_for_evaluation"]
    stale = ramp_snapshot(path, at=observed + timedelta(days=2))
    assert stale["capture_status"]["freshness"] == "STALE"
    assert not stale["capture_status"]["usable_for_evaluation"]
    assert "DETERMINISTIC_REPLAY" in stale["sources"]
    proof["bills"][0]["amount"]["amount"] = "1"
    path.write_text(json.dumps(proof))
    invalid = ramp_snapshot(path, at=observed)
    assert invalid["capture_status"]["integrity"] == "INVALID" and invalid["bills"] == []


def test_legacy_is_pinned_and_not_current_financial_input():
    proof = ramp_snapshot()
    assert proof["capture_status"]["legacy"]
    assert proof["capture_status"]["integrity"] == "ARCHIVE_CHECKSUM_VERIFIED"
    assert not proof["capture_status"]["usable_for_evaluation"]


def test_resealed_malformed_capture_and_future_are_unavailable(tmp_path):
    path = tmp_path / "capture"
    proof = capture(Reader())
    observed = datetime.fromisoformat(proof["observed_at"])
    path.write_text(json.dumps(proof))
    assert ramp_snapshot(path, at=observed - timedelta(seconds=1))["bills"] == []
    proof["bills"][0]["status"] = None
    path.write_text(json.dumps(seal_capture(proof)))
    assert ramp_snapshot(path)["bills"] == []


def test_failed_and_partial_capture_not_financial_input(tmp_path):
    for provider in (Paged(), Reader()):
        if isinstance(provider, Reader) and not isinstance(provider, Paged):
            provider.token = lambda scopes: Token("unused", frozenset(), frozenset(scopes))
        proof = capture(provider, page_size=2, max_pages=1)
        path = tmp_path / "capture"
        path.write_text(json.dumps(proof))
        assert not ramp_snapshot(path)["capture_status"]["usable_for_evaluation"]


@pytest.mark.parametrize("change", ["quantity", "rate", "currency", "missing"])
def test_quantity_rate_actually_checked(change):
    row = bill()
    line = row["inventory_line_items"][0]
    if change == "quantity": line["quantity"] = "3"
    if change == "rate": line["unit_price"]["amount"] = 3751
    if change == "currency": line["unit_price"]["currency_code"] = "EUR"
    if change == "missing": line.pop("quantity")
    expected = "UNAVAILABLE" if change == "missing" else "MISMATCH"
    assert sanitize_bill(row)["lines"][0]["quantity_rate_check"] == expected


def test_canonical_ids_duplicates_and_ledger_fields():
    row = bill()
    line = row["inventory_line_items"][0]
    line["accounting_field_selections"] = [{"id": "opaque-option-42", "name": "PRIVATE",
        "category_info": {"id": "opaque-category", "type": "GL_ACCOUNT", "name": "PRIVATE"}}]
    clean = sanitize_bill(row)
    assert clean["lines"][0]["accounting_field_selections"][0]["id"] == "opaque-option-42"
    assert "PRIVATE" not in json.dumps(clean)
    row["line_items"] = [copy.deepcopy(line)]
    with pytest.raises(RampError, match="Duplicate"): sanitize_bill(row)
    for value in (row["id"].upper(), row["id"] + " ", "{" + row["id"] + "}"):
        with pytest.raises(RampError): uuid_text(value)


@given(st.integers(min_value=0, max_value=10**12), st.integers(min_value=0, max_value=10**6))
def test_minor_units_quantity_arithmetic_property(minor, quantity):
    row = bill()
    row["inventory_line_items"][0].update(quantity=quantity, unit_price=currency(minor), amount=currency(minor * quantity))
    assert sanitize_bill(row)["lines"][0]["quantity_rate_check"] == "MATCH"
    assert Decimal(money(currency(minor))["amount"]) * 100 == minor


@pytest.mark.parametrize("quantity", [True, 1.0, "NaN", "Infinity", "-1", "1e99999", "1e-99999"])
def test_bad_quantity_rejected(quantity):
    row = bill()
    row["inventory_line_items"][0]["quantity"] = quantity
    with pytest.raises(RampError): sanitize_bill(row)


@pytest.mark.parametrize("missing", ["env", "authorization", "vendor"])
def test_draft_gates_precede_auth_or_journal(tmp_path, monkeypatch, draft_gate, missing):
    p = Reader()
    if missing == "env": monkeypatch.delenv("RAMP_ENABLE_DRAFT_WRITE")
    with pytest.raises(RampError):
        capture(p, write=True, journal=tmp_path / "ops", authorize_draft=missing != "authorization",
                designated_vendor_id=None if missing == "vendor" else p.vendor)
    assert not p.scopes and not (tmp_path / "ops").exists()


def test_arbitrary_vendor_not_selected(tmp_path, draft_gate):
    p = Reader()
    with pytest.raises(RampError, match="Designated vendor not found"):
        capture(p, write=True, journal=tmp_path / "ops", authorize_draft=True, designated_vendor_id=str(uuid4()))
    assert all("bills:write" not in s for s in p.scopes)


@pytest.mark.parametrize("corruption", ["quantity", "unit_price", "sync_status"])
def test_draft_same_total_wrong_line_or_sync_never_patched(tmp_path, draft_gate, corruption):
    class Wrong(FakeProvider):
        def request(self, *args):
            row = copy.deepcopy(super().request(*args))
            if corruption == "quantity": row["inventory_line_items"][0]["quantity"] = "1001"
            elif corruption == "unit_price": row["inventory_line_items"][0]["unit_price"]["amount"] = 3751
            else: row["sync_status"] = "BILL_SYNCED"
            return row
    p = Wrong()
    with pytest.raises(RampError):
        verify_draft(p, token(), tmp_path / "ops", str(uuid4()), authorized=True)
    assert p.posts == 1 and p.patches == 0


def test_private_journal_and_foreign_vendor(tmp_path, draft_gate):
    p, vendor = FakeProvider(), str(uuid4())
    journal = tmp_path / "ops"
    verify_draft(p, token(), journal, vendor, authorized=True)
    assert journal.stat().st_mode & 0o077 == 0
    with pytest.raises(RampError, match="vendor mismatch"):
        verify_draft(p, token(), journal, str(uuid4()), authorized=True)
    assert p.posts == 1 and p.patches == 1
    link = tmp_path / "link"
    link.symlink_to(journal)
    with pytest.raises(RampError, match="Private regular"):
        verify_draft(p, token(), link, vendor, authorized=True)


def cli():
    spec = importlib.util.spec_from_file_location("ramp_probe", Path(__file__).parents[1] / "scripts/ramp_probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_cli_and_scope_probe(tmp_path, monkeypatch, capsys):
    module = cli()
    provider = Reader()
    monkeypatch.setattr(module, "SandboxRampProvider", lambda: provider)
    output = tmp_path / "proof.json"
    assert module.main(["--output", str(output)]) == 0
    assert "checksum_sha256" in json.loads(output.read_text())
    provider.reads.clear()
    assert module.main(["--scope-only", "--include-write-scope"]) == 0
    assert not provider.reads
    assert "PRIVATE_TOKEN" not in capsys.readouterr().out


def test_cli_write_disabled_never_opens_credentials(monkeypatch):
    module = cli()
    def forbidden(): pytest.fail("credential constructor must not run")
    monkeypatch.setattr(module, "SandboxRampProvider", forbidden)
    monkeypatch.delenv("RAMP_ENABLE_DRAFT_WRITE", raising=False)
    assert module.main(["--verify-draft"]) == 1


def test_cli_missing_grants_returns_failure_with_safe_proof(monkeypatch, capsys):
    module = cli()
    p = Reader()
    p.token = lambda scopes: Token("SECRET", frozenset(), frozenset(scopes))
    monkeypatch.setattr(module, "SandboxRampProvider", lambda: p)
    assert module.main(["--scope-only"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["requests"][0]["missing"] == ["vendors:read"]


def test_draft_same_total_and_product_but_wrong_quantity_blocked(tmp_path, draft_gate):
    class Wrong(FakeProvider):
        def request(self, *args):
            row = copy.deepcopy(super().request(*args))
            row["inventory_line_items"][0]["quantity"] = "500"
            row["inventory_line_items"][0]["unit_price"]["amount"] = 7500
            return row
    p = Wrong()
    with pytest.raises(RampError, match="quantity, unit price"):
        verify_draft(p, token(), tmp_path / "ops", str(uuid4()), authorized=True)
    assert p.posts == 1 and p.patches == 0


def test_ordinary_bill_requires_provider_identity():
    for field in ("vendor", "entity_id"):
        row = bill()
        row.pop(field)
        with pytest.raises(RampError, match="identity required"):
            sanitize_bill(row)


def test_mutation_transport_rejects_payment_payload(draft_gate):
    provider = SandboxRampProvider.__new__(SandboxRampProvider)
    provider._http = lambda *args: pytest.fail("No network mutation should occur")
    with pytest.raises(RampError):
        provider._draft_mutation(token(), str(uuid4()), {"payment_method": "ACH"}, authorized=True)
    with pytest.raises(RampError):
        provider._draft_mutation(token(), None, {"vendor_id": str(uuid4()), "payment_details": {}}, authorized=True)
