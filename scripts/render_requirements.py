"""Render the V3 requirement checklist from its JSON source.

    uv run --locked python scripts/render_requirements.py           # rewrite REQUIREMENTS.md
    uv run --locked python scripts/render_requirements.py --check   # fail if it is out of date

The JSON file is the maintained record. This script only formats it; it never
changes a disposition, owner or gap.
"""
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/v4/integration90/requirements.json"
TARGET = ROOT / "docs/v4/integration90/REQUIREMENTS.md"
UP = "../../../"
ORDER = ("MET", "MET_LOCAL", "PARTIAL", "NOT_MET", "SUPERSEDED")


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ")


def ref(item):
    path, _, name = item.partition("::")
    base = path.partition("#")[0]
    label = f"`{name}`" if name else Path(base).name
    return f"[{label}]({UP}{path})"


def render(data):
    reqs = data["requirements"]
    out = ["# V3 requirement completion checklist", "",
           f"Every requirement in the original V3 handoff, specification and DAG, with its current disposition. "
           f"Snapshot {data['as_of']}; baseline `{data['baseline_commit'][:7]}`. "
           "Generated from [requirements.json](requirements.json) by `scripts/render_requirements.py`; "
           "`tests/test_requirements_traceability.py` fails if a requirement disappears, a cited file or test does not exist, "
           "or an incomplete item lacks a gap, class and owner.", "",
           "A disposition describes evidence, not effort. MET_LOCAL means verified with local tests or authored or controlled data; "
           "it is not live Ramp, real vendor or customer proof.", "",
           "## Summary", "", "| Disposition | Count | Meaning |", "|:---|---:|:---|"]
    counts = Counter(r["disposition"] for r in reqs)
    for d in ORDER:
        out.append(f"| {d} | {counts.get(d, 0)} | {cell(data['dispositions'][d])} |")
    out.append(f"| **Total** | **{len(reqs)}** | |")
    out += ["", "| Gap class (open items) | Count |", "|:---|---:|"]
    classes = Counter(r["gap_class"] for r in reqs if r["gap_class"])
    for c in data["gap_classes"]:
        out.append(f"| {c.replace('_', ' ')} | {classes.get(c, 0)} |")
    out += ["", "| Owner | Open items | Workstream |", "|:---|---:|:---|"]
    owners = Counter(r["owner"] for r in reqs if r["disposition"] in ("PARTIAL", "NOT_MET"))
    for o, desc in data["owners"].items():
        out.append(f"| {o} | {owners.get(o, 0)} | {cell(desc)} |")
    groups = []
    for r in reqs:
        if r["group"] not in groups:
            groups.append(r["group"])
    for g in groups:
        out += ["", f"## {g}", "", "| ID | Requirement | Disposition | Evidence | Gap (class) | Owner | Decisions |",
                "|:---|:---|:---|:---|:---|:---|:---|"]
        for r in (x for x in reqs if x["group"] == g):
            evidence = " · ".join(ref(e) for e in r["implementation"] + r["evidence"])
            gap = cell(r["gap"]) + (f" ({r['gap_class'].replace('_', ' ')})" if r["gap_class"] else "")
            out.append(f"| {r['id']} | {cell(r['requirement'])} [source]({UP}{r['source']}) | {r['disposition']} | {evidence} | "
                       f"{gap or '—'} | {r['owner']} | {', '.join(r['decisions']) or '—'} |")
    return "\n".join(out) + "\n"


def main(argv):
    text = render(json.loads(SOURCE.read_text()))
    if "--check" in argv:
        if TARGET.read_text() != text:
            print("REQUIREMENTS.md is out of date; run scripts/render_requirements.py", file=sys.stderr)
            return 1
        return 0
    TARGET.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
