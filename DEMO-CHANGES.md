# Demo line changes (`demo/film-20261110`)

This line is for the film recorded on November 10, 2026. For it the owner lifted three limits: the side panel may say a service credit may apply to a Ramp bill, the extension may show a toolbar badge, and Uptime may post a note to the bill in Ramp. Everything else stands: nothing here makes a write to Ramp by itself except the fixed notes a server started with `--ramp-notes auto` posts at start-up, after a reviewer decision and after a refresh, and every amount, stage and match on the matched page is the server's.

## Side panel, round two

- **Matched bill page.** A Ramp bill that the server lists in `verified_records` with a `match` shows: "A service credit may apply to this bill", the credit amount and service month, the bill in Ramp and how it was matched, the agreement's quoted clause and inputs, the invoice, the credit applied so far and the remaining balance, the five credit stages with the current one marked, and the bill's notes. The primary button reads "Review and file the claim" at the Estimated stage and "Open the case in Uptime" after it; "Add a note to this bill in Ramp" calls `POST /api/ramp/notes` and is hidden when that answers 404. A bill that is not matched (the DocuSign bill) keeps its present words.
- **Toolbar badge.** The framed page sends `{type: 'uptime-bill-status', bill, state}`; the panel sets a "$" badge on its toolbar button for that tab when `state` is `match` and clears it otherwise. No permission was added: `chrome.action` needs only the manifest's existing `action` key.
- **Compact header at 400 px.** In panel mode the "for Ramp" pill and the account initials are hidden so the wordmark and the whole account name fit on one row.

## Existing tests changed

| Test (exact name) | Reason |
|---|---|
| `web/ramp_bill.test.cjs` › `panel mode is on only when the page is framed, and its message is addressed to one extension origin` | Its stylesheet-scope check also allows the matched page's `.match-` rules, which live in the same panel block. |

No existing test that forbids "claim", "eligible" or the Northwind figures needed changing: they run on the unmatched bills, which keep their words, and the matched bill is a separate fixture in new tests. Those prohibitions now apply to unmatched bills only.

## Tests added

`web/ramp_bill.test.cjs`: the matched page's words and stages, the button words by stage, the notes button's two kinds, its refusal, its non-POSTED answer and its 404 hiding, notes by author, the fallbacks for a missing `verified_records`, `match` or `notes`, and the bill-status message shape. `tests/helpers/side_panel_extension.test.cjs`: the bill-status message checks and the badge calls.

## Side panel, round three

- **"You're in Uptime."** When the active tab is the Uptime app (the tab the panel opened, or any tab on the app's origin) the panel hides its frame without reloading it and shows the Uptime mark, "You're in Uptime" and "You may close this panel."; the bar reads "Uptime" and that tab's badge is cleared. **Permission added:** `http://127.0.0.1:8776/*` in `host_permissions`, so the panel can read the address of a tab on the app's origin; it makes no request to it. Change it with `origin` in `extension/config.js`.
- **"Bills Uptime is tracking."** On a Ramp page that is not one bill (the bar reads "Ramp, no single bill open") the frame opens `#ramp-bills`: every verified record, matched first, with vendor, invoice, amount and one line ("Service credit may apply · $2,400.00", "Above contracted price · $1,000.00", "No agreement on file"), under a count ("2 bills may have money to recover"). A row sends `{type: 'uptime-open-bill', bill}`; the panel, under the same sender checks, moves that Ramp tab to `https://demo.ramp.com/bill-pay/bills/list/<id>`. Any other site still reads "No Ramp bill open".
- **Price exception.** `match.kind: "price_exception"` reads "This bill is above the contracted price by <amount>", with Billed, Expected, Basis and State, and the button "Review in Uptime" to `recovery` (added to the routes the page and the panel allow). It has no credit stages and no note button.
- **Notes and the read.** `notes_mode` `auto` hides the note button and shows Uptime's notes as "Uptime added a note to this bill in Ramp · <time>"; `off` hides the button; `manual` or absent keeps it. A record with `read: {at, live: true}` says "Read from Ramp just now · <time>" with a "Refresh from Ramp" link that calls `POST /api/ramp/refresh` with `{bill_id}` and re-renders (hidden on 404). `ramp_credit.status: "APPLIED_CONFIRMED"` heads the page "A service credit was applied to this bill in Ramp", closes the money card with "Credit applied in Ramp · <amount> · confirmed on the bill and the credit", and marks Applied "Confirmed in Ramp".

### Existing tests changed in round three

| Test (exact name) | Reason |
|---|---|
| `tests/test_side_panel_framing.py::test_the_packaged_extension_is_the_one_origin_the_option_is_documented_with` | The manifest now also asks for the Uptime app's own origin, to recognise a tab on Uptime itself. |
| `tests/helpers/side_panel_extension.test.cjs` › `the manifest asks for the side panel and Ramp tab addresses only, and its key pins one ID`, renamed `the manifest asks for the side panel, Ramp tab addresses and the Uptime app's own tab addresses only, and its key pins one ID` | The same added host permission, pinned to `config.origin`. |
| `tests/helpers/side_panel_extension.test.cjs` › `only overview, records, cases and one case by a plain id may be opened, on the configured origin only`, renamed `only overview, records, recovery, cases and one case by a plain id may be opened, on the configured origin only` | `recovery` is now an allowed route, for the price exception. |
| `web/ramp_bill.test.cjs` › `panel mode is on only when the page is framed, and its message is addressed to one extension origin` | Its stylesheet-scope check also allows the tracking list's `.track-` rules. |

## From the steps and case-page work

Tests changed on the demo line because the demo deliberately changes a rule. One line of reason each.

## Steps on the Overview, three actors, contract-reading chips, "What was filed" (November 10)

- `web/steps_replay.test.cjs` › "the legend counts equal the recorded steps and agree with the server’s own counts": the legend's labels are now "Uptime agent" and "Received from the vendor and other sources", and the sentence under it changed; the counts it checks are unchanged.
- `web/steps_replay.test.cjs` › "off by default: every step shows at once, nothing is scheduled and no request is added": renamed "on by default on the demo line; turned off, every step shows at once, nothing is scheduled and no request is added", because the replay is on by default on the demo line.
- `web/steps_replay.test.cjs` › "turned on, the next decision’s steps are shown one at a time in recorded order, then all remain": it now starts with the setting off. Its check that the page never says "agent" became a check that no step is attributed to a model, Claude or an AI, because the demo line names the "Uptime agent".
- `web/steps_replay.test.cjs` › "Replay shows the whole list in recorded order; skipping or turning it off shows every step at once": it now starts with the setting off, so the automatic replay on first view does not mix with the replay under test.
- `web/steps_replay.test.cjs` › "browser storage that refuses leaves the setting in memory for this page": it now turns the setting off rather than on, because on is the default.
- `web/filed_view.test.cjs` › "a filed claim prints exactly the packet’s own fields in plain labels": the destination now reads "Vendor claims intake (local)" in place of `isolated-local-simulator`; the exact value stays in the complete server record.
- `web/filed_view.test.cjs` › "the case page shows What was filed before the correspondence, from the record it already loaded": renamed "the case page shows What was filed below the correspondence, closed until opened, from the record it already loaded", because the section moved below the correspondence and is now closed by default.

No assertion about money, authority or what reached Ramp was weakened. No Python test was changed in this round.

- `web/ramp_bill.test.cjs` › `a matched bill leads with the possible credit, how it was matched, the evidence, the money and the stages`: the matched page no longer says who started the read, because on the demo line the Northwind bill was entered in Ramp and read back by an agent at the owner's direction.

## The Overview becomes the portfolio; the January case moves to `#recovery` (November 10, round three)

The case's figures, lifecycle, recovery card, decisions, step display, price exception and Ramp record now live at `#recovery`, unchanged. Tests that used them from `#overview` now open `#recovery`. No assertion about amounts, stages or who acted was changed.

- `tests/test_finance_browser_90.py` › `test_attention_guide_keyboard_actions_and_expired_session_recovery`: opens `/#recovery`; the "Show details" focus check now expects `location.hash == '#recovery'` instead of `''`, because the page's own route is now `#recovery` (the button still does not change the route).
- `tests/test_finance_browser_90.py` › `test_narrow_screen_error_empty_and_guide_failure_states`: opens `/#recovery`, where the guide, months table and recovery card now are.
- `tests/test_finance_keyboard_95.py` › `test_keyboard_only_demo_path_needs_a_deliberate_tab_before_each_decision`: opens `/#recovery`, where the decisions are.
- `tests/test_finance_keyboard_95.py` › `test_a_held_enter_records_one_decision_only`: opens `/#recovery`, where the decisions are.
- `tests/test_guide_suggestions_browser_95.py` › `test_suggested_questions_answer_read_only_by_click_and_keyboard_on_a_narrow_screen`: opens `/#recovery`, where the guide is.
- `tests/test_submission_ui_browser.py` › `DESTINATIONS` (used by `test_workspace_name_is_the_same_whatever_page_opens_first`): the Overview's heading is now "Portfolio", not "Northwind Cloud".
- `tests/test_submission_ui_browser.py` › `test_reload_keeps_reading_but_disables_actions_with_one_way_back`: opens `/#recovery`, where "Approve January claim" is.
- `tests/test_submission_ui_browser.py` › `test_four_destinations_fit_a_phone_and_the_overview_leads_with_the_outcome`: opens `/#recovery` for the outcome and lifecycle checks; the four destinations are still each visited.
- `tests/test_submission_ui_browser.py` › `test_automation_workspace_needs_four_person_decisions_and_activity_shows_every_step`: opens `/#recovery`, where the four decisions are.
- `tests/test_workspace_ui_v4.py` › `test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable`: opens `/#recovery`; its stub server answers only the workflow read, and the portfolio also reads the agreements and the Ramp workspace.
- `web/browser-contract.test.cjs` › "configured workspace renders inside the finance shell and keeps native records accessible": the Overview now shows "Portfolio" and reads the workflow first, then `/api/vendors` and `/api/ramp/workspace`; "Northwind Cloud" and the single workflow read are now checked on `#recovery`.

The Python browser tests above were edited but not run at the time (no full suite). One headless Chrome look went through the same paths. They have since passed in the full runs recorded in `DEMO-NOTES.md`.

## Ramp demo server, round two: price exception, automatic notes, refresh, the credit as Ramp shows it (November 10)

- `tests/test_ramp_demo_notes.py` › `test_several_verified_bills_load_and_the_single_record_is_unchanged`: each listed record now also carries `read`, so the comparison with `verified_record` leaves out `read` beside `match` and `notes`, and checks `read` for the saved DocuSign read.
- `tests/test_ramp_demo_notes.py` › `test_the_northwind_sample_matches_and_the_docusign_bill_does_not`: the expected match gains `kind: service_credit` and `ramp_credit`, and its `route` is now `recovery`, because the case's workflow page moved off the Overview.

No amount, stage or authority assertion was weakened.

- `web/ramp_bill.test.cjs` › `a live read says so with its time and can be refreshed; refresh hides on 404; a saved read keeps Not a live read`: the refresh request now sends an empty body, which is what the server accepts.

## How a contract was read, and live Claude readings (`work/demo-ai-20261110`)

- **Agreements page, "How this contract was read".** Every agreement whose record names how it was read shows its source text beside the terms read from it, each term tied to its sentence (hover, focus or press either side). One line of facts from the record: the model (or "No model was used"), how many quotes appear word for word in the source text the server sent (checked in the page), and who accepted the interpretation. "Replay the reading" steps through the terms in reading order, labelled "Recorded run · <date>" from the extraction record. Pure helpers are in `web/contract_reading.js`.
- **"Read a contract with Claude".** Offered to an account that may stage drafts. It submits a real proposal job for an authored sample (`fixtures/submission_onboarding/`) or pasted text, shows each job's state from the server, then the proposed terms beside their sentences, labelled "Live run". Nothing is staged or approved.
- **`scripts/setup_northwind.py --serve --model-jobs`** writes `<workspace>/model-jobs/` (config and exact-request approvals for the samples, three takes each, model invocation only, 12 hours) at start-up and serves with it.

No existing test was changed for this.

## Portfolio round four: matched Ramp bills, notes in Ramp, other vendors' estimates (November 10)

- `web/portfolio.test.cjs` › "the credit row follows the credit’s own latest recorded stage; nothing is added across stages or rows": the tiles object now also carries `matched` (Ramp bills matched to an invoice); the expected object gains `matched: 0`. Amount and stage assertions are unchanged.
- `web/portfolio.test.cjs` › "agents at work counts recorded facts: Claude readings, Uptime agent steps and reviewer decisions": the counters now also carry `notes` and `uptimeNotes`; the expected objects gain `notes: 0, uptimeNotes: 0`.
- `web/portfolio.test.cjs` › "the portfolio page reads the agreements and the saved Ramp workspace and shows rows, tiles and counters": the credits tile line now names the vendor ("Northwind Cloud · January 2026: $2,400.00 · Estimated"), because other vendors' estimates can now appear in it.

## Second vendor: Corvid Ledger estimate

- `scripts/setup_northwind.py` `seed()` gains three lines after `seed_calyx(post)`: it installs Corvid Ledger (`/api/vendors/corvid-ledger`) from the recorded `claude-opus-5-5` reading, through `uptime/demo_opportunities.py:seed`.
- The workflow view gains `opportunities`, set after the finance summary: Corvid's October 2026 credit, evaluated read-only by the installed ACTIVE agreement (no case, claim, approval, posting or application). Fixtures and limits: `fixtures/corvid_ledger_demo/README.md`.
- The portfolio (`web/workspace_ui.js` `portfolioRows`) shows each entry as a "Service credit" row, "Estimated · not claimed", next: Reviewer, linking to `#agreements`; the tiles count it.
- No existing test changed. Added: `tests/test_demo_opportunities.py` and one test in `web/portfolio.test.cjs`.

## Ramp demo server, round three: other vendors' estimated credits (November 10)

- `tests/test_ramp_demo_notes.py` › `test_the_northwind_sample_matches_and_the_docusign_bill_does_not`: the expected `agreement` gains `read_by` (`deterministic_document_parser`, the Northwind agreement's own extraction method), so a page can say who read each contract.
- Added `tests/test_ramp_demo_round3.py`: a Ramp bill that agrees with another vendor's estimated credit (Corvid, `opportunities`) is matched with route `agreements`; auto mode posts its note once; a bill one cent off does not match. The note for such a bill ends "The estimate is waiting for review in Uptime." because no claim is being prepared for it; the fixed shapes in `uptime/ramp_workflow.py` allow that second ending.

## Wording and the panel's routes (coordinator, November 10, 04:31 PST)

- Rule-based steps are labelled "Uptime · automatic" (they were "Uptime agent"), and the portfolio's counters are headed "Who is doing the work" (was "Agents at work"), so that "agent" on screen always means a model. Changed tests: `web/steps_replay.test.cjs` (the legend figures and the sentence under them), `web/overview_steps.test.cjs` › "three plain actors: the reviewer, Uptime automatic steps, and the vendor or the named source" (was "... the Uptime agent ...") and its two label lists, `web/portfolio.test.cjs` › "the work counters count recorded facts: Claude readings, automatic steps and reviewer decisions" (was "agents at work counts ...") plus the `nextActor` word and the page-text list.
- The portfolio header no longer shows one case's "As of" date, because the page spans months and vendors.
- The side panel may ask to open `agreements` (a bill matched to another vendor's estimate leads there). Changed test: `tests/helpers/side_panel_extension.test.cjs` › "only overview, records, recovery, agreements, cases and one case by a plain id may be opened, on the configured origin only" (was without "agreements"; `agreements/x` is still refused).
- A matched bill's page shows "Contract read by" from the match's `read_by`, and for an estimate with no claim the button reads "Review the estimate in Uptime".

## Jev client (`work/demo-tb-jev-20261110`)

- Added `uptime/jev.py` (`JevClient`, `JevUnavailable`, `FakeJev`), the interface in `docs/demo/TEMPLATE-BUILDER.md` unchanged. One extra keyword-only constructor argument, `opener`, lets tests inject a fake transport.
- Verified against TypeSafe's OpenAPI document (`https://api.typesafe.ai/openapi.json`) and real calls: `POST https://api.typesafe.ai/v1/systemone`, Bearer key, body `{"model": "jev-1.13.0", "state": <text>, "questions": {"q": {"type": "choice" | "noul", "instructions": ..., "criteria": {...}}}}`; answers under `answers.q` (`choice` + `probabilities`, or `noul` = probability of yes).
- Standard library only. HTTPS to `api.typesafe.ai` only, redirects not followed, 20 s timeout, context cut to 6,000 characters. The key is read per call and never kept, logged or put in an exception.
- Added `tests/test_jev.py` (no network) and `scripts/jev_smoke.py` (two real calls on a made-up SLA sentence).
- No existing test changed.

## Template builder engine (`work/demo-tb-engine-20261110`)

New files: `uptime/template_rules.py` (the fixed interpreter: one regular expression per term, run in a time-limited worker process), `uptime/template_builder.py` (`TemplateBuilds`: Jev classification, three Claude readers, Claude template builder with up to two repair rounds, five checks, reviewer approval by SHA-256, the post-approval read; HTTP routes), `fixtures/template_builder_demo/` (three authored Halcyon Grid addenda, `expected.json`, `README.md`), `tests/test_template_builder.py`, `scripts/template_builder_smoke.py` (one real build against the Claude Code CLI and Jev).

Wiring: `uptime/server.py` registers the routes (off unless `app.state.template_builds` is set); `scripts/setup_northwind.py` gains `--template-builder` (requires `--serve`; `--claude-executable` now also applies to it) and `prepare_template_builds`.

No existing test was changed.
## Template builder page (November 10)

Built against `docs/demo/TEMPLATE-BUILDER.md` (routes and the `sample`, `build` and `reading` shapes) with no change to that page.

- New: `web/template_builder_ui.js` (the Agreements section "A contract type Uptime has not read before" and the run page
  `#template-build/<id>`, drawn from `build` alone and polled every 700 ms until READY_FOR_REVIEW, APPROVED or FAILED;
  polling stops when the view is left) and `web/template_builder.test.cjs` (14 tests through every build state, Jev not
  reached, a blocking failure, approval, a reading with a term not found, a failed build and a disabled server).
- `web/style.css`: one new block, "15c. Template builder", placed before "16. Side panel", which stays last.
- `web/index.html`: one script tag for `/static/template_builder_ui.js`, before `app.js`.
- `web/app.js`: `companionRoute` maps `template-build/<id>` to the view `template-build`; the view is rendered by the
  template builder and marks Agreements in the rail; the Agreements route mounts the section after the companion page
  renders; navigation and sign-out unmount it. Not added to the side-panel allowed routes.
- No existing test was changed.
- After merging `demo/film-20261110`: the page also uses the engine's additions. The second-document check names
  `sample.second_document` (or the check's `document`); an expanded term shows `rule.map`, `rule_quote` and
  `rule_error`; a term without a Jev answer while Jev's check ran says "No answer" with no number; a refused start
  (429, 404) shows the server's sentence. An advisory check that did not pass (Jev's) reads "For the reviewer" in
  amber rather than a red failure, a REVIEW term's Jev figure is amber, and the approval card names the marked terms
  and says Jev's check is advisory. Two tests added to `web/template_builder.test.cjs` (16 in all). Watched one real
  build (`--template-builder`) through the page: ready for review after 23.7 s, approved, next contract read by the
  template in 5.0 ms with 0 model calls.

## After the first full run of the demo line (coordinator, November 10, 05:38 PST)

The full suite was run once on `977bd19`: 5,539 passed and 3 failed, all three because of the template builder's new files.

- `tests/test_ramp_ui_v4.py` › `test_ramp_browser_navigation_and_read_only_plan` and `tests/test_workspace_ui_v4.py` › `test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable`: each test's stand-in server lists the static files the page may load; the list gains `template_builder_ui.js`, the new script `web/index.html` loads. Nothing else in either test changed.
- `tests/test_vendor_requirements_89.py` › `test_new_vendor_name_reaches_shadow_with_useful_drafts_and_no_vendor_code` was NOT changed. It checks that no file in the `uptime` package names its made-up vendor "Halcyon", and the template builder had named its own sample vendor in code. The sample list moved to `fixtures/template_builder_demo/samples.json`; `uptime/template_builder.py` now names no vendor and serves only the documents that file lists.
- Added `tests/test_template_builder.py` › `test_only_the_listed_sample_texts_are_served`: the sample text is served, and `expected.json` (the authored answers), `samples.json`, the README and an unlisted name are not.

## Before publishing (coordinator, November 10, about 12:15 PST)

A read-only review of everything the demo line adds found nothing that blocked publishing and several things worth fixing first.

- `tests/test_ramp_demo_round2.py`, the shared `auto` fixture and › `test_a_failed_note_never_breaks_a_decision_and_is_recorded`: reading `/api/ramp/workspace` used to retry a failed note, so a read could write to Ramp. It no longer does. The fixture now reads the workspace while a retry is due and the test asserts nothing was posted; the retry itself is then run the way the served app's timer runs it (`auto_check`). The assertions about what reaches Ramp are otherwise unchanged.
- `uptime/ramp_workspace.py`: the read route no longer calls the note poster. `uptime/ramp_demo.py`: `start_retries` retries a failed note from a background timer in auto mode; `ramp_credit` answers `APPLIED_CONFIRMED` only when exactly one applied credit is verified on both sides, and `UNKNOWN` otherwise.
- `uptime/template_builder.py`: the sample text route checks the tenant. `uptime/template_rules.py`: a text over 200,000 characters is refused.
- Notes corrected: the sentence above about writes to Ramp, the two sentences about Python tests, `docs/demo/TEMPLATE-BUILDER.md` on which routes need a reviewer, and the route list in `extension/README.md`.

## After GitHub's check run (coordinator, November 10, 12:44 PST)

GitHub's check workflow ran the suite on the published commits and one test failed there (5,542 passed): on its Linux image `/usr/bin/true` is a link to `/usr/bin/gnutrue`, and the configuration records the resolved path.

- `tests/test_setup_model_jobs_demo.py` › `test_model_jobs_writes_private_config_and_exact_sample_approvals`: the expected `executable` is now the resolved path of `/usr/bin/true` (it was the literal string). The test came with the demo line and had only run on macOS, where the two are the same. Nothing about approvals, modes or requests changed.

## Template builder version 2: the engine (engine agent, November 10, afternoon)

Answers the judge's criticisms 2, 3 (in part) and 4. The contract is "Version 2" in `docs/demo/TEMPLATE-BUILDER.md`.
The section "Version 2 as the engine built it" there records the shapes left open, two deliberate changes and the
blocker in `uptime/server.py`.

- `uptime/template_rules.py`: every match of a rule is found. Different values in more than one place read nothing
  and the error says how many places matched; identical values are accepted. New: `value_in_sentence`,
  `plausibility`, map validation for choice terms, and per-term `places` / `ambiguous`. Jev's per-term questions
  now ask what the sentence literally says.
- `uptime/template_builder.py`:
  - Jev routes the run (`MATCHED`, `NEEDS_REVIEWER` and `continue_without_jev`).
  - The three readers differ: clause by clause, numbers first, and a sceptic on `claude-sonnet-5-5`. `ClaudeCLI`
    takes the model per call and verifies it from the envelope.
  - The new check `value_in_sentence`. The `second_document` check has no answer key: three fresh readers read the
    second contract in parallel with the first three.
  - Approval requires acknowledging the terms Jev did not support.
  - Reads are guarded with five guards and persisted. Each term says why it is blank.
  - Contracts can be pasted, with consent; the per-process build limit is 12.
  - `approved_readings`, `set_agreement` and `on_reading` for the money link.
  - A repair answer in the wrong shape uses its round and the next round is tried.
- `scripts/template_builder_smoke.py` was rewritten: a real build, an approval by a script in a throwaway folder
  (said plainly), a guarded read, and a second build that Jev routes to the approved template.

Existing tests changed in `tests/test_template_builder.py`, each for the reason given:
- The `FakeClaude` and `FakeJev` helpers: Claude is now called with `model=`; readers answer in their role's shape
  and on either contract; Jev's per-term questions changed wording. The fakes' answers are still the authored values.
- `test_happy_path_approval_and_the_template_reads_document_c`: six reader calls instead of three (the second
  contract is read by readers, not checked against an answer key); six checks; the approval body carries
  `acknowledged: []`; the reading is asserted ACCEPTED with every guard passing. The value assertions are unchanged.
- `test_a_quote_not_in_the_contract_blocks_approval` and `test_a_rule_that_fails_on_the_second_document_is_repaired`:
  the approval body gains `acknowledged`; the repair prompt is read from the fake's prompt list. Assertions unchanged.
- `test_two_readers_failing_fails_the_build`: unchanged text. The fake now fails readers by role on the first
  contract, because six readers run at once.
- `test_jev_unreachable_still_reaches_review` was replaced by
  `test_jev_unreachable_waits_for_a_reviewer_then_builds_with_every_term_flagged`. Version 2 changes the behaviour:
  with Jev unreachable nothing starts until a reviewer continues, and then every term needs acknowledgement.

New tests (same file) cover: ambiguity refusal; acceptance of identical repeats; `value_in_sentence`;
`plausibility`; differing readers and models; the sceptic's conflict; the CLI's model verification; MATCHED with no
Claude call; a match under 0.80; unrecognised; Jev not asked with nothing on file; acknowledgement gating, including
an unanswered term; the keyless second check passing, failing and with no majority; consent and the paste limits;
a paste with and without a second contract; the build limit of 12; each read guard refusing; the advisory
template-match guard; the read body shapes; `on_reading`, `approved_readings` and `set_agreement`; the money link on
a MATCHED build; the choice map validation; a repair round in the wrong shape; per-term reasons on a reading; and the
Jev question wording. No new files.

## Template builder version 2: the money link (`work/tb2-money-20261110`)

An ACCEPTED read by an approved template now yields a SHADOW agreement whose estimated credit the existing
`monthly-availability/1` engine computes (`vendor_terms.compile_terms`, `bind_overlay`, `vendor_eval.evaluate`). No model
is called and no credit arithmetic was added. Nothing is posted, claimed, filed or applied.

New files: `uptime/template_agreements.py`, `tests/test_template_agreements.py`,
`fixtures/template_builder_demo/evidence/README.md` and `fixtures/template_builder_demo/evidence/halcyon-c/`
(`overlay.json`, `usage.json`, `invoice.json`, `estimate.json`; authored, December 2026).

Changed: `uptime/demo_opportunities.py` (`opportunities` takes an optional `templates` callable whose rows follow
Corvid's; Corvid's evaluation moved unchanged into `_corvid`), one argument in the `opportunities(...)` call in
`uptime/northwind_workflow.py`, and one line after `app.state.template_builds` is assigned in
`scripts/setup_northwind.py` (`template_agreements.connect(app)`: sets `on_reading` and the workflow's portfolio lister).

No existing test was changed.

## Held-out evaluation of the template builder (evaluation agent, November 10)

No existing test, engine file, prompt, shipped sample or page file was changed. New files:

- `scripts/evaluate_template_builder.py`: one command, no arguments; builds a template from each held-out form's
  document A (B as the second contract), approves it as `evaluation-script` when every blocking check passed, reads the
  held-out document C with it, scores C against the hand key and writes `fixtures/template_builder_heldout/results/<timestamp>.json`.
  Uses the version 2 API when present and the version 1 API otherwise.
- `fixtures/template_builder_heldout/author.py`, `briefs/` (the common brief, six style briefs and the exact text sent
  for each form), `forms/form-1` to `form-6` (`response.txt` as returned, `a.txt`, `b.txt`, `c.txt`, the author's
  `author_values.json`, `manifest.json` with SHA-256s, and the hand-written `key.json`), and `results/`.
- `docs/demo/TEMPLATE-BUILDER-HELDOUT.md`: how the contracts were written and frozen, and the baseline result.

## Template builder page, version 2 (page agent, November 10, afternoon; branch `work/tb2-page-20261110`)

Built against the shapes in `docs/demo/TEMPLATE-BUILDER.md` › "Version 2" with mocked responses; the new server code is not on this branch.

- `web/template_builder_ui.js`: "Paste a contract" on the Agreements page (title, vendor, text, optional second contract, required consent naming Claude and Jev; the button stays disabled until there is text and consent; the server's sentence is shown on 409, 404, 429 and 422). The run page draws `MATCHED` (leads with the reading and its guards, reader and builder steps "Not started", a line that no Claude agent ran), `NEEDS_REVIEWER` (one "Build without Jev" button, `POST .../continue` with `{}`, then polling resumes) and the ordinary route (the Jev step says why the readers started). Reader cards show their role in words and the model that answered. Checks are drawn in the interface page's order; a check with `"ran": false` reads "Not checked" and is never a pass or a failure. Terms show the second contract's readers and whether the value is in its sentence; a term with `needs_acknowledgement` gets a tick box in its expanded row, and "Approve this template" stays disabled with the count still to acknowledge until each is ticked; the POST sends `acknowledged`. Readings show ACCEPTED or REFUSED with each failed guard's reason, the guard list (Jev's probability on `template_match`), "Values by fixed rules · Jev checked the document type" when `model_calls` is 0 and `jev_template` is present, what a refused read found marked as not accepted, and the money link card (`reading.agreement`) exactly as sent, with the `evaluation` sentence and no amount when `credit` is null. After approval a next contract can be pasted and read.
- `web/ramp_ui.js` (one expression) and `web/workspace_ui.js` (one expression): a `read_by` starting `template:` reads "Fixed rules · template <id>".
- `web/style.css`: additions inside the template-builder block (15c), which still sits before the side-panel block.
- Changed existing tests in `web/template_builder.test.cjs`:
  - `READY_FOR_REVIEW: terms with agreement, Jev percentage and a term marked for the reviewer; rows open to the sentence and rule`: Jev's check row now reads "Jev · a term it does not support needs your acknowledgement" instead of "Jev · advisory", because in version 2 Jev's check gates approval through acknowledgement. The figures asserted are unchanged.
  - `approving POSTs the exact SHA-256, then shows who approved it and offers the next contract; the reading never guesses`: the expected approve body gains `acknowledged: []`, the version 2 body (the page always sends the list). The SHA-256 assertion is unchanged.
- New tests in `web/template_builder.test.cjs` (11): MATCHED; NEEDS_REVIEWER and the continue button (and a refused continue); differing reader roles and models; six checks in order with `value_in_sentence` failing and blocking; the second-contract check with `ran: false`; acknowledgements gating approval and the POST body (and a 409); a REFUSED reading with its reasons; a reading with an agreement and with `credit: null`; pasting a next contract after approval; the paste form's disabled states, POST body and 409/404/429/422 sentences; `read_by` wording in the two shared files.
- No new files in the repository.

### Template builder page against the real server (page agent, November 10, evening)

After merging `work/submission-integration-20261109` (7babdfe), the page also shows what the engine added: the `classify` step reads "Not asked" with no timing or Jev figure when `detail.asked` is false; a term's `conflict` (the sceptic's sentence) and `rule_places`; the second-contract check's `basis` and its `readers` (role, model, seconds); a reading's `reasons`, each blank term's `error`, and `agreement_note`. One new test in `web/template_builder.test.cjs`; no existing test changed. One real pass in headless Chrome (one real build, one pasted contract that came back MATCHED): approval sent both flagged fields, the next contract's reading was ACCEPTED with five passing guards and an estimated credit of USD 4,200.00 for October 2026, and the portfolio row reads "Agreement HGS-PAA-2026-0457 · Fixed rules · template halcyon-availability-addendum/1".

## Joining version 2 (coordinator, November 10, about 17:20 PST)

- `uptime/server.py`: the template-builder routes join the paths allowed a 256 KB signed body; a pasted contract is larger than the default 4 KB.
- The next-contract sample `fixtures/template_builder_demo/halcyon-c.txt` takes effect on August 3, 2026 (it said November 3), and its authored usage and invoice are for October 2026 (they were for December), so the estimated month has already happened. Both months have 31 days; the arithmetic is unchanged. `tests/test_template_agreements.py` (new that afternoon) follows: the effective date, the month and the invoice id.
- The estimate's sentence is written for a person from the engine's own results ("44,545 of 44,640 UTC minutes were available (99.787%), so the 35% credit tier applies: 35% of USD 12,000.00 is USD 4,200.00."); the engine's raw line stays among the inputs. `tests/test_template_agreements.py` › `test_authored_month_is_estimated_by_the_engine_to_the_cent` and › `test_no_unavailability_earns_no_credit_and_no_invented_amount` expect the new sentence.
- Jev's summary on a matched run gives the probability as a percentage.
- `scripts/evaluate_template_builder.py`: its call counter now passes through the model the version 2 engine names per call. The first run on version 2 failed every form in 0.0 seconds for that reason and measured nothing; it is kept under `fixtures/template_builder_heldout/results/harness-fault/` with a note.

### Terms a contract does not state (page agent, November 10, evening)

Built against the coordinator's shapes with mocks (the engine change lands separately). A term with `status: "NOT_STATED"` / `stated: false` reads "Not stated in this contract" with the readers' agreement, no Jev figure, its `reason` in the expanded row and the tick box "I have checked that the contract does not state this"; it counts toward the acknowledgements that gate approval and its field is sent in `acknowledged`. The new `stated` check is drawn first; a check with `not_stated` above zero reads "8 of 8 · 1 not stated". A reading's not-stated field reads "Not stated when this template was built" (never "Not found") and the count line reads "8 of 8 terms found · 1 not stated". The approval note no longer says every flagged term is one "Jev did not support". Three tests added to `web/template_builder.test.cjs`; no existing test changed.

- (Engine, November 10, evening.) Not-stated terms: when every reader says the contract does not state a term in the
  unit asked, the term is `NOT_STATED` and has no rule. The reviewer acknowledges it, and the template records it in its
  hashed body. A new blocking check `stated` requires the commitment and the first-tier credit. Reads report not-stated
  fields without failing `complete`. Existing tests changed in `tests/test_template_builder.py`, additive shapes only:
  `test_happy_path_approval_and_the_template_reads_document_c` (the check list starts with `stated`),
  `test_second_contract_check_passes_against_what_its_readers_agreed` (`second_readers` gains `stated`), and
  `test_a_pasted_contract_without_a_second_contract_can_be_approved_unchecked` (the check gains `not_stated: 0`).
  Seven tests added. Shapes: docs/demo/TEMPLATE-BUILDER.md, "A term every reader agrees the contract does not state".

### Acknowledged terms after approval; three README images retaken (page agent, November 10, night)

- An acknowledged term's open detail takes the row's green (`.tb-term-acked + .tb-detail-row`). An acknowledged row is no longer also drawn as waiting for review. After approval, the terms the review step records in `acknowledged` stay marked, with the line "Acknowledged by the reviewer when this version was approved.", and the header pill reads "N terms acknowledged at approval".
- The second-contract check capitalises the first letter of the server's `basis` sentence, because builds saved before the server fix keep the lowercase sentence.
- When a document has been read more than once, the latest reading is shown.
- `docs/assets/demo/template-terms.png`, `template-checks.png` and `template-credit.png` are retaken from the resumed workspace of the last real run (`--resume --template-builder`, no Claude call). The credit image comes from a fresh `read` of the next contract (template only, 45.4 ms, 0 model calls), so the agreement's inputs no longer carry the engine's raw line.
- Tests: one existing test extended in `web/template_builder.test.cjs` (`terms show the second contract’s readers and the value in its sentence; approval waits for every acknowledgement and sends them`) with assertions for the state after approval. Its existing assertions are unchanged. Two further assertions were added to existing tests: the capitalised basis, and the latest reading of a document.

## Template claims: the credit an approved template read goes through the claim lifecycle (November 10, evening)

An accepted read of `halcyon-a` by an approved template now carries its ESTIMATED credit through the Northwind case's
stages and four reviewer decisions, with the same machinery (`WorkspaceWorkflow`, the correspondence inbox, the
allocation ledger, the local ledger provider, the coordinator). Each such case lives in its own case database under
`<workspace>/template-claims/<document id>/`, so it has its own clock, intents, steps, inbox and ledger.

- Hooks in existing files: `uptime/northwind_workflow.py` (`_next` takes the claim labels from `self.labels`; same
  strings for Northwind); `uptime/server.py` (registers `/api/template-claims/...`); `scripts/setup_northwind.py`
  (enrols the four signed sources for each authored template claim's two months; keeps `senders` on `app.state`;
  connects claims with `--template-builder`); `web/workspace_ui.js` (`create()` takes `viewPath`, `actionPath`, `guide`,
  `caseLinks`, `decorate`; a null `price_finding` hides the price card; a template estimate with a `claim` shows the
  claim's stage, amount, next actor and link on the portfolio); `web/app.js` (`#template-claim/<id>`); `web/index.html`
  (one script tag); `web/template_builder_ui.js` (one "Open the claim" link on the agreement card).
- Changed existing tests: `tests/test_ramp_ui_v4.py` › `test_ramp_browser_navigation_and_read_only_plan` and
  `tests/test_workspace_ui_v4.py` (its static-file allow-list used by
  `test_configured_workflow_keeps_evidence_money_and_original_navigation_reachable`,
  `test_workflow_action_uses_real_dom_collection_and_refreshes_server_state` and
  `test_result_quotes_and_decimal_equations_render_as_server_text_without_html_execution`): `template_claim_ui.js`
  added to the scripts a page may load, because `web/index.html` now loads it. No assertion changed.
- New files: `uptime/template_claims.py`, `web/template_claim_ui.js`, `web/template_claim_ui.test.cjs` (4 tests),
  `tests/test_template_claims.py` (6 tests), `fixtures/template_builder_demo/evidence/halcyon-a/` (README, overlay,
  usage, invoice, estimate, lifecycle, correspondence, next_invoice, agreement, order-monthly-rate.txt, service-log.txt).
- Follow-ups (same evening): a lone outcome card takes the whole row (`web/style.css`, one rule beside `.outcome`), so the
  case page's invoice figures fit on one line; Northwind's page has two cards and is unchanged. After approval the
  build page offers "Read this contract with the approved template" for the sample's own document (POST
  `{"document_id": <its id>}`). "Open the claim" now appears only when the server marks the reading's agreement
  `"claim": {"available": true, "case": <document id>}` (`template_claims.connect` wraps the money link's `on_reading`);
  a reading with an estimate but no claim evidence carries no marker and shows no link. New tests: 2 in
  `web/template_claim_ui.test.cjs`, 1 in `tests/test_template_claims.py`.
- Known limits: (1) the first decision's packet approval is of the estimate the reviewer saw (reading, template SHA-256,
  values, evidence hashes, amount); the inbox's approval of the claim packet is recorded under it only after the
  engine's assessed claim matches that estimate, not on a packet the reviewer saw on screen. (2) Because each case
  lives in its own database, its steps and agreement are not yet counted in the portfolio's "Who is doing the work",
  Activity, Cases or "Agreements on file", and the generic `/api/dashboard` does not list it.
## Template builder version 3: a schedule of tiers, and units (November 10, night; branch `work/tb3-tiers-20261110`)

Shapes: `docs/demo/TEMPLATE-BUILDER.md`, "Version 3". The three tier terms became one `credit_schedule` (one to six
tiers); `claim_window_days` and `maintenance_notice_hours` became `claim_window` and `maintenance_notice`, each a value
and the unit the contract writes. Changed files: `uptime/template_rules.py` (interpreter `uptime.template_rules/3`:
schedule and duration rules, `normalize_lines`, `order_schedule`, `canonical_schedule`, `canonical_duration`,
`row_in_sentence`), `uptime/template_builder.py` (prompts, parsing, agreement on whole values, per-tier quotes, Jev
once per tier), `uptime/template_agreements.py` (only the value-to-engine mapping: `FIELDS`, `LABELS`, `_tiers`,
`_restatement`, `_term_inputs`; `evaluate`'s signature and the agreement object are unchanged),
`web/template_builder_ui.js` and its block in `web/style.css`, `fixtures/template_builder_demo/expected.json` (the new
shape; same values), `scripts/evaluate_template_builder.py` (maps the held-out keys' old field names; see its
docstring) and `scripts/template_builder_smoke.py` (also prints the money link's estimate).

Existing tests changed, each only for the new term shape; no threshold or monetary assertion was relaxed:

- `tests/test_template_builder.py` helpers `GOOD_RULES`, `FakeClaude` (and new `reader_item`, `reader_terms`): the
  Halcyon rules and reader answers in the version 3 shapes (one schedule rule with one row pattern; durations with
  named `value` and `unit` groups).
- `test_happy_path_approval_and_the_template_reads_document_c`: quotes 27 -> 24 (6 terms and 2 tiers, 3 readers);
  found and total 9 -> 7; a schedule's quote is a list of sentences, each still required to be in contract C.
- `test_a_quote_not_in_the_contract_blocks_approval`: the invented quote is on `claim_window` with a unit; 26/27 -> 23/24.
- `test_a_rule_that_fails_on_the_second_document_is_repaired`, `test_a_wrong_shaped_repair_answer_uses_a_round_and_the_next_round_runs`:
  the hard-wired claim rule written with named groups.
- `test_interpreter_guards`: the time-limit, compile and "exactly one group" cases use `credit_cap_percent` (a
  duration rule now needs named groups, which is asserted separately); the hard-coded claim rule uses named groups.
- `test_a_rule_matching_two_places_with_different_values_reads_nothing`: the loose claim rule uses named groups; still 3 places.
- `test_value_in_sentence_digits_words_and_choices`: durations are {value, unit}; the "99.50%" case moves to a percent
  term; added: a calendar-days value is not in a business-days sentence and the reverse, and hours are not in a days sentence.
- `test_plausibility`: the two-tier cases become schedule cases (a tier above the commitment, credits that do not rise,
  a repeated threshold); claim and notice cases use durations, plus a unit that is not one of the term's.
- `test_a_sceptic_conflict_puts_the_term_under_review`: the conflict is on `credit_schedule` (the second-tier threshold no longer exists as a term).
- `test_jev_unreachable_waits_for_a_reviewer_then_builds_with_every_term_flagged`: 9 -> 7 terms to acknowledge.
- `test_approval_is_refused_until_the_flagged_terms_are_acknowledged`, `test_a_term_jev_did_not_answer_needs_acknowledgement`,
  `test_every_reading_term_says_why_it_is_blank`, `test_readers_disagreeing_on_whether_a_term_is_stated_invent_no_value`: field names only.
- `test_second_contract_check_passes_against_what_its_readers_agreed`, `test_second_contract_check_fails_when_its_readers_agree_on_another_value`:
  9 -> 7 and 8 -> 6 terms; the claim window's values are {value, unit}.
- `test_a_read_missing_a_term_is_refused`, `test_a_read_whose_value_is_not_in_its_sentence_is_refused`: "8 of 9" -> "6 of 7".
- `test_an_implausible_read_is_refused`: the implausible edit is now a cap (20%) below the highest credit (25%),
  because lowering the second tier's credit to 5% now makes the interpreter itself refuse the schedule, which the
  test also asserts (the read is still REFUSED, now by `complete`).
- `test_jev_questions_ask_what_the_sentence_literally_says`: the threshold question becomes one question per tier;
  9 -> 8 questions (6 terms and 2 tiers).
- `test_a_term_all_readers_say_is_not_stated_is_approvable_once_acknowledged`, `test_the_second_contract_stating_a_term_the_first_does_not_fails_second_document`,
  `test_the_interpreter_skips_not_stated_fields`: field names; counts 8 -> 6 and 9 -> 7.
- `test_a_reader_converting_days_to_hours_is_caught_by_value_in_sentence`: the converted value carries a unit.
- `test_a_required_term_not_stated_blocks_approval`: the required pair is the commitment and `credit_schedule`.
- `test_a_reader_saying_not_stated_with_a_value_is_refused`: reader answers in the new shapes; the prompt is checked for
  "Never convert between units" and the business-days example instead of the removed hours wording.
- `tests/test_template_agreements.py` › `test_overlay_from_halcyon_c_terms_is_the_engines_tier_family`: field name
  `maintenance_notice`. › `test_the_maintenance_notice_term_may_be_missing_because_the_engine_does_not_use_it`: field
  name and input wording ("Not stated in this contract"), plus notice in business days. ›
  `test_missing_term_gives_no_credit_and_names_the_term`: the missing term is the schedule. ›
  `test_terms_the_engine_cannot_express_are_refused`: the out-of-order case is a schedule tier above the commitment,
  now refused before the engine with the plausibility sentence; added credits that do not rise and claim windows in
  business days and months.
- `web/template_builder.test.cjs`: no existing test changed.

New tests: 13 in `tests/test_template_builder.py` (lines kept apart from a sentence, a three-row table, a schedule of
one, a commitment row, three refused schedules, identical tiers merged, rule shapes, durations keeping units, reader
schedules, agreement on the whole schedule with Jev per tier, the schedule in the hash and the reading), 1 in
`tests/test_template_agreements.py` (schedules of one and three tiers through the engine), 2 in
`web/template_builder.test.cjs` (schedule rows and sentences, durations; a reading's schedule). New files: none in part 1.

Checks for part 1: `tests/test_template_builder.py`, `tests/test_template_agreements.py`, `tests/test_demo_opportunities.py`,
`tests/test_jev.py`: 126 passed; `node --test web/*.test.cjs tests/helpers/*.test.cjs`: 237 tests, 237 pass. One real
build on the shipped sample (`scripts/template_builder_smoke.py`, real Claude Code CLI and real Jev, 8 Claude calls):
READY_FOR_REVIEW with every blocking check passing (24 of 24 quotes, 7 of 7 values in their sentences, reproduce 7 of
7, second contract 7 of 7); Jev answered 0.72 on a tier, so the schedule needed acknowledgement; approved by the
script `smoke-script` (not a person); halcyon-c read ACCEPTED with 7 of 7 terms and estimated USD 4,200.00 for
October 2026; a second build of halcyon-c pasted was MATCHED by Jev (0.91) with no Claude call. The full
`uv run --locked pytest` merge suite was not run on this branch. Held-out run 4: `docs/demo/TEMPLATE-BUILDER-HELDOUT.md`.

### Real public SLAs (part 2, same branch)

No engine, prompt, check or threshold was changed for this part, and no existing test was changed. New files:
`scripts/evaluate_public_slas.py` (fetch once with urllib into `~/uptime-demo/public-slas/`, HTML to text with
html.parser, one real build per page, script approval, guarded read, scoring in two views, every quoted sentence,
pattern, map phrase, reader reason and interpreter message hashed), `fixtures/template_builder_public/sources.json`,
`fixtures/template_builder_public/key.json` (values only, written by hand; one value corrected after the run, noted in
it), `fixtures/template_builder_public/results/20261111T015844Z.json` and `docs/demo/TEMPLATE-BUILDER-PUBLIC-SLAS.md`.
The vendors' text is not in the repository. Found and left unfixed so the published numbers stand: the
`value_in_sentence` words for `credit_application` and `measurement_period` refuse correct values on most real pages,
and "invoices" (plural) does not match the word "invoice".
- After merging version 3 terms (`work/tb3-tiers-20261110`, f17bd8b): the claim flow calls the money link's conversion
  unchanged and needed no conversion of its own. Changed in my own tests only: `tests/test_template_claims.py` ›
  `test_a_misread_term_fails_the_controls_and_opens_nothing` misreads the second tier through `credit_schedule`
  (the old field `tier_2_credit_percent` no longer exists), and
  `test_nothing_is_possible_before_an_accepted_read` also checks that a claim window in business days opens nothing.
  The case page's reading card says the read terms in the new shapes (one new test in `web/template_claim_ui.test.cjs`).
  One real run on version 3 (build tb_482574, 7 of 7 terms) went to USD 6,000.00 outstanding on HGS-INV-2026-12-2391.
- No vendor named in package code (GitHub run 42945120731: `tests/test_vendor_requirements_89.py` ›
  `test_new_vendor_name_reaches_shadow_with_useful_drafts_and_no_vendor_code`). The case workspace's catalog
  installation id and its authored engine controls moved from `uptime/template_claims.py` into data:
  `fixtures/template_builder_demo/evidence/halcyon-a/catalog.json` (`vendor_id`, `controls`, `control_base`, validated
  at load). It is outside the inputs' SHA-256 set, so case workspaces made before it reopen with `--resume` unchanged
  (checked on the last real run's workspace: same installation id, same applied credit). One docstring line in
  `uptime/template_agreements.py` no longer names the sample's form. The test itself is unchanged.

## Template builder version 3.1: choices rest on the contract's phrase (November 11)

Shapes: `docs/demo/TEMPLATE-BUILDER.md`, "Version 3.1". `CHOICE_WORDS` removed from `uptime/template_rules.py`
(and with it the plural defect); `value_in_sentence` takes the contract's `phrase` for a choice; readers give it, agree
on (option, phrase), the rule's map is pruned to vouched-for phrases, `reproduce` requires the readers' phrase, Jev is
asked about it. Numeric checks and every threshold unchanged. Build terms gain `phrase`/`rule_phrase` (choices) and
readers gain `phrase`; reading terms, `approved_readings()`, `reading.agreement` and `template_agreements.evaluate` are
unchanged. The page shows the contract's words in a choice term's row.

Existing tests changed in `tests/test_template_builder.py`:
- helpers `reader_item`, `reader_terms` (and new `phrase_for`): fake readers give the phrase the good rule captures.
- `test_value_in_sentence_digits_words_and_choices`: the two choice assertions pass the phrase; the negative
  `refund` case (option word absent) became "no phrase given" and "phrase absent from the sentence".
- `test_a_read_whose_value_is_not_in_its_sentence_is_refused`: the builder's extra map entry is now pruned, so the read
  is still REFUSED but by `complete` ("6 of 7") instead of `value_in_sentence`; the pruned map is asserted.
- `test_jev_questions_ask_what_the_sentence_literally_says`: choice questions start "Does this sentence, in the
  words …", so the prefix asserted is "Does this sentence"; the count (8) is unchanged.
New tests: 8 in `tests/test_template_builder.py` (four phrases the old list refused, a phrase not in its sentence,
agreement and Jev on the phrase, a rule capturing other words, a choice without a phrase), 1 in
`web/template_builder.test.cjs`.

### Fresh public SLAs and the re-run (November 11)

No engine change after `46d1968` except one docstring in `uptime/template_rules.py` (its example phrases removed so no
vendor wording sits in `uptime/`; behaviour unchanged). No existing test changed. `scripts/evaluate_public_slas.py`
gains `--set fresh` (a second source list), hashes choice phrases (`phrase`, `rule_phrase`) as it hashes quotes, and
its scoring reads the key file named in the results. New files: `fixtures/template_builder_public/sources_fresh.json`,
`key_fresh.json` (written and committed before the run; one recorded change after it),
`results/fresh-20261111T021719Z.json` (fresh pages) and `results/20261111T022756Z.json` (re-run of the first thirteen).
The two new results files had their choice phrases hashed after the run, before commit. Tables in
`docs/demo/TEMPLATE-BUILDER-PUBLIC-SLAS.md`.
- Exact wording about the read (item 5): "with no model call" was in `web/template_claim_ui.js` (the case page's first
  line) and in the case projection's document description in `uptime/template_claims.py`. Both now say the values were
  read by fixed rules and no model read or computed a value; a separate line, from the reading's own record
  (`jev_template` and its `template_match` guard), says Jev confirmed the document follows the template at N%, or that
  Jev was not asked, and that no Claude call took part. `model_calls` is the reading's own, no longer a constant 0.
- The agreement card once a claim exists (item 2): with a claim case opened for the reading, the card on the build page
  shows the case's latest recorded stage and its amount in the figure ("Credit", "Claim stage: Applied to bill") and in
  the foot; with no case it is drawn exactly as before. One amount, read-only from `GET /api/template-claims`.
- Counters, Cases and Activity (item 3): `GET /api/template-claims` (read-only) lists each opened case with its vendor,
  claim id, stage, its steps' authority kinds and states, and its history. The portfolio's "Who is doing the work"
  counts those steps with the same `stepLegend` it uses for the workspace case; Cases lists each case with its vendor;
  Activity adds each case's steps and history under "<vendor> · <month> claim". Nothing is written to the main
  workspace and no amount is added across cases.
- Changed existing tests (mine, from this branch): `web/template_claim_ui.test.cjs` › `the reading card says fixed
  rules, the template, who built it and the approving account; never calls code an agent` expects the new first line
  and the Jev line; `tests/test_template_claims.py` › `test_whole_path_to_the_credit_applied_once_on_the_next_invoice`
  takes `model_calls` and `jev_template` from the stand-in's reading record (the stand-in's `get` now returns one) and
  checks the listing. New tests: two in `web/template_claim_ui.test.cjs` (the card following the case; counters and
  Cases).

### The reader prompt's example phrases (coordinator, November 10, 20:35 PST)

The choice-phrase fix (`46d1968`) gave the readers three example phrases. Two, "monthly billing cycle" and "against
future payments", were AWS's wording from the first set of public pages. The fix was committed before the fresh pages
were searched for (the agent's own record: commit at 02:15:40 UTC, first search at 02:15:47 UTC), but three of the
fresh pages (Ably, Neon, Upstash) use the same words, as SLAs often copy AWS's, so those examples handed a reader
part of those pages' answers. They are replaced with three invented phrases that are in none of the 26 cached pages
and none of the sample or held-out contracts: "in any one calendar quarter", "returned to you as a refund", "kept as
a balance on your account". Nothing else in the prompt, the checks or the thresholds changed.

- New test: `tests/test_template_builder.py` ›
  `test_the_reader_prompt_examples_are_in_no_sample_or_held_out_contract` (the cached public pages are outside the
  repository, so the test covers the 29 contract texts under `fixtures/template_builder_demo/` and
  `fixtures/template_builder_heldout/`).
- No existing test changed.
- One docstring sentence in `uptime/template_agreements.py` reworded (the template reads no time zone).
- The fresh-pages table in `docs/demo/TEMPLATE-BUILDER-PUBLIC-SLAS.md` was measured with the old examples; a re-run
  with the new ones is labelled as such there.

### Fresh pages re-run with invented prompt examples (November 11, evening)

Merged `work/submission-integration-20261109` (08dd0b7, which replaced the reader prompt's three example phrases with
invented ones); the merge fast-forwarded with no conflict. No engine, prompt, check or threshold change on this branch.
One re-run of the 13 buildable fresh pages from the cache (57 Claude calls, 77 Jev calls):
`fixtures/template_builder_public/results/fresh-20261111T043341Z.json`, with choice phrases hashed at run time. Docs:
`docs/demo/TEMPLATE-BUILDER-PUBLIC-SLAS.md` says beside the second table which examples were AWS's wording and which
fresh pages contain them, adds the re-run as a fourth table labelled as a check rather than a clean measurement, with a
page-by-page comparison, and adds to the limits that a claim window's starting point is not a term (and is not
scored). `fixtures/template_builder_demo/evidence/README.md` and `.../halcyon-a/README.md`: "nine read terms" is now
"seven". No test changed.
