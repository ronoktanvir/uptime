"""Synthetic readback of a human-posted Ramp bill note.

The real SandboxRampProvider token/request gates run over a fake transport. No
credentials, network, captures or provider writes. Every credential value is fake.
"""
import copy
import importlib.util
import json
import os
import stat
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from uptime.ramp import ORIGIN, RampError, RampHTTPError, SandboxRampProvider

ROOT = Path(__file__).resolve().parents[1]


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_ramp_comment", ROOT / "scripts/verify_ramp_comment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vrc = _load_script()


def uid(n):
    return str(UUID(int=n))


BUSINESS, OTHER_BUSINESS = uid(500), uid(501)
BILL, OTHER_BILL = uid(10), uid(11)
USER, OTHER_USER = uid(26), uid(27)
URL = "https://demo.ramp.com/bill-pay/bills/list/" + BILL
NOTE = ("Uptime review: governing agreement or usage evidence is missing for this bill. "
        "Unable to verify charges against contract terms. Please attach the signed agreement "
        "or usage records.")
WHEN = "2026-11-01T12:00:00+00:00"
FAKE_BASIC = "RkFLRS1JRDpGQUtFLVNFQ1JFVA=="  # base64("FAKE-ID:FAKE-SECRET")
SECRETS = ("PRIVATE", "FAKE-TOKEN", FAKE_BASIC, "FAKE-SECRET")
COMMENTS = "comments/bills/" + BILL


def comment(ident, message=NOTE, created=WHEN, user=USER):
    return {"id": ident, "message": message, "created_at": created, "user_id": user}


def next_url(start, path=COMMENTS):
    return f"{ORIGIN}/developer/v1/{path}?start={start}"


def page(rows, start=None):
    return {"data": rows, "page": {"next": None if start is None else next_url(start)}}


def token_value(scope):
    return "FAKE-TOKEN-" + scope.replace(":", "-")


class FakeRamp:
    """Transport behind the real provider. Records everything and allows only reads."""

    def __init__(self):
        self.business = [BUSINESS]  # successive /business answers; the last one repeats
        self.bill = {"id": BILL, "status": "OPEN", "memo": "PRIVATE MEMO"}
        self.passes = [{None: page([comment("c-note")])}]  # per full listing: cursor -> response
        self.grants = {}
        self.errors = {}
        self.calls, self.token_requests = [], []
        self._business_reads, self._pass = 0, -1

    def http(self, method, path, headers, body=None):
        parts = urlsplit("/" + path)
        route = parts.path[1:]
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        self.calls.append((method, route, query))
        if (method, route) == ("POST", "token"):
            assert headers["Authorization"] == "Basic " + FAKE_BASIC
            scope = parse_qs(body)["scope"][0]
            self.token_requests.append(scope)
            return {"access_token": token_value(scope), "token_type": "bearer",
                    "scope": self.grants.get(scope, scope)}
        assert method == "GET" and body is None, "provider mutation attempted"
        if route in self.errors:
            raise self.errors[route]
        if route == "business":
            assert headers["Authorization"] == "Bearer " + token_value("business:read")
            value = self.business[min(self._business_reads, len(self.business) - 1)]
            self._business_reads += 1
            return {"id": value, "business_name_legal": "PRIVATE BUSINESS"}
        assert headers["Authorization"] == "Bearer " + token_value("bills:read")
        if route == "bills/" + BILL:
            return copy.deepcopy(self.bill)
        if route == COMMENTS:
            if "start" not in query:
                self._pass += 1
            listing = self.passes[min(self._pass, len(self.passes) - 1)]
            return copy.deepcopy(listing[query.get("start")])
        raise AssertionError("route outside the readback surface")

    def comment_calls(self):
        return [c for c in self.calls if c[1].startswith("comments/")]


def provider_for(fake):
    provider = SandboxRampProvider.__new__(SandboxRampProvider)
    provider._basic = FAKE_BASIC
    provider.client_fingerprint = "0" * 64
    provider._http = fake.http
    provider._draft_mutation = lambda *a, **k: pytest.fail("provider write procedure invoked")
    return provider


def run(fake, **kwargs):
    return vrc.verify_comment(provider_for(fake), business_id=BUSINESS, bill_url=URL, **kwargs)


def assert_read_only(fake):
    allowed = {("POST", "token"), ("GET", "business"), ("GET", "bills/" + BILL), ("GET", COMMENTS)}
    assert {(m, r) for m, r, _ in fake.calls} <= allowed
    assert set(fake.token_requests) <= {"business:read", "bills:read"}


def assert_no_secrets(text):
    for secret in SECRETS:
        assert secret not in text


def assert_no_comment_claim(receipt):
    assert receipt["comment_id"] is receipt["body"] is receipt["created_at"] is receipt["author_user_id"] is None
    assert receipt["write_attempted"] is receipt["api_write_proven"] is receipt["authorship_proven"] is False
    assert receipt["actual_money_recovered"] is None


# --- verification -----------------------------------------------------------------------

def test_verified_two_complete_reads_and_minimal_receipt():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-other", "PRIVATE unrelated discussion", user=OTHER_USER),
                                comment("c-note", created="2026-11-01T07:00:00-05:00")])}]
    receipt = run(fake)
    assert {k: v for k, v in receipt.items() if k not in {"observed_at", "note", "origin", "evidence"}} == {
        "schema": "uptime-human-ramp-note-readback/1", "status": "VERIFIED_READBACK",
        "business_id": BUSINESS, "bill_id": BILL, "comment_id": "c-note", "body": NOTE,
        "created_at": WHEN, "author_user_id": USER,
        "verified_read_scopes": ["business:read", "bills:read"], "read_passes": 2,
        "write_attempted": False, "api_write_proven": False, "authorship_proven": False,
        "actual_money_recovered": None}
    assert receipt["evidence"] == "LOCAL_OBSERVATION_NOT_PROVIDER_SIGNED"
    assert "not signed" in receipt["note"] and "did not create" in receipt["note"]
    assert_read_only(fake)
    assert_no_secrets(json.dumps(receipt))
    assert "c-other" not in json.dumps(receipt) and OTHER_USER not in json.dumps(receipt)
    # Business is bound before any bill read and rechecked after the last comment read.
    routes = [r for _, r, _ in fake.calls if r != "token"]
    assert routes == ["business", "bills/" + BILL, COMMENTS, COMMENTS, "business"]
    assert all(q == {"page_size": "100"} for _, _, q in fake.comment_calls())


def test_note_on_last_page_requires_reading_every_page_twice():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-1", "PRIVATE a")], "p2"),
                    "p2": page([comment("c-2", "PRIVATE b")], "p3"),
                    "p3": page([comment("c-note")])}]
    receipt = run(fake, max_pages=3)
    assert receipt["status"] == "VERIFIED_READBACK" and receipt["comment_id"] == "c-note"
    assert [q.get("start") for _, _, q in fake.comment_calls()] == [None, "p2", "p3"] * 2
    assert_read_only(fake)


def test_empty_listing_is_honest_not_found_without_invented_ids():
    fake = FakeRamp()
    fake.passes = [{None: page([])}]
    receipt = run(fake)
    assert receipt["status"] == "NOT_FOUND" and receipt["read_passes"] == 1
    assert_no_comment_claim(receipt)
    assert fake.calls[-1][:2] == ("GET", "business")


def test_near_miss_bodies_are_not_matches():
    fake = FakeRamp()
    variants = [NOTE + " ", " " + NOTE, NOTE.lower(), NOTE[:-1], NOTE.replace(" ", " ", 1),
                "PRIVATE " + NOTE]
    fake.passes = [{None: page([comment(f"c-{i}", v) for i, v in enumerate(variants)])}]
    receipt = run(fake)
    assert receipt["status"] == "NOT_FOUND"
    assert_no_comment_claim(receipt)
    assert_no_secrets(json.dumps(receipt))


def test_duplicate_exact_notes_are_ambiguous_never_first():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-a")], "p2"), "p2": page([comment("c-b", user=OTHER_USER)])}]
    receipt = run(fake)
    assert receipt["status"] == "AMBIGUOUS"
    assert_no_comment_claim(receipt)
    assert "c-a" not in json.dumps(receipt) and "c-b" not in json.dumps(receipt)


def test_expected_comment_id_narrows_exact_duplicates_or_reports_not_found():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-a"), comment("c-b", user=OTHER_USER)])}]
    receipt = run(fake, expected_comment_id="c-b")
    assert receipt["status"] == "VERIFIED_READBACK"
    assert (receipt["comment_id"], receipt["author_user_id"]) == ("c-b", OTHER_USER)
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-a"), comment("c-wrong-body", "PRIVATE other")])}]
    assert run(fake, expected_comment_id="c-wrong-body")["status"] == "NOT_FOUND"
    assert run(FakeRamp(), expected_comment_id="c-absent")["status"] == "NOT_FOUND"


# --- binding ----------------------------------------------------------------------------

def test_cross_business_before_any_bill_access():
    fake = FakeRamp()
    fake.business = [OTHER_BUSINESS]
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)
    assert "bills:read" not in fake.token_requests
    assert not any(r.startswith(("bills", "comments")) for _, r, _ in fake.calls)


def test_business_changed_after_reads_yields_no_receipt():
    fake = FakeRamp()
    fake.business = [BUSINESS, OTHER_BUSINESS]
    with pytest.raises(vrc.CommentVerificationError, match="business"):
        run(fake)


@pytest.mark.parametrize("scope,granted", [("business:read", "business:read bills:write"),
                                           ("bills:read", "bills:read bills:write"),
                                           ("bills:read", "")])
def test_inexact_grants_stop_before_resource_reads(scope, granted):
    fake = FakeRamp()
    fake.grants[scope] = granted
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)
    assert not any(r.startswith(("bills", "comments")) for _, r, _ in fake.calls)


@pytest.mark.parametrize("bill", [{"id": OTHER_BILL}, {"id": BILL.upper()}, {"data": [{"id": BILL}]}, [BILL]])
def test_bill_object_mismatch_stops_before_comments(bill):
    fake = FakeRamp()
    fake.bill = bill
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)
    assert not fake.comment_calls()


@pytest.mark.parametrize("kwargs", [
    {"business_id": BUSINESS.upper()}, {"business_id": "not-a-uuid"}, {"business_id": None},
    {"bill_url": "https://app.ramp.com/bill-pay/bills/list/" + BILL},
    {"bill_url": URL + "/"}, {"bill_url": URL + "?x=1"}, {"bill_url": URL.upper()},
    {"bill_url": "https://demo.ramp.com/bill-pay/bills/drafts/" + BILL},
    {"bill_url": "http://demo.ramp.com/bill-pay/bills/list/" + BILL},
    {"expected_comment_id": "bad id"}, {"expected_comment_id": "x" * 129}, {"expected_comment_id": 7},
    {"expected_body": ""}, {"expected_body": None},
    {"max_pages": 0}, {"max_pages": 11}, {"max_pages": True},
])
def test_invalid_inputs_rejected_before_network(kwargs):
    fake = FakeRamp()
    args = {"business_id": BUSINESS, "bill_url": URL, **kwargs}
    with pytest.raises(vrc.CommentVerificationError):
        vrc.verify_comment(provider_for(fake), **args)
    assert fake.calls == []


# --- pagination and response shape ------------------------------------------------------

@pytest.mark.parametrize("bad_next", [
    "https://api.ramp.com/developer/v1/" + COMMENTS + "?start=p2",
    "http://demo-api.ramp.com/developer/v1/" + COMMENTS + "?start=p2",
    "https://user:pw@demo-api.ramp.com/developer/v1/" + COMMENTS + "?start=p2",
    next_url("p2", "comments/bills/" + OTHER_BILL),
    next_url("p2", "comments/draft-bills/" + BILL),
    next_url("p2") + "&user_id=PRIVATE",
    next_url("p2") + "&start=p3",
    next_url("p2") + "#frag",
    next_url("p2") + "&page_size=2",
    next_url("..%2Fbills"),
    next_url("x" * 513),
    f"{ORIGIN}/developer/v1/{COMMENTS}",
])
def test_malicious_next_page_is_never_followed(bad_next):
    fake = FakeRamp()
    fake.passes = [{None: {"data": [comment("c-note")], "page": {"next": bad_next}}}]
    with pytest.raises(vrc.CommentVerificationError) as caught:
        run(fake)
    assert len(fake.comment_calls()) == 1
    assert_read_only(fake)
    assert_no_secrets(str(caught.value))


def test_repeated_cursor_cannot_loop():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-1", "x")], "p2"), "p2": page([comment("c-note")], "p2")}]
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)
    assert len(fake.comment_calls()) == 2


def test_listing_beyond_page_bound_is_incomplete_not_not_found():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-1", "x")], "p2"), "p2": page([comment("c-2", "y")], "p3"),
                    "p3": page([comment("c-note")])}]
    with pytest.raises(vrc.CommentVerificationError, match="incomplete"):
        run(fake, max_pages=2)
    assert len(fake.comment_calls()) == 2


@pytest.mark.parametrize("rows", [
    [comment("c-note"), comment("c-note")],
    [comment("c-x", "PRIVATE"), comment("c-note"), comment("c-x", "PRIVATE again")],
])
def test_duplicate_comment_ids_or_rows_rejected(rows):
    fake = FakeRamp()
    fake.passes = [{None: page(rows)}]
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)


def test_duplicate_id_across_pages_rejected():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-note")], "p2"), "p2": page([comment("c-note", "other")])}]
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)


@pytest.mark.parametrize("response", [
    {"data": [comment("c-note")]},
    {"data": [comment("c-note")], "page": {}},
    {"data": [comment("c-note")], "page": None},
    {"data": {"c-note": NOTE}, "page": {"next": None}},
    {"page": {"next": None}},
    [comment("c-note")],
    {"data": ["PRIVATE"], "page": {"next": None}},
    {"data": [comment(f"c-{i}", "x") for i in range(101)], "page": {"next": None}},
    page([{"id": "c-note", "created_at": WHEN, "user_id": USER}]),
    page([comment("c-note", message=1)]),
    page([comment("c-note"), comment("bad id!", "PRIVATE")]),
    page([comment("c-note"), comment(5, "PRIVATE")]),
    page([comment("c-note"), comment("c-x", "PRIVATE", created=None)]),
    page([comment("c-note"), comment("c-x", "PRIVATE", user=None)]),
])
def test_malformed_pages_or_records_rejected(response):
    fake = FakeRamp()
    fake.passes = [{None: response}]
    with pytest.raises(vrc.CommentVerificationError) as caught:
        run(fake)
    assert_no_secrets(str(caught.value))


@pytest.mark.parametrize("row", [
    comment("c-note", created="2026-11-01T12:00:00"),
    comment("c-note", created="yesterday"),
    comment("c-note", user="not-a-uuid"),
    comment("c-note", user=USER.upper()),
    comment("c-note", user=""),
])
def test_matched_comment_requires_timezone_and_canonical_user_uuid(row):
    fake = FakeRamp()
    fake.passes = [{None: page([row])}]
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)
    assert len(fake.comment_calls()) == 1


# --- second read ------------------------------------------------------------------------

@pytest.mark.parametrize("second", [
    [comment("c-note2")],
    [comment("c-note", NOTE + ".")],
    [comment("c-note", created="2026-11-01T12:00:01+00:00")],
    [comment("c-note", created="2026-11-01T07:00:00-05:00")],
    [comment("c-note", user=OTHER_USER)],
    [],
    [comment("c-other", "PRIVATE")],
    [comment("c-note"), comment("c-late")],
])
def test_second_read_change_is_never_verified(second):
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-note")])}, {None: page(second)}]
    receipt = run(fake)
    assert receipt["status"] == "CHANGED_OR_AMBIGUOUS" and receipt["read_passes"] == 2
    assert_no_comment_claim(receipt)
    assert len(fake.comment_calls()) == 2
    assert_no_secrets(json.dumps(receipt))


def test_second_read_pagination_failure_raises():
    fake = FakeRamp()
    fake.passes = [{None: page([comment("c-note")])},
                   {None: {"data": [comment("c-note")], "page": {"next": next_url("p2", "bills")}}}]
    with pytest.raises(vrc.CommentVerificationError):
        run(fake)


# --- sanitized failures -----------------------------------------------------------------

@pytest.mark.parametrize("route,error", [
    (COMMENTS, RampHTTPError(403)), (COMMENTS, RampError("PRIVATE FAKE-TOKEN-bills-read")),
    ("bills/" + BILL, RampHTTPError(404)), ("bills/" + BILL, ValueError("PRIVATE body")),
    ("business", KeyError("PRIVATE")), ("business", RampHTTPError(401)),
])
def test_provider_failures_are_fixed_and_secret_free(route, error):
    fake = FakeRamp()
    fake.errors[route] = error
    with pytest.raises(vrc.CommentVerificationError) as caught:
        run(fake)
    assert_no_secrets(str(caught.value))
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None or caught.value.__suppress_context__
    assert_read_only(fake)


# --- CLI --------------------------------------------------------------------------------

@pytest.fixture
def custody(tmp_path):
    directory = tmp_path / "custody"
    directory.mkdir()
    directory.chmod(0o700)
    return directory


def install(monkeypatch, fake):
    built = []
    def factory():
        built.append(True)
        return provider_for(fake)
    monkeypatch.setattr(vrc, "SandboxRampProvider", factory)
    return built


def cli_args(receipt, *extra):
    return ["--business-id", BUSINESS, "--bill-url", URL, "--receipt", str(receipt), *extra]


def test_cli_verified_writes_owner_only_receipt_and_prints_only_status(custody, monkeypatch, capsys):
    fake = FakeRamp()
    install(monkeypatch, fake)
    target = custody / "readback.json"
    assert vrc.main(cli_args(target)) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == ["status=VERIFIED_READBACK", f"receipt={target}"]
    assert captured.err == ""
    assert stat.S_IMODE(target.stat().st_mode) == 0o600 and not target.is_symlink()
    saved = json.loads(target.read_text())
    assert saved["status"] == "VERIFIED_READBACK" and saved["comment_id"] == "c-note"
    assert_no_secrets(target.read_text() + captured.out)
    assert_read_only(fake)


@pytest.mark.parametrize("passes,status", [([{None: page([])}], "NOT_FOUND"),
                                           ([{None: page([comment("a"), comment("b")])}], "AMBIGUOUS")])
def test_cli_non_verified_outcomes_written_but_nonzero(custody, monkeypatch, capsys, passes, status):
    fake = FakeRamp()
    fake.passes = passes
    install(monkeypatch, fake)
    target = custody / "readback.json"
    assert vrc.main(cli_args(target)) != 0
    assert capsys.readouterr().out.splitlines()[0] == "status=" + status
    assert json.loads(target.read_text())["status"] == status


def test_cli_comment_id_option_narrows(custody, monkeypatch):
    fake = FakeRamp()
    fake.passes = [{None: page([comment("a"), comment("b")])}]
    install(monkeypatch, fake)
    target = custody / "readback.json"
    assert vrc.main(cli_args(target, "--comment-id", "b")) == 0
    assert json.loads(target.read_text())["comment_id"] == "b"


def _unsafe(kind, tmp_path, custody):
    if kind == "relative":
        return "readback.json", None
    if kind == "existing":
        path = custody / "readback.json"
        path.write_text("PREEXISTING")
        return str(path), lambda: path.read_text() == "PREEXISTING"
    if kind == "file_symlink":
        target, link = custody / "elsewhere.json", custody / "readback.json"
        link.symlink_to(target)
        return str(link), lambda: not target.exists() and link.is_symlink()
    if kind == "dir_symlink":
        real = custody / "real"
        real.mkdir(mode=0o700)
        (custody / "alias").symlink_to(real)
        return str(custody / "alias" / "readback.json"), lambda: not (real / "readback.json").exists()
    if kind == "shared_dir":
        shared = tmp_path / "shared"
        shared.mkdir()
        shared.chmod(0o750)
        return str(shared / "readback.json"), lambda: not (shared / "readback.json").exists()
    if kind == "missing_dir":
        return str(custody / "absent" / "readback.json"), None
    if kind == "dotdot":
        return str(custody) + "/../custody/readback.json", lambda: not (custody / "readback.json").exists()
    if kind == "directory":
        return str(custody), None
    if kind == "repository":
        path = ROOT / "readback-must-not-exist.json"
        return str(path), lambda: not path.exists()
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["relative", "existing", "file_symlink", "dir_symlink", "shared_dir",
                                  "missing_dir", "dotdot", "directory", "repository"])
def test_cli_unsafe_receipt_rejected_before_credentials_or_network(kind, tmp_path, custody, monkeypatch, capsys):
    fake = FakeRamp()
    built = install(monkeypatch, fake)
    raw, unchanged = _unsafe(kind, tmp_path, custody)
    assert vrc.main(cli_args(raw)) != 0
    assert not built and fake.calls == []
    if unchanged is not None:
        assert unchanged()
    assert "VERIFIED" not in capsys.readouterr().out


def test_cli_never_overwrites_receipt_created_during_reads(custody, monkeypatch, capsys):
    fake = FakeRamp()
    target = custody / "readback.json"
    def factory():
        target.write_text("PREEXISTING")
        return provider_for(fake)
    monkeypatch.setattr(vrc, "SandboxRampProvider", factory)
    assert vrc.main(cli_args(target)) != 0
    assert target.read_text() == "PREEXISTING"
    assert "status=VERIFIED_READBACK" not in capsys.readouterr().out


@pytest.mark.parametrize("failure", ["comments", "credentials", "unexpected"])
def test_cli_failures_print_no_secrets_and_write_nothing(failure, custody, monkeypatch, capsys):
    fake = FakeRamp()
    if failure == "comments":
        fake.errors[COMMENTS] = RampError("PRIVATE FAKE-TOKEN-bills-read")
        install(monkeypatch, fake)
    else:
        error = (RampError("PRIVATE credential path FAKE-SECRET") if failure == "credentials"
                 else RuntimeError("PRIVATE FAKE-SECRET"))
        def factory():
            raise error
        monkeypatch.setattr(vrc, "SandboxRampProvider", factory)
    target = custody / "readback.json"
    assert vrc.main(cli_args(target)) != 0
    captured = capsys.readouterr()
    assert_no_secrets(captured.out + captured.err)
    assert "Traceback" not in captured.err and captured.err.startswith("status=ERROR")
    assert not target.exists()


@pytest.mark.parametrize("argv", [
    ["--client-secret", "FAKE-SECRET"],
    ["--token", "PRIVATE"],
    ["--business-id", BUSINESS, "--bill-url", URL],
    ["--business-id", "PRIVATE", "--bill-url", URL, "--receipt", "/x/readback.json"],
])
def test_cli_rejects_credential_args_and_bad_input_without_echo(argv, monkeypatch, capsys):
    fake = FakeRamp()
    built = install(monkeypatch, fake)
    assert vrc.main(argv) != 0
    captured = capsys.readouterr()
    assert_no_secrets(captured.out + captured.err)
    assert not built and fake.calls == []
