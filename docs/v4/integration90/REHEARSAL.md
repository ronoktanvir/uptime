# Final two-minute rehearsal

**Owner:** W8 (integration owner). **State on November 9, 2026:** the script is rehearsed against the verified services but **not filmed**, and a person has not yet run it against a stopwatch. Offline replay receipt: [rehearsal-offline.json](../evidence/integration-90/rehearsal-offline.json). Served-flow restart probe: `tests/test_release_probes_gent8.py`.

This supersedes the 101–120 second row in [DEMO.md](../DEMO.md). The CalyxQuay review cannot be performed live again: its grant is COMPLETED and the adapter is REVOKED at revision 9. The presenter shows the recorded history instead.

## Before the clock starts (5 minutes)

1. Fresh Northwind workspace (new directory each time; key stays in that directory):
   ```sh
   uv sync --locked
   uv run --locked python scripts/setup_northwind.py \
     --directory "$HOME/.local/share/uptime/northwind-session-002" \
     --origin http://127.0.0.1:8776 --serve
   ```
   Open http://127.0.0.1:8776, sign in as `scripted-test-reviewer` with `scripted-reviewer.jwk` from that directory.
2. Ramp tab: the verified demo bill `f74ba12c-95d0-582d-9f62-26d8057d1d37` in demo.ramp.com, showing the person-posted note (comment `376563cf…`, 2026-11-08 01:46:45 UTC). Optional read-only confirmation: `scripts/verify_ramp_comment.py` as in [DEMO-PATH-87](../DEMO-PATH-87.md). No write is made.
3. Review tab: http://127.0.0.1:8777/#vendors (Ronok's workspace) showing CalyxQuay history revisions 1–9. If that listener is down, open [the recorded-review receipt](../evidence/local-review-88/recorded-review-20261109.json) instead. Do not restart it with a new exception.
4. Fallback ready: `scripts/rehearse_northwind.py` against the fresh workspace, plus the saved complete screen `docs/v4/validation/northwind/browser-applied.png`.

## Script (about 260 spoken words)

| Time | Screen and action | Say |
|:---|:---|:---|
| 0:00–0:10 | Northwind contract review | "Uptime checks contract terms against financial records. This contract and its usage records are authored for the demo." |
| 0:10–0:28 | Expand the March amendment, the price finding and the three monthly results | "March was billed 12,000 against 11,000, so a 1,000 price finding stays open. January's outage earns 20 percent of 12,000: 2,400. February is ineligible. March is missing required evidence, so Uptime says unknown instead of guessing." |
| 0:28–0:43 | Ramp tab: the person-posted note on the real bill | "This is a real Ramp demo bill. A teammate posted this evidence request, and the API read it back with the same ID. It asks for the agreement; it does not stop payment, and this authored contract is not evidence against this bill." |
| 0:43–1:18 | Approve/file January → receive response → attach log → verify log → approve and send response | "Filing is signed and idempotent. The vendor's reply asks for proof; the log is verified separately before the follow-up goes out." |
| 1:18–1:41 | Receive award → post to Local ledger → receive April invoice → apply credit | "The 2,400 award is recorded and applied: April's 11,000 invoice now shows 8,600. This is the Local ledger, not money recovered in Ramp, and the March 1,000 stays separate. We never add the stages together." |
| 1:41–2:00 | Review tab: CalyxQuay history | "New vendors arrive as declarative rules that run in shadow first. Here, Ronok's enrolled account accepted the interpretation, approved, activated and rolled back one version under a 48-hour local permission. The earlier entries are scripted setup. Promotion beyond this local review is still release-gated." |

Say "Ronok's enrolled account" rather than "Ronok clicked" unless Ronok is presenting and confirms he performed the steps; the record authenticates the account, not the person at the keyboard.

## Do not say

- That Uptime wrote to Ramp, stopped a payment, or recovered money in Ramp.
- That the Northwind contract governs the Ramp bill shown.
- That the revisions 1–5 entries are Ronok's decisions, or that the local review is release certification.
- Any accuracy or ROI number. Independent unseen-vendor and reply evaluations are paused (D13).

## Rehearsal record

| Check | Result | Evidence |
|:---|:---|:---|
| Offline deterministic replay | Passed in 2.43 s: price exposure 7,500.00 hypothetical; simulated award 100.00; recorded 100.00; applied 50.00; disputed 20.00; onboarding SHADOW→APPROVED→ACTIVE→REVOKED; actual customer recovery null | [receipt](../evidence/integration-90/rehearsal-offline.json) |
| Served Northwind 11 actions across a hard kill and restart | Passed: state equal after restart, duplicate replay unchanged, April 11,000.00 → 8,600.00 | `tests/test_release_probes_gent8.py` (integrated from the verification lane) |
| Human-posted Ramp note | Verified November 7 by two read-only API reads | [read-back](../evidence/demo-path-87/human-ramp-note.json) |
| CalyxQuay recorded review | REVOKED at revision 9; grant COMPLETED | [receipt](../evidence/local-review-88/recorded-review-20261109.json) |
| Timed run by a person | **Not done** | Needs the presenter's machine and a stopwatch |
| Film | **Not done** for Northwind; the historical 120-second film shows an older replay | [DEMO.md](../DEMO.md) |
