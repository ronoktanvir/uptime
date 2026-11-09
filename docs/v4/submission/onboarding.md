# Role 1: contract intelligence (onboarding) handoff

Owner: `agent2` (W3). Branch `work/submission-onboarding-20261109`, from `origin/main` `55ea607`. Started 13:20 PST, November 9, 2026. This is a dated record and is updated as work lands.

## 1. Judge findings in this area, reproduced on current source

| Finding | Reproduction on `55ea607` | Status |
|---|---|---|
| The guide answers "renewal date and notice period" with `Clause 1: "Service Level Agreement"` | `tests/test_guide_unmodeled_terms_sub.py`: **10 failed** before the fix. Cause in the workspace guide (`finance_guide.answer`, `/api/workspace/guide`): "contract" or "terms" matched the generic `agreement` topic, so clause quotations, including the bare heading, became the answer. The case-inspector guide (`intelligence.explain`, `/api/guide`) had the same weakness through its proof intent. | **Fixed** in `72b65f6`. Both guides abstain on renewal, notice, termination and contract-term questions that no grounded fact states, and a bare heading is never a fact. 80 passed with the existing guide and browser suites; no existing test changed. |
| "No model runs anywhere in the demo"; Generate is disabled | The model path exists through ordinary routes (`POST /api/vendors/{id}/proposal-access`, then `/proposal-jobs` with `profile: "auto"`; tool-free `SafePublicClaude` transport; exact-request approvals). The Northwind setup serves without `--public-proposal-config`, so the provider is unconfigured and Generate stays disabled. | **Demonstrated** on a throwaway server (8811): six genuine `claude-opus-5-5` calls; the authored Corvid Ledger contract reached **SHADOW**. See §4 and the [runbook](onboarding-runbook.md). Enabling it inside the Northwind workspace is agent3's setup (`scripts/setup_northwind.py --public-proposal-config`). |
| `20000000/1000000% credit` | The text is the evaluator's trace message (`uptime/vendor_eval.py:141,145`), which is pinned evaluator source. | **A structured field already exists.** Monthly results that earn a credit carry `rate_units`: an integer at 1,000,000 units per percent, so `rate_units / 1_000_000` is the percent (20000000 → 20%). Tier data uses the same scale (`below_units`, `credit_units`). Results without a credit have no `rate_units`; render "no credit". For gent7. |
| Model failures | A provider exit failure or identity-verification failure inside a job is labelled `proposal_validation_failed`, the same as a genuine validation refusal. Timeouts are already `UNCERTAIN`/`provider_timeout`. | **Fixed** in `611efdf`: `provider_failed` and `provider_identity_unverified`. Recovery is a new attempt identifier. agent3 told. |
| Refusals without a passage | The cohort and the first authored run showed `PUBLIC_PROPOSITION_UNESTABLISHED` with no cited passage for identifier-grounding and duplicate-term refusals. | **Fixed** in `c4b64dd`: the passage is located by replaying growing prefixes of the same reading (`UNGROUNDED_PARTY_IDENTIFIER`, `CONFLICTING_SOURCE_TERMS`). |
| Guide: "How much money has Uptime saved us in total?" returns month records | Reproduced (2 failing tests) | **Fixed** in `57dc7e3`: a fixed lead plus the server's stage values with the "not amounts to add" caveat, the open price finding ("not an awarded credit") and the Local-ledger destination. No sum. |
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
| `reason` | Fixed code when not succeeded: `proposal_validation_failed`, `provider_failed`, `provider_identity_unverified`, `provider_timeout` (`UNCERTAIN`), `provider_outcome_unknown`, `approval_unavailable_before_dispatch`, `restart_before_dispatch`, `restart_after_dispatch` |
| `submitted_at`, `started_at`, `finished_at` | ISO UTC (in the projection since `611efdf`) |
| `provider` (since `611efdf`) | `model` (verified actually used), `session`, `client_reported_cost_usd`, `usage` (token counts), `returncode`, `tool_events` (0), `tool_inventory` ([]), `mcp_inventory` ([]), `transport` (profile name and revision), `output_sha256`, `result_sha256` |
| `request_sha256`, `context_sha256` | Pins |
| `proposal` (when `SUCCEEDED`) | `profile`, `attempt_nonce`, `source_sha256`, `proposal_sha256`, `model`, `session`, `document` {name, uri, classification}, `clauses` [{`quote` (exact source slice), `field`, `value` (proposed term)}] |
| `candidate_available`, `refusal` | Whether a SHADOW candidate can be staged; fixed refusal code otherwise |
| `public_diagnostic` (when `REFUSED`) | Validator finding: issues [{code, explanation, block, start, end, block_sha256, quote}], missing_terms |

The selection view (`profile: "auto"`, from `proposal-access`) provides `outcome`, `selected`, the per-family `state` and `refusal`, `review_requirements` (verbatim) and `selection_sha256`. After staging, the adapter's lifecycle state comes from `GET /api/vendors/{id}` (`state`: `SHADOW`, `APPROVED`, `ACTIVE` or `REVOKED`). The review section comes from `GET /api/vendors/{id}/requirements`, already rendered by W7.

Render all text as text. Show quotes untrimmed. Never show a refused or uncertain job as a candidate.

## 4. Genuine model runs (13:15–13:19 PST)

Six calls, one per supported family per authored contract. Model `claude-opus-5-5`, verified from the provider stream; no tools, no MCP servers; about USD 0.41 in all. No call was repeated. Approvals were recorded with the operator CLI before each submission; `approved_by` names this agent, for model invocation only. Contract files were fixed at 21:12:39Z, before every approval and call. Details: [genuine-calls-summary.json](../evidence/submission-onboarding-20261109/genuine-calls-summary.json).

| Contract | Monthly job / session | Resource job / session | Outcome |
|---|---|---|---|
| Halden Relay | `d98bbf92` / `75c9b80a`: refused, vendor name quoted apart from its supply verb | `d7490489` / `dc0005bd`: refused | **NO_SUPPORTED_FAMILY** |
| Corvid Ledger | `26ee4e3f` / `41f4dcb6`: **validated** | `d3f1a3ca` / `b1418b20`: refused, required resource terms absent | **SELECTED** monthly, staged **SHADOW** (version `ff76ed67`); no actions; interpretation review required |
| Control | `708056a1` / `2095764e`: refused, same split-party reason | `4cad579b` / `5f6482d8`: refused; both filing passages and the measurement block cited | **NO_SUPPORTED_FAMILY** |

**Independent cohort, for comparison:** 0/4 intended positives, 6/6 refused, every monthly reading failing identifier grounding first. The authored positives were written inside the validated grammar (no-model pre-check), so their success is a demonstration, not a score. The Halden Relay refusal shows that the cohort's failure class also appears on in-grammar text. The generalization fix belongs to the next workstream and is not in this push; no grounding check was relaxed.

**Code that ran.**
- Halden Relay ran on `611efdf` exactly: the server started at 13:14:00 PST, after that commit, with no uncommitted `uptime/` change.
- Corvid Ledger and the control ran on code byte-identical to `c4b64dd`'s `uptime/` tree. The server restarted at 13:17:17 PST, after the last diagnostics edit at 13:17:07; that file is unchanged in `c4b64dd`. The only later `uptime/` change is `finance_guide.py` in `57dc7e3` (13:21:18), after both runs.

**Recorded workspace custody.** The preserved `workspace.sqlite` must hash `9043eaaf356071a1f45a841daf075a8cb3ee1945c009cd6b8437f95cb3241736`. Serving it directly at 13:31 PST changed it to `41fecca2f491a181331bf1ce2dafe806fad9dc3c64b93eadf16e8d315b63d07f` (two SQLite header bytes, no record), and it was restored at 15:42 PST. Never serve the preserved folder; serve only a scratch copy, as in the [runbook](onboarding-runbook.md#preserved-recorded-workspace-for-the-film).

**Limits:**
- The control's conflicting-terms and exclusion refusals were not reached by its genuine monthly call, because identifier grounding failed first. They are shown by `tests/test_submission_refusal_location.py` and `tests/test_vendor_selection_refusals_89.py`.
- The Halden Relay record keeps the generic explanation it was stored with. Its precise passage is shown by an offline replay with the current code.

