# W3 vendor onboarding handoff (agent2, workstream 89)

As of November 9, 2026 (America/Los_Angeles). Every commit below is merged into `work/integration-90`. Verified with `git merge-base --is-ancestor` against `e10d95d`. The integration owner's round 6 full suite on a fresh clone of `3f60647` passed **4664, 1 warning** and includes all of it.

**Blocked only on Ronok:** the human promotion and rollback step of the D05 unseen-vendor proof (see [External proof still missing](#external-proof-still-missing)).

## Commits, files and behavior

| Area | Commits | Files | Behavior |
|---|---|---|---|
| Requirement card and generated drafts (decision 90) | `c8c5553`, `f9153b2`; extended by `8ef6542` (ONB-4) and `7906764` (ONB-3) | `uptime/vendor_requirements.py` (new), `uptime/vendor_api.py`, `tests/test_vendor_requirements_89.py`, `tests/test_vendor_drafts_categories_89.py`, `docs/v4/ONBOARDING-TRACE-89.md`, `docs/v4/decisions/ADR-0090-adapter-requirement-card.md` | Read-only `GET /api/vendors/{id}/requirements`. Six card elements (source clauses, eligible fee, evidence, exclusions, deadline, submission channel), each with cited clause ids or a concrete review requirement. Generated shadow drafts (monthly tiered family) cover tier boundaries, evidence controls, unknown fee, deadline boundary, timezone offsets, private-amendment months and an out-of-interval month. They use a placeholder fee, are labeled `derived` (they cannot be posted as the independent suite), and reuse of draft facts is flagged. Outside the reviewed-semantics hash. W7 renders it as "Review requirements" (`5d8af56`). |
| Refusal diagnostics (decision 90 addendum) | `8ed84e5`, `edf0c05` | `uptime/vendor_refusal_diagnostics.py` (new), `uptime/public_proposal_jobs.py`, `uptime/vendor_api.py`, `tests/test_vendor_refusal_diagnostics_89.py` | A refused vendor proposal job shows the validator's own finding as a fixed code, the exact public passage and the missing terms. Stored data is re-verified against the job's pinned context on read. Model text is never stored or shown. Correspondence jobs never carry one. |
| D05 automatic family selection, phase 1 (decision 97) | `df35398`, `6d31f93` | `uptime/vendor_family_selection.py` (new), `uptime/public_proposal_jobs.py` (read-only `attempts()`), `uptime/vendor_api.py`, `tests/test_vendor_family_selection_89.py` | `profile: "auto"` on the existing draft routes. Offline deterministic selection for canonical monthly sources; otherwise one exact-approved job per family. Outcomes: `SELECTED`, `AMBIGUOUS` (monotone across attempts and reviewers), `NO_SUPPORTED_FAMILY` or `INCOMPLETE`, with per-family reasons. `vendor_model_jobs.py` and every semantics file are byte-identical. |
| D05 phase 2 and browser | `1c6dbc0`, `604880e`, `f1a37a1` | `uptime/vendor_family_selection.py`, `web/v4_ui.js`, `web/v4_style.css`, `tests/test_vendor_model_jobs_browser.py`, `tests/test_vendor_auth83.py`, `tests/helpers/vendor_model_jobs.test.cjs`, `tests/helpers/vendor_auth83.test.cjs`, `tests/helpers/vendor_monthly_profile79.test.cjs` | Only the selected job can stage a candidate (HTTP 409 otherwise). The browser has no profile select, polls with GET only, refreshes explicitly, and offers staging only for `SELECTED`. Reviewed and approved by gent7 (W7 owner). |
| D05 operator support | `d5038b8` | `scripts/public_proposals.py`, `tests/onboarding79/test_public_proposal_export_auto_89.py`, `docs/v4/D05-UNSEEN-VENDOR-RUNBOOK.md`, `docs/v4/PUBLIC-PROPOSAL-RUNTIME.md` | `export-vendor --profile auto` writes one exact, permission-free export per family. Runbook for the unseen-vendor run. |
| F4 and F6 (W5 findings) | `aeb4522`, `3e24d01` (integration merge) | `uptime/vendor_terms.py`, `uptime/vendor_eval.py`, `uptime/vendor_resource_eval.py`, `uptime/vendor_registry.py`, `uptime/vendor_requirements.py`, `tests/test_vendor_filing_override_f4.py`, two fixtures | **F4:** a private filing amendment governs only from its stated calendar month; undated means unsupported. agent0 applied the same helper to the claim route in `v4_routes.py`. **F6:** the dispatched governing citation labels its evidence digest `OPERATOR_SUPPLIED_UNVERIFIED`. Reviewed-semantics change, batched with agent1's D03/F5/D04-C re-review. |
| Evaluation 84 named remediation | `e8f58ff` | `uptime/vendor_terms.py`, `tests/test_vendor_unlabeled_parties_84r.py` | The propositions grammar also grounds a vendor as the exact subject of a supply verb, and an agreement as the whole opening title line. Built from gent8's phrasing-class summaries only. The 0/4 first-attempt score is unchanged. |
| Records and refusal test | `c814c2d`, `2deb6ea`, `75bf846` | `docs/vendor-onboarding.md`, `docs/v4/ONBOARDING-TRACE-89.md`, ADR-0097, `tests/test_vendor_selection_refusals_89.py` | Accepted W5 findings; requirement status; a maintenance exclusion refuses under automatic selection with the exact passage cited. |

Ledgers: [TEST-CHANGES-onboarding-89.md](TEST-CHANGES-onboarding-89.md) and [TEST-CHANGES-onboarding-f4f6-89.md](TEST-CHANGES-onboarding-f4f6-89.md). They name every changed existing test and its reason. No authority or monetary assertion was weakened.

## Tests and actual results

Focused runs used a unique `--basetemp` with `-o tmp_path_retention_policy=failed`, deleted afterwards.

| Change | Result |
|---|---|
| Requirement card (first run) | 3 failed, 6 passed: wrong citation field name, fixed. Then 16 passed. |
| Requirement card, related set | 1451 passed. |
| Refusal diagnostics | First draft 9 passed. Revised after the Opus critique: 12 passed; related set 1527 passed. |
| D05 phase 1 | 22 passed; focused set 1174 passed. |
| D05 phase 2 server (before the browser change) | 3 browser tests failed as expected. |
| D05 phase 2 with browser | JS 24 passed and 33 passed; affected Python 81 passed. Broad set: 1 failed (a test race), 1182 passed. The race was fixed; then 7 passed, twice. |
| F4/F6 | A concurrent run hung in a browser test and was stopped. Alone: 1912 passed; after merging integration, 1969 passed. |
| Evaluation 84 remediation | 12 passed (the positive case fails on the previous grammar). Vendor/onboarding 1066 passed. |
| ONB-4 drafts | 28 passed. |
| ONB-3 card element | 45 passed. |
| Correct-reason refusal | 2 passed. |
| gent7 requirements UI, against the W3 server | 59 passed, then 45 passed. |

## Decision references

**Ronok's own decisions**, relayed from his overview session and recorded by agent0 in [the team decision sheet](TEAM-DECISION-HANDOFF.md#team-decision-sheet):

| Decision | Choice |
|---|---|
| D03 | Bounded exact source IDs, extended to vendor/service names |
| D04 | Typed scope variants |
| D05 | Auto-select plus human approval |
| D06 | Humans gate judgment |
| D07 | Narrow published matrix |
| D10 | Public material only to models |
| D11 | Stay local |
| D14 | No mandatory Opus critique |
| F5 | Require reviewed binding |
| "1a" | Repair the evaluation 84 claim-basis validator causes through normal review; setup only; never rescore |

**Delegated decisions.** The overview session chose these under Ronok's (Recommended) authority before 12:23 PST; they are not his personal choices:
- the unseen vendor is selected by gent8 under a sealed pre-registered rule;
- W3 makes the D05 browser change, with gent7 reviewing.

**Integration and workstream decisions:**
- agent0 (W0): ADR numbers 90 and 97; acceptance of the refusal-diagnostic and `v4_routes` F4 interface requests; ONB-1 deferred until after the demo.
- agent3 (W4): no conflict with the refusal-diagnostic field.

**W3 design decisions, each with one Opus 5.5 critique:**
- decision 90, session `3b18edac-7a5e-47cd-b7db-0e0e8ce3a8f1`;
- decision 90 addendum, session `c6135350-f030-4264-9a00-82e243bd4f4d` (conditional dissent; three points accepted);
- decision 97, session `f57c7f16-ac61-4dce-8232-51d73184e6f3` (five amendments accepted; one disagreement, resolved with validator probe evidence and recorded in ADR-0097).

## Remaining gaps

- **ONB-1, discovery from Ramp records: not met; deferred until after the demo by agent0.** Stored Ramp vendors keep IDs only, so discovery needs a reviewed binding between an adapter slot and a Ramp vendor ID (D03; W1/W0).
- **Exclusions and conditions.** The monthly family refuses any exclusion or qualifier, and most real public SLAs contain one (D07 narrow matrix). Supporting cited exclusions would be a semantic expansion needing a team decision. Do not make it before the D05 run (selector bias).
- **Evaluation 84 causes not addressed:** model-flagged clauses, the deterministic `/candidates` parser on the unknown clauses, the resource-month block 4 flag, and the aggregate fixed-period phrasing. After D04-C, the verification lane expects the 11 `monthly_tier` dispute cases to refuse with "requires incident".
- **Submission channel.** It is visible on the card but never delivered; delivery waits on D08.
- **Re-review.** Every active adapter needs one renewed review after the batched semantics change; fresh setups need none.

## Rollback

| Area | How to roll back |
|---|---|
| Requirement card and drafts | Revert `7906764`, `8ef6542`, `c8c5553`. Read-only route, nothing persisted. Revert W7's `5d8af56` as well. |
| Refusal diagnostics | Revert `8ed84e5`. The nullable `public_diagnostic_json` column stays harmlessly. |
| D05 | Revert `f1a37a1`, `604880e`, `1c6dbc0` (restores the operator profile select and candidate staging), then `df35398`. `vendor_model_jobs.py` was never changed, so job context pins stay valid. Revert `d5038b8` for the export and runbook. |
| F4/F6 and the evaluation 84 remediation | Revert `e8f58ff` and `aeb4522` together with agent0's `v4_routes.py` F4 change, so the claim route and evaluator stay consistent. This changes the semantics hash again, so active adapters need another review. |

## External proof still missing

1. **The D05 unseen-vendor proof** on the ordinary app path, with real public-only inference:
   - gent8 holds the sealed selection, and its driver is ready.
   - **Blocked on a Ronok decision** (recorded in BLOCKERS): in the ordinary app his approve/activate/rollback cannot run for a vendor other than CalyxQuay. Options: (a) authorize a version-scoped exception for the D05 vendor; (b) stop the proof at SHADOW; (c) a full signed release (not feasible today).
   - The most likely honest outcome is a cited refusal, not an adapter.
2. **Corpus84 claim-basis activation preflight** after the merged remediation: the verification lane runs it as setup only and reports it as it is.
3. **Human promotion of an unseen vendor's adapter.** Only CalyxQuay's bounded local review exists.
4. **A real claim-delivery channel (D08).**
