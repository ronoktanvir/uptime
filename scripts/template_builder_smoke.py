"""Demo line: one REAL template-builder run, in process, against the real Claude Code CLI and real Jev.

  (a) builds a template from the shipped sample: steps with seconds and the model that answered, checks, and the
      terms that need the reviewer's acknowledgement;
  (b) approves it in a throwaway folder as the reviewer name `smoke-script`, acknowledging what is flagged. A script
      is not a reviewer: this approval exists only in that throwaway folder and says so;
  (c) reads the shipped next contract with the approved template and prints its status and guards;
  (d) starts a second build for a contract of the same form (the next contract, pasted) and shows whether Jev matched
      the approved template and whether any Claude reader ran.

Jev is reached through uptime.jev.JevClient, which reads its own key file; this script never reads or prints it.

    uv run --locked python scripts/template_builder_smoke.py [--claude-executable PATH]
"""
import argparse
from pathlib import Path
import shutil
import sys
import tempfile
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.jev import JevClient  # noqa: E402
from uptime.template_builder import FIXTURES, ClaudeCLI, TemplateBuilds  # noqa: E402


class Counted:
    """The real ClaudeCLI, counting calls."""

    def __init__(self, cli):
        self.cli, self.calls = cli, []

    def __call__(self, system, prompt, model=None):
        self.calls.append(model)
        return self.cli(system, prompt, model=model)


def show_build(build, seconds):
    print("build %s: state %s after %.1f s (sample_id=%s, source=%s)" % (
        build["id"], build["state"], seconds, build["sample_id"], build["source"]["kind"]))
    if build["error"]:
        print("  error:", build["error"]["sentence"])
    for s in build["steps"]:
        d = s["detail"] or {}
        extra = {k: d[k] for k in ("role", "choice", "probability", "repair_rounds", "numbers_listed") if k in d}
        if d.get("conflicts"):
            extra["conflicts"] = [c["field"] for c in d["conflicts"]]
        print("  step %-9s %-8s %6s  model=%-18s %s %s" % (s["id"], s["state"], (s["seconds"] or "-") + "s",
                                                         s["model"], s["summary"], extra or ""))
    for c in build["checks"]:
        print("  check %-18s %s/%s ok=%s blocking=%s%s" % (
            c["id"], c.get("passed"), c.get("total"), c["ok"], c.get("blocking"),
            " ran=%s" % c["ran"] if "ran" in c else ""))
        if c["id"] == "second_document" and c.get("readers"):
            for r in c["readers"]:
                print("        second reader %d %-16s model=%s %ss ok=%s" % (r["reader"], r["role"], r["model"], r["seconds"], r["ok"]))
    for t in build["terms"]:
        print("  term %-28s %-24s %-6s agree=%s/%s in_sentence=%s rule=%s second=%s/%s jev=%s ack=%s" % (
            t["field"], t["display"], t["status"], t["agreement"]["agree"], t["agreement"]["of"], t["value_in_sentence"],
            t["rule_value"], t["second_document_value"], (t["second_readers"] or {}).get("value"),
            t["jev"] and (t["jev"]["yes"], t["jev"]["probability"]), t["needs_acknowledgement"]))


def show_reading(reading):
    print("reading %s: %s; %d of %d terms in %s ms, model_calls=%d, Jev template check %s" % (
        reading["id"], reading["status"], reading["found"], reading["total"], reading["milliseconds"],
        reading["model_calls"], reading["jev_template"]))
    for g in reading["guards"]:
        print("  guard %-18s ok=%-5s %s%s" % (g["id"], g["ok"], g["detail"], " (advisory)" if g.get("advisory") else ""))
    for t in reading["terms"]:
        print("  %-28s %s" % (t["field"], t["display"] if t["value"] is not None else "null: " + str(t["error"])))
    if reading["reasons"]:
        print("  refused because:", "; ".join(reading["reasons"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-executable", default=None)
    args = parser.parse_args()
    executable = args.claude_executable or shutil.which("claude")
    if not executable:
        sys.exit("No Claude Code CLI found.")
    folder = Path(tempfile.mkdtemp(prefix="uptime-tb-smoke-"))
    claude = Counted(ClaudeCLI(executable))
    builds = TemplateBuilds(folder / "template-builds", claude, JevClient(), background=False)
    print("Throwaway folder:", folder)

    print("\n(a) Build from the shipped sample")
    t = perf_counter()
    build = builds.start("halcyon-availability-addendum")
    show_build(build, perf_counter() - t)
    print("Claude calls:", len(claude.calls), "models requested:", sorted(set(claude.calls)))
    flagged = [x["field"] for x in build["terms"] if x["needs_acknowledgement"]]
    print("terms needing acknowledgement:", flagged or "none")
    if build["state"] != "READY_FOR_REVIEW" or not build["template"]:
        sys.exit("The build did not reach review; stopping here.")
    blocking = [c["id"] for c in build["checks"] if c["blocking"] and not c["ok"]]
    if blocking:
        sys.exit("Blocking checks failed (%s); the template cannot be approved. Stopping here." % ", ".join(blocking))

    print("\n(b) Approval BY A SCRIPT (reviewer name smoke-script), in the throwaway folder only; not a human review")
    done = builds.approve(build["id"], build["template"]["sha256"], "smoke-script", flagged)
    print("template %s %s state %s; review step: %s" % (done["template"]["id"], done["template"]["sha256"],
                                                       done["template"]["state"], done["steps"][-1]["summary"]))

    print("\n(c) Read the shipped next contract with the approved template")
    calls = len(claude.calls)
    show_reading(builds.read(build["id"], document_id="halcyon-c"))
    print("Claude calls during the read:", len(claude.calls) - calls)

    print("\n(d) A second build for a contract of the same form (halcyon-c, pasted)")
    calls = len(claude.calls)
    t = perf_counter()
    second = builds.start(contract={"title": "Platform Availability Addendum", "vendor": "Halcyon Grid Services",
                                    "text": (FIXTURES / "halcyon-c.txt").read_text()}, consent=True)
    show_build(second, perf_counter() - t)
    print("Jev matched the approved template:", second["state"] == "MATCHED", second["matched_template"])
    print("Claude calls during the second build:", len(claude.calls) - calls)
    for reading in second["readings"]:
        show_reading(reading)


if __name__ == "__main__":
    main()
