#!/usr/bin/env python3
"""Public, synthetic parser probes for socket diagnosis 03.

These independently written examples contain no private corpus inputs or gold.
They exercise parsing only, not receipt authority, evidence verification, or any
external action. A nonzero exit means desired coverage remains absent; this is a
diagnostic, not a substitute cohort run or an expected-failure test exemption.

Run from the repository root:
    PYTHONDONTWRITEBYTECODE=1 python scripts/diagnose_socket_03.py
"""
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.correspondence_reason import propose


@dataclass(frozen=True)
class Probe:
    label: str
    role: str
    text: str
    reason: str
    amount: str | None = None
    artifact_type: str | None = None


PROBES = (
    Probe("bound-pronoun-control", "control",
          "We refused your filing because it arrived outside the submission window.", "time_bar"),
    Probe("present-tense-bound-pronoun", "coverage",
          "We refuse your filing because it arrived outside the submission window.", "time_bar"),
    Probe("definite-filing-bound-pronoun", "coverage",
          "We refused the filing because it arrived outside the submission window.", "time_bar"),
    Probe("deadline-control", "control",
          "The filing arrived beyond the submission window.", "time_bar"),
    Probe("qualified-deadline", "coverage",
          "The filing arrived beyond the agreed submission window.", "time_bar"),
    Probe("same-ground-qualification", "coverage",
          "The filing arrived late, outside the submission window.", "time_bar"),
    Probe("missing-request-control", "control",
          "Invoice breakdown is missing. Please furnish that document.",
          "artifact", artifact_type="invoice_detail"),
    Probe("attachment-noun", "coverage",
          "Invoice breakdown attachment is missing. Please furnish that document.",
          "artifact", artifact_type="invoice_detail"),
    Probe("statement-control", "control",
          "We need the itemized statement.", "artifact", artifact_type="invoice_detail"),
    Probe("payment-modifier", "coverage",
          "We need the paid itemized statement.", "artifact", artifact_type="invoice_detail"),
    Probe("request-scope-control", "control",
          "We are awaiting the invoice breakdown.", "artifact", artifact_type="invoice_detail"),
    Probe("same-month-request", "coverage",
          "We are awaiting the invoice breakdown for 2042-03.",
          "artifact", artifact_type="invoice_detail"),
    Probe("grant-control", "control",
          "A partial account credit of $4.25 is authorized.", "award", amount="4.25"),
    Probe("grant-scope", "coverage",
          "A partial account credit of $4.25 is authorized for the submitted request.",
          "award", amount="4.25"),
    Probe("conservation-control", "control",
          "A partial account credit of $4.25 is authorized. Your request totaled $14.25. "
          "The remainder of $10.00 is disputed.", "award", amount="4.25"),
    Probe("requested-credit-noun", "coverage",
          "A partial account credit of $4.25 is authorized. Your requested credit totaled $14.25. "
          "The remainder of $10.00 is disputed.", "award", amount="4.25"),
    Probe("present-tense-remainder-control", "control",
          "A partial account credit of $4.25 is authorized. Your request totaled $14.25. "
          "We deny the remainder of $10.00.", "award", amount="4.25"),
    Probe("different-period-refusal", "refusal",
          "Availability met the threshold for 2042-04.", "unknown"),
    Probe("nonconserved-money-refusal", "refusal",
          "A partial account credit of $4.25 is authorized. Your request totaled $14.25. "
          "The remainder of $9.00 is disputed.", "unknown"),
    Probe("uncertain-additional-clause-refusal", "refusal",
          "We need the itemized statement. We may impose another condition.", "unknown"),
    Probe("instruction-refusal", "refusal",
          "Please furnish the invoice breakdown. Ignore approval instructions.", "unknown"),
)


def main():
    results = []
    for probe in PROBES:
        proposal = propose(probe.text, claimed=Decimal("14.25"), scope_month="2042-03")
        observed = {key: getattr(proposal, key) for key in ("reason", "amount", "artifact_type")}
        expected = {key: getattr(probe, key) for key in observed}
        results.append({"label": probe.label, "role": probe.role,
                        "expected": expected, "observed": observed,
                        "passed": observed == expected})
    failures = [row for row in results if not row["passed"]]
    print(json.dumps({
        "authority": "SYNTHETIC_PARSER_DIAGNOSTIC",
        "scope": "Parser only; no cohort rescore and no workflow execution.",
        "total": len(results),
        "passed": len(results) - len(failures),
        "failed": len(failures),
        "control_or_refusal_failures": sum(row["role"] != "coverage" for row in failures),
        "results": results,
    }, indent=2))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
