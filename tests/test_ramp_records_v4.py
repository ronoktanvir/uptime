"""Entirely synthetic Ramp records and injected transport; never read credentials or captures."""
import copy
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest

from uptime.ramp import (NATIVE_READ_SCOPES, ORIGIN, RampError, RampHTTPError,
                         SandboxRampProvider, Token, WORKFLOW_SCOPES)
from uptime.ramp_records import (SCHEMA, _validate_snapshot, load_snapshot, native_ui_url,
    sanitize_approval, sanitize_bill, sanitize_credit, sanitize_purchase_order,
    sanitize_transaction, seal_snapshot, scope_probe, sync_records)


def uid(n):
    return str(UUID(int=n))


BILL, DRAFT, VENDOR, ENTITY, TRANSACTION, AGREEMENT, PO, CREDIT, LINE = [uid(i) for i in range(1, 10)]
DATE = "2026-01-01T00:00:00+00:00"


def money(n=100, currency="USD", scale=100):
    return {"amount": n, "currency_code": currency, "minor_unit_conversion_rate": scale}


def page(rows, next_url=None):
    return {"data": copy.deepcopy(rows), "page": {"next": next_url}}


class Reader:
    def __init__(self, linked=False):
        self.calls, self.scopes = [], []
        self.rows = {
            "bills": [{"id": BILL, "vendor": {"id": VENDOR, "name": "Example Hosting Co"}, "entity_id": ENTITY,
                       "status": "OPEN", "approval_status": "PENDING", "amount": money(), "issued_at": DATE,
                       "deep_link_url": None, "purchase_order_id": PO if linked else None,
                       "applied_vendor_credits": [], "line_items": [], "inventory_line_items": [
                           {"id": LINE, "quantity": Decimal("2.5"), "unit_price": money(40), "amount": money(),
                            "memo": "PRIVATE"}], "memo": "PRIVATE", "invoice_urls": ["https://private.invalid"]}],
            "bills/drafts": [{"id": DRAFT, "status": "DRAFT", "vendor": None, "entity_id": None}],
            "vendors": [{"id": VENDOR, "approval_status": "PENDING", "is_active": True,
                         "name": "Example Hosting Co", "display_name": "PRIVATE", "contacts": ["PRIVATE"]}],
            "transactions": [{"id": TRANSACTION, "entity_id": ENTITY, "state": "PENDING", "merchant_id": uid(22),
                              "entity_amount": {"value": -100, "currency": "USD"}, "minor_unit_conversion_rate": 100,
                              "merchant_amount": {"value": -120, "currency": "EUR"}, "user_transaction_time": DATE,
                              "merchant_name": "PRIVATE"}],
            "vendors/agreements": [],
            "vendors/credits": [],
            "purchase-orders": [{"id": PO, "vendor_id": VENDOR, "entity_id": ENTITY, "amount": money(900),
                                "bill_ids": [BILL] if linked else [], "billing_status": "OPEN",
                                "ramp_url": "https://demo.ramp.com/s/procurement/purchase-orders/" + PO,
                                "name": "PRIVATE", "line_items": [{"id": uid(77), "quantity": 3,
                                "unit_price": money(300), "amount": money(900), "start_date": "2026-01-01"}]}],
        }
        self.overrides = {}

    def token(self, scopes):
        self.scopes.append(frozenset(scopes))
        return Token("PRIVATE_TOKEN", frozenset(scopes), frozenset(scopes))

    def request(self, token, method, path, query=None, data=None):
        assert token.exact
        assert method == "GET" or (method, path) == ("POST", "vendors/agreements")
        self.calls.append((method, path, copy.deepcopy(query), copy.deepcopy(data)))
        if path in self.overrides:
            value = self.overrides[path]
            if isinstance(value, Exception):
                raise value
            return copy.deepcopy(value)
        if path == "vendors/agreements":
            assert method == "POST" and query is None and set(data) <= {"page_size", "start"}
        if path in self.rows:
            return page(self.rows[path])
        if path == "approvals":
            ident = query["entity_ids"][0]
            kind = query["entity_type"].lower()
            return page([{"entity_id": ident, "entity_type": kind, "status": "PENDING",
                          "approval_history": [{"action_at": DATE, "step_status": "not applicable", "user_email": "PRIVATE"}],
                          "next_approvers": [{"user_id": uid(23), "user_email": "PRIVATE"}]}])
        if path.startswith("comments/"):
            return page([{"id": "opaque-comment-1", "created_at": DATE, "message": "PRIVATE", "user_id": uid(23)}])
        prefix, ident = path.rsplit("/", 1)
        return copy.deepcopy(next(r for r in self.rows[prefix] if r["id"] == ident))


def test_default_legacy_off_and_full_snapshot():
    reader = Reader()
    snapshot = sync_records(reader)
    _validate_snapshot(snapshot)
    assert snapshot["schema"] == SCHEMA
    assert len(reader.scopes) == 5 and all(len(s) == 1 for s in reader.scopes)
    assert set().union(*reader.scopes) == NATIVE_READ_SCOPES
    assert "PRIVATE" not in json.dumps(snapshot)
    resources = snapshot["resources"]
    assert resources["purchase_orders"]["status"] == "NOT_REQUESTED"
    assert not any(path.startswith("purchase-orders") for _, path, _, _ in reader.calls)
    assert resources["agreements"]["status"] == resources["credits"]["status"] == "EMPTY"
    bill = resources["bills"]["records"][0]
    assert bill["vendor_id"] == VENDOR and bill["deep_link_url"] is None
    # Display names are retained only in their own fields; memos, contacts and URLs never are.
    assert bill["vendor_name"] == "Example Hosting Co" and bill["invoice_number"] is None
    assert resources["vendors"]["records"][0]["name"] == "Example Hosting Co"
    assert bill["lines"][0]["quantity"] == "2.5" and bill["lines"][0]["quantity_rate_check"] == "MATCH"
    assert bill["lines"][0]["amount"]["amount_minor"] == 100
    assert resources["transactions"]["records"][0]["vendor_id"] is None
    assert resources["transactions"]["records"][0]["amount"]["amount"] == "-1"
    assert len(resources["approvals"]["records"]) == 2
    assert resources["approvals"]["status"] == "COMPLETE"
    assert all(r["id_kind"] == "parent_resource" for r in resources["approvals"]["records"])
    assert len(resources["comments"]["records"]) == 2


def test_opt_in_independent_pos_do_not_infer_bill_link_from_vendor():
    reader = Reader()
    snap = sync_records(reader, include_unlinked_purchase_orders=True)
    _validate_snapshot(snap)
    po = snap["resources"]["purchase_orders"]["records"][0]
    assert po["vendor_id"] == VENDOR and po["reciprocal_bill_ids"] == []
    assert po["discovery"] == ["INDEPENDENT_POs"]
    assert snap["resources"]["bills"]["records"][0]["purchase_order_id"] is None
    cov = snap["resources"]["purchase_orders"]["coverage"]["INDEPENDENT_POs"]
    assert cov["listed"] == cov["details_read"] == 1 and cov["status"] == "COMPLETE"
    assert po["ramp_url"].endswith(PO) and po["lines"][0]["quantity"] == "3"


@pytest.mark.parametrize("reciprocal", [True, False])
def test_linked_pos_require_reciprocal_native_ids_and_detail_deduplication(reciprocal):
    reader = Reader(linked=True)
    if not reciprocal:
        reader.rows["purchase-orders"][0]["bill_ids"] = []
    snap = sync_records(reader, include_unlinked_purchase_orders=True)
    _validate_snapshot(snap)
    po = snap["resources"]["purchase_orders"]["records"][0]
    assert po["reciprocal_bill_ids"] == ([BILL] if reciprocal else [])
    assert po["discovery"] == ["LINKED", "INDEPENDENT_POs"]
    assert len([c for c in reader.calls if c[1] == "purchase-orders/" + PO]) == 1


def test_default_still_follows_linked_po_without_list():
    reader = Reader(linked=True)
    snap = sync_records(reader)
    _validate_snapshot(snap)
    assert snap["resources"]["purchase_orders"]["records"][0]["reciprocal_bill_ids"] == [BILL]
    assert not any(c[1] == "purchase-orders" for c in reader.calls)


def test_agreement_query_and_documented_payee_uuid_and_linked_po():
    reader = Reader()
    reader.rows["vendors/agreements"] = [{"id": AGREEMENT, "payee_id": VENDOR, "name": "PRIVATE"}]
    reader.overrides["vendors/agreements/" + AGREEMENT] = {"id": AGREEMENT, "payee": {"uuid": VENDOR, "name": "PRIVATE"},
        "currency": "USD", "total_value": money(900), "start_date": "2026-01-01", "end_date": "2027-01-01",
        "purchase_orders": [{"id": PO, "documents": [{"url": "PRIVATE"}]}], "line_items": [{"secret": "PRIVATE"}]}
    snap = sync_records(reader)
    _validate_snapshot(snap)
    agreement = snap["resources"]["agreements"]["records"][0]
    assert agreement["vendor_id"] == VENDOR and agreement["purchase_order_ids"] == [PO]
    assert agreement["lines"] is None and "PRIVATE" not in json.dumps(snap)
    assert snap["resources"]["purchase_orders"]["records"][0]["reciprocal_bill_ids"] == []
    assert ("POST", "vendors/agreements", None, {"page_size": 10}) in reader.calls


def test_credit_shapes_compatible_with_recovered_projection():
    reader = Reader()
    reader.rows["vendors/credits"] = [{"id": CREDIT, "vendor_id": VENDOR, "entity_id": ENTITY,
        "reference_bill_id": BILL, "accounting_date": "2026-01-01", "total_amount": money(100),
        "remaining_amount": money(60), "total_applied_amount": money(40),
        "applied_bills": [{"bill_id": BILL, "amount": money(40)}], "applied_draft_bills": [],
        "inventory_line_items": [{"unit_quantity": Decimal("2.5"), "unit_price": money(40), "amount": money(100), "memo": "PRIVATE"}]}]
    snap = sync_records(reader)
    _validate_snapshot(snap)
    row = snap["resources"]["credits"]["records"][0]
    assert row["total_applied"]["amount_minor"] == 40 and row["applied_bills"][0]["bill_id"] == BILL
    assert row["applied_drafts"] == [] and row["lines"][0]["id"] is None
    assert row["lines"][0]["quantity"] == "2.5"
    assert any(c[1] == "vendors/credits/" + CREDIT for c in reader.calls)


@pytest.mark.parametrize("state", ["PENDING", "INITIALIZED", "APPROVED", "TERMINATED", "REJECTED"])
def test_approval_schema_parent_identity_and_all_published_states(state):
    raw = {"entity_id": BILL, "entity_type": "bill", "status": state,
           "approval_history": [], "next_approvers": []}
    result = sanitize_approval(raw, "bill", BILL)
    assert result["id"] == BILL and result["status"] == state
    assert result["id_kind"] == "parent_resource"
    with pytest.raises(RampError):
        sanitize_approval(raw, "transaction", BILL)
    with pytest.raises(RampError):
        sanitize_approval(raw, "bill", uid(99))


@pytest.mark.parametrize("response,expected", [(page([]), "EMPTY"), (RampHTTPError(403), "FORBIDDEN"),
    (RampHTTPError(400), "UNAVAILABLE"), ({"data": [], "page": {}}, "UNAVAILABLE")])
def test_approval_empty_nonapplicability_and_failed_parents_distinct(response, expected):
    reader = Reader()
    reader.overrides["approvals"] = response
    snap = sync_records(reader)
    _validate_snapshot(snap)
    assert snap["resources"]["approvals"]["status"] == expected
    assert snap["resources"]["approvals"]["complete"] is (expected == "EMPTY")


@pytest.mark.parametrize("granted,reported", [(set(), True), ({"bills:read", "bills:write"}, True), ({"bills:read"}, False)])
def test_exact_scopes_no_silent_fallback(granted, reported):
    reader = Reader()
    def token(scopes):
        return Token("PRIVATE", frozenset(granted), frozenset(scopes), reported)
    reader.token = token
    snap = sync_records(reader, include_unlinked_purchase_orders=True)
    _validate_snapshot(snap)
    assert not reader.calls
    assert all(r["status"] == "UNAVAILABLE" for r in snap["resources"].values())


def test_token_request_metadata_cannot_substitute_different_scope():
    reader = Reader()
    reader.token = lambda scopes: Token("PRIVATE", frozenset({"vendors:read"}), frozenset({"vendors:read"}))
    snap = sync_records(reader)
    assert snap["resources"]["bills"]["status"] == "UNAVAILABLE"
    assert all(c[1].startswith("vendors") for c in reader.calls)


def test_scope_only_does_not_read_or_write():
    reader = Reader()
    proof = scope_probe(reader)
    assert not reader.calls and len(proof["requests"]) == 5
    assert "PRIVATE_TOKEN" not in json.dumps(proof)
    assert not proof["writes_attempted"]


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_resource_http_failure_preserves_exact_status(status):
    reader = Reader()
    reader.overrides["purchase-orders"] = RampHTTPError(status)
    snap = sync_records(reader, include_unlinked_purchase_orders=True)
    _validate_snapshot(snap)
    po = snap["resources"]["purchase_orders"]
    assert po["status"] == ("FORBIDDEN" if status == 403 else "UNAVAILABLE")
    assert po["issues"][0]["http_status"] == status and not po["complete"]


def test_bounded_list_and_detail_have_separate_coverage():
    reader = Reader()
    rows = [dict(reader.rows["purchase-orders"][0], id=uid(100+i)) for i in range(2)]
    reader.rows["purchase-orders"] = rows
    reader.overrides["purchase-orders"] = page(rows, ORIGIN + "/developer/v1/purchase-orders?start=next&page_size=2")
    snap = sync_records(reader, page_size=2, detail_limit=1, include_unlinked_purchase_orders=True)
    _validate_snapshot(snap)
    po = snap["resources"]["purchase_orders"]
    assert po["status"] == "TRUNCATED" and len(po["records"]) == 1
    cov = po["coverage"]["INDEPENDENT_POs"]
    assert cov["pages_read"] == cov["details_attempted"] == 1 and not cov["list_complete"] and not cov["detail_complete"]


@pytest.mark.parametrize("next_url", ["https://api.ramp.com/developer/v1/purchase-orders?start=x",
    ORIGIN + "/developer/v1/bills?start=x", ORIGIN + "/developer/v1/purchase-orders?start=x&token=PRIVATE",
    ORIGIN + "/developer/v1/purchase-orders?start=x&start=y", ORIGIN + "/developer/v1/purchase-orders?start=x#",
    ORIGIN + "/developer/v1/purchase-orders?start=x&page_size=100"])
def test_unsafe_next_never_followed_or_saved(next_url):
    reader = Reader()
    reader.overrides["purchase-orders"] = page(reader.rows["purchase-orders"], next_url)
    snap = sync_records(reader, page_size=2, max_pages=2, include_unlinked_purchase_orders=True)
    _validate_snapshot(snap)
    assert len([c for c in reader.calls if c[1] == "purchase-orders"]) == 1
    assert snap["resources"]["purchase_orders"]["status"] == "PARTIAL"
    assert "PRIVATE" not in json.dumps(snap)


def test_repeated_cursor_cannot_loop():
    reader = Reader()
    reader.overrides["purchase-orders"] = page([], ORIGIN + "/developer/v1/purchase-orders?start=x")
    snap = sync_records(reader, max_pages=10, include_unlinked_purchase_orders=True)
    assert len([c for c in reader.calls if c[1] == "purchase-orders"]) == 2
    assert snap["resources"]["purchase_orders"]["status"] == "UNAVAILABLE"


def test_detail_identity_mismatch_not_list_fallback():
    reader = Reader()
    reader.overrides["purchase-orders/" + PO] = dict(reader.rows["purchase-orders"][0], id=uid(999))
    snap = sync_records(reader, include_unlinked_purchase_orders=True)
    assert not snap["resources"]["purchase_orders"]["records"]
    assert snap["resources"]["purchase_orders"]["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("suffix", ["?token=PRIVATE", "?", "#section", "#", "/", "/../" + PO, "%3F"])
def test_native_ui_links_no_query_fragment_or_noncanonical_path(suffix):
    url = "https://demo.ramp.com/s/procurement/purchase-orders/" + PO
    assert native_ui_url(url + suffix, PO, "purchase_order") is None


@pytest.mark.parametrize("origin", ["http://demo.ramp.com", "https://demo.ramp.com:443", "https://demo.ramp.com.evil",
    "https://user:PRIVATE@demo.ramp.com", "https://app.ramp.com", "https://DEMO.ramp.com"])
def test_native_ui_links_exact_sandbox_origin(origin):
    assert native_ui_url(origin + "/s/procurement/purchase-orders/" + PO, PO, "purchase_order") is None


def test_native_links_provider_values_only_and_same_object():
    row = Reader().rows["bills"][0]
    assert sanitize_bill(row)["deep_link_url"] is None
    url = "https://demo.ramp.com/bill-pay/bills/" + BILL
    row["deep_link_url"] = url
    assert sanitize_bill(row)["deep_link_url"] == url
    row["deep_link_url"] = url.replace(BILL, uid(999))
    assert sanitize_bill(row)["deep_link_url"] is None
    assert native_ui_url("https://demo.ramp.com/s/procurement/purchase-orders/" + PO, BILL, "bill") is None


def test_published_nullable_scale_never_guessed():
    row = Reader().rows["bills"][0]
    row["amount"]["minor_unit_conversion_rate"] = None
    result = sanitize_bill(row)
    assert result["amount"] == {"amount": None, "amount_minor": 100, "currency": "USD", "minor_unit_conversion_rate": None}
    reader = Reader()
    reader.rows["bills"] = [row]
    _validate_snapshot(sync_records(reader))


@pytest.mark.parametrize("bounds", [{"detail_limit": 101}, {"page_size": True}, {"max_pages": 0},
    {"include_unlinked_purchase_orders": "true"}])
def test_bounds_before_tokens(bounds):
    reader = Reader()
    with pytest.raises(RampError):
        sync_records(reader, **bounds)
    assert not reader.scopes and not reader.calls


def sdk():
    provider = SandboxRampProvider.__new__(SandboxRampProvider)
    calls = []
    provider._http = lambda *args: calls.append(args) or {}
    return provider, calls


def token(scope):
    return Token("PRIVATE", frozenset({scope}), frozenset({scope}))


@pytest.mark.parametrize("method,path,scope,query,data", [
    ("POST", "vendors/agreements", "vendors:read", None, {"page_size": 2}),
    ("GET", "vendors/" + VENDOR, "vendors:read", None, None),
    ("GET", "purchase-orders", "purchase_orders:read", {"page_size": 2}, None),
    ("GET", "purchase-orders/" + PO, "purchase_orders:read", None, None),
    ("GET", "transactions/" + TRANSACTION, "transactions:read", None, None),
    ("GET", "approvals", "approvals:read", {"page_size": 2, "entity_type": "BILL", "entity_ids": [BILL]}, None),
    ("GET", "comments/bills/" + BILL, "bills:read", {"page_size": 2}, None),
])
def test_sdk_exact_read_surfaces(method, path, scope, query, data):
    provider, calls = sdk()
    provider.request(token(scope), method, path, query, data)
    assert len(calls) == 1 and calls[0][0] == method
    if path == "approvals":
        assert "entity_ids=" + BILL in calls[0][1] and "%5B" not in calls[0][1]
    if method == "POST":
        assert json.loads(calls[0][3]) == {"page_size": 2}


@pytest.mark.parametrize("method,path,scope,query,data", [
    ("POST", "bills", "bills:read", None, {}), ("PATCH", "bills/" + BILL, "bills:read", None, {}),
    ("DELETE", "vendors/" + VENDOR, "vendors:read", None, None),
    ("GET", "vendors/" + VENDOR + "/accounts", "vendors:read", None, None),
    ("GET", "purchase-orders", "bills:read", None, None),
    ("POST", "vendors/agreements", "vendors:read", None, {"page_size": 2, "name": "PRIVATE"}),
    ("POST", "vendors/agreements", "vendors:read", {}, {"page_size": 2}),
    ("GET", "bills?secret=PRIVATE", "bills:read", None, None),
    ("GET", "bills/" + BILL, "bills:read", {"page_size": 2}, None),
    ("GET", "approvals", "approvals:read", {"entity_type": "bill", "entity_ids": [BILL]}, None),
    ("GET", "bills", "bills:read", {"start": "x&PRIVATE"}, None),
    ("GET", "comments/spend-requests/" + BILL, "bills:read", None, None),
])
def test_sdk_rejects_other_routes_filters_and_writes_before_transport(method, path, scope, query, data):
    provider, calls = sdk()
    with pytest.raises(RampError):
        provider.request(token(scope), method, path, query, data)
    assert not calls


def test_sdk_token_scope_allowlist_shared_with_workflow():
    provider, calls = sdk()
    provider._basic = "unused"
    for scope in NATIVE_READ_SCOPES | WORKFLOW_SCOPES:
        provider._http = lambda *args: {"scope": scope, "access_token": "PRIVATE", "token_type": "bearer"}
        assert provider.token({scope}).exact
    provider._http = lambda *args: pytest.fail("No transport for nonallowlisted scopes")
    with pytest.raises(RampError):
        provider.token({"vendors:write"})
    assert "PRIVATE" not in repr(token("bills:read"))


def test_snapshot_integrity_freshness_and_local_reseal_validation(tmp_path):
    snap = sync_records(Reader(), include_unlinked_purchase_orders=True)
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps(snap))
    at = datetime.fromisoformat(snap["completed_at"])
    assert load_snapshot(path, at=at)["snapshot_status"]["freshness"] == "FRESH"
    assert load_snapshot(path, at=at + timedelta(days=2))["snapshot_status"]["freshness"] == "STALE"
    assert not load_snapshot(path, at=at)["snapshot_status"]["usable_for_evaluation"]
    assert load_snapshot(path, at=at - timedelta(days=1))["snapshot_status"]["integrity"] == "INVALID"
    snap["resources"]["bills"]["records"][0]["amount"]["amount"] = "999"
    path.write_text(json.dumps(seal_snapshot(snap)))
    assert load_snapshot(path, at=at)["snapshot_status"]["integrity"] == "INVALID"


@pytest.mark.parametrize("change", ["private", "money", "link", "reciprocal", "status", "duplicate", "approval_id"])
def test_resealed_invalid_record_is_rejected(change):
    snap = sync_records(Reader(), include_unlinked_purchase_orders=True)
    bill = snap["resources"]["bills"]["records"][0]
    po = snap["resources"]["purchase_orders"]["records"][0]
    if change == "private": bill["name"] = "PRIVATE"
    elif change == "money": bill["amount"]["amount_minor"] = True
    elif change == "link": po["ramp_url"] += "?PRIVATE"
    elif change == "reciprocal": po["reciprocal_bill_ids"] = [BILL]
    elif change == "status": snap["resources"]["bills"]["status"] = "EMPTY"
    elif change == "duplicate": snap["resources"]["bills"]["records"].append(copy.deepcopy(bill))
    else: snap["resources"]["approvals"]["records"][0]["id"] = uid(999)
    with pytest.raises(RampError):
        _validate_snapshot(seal_snapshot(snap))


def cli():
    spec = importlib.util.spec_from_file_location("ramp_sync", Path(__file__).parents[1] / "scripts/ramp_sync.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_flag_and_private_output(tmp_path, monkeypatch, capsys):
    module, reader = cli(), Reader()
    monkeypatch.setattr(module, "SandboxRampProvider", lambda: reader)
    path = tmp_path / "records.json"
    assert module.main(["--all-purchase-orders", "--output", str(path)]) == 0
    snap = json.loads(path.read_text())
    _validate_snapshot(snap)
    assert snap["resources"]["purchase_orders"]["records"]
    assert path.stat().st_mode & 0o077 == 0
    reader.calls.clear()
    assert module.main(["--scope-only"]) == 0
    assert not reader.calls and "PRIVATE" not in capsys.readouterr().out


def test_cli_default_no_independent_pos_and_invalid_bounds_before_credentials(tmp_path, monkeypatch):
    module, reader = cli(), Reader()
    monkeypatch.setattr(module, "SandboxRampProvider", lambda: reader)
    assert module.main(["--output", str(tmp_path / "records.json")]) == 0
    assert not any(c[1] == "purchase-orders" for c in reader.calls)
    monkeypatch.setattr(module, "SandboxRampProvider", lambda: pytest.fail("No credentials for invalid bounds"))
    assert module.main(["--detail-limit", "0", "--output", str(tmp_path / "bad")]) == 1


def test_missing_associations_are_not_inferred_zero():
    reader = Reader()
    reader.rows["bills"][0].pop("applied_vendor_credits")
    snapshot = sync_records(reader)
    _validate_snapshot(snapshot)
    assert snapshot["resources"]["bills"]["records"][0]["applied_credits"] is None
    row = sanitize_credit({"id": CREDIT, "vendor_id": VENDOR})
    assert row["applied_bills"] is row["applied_drafts"] is row["total_applied"] is None


def test_multiple_pages_keep_filter_and_bounded_agreement_query_body():
    reader = Reader()
    original = reader.request
    def request(tok, method, path, query=None, data=None):
        if path == "vendors/agreements":
            reader.calls.append((method, path, query, copy.deepcopy(data)))
            if "start" not in data:
                return page([], ORIGIN + "/developer/v1/vendors/agreements?page_size=2&start=next")
            assert data == {"page_size": 2, "start": "next"} and query is None
            return page([])
        return original(tok, method, path, query, data)
    reader.request = request
    snapshot = sync_records(reader, page_size=2, max_pages=2)
    _validate_snapshot(snapshot)
    assert snapshot["resources"]["agreements"]["status"] == "EMPTY"
    assert snapshot["resources"]["agreements"]["coverage"]["vendors/agreements"]["pages_read"] == 2


def test_pos_share_global_detail_budget_between_linked_and_independent():
    reader = Reader(linked=True)
    reader.rows["purchase-orders"].append(dict(reader.rows["purchase-orders"][0], id=uid(999), bill_ids=[]))
    snapshot = sync_records(reader, detail_limit=1, include_unlinked_purchase_orders=True)
    _validate_snapshot(snapshot)
    resource = snapshot["resources"]["purchase_orders"]
    assert len(resource["records"]) == 1 and resource["records"][0]["id"] == PO
    assert resource["coverage"]["INDEPENDENT_POs"]["status"] == "TRUNCATED"
    assert len([c for c in reader.calls if c[1].startswith("purchase-orders/")]) == 1


def test_independent_po_failed_detail_has_failure_coverage():
    reader = Reader()
    reader.overrides["purchase-orders/" + PO] = RampHTTPError(403)
    snapshot = sync_records(reader, include_unlinked_purchase_orders=True)
    _validate_snapshot(snapshot)
    resource = snapshot["resources"]["purchase_orders"]
    assert resource["status"] == "FORBIDDEN"
    cov = resource["coverage"]["INDEPENDENT_POs"]
    assert cov["status"] == "PARTIAL" and cov["issues"][0]["http_status"] == 403


def test_duplicate_page_ids_refuse_complete_coverage():
    reader = Reader()
    reader.rows["purchase-orders"] *= 2
    snapshot = sync_records(reader, include_unlinked_purchase_orders=True)
    _validate_snapshot(snapshot)
    resource = snapshot["resources"]["purchase_orders"]
    assert resource["status"] == "PARTIAL" and len(resource["records"]) == 1


@pytest.mark.parametrize("change", ["complete", "private_issue", "private_coverage"])
def test_saved_coverage_cannot_claim_complete_or_store_raw_errors(change):
    snapshot = sync_records(Reader(), include_unlinked_purchase_orders=True)
    res = snapshot["resources"]["purchase_orders"]
    if change == "complete":
        res["coverage"]["INDEPENDENT_POs"]["has_next"] = True
    elif change == "private_issue":
        res["issues"] = [{"code": "PRIVATE"}]
    else:
        res["coverage"]["INDEPENDENT_POs"]["url"] = "PRIVATE"
    with pytest.raises(RampError):
        _validate_snapshot(seal_snapshot(snapshot))


def test_ui_link_and_independent_discovery_fields_are_additive():
    snapshot = sync_records(Reader(linked=True))
    for bill in snapshot["resources"]["bills"]["records"]:
        bill.pop("deep_link_url")
    for po in snapshot["resources"]["purchase_orders"]["records"]:
        for key in ("ramp_url", "discovery", "reciprocal_bill_ids"):
            po.pop(key)
    _validate_snapshot(seal_snapshot(snapshot))


def linked_vendor_reader():
    reader = Reader()
    reader.overrides['vendors/' + VENDOR] = copy.deepcopy(reader.rows['vendors'][0])
    reader.rows['vendors'] = [dict(reader.rows['vendors'][0], id=uid(90))]
    return reader


def test_linked_vendor_priority_shared_budget_and_inventory_truncation():
    reader = linked_vendor_reader()
    reader.overrides['vendors'] = page(reader.rows['vendors'],
        ORIGIN + '/developer/v1/vendors?page_size=10&start=next')
    snap = sync_records(reader, detail_limit=1)
    _validate_snapshot(snap)
    resource = snap['resources']['vendors']
    assert [r['id'] for r in resource['records']] == [VENDOR]
    assert resource['coverage']['LINKED_VENDORS']['status'] == 'COMPLETE'
    assert resource['coverage']['vendors']['list_complete'] is False
    assert resource['status'] == 'TRUNCATED'
    assert [c[1] for c in reader.calls if c[1].startswith('vendors/') and c[1].split('/')[-1] in {VENDOR, uid(90)}] == ['vendors/' + VENDOR]


@pytest.mark.parametrize('failure', [RampHTTPError(403), RampHTTPError(500), {'id': uid(99)}, {'id': 'not-an-id'}])
def test_linked_vendor_failure_never_substitutes_list_or_retries(failure):
    reader = Reader()
    reader.overrides['vendors/' + VENDOR] = failure
    snap = sync_records(reader)
    _validate_snapshot(snap)
    resource = snap['resources']['vendors']
    assert resource['records'] == []
    assert resource['coverage']['LINKED_VENDORS']['details_attempted'] == 1
    assert resource['coverage']['LINKED_VENDORS']['details_read'] == 0
    assert resource['coverage']['LINKED_VENDORS']['status'] in {'FORBIDDEN', 'UNAVAILABLE'}
    assert resource['coverage']['vendors']['detail_complete'] is False
    assert sum(c[1] == 'vendors/' + VENDOR for c in reader.calls) == 1


def test_linked_vendor_partial_failure_preserves_only_verified_ids():
    reader = linked_vendor_reader()
    reader.rows['bills'].append(dict(reader.rows['bills'][0], id=uid(88), vendor={'id': uid(89)}))
    reader.overrides['vendors/' + uid(89)] = RampHTTPError(500)
    snap = sync_records(reader, detail_limit=2)
    _validate_snapshot(snap)
    resource = snap['resources']['vendors']
    assert [r['id'] for r in resource['records']] == [VENDOR]
    assert resource['coverage']['LINKED_VENDORS']['status'] == 'PARTIAL'
    assert resource['coverage']['LINKED_VENDORS']['details_attempted'] == 2
    assert resource['status'] == 'PARTIAL'


@pytest.mark.parametrize('granted,reported', [(set(), True), ({'vendors:read', 'vendors:write'}, True), ({'vendors:read'}, False)])
def test_linked_vendor_missing_or_inexact_grant_never_reads(granted, reported):
    reader = Reader()
    original = reader.token
    reader.token = lambda scopes: Token('PRIVATE', frozenset(granted), frozenset(scopes), reported) if scopes == {'vendors:read'} else original(scopes)
    snap = sync_records(reader)
    _validate_snapshot(snap)
    assert snap['resources']['bills']['records']
    assert not any(c[1].startswith('vendors') for c in reader.calls)
    cov = snap['resources']['vendors']['coverage']['LINKED_VENDORS']
    assert cov['listed'] == 1 and cov['details_attempted'] == 0
    assert cov['status'] == 'UNAVAILABLE' and not cov['detail_complete']


def test_linked_vendor_duplicate_competing_payload_cannot_override_detail():
    reader = Reader()
    reader.overrides['vendors/' + VENDOR] = dict(reader.rows['vendors'][0], is_active=False)
    reader.rows['vendors'].append(dict(reader.rows['vendors'][0], is_active=True, name='HOSTILE PRIVATE'))
    snap = sync_records(reader)
    _validate_snapshot(snap)
    resource = snap['resources']['vendors']
    assert len(resource['records']) == 1 and resource['records'][0]['is_active'] is False
    assert resource['status'] == 'PARTIAL'
    assert resource['coverage']['LINKED_VENDORS']['status'] == 'COMPLETE'
    assert sum(c[1] == 'vendors/' + VENDOR for c in reader.calls) == 1
    assert 'PRIVATE' not in json.dumps(snap)


def test_linked_vendor_archived_and_foreign_entity_are_observations_not_authority(tmp_path):
    reader = Reader()
    reader.rows['bills'][0]['archived_at'] = DATE
    reader.rows['vendors'][0].update(default_entity_id=uid(99), parent_vendor_id=uid(98), is_active=False)
    reader.rows['bills'].append(dict(reader.rows['bills'][0], id=uid(97), entity_id=uid(96)))
    snap = sync_records(reader)
    _validate_snapshot(snap)
    vendor = snap['resources']['vendors']['records'][0]
    assert vendor['default_entity_id'] == uid(99) and not vendor['is_active']
    assert {b['entity_id'] for b in snap['resources']['bills']['records'] if b['kind'] == 'bill'} == {ENTITY, uid(96)}
    assert sum(c[1] == 'vendors/' + VENDOR for c in reader.calls) == 1
    assert not any(c[1] in {'vendors/' + uid(98), 'vendors/' + uid(99)} for c in reader.calls)
    target = tmp_path / 'capture.json'
    target.write_text(json.dumps(snap))
    loaded = load_snapshot(target, at=datetime.fromisoformat(snap['completed_at']) + timedelta(days=2))
    assert loaded['snapshot_status']['freshness'] == 'STALE'
    assert loaded['snapshot_status']['usable_for_evaluation'] is False


def test_vendor_inventory_only_option_retains_historical_schema():
    reader = linked_vendor_reader()
    snap = sync_records(reader, include_linked_vendors=False)
    _validate_snapshot(snap)
    assert set(snap['resources']['vendors']['coverage']) == {'vendors'}
    assert [r['id'] for r in snap['resources']['vendors']['records']] == [uid(90)]
    assert not any(c[1] == 'vendors/' + VENDOR for c in reader.calls)
    with pytest.raises(RampError):
        sync_records(reader, include_linked_vendors=1)


def test_linked_vendor_seventh_reference_is_bounded_and_sample_is_not_inventory():
    reader = Reader()
    reader.rows['bills'] = [dict(reader.rows['bills'][0], id=uid(100+i), vendor={'id': uid(200+i)}) for i in range(7)]
    reader.rows['bills/drafts'] = [dict(reader.rows['bills'][0], id=uid(300), status='DRAFT')]
    reader.rows['vendors'] = []
    for i in range(7):
        reader.overrides['vendors/' + uid(200+i)] = {'id': uid(200+i)}
    # Seven captured bill references are distinct; drafts consume the same parent budget.
    snap = sync_records(reader, detail_limit=7)
    _validate_snapshot(snap)
    assert len(snap['resources']['vendors']['records']) == 7
    assert snap['resources']['bills']['status'] == 'TRUNCATED'
    assert snap['resources']['vendors']['coverage']['LINKED_VENDORS']['parent_scope'] == 'captured_native_records'
    assert len([c for c in reader.calls if c[1] in {'vendors/' + uid(200+i) for i in range(7)}]) == 7
    # Unit exercise of the linked phase isolates a smaller vendor budget from parent budget.
    from uptime.ramp_records import _vendor_capture, _resource, _grant
    token, grant = _grant(reader, 'vendors:read')
    resource = _resource(grant)
    reader.calls.clear()
    _vendor_capture(reader, token, resource, snap['resources']['bills']['records'], 10, 1, 6)
    assert resource['coverage']['LINKED_VENDORS']['status'] == 'TRUNCATED'
    assert resource['coverage']['LINKED_VENDORS']['details_attempted'] == 6
    assert resource['coverage']['LINKED_VENDORS']['listed'] == 7
    assert not any(c[1] == 'vendors/' + uid(206) for c in reader.calls)
