# Demo line changes (`demo/film-20261110`)

This line is for the film recorded on November 10, 2026. For it the owner lifted three limits: the side panel may say a service credit may apply to a Ramp bill, the extension may show a toolbar badge, and Uptime may post a note to the bill in Ramp. Everything else stands: nothing here makes a write to Ramp by itself, and every amount, stage and match on the matched page is the server's.

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

No assertion about money, authority or what reached Ramp was weakened. No Python test was changed.
