"""uptime/jev.py without network: a fake opener stands in for urllib."""
from decimal import Decimal
import io
import json
import socket
import urllib.error

import pytest

from uptime import jev as jev_module
from uptime.jev import FakeJev, JevClient, JevUnavailable, check_url

KEY = "tsk-SECRET-test-key-0123456789"


class Response:
    def __init__(self, body, status=200, url=jev_module.ENDPOINT):
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.status = status
        self._url = url

    def read(self, n=-1):
        return self._body if n < 0 else self._body[:n]

    def getcode(self):
        return self.status

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class Opener:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append({"url": request.full_url, "method": request.get_method(),
                              "headers": dict(request.header_items()), "body": json.loads(request.data),
                              "timeout": timeout})
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.fixture
def key_file(tmp_path):
    path = tmp_path / "jev-api-key"
    path.write_text(f"  {KEY}\n")
    return path


def client(key_file, result):
    opener = Opener(result)
    return JevClient(key_file=key_file, opener=opener), opener


CHOICE_ANSWER = {"model": "jev-1.13.0", "answers": {"q": {
    "type": "choice", "choice": "sla", "probabilities": {"sla": 0.85, "lease": 0.1, "unrecognised": 0.05},
    "confidence": 0.82}}, "usage": {"input_tokens": 312, "output_tokens": 48}}
NOUL_ANSWER = {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 0.93}},
               "usage": {"input_tokens": 100, "output_tokens": 10}}


def test_choice_request_shape_and_parsing(key_file):
    jev, opener = client(key_file, Response(CHOICE_ANSWER))
    result = jev.choice("Which contract type?", ["sla", "lease", "unrecognised"], "The provider keeps 99.9%.")
    assert result["choice"] == "sla"
    assert result["probability"] == Decimal("0.85") and isinstance(result["probability"], Decimal)
    assert result["model"] == "jev-1.13.0"
    assert isinstance(result["milliseconds"], int) and result["milliseconds"] >= 0
    assert set(result) == {"choice", "probability", "model", "milliseconds"}
    [sent] = opener.requests
    assert sent["url"] == "https://api.typesafe.ai/v1/systemone"
    assert sent["method"] == "POST"
    assert sent["headers"]["Authorization"] == f"Bearer {KEY}"  # stripped
    assert sent["headers"]["Content-type"] == "application/json"
    assert sent["timeout"] == 20.0
    assert sent["body"] == {"model": "jev-1.13.0", "state": "The provider keeps 99.9%.", "questions": {"q": {
        "type": "choice", "instructions": "Which contract type?",
        "criteria": {"sla": None, "lease": None, "unrecognised": None}}}}


def test_yes_no_request_shape_and_parsing(key_file):
    jev, opener = client(key_file, Response(NOUL_ANSWER))
    result = jev.yes_no("Is the term supported?", "Sentence.")
    assert result == {"yes": True, "probability": Decimal("0.93"), "model": "jev-1.13.0",
                      "milliseconds": result["milliseconds"]}
    assert opener.requests[0]["body"]["questions"] == {"q": {"type": "noul", "instructions": "Is the term supported?"}}
    no, _ = client(key_file, Response({**NOUL_ANSWER, "answers": {"q": {"type": "noul", "noul": 0.2}}}))
    assert no.yes_no("Q?", "C")["yes"] is False


def test_context_is_capped_and_long_inputs_refused(key_file):
    jev, opener = client(key_file, Response(NOUL_ANSWER))
    jev.yes_no("Q?", "x" * 50_000)
    assert len(opener.requests[0]["body"]["state"]) == jev_module.MAX_CONTEXT
    with pytest.raises(JevUnavailable):
        jev.yes_no("q" * 5000, "C")
    with pytest.raises(JevUnavailable):
        jev.choice("Q?", ["a"] * 2, "C")
    with pytest.raises(JevUnavailable):
        jev.choice("Q?", [], "C")
    with pytest.raises(JevUnavailable):
        jev.choice("Q?", [f"o{i}" for i in range(256)], "C")
    assert len(opener.requests) == 1


@pytest.mark.parametrize("status,sentence", [
    (401, "Jev did not accept the key (401)."),
    (403, "Jev refused this key access to the model (403)."),
    (429, "Jev is limiting requests right now (429)."),
    (400, "Jev rejected the request as malformed (400)."),
    (422, "Jev rejected the request as malformed (422)."),
    (500, "Jev had a server error (500)."),
    (503, "Jev had a server error (503)."),
    (302, "Jev answered with a redirect, which Uptime does not follow (302)."),
])
def test_http_errors_map_to_sentences(key_file, status, sentence):
    error = urllib.error.HTTPError(jev_module.ENDPOINT, status, "x", {}, io.BytesIO(f"echo {KEY}".encode()))
    jev, _ = client(key_file, error)
    with pytest.raises(JevUnavailable) as raised:
        jev.yes_no("Q?", "C")
    assert raised.value.sentence == sentence
    assert raised.value.__cause__ is None and raised.value.__context__ is None


def test_non_200_success_status_is_refused(key_file):
    jev, _ = client(key_file, Response(NOUL_ANSWER, status=204))
    with pytest.raises(JevUnavailable, match=r"unexpected status \(204\)"):
        jev.yes_no("Q?", "C")


@pytest.mark.parametrize("error", [socket.timeout("timed out"), TimeoutError(),
                                   urllib.error.URLError(socket.timeout("timed out"))])
def test_timeout(key_file, error):
    jev, _ = client(key_file, error)
    with pytest.raises(JevUnavailable) as raised:
        jev.choice("Q?", ["a", "b"], "C")
    assert raised.value.sentence == "Jev did not answer within 20 seconds."


def test_unreachable_and_unexpected_errors_hide_their_message(key_file):
    for error in (urllib.error.URLError("Name or service not known"), ConnectionResetError(f"reset {KEY}"),
                  ValueError(f"Invalid header value {KEY}")):
        jev, _ = client(key_file, error)
        with pytest.raises(JevUnavailable) as raised:
            jev.yes_no("Q?", "C")
        assert raised.value.sentence == "Jev could not be reached."
        assert KEY not in str(raised.value)


@pytest.mark.parametrize("body", [
    b"not json", b"[]", {"answers": {"q": {"type": "noul", "noul": 0.5}}},  # no model
    {"model": "jev-1.13.0", "answers": {}},
    {"model": "jev-1.13.0", "answers": {"q": {"type": "choice", "choice": "a"}}},
    {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": "0.9"}}},
    {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 1.5}}},
    {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": True}}},
])
def test_unexpected_shapes_for_yes_no(key_file, body):
    jev, _ = client(key_file, Response(body))
    with pytest.raises(JevUnavailable) as raised:
        jev.yes_no("Q?", "C")
    assert raised.value.sentence == "Jev's answer was not in the expected shape."


@pytest.mark.parametrize("answer", [
    {"type": "choice", "choice": "zzz", "probabilities": {"zzz": 0.9}},  # not one of the options
    {"type": "choice", "choice": "a"},  # no probabilities
    {"type": "choice", "choice": "a", "probabilities": {"b": 0.9}},
    {"type": "noul", "noul": 0.9},
])
def test_unexpected_shapes_for_choice(key_file, answer):
    jev, _ = client(key_file, Response({"model": "jev-1.13.0", "answers": {"q": answer}}))
    with pytest.raises(JevUnavailable, match="expected shape"):
        jev.choice("Q?", ["a", "b"], "C")


def test_missing_empty_and_unusable_key_files(tmp_path, monkeypatch):
    opener = Opener(Response(NOUL_ANSWER))
    with pytest.raises(JevUnavailable) as raised:
        JevClient(key_file=tmp_path / "absent", opener=opener).yes_no("Q?", "C")
    assert raised.value.sentence == "Jev's key file is missing."
    assert raised.value.__context__ is None
    empty = tmp_path / "empty"
    empty.write_text("  \n")
    with pytest.raises(JevUnavailable, match="empty"):
        JevClient(key_file=empty, opener=opener).yes_no("Q?", "C")
    bad = tmp_path / "bad"
    bad.write_text("abc defé")
    with pytest.raises(JevUnavailable) as raised:
        JevClient(key_file=bad, opener=opener).yes_no("Q?", "C")
    assert "abc" not in raised.value.sentence
    assert opener.requests == []
    monkeypatch.setenv("UPTIME_JEV_KEY_FILE", str(tmp_path / "from-env"))
    (tmp_path / "from-env").write_text(KEY)
    JevClient(opener=opener).yes_no("Q?", "C")
    assert opener.requests[0]["headers"]["Authorization"] == f"Bearer {KEY}"


def test_key_is_read_at_each_call_and_never_kept(key_file):
    jev, opener = client(key_file, Response(NOUL_ANSWER))
    jev.yes_no("Q?", "C")
    key_file.write_text("tsk-rotated")
    jev.yes_no("Q?", "C")
    assert [r["headers"]["Authorization"] for r in opener.requests] == [f"Bearer {KEY}", "Bearer tsk-rotated"]
    assert KEY not in repr(jev) and "tsk-rotated" not in repr(jev)
    assert all(KEY not in repr(value) and "tsk-rotated" not in repr(value) for value in vars(jev).values())


def test_key_never_appears_in_an_exception(key_file):
    for result in (urllib.error.HTTPError(jev_module.ENDPOINT, 401, KEY, {}, None), Response(KEY.encode()),
                   RuntimeError(KEY)):
        jev, _ = client(key_file, result)
        with pytest.raises(JevUnavailable) as raised:
            jev.choice("Q?", ["a"], "C")
        text = " ".join([str(raised.value), repr(raised.value), raised.value.sentence, str(raised.value.args)])
        assert KEY not in text
        assert raised.value.__cause__ is None and raised.value.__context__ is None


def test_host_allow_list():
    assert check_url("https://api.typesafe.ai/v1/systemone")
    for url in ("http://api.typesafe.ai/v1/systemone", "https://api.typesafe.ai.evil.example/v1/systemone",
                "https://evil.example/v1/systemone", "https://user@api.typesafe.ai/v1/systemone",
                "https://api.typesafe.ai:8443/v1/systemone", "https://openrouter.ai/api/v1/systemone"):
        with pytest.raises(JevUnavailable):
            check_url(url)


def test_answer_from_another_host_is_refused(key_file):
    jev, _ = client(key_file, Response(NOUL_ANSWER, url="https://evil.example/v1/systemone"))
    with pytest.raises(JevUnavailable, match="only sends Jev requests"):
        jev.yes_no("Q?", "C")


def test_endpoint_change_is_refused_before_the_key_is_read(key_file, monkeypatch):
    monkeypatch.setattr(jev_module, "ENDPOINT", "https://evil.example/v1/systemone")
    jev, opener = client(key_file, Response(NOUL_ANSWER))
    with pytest.raises(JevUnavailable):
        jev.yes_no("Q?", "C")
    assert opener.requests == []


def test_default_opener_does_not_follow_redirects():
    handler = jev_module._NoRedirect()
    assert handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/") is None
    opener = jev_module._default_opener()
    assert any(isinstance(h, jev_module._NoRedirect) for h in opener.handlers)


def test_fake_jev():
    fake = FakeJev(choice="lease", yes=False)
    assert fake.choice("Q?", ["sla", "lease"], "C") == {"choice": "lease", "probability": Decimal("0.95"),
                                                         "model": "jev-fake", "milliseconds": 0}
    assert fake.yes_no("Q?", "C") == {"yes": False, "probability": Decimal("0.03"), "model": "jev-fake",
                                      "milliseconds": 0}
    assert FakeJev().choice("Q?", ["sla", "lease"], "C")["choice"] == "sla"
    assert FakeJev(yes_probability="0.85").yes_no("Q?", "C")["probability"] == Decimal("0.85")
    assert len(fake.calls) == 2
    with pytest.raises(JevUnavailable, match="down"):
        FakeJev(unavailable="Jev is down.").yes_no("Q?", "C")
