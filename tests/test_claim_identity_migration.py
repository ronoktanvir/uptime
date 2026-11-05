"""Synthetic historical receipts test migration safety, never financial entitlement."""
from copy import deepcopy
import json
import sqlite3

import pytest

from uptime.claim_identity import TABLE, claim_key, reserve_claim
from uptime.contracts import fingerprint
from test_claim_identity import BASE

IDENTITY_FIELDS = ("tenant", "vendor", "account", "agreement_id", "agreement_version", "service", "month", "remedy")


def test_version_timezone_and_cosmetic_labels_do_not_mint_a_right(tmp_path):
    path = tmp_path / "claims.db"
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        first = reserve_claim(db, **BASE)
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        changed = BASE | dict(agreement_version="2027-republished", vendor="TWILIO", service="twilio messaging api",
                             at="2026-11-01T22:00:00-12:00", receipt_id="unused-retry-id")
        assert reserve_claim(db, **changed) == first | {"created": False}
        with pytest.raises(ValueError, match="another claim or route"):
            reserve_claim(db, **(changed | dict(route="correspondence", case_id="newer-version")))
        assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 1


@pytest.mark.parametrize("field,value", [("tenant", "other-business"), ("vendor", "Other Vendor"),
    ("account", "independent-customer"), ("agreement_id", "independent-agreement"), ("month", "2026-11"),
    ("service", "Other API"), ("remedy", "resource-month/station-b")])
def test_independent_business_scope_and_fee_period_are_not_suppressed(field, value):
    with sqlite3.connect(":memory:") as db:
        db.execute("BEGIN IMMEDIATE")
        first = reserve_claim(db, **BASE)
        second = reserve_claim(db, **(BASE | {field: value, "receipt_id": "r-2"}))
        assert first["obligation"] != second["obligation"] and second["created"]


@pytest.mark.parametrize("field,value", [("tenant", "bears\x00other"), ("account", "acct\n1"),
    ("agreement_version", ""), ("month", "0000-01"), ("month", "２０２６-10"),
    ("at", "2026-11-02T10:00:00"), ("initial_receipt_id", ""), ("packet_digest", None), ("scope", {})])
def test_invalid_identity_fails_closed(field, value):
    with sqlite3.connect(":memory:") as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError):
            reserve_claim(db, **(BASE | {field: value}))
        if db.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TABLE,)).fetchone():
            assert db.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0] == 0


def test_label_unicode_normalization_preserves_opaque_account_identity():
    identity = {k: BASE[k] for k in IDENTITY_FIELDS}
    assert claim_key(**(identity | {"vendor": "Caf\u00e9"})) == claim_key(**(identity | {"vendor": "Cafe\u0301"}))
    assert claim_key(**(identity | {"account": "ACCOUNT"})) != claim_key(**(identity | {"account": "account"}))


def history(db, *, generic=False, version="2026-04-09"):
    scope = dict(account=BASE["account"], vendor="Other Vendor" if generic else "Twilio", contract="private-alias",
                 service=BASE["service"], component="station-A", month=BASE["month"], region="west",
                 invoice="invoice-a", incident="incident-a", currency="USD")
    packet = dict(tenant=BASE["tenant"], claim="old-inbox", scope=scope,
                  agreement_id=BASE["agreement_id"], version=version)
    digest = fingerprint(packet)
    receipt = dict(id="historic-receipt", action="submit-claim", at=BASE["at"], digest=digest,
                   approval={"digest": digest}, packet=packet)
    db.execute("CREATE TABLE inbox_claim (tenant TEXT,id TEXT,scope TEXT,state TEXT)")
    db.execute("INSERT INTO inbox_claim VALUES(?,?,?,?)",
               (BASE["tenant"], "old-inbox", json.dumps(scope), json.dumps({"submissions": [receipt]})))
    return scope, receipt


def v1(db, scope, receipt, *, remedy="availability"):
    db.execute("""CREATE TABLE claim_dispatch_identity (obligation TEXT,step TEXT,route TEXT,case_id TEXT,
               scope TEXT,packet_digest TEXT,receipt_id TEXT,at TEXT)""")
    p = receipt["packet"]
    old_key = fingerprint([p["tenant"], scope["vendor"].casefold(), scope["account"], p["agreement_id"], p["version"],
                           scope["service"].casefold(), scope["month"], remedy])
    db.execute("INSERT INTO claim_dispatch_identity VALUES(?,?,?,?,?,?,?,?)",
               (old_key, "initial", "correspondence", p["claim"], json.dumps(scope, sort_keys=True, separators=(",", ":")),
                receipt["digest"], receipt["id"], receipt["at"]))


def test_v1_backfill_is_additive_and_blocks_version_bypass(tmp_path):
    path = tmp_path / "history.db"
    with sqlite3.connect(path) as db:
        scope, receipt = history(db)
        v1(db, scope, receipt)
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="another claim or route"):
            reserve_claim(db, **(BASE | dict(agreement_version="2027-new")))
        row = db.execute(f"SELECT receipt_id,identity FROM {TABLE}").fetchone()
        assert row[0] == receipt["id"] and "2026-04-09" not in row[1]
        assert db.execute("SELECT count(*) FROM claim_dispatch_identity").fetchone()[0] == 1
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="another claim or route"):
            reserve_claim(db, **BASE)
        for command in (f"DELETE FROM {TABLE}", f"UPDATE {TABLE} SET receipt_id='new'"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(command)


def test_generic_history_needs_provable_remedy_and_keeps_resource_scope():
    with sqlite3.connect(":memory:") as db:
        scope, r = history(db, generic=True)
        with pytest.raises(ValueError, match="remedy is unknown"):
            reserve_claim(db, **BASE)
        v1(db, scope, r, remedy="resource-month/station-A")
        assert reserve_claim(db, **(BASE | dict(vendor="Other Vendor", remedy="resource-month/station-B")))["created"]
        with pytest.raises(ValueError, match="another claim or route"):
            reserve_claim(db, **(BASE | dict(vendor="Other Vendor", remedy="resource-month/station-A")))


@pytest.mark.parametrize("damage", ["missing_packet", "changed_digest", "missing_approval", "different_tenant",
                                    "two_initials", "unknown_action", "changed_scope", "orphan_supplement"])
def test_incomplete_or_conflicting_submissions_never_open_reservation(damage):
    with sqlite3.connect(":memory:") as db:
        scope, r = history(db)
        rows = [r]
        if damage == "missing_packet":
            r.pop("packet")
        elif damage == "changed_digest":
            r["digest"] = "0" * 64
        elif damage == "missing_approval":
            r.pop("approval")
        elif damage == "different_tenant":
            r["packet"]["tenant"] = "other"
        elif damage == "two_initials":
            rows.append(deepcopy(r) | {"id": "duplicate"})
        elif damage == "unknown_action":
            r["action"] = "unknown"
        elif damage == "changed_scope":
            r["packet"]["scope"] = scope | {"account": "other"}
        else:
            r["action"] = "submit-response"
        db.execute("UPDATE inbox_claim SET state=?", (json.dumps({"submissions": rows}),))
        with pytest.raises(ValueError):
            reserve_claim(db, **BASE)
        assert db.execute(f"SELECT count(*) FROM {TABLE} WHERE route='legacy'").fetchone()[0] == 0


def test_unattributable_v1_reservation_blocks_new_dispatch():
    with sqlite3.connect(":memory:") as db:
        scope, receipt = history(db)
        v1(db, scope, receipt)
        db.execute("DELETE FROM inbox_claim")
        with pytest.raises(ValueError, match="Unresolved historical"):
            reserve_claim(db, **BASE)


def test_rollback_leaves_no_partial_reservation(tmp_path):
    path = tmp_path / "atomic.db"
    with pytest.raises(RuntimeError):
        with sqlite3.connect(path) as db:
            db.execute("BEGIN IMMEDIATE")
            reserve_claim(db, **BASE)
            raise RuntimeError("Synthetic crash before local outbox commit")
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        assert reserve_claim(db, **(BASE | dict(route="correspondence", receipt_id="after-rollback")))["created"]


def test_other_tenant_v1_history_does_not_block_independent_business():
    with sqlite3.connect(":memory:") as db:
        scope, receipt = history(db)
        v1(db, scope, receipt)
        assert reserve_claim(db, **(BASE | dict(tenant="independent-business")))["created"]


def test_historical_double_filing_is_quarantined_instead_of_picking_a_winner():
    with sqlite3.connect(":memory:") as db:
        scope, r = history(db)
        duplicate = deepcopy(r)
        duplicate["id"] = "other-receipt"
        duplicate["packet"]["claim"] = "other-case"
        duplicate["digest"] = fingerprint(duplicate["packet"])
        duplicate["approval"]["digest"] = duplicate["digest"]
        db.execute("INSERT INTO inbox_claim VALUES(?,?,?,?)",
                   (BASE["tenant"], "other-case", json.dumps(scope), json.dumps({"submissions": [duplicate]})))
        with pytest.raises(ValueError, match="another claim or route"):
            reserve_claim(db, **(BASE | dict(account="new-account")))
        assert db.execute(f"SELECT count(*) FROM {TABLE} WHERE route='legacy'").fetchone()[0] == 0
