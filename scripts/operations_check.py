"""Read-only workspace health report. Exit 0 when OK, 2 when an operator must act, 1 when unreadable."""
import argparse
from datetime import timedelta
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.operations_health import check, render


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--outbox", type=Path, help="Native outbox database next to the native configuration")
    parser.add_argument("--config", type=Path, action="append", default=[],
                        help="Protected configuration or credential file to check for custody only (repeatable)")
    parser.add_argument("--stale-hours", type=int, default=24, choices=range(1, 169), metavar="1..168")
    parser.add_argument("--deadline-days", type=int, default=7, choices=range(1, 91), metavar="1..90")
    args = parser.parse_args(argv)
    if not args.db.is_file():
        parser.exit(1, "Workspace database unavailable\n")
    try:
        report = check(args.db.absolute(), stale_after=timedelta(hours=args.stale_hours),
                       deadline_window=timedelta(days=args.deadline_days),
                       outbox=args.outbox.absolute() if args.outbox else None,
                       config_files=[p.absolute() for p in args.config])
    except (sqlite3.Error, OSError) as exc:
        parser.exit(1, f"Workspace health check unavailable ({type(exc).__name__})\n")
    print(render(report))
    return 2 if report["status"] == "ATTENTION" else 0


if __name__ == "__main__":
    sys.exit(main())
