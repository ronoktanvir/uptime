"""Demo line: Uptime's fixed interpreter for contract templates.

A template is data: per term, a regular expression with exactly one capture group, the term's type and (for a
choice) a map from captured phrase to option. Nothing in a template runs as code. Each match runs in a separate
Python worker process with a time limit, so a runaway pattern fails its rule instead of hanging the server.

Every match of a rule is found. A rule that matches in more than one place with different values reads nothing
(value null, with an error naming how many places matched); identical values in several places are accepted.
`value_in_sentence` and `plausibility` are the code checks a guarded read runs on the values.
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
TEXT_LIMIT = 200_000  # characters; the sample contracts are about 6,000

# The fixed term set an SLA credit needs. `question` is how Jev is asked whether a sentence supports the term: it
# asks what the sentence literally says, not how Uptime names the term ("Lower Threshold means 99.0%" is a yes).
TERMS = (
    {"field": "availability_target_percent", "label": "Availability commitment", "type": "percent",
     "describe": "the availability percentage the provider commits to in each measurement period",
     "question": "Does this sentence give {display} as the availability level the provider commits to?"},
    {"field": "measurement_period", "label": "Measurement period", "type": "choice",
     "options": {"calendar_month": "Calendar month", "calendar_quarter": "Calendar quarter", "calendar_year": "Calendar year"},
     "describe": "the period over which availability is measured",
     "question": "Does this sentence say availability is measured over each {display_lower}?"},
    {"field": "tier_1_credit_percent", "label": "Credit, first tier below the commitment", "type": "percent",
     "describe": "the service credit, as a percent of fees, when availability is below the commitment but not below the second tier's threshold",
     "question": "Does this sentence give {display} of the fees as the service credit for the first, smallest credit level?"},
    {"field": "tier_2_threshold_percent", "label": "Second tier starts below", "type": "percent",
     "describe": "the availability percentage below which the second, larger credit tier applies",
     "question": "Does this sentence give {display} as an availability level at which the service credit changes, such as a threshold or the boundary between credit levels?"},
    {"field": "tier_2_credit_percent", "label": "Credit, second tier", "type": "percent",
     "describe": "the service credit, as a percent of fees, in the second (larger) tier",
     "question": "Does this sentence give {display} of the fees as the service credit for a lower availability level, the larger credit level?"},
    {"field": "credit_cap_percent", "label": "Credit cap", "type": "percent",
     "describe": "the most credits can total in one measurement period, as a percent of fees",
     "question": "Does this sentence limit the total service credits for a period to {display} of the fees?"},
    {"field": "claim_window_days", "label": "Claim window", "type": "integer", "unit": "days",
     "describe": "how many days the customer has to submit a credit claim",
     "question": "Does this sentence give {display} as the time within which a credit claim must be made?"},
    {"field": "maintenance_notice_hours", "label": "Scheduled-maintenance notice", "type": "integer", "unit": "hours",
     "describe": "how many hours of prior notice the provider must give before scheduled maintenance",
     "question": "Does this sentence require at least {display} of notice before scheduled maintenance?"},
    {"field": "credit_application", "label": "How a credit is applied", "type": "choice",
     "options": {"next_invoice": "Against the next invoice", "refund": "Paid as a refund",
                 "account_balance": "Held as an account balance"},
     "describe": "how an awarded service credit reaches the customer",
     "question": "Does this sentence say how a service credit reaches the customer, namely {display_lower}?"},
)
TERM = {t["field"]: t for t in TERMS}
WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
MAX_MATCHES = 50
# For a choice term, the word a sentence must contain for the option to be "in" it.
CHOICE_WORDS = {"calendar_month": r"\bmonth\b", "calendar_quarter": r"\bquarter\b", "calendar_year": r"\byear\b",
                "next_invoice": r"\binvoice\b", "refund": r"\brefund", "account_balance": r"\bbalance\b"}
PERCENT_FIELDS = tuple(t["field"] for t in TERMS if t["type"] == "percent")


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
        found = []
        for m in re.compile(job["pattern"], re.IGNORECASE).finditer(job["text"]):
            found.append([m.start(), m.end(), m.group(1), m.start(1), m.end(1)])
            if len(found) >= job["limit"]:
                break
        out = {"m": found}
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

    def search_all(self, pattern, text, limit=MAX_MATCHES):
        """-> [(start, end, group, gstart, gend), ...] for every match, at most `limit`. Raises TimeoutError / ValueError."""
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self._start()
            self.process.stdin.write((json.dumps({"pattern": pattern, "text": text, "limit": limit}) + "\n").encode())
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
        return [tuple(m) for m in answer["m"]]

    def search(self, pattern, text):
        """The first match, or None."""
        found = self.search_all(pattern, text, 1)
        return found[0] if found else None

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


def _empty(error, raw=None, places=0, ambiguous=False):
    return {"value": None, "raw": raw, "quote": None, "error": error, "places": places, "ambiguous": ambiguous}


def run_rule(rule, text, matcher=MATCHER):
    """One rule on normalized text -> {"value", "raw", "quote", "error", "places", "ambiguous"}.

    Every match is found. Different values in more than one place: value null, ambiguous, never a guess."""
    term = TERM.get(rule.get("field"))
    if term is None:
        return _empty("Unknown term.")
    refused = check_pattern(rule.get("pattern"))
    if refused:
        return _empty(refused)
    if term["type"] == "choice":
        unknown = sorted({str(v) for v in (rule.get("map") or {}).values()} - set(term["options"]))
        if not isinstance(rule.get("map"), dict) or unknown:
            return _empty("The rule's map names %s, which %s not an option (options: %s)." % (
                ", ".join(unknown) or "nothing", "is" if len(unknown) == 1 else "are", ", ".join(term["options"])))
    try:
        found = matcher.search_all(rule["pattern"], text)
    except (TimeoutError, ValueError) as exc:
        return _empty(str(exc))
    found = [f for f in found if f[2] is not None]
    if not found:
        return _empty("The rule found nothing.")
    values = [canonical(term["type"], f[2], term.get("options"), rule.get("map")) for f in found]
    distinct = {v if v is not None else ("raw", f[2].strip().lower()) for v, f in zip(values, found)}
    if len(distinct) > 1:
        shown = sorted({v if v is not None else f[2].strip()[:30] for v, f in zip(values, found)})
        more = " or more" if len(found) >= MAX_MATCHES else ""
        return _empty("The rule matched in %d%s places with %d different values (%s), so it reads nothing here."
                      % (len(found), more, len(distinct), ", ".join(shown)), found[0][2], len(found), True)
    start, end, raw, _, _ = found[0]
    value = values[0]
    if value is None:
        return _empty("The rule captured %r, which is not a %s." % (raw[:60], term["type"]), raw, len(found))
    if term["type"] != "choice" and _hardcodes(rule["pattern"], raw, value):
        return _empty("The pattern spells out the value it captured, so it is refused.", raw, len(found))
    return {"value": value, "raw": raw, "quote": sentence_at(text, start, end), "error": None,
            "places": len(found), "ambiguous": False}


def apply(template, text, matcher=MATCHER):
    """Run every rule of `template` on `text`; a term a rule does not find is null, never guessed."""
    started = perf_counter()
    too_long = len(text) > TEXT_LIMIT
    text = "" if too_long else normalize(text)
    by_field = {r.get("field"): r for r in template.get("rules", [])}
    terms = []
    for term in TERMS:
        rule = by_field.get(term["field"])
        if too_long:
            result = _empty("The contract is too long for the interpreter.")
        else:
            result = run_rule(rule, text, matcher) if rule else _empty("The template has no rule for this term.")
        terms.append({"field": term["field"], "label": term["label"], "type": term["type"],
                      "value": result["value"], "display": display(term["field"], result["value"]),
                      "quote": result["quote"], "error": result["error"], "places": result["places"],
                      "ambiguous": result["ambiguous"]})
    return {"terms": terms, "found": sum(t["value"] is not None for t in terms), "total": len(terms),
            "milliseconds": "%.1f" % ((perf_counter() - started) * 1000)}


# --- Value checks (code, no model) --------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_NUMBER_WORD = "|".join(sorted(list(WORDS) + list(TENS), key=len, reverse=True))
_NUMBER_WORDS = re.compile(r"\b(?:%s)(?:[ -](?:%s))*\b" % (_NUMBER_WORD, _NUMBER_WORD))


def value_in_sentence(field, value, sentence):
    """True when `value` is literally in `sentence`: as digits ("99.95%", "(30)") or number words ("seventy-two")
    for a number, or the option's own word ("month", "invoice") for a choice. Code only."""
    term = TERM.get(field)
    if term is None or value is None or not isinstance(sentence, str) or not sentence.strip():
        return False
    text = normalize(sentence)
    if term["type"] == "choice":
        word = CHOICE_WORDS.get(value)
        return bool(word and re.search(word, text, re.IGNORECASE))
    try:
        wanted = Decimal(str(value))
    except InvalidOperation:
        return False
    for match in _NUMBER.finditer(text):
        try:
            if Decimal(match.group().replace(",", "")) == wanted:
                return True
        except InvalidOperation:
            continue
    if wanted == wanted.to_integral_value():
        for match in _NUMBER_WORDS.finditer(text.lower()):
            if _words_to_int(match.group()) == wanted:
                return True
    return False


def _number(values, field):
    raw = values.get(field)
    if raw is None:
        return None
    try:
        number = Decimal(str(raw))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def plausibility(values):
    """Sentences naming each implausible combination of `values` (field -> value string or None); empty when
    plausible. A missing value is not judged here (the completeness guard reports it)."""
    problems = []
    n = {f: _number(values, f) for f in PERCENT_FIELDS + ("claim_window_days", "maintenance_notice_hours")}
    for f in PERCENT_FIELDS:
        if values.get(f) is not None and (n[f] is None or not Decimal(0) <= n[f] <= Decimal(100)):
            problems.append("%s (%s) is not a percentage between 0 and 100." % (TERM[f]["label"], values.get(f)))
    target, threshold = n["availability_target_percent"], n["tier_2_threshold_percent"]
    if target is not None and threshold is not None and not threshold < target:
        problems.append("The second tier's threshold (%s%%) is not below the commitment (%s%%)." % (threshold, target))
    first, second = n["tier_1_credit_percent"], n["tier_2_credit_percent"]
    if first is not None and second is not None and not second > first:
        problems.append("The second tier's credit (%s%%) is not above the first tier's (%s%%)." % (second, first))
    cap, credits = n["credit_cap_percent"], [c for c in (first, second) if c is not None]
    if cap is not None and credits and cap < max(credits):
        problems.append("The credit cap (%s%%) is below the highest credit (%s%%)." % (cap, max(credits)))
    for f in ("claim_window_days", "maintenance_notice_hours"):
        if values.get(f) is not None and (n[f] is None or n[f] <= 0):
            problems.append("%s (%s) is not a positive number of %s." % (TERM[f]["label"], values.get(f), TERM[f]["unit"]))
    return problems
