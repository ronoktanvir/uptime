"""Narrow sandbox adapter. The UI consumes saved, sanitized observations offline."""
import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID, uuid4

from .contracts import Source

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/ramp"
ORIGIN = "https://demo-api.ramp.com"
READS = {"vendors:read", "bills:read"}
WRITE_SCOPES = {"bills:read", "bills:write"}
# Token capability only; workflow mutations belong to the separately gated workflow adapter.
NATIVE_READ_SCOPES = frozenset({"vendors:read", "bills:read", "transactions:read",
                                "purchase_orders:read", "approvals:read"})
WORKFLOW_SCOPES = frozenset({"transactions:write", "blank_canvas:write", "unified_requests:read",
                             "custom_forms:read", "spend_programs:read", "spend_requests:read"})
TOKEN_SCOPES = NATIVE_READ_SCOPES | WRITE_SCOPES | WORKFLOW_SCOPES
DRAFT_PATH = "bills/drafts"
SCOPE = re.compile(r"[a-z][a-z0-9_]*:(?:read|write)")
LEGACY_SHA256 = "c6dff501561a29d626e4c28ebc774c77eb0c54e92e4a82193acf8114eccaf2c6"
MAX_CAPTURE_BYTES = 4_000_000


class RampError(RuntimeError):
    """Messages are safe for display. Never include provider bodies or headers."""


class RampHTTPError(RampError):
    def __init__(self, status):
        self.status = status
        super().__init__(f"Ramp HTTP {status}")


def now():
    return datetime.now(timezone.utc).isoformat()


def uuid_text(value):
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
        return value
    except (ValueError, AttributeError):
        raise RampError("Noncanonical provider ID") from None


def money(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise RampError("Invalid provider monetary units")
    currency = value.get("currency_code")
    scale = value.get("minor_unit_conversion_rate")
    minor = value.get("amount")
    if (not isinstance(currency, str) or not re.fullmatch("[A-Z]{3}", currency)
            or type(minor) is not int or abs(minor) > 10**24
            or type(scale) is not int or scale not in {1, 10, 100, 1000, 10000}
            or (currency == "USD" and scale != 100)):
        raise RampError("Invalid provider monetary units")
    return {"currency": currency, "amount": format(Decimal(minor) / scale, "f")}


def _enum(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,60}", value):
        raise RampError("Invalid provider enum")
    return value


def _quantity(value):
    if value is None:
        return None
    try:
        if type(value) not in (int, str, Decimal) or len(str(value)) > 80:
            raise ValueError
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > 10**18 or result.as_tuple().exponent < -12:
            raise ValueError
        return format(result, "f")
    except (ValueError, InvalidOperation):
        raise RampError("Invalid inventory quantity") from None


def _optional_id(value):
    return None if value is None else uuid_text(value)


def _accounting_ids(row):
    # These are ledger categories, never a customer account or contract binding.
    def opaque_id(value):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}", value):
            raise RampError("Invalid accounting identifier")
        return value
    return [{"id": opaque_id(item["id"]),
             "category_id": opaque_id(item["category_info"]["id"]),
             "category_type": _enum(item["category_info"].get("type"))}
            for item in row.get("accounting_field_selections", [])]


def _timestamp(value):
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        raise RampError("Invalid provider timestamp") from None


def sanitize_bill(bill):
    """Retain accounting facts and UUIDs, omit names, free text, URLs and contacts."""
    lines = []
    seen = set()
    for kind in ("line_items", "inventory_line_items"):
        for line in bill.get(kind, []):
            ident = uuid_text(line["id"])
            if ident in seen:
                raise RampError("Duplicate provider line ID")
            seen.add(ident)
            quantity = _quantity(line.get("quantity"))
            amount, rate = money(line.get("amount")), money(line.get("unit_price"))
            check = "UNAVAILABLE"
            if quantity is not None and amount is not None and rate is not None:
                with localcontext() as context:
                    context.prec = 80
                    matches = (amount["currency"] == rate["currency"]
                               and Decimal(quantity) * Decimal(rate["amount"]) == Decimal(amount["amount"]))
                check = "MATCH" if matches else "MISMATCH"
            lines.append({"id": ident, "kind": kind, "amount": amount,
                          "unit_price": rate, "quantity": quantity, "quantity_rate_check": check,
                          "accounting_field_selections": _accounting_ids(line),
                          "service_date": None, "sku": None})
    credits = [{"credit_id": uuid_text(c["id"]), "amount": money(c["amount"])}
               for c in bill.get("applied_vendor_credits", [])]
    status = _enum(bill.get("status"))
    if status not in {"OPEN", "PAID", "DRAFT"}:
        raise RampError("Invalid bill status")
    vendor_id = _optional_id((bill.get("vendor") or {}).get("id"))
    entity_id = _optional_id(bill.get("entity_id"))
    if status != "DRAFT" and (vendor_id is None or entity_id is None):
        raise RampError("Bill vendor and entity identity required")
    return {"id": uuid_text(bill["id"]), "status": _enum(bill.get("status")),
            "vendor_id": vendor_id, "entity_id": entity_id,
            "account_id": None, "account_identity": "UNAVAILABLE_IN_BILL_API",
            "accounting_field_selections": _accounting_ids(bill),
            "approval_status": _enum(bill.get("approval_status")),
            "issued_at": _timestamp(bill.get("issued_at")),
            "amount": money(bill.get("amount")), "lines": lines, "applied_credits": credits,
            "sources": [Source.RAMP.value]}


def sanitize_credit(credit):
    def applied(key):
        return [{"bill_id": uuid_text(item["bill_id"]), "amount": money(item["amount"])}
                for item in credit.get(key, [])]
    return {"id": uuid_text(credit["id"]), "vendor_id": uuid_text(credit["vendor_id"]),
            "entity_id": _optional_id(credit.get("entity_id")),
            "account_id": None, "account_identity": "UNAVAILABLE_IN_CREDIT_API",
            "archived_at": _timestamp(credit.get("archived_at")),
            "total": money(credit["total_amount"]), "remaining": money(credit["remaining_amount"]),
            "applied_bills": applied("applied_bills"), "applied_drafts": applied("applied_draft_bills"),
            "sources": [Source.RAMP.value]}


@dataclass(frozen=True)
class Token:
    value: str = field(repr=False)
    granted: frozenset
    expected: frozenset
    scope_reported: bool = True

    @property
    def exact(self):
        return self.scope_reported and self.granted == self.expected


def _read_query(query, path):
    """Allow only the bounded filters used by the read synchronizer and legacy capture."""
    lists = {"bills", DRAFT_PATH, "vendors", "vendors/credits", "vendors/agreements",
             "transactions", "purchase-orders", "approvals"}
    allowed = {"page_size", "start"} if path in lists or path.startswith("comments/") else set()
    if path == "vendors/credits":
        allowed |= {"include_fully_used"}
    if path == "approvals":
        allowed |= {"entity_type", "entity_ids"}
    if not isinstance(query, dict) or set(query) - allowed:
        raise RampError("Query outside allowlist")
    if "page_size" in query and (type(query["page_size"]) is not int or not 2 <= query["page_size"] <= 100):
        raise RampError("Invalid page bound")
    if "start" in query and (not isinstance(query["start"], str)
                             or not re.fullmatch(r"[A-Za-z0-9_=-]{1,512}", query["start"])):
        raise RampError("Invalid read cursor")
    if "include_fully_used" in query and query["include_fully_used"] != "true":
        raise RampError("Invalid credit filter")
    if path == "vendors/agreements" and "page_size" not in query:
        raise RampError("Bounded agreement query required")
    if path == "approvals":
        if query.get("entity_type") not in {"BILL", "TRANSACTION"}:
            raise RampError("Approval entity outside allowlist")
        ids = query.get("entity_ids")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
            raise RampError("Bounded approval parents required")
        for ident in ids:
            uuid_text(ident)


class SandboxRampProvider:
    def __init__(self):
        self._guard()
        path = Path.home() / ".config/uptime/ramp-sandbox.json"
        if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
            raise RampError("Private sandbox credential file unavailable")
        cfg = json.loads(path.read_text())
        if cfg.get("base_url") != ORIGIN:
            raise RampError("Credential origin mismatch")
        self._basic = base64.b64encode((cfg["client_id"] + ":" + cfg["client_secret"]).encode()).decode()

    @staticmethod
    def _guard():
        if os.environ.get("RAMP_ENV") != "sandbox" or os.environ.get("RAMP_BASE_URL", ORIGIN) != ORIGIN:
            raise RampError("Exact sandbox environment required")

    def _http(self, method, path, headers, body=None):
        self._guard()
        # Fixed TLS origin. http.client neither follows redirects nor reads proxy env.
        conn = http.client.HTTPSConnection("demo-api.ramp.com", timeout=15)
        try:
            conn.request(method, "/developer/v1/" + path, body, headers)
            res = conn.getresponse()
            expected_status = 201 if method == "POST" and path == DRAFT_PATH else 200
            if res.status != expected_status:
                raise RampHTTPError(res.status)
            data = res.read(4_000_001)
            if len(data) > 4_000_000:
                raise RampError("Provider response exceeded limit")
            return json.loads(data, parse_float=Decimal)
        except (OSError, http.client.HTTPException, ValueError):
            raise RampError("Sandbox network or response unavailable") from None
        finally:
            conn.close()

    def token(self, scopes):
        scopes = frozenset(scopes)
        if not scopes or not scopes <= TOKEN_SCOPES:
            raise RampError("Scope outside allowlist")
        body = urlencode({"grant_type": "client_credentials", "scope": " ".join(sorted(scopes))})
        data = self._http("POST", "token", {"Authorization": "Basic " + self._basic,
                                           "Content-Type": "application/x-www-form-urlencoded"}, body)
        if not isinstance(data, dict) or not isinstance(data.get("scope", ""), str):
            raise RampError("Unexpected token metadata")
        granted = frozenset(data.get("scope", "").split())
        if (not all(SCOPE.fullmatch(s) for s in granted) or not isinstance(data.get("access_token"), str)
                or not data["access_token"] or any(c in data["access_token"] for c in "\r\n")
                or str(data.get("token_type", "")).lower() != "bearer"):
            raise RampError("Unexpected token metadata")
        return Token(data["access_token"], granted, scopes, "scope" in data)

    def request(self, token, method, path, query=None, data=None):
        if not token.exact:
            raise RampError("Only scope-verified reads permitted")
        agreement_query = method == "POST" and path == "vendors/agreements"
        if agreement_query:
            if query is not None or not isinstance(data, dict):
                raise RampError("Only bounded agreement query permitted")
            _read_query(data, "vendors/agreements")
            needed = "vendors:read"
        elif method != "GET" or data is not None:
            raise RampError("Only scope-verified reads permitted")
        parts = path.split("/")
        if agreement_query:
            pass
        elif path in {"vendors", "vendors/credits"}:
            needed = "vendors:read"
        elif path in {"bills", DRAFT_PATH}:
            needed = "bills:read"
        elif path in {"transactions", "purchase-orders", "approvals"}:
            needed = {"transactions": "transactions:read", "purchase-orders": "purchase_orders:read",
                      "approvals": "approvals:read"}[path]
        elif parts[:-1] in (["bills", "drafts"], ["bills"], ["vendors", "credits"],
                           ["vendors"], ["vendors", "agreements"], ["transactions"], ["purchase-orders"]):
            if parts[-1] != uuid_text(parts[-1]):
                raise RampError("Invalid provider ID")
            needed = {"vendors": "vendors:read", "bills": "bills:read",
                      "transactions": "transactions:read", "purchase-orders": "purchase_orders:read"}[parts[0]]
        elif len(parts) == 3 and parts[0] == "comments" and parts[1] in {"bills", "draft-bills"}:
            uuid_text(parts[-1])
            needed = "bills:read"
        else:
            raise RampError("Path outside allowlist")
        if needed not in token.granted:
            raise RampError("Scope outside allowlist")
        headers = {"Authorization": "Bearer " + token.value}
        if agreement_query:
            headers["Content-Type"] = "application/json"
            return self._http("POST", path, headers, json.dumps(data, allow_nan=False))
        _read_query({} if query is None else query, path)
        path += "?" + urlencode(query, doseq=True) if query else ""
        return self._http("GET", path, headers)

    def _draft_mutation(self, token, ident, data, *, authorized=False):
        _write_gate(authorized)
        if not token.exact or token.granted != WRITE_SCOPES:
            raise RampError("Exact draft scopes required")
        if ident is None:
            tag = data.get("remote_id")
            if (not isinstance(tag, str) or not re.fullmatch(r"UPTIME-[a-f0-9]{32}", tag)
                    or data != _draft_payload(data.get("vendor_id"), tag)):
                raise RampError("Only the designated demo draft payload is allowed")
        elif data != {"memo": "Uptime sandbox readback"}:
            raise RampError("Only the journaled draft memo update is allowed")
        path = DRAFT_PATH if ident is None else DRAFT_PATH + "/" + uuid_text(ident)
        return self._http("POST" if ident is None else "PATCH", path,
                          {"Authorization": "Bearer " + token.value, "Content-Type": "application/json"},
                          json.dumps(data))


class FixtureRampProvider:
    def snapshot(self):
        return json.loads((FIXTURES / "offline.json").read_text())


def _digest(proof):
    payload = {k: v for k, v in proof.items() if k != "checksum_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def seal_capture(proof):
    """Local integrity only: this unkeyed digest is not provider attestation."""
    return {**proof, "checksum_sha256": _digest(proof)}


def _validate_saved_capture(proof):
    def amount(value):
        if value is None:
            return
        if (not isinstance(value, dict) or not isinstance(value.get("currency"), str)
                or not re.fullmatch(r"[A-Z]{3}", value["currency"])
                or not isinstance(value.get("amount"), str)
                or not re.fullmatch(r"-?[0-9]{1,25}(?:\.[0-9]{1,4})?", value["amount"])):
            raise RampError("Invalid saved amount")
    if not isinstance(proof.get("capabilities"), dict) or proof.get("sources") != [Source.RAMP.value]:
        raise RampError("Invalid saved provenance")
    for field in ("vendor_ids", "bills", "credits"):
        if not isinstance(proof.get(field), list):
            raise RampError("Invalid saved records")
    for ident in proof["vendor_ids"]:
        uuid_text(ident)
    for records in (proof["bills"], proof["credits"]):
        seen = set()
        for row in records:
            ident = uuid_text(row["id"])
            if ident in seen or row["sources"] != [Source.RAMP.value]:
                raise RampError("Invalid saved identity")
            seen.add(ident)
            _optional_id(row.get("vendor_id"))
            _optional_id(row.get("entity_id"))
    for bill in [*proof["bills"], *([proof["draft"]] if proof.get("draft") else [])]:
        uuid_text(bill["id"])
        if bill["status"] not in {"OPEN", "PAID", "DRAFT"} or not isinstance(bill["lines"], list):
            raise RampError("Invalid saved bill")
        amount(bill["amount"])
        line_ids = set()
        for line in bill["lines"]:
            ident = uuid_text(line["id"])
            if ident in line_ids:
                raise RampError("Duplicate saved line")
            line_ids.add(ident)
            _quantity(line["quantity"])
            amount(line["amount"])
            amount(line["unit_price"])
    for credit in proof["credits"]:
        amount(credit["total"])
        amount(credit["remaining"])


def ramp_snapshot(path=None, *, at=None, max_age_seconds=86400):
    """Validate a saved observation without credentials or network access."""
    path = Path(path) if path is not None else FIXTURES / "verified.json"
    if not path.exists():
        return FixtureRampProvider().snapshot()
    try:
        if path.stat().st_size > MAX_CAPTURE_BYTES:
            raise RampError("Capture exceeded size limit")
        raw = path.read_bytes()
        proof = json.loads(raw)
        legacy = "capture_version" not in proof
        if legacy:
            if hashlib.sha256(raw).hexdigest() != LEGACY_SHA256:
                raise RampError("Legacy capture checksum mismatch")
        elif (proof.get("capture_version") != 2 or not isinstance(proof.get("checksum_sha256"), str)
              or not hmac.compare_digest(proof["checksum_sha256"], _digest(proof))):
            raise RampError("Capture checksum mismatch")
        if proof.get("origin") != ORIGIN or proof.get("mode") != "saved sandbox observation":
            raise RampError("Capture origin mismatch")
        if not legacy:
            _validate_saved_capture(proof)
        observed = datetime.fromisoformat(_timestamp(proof["observed_at"]))
        current = at or datetime.now(timezone.utc)
        if current.tzinfo is None or type(max_age_seconds) is not int or max_age_seconds <= 0:
            raise RampError("Invalid capture freshness policy")
        age = (current - observed).total_seconds()
        if age < 0:
            raise RampError("Capture timestamp is in the future")
        stale = age > max_age_seconds
        proof["capture_status"] = {
            "integrity": "ARCHIVE_CHECKSUM_VERIFIED" if legacy else "CHECKSUM_VERIFIED",
            "freshness": "STALE" if stale else "FRESH", "age_seconds": int(age),
            "max_age_seconds": max_age_seconds, "legacy": legacy,
            "usable_for_evaluation": not legacy and not stale and all(
                proof["capabilities"].get(kind, {}).get("state") == "READ_VERIFIED"
                and proof["capabilities"][kind].get("detail_complete", proof["capabilities"][kind].get("list_complete")) is True
                for kind in ("vendors", "bills", "credits")) and all(
                    line.get("quantity_rate_check") != "MISMATCH"
                    for bill in proof["bills"] for line in bill["lines"]),
            "requires_contract_mapping": True,
            "provider_attestation": False,
        }
        proof["sources"] = list(dict.fromkeys([*proof["sources"], Source.REPLAY.value]))
        return proof
    except (RampError, OSError, ValueError, TypeError, KeyError, OverflowError, AttributeError):
        return {"mode": "unavailable capture", "observed_at": None, "origin": ORIGIN,
                "sources": [Source.UNAVAILABLE.value], "bills": [], "credits": [],
                "vendor_ids": [], "draft": None, "capabilities": {},
                "capture_status": {"integrity": "INVALID", "freshness": "UNKNOWN",
                                   "usable_for_evaluation": False}}


def _capability(token):
    missing, unexpected = token.expected - token.granted, token.granted - token.expected
    if not token.scope_reported:
        diagnosis = "SCOPE_FIELD_ABSENT"
    elif missing and unexpected:
        diagnosis = "MISSING_AND_UNEXPECTED_GRANTS"
    elif missing:
        diagnosis = "MISSING_GRANTS"
    elif unexpected:
        diagnosis = "UNEXPECTED_GRANTS"
    else:
        diagnosis = "EXACT_GRANT"
    return {"granted": sorted(token.granted), "requested": sorted(token.expected),
            "missing": sorted(missing), "unexpected": sorted(unexpected),
            "scope_reported": token.scope_reported, "diagnosis": diagnosis,
            "state": "GRANTED" if token.exact else "SCOPE_MISMATCH",
            "sources": [Source.RAMP.value]}


def _failure(exc):
    if isinstance(exc, RampHTTPError):
        return {"state": {401: "AUTHENTICATION_REJECTED", 403: "ACCESS_REJECTED"}.get(
            exc.status, "HTTP_ERROR"), "http_status": exc.status}
    return {"state": "PROVIDER_ERROR"}


def scope_probe(provider, *, include_write=False):
    """Only token exchanges; never fetch records, follow URLs, or mutate bills."""
    requests = [{"vendors:read"}, {"bills:read"}]
    if include_write:
        requests.extend([WRITE_SCOPES, {"bills:write"}])
    result = {"mode": "token metadata only", "origin": ORIGIN, "observed_at": now(),
              "requests": [], "app_allowed_scopes": "NOT_OBSERVABLE_FROM_TOKEN_RESPONSE",
              "admin_configuration": "NOT_INSPECTED", "records_read": False, "writes_attempted": False}
    for scopes in requests:
        try:
            result["requests"].append(_capability(provider.token(scopes)))
        except RampError as exc:
            result["requests"].append({"requested": sorted(scopes), **_failure(exc)})
    return result


def _bounds(page_size, max_pages, detail_limit):
    if (type(page_size) is not int or not 2 <= page_size <= 100
            or type(max_pages) is not int or not 1 <= max_pages <= 10
            or type(detail_limit) is not int or not 1 <= detail_limit <= 100):
        raise RampError("Invalid pagination bounds")


def _next_query(next_url, path, initial):
    # Provider URLs are untrusted; only extract a cursor and reconstruct our own request.
    try:
        if not isinstance(next_url, str) or len(next_url) > 4096:
            raise ValueError
        parsed = urlsplit(next_url)
        if (parsed.scheme != "https" or parsed.netloc != "demo-api.ramp.com"
                or parsed.path != "/developer/v1/" + path or parsed.fragment):
            raise ValueError
        values = parse_qs(parsed.query, strict_parsing=True, keep_blank_values=True)
        if (set(values) - (set(initial) | {"start"}) or "start" not in values
                or any(len(v) != 1 for v in values.values())):
            raise ValueError
        for name, expected in initial.items():
            if name in values and values[name][0] != str(expected):
                raise ValueError
        cursor = values["start"][0]
        if not re.fullmatch(r"[A-Za-z0-9_=-]{1,512}", cursor):
            raise ValueError
        return {**initial, "start": cursor}
    except (ValueError, TypeError):
        raise RampError("Unsafe pagination metadata") from None


def _pages(provider, token, path, page_size, max_pages):
    initial = {"page_size": page_size}
    if path == "vendors/credits":
        initial["include_fully_used"] = "true"
    query, rows, seen_ids, seen_cursors = initial, [], set(), set()
    for page_number in range(1, max_pages + 1):
        response = provider.request(token, "GET", path, query)
        if not isinstance(response, dict):
            raise RampError("Invalid provider page")
        batch = response.get("data")
        if not isinstance(batch, list) or len(batch) > page_size:
            raise RampError("Invalid provider page")
        for row in batch:
            if not isinstance(row, dict):
                raise RampError("Invalid provider record")
            ident = uuid_text(row["id"])
            if ident in seen_ids:
                raise RampError("Duplicate provider record across pages")
            seen_ids.add(ident)
        rows.extend(batch)
        page = response.get("page")
        if not isinstance(page, dict) or "next" not in page:
            raise RampError("Missing pagination metadata")
        next_url = page["next"]
        if next_url is None:
            break
        query = _next_query(next_url, path, initial)
        if query["start"] in seen_cursors:
            raise RampError("Repeated pagination cursor")
        seen_cursors.add(query["start"])
    return rows, {"pages_read": page_number, "max_pages": max_pages, "page_size": page_size,
                  "listed": len(rows), "has_next": next_url is not None,
                  "list_complete": next_url is None}


def _write_gate(authorized):
    SandboxRampProvider._guard()
    if authorized is not True or os.environ.get("RAMP_ENABLE_DRAFT_WRITE") != "1":
        raise RampError("Explicit draft authorization and feature gate required")


def _draft_payload(vendor_id, tag):
    return {"vendor_id": uuid_text(vendor_id), "invoice_number": tag, "remote_id": tag,
            "enable_accounting_sync": False, "invoice_currency": "USD",
            "inventory_line_items": [{"quantity": "1000", "unit_price": "37.50",
                                      "memo": "Uptime demo seats"}]}


def capture(provider, write=False, journal=None, *, designated_vendor_id=None,
            authorize_draft=False, page_size=20, max_pages=3, detail_limit=20):
    _bounds(page_size, max_pages, detail_limit)
    if write:
        _write_gate(authorize_draft)
        if designated_vendor_id is None or journal is None:
            raise RampError("Designated sandbox vendor and durable journal required")
        designated_vendor_id = uuid_text(designated_vendor_id)
    proof = {"capture_version": 2, "mode": "saved sandbox observation", "origin": ORIGIN,
             "observed_at": now(), "ui_url": "https://demo.ramp.com", "sources": [Source.RAMP.value],
             "capabilities": {}, "bills": [], "vendor_ids": [], "credits": [], "draft": None,
             "schema_url": "https://docs.ramp.com/openapi/developer-api.json"}
    for kind, scope, path in (("vendors", "vendors:read", "vendors"),
                              ("credits", "vendors:read", "vendors/credits"), ("bills", "bills:read", "bills")):
        cap = proof["capabilities"][kind] = {"requested": [scope]}
        try:
            token = provider.token({scope})
            cap.update(_capability(token))
            if not token.exact:
                continue
            rows, metadata = _pages(provider, token, path, page_size, max_pages)
            cap.update(metadata, state="READ_VERIFIED", sampled=len(rows))
            if kind == "vendors":
                proof["vendor_ids"] = [uuid_text(row["id"]) for row in rows]
                continue
            if kind == "bills":
                rows = sorted(rows, key=lambda row: (row.get("status") == "OPEN"
                              and row.get("approval_status") == "PENDING",
                              bool(row.get("inventory_line_items"))), reverse=True)
            records, readback_ids = [], []
            for row in rows[:detail_limit]:
                ident = uuid_text(row["id"])
                detail = provider.request(token, "GET", f"{path}/{ident}")
                if uuid_text(detail["id"]) != ident:
                    raise RampError("Unexpected detail ID")
                records.append(sanitize_bill(detail) if kind == "bills" else sanitize_credit(detail))
                readback_ids.append(ident)
            proof[kind] = records
            cap.update(readback_ids=readback_ids, detail_limit=detail_limit,
                       detail_complete=len(records) == len(rows) and cap["list_complete"])
            if readback_ids:
                cap["readback_id"] = readback_ids[0]
        except (RampError, KeyError, TypeError, ValueError, AttributeError) as exc:
            cap.update(_failure(exc))
            if kind in {"bills", "credits"}:
                proof[kind] = []
    cap = proof["capabilities"]["draft_write"] = {
        "state": "NOT_REQUESTED", "requested": [], "granted": [], "writes_attempted": False}
    if write:
        if designated_vendor_id not in proof["vendor_ids"]:
            raise RampError("Designated vendor not found in bounded sandbox read")
        try:
            token = provider.token(WRITE_SCOPES)
            cap.update(_capability(token))
        except RampError as exc:
            cap.update(_failure(exc))
        else:
            if token.exact:
                proof["draft"] = verify_draft(provider, token, journal, designated_vendor_id,
                                               authorized=authorize_draft)
                cap.update(state="DRAFT_READBACK_VERIFIED", writes_attempted=True)
    proof["completed_at"] = now()
    return seal_capture(proof)


def verify_draft(provider, token, journal, vendor_id, *, authorized=False):
    """One locally journaled demo operation. Ambiguous mutations are never repeated."""
    if not token.exact or token.granted != WRITE_SCOPES:
        raise RampError("Exact draft scopes required")
    _write_gate(authorized)
    vendor_id = uuid_text(vendor_id)
    path = Path(journal)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            raise RampError("Private regular draft journal required") from None
    else:
        os.close(descriptor)
    conn = sqlite3.connect(path)
    memo = "Uptime sandbox readback"

    def check(row, ident, tag):
        if (row["id"] != ident or row.get("remote_id") != tag or row.get("invoice_number") != tag
                or row.get("status") != "DRAFT" or row.get("vendor", {}).get("id") != vendor_id
                or money(row.get("amount")) != {"amount": "37500", "currency": "USD"}):
            raise RampError("Draft readback mismatch")
        sanitized = sanitize_bill(row)
        lines = sanitized["lines"]
        if (len(lines) != 1 or lines[0]["kind"] != "inventory_line_items"
                or lines[0]["quantity_rate_check"] != "MATCH"
                or Decimal(lines[0]["quantity"]) != Decimal("1000")
                or Decimal(lines[0]["unit_price"]["amount"]) != Decimal("37.50")
                or lines[0]["unit_price"]["currency"] != "USD"
                or lines[0]["amount"] != {"amount": "37500", "currency": "USD"}
                or row.get("sync_status") != "NOT_SYNCED"):
            raise RampError("Draft quantity, unit price or sync readback mismatch")

    try:
        conn.execute("CREATE TABLE IF NOT EXISTS draft (key INTEGER PRIMARY KEY CHECK(key=1), "
                     "tag TEXT NOT NULL, vendor TEXT NOT NULL, id TEXT, phase TEXT NOT NULL)")
        conn.execute("BEGIN IMMEDIATE")
        saved = conn.execute("SELECT tag,vendor,id,phase FROM draft WHERE key=1").fetchone()
        if saved is None:
            tag = "UPTIME-" + uuid4().hex
            conn.execute("INSERT INTO draft VALUES(1,?,?,NULL,'creating')", (tag, vendor_id))
            conn.commit()  # reserve before any network mutation
            payload = _draft_payload(vendor_id, tag)
            row = provider._draft_mutation(token, None, payload, authorized=authorized)
            ident = uuid_text(row["id"])
            check(row, ident, tag)
            conn.execute("UPDATE draft SET id=?, phase='created' WHERE key=1", (ident,))
            conn.commit()
        else:
            tag, saved_vendor, ident, phase = saved
            conn.commit()
            if vendor_id != saved_vendor:
                raise RampError("Journal vendor mismatch")
            if ident is None:
                raise RampError("Unconfirmed draft creation; reconcile by journal tag before proceeding")
            if (not re.fullmatch(r"UPTIME-[a-f0-9]{32}", tag)
                    or phase not in {"created", "updating", "verified"}):
                raise RampError("Invalid draft journal ownership")
            ident = uuid_text(ident)
        route = DRAFT_PATH + "/" + ident
        row = provider.request(token, "GET", route)
        check(row, ident, tag)
        # Claim update exactly once across processes, including ambiguous replies.
        if conn.execute("UPDATE draft SET phase='updating' WHERE key=1 AND phase='created'").rowcount:
            conn.commit()
            changed = provider._draft_mutation(token, ident, {"memo": memo}, authorized=authorized)
            check(changed, ident, tag)
        conn.commit()
        row = provider.request(token, "GET", route)
        check(row, ident, tag)
        if row.get("memo") != memo:
            raise RampError("Unconfirmed draft update; no automatic retry")
        conn.execute("UPDATE draft SET phase='verified' WHERE key=1")
        conn.commit()
        return {**sanitize_bill(row), "tag": tag, "verified_at": now()}
    finally:
        conn.close()
