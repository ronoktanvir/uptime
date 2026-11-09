"""Read-only demo-machine readiness check. Exit 0 READY, 2 ATTENTION, 1 when the check itself failed."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.operations_preflight import check


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, action="append", default=[], required=True,
                        help="Workspace database used in the demo (repeatable)")
    parser.add_argument("--port", type=int, action="append", default=[],
                        help="Local demo port that must listen on loopback only (repeatable)")
    parser.add_argument("--backup-dir", type=Path, help="Folder holding backups made with workspace_recovery.py")
    parser.add_argument("--config", type=Path, action="append", default=[],
                        help="Protected configuration or credential file to check for custody only (repeatable)")
    args = parser.parse_args(argv)
    try:
        report = check([p.absolute() for p in args.workspace], ports=args.port,
                       backup_dir=args.backup_dir.absolute() if args.backup_dir else None,
                       config_files=[p.absolute() for p in args.config])
    except OSError as exc:
        parser.exit(1, f"Preflight unavailable ({type(exc).__name__})\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if report["status"] == "ATTENTION" else 0


if __name__ == "__main__":
    sys.exit(main())
