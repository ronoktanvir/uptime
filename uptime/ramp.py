"""Narrow sandbox adapter. The UI consumes saved, sanitized observations offline."""
import base64
import http.client
import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode
from uuid import UUID, uuid4

from .contracts import Source

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/ramp"
ORIGIN = "https://demo-api.ramp.com"
READS = {"vendors:read", "bills:read"}
WRITE_SCOPES = {"bills:read", "bills:write"}
DRAFT_PATH = "bills/drafts"
SCOPE = re.compile(r"[a-z][a-z0-9_]*:(?:read|write)")


class RampError(RuntimeError):
    """Messages are safe for display. Never include provider bodies or headers."""


def now():
    return datetime.now(timezone.utc).isoformat()


def uuid_text(value):
    return str(UUID(str(value)))


def money(value):
    if value is None:
        return None
    currency = value["currency_code"]
    scale = value["minor_unit_conversion_rate"]
    minor = value["amount"]
    if (not re.fullmatch("[A-Z]{3}", currency) or type(minor) is not int
            or type(scale) is not int or scale <= 0 or (currency == "USD" and scale != 100)):
        raise RampError("Invalid provider monetary units")
    return {"currency": currency, "amount": format(Decimal(minor) / scale, "f")}


def _enum(value):
    if value is None:
        return None
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,60}", value):
        raise RampError("Invalid provider enum")
    return value


def sanitize_bill(bill):
    """Retain accounting facts and UUIDs, omit names, free text, URLs and contacts."""
    lines = []
    for kind in ("line_items", "inventory_line_items"):
        for line in bill.get(kind, []):
            quantity = line.get("quantity")
            if quantity is not None:
                quantity = Decimal(str(quantity))
                if not quantity.is_finite() or quantity < 0:
                    raise RampError("Invalid inventory quantity")
            lines.append({"id": uuid_text(line["id"]), "kind": kind, "amount": money(line["amount"]),
                          "unit_price": money(line.get("unit_price")),
                          "quantity": None if quantity is None else str(quantity),
                          "service_date": None, "sku": None})
    credits = [{"credit_id": uuid_text(c["id"]), "amount": money(c["amount"])}
               for c in bill.get("applied_vendor_credits", [])]
    issued = bill.get("issued_at")
    return {"id": uuid_text(bill["id"]), "status": _enum(bill.get("status")),
            "approval_status": _enum(bill.get("approval_status")),
            "issued_at": datetime.fromisoformat(issued).isoformat() if issued else None,
            "amount": money(bill.get("amount")), "lines": lines, "applied_credits": credits,
            "sources": [Source.RAMP.value]}


def sanitize_credit(credit):
    def applied(key):
        return [{"bill_id": uuid_text(item["bill_id"]), "amount": money(item["amount"])}
                for item in credit.get(key, [])]
    return {"id": uuid_text(credit["id"]), "vendor_id": uuid_text(credit["vendor_id"]),
            "total": money(credit["total_amount"]), "remaining": money(credit["remaining_amount"]),
            "applied_bills": applied("applied_bills"), "applied_drafts": applied("applied_draft_bills"),
            "sources": [Source.RAMP.value]}


@dataclass(frozen=True)
class Token:
    value: str = field(repr=False)
    granted: frozenset
    expected: frozenset

    @property
    def exact(self):
        return self.granted == self.expected


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
                raise RampError(f"Ramp HTTP {res.status}")
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
        if not scopes or not scopes <= READS | WRITE_SCOPES:
            raise RampError("Scope outside allowlist")
        body = urlencode({"grant_type": "client_credentials", "scope": " ".join(sorted(scopes))})
        data = self._http("POST", "token", {"Authorization": "Basic " + self._basic,
                                           "Content-Type": "application/x-www-form-urlencoded"}, body)
        granted = frozenset(data.get("scope", "").split())
        if (not all(SCOPE.fullmatch(s) for s in granted) or not data.get("access_token")
                or str(data.get("token_type", "")).lower() != "bearer"):
            raise RampError("Unexpected token metadata")
        return Token(data["access_token"], granted, scopes)

    def request(self, token, method, path, query=None, data=None):
        if not token.exact or method != "GET" or data is not None:
            raise RampError("Only scope-verified reads permitted")
        parts = path.split("/")
        if path in {"vendors", "vendors/credits"}:
            needed = "vendors:read"
        elif path in {"bills", DRAFT_PATH}:
            needed = "bills:read"
        elif parts[:-1] in (["bills", "drafts"], ["bills"], ["vendors", "credits"]):
            if parts[-1] != uuid_text(parts[-1]):
                raise RampError("Invalid provider ID")
            needed = "vendors:read" if parts[0] == "vendors" else "bills:read"
        else:
            raise RampError("Path outside allowlist")
        if needed not in token.granted:
            raise RampError("Scope outside allowlist")
        path += "?" + urlencode(query) if query else ""
        return self._http("GET", path, {"Authorization": "Bearer " + token.value})

    def _draft_mutation(self, token, ident, data):
        if not token.exact or token.granted != WRITE_SCOPES:
            raise RampError("Exact draft scopes required")
        path = DRAFT_PATH if ident is None else DRAFT_PATH + "/" + uuid_text(ident)
        return self._http("POST" if ident is None else "PATCH", path,
                          {"Authorization": "Bearer " + token.value, "Content-Type": "application/json"},
                          json.dumps(data))


class FixtureRampProvider:
    def snapshot(self):
        return json.loads((FIXTURES / "offline.json").read_text())


def ramp_snapshot():
    """Last verified observation, not a fresh network call. No credentials needed."""
    path = FIXTURES / "verified.json"
    return json.loads(path.read_text()) if path.exists() else FixtureRampProvider().snapshot()


def _capability(token):
    return {"granted": sorted(token.granted), "requested": sorted(token.expected),
            "state": "GRANTED" if token.exact else "SCOPE_MISMATCH",
            "sources": [Source.RAMP.value]}


def capture(provider, write=False, journal=None):
    proof = {"mode": "saved sandbox observation", "origin": ORIGIN, "observed_at": now(),
             "ui_url": "https://demo.ramp.com", "sources": [Source.RAMP.value], "capabilities": {}, "bills": [], "vendor_ids": [],
             "credits": [], "draft": None, "schema_url": "https://docs.ramp.com/openapi/developer-api.json"}
    for kind, scope, path in (("vendors", "vendors:read", "vendors"),
                              ("credits", "vendors:read", "vendors/credits"), ("bills", "bills:read", "bills")):
        token = provider.token({scope})
        cap = proof["capabilities"][kind] = _capability(token)
        if not token.exact:
            continue
        params = {"page_size": 20}
        if kind == "credits":
            params["include_fully_used"] = "true"
        response = provider.request(token, "GET", path, params)
        rows = response["data"]
        cap.update(state="READ_VERIFIED", sampled=len(rows), page_limit=20,
                   has_next=bool(response.get("page", {}).get("next")))
        if kind == "vendors":
            proof["vendor_ids"] = [uuid_text(row["id"]) for row in rows[:1]]
        elif kind == "credits":
            for row in rows:
                ident = uuid_text(row["id"])
                credit = provider.request(token, "GET", f"vendors/credits/{ident}")
                if uuid_text(credit["id"]) != ident:
                    raise RampError("Unexpected credit detail ID")
                proof["credits"].append(sanitize_credit(credit))
        elif rows:
            chosen = max(rows, key=lambda row: (bool(row.get("inventory_line_items")),
                                                 bool(row.get("line_items"))))
            candidates = [chosen]
            pending = next((row for row in rows if row.get("status") == "OPEN"
                            and row.get("approval_status") == "PENDING"), None)
            if pending is not None and pending["id"] != chosen["id"]:
                candidates.append(pending)
            cap["readback_ids"] = []
            for row in candidates:
                ident = uuid_text(row["id"])
                detail = provider.request(token, "GET", f"bills/{ident}")
                if uuid_text(detail["id"]) != ident:
                    raise RampError("Unexpected bill detail ID")
                proof["bills"].append(sanitize_bill(detail))
                cap["readback_ids"].append(ident)
            cap["readback_id"] = cap["readback_ids"][0]

    token = provider.token(WRITE_SCOPES)
    cap = proof["capabilities"]["draft_write"] = _capability(token)
    if not token.exact:
        cap["detail"] = "Ramp omitted or changed requested scopes. No draft mutation attempted."
    elif write:
        if not proof["vendor_ids"] or journal is None:
            raise RampError("Verified vendor ID and durable journal required")
        proof["draft"] = verify_draft(provider, token, journal, proof["vendor_ids"][0])
        cap["state"] = "DRAFT_READBACK_VERIFIED"
    return proof


def verify_draft(provider, token, journal, vendor_id):
    """One locally journaled demo operation. Ambiguous mutations are never repeated."""
    if not token.exact or token.granted != WRITE_SCOPES:
        raise RampError("Exact draft scopes required")
    vendor_id = uuid_text(vendor_id)
    path = Path(journal)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    memo = "Uptime sandbox readback"

    def check(row, ident, tag):
        if (row["id"] != ident or row.get("remote_id") != tag or row.get("invoice_number") != tag
                or row.get("status") != "DRAFT" or row.get("vendor", {}).get("id") != vendor_id
                or money(row.get("amount")) != {"amount": "37500", "currency": "USD"}):
            raise RampError("Draft readback mismatch")

    try:
        conn.execute("CREATE TABLE IF NOT EXISTS draft (key INTEGER PRIMARY KEY CHECK(key=1), "
                     "tag TEXT NOT NULL, vendor TEXT NOT NULL, id TEXT, phase TEXT NOT NULL)")
        conn.execute("BEGIN IMMEDIATE")
        saved = conn.execute("SELECT tag,vendor,id,phase FROM draft WHERE key=1").fetchone()
        if saved is None:
            tag = "UPTIME-" + uuid4().hex
            conn.execute("INSERT INTO draft VALUES(1,?,?,NULL,'creating')", (tag, vendor_id))
            conn.commit()  # reserve before any network mutation
            payload = {"vendor_id": vendor_id, "invoice_number": tag, "remote_id": tag,
                       "enable_accounting_sync": False, "invoice_currency": "USD",
                       "inventory_line_items": [{"quantity": "1000", "unit_price": "37.50",
                                                 "memo": "Uptime demo seats"}]}
            row = provider._draft_mutation(token, None, payload)
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
        route = DRAFT_PATH + "/" + ident
        row = provider.request(token, "GET", route)
        check(row, ident, tag)
        # Claim update exactly once across processes, including ambiguous replies.
        if conn.execute("UPDATE draft SET phase='updating' WHERE key=1 AND phase='created'").rowcount:
            conn.commit()
            changed = provider._draft_mutation(token, ident, {"memo": memo})
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
