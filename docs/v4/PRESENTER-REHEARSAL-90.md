# Finance screen walkthrough for the two-minute presentation (W7)

This is the screen portion of the rehearsal. The integration owner keeps the final continuous two-minute script and folds this in. Product screens use ordinary labels. The authored-data and authority disclosures below are spoken, not shown on screen.

## What the audience must leave with

| Shown | What it is | What it is not |
| --- | --- | --- |
| Northwind contract, usage and invoices | An authored walkthrough package run through the existing engines | A real customer's agreement or usage |
| January $2,400 credit applied to the April invoice ($11,000 → $8,600) | A Local ledger posting and application, read back locally | Money recovered in Ramp, a Ramp credit or a vendor payment |
| March $1,000 price finding | An open finding against the March invoice | A credit, an award or part of the $2,400 |
| March service credit | Undetermined because usage evidence is missing | Ineligible |
| Ramp bill `f74ba12c-95d0-582d-9f62-26d8057d1d37` note | A note a person posted, confirmed by API read-back | An Uptime API write, a payment hold or evidence that Northwind terms apply to that bill |
| CalyxQuay review | A recorded review in a separate local workspace. Revisions 6–9 are under the `ronok-tanvir` account: interpretation accepted, tests approved, activated, rolled back. Final state REVOKED at revision 9; nothing active. Revisions 1–5 are scripted preparation. | A current activation, a commercial approval, or the scripted CalyxQuay record shown inside the Northwind workspace |

## Before presenting

1. Use the prepared presentation listener at http://127.0.0.1:8776. It serves the frozen demo build `fde492c` from its own clean checkout; [the integration rehearsal record](integration90/REHEARSAL.md) has the exact paths and checks. Never reuse or overwrite the real Ramp workspace. To prepare another fresh workspace, run this from that frozen checkout into a new directory:
   ```sh
   uv run --locked python scripts/setup_northwind.py --directory "$HOME/.local/share/uptime-engineering/runtime/northwind-presentation-$(date +%m%d%H%M)" --serve
   ```
   Sign in as `scripted-test-reviewer` with that directory's `scripted-reviewer.jwk`. This is the scripted walkthrough reviewer, not a person.
2. In a second tab, open the Ramp demo bill: https://demo.ramp.com/bill-pay/bills/list/f74ba12c-95d0-582d-9f62-26d8057d1d37. Do not post, edit or approve anything.
3. For CalyxQuay, open the recorded receipt `docs/v4/evidence/local-review-88/recorded-review-20261109.json`. If the 8777 listener is still serving, you can show its read-only vendor review screen. Do not sign in to act, and never read or use the reviewer key.
4. Check the Northwind view on the presenting screen. "Needs attention" must list, in order:
   - File the January 2026 claim before the deadline
   - Approve the claim packet before it is filed
   - Review invoice NW-2026-03 before payment
   - Complete March 2026 usage evidence
   - Next step: Approve January claim

## Screen timeline

The timed browser receipt on `5312938` measured 8.2 seconds of pure interaction for all eleven steps and two guide questions (an earlier run on the pre-rebase tree measured 12.4 seconds). That leaves the rest of the two minutes for speaking. Times below are suggestions; the integration owner's script controls.

| Time | Screen action | Spoken line |
| --- | --- | --- |
| 0:00–0:15 | Northwind view. Point to **Needs attention**. | **Disclosure 1:** "This contract and its usage records are authored for the demo." "Uptime reads the case and says what needs a person: a filing deadline, an approval, a price review and missing March usage." |
| 0:15–0:35 | January row → **Calculation inputs**; then **Read clause**. | "$12,000 fee, 135 eligible minutes, two completed shortfall steps, 20 percent: $2,400. Each number comes from the clause shown. February is below the threshold. March isn't ineligible — its usage evidence is incomplete, so no amount exists yet." |
| 0:35–1:05 | Click the eleven recovery steps in order: approve, file, receive response, attach log, verify log, approve response, send response, receive decision, **Post to Local ledger**, receive next invoice, apply credit. | "The vendor first asks for a log. We attach and verify it, approve a response, and the credit is awarded. Each step runs once; a repeat changes nothing." |
| 1:05–1:20 | Stage figures, then **Bill reconciliation** and **March price review**. | "These are stages of one credit, not amounts to add. Applied to April: $11,000 becomes $8,600." **Disclosure 4:** "The credit application shown here is in Local ledger, not money recovered in Ramp." "The March $1,000 price finding stays open and separate." |
| 1:20–1:35 | **Ask about this case**: type "Did the credit reach Ramp?" and press Enter, then type "Should we dispute the March invoice?" and press Enter. Type both on the demo build `fde492c`, which has no suggested questions. A listener rebuilt from `9b9092f` or later also offers "Did the credit reach Ramp?" as a one-click suggestion under **Try:** | "The guide answers only from this case's records and cites them. It says the credit is in Local ledger, and it declines to make the dispute decision for us." |
| 1:35–1:50 | Switch to the Ramp tab; show the note on bill `f74ba12c…`. | **Disclosure 3:** "The connected Ramp bill needs its own agreement; this authored contract is not evidence against it." "A teammate posted this note in Ramp, and we confirmed it through Ramp's API. Uptime did not post it." |
| 1:50–2:00 | CalyxQuay receipt or the 8777 review history. | **Disclosure 2:** "In a separate local workspace, Ronok Tanvir's reviewer account recorded the CalyxQuay review: interpretation accepted, tests approved, activated, then rolled back, so nothing is active. The preparation before that was scripted." |

## Screens to use and screens to avoid

On a fresh Northwind workspace (checked at 390 px and 1360 px; no sideways scroll, no page errors), these screens use ordinary wording:

- **Contract worklist** (the Northwind finance view)
- **Ramp records**
- **Vendor intake & versions**
- **Correspondence & disputes**

Do not open these during the recording:

- Case ledger · Advanced
- Onboarding lab
- Integrations
- Advanced workflows
- Regression comparison
- Policies

They show the older seeded comparison portfolio and offline provider, labelled with "synthetic", "fixture" and "replay" wording, and the policy text mentions the simulator. The labels are accurate, but those records are not part of the Northwind walkthrough.

## Never say

- "Recovered" or "saved" for the $2,400 in Ramp.
- That the $1,000 is a credit, or that stages add up.
- "Post to Ramp" — the destination is Local ledger.
- That Uptime posted the Ramp note or held a payment.
- That CalyxQuay is active, or that the Northwind workspace's CalyxQuay record is Ronok's review.
- That the guide used a model. It answers from fixed, cited case facts. Model wording depends on pending decisions D10 and D12.

## Deterministic fallback

Use these if a live element fails. Each one is offline and repeatable, and none performs a native or model action.

1. **Full action path over loopback HTTP.** Each step is read back, and a duplicate is confirmed unchanged. Run against a fresh directory:
   ```sh
   uv run --locked python scripts/rehearse_northwind.py --directory <fresh-directory> --receipt <receipt.json>
   ```
2. **The same screens in real Chrome.** Covers sign-in, actions, expired-session recovery, keyboard use and the 390 px layout:
   ```sh
   uv run --locked pytest -q tests/test_finance_browser_90.py
   ```
3. **Recorded receipts.** Show these instead of live screens:
   - `docs/v4/evidence/finance-guide-90/screen-walkthrough-timing.json`, with its two screenshots
   - `docs/v4/evidence/demo-path-87/northwind-socket.json`
   - `docs/v4/evidence/demo-path-87/human-ramp-note.json`
   - `docs/v4/evidence/local-review-88/recorded-review-20261109.json`
4. **If the Ramp tab fails**, show the read-back receipt. Never repost, retry native posting, or use another credential, model or browser to act in Ramp.

## Accessibility checks the presenter can rely on

- Every control is a native button, link or form field. Tab order follows the page.
- **Show details** and **Source** buttons move focus to the cited section heading.
- In the guide, Enter submits; answers are announced politely.
- At 390 px width the page does not scroll sideways.
- An expired session returns to sign-in without repeating an action. Signing in again shows the same next step.
