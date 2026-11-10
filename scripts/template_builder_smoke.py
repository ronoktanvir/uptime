"""Demo line: one REAL template build, in process, against the real Claude Code CLI and (when reachable) real Jev.

Prints the build summary: steps with seconds, checks, terms, and whether the proposed template reads document C
completely. No reviewer approval is made here (a script is not a reviewer); document C is read by running the
proposed template through the same fixed interpreter, with no model call.

    uv run --locked python scripts/template_builder_smoke.py [--claude-executable PATH] [--no-jev] [--keep DIR]
"""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime import template_rules as rules  # noqa: E402
from uptime.template_builder import FIXTURES, ClaudeCLI, TemplateBuilds  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-executable", default=None)
    parser.add_argument("--no-jev", action="store_true")
    parser.add_argument("--keep", type=Path, help="Write the build JSON files here instead of a temporary folder")
    args = parser.parse_args()
    executable = args.claude_executable or shutil.which("claude")
    if not executable:
        sys.exit("No Claude Code CLI found.")
    jev = None
    if not args.no_jev:
        from uptime.jev import JevClient
        jev = JevClient()
    folder = args.keep or Path(tempfile.mkdtemp(prefix="uptime-tb-smoke-"))
    builds = TemplateBuilds(folder, ClaudeCLI(executable), jev, background=False)
    build = builds.start("halcyon-availability-addendum")
    print("build", build["id"], "state", build["state"], "files in", folder)
    if build["error"]:
        print("error:", build["error"]["sentence"])
    for s in build["steps"]:
        print("  step %-9s %-8s %-6s %s%s" % (s["id"], s["state"], (s["seconds"] or "-") + "s", s["summary"],
                                             "  " + json.dumps(s["detail"]) if s["detail"] else ""))
    for c in build["checks"]:
        print("  check %-16s %s/%s ok=%s blocking=%s%s" % (c["id"], c["passed"], c["total"], c["ok"], c["blocking"],
              " ran=%s lowest=%s" % (c["ran"], c["lowest"]) if c["id"] == "jev" else ""))
    for t in build["terms"]:
        print("  term %-28s %-24s %s agree=%s/%s rule=%s second=%s jev=%s" % (
            t["field"], t["display"], t["status"], t["agreement"]["agree"], t["agreement"]["of"], t["rule_value"],
            t["second_document_value"], t["jev"] and (t["jev"]["yes"], t["jev"]["probability"])))
        print("       rule:", t["rule"] and t["rule"]["pattern"])
    if build["template"]:
        print("template", build["template"]["id"], build["template"]["sha256"])
        body = builds.builds[build["id"]]["_template_body"]
        expected = json.loads((FIXTURES / "expected.json").read_text())["halcyon-c"]["terms"]
        reading = rules.apply(body, (FIXTURES / "halcyon-c.txt").read_text())
        got = {t["field"]: t["value"] for t in reading["terms"]}
        print("document C (proposed template, no model call): found %d of %d in %s ms; equals expected.json: %s"
              % (reading["found"], reading["total"], reading["milliseconds"], got == expected))
        for f in expected:
            if got[f] != expected[f]:
                print("   differs:", f, "got", got[f], "expected", expected[f])


if __name__ == "__main__":
    main()
