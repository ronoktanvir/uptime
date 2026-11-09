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
3. **Ramp tab:** demo bill `f74ba12c-95d0-582d-9f62-26d8057d1d37` in demo.ramp.com, showing the person-posted note (comment `376563cf…`). Do not post, edit or approve anything. Optional read-only checks, neither of which writes anything:
   - W1 Ramp check: `RAMP_ENV=sandbox UPTIME_RAMP_CREDENTIAL_FILE=~/.config/uptime/ramp-demo-native.json python scripts/ramp_prefilm_check.py --output-dir ~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109`. Exit 0 prints `PREFILM PASS …`. The first run, at 12:36 UTC, passed with no failures and 0 writes ([summary](../evidence/ramp-lineage-93/prefilm-20261109T123606Z.json)). It refuses to run under CI.
   - W9 machine check: `uv run --locked python scripts/operations_preflight.py` (disk, sandbox-only Ramp environment, loopback-only ports, no tunnel, workspace health, a verified backup). It returned READY on this Mac. Night-before steps are in [DEMO-MACHINE-90.md](../DEMO-MACHINE-90.md).
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

## Screens to use and avoid while recording

From the W7 sweep of a fresh workspace at 390 px and 1360 px: no sideways scroll and no page errors on any route.

- **Use:** Contract worklist (finance view), Ramp records, Vendor intake & versions, Correspondence & disputes.
- **Avoid:** Case ledger · Advanced, Onboarding lab, Integrations, Advanced workflows, Regression comparison, Policies. They show the older seeded comparison portfolio and simulator wording. Those labels are accurate but off-message for this script.

## Never say

- "Recovered" or "saved" for the $2,400, or that anything reached Ramp, stopped a payment or held a bill.
- "Post to Ramp": the destination is Local ledger.
- That the $1,000 is a credit, or that the stages add up.
- That the Northwind contract governs the Ramp bill. The W1 lineage explicitly refuses that link (`NO_GOVERNING_AGREEMENT`, all money null).
- That CalyxQuay is active, that revisions 1–5 are Ronok's decisions, or that the local review is release certification.
- That the guide uses a model. It answers from fixed, cited case facts; D10 and D12 keep it read-only, with no case data sent to a model.
- That the unseen-vendor onboarding (D05) succeeded or will succeed. It has not run, and a correct refusal is the likely outcome.
- Any accuracy or ROI number. The onboarding evaluation's first attempts accepted 0 of 4 supported extractions, and the D13 bar is not met.

## If asked (not in the two minutes)

- **"A status page isn't customer proof."** Show the W5 public status receipt ([public-status-live-91a.json](../evidence/evidence-custody-90/public-status-live-91a.json)). Twilio's real published incident `fm5fk85h6glc` was delivered as a signed status record, and the claim stayed INSUFFICIENT_EVIDENCE with a null amount until customer impact is shown. Disclosure: "the claim account is a local test scope; the outage is Twilio's real published incident." To re-run it, use `scripts/rehearse_public_status.py` in its own harness-hosted workspace, never the Northwind presentation workspace. Running it live needs one public HTTPS GET.
- **"Where did this clause come from?"** Show the W5 custody receipt ([document-custody-91.json](../evidence/evidence-custody-90/document-custody-91.json)). A read-only audit re-sliced 77 of 77 stored citations, across 5 adapter versions in the presentation and review workspaces, from the stored source text at the stated offsets, with matching document and quote hashes. It proves where the words are, not that the interpretation is right.
- **"What happened in the dispute?"** Open the **Dispute record** panel on the Northwind case. It shows the vendor's missing-evidence request, the cure and the reported award, each with its checks. It shows only Claimed and Awarded; posting and application are on the bill reconciliation screen.
- **"How do new vendors get added?"** Point to the adapter requirement card (decision 90) and D05: on the integration branch, Uptime selects the rule family from the source itself (decisions 97 and phase 2), and a person still approves before activation. The demo build `fde492c` predates phase 2. The unseen-vendor proof has not run. Do not promise that the unseen vendor will onboard successfully. Most public SLAs carry maintenance or force-majeure exclusions, which the monthly family refuses under D07. The likely honest outcome is NO_SUPPORTED_FAMILY with the exact passage cited: a correct refusal, not a promoted adapter.

## Fallback

Each fallback is offline and repeatable, and none performs a native or model action.

1. **Full action path over loopback HTTP**, every step read back and duplicates checked: `uv run --locked python scripts/rehearse_northwind.py --directory <fresh directory> --receipt <receipt.json>`
2. **The same screens in real Chrome:** `uv run --locked pytest -q tests/test_finance_browser_90.py`
3. **Saved screens and receipts:** `docs/v4/evidence/finance-guide-90/finance-view-final-1360.png` (and `-390.png` for narrow screens), the [timing receipt](../evidence/finance-guide-90/screen-walkthrough-timing.json), [Northwind socket proof](../evidence/demo-path-87/northwind-socket.json), [Ramp note read-back](../evidence/demo-path-87/human-ramp-note.json) with the [November 9 re-read](../evidence/ramp-lineage-93/live-read-20261109.json) and [bill lineage](../evidence/ramp-lineage-93/lineage-f74ba12c.json), and [CalyxQuay review](../evidence/local-review-88/recorded-review-20261109.json).
4. **If the Ramp tab fails**, show the read-back receipts. Never repost, retry native posting, or use another credential, model or browser to act in Ramp.

## Local sessions

Prepared November 9, 2026, at about 13:03 UTC (5:03 AM Pacific):

- **Presentation, http://127.0.0.1:8776**: served from the frozen demo build `fde492c` in the detached, clean checkout `$HOME/.local/share/uptime-engineering/presentation-fde492c`. The fresh, unfiled workspace is `$HOME/.local/share/uptime-engineering/runtime/northwind-presentation-fde492c`. Sign in as `scripted-test-reviewer` with that directory's `scripted-reviewer.jwk`. Its opening attention list matches the pre-filming checklist exactly. It runs in the Claude desktop terminal tab "Northwind presentation 8776 (demo build fde492c)"; stop it with Ctrl-C there. To restart without resetting state, run the same `setup_northwind.py` command from that checkout with `--resume`.
- **Ronok's review, http://127.0.0.1:8777/#vendors**: unchanged, served from `$HOME/uptime`. Use the read-only history only; the grant is spent.
- The earlier `northwind-presentation-87` directory is preserved and not served.

Do not run `rehearse_northwind.py` against the presentation directory; it completes all actions. Use a throwaway directory instead (see Fallback).

## Rehearsal record

| Check | Result | Evidence |
|:---|:---|:---|
| Offline deterministic replay | Passed in 2.43 s on `37d73f2`: simulated award 100.00, recorded 100.00, applied 50.00, disputed 20.00; onboarding SHADOW→APPROVED→ACTIVE→REVOKED; actual customer recovery null | [receipt](../evidence/integration-90/rehearsal-offline.json) |
| Served Northwind flow across a hard kill and restart | Passed: state equal after restart, duplicate replay unchanged, April 11,000.00 → 8,600.00 | `tests/test_release_probes_gent8.py` |
| W7 screens in headless Chrome, all 11 steps plus 2 guide questions | 8.2 s of interaction on `5312938`; initial attention list as above | [timing receipt](../evidence/finance-guide-90/screen-walkthrough-timing.json) |
| Human-posted Ramp note | Verified November 7 by two read-only API reads; re-observed in a complete thread read at 2026-11-09 11:02 UTC; bill unchanged (USD 840, OPEN, approval PENDING, no applied credit) | [read-back](../evidence/demo-path-87/human-ramp-note.json), [re-read](../evidence/ramp-lineage-93/live-read-20261109.json) |
| CalyxQuay recorded review | REVOKED at revision 9; grant COMPLETED | [receipt](../evidence/local-review-88/recorded-review-20261109.json) |
| Integration suite on the demo build | Fresh clone of `fde492c`: 4,523 passed, 1 warning in 523.01 s; 92/92 JavaScript checks; offline rehearsal, progress graph, secret scan and checklist render passed | [receipt](../evidence/integration-90/verification-fde492c.json) |
| 11-step walkthrough over real HTTP on the demo build | Passed in 5.1 s against a throwaway workspace served from the frozen checkout. Every duplicate was unchanged and every readback equal; Local ledger 2,400.00 claimed, awarded, posted and applied; April 11,000.00 → 8,600.00; authority `SCRIPTED_REVIEWER` | [receipt](../evidence/integration-90/northwind-http-fde492c.json) |
| W9 machine preflight against the live listeners | READY, with no findings. 8776, 8777 and 8780 listen on 127.0.0.1 only; both workspaces are healthy; the Ramp environment is unset; 8.4 GiB free. The workspace databases are byte-identical before and after. Disclosed side effect: the read-only open created empty SQLite `-wal`/`-shm` sidecars in `ronok-review-87`, with no data written; they were left in place, and the W9 tool is being fixed | W9 (`gen6`) report |
| Fresh presentation workspace on 8776 | Serving the demo build; opening attention list as in the checklist; no action taken | This section |
| Timed run by a person | **Not done** | Needs the presenter and a stopwatch |
| Film | **Not done**; Ronok decides when to record | — |
