# Test changes — finance next steps and grounded guide (W7, `work/finance-guide-90`)

**No existing test function, assertion, fixture or expected outcome changed.** The following existing tests run unchanged against the new code:

- `tests/test_northwind_workflow.py`
- `tests/test_workspace_ui_v4.py`
- `tests/test_ramp_ui_v4.py`
- `tests/test_intelligence.py`
- `tests/test_advanced_companion.py`
- `tests/test_vendor_auth83.py`
- the other existing files in the focused list below
- all existing `web/*.test.cjs` and `tests/helpers/*.test.cjs` checks

Decision: [ADR 95](decisions/ADR-0095-grounded-finance-guide.md).

## New tests

| File | Count | Purpose |
| --- | ---: | --- |
| `tests/test_finance_view_90.py` | 21 | Attention items across a real 12-state authored run. Ineligible February is never "missing evidence". Projection additions copy domain values. Every summary amount is copied from the projection. Also covers constructed conflicts, missing agreement, closed filing windows, unparseable amounts and server-supplied Ramp records only. |
| `tests/test_finance_guide_90.py` | 45 | Cited answers whose numbers all appear in the case. Unknown amounts stay unknown. Abstention on outside-case and judgment questions. Read-only answers to action requests. Injected questions and source text. No row change in either database. Determinism and route boundaries. The authored paraphrase corpus (tuning and holdout). Stages never summed. Same-amount disambiguation. Exact deadline instants. Unsigned and signed sessions give identical answers with full database dumps unchanged. A named viewer cannot be enrolled in the authored workspace. A viewer projection gets the same answers except for the server-offered step. |
| `tests/test_finance_browser_90.py` | 2 | Live uvicorn and real Chrome. Real sign-in with the workspace's scripted credential, signed actions, server-side session expiry during an action and during a guide question, keyboard focus movement, 390 px layout, load and guide failures, and the empty state. Product text excludes demo, fixture and "Post to Ramp" wording. |
| `tests/data/finance_guide_paraphrases_95.json` | data | Authored paraphrases: 40 tuning cases and 20 holdout cases. |
| `web/finance_view.test.cjs` | 5 | DOM rendering of attention items, destination, inputs and price lines. The guide posts only the question. Abstention and failure messages. A 401 returns to sign-in once. The older layout is used when no summary is present. |
| `web/vendor_history.test.cjs` | 2 | The review history separates scripted preparation from account actions, and the final state is stated plainly (rolled back with nothing active, active version, or other). |
| `tests/helpers/refusal_diagnostic.test.cjs` | 2 | W3 request (commit `5312938`): a refused vendor proposal job shows the server's verified diagnostic — fixed explanations, the exact passage with offsets and SHA-256, missing terms — as inert text. A missing or foreign-schema diagnostic, or a non-refused job, renders nothing extra. |

## New tests corrected during development, before commit

1. **`test_guide_route_boundaries`.** The "missing action header" probe reused headers that already carried `X-Uptime-Action`, so it returned 200. It now strips the header, and a foreign-origin probe was added. Both return 403.
2. **`test_stage_amounts_are_never_summed_and_never_increase_downstream`.** It first used `ledger.estimated`, which is null in states 2–7 (an unknown estimate stays unknown). It now uses January's evaluated amount.
3. **`web/finance_view.test.cjs`.** It expected "scripted reviewer"; the existing UI label is "Scripted reviewer".
4. **`web/vendor_history.test.cjs`.** The stub returned the vendor list for the detail route. It now answers by path, as the real client requests.
5. **Viewer test replaced.** The first draft enrolled a named viewer in the authored workspace. Authority binding refuses that by design. It was replaced by three tests: unsigned vs signed requests over HTTP, an explicit enrollment-refusal check, and viewer-projection equivalence.
6. **`test_injected_source_text_is_quoted_as_data_and_grants_nothing`.** The expected response keys gained `scope_note` when the answer footer was added after the Opus critique.

## Defects found by the new tests

| Defect | Found by | Fix |
| --- | --- | --- |
| A shortened adapter version hash produced a number absent from the case (2 failed, 39 passed) | Number-grounding assertions | Exact version is now the citation reference (`221a909`) |
| The new price-lines table widened its grid column, so the page scrolled sideways at 390 px | Browser test | `.section-grid>*{min-width:0}` (UI commit) |
| Ranking: tuning corpus first run 35/40 (four wrong first facts and a poem request treated as an action). Causes: generic `where` in status, missing-evidence months not primary for evidence, claim status vs stage ranking, and `write` as an action verb. | Authored corpus | Fixed; 40/40 on tuning. Holdout written afterwards and run once: 19/20, zero wrong facts, one safe abstention ("Are there open items?"). |

## Results

| Run | Source | Result |
| --- | --- | --- |
| Focused regression before the critique changes | Working tree on `03b372e` | **338 passed, 1 warning in 587.64s** |
| Same group after rebase | `8cf8f0c` | **349 passed, 1 warning in 276.90s** ([verification](evidence/finance-guide-90/verification.json)) |
| JavaScript checks | Tree equal to `5312938` | **84/84 pass** (75 existing + 9 new) |
| Full `uv run --locked pytest` | `fde492c` (integration round 3, fresh clone) | **4523 passed, 1 warning in 523.01s (0:08:43)** — run by the integration owner; see the full-suite record below |

The focused list covers:

- the new tests
- `test_advanced_companion`
- `test_intelligence`
- `test_journey_api`
- `test_journey_browser`
- `test_local_review_exception`
- `test_local_review_exception_disputes`
- `test_northwind_financial`
- `test_northwind_inputs`
- `test_northwind_local_ledger`
- `test_northwind_workflow`
- `test_ramp_workspace_installation`
- `test_v4_audit_browser`
- `test_v4_authority_browser`
- `test_vendor_auth83`
- `test_vendor_model_jobs_browser`
- `test_workspace_tenant_v4`
- `test_workspace_ui_v4`
- `test_ramp_ui_v4`

## Preserved flake

`tests/test_workspace_ui_v4.py::test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable` failed once:

- **Failing run:** 1 failed, 75 passed, 1 warning in 263.91s, under heavy machine load.
- **Rerun alone:** 3 passed in 8.11s.
- **Same group rerun:** 76 passed, 1 warning in 93.80s.

The traceback was not captured; that omission is recorded. The test is unchanged. [Receipt](evidence/finance-guide-90/flake-workspace-ui-v4.json).

## Follow-up after the first merge (`0f39570`)

A post-merge spot check found safe but unhelpful abstentions. "Was the claim filed?" and "Why was the claim denied?" had no claim-history fact to answer from. "Record of approvals?" was read as an action. "What does Clause 8 say?" did not lead with that clause.

The follow-up commit makes four changes:

- adds a claim-history fact that quotes the recorded workflow events verbatim with their timestamps;
- adds a claim topic (`filing` is deliberately excluded, so deadline questions keep their deadline-only answer);
- matches a named clause;
- removes `record` from the action verbs.

It adds four guide tests (three parametrized history questions and one clause/noun check). No merged test changed. The first attempt included `filing` in the topic, and the merged `test_initial_state_reports_the_open_deadline_and_the_next_step` failed. The topic was narrowed instead of changing that test.

Results after the follow-up:

- finance view, guide and browser tests: **68 passed, 1 warning in 18.95s**
- tuning corpus: still 40/40
- holdout, re-run after this change: still 19/20 with the same safe abstention

The holdout no longer predates every retrieval change. The change was motivated by the spot check, not by holdout results.

## Legacy case-inspector guide abstention (D12)

The new file `tests/test_intelligence_abstain_95.py` has 11 cases:

- **6 unsupported questions.** Each abstains and keeps its `basis` intent label, including the existing tests' "Show the profile", "Show my billing profile." and the 1,000-character limit question.
- **5 supported questions.** Each still answers from the case with its original intent. One is the existing injection question.

No existing test changed. These existing tests run unchanged alongside the new file:

- `tests/test_intelligence.py`
- `tests/test_portfolio_v4.py` (pins "Show the profile" → `basis`)
- `tests/test_journey_api.py`
- `tests/test_v4_audit_workflow.py`
- `tests/test_v4_audit_protocol.py`

Result: **94 passed, 1 warning in 87.66s**.

## Dispute interaction and Ramp record wording (W4 request and demo copy)

No existing test changed. New tests:

| File | Count | Purpose |
| --- | ---: | --- |
| `tests/helpers/denial_acceptance.test.cjs` | 6 | Covers the following: <ul><li>"Accept denial" posts only `{basis_digest}` to `/denial-acceptance`, never `/actions/accept-denial`.</li><li>A stale-basis 409 accepts nothing and reloads the new offer.</li><li>A malformed offer or a read-only session cannot post.</li><li>The read-only dispute record uses plain labels and keeps vendor text inert.</li><li>A blocking contradicting delivery is explained, and nothing is inferred from the stage.</li><li>89b checks are worded by meaning; `contradicting_deliveries_unresolved: true` is never "pass".</li></ul> |
| `tests/test_interpretation_denial_label_95.py` | 1 | Real Chrome. A DENIAL_REVIEW preview names the ground-recording step and shows plain classifications. The step posts to `/prepare-response` only. |
| `web/ramp_wording.test.cjs` | 2 | Ramp record codes read as meaning-preserving wording, while other codes stay exact. Native routes lead each row and record page. Unverified URLs offer none. |

Results:

- JavaScript: **92/92**
- Correspondence, disposition and interpretation suites, including W4's unchanged `test_correspondence_disposition_89.py`: **69 passed**
- Companion and correspondence browser suites after the 89b follow-up: **25 passed**
- Ramp, workspace and finance browser tests: **6 passed**

## D05 automatic selection follow-up (branch `work/refusal-diagnostic-auto-89`, on agent2's `f1a37a1`)

**Changed test (my own, from `5312938`): `tests/helpers/refusal_diagnostic.test.cjs`.** Its two tests are replaced:

| Old test | New test |
| --- | --- |
| "a refused job shows fixed explanations, the exact passage and missing terms as text" | "a refused family shows its verified diagnostic; a family without one shows the summary" |
| "no diagnostic, a wrong schema or a non-refused job shows nothing extra" | "a foreign or malformed diagnostic falls back to the summary; no refusal shows nothing extra" |

Reason: decision 97 (D05) removes the "Extraction profile" select. A refused job is no longer opened in its own job view; each family's refusal appears in the selection view. On `f1a37a1` the old tests failed with `TypeError: Cannot set properties of undefined (setting 'value')`: 0 passed, 2 failed.

The assertions are not weakened. They still pin all of the following:

- fixed server explanations
- exact block, offsets and SHA-256
- missing terms
- the source document
- inert markup in quoted passages
- no staging control
- no post other than the read-only selection request

They now also check two new points:

- the verified diagnostic replaces the summary rather than repeating it;
- a rejected diagnostic contributes no verified detail.

UI change, one line in `web/v4_ui.js`: each family row prefers `refusalDiagnostic(f.public_diagnostic, 'Why this family was refused')` and falls back to agent2's `familyRefusal(f.refusal)` summary. The heading is kept so agent2's browser assertions are unchanged.

Results on this branch:

- JavaScript: 94/94
- `test_vendor_model_jobs_browser`, `test_vendor_auth83`, `test_vendor_family_selection_89`, `test_advanced_companion`, finance, workspace and Ramp UI browser tests, and `test_v4_authority_browser`: **43 passed, 1 warning in 36.81s**
- the same set on `f1a37a1` alone: 43 passed; JavaScript there was 92/94, the two failures being the old file above
- Use-screen sweep at 390 px: no sideways scroll, no demo wording, no page errors

## Full-suite record

| Run | Tested commit | Result | Covers |
| --- | --- | --- | --- |
| Integration round 3 (integration owner, fresh clone) | `fde492c` | **4523 passed, 1 warning in 523.01s (0:08:43)** | Every W7 commit through `3f13db8`, including `679133c`, `0b6523e`, `a47fb5a`, `d3ac7d7` and `e7d9726` |
| Integration round 5 | Pending | Result line to be recorded when the integration owner reports it | The D05 follow-up `0848d59`, merged as `1eac5ed`, which is not in `fde492c` |

Receipts on `work/integration-90`:

- `docs/v4/evidence/integration-90/full-suite-fde492c.log`
- `docs/v4/evidence/integration-90/verification-fde492c.json`

I did not run a separate full suite on this branch. The integration owner coordinates full runs one at a time on the shared disk. My queued run was cancelled before it started, and no temporary data was created.

