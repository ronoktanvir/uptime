# Role 3: the supported Ramp connection

Owner `agent4`. Branch `work/submission-ramp-20261109`, from `origin/main` at `55ea607`. November 9, 2026.

This file is the role's handoff: findings, blockers, the Ramp-context fields the interface renders, the plan and its status. It is a dated record and doesn't show that work is still running.

No live Ramp read and no Ramp write were made for this role. Earlier on November 9, under the W1 lane, read-only reads were made at 11:02, 12:35 and 12:39 UTC; they're recorded in [`evidence/ramp-lineage-93/`](../evidence/ramp-lineage-93/).

## (a) The judge's Ramp findings, reproduced on current source

| Judge finding | What the source shows on `55ea607` | Class |
|---|---|---|
| The main screen reads "Ramp bill: Not linked", destination "Local ledger" | `web/workspace_ui.js:156` shows `Not linked` when the workflow has no linked Ramp bill. `uptime/northwind_workflow.py:37` fixes the destination as `Local ledger`. Northwind is an authored walkthrough that D02 keeps out of Ramp, so both labels are accurate | Accurate state. The weakness is that the screen gives no Ramp context at all |
| The Ramp page is a saved capture marked not live and `TRUNCATED` | For the presentation tenant (`bears`), `RampWorkspace._observation` falls back to the packaged capture `fixtures/ramp/native-observed.json`, observed **2026-11-05 00:36 UTC**. In replay mode its freshness is `HISTORICAL_REPLAY`, which `web/ramp_ui.js:13` renders as "Saved capture (not live)". Vendors, transactions, POs and approvals are `TRUNCATED`: 40 listed with more pages, 12 retained | Accurate labels. The page doesn't say *what* is missing, or that the bill list itself is complete (6 of 6) |
| Bills are listed by UUID with no vendor names | Each worklist row's `vendor` is the native `vendor_id` (`uptime/ramp_findings.py:161`). The records sanitizer keeps no names or invoice numbers by design (`_RECORD_KEYS` in `uptime/ramp_records.py`), so there is nothing else to show | Usability defect, from a deliberate data-minimization choice |
| — (found while reproducing) | The packaged capture comes from an **earlier installation**. Its six bills don't include demo bill `f74ba12c`, and it has no comments. The one real Ramp artifact (the person-posted note on `f74ba12c`, comment `376563cf…`) **can't be reached from the Ramp page** | Usability and evidence defect |
| — (found while reproducing) | `provider_uri` is accepted only from Ramp's own `deep_link_url` (`ramp_findings._link`). The demo bills carry none, so every row shows "Native destination unavailable". The one verified bill URL, observed by a person, exists only in the association receipt | Missing functionality: the associated record can't be opened from Uptime |
| No Uptime write has ever reached Ramp; the one Ramp artifact is a comment a person typed | True. See the three separate blockers below | Blocked; a person must complete the established route |

## (b) Three different blockers

| Blocker | What it is | Evidence | Who can clear it |
|---|---|---|---|
| **1. Provider permission and capability** (Ramp) | What the Ramp demo app may call, and what Ramp offers at all. Comments and bill holds need `bills:write`, which **is granted**. Approval steps need `approval_chains:write`, which isn't granted, and the endpoint is published as still in development. **Vendor credit create and apply have no public API**: this is a missing capability, not a missing permission | [Grants receipt](../evidence/native-demo-grants-20261106.json): `vendors:read`, `bills:read` and `bills:write` show `EXACT_GRANT`. [OpenAPI check](../evidence/ramp-lineage-93/platform-verification-20261109.json): `29571a47…`, 277 operations, no credit write | Ramp app admin, for scopes. Credits stay person-operated in Ramp's UI (D09) |
| **2. Local release requirements** (Uptime's own gates) | Uptime refuses native actions unless every gate holds. The binding's `_guard` requires sandbox mode, no rehearsal, `gates.native_install_ready`, a matching tenant and an unchanged protected configuration. Each action needs a **named human reviewer** whose key matches the offline enrollment, and a signed review of that exact action that expires within 5 minutes. The server refuses to run the Northwind workflow beside a native connection (isolation check) | `uptime/ramp_native_binding.py:209-219` and `:243-248`; `uptime/ramp_workflow.py` `_verify_review`; `uptime/server.py:38-39` | An enrolled human reviewer, in a sandbox installation that passes the release gate. **The isolation check stays** |
| **3. Agent posting restriction** (execution policy) | An automatic approval review of the agent's action refused the agent-run native posting retest, with the stated reason "possible cybersecurity risk". It isn't a Ramp permission, since `bills:write` is granted, and it isn't an Uptime gate. Human approval of a handoff doesn't override it | [TEAM-DECISION-HANDOFF](../TEAM-DECISION-HANDOFF.md#native-execution-restriction-is-not-another-missing-scope-decision); `docs/v4/STATUS.md`; integration90 BLOCKERS | Only a person may run the operator route. **No agent retries or reroutes it** |

So an Uptime-origin comment needs blocker 2 satisfied by a person, and the act itself performed by that person (blocker 3). It doesn't need a new Ramp permission (blocker 1). A credit application needs no Uptime write at all; it's person-operated in Ramp, with Uptime reading back the result.

## (c) Ramp-context fields for the interface

Implemented at `5f5cee4` and `1527bc0`; the names below are final. `GET /api/ramp/workspace` returns `capture`, `records[].ramp_context` and `verified_record`. `GET /api/ramp/records/{id}` returns `ramp_context`. All are read-only and computed from saved Ramp captures; the interface never computes or infers any of them.

**Capture** (`capture`, one per response):

| Field | Meaning |
|---|---|
| `business_id` | The installation-verified Ramp business, or `null` for the packaged capture (no business proof) |
| `custody` | `operator_import` (a person ran the read) or `packaged_receipt` (a saved file shipped with the app) |
| `custody` values | `operator_import`, `packaged_receipt` or `packaged_verified_record` (the saved demo-bill record) |
| `observed_at`, `completed_at` | When Ramp was read, as ISO-8601 UTC strings; the interface formats them |
| `freshness` | `FRESH` (24 hours or less), `STALE` or `HISTORICAL_REPLAY` |
| `capture_checksum` | Integrity digest of the saved capture |
| `resources[]` | Per resource: `name`, `status`, `complete`, `retained` (records kept), `listed` (IDs Ramp returned), `list_complete`, `has_next`, `pages_read`, `page_size`, `max_pages`, `detail_budget_reached` |
| `account_complete` | `true` only when the bill, transaction and purchase-order lists that were requested are all complete. Otherwise the screen must say the list is partial |
| `incomplete_lists` | Names of the requested worklist lists that are partial, for example `["transactions"]` |

**Record** (`ramp_context`, one per worklist row and on record detail):

| Field | Meaning |
|---|---|
| `business_id`, `object_type`, `object_id` | Exact native identity |
| `vendor_id`, `vendor_name` | `vendor_name` comes only from a captured vendor record. `null` means "not captured"; never inferred |
| `entity_id` | Native entity |
| `invoice_number` | From the bill when captured; else `null` |
| `amount` | `{currency, amount}` decimal string; never recomputed |
| `status`, `status_summary`, `approval_status` | Ramp's own values, for example `OPEN`, `APPROVAL_PENDING` and `PENDING` |
| `issued_at`, `due_at` | Native dates |
| `observed_at`, `capture_checksum` | The read this row came from |
| `ramp_link` | `{url, basis}`. `basis` is `PROVIDER_DEEP_LINK` or `OPERATOR_OBSERVED_URL` (a person observed that exact URL, verified against the API). Otherwise `null`; never constructed |
| `agreement_binding` | `{status: BOUND, NONE or CONFLICT; contract_id; association_digest}` from a reviewed association only |
| `finding_attachable` | `true` only when business, vendor, bill and agreement are all bound exactly. When `false`, any contract finding is withheld from this record |
| `discussion` | `[{comment_id, created_at, attribution}]`. `attribution` is `PERSON_POSTED_VERIFIED_READBACK` when the committed human-note receipt matches, else `UNATTRIBUTED`. A local receipt never shows as a Ramp confirmation |
| `credit_links` | Status from the D09 read-back (`NO_APPLIED_CREDITS`, `VERIFIED_APPLICATIONS`, `REVIEW_REQUIRED` or `UNKNOWN`), with `reasons`, `applied_verified_minor` and `links` |
| `native_confirmation` | Always `RAMP_READ_ONLY`: these fields describe what Uptime read from Ramp, never a write |
| `actual_recovery` | Always `null` |

**Verified record** (`verified_record`, on the workspace overview; only in the packaged presentation workspace, otherwise `null`):

| Field | Meaning |
|---|---|
| `kind`, `live_read`, `started_by`, `excerpt`, `statement` | `SAVED_VERIFIED_RECORD`, `false`, `PERSON`, `true`, and the excerpt statement. The panel reads "Saved record read from Ramp … started by a person. Not a live read." |
| `capture` | The same capture summary as above, for business `1569e402…`, read 2026-11-09 22:00:38 UTC (Ronok's run), plus `excerpt_checksum`. `capture_checksum` refers to the private full read |
| `ramp_context` | The record fields above for bill `f74ba12c…`: vendor name "DocuSign" and invoice "DD-PREAPPROVAL" from the captured records, an operator-observed link, binding `NONE`, `finding_attachable: false`, the note attributed to a person, credits `NO_APPLIED_CREDITS` |
| `finding` | `{outcome: INSUFFICIENT_EVIDENCE, finding_kind: UNBOUND_RECORD, missing, amount: null}` |
| `contract_terms`, `actual_recovery` | `NONE_BOUND`, `null` |

**Requests to role 4 (gent7).** The Ramp page already renders all of this inside `web/ramp_ui.js`: the verified record panel, worklist attribution and partial-list statement, and row and record context. No mount or route change is needed for that. **Optional:** a link from the companion workflow's Ramp section to the Ramp page (`#ramp`), so the "Ramp bill: Not linked" card can point to the verified record. That is a route change for gent7 through the coordinator.

## (d) Plan

1. **Capability matrix** (task 1, 10). Comment vs payment hold vs approval step vs credit application, each with its operation, scope, payment effect, read-back and current proof. It reuses today's OpenAPI verification; the docs aren't refetched.
2. **Read-only worklist** (tasks 3, 4, 6, 7). In `ramp_records`, add optional, bounded display fields (`vendor name`, bill `invoice_number`), with the snapshot schema kept backward-compatible so old captures read as "not captured". In `ramp_workspace`, project `capture` and `ramp_context`, carry the verified bill URL from the association receipt, and bind findings only through `ramp_association`/`ramp_case_lineage`. In `web/ramp_ui.js`, add vendor name, invoice, amount, status, observation time, the exact link, and an explicit "partial list" statement with counts. Plus identity tests: a Northwind finding never attaches to `f74ba12c`; a local receipt never satisfies a native confirmation; the person-posted note stays attributed to the person.
3. **Getting the real bill onto the page** (task 5, proposal first). The packaged capture predates `f74ba12c`. I'll propose **packaging the November 9 checksum-verified capture and its association receipt** (read-only files, no credentials) as the presentation tenant's Ramp context, replacing the November 5 file. Changing which capture `bears` loads is a W1 change, and I'll wait for the coordinator's yes. The isolation check in `server.py` is untouched; the companion workflow gets a read-only link to that context, not a native connection.
4. **Operator proof packet** (task 8). The exact target, note body, prerequisites (blocker 2), the person-run route, and same-object read-back with `scripts/verify_ramp_comment.py` and `scripts/ramp_prefilm_check.py`. Not executed.
5. **Northwind bill proposal** (task 9). Proposed fields and manual steps for a person to create a matching authored bill in Ramp's demo. Not created. It changes D02 (a delegated default), so it goes to Ronok as a proposal.
6. **Fresh capture with names.** The existing captures predate the name fields. I'll prepare a person-run read-only command (`scripts/ramp_sync.py` at the existing bounds, then `scripts/ramp_refresh_workspace.py`) and state exactly what it reads, for the coordinator to put to Ronok. I won't run it myself.

## Status

## Delivered

| Deliverable | Where |
|---|---|
| Supported-capability matrix (task 1, 10) | [ramp-capabilities.md](ramp-capabilities.md) |
| Read-only worklist: names, invoice, amounts, statuses, read time, exact links, partial captures (tasks 3, 4) | `27ac360`, `5f5cee4`, `318668b` |
| Verified demo-bill record beside the worklist (task 5, coordinator option A) | `1527bc0`, `fixtures/ramp/verified-demo-bill.json` |
| Exact bindings before a finding shows on a Ramp record (task 6); evidence gap kept on the unrelated bill (task 7) | `uptime/ramp_context.py`; `tests/test_ramp_context.py` |
| Operator proof packet (task 8), fresh-capture command, Northwind bill proposal (task 9) | [ramp-operator-packet.md](ramp-operator-packet.md) |

**Acceptance criteria:**
- **A judge can open the exact associated Ramp record from Uptime:** the "Open this bill in Ramp" link in the Verified Ramp record panel, basis "observed by a person, confirmed by API read".
- **Read freshness, missing evidence and object identity are inspectable:** the read time and partial-list statement, the per-record business, vendor, entity and bill identity, binding status and the evidence-gap finding.
- **A local receipt can't satisfy a native confirmation:** `native_confirmation: RAMP_READ_ONLY`; tested with Local ledger activity beside a Ramp capture.
- **The human-posted comment stays attributed to the person:** `PERSON_POSTED_VERIFIED_READBACK`, matched to the committed receipt.
- **Uptime-origin posting stays an open proof requirement:** packet item 2.

**Needs a person or Ronok:**
- whether and where to run the Uptime-origin comment route (packet item 2);
- the Northwind bill decision, which changes D02; I recommend against it (item 5);
- the award-verification role and the D06 two-person question.

## Status log

- 13:08 PST: this file. Implementation follows in focused commits; the changed-test ledger is [`TEST-CHANGES-submission-ramp-20261109.md`](../TEST-CHANGES-submission-ramp-20261109.md).
- After 13:08 PST: coordinator approved option A (verified demo-bill panel), with conditions; all applied.
- 13:24 PST: worklist, context projection, verified record, capability matrix and operator packet pushed. Focused: 1,155 passed, 1 warning; Node 109 passed.
- 14:00 and 14:03 PST: Ronok ran the two read-only capture commands himself. 14:09 PST: verified record rebuilt as a minimal excerpt with names (packet item 4). Same bill, business, USD 840 and note `376563cf…` as before. Vendor "DocuSign", invoice "DD-PREAPPROVAL".
