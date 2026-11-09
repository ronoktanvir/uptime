# Ramp capability matrix

Role 3, November 9, 2026. The Ramp sources are the official OpenAPI as refetched at 11:01 UTC (SHA-256 `29571a47…`, 277 operations, the same set as the November 5 pin) and Ramp's help article on vendor credits (HTML SHA-256 `6ac21805…`); see [platform verification](../evidence/ramp-lineage-93/platform-verification-20261109.json). Nothing was refetched for this file. Connector behavior is from the current source on `work/submission-ramp-20261109`.

**Three different things.**
- A **comment** asks a person to look; it changes nothing about payment.
- A **payment intervention** (hold, approval step) changes what Ramp will do with the payment.
- A **credit application** reduces what is paid on a bill, using a vendor credit recorded in Ramp.

Uptime has done none of these itself in Ramp. One comment was posted by a person.

| Capability | Ramp operation and scope | Effect on payment | How Uptime confirms it | Who may perform it here | Current proof |
|---|---|---|---|---|---|
| Read records | `GET` bills, drafts, vendors, transactions, credits, comments; agreement list query (read-only `POST vendors/agreements`); `GET business`. Read scopes **granted** | None | Checksummed sanitized capture; per-resource coverage and pagination | Uptime, when a person starts the read (D06 matrix) | Captures on November 5 and November 9, all read-only. Vendor list complete at 411 |
| **Comment** on a bill | `POST comments/bills/{id}`; `bills:write` **granted** | **None.** Informational only | Same-thread `GET` finds the exact comment ID, text and time. A POST response alone stays uncertain | **A person** in Ramp's UI, or a person running Uptime's route ([packet](ramp-operator-packet.md)). Never an agent (blocker 3) | **One person-posted note** on `f74ba12c` (`376563cf…`, 2026-11-08 01:46:45 UTC), read back twice on November 8 and again on November 9. **No Uptime-origin comment** |
| **Payment hold** | `POST bills/{id}/hold`, `POST bills/{id}/release`; `bills:write` granted | **Blocks all payment rails** until released | `GET bills/{id}` shows `status_summary = ON_HOLD` after the request time. A hold already present beforehand isn't attributed to the request | A person in Ramp's UI. Uptime has no hold route | Never executed |
| Approval step | `POST approvals/{entity_type}/{entity_id}/add-step`; `approval_chains:write` **not granted**; Ramp publishes it as still in development | Payment waits for the added approver | None established | None | Never executed |
| Blank Canvas decision | `POST blank-canvas-approvals/{trigger_instance_id}`; `blank_canvas:write` | Acts on a configured procurement trigger, not a bill | None | None; no trigger is configured | Disabled |
| Draft bill create or update | `POST bills/drafts`, `PATCH bills/drafts/{id}`; `bills:write` granted | A draft isn't payable until submitted | Same-ID read-back | Blocked by the agent restriction; no person-run route is prepared | Tested only against a controlled provider (VAL-2 not met) |
| **Vendor credit creation** | **No public API.** Ramp UI: from a paid bill (⋯ → New Vendor Credit) or the vendor profile (New → Vendor credit) | None until applied | `GET vendors/credits` (active and fully used; archived not requested) | A person in Ramp, against a verified award (D09) | The demo business's credit list was complete and **empty** on November 9 |
| **Credit application** to a bill | **No public API.** Ramp UI: Apply available vendor credits → Split payment → Vendor credit, before payment starts or is batched | **Reduces the amount paid** on that bill | Both sides must agree: the bill's `applied_vendor_credits` and the credit's `applied_bills`, same amount and currency (`credit_links`). One-sided means unknown | A person in Ramp (D09). Uptime prepares and reads back only | Never executed. Demo bill: `NO_APPLIED_CREDITS` |

## Uptime's own records, not Ramp

| Uptime record | What it is | Never shown as |
|---|---|---|
| Local ledger award, credit and application (Northwind walkthrough) | Authored walkthrough state in Uptime's own database, destination "Local ledger" | A Ramp credit, a Ramp confirmation or recovered money |
| Lineage and read-back receipts | Uptime's checks over Ramp reads | A write to Ramp |
| Prepared operator instruction | What a person should do in Ramp | Something Uptime did |

## Facts that change the story

- Ramp describes `deep_link_url` as a link to the bill **in the ERP**. Uptime accepts it only when it is exactly a `demo.ramp.com` bill path. Demo bills carry none.
- The only verified Ramp link to the demo bill is the exact URL a person observed. Uptime confirmed it against the same bill by API read. Uptime never builds bill URLs from a pattern.
- Ramp's older "Apply vendor credits" toggle applies credits by accounting date and can pick a different credit. The operator procedure stops if only that toggle appears.
