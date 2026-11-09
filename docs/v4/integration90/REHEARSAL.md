# Final two-minute rehearsal

**Owner:** integration owner (W8). **Purpose:** the continuous script Ronok records for the November 10 deadline. It folds in the W7 screen timeline ([PRESENTER-REHEARSAL-90.md](../PRESENTER-REHEARSAL-90.md)) and the freshest Ramp evidence. The state of each check is in the [rehearsal record](#rehearsal-record) at the end. Nothing has been filmed yet, and no person has run this against a stopwatch.

The CalyxQuay review **cannot be performed live again**: its grant is COMPLETED and the adapter is REVOKED at revision 9. The presenter shows the recorded history instead.

## Pre-filming checklist (about 5 minutes)

1. **Serve the tested build from a frozen checkout**, never from a worktree other agents are editing. The presentation listener and its directory are listed in [Local sessions](#local-sessions) once prepared. To prepare a new one:
   ```sh
   uv sync --locked
   uv run --locked python scripts/setup_northwind.py \
     --directory "$HOME/.local/share/uptime-engineering/runtime/northwind-presentation-$(date +%m%d%H%M)" \
     --origin http://127.0.0.1:8776 --serve
   ```
   Open http://127.0.0.1:8776 and sign in as `scripted-test-reviewer` with that directory's `scripted-reviewer.jwk`. This account is the scripted walkthrough reviewer, not a person. Keep the key out of chat and Git.
2. **Check the opening screen.** **Needs attention** must list, in order:
   - File the January 2026 claim before the deadline
   - Approve the claim packet before it is filed
   - Review invoice NW-2026-03 before payment
   - Complete March 2026 usage evidence
   - Next step: Approve January claim
3. **Ramp tab:** demo bill `f74ba12c-95d0-582d-9f62-26d8057d1d37` in demo.ramp.com, showing the person-posted note (comment `376563cf…`). Do not post, edit or approve anything. Optional: the W1 read-only pre-filming check (no write) confirms the note is still there and the bill is unchanged.
4. **Review tab:** the recorded CalyxQuay review, either the 8777 listener's read-only vendor history or [the receipt](../evidence/local-review-88/recorded-review-20261109.json). Do not sign in to act there, and never read or use the reviewer key.
5. **Fallback open in a background tab:** the saved screens in `docs/v4/evidence/finance-guide-90/` and the receipts listed under [Fallback](#fallback).

## Script

About 260 spoken words. Measured interaction time for all eleven steps plus two guide questions is 8.2 s ([timing receipt](../evidence/finance-guide-90/screen-walkthrough-timing.json)), so most of the two minutes is speech.

| Time | Screen and action | Say |
|:---|:---|:---|
| 0:00–0:15 | Northwind view; point to **Needs attention** | "Uptime checks contract terms against financial records. **This contract and its usage records are authored for the demo.** Uptime reads the case and says what needs a person: a filing deadline, an approval, a price review and missing March usage." |
| 0:15–0:35 | January row → **Calculation inputs**, then **Read clause**; glance at February and March | "$12,000 fee, 135 eligible minutes, 20 percent: $2,400. Each number comes from the clause shown. February is below the threshold. March isn't ineligible: its usage evidence is incomplete, so no amount exists yet." |
| 0:35–1:05 | Run the eleven steps: approve, file, receive response, attach log, verify log, approve response, send response, receive decision, **Post to Local ledger**, receive next invoice, apply credit | "The vendor asks for a log. We attach it, verify it separately and approve a response, and the credit is awarded. Each step runs once; repeating it changes nothing." |
| 1:05–1:20 | Stage figures → **Bill reconciliation** → **March price review** | "These are stages of one credit, not amounts to add. Applied to April, $11,000 becomes $8,600. **This application is in Local ledger, not money recovered in Ramp.** The March $1,000 price finding stays open and separate." |
| 1:20–1:35 | **Ask about this case**: "Did the credit reach Ramp?", then "Should we dispute the March invoice?" | "The guide answers only from this case's records and cites them. It says the credit is in Local ledger, and it declines to make the dispute decision for us." |
| 1:35–1:50 | Ramp tab: the note on bill `f74ba12c…` | "This is a real Ramp demo bill. A teammate posted this note and we confirmed it through Ramp's API; Uptime did not post it. **The bill needs its own agreement; this authored contract is not evidence against it.**" |
| 1:50–2:00 | Review tab: CalyxQuay history | "New vendors arrive as rules that run in shadow first. In a separate local workspace, Ronok's enrolled reviewer account accepted the interpretation, approved, activated and rolled back one version, so nothing is active. The steps before that were scripted. Wider promotion is still release-gated." |

If someone other than Ronok presents, say "Ronok's enrolled account" rather than "Ronok clicked": the record authenticates the account, not the person at the keyboard.

## Never say

- "Recovered" or "saved" for the $2,400, or that anything reached Ramp, stopped a payment or held a bill.
- "Post to Ramp": the destination is Local ledger.
- That the $1,000 is a credit, or that the stages add up.
- That the Northwind contract governs the Ramp bill. The W1 lineage explicitly refuses that link (`NO_GOVERNING_AGREEMENT`, all money null).
- That CalyxQuay is active, that revisions 1–5 are Ronok's decisions, or that the local review is release certification.
- That the guide uses a model. It answers from fixed, cited case facts; D10 and D12 keep it read-only, with no case data sent to a model.
- Any accuracy or ROI number. The onboarding evaluation's first attempts accepted 0 of 4 supported extractions, and the D13 bar is not met.

## If asked (not in the two minutes)

- **"A status page isn't customer proof."** Show the W5 public status receipt ([public-status-live-91a.json](../evidence/evidence-custody-90/public-status-live-91a.json)). Twilio's real published incident `fm5fk85h6glc` was delivered as a signed status record, and the claim stayed INSUFFICIENT_EVIDENCE with a null amount until customer impact is shown. Disclosure: "the claim account is a local test scope; the outage is Twilio's real published incident." To re-run it, use `scripts/rehearse_public_status.py` in its own harness-hosted workspace, never the Northwind presentation workspace. Running it live needs one public HTTPS GET.
- **"How do new vendors get added?"** Point to the adapter requirement card (decision 90) and the D05 decision: Uptime selects among supported rule families, and a person approves before activation. Auto-selection is not built yet.

## Fallback

Each fallback is offline and repeatable, and none performs a native or model action.

1. **Full action path over loopback HTTP**, every step read back and duplicates checked: `uv run --locked python scripts/rehearse_northwind.py --directory <fresh directory> --receipt <receipt.json>`
2. **The same screens in real Chrome:** `uv run --locked pytest -q tests/test_finance_browser_90.py`
3. **Saved screens and receipts:** `docs/v4/evidence/finance-guide-90/finance-view-final-1360.png` (and `-390.png` for narrow screens), the [timing receipt](../evidence/finance-guide-90/screen-walkthrough-timing.json), [Northwind socket proof](../evidence/demo-path-87/northwind-socket.json), [Ramp note read-back](../evidence/demo-path-87/human-ramp-note.json) with the [November 9 re-read](../evidence/ramp-lineage-93/live-read-20261109.json) and [bill lineage](../evidence/ramp-lineage-93/lineage-f74ba12c.json), and [CalyxQuay review](../evidence/local-review-88/recorded-review-20261109.json).
4. **If the Ramp tab fails**, show the read-back receipts. Never repost, retry native posting, or use another credential, model or browser to act in Ramp.

## Local sessions

Filled in when the presentation listener is prepared from the frozen tested build; see the rehearsal record.

## Rehearsal record

| Check | Result | Evidence |
|:---|:---|:---|
| Offline deterministic replay | Passed in 2.43 s on `37d73f2`: simulated award 100.00, recorded 100.00, applied 50.00, disputed 20.00; onboarding SHADOW→APPROVED→ACTIVE→REVOKED; actual customer recovery null | [receipt](../evidence/integration-90/rehearsal-offline.json) |
| Served Northwind flow across a hard kill and restart | Passed: state equal after restart, duplicate replay unchanged, April 11,000.00 → 8,600.00 | `tests/test_release_probes_gent8.py` |
| W7 screens in headless Chrome, all 11 steps plus 2 guide questions | 8.2 s of interaction on `5312938`; initial attention list as above | [timing receipt](../evidence/finance-guide-90/screen-walkthrough-timing.json) |
| Human-posted Ramp note | Verified November 7 by two read-only API reads; re-observed in a complete thread read at 2026-11-09 11:02 UTC; bill unchanged (USD 840, OPEN, approval PENDING, no applied credit) | [read-back](../evidence/demo-path-87/human-ramp-note.json), [re-read](../evidence/ramp-lineage-93/live-read-20261109.json) |
| CalyxQuay recorded review | REVOKED at revision 9; grant COMPLETED | [receipt](../evidence/local-review-88/recorded-review-20261109.json) |
| Rehearsal on the round-2 integration build | Pending the round-2 suite | — |
| Timed run by a person | **Not done** | Needs the presenter and a stopwatch |
| Film | **Not done**; Ronok decides when to record | — |
