"""Private, offline blind acceptance over real signed loopback HTTP.

No fixture values, model output, response bodies or exception text may be logged.
The only export is an allowlisted receipt. Product imports occur after --source.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time

FREEZE = "9364cd2bf2023adbc1a6f99bc275ac1ae36476ee"


class BoundaryError(Exception):
    """A constant failure code, never private exception text."""


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    return sha256(value).hexdigest()


def instant(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() is None:
        raise BoundaryError("TIMEZONE_MISSING")
    return result.astimezone(UTC)


def local_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise BoundaryError("FIXTURE_PATH_INVALID")
    return path


def read_json(path):
    return json.loads(path.read_bytes(), parse_float=Decimal)


def money(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise BoundaryError("MONEY_ENCODING_INVALID")
    return Decimal(value)


def money_check(expected, observed, *, available):
    """Unknown is not zero; unavailable is not a wrong numeric result."""
    if not available:
        return "UNAVAILABLE"
    if expected is None or observed is None:
        return "PASS" if expected is observed else "UNKNOWN_MISMATCH"
    return "PASS" if money(expected) == money(observed) else "WRONG_MONEY"


def select_records(records, selectors, as_of):
    index = {row["id"]: row for row in records}
    if len(index) != len(records) or len(set(selectors)) != len(selectors):
        raise BoundaryError("DUPLICATE_INPUT_ID")
    if set(selectors) - index.keys():
        raise BoundaryError("MISSING_INPUT_ID")
    ready, unavailable = [], []
    for identifier in selectors:
        row = index[identifier]
        (ready if instant(row["available_at"]) <= instant(as_of) else unavailable).append(row)
    return ready, unavailable


def write_receipt(path, receipt):
    """Create-only, private permissions; never overwrite previous observations."""
    raw = json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    with path.open("xb", opener=lambda name, flags: os.open(name, flags, 0o600)) as handle:
        handle.write(raw)

