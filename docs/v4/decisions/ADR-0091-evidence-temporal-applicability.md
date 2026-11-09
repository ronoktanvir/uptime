# ADR 91 — refuse out-of-period evidence at the signed source grant

Status: implemented on `work/evidence-custody-90` at `a924aae`; focused checks pass; integration and the full suite belong to the W0 owner. November 9, 2026, America/Los_Angeles. Workstream W5, evidence and source custody.

[Decision packet](packets/91-evidence-temporal-applicability.md) · [Actual Opus 5.5 critique](reviews/91-evidence-temporal-applicability.json), session `9a4d8b82-a28d-4b00-9a08-bb01ff014921` · [Findings receipt](../evidence/evidence-custody-90/findings-91.json) · [Support matrix](../EVIDENCE-SUPPORT-MATRIX-91.md) · [Test ledger](../TEST-CHANGES-evidence-custody-90.md)

## Problem

A source grant names one exact claim scope, including a `YYYY-MM` service month. Before this change the grant compared envelope identity, role and nested identity strings, but never a record's measured timestamps. The intake desk keeps one immutable record per kind. The [findings receipt](../evidence/evidence-custody-90/findings-91.json) reproduces the consequence: a September status record delivered for an October claim is stored, and once the correct October status, impact and invoice arrive the claim reports `Contradictory independent records require review` with no recovery path. A wrong-period record is neither rejected nor quarantined.

## Choice

`uptime/evidence_applicability.py` adds one pure rule, called from `source_config.event_in_scope` (the signed grant) and by `scripts/deliver_evidence.py` before signing:

1. Short measured records (status, impact, component, notice window, nested resource, telemetry, exclusion and maintenance rows) must overlap the UTC month widened by 14 hours each side. A month measured in a named civil zone is not refused at intake.
2. A period report (coverage, resource status/attribution, provider/customer telemetry) that crosses the UTC month boundary must keep more than 14 hours inside it. An adjacent month in any civil zone overlaps the UTC month by at most 14 hours; every genuine zone-measured month overlaps it by days. A report wholly inside the UTC month is admitted however short.
3. Nested rows must also overlap their own report interval; request witnesses must fall in the widened month.
4. A report marked `complete` cannot be observed before its own interval ends.

Issue, announcement, filing, delivery and billing-cycle timestamps are not checked. Partial overlap is admitted; boundary clipping remains the evaluator's contract rule. Refusal is the existing HTTP 403 before storage. The server returns no reason; the client names the operator's own record locally. No `Scope` field, identity validation, stored hash or idempotency key changes, so D03/D04 are untouched.

## Criticism and disagreement

The single Opus critique called the change a sound interim filter and identified one real flaw: the first period rule (any overlap with the unwidened UTC month) admitted a UTC−12 September report, which ends at 12:00 UTC on 1 October. That defect was corrected. Opus proposed requiring more than half the month; that would refuse honestly partial reports that evaluators already classify as insufficient. The adopted threshold refuses only boundary-crossing reports with 14 hours or less inside the month. The first version of that threshold also refused a one-hour mid-month report used by the unchanged existing test `test_grant_validates_every_nested_resource_and_invoice_line`; the rule, not the test, was corrected. Both failed intermediate runs are recorded in the test ledger.

Opus noted that the complete-before-end check compares sender clocks. Both timestamps come from the same signed record, so the check refuses an internally inconsistent completeness claim; a skewed sender can re-observe. This matches the desk's existing rule for resource reports. Retained, with the disagreement recorded.

Opus recommended an append-only refusal log. The refusal happens inside the shared authentication route (`auth.py`, W0). Writing files from an authorization predicate that the client also runs would add an unbounded side effect. This is sent to W0 as a request rather than implemented here.

Accepted residuals, each recorded by a test or finding: a short wrong-month record inside the 14-hour margin is still admitted, and the desk can still be occupied by it; already-stored mistaken records have no supersede path; the margin assumes calendar months in civil zones, which every supported family uses. A non-calendar measurement period requires revisiting this rule.

Opus also advised that the Twilio profile's implicit completeness, which returns `INELIGIBLE` without a complete-month report, is a contract-semantics decision rather than a routine fix, and that the embedded/HMAC bypass needs prompt owner attention. Both are routed to their owners with the probe receipt; neither is changed here.

## Validation and rollback

23 new controls in `tests/test_evidence_applicability_91.py`, including a mounted HTTP delivery that is refused with no stored row and is followed by the correct record without contradiction. Final focused run at `a924aae`: **401 passed, 1 warning in 328.72s** across 17 suites, including every Northwind workflow test; no existing test or expectation changed. The full locked suite runs after W0 integration and is not claimed here.

Rollback: remove the `temporal_refusal` call in `source_config.event_in_scope` and in `deliver_evidence.deliver`. No stored data, signature or hash migrates.
