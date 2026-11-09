"""Read-only inventory of stored account/agreement identities against source-identity/1.

Opens each SQLite file with ``mode=ro`` and never writes. Reports counts and
refusal codes per database, table and field. A refused value is reported only by
its SHA-256 digest, never by its text. Required before D03 implementation by the
decision-94 critique: zero refusals, or an explicit remediation list.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uptime.source_identity import VERSION, refusal  # noqa: E402

IDENTITY_KEYS = {"account", "agreement", "contract", "account_id", "contract_id", "agreement_id", "public_agreement"}
LEGACY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}")


def _walk(value, found, depth=0, parent="$"):
    """Collect identity values with their enclosing key, e.g. ``overlay.agreement``."""
    if depth > 12:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in IDENTITY_KEYS and isinstance(item, str):
                found.append((f"{parent}.{key}", item))
            else:
                _walk(item, found, depth + 1, key if isinstance(item, dict) else parent)
    elif isinstance(value, list):
        for item in value:
            _walk(item, found, depth + 1, parent)


def inventory(path: Path):
    tables = defaultdict(lambda: defaultdict(Counter))
    refused = defaultdict(set)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in names:
            columns = [r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')]
            for row in connection.execute(f'SELECT * FROM "{table}"'):
                found = []
                for column, cell in zip(columns, row):
                    if not isinstance(cell, str):
                        continue
                    if column in IDENTITY_KEYS:
                        found.append((column, cell))
                    elif cell[:1] in "[{":
                        try:
                            _walk(json.loads(cell), found)
                        except ValueError:
                            pass
                for field, value in found:
                    reason = refusal(value)
                    counts = tables[table][field]
                    counts["total"] += 1
                    if reason:
                        counts["refused:" + reason] += 1
                        refused[f"{table}.{field}"].add(sha256(value.encode()).hexdigest())
                        for character in sorted({c for c in value if refusal(c) and c not in " "}):
                            # The Unicode name of each disallowed character, never the value itself.
                            counts["character:" + unicodedata.name(character, f"U+{ord(character):04X}")] += 1
                    elif LEGACY_ID.fullmatch(value):
                        counts["legacy_restricted_id"] += 1
                    else:
                        counts["widened_only"] += 1
    finally:
        connection.close()
    return ({t: {f: dict(c) for f, c in fields.items()} for t, fields in tables.items()},
            {k: sorted(v) for k, v in refused.items()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("databases", nargs="+", type=Path)
    parser.add_argument("--root", type=Path, required=True, help="report paths relative to this directory")
    args = parser.parse_args()
    report = {"rule": VERSION, "fields": sorted(IDENTITY_KEYS), "values_printed": False, "databases": {}}
    for path in args.databases:
        counts, refused = inventory(path)
        report["databases"][str(path.resolve().relative_to(args.root.resolve()))] = {
            "tables": counts, "refused_value_sha256": refused}
    report["total_refused"] = sum(n for db in report["databases"].values() for fields in db["tables"].values()
                                  for counts in fields.values() for k, n in counts.items() if k.startswith("refused:"))
    print(json.dumps(report, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
