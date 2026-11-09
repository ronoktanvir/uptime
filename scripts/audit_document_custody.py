"""Re-slice every stored adapter citation from its exact stored source text (read-only).

uv run --locked python scripts/audit_document_custody.py --db WORKSPACE.sqlite [--db ...]
Prints a JSON report and exits 1 if any catalog is not traceable. The database is opened in
SQLite immutable mode; nothing is written. Traceable means the cited words are present at
the stated offsets of the stored source; it does not certify their interpretation.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.evidence_custody import audit_database  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, action="append", required=True)
    args = parser.parse_args()
    reports = {}
    for path in args.db:
        try:
            reports[str(path)] = audit_database(path)
        except (OSError, ValueError) as exc:
            reports[str(path)] = dict(traceable=False, error=type(exc).__name__)
    print(json.dumps(reports, indent=2))
    return 0 if all(r["traceable"] for r in reports.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
