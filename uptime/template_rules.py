"""Demo line: Uptime's fixed interpreter for contract templates.

A template is data: per term, a regular expression with exactly one capture group, the term's type and (for a
choice) a map from captured phrase to option. Nothing in a template runs as code. Each match runs in a separate
Python worker process with a time limit, so a runaway pattern fails its rule instead of hanging the server.
"""
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
import re
import select
import subprocess
import sys
from threading import Lock
from time import perf_counter

PATTERN_LIMIT = 400
MATCH_SECONDS = 0.5

# The fixed term set an SLA credit needs. `question` is how Jev is asked whether a sentence supports the term.
TERMS = (
    {"field": "availability_target_percent", "label": "Availability commitment", "type": "percent",
     "describe": "the availability percentage the provider commits to in each measurement period",
     "question": "the availability commitment is {display}"},
    {"field": "measurement_period", "label": "Measurement period", "type": "choice",
     "options": {"calendar_month": "Calendar month", "calendar_quarter": "Calendar quarter", "calendar_year": "Calendar year"},
     "describe": "the period over which availability is measured",
     "question": "the measurement period is each {display_lower}"},
    {"field": "tier_1_credit_percent", "label": "Credit, first tier below the commitment", "type": "percent",
     "describe": "the service credit, as a percent of fees, when availability is below the commitment but not below the second tier's threshold",
     "question": "the service credit for the first tier below the commitment is {display} of the fees"},
    {"field": "tier_2_threshold_percent", "label": "Second tier starts below", "type": "percent",
     "describe": "the availability percentage below which the second, larger credit tier applies",
     "question": "the second credit tier applies when availability is less than {display}"},
    {"field": "tier_2_credit_percent", "label": "Credit, second tier", "type": "percent",
     "describe": "the service credit, as a percent of fees, in the second (larger) tier",
     "question": "the second credit tier gives a service credit of {display} of the fees"},
    {"field": "credit_cap_percent", "label": "Credit cap", "type": "percent",
     "describe": "the most credits can total in one measurement period, as a percent of fees",
     "question": "service credits in one period are capped at {display} of the fees"},
    {"field": "claim_window_days", "label": "Claim window", "type": "integer", "unit": "days",
     "describe": "how many days the customer has to submit a credit claim",
     "question": "the customer must submit a credit claim within {display}"},
    {"field": "maintenance_notice_hours", "label": "Scheduled-maintenance notice", "type": "integer", "unit": "hours",
     "describe": "how many hours of prior notice the provider must give before scheduled maintenance",
     "question": "the provider must give {display} of notice before scheduled maintenance"},
    {"field": "credit_application", "label": "How a credit is applied", "type": "choice",
     "options": {"next_invoice": "Against the next invoice", "refund": "Paid as a refund",
                 "account_balance": "Held as an account balance"},
     "describe": "how an awarded service credit reaches the customer",
     "question": "a service credit is applied {display_lower}"},
)
TERM = {t["field"]: t for t in TERMS}
WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def normalize(text):
    """One space for any run of whitespace; straight quotes for curly ones."""
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(template):
    return hashlib.sha256(canonical_json(template).encode()).hexdigest()


def _words_to_int(text):
    text = text.lower().replace("-", " ").split()
    if not text:
        return None
    total = 0
    for word in text:
        if word in WORDS:
            total += WORDS[word]
        elif word in TENS:
            total += TENS[word]
        else:
            return None
    return total


def canonical(kind, raw, options=None, mapping=None):
    """The typed value as a string, or None when the raw text is not a value of that type."""
    if raw is None:
        return None
    raw = str(raw).strip()
    if kind == "percent":
        try:
            number = Decimal(raw.rstrip("%").replace(",", "").strip())
        except InvalidOperation:
            return None
        if not number.is_finite() or number < 0 or number > 100:
            return None
        return format(number.normalize(), "f")
    if kind == "integer":
        if re.fullmatch(r"\d{1,6}", raw):
            return str(int(raw))
        found = _words_to_int(raw)
        return None if found is None else str(found)
    if kind == "choice":
        phrase = re.sub(r"[^a-z0-9_ ]", "", normalize(raw).lower()).strip()
        if phrase in (options or {}):
            return phrase
        for key, option in (mapping or {}).items():
            if re.sub(r"[^a-z0-9_ ]", "", normalize(key).lower()).strip() == phrase and option in (options or {}):
                return option
        return None
    raise ValueError("Unknown term type.")


def display(field, value):
    if value is None:
        return None
    term = TERM[field]
    if term["type"] == "percent":
        return value + "%"
    if term["type"] == "integer":
        return value + " " + term["unit"]
    return term["options"][value]


# --- Sentences --------------------------------------------------------------------------

_ABBREVIATIONS = ("Inc.", "Co.", "No.", "Ltd.", "e.g.", "i.e.", "U.S.", "St.")


def sentence_at(text, start, end):
    """The sentence (or list item) of normalized `text` around [start, end)."""
    def boundary(i):
        if text[i] in ";:":
            return True
        if text[i] != ".":
            return False
        before = text[max(0, i - 5):i + 1]
        return not any(before.endswith(a) for a in _ABBREVIATIONS)
    left = start
    while left > 0 and not (text[left - 1] == " " and left >= 2 and boundary(left - 2)):
        left -= 1
    right = end
    while right < len(text) and not (boundary(right) and (right + 1 == len(text) or text[right + 1] == " ")):
        right += 1
    return text[left:min(len(text), right + 1)].strip()


# --- The time-limited matcher -------------------------------------------------------------

_WORKER = r"""
import json, re, sys
for line in sys.stdin:
    try:
        job = json.loads(line)
        m = re.compile(job["pattern"], re.IGNORECASE).search(job["text"])
        out = {"m": None if m is None else [m.start(), m.end(), m.group(1), m.start(1), m.end(1)]}
    except Exception as exc:
        out = {"error": type(exc).__name__}
    sys.stdout.write(json.dumps(out) + "\n"); sys.stdout.flush()
"""


class Matcher:
    """One worker process; a match that overruns its time limit kills the worker and fails that rule."""

    def __init__(self, seconds=MATCH_SECONDS):
        self.seconds, self.process, self.lock = seconds, None, Lock()

    def _start(self):
        self.process = subprocess.Popen([sys.executable, "-I", "-c", _WORKER], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)

    def _kill(self):
        if self.process is not None:
            self.process.kill()
            self.process.wait()
        self.process = None

    def search(self, pattern, text):
        """-> (start, end, group, gstart, gend) or None. Raises TimeoutError / ValueError."""
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self._start()
            self.process.stdin.write((json.dumps({"pattern": pattern, "text": text}) + "\n").encode())
            out, fd, deadline = b"", self.process.stdout.fileno(), perf_counter() + self.seconds
            while not out.endswith(b"\n"):
                left = deadline - perf_counter()
                ready = select.select([fd], [], [], max(0, left))[0] if left > 0 else []
                if not ready:
                    self._kill()
                    raise TimeoutError("The rule took longer than %s seconds and was stopped." % self.seconds)
                piece = os.read(fd, 65536)
                if not piece:
                    self._kill()
                    raise ValueError("The rule worker stopped.")
                out += piece
        answer = json.loads(out)
        if "error" in answer:
            raise ValueError("The pattern could not run (%s)." % answer["error"])
        return None if answer["m"] is None else tuple(answer["m"])

    def close(self):
        with self.lock:
            self._kill()


MATCHER = Matcher()


def check_pattern(pattern):
    """A sentence saying why a pattern is refused before it runs, or None."""
    if not isinstance(pattern, str) or not pattern:
        return "The rule has no pattern."
    if len(pattern) > PATTERN_LIMIT:
        return "The pattern is longer than %d characters." % PATTERN_LIMIT
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return "The pattern does not compile: %s." % exc
    if compiled.groups != 1:
        return "The pattern must have exactly one capture group; it has %d." % compiled.groups
    if re.search(r"\\[1-9]|\(\?P=", pattern):
        return "The pattern uses a back-reference."
    return None


def _hardcodes(pattern, raw, value):
    """True when the pattern spells out the value it captured, so it would not read another contract."""
    bare = re.sub(r"\{\d*,?\d*\}|\[[^\]]*\]", "", pattern).replace("\\", "")
    for token in {raw.strip().rstrip("%"), value}:
        if token and sum(c.isdigit() for c in token) >= 2 and token in bare:
            return True
    return False


def run_rule(rule, text, matcher=MATCHER):
    """One rule on normalized text -> {"value", "raw", "quote", "error"}."""
    term = TERM.get(rule.get("field"))
    if term is None:
        return {"value": None, "raw": None, "quote": None, "error": "Unknown term."}
    refused = check_pattern(rule.get("pattern"))
    if refused:
        return {"value": None, "raw": None, "quote": None, "error": refused}
    try:
        found = matcher.search(rule["pattern"], text)
    except (TimeoutError, ValueError) as exc:
        return {"value": None, "raw": None, "quote": None, "error": str(exc)}
    if found is None or found[2] is None:
        return {"value": None, "raw": None, "quote": None, "error": "The rule found nothing."}
    start, end, raw, _, _ = found
    value = canonical(term["type"], raw, term.get("options"), rule.get("map"))
    if value is None:
        return {"value": None, "raw": raw, "quote": None,
                "error": "The rule captured %r, which is not a %s." % (raw[:60], term["type"])}
    if term["type"] != "choice" and _hardcodes(rule["pattern"], raw, value):
        return {"value": None, "raw": raw, "quote": None,
                "error": "The pattern spells out the value it captured, so it is refused."}
    return {"value": value, "raw": raw, "quote": sentence_at(text, start, end), "error": None}


def apply(template, text, matcher=MATCHER):
    """Run every rule of `template` on `text`; a term a rule does not find is null, never guessed."""
    started = perf_counter()
    text = normalize(text)
    by_field = {r.get("field"): r for r in template.get("rules", [])}
    terms = []
    for term in TERMS:
        rule = by_field.get(term["field"])
        result = run_rule(rule, text, matcher) if rule else {"value": None, "raw": None, "quote": None,
                                                            "error": "The template has no rule for this term."}
        terms.append({"field": term["field"], "label": term["label"], "type": term["type"],
                      "value": result["value"], "display": display(term["field"], result["value"]),
                      "quote": result["quote"], "error": result["error"]})
    return {"terms": terms, "found": sum(t["value"] is not None for t in terms), "total": len(terms),
            "milliseconds": "%.1f" % ((perf_counter() - started) * 1000)}
