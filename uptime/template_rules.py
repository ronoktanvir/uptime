"""Demo line: Uptime's fixed interpreter for contract templates.

A template is data: per term, a regular expression (or, for the credit schedule, one to six row patterns), the term's
type and, for a choice, a map from captured phrase to option. Nothing in a template runs as code. Each match runs in a
separate Python worker process with a time limit, so a runaway pattern fails its rule instead of hanging the server.

Every match of a rule is found. A rule that matches in more than one place with different values reads nothing
(value null, with an error naming how many places matched); identical values in several places are accepted.
`value_in_sentence` and `plausibility` are the code checks a guarded read runs on the values.

Term types (interpreter version 3, docs/demo/TEMPLATE-BUILDER.md, "Version 3"):

- percent: a decimal string without "%" ("99.95"); integer is no longer a term type.
- choice: an option id.
- schedule (`credit_schedule`): one to six rows, each {"below_percent", "credit_percent"}: availability below that
  percentage earns that credit. Rows are ordered by threshold, highest first; thresholds fall as credits rise. A row's
  pattern has the named groups `below` and `credit`, or only `credit` with `"below": "commitment"` when its sentence
  states the threshold as the commitment itself. Each row is matched in its own sentence or line.
- duration (`claim_window`, `maintenance_notice`): {"value": digits, "unit": one of the term's units}. The unit is the
  one the contract writes, never converted. The pattern has the named groups `value` and `unit`.
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
MAX_TIERS = 6
INTERPRETER = "uptime.template_rules/3"

# The fixed term set an SLA credit needs. `question` is how Jev is asked whether a sentence supports the term: it
# asks what the sentence literally says, not how Uptime names the term ("Lower Threshold means 99.0%" is a yes).
# The schedule is asked about once per row.
TERMS = (
    {"field": "availability_target_percent", "label": "Availability commitment", "type": "percent",
     "describe": "the availability percentage the provider commits to in each measurement period",
     "question": "Does this sentence give {display} as the availability level the provider commits to?"},
    {"field": "measurement_period", "label": "Measurement period", "type": "choice",
     "options": {"calendar_month": "Calendar month", "calendar_quarter": "Calendar quarter", "calendar_year": "Calendar year"},
     "describe": "the period over which availability is measured",
     "question": "Does this sentence, in the words \"{phrase}\", make each {display_lower} the measurement period?"},
    {"field": "credit_schedule", "label": "Credit schedule", "type": "schedule",
     "describe": "every service-credit tier: for each, the availability percentage below which it applies and the "
                 "credit it earns as a percent of fees (one to six tiers; a single flat credit is one tier)",
     "question": "Does this sentence give a service credit of {credit}% of the fees when availability is below {below}?"},
    {"field": "credit_cap_percent", "label": "Credit cap", "type": "percent",
     "describe": "the most credits can total in one measurement period, as a percent of fees",
     "question": "Does this sentence limit the total service credits for a period to {display} of the fees?"},
    {"field": "claim_window", "label": "Claim window", "type": "duration",
     "units": {"days": "days", "business_days": "business days", "months": "months"},
     "describe": "how long the customer has to submit a credit claim, as a number and the unit the contract uses",
     "question": "Does this sentence give {display} as the time within which a credit claim must be made?"},
    {"field": "maintenance_notice", "label": "Scheduled-maintenance notice", "type": "duration",
     "units": {"hours": "hours", "days": "days", "business_days": "business days"},
     "describe": "how much prior notice the provider must give before scheduled maintenance, as a number and the "
                 "unit the contract uses",
     "question": "Does this sentence require at least {display} of notice before scheduled maintenance?"},
    {"field": "credit_application", "label": "How a credit is applied", "type": "choice",
     "options": {"next_invoice": "Against the next invoice", "refund": "Paid as a refund",
                 "account_balance": "Held as an account balance"},
     "describe": "how an awarded service credit reaches the customer",
     "question": "Does this sentence, in the words \"{phrase}\", say that a service credit reaches the customer {display_lower}?"},
)
TERM = {t["field"]: t for t in TERMS}
WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
MAX_MATCHES = 50
NOT_STATED = "Not stated in the contract this template was built from"
PERCENT_FIELDS = tuple(t["field"] for t in TERMS if t["type"] == "percent")
DURATION_FIELDS = tuple(t["field"] for t in TERMS if t["type"] == "duration")
# The unit phrases a duration may capture, as the contract writes them. Nothing else is a unit; nothing is converted.
UNIT_PHRASES = {"hour": "hours", "hours": "hours", "day": "days", "days": "days", "calendar day": "days",
                "calendar days": "days", "business day": "business_days", "business days": "business_days",
                "month": "months", "months": "months", "calendar month": "months", "calendar months": "months"}
UNIT_WORDS = {"hours": ("hour", "hours"), "days": ("day", "days"), "business_days": ("business day", "business days"),
              "months": ("month", "months")}
UNIT_IN_SENTENCE = {"hours": r"\bhours?\b", "days": r"(?<!business )\bdays?\b", "business_days": r"\bbusiness days?\b",
                    "months": r"\bmonths?\b"}
# Words that let a row state its threshold as the commitment itself ("below the Availability Commitment").
COMMITMENT_WORDS = r"\b(?:commitment|committed|guarantee|guaranteed|service level|sla|slo|target)\b"
SCHEDULE_GROUPS = {"below", "credit"}
DURATION_GROUPS = {"value", "unit"}


def normalize(text):
    """One space for any run of whitespace; straight quotes for curly ones."""
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    return re.sub(r"\s+", " ", text).strip()


def normalize_lines(text):
    """(normalize(text), line) where line[i] is the line of the original text that normalized character i came from.
    A collapsed run of whitespace belongs to the line before it."""
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    out, lines, line = [], [], 0
    for m in re.finditer(r"\s+|\S+", text):
        token = m.group()
        if token[0].isspace():
            if out:
                out.append(" ")
                lines.append(line)
            line += token.count("\n")
        else:
            out.append(token)
            lines.extend([line] * len(token))
    if out and out[-1] == " ":
        out.pop()
        lines.pop()
    return "".join(out), lines


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


def canonical_unit(field, raw):
    """A duration's unit id from the phrase the contract writes ("Business Days" -> business_days), or None."""
    if raw is None:
        return None
    phrase = re.sub(r"[^a-z_ ]", "", normalize(str(raw)).lower()).strip()
    unit = UNIT_PHRASES.get(phrase) or (phrase if phrase in UNIT_WORDS else None)
    return unit if unit in TERM[field]["units"] else None


def canonical_duration(field, value, unit):
    """{"value": digits, "unit": unit id} or None. Nothing is converted between units."""
    number, unit_id = canonical("integer", value), canonical_unit(field, unit)
    if number is None or unit_id is None:
        return None
    return {"value": number, "unit": unit_id}


def order_schedule(rows):
    """(rows ordered by threshold, highest first, with identical rows merged; None) or (None, why it is refused).

    Refused: no row, more than six, a threshold repeated with different credits, or thresholds that do not fall as
    the credits rise."""
    unique = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    by_threshold = {}
    for row in unique:
        by_threshold.setdefault(Decimal(row["below_percent"]), []).append(row["credit_percent"])
    for below, credits in by_threshold.items():
        if len(credits) > 1:
            return None, ("The schedule gives %s different credits (%s) for availability below %s%%."
                          % (len(credits), ", ".join(c + "%" for c in credits), format(below.normalize(), "f")))
    if not unique:
        return None, "The schedule has no tier."
    if len(unique) > MAX_TIERS:
        return None, "The schedule has %d tiers; at most %d are read." % (len(unique), MAX_TIERS)
    ordered = sorted(unique, key=lambda r: Decimal(r["below_percent"]), reverse=True)
    for upper, lower in zip(ordered, ordered[1:]):
        if not Decimal(lower["credit_percent"]) > Decimal(upper["credit_percent"]):
            return None, ("The schedule's thresholds do not fall as the credits rise: below %s%% earns %s%%, below %s%% "
                          "earns %s%%." % (upper["below_percent"], upper["credit_percent"], lower["below_percent"],
                                           lower["credit_percent"]))
    return ordered, None


def canonical_schedule(rows, commitment=None):
    """Raw rows [{"below": number or "commitment", "credit": number}] -> (ordered schedule, None) or (None, why)."""
    if not isinstance(rows, list):
        return None, "The schedule is not a list of tiers."
    out = []
    for row in rows:
        if not isinstance(row, dict):
            return None, "A tier is not an object."
        below = row.get("below")
        if isinstance(below, str) and below.strip().lower() == "commitment":
            if commitment is None:
                return None, "A tier's threshold is the commitment, but the commitment has no value."
            below = commitment
        b, c = canonical("percent", below), canonical("percent", row.get("credit"))
        if b is None or c is None:
            return None, "A tier is not two percentages (below %r, credit %r)." % (row.get("below"), row.get("credit"))
        out.append({"below_percent": b, "credit_percent": c})
    return order_schedule(out)


def display(field, value):
    if value is None:
        return None
    term = TERM[field]
    if term["type"] == "percent":
        return value + "%"
    if term["type"] == "integer":
        return value + " " + term["unit"]
    if term["type"] == "schedule":
        return "; ".join("below %s%%: %s%%" % (r["below_percent"], r["credit_percent"]) for r in value)
    if term["type"] == "duration":
        one, many = UNIT_WORDS[value["unit"]]
        return "%s %s" % (value["value"], one if value["value"] == "1" else many)
    return term["options"][value]


def same(a, b):
    """Two term values are the same (lists and objects compared by content)."""
    return canonical_json(a) == canonical_json(b)


# --- Sentences --------------------------------------------------------------------------

_ABBREVIATIONS = ("Inc.", "Co.", "No.", "Ltd.", "e.g.", "i.e.", "U.S.", "St.")


def sentence_bounds(text, start, end):
    """[left, right) of the sentence (or list item) of normalized `text` around [start, end)."""
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
    return left, min(len(text), right + 1)


def sentence_at(text, start, end):
    """The sentence (or list item) of normalized `text` around [start, end)."""
    left, right = sentence_bounds(text, start, end)
    return text[left:right].strip()


def row_bounds(text, lines, start, end):
    """The sentence around a match, clipped to the original lines the match spans: a table row's line, or a sentence."""
    left, right = sentence_bounds(text, start, end)
    if lines:
        first, last = lines[start], lines[max(start, end - 1)]
        while left < start and lines[left] < first:
            left += 1
        while right > end and lines[right - 1] > last:
            right -= 1
    while left < right and text[left] == " ":
        left += 1
    while right > left and text[right - 1] == " ":
        right -= 1
    return left, right


# --- The time-limited matcher -------------------------------------------------------------

_WORKER = r"""
import json, re, sys
for line in sys.stdin:
    try:
        job = json.loads(line)
        found = []
        for m in re.compile(job["pattern"], re.IGNORECASE).finditer(job["text"]):
            one = m.re.groups >= 1
            found.append([m.start(), m.end(), m.group(1) if one else None, m.start(1) if one else -1,
                          m.end(1) if one else -1, m.groupdict()])
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
        """-> [(start, end, group1, gstart, gend, groupdict), ...] for every match, at most `limit`.
        Raises TimeoutError / ValueError."""
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


def check_pattern(pattern, names=None):
    """A sentence saying why a pattern is refused before it runs, or None. With `names`, the pattern must have exactly
    those named groups and no other group; without, exactly one capture group."""
    if not isinstance(pattern, str) or not pattern:
        return "The rule has no pattern."
    if len(pattern) > PATTERN_LIMIT:
        return "The pattern is longer than %d characters." % PATTERN_LIMIT
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return "The pattern does not compile: %s." % exc
    if names is None and compiled.groups != 1:
        return "The pattern must have exactly one capture group; it has %d." % compiled.groups
    if names is not None and (compiled.groups != len(names) or set(compiled.groupindex) != set(names)):
        return "The pattern must have exactly the named groups %s and no other capture group." % ", ".join(
            "(?P<%s>...)" % n for n in sorted(names))
    if re.search(r"\\[1-9]|\(\?P=", pattern):
        return "The pattern uses a back-reference."
    return None


def _hardcodes(pattern, raw, value):
    """True when the pattern spells out the value it captured, so it would not read another contract."""
    bare = re.sub(r"\{\d*,?\d*\}|\[[^\]]*\]", "", pattern).replace("\\", "")
    for token in {(raw or "").strip().rstrip("%"), value}:
        if token and sum(c.isdigit() for c in token) >= 2 and token in bare:
            return True
    return False


def _empty(error, raw=None, places=0, ambiguous=False):
    return {"value": None, "raw": raw, "quote": None, "error": error, "places": places, "ambiguous": ambiguous}


def _one_value(rule, text, matcher, names, convert):
    """A rule read as one value: every match converted; different values in several places read nothing."""
    try:
        found = matcher.search_all(rule["pattern"], text)
    except (TimeoutError, ValueError) as exc:
        return _empty(str(exc))
    found = [f for f in found if (f[5] if names else f[2]) is not None and (not names or all(f[5].get(n) is not None for n in names))]
    if not found:
        return _empty("The rule found nothing.")
    converted = [convert(f) for f in found]
    values = [v for v, _ in converted]
    raws = [r for _, r in converted]
    distinct = {canonical_json(v) if v is not None else "raw:" + r.strip().lower() for v, r in zip(values, raws)}
    if len(distinct) > 1:
        shown = sorted({display(rule["field"], v) if v is not None else r.strip()[:30] for v, r in zip(values, raws)})
        more = " or more" if len(found) >= MAX_MATCHES else ""
        return _empty("The rule matched in %d%s places with %d different values (%s), so it reads nothing here."
                      % (len(found), more, len(distinct), ", ".join(shown)), raws[0], len(found), True)
    start, end = found[0][0], found[0][1]
    value, raw = values[0], raws[0]
    if value is None:
        return _empty("The rule captured %r, which is not a %s." % (raw[:60], TERM[rule["field"]]["type"]), raw, len(found))
    return {"value": value, "raw": raw, "quote": sentence_at(text, start, end), "error": None,
            "places": len(found), "ambiguous": False, "_number": raw}


def _run_schedule(rule, text, matcher, lines, commitment):
    """A schedule rule: every match of every row pattern is a tier; each tier in its own sentence or line."""
    rows = rule.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_TIERS:
        return _empty("A schedule rule needs one to %d row patterns." % MAX_TIERS)
    found = []  # (unit bounds, start, value row)
    for i, row_rule in enumerate(rows, 1):
        if not isinstance(row_rule, dict) or "pattern" not in row_rule or not set(row_rule) <= {"pattern", "below"}:
            return _empty("Row pattern %d is not {pattern} or {pattern, below}." % i)
        fixed = row_rule.get("below")
        if fixed not in (None, "commitment"):
            return _empty('Row pattern %d: "below" may only be "commitment".' % i)
        names = {"credit"} if fixed else SCHEDULE_GROUPS
        refused = check_pattern(row_rule["pattern"], names)
        if refused:
            return _empty("Row pattern %d: %s" % (i, refused))
        try:
            matches = matcher.search_all(row_rule["pattern"], text)
        except (TimeoutError, ValueError) as exc:
            return _empty("Row pattern %d: %s" % (i, exc))
        for start, end, _, _, _, groups in matches:
            if groups.get("credit") is None or (not fixed and groups.get("below") is None):
                continue
            if fixed and commitment is None:
                return _empty("Row pattern %d takes its threshold from the commitment, which was not read." % i)
            below = commitment if fixed else canonical("percent", groups["below"])
            credit = canonical("percent", groups["credit"])
            if below is None or credit is None:
                return _empty("Row pattern %d captured %r and %r, which are not two percentages."
                              % (i, groups.get("below") or "the commitment", groups["credit"]), groups["credit"], len(matches))
            if _hardcodes(row_rule["pattern"], groups["credit"], credit) or (
                    not fixed and _hardcodes(row_rule["pattern"], groups["below"], below)):
                return _empty("Row pattern %d spells out a value it captured, so it is refused." % i)
            found.append((row_bounds(text, lines, start, end), start, {"below_percent": below, "credit_percent": credit}))
    if not found:
        return _empty("The rule found no tier.")
    by_unit = {}
    for bounds, _, row in found:
        by_unit.setdefault(bounds, [])
        if row not in by_unit[bounds]:
            by_unit[bounds].append(row)
    crowded = [rows_ for rows_ in by_unit.values() if len(rows_) > 1]
    if crowded:
        return _empty("Two different tiers were matched in one sentence or line (%s), so the schedule reads nothing here."
                      % display("credit_schedule", crowded[0]), None, len(found), True)
    ordered, error = order_schedule([row for _, _, row in sorted(found, key=lambda f: f[1])])
    if error:
        return _empty(error + " The schedule reads nothing here.", None, len(found), "different credits" in error)
    quotes = []
    for row in ordered:
        bounds = min((f for f in found if f[2] == row), key=lambda f: f[1])[0]
        quotes.append(text[bounds[0]:bounds[1]])
    return {"value": ordered, "raw": None, "quote": quotes, "error": None, "places": len(found), "ambiguous": False}


def run_rule(rule, text, matcher=MATCHER, lines=None, commitment=None):
    """One rule on normalized text -> {"value", "raw", "quote", "error", "places", "ambiguous"}.

    Every match is found. Different values in more than one place: value null, ambiguous, never a guess. A schedule
    rule's value is a list of tiers and its quote a list of sentences, one per tier; `lines` (from normalize_lines)
    lets a table row on its own line count as its own row, and `commitment` is the read commitment for a row whose
    threshold is the commitment itself."""
    term = TERM.get(rule.get("field"))
    if term is None:
        return _empty("Unknown term.")
    if term["type"] == "schedule":
        result = _run_schedule(rule, text, matcher, lines, commitment)
        result.pop("_number", None)
        return result
    names = DURATION_GROUPS if term["type"] == "duration" else None
    refused = check_pattern(rule.get("pattern"), names)
    if refused:
        return _empty(refused)
    if term["type"] == "choice":
        unknown = sorted({str(v) for v in (rule.get("map") or {}).values()} - set(term["options"]))
        if not isinstance(rule.get("map"), dict) or unknown:
            return _empty("The rule's map names %s, which %s not an option (options: %s)." % (
                ", ".join(unknown) or "nothing", "is" if len(unknown) == 1 else "are", ", ".join(term["options"])))
    if term["type"] == "duration":
        def convert(f):
            g = f[5]
            return canonical_duration(term["field"], g["value"], g["unit"]), "%s %s" % (g["value"], g["unit"])
    else:
        def convert(f):
            return canonical(term["type"], f[2], term.get("options"), rule.get("map")), f[2]
    result = _one_value(rule, text, matcher, names, convert)
    raw = result.pop("_number", None)
    if result["value"] is not None and term["type"] != "choice":
        number = raw.split(" ", 1)[0] if term["type"] == "duration" else raw
        shown = result["value"]["value"] if term["type"] == "duration" else result["value"]
        if _hardcodes(rule["pattern"], number, shown):
            return _empty("The pattern spells out the value it captured, so it is refused.", raw, result["places"])
    return result


def apply(template, text, matcher=MATCHER):
    """Run every rule of `template` on `text`; a term a rule does not find is null, never guessed. A field the
    template lists under `not_stated` has no rule: null, `stated: false`, and not counted in `total`."""
    started = perf_counter()
    too_long = len(text) > TEXT_LIMIT
    text, lines = ("", []) if too_long else normalize_lines(text)
    by_field = {r.get("field"): r for r in template.get("rules", [])}
    not_stated = [f for f in template.get("not_stated", []) if f in TERM and f not in by_field]
    terms, values = [], {}
    for term in TERMS:
        rule = by_field.get(term["field"])
        if term["field"] in not_stated:
            result = _empty(NOT_STATED)
        elif too_long:
            result = _empty("The contract is too long for the interpreter.")
        elif rule is None:
            result = _empty("The template has no rule for this term.")
        else:
            result = run_rule(rule, text, matcher, lines, values.get("availability_target_percent"))
        values[term["field"]] = result["value"]
        terms.append({"field": term["field"], "label": term["label"], "type": term["type"],
                      "value": result["value"], "display": display(term["field"], result["value"]),
                      "quote": result["quote"], "error": result["error"], "places": result["places"],
                      "ambiguous": result["ambiguous"], "stated": term["field"] not in not_stated,
                      **({"phrase": result["raw"] if result["value"] is not None else None}
                         if term["type"] == "choice" else {})})
    return {"terms": terms, "found": sum(t["value"] is not None for t in terms), "total": len(terms) - len(not_stated),
            "not_stated": not_stated,
            "milliseconds": "%.1f" % ((perf_counter() - started) * 1000)}


# --- Value checks (code, no model) --------------------------------------------------------

_NUMBER = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_NUMBER_WORD = "|".join(sorted(list(WORDS) + list(TENS), key=len, reverse=True))
_NUMBER_WORDS = re.compile(r"\b(?:%s)(?:[ -](?:%s))*\b" % (_NUMBER_WORD, _NUMBER_WORD))


def _number_in(value, text):
    """True when the number `value` is in `text` as digits, or as number words for a whole number."""
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


def row_in_sentence(row, sentence, commitment=None):
    """A tier is in its sentence: its credit is written there, and its threshold too, or the threshold is the
    commitment and the sentence names the commitment."""
    if not isinstance(row, dict) or not isinstance(sentence, str) or not sentence.strip():
        return False
    text = normalize(sentence)
    if not _number_in(row.get("credit_percent"), text):
        return False
    if _number_in(row.get("below_percent"), text):
        return True
    return (commitment is not None and same(canonical("percent", commitment), row.get("below_percent"))
            and bool(re.search(COMMITMENT_WORDS, text, re.IGNORECASE)))


def phrase_in(phrase, sentence):
    """True when the contract's own phrase is literally in the sentence (whitespace and quote marks normalized,
    letter case ignored)."""
    if not isinstance(phrase, str) or not phrase.strip() or not isinstance(sentence, str):
        return False
    return normalize(phrase).lower() in normalize(sentence).lower()


def value_in_sentence(field, value, sentence, commitment=None, phrase=None):
    """True when `value` is literally in `sentence`: as digits ("99.95%", "(30)") or number words ("seventy-two")
    for a number, the number and the unit for a duration, and every tier in its own sentence for a schedule
    (`sentence` is then the list of tier sentences). For a choice, `phrase` is the contract's own words that give the
    option (the readers copy them from the contract), and the check is that those words are in the sentence; which
    option the words give is what the readers agree on, the rule's map records and Jev is asked about. No list of
    expected words is used. Code only."""
    term = TERM.get(field)
    if term is None or value is None:
        return False
    if term["type"] == "schedule":
        return (isinstance(value, list) and isinstance(sentence, list) and len(value) == len(sentence) and bool(value)
                and all(row_in_sentence(r, s, commitment) for r, s in zip(value, sentence)))
    if not isinstance(sentence, str) or not sentence.strip():
        return False
    text = normalize(sentence)
    if term["type"] == "choice":
        return value in term["options"] and phrase_in(phrase, text)
    if term["type"] == "duration":
        return (isinstance(value, dict) and value.get("unit") in UNIT_IN_SENTENCE
                and _number_in(value.get("value"), text)
                and bool(re.search(UNIT_IN_SENTENCE[value["unit"]], text, re.IGNORECASE)))
    return _number_in(value, text)


def _number(values, field):
    raw = values.get(field)
    if raw is None or isinstance(raw, (list, dict)):
        return None
    try:
        number = Decimal(str(raw))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def plausibility(values):
    """Sentences naming each implausible combination of `values` (field -> value or None); empty when plausible. A
    missing value is not judged here (the completeness guard reports it)."""
    problems = []
    n = {f: _number(values, f) for f in PERCENT_FIELDS}
    for f in PERCENT_FIELDS:
        if values.get(f) is not None and (n[f] is None or not Decimal(0) <= n[f] <= Decimal(100)):
            problems.append("%s (%s) is not a percentage between 0 and 100." % (TERM[f]["label"], values.get(f)))
    target, cap = n["availability_target_percent"], n["credit_cap_percent"]
    schedule = values.get("credit_schedule")
    credits = []
    if schedule is not None:
        rows = schedule if isinstance(schedule, list) else None
        ordered, error = (None, "The credit schedule is not a list of tiers.") if rows is None else (
            canonical_schedule([{"below": r.get("below_percent"), "credit": r.get("credit_percent")}
                                for r in rows if isinstance(r, dict)]) if all(isinstance(r, dict) for r in rows)
            else (None, "A tier is not an object."))
        if error:
            problems.append(error)
        else:
            credits = [Decimal(r["credit_percent"]) for r in ordered]
            if target is not None and Decimal(ordered[0]["below_percent"]) > target:
                problems.append("A tier's threshold (%s%%) is above the commitment (%s%%)."
                                % (ordered[0]["below_percent"], values.get("availability_target_percent")))
    if cap is not None and credits and cap < max(credits):
        problems.append("The credit cap (%s%%) is below the highest credit (%s%%)." % (cap, format(max(credits).normalize(), "f")))
    for f in DURATION_FIELDS:
        v = values.get(f)
        if v is None:
            continue
        if not isinstance(v, dict) or v.get("unit") not in TERM[f]["units"] or not str(v.get("value", "")).isdigit() \
                or int(v["value"]) <= 0:
            problems.append("%s (%s) is not a positive number of %s." % (
                TERM[f]["label"], canonical_json(v) if not isinstance(v, str) else v,
                " or ".join(TERM[f]["units"].values())))
    return problems
