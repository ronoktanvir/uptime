"""Demo line: build a deterministic reader (a template) for a contract type Uptime has not read before.

Jev says whether the contract matches a template on file; three Claude readers extract the fixed terms with their
sentences; a Claude template builder writes one extraction rule per term (data, run by uptime.template_rules);
code checks the result; Jev says whether each sentence supports its term; a reviewer approves the exact template
version by SHA-256; after that the next contract of the type is read by the template alone, with no model call.

Only the shipped samples can be built, and at most MAX_BUILDS builds run per server process, so no arbitrary text is
sent to a model. Interface: docs/demo/TEMPLATE-BUILDER.md.
"""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
from decimal import Decimal
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
CLAUDE_SECONDS = 90
MAX_BUILDS = 6
REPAIR_ROUNDS = 2
JEV_THRESHOLD = Decimal("0.90")
TEMPLATES_ON_FILE = ("northwind-cloud-sla", "corvid-ledger-sla")
RUNNING = ("QUEUED", "CLASSIFYING", "READING", "BUILDING", "CHECKING")
STEPS = (("classify", "JEV", "Which contract type is this?"), ("reader-1", "CLAUDE", "Reader 1"),
         ("reader-2", "CLAUDE", "Reader 2"), ("reader-3", "CLAUDE", "Reader 3"),
         ("build", "CLAUDE", "Template builder"), ("checks", "UPTIME", "Checks"),
         ("review", "REVIEWER", "Reviewer approval"))
DISABLED = "Building templates with Claude is off on this server; start it with --template-builder."


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
    folder = Path(folder)
    expected = json.loads((folder / "expected.json").read_text())

    def document(ident, title):
        text = (folder / (ident + ".txt")).read_text()
        return {"id": ident, "title": title, "vendor": "Halcyon Grid Services", "customer": expected[ident]["customer"],
                "chars": len(text), "text_url": "/fixtures/template_builder_demo/" + ident + ".txt",
                "_path": str(folder / (ident + ".txt")), "_expected": expected[ident]["terms"]}
    title = "Platform Availability Addendum"
    return [{"id": "halcyon-availability-addendum", "title": "Halcyon Grid: Platform Availability Addendum",
             "vendor": "Halcyon Grid Services",
             "document": document("halcyon-a", title + " · " + expected["halcyon-a"]["customer"]),
             "second_document": document("halcyon-b", title + " · " + expected["halcyon-b"]["customer"]),
             "next_documents": [document("halcyon-c", title + " · " + expected["halcyon-c"]["customer"])]}]


def public(value):
    """Drop private keys (leading underscore) from a nested answer."""
    if isinstance(value, dict):
        return {k: public(v) for k, v in value.items() if not k.startswith("_")}
    if isinstance(value, list):
        return [public(v) for v in value]
    return value


# --- Claude through the local Claude Code CLI ---------------------------------------------

class ClaudeCLI:
    """claude(system, prompt) -> text, through the pinned safe profile: tools off, no session persistence,
    a fresh empty temporary directory, a time limit. The CLI's own sign-in is used; no credential is read here."""

    def __init__(self, executable, model=MODEL, timeout=CLAUDE_SECONDS):
        self.executable = str(Path(executable).resolve(strict=True))
        self.model, self.timeout = model, timeout

    def __call__(self, system, prompt):
        from .correspondence_model_transport import public_environment
        env = public_environment()
        env["PATH"] = os.environ.get("PATH", env["PATH"])
        if "CLAUDE_CODE_OAUTH_TOKEN" in os.environ:
            env["CLAUDE_CODE_OAUTH_TOKEN"] = os.environ["CLAUDE_CODE_OAUTH_TOKEN"]
        argv = [self.executable, "-p", "--safe-mode", "--model", self.model, "--tools", "", "--strict-mcp-config",
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
        if envelope.get("is_error") is not False or self.model not in (envelope.get("modelUsage") or {}):
            raise ModelFailed("The answer did not come from %s." % self.model)
        if not isinstance(envelope.get("result"), str):
            raise ModelFailed("The Claude Code CLI answer had no text.")
        return envelope["result"]


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
        out.append(row)
    return json.dumps(out, indent=1)


def reader_prompt(text):
    return ("Read the contract below and return these terms:\n" + _schema() + "\n\n"
            "For each term give `value` and `quote`.\n"
            "- value: for percent, the number as a string without the % sign (\"99.5\"); for integer, digits as a "
            "string (\"30\"); for choice, one of the option ids; null if the contract does not state the term.\n"
            "- quote: the one sentence or list item the value comes from, copied character for character from the "
            "contract (keep its section number if it has one); null when value is null.\n"
            "Answer as {\"terms\": {\"<field>\": {\"value\": ..., \"quote\": ...}, ...}} with exactly these fields.\n\n"
            "CONTRACT\n<<<\n" + text + "\n>>>")


RULE_SPEC = (
    "A rule is {\"pattern\": <regular expression>} (choice terms add \"map\": {<captured phrase, lowercase>: <option id>}).\n"
    "- Python `re` syntax. Uptime runs re.search(pattern, contract, re.IGNORECASE) on the contract with every run of "
    "whitespace (newlines included) collapsed to one space; the first match wins.\n"
    "- Exactly one capturing group, holding only the value: for percent the number without % "
    "(like (\\d+(?:\\.\\d+)?)), for integer the digits, for choice the contract's own phrase. Use (?:...) for other "
    "groups. No back-references. At most 400 characters.\n"
    "- The same rule must read other contracts of this form, where every number, percentage, party, date, address "
    "and order number is different. Never write the value's own digits into the pattern; Uptime refuses a rule "
    "that does. Anchor on the fixed wording of the clause so that the first match is the right clause, and beware "
    "other numbers in the contract (payment terms, termination notice, emergency maintenance, review periods).\n"
    "- Avoid nested quantifiers such as (a+)+; prefer explicit wording or [^.;]*? between anchors.\n")


def builder_prompt(text, agreed):
    terms = [{"field": f, "type": rules.TERM[f]["type"], "value": v["value"], "sentence": v["quote"]}
             for f, v in agreed.items()]
    return ("Write one extraction rule per term for this contract form.\n" + RULE_SPEC +
            "\nThe terms the readers found in this contract:\n" + json.dumps(terms, indent=1) +
            "\n\nAnswer as {\"rules\": {\"<field>\": {\"pattern\": ...}, ...}} with exactly these fields: "
            + ", ".join(agreed) + ".\n\nCONTRACT\n<<<\n" + text + "\n>>>")


def repair_prompt(text, second_text, agreed, current, failures):
    rows = [{"field": f, "type": rules.TERM[f]["type"], "value_in_this_contract": agreed[f]["value"],
             "sentence": agreed[f]["quote"], "current_rule": current.get(f), "what_went_wrong": failures[f]}
            for f in failures]
    return ("Some extraction rules for this contract form failed. Write corrected rules for these fields only.\n"
            + RULE_SPEC + "\nThe failed rules:\n" + json.dumps(rows, indent=1) +
            "\n\nAnswer as {\"rules\": {\"<field>\": {\"pattern\": ...}, ...}} with exactly these fields: "
            + ", ".join(failures) + ".\n\nCONTRACT (the one the readers read)\n<<<\n" + text + "\n>>>\n\n"
            "SECOND CONTRACT OF THE SAME FORM (its terms are not given to you)\n<<<\n" + second_text + "\n>>>")


def parse_reader(answer):
    value = strict_object(answer)
    terms = value.get("terms")
    if set(value) != {"terms"} or not isinstance(terms, dict) or set(terms) != set(rules.TERM):
        raise ModelFailed("The reader's answer did not have exactly the fixed terms.")
    out = {}
    for field, item in terms.items():
        if not isinstance(item, dict) or set(item) != {"value", "quote"}:
            raise ModelFailed("The reader's answer for %s was not {value, quote}." % field)
        raw, quote = item["value"], item["quote"]
        if raw is not None and not isinstance(raw, (str, int, Decimal)) or isinstance(raw, bool):
            raise ModelFailed("The reader's value for %s has the wrong type." % field)
        if quote is not None and not isinstance(quote, str):
            raise ModelFailed("The reader's quote for %s is not text." % field)
        term = rules.TERM[field]
        value_ = rules.canonical(term["type"], raw, term.get("options")) if raw is not None else None
        out[field] = {"value": value_, "quote": quote, "invalid": raw is not None and value_ is None}
    return out


def parse_rules(answer, fields):
    value = strict_object(answer)
    found = value.get("rules")
    if set(value) != {"rules"} or not isinstance(found, dict) or set(found) != set(fields):
        raise ModelFailed("The builder's answer did not have exactly one rule per requested term.")
    out = {}
    for field, item in found.items():
        choice = rules.TERM[field]["type"] == "choice"
        allowed = {"pattern", "map"} if choice else {"pattern"}
        if not isinstance(item, dict) or "pattern" not in item or not set(item) <= allowed:
            raise ModelFailed("The builder's rule for %s has the wrong shape." % field)
        if not isinstance(item["pattern"], str):
            raise ModelFailed("The builder's pattern for %s is not text." % field)
        rule = {"field": field, "type": rules.TERM[field]["type"], "pattern": item["pattern"], "group": 1}
        if choice:
            mapping = item.get("map")
            if not isinstance(mapping, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in mapping.items()):
                raise ModelFailed("The builder's map for %s is not phrase to option." % field)
            rule["map"] = dict(mapping)
        out[field] = rule
    return out


# --- The orchestration --------------------------------------------------------------------

class TemplateBuilds:
    def __init__(self, directory, claude, jev, samples=None, max_builds=MAX_BUILDS, background=True):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        self.claude, self.jev = claude, jev
        self.samples = {s["id"]: s for s in (samples if samples is not None else demo_samples())}
        self.max_builds, self.background = max_builds, background
        self.started = 0
        self.lock = Lock()
        self.builds = {}
        for path in sorted(self.directory.glob("tb_*.json")):
            try:
                build = json.loads(path.read_text())
            except (OSError, ValueError):
                continue
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
    def _save(self, build):
        path = self.directory / (build["id"] + ".json")
        handle, temporary = tempfile.mkstemp(dir=self.directory, prefix=".tb-")
        try:
            os.fchmod(handle, 0o600)
            with os.fdopen(handle, "w") as out:
                json.dump(build, out, indent=1)
            os.replace(temporary, path)
        except BaseException:
            if os.path.exists(temporary):
                os.unlink(temporary)
            raise

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
            build = self.builds.get(build_id)
            if build is None:
                raise TemplateRefused("No template build with that id.", 404)
            return public(copy.deepcopy(build))

    def _templates(self):
        out = []
        for build in self.builds.values():
            t = build.get("template")
            if t:
                sample = self.samples.get(build["sample_id"], {})
                out.append({**{k: t[k] for k in ("id", "sha256", "rules", "state", "approved_by", "approved_at")},
                            "sample_id": build["sample_id"], "vendor": sample.get("vendor"), "title": sample.get("title")})
        return out

    def overview(self):
        with self.lock:
            builds = sorted(self.builds.values(), key=lambda b: b["started_at"], reverse=True)
            return {"enabled": True, "reason": None, "samples": [public(s) for s in self.samples.values()],
                    "builds": public(copy.deepcopy(builds)), "templates": public(self._templates())}

    # -- Start
    def start(self, sample_id):
        with self.lock:
            sample = self.samples.get(sample_id)
            if sample is None:
                raise TemplateRefused("Only the shipped sample contracts can be built.", 404)
            for build in self.builds.values():
                if build["sample_id"] == sample_id and build["state"] in RUNNING:
                    return public(copy.deepcopy(build))
            if self.started >= self.max_builds:
                raise TemplateRefused("This server has run its %d template builds; restart it to run more." % self.max_builds, 429)
            self.started += 1
            stamp = now()
            build = {"id": "tb_" + secrets.token_hex(3), "sample_id": sample_id, "state": "QUEUED",
                     "started_at": stamp, "updated_at": stamp, "finished_at": None,
                     "steps": [{"id": i, "actor": a, "label": label, "state": "PENDING", "started_at": None,
                                "finished_at": None, "seconds": None,
                                "model": MODEL if a == "CLAUDE" else None, "summary": None, "detail": {}}
                               for i, a, label in STEPS],
                     "terms": [], "checks": [], "template": None, "error": None}
            build["steps"][-1]["summary"] = "Waiting for the template"
            self.builds[build["id"]] = build
            self._save(build)
        if self.background:
            Thread(target=self._run, args=(build,), daemon=True, name="template-build-" + build["id"]).start()
        else:
            self._run(build)
        return self.get(build["id"])

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

    # -- The steps
    def _classify(self, build, sample, text):
        self._update(build, state="CLASSIFYING")
        self._step(build, "classify", state="RUNNING")
        options = list(TEMPLATES_ON_FILE) + sorted({b["sample_id"] for b in self.builds.values()
                                                     if (b.get("template") or {}).get("state") == "APPROVED"}) + ["unrecognised"]
        if self.jev is None:
            self._step(build, "classify", state="FAILED", summary="Jev could not be reached: no Jev client is configured on this server.",
                       detail={"options": options})
            return False
        try:
            answer = self.jev.choice("Which contract template does this document follow?", options, text[:1500])
        except Exception as exc:
            self._step(build, "classify", state="FAILED", detail={"options": options},
                       summary="Jev could not be reached: " + (getattr(exc, "sentence", None) or "the call failed."))
            return False
        choice = answer["choice"]
        summary = ("No template on file matches" if choice == "unrecognised"
                   else "Jev matched the template " + choice + "; building a new one anyway")
        self._step(build, "classify", state="DONE", model=answer.get("model"), summary=summary,
                   detail={"choice": choice, "probability": str(answer["probability"]), "options": options})
        return True

    def _read(self, build, index, text):
        ident = "reader-%d" % index
        self._step(build, ident, state="RUNNING")
        try:
            found = parse_reader(self.claude(SYSTEM, reader_prompt(text)))
        except Exception as exc:
            self._step(build, ident, state="FAILED", summary=str(exc) if isinstance(exc, ModelFailed) else
                       "The call failed: " + type(exc).__name__)
            return None
        normalized = rules.normalize(text)
        stated = 0
        for item in found.values():
            item["quote_found"] = bool(item["quote"]) and rules.normalize(item["quote"]) in normalized
            stated += item["value"] is not None
        quotes = sum(i["quote_found"] for i in found.values() if i["value"] is not None)
        self._step(build, ident, state="DONE", summary="%d terms, %d quotes found in the contract" % (stated, quotes),
                   detail={"terms": stated, "quotes_found": quotes})
        return found

    def _pipeline(self, build):
        sample = self.samples[build["sample_id"]]
        text = Path(sample["document"]["_path"]).read_text()
        second = sample["second_document"]
        second_text = Path(second["_path"]).read_text()
        jev_ok = self._classify(build, sample, text)

        # Readers, in parallel
        self._update(build, state="READING")
        with ThreadPoolExecutor(3) as pool:
            readings = list(pool.map(lambda i: self._read(build, i, text), (1, 2, 3)))
        succeeded = [(i + 1, r) for i, r in enumerate(readings) if r is not None]
        if len(succeeded) < 2:
            self._fail(build, "Only %d of 3 Claude readers answered in the expected shape; at least 2 are needed." % len(succeeded))
            return
        agreed = {}
        for term in rules.TERMS:
            f = term["field"]
            votes = Counter(r[f]["value"] for _, r in succeeded)
            value, count = max(votes.items(), key=lambda kv: (kv[1], -[r[f]["value"] for _, r in succeeded].index(kv[0])))
            holders = [r[f] for _, r in succeeded if r[f]["value"] == value]
            best = next((h for h in holders if h["quote_found"]), holders[0])
            agreed[f] = {"value": value, "quote": best["quote"], "agree": count}

        # Builder, then up to two repair rounds
        self._update(build, state="BUILDING")
        self._step(build, "build", state="RUNNING")
        try:
            current = parse_rules(self.claude(SYSTEM, builder_prompt(text, agreed)), list(agreed))
        except Exception as exc:
            sentence = str(exc) if isinstance(exc, ModelFailed) else "The call failed: " + type(exc).__name__
            self._step(build, "build", state="FAILED", summary=sentence)
            self._fail(build, "The template builder did not return usable rules: " + sentence)
            return
        expected_b = second["_expected"]
        repairs, repair_note = 0, None

        def evaluate():
            on_a = rules.apply({"rules": list(current.values())}, text)
            on_b = rules.apply({"rules": list(current.values())}, second_text)
            a = {t["field"]: t for t in on_a["terms"]}
            b = {t["field"]: t for t in on_b["terms"]}
            failures = {}
            for f in agreed:
                problems = []
                if a[f]["value"] != agreed[f]["value"]:
                    problems.append("On this contract the rule " + (
                        "returned %r but the readers found %r." % (a[f]["value"], agreed[f]["value"])
                        if a[f]["value"] is not None else "failed: " + (a[f]["error"] or "found nothing.")))
                if b[f]["value"] != expected_b[f]:
                    problems.append("On the second contract the rule " + (
                        "captured a value that is not that contract's term." if b[f]["value"] is not None
                        else "failed: " + (b[f]["error"] or "found nothing.")))
                if problems:
                    failures[f] = " ".join(problems)
            return a, b, failures

        on_a, on_b, failures = evaluate()
        while failures and repairs < REPAIR_ROUNDS:
            self._step(build, "build", summary="%d of %d rules failed a check; repair round %d"
                       % (len(failures), len(agreed), repairs + 1), detail={"rules": len(current), "repair_rounds": repairs})
            try:
                fixed = parse_rules(self.claude(SYSTEM, repair_prompt(
                    text, second_text, agreed, {f: {k: v for k, v in current[f].items() if k in ("pattern", "map")}
                                                for f in failures}, failures)), list(failures))
            except Exception as exc:
                repair_note = "Repair round %d failed: %s" % (repairs + 1, str(exc) if isinstance(exc, ModelFailed) else type(exc).__name__)
                repairs += 1
                break
            current.update(fixed)
            repairs += 1
            on_a, on_b, failures = evaluate()
        summary = "%d extraction rules written" % len(current)
        if repairs:
            summary += ", %d repair round%s" % (repairs, "" if repairs == 1 else "s")
        if failures:
            summary += "; %d still fail" % len(failures)
        detail = {"rules": len(current), "repair_rounds": repairs}
        if repair_note:
            detail["repair_note"] = repair_note
        body = {"id": "%s/%d" % (sample["id"], 1 + sum(1 for b in self.builds.values()
                                                       if b["sample_id"] == sample["id"] and b.get("template"))),
                "sample_id": sample["id"], "vendor": sample["vendor"], "form": sample["title"], "interpreter": "uptime.template_rules/1",
                "rules": [current[t["field"]] for t in rules.TERMS if t["field"] in current]}
        digest = rules.sha256(body)
        with self.lock:
            build["_template_body"] = body
            build["template"] = {"id": body["id"], "sha256": digest, "rules": len(body["rules"]), "state": "PROPOSED",
                                 "approved_by": None, "approved_at": None}
        self._step(build, "build", state="DONE", summary=summary, detail=detail)

        # Checks
        self._update(build, state="CHECKING")
        self._step(build, "checks", state="RUNNING")
        terms = []
        for term in rules.TERMS:
            f = term["field"]
            a = agreed[f]
            terms.append({"field": f, "label": term["label"], "type": term["type"], "value": a["value"],
                          "display": rules.display(f, a["value"]), "quote": a["quote"],
                          "readers": [{"reader": i, "value": r[f]["value"], "quote_found": r[f]["quote_found"]}
                                      for i, r in succeeded],
                          "agreement": {"agree": a["agree"], "of": len(succeeded)},
                          "rule": {k: v for k, v in current[f].items() if k in ("pattern", "group", "map")} if f in current else None,
                          "rule_value": on_a[f]["value"], "rule_quote": on_a[f]["quote"], "rule_error": on_a[f]["error"],
                          "second_document_value": on_b[f]["value"],
                          "second_document_ok": on_b[f]["value"] == expected_b[f],
                          "jev": None, "status": None})
        jev_ran = False
        if jev_ok and self.jev is not None:
            def ask(term):
                if term["value"] is None or not term["quote"]:
                    return None
                shown = term["display"]
                question = "Does this sentence state that " + rules.TERM[term["field"]]["question"].format(
                    display=shown, display_lower=shown.lower()) + "?"
                try:
                    answer = self.jev.yes_no(question, term["quote"])
                except Exception:
                    return None
                return {"yes": bool(answer["yes"]), "probability": str(answer["probability"]), "model": answer.get("model")}
            with ThreadPoolExecutor(4) as pool:
                for term, verdict in zip(terms, pool.map(ask, terms)):
                    term["jev"] = verdict
            jev_ran = any(t["jev"] is not None for t in terms)
        reader_quotes = [(i, r[f]) for i, r in succeeded for f in r if r[f]["value"] is not None or r[f]["invalid"]]

        def jev_pass(t):
            return t["jev"] is not None and t["jev"]["yes"] and Decimal(t["jev"]["probability"]) >= JEV_THRESHOLD
        for t in terms:
            fine = (t["agreement"]["agree"] == t["agreement"]["of"] and all(r["quote_found"] for r in t["readers"] if r["value"] is not None)
                    and t["rule_value"] == t["value"] and t["second_document_ok"] and (not jev_ran or jev_pass(t)))
            t["status"] = "PASS" if fine else "REVIEW"
        answered = [t for t in terms if t["jev"] is not None]
        checks = [
            {"id": "quotes", "label": "Every quote is in the contract, word for word",
             "passed": sum(1 for _, q in reader_quotes if q.get("quote_found")), "total": len(reader_quotes), "blocking": True, "by": "UPTIME"},
            {"id": "agreement", "label": "The %s readers agree" % ("three" if len(succeeded) == 3 else "two"),
             "passed": sum(t["agreement"]["agree"] == t["agreement"]["of"] for t in terms), "total": len(terms), "blocking": False, "by": "UPTIME"},
            {"id": "reproduce", "label": "The template returns every term from this contract",
             "passed": sum(t["rule_value"] == t["value"] for t in terms), "total": len(terms), "blocking": True, "by": "UPTIME"},
            {"id": "second_document", "label": "The template reads a second contract of the same form",
             "passed": sum(t["second_document_ok"] for t in terms), "total": len(terms), "blocking": True, "by": "UPTIME",
             "document": {"id": second["id"], "title": second["title"]}},
            {"id": "jev", "label": "Jev: each term is supported by its sentence", "passed": sum(jev_pass(t) for t in terms),
             "total": len(terms), "blocking": False, "by": "JEV", "threshold": str(JEV_THRESHOLD),
             "lowest": min((t["jev"]["probability"] for t in answered), key=Decimal) if answered else None, "ran": jev_ran},
        ]
        for c in checks:
            c["ok"] = c["passed"] == c["total"] and c["total"] > 0 and (c["id"] != "jev" or jev_ran)
        passed = sum(c["ok"] for c in checks)
        blocking_failed = [c["label"] for c in checks if c["blocking"] and not c["ok"]]
        summary = "%d of %d checks passed" % (passed, len(checks))
        if blocking_failed:
            summary += "; blocking: " + "; ".join(blocking_failed)
        with self.lock:
            build["terms"], build["checks"] = terms, checks
        self._step(build, "checks", state="DONE", summary=summary, detail={"passed": passed, "total": len(checks)})
        self._step(build, "review", summary="Waiting for a reviewer" if not blocking_failed
                   else "Approval is blocked until the failed checks pass")
        self._update(build, state="READY_FOR_REVIEW", finished_at=now())

    # -- Reviewer approval and the post-approval read
    def approve(self, build_id, sha, reviewer):
        with self.lock:
            build = self.builds.get(build_id)
            if build is None:
                raise TemplateRefused("No template build with that id.", 404)
            if build["state"] != "READY_FOR_REVIEW" or not build.get("template"):
                raise TemplateRefused("Only a template that is ready for review can be approved; this build is %s." % build["state"])
            if not isinstance(sha, str) or sha != build["template"]["sha256"] or rules.sha256(build["_template_body"]) != sha:
                raise TemplateRefused("That SHA-256 is not this build's template; nothing was approved.")
            failed = [c["label"] for c in build["checks"] if c["blocking"] and not c["ok"]]
            if failed:
                raise TemplateRefused("A blocking check failed, so this template cannot be approved: " + "; ".join(failed) + ".")
            stamp = now()
            build["template"].update(state="APPROVED", approved_by=reviewer, approved_at=stamp)
            step = build["steps"][-1]
            step.update(state="DONE", started_at=stamp, finished_at=stamp, summary="Approved by " + reviewer,
                        detail={"template_sha256": sha})
            build.update(state="APPROVED", updated_at=stamp)
            self._save(build)
            return public(copy.deepcopy(build))

    def read(self, build_id, document_id):
        with self.lock:
            build = self.builds.get(build_id)
            if build is None:
                raise TemplateRefused("No template build with that id.", 404)
            if build["state"] != "APPROVED" or (build.get("template") or {}).get("state") != "APPROVED":
                raise TemplateRefused("This template is not approved yet, so it cannot read contracts.")
            body = build["_template_body"]
            if rules.sha256(body) != build["template"]["sha256"]:
                raise TemplateRefused("The stored template no longer matches its approved SHA-256.")
            sample = self.samples[build["sample_id"]]
        document = next((d for d in sample["next_documents"] if d["id"] == document_id), None)
        if document is None:
            raise TemplateRefused("That document is not one of this sample's next contracts.", 404)
        result = rules.apply(body, Path(document["_path"]).read_text())
        return {"document": {"id": document["id"], "title": document["title"], "vendor": document["vendor"]},
                "read_by": "TEMPLATE", "template": {"id": body["id"], "sha256": build["template"]["sha256"]},
                "model_calls": 0, "milliseconds": result["milliseconds"],
                "terms": [{k: t[k] for k in ("field", "label", "type", "value", "display", "quote")} for t in result["terms"]],
                "found": result["found"], "total": result["total"], "read_at": now()}


# --- HTTP ---------------------------------------------------------------------------------

def register_template_builds(app, bench, auth):
    """Routes for docs/demo/TEMPLATE-BUILDER.md. The feature is on when app.state.template_builds is set."""
    from fastapi import Depends
    from fastapi.responses import FileResponse, JSONResponse
    from pydantic import BaseModel, ConfigDict, Field

    app.state.template_builds = getattr(app.state, "template_builds", None)

    class Start(BaseModel):
        model_config = ConfigDict(extra="forbid")
        sample_id: str = Field(min_length=1, max_length=128)

    class Approve(BaseModel):
        model_config = ConfigDict(extra="forbid")
        template_sha256: str = Field(min_length=1, max_length=128)

    class Read(BaseModel):
        model_config = ConfigDict(extra="forbid")
        document_id: str = Field(min_length=1, max_length=128)

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
        return plain(lambda: {"build": service().start(body.sample_id)}, 202)

    @app.get("/api/template-builds/{build_id}")
    def one(build_id: str, p=Depends(auth.actor)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"build": service().get(build_id)})

    @app.post("/api/template-builds/{build_id}/approve")
    def approve(build_id: str, body: Approve, p=Depends(auth.reviewer)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"build": service().approve(build_id, body.template_sha256, p.subject)})

    @app.post("/api/template-builds/{build_id}/read")
    def read(build_id: str, body: Read, p=Depends(auth.reviewer)):
        bench.require_tenant(p)
        if service() is None:
            return JSONResponse(off, 404)
        return plain(lambda: {"reading": service().read(build_id, body.document_id)})

    @app.get("/fixtures/template_builder_demo/{name}")
    def sample_text(name: str, p=Depends(auth.actor)):
        if not re.fullmatch(r"halcyon-[abc]\.txt", name):
            return JSONResponse(off, 404)
        return FileResponse(FIXTURES / name, media_type="text/plain; charset=utf-8")
