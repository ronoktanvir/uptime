# Interface design: one visual system (handoff)

**Owner:** the design session started November 9, 2026, about 15:20 PST. **Branch:** `work/submission-design-20261109`, from `968c12b` (application code `6b93e31`). **Owns:** `web/`, the JavaScript checks in `web/*.test.cjs` and `tests/helpers/`, and the browser tests that drive these pages. Changed existing tests are listed in [the ledger](../TEST-CHANGES-submission-design-20261109.md).

This file is the plan and the record. Sections 1 to 4 were written before any code changed and are kept as the plan; section 3 was amended where the build differs. Sections 5 to 7 record what was built, how it was checked and what is left.

## 1. What this redesign is, and is not

Ronok opened the running build and asked what the Agreements page meant. The pages were correct but read as a builder's console. The aim is a calm, legible product in the manner of Stripe's dashboard: generous whitespace, one confident accent, a clear type scale, hairline cards with very little depth, numbers set for comparison, and a first screen on every page that says what the page is and what to do next.

It is presentation only. The interface still renders what the server sends.

- No money is computed in the browser and no stages are added together.
- No server state is renamed in a way that hides its destination or status. "Local ledger" stays "Local ledger"; "Ramp bill: Not linked" stays.
- Honest labels stay word for word: "Scripted preparation (scripted-test-reviewer)", "unreviewed and not approved", "Untrusted suggestions", "requires your review", "Not a live read", and the partial-list statements on the Ramp page.
- Nothing is removed. Forms, histories, fingerprints and raw records move behind closed sections, one click away.
- The security model is unchanged: no inline styles or scripts, no external assets, no new network hosts, signing key in page memory only.
- It borrows a design language, not assets. No Stripe logo, wordmark, illustration, copy or font is used, and nothing suggests the product is made by or affiliated with Stripe or Ramp. The name stays "Uptime", "for Ramp".

## 2. Visual system

All tokens are CSS custom properties on `:root` in `web/style.css`. `web/v4_style.css` and `web/interpretation.css` use the same tokens and define none of their own.

### Colour

One accent (a cobalt indigo), a navy ink, cool slate neutrals and three status tints. Every text pairing below meets WCAG AA (4.5:1); the ratios were computed, not estimated.

| Token | Value | Use | Contrast |
|:---|:---|:---|:---|
| `--bg` | `#ffffff` | Page canvas (white since the second pass; it was `#f6f8fb`) | |
| `--rail-bg` | `#f5f6f8` | Sidebar | |
| `--surface` | `#ffffff` | Cards, sidebar, inputs | |
| `--sunken` | `#f6f7f9` | Table heads, quotes, code | |
| `--line` | `#e3e8ef` | Hairlines and card borders | decorative |
| `--field` | `#8a94a6` | Input borders | 3.06:1 on white (non-text) |
| `--ink` | `#0f1a36` | Headings and key figures | 17.2:1 on white |
| `--text` | `#27304a` | Body text | 13.1:1 on white, 12.3:1 on canvas |
| `--muted` | `#5a6478` | Labels, captions, secondary text | 5.9:1 on white, 5.6:1 on canvas |
| `--accent` | `#4353e0` | Primary buttons, links, current step, focus ring | 5.9:1 on white, white on it 5.9:1 |
| `--accent-strong` | `#3442c4` | Hover and pressed | white on it 7.7:1 |
| `--accent-soft` | `#eef0fe` | Current navigation item, selected and highlighted areas | accent on it 5.2:1 |
| `--ok` / `--ok-soft` | `#0a6b48` / `#e2f5ec` | Recorded, complete, passed | 5.8:1 |
| `--warn` / `--warn-soft` | `#8a4a03` / `#fff2d9` | Open findings, waiting, needs review | 6.2:1 |
| `--bad` / `--bad-soft` | `#b42318` / `#fde9e7` | Failed, uncertain outcome | 5.6:1 |
| neutral pill | `#46506a` on `#eef1f6` | States with no judgement attached | 7.1:1 |

Status colour is never the only signal: every pill carries its words, and lifecycle steps carry "Recorded" or "Not yet" in text.

### Type

Inter, one variable font file that the app serves itself ([notices](THIRD-PARTY-NOTICES.md)); nothing is loaded from another host and the content security policy is unchanged. It replaced the system font stack on November 9 at Ronok's request, and that stack remains the fallback: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. References and digests use `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`. Amounts that line up in a column or a row of figures use tabular figures; references do not, because in this typeface tabular figures also widen hyphens.

| Role | Size / line | Weight |
|:---|:---|:---|
| Hero figure | 40 / 44 | 600 |
| Figure | 24 / 30 | 600 |
| Page title (`h1`) | 24 / 30 | 650 |
| Card title (`h2`) | 15 / 22 | 600 |
| Sub-heading (`h3`) | 13 / 20 | 600 |
| Body | 14 / 20 | 400 |
| Table head | 11 / 16, capitals, wide-set | 600 |
| Secondary | 13 / 20 | 400 |
| Label and caption | 12 / 16 | 500 |

Three voices, each for one kind of text (second pass):

- **Interface:** Inter, for everything the product itself says.
- **Quoted source text:** a serif, for a contract clause or a vendor's reply, so a document's words never look like the interface's own. It is the system serif (`ui-serif`, New York on a Mac, Georgia elsewhere); no file is bundled for it.
- **References:** monospace, for identifiers and digests, as before.

### Space, shape, depth, motion

- **Spacing** on a 4-pixel scale: 4, 8, 12, 16, 20, 24, 32, 40, 48. Cards pad 24 (20 on a phone); the page gutter is 40 on a desktop, 24 on a tablet and 16 on a phone.
- **Radius:** 6 for controls, 10 for cards, a full pill for badges.
- **Depth:** a hairline border plus one barely visible shadow (`0 1px 2px` at 5% navy). Only the case dialog casts a real shadow.
- **Motion:** 140 ms ease on colour, border and shadow for hover, focus and press. Nothing animates on load, nothing times a workflow transition, and `prefers-reduced-motion` turns all of it off.
- **Focus:** a 2-pixel accent ring with a 2-pixel offset on every interactive element, always visible.

### Components

| Component | Notes |
|:---|:---|
| App shell | Light sidebar: brand, workspace name, four destinations, collapsed "More tools", and refresh and account at the foot. The content column is capped at 1120 px and starts at the top of the page; there is no separate top bar. Below 760 px the sidebar becomes a slim header of about 125 px: brand and account on one row, the four destinations as tabs, then "More tools" and the workspace name. |
| Page header | Small context line, page title, one sentence saying what the page is, and the "as of" time on the right. |
| Card | White surface, hairline, 10 px radius. Title row with an optional status or link on the right. |
| Figure | A label over a tabular amount; the hero variant is larger. |
| Field list | Label above value in a responsive grid, for short facts. |
| Table | Label-sized header on the sunken tint, hairline rows, amounts right-aligned, horizontal scroll inside its own frame on narrow screens. |
| Pill | State in words on a status tint. |
| Stepper | The five lifecycle stages on one line with a connecting rule; a marker, the stage label, the amount and "Recorded" or "Not yet". |
| Timeline | A vertical rule with one row per step: time, what happened, who or what authorised it. |
| Disclosure | A closed section with a chevron. Two sizes: an inline "inspector" for a few values and a card-level "fold" for forms and histories. |
| Quote | The exact clause or reply text on the sunken tint with an accent rule, never trimmed. |
| Reference | Monospace, wraps anywhere, shortened only where the full value sits one click away. |
| Buttons | Primary (accent), secondary (white with hairline), quiet text button. 36 px high, 44 px on a phone. |
| Inputs | 36 px high, visible border, accent ring on focus, a dashed drop area for the credential file. |
| Status line | The live region for results and errors; tinted only when it has something to say. |
| Icons | [Phosphor Icons](THIRD-PARTY-NOTICES.md) (MIT), held in the stylesheet and the page itself. Used where they help recognition: the sidebar, the tags that say who or what acted, links that go forward, back or out to Ramp, the "as of" time, and four status marks (price exception, verified Ramp record, in force, failed read). Decoration only: no icon names an element or says more than the words beside it. |

## 3. Layout plan per page

Reference size: 1440×900, first viewport and full page. Also looked at on a computer screen at 1280×720, 1920×1080 and 1024×768. 390×844 is checked for use without horizontal scroll; its visual polish is deferred (see section 7).

| Page | First screen | Below, or one click away |
|:---|:---|:---|
| **Sign-in** | A centred card with the brand, "Sign in to Uptime", the account name, a drop area for the credential file and one sentence on where the key is kept. The navigation is hidden until sign-in. | — |
| **Overview** | Header, then the outcome: the credit (or the invoice after the credit is applied) beside the separate price exception. Under it the five-stage lifecycle across the full width, then the recovery card with the next decision beside "Needs attention". | The Ramp record ("Ramp bill: Not linked") and "Ask about this case" under the recovery card, then an Evidence group: service credit evaluations, price review and bill reconciliation. Agreement, coverage and review records are three closed sections at the foot. |
| **Activity** | Header, a one-line summary of routine steps with the server's two counts, then the step timeline: time, step, and who or what authorised it, tagged as a reviewer decision, an automatic step under a recorded approval, or a received event. A decision names the account exactly as the server sends it ("Decided by scripted-test-reviewer"); the interface never says a person decided. | Workflow history, the pointer to model jobs and the coverage history (closed). |
| **Cases** | Header and the list of cases: title, vendor, month, stage, outcome, amount, and a way in. | Setting up a case, access details and the complete record of each case, in closed sections. |
| **One case** | Back link, title and stage; the facts (amounts by stage, filing cutoff, next contact); then the correspondence in order with each vendor reply quoted and each step's actor. | Evidence and receipts, evaluation, dispute record and the complete server record, closed. |
| **Agreements** | Header and one card per agreement: vendor, state in the server's word with one plain sentence, what it covers, what the source establishes with each cited clause, and who performed the review steps as the server states it. A vendor's model proposal job sits directly under that vendor when one exists: status, model, times, each proposed term beside its exact quoted sentence, and the sentence that it is unreviewed and not approved. | Review history, requirements detail, version actions, test and evaluation forms and the raw record per vendor; "Add an agreement" (proposal generator and local intake) and access details for the page. All closed. |
| **Ramp records** | Header, then the "Verified Ramp record" card alone: what it is, "Not a live read", the bill's facts as a field list, the Ramp link and the discussion. Under it the earlier saved worklist in its own titled card with its read time and partial-list statements (amended after acceptance finding P2). | The worklist's rows (closed while a verified record is shown) with their filter and search, then coverage, permissions, reconciliation and writeback evidence, closed as before. |
| **Reading a vendor reply** | The same brand bar and sign-in card; then the reply text as a quote, the claim facts, and the reviewer's own reading as a form. Suggestions keep the heading "Untrusted suggestions" and "requires your review". | Source details, permission and request details, closed as today. |
| **Advanced tools** | Restyled through the shared components (cards, tables, field lists, pills). Their structure and the server's own labels are unchanged. | — |

## 4. How it is checked

- **Looking.** After each change a fresh throwaway walkthrough is served from this worktree on a port in 8871–8879 and captured with Playwright driving installed Chrome, signing in through the ordinary form. Each image is opened and inspected for overlap, clipping, overflow, misalignment, uneven spacing, weak contrast, bad wrapping, layout shift, horizontal scroll and console or page errors. The capture script reports page height, any element wider than the viewport, and every console message.
- **States.** Sign-in; Overview before any decision and after each of the four; Activity; Cases and one case; Agreements; Ramp records; the reading page. The two recorded model screens are served from copies only.
- **Checks.** `node --test web/*.test.cjs tests/helpers/*.test.cjs` and the focused browser tests, each under a hard time limit. The full Python suite is the coordinator's, after merging.

## 5. What changed per page

Every page now uses the one system in section 2. Nothing the server sends was renamed, recomputed or removed; what left the first screen sits in a closed section on the same page.

Commits, in order: `663eed2` this plan · `943151f` shell, tokens, sign-in, Overview and Activity · `3273d87` Agreements · `29ecdb3` Cases · `d68e67e` Ramp records · `203b252` reading page · `c280283` one Ramp bill · `1dca1cf` and `53f6115` the pass over every page on a computer screen.

Page height at 1440×900 on the same walkthrough data, before this branch and now:

| Page | Before | Now |
|:---|---:|---:|
| Overview, before any decision | 4,264 px | 2,679 px |
| Overview, after the four decisions | 3,918 px | 2,700 px |
| Activity, after the four decisions | 4,975 px | 2,939 px |
| Cases | 2,926 px | 900 (one screen) px |
| One case | 2,638 px | 2,363 px |
| Agreements | 7,917 px | 3,242 px |
| Ramp records | 2,945 px | 1,361 px |
| Portfolio comparison (More tools) | 23,774 px | 3,625 px |

The state this branch started from is in [the earlier interface evidence](../evidence/submission-ui/) (its "after" images). The final screenshots are listed in section 6.

### The shell, on every page

- **Before:** a dark navy sidebar with symbol glyphs, and a top bar holding the workspace name, the account button and "Refresh data".
- **Now:** a light sidebar with the brand, the workspace name, the four destinations with line icons, "More tools" (closed until one of its pages is open), and "Refresh data" and "Sign out · account" at the foot. There is no top bar: each page starts at the top of the window with a context line, its title, one sentence saying what it is, and the "as of" time.
- The sidebar is hidden before sign-in and while the first page loads, because there is nothing to navigate to yet.
- The content column is capped at 1,120 px and centred in the space beside the sidebar, so the layout is the same at 1440 and 1920.
- Unchanged: the skip link, both live regions, every route (`#overview`, `#cases`, `#cases/<id>`, `#agreements`, `#activity`, `#records` and every older hash), the order of requests on load, and the static file list (no asset file was added).

- **Icons** (added after the first merge, at Ronok's request): the sidebar, tags, link arrows and four status marks use Phosphor Icons, as listed in [the notices](THIRD-PARTY-NOTICES.md). The words are unchanged.

- **Typeface** (added after the first merge, at Ronok's request): Inter, bundled, in place of the system font. One file was added to what the app serves, `InterVariable.woff2`, and the two tests that list the page's own files serve it too (ledger rows 12 and 13).

### Sign-in

- **Before:** a full-width panel beside the sidebar, under the top bar.
- **Now:** one centred card: brand, "Sign in to Uptime", the account name, a dashed drop area for the credential file, one sentence that the file is used only in this page and never uploaded, and a full-width "Sign in" button. The reading page shows the same card.
- Unchanged: the fields and their order, drag and drop onto the form, and where the key is kept (page memory only).

### Overview (the film's main screen)

- **First screen at 1440×900:** the outcome, the lifecycle, and the recovery card with the next decision beside "Needs attention".
  - Outcome: the service credit as the server states it, beside the separate price exception with an amber top rule and the sentence that it is not included in the credit. After the credit is applied the same card shows the invoice, the credit applied and the remaining balance on one line, from `finance.bill`.
  - Lifecycle: the five server stages on one line with a connecting rule. Each shows the server's label, amount and "Recorded" or "Not yet". "Posted to Local ledger" keeps its destination in the label.
  - Recovery: claim stage, credit stage, destination and claim reference; then one bar with the routine-steps sentence and the offered action as the only primary button on the page. When the server stops for a reviewer elsewhere the bar is amber and says why in the server's words.
- **Below:** "Ramp record" (Connection destination: Local ledger · Ramp bill: Not linked · "No Ramp bill is linked to this agreement"), "Ask about this case", then an Evidence group: the monthly evaluations table, the price review and the bill reconciliation. Agreement, coverage and review records are three closed sections at the foot.
- **Before:** the same content in one long column, with amber-filled "Not yet" lifecycle cells, the attention list under the recovery card, and the agreement and coverage records open.
- Unchanged: the heading that takes focus after an action, the order of everything a held key could reach, and every amount, which is the server's string.

### Activity

- A panel "Steps in order" with the server's state, its two counts as figures (reviewer decisions, automatic steps) and the summary sentence, then a vertical timeline: the time on the case's clock, the step, a tag (Reviewer decision, Automatic step or Received event) and who or what authorised it.
- A decision reads "Decided by scripted-test-reviewer": the account exactly as the server sends it. The interface does not say a person decided.
- Workflow history, the pointer to model jobs and the coverage history follow.

### Cases, and one case

- **Cases before:** the page opened with "Identity & approval gate" and the "Set up a correspondence case" form; the cases came after them.
- **Cases now:** a table of cases (title, vendor and reference, service month, stage, outcome, claim amount, "Open case"). Setting up a case, the complete record of each case and "Your access on this page" are closed sections.
- **One case now:** a way back ("All cases"), the vendor and month, the title and the reference. Then:
  - "Vendor wording to review", only when the server offers the reading page, with its link as the primary action;
  - "Where this claim stands": stage, outcome, filing cutoff, next contact and the scope, the amounts by stage (Estimated, Claimed, Awarded, Disputed remainder) with the sentence that they are not added together, and the reviewer actions the server offers;
  - "Correspondence, in order": one row per recorded event with its time, the actor exactly as recorded ("Actor: scripted-test-reviewer"), its receipt or event reference, and each vendor reply quoted in full under the event that delivered it;
  - the dispute record, and five closed sections holding the decision and amounts as recorded, the event timeline, evidence and receipts, the evaluation, and the complete server record.

### Agreements

- **Before:** the page opened with "Identity & approval gate" and the proposal form; each vendor was a raw record followed by every review row and five open forms. 7,917 px tall.
- **Now:** one card per agreement, with jump chips when there are several.
  - The vendor and the server's state word ("ACTIVE", "SHADOW") with one plain sentence: "In force in this workspace.", "Not in force." and the existing state sentence.
  - Short facts: agreement, what it covers, account, period in effect, source document, how the source was read, revision, reviewer as the server sends it ("scripted-test-reviewer (scripted test)").
  - When the agreement was staged from a model job, the job sits directly under the facts: job, status, model, times, the sentence "The proposal is unreviewed and not approved", and each proposed term beside the exact sentence it cites and its typed value. Digests stay in the closed "Request details".
  - "What the source establishes": each requirement with its status in words, the clauses it cites and those clauses quoted exactly, with the note "Read only. These requirements grant no approval, activation or dispatch."
  - "Review steps": who performed them, as the server states it ("Scripted preparation (scripted-test-reviewer)", "Recorded under account …"), with the number of steps and the latest one. The full history is one click away.
- Closed, one click away: typed values and reviewer tasks, the review history, the review tools and version actions with the full record, "Add an agreement" (proposal generator and local intake), and "Your access on this page".
- The requirements of an agreement that has a source manifest are read with the page (one extra GET per such agreement), so the card does not need a button press.

### Ramp records, and one Ramp bill

- **Now:** the "Verified Ramp record" card stands alone at the top: what it is ("Saved record read from Ramp …, started by a person. Not a live read."), the bill as read from Ramp as a field list, its identifiers, the Ramp link statement, what Uptime found for this bill in words, and the discussion with "Uptime has made no write to Ramp."
- The earlier saved worklist is a separate card titled "Ramp worklist" with its own read time and its partial-list statements. Its rows are closed while a verified record is shown. A scenario row starts with "Scenario only, not a finding" and labels its outcome and amount as the scenario's.
- Record coverage, agreements and permission, credit reconciliation and writeback evidence are closed sections, as before.
- **New route `#ramp-bill/<Ramp bill id>`,** for a panel about 420 px wide beside Ramp. It makes one request (the saved Ramp workspace) and shows one of three things: the verified bill; a bill found only in the saved worklist, with that worklist's own statement; or one sentence that the bill is not in what Uptime has read. It never shows the Northwind claim, credit or price finding. An agreement binding of `NONE` reads "No agreement on file for this bill" and `finding_attachable: false` reads "No contract finding is attached to this bill".

### Reading a vendor reply (`interpretation.html`)

- A slim brand bar with "Back to the case", then a 960 px column: the context line, the title, the amber note that reading does not authorise a filing, entry, waiver or closure, the reply quoted exactly with its claim facts, the reviewer's own reading as a form, the request, "Untrusted suggestions" with "Requested interpretation — requires your review", and the reconcile-and-attest step.
- It links the main stylesheet, so its colours, controls and cards are the same components. Status messages appear in one fixed, non-interactive line at the foot.

### More tools

Restyled through the shared components; structure and the server's own words are unchanged unless listed here.

- **Case ledger:** the six figures sit three to a row; the title and its three filters share one line; case references are in monospace on one line. Stage and eligibility stay the server's words.
- **Case inspector (dialog):** long values wrap inside their cards, and a linked record's reference is set apart from its label.
- **Onboarding lab, Policies:** times read as on every other page ("Nov 9, 2026, 23:20 UTC"); the exact value stays on the element. Source links are one per line.
- **Advanced workflows:** says what it is in its header; the observed integrity record sits inside its own card.
- **Portfolio comparison:** each cohort shows its figures (the server's label, value and note) and its cases (title, amount, the server's outcome and stage words). Every full record is one click away. It was a 23,774 px list of raw fields.
- **A failed read** shows "Unable to load this view" with the reason and "Try again", with the same distance from the top as a page header.

### Second pass: the look of an established application (November 9, late)

Ronok asked for the interface to read as an established application rather than a small page that explains itself: an application's structure, more icons, more than one typeface, and typographic emphasis, with Ramp's layout as a possible reference. Layout conventions were taken from that kind of product (a tinted sidebar beside a white working area, compact page headers, dense tables with entity tiles and state chips). No logo, colour, wordmark, illustration or typeface of Ramp's is used, and nothing suggests the product is Ramp's.

- **Shell.** The working area is white and the sidebar is tinted. The sidebar opens with the brand and a "for Ramp" tag, then a workspace block (the workspace's initials, the label "Workspace" and its name). The current page is a raised white row. Every tool under "More tools" has its icon. The account row shows the account's initials beside the control's own words.
- **Page headers.** Each page opens with a tile (the vendor's initials on the Overview, the page's icon elsewhere), a small context line and the title, on a hairline. The introduction sentences under the titles are gone: the Overview's, Activity's, Agreements', Cases', Ramp records' and Advanced workflows'. The Evidence group's sentence and the sentence over a case's correspondence are gone too. Statements that say what a figure is or is not were kept, word for word: "One credit, shown at each stage. The amounts are not added together.", "Separate from the service credit and not included in it.", "Read only. These requirements grant no approval, activation or dispatch.", the Ramp page's read and partial-list statements, and the Portfolio page's "A seeded scenario is not a portfolio total."
- **Cards and tables.** The main cards carry a small icon beside their titles. Table heads are small capitals. A state chip carries a dot in its own colour. The decision button carries a check mark, and "Sign in again to take actions" a key.
- **Entities.** A vendor's initials sit in a tile beside its name on its agreement card and on each row of the Cases list.
- **Company pictures.** At Ronok's request the two authored companies he supplied pictures for show them in place of their initials: a cloud mark for Northwind Cloud (Overview header, Cases rows, its agreement card) and a lighthouse mark for Harborline Analytics (the sidebar's workspace block). The stylesheet names the two pictures; any other name keeps its initials. Details are in [the notices](THIRD-PARTY-NOTICES.md).
- **Type.** Titles are smaller and heavier, text is set tighter, and quoted source text is in a serif (section 2).
- **Unchanged.** Every control keeps its words and its place: no row was added to the table below for this pass. No amount, state, destination or disclosure changed, and no test changed.

### Controls renamed or moved (for the filming checklist)

Every control keeps what it does. A label not listed here is unchanged. "Closed section" means a titled row with a chevron: click the title and the content is the same as before.

| Page | Control | Before | Now |
|:---|:---|:---|:---|
| Every page | "Refresh data" | Top bar, right | Foot of the sidebar. Same label |
| Every page | Account control, "Sign out · account" | Top bar, centre | Foot of the sidebar, under "Refresh data". Same label |
| Every page | Workspace name | Top bar, left | Under the brand in the sidebar |
| Sign-in | Sentence about the credential file | In the introduction | Under the file field. "Account name", "Credential file" and "Sign in" are unchanged |
| Overview | The decision button ("Approve January claim", "Approve response", "Post to Local ledger", "Apply credit to eligible invoice") | Its own line under the recovery fields | Right side of the routine-steps bar in the same card. Same labels |
| Overview, Activity | Routine-steps sentence | "… Waiting for a person to approve.", "… Stopped for a person: …", "Each step runs when a person presses it …" | The same sentences with "a reviewer" |
| Overview | "Reviewer" fact | Only inside the closed records | Right of the recovery card's title: "Reviewer  Dana Reyes · Scripted reviewer" |
| Overview | "See every step in Activity" | End of the routine-steps sentence | Link row under the bar |
| Overview | "Open this claim’s case and correspondence" | Under the decision button | The same link row |
| Overview | "Needs attention", with "Show details" | Under the recovery card | Column to the right of the recovery card |
| Overview | "Ramp record" with "Open Ramp records"; "Ask about this case" | Further down the page | Under the recovery card, left column |
| Overview | "Service credit evaluations", "March price review", "Bill reconciliation" | No group heading | Under a new heading, "Evidence". Titles unchanged |
| Overview | "Governing agreement", "CalyxQuay coverage in this workspace", "Agreement & review record" | Open panels | Closed sections at the foot |
| Activity | Panel title | "Automation" | "Steps in order" |
| Activity | Count sentence | "… N person decisions and N automatic steps recorded." | "… N reviewer decisions and N automatic steps recorded." |
| Activity | Tag beside each step | None | "Reviewer decision", "Automatic step" or "Received event". "Decided by …" and "Step details" are unchanged |
| Cases (`#cases`) | Page heading | "Correspondence & disputes" | "Cases"; the old title is the small line above it |
| Cases | Way into a case | Button "Inspect case <id>" | Link "Open case" at the right of the row; the case title is also a link. Address `#cases/<id>` |
| Cases | "Set up a correspondence case" | Open form at the top | Closed section of the same name under the list |
| Cases | "Complete case record" for each case | A closed row under each case | Inside the closed section "Complete record of each case (N)", one row per case |
| Cases, one case, Agreements | "Identity & approval gate" | Open panel at the top | Closed section "Your access on this page" at the foot. A page that is read-only says so in a line at the top |
| Cases, Agreements, Advanced workflows, Portfolio comparison | "Refresh server state" | Under the gate | Page header, right |
| One case (`#cases/<id>`) | Way back | Button "Back to correspondence" | Link "All cases", top left. After a failed read: "Back to all cases" |
| One case | "Refresh case receipts" | Top of the page body | Page header, right |
| One case | "Review unfamiliar vendor wording" | In the body of the case record | First card, "Vendor wording to review", as its main button |
| One case | The case record | One panel, "Correspondence case" | "Where this claim stands" (facts, amounts, "Reviewer actions") and "Correspondence, in order" |
| One case | "Show dispute record" | Inside the case panel | Its own card, "Dispute record", under the correspondence |
| One case | "Event timeline", "Evidence & receipts", "Current and historical evaluation" | Sections of the case panel | Closed sections at the foot, with "Decision, unknowns and amounts as recorded" and "Complete server case record" |
| Agreements (`#agreements`) | Page heading | "Vendor intake & versions" | "Agreements" |
| Agreements | "Generate a public proposal" and "Local deterministic intake", with "Check generation access", "Generate proposals", "Refresh proposal status" and "Stage local candidate" | Open at the top of the page | Inside the closed section "Add an agreement" at the foot. Labels unchanged |
| Agreements | "Show review requirements" | A button on every agreement | Not needed for an agreement that has a source manifest: its requirements are in view under "What the source establishes". The button remains for an agreement without one |
| Agreements | "Review history" | Open list | "Review history (N steps)", closed, under "Review steps" |
| Agreements | Version actions (such as "Roll back activation", "Revoke approval"), "Rules, overlay, tests and reviewer versions", and the forms "Record semantic review", "Revoke semantic binding", "Submit independent tests", "Preview candidate", "Evaluate into a case" | Open on each agreement | Inside the closed section "Review tools, version actions and the full record" on that agreement's card. Labels unchanged |
| Agreements | Model job card | Labels "status", "model" | Title "Model proposal job"; labels "Status", "Model". "Request details" is still closed |
| Ramp records (`#records`) | Page heading | "Ramp worklist" | "Ramp records". "Ramp worklist" is now the title of the saved worklist card |
| Ramp records | The record table, with its search and filters | Open, titled "Financial records" | Inside "Records in this worklist", which is closed while a verified record is shown |
| Ramp records | "Open this bill in Ramp" | In the verified panel | Right of the "Verified Ramp record" title |
| One Ramp record | "Back to Ramp worklist" | Returned to the worklist | Same label; returns to the page the record was opened from |
| One Ramp bill (`#ramp-bill/<id>`) | New page | None | "Open the full record" leads to `#records` |
| Reading a vendor reply | Way back | None on the page | Bar at the top with "Back to the case" (to `#cases/<claim>`). Every button keeps its label |
| Portfolio comparison (More tools) | Button under each case | "Inspect <case id>" | "Inspect case". Raw fields are under "Full record", closed, on each figure and case |

### Acceptance findings answered

| Finding | What it said | What changed |
|:---|:---|:---|
| **P2**, Ramp records | The verified record must stand alone at the top; the earlier saved worklist needs its own titled section; a scenario row must say it is a scenario before any outcome or amount. | As described under Ramp records above. No server value was dropped or renamed. Commit `d68e67e`. |
| **P3**, Overview | February showed an unknown amount although its outcome is determined. | A month whose outcome is `INELIGIBLE` and whose amount is null reads "No credit". An unknown outcome still reads "Not determined". The interface never prints `$0.00` that the server did not send. The Cases list follows the same rule. Commits `943151f` (Overview) and `29ecdb3` (Cases). |
| Coordinator's correction | The interface must not assert that a person decided. | Steps are tagged "Reviewer decision" and name the account as sent; the count sentence reads "4 reviewer decisions and 7 automatic steps recorded"; the model jobs note reads "A model proposes; a reviewer decides." Three assertions changed (ledger rows 1 to 3). |
| **A1** (P2), Overview, Activity, case page, Agreements | The routine-steps line said a person acts ("Waiting for a person to approve", "Stopped for a person: …"), and the approval then comes from a scripted account. | Every interface sentence about who approves, reviews or presses now says "reviewer": the six pause reasons, "Each step runs when a reviewer presses it in this workspace.", "A reviewer must review it; this case offers no action until then." and "… a reviewer’s approval remain required." Left as they are, because they are about an actual person: "Posted by a person in Ramp", "started by a person" and "observed in Ramp by a person" on the Ramp read. Four tests changed (ledger rows 14 to 17). |
| **A3** (P3), Overview | The server's statement that this reviewer is scripted was only inside closed sections on the film's main screen. | The recovery card shows one field at the right of its title line: "Reviewer" with the name as the server sends it and its authority kind in the same words the closed records use ("Dana Reyes · Scripted reviewer"). It takes no height of its own, is not a control, and is left out when the server names no reviewer. |
| **A2** (P2), one case | The closed section "Decision, unknowns and amounts as recorded" showed "Posted USD 0.00" and "Applied USD 0.00" after the credit had been posted and applied, because the claim's own record does not track those two stages and sends a zero for both. | In that section a zero for Posted or Applied is no longer stated as an amount; one sentence says so: "This record does not track posting or application; the Overview’s credit lifecycle shows them for the credit it follows." A non-zero amount on the record is shown like the others. Estimated, Claimed, Awarded and Disputed remainder are as the record sends them, and "Complete server case record" below is unchanged, zeros included. Three new tests; no existing test changed. |

Confirmed by acceptance and still true: the reviewer is shown as scripted; no screen says money was recovered in Ramp; the Ramp card reads "No Ramp bill is linked to this agreement"; quotes are byte-exact and untrimmed.

## 6. What was checked, and how

### Looking

- Every page was served from this worktree and captured with Playwright driving installed Chrome, signing in through the ordinary form. Nothing is injected into the page. Each image was opened and read for overlap, clipping, misalignment, uneven spacing, wrapping and contrast; the script also reports page height, any element wider than the window, and every console message, failed request and HTTP error.
- **Sizes:** 1440×900 for every page and state; 1280×720, 1920×1080 and 1024×768 for Overview, Agreements, Cases, Ramp records and the Case ledger; 390×844 for every page (width only, see section 7).
- **States:** sign-in; Overview before any decision, after each of the four, and stopped for a reviewer; Activity before and after; Cases and one case (awarded, and stopped for vendor wording); Agreements on the walkthrough and on the recorded contract job; Ramp records; one Ramp bill at 420 px and on a full page; the reading page before and after sign-in; every More tools page, the case inspector dialog and a failed read.
- **Result:** no console message, failed request or HTTP error on any page, apart from the one request deliberately blocked to look at the failed-read state. No page is wider than its window at any size checked.
- **Sources:** three throwaway walkthrough workspaces on ports 8871 to 8873. The two recorded model screens were served from copies only: the contract job on 8874 and the denial reading at its recorded origin 8823. All five were stopped and their folders deleted at the end. The preserved originals were only copied; their database hashes (`9043eaaf…` and `1a035ab2…`) were checked unchanged when the copies were made.

### Final screenshots

First viewport only, in [`docs/v4/evidence/submission-design/`](../evidence/submission-design/). Each name ends in its window width.

| Page or state | 1440×900 | 390×844 |
|:---|:---|:---|
| Sign-in | [image](../evidence/submission-design/signin-1440.png) | [image](../evidence/submission-design/signin-390.png) |
| Overview before any decision | [image](../evidence/submission-design/overview-before-1440.png) | [image](../evidence/submission-design/overview-before-390.png) |
| Overview after the four decisions | [image](../evidence/submission-design/overview-after-1440.png) | [image](../evidence/submission-design/overview-after-390.png) |
| Activity | [image](../evidence/submission-design/activity-1440.png) | [image](../evidence/submission-design/activity-390.png) |
| Cases | [image](../evidence/submission-design/cases-1440.png) | [image](../evidence/submission-design/cases-390.png) |
| One case | [image](../evidence/submission-design/case-1440.png) | [image](../evidence/submission-design/case-390.png) |
| Agreements | [image](../evidence/submission-design/agreements-1440.png) | [image](../evidence/submission-design/agreements-390.png) |
| Agreements, recorded contract job | [image](../evidence/submission-design/agreements-recorded-job-1440.png) | [image](../evidence/submission-design/agreements-recorded-job-390.png) |
| Ramp records | [image](../evidence/submission-design/ramp-records-1440.png) | [image](../evidence/submission-design/ramp-records-390.png) |
| Reading a vendor reply | [image](../evidence/submission-design/reading-1440.png) | [image](../evidence/submission-design/reading-390.png) |
| One Ramp bill, panel width | [420×900](../evidence/submission-design/ramp-bill-420.png) | |

### Checks

The full Python suite was not run here; it is the coordinator's, after merging.

Run at `53f6115`, the last commit that changes anything under `web/` or `tests/`; the commits after it add only this record and the screenshots.

- `node --test web/*.test.cjs tests/helpers/*.test.cjs` → `tests 124`, `pass 124`, `fail 0`, `cancelled 0`, `skipped 0`.
- The focused Python tests, one file at a time, each under a hard limit of 300 seconds:
  `perl -e 'alarm 300; exec @ARGV' uv run --locked pytest -q <file> --basetemp=<scratch>/<name> -o tmp_path_retention_policy=failed`

| File | Result line |
|:---|:---|
| `tests/test_submission_ui_browser.py` | 5 passed in 17.75s |
| `tests/test_finance_browser_90.py` | 2 passed in 7.94s |
| `tests/test_finance_keyboard_95.py` | 2 passed in 9.79s |
| `tests/test_guide_suggestions_browser_95.py` | 1 passed in 3.45s |
| `tests/test_workspace_ui_v4.py` | 3 passed in 2.79s |
| `tests/test_ramp_ui_v4.py` | 1 passed in 1.81s |
| `tests/test_ramp_bill_panel.py` | 2 passed in 4.53s |
| `tests/test_advanced_companion.py` | 4 passed in 4.65s |
| `tests/test_contract_job_card_r4.py` | 1 passed in 5.76s |
| `tests/test_vendor_model_jobs_browser.py` | 5 passed in 12.57s |
| `tests/test_vendor_auth83.py` | 2 passed in 7.92s |
| `tests/test_requirements_card_ui_95.py` | 1 passed in 0.90s |
| `tests/test_correspondence_artifact_category_ui_81.py` | 2 passed in 2.72s |
| `tests/test_correspondence_denial_bundle_ui_78.py` | 4 passed in 4.62s |
| `tests/test_correspondence_interpretation_ui.py` | 1 passed in 1.84s |
| `tests/test_correspondence_model_jobs_ui_75.py` | 6 passed in 6.22s |
| `tests/test_interpretation_denial_label_95.py` | 1 passed in 2.08s |
| `tests/test_interpretation_uncertain_candidate_r4.py` | 3 passed in 3.43s |
| `tests/test_v4_authority_browser.py` | 1 passed in 3.65s |
| `tests/test_local_review_exception.py` | 15 passed in 5.44s |
| `tests/test_vendor_monthly_profile_79.py` | 10 passed in 0.92s |

  21 files, 72 passed, none failed, 121 seconds in all. No run hung and none was interrupted.
- One earlier run of the same per-file loop was invalid and is not counted: its scratch parent folder did not exist, so every test that uses `tmp_path` errored at setup within about a second. The folder was created and the loop rerun; the table is that rerun.
- The walkthrough was also driven end to end on the final build through the ordinary pages: sign in, then "Approve January claim", "Approve response", "Post to Local ledger" and "Apply credit to eligible invoice", each recorded once, with focus on the recovery heading after each.

### After the first merge (November 9, evening)

- **The redesign reached `main` through the coordinator's merge** (`3bbd47e`, with the side panel), after the coordinator's own full run on that merge: 5,452 passed. Nothing below replaces that run.
- **A second merge of the same commits was made here and not pushed.** At Ronok's direct request this session merged `a92f86c` onto `main`'s then head as `618cc8e`, before learning the coordinator had already pushed. Its first full run was cut off by this session's 30-minute limit: it had printed nothing since 14 percent, at `tests/test_contract_job_card_r4.py`, the first browser launch, with no test failed before it. The rerun, with a five-minute stall check, finished: `5400 passed, 1 warning in 431.91s`. The merge was then deleted unpushed, since it added nothing to `main`.
- **Icons** (the commit after `main`'s `0cd60d9` on this branch): `node --test web/*.test.cjs tests/helpers/*.test.cjs` → `tests 129`, `pass 129`, `fail 0`. The 21 files in the table above plus `tests/test_side_panel_framing.py` and `tests/test_setup_side_panel.py`, one file at a time under the same limit: 23 files, 124 passed, none failed, 204 seconds. `scripts/check_repo.py`: exit 0. Looked at on Overview, Activity, Agreements, Ramp records and Cases at 1440×900, the sign-in card, and the one-bill page at 420×900: no console message, no page wider than its window. No test changed. The full run for this change is the coordinator's, before it merges.

- **Typeface** (the commit after the icons on this branch): `node --test web/*.test.cjs tests/helpers/*.test.cjs` → `tests 129`, `pass 129`, `fail 0`. The same 23 files, one at a time under the same limit: 124 passed, none failed, 128 seconds. The font is served by the real server as `font/woff2`, 352,240 bytes. Looked at on sign-in, Overview, Activity, Cases, one case, Agreements and Ramp records at 1440×900 and the one-bill page at 420×900: Inter is the face in use on each, no console message, no failed request, no page wider than its window. One side effect was found and fixed by looking: tabular figures widened the hyphens in references, so they are now asked for only where amounts line up. Two tests changed (ledger rows 12 and 13). The full run for this change is the coordinator's, before it merges.

- **Acceptance findings A1 and A3** (the commit after `main`'s `53c38e3` on this branch): `node --test web/*.test.cjs tests/helpers/*.test.cjs` → `tests 129`, `pass 129`, `fail 0`. The same 23 files, one at a time under the same limit: 124 passed, none failed, 123 seconds. Looked at on the Overview at 1440×900 and 390×844: the reviewer field sits on the recovery card's title line, nothing below it moved, no console message, no page wider than its window. Four tests changed (ledger rows 14 to 17). The full run for this change is the coordinator's, before it merges.

- **Second pass and A2** (the two commits after `main`'s `d23db79` on this branch): `node --test web/*.test.cjs tests/helpers/*.test.cjs` → `tests 132`, `pass 132`, `fail 0` (three new, for A2). The same 23 files, one at a time under the same limit: 124 passed, none failed, 145 seconds. Looked at on sign-in, Overview, Activity, Cases, one case (with the closed amounts section open), Agreements, Ramp records and Portfolio comparison at 1440×900, and the one-bill page at 420×900: no console message, no failed request, no page wider than its window. The full run is the coordinator's, before it merges.

- **Company pictures** (the commit after the three above): `node --test web/*.test.cjs tests/helpers/*.test.cjs` → `tests 132`, `pass 132`, `fail 0`. The same 23 files, one at a time under the same limit: 124 passed, none failed, 121 seconds. Looked at on the Overview and Cases at 1440×900: both pictures in their tiles, no console message, no page wider than its window. No test changed.

## 7. Known limits and open items

- **Phone width is usable, not polished.** Ronok asked for the computer layout first and the phone later, since the demo does not use it. At 390×844 no page is wider than the window and every control is reachable, and the 390 px images above show the present state. Spacing, type sizes and the order of blocks at that width have not had the pass the computer layout had.
- **Reference window.** The first screen is designed for 1440×900. At 1280×720 the Overview's decision button starts about 40 px below the first screen; record at 1440×900 or larger, or scroll once.
- **More tools keep the server's own codes.** Case ledger, the case inspector, Onboarding lab, Policies and Integrations were restyled and tidied, not redesigned. They show stage and eligibility as the server's words in capitals (for example `RETROSPECTIVE_REVIEW`), and the case inspector shows an evidence detail as the server's JSON text. The Onboarding lab shows both offered actions as primary buttons.
- **Quotes keep the source's own line breaks.** A clause is shown byte for byte, so in a wide column its lines can end early. That is deliberate.
- **Light theme only.** The page declares a light colour scheme; no dark theme was made.
- **Two of the three type voices are the system's.** Quoted text uses the system serif and references the system monospace, so their letter shapes differ between a Mac and other machines. Bundling a serif and a monospace would fix that; it needs Ronok's yes to two downloads.
- **One font file.** The typeface is a 344 KB file loaded from the app itself on each page load. Until it arrives no text is drawn in another face (up to three seconds on a slow connection; a few milliseconds locally), so text never reflows.
- **The panel beside Ramp** (`#ramp-bill/<id>`) is tested at 420×900 in Chrome, not inside the extension's side panel; the coordinator is checking it there.

### For the coordinator or Ronok

- **A field from the server (optional).** The claim record's `ledger.posted` and `ledger.applied` are constants (`"0.00"`, `uptime/correspondence.py:822`), so the case page shows Estimated, Claimed, Awarded and Disputed remainder in view and keeps all six exact values in the closed "Decision, unknowns and amounts as recorded". To show posting and application on the case page, the claim record would need the same per-stage values the workflow projection has in `finance.stages`. Nothing is wrong on screen today.
- **Wording still outside the interface's hands.** The interface's own sentences now say "reviewer" (finding A1). Two things on screen still say "human" or "person" because the server sends them: the claim stage `HUMAN_REVIEW`, shown as "human review" on the Overview, in the Cases list and in the reading page's own sentences that name that stage; and the server's pause detail for a conflicting record ("… a person must review it."). The list of server strings went to the coordinator.
- **Nothing else is waiting on a decision.**
