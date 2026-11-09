# Role 4 — presentation interface (handoff)

**Owner:** `gent7`. **Branch:** `work/submission-ui-20261109` from `origin/main` `55ea607`. **Owns for this push:** `web/` and its tests (except `web/ramp_ui.js`, `web/ramp_ui.test.cjs` and `web/ramp_wording.test.cjs`, which agent4 owns), `uptime/workbench.py`, and browser interaction tests. Changed existing tests go in [the ledger](../TEST-CHANGES-submission-ui-20261109.md).

## (a) Findings reproduced on current source

Measured on November 9 at 13:05 PST with headless Chrome. The workspace was a fresh authored Northwind one, served on `127.0.0.1:8841`, from this branch at `55ea607`, where `web/` matches the judged `fcbeede`.

| Measure | Result |
| --- | --- |
| Primary navigation items | **13** in one rail: 8 static and 5 appended by `app.js`. There are three duplicate pairs: Vendor contracts / Vendor intake & versions (both `#vendors`), Correspondence / Correspondence & disputes (both `#disputes`), and Onboarding lab ×2 (`#onboarding`, `#lab`). |
| Workspace names on screen | **3**: "Finance workbench" (title and rail caption), "Harborline Analytics" (topbar on the finance view), and "Contract operations" (topbar on every other route). |
| Overview height, 1440×900 | **8,016 px** before any action; **8,547 px** after the 11 steps |
| Overview height, 390 px wide | **12,710 px** after the 11 steps |
| First viewport after the full flow | Four tiles, each "$2,400.00" (Claimed, Awarded, Posted to Local ledger, Applied to bill). $11,000 → $8,600 and the $1,000 March exception are not visible. |
| Raw technical text in the overview | 5 SHA-256 values, 27 ISO timestamps and `20000000/1000000% credit` (evaluator trace) after the flow; 2 hashes and 14 timestamps before |
| Clicks from sign-in to applied credit | **11** action clicks |
| Setup steps for a fresh operator (README) | 6, plus a hidden-folder reveal: `uv sync`; the setup command; open the URL; type `scripted-test-reviewer`; pick `scripted-reviewer.jwk` under `~/.local/share/uptime-engineering/runtime/<dir>/`, which macOS hides, so the picker needs ⌘⇧. first; Sign in |
| Reload | The page still reads, because the bearer session token is in `sessionStorage`. Action buttons stay enabled. Clicking one returns to sign-in and records nothing (0 intents), because the signing key was only in memory. |
| `presentationLabel` | `web/app.js:12–24` rewrites server strings such as "Simulated award" to "Awarded credit" on the advanced case ledger |

Screenshots: [1440 before](../evidence/submission-ui/before-overview-1440-initial.png) · [1440 after the flow](../evidence/submission-ui/before-overview-1440-final.png) · [390 px after the flow](../evidence/submission-ui/before-overview-390-final.png).

## (b) Navigation

Four primary destinations, all rendering existing backend state:

| Destination | Route | Content |
| --- | --- | --- |
| **Overview** | `#overview` (and the existing `#ramp`) | The outcome headline (task 3), "Needs attention", the credit lifecycle (task 5) and the next step. Without a configured workflow, it falls back to the Ramp worklist as today. |
| **Cases** | `#cases` (and the existing `#disputes`) | Claims and their correspondence, including the dispute record. The Northwind claim is reachable here. |
| **Agreements** | `#agreements` (and the existing `#vendors`) | Governing agreements and vendor coverage, with review requirements and the proposal generator |
| **Activity** | `#activity` (new) | What happened, in order: workflow history and coverage history from the workflow projection, plus automation and model-job state when roles 1 and 2 publish them (task 8) |

These move to a secondary **More** group, still one click away: Ramp records, Case ledger, Onboarding lab, Policies, Integrations, Advanced workflows and Regression comparison. The duplicates go. Every old route hash keeps working, so bookmarks and existing route-driven tests still reach their views. Ramp records stays in More because agent4 owns its rows and the Northwind workspace has no linked Ramp bill. The Overview names the destination and links to it.

One workspace name: "Harborline Analytics" (the company from the projection) in the topbar on every route, with "Uptime" as the product brand. "Finance workbench" and "Contract operations" are removed.

## (c) Sign-in setup needed from `scripts/setup_northwind.py` (agent3)

Hidden-folder trap (task 10). Requested behavior:

1. Setup writes a copy of the scripted reviewer's credential to a visible, owner-only location, `~/Uptime credentials/<workspace-directory-name>/scripted-reviewer.jwk`, with the directory at mode 0700 and the file at 0600. Setup refuses to overwrite an existing file. The file stays outside the repository and the workspace database. The copy covers only the scripted walkthrough reviewer, never a person's key.
2. Setup prints that exact path, the account name `scripted-test-reviewer` and the URL as its last lines, one per line.
3. No new route, no one-time login URL and no change to `auth*.py`.

On the browser side I will:

- say on the sign-in form which file to choose and that setup printed its location;
- accept the file by drag and drop as well as the picker;
- name the key file in errors.

Sessions (task 11): the signing key stays in memory only. A reload keeps the read session, so the pages still read. In that state every action control is disabled, with one "Sign in again to take actions" control in place of buttons that fail on click. No key goes to `localStorage`, IndexedDB, a URL or a log.

## (d) Projection fields

No new field is needed for tasks 1–7 and 9. All of these already exist in `GET /api/workspace/workflow` and are rendered as given:

- `ledger.bill.original_amount` and `outstanding_amount`
- `ledger.applied` (shown only with `record_ids.application`)
- `ledger.destination`
- `price_finding.amount`, `state` and `invoice_id`
- `ledger.claimed`, `awarded` and `posted`

The browser computes no money.

Two notes:

- `ledger.estimated` becomes null while the claim is filed and awaiting the vendor (states 2–7). The lifecycle will show Estimated from the claim month's evaluated amount (`months[i].amount` for `claim.month`), which the server already supplies, so it does not look undetermined mid-flow. If agent3 prefers a stable `ledger.estimated`, I'll switch to it.
- Rates (task 7): the human calculation lines (`months[i].calculation`) are already the main display. The raw evaluator trace moves into the inspector, and any `N/1000000%` text left in view is shown as an exact percent at the rendering boundary. Only power-of-ten denominators are converted, by shifting the decimal point; nothing else changes. A structured rate field from agent2 would replace this.

Task 8 waits on the field notes from roles 1–3 (`disputes.md`, `onboarding.md`, `ramp.md`).

## (e) Question for the coordinator

Automated browser tests start a throwaway uvicorn listener on an ephemeral loopback port (`bind(0)`) and stop it at the end of the test. My manual probes use 8841–8849 only. Please confirm the ephemeral ports in tests are acceptable, or I'll pin the fixtures to 8843–8849.
