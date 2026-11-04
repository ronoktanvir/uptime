"""Print one deterministic dispute trace to stdout without touching the app's DB."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from uptime.contracts import Principal
from uptime.disputes import DisputeDesk


def trace(case_id):
    reviewer = Principal("bears", "finance-reviewer", "reviewer")
    with TemporaryDirectory() as directory:
        desk = DisputeDesk(Path(directory) / "local.sqlite")
        desk.seed(reviewer.tenant)
        case = desk.case(reviewer, case_id)
        actions = []
        while case["actions"]:
            if len(actions) >= 8:
                raise RuntimeError("Replay exceeded the bounded action budget.")
            action = case["actions"][0]["id"]
            actions.append(action)
            case = desk.act(reviewer, case_id, action)
    keys = ("id", "title", "vendor", "mode", "sources", "stage", "ledger", "clauses", "trace",
            "evidence", "timeline", "submissions", "replies", "filing_cutoff")
    return {**{key: case[key] for key in keys}, "performed_actions": actions}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id", choices=["dispute-cure", "dispute-denial", "dispute-review", "dispute-partial"])
    print(json.dumps(trace(parser.parse_args().case_id), indent=2))
