"""Cross-route economic claim identity. All writes use the caller's transaction.

Account and agreement IDs must already be resolved by trusted server bindings.
Human-readable vendor/service labels are case-folded. Opaque IDs stay exact.
Customer contract aliases, invoice/incident/component/case IDs are not economic
identity fields. Historical transport receipts must be backfilled before enabling
a second route on a pre-V4 database.
"""
import json
import re

from .contracts import fingerprint


def _identity(value):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Canonical nonempty identity required.")
    return value


def claim_key(*, tenant, vendor, account, agreement_id, agreement_version, service, month, remedy):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", _identity(month)):
        raise ValueError("Canonical service month required.")
    return fingerprint([_identity(tenant), _identity(vendor).casefold(), _identity(account),
                        _identity(agreement_id), _identity(agreement_version), _identity(service).casefold(),
                        month, _identity(remedy)])


def reserve_claim(db, *, tenant, vendor, account, agreement_id, agreement_version, service, month,
                  remedy, route, case_id, packet_digest, scope, receipt_id, at, initial_receipt_id=None):
    """Reserve one initial filing and one scoped supplement within a write transaction.

    An exact retry returns its original reservation. A case/route alias fails
    before the caller hands any content to a local or external transport.
    """
    if not db.in_transaction:
        raise ValueError("Dispatch reservation requires the caller's active transaction.")
    key = claim_key(tenant=tenant, vendor=vendor, account=account, agreement_id=agreement_id,
                    agreement_version=agreement_version, service=service, month=month, remedy=remedy)
    for value in (route, case_id, receipt_id, at):
        _identity(value)
    if not re.fullmatch(r"[0-9a-f]{64}", packet_digest):
        raise ValueError("A content-addressed approved packet is required.")
    scope_json = json.dumps(scope, sort_keys=True, separators=(",", ":"), allow_nan=False)
    db.execute("""CREATE TABLE IF NOT EXISTS claim_dispatch_identity (
        obligation TEXT NOT NULL, step TEXT NOT NULL, route TEXT NOT NULL, case_id TEXT NOT NULL,
        scope TEXT NOT NULL, packet_digest TEXT NOT NULL, receipt_id TEXT NOT NULL, at TEXT NOT NULL,
        PRIMARY KEY(obligation,step), UNIQUE(receipt_id))""")
    initial = db.execute("SELECT route,case_id,scope,packet_digest,receipt_id,at FROM claim_dispatch_identity WHERE obligation=? AND step='initial'",
                         (key,)).fetchone()
    step = "supplement" if initial_receipt_id else "initial"
    if initial:
        owner_route, owner_case, original_scope, _, original_receipt, _ = tuple(initial)
        if (owner_route, owner_case) != (route, case_id):
            raise ValueError("This monthly business obligation already belongs to another claim or route.")
        if original_scope != scope_json:
            raise ValueError("Dispatch scope differs from the original business claim.")
        if initial_receipt_id and initial_receipt_id != original_receipt:
            raise ValueError("Supplement must reference the original filing receipt.")
    elif initial_receipt_id:
        raise ValueError("An initial claim must be reserved before any supplement.")
    existing = db.execute("SELECT route,case_id,scope,packet_digest,receipt_id,at FROM claim_dispatch_identity WHERE obligation=? AND step=?",
                          (key, step)).fetchone()
    if existing:
        if tuple(existing)[:4] != (route, case_id, scope_json, packet_digest):
            raise ValueError("The business obligation already has a different approved packet for this step.")
        return dict(obligation=key, step=step, receipt_id=existing[4], at=existing[5], created=False)
    db.execute("INSERT INTO claim_dispatch_identity VALUES(?,?,?,?,?,?,?,?)",
               (key, step, route, case_id, scope_json, packet_digest, receipt_id, at))
    return dict(obligation=key, step=step, receipt_id=receipt_id, at=at, created=True)
