"""Held-out evaluation of the template builder on contracts it was not written for.

For each frozen form in fixtures/template_builder_heldout/forms/ (documents A, B, C written blind by Claude authors):

1. build a template from A, with B as the second contract (real Claude Code CLI, real Jev);
2. if every blocking check passed, approve it as "evaluation-script" (a script, not a human reviewer);
3. read the held-out contract C with the approved template;
4. score C's read against the hand-written key (key.json): per term correct, wrong, refused or not_stated.

Writes fixtures/template_builder_heldout/results/<timestamp>.json and prints a summary table.

    uv run --locked python scripts/evaluate_template_builder.py

Works on both engine versions. Version 2 (docs/demo/TEMPLATE-BUILDER.md, "Version 2") is used when the service's
start() accepts `contract`: a pasted contract, a keyless second-contract check and guarded reads. Otherwise the
version 1 API is used: the form goes in through `samples=`, and the second-contract check is given the hand-written
key for B as its answer key (recorded in the results as `second_check_uses_answer_key: true`).

The keys (forms/form-<n>/key.json) keep the nine field names of the version 1 and 2 engines. For the version 3 term
set (a credit schedule and durations with units), `version3_key` maps them, and says so in the results:

- credit_schedule = [{below: availability_target_percent, credit: tier_1_credit_percent},
                     {below: tier_2_threshold_percent, credit: tier_2_credit_percent}]. Every held-out C states its
  first tier as starting below the commitment itself (checked by reading each C), so the first tier's threshold is the
  commitment. If any of the five old fields is not_stated, the schedule is not_stated.
- claim_window = {value: claim_window_days, unit: "days"}. Every held-out C states its claim window in calendar days
  (checked by reading each C).
- maintenance_notice: the old key held hours, converting calendar days to hours (days x 24) and marking Business Days
  not_stated. Version 3 records the unit the contract writes, so for each held-out C the key is restated from the
  contract's own sentence in NOTICE_AS_WRITTEN (written by the evaluating agent from the six sentences, after the
  version 3 engine was written). A and B, which are not scored, map hours to {value, "hours"}.
- The other four fields are unchanged.

No credential is read here: the Claude Code CLI uses its own sign-in, and uptime.jev.JevClient reads its key file
itself. Builds run one at a time. The script stops before a form if it has made MAX_CLAUDE_CALLS Claude calls.
"""
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import shutil
import sys
import tempfile
from time import perf_counter
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uptime import template_rules as rules  # noqa: E402
from uptime import template_builder as tb  # noqa: E402

HELDOUT = ROOT / "fixtures" / "template_builder_heldout"
FORMS = HELDOUT / "forms"
RESULTS = HELDOUT / "results"
REVIEWER = "evaluation-script"
MAX_CLAUDE_CALLS = 80
FIELDS = [t["field"] for t in rules.TERMS]
VERSION3 = "credit_schedule" in rules.TERM
# Maintenance notice in each held-out C, as the contract writes it. The old key's value is in the comment.
NOTICE_AS_WRITTEN = {
    "form-1": {"value": "96", "unit": "hours"},           # 5.1 "ninety-six (96) hours' advance notice"; old key 96
    "form-2": {"value": "10", "unit": "days"},            # "at least 10 days' notice"; old key 240 (10 x 24)
    "form-3": {"value": "3", "unit": "business_days"},    # 8.2 "three (3) Business Days' written notice"; old not_stated
    "form-4": {"value": "10", "unit": "business_days"},   # 1.12 "not less than 10 Business Days"; old not_stated
    "form-5": {"value": "10", "unit": "days"},            # 9. "at least 10 days' written notice"; old key 240
    "form-6": {"value": "3", "unit": "business_days"},    # 5.2 "three (3) Business Days' written notice"; old not_stated
}
KEY_MAPPING_NOTE = (
    "Keys keep the old nine field names; version3_key maps them: credit_schedule from the commitment and tier 1 credit "
    "plus tier 2 threshold and credit; claim_window as calendar days; maintenance_notice for each held-out C restated "
    "from the contract's own sentence (NOTICE_AS_WRITTEN), because the old key converted days to hours and marked "
    "Business Days not stated.")


def version3_key(form_id, letter, key_doc):
    """A key document in the version 3 shape (see the module docstring)."""
    old = key_doc["terms"]
    if not VERSION3:
        return key_doc
    tiers = ("availability_target_percent", "tier_1_credit_percent", "tier_2_threshold_percent", "tier_2_credit_percent")
    if any(old[f] == "not_stated" for f in tiers):
        schedule = "not_stated"
    else:
        schedule, _ = rules.canonical_schedule([{"below": old["availability_target_percent"], "credit": old["tier_1_credit_percent"]},
                                                {"below": old["tier_2_threshold_percent"], "credit": old["tier_2_credit_percent"]}])
    claim = "not_stated" if old["claim_window_days"] == "not_stated" else {"value": old["claim_window_days"], "unit": "days"}
    if letter == "c":
        notice = NOTICE_AS_WRITTEN[form_id]
    else:
        notice = "not_stated" if old["maintenance_notice_hours"] == "not_stated" else {"value": old["maintenance_notice_hours"], "unit": "hours"}
    terms = {"availability_target_percent": old["availability_target_percent"], "measurement_period": old["measurement_period"],
             "credit_schedule": schedule, "credit_cap_percent": old["credit_cap_percent"], "claim_window": claim,
             "maintenance_notice": notice, "credit_application": old["credit_application"]}
    return dict(key_doc, terms=terms)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CountingJev:
    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def _wrap(self, name, *args):
        started = perf_counter()
        try:
            answer = getattr(self.inner, name)(*args)
        except Exception as exc:
            self.calls.append({"method": name, "seconds": round(perf_counter() - started, 2), "ok": False,
                               "error": getattr(exc, "sentence", None) or type(exc).__name__})
            raise
        self.calls.append({"method": name, "seconds": round(perf_counter() - started, 2), "ok": True})
        return answer

    def choice(self, question, options, context):
        return self._wrap("choice", question, options, context)

    def yes_no(self, question, context):
        return self._wrap("yes_no", question, context)


class CountingClaudeFactory:
    """Version 2 may build its own ClaudeCLI per model (readers on different models). Counting is done by patching
    tb.ClaudeCLI.__call__ so every CLI call in the engine is recorded whichever object makes it."""

    def __init__(self):
        self.calls = []
        self.original = tb.ClaudeCLI.__call__
        factory = self

        def counted(cli, system, prompt, *args, **kwargs):
            # Version 2 passes the model per call (one reader runs on a different model); pass it through and record it.
            model = kwargs.get("model") or (args[0] if args else None) or cli.model
            started = perf_counter()
            try:
                answer = factory.original(cli, system, prompt, *args, **kwargs)
            except Exception as exc:
                factory.calls.append({"model": model, "seconds": round(perf_counter() - started, 1), "ok": False,
                                      "error": str(exc) or type(exc).__name__})
                raise
            factory.calls.append({"model": model, "seconds": round(perf_counter() - started, 1), "ok": True})
            return answer
        tb.ClaudeCLI.__call__ = counted

    def restore(self):
        tb.ClaudeCLI.__call__ = self.original


def load_forms():
    forms = []
    for folder in sorted(FORMS.glob("form-*")):
        manifest = json.loads((folder / "manifest.json").read_text())
        key = json.loads((folder / "key.json").read_text())
        for name, digest in manifest["files"].items():
            if name.endswith(".txt") and name != "response.txt":
                if hashlib.sha256((folder / name).read_text().encode()).hexdigest() != digest:
                    raise SystemExit("%s/%s does not match its frozen SHA-256; the evaluation stops." % (folder.name, name))
        key = {d: version3_key(folder.name, d, key[d]) if d in "abc" else key[d] for d in key}
        forms.append({"id": folder.name, "folder": folder, "manifest": manifest, "key": key,
                      "texts": {d: (folder / (d + ".txt")).read_text() for d in "abc"}})
    return forms


def expected_of(key_doc):
    """The key as the engine's canonical values; not_stated -> None."""
    return {f: (None if key_doc["terms"][f] == "not_stated" else key_doc["terms"][f]) for f in FIELDS}


def version():
    params = inspect.signature(tb.TemplateBuilds.start).parameters
    return 2 if "contract" in params else 1


def make_service(directory, claude, jev, form, api):
    if api == 2:
        return tb.TemplateBuilds(directory, claude, jev, background=False)
    folder = form["folder"]

    def document(letter):
        k = form["key"][letter]
        return {"id": form["id"] + "-" + letter, "title": "%s · %s" % (k.get("title") or form["id"], k.get("customer")),
                "vendor": k.get("vendor"), "customer": k.get("customer"), "chars": len(form["texts"][letter]),
                "text_url": None, "_path": str(folder / (letter + ".txt")), "_expected": expected_of(k)}
    sample = {"id": "heldout-" + form["id"], "title": form["key"]["a"].get("title") or form["id"],
              "vendor": form["key"]["a"].get("vendor"), "document": document("a"),
              "second_document": document("b"), "next_documents": [document("c")]}
    return tb.TemplateBuilds(directory, claude, jev, samples=[sample], background=False)


def start(service, form, api):
    if api == 2:
        a, b = form["key"]["a"], form["key"]["b"]
        build = service.start(contract={"title": a.get("title") or form["id"], "vendor": a.get("vendor"), "text": form["texts"]["a"]},
                              second_contract={"title": b.get("title") or form["id"], "text": form["texts"]["b"]},
                              consent=True)
        if build.get("state") == "NEEDS_REVIEWER":
            # Jev could not be reached. The product lets a reviewer press "Build without Jev"; the script does so and says so.
            for name in ("continue_build", "continue_without_jev", "proceed", "continue_"):
                if hasattr(service, name):
                    build = getattr(service, name)(build["id"], REVIEWER) if name == "continue_without_jev" \
                        else getattr(service, name)(build["id"])
                    build["_evaluation_note"] = "Jev could not be reached; the script continued the build without Jev (%s)." % name
                    break
        return build
    return service.start("heldout-" + form["id"])


def flagged_terms(build):
    out = []
    for t in build.get("terms") or []:
        if t.get("needs_acknowledgement") or t.get("status") == "REVIEW":
            out.append(t["field"])
    return out


def approve(service, build, api):
    sha = build["template"]["sha256"]
    params = inspect.signature(service.approve).parameters
    if "acknowledged" in params:
        ack = [t["field"] for t in build["terms"] if t.get("needs_acknowledgement")]
        return service.approve(build["id"], sha, REVIEWER, ack), ack
    return service.approve(build["id"], sha, REVIEWER), []


def read_c(service, build, form, api):
    """-> (reading, path) where path says how the read was made."""
    text = form["texts"]["c"]
    params = inspect.signature(service.read).parameters
    for name in ("contract", "text"):
        if name in params:
            arg = {"title": form["key"]["c"].get("title") or form["id"], "vendor": form["key"]["c"].get("vendor"), "text": text} \
                if name == "contract" else text
            return service.read(build["id"], **{name: arg}), "service.read(%s=...)" % name
    if api == 1:
        return service.read(build["id"], form["id"] + "-c"), "service.read(document_id) with C as the sample's next document"
    # Version 2 with no documented way to read a pasted document by an approved template: run the stored approved
    # template through the fixed interpreter and the version 2 guard functions, and say so.
    body = service.builds[build["id"]]["_template_body"]
    result = rules.apply(body, text)
    values = {t["field"]: t["value"] for t in result["terms"]}
    guards = [{"id": "complete", "ok": result["found"] == result["total"], "detail": "%d of %d" % (result["found"], result["total"])}]
    if hasattr(rules, "value_in_sentence"):
        good = sum(1 for t in result["terms"] if t["value"] is not None and rules.value_in_sentence(t["field"], t["value"], t["quote"]))
        guards.append({"id": "value_in_sentence", "ok": good == result["found"], "detail": "%d of %d" % (good, result["found"])})
    if hasattr(rules, "plausibility"):
        problems = rules.plausibility(values)
        guards.append({"id": "plausible", "ok": not problems, "detail": problems or None})
    errors = [t["error"] for t in result["terms"] if t.get("error") and "places" in (t.get("error") or "")]
    guards.append({"id": "unambiguous", "ok": not errors, "detail": errors or None})
    reading = {"read_by": "TEMPLATE", "model_calls": 0, "milliseconds": result["milliseconds"],
               "terms": [{k: t[k] for k in ("field", "value", "display", "quote", "error")} for t in result["terms"]],
               "found": result["found"], "total": result["total"],
               "status": "ACCEPTED" if all(g["ok"] for g in guards) else "REFUSED", "guards": guards}
    return reading, ("script: rules.apply on the approved template plus the template_rules guard functions "
                     "(version 2 exposes no read of a pasted document; Jev's template_match guard was not run)")


def score(reading_terms, key_doc, refused_read=False):
    rows, counts = [], {"correct": 0, "wrong": 0, "refused": 0, "not_stated": 0}
    got = {t["field"]: t for t in reading_terms}
    for f in FIELDS:
        want = key_doc["terms"][f]
        t = got.get(f) or {}
        value = None if refused_read else t.get("value")
        if want == "not_stated":
            # A value returned for a term the contract does not state is a value that is not the key's: wrong.
            outcome = "not_stated" if value is None else "wrong"
        elif value is None:
            outcome = "refused"
        elif rules.same(value, want):
            outcome = "correct"
        else:
            outcome = "wrong"
        counts[outcome] += 1
        rows.append({"field": f, "key": want, "value": t.get("value"), "counted_value": value, "outcome": outcome,
                     "quote": t.get("quote"), "error": t.get("error"),
                     "value_on_not_stated": want == "not_stated" and value is not None})
    return {"terms": rows, "counts": counts}


def run_form(form, api, executable, jev_client, run_dir):
    record = {"form": form["id"], "style_brief": form["manifest"]["brief_file"],
              "author_model": form["manifest"]["models_answered"], "api_version": api,
              "second_check_uses_answer_key": api == 1, "steps": [], "error": None}
    factory = CountingClaudeFactory()
    claude = tb.ClaudeCLI(executable)
    jev = CountingJev(jev_client) if jev_client is not None else None
    started = perf_counter()
    try:
        service = make_service(run_dir / form["id"], claude, jev, form, api)
        t0 = perf_counter()
        build = start(service, form, api)
        record["steps"].append({"step": "build", "seconds": round(perf_counter() - t0, 1), "state": build["state"]})
        record["build"] = build
        body = (service.builds.get(build["id"]) or {}).get("_template_body")
        record["template_body"] = body
        blocking = [c for c in build.get("checks") or [] if c.get("blocking")]
        record["blocking_failed"] = [c["id"] for c in blocking if not c["ok"]]
        record["all_blocking_passed"] = bool(build.get("template")) and bool(blocking) and not record["blocking_failed"] \
            and build["state"] == "READY_FOR_REVIEW"
        record["flagged_terms"] = flagged_terms(build)
        record["approved"] = False
        if record["all_blocking_passed"]:
            t0 = perf_counter()
            approved, ack = approve(service, build, api)
            record["approved"] = approved["state"] == "APPROVED"
            record["acknowledged"] = ack
            record["steps"].append({"step": "approve", "by": REVIEWER, "note": "approved by a script, not a person",
                                    "seconds": round(perf_counter() - t0, 3), "state": approved["state"]})
            t0 = perf_counter()
            reading, path = read_c(service, approved, form, api)
            record["steps"].append({"step": "read_c", "seconds": round(perf_counter() - t0, 3), "path": path})
            record["reading"] = reading
            refused = reading.get("status") == "REFUSED"
            record["score"] = score(reading["terms"], form["key"]["c"], refused_read=refused)
            record["read_status"] = reading.get("status", "no status (version 1 read is unguarded)")
        elif body is not None:
            # Diagnostic only, not the product path: the proposed (unapproved) template run on C.
            result = rules.apply(body, form["texts"]["c"])
            record["diagnostic_unapproved_read_of_c"] = {
                "note": "Not approved, so the product would not read C. This is the proposed template run through the "
                        "fixed interpreter by the script, for diagnosis only; it is not counted in the score.",
                "terms": result["terms"], "score": score(result["terms"], form["key"]["c"])}
    except Exception as exc:
        record["error"] = {"type": type(exc).__name__, "sentence": str(exc), "traceback": traceback.format_exc()}
    finally:
        factory.restore()
    record["seconds"] = round(perf_counter() - started, 1)
    record["claude_calls"] = factory.calls
    record["jev_calls"] = jev.calls if jev else []
    return record


def table(records):
    head = "%-7s %-18s %-17s %-16s %-8s %-7s %-14s %4s %4s %4s %4s %7s %6s %4s" % (
        "form", "author", "build", "blocking failed", "approved", "flagged", "C read", "ok", "wrong", "ref", "n/s",
        "secs", "claude", "jev")
    lines = [head, "-" * len(head)]
    for r in records:
        c = (r.get("score") or {}).get("counts") or {}
        lines.append("%-7s %-18s %-17s %-16s %-8s %-7s %-14s %4s %4s %4s %4s %7s %6s %4s" % (
            r["form"], ",".join(r["author_model"]).replace("claude-", ""), (r.get("build") or {}).get("state", "ERROR"),
            ",".join(r.get("blocking_failed") or []) or "-", "script" if r.get("approved") else "no",
            len(r.get("flagged_terms") or []), (r.get("read_status") or "not read")[:14],
            c.get("correct", "-"), c.get("wrong", "-"), c.get("refused", "-"), c.get("not_stated", "-"),
            r["seconds"], len(r["claude_calls"]), len(r["jev_calls"])))
    return "\n".join(lines)


def main():
    executable = shutil.which("claude")
    if not executable:
        sys.exit("No Claude Code CLI found on PATH.")
    from uptime.jev import JevClient
    jev = JevClient()
    api = version()
    forms = load_forms()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / (stamp + ".json")
    run = {"started_at": now(), "api_version": api, "engine_commit": None, "reviewer": REVIEWER,
           "reviewer_note": "Approvals in this run were made by a script named evaluation-script, not by a person.",
           "key_mapping_note": KEY_MAPPING_NOTE if VERSION3 else None,
           "second_check_note": ("Version 1: the second-contract check is given the hand-written key for B as its "
                                 "answer key, because that API needs one." if api == 1 else
                                 "Version 2: the second-contract check runs without an answer key."),
           "forms": []}
    try:
        import subprocess
        run["engine_commit"] = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                                              text=True).stdout.strip() or None
    except OSError:
        pass
    total_calls = 0
    with tempfile.TemporaryDirectory(prefix="uptime-heldout-") as tmp:
        for form in forms:
            if total_calls >= MAX_CLAUDE_CALLS:
                run["forms"].append({"form": form["id"], "skipped": "stopped at %d Claude calls" % total_calls})
                continue
            print("form %s: building (engine API version %d) ..." % (form["id"], api), flush=True)
            record = run_form(form, api, executable, jev, Path(tmp))
            total_calls += len(record["claude_calls"])
            run["forms"].append(record)
            out.write_text(json.dumps(run, indent=1, default=str) + "\n")
            print("  %s in %.1f s, %d Claude calls%s" % ((record.get("build") or {}).get("state", "ERROR"), record["seconds"],
                  len(record["claude_calls"]), ("; error: " + record["error"]["sentence"]) if record["error"] else ""), flush=True)
    done = [r for r in run["forms"] if "skipped" not in r]
    scored = [r for r in done if r.get("score")]
    totals = {k: sum(r["score"]["counts"][k] for r in scored) for k in ("correct", "wrong", "refused", "not_stated")}
    run["summary"] = {
        "forms": len(forms), "forms_run": len(done),
        "forms_all_blocking_passed": sum(1 for r in done if r.get("all_blocking_passed")),
        "forms_approved_by_script": sum(1 for r in done if r.get("approved")),
        "forms_with_flagged_terms": sum(1 for r in done if r.get("flagged_terms")),
        "forms_with_c_read": len(scored),
        "c_reads_refused": sum(1 for r in scored if r.get("reading", {}).get("status") == "REFUSED"),
        "c_terms": totals, "c_terms_scored": sum(totals.values()),
        "values_returned_for_not_stated_terms": sum(1 for r in scored for t in r["score"]["terms"] if t["value_on_not_stated"]),
        "wrong": [{"form": r["form"], "field": t["field"], "key": t["key"], "value": t["value"], "quote": t["quote"]}
                  for r in scored for t in r["score"]["terms"] if t["outcome"] == "wrong"],
        "claude_calls": sum(len(r["claude_calls"]) for r in done), "jev_calls": sum(len(r["jev_calls"]) for r in done),
        "seconds": round(sum(r["seconds"] for r in done), 1)}
    run["finished_at"] = now()
    out.write_text(json.dumps(run, indent=1, default=str) + "\n")
    print()
    print("Held-out evaluation, engine API version %d (%s). Approvals were made by a script (%s), not a person."
          % (api, run["engine_commit"], REVIEWER))
    print(run["second_check_note"])
    if VERSION3:
        print(KEY_MAPPING_NOTE)
    print(table(done))
    s = run["summary"]
    print()
    print("forms: %d; all blocking checks passed: %d; approved by the script: %d; forms with a term flagged for the reviewer: %d"
          % (s["forms_run"], s["forms_all_blocking_passed"], s["forms_approved_by_script"], s["forms_with_flagged_terms"]))
    print("held-out C: %d forms read (%d reads refused); of %d terms scored: %d correct, %d wrong, %d refused, %d not stated"
          % (s["forms_with_c_read"], s["c_reads_refused"], s["c_terms_scored"], totals["correct"], totals["wrong"],
             totals["refused"], totals["not_stated"]))
    print("(n/s: the key says the contract does not state the term and the read returned nothing; a value returned "
          "for such a term is counted wrong: %d)" % s["values_returned_for_not_stated_terms"])
    for w in s["wrong"]:
        print("WRONG %s %s: key %s, returned %s, from: %s" % (w["form"], w["field"], json.dumps(w["key"]), json.dumps(w["value"]),
                                                            w["quote"]))
    print("calls: %d Claude, %d Jev; %.1f s in all" % (s["claude_calls"], s["jev_calls"], s["seconds"]))
    print("results:", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
