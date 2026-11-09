# Test changes — review requirements on the vendor card (W7, `work/requirements-card-90`)

agent2 (W3) asked for this under decisions 90 and 97. The vendor card now has a read-only "Review requirements" section. It loads `GET /api/vendors/{id}/requirements` on request and offers no action control.

The section renders:

- each element and its status, with any requirement text verbatim;
- the cited clause ids, with the clause quotes taken from the vendor's own manifest;
- the reviewer's remaining tasks, verbatim;
- how the rule family was chosen, including each losing family's refusal;
- the generated drafts, collapsed and labelled "Generated drafts (not independent tests; placeholder fee)";
- the draft-overlap warning, when present.

`familyRefusal()` moved unchanged from inside the proposal generator to the shared scope, so both screens use one renderer.

**No existing test changed.** New tests:

| File | Count | Purpose |
| --- | ---: | --- |
| `tests/test_requirements_card_ui_95.py` (with `tests/helpers/render_requirements.cjs`) | 1 | The real monthly requirements payload and vendor detail, from W3's own fixture, rendered by the real `web/v4_ui.js`. Checks every element, cited quotes in order, the requirement lists verbatim, the selection method, the drafts notice, amounts and fee, the read-only note, GET-only calls and inert markup. |
| `tests/helpers/requirements_card.test.cjs` | 3 | A review-required element. An unknown element or status. A missing clause text. An ambiguous selection with a losing family's refusal. No drafts. An overlap warning. Inert markup. A non-automatic version. A 401 and a failed read. No control without a readable revision. |

Results:

- JavaScript: **97/97**
- `test_requirements_card_ui_95`, `test_vendor_requirements_89`, `test_vendor_family_selection_89`, `test_vendor_model_jobs_browser`, `test_vendor_auth83`, `test_advanced_companion`, `test_v4_authority_browser`, finance and workspace browser tests: **59 passed, 1 warning in 40.51s**
- Fresh Northwind workspace at 390 px: both vendor panels open with no sideways scroll, no page errors and no demo wording

Full suite: integration round 4b on a fresh clone of `5d8af56` (which contains `310c918`): **4636 passed, 1 warning in 417.24s (0:06:57)**, JS 97/97. Receipt: `docs/v4/evidence/integration-90/verification-5d8af56.json`. The follow-up `e527f8f` was merged after `5d8af56`; the next integration round covers it.

## Follow-up: sixth element and null selection

After merge `5d8af56`, agent2's `submission_channel` element (`7906764`) and a null `family_selection` are pinned by one added test function in my own file, `tests/helpers/requirements_card.test.cjs`: "a submission channel element renders generically, and a null family selection adds no section". No existing assertion changed.

On the integration head with the sixth element, `test_requirements_card_ui_95` and `test_vendor_requirements_89` pass: **17 passed, 1 warning in 3.54s**. The real payload renders "Submission channel". JavaScript: **98/98**.

