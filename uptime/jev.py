"""Jev client: typed decisions with probabilities from TypeSafe AI's decision model.

Endpoint (verified against TypeSafe's OpenAPI document and one real call on November 10, 2026):
``POST https://api.typesafe.ai/v1/systemone`` with ``Authorization: Bearer <key>`` and a JSON body

    {"model": "jev-1.13.0", "state": "<text>",
     "questions": {"<id>": {"type": "choice", "instructions": "...", "criteria": {"<option>": null, ...}}}}
    {"model": "jev-1.13.0", "state": "<text>",
     "questions": {"<id>": {"type": "noul", "instructions": "..."}}}

Question types are lowercase. A ``choice`` takes 1 to 255 criteria (option name -> description or null); a
``noul`` is yes/no. A 200 answer is

    {"model": "jev-1.13.0",
     "answers": {"<id>": {"type": "choice", "choice": "...", "probabilities": {...}, "confidence": 0.82}},
     "usage": {"input_tokens": 312, "output_tokens": 48}}

with a ``noul`` answer carrying ``{"type": "noul", "noul": 0.93}``, the probability of yes. Errors are 400
(``detail``), 422 (validation ``detail`` list), 401 unknown key, 403 model access denied, 429 and 5xx.

Sources: https://api.typesafe.ai/openapi.json, https://docs.typesafe.ai/primitives/choice.md,
https://docs.typesafe.ai/primitives/noul.md, cross-checked with https://docs.litellm.ai/docs/pass_through/typesafe
and https://www.truefoundry.com/docs/ai-gateway/jev.

What Jev is used for here: it supports and triages. It picks which contract template a document resembles and says
whether a term is supported by its quoted sentence, each with a probability shown to the reviewer. It is never used
for arithmetic, dates or deadlines; those stay in code. Its answers are advisory and never approve anything.

The API key is read from the key file at each call, used for that one request and dropped. It is never kept on the
object, logged, printed, returned or put into an exception. Requests go only to https://api.typesafe.ai; redirects are
not followed. Context longer than ``MAX_CONTEXT`` characters is cut to its first ``MAX_CONTEXT`` characters.
Standard library only.
"""
from __future__ import annotations

import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

HOST = "api.typesafe.ai"
ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
MAX_CONTEXT = 6000
MAX_QUESTION = 1000
MAX_OPTION = 200
MAX_OPTIONS = 255
MAX_RESPONSE_BYTES = 1_000_000
QUESTION_ID = "q"


class JevUnavailable(Exception):
    """Carries .sentence, a plain sentence safe to show a reviewer. Never contains the key."""

    def __init__(self, sentence: str):
        super().__init__(sentence)
        self.sentence = sentence

    def __repr__(self) -> str:
        return f"JevUnavailable({self.sentence!r})"


def check_url(url: str) -> str:
    """Refuse any URL that is not HTTPS on the TypeSafe API host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname != HOST or parts.port not in (None, 443) or parts.username:
        raise JevUnavailable("Uptime only sends Jev requests to https://api.typesafe.ai.")
    return url


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401 - urllib hook
        return None  # urllib then raises HTTPError with the 3xx code


def _default_opener():
    return urllib.request.build_opener(_NoRedirect())


def _default_key_file() -> Path:
    configured = os.environ.get("UPTIME_JEV_KEY_FILE")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".config" / "uptime" / "jev-api-key"


def _status_sentence(status: int) -> str:
    if status == 401:
        return "Jev did not accept the key (401)."
    if status == 403:
        return "Jev refused this key access to the model (403)."
    if status == 429:
        return "Jev is limiting requests right now (429)."
    if status in (400, 422):
        return f"Jev rejected the request as malformed ({status})."
    if 300 <= status < 400:
        return f"Jev answered with a redirect, which Uptime does not follow ({status})."
    if status >= 500:
        return f"Jev had a server error ({status})."
    return f"Jev answered with an unexpected status ({status})."


def _probability(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (Decimal, int)):
        raise JevUnavailable("Jev's answer was not in the expected shape.")
    p = Decimal(value)
    if not p.is_finite() or p < 0 or p > 1:
        raise JevUnavailable("Jev's answer was not in the expected shape.")
    return p


def _text(value, limit: int, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JevUnavailable(f"The {what} for Jev is empty.")
    if len(value) > limit:
        raise JevUnavailable(f"The {what} for Jev is longer than {limit} characters.")
    return value


class JevClient:
    def __init__(self, key_file=None, timeout=20.0, *, opener=None):
        """key_file defaults to $UPTIME_JEV_KEY_FILE, then ~/.config/uptime/jev-api-key.
        The key is read from the file at each call, never kept on the object, logged, printed or returned.
        ``opener`` (an object with ``open(request, timeout=...)``) is for tests; the default follows no redirects."""
        self._key_file = Path(key_file).expanduser() if key_file is not None else None
        self.timeout = min(float(timeout), 20.0)
        self._opener = opener if opener is not None else _default_opener()

    def __repr__(self) -> str:
        return f"JevClient(endpoint={ENDPOINT!r}, model={MODEL!r}, timeout={self.timeout})"

    # -- public ---------------------------------------------------------------------------------------------------
    def choice(self, question: str, options: list[str], context: str) -> dict:
        """-> {"choice": <one of options>, "probability": Decimal, "model": str, "milliseconds": int}"""
        question = _text(question, MAX_QUESTION, "question")
        if not isinstance(options, (list, tuple)) or not options:
            raise JevUnavailable("Jev needs at least one option to choose from.")
        if len(options) > MAX_OPTIONS:
            raise JevUnavailable(f"Jev accepts at most {MAX_OPTIONS} options.")
        names = [_text(option, MAX_OPTION, "option") for option in options]
        if len(set(names)) != len(names):
            raise JevUnavailable("The options for Jev repeat a name.")
        body = {"type": "choice", "instructions": question, "criteria": {name: None for name in names}}
        answer, model, ms = self._ask(body, context)
        chosen = answer.get("choice")
        probabilities = answer.get("probabilities")
        if answer.get("type") != "choice" or chosen not in names or not isinstance(probabilities, dict) \
                or chosen not in probabilities:
            raise JevUnavailable("Jev's answer was not in the expected shape.")
        return {"choice": chosen, "probability": _probability(probabilities[chosen]), "model": model,
                "milliseconds": ms}

    def yes_no(self, question: str, context: str) -> dict:
        """-> {"yes": bool, "probability": Decimal (of yes), "model": str, "milliseconds": int}"""
        question = _text(question, MAX_QUESTION, "question")
        answer, model, ms = self._ask({"type": "noul", "instructions": question}, context)
        if answer.get("type") != "noul":
            raise JevUnavailable("Jev's answer was not in the expected shape.")
        p = _probability(answer.get("noul"))
        return {"yes": p >= Decimal("0.5"), "probability": p, "model": model, "milliseconds": ms}

    # -- transport ------------------------------------------------------------------------------------------------
    def _read_key(self) -> str:
        path = self._key_file or _default_key_file()
        key, sentence = None, None
        try:
            key = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            sentence = "Jev's key file is missing."
        except (OSError, UnicodeDecodeError):
            sentence = "Jev's key file could not be read."
        if sentence:
            raise JevUnavailable(sentence)  # outside the handler: nothing chained
        if not key:
            raise JevUnavailable("Jev's key file is empty.")
        if not all(33 <= ord(c) < 127 for c in key):
            raise JevUnavailable("Jev's key file does not hold a usable key.")
        return key

    def _ask(self, question: dict, context: str) -> tuple[dict, str, int]:
        if not isinstance(context, str):
            raise JevUnavailable("The context for Jev must be text.")
        payload = {"model": MODEL, "state": context[:MAX_CONTEXT], "questions": {QUESTION_ID: question}}
        data = json.dumps(payload).encode("utf-8")
        url = check_url(ENDPOINT)
        key = self._read_key()
        request = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"})
        del key
        started = time.monotonic()
        try:
            raw = self._send(request)
        finally:
            request.remove_header("Authorization")
            del request
        ms = int(round((time.monotonic() - started) * 1000))
        parsed = None
        try:
            parsed = json.loads(raw, parse_float=Decimal)
        except (ValueError, UnicodeDecodeError):
            pass  # raised below, outside the handler, so no decoder error (with the body) is chained
        answers = parsed.get("answers") if isinstance(parsed, dict) else None
        answer = answers.get(QUESTION_ID) if isinstance(answers, dict) else None
        model = parsed.get("model") if isinstance(parsed, dict) else None
        if not isinstance(answer, dict) or not isinstance(model, str) or not model:
            raise JevUnavailable("Jev's answer was not in the expected shape.")
        return answer, model, ms

    def _send(self, request) -> bytes:
        sentence = None
        try:
            response = self._opener.open(request, timeout=self.timeout)
            with response:
                status = getattr(response, "status", None) or response.getcode()
                final = response.geturl() if hasattr(response, "geturl") else ENDPOINT
                if final != ENDPOINT:
                    check_url(final)
                if status != 200:
                    sentence = _status_sentence(status)
                else:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                    if len(raw) > MAX_RESPONSE_BYTES:
                        sentence = "Jev's answer was larger than expected."
                    else:
                        return raw
        except JevUnavailable:
            raise
        except urllib.error.HTTPError as error:
            sentence = _status_sentence(error.code)
            error.close()
        except (TimeoutError, socket.timeout):
            sentence = f"Jev did not answer within {self.timeout:g} seconds."
        except urllib.error.URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                sentence = f"Jev did not answer within {self.timeout:g} seconds."
            else:
                sentence = "Jev could not be reached."
        except Exception:  # anything else (e.g. connection reset); its message is never passed on
            sentence = "Jev could not be reached."
        raise JevUnavailable(sentence)


class FakeJev:
    """Same two methods as JevClient, with fixed answers, for tests.

    ``choice`` is the option to pick (default: the first option); ``yes`` the yes/no answer. A probability may be
    given as ``choice_probability`` / ``yes_probability``. Pass ``unavailable="sentence"`` to raise JevUnavailable.
    Every call is recorded in ``.calls``."""

    def __init__(self, choice=None, yes=True, *, choice_probability="0.95", yes_probability=None,
                 model="jev-fake", unavailable=None):
        self._choice = choice
        self._yes = yes
        self._choice_probability = Decimal(str(choice_probability))
        self._yes_probability = Decimal(str(yes_probability)) if yes_probability is not None else \
            (Decimal("0.97") if yes else Decimal("0.03"))
        self.model = model
        self.unavailable = unavailable
        self.calls: list[tuple] = []

    def choice(self, question: str, options: list[str], context: str) -> dict:
        self.calls.append(("choice", question, list(options), context))
        if self.unavailable:
            raise JevUnavailable(self.unavailable)
        picked = options[0] if self._choice is None else self._choice
        if picked not in options:
            raise JevUnavailable("Jev's answer was not in the expected shape.")
        return {"choice": picked, "probability": self._choice_probability, "model": self.model, "milliseconds": 0}

    def yes_no(self, question: str, context: str) -> dict:
        self.calls.append(("yes_no", question, context))
        if self.unavailable:
            raise JevUnavailable(self.unavailable)
        return {"yes": bool(self._yes), "probability": self._yes_probability, "model": self.model, "milliseconds": 0}
