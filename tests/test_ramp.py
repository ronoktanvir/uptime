import json
from decimal import Decimal
from uuid import uuid4

import pytest

from uptime.ramp import (FIXTURES, ORIGIN, WRITE_SCOPES, FixtureRampProvider, RampError,
                         SandboxRampProvider, Token, capture, money, ramp_snapshot, verify_draft)


def token(scopes=WRITE_SCOPES):
    return Token("unused", frozenset(scopes), frozenset(scopes))


def test_exact_origin_required(monkeypatch):
    monkeypatch.setenv("RAMP_ENV", "sandbox")
    for wrong in ("https://api.ramp.com", ORIGIN + "@another.test", ORIGIN + "/", ORIGIN + ":444"):
        monkeypatch.setenv("RAMP_BASE_URL", wrong)
        with pytest.raises(RampError): SandboxRampProvider._guard()
    monkeypatch.setenv("RAMP_BASE_URL", ORIGIN)
    monkeypatch.delenv("RAMP_ENV")
    with pytest.raises(RampError): SandboxRampProvider._guard()


def test_transport_refuses_redirect_without_second_request(monkeypatch):
    calls = []
    class Redirect:
        status = 307
        def __init__(self, host, timeout): calls.append(host)
        def request(self, *args): pass
        def getresponse(self): return self
        def close(self): pass

    monkeypatch.setenv("RAMP_ENV", "sandbox")
    monkeypatch.setenv("RAMP_BASE_URL", ORIGIN)
    monkeypatch.setattr("uptime.ramp.http.client.HTTPSConnection", Redirect)
    with pytest.raises(RampError, match="307"):
        SandboxRampProvider.__new__(SandboxRampProvider)._http("GET", "bills", {})
    assert calls == ["demo-api.ramp.com"]


def test_public_read_surface_rejects_mutation_and_other_origins():
    client = SandboxRampProvider.__new__(SandboxRampProvider)
    for method, path in [("GET", "https://elsewhere.test/path"), ("PATCH", "bills/drafts/" + str(uuid4())),
                         ("POST", "bills"), ("GET", "vendors/credits")]:
        with pytest.raises(RampError):
            client.request(token(), method, path)


def test_sanitized_snapshot_and_fixture_are_distinct():
    proof = ramp_snapshot()
    assert proof["mode"] == "saved sandbox observation"
    assert {b["id"] for b in proof["bills"]} == set(proof["capabilities"]["bills"]["readback_ids"])
    assert all("LIVE_RAMP_SANDBOX" in b["sources"] for b in proof["bills"])
    offline = FixtureRampProvider().snapshot()
    assert "LIVE_RAMP_SANDBOX" not in json.dumps(offline)
    assert "Bearer " not in (FIXTURES / "verified.json").read_text()
    assert proof["origin"] == ORIGIN


class FakeProvider:
    def __init__(self):
        self.posts = self.patches = 0
        self.row = None
        self.lose_create_reply = self.lose_update_reply = False
        self.bad_read = False

    def _draft_mutation(self, tok, ident, data):
        if ident is None:
            self.posts += 1
            self.row = {"id": str(uuid4()), "vendor": {"id": data["vendor_id"]}, "status": "DRAFT",
                        "amount": {"currency_code": "USD", "amount": 3750000, "minor_unit_conversion_rate": 100},
                        "remote_id": data["remote_id"], "invoice_number": data["invoice_number"]}
            if self.lose_create_reply:
                raise RampError("Connection lost")
        else:
            assert ident == self.row["id"]
            self.patches += 1
            self.row["memo"] = data["memo"]
            if self.lose_update_reply:
                raise RampError("Connection lost")
        return self.row.copy()

    def request(self, tok, method, path):
        assert method == "GET" and path.endswith(self.row["id"])
        row = self.row.copy()
        if self.bad_read: row["invoice_number"] = "unrelated"
        return row


def test_verified_draft_replay_and_ambiguous_updates(tmp_path):
    vendor = str(uuid4())
    provider = FakeProvider()
    provider.lose_update_reply = True
    with pytest.raises(RampError): verify_draft(provider, token(), tmp_path / "ops", vendor)
    first = verify_draft(provider, token(), tmp_path / "ops", vendor)
    assert verify_draft(provider, token(), tmp_path / "ops", vendor)["id"] == first["id"]
    assert (provider.posts, provider.patches) == (1, 1)
    assert "tag" in first and first["status"] == "DRAFT"


def test_ambiguous_create_is_never_retried(tmp_path):
    p = FakeProvider()
    p.lose_create_reply = True
    vendor = str(uuid4())
    for _ in range(2):
        with pytest.raises(RampError): verify_draft(p, token(), tmp_path / "ops", vendor)
    assert (p.posts, p.patches) == (1, 0)


def test_wrong_draft_identity_blocks_update(tmp_path):
    p = FakeProvider()
    p.bad_read = True
    with pytest.raises(RampError): verify_draft(p, token(), tmp_path / "ops", str(uuid4()))
    assert (p.posts, p.patches) == (1, 0)


@pytest.mark.parametrize("granted", [{"bills:read"}, WRITE_SCOPES | {"vendors:write"}])
def test_mismatched_scope_capture_stops_write(tmp_path, granted):
    class Narrow:
        def token(self, scopes):
            return Token("unused", frozenset(granted if scopes == WRITE_SCOPES else scopes),
                         frozenset(scopes))
        def request(self, tok, method, path, query):
            assert method == "GET"
            return {"data": [], "page": {"next": None}}
    proof = capture(Narrow(), True, tmp_path / "ops")
    assert proof["draft"] is None
    assert proof["capabilities"]["draft_write"]["state"] == "SCOPE_MISMATCH"
    assert not (tmp_path / "ops").exists()


def test_minor_units_never_use_a_float():
    val = {"currency_code": "USD", "amount": 48128, "minor_unit_conversion_rate": 100}
    assert money(val)["amount"] == "481.28"
    for bad in (Decimal("1.5"), None):
        with pytest.raises(RampError): money({**val, "minor_unit_conversion_rate": bad})
