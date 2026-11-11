"""Demo line: build a deterministic reader (a template) for a contract type Uptime has not read before.

Version 2 (docs/demo/TEMPLATE-BUILDER.md, "Version 2"):

- Jev routes the run. It chooses among the APPROVED templates in this workspace plus `unrecognised`. A match at 0.80 or
  more starts no reader: the contract is read by that template under the read guards (state MATCHED). `unrecognised`
  or under 0.80 starts the readers. Jev unreachable starts nothing (state NEEDS_REVIEWER) until a reviewer chooses to
  build without Jev.
- Three Claude readers that differ in instructions (clause by clause, numbers first, sceptic) and, for the sceptic, in
  model. Three fresh readers read the second contract at the same time; the template's values there must equal what
  they agreed on (no answer key).
- A Claude template builder writes one rule per term (data, run by uptime.template_rules).
- Code checks; Jev per term gates approval through the reviewer's acknowledgement.
- Every later read is guarded (complete, unambiguous, value in sentence, plausible, Jev's template match) and
  persisted on the build; an accepted reading can be handed to `on_reading` (the money link).

A contract may be one of the shipped samples or pasted text (with consent), stored only under this folder. At most
MAX_BUILDS builds start per server process. The authored answer key (expected.json) is never used here.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
from threading import Lock, Thread
from time import perf_counter

from . import template_rules as rules

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "template_builder_demo"
MODEL = "claude-opus-5-5"
SCEPTIC_MODEL = "claude-sonnet-5-5"
CLAUDE_SECONDS = 90
MAX_BUILDS = 12
REPAIR_ROUNDS = 2
JEV_THRESHOLD = Decimal("0.90")
MATCH_THRESHOLD = Decimal("0.80")
PASTE_LIMIT = 60_000
NAME_LIMIT = 200
JEV_CONTEXT = 6000
JEV_QUESTION = 1000
JEV_OPTION = 200
UNRECOGNISED = "unrecognised"
RUNNING = ("QUEUED", "CLASSIFYING", "READING", "BUILDING", "CHECKING")
STEPS = (("classify", "JEV", "Which contract type is this?"), ("reader-1", "CLAUDE", "Reader 1"),
         ("reader-2", "CLAUDE", "Reader 2"), ("reader-3", "CLAUDE", "Reader 3"),
         ("build", "CLAUDE", "Template builder"), ("checks", "UPTIME", "Checks"),
         ("review", "REVIEWER", "Reviewer approval"))
# Reader index -> (role, model). The sceptic runs on a different model.
READERS = {1: ("clause_by_clause", MODEL), 2: ("numbers_first", MODEL), 3: ("sceptic", SCEPTIC_MODEL)}
NOT_STARTED = "Not started: Jev matched an approved template"
# A credit cannot be computed without these; a template whose contract does not state them cannot be approved.
REQUIRED_TERMS = ("availability_target_percent", "credit_schedule")
DISABLED = "Building templates with Claude is off on this server; start it with --template-builder."
GUARD_LABELS = {"complete": "Every rule found a value",
                "unambiguous": "No rule matched in two places with different values",
                "value_in_sentence": "Each value is in the sentence its rule matched",
                "plausible": "The values fit together",
                "template_match": "Jev: this document follows the template"}


class TemplateRefused(Exception):
    """One plain sentence for the reviewer, with an HTTP status."""

    def __init__(self, sentence, status=409):
        super().__init__(sentence)
        self.status = status


class ModelFailed(Exception):
    """A model call failed or answered in the wrong shape; carries a plain sentence."""


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Samples ----------------------------------------------------------------------------

def demo_samples(folder=FIXTURES):
    """The shipped sample contracts, as the fixture folder's samples.json lists them. No vendor is named in code.
    Only each document's customer name is taken from expected.json; its authored terms are never read here."""
    folder = Path(folder)
    customers = {k: v.get("customer") for k, v in json.loads((folder / "expected.json").read_text()).items()}
    samples = []
    for row in json.loads((folder / "samples.json").read_text()):
        def document(ident, row=row):
            text = (folder / (ident + ".txt")).read_text()
            return {"id": ident, "title": row["form"] + " · " + customers[ident], "vendor": row["vendor"],
                    "customer": customers[ident], "chars": len(text),
                    "text_url": "/fixtures/template_builder_demo/" + ident + ".txt",
                    "_path": str(folder / (ident + ".txt"))}
        samples.append({"id": row["id"], "title": row["title"], "form": row["form"], "vendor": row["vendor"],
                        "document": document(row["document"]), "second_document": document(row["second_document"]),
                        "next_documents": [document(ident) for ident in row["next_documents"]]})
    return samples


def shipped_texts(folder=FIXTURES):
    """File names of the sample contracts that may be served: exactly the documents samples.json lists."""
    return {Path(d["_path"]).name for s in demo_samples(folder)
            for d in (s["document"], s["second_document"], *s["next_documents"])}


def public(value):
    """Drop private keys (leading underscore) from a nested answer."""
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [public(v) for v in value]
    return value


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "contract"


# --- Claude through the local Claude Code CLI ---------------------------------------------

class Answer(str):
    """The model's text, carrying `.model`: the model the CLI's own envelope says answered."""
    model = None


class ClaudeCLI:
    """claude(system, prompt, model=None) -> text, through the pinned safe profile: tools off, no session persistence,
    a fresh empty temporary directory, a time limit. The CLI's own sign-in is used; no credential is read here.
    The model is chosen per call and verified from the CLI's JSON envelope (`modelUsage`)."""

    def __init__(self, executable, model=MODEL, timeout=CLAUDE_SECONDS):
        self.executable = str(Path(executable).resolve(strict=True))
        self.model, self.timeout = model, timeout

    def __call__(self, system, prompt, model=None):
        from .correspondence_model_transport import public_environment
        model = model or self.model
        env = public_environment()
        env["PATH"] = os.environ.get("PATH", env["PATH"])
        if "CLAUDE_CODE_OAUTH_TOKEN" in os.environ:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = os.environ["CLAUDE_CODE_OAUTH_TOKEN"]
        argv = [self.executable, "-p", "--safe-mode", "--model", model, "--tools", "", "--strict-mcp-config",
                "--setting-sources", "", "--no-session-persistence", "--output-format", "json",
                "--system-prompt", system]
        with tempfile.TemporaryDirectory(prefix="uptime-template-") as empty:
            try:
                done = subprocess.run(argv, input=prompt, cwd=empty, env=env, capture_output=True, text=True,
                                      timeout=self.timeout)
            except subprocess.TimeoutExpired:
                raise ModelFailed("Claude did not answer within %d seconds." % self.timeout) from None
        if done.returncode:
            raise ModelFailed("The Claude Code CLI ended with an error (exit %d)." % done.returncode)
        try:
            envelope = json.loads(done.stdout)
        except ValueError:
            raise ModelFailed("The Claude Code CLI did not answer in JSON.") from None
        if envelope.get("is_error") is not False or model not in (envelope.get("modelUsage") or {}):
            raise ModelFailed("The answer did not come from %s." % model)
        if not isinstance(envelope.get("result"), str):
            raise ModelFailed("The Claude Code CLI answer had no text.")
        answer = Answer(envelope["result"])
        answer.model = model
        return answer


def strict_object(text):
    """Exactly one JSON object, optionally inside one ```json fence; anything else is refused."""
    raw = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", raw, re.S)
    if fenced:
        raw = fenced.group(1)
    try:
        value = json.loads(raw, parse_float=Decimal)
    except ValueError:
        raise ModelFailed("The answer was not one JSON object.") from None
    if not isinstance(value, dict):
        raise ModelFailed("The answer was not one JSON object.")
    return value


# --- Prompts ----------------------------------------------------------------------------

SYSTEM = "You read contracts for Uptime, a service-credit tool. Answer with exactly one JSON object and nothing else."


def _schema():
    out = []
    for t in rules.TERMS:
        row = {"field": t["field"], "type": t["type"], "meaning": t["describe"]}
        if t["type"] == "choice":
            row["options"] = list(t["options"])
        if t["type"] == "duration":
            row["units"] = list(t["units"])
        out.append(row)
    return json.dumps(out, indent=1)


ROLE_INSTRUCTIONS = {
    "clause_by_clause": (
        "Work clause by clause: go through the contract section by section, in order, and for each term take the "
        "one clause that states it for the service the contract covers.",
        "Answer as {\"terms\": {\"<field>\": {\"value\": ..., \"quote\": ...}, ...}} with exactly these fields."),
    "numbers_first": (
        "Work numbers first: before choosing any term, list every number the contract states (percentages, days, "
        "hours, counts, amounts, written in digits or in words) and what each one governs. Then pick each term from "
        "that list; most numbers in a contract govern something other than these terms.",
        "Answer as {\"numbers\": [{\"number\": \"...\", \"governs\": \"...\"}, ...], \"terms\": {\"<field>\": "
        "{\"value\": ..., \"quote\": ...}, ...}} with exactly these fields under terms."),
    "sceptic": (
        "Be the sceptic. For each term, once you have found it, look for a second place in the contract that states "
        "the same term. If a second place states it with a different value, copy that sentence character for "
        "character into `conflict`; otherwise `conflict` is null. Beware numbers that look like a term but govern "
        "something else (termination thresholds, payment terms, emergency maintenance, review periods).",
        "Answer as {\"terms\": {\"<field>\": {\"value\": ..., \"quote\": ..., \"conflict\": ...}, ...}} with exactly "
        "these fields."),
}


def reader_prompt(text, role="clause_by_clause"):
    how, shape = ROLE_INSTRUCTIONS[role]
    return ("Read the contract below and return these terms:\n" + _schema() + "\n\n"
            "Your role: " + role + ". " + how + "\n\n"
            "For each term give `value` and `quote`.\n"
            "- percent: value is the number as a string without the % sign (\"99.5\"). choice: value is one of the "
            "option ids.\n"
            "- duration: value is the number as digits (\"30\") and add \"unit\": one of the term's units, the unit "
            "the contract itself writes (\"business_days\" for Business Days, \"days\" for days or calendar days). "
            "Never convert between units: 5 business days stays {\"value\": \"5\", \"unit\": \"business_days\"}. A "
            "unit that is not in the term's list (weeks, working days, billing cycles) means the term is not stated.\n"
            "- schedule (credit_schedule): value is a list of every credit tier, one object per tier: {\"below\": "
            "\"<the availability percentage below which the tier applies>\", \"credit\": \"<the credit, a percent of "
            "fees>\", \"quote\": \"<the one sentence, list item or table row that states this tier>\"}. A single flat "
            "credit is one tier. If a tier's sentence states its threshold only as the commitment itself (\"below the "
            "Availability Commitment\"), give \"below\": \"commitment\". For a tier stated as a range (\"99.0% to "
            "99.9%\"), below is the upper end. The term's own quote is null.\n"
            "- quote: the one sentence or list item the value comes from, copied character for character from the "
            "contract (keep its section number if it has one).\n"
            "- Answer only what the contract states. If the contract does not state a term in the form asked, the term "
            "is not stated: for example, a credit cap that is not a percentage of the period's fees is not a "
            "percentage cap, and credits in days of service or fixed amounts are not a percentage schedule. For a "
            "term that is not stated answer {\"value\": null, \"quote\": null, \"stated\": false, \"reason\": "
            "\"<what the contract does state, or that it says nothing about it>\"} (the sceptic also keeps "
            "\"conflict\": null).\n"
            + shape + "\n\nCONTRACT\n<<<\n" + text + "\n>>>")


RULE_SPEC = (
    "A rule is {\"pattern\": <regular expression>}. Choice terms add \"map\": {<captured phrase, lowercase>: <option id>}.\n"
    "- Python `re` syntax. Uptime runs re.finditer(pattern, contract, re.IGNORECASE) on the contract with every run of "
    "whitespace (newlines included) collapsed to one space and finds EVERY match. If the rule matches in more than one "
    "place with different values, Uptime refuses it as ambiguous and reads nothing, so anchor each rule on wording "
    "that occurs only in the clause that states the term.\n"
    "- percent and choice: exactly one capturing group, holding only the value: for percent the number without % "
    "(like (\\d+(?:\\.\\d+)?)), for choice the contract's own phrase. Use (?:...) for other groups.\n"
    "- duration: exactly two named groups, (?P<value>\\d+) for the number and (?P<unit>...) for the unit word as the "
    "contract writes it (for example (?P<unit>business days|days|hours)). Uptime records the unit; it never converts.\n"
    "- schedule (credit_schedule): {\"rows\": [{\"pattern\": ...}, ...]}, one to six row patterns. Each row pattern "
    "has the named groups (?P<below>...) for the threshold percentage and (?P<credit>...) for the credit percentage "
    "and no other capture group; one pattern may match several tiers (one per sentence, list item or table row). "
    "A row whose sentence states its threshold only as the commitment itself is {\"pattern\": ..., \"below\": "
    "\"commitment\"} with only (?P<credit>...). Every tier must be matched in its own sentence or line; two "
    "different tiers matched in one sentence or line make the schedule read nothing. The rows read must be exactly "
    "the readers' schedule.\n"
    "- No back-references. At most 400 characters per pattern.\n"
    "- The same rule must read other contracts of this form, where every number, percentage, party, date, address "
    "and order number is different. Never write the value's own digits into the pattern; Uptime refuses a rule "
    "that does. Beware other numbers in the contract (payment terms, termination notice, emergency maintenance, "
    "review periods).\n"
    "- Avoid nested quantifiers such as (a+)+; prefer explicit wording or [^.;]*? between anchors.\n")


def _term_for_prompt(field, value, quote):
    """One term as the builder and repair prompts show it: a schedule's tiers carry their own sentences."""
    term = rules.TERM[field]
    if term["type"] == "schedule" and isinstance(value, list):
        quotes = quote if isinstance(quote, list) else [None] * len(value)
        return {"field": field, "type": "schedule",
                "tiers": [{"below": r["below_percent"], "credit": r["credit_percent"], "sentence": q}
                          for r, q in zip(value, quotes)]}
    return {"field": field, "type": term["type"], "value": value, "sentence": quote}


def builder_prompt(text, agreed):
    terms = [_term_for_prompt(f, v["value"], v["quote"]) for f, v in agreed.items()]
    return ("Write one extraction rule per term for this contract form.\n" + RULE_SPEC +
            "\nThe terms the readers found in this contract:\n" + json.dumps(terms, indent=1) +
            "\n\nAnswer as {\"rules\": {\"<field>\": {\"pattern\": ...}, ...}} (the schedule as {\"rows\": [...]}) with "
            "exactly these fields: " + ", ".join(agreed) + ".\n\nCONTRACT\n<<<\n" + text + "\n>>>")


def repair_prompt(text, second_text, agreed, current, failures):
    rows = [dict(_term_for_prompt(f, agreed[f]["value"], agreed[f]["quote"]), current_rule=current.get(f),
                 what_went_wrong=failures[f]) for f in failures]
    second = ("\n\nSECOND CONTRACT OF THE SAME FORM (its terms are not given to you)\n<<<\n" + second_text + "\n>>>"
              if second_text is not None else "")
    return ("Some extraction rules for this contract form failed. Write corrected rules for these fields only.\n"
            + RULE_SPEC + "\nThe failed rules:\n" + json.dumps(rows, indent=1) +
            "\n\nAnswer as {\"rules\": {\"<field>\": {\"pattern\": ...}, ...}} (the schedule as {\"rows\": [...]}) with "
            "exactly these fields: " + ", ".join(failures) + ".\n\nCONTRACT (the one the readers read)\n<<<\n" + text
            + "\n>>>" + second)


def _scalar(raw):
    return raw is None or isinstance(raw, (str, int, Decimal)) and not isinstance(raw, bool)


def parse_reader(answer, role="clause_by_clause"):
    value = strict_object(answer)
    terms = value.get("terms")
    top = {"terms", "numbers"} if role == "numbers_first" else {"terms"}
    if set(value) != top or not isinstance(terms, dict) or set(terms) != set(rules.TERM):
        raise ModelFailed("The reader's answer did not have exactly the fixed terms.")
    if role == "numbers_first" and not isinstance(value["numbers"], list):
        raise ModelFailed("The reader's list of numbers was not a list.")
    # The availability commitment first: a tier may take its threshold from it.
    order = sorted(terms, key=lambda f: f != "availability_target_percent")
    out = {}
    for field in order:
        item, term = terms[field], rules.TERM[field]
        keys = {"value", "quote", "conflict"} if role == "sceptic" else {"value", "quote"}
        extra = {"stated", "reason"} | ({"unit"} if term["type"] == "duration" else set())
        need = keys - {"quote"} if term["type"] == "schedule" else keys
        if not isinstance(item, dict) or not need <= set(item) <= keys | extra:
            raise ModelFailed("The reader's answer for %s was not {%s}." % (field, ", ".join(sorted(keys))))
        raw, quote = item["value"], item.get("quote")
        stated, reason = item.get("stated"), item.get("reason")
        if stated is not None and not isinstance(stated, bool) or reason is not None and not isinstance(reason, str):
            raise ModelFailed("The reader's stated/reason for %s has the wrong type." % field)
        if stated is False and raw is not None:
            raise ModelFailed("The reader said %s is not stated but gave a value." % field)
        conflict = item.get("conflict")
        if conflict is not None and not isinstance(conflict, str):
            raise ModelFailed("The reader's conflict for %s is not text." % field)
        if term["type"] == "schedule":
            if raw is not None and (not isinstance(raw, list) or not all(
                    isinstance(r, dict) and set(r) <= {"below", "credit", "quote"} and _scalar(r.get("below"))
                    and _scalar(r.get("credit")) and (r.get("quote") is None or isinstance(r.get("quote"), str))
                    for r in raw)):
                raise ModelFailed("The reader's credit schedule is not a list of {below, credit, quote}.")
            value_, quote = None, None
            if raw is not None:
                commitment = (out.get("availability_target_percent") or {}).get("value")
                value_, _ = rules.canonical_schedule([{"below": r.get("below"), "credit": r.get("credit")} for r in raw],
                                                     commitment)
                if value_ is not None:
                    quotes = {}
                    for r in raw:
                        below = commitment if str(r.get("below", "")).strip().lower() == "commitment" else r.get("below")
                        key = (rules.canonical("percent", below), rules.canonical("percent", r.get("credit")))
                        quotes.setdefault(key, r.get("quote"))
                    quote = [quotes.get((row["below_percent"], row["credit_percent"])) for row in value_]
        else:
            if not _scalar(raw):
                raise ModelFailed("The reader's value for %s has the wrong type." % field)
            if quote is not None and not isinstance(quote, str):
                raise ModelFailed("The reader's quote for %s is not text." % field)
            if term["type"] == "duration":
                unit = item.get("unit")
                if unit is not None and not isinstance(unit, str):
                    raise ModelFailed("The reader's unit for %s is not text." % field)
                value_ = rules.canonical_duration(field, raw, unit) if raw is not None else None
            else:
                value_ = rules.canonical(term["type"], raw, term.get("options")) if raw is not None else None
        out[field] = {"value": value_, "quote": quote, "invalid": raw is not None and value_ is None,
                      "conflict": conflict or None, "stated": raw is not None,
                      "reason": ((reason or "").strip() or None) if raw is None else None}
    numbers = len(value["numbers"]) if role == "numbers_first" else None
    return {f: out[f] for f in rules.TERM}, numbers


def parse_rules(answer, fields):
    value = strict_object(answer)
    found = value.get("rules")
    if set(value) != {"rules"} or not isinstance(found, dict) or set(found) != set(fields):
        raise ModelFailed("The builder's answer did not have exactly one rule per requested term.")
    out = {}
    for field, item in found.items():
        kind = rules.TERM[field]["type"]
        rule = {"field": field, "type": kind}
        if kind == "schedule":
            rows = item.get("rows") if isinstance(item, dict) else None
            if set(item or {}) != {"rows"} or not isinstance(rows, list) or not 1 <= len(rows) <= rules.MAX_TIERS or not all(
                    isinstance(r, dict) and isinstance(r.get("pattern"), str) and set(r) <= {"pattern", "below"}
                    and r.get("below") in (None, "commitment") for r in rows):
                raise ModelFailed("The builder's schedule rule is not {rows: [{pattern, below?}]} with one to six rows.")
            rule["rows"] = [{k: r[k] for k in ("pattern", "below") if k in r} for r in rows]
            out[field] = rule
            continue
        allowed = {"pattern", "map"} if kind == "choice" else {"pattern"}
        if not isinstance(item, dict) or "pattern" not in item or not set(item) <= allowed:
            raise ModelFailed("The builder's rule for %s has the wrong shape." % field)
        if not isinstance(item["pattern"], str):
            raise ModelFailed("The builder's pattern for %s is not text." % field)
        rule["pattern"] = item["pattern"]
        if kind != "duration":
            rule["group"] = 1
        if kind == "choice":
            mapping = item.get("map")
            if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
                raise ModelFailed("The builder's map for %s is not phrase to option." % field)
            rule["map"] = dict(mapping)
        out[field] = rule
    return out


def _patterns(rule):
    """Every pattern of a rule (a schedule has one per row)."""
    if isinstance(rule.get("rows"), list):
        return [r.get("pattern", "") for r in rule["rows"] if isinstance(r, dict)]
    return [rule.get("pattern", "")]


def anchors(body, count=3):
    """A few fixed phrases from a template's rules (literal wording between the regular-expression parts)."""
    found = []
    for s in [p for rule in body.get("rules", []) for p in _patterns(rule)]:
        s = re.sub(r"\\[dDsSwWbB]", " ", s)
        s = re.sub(r"\[[^\]]*\]|\{\d*,?\d*\}|\(\?[:=!<]*", " ", s)
        s = re.sub(r"\\(.)", r"\1", s)
        for part in re.split(r"[()|*+?^$.]", s):
            part = " ".join(part.split())
            if len(part) >= 12 and re.search(r"[A-Za-z]{4}", part) and part not in found:
                found.append(part)
    return sorted(found, key=len, reverse=True)[:count]


def _sentence(exc):
    return getattr(exc, "sentence", None) or (str(exc) if isinstance(exc, ModelFailed) else None) \
        or "the call failed (%s)." % type(exc).__name__


def _probability(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _key(value):
    """A hashable key for a term value (a schedule is a list, a duration an object)."""
    return rules.canonical_json(value)


# --- The orchestration --------------------------------------------------------------------

class TemplateBuilds:
    def __init__(self, directory, claude, jev, samples=None, max_builds=MAX_BUILDS, background=True):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self.claude, self.jev = claude, jev
        self.samples = {s["id"]: s for s in (samples if samples is not None else demo_samples())}
        self.max_builds, self.background = max_builds, background
        self.on_reading = None  # the money link sets this: callable(approved_readings() entry) -> agreement dict
        self.started = 0
        self.lock = Lock()
        self.builds = {}
        for path in sorted(self.directory.glob("tb_*.json")):
            try:
                build = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
            build.setdefault("readings", [])
            build.setdefault("matched_template", None)
            if build.get("state") in RUNNING:
                build["state"] = "FAILED"
                build["error"] = {"sentence": "The server stopped while this build was running; start a new build."}
                build["finished_at"] = build["updated_at"] = now()
                for step in build["steps"]:
                    if step["state"] in ("RUNNING", "PENDING") and step["id"] != "review":
                        step["state"] = "FAILED" if step["state"] == "RUNNING" else "SKIPPED"
                self.builds[build["id"]] = build
                self._save(build)
            else:
                self.builds[build["id"]] = build

    # -- Persistence and snapshots
    def _write(self, path, text):
        handle, temporary = tempfile.mkstemp(dir=self.directory, prefix=".tb-")
        try:
            os.fchmod(handle, 0o600)
            with os.fdopen(handle, "w") as out:
                out.write(text)
            os.replace(temporary, path)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

    def _save(self, build):
        self._write(self.directory / (build["id"] + ".json"), json.dumps(build, indent=1))

    def _update(self, build, **fields):
        with self.lock:
            build.update(fields)
            build["updated_at"] = now()
            self._save(build)

    def _step(self, build, ident, **fields):
        with self.lock:
            step = next(s for s in build["steps"] if s["id"] == ident)
            if fields.get("state") == "RUNNING":
                step["started_at"], step["_t"] = now(), perf_counter()
            if fields.get("state") in ("DONE", "FAILED") and step.get("_t") is not None:
                step["finished_at"] = now()
                step["seconds"] = "%.1f" % (perf_counter() - step.pop("_t"))
            step.update(fields)
            build["updated_at"] = now()
            self._save(build)

    def get(self, build_id):
        with self.lock:
            return public(copy.deepcopy(self._build(build_id)))

    def _build(self, build_id):
        build = self.builds.get(build_id)
        if build is None:
            raise TemplateRefused("No template build with that id.", 404)
        return build

    def _approved(self):
        """Builds whose template is APPROVED, oldest first. Call with the lock held."""
        return sorted((b for b in self.builds.values() if (b.get("template") or {}).get("state") == "APPROVED"),
                      key=lambda b: b["started_at"])

    def _template_entry(self, build):
        t, source = build["template"], build.get("source") or {}
        sample = self.samples.get(build.get("sample_id"), {})
        return {**{k: t[k] for k in ("id", "sha256", "rules", "state", "approved_by", "approved_at")},
                "sample_id": build.get("sample_id"), "vendor": source.get("vendor", sample.get("vendor")),
                "title": source.get("title", sample.get("title"))}

    def overview(self):
        with self.lock:
            builds = sorted(self.builds.values(), key=lambda b: b["started_at"], reverse=True)
            return {"enabled": True, "reason": None, "samples": [public(s) for s in self.samples.values()],
                    "builds": public(copy.deepcopy(builds)),
                    "templates": [self._template_entry(b) for b in self.builds.values() if b.get("template")]}

    # -- Start
    def start(self, sample_id=None, contract=None, second_contract=None, consent=False):
        """Start a build for a shipped sample (`sample_id`) or a pasted contract (`contract` = {title, vendor, text},
        optional `second_contract` = {title, text}, `consent` must be true)."""
        if (sample_id is None) == (contract is None):
            raise TemplateRefused("Give either a sample or a pasted contract.", 400)
        if contract is not None:
            pasted = self._check_paste(contract, second_contract, consent)
        with self.lock:
            if sample_id is not None:
                sample = self.samples.get(sample_id)
                if sample is None:
                    raise TemplateRefused("That sample contract is not shipped with Uptime.", 404)
                for build in self.builds.values():
                    if build.get("sample_id") == sample_id and build["state"] in RUNNING + ("NEEDS_REVIEWER",):
                        return public(copy.deepcopy(build))
            if self.started >= self.max_builds:
                raise TemplateRefused("This server has run its %d template builds; restart it to run more." % self.max_builds, 429)
            self.started += 1
            stamp = now()
            ident = "tb_" + secrets.token_hex(3)
            while ident in self.builds:
                ident = "tb_" + secrets.token_hex(3)
            if sample_id is not None:
                doc, second = sample["document"], sample["second_document"]
                source = {"kind": "sample", "title": sample["title"], "vendor": sample["vendor"], "chars": doc["chars"]}
                private = {"_form": sample["id"], "_form_title": sample["form"], "_text_path": doc["_path"],
                           "_document": {k: doc[k] for k in ("id", "title", "vendor", "customer")},
                           "_second_path": second["_path"], "_second_document": {"id": second["id"], "title": second["title"]}}
                second_public = {"provided": True, "title": second["title"]}
            else:
                text_path = self.directory / (ident + "-contract.txt")
                self._write(text_path, pasted["text"])
                private = {"_form": slug(pasted["vendor"] + " " + pasted["title"]), "_form_title": pasted["title"],
                           "_text_path": str(text_path),
                           "_document": {"id": ident + "-contract", "title": pasted["title"], "vendor": pasted["vendor"],
                                         "customer": None},
                           "_second_path": None, "_second_document": None}
                if pasted["second"] is not None:
                    second_path = self.directory / (ident + "-second.txt")
                    self._write(second_path, pasted["second"]["text"])
                    private["_second_path"] = str(second_path)
                    private["_second_document"] = {"id": ident + "-second", "title": pasted["second"]["title"]}
                source = {"kind": "pasted", "title": pasted["title"], "vendor": pasted["vendor"],
                          "chars": len(pasted["text"])}
                second_public = ({"provided": True, "title": pasted["second"]["title"]} if pasted["second"]
                                 else {"provided": False, "title": None})
            build = {"id": ident, "sample_id": sample_id, "state": "QUEUED", "source": source, "second": second_public,
                     "started_at": stamp, "updated_at": stamp, "finished_at": None,
                     "steps": [{"id": i, "actor": a, "label": label, "state": "PENDING", "started_at": None,
                                "finished_at": None, "seconds": None,
                                "model": (READERS[int(i[-1])][1] if i.startswith("reader-") else MODEL) if a == "CLAUDE" else None,
                                "summary": None, "detail": {"role": READERS[int(i[-1])][0]} if i.startswith("reader-") else {}}
                               for i, a, label in STEPS],
                     "terms": [], "checks": [], "template": None, "matched_template": None, "readings": [],
                     "error": None, **private}
            build["steps"][-1]["summary"] = "Waiting for the template"
            self.builds[ident] = build
            self._save(build)
        self._launch(self._run, build)
        return self.get(ident)

    @staticmethod
    def _check_paste(contract, second_contract, consent):
        if consent is not True:
            raise TemplateRefused("A pasted contract is sent to Claude and to Jev; consent must be given first.", 400)

        def text_of(item, what, vendor):
            if not isinstance(item, dict):
                raise TemplateRefused("The %s must have a title and text." % what, 400)
            allowed = {"title", "vendor", "text"} if vendor else {"title", "text"}
            if not set(item) <= allowed or not {"title", "text"} <= set(item) or (vendor and "vendor" not in item):
                raise TemplateRefused("The %s must have exactly %s." % (what, ", ".join(sorted(allowed))), 400)
            out = {}
            for key in allowed:
                value = item[key]
                limit = PASTE_LIMIT if key == "text" else NAME_LIMIT
                if not isinstance(value, str) or not value.strip():
                    raise TemplateRefused("The %s's %s is empty." % (what, key), 400)
                if len(value) > limit:
                    raise TemplateRefused("The %s's %s is longer than %s characters." % (what, key, format(limit, ",")), 400)
                out[key] = value if key == "text" else " ".join(value.split())
            return out
        pasted = text_of(contract, "contract", True)
        pasted["second"] = None if second_contract is None else text_of(second_contract, "second contract", False)
        return pasted

    def _launch(self, target, build):
        if self.background:
            Thread(target=target, args=(build,), daemon=True, name="template-build-" + build["id"]).start()
        else:
            target(build)

    def _fail(self, build, sentence):
        with self.lock:
            for step in build["steps"]:
                if step["state"] == "PENDING" and step["id"] != "review":
                    step["state"] = "SKIPPED"
            build.update(state="FAILED", error={"sentence": sentence}, finished_at=now(), updated_at=now())
            self._save(build)

    def _run(self, build):
        try:
            self._pipeline(build)
        except Exception as exc:  # the build records the failure; the server keeps running
            self._fail(build, "The build stopped: %s" % (str(exc) or type(exc).__name__))

    def _run_without_jev(self, build):
        try:
            self._make_template(build, Path(build["_text_path"]).read_text(), jev_ok=False)
        except Exception as exc:
            self._fail(build, "The build stopped: %s" % (str(exc) or type(exc).__name__))

    # -- Step 1: Jev routes
    def _options(self):
        """[(option text, approved template build)] for Jev's choice, within the client's limits. Lock held."""
        out, used = [], set()
        for b in self._approved():
            entry = self._template_entry(b)
            text = ("%s: %s, %s" % (entry["id"], entry["vendor"], entry["title"]))[:JEV_OPTION]
            if text in used:
                continue
            used.add(text)
            out.append((text, b))
        return out

    def _question(self, options):
        head = ("Which approved contract template does this document follow? Choose a template only if the document "
                "is the same contract form from the same vendor; otherwise choose unrecognised.")
        lines = []
        for text, b in options:
            phrases = anchors(b["_template_body"])
            lines.append(" " + text + (" (wording such as: " + "; ".join('"%s"' % p for p in phrases) + ")" if phrases else "") + ".")
        question = head
        for line in lines:
            if len(question) + len(line) > JEV_QUESTION:
                break
            question += line
        return question

    def _ask_template(self, text):
        """Jev's choice among the approved templates and unrecognised -> (answer or None, sentence, option map, ids)."""
        with self.lock:
            options = self._options()
            question = self._question(options)
        by_text = {t: b for t, b in options}
        ids = [b["template"]["id"] for _, b in options] + [UNRECOGNISED]
        if self.jev is None:
            return None, "no Jev client is configured on this server.", by_text, ids
        try:
            answer = self.jev.choice(question, [t for t, _ in options] + [UNRECOGNISED], text[:JEV_CONTEXT])
        except Exception as exc:
            return None, _sentence(exc), by_text, ids
        return answer, None, by_text, ids

    def _pipeline(self, build):
        text = Path(build["_text_path"]).read_text()
        self._update(build, state="CLASSIFYING")
        self._step(build, "classify", state="RUNNING")
        with self.lock:
            nothing_on_file = not self._approved()
        if nothing_on_file:
            # One option would force Jev to answer it with certainty; there is nothing to match, so Jev is not asked.
            self._step(build, "classify", state="DONE", model=None,
                       summary="No approved template is on file, so there was nothing for Jev to match; reading the contract",
                       detail={"choice": UNRECOGNISED, "probability": None, "options": [UNRECOGNISED], "asked": False})
            self._make_template(build, text, jev_ok=True)
            return
        answer, sentence, by_text, ids = self._ask_template(text)
        if answer is None:
            self._step(build, "classify", state="FAILED", detail={"options": ids},
                       summary="Jev could not be reached: " + sentence + " Nothing was started; a reviewer may build without Jev.")
            self._update(build, state="NEEDS_REVIEWER")
            self._step(build, "review", summary="Jev could not be reached; a reviewer may choose to build without Jev")
            return
        matched = by_text.get(answer["choice"])
        probability = _probability(answer["probability"])
        choice = matched["template"]["id"] if matched else UNRECOGNISED
        detail = {"choice": choice, "probability": str(answer["probability"]), "options": ids, "asked": True}
        if matched is not None and probability is not None and probability >= MATCH_THRESHOLD:
            self._step(build, "classify", state="DONE", model=answer.get("model"), detail=detail,
                       summary="Jev matched the approved template %s (%d%%)" % (choice, int(probability * 100)))
            self._matched(build, text, matched, answer)
            return
        if matched is not None:
            summary = "Jev's best match, %s, was under %s (%s); reading the contract from scratch" % (
                choice, MATCH_THRESHOLD, answer["probability"])
        else:
            summary = "No approved template matches; reading the contract from scratch"
        self._step(build, "classify", state="DONE", model=answer.get("model"), summary=summary, detail=detail)
        self._make_template(build, text, jev_ok=True)

    def continue_without_jev(self, build_id, reviewer):
        """A reviewer's decision to build without Jev after Jev could not be reached; recorded on `classify`."""
        with self.lock:
            build = self._build(build_id)
            if build["state"] != "NEEDS_REVIEWER":
                raise TemplateRefused("Only a build waiting for a reviewer can continue without Jev; this build is %s."
                                      % build["state"])
            stamp = now()
            step = build["steps"][0]
            step["detail"] = dict(step.get("detail") or {}, reviewer_decision={"by": reviewer, "at": stamp})
            step["summary"] = (step.get("summary") or "Jev could not be reached.").split(" Nothing was started")[0] \
                + " %s chose to build without Jev; every term will need the reviewer's acknowledgement." % reviewer
            build["steps"][-1]["summary"] = "Waiting for the template"
            build.update(state="QUEUED", updated_at=stamp, _without_jev=True)
            self._save(build)
        self._launch(self._run_without_jev, build)
        return self.get(build_id)

    # -- The MATCHED route: the approved template reads the contract, guarded
    def _matched(self, build, text, template_build, answer):
        with self.lock:
            for step in build["steps"]:
                if step["id"].startswith("reader-") or step["id"] in ("build", "review"):
                    step.update(state="SKIPPED", summary=NOT_STARTED, model=None)
            self._save(build)
        self._step(build, "checks", state="RUNNING")
        reading = self._guarded_read(template_build, text, build["_document"], answer)
        checks = [{"id": g["id"], "label": g["label"], "ok": g["ok"], "detail": g["detail"],
                   "advisory": g.get("advisory", False), "blocking": not g.get("advisory", False),
                   "by": "JEV" if g["id"] == "template_match" else "UPTIME",
                   "passed": g.pop("_passed"), "total": g.pop("_total")} for g in reading["guards"]]
        with self.lock:
            build["checks"] = checks
            build["readings"].append(reading)
            build["matched_template"] = {"id": template_build["template"]["id"],
                                         "sha256": template_build["template"]["sha256"],
                                         "probability": str(answer["probability"])}
        self._step(build, "checks", state="DONE", detail={"reading_id": reading["id"], "status": reading["status"]},
                   summary="Read by the approved template: %s, %d of %d terms" % (
                       reading["status"], reading["found"], reading["total"]))
        self._update(build, state="MATCHED", finished_at=now())
        self._attach(build, reading)

    # -- The readers, the builder and the checks
    def _read(self, text, index, on_step=None):
        """One reader -> (found or None, record). `on_step(**fields)` reports progress to a step, if given."""
        role, model = READERS[index]
        started = perf_counter()
        if on_step:
            on_step(state="RUNNING")
        record = {"reader": index, "role": role, "model": model, "seconds": None, "ok": False, "summary": None}
        try:
            answer = self.claude(SYSTEM, reader_prompt(text, role), model=model)
            found, numbers = parse_reader(answer, role)
        except Exception as exc:
            record.update(seconds="%.1f" % (perf_counter() - started), summary=_sentence(exc))
            if on_step:
                on_step(state="FAILED", model=None, summary=record["summary"], detail={"role": role})
            return None, record
        answered = getattr(answer, "model", None) or model
        normalized = rules.normalize(text)
        for item in found.values():
            quotes = item["quote"] if isinstance(item["quote"], list) else [item["quote"]]
            item["quotes_found"] = [bool(q) and rules.normalize(q) in normalized for q in quotes]
            item["quote_found"] = bool(quotes) and all(item["quotes_found"])
        stated = sum(i["value"] is not None for i in found.values())
        quotes = sum(sum(i["quotes_found"]) for i in found.values() if i["value"] is not None)
        detail = {"role": role, "terms": stated, "quotes_found": quotes}
        summary = "%d terms, %d quotes found in the contract" % (stated, quotes)
        if numbers is not None:
            detail["numbers_listed"] = numbers
            summary += "; %d numbers listed first" % numbers
        if role == "sceptic":
            conflicts = [{"field": f, "sentence": i["conflict"]} for f, i in found.items() if i["conflict"]]
            detail["conflicts"] = conflicts
            summary += "; %d conflict%s reported" % (len(conflicts), "" if len(conflicts) == 1 else "s")
        record.update(model=answered, seconds="%.1f" % (perf_counter() - started), ok=True, summary=summary)
        if on_step:
            on_step(state="DONE", model=answered, summary=summary, detail=detail)
        return found, record

    @staticmethod
    def _agree(succeeded):
        agreed = {}
        for term in rules.TERMS:
            f = term["field"]
            order = [_key(r[f]["value"]) for _, r in succeeded]
            votes = Counter(order)
            key, count = max(votes.items(), key=lambda kv: (kv[1], -order.index(kv[0])))
            holders = [r[f] for _, r in succeeded if _key(r[f]["value"]) == key]
            value = holders[0]["value"]
            best = next((h for h in holders if h["quote_found"]), holders[0])
            # Not stated only when every answering reader says so; any value or unreadable answer keeps it stated.
            silent = all(not r[f]["stated"] for _, r in succeeded)
            reason = next((r[f]["reason"] for _, r in succeeded if r[f]["reason"]), None) if silent else None
            agreed[f] = {"value": value, "quote": None if silent else best["quote"], "agree": count,
                         "stated": not silent, "reason": reason or ("No reader found it in the contract." if silent else None)}
        return agreed

    @staticmethod
    def _second_agreement(second_found):
        """Per term, what the second readers agreed on: the majority value among readers whose quote is in the
        second contract. A value needs at least two readers behind it."""
        answered = [r for r in second_found if r is not None]
        out = {}
        for term in rules.TERMS:
            f = term["field"]
            held = {_key(r[f]["value"]): r[f]["value"] for r in answered if r[f]["value"] is not None and r[f]["quote_found"]}
            votes = Counter(_key(r[f]["value"]) for r in answered if r[f]["value"] is not None and r[f]["quote_found"])
            if votes:
                key, count = max(votes.items(), key=lambda kv: kv[1])
                value = held[key]
                if list(votes.values()).count(count) > 1:
                    value = None  # a tie is not agreement
            else:
                value, count = None, 0
            silent = len(answered) >= 2 and all(not r[f]["stated"] for r in answered)
            out[f] = {"agree": len(answered) if silent else count, "of": len(answered),
                      "value": value if count >= 2 else None, "stated": not silent}
        return out

    def _make_template(self, build, text, jev_ok):
        second_path = build.get("_second_path")
        second_text = Path(second_path).read_text() if second_path else None

        # Readers, in parallel: three on this contract and, at the same time, three fresh ones on the second.
        self._update(build, state="READING")
        pool = ThreadPoolExecutor(6)
        try:
            firsts = [pool.submit(self._read, text, i, lambda i=i, **f: self._step(build, "reader-%d" % i, **f))
                      for i in (1, 2, 3)]
            seconds = [pool.submit(self._read, second_text, i) for i in (1, 2, 3)] if second_text is not None else []
            readings = [f.result() for f in firsts]
            succeeded = [(i + 1, r) for i, (r, _) in enumerate(readings) if r is not None]
            if len(succeeded) < 2:
                self._fail(build, "Only %d of 3 Claude readers answered in the expected shape; at least 2 are needed."
                           % len(succeeded))
                return
            agreed = self._agree(succeeded)
            stated = {f: a for f, a in agreed.items() if a["stated"]}
            if not stated:
                self._fail(build, "Every reader says the contract states none of the terms, so there is nothing to build.")
                return

            # Builder (while the second readers may still be reading), then up to two repair rounds
            self._update(build, state="BUILDING")
            self._step(build, "build", state="RUNNING")
            try:
                answer = self.claude(SYSTEM, builder_prompt(text, stated), model=MODEL)
                current = parse_rules(answer, list(stated))
            except Exception as exc:
                self._step(build, "build", state="FAILED", model=None, summary=_sentence(exc))
                self._fail(build, "The template builder did not return usable rules: " + _sentence(exc))
                return
            builder_model = getattr(answer, "model", None) or MODEL
            second_results = [f.result() for f in seconds]
        finally:
            pool.shutdown(wait=True)
        second_found = [r for r, _ in second_results]
        second_records = [rec for _, rec in second_results]
        second_agreed = self._second_agreement(second_found) if second_text is not None else None
        repairs, repair_note = 0, None

        def evaluate():
            body = {"rules": list(current.values())}
            a = {t["field"]: t for t in rules.apply(body, text)["terms"]}
            b = {t["field"]: t for t in rules.apply(body, second_text)["terms"]} if second_text is not None else None
            failures = {}
            for f in stated:
                problems = []
                if a[f]["value"] is None or not rules.same(a[f]["value"], agreed[f]["value"]):
                    problems.append("On this contract the rule " + (
                        "returned %r but the readers found %r." % (a[f]["value"], agreed[f]["value"])
                        if a[f]["value"] is not None else "failed: " + (a[f]["error"] or "found nothing.")))
                if b is not None and second_agreed[f]["value"] is not None and not rules.same(b[f]["value"], second_agreed[f]["value"]):
                    problems.append("On the second contract the rule " + (
                        "captured a value that is not what that contract's readers agreed on." if b[f]["value"] is not None
                        else "failed: " + (b[f]["error"] or "found nothing.")))
                if problems:
                    failures[f] = " ".join(problems)
            return a, b, failures

        on_a, on_b, failures = evaluate()
        while failures and repairs < REPAIR_ROUNDS:
            self._step(build, "build", summary="%d of %d rules failed a check; repair round %d"
                       % (len(failures), len(stated), repairs + 1), detail={"rules": len(current), "repair_rounds": repairs})
            try:
                fixed = parse_rules(self.claude(SYSTEM, repair_prompt(
                    text, second_text, agreed, {f: {k: v for k, v in current[f].items() if k in ("pattern", "map", "rows")}
                                                for f in failures}, failures), model=MODEL), list(failures))
            except Exception as exc:  # a used round; the next one is tried, up to the limit
                repair_note = ((repair_note + " ") if repair_note else "") + "Repair round %d failed: %s" % (
                    repairs + 1, _sentence(exc))
                repairs += 1
                continue
            current.update(fixed)
            repairs += 1
            on_a, on_b, failures = evaluate()
        summary = "%d extraction rules written" % len(current)
        if len(stated) < len(agreed):
            summary += " (%d term%s not stated in the contract)" % (len(agreed) - len(stated), "" if len(agreed) - len(stated) == 1 else "s")
        if repairs:
            summary += ", %d repair round%s" % (repairs, "" if repairs == 1 else "s")
        if failures:
            summary += "; %d still fail" % len(failures)
        detail = {"rules": len(current), "repair_rounds": repairs}
        if repair_note:
            detail["repair_note"] = repair_note
        with self.lock:
            form = build["_form"]
            version = 1 + sum(1 for b in self.builds.values() if b.get("_form") == form and b.get("template"))
            vendor = build["source"]["vendor"]
            body = {"id": "%s/%d" % (form, version), "sample_id": build.get("sample_id"), "vendor": vendor,
                    "form": build["_form_title"], "interpreter": rules.INTERPRETER,
                    "rules": [current[t["field"]] for t in rules.TERMS if t["field"] in current],
                    "not_stated": [t["field"] for t in rules.TERMS if not agreed[t["field"]]["stated"]]}
            digest = rules.sha256(body)
            build["_template_body"] = body
            build["template"] = {"id": body["id"], "sha256": digest, "rules": len(body["rules"]), "state": "PROPOSED",
                                 "approved_by": None, "approved_at": None, "not_stated": body["not_stated"]}
        self._step(build, "build", state="DONE", model=builder_model, summary=summary, detail=detail)
        self._checks(build, text, agreed, succeeded, current, on_a, on_b, second_agreed, second_records, jev_ok)

    def _checks(self, build, text, agreed, succeeded, current, on_a, on_b, second_agreed, second_records, jev_ok):
        self._update(build, state="CHECKING")
        self._step(build, "checks", state="RUNNING")
        sceptic = dict(succeeded).get(3)
        commitment = agreed["availability_target_percent"]["value"]
        terms = []
        for term in rules.TERMS:
            f = term["field"]
            a = agreed[f]
            second = second_agreed[f] if second_agreed is not None else None
            row = {"field": f, "label": term["label"], "type": term["type"], "stated": a["stated"],
                   "readers": [{"reader": i, "value": r[f]["value"], "quote_found": r[f]["quote_found"],
                                "stated": r[f]["stated"]} for i, r in succeeded],
                   "agreement": {"agree": a["agree"], "of": len(succeeded)},
                   "second_readers": second, "jev": None, "needs_acknowledgement": True}
            if not a["stated"]:
                # Every reader says the contract does not state it: no value, no rule; the reviewer confirms it.
                row.update(value=None, display=None, quote=None, reason=a["reason"], conflict=None,
                           value_in_sentence=None, rule=None, rule_value=None, rule_quote=None, rule_error=None,
                           rule_places=0, second_document_value=None,
                           second_document_ok=second is not None and not second["stated"], status="NOT_STATED")
            else:
                row.update(value=a["value"], display=rules.display(f, a["value"]) if a["value"] is not None else None,
                           quote=a["quote"], reason=None,
                           conflict=sceptic[f]["conflict"] if sceptic else None,
                           value_in_sentence=rules.value_in_sentence(f, a["value"], a["quote"], commitment),
                           rule={k: v for k, v in current[f].items() if k in ("pattern", "group", "map", "rows")} if f in current else None,
                           rule_value=on_a[f]["value"], rule_quote=on_a[f]["quote"], rule_error=on_a[f]["error"],
                           rule_places=on_a[f]["places"],
                           second_document_value=on_b[f]["value"] if on_b is not None else None,
                           second_document_ok=(second is not None and second["value"] is not None
                                               and rules.same(on_b[f]["value"], second["value"])), status=None)
            terms.append(row)
        stated_terms = [t for t in terms if t["stated"]]
        not_stated = len(terms) - len(stated_terms)
        jev_ran = False
        if jev_ok and self.jev is not None:
            def ask(term):
                if not term["stated"] or term["value"] is None or not term["quote"]:
                    return None
                return self._ask_term(term["field"], term["value"], term["quote"], commitment)
            with ThreadPoolExecutor(4) as pool:
                for term, verdict in zip(terms, pool.map(ask, terms)):
                    term["jev"] = verdict
            jev_ran = any(t["jev"] is not None for t in terms)

        def jev_pass(t):
            p = _probability(t["jev"]["probability"]) if t["jev"] is not None else None
            return t["jev"] is not None and t["jev"]["yes"] and p is not None and p >= JEV_THRESHOLD
        for t in stated_terms:
            t["needs_acknowledgement"] = not jev_pass(t)
            fine = (t["agreement"]["agree"] == t["agreement"]["of"] and t["value"] is not None
                    and all(r["quote_found"] for r in t["readers"] if r["value"] is not None)
                    and t["value_in_sentence"] and rules.same(t["rule_value"], t["value"]) and not t["conflict"]
                    and (on_b is None or t["second_document_ok"]) and not t["needs_acknowledgement"])
            t["status"] = "PASS" if fine else "REVIEW"
        reader_quotes = [found for _, r in succeeded for f in r if r[f]["value"] is not None or r[f]["invalid"]
                         for found in (r[f]["quotes_found"] if r[f]["value"] is not None else [r[f]["quote_found"]])]
        answered = [t for t in terms if t["jev"] is not None]
        flagged = [t["field"] for t in terms if t["needs_acknowledgement"]]
        second_doc = build.get("_second_document")
        if on_b is not None:
            second_check = {"id": "second_document", "label": "The template reads a second contract of the same form",
                            "passed": sum(t["second_document_ok"] for t in terms), "total": len(terms),
                            "blocking": True, "by": "UPTIME", "ran": True, "document": second_doc,
                            "readers": second_records,
                            "basis": "Three fresh readers of the second contract; no answer key. A term not stated in "
                                     "this contract passes only if they all say it is not stated there either."}
        else:
            second_check = {"id": "second_document", "label": "The template reads a second contract of the same form",
                            "passed": 0, "total": 0, "blocking": False, "by": "UPTIME", "ran": False, "document": None,
                            "readers": [], "basis": "No second contract was given, so this was not checked."}
        required = [t for t in terms if t["field"] in REQUIRED_TERMS]
        checks = [
            {"id": "stated", "label": "The contract states the terms a credit needs",
             "passed": sum(t["stated"] and t["value"] is not None for t in required), "total": len(required),
             "blocking": True, "by": "UPTIME", "required": list(REQUIRED_TERMS)},
            {"id": "quotes", "label": "Every quote is in the contract, word for word",
             "passed": sum(1 for q in reader_quotes if q), "total": len(reader_quotes),
             "blocking": True, "by": "UPTIME"},
            {"id": "value_in_sentence", "label": "Each value is in its sentence, as digits or words",
             "passed": sum(bool(t["value_in_sentence"]) for t in stated_terms), "total": len(stated_terms),
             "blocking": True, "by": "UPTIME"},
            {"id": "agreement", "label": "The %s readers agree" % ("three" if len(succeeded) == 3 else "two"),
             "passed": sum(t["agreement"]["agree"] == t["agreement"]["of"] for t in terms), "total": len(terms),
             "blocking": False, "by": "UPTIME"},
            {"id": "reproduce", "label": "The template returns every stated term from this contract, one value per rule",
             "passed": sum(t["value"] is not None and rules.same(t["rule_value"], t["value"]) for t in stated_terms),
             "total": len(stated_terms), "blocking": True, "by": "UPTIME"},
            second_check,
            {"id": "jev", "label": "Jev: each term is supported by its sentence", "passed": sum(jev_pass(t) for t in stated_terms),
             "total": len(stated_terms), "blocking": False, "by": "JEV", "threshold": str(JEV_THRESHOLD),
             "lowest": min((t["jev"]["probability"] for t in answered), key=Decimal) if answered else None,
             "ran": jev_ran, "needs_acknowledgement": flagged},
        ]
        for c in checks:
            c["not_stated"] = not_stated
        for c in checks:
            c["ok"] = c["passed"] == c["total"] and c["total"] > 0 and c.get("ran", True)
        passed = sum(c["ok"] for c in checks)
        blocking_failed = [c["label"] for c in checks if c["blocking"] and not c["ok"]]
        summary = "%d of %d checks passed" % (passed, len(checks))
        if blocking_failed:
            summary += "; blocking: " + "; ".join(blocking_failed)
        if flagged:
            summary += "; %d term%s need%s the reviewer's acknowledgement" % (
                len(flagged), "" if len(flagged) == 1 else "s", "s" if len(flagged) == 1 else "")
        with self.lock:
            build["terms"], build["checks"] = terms, checks
        self._step(build, "checks", state="DONE", summary=summary, detail={"passed": passed, "total": len(checks)})
        if blocking_failed:
            review = "Approval is blocked until the failed checks pass"
        elif flagged:
            review = "Waiting for a reviewer, who must acknowledge %d flagged term%s" % (len(flagged), "" if len(flagged) == 1 else "s")
        else:
            review = "Waiting for a reviewer"
        self._step(build, "review", summary=review, detail={"needs_acknowledgement": flagged})
        self._update(build, state="READY_FOR_REVIEW", finished_at=now())

    def _ask_term(self, field, value, quote, commitment):
        """Jev on one stated term: once per term, and once per row for the schedule (each row in its own sentence).
        -> {"yes", "probability", "model"} (a schedule's also has "rows"), or None when Jev did not answer."""
        term = rules.TERM[field]

        def one(question, context):
            try:
                answer = self.jev.yes_no(question, context[:JEV_CONTEXT])
            except Exception:
                return None
            return {"yes": bool(answer["yes"]), "probability": str(answer["probability"]), "model": answer.get("model")}
        if term["type"] == "schedule":
            rows = []
            for row, sentence in zip(value, quote if isinstance(quote, list) else []):
                below = row["below_percent"] + "%"
                if commitment is not None and rules.same(row["below_percent"], commitment) and sentence and \
                        not rules.value_in_sentence("availability_target_percent", row["below_percent"], sentence):
                    below = "the availability commitment (%s%%)" % row["below_percent"]
                rows.append(one(term["question"].format(credit=row["credit_percent"], below=below), sentence or "")
                            if sentence else None)
            if not rows or any(r is None for r in rows):
                return None
            lowest = min(rows, key=lambda r: Decimal(r["probability"]))
            return {"yes": all(r["yes"] for r in rows), "probability": lowest["probability"], "model": lowest["model"],
                    "rows": rows}
        shown = rules.display(field, value)
        return one(term["question"].format(display=shown, display_lower=shown.lower()), quote)

    # -- Reviewer approval
    def approve(self, build_id, sha, reviewer, acknowledged=None):
        with self.lock:
            build = self._build(build_id)
            if build["state"] != "READY_FOR_REVIEW" or not build.get("template"):
                raise TemplateRefused("Only a template that is ready for review can be approved; this build is %s." % build["state"])
            if not isinstance(sha, str) or sha != build["template"]["sha256"] or rules.sha256(build["_template_body"]) != sha:
                raise TemplateRefused("That SHA-256 is not this build's template; nothing was approved.")
            failed = [c["label"] for c in build["checks"] if c["blocking"] and not c["ok"]]
            if failed:
                raise TemplateRefused("A blocking check failed, so this template cannot be approved: " + "; ".join(failed) + ".")
            flagged = [t["field"] for t in build["terms"] if t.get("needs_acknowledgement")]
            given = list(acknowledged or [])
            if not all(isinstance(f, str) for f in given) or len(set(given)) != len(given) or set(given) != set(flagged):
                raise TemplateRefused(
                    "Approval must acknowledge exactly the flagged terms (not supported by Jev, or not stated in the "
                    "contract): %s; nothing was approved."
                    % (", ".join(flagged) if flagged else "none"))
            stamp = now()
            build["template"].update(state="APPROVED", approved_by=reviewer, approved_at=stamp)
            step = build["steps"][-1]
            step.update(state="DONE", started_at=stamp, finished_at=stamp,
                        summary="Approved by " + reviewer + (", acknowledging %d flagged term%s" % (
                            len(flagged), "" if len(flagged) == 1 else "s") if flagged else ""),
                        detail={"template_sha256": sha, "acknowledged": flagged,
                                "without_jev": bool(build.get("_without_jev"))})
            build.update(state="APPROVED", updated_at=stamp)
            self._save(build)
            return public(copy.deepcopy(build))

    # -- Guarded reads
    def _guarded_read(self, template_build, text, document, jev_answer=None):
        """Read `text` with an approved template and run the five guards -> a reading (not yet stored)."""
        with self.lock:
            body = template_build["_template_body"]
            sha = template_build["template"]["sha256"]
            if rules.sha256(body) != sha:
                raise TemplateRefused("The stored template no longer matches its approved SHA-256.")
            template_id = template_build["template"]["id"]
        result = rules.apply(body, text)
        terms = result["terms"]
        values = {t["field"]: t["value"] for t in terms}
        ambiguous = [t["field"] for t in terms if t["ambiguous"]]
        with_value = [t for t in terms if t["value"] is not None]
        in_sentence = [t for t in with_value if rules.value_in_sentence(t["field"], t["value"], t["quote"],
                                                                         values.get("availability_target_percent"))]
        problems = rules.plausibility(values)
        guards = [
            {"id": "complete", "ok": result["found"] == result["total"], "detail": "%d of %d" % (result["found"], result["total"]),
             "_passed": result["found"], "_total": result["total"]},
            {"id": "unambiguous", "ok": not ambiguous,
             "detail": None if not ambiguous else "; ".join("%s: %s" % (t["field"], t["error"]) for t in terms if t["ambiguous"]),
             "_passed": result["total"] - len(ambiguous), "_total": result["total"]},
            {"id": "value_in_sentence", "ok": len(in_sentence) == len(with_value) and bool(with_value),
             "detail": "%d of %d" % (len(in_sentence), len(with_value)), "_passed": len(in_sentence), "_total": len(with_value)},
            {"id": "plausible", "ok": not problems, "detail": " ".join(problems) or None,
             "_passed": 0 if problems else 1, "_total": 1},
        ]
        # template_match: Jev's choice for this document, at MATCH_THRESHOLD or more
        sentence, by_text = None, None
        if jev_answer is None:
            jev_answer, sentence, by_text, _ = self._ask_template(text)
        if jev_answer is None:
            jev_template = None
            guards.append({"id": "template_match", "ok": False, "advisory": True,
                           "detail": "Jev could not be reached: " + sentence + " This guard is advisory until it can.",
                           "_passed": 0, "_total": 1})
        else:
            if by_text is None:
                with self.lock:
                    by_text = {t: b for t, b in self._options()}
            chosen = by_text.get(jev_answer["choice"])
            choice = chosen["template"]["id"] if chosen is not None else UNRECOGNISED
            p = _probability(jev_answer["probability"])
            ok = chosen is template_build and p is not None and p >= MATCH_THRESHOLD
            jev_template = {"choice": choice, "probability": str(jev_answer["probability"]), "model": jev_answer.get("model")}
            guards.append({"id": "template_match", "ok": ok, "advisory": False,
                           "detail": str(jev_answer["probability"]) if ok else "Jev chose %s (%s)" % (choice, jev_answer["probability"]),
                           "_passed": int(ok), "_total": 1})
        for g in guards:
            g["label"] = GUARD_LABELS[g["id"]]
        for t in terms:  # why each term is blank or doubtful: the guards it failed, with its own error
            failed = []
            if not t["stated"]:
                t["failed_guards"] = []
                continue
            if t["value"] is None:
                failed.append("complete")
            if t["ambiguous"]:
                failed.append("unambiguous")
            if t["value"] is not None and t not in in_sentence:
                failed.append("value_in_sentence")
                t["error"] = t["error"] or "The value %s is not in the sentence the rule matched." % t["display"]
            t["failed_guards"] = failed
        status = "ACCEPTED" if all(g["ok"] or g.get("advisory") for g in guards) else "REFUSED"
        refused_because = [g["label"] + (": " + g["detail"] if g["detail"] and not g["ok"] else "")
                           for g in guards if not g["ok"] and not g.get("advisory")]
        return {"id": "rd_" + secrets.token_hex(3), "status": status, "reasons": refused_because,
                "document": document, "read_by": "TEMPLATE",
                "template": {"id": template_id, "sha256": sha}, "model_calls": 0, "milliseconds": result["milliseconds"],
                "terms": [{k: t[k] for k in ("field", "label", "type", "value", "display", "quote", "stated", "error",
                                             "failed_guards")} for t in terms],
                "found": result["found"], "total": result["total"], "not_stated": result["not_stated"], "guards": guards,
                "jev_template": jev_template, "agreement": None, "read_at": now()}

    def read(self, build_id, document_id=None, document=None):
        """Read a next contract with this build's approved template: a shipped next document (`document_id`) or a
        pasted one (`document` = {title, text}). Every read is guarded and stored on the build."""
        if (document_id is None) == (document is None):
            raise TemplateRefused("Give either a document id or a pasted document.", 400)
        with self.lock:
            build = self._build(build_id)
            if build["state"] != "APPROVED" or (build.get("template") or {}).get("state") != "APPROVED":
                raise TemplateRefused("This template is not approved yet, so it cannot read contracts.")
            sample = self.samples.get(build.get("sample_id")) or {"next_documents": []}
        if document_id is not None:
            own = [sample["document"]] if sample.get("document") else []
            found = next((d for d in [*own, *sample["next_documents"]] if d["id"] == document_id), None)
            if found is None:
                raise TemplateRefused("That document is neither the contract this template was built from nor one of its next contracts.", 404)
            text = Path(found["_path"]).read_text()
            meta = {k: found[k] for k in ("id", "title", "vendor", "customer")}
        else:
            if not isinstance(document, dict) or not {"title", "text"} <= set(document) <= {"title", "vendor", "text"} \
                    or not all(isinstance(document[k], str) and document[k].strip() for k in document):
                raise TemplateRefused("A pasted document needs a title and text (and may name its vendor).", 400)
            if len(document["text"]) > PASTE_LIMIT or any(len(document[k]) > NAME_LIMIT for k in ("title", "vendor") if k in document):
                raise TemplateRefused("The pasted document is longer than the limits (60,000 characters of text).", 400)
            text = document["text"]
            vendor = " ".join(document["vendor"].split()) if "vendor" in document else (
                build["source"]["vendor"] if build.get("source") else sample.get("vendor"))
            meta = {"id": None, "title": " ".join(document["title"].split()), "vendor": vendor, "customer": None}
        reading = self._guarded_read(build, text, meta)
        for g in reading["guards"]:
            g.pop("_passed", None)
            g.pop("_total", None)
        if reading["document"]["id"] is None:
            reading["document"]["id"] = "pasted-" + reading["id"]
        with self.lock:
            build["readings"].append(reading)
            build["updated_at"] = now()
            self._save(build)
        self._attach(build, reading)
        with self.lock:
            return public(copy.deepcopy(reading))

    # -- For the money link
    def _entry(self, build, reading, approved):
        """One approved_readings() entry. Lock held."""
        template_build = approved.get(reading["template"]["sha256"])
        doc = reading["document"]
        return {"build_id": build["id"], "reading_id": reading["id"],
                "template": {"id": reading["template"]["id"], "sha256": reading["template"]["sha256"]},
                "vendor": (template_build.get("source") or {}).get("vendor") or doc.get("vendor"),
                "document": {"id": doc.get("id"), "title": doc.get("title"), "customer": doc.get("customer")},
                "values": {t["field"]: t["value"] for t in reading["terms"]}, "read_at": reading["read_at"]}

    def approved_readings(self):
        """Every ACCEPTED reading under an APPROVED template in this workspace, oldest first."""
        with self.lock:
            approved = {b["template"]["sha256"]: b for b in self._approved()}
            out = [self._entry(b, r, approved) for b in self.builds.values() for r in b.get("readings", [])
                   if r["status"] == "ACCEPTED" and r["template"]["sha256"] in approved]
        return sorted(out, key=lambda e: e["read_at"])

    def set_agreement(self, build_id, reading_id, agreement):
        """Attach the money link's agreement (a JSON object) to one reading."""
        if agreement is not None and not isinstance(agreement, dict):
            raise TemplateRefused("An agreement must be a JSON object.", 400)
        json.dumps(agreement)  # refuses anything that cannot be stored
        with self.lock:
            build = self._build(build_id)
            reading = next((r for r in build.get("readings", []) if r["id"] == reading_id), None)
            if reading is None:
                raise TemplateRefused("No reading with that id on this build.", 404)
            reading["agreement"] = copy.deepcopy(agreement)
            build["updated_at"] = now()
            self._save(build)
            return public(copy.deepcopy(reading))

    def _attach(self, build, reading):
        """Hand an ACCEPTED reading to `on_reading` and store what it returns as the reading's agreement."""
        hook = self.on_reading
        if hook is None or reading["status"] != "ACCEPTED":
            return
        with self.lock:
            approved = {b["template"]["sha256"]: b for b in self._approved()}
            if reading["template"]["sha256"] not in approved:
                return
            entry = copy.deepcopy(self._entry(build, reading, approved))
        try:
            agreement = hook(entry)
            if agreement is not None and not isinstance(agreement, dict):
                raise TypeError("not an object")
            json.dumps(agreement)
        except Exception as exc:
            with self.lock:
                reading["agreement"] = None
                reading["agreement_note"] = "No agreement was created from this reading: %s" % (
                    getattr(exc, "sentence", None) or type(exc).__name__)
                self._save(build)
            return
        with self.lock:
            reading["agreement"] = copy.deepcopy(agreement)
            self._save(build)


# --- HTTP ---------------------------------------------------------------------------------

def register_template_builds(app, bench, auth):
    """Routes for docs/demo/TEMPLATE-BUILDER.md. The feature is on when app.state.template_builds is set."""
    from typing import Optional

    from fastapi import Depends
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel, ConfigDict, Field

    app.state.template_builds = getattr(app.state, "template_builds", None)

    class Contract(BaseModel):
        model_config = ConfigDict(extra="forbid")
        title: str = Field(min_length=1, max_length=NAME_LIMIT)
        vendor: str = Field(min_length=1, max_length=NAME_LIMIT)
        text: str = Field(min_length=1, max_length=PASTE_LIMIT)

    class Second(BaseModel):
        model_config = ConfigDict(extra="forbid")
        title: str = Field(min_length=1, max_length=NAME_LIMIT)
        text: str = Field(min_length=1, max_length=PASTE_LIMIT)

    class Start(BaseModel):
        model_config = ConfigDict(extra="forbid")
        sample_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
        contract: Optional[Contract] = None
        second_contract: Optional[Second] = None
        consent: bool = False

    class Approve(BaseModel):
        model_config = ConfigDict(extra="forbid")
        template_sha256: str = Field(min_length=1, max_length=128)
        acknowledged: list[str] = Field(default_factory=list, max_length=len(rules.TERMS))

    class Continue(BaseModel):
        model_config = ConfigDict(extra="forbid")

    class Read(BaseModel):
        model_config = ConfigDict(extra="forbid")
        document_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
        contract: Optional[Contract] = None
        consent: bool = False

    def plain(call, status=200):
        try:
            return JSONResponse(call(), status)
        except TemplateRefused as refused:
            return JSONResponse({"detail": str(refused)}, refused.status)

    def service():
        return app.state.template_builds

    off = {"detail": "Not Found"}

    @app.get("/api/template-builds")
    def overview(p=Depends(auth.actor)):
        bench.require_tenant(p)
        if service() is None:
            return {"enabled": False, "reason": DISABLED, "samples": [], "builds": [], "templates": []}
        return service().overview()

    @app.post("/api/template-builds")
    def start(body: Start, p=Depends(auth.reviewer)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"build": service().start(
            sample_id=body.sample_id, contract=body.contract.model_dump() if body.contract else None,
            second_contract=body.second_contract.model_dump() if body.second_contract else None,
            consent=body.consent)}, 202)

    @app.get("/api/template-builds/{build_id}")
    def one(build_id: str, p=Depends(auth.actor)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"build": service().get(build_id)})

    @app.post("/api/template-builds/{build_id}/continue")
    def proceed(build_id: str, body: Continue, p=Depends(auth.reviewer)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"build": service().continue_without_jev(build_id, p.subject)})

    @app.post("/api/template-builds/{build_id}/approve")
    def approve(build_id: str, body: Approve, p=Depends(auth.reviewer)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"build": service().approve(build_id, body.template_sha256, p.subject, body.acknowledged)})

    @app.post("/api/template-builds/{build_id}/read")
    def read(build_id: str, body: Read, p=Depends(auth.reviewer)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        if (body.document_id is None) == (body.contract is None):
            return JSONResponse({"detail": "Give either a document id or a pasted contract."}, 400)
        if body.document_id is not None:
            return plain(lambda: {"reading": service().read(build_id, document_id=body.document_id)})
        if body.consent is not True:
            return JSONResponse({"detail": "A pasted contract is sent to Jev to check its type; consent must be given first."}, 400)
        return plain(lambda: {"reading": service().read(build_id, document=body.contract.model_dump())})

    @app.get("/fixtures/template_builder_demo/{name}")
    def sample_text(name: str, p=Depends(auth.actor)):
        bench.require_tenant(p)
        if name not in shipped_texts():
            return JSONResponse(off, 404)
        return FileResponse(FIXTURES / name, media_type="text/plain; charset=utf-8")
