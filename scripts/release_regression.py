"""Run the full repository Python and browser-JS suites and emit a create-only release report."""
import argparse
from collections import Counter
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uptime.gates import canonical, digest, source_identity


class PythonResults:
    def __init__(self):
        self.collected = []
        self.results = {}
        self.deselected = 0

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_deselected(self, items):
        self.deselected += len(items)

    def pytest_runtest_logreport(self, report):
        if report.outcome != "passed" or report.when == "call":
            result = "unexpected_xpass" if hasattr(report, "wasxfail") else report.outcome
            if self.results.get(report.nodeid, "passed") == "passed":
                self.results[report.nodeid] = result

    def report(self, exit_code):
        counts = Counter(self.results.values())
        if self.deselected:
            counts["deselected"] = self.deselected
        if set(self.collected) != set(self.results) or len(set(self.collected)) != len(self.collected):
            counts["collection_mismatch"] = 1
        return {"collected":len(self.collected), "counts":dict(counts), "exit_code":int(exit_code),
                "collection_sha256":digest(canonical(sorted(self.collected)))}


def javascript(root):
    files = sorted(p.relative_to(root).as_posix() for p in (root/"web").glob("*.test.cjs"))
    if not files:
        raise ValueError("No JS tests collected")
    proc = subprocess.run(["node", "--test", "--test-reporter=tap", *files], cwd=root,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False)
    names = re.findall(r"^(?:not )?ok [0-9]+ - (.+)$", proc.stdout, re.M)
    counters = {name:int(count) for name,count in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) ([0-9]+)$", proc.stdout, re.M)}
    if set(counters) != {"tests","pass","fail","cancelled","skipped","todo"} or counters["tests"] != len(names):
        raise ValueError("Incomplete JS test transcript")
    return {"collected":len(names), "counts":{("passed" if k == "pass" else k):v for k,v in counters.items() if k != "tests" and v},
            "collection_sha256":digest(canonical(sorted(names))), "exit_code":proc.returncode, "files":files}


def main():
    import pytest
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report_path = args.report.resolve()
    if report_path.exists():
        parser.error("Choose a new report path")
    os.chdir(ROOT)
    for key in ("PYTEST_ADDOPTS", "PYTEST_PLUGINS", "NODE_OPTIONS"):
        os.environ.pop(key, None)
    before = source_identity(ROOT)
    runner = PythonResults()
    code = pytest.main(["-q", "tests"], plugins=[runner])
    suites = {"pytest":runner.report(code), "node":javascript(ROOT)}
    data = {"schema":"uptime-full-regression/1", "generated_at":datetime.now(UTC).isoformat(),
            "source":before, "source_stable":source_identity(ROOT) == before,
            "runner_sha256":digest(Path(__file__).read_bytes()), **suites}
    with report_path.open("x") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0 if data["source_stable"] and all(
        s["exit_code"] == 0 and s["collected"] > 0 and s["counts"] == {"passed":s["collected"]} for s in suites.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
