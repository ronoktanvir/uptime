"""Transactional economic identity for the two local claim intake routes.

Trusted callers resolve tenant, vendor, account, agreement lineage and remedy.
Versions belong to packet approval, never to the economic uniqueness key. Month
is the controlling fee period, not a month inferred from a filing timestamp.
Resource-specific remedies include their trusted resource ID in ``remedy``.
This module reserves dispatch, but does not establish entitlement or authority.

The additive v2 registry retains the old registry and receipts for audit. Before
any new reservation it imports both historical routes, refusing incomplete or
conflicting history. No current fixture or current contract fills historical gaps.
"""
from dataclasses import asdict
from datetime import UTC, datetime
import json
import re
import unicodedata

from .contracts import fingerprint

TABLE = "claim_dispatch_identity_v2"


class EconomicScopeReviewRequired(ValueError):
    """A retained legacy key cannot safely represent this measurement tuple."""


def _identity(value):
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(unicodedata.category(c).startswith("C") for c in value)):
        raise ValueError("Canonical nonempty identity required.")
    return value


def _label(value):
    return unicodedata.normalize("NFC", _identity(value)).casefold()


def _instant(value):
    at = datetime.fromisoformat(_identity(value))
    if at.utcoffset() is None:
        raise ValueError("An aware reservation timestamp is required.")
    return at.astimezone(UTC).isoformat()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _economic(*, tenant, vendor, account, agreement_id, agreement_version, service, month, remedy):
    if not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", _identity(month)) or month.startswith("0000"):
        raise ValueError("Canonical service month required.")
    _identity(agreement_version)  # Required provenance; deliberately excluded from identity.
    return [_identity(tenant), _label(vendor), _identity(account), _identity(agreement_id),
            _label(service), month, _identity(remedy)]


def claim_key(**identity):
    return fingerprint(_economic(**identity))


def resource_remedy(manifest, overlay):
    """Use the supported contract's measurement unit, preserving stored wire keys."""
    if manifest["family"] == "monthly-availability/1":
        return "availability"
    if manifest["family"] != "resource-month/1":
        raise ValueError("Unsupported economic scope.")
    if manifest.get("aggregate_monitor"):
        return "resource-month/aggregate-service"
    resource = _identity(overlay["resource_id"])
    record = overlay.get("subscription_record") or {}
    region = _identity(record.get("region")) if manifest.get("subscription") else None
    # v2 retained the literal delimiter representation. Minting an escaped key
    # would bypass an old reservation until a verified alias migration exists.
    if "/" in resource or region is not None and "/" in region:
        raise EconomicScopeReviewRequired("The resource/region identifier is ambiguous in the retained economic key; manual reconciliation is required.")
    if region is None and resource == "aggregate-service":
        raise EconomicScopeReviewRequired("This resource identifier is reserved for the whole-service aggregate remedy; manual reconciliation is required.")
    return "resource-month/" + resource + ("/" + region if region else "")


def vendor_economic_identity(tenant, manifest, overlay, month, version):
    """Resolve a published contract, independent of installation and document version."""
    identity = dict(tenant=tenant, vendor=manifest["vendor"], account=overlay["account"],
                    agreement_id=manifest.get("agreement") or overlay["agreement"],
                    agreement_version=version, service=overlay["product"], month=month,
                    remedy=resource_remedy(manifest, overlay))
    _economic(**identity)
    return identity


def _schema(db):
    db.execute(f"""CREATE TABLE IF NOT EXISTS {TABLE} (
        obligation TEXT NOT NULL, step TEXT NOT NULL CHECK(step IN ('initial','supplement')),
        route TEXT NOT NULL, case_id TEXT NOT NULL, scope TEXT NOT NULL,
        packet_digest TEXT NOT NULL, receipt_id TEXT NOT NULL UNIQUE, at TEXT NOT NULL,
        identity TEXT NOT NULL, PRIMARY KEY(obligation,step))""")
    for operation in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS {TABLE}_no_{operation.lower()}
            BEFORE {operation} ON {TABLE}
            BEGIN SELECT RAISE(ABORT, 'immutable claim reservation'); END""")


def _reserve(db, *, identity, route, case_id, packet_digest, scope, receipt_id, at,
             initial_receipt_id=None, historical=False):
    economic = _economic(**identity)
    key = fingerprint(economic)
    for value in (route, case_id, receipt_id):
        _identity(value)
    at = _instant(at)
    if not isinstance(packet_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", packet_digest):
        raise ValueError("A content-addressed approved packet is required.")
    if not isinstance(scope, dict) or not scope:
        raise ValueError("An explicit approved scope is required.")
    scope_json = _json(scope)
    if initial_receipt_id is not None:
        _identity(initial_receipt_id)
    step = "supplement" if initial_receipt_id is not None else "initial"
    initial = db.execute(f"SELECT route,case_id,scope,packet_digest,receipt_id,at FROM {TABLE} "
                         "WHERE obligation=? AND step='initial'", (key,)).fetchone()
    if initial:
        owner_route, owner_case, original_scope, _, original_receipt, _ = tuple(initial)
        if (owner_route, owner_case) != (route, case_id):
            raise ValueError("This monthly business obligation already belongs to another claim or route.")
        if original_scope != scope_json:
            raise ValueError("Dispatch scope differs from the original business claim.")
        if initial_receipt_id is not None and initial_receipt_id != original_receipt:
            raise ValueError("Supplement must reference the original filing receipt.")
    elif initial_receipt_id is not None:
        raise ValueError("An initial claim must be reserved before any supplement.")
    existing = db.execute(f"SELECT route,case_id,scope,packet_digest,receipt_id,at FROM {TABLE} "
                          "WHERE obligation=? AND step=?", (key, step)).fetchone()
    if existing:
        if (tuple(existing)[:4] != (route, case_id, scope_json, packet_digest)
                or historical and existing[4] != receipt_id):
            raise ValueError("The business obligation already has a different approved packet or receipt for this step.")
        return dict(obligation=key, step=step, receipt_id=existing[4], at=existing[5], created=False)
    db.execute(f"INSERT INTO {TABLE} VALUES(?,?,?,?,?,?,?,?,?)",
               (key, step, route, case_id, scope_json, packet_digest, receipt_id, at, _json(economic)))
    return dict(obligation=key, step=step, receipt_id=receipt_id, at=at, created=True)


def _legacy(payload):
    """Map the supported legacy wire contract, never infer a new agreement."""
    if (_label(payload["vendor"]) != "twilio" or payload["obligation"] != "monthly_api_availability"
            or payload["product"] != "Twilio Messaging API"):
        raise ValueError("Historical legacy agreement requires manual reconciliation.")
    identity = dict(tenant=payload["tenant"], vendor=payload["vendor"], account=payload["account"],
                    agreement_id="twilio-apis", agreement_version=payload["governing_version"],
                    service=payload["product"], month=payload["month"], remedy="availability")
    # Stable approved filing scope; incident times and artifact lists change in a supplement.
    scope = {k: payload[k] for k in ("tenant", "vendor", "account", "product", "region", "month", "channel")}
    return identity, scope


def _v1_key(identity):
    return fingerprint([identity["tenant"], identity["vendor"].casefold(), identity["account"],
                        identity["agreement_id"], identity["agreement_version"], identity["service"].casefold(),
                        identity["month"], identity["remedy"]])


def _receipt(receipt, packet):
    digest = fingerprint(packet)
    if receipt["digest"] != digest or receipt["approval"]["digest"] != digest:
        raise ValueError("Historical receipt does not match its approved packet.")
    return dict(receipt_id=receipt["id"], packet_digest=digest, at=receipt["at"])



def _historical_parent(db, tenant, case_id, scope, state, receipt, reservation):
    from .correspondence_history import receipt_chain

    chain = receipt_chain(state)
    if not chain or chain[1] is not None or len(state["submissions"]) != 1:
        raise ValueError("Historical response requires its single original filing predecessor.")
    original = chain[0]
    packet = receipt["packet"]
    if (reservation[1:3] != ("supplement", "historical-receipt") or receipt["action"] != "submit-response"
            or original["source"] != "vendor" or packet.get("purpose") != "procedural_evidence_only"
            or packet.get("requested") != "0.00" or receipt.get("requested") != "0.00"
            or packet.get("in_reply_to") != original["body"]["receipt_id"]
            or packet.get("original_receipt_digest") != original["digest"]):
        raise ValueError("Historical response does not match its witnessed procedural filing.")
    if (packet["tenant"] != tenant or packet["claim"] != case_id or packet["scope"] != scope
            or original["body"].get("contract_version") not in (None, packet["version"])):
        raise ValueError("Historical response differs from its original scope or governing version.")
    economic = json.loads(reservation[8])
    identity = dict(tenant=tenant, vendor=scope["vendor"], account=scope["account"],
                    agreement_id=packet["agreement_id"], agreement_version=packet["version"],
                    service=scope["service"], month=scope["month"], remedy=economic[-1])
    checked = _receipt(receipt, packet)
    expected = (claim_key(**identity), "supplement", "historical-receipt", case_id, _json(scope),
                checked["packet_digest"], checked["receipt_id"], _instant(checked["at"]), _json(_economic(**identity)))
    if tuple(reservation[:7]) + (_instant(reservation[7]), reservation[8]) != expected:
        raise ValueError("Historical response differs from its approved canonical reservation.")
    digest = fingerprint([tenant, scope, original["body"]["receipt_id"]])
    parent_id = "HIST-" + digest
    parent = db.execute(f"SELECT route,case_id,scope,packet_digest,receipt_id,at,identity FROM {TABLE} "
                        "WHERE obligation=? AND step='initial'", (reservation[0],)).fetchone()
    if (not parent or tuple(parent[:5]) != ("historical-receipt", case_id, _json(scope), digest, parent_id)
            or parent[6] != reservation[8]
            or datetime.fromisoformat(_instant(parent[5])) > datetime.fromisoformat(_instant(receipt["at"]))):
        raise ValueError("Historical response has no matching canonical original reservation.")
    return parent_id


def _backfill(db, tenant):
    """Use stored submissions only. Incomplete/conflicting history closes dispatch.

    No migration-complete flag: receipts appended by an older writer remain visible
    on the next transaction. Both runtime routes still must reserve before sending.
    """
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    old = {}
    if "claim_dispatch_identity" in tables:
        old = {r[6]: tuple(r) for r in db.execute("SELECT obligation,step,route,case_id,scope,packet_digest,receipt_id,at FROM claim_dispatch_identity")}
    migrated = set()
    try:
        legacy = {}
        if "dispute_receipts" in tables:
            for rid, case_id, action, body in db.execute(
                    "SELECT id,case_id,action,body FROM dispute_receipts WHERE tenant=?", (tenant,)):
                r = json.loads(body)
                if r["id"] != rid or r["action"] != action:
                    raise ValueError("Conflicting historical receipt metadata.")
                legacy[rid] = (case_id, r)
        if "dispute_cases" in tables:
            for case_id, raw in db.execute("SELECT id,state FROM dispute_cases WHERE tenant=?", (tenant,)):
                state = json.loads(raw)
                for r in state["submissions"]:
                    saved = legacy.get(r["id"])
                    if saved is not None and saved != (case_id, r):
                        raise ValueError("Historical state and receipt disagree.")
                    legacy[r["id"]] = (case_id, r)
        initial_by_case = {}
        for case_id, r in sorted(legacy.values(), key=lambda item: item[1]["action"] != "submit-claim"):
            payload = r["payload"]
            identity, scope = _legacy(payload)
            if identity["tenant"] != tenant or r["action"] not in {"submit-claim", "submit-response"}:
                raise ValueError("Historical legacy scope is not established.")
            parent = None
            if r["action"] == "submit-response":
                parent = initial_by_case[case_id]
            _reserve(db, identity=identity, route="legacy", case_id=case_id, scope=scope,
                     initial_receipt_id=parent, historical=True, **_receipt(r, payload))
            if parent is None:
                initial_by_case[case_id] = r["id"]
            migrated.add(r["id"])
        if "inbox_claim" in tables:
            for case_id, raw_scope, raw_state in db.execute(
                    "SELECT id,scope,state FROM inbox_claim WHERE tenant=?", (tenant,)):
                scope, state = json.loads(raw_scope), json.loads(raw_state)
                parent = None
                for r in state["submissions"]:
                    packet = r["packet"]
                    if packet["tenant"] != tenant or packet["claim"] != case_id or packet["scope"] != scope:
                        raise ValueError("Historical inbox scope is not established.")
                    existing = db.execute(f"SELECT obligation,step,route,case_id,scope,packet_digest,receipt_id,at,identity "
                                          f"FROM {TABLE} WHERE receipt_id=?", (r["id"],)).fetchone()
                    route = "correspondence"
                    predecessor = parent
                    if existing and existing[2] == "historical-receipt":
                        route = "historical-receipt"
                        predecessor = _historical_parent(db, tenant, case_id, scope, state, r, existing)
                    else:
                        if r["action"] != ("submit-response" if parent else "submit-claim"):
                            raise ValueError("Historical inbox step is not established.")
                        if parent is not None and packet.get("in_reply_to") != parent:
                            raise ValueError("Historical supplement has no matching original receipt.")
                    identity = dict(tenant=tenant, vendor=scope["vendor"], account=scope["account"],
                                    agreement_id=packet["agreement_id"], agreement_version=packet["version"],
                                    service=scope["service"], month=scope["month"], remedy="availability")
                    if existing:
                        identity["remedy"] = json.loads(existing[8])[-1]
                    elif _label(scope["vendor"]) != "twilio":
                        # Older generic packets omitted remedy. Only the old stored
                        # reservation hash can establish which supported remedy it used.
                        candidates = ["availability", "resource-month/" + scope["component"]]
                        matches = [value for value in candidates if r["id"] in old and
                                   _v1_key(identity | {"remedy": value}) == old[r["id"]][0]]
                        if len(matches) != 1:
                            raise ValueError("Historical remedy is unknown; manual reconciliation required.")
                        identity["remedy"] = matches[0]
                    checked = _receipt(r, packet)
                    if existing:
                        expected = (claim_key(**identity), "supplement" if predecessor else "initial", route,
                                    case_id, _json(scope), checked["packet_digest"], checked["receipt_id"],
                                    _instant(checked["at"]), _json(_economic(**identity)))
                        if tuple(existing[:7]) + (_instant(existing[7]), existing[8]) != expected:
                            raise ValueError("Canonical inbox reservation and approved receipt disagree.")
                    _reserve(db, identity=identity, route=route, case_id=case_id, scope=scope,
                             initial_receipt_id=predecessor, historical=True, **checked)
                    if r["id"] in old:
                        row = old[r["id"]]
                        expected = (_v1_key(identity), "supplement" if parent else "initial", "correspondence",
                                    case_id, _json(scope), r["digest"], r["id"])
                        if row[:7] != expected or _instant(row[7]) != _instant(r["at"]):
                            raise ValueError("Historical reservation and receipt disagree.")
                    parent = parent or r["id"]
                    migrated.add(r["id"])
        for rid, row in old.items():
            if rid not in migrated:
                # v1 has no tenant column. An unattributable row cannot be safely ignored.
                row_scope = json.loads(row[4])
                if row_scope.get("tenant") not in (None, tenant):
                    continue
                if row[2] == "correspondence" and "inbox_claim" in tables:
                    owners = [owner for owner, raw_scope in db.execute(
                        "SELECT tenant,scope FROM inbox_claim WHERE id=?", (row[3],))
                        if json.loads(raw_scope) == row_scope]
                    if owners and all(owner != tenant for owner in owners):
                        continue
                raise ValueError("Unresolved historical reservation requires manual reconciliation.")
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        raise ValueError("Incomplete historical claim evidence requires manual reconciliation.") from error


def reserve_claim(db, *, tenant, vendor, account, agreement_id, agreement_version, service, month,
                  remedy, route, case_id, packet_digest, scope, receipt_id, at, initial_receipt_id=None):
    """Reserve initial filing or one supplement in the caller's write transaction.

    Exact retry returns the original reservation. ``created=False`` is not a new
    transport authorization. Unknown delivery must retain ownership for manual
    reconciliation; this registry intentionally has no release operation.
    """
    if not db.in_transaction:
        raise ValueError("Dispatch reservation requires the caller's active transaction.")
    identity = dict(tenant=tenant, vendor=vendor, account=account, agreement_id=agreement_id,
                    agreement_version=agreement_version, service=service, month=month, remedy=remedy)
    _economic(**identity)
    _schema(db)
    _backfill(db, tenant)
    return _reserve(db, identity=identity, route=route, case_id=case_id, packet_digest=packet_digest,
                    scope=scope, receipt_id=receipt_id, at=at, initial_receipt_id=initial_receipt_id)


def reserve_legacy_claim(db, *, ticket, case_id, receipt_id, at, initial_receipt_id=None):
    """Legacy hook, after approval validation and before the pure local simulator."""
    identity, scope = _legacy(asdict(ticket))
    return reserve_claim(db, **identity, route="legacy", case_id=case_id, packet_digest=ticket.digest,
                         scope=scope, receipt_id=receipt_id, at=at, initial_receipt_id=initial_receipt_id)
