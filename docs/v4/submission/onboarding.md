# Role 1: contract intelligence (onboarding) handoff

Owner: `agent2` (W3). Branch `work/submission-onboarding-20261109`, from `origin/main` `55ea607`. Started 13:20 PST, November 9, 2026. This is a dated record and is updated as work lands.

## 1. Judge findings in this area, reproduced on current source

| Finding | Reproduction on `55ea607` | Status |
|---|---|---|
| The guide answers "renewal date and notice period" with `Clause 1: "Service Level Agreement"` | `tests/test_guide_unmodeled_terms_sub.py`: **10 failed** before the fix. Cause in the workspace guide (`finance_guide.answer`, `/api/workspace/guide`): "contract" or "terms" matched the generic `agreement` topic, so clause quotations, including the bare heading, became the answer. The case-inspector guide (`intelligence.explain`, `/api/guide`) had the same weakness through its proof intent. | **Fixed** in `72b65f6`. Both guides abstain on renewal, notice, termination and contract-term questions that no grounded fact states, and a bare heading is never a fact. 80 passed with the existing guide and browser suites; no existing test changed. |
| "No model runs anywhere in the demo"; Generate is disabled | The model path exists through ordinary routes (`POST /api/vendors/{id}/proposal-access`, then `/proposal-jobs` with `profile: "auto"`; tool-free `SafePublicClaude` transport; exact-request approvals). The Northwind setup serves without `--public-proposal-config`, so the provider is unconfigured and Generate stays disabled. | To demonstrate on a separate throwaway server (ports 8811–8819) with a protected config, real calls and kept receipts. Plan in §2. |
| `20000000/1000000% credit` | The text is the evaluator's trace message (`uptime/vendor_eval.py:141,145`), which is pinned evaluator source. | **A structured field already exists.** Monthly results that earn a credit carry `rate_units`: an integer at 1,000,000 units per percent, so `rate_units / 1_000_000` is the percent (20000000 → 20%). Tier data uses the same scale (`below_units`, `credit_units`). Results without a credit have no `rate_units`; render "no credit". For gent7. |
| Model failures | A provider exit failure or identity-verification failure inside a job is labelled `proposal_validation_failed`, the same as a genuine validation refusal. Timeouts are already `UNCERTAIN`/`provider_timeout`. | **Planned fix:** distinct codes `provider_failed` and `provider_identity_unverified`, so an error is never presented as a refusal of the contract. W4 shares the job service; agent3 is told before merge. |
| Model job fields the interface needs | The vendor job projection has no timestamps and no provider receipt. | **Planned:** add them read-only (§3) without editing `vendor_model_jobs.py`, whose bytes pin every job context. |

## 2. Plan

1. **Pre-check (no model call).** Each authored contract is checked against the deterministic validators with a hand-written ideal reading before any model call:
   - the strict offline parser must **not** accept it, otherwise Uptime correctly selects it with no model call;
   - the guarded monthly propositions grammar must accept a correct reading.

   So a genuine call has a fair chance and the demo really is model-assisted.
2. **Genuine calls.**
   - Setting: a throwaway local server on port 8811 with a protected public-proposal config, `claude-opus-5-5`, and the ordinary routes with `profile: "auto"`.
   - Approval: operator approval of each exact request through `scripts/public_proposals.py export-vendor --profile auto`. `approved_by` records this agent; it is not a human review.
   - Call budget: one call per supported family per contract, which is how automatic selection works: 2 calls per contract, 3 contracts, 6 calls in all. There is no retry until a pass; failures and timeouts are kept with their receipts.
3. **Evidence.** For each contract: source, digest, job ids, provider receipts (model, session, cost, usage), timestamps, exact quoted clauses, proposed terms, validation and selection outcome, and SHADOW state. Kept under `docs/v4/evidence/submission-onboarding-20261109/`. No credentials and no sealed inputs.
4. **Recovery.** Provider failure and timeout get distinct codes; recovery is the existing new-attempt control (a new attempt identifier with its own approval). There is never a canned success.
5. **Separation.** Staging creates SHADOW only. Interpretation acceptance, independent tests, approval and activation stay separate. No activation or human approval is performed or simulated.
6. **Runbook** at `docs/v4/submission/onboarding-runbook.md`.

### Authored contracts

All are explicitly authored public-style text, not derived from any corpus or sealed input, with vendor names chosen for this purpose. A and B use different wording within the published monthly family. C is the refusal control.

- **A, "Halden Relay Service Level Agreement":** prose SLA. Parties are named by sentences rather than labels, with a product/plan scope sentence, a prose measurement sentence, a two-column availability table, a filing sentence and a future-invoice remedy. Expected: monthly selected, SHADOW.
- **B, "Corvid Ledger Availability Commitment":** different wording. Labeled party clauses phrased as sentences, a scope stated before the tiers, tiers in prose rows, and different filing and remedy phrasing. Expected: monthly selected, SHADOW, the same workflow, and no vendor-name code.
- **C, control:** a variant containing a maintenance exclusion and contradictory filing windows. Expected: refused with the cited passage, and no adapter.

The exact texts are fixed in `fixtures/submission_onboarding/` before any call.

## 3. Model job fields for the interface (role 4)

Vendor proposal job, from `GET /api/vendors/{id}/proposal-jobs/{job_id}` and each `families[].job` in the selection view:

| Field | Meaning |
|---|---|
| `job_id`, `vendor_id` | Identity |
| `kind` | Always `vendor` for this route |
| `status` | `QUEUED`, `RUNNING`, `SUCCEEDED`, `REFUSED`, `CANCELLED` or `UNCERTAIN` |
| `reason` | Fixed code when not succeeded: `proposal_validation_failed`, `provider_failed` (planned), `provider_identity_unverified` (planned), `provider_timeout` (`UNCERTAIN`), `provider_outcome_unknown`, `approval_unavailable_before_dispatch`, `restart_before_dispatch`, `restart_after_dispatch` |
| `submitted_at`, `started_at`, `finished_at` | ISO UTC (planned in the projection) |
| `provider` (planned) | `model` (verified actually used), `session`, `client_reported_cost_usd`, `usage` (token counts), `returncode`, `tool_events` (0), `tool_inventory` ([]), `mcp_inventory` ([]), `transport` (profile name and revision), `output_sha256`, `result_sha256` |
| `request_sha256`, `context_sha256` | Pins |
| `proposal` (when `SUCCEEDED`) | `profile`, `attempt_nonce`, `source_sha256`, `proposal_sha256`, `model`, `session`, `document` {name, uri, classification}, `clauses` [{`quote` (exact source slice), `field`, `value` (proposed term)}] |
| `candidate_available`, `refusal` | Whether a SHADOW candidate can be staged; fixed refusal code otherwise |
| `public_diagnostic` (when `REFUSED`) | Validator finding: issues [{code, explanation, block, start, end, block_sha256, quote}], missing_terms |

The selection view (`profile: "auto"`, from `proposal-access`) provides `outcome`, `selected`, the per-family `state` and `refusal`, `review_requirements` (verbatim) and `selection_sha256`. After staging, the adapter's lifecycle state comes from `GET /api/vendors/{id}` (`state`: `SHADOW`, `APPROVED`, `ACTIVE` or `REVOKED`). The review section comes from `GET /api/vendors/{id}/requirements`, already rendered by W7.

Render all text as text. Show quotes untrimmed. Never show a refused or uncertain job as a candidate.
