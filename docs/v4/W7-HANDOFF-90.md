# W7 handoff — finance views, evidence inspection, guide and presenter materials

**Owner:** W7 (session `gent7`). **Written:** November 9, 2026, on integration head `e10d95d`. **Status:** all W7 work is merged into `work/integration-90` and covered by a recorded full-suite run. Nothing is blocked on a Ronok decision. Two follow-ups would need decisions (see [Remaining gaps](#remaining-gaps)).

## What a teammate can now do without developer help

- **Read the outcome.** On the Northwind finance view, see the January $2,400 credit by stage (claimed, awarded, posted to Local ledger, applied). See April's $11,000 → $8,600 bill and the separate, still-open March $1,000 price finding. None of these amounts are added together.
- **Inspect the evidence.** Open each month's calculation inputs, read the exact governing clause, see the March invoice lines (billed, contract amount, difference, governing version), and follow the dispute record from the vendor's missing-evidence request to the award.
- **See what needs a person.** "Needs attention" lists, in priority order:
  - credit-record conflicts
  - a missing agreement
  - the filing deadline (open or closed, on the workspace clock)
  - approvals waiting for a reviewer
  - the open price review
  - evidence the vendor asked for
  - months with missing usage (shown as undetermined, never ineligible)
  - the next offered step
- **Ask about the case.** The read-only guide answers from the case's own records and cites each one. It abstains on questions outside the case or that need judgment, and it answers requests to act without acting.

## Commits

All are on `origin/work/integration-90`. The commit-to-merge mapping below was checked against the repository with `git merge-base`.

| Area | Commits | Integrated by merge |
| --- | --- | --- |
| Next steps and grounded guide (backend) | `1b2391e`, `221a909`, `679133c` | `0f39570`, `a3bfefc` |
| Workflow projection fields and read-only guide route (W8-owned file, accepted request) | `00dffde` | `0f39570` |
| Finance view, Ramp destination panel, calculation inputs, price lines, guide UI, vendor review history | `8cf8f0c` | `0f39570` |
| Refusal diagnostic on refused proposal jobs (W3 request) | `5312938` | `0f39570` |
| Case-inspector guide abstains (D12) | `0b6523e` | `cc35de4` |
| Denial acceptance and dispute record (W4 request), 89b contradicting-delivery notice | `a47fb5a`, `e7d9726` | `ec3c9fe` |
| Ramp records wording | `d3ac7d7` | `ec3c9fe` |
| D05 phase 2 review of agent2's UI, plus verified per-family diagnostics | review of `604880e`; `0848d59` | `8f46788`, `1eac5ed` |
| Review requirements card (W3 request) | `310c918`, `e527f8f` | `5d8af56`, `c46d253` |
| One-click guide questions | `9b9092f` | `9a85f98` |
| Keyboard focus after recovery steps (item 9) | `f0cfa05` | `4e51391` |
| Tests | `100abf5`, plus tests inside each commit above | — |
| Docs: ADR 95, ledgers, walkthrough, evidence | `db779c3`, `d0c590e`, `3f13db8`, `22759f4`, `d580292`, `90da094`, `fe3a4cc`, `2cc59ca`, `4fe9f48` | `0f39570`, `ec3c9fe`, `16c4635`, `853d4a9`, `0accff1`, `8665ff9`, `66be040`, `4e51391`, `e10d95d` |

On `work/finance-guide-90`, `8dd7cd9` and its revert `2dce8fd` cancel out. Neither was merged.

## Files changed

- **Product:** `uptime/finance_view.py`, `uptime/finance_guide.py` (both new); `uptime/northwind_workflow.py` (additive projection fields and guide route); `uptime/intelligence.py`; `web/workspace_ui.js`, `web/ramp_ui.js`, `web/v4_ui.js`, `web/interpretation.js`, `web/auth.js` (the guide uses the read session), `web/style.css`, `web/v4_style.css`.
- **Tests (all new):**
  - `tests/test_finance_view_90.py`
  - `tests/test_finance_guide_90.py`
  - `tests/test_finance_browser_90.py`
  - `tests/test_finance_keyboard_95.py`
  - `tests/test_guide_suggestions_browser_95.py`
  - `tests/test_intelligence_abstain_95.py`
  - `tests/test_interpretation_denial_label_95.py`
  - `tests/test_requirements_card_ui_95.py`
  - `tests/data/finance_guide_paraphrases_95.json`
  - `tests/helpers/`: `denial_acceptance.test.cjs`, `refusal_diagnostic.test.cjs`, `requirements_card.test.cjs`, `render_requirements.cjs`
  - `web/`: `finance_view.test.cjs`, `finance_focus.test.cjs`, `guide_suggestions.test.cjs`, `ramp_wording.test.cjs`, `vendor_history.test.cjs`
- **Docs:**
  - [ADR 95](decisions/ADR-0095-grounded-finance-guide.md), with its packet and review
  - [presenter walkthrough](PRESENTER-REHEARSAL-90.md)
  - ledgers: [finance](TEST-CHANGES-finance-guide-90.md), [requirements card](TEST-CHANGES-requirements-card-90.md), [guide suggestions](TEST-CHANGES-guide-suggestions-90.md), [item 9 audit](TEST-CHANGES-item9-audit-90.md)
  - evidence under `evidence/finance-guide-90/`

## Behavior by assignment item

1. **Ramp stays central.** The finance view names the configured destination (Local ledger) and states that no Ramp bill is linked. It links only a record the server supplies. Every Ramp record row and page leads with a verified "Open in Ramp" link (demo.ramp.com URLs only). Ramp record source codes read as plain wording that keeps their meaning: "Saved capture (not live)", "Scenario only, not a finding", "Local counterparty, not a vendor".
2. **Next useful action from case state.** `uptime/finance_view.py` copies values and compares exact decimals; it never derives an amount.
3. **Inputs, clauses, amendments and stages.** Month inputs (fee, fee reference, eligible minutes, completed increments, credit rate, claim deadline, usage record) and price lines come from the evaluator's own results. The stages are labelled as one credit and are never summed. A test asserts that no sum of stages appears.
4. **Clean copy.** "Post to Ramp" appears nowhere. A screen sweep at 390 px and 1360 px found no demo wording on the use-list screens (finance view, Ramp records, vendors, disputes).
5. **Grounded guide.** Fixed fact templates are copied from the projection. Every sentence cites a fact, and every number must appear in the case records. The guide abstains for unsupported, outside-case and judgment questions. No model is called (D10/D12).
6. **Read-only.** The guide route writes nothing: full database dumps are unchanged for both unsigned and signed requests. Action requests get a read-only answer.
7. **CalyxQuay.** The Northwind panel is labelled as that workspace's scripted coverage record. The vendor review screen lists who recorded each revision (scripted preparation versus an account) and says "Rolled back. No version is active." when that is the state. The recorded review (REVOKED at revision 9; revisions 6–9 under `ronok-tanvir`) is not imported into the Northwind workspace; the integration owner rejected combining the records.
8. **Rehearsal, disclosures and fallback.** The walkthrough gives a timeline, the four spoken disclosures, screens to use and avoid, and a deterministic fallback. It matches the frozen demo build `fde492c`. The integration owner's `integration90/REHEARSAL.md` folds it in, including W7's evidence-based corrections: the note author is unproven, and the dispute-record path is verified.
9. **Narrow screens, keyboard, empty and error states, expired sessions.** All four use-list screens passed. Item 9 fixed one gap: focus now follows the next recovery step.

Requests from other workstreams, also delivered:

- **W4:** "Accept denial" posts the offered `basis_digest` to `/denial-acceptance`, and a stale basis reloads the new offer. A read-only dispute record. Contradicting-delivery notices.
- **W3:**
  - verified refusal diagnostics, per job and per family;
  - the review requirements card;
  - review of the D05 phase 2 UI, approved with one follow-up (`0848d59`, verified per-family diagnostics in the selection view).

## Tests and actual results

| Run | Tested commit | Result |
| --- | --- | --- |
| Integration round 3 (fresh clone) | `fde492c` (the demo build) | 4523 passed, 1 warning in 523.01s |
| Integration round 4b (fresh clone) | `5d8af56` | 4636 passed, 1 warning in 417.24s; JS 97/97 |
| Integration round 5 (fresh clone) | `6f43a91` | 4663 passed, 1 warning in 322.05s; JS 101/101 |
| Integration round 6 (fresh clone) | `3f60647` | **4664 passed, 1 warning in 322.63s; JS 104/104** |

The integration owner ran all four rounds. Receipts are in `evidence/integration-90/verification-<commit>.json`. W7 ran no separate full suite, by agreement with the integration owner, so that only one full suite runs at a time on the shared disk.

Notable focused results:

- authored paraphrase corpus: 35/40, then 40/40 after fixes; holdout run once, 19/20 with zero wrong facts and one safe abstention (author-written, so not an independent evaluation);
- the guide's number-grounding test caught a shortened hash, fixed in `221a909`;
- the keyboard walk fails without `f0cfa05`.

No existing test function or assertion was changed. Two exceptions are recorded with reasons in the ledgers:

- my own `refusal_diagnostic.test.cjs` moved to the automatic flow because the profile select was removed;
- several of my own unmerged new tests were corrected before commit.

One flake is preserved, not explained: `test_workspace_ui_v4.py::test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable` failed once under heavy load and passed on reruns. The traceback was not captured; the next occurrence should capture it.

## Decision references

| Decision | How it was made | Effect on W7 |
| --- | --- | --- |
| D03, D04, D05, D06, D07, D10, D11, D12, D13, D14 | **Ronok's own decisions**, recorded November 9 from his overview session (`TEAM-DECISION-HANDOFF.md`) | D12 (read-only first) and D10 (public material only to Claude) define the guide; no model is called because case data is a private overlay. D06 keeps judgment with people. D05 drives the automatic-selection UI. D14 retired the mandatory critique. |
| D01, D02, D09 | **Delegated:** the handoff defaults chosen by the overview session under Ronok's "(Recommended)" authority | The finance view and walkthrough keep native Ramp claims within D02 and D09: no Uptime-origin Ramp write, credits only in Local ledger. |
| D05 phase 2 UI assigned to W3, reviewed by W7 | **Delegated**, by the overview session under Ronok's authority | W7 reviewed and approved `604880e`/`f1a37a1` and added `0848d59`. |
| Full suite on the W7 head | **Ronok's direct instruction** in this session ("Yes, run it after") | Met by integration rounds 4b–6, which cover every W7 commit, run when the integration owner's runs allowed. |
| No model composer, no import of Ronok's review into Northwind, ADR number 95 | **Integration-owner directions** (agent0), not team decisions | Followed. |
| ADR 95 (deterministic view and guide) | W7 implementation decision with one actual Opus 5.5 critique (`claude-opus-5-5`, session `4d9dc03f-9377-4504-8dfe-700c039d148c`) | Disagreements and responses are recorded in the ADR. |
| D08 (claim and dispute delivery channel) | **Pending** | Not needed by W7. |

## Remaining gaps

- **Model-written guide answers** are not built. Under D10, Northwind case facts count as a private overlay and cannot go to a model. Adding them needs customer consent under D10 or a public-only use case, plus a server change so the guide does not hold the shared write lock during a model call. That would be a W0 interface request, and it depends on D10/D12.
- **Attention order and conflict rules** are a finance judgment (Opus's strongest objection). They only order the display and gate nothing, but a finance owner should accept them.
- **The demo build `fde492c` predates several W7 changes:** the requirements card, the one-click questions, the keyboard focus fix and the D05 automatic-selection UI. The walkthrough and `REHEARSAL.md` say what that build lacks.
- **The advanced screens** (case ledger, onboarding lab, integrations, advanced workflows, regression, policies) still show accurate synthetic/fixture/replay labels from the older seeded portfolio. The presenter avoids them.
- **Not done:** a timed run by a person, and the film.

## Rollback

Each change is additive. Nothing stores new rows or changes signatures, hashes or idempotency keys. To remove a piece from `work/integration-90`, revert its merge commit with the first parent (`git revert -m 1 <merge>`), newest first:

| Piece | Merge to revert |
| --- | --- |
| Keyboard focus | `4e51391` |
| One-click questions | `9a85f98` (the docs-only `0accff1` can stay) |
| Requirements card | `c46d253`, then `5d8af56` |
| D05 per-family diagnostics | `1eac5ed` (and `8f46788` for agent2's UI, which also reverts the W3 server enforcement it was paired with) |
| Dispute UI and Ramp wording | `ec3c9fe` |
| Case-inspector abstention | `cc35de4` |
| Guide follow-up | `a3bfefc` |
| Finance view, guide and projection fields | `0f39570` (needs every later W7 revert first) |

Docs-only merges can stay.

## External proof still missing

- No Uptime-origin Ramp write. The agent-run native-posting retest stays blocked and was not retried.
- No Ramp vendor credit and no credit applied to a Ramp bill. The $2,400 application is in Local ledger.
- No real vendor response, award or customer agreement. Northwind is authored.
- The Ramp bill note was posted by a person and read back through the API. The poster's identity is not proven, and it is not evidence that Northwind terms apply to that bill.
- The CalyxQuay review is a recorded local exception (REVOKED at revision 9). It is not a commercial approval or a release certification.
- The guide has no live model answer; this is by D10/D12.
