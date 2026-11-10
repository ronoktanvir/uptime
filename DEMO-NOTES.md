# Demo line notes (November 10, 2026)

This branch, `demo/film-20261110`, is a separate line for the film. It was cut from `main` at `96e37d7` when Ronok lifted the project's standing rules for 24 hours of demo preparation ("this is all just for the demo ... I'm doing that to change the rule"). `main` is untouched by it. This file says what the demo line does differently, so the two can be brought back together later.

## What was done in Ramp's sandbox, and by whom

- **A vendor and a bill were entered by the coordinator, an AI agent**, in a browser window Ronok signed in to, at his instruction, on November 10 at about 03:15 PST.
  - Vendor: `Northwind Cloud`, state California, contact `billing@northwind-cloud.example` (a reserved address that reaches nobody), with "Invite this vendor" turned off.
  - Bill: invoice `NW-2026-04`, invoice date April 1, 2026, due May 1, 2026, one line "Cloud Hosting, 1 service-month, April 2026", USD 11,000.00, entity Save Time Inc. The payment method Ramp pre-filled was cleared, so no payment is set up. Not approved, not paid.
  - The state, the due date and the contact address are not in the walkthrough's fixtures; the form required them.
  - Ramp bill id: `b52cc017-9d2a-411d-bd81-7926a5c7e86f`.
- **A second bill was entered the same way** at about 03:45 PST, at Ronok's request for more than one qualifying bill: invoice `NW-2026-03`, invoice date March 1, 2026, due March 31, 2026, one line "Cloud Hosting, 1 service-month, March 2026", USD 12,000.00, same vendor and entity, payment method cleared, not approved, not paid. Ramp bill id: `a779dd0e-70ce-4a7d-83cd-3c3271925e7d`. In the walkthrough this is the invoice billed USD 1,000.00 above the amended rate.
- **A third bill, for the second company**, was entered the same way at about 04:10 PST after Ronok answered "Yes, add one": vendor `Corvid Data Cooperative` (state New York, contact `billing@corvid-data.example`, invitation off), invoice `CDC-2026-10-0117`, invoice date November 1, 2026, due December 1, 2026, one line "Corvid Ledger, Archive plan, monthly service fee, October 2026", USD 10,000.00, payment method cleared, not approved, not paid. Ramp bill id: `90e8214b-e6fa-4cb0-81b6-8c5f487b4cb3`.
- **Uptime has posted notes to Ramp through the API** since about 03:55 PST: at start-up with `--ramp-notes auto` the server posted one note on each matched Northwind bill and read each back. They appear in each bill's Activity under the author "Uptime".
- Ramp's sandbox has a "New credit" screen under Bill Pay, Vendor credits; none has been created. Ramp's API, as packaged here, has no call that creates a vendor credit.
- **The read of that bill** (the two read-only commands and the packaging script) was also run by the coordinator, with the Ramp credential file on this machine, which it did not open. The packaged record says `started_by: PERSON` because the packaging code writes that; the matched page therefore does not say who started the read.
- The credential already carries `bills:write`. No note has been posted by an agent; the note button is for Ronok to press.

## What the demo line adds to the product

- The side panel is a focused one-bill view. A Ramp bill whose vendor, invoice number and amount equal the walkthrough's April invoice is shown as matched, with the credit, the clause, the inputs and a button into the full app. A badge appears on the toolbar button while a matched bill is shown.
- `POST /api/ramp/notes` lets Uptime post one of two fixed notes on a matched bill through Ramp's API, only when the server is started with `--ramp-notes`.
- After each reviewer decision on the Overview, the steps that decision recorded are shown one at a time. They have already run when they appear.
- Automatic steps are tagged "Uptime agent". That means fixed automation under an approval a reviewer already recorded; no step in this walkthrough is a model's.

## How the demo line is run

- No full test suite per merge. The JavaScript checks and the focused tests for what changed are run, and the pages are looked at.
- Changed tests are listed in `DEMO-CHANGES.md`.
