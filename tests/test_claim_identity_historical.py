"""A witnessed original and zero-dollar response keep their canonical reservation during backfill."""
from datetime import timedelta
import json
import sqlite3

import pytest

from uptime.claim_identity import TABLE, reserve_claim
from uptime.contracts import fingerprint
from uptime.storage import database
from test_claim_identity import BASE
from test_correspondence_resource import env, install, reports, deliver


def historical_db(*, requested="0.00", purpose="procedural_evidence_only"):
    db = sqlite3.connect(":memory:")
    db.execute("BEGIN IMMEDIATE")
    scope = {"vendor":"Example","account":"buyer","contract":"terms","service":"API","component":"station",
             "region":"global","incident":"loss","currency":"USD","month":"2026-06"}
    original = {"kind":"original_filing_receipt","source":"vendor","digest":fingerprint({"vendor receipt":1}),
                "body":{"receipt_id":"vendor-original"}}
    original_digest = fingerprint([BASE["tenant"],scope,original["body"]["receipt_id"]])
    identity = {**BASE,"vendor":scope["vendor"],"account":scope["account"],"agreement_id":scope["contract"],
                "service":scope["service"],"month":scope["month"],"remedy":"resource-month/station",
                "route":"historical-receipt","case_id":"historical","scope":scope}
    first = identity | {"receipt_id":"HIST-"+original_digest,"packet_digest":original_digest}
    reserve_claim(db,**first)
    packet = {"tenant":BASE["tenant"],"claim":"historical","scope":scope,"agreement_id":"terms","version":"v1",
              "purpose":purpose,"requested":requested,"in_reply_to":"vendor-original",
              "original_receipt_digest":original["digest"]}
    receipt = {"id":"LOCAL-response","action":"submit-response","packet":packet,"at":BASE["at"],
               "digest":fingerprint(packet),"approval":{"digest":fingerprint(packet)},"requested":requested}
    reserve_claim(db,**(identity | {"receipt_id":receipt["id"],"packet_digest":receipt["digest"],
                                   "initial_receipt_id":first["receipt_id"]}))
    state = {"submissions":[receipt],"evidence":[original]}
    db.execute("CREATE TABLE inbox_claim(tenant TEXT,id TEXT,scope TEXT,state TEXT)")
    db.execute("INSERT INTO inbox_claim VALUES(?,?,?,?)",(BASE["tenant"],"historical",json.dumps(scope),json.dumps(state)))
    return db, identity, state


def test_unrelated_reservations_preserve_historical_owner_and_never_mint_a_second_claim():
    db, identity, state = historical_db()
    with db:
        original = list(db.execute(f"SELECT * FROM {TABLE} ORDER BY step"))
        for i in range(3):
            assert reserve_claim(db,**(BASE | {"account":f"unrelated-{i}","case_id":f"new-{i}","receipt_id":f"receipt-{i}"}))["created"]
        assert list(db.execute(f"SELECT * FROM {TABLE} WHERE route='historical-receipt' ORDER BY step")) == original
        assert [(r[1],r[2]) for r in original] == [("initial","historical-receipt"),("supplement","historical-receipt")]
        for change in ({"route":"correspondence"},{"case_id":"financial-copy"},{"agreement_version":"new-version"}):
            with pytest.raises(ValueError):
                reserve_claim(db,**(identity | change | {"receipt_id":"financial-copy","packet_digest":fingerprint({"request":"12.00"})}))



@pytest.mark.parametrize("requested,purpose", [("0.01","procedural_evidence_only"), ("12.00","procedural_evidence_only"),
                                               ("0.00","financial_claim")])
def test_matching_approved_packet_and_reservation_cannot_uplift_a_procedural_response(requested,purpose):
    db,identity,state = historical_db(requested=requested,purpose=purpose)
    with db:
        packet = state["submissions"][0]["packet"]
        assert db.execute(f"SELECT packet_digest FROM {TABLE} WHERE step='supplement'").fetchone()[0] == fingerprint(packet)
        with pytest.raises(ValueError,match="procedural"):
            reserve_claim(db,**BASE)
        assert db.execute(f"SELECT count(*) FROM {TABLE} WHERE route='legacy'").fetchone()[0] == 0


@pytest.mark.parametrize("damage", ["request","receipt_request","purpose","reply","original_digest","original_source","original_id",
                                    "action","time","scope","orphan","initial_route","initial_digest","initial_case",
                                    "reservation_step","reservation_route","reservation_time","reservation_identity"])
def test_changed_historical_chain_cannot_open_unrelated_reservation(damage):
    db,identity,state = historical_db()
    r = state["submissions"][0]
    packet = r["packet"]
    if damage=="request": packet["requested"]="12.00"
    elif damage=="receipt_request": r["requested"]="12.00"
    elif damage=="purpose": packet["purpose"]="financial_claim"
    elif damage=="reply": packet["in_reply_to"]="different"
    elif damage=="original_digest": packet["original_receipt_digest"]="0"*64
    elif damage=="original_source": state["evidence"][0]["source"]="customer"
    elif damage=="original_id": state["evidence"][0]["body"]["receipt_id"]="other"
    elif damage=="action": r["action"]="submit-claim"
    elif damage=="time": r["at"]="2026-11-03T10:00:00Z"
    elif damage=="scope": packet["scope"]={**identity["scope"],"account":"other"}
    else:
        db.execute(f"DROP TRIGGER {TABLE}_no_update")
        db.execute(f"DROP TRIGGER {TABLE}_no_delete")
        if damage=="orphan": db.execute(f"DELETE FROM {TABLE} WHERE step='initial'")
        else:
            column,value,step = {
                "initial_route":("route","correspondence","initial"),"initial_digest":("packet_digest","a"*64,"initial"),
                "initial_case":("case_id","another-case","initial"),"reservation_step":("step","initial","supplement"),
                "reservation_route":("route","correspondence","supplement"),
                "reservation_time":("at","2026-11-03T10:00:00Z","supplement"),
                "reservation_identity":("identity",'["invalid"]',"supplement")}[damage]
            if damage=="reservation_step": db.execute(f"DELETE FROM {TABLE} WHERE step='initial'")
            db.execute(f"UPDATE {TABLE} SET {column}=? WHERE step=?",(value,step))
    db.execute("UPDATE inbox_claim SET state=?",(json.dumps(state),))
    with pytest.raises(ValueError):
        reserve_claim(db,**BASE)
    assert db.execute(f"SELECT count(*) FROM {TABLE} WHERE route='legacy'").fetchone()[0] == 0
    db.close()


def test_signed_procedural_response_survives_backfill_for_an_independent_reservation(env,tmp_path,monkeypatch):
    from test_vendor_resource_operators import EXTENSION, readings
    install(env,tmp_path,monkeypatch,extra_terms=EXTENSION,shadow=readings(),expected="10.44")
    rows = reports()
    rows[0][1]["complete"] = rows[1][1]["complete"] = False
    original = {"kind":"original_filing_receipt","receipt_id":"original-regression","source_ref":"vendor-observed",
                "received_at":"2026-07-02T12:30:00Z","observed_at":env.now.isoformat(),
                "submitted_to":"claims@example.invalid","fields":[{"name":"station identifier","refs":[env.scope["component"]]}]}
    deliver(env,[("vendor-fixture",original),("customer-fixture",rows[3][1])])
    deliver(env,[("vendor-fixture",{"kind":"message","receipt_id":original["receipt_id"],
        "text":"Our desk cannot complete review without the station logs. Please supply log references."})])
    deliver(env,rows[:2])
    env.action("approve-response")
    env.now += timedelta(days=1)
    submitted = env.action("submit-response")
    response = submitted["submissions"][0]
    assert response["requested"] == "0.00"
    with database(env.app.state.bench.path) as db,db:
        db.execute("BEGIN IMMEDIATE")
        old = [tuple(r) for r in db.execute(f"SELECT * FROM {TABLE} WHERE route='historical-receipt' ORDER BY step")]
        assert reserve_claim(db,**BASE)["created"]
        assert [tuple(r) for r in db.execute(f"SELECT * FROM {TABLE} WHERE route='historical-receipt' ORDER BY step")] == old
    assert [r[1] for r in old] == ["initial","supplement"]
    assert old[0][6] == "HIST-"+fingerprint([BASE["tenant"],env.scope,original["receipt_id"]])
    assert old[1][6] == response["id"]
    assert env.read()["submissions"] == submitted["submissions"]
    assert env.read()["ledger"]["claimed"] == env.read()["ledger"]["awarded"] == "0.00"
