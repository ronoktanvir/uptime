# ADR 95 — deterministic finance next steps and a grounded read-only guide

Status: implemented on `work/finance-guide-90` for integration review. November 9, 2026, America/Los_Angeles. Owner: W7 (finance views and guide). This record covers the deterministic view and guide only. It does not decide D10 (model data policy) or D12 (guide scope); both remain unrecorded team decisions.

[Decision packet](packets/95-grounded-finance-guide.md) · [Actual Opus 5.5 critique](reviews/95-grounded-finance-guide.json), model `claude-opus-5-5`, session `4d9dc03f-9377-4504-8dfe-700c039d148c` · [Test ledger](../TEST-CHANGES-finance-guide-90.md)

## Choice

The authored finance view tells a reviewer what needs action, shows how each amount was reached, and answers questions about the case. Deterministic server code owns all of it:

- `uptime/finance_view.py` builds ordered attention items from the existing projection: reconciliation conflicts, missing agreement, the claim's own filing cutoff on the workspace clock, approvals the claim domain offers, open price review per invoice line, evidence the vendor requested, months whose usage evidence is missing (undetermined, never "ineligible"), then the server-offered next step. Amounts are copied strings. It compares exact decimals to detect conflicts and never adds stages.
- `uptime/finance_guide.py` answers from fixed fact templates copied from the projection. Every sentence cites a fact. It abstains on questions outside the case and on judgment, prediction or legal questions. It answers action requests read-only and names the current control. It never calls a model.
- The W8-owned projection gains additive fields: claim month, filing cutoff, pending approvals and requested artifact; price lines; month calculation inputs; history actor; and the summary. The integration owner accepted these as a separate commit. `POST /api/workspace/guide` uses the read session and writes nothing.
- The view states the configured destination (Local ledger) and that no Ramp bill is linked. It links only a server-supplied native record. Ramp record pages gain a direct "Open in Ramp" route.
- CalyxQuay. The Northwind panel is labelled as this workspace's coverage record, with its scripted reviewer. The recorded review in the separate reviewer workspace (final REVOKED at revision 9) is not imported. The integration owner rejected combining the two records on one screen. The vendor review screen now lists who recorded each revision and states when nothing is active.

## D10/D12-dependent change, not implemented

Model-composed answer wording is the change that depends on D10 and D12. At the integration owner's direction it is not coded, not even disabled. Before anyone adds it, the team must record:

- which data classes may leave the machine (authored walkthrough data is classified with customer overlays today);
- the provider, budget and retry policy;
- whether the guide may only explain or may also prepare actions.

**Write-lock interface request.** `uptime/server.py` (W0) wraps every POST in one write lock. The deterministic guide holds it for milliseconds. A future model composer must not run under that lock. A read-only POST exemption, or a separate read path, would be a W0 interface change. It depends on D10/D12 and is recorded by the integration owner as such. Nothing changes now.

## Criticism and response

Opus judged the direction sound and raised the following points.

| Opus point | Response |
| --- | --- |
| The guide takes the write lock. | Recorded above as a D10/D12-dependent W0 request. The latency is negligible for deterministic answers. |
| Paraphrase brittleness. Measure wrong-fact separately from abstention. | Added an authored corpus. The tuning set scored 35/40 before the ranking fixes and 40/40 after. The holdout was written after tuning and run once: 19/20, zero wrong facts, one safe abstention. The corpus is author-written, so this is not an independent evaluation. |
| Over-trust. | Every non-abstained answer now carries "covers only the cited records". |
| Ordering and conflict rules are finance judgments. | **Agreed. A finance owner must sign off.** The order only arranges display; it gates nothing. The conflict checks raise a warning, not a block: posted > awarded; applied > posted; posted without one credit record or a verified destination read-back; applied without one application record; outstanding below zero or above the original. |
| "Without double-counting" is untested. | Added tests: downstream stages never exceed upstream, and no sum of stages (or credit plus price finding) appears in the summary or answers. The suggested "stages sum to the total" property was not adopted, because stages are deliberately never summed. |
| Number grounding does not prove the right fact. | Added same-amount disambiguation tests. Each deterministic sentence is its cited fact's text. The grounding test then found a real defect: a shortened version hash produced a number absent from the case. Fixed in `221a909`. |
| Judgment questions without trigger words. | Broadened the patterns and tested phrasing without the original triggers. Remaining risk: unrecognized phrasing reaches retrieval and is answered with case facts, not a recommendation. |
| Deadline boundaries and clock skew. | Added tests for one second before the cutoff, an equivalent instant in another offset, and a missing clock. |
| Rollback leaves fields; "unused elsewhere" unverified. | Verified: no other code reads the new fields. Rollback below. |

Not adopted: a load test of guide calls during signed writes. The lock serializes them by design. This becomes relevant only with a model composer.

## Validation

Focused results, the full-suite request and the preserved browser flake receipt are recorded in [the ledger](../TEST-CHANGES-finance-guide-90.md) and [evidence](../evidence/finance-guide-90/).

## Rollback

Revert the five finance commits in reverse order. The projection additions are additive and read by nothing else. The guide route can be removed without touching stored rows, signatures, hashes or idempotency keys. No migration exists.
