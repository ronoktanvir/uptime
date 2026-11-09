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

## (c) Sign-in

**Coordinator decision, which replaces my original request.** Setup takes an explicit `--reviewer-credential PATH`. There is no automatic copy under a new home folder. Setup ends by printing the credential path, the account name and the URL, one per line, and the README's first command uses a visible workspace directory. Verified on the merged code: setup into a visible directory took 1.6 s and printed those three lines last.

Browser side (`web/auth.js`):

- The form says which file to choose and that setup printed its location.
- The file can be dropped on the form as well as picked.
- Errors name the file.
- The signing key stays in memory only.
- After a reload the read session remains, every action control is disabled, and one "Sign in again to take actions" control is shown in their place. No key material goes to `localStorage`, `sessionStorage`, a URL or a log. A browser test checks storage and the URL.

## (d) Projection fields used

- **Lifecycle:** `workflow.finance.stages[]`, as the single server projection (coordinator ruling). The ledger drops its estimate while the claim is in flight, so `uptime/finance_view.py` now falls back to the claim month's own evaluated amount from the same projection. It is copied, never computed, and unknown stays null.
- **Headline:**
  - `workflow.finance.bill.{id, original, applied, outstanding, application_ref}`;
  - `workflow.ledger.bill.month` and `workflow.price_finding.month` when present;
  - `price_finding.{amount, state, invoice_id}`.
- **Rates:** the calculation lines and inputs come from `months[].inputs.credit_percent`, which the server derives from the integer `rate_units`. The power-of-ten conversion applies only to leftover evaluator trace text.
- **Automation:** `workflow.automation.{enabled, state, pause{reason, detail, operation, since}, steps[], counts}`.
  - Each step's `at` is on the case timeline, the clock that "As of" shows. `recorded_at` (wall time) appears only in the step's details.
  - No durations are derived from either clock.
- **Model jobs:**
  - Denial job: `model_job.job.{state, provider.model, submitted_at, started_at, finished_at}` and `candidates[].provenance.{model, elapsed_seconds}`.
  - Contract proposal job: `provider.model`, or `proposal.model` for a succeeded job, plus the three times.
  - Absent fields are omitted, never shown as placeholders.

The browser computes no money.

## (e) Ports

The coordinator accepted ephemeral loopback ports (`bind(0)`) in automated tests. Manual probes used 8841–8845 only.

## (f) Before and after

Both measurements were taken with headless Chrome on a fresh authored Northwind workspace.

- **Before:** at `55ea607`, the judged web build, with the step-by-step workflow.
- **After:** at `3f011de`, on this branch with role 2 merged. The workspace was created with `routine_automation=True`, the new setup default. The measurement script is in the role 4 session scratchpad and is not committed.

| Measure | Before | After |
|---|---|---|
| Primary navigation items visible | 13 in one rail, with three duplicate pairs | **4** (Overview, Cases, Agreements, Activity). Seven advanced tools sit under a collapsed "More tools". |
| Workspace names on screen | 3 ("Finance workbench", "Harborline Analytics", "Contract operations") | **1**: "Harborline Analytics" in the topbar and "Harborline Analytics · Uptime" as the title on every route, whichever page opens first |
| Overview height, 1440×900, before any action | 8,016 px | **4,226 px** |
| Overview height, 1440×900, after the flow | 8,547 px | **3,880 px** |
| Overview height, 390 px, after the flow | 12,710 px | **6,360 px** |
| First viewport after the flow | Four "$2,400.00" tiles | "April invoice NW-2026-04: Invoice $11,000.00, Credit applied $2,400.00, Remaining balance $8,600.00"; "March price exception $1,000.00, Separate from the service credit and not included in it"; then the five-step credit lifecycle |
| Raw hashes / ISO timestamps / `N/1000000%` in the overview after the flow | 5 / 27 / yes | **0 / 0 / no** (the same on Activity) |
| Clicks from sign-in to applied credit | 11 | **4** person decisions: Approve January claim, Approve response, Post to Local ledger, Apply credit to eligible invoice. The server runs the other seven steps under recorded authority (role 2). |
| Held or repeated Enter | Advanced all eleven steps | Records one step. Focus moves to the recovery heading, and repeated key events are ignored. |
| Setup steps for a fresh operator | 6, plus revealing a hidden folder in the file picker | 6, with no hidden folder. Setup prints the credential path, account and URL as its last lines, and the file can be dropped on the form. |
| After a reload | Actions looked enabled; a click returned to sign-in and recorded nothing | Pages still read; actions are disabled, with one "Sign in again to take actions" control |
| Client-side renaming of server states | `presentationLabel` rewrote "Simulated award" → "Awarded credit" and others | Removed. Server stage labels are shown as sent. |
| Page errors | 0 | 0 |

Screenshots, taken from this branch's build:

- [Overview at 1440, before any action](../evidence/submission-ui/after-overview-1440-initial.png)
- [Overview at 1440, after the flow](../evidence/submission-ui/after-overview-1440-final.png)
- [Overview at 390, after the flow](../evidence/submission-ui/after-overview-390-final.png)
- [Activity at 1440](../evidence/submission-ui/after-activity-1440.png)

The before screenshots are listed in (a).

## (g) Checks after roles 1–3 were merged (November 9, about 14:00 PST)

The branch was merged with the integration commit `c756853` (roles 1 and 3) and the role 2 head `8cc4f6f`.

- **Ramp records (`#records`).**
  - The Overview's Ramp card still says "Ramp bill: Not linked" and that no Ramp bill is linked to this agreement. Its link, "Open Ramp records", opens `#records` with More tools expanded and Ramp records marked current.
  - Agent4's **Verified Ramp record** panel is the first panel on that page. It reads "Saved verified record of one Ramp demo bill… Not a live read" and shows bill `f74ba12c…`, the person-observed link and the person-posted note read back.
  - Checked at 1440×900 with no page errors. [Screenshot](../evidence/submission-ui/after-ramp-records-1440.png).
- **Recorded contract job (Corvid Ledger).**
  - Source: a scratch copy of role 1's preserved workspace, served on 8847 and deleted afterwards. Signed in as `role1-operator`; the access read used the authored public fixture and attempt `initial`, and no new job was submitted.
  - The job card shows job `26ee4e3f…`, status SUCCEEDED, model `claude-opus-5-5`, and submitted, started and finished at Nov 9, 2026, 21:17 UTC. Every clause quote is shown untrimmed beside its typed value, and the vendor card shows SHADOW.
  - Review-history times are now formatted dates.
  - Checked at 1440×900. [Screenshot](../evidence/submission-ui/after-contract-job-1440.png).
- **Recorded denial reading (job `29f371d0`).**
  - Source: a scratch copy of agent3's preserved workspace, served at its recorded origin 8823 from this branch with role 2 `c612114` merged. It was stopped and deleted afterwards, and the preserved database hash (`1a035ab2…`) is unchanged.
  - Overview: Claim stage "human review", Credit stage "Claimed", and "Routine steps: Paused · Stopped for a person: the vendor gave a ground the system does not recognize." It then shows the server's own detail ("The vendor reply needs the reviewer's reading and semantic review."), "1 person decision and 2 automatic steps recorded" and "No actions available". Lifecycle: Estimated and Claimed $2,400.00; Awarded, Posted and Applied $0.00.
  - The new link "Open this claim's case and correspondence" opens `#cases/inbox-northwind-2026-01`, where the server's "Review unfamiliar vendor wording" link leads to the reading. The case page used to show 54 hashes, 34 raw timestamps and the raw rate fraction; it now shows none of them on screen. Its timeline, receipts and evaluation trace are in collapsed inspectors, and the complete record is one click away.
  - Reading page: the reply text, then the reviewer's own reading. The job line reads "Request 29f371d0…: Request completed… Model claude-opus-5-5. Finished Nov 9, 2026, 21:20 UTC. Receipt: return code 0 · 0 tool events · no tools available · no MCP servers · client-reported cost USD 0.044891 · session ce56dc6e…".
  - Candidate: "Proposed by model claude-opus-5-5". Both returned propositions read "unsupported" and cite the whole reply (bytes 0–200), shown untrimmed and as returned. "Show dispute record" on the case page loads the read-only disposition.
  - No page errors. Screenshots: [Overview](../evidence/submission-ui/after-denial-overview-1440.png) · [Reading](../evidence/submission-ui/after-denial-reading-1440.png).
  - Separately, an UNCERTAIN request's validated candidate stays visible and inert, per the coordinator's ruling. Its summary and a note beside it give the job id, state and reason (`tests/test_interpretation_uncertain_candidate_r4.py`).
- **Recovery card.** "Claim stage" (the claim's own server value, unchanged) is shown next to "Credit stage", the latest recorded stage from `finance.stages`, so an applied credit no longer sits under "Current stage: awarded".

## (h) Limits and open items

- **Ramp page (agent4's `web/ramp_ui.js`), for the coordinator to route:** the header line prints `Updated 2026-11-05T00:36:21.156851+00:00` as a raw instant, and the verified record shows `NO_APPLIED_CREDITS` and the resource codes (`TRUNCATED`) as raw enums. I have not edited that file.
- **Advanced tools (coordinator question 4).** The legacy projections carry a structured stage (`metric.key`: exposure, estimated, claimed, awarded, posted, applied; action ids such as `record-credit`) but no destination field. The only destination signal is the per-stage source codes (`SIMULATED_VENDOR` and similar), and the November 4 direction excludes showing those as classification badges. Showing "state, destination" there would need a new server field, so the screens show the server's labels verbatim. The presenter guide keeps them out of the recording.
- **Cooldown display.** The cooldown line reads "Not sent before …, the end of the response cooldown" whenever `timing.not_before` is present. The 24-hour duration is not computed in the browser.
