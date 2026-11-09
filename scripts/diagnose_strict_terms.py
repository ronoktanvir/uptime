#!/usr/bin/env python3
"""Classify every clause of a public source for the strict deterministic monthly parser, offline.

Reads a document JSON (name, uri, classification, text) and prints clause numbers, offsets, SHA-256 values and
fixed categories: no source text, no model call, no database or network access. Use it to learn every clause the
deterministic `/candidates` route cannot read, then describe each one's phrasing class without quoting it.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.vendor_strict_diagnostics import classify  # noqa: E402
from uptime.vendor_terms import Document  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    args = parser.parse_args(argv)
    try:
        document = Document.model_validate(json.loads(args.document.read_text(encoding='utf-8')))
        report = classify(document)
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, f'No report: {type(error).__name__}. Check the document JSON and its classification.\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
