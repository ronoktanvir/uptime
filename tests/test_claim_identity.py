import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from uptime.claim_identity import reserve_claim
from uptime.contracts import fingerprint

BASE = dict(tenant="bears", vendor="Twilio", account="acct-1", agreement_id="twilio-apis", agreement_version="2026-04-09",
            service="Twilio Messaging API", month="2026-10", remedy="availability",
            route="legacy", case_id="old", packet_digest=fingerprint({"packet":1}),
            scope={"incident":"abc", "invoice":"i-1"}, receipt_id="r-1", at="2026-11-02T10:00:00Z")


def test_cross_route_aliases_retry_supplement_and_restart(tmp_path):
    path = tmp_path / "claims.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        first = reserve_claim(db, **BASE)
        assert first["created"]
    with sqlite3.connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        assert not reserve_claim(db, **BASE)["created"]
        for change in ({"route":"correspondence"}, {"case_id":"copy"}, {"scope":{"incident":"different"}},
                       {"packet_digest":fingerprint({"different":True})}):
            with pytest.raises(ValueError):
                reserve_claim(db, **(BASE | change))
        supplement = BASE | dict(receipt_id="r-2", initial_receipt_id="r-1", packet_digest=fingerprint({"packet":2}))
        assert reserve_claim(db, **supplement)["created"]
        assert not reserve_claim(db, **supplement)["created"]
        with pytest.raises(ValueError):
            reserve_claim(db, **(supplement | dict(receipt_id="r-3", packet_digest=fingerprint({"packet":3}))))
    assert first["obligation"]


def test_concurrent_routes_have_one_owner(tmp_path):
    path = tmp_path / "claims.sqlite"
    def run(index):
        try:
            with sqlite3.connect(path, timeout=10) as db:
                db.execute("BEGIN IMMEDIATE")
                return reserve_claim(db, **(BASE | dict(route="route-"+str(index),receipt_id="receipt-"+str(index))))
        except ValueError:
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(run, range(8)))
    assert sum(r is not None for r in result) == 1


def test_registry_requires_transaction_and_canonical_ids():
    with sqlite3.connect(":memory:") as db:
        with pytest.raises(ValueError):
            reserve_claim(db, **BASE)
        db.execute("BEGIN")
        with pytest.raises(ValueError):
            reserve_claim(db, **(BASE | {"account":" acct-1"}))
