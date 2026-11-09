# Ramp operator packet (for a person; nothing here was executed)

Role 3, November 9, 2026. This packet prepares four person-operated items. **No step was run by an agent, and none may be.** The agent-run posting retest was refused by automatic approval review and is never retried or rerouted.

Each item says what it reads or writes, what must already be true, and how Uptime checks the result. Decisions marked **Ronok** are his to make.

## 1. Re-verify the existing person-posted note (read-only)

Already done on November 8 and November 9. Repeat it just before filming:

```bash
RAMP_ENV=sandbox UPTIME_RAMP_CREDENTIAL_FILE=~/.config/uptime/ramp-demo-native.json uv run --locked python scripts/ramp_prefilm_check.py --output-dir ~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109
```

- **Reads:** the business; bill `f74ba12c-95d0-582d-9f62-26d8057d1d37`; one bounded records sync (bills, vendors, transactions, agreements, credits, approvals, comments).
- **Writes:** nothing in Ramp; one owner-only receipt outside the repository.
- **Pass means:** same business `1569e402-460e-4952-adad-9df27db628a0` and same bill. Vendor, entity and amount (USD 840) unchanged. No credit linked. Note `376563cf-950c-409d-b3d8-a68599c45fa0` re-observed. Clean evidence-gap lineage.
- **Doesn't prove:** who clicked Post, or any Uptime-origin write.

## 2. Uptime-origin comment through the established route (person-run; **Ronok** decides whether and where)

This is the only route that would turn "Uptime-origin posting" from an open proof requirement into evidence. It is the existing procedure in [NATIVE-OPERATOR.md](../NATIVE-OPERATOR.md). A person runs every step; an agent runs none.

**Exact target.** A bill in business `1569e402-460e-4952-adad-9df27db628a0`. The obvious target, `f74ba12c`, already carries the person-posted evidence request, and Uptime's lineage plan for it is "already surfaced; don't post again". A second comment there would duplicate the request, so **Ronok** chooses:
- (a) `f74ba12c`, accepting a second, Uptime-origin comment;
- (b) another bill in the same business with its own evidence-gap finding;
- (c) not running it, in which case the proof stays open.

**Exact body.** The fixed `EVIDENCE_REQUIRED` template in `uptime/ramp_workflow.py`, followed by an opaque `[uptime:<action id>]` marker. Nothing else; no amount, party name or URL:

> Uptime contract review: price compliance is undetermined. Before approving this bill, obtain the governing signed terms and amendments, and verify itemized charges, service dates, quantities and tax treatment against those terms. No approval, payment instruction, entitlement or realized savings is asserted.

**Prerequisites** (blocker 2; all must hold, or the server refuses):
1. The Ramp app holds `business:read`, `bills:read` and `bills:write`. They are granted per the [grants receipt](../evidence/native-demo-grants-20261106.json); preflight re-checks them.
2. A sandbox installation, not rehearsal mode, with a **current signed native release**. `gates.native_install_ready` must pass. Today there is no current `release_attestation.json`, so this fails until the release evidence exists.
3. A protected native configuration (0700 directory, 0600 file) naming the business and a **named human reviewer** whose public key matches the workspace enrollment.
4. An **independent issuer** registered with `native_actions = ("bill.comment.create",)` for this business, and signed mandates for each staged request (`REVIEWER-MANDATES.md`).
5. A current operator-imported capture of that business (`scripts/ramp_refresh_workspace.py`) containing the target bill.
6. The Northwind workflow is **not** started in this workspace. The isolation check in `uptime/server.py` refuses that combination, and it stays.

**Steps (person):** run `preflight`, then `prepare --object-id <bill>`, inspect `plan`, `review` (expires within 5 minutes), then `execute` with the independently mandated stage files. These are the commands in NATIVE-OPERATOR.md, steps 1–5.

**Same-object read-back checks.** Delivery counts only when all of these hold:
- the same bill's paginated discussion contains exactly one comment with the action's marker;
- its ID equals the POST response ID;
- its text equals the reviewed body byte for byte;
- the business re-read equals the configured business.

Then run `scripts/verify_ramp_comment.py` with `--comment-id` for an independent read-only confirmation.

- **Stop conditions:** a missing, duplicate or changed comment; a different business; or a timeout. Any of these leaves the action `UNCERTAIN`. A person runs `reconcile` (GETs only). **Never post again.**
- **What it proves:** one Uptime-origin informational comment on one bill. It doesn't prove a payment stop, an approval, an entitlement or recovered money.

## 3. Credit application (D09)

**Doesn't apply to the demo bill.** It has no governing agreement and no award, and its credit list was complete and empty. Creating a Ramp credit for it would invent value.

The procedure for a real case is in [RAMP-CASE-LINEAGE.md](../RAMP-CASE-LINEAGE.md#person-operated-credit-procedure-d09). It needs a vendor award verified by a role separate from the operator, which isn't named yet (**Ronok or team**), and an answer on one-person versus two-person execution (D06 sub-question, **Ronok**). Uptime's check afterwards is `scripts/ramp_credit_readback.py`: only `VERIFIED_BOTH_SIDES` counts.

## 4. Fresh read-only capture with vendor names (for **Ronok** to approve; I don't run it)

The saved captures predate the new display fields, so vendor names and invoice numbers show as "not captured". A person can refresh them with two read-only commands:

```bash
RAMP_ENV=sandbox UPTIME_RAMP_CREDENTIAL_FILE=~/.config/uptime/ramp-demo-native.json uv run --locked python scripts/ramp_verify_browser.py --bill-url https://demo.ramp.com/bill-pay/bills/list/f74ba12c-95d0-582d-9f62-26d8057d1d37 --output ~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109/association-names.json
```

```bash
RAMP_ENV=sandbox UPTIME_RAMP_CREDENTIAL_FILE=~/.config/uptime/ramp-demo-native.json uv run --locked python scripts/ramp_sync.py --page-size 100 --max-pages 5 --detail-limit 100 --output ~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109/records-names.json
```

**What they read:**
- **Association command:** token exchanges for `business:read` and `bills:read`, then `GET business` and `GET bills/f74ba12c…`.
- **Records sync:** token exchanges for `bills:read`, `vendors:read`, `transactions:read` and `approvals:read`, plus `purchase_orders:read` only for POs linked from bills; one scope each. It reads:
  - lists of bills and drafts (6 today);
  - vendors, with up to 500 listed and 100 detail records; vendors linked from bills come first;
  - transactions (up to 500 listed; more exist);
  - the agreement list query;
  - vendor credits, including fully used ones;
  - approvals for captured parents;
  - comments on each captured bill.

**What is kept:** sanitized records only. New: the bill's `vendor.name`, `invoice_number` and the vendor `name`, as bounded exact text. No memos, contacts, URLs, comment text or emails. **Writes:** none in Ramp. Two new owner-only files.

After a person runs them, I can rebuild `fixtures/ramp/verified-demo-bill.json` from those two files (same checks, now with names), as a separate reviewed commit.

## 5. A matching authored Northwind bill in Ramp's demo (proposal for **Ronok**; not created)

It would let one screen show an authored contract finding next to a Ramp bill. It changes D02 (a delegated default keeps Northwind out of Ramp), so it's Ronok's decision.

**Consequence to accept first:** the Northwind agreement is authored, not signed by a real customer. Under the current rules it can bind only as hypothetical terms (`SYNTHETIC_NEGOTIATED`). Ramp context then shows the finding as a scenario (`HYPOTHETICAL`, `finding_attachable: false`), never as an entitlement on the Ramp record. Calling the authored terms operator-attested would misstate them. **My recommendation: don't create it for the submission.** Tell the story with the two clearly separate records. If Ronok still wants it, these are the fields and steps for a person.

**Proposed fields** (from `fixtures/northwind/invoices.json`, the March invoice, the one with the 1,000 price finding):

| Field | Value |
|---|---|
| Vendor | Northwind Cloud (a new demo vendor; not an existing one) |
| Entity | The demo business's existing entity |
| Invoice number | `NW-2026-03` |
| Invoice date | 2026-03-01 |
| Amount | USD 12,000.00 |
| Line | Cloud Hosting, 1 service-month, March 2026, USD 12,000.00 |
| Payment | Leave unpaid and pending approval; don't schedule payment |
| Memo | None. Put no contract text, amount claims or "Uptime" wording in Ramp |

**Manual steps (person, in demo.ramp.com):**
1. Create the vendor "Northwind Cloud" in Bill Pay.
2. Create the bill with the fields above. Don't submit it for payment.
3. Copy the exact bill URL from the browser.
4. Run item 4 with that URL instead of `f74ba12c`.
5. Hand Uptime the two files.

Binding the authored terms to the new bill would then take a reviewed association and price binding by role 3 and the terms owner. It would be shown as hypothetical, as described above. Nothing would be posted to Ramp.
