# ADR 93 — one Ramp case identity from financial record to reconciliation

Status: implemented on branch `work/ramp-case-lineage` for integration review. November 9, 2026, America/Los_Angeles. This record makes no native write and approves no pending team decision.

[Decision packet](packets/93-ramp-case-lineage.md) · [Actual Opus 5.5 critique](reviews/93-ramp-case-lineage.json), session `ac3c67f8-8f6a-453d-be5c-dad919bd1189`, model `claude-opus-5-5`, tool-free · [Workstream record](../RAMP-CASE-LINEAGE.md)

## Choice

Add a read-side lineage that keeps one case's identity across the stages:

`Ramp record → applicability → finding → surface → award → credit → application`

It stops at the first disagreement and keeps the money stages separate. The applied amount comes only from credit-to-bill applications that both sides report. Applicability uses reviewed native IDs only, and missing evidence stays `UNKNOWN`. Native credit creation and application stay with a person in Ramp's UI. Uptime only prepares the instruction and classifies the read-back.

## Alternatives

- **Extend `RampCreditSync`/`AllocationLedger`.** Rejected for now. The ledger accepts only simulated awards and D09 is pending. Changing shared settlement tables is a larger reviewed change.
- **Match a credit to an award by `reference_number` or equal amount.** Rejected. The records sync doesn't retain reference text, and equal amounts aren't identity. An explicit reviewed `CreditBinding` is required.
- **Treat a decrease as an automatic reversal.** Rejected. Both silently lowering the amount and keeping the higher one would misstate attributable money, so a decrease needs review.
- **Accept a configured-approval payload as proof.** Rejected. No configured integration or read-back exists here.

## Criticism and disposition

Opus judged the separation and refusal design sound. It found one structural gap and six defects. All were confirmed in the code and fixed, each with a falsification test:

| Critique | Disposition |
|---|---|
| One credit could be counted by two cases, or one award split across credits | Fixed. `build_lineage` needs the tenant's complete `binding_registry`. An unregistered binding is refused. A credit bound twice or an award split across credits gives `REVIEW_REQUIRED` with applied set to null. |
| A human note was verified even if no later read showed it | Fixed. If a later complete read of that bill's comment thread lacks the note, the lineage needs review. The receipt's original two-pass read-back stays the verification of record. |
| Reciprocity was checked one way only | Fixed. A bill that lists the credit without a matching credit entry makes applied `UNKNOWN`. |
| A released hold still counted | Fixed. A hold counts only while the latest read after the request shows `ON_HOLD`. A pre-existing hold isn't attributed. `placed_by_proven` is always false. |
| `prepare` trusted the lineage dict and reused an old association | Fixed. It recomputes `lineage_digest` and requires an association computed for the current capture. |
| Rows without a `kind` were handled inconsistently | Fixed. One mapping is used everywhere, and a row without a known kind is never the case record. |
| Concurrent use of the credit was misreported | Fixed. The pair amount decides confirmation, and concurrent use elsewhere is reported as `CONFIRMED_CREDIT_ALSO_USED_ELSEWHERE`. |

Points where we disagree, or which are deferred:

- **Blocking `prepare`.** Opus recommended blocking `prepare_operator_application` until D09 and an attribution store exist. Instead, the function stays tested but isn't exposed through any route or CLI. It already refuses unless the award is `VERIFIED_VENDOR_AWARD`, and nothing in the product can issue that today. Exposing it is the gated step, and it needs D09.
- **Separating preparer and executor.** Opus recommended requiring the person who applies the credit to differ from the preparer. `confirm` records `executed_by` and `separation_of_duties`, but doesn't enforce it. Whether one person may hold both roles is D06. This mirrors decision 88's explicit statement that the same person can hold two roles.
- **Unsupported claims in the packet.** These are answered in the workstream record and evidence:
  - Field names: the records sanitizer maps `applied_vendor_credits`, `applied_draft_bills` and `total_applied_amount` to `applied_credits`, `applied_drafts` and `total_applied`; see `RAMP-RECORDS.md`.
  - `Bill.status` is the published `OPEN|PAID` enum.
  - The default credit list excludes archived credits. Our sync requests `include_fully_used=true`.
  - The help-article hash is recorded in the platform-verification receipt. The page itself isn't committed.
- **D03 alignment.** The overview session relayed Ronok's November 9 decision: bounded exact source IDs, with no slugging, trimming, case-folding or alias registry. The first commit also refused non-NFC text, which `claim_identity` accepts. That extra refusal was removed so both layers accept exactly the same values. Agent1's shared contract remains the swap point.
- **Parallel source of truth.** Accepted as a cost. Merging with `AllocationLedger` is follow-up work after D09.

## Validation

`tests/test_ramp_case_lineage.py` is a new file of 58 controlled cases. It covers association, identity breaks, partial and full application, drafts, reciprocity, reversal, absence, duplicates, truncation, double attribution, notes, holds, the outbox, preparation gates, read-back outcomes and the preserved receipt. Snapshots come from an injected read-only fake provider through the real `sync_records` sanitizer and validator. These tests are not live execution.

Focused Ramp, allocation, reconciliation and credit suites: 1,064 passed with 1 warning, before the final critique fixes. The full-suite result and tested commit are recorded in [TEST-CHANGES-93](../TEST-CHANGES-93.md).

The single real case is demo bill `f74ba12c`, built from a read-only capture on November 9: evidence-gap finding → verified human note → no award or credit. All case money is null.

## Rollback

Revert the decision 93 commits. No existing module, table, test or receipt changed. Keep the private runtime receipts for audit.
