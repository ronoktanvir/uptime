# Interface design: one visual system (handoff)

**Owner:** the design session started November 9, 2026, about 15:20 PST. **Branch:** `work/submission-design-20261109`, from `968c12b` (application code `6b93e31`). **Owns:** `web/`, the JavaScript checks in `web/*.test.cjs` and `tests/helpers/`, and the browser tests that drive these pages. Changed existing tests are listed in [the ledger](../TEST-CHANGES-submission-design-20261109.md).

This file is the plan and the record. Sections 1 to 4 were written before any code changed. Section 5 onward is filled in as each page lands.

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
| `--bg` | `#f6f8fb` | Page canvas | |
| `--surface` | `#ffffff` | Cards, sidebar, inputs | |
| `--sunken` | `#f8fafc` | Table heads, quotes, code | |
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

A system font stack, because the content security policy allows no external fonts: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`. References and digests use `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`. All amounts use tabular figures so columns of money line up.

| Role | Size / line | Weight |
|:---|:---|:---|
| Hero figure | 40 / 44 | 600 |
| Figure | 24 / 30 | 600 |
| Page title (`h1`) | 28 / 34 | 600 |
| Card title (`h2`) | 16 / 24 | 600 |
| Sub-heading (`h3`) | 14 / 20 | 600 |
| Body | 14 / 22 | 400 |
| Secondary | 13 / 20 | 400 |
| Label and caption | 12 / 16 | 500 |

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

## 3. Layout plan per page

Sizes checked: 1440×900 and 390×844, first viewport and full page.

| Page | First screen | Below, or one click away |
|:---|:---|:---|
| **Sign-in** | A centred card with the brand, "Sign in to Uptime", the account name, a drop area for the credential file and one sentence on where the key is kept. The navigation is hidden until sign-in. | — |
| **Overview** | Header, then the outcome: the credit (or the invoice after the credit is applied) beside the separate price exception. Under it the five-stage lifecycle across the full width, then the recovery card with the next decision beside "Needs attention". | The Ramp record ("Ramp bill: Not linked") and "Ask about this case" under the recovery card, then an Evidence group: service credit evaluations, price review and bill reconciliation. Agreement, coverage and review records are three closed sections at the foot. |
| **Activity** | Header, a one-line summary of routine steps with the server's two counts, then the step timeline: time, step, and who or what authorised it, tagged as a reviewer decision, an automatic step under a recorded approval, or a received event. A decision names the account exactly as the server sends it ("Decided by scripted-test-reviewer"); the interface never says a person decided. | Workflow history, the pointer to model jobs and the coverage history (closed). |
| **Cases** | Header and the list of cases: title, vendor, month, stage, outcome, amount, and a way in. | Setting up a case, access details and the complete record of each case, in closed sections. |
| **One case** | Back link, title and stage; the facts (amounts by stage, filing cutoff, next contact); then the correspondence in order with each vendor reply quoted and each step's actor. | Evidence and receipts, evaluation, dispute record and the complete server record, closed. |
| **Agreements** | Header and one card per agreement: vendor, state in the server's word with one plain sentence, what it covers, what the source establishes with each cited clause, and who performed the review steps as the server states it. A vendor's model proposal job sits directly under that vendor when one exists: status, model, times, each proposed term beside its exact quoted sentence, and the sentence that it is unreviewed and not approved. | Review history, requirements detail, version actions, test and evaluation forms and the raw record per vendor; "Add an agreement" (proposal generator and local intake) and access details for the page. All closed. |
| **Ramp records** | Header with read time and completeness, then the "Verified Ramp record" card: what it is, "Not a live read", the bill's facts as a field list, the Ramp link and the discussion. | The record list with its filter and search, then coverage, permissions, reconciliation and writeback evidence, closed as today. |
| **Reading a vendor reply** | The same brand bar and sign-in card; then the reply text as a quote, the claim facts, and the reviewer's own reading as a form. Suggestions keep the heading "Untrusted suggestions" and "requires your review". | Source details, permission and request details, closed as today. |
| **Advanced tools** | Restyled through the shared components (cards, tables, field lists, pills). Their structure and the server's own labels are unchanged. | — |

## 4. How it is checked

- **Looking.** After each change a fresh throwaway walkthrough is served from this worktree on a port in 8871–8879 and captured with Playwright driving installed Chrome, signing in through the ordinary form. Each image is opened and inspected for overlap, clipping, overflow, misalignment, uneven spacing, weak contrast, bad wrapping, layout shift, horizontal scroll and console or page errors. The capture script reports page height, any element wider than the viewport, and every console message.
- **States.** Sign-in; Overview before any decision and after each of the four; Activity; Cases and one case; Agreements; Ramp records; the reading page. The two recorded model screens are served from copies only.
- **Checks.** `node --test web/*.test.cjs tests/helpers/*.test.cjs` and the focused browser tests, each under a hard time limit. The full Python suite is the coordinator's, after merging.

## 5. What changed per page

Filled in as each page lands.

## 6. Known limits

Filled in at the end.
