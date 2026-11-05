# Native Ramp read observations

`uptime.ramp_records.sync_records` imports bounded, sanitized observations through an injected provider. `scripts/ramp_sync.py` is the operator entrypoint that constructs the existing fixed sandbox SDK. The UI/loader never constructs a provider, exchanges tokens, follows UI links, or reads credentials. Original V3 capture, draft journal and fixture adapter remain separate and unchanged.

The reader makes no financial or entitlement determination. A complete resource means its specified list and selected details were fetched successfully, not that its fields establish an eligible expense, contract, customer account, award, recovery or permission to write. Missing fields stay null. Complete empty lists differ from unavailable resources. Read scopes and successful reads are not evidence of a write grant or commercial entitlement.

## Operator command

After root integrates the commit, run from the integrated repository on the authorized machine:

```sh
RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com \
  /Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python scripts/ramp_sync.py \
  --all-purchase-orders --page-size 10 --max-pages 1 --detail-limit 10 \
  --output runtime/ramp-records.json
```

Omit `--all-purchase-orders` to preserve linked-only PO behavior. The Python argument is `include_unlinked_purchase_orders=False` by default; pass `True` explicitly to enable discovery. The flag does not promise a full inventory: page/detail bounds still apply. The command prints only checksum and resource counts/status, writes the sanitized snapshot atomically with mode 0600, and returns nonzero for unavailable/forbidden/partial resources. An intentional bounded `TRUNCATED` sample is not a command failure.

`--scope-only` exchanges independent tokens for the five read scopes, makes no resource calls or writes, and prints grant metadata only. It cannot be combined with `--all-purchase-orders`. `--output` is required for record mode and optional for scope diagnostics. Validate arguments before credential construction. No write flag exists.

## Exact public operations

All paths below are under `/developer/v1/`, fixed to `https://demo-api.ramp.com`. No redirects, arbitrary destinations, fallback scopes, guessed endpoints or banking/contact reads are used.

| Resource | Operations | Exact scope |
|---|---|---|
| Bills and drafts | GET `bills`, `bills/drafts`, and their UUID details | `bills:read` |
| Vendors | GET `vendors` and `vendors/{id}` | `vendors:read` |
| Transactions | GET `transactions` and `transactions/{id}` | `transactions:read` |
| Agreements | POST **query** `vendors/agreements` with `{page_size,start?}`; GET `vendors/agreements/{id}` | `vendors:read` |
| Purchase orders | GET `purchase-orders/{id}`; optional GET `purchase-orders` | `purchase_orders:read` |
| Vendor credits | GET `vendors/credits?include_fully_used=true`, GET `vendors/credits/{id}` | `vendors:read` |
| Approvals | GET `approvals` with uppercase `entity_type=BILL` or `TRANSACTION`, repeated `entity_ids` query values | `approvals:read` |
| Bill/draft comments | GET `comments/bills/{id}` or `comments/draft-bills/{id}` | `bills:read` |

Each token must report exactly the independently requested singleton scope; missing scope metadata, missing grants or extra grants prevent dependent calls. Token failures do not stop unrelated resources. Agreement POST is the documented query under `vendors:read`; its body accepts only pagination fields. Generic provider request still rejects every other POST, all PATCH/DELETE, and nonallowlisted filters. Existing explicitly gated V3 draft mutations use their existing separate method.

SDK `Token(value, granted, expected, scope_reported=True)` and `.exact` are unchanged. `NATIVE_READ_SCOPES`, `WORKFLOW_SCOPES`, `TOKEN_SCOPES` expose the explicit token allowlists. Workflow token capabilities add `transactions:write`, `blank_canvas:write`, `unified_requests:read`, `custom_forms:read`, `spend_programs:read`, `spend_requests:read`; existing `bills:write` remains supported. Only the separately governed workflow adapter may use those grants. The records synchronizer never requests them. Token availability does not enable mutations through `request()`.

## Bounds and coverage

`page_size`: 2–100 (default 10); `max_pages`: 1–10 per list/parent (default 1); `detail_limit`: 1–100 per resource (default 10). Bills and drafts share a detail budget. Linked and independently listed POs also share a detail budget; linked IDs have priority and overlap is fetched once. Approvals/comments each have at most `detail_limit` parent reads, each with the same page bound. At most `6*max_pages + 6*detail_limit + 2*detail_limit*max_pages` resource requests, plus `max_pages` when independent POs are enabled, plus five token exchanges. No automatic retries.

Next-page URLs are untrusted: exact sandbox API origin/path only, unchanged initial filters, one bounded cursor, no extra query parameters/fragment, no repeated cursor. The reader reconstructs a fresh allowed request, including POST query bodies. Invalid pages, duplicates, oversized pages and detail-ID mismatches produce safe issues. Failed details never silently fall back to list summaries.

Statuses:

- `COMPLETE`: successful listed records/details within declared coverage.
- `EMPTY`: successful complete read with zero records.
- `TRUNCATED`: clean observations stopped at a page/detail/parent bound, or dependent parent coverage is incomplete.
- `PARTIAL`: at least one retained record plus a read/validation error.
- `FORBIDDEN`: no retained records and an HTTP 403 prevented the read.
- `UNAVAILABLE`: no retained records and absent/mismatched grant or other read/validation failure.
- `NOT_REQUESTED`: optional discovery disabled or no captured parent IDs to fetch. Lack of sampled PO links does not establish absence of POs.

Every resource exposes `coverage` and safe `issues`. List coverage has `pages_read,listed,list_complete,has_next,page_size,max_pages,issues`; details add `details_attempted,details_read,detail_complete`. Child coverage identifies its parent scope and parent IDs. `complete` is true only for `COMPLETE`/`EMPTY`. Coverage is never an atomic provider snapshot or an inventory beyond documented list defaults (for example transaction defaults exclude declines, PO/agreement defaults exclude archived records).

PO coverage separates `LINKED` from `INDEPENDENT_POs`; independent coverage has its own status/counts/completeness. Records identify their `discovery` source(s). Bill `purchase_order_id` and PO `bill_ids` preserve provider assertions independently. Only both matching IDs **and** vendor/entity identity establish `reciprocal_bill_ids`. Same vendor/name/amount, nearby dates, agreement metadata or incidental visibility never create an association. One-sided links remain observable without becoming reciprocal.

## Snapshot schema `uptime-ramp-records/1`

Envelope: `schema, origin, observed_at, completed_at, resources, checksum`. Times are UTC ISO8601; the interval describes a non-atomic capture. `resources` has exactly `bills,vendors,transactions,agreements,purchase_orders,credits,approvals,comments`. Each is `{status,records,complete,grant,issues,coverage}`. `grant` preserves safe requested/granted/missing/unexpected scope metadata, diagnosis and state; issue bodies contain only a fixed code, optional native object ID and HTTP status, never raw provider error text.

`checksum` is SHA256 of sorted compact JSON excluding `checksum` and loader-added `snapshot_status`, with nonfinite numbers forbidden. It detects local corruption, not provider authenticity or organization identity. `_validate_snapshot` checks the complete schema, monetary arithmetic, completeness consistency, record identities and reciprocal links. `load_snapshot(path, at=None, max_age_seconds=86400)` also checks freshness, future timestamps and a 32 MB size bound, makes no network calls, and adds `snapshot_status`. Invalid data returns unavailable empty resources; stale data remains historical with `STALE`. Even fresh data has `usable_for_evaluation:false` until an independent scoped evidence/contract evaluator establishes applicability.

Every record has native `id` and `sources:["LIVE_RAMP_SANDBOX"]` as observation provenance. In tests this is only an injected synthetic transport exercising the provider contract; no test output is a live receipt. IDs are never display names, customer names, business-ownership proofs or contract mappings. `vendor_id` may be null; transaction `merchant_id` is a different namespace and never becomes `vendor_id`.

Money: `{amount, currency, amount_minor, minor_unit_conversion_rate}`. `amount` is a decimal **string** in major units; `amount_minor` is the exact signed integer. A nullable/missing published conversion rate leaves `amount:null` and preserves minor amount/currency. No guessed USD divisor or FX conversion. Transaction `entity_amount` uses its explicit entity conversion rate; `merchant_amount` has no documented own scale and retains unscaled minor units. Deprecated transaction float amounts are not substituted.

Record fields, in addition to `id,sources`:

| Resource | Fields |
|---|---|
| bills | `kind` (`bill`/`draft`), `vendor_id,entity_id,account_id:null,account_identity,status,approval_status,status_summary,sync_status,created_at,issued_at,due_at,paid_at,archived_at,accounting_date,posting_date,draft_bill_id,purchase_order_id,item_receipt_ids,amount,lines,applied_credits,deep_link_url` |
| vendors | `parent_vendor_id,default_entity_id,merchant_id,status,is_active,created_at,updated_at`; status comes from native approval_status |
| transactions | `vendor_id:null,entity_id,merchant_id,card_id,spend_program_id,original_transaction_id,amount,merchant_amount,original_amount,status,sync_status,all_requirements_met_and_approved,user_transaction_time,settlement_date,accounting_date,updated_at,lines`; status comes from native state |
| agreements | `vendor_id,currency,amount,renewal_status,is_active,auto_renewal,created_at,updated_at,archived_at,deleted_at,start_date,end_date,last_date_to_terminate,purchase_order_ids,lines:null`; vendor comes from detail `payee.uuid`, amount from `total_value`; untyped agreement lines are not contract terms |
| purchase_orders | `vendor_id,entity_id,spend_program_id,spend_request_id,status,receipt_status,creation_source,amount,spend_total_amount,created_at,archived_at,promise_date,spend_start_date,spend_end_date,bill_ids,transaction_ids,item_receipt_ids,three_way_match_enabled,lines,reciprocal_bill_ids,discovery,ramp_url`; status comes from native billing_status |
| credits | `vendor_id,entity_id,reference_bill_id,accounting_date,created_at,archived_at,total,remaining,total_applied,applied_bills,applied_drafts,lines` |
| approvals | `id_kind:"parent_resource",object_id,object_type,entity_id,entity_type,status,approval_history,next_approver_count` |
| comments | `object_id,object_type,created_at`; comment id is a bounded opaque native string |

`applied_credits`: null or `[{credit_id,amount}]`; credit `applied_bills/applied_drafts`: null or `[{bill_id,amount}]`. Null means unavailable; `[]` means returned empty. These preserve the recovered workspace credit projection. Credit accounting dates and agreement/PO line start/end dates are `YYYY-MM-DD`; other material dates are timezone-aware timestamps.

Lines: `{id,kind,amount,unit_price,quantity,quantity_rate_check,unit,service_date,sku,purchase_order_line_item_id,item_receipt_line_item_ids,start_date,end_date}`. Quantity is an exact nonnegative decimal string; `quantity_rate_check` is MATCH/MISMATCH/UNAVAILABLE. Inventory lines preserve documented bill quantity/rate, credit `unit_quantity`, and PO quantity/rate/date ranges. Unsupported unit/SKU/service-date claims stay null. The selected typed API line schemas do not supply a unit-of-measure field. Never derive a unit/SKU from a memo, description, external ID, currency or vendor. Native missing line IDs (credit lines, generated transaction splits) remain null and cannot support exact line-ID bindings. Absent typed line arrays yield no lines, never an inferred zero expense. Agreement untyped line objects and merchant receipt numeric fields without documented currency/unit semantics are omitted.

Approvals deliberately use the parent resource `entity_id` as record `id`, disambiguated by lowercase `object_type`/`entity_type`. The official response has **no standalone approval ID**. This is never a Blank Canvas trigger/instance ID. Requests use uppercase filters, responses lowercase types. All published parent states, including INITIALIZED/PENDING/TERMINATED, are accepted. `approval_history` retains `{action_at,step_status}` only; unknown free-text step states become null without refusing the valid parent. Users/emails are omitted; next approvers are represented by count. A successful empty response remains EMPTY. HTTP 400/403 or malformed shapes remain explicit failures; no nonapplicability is guessed from an error.

## Native UI link policy

Only an actual `Bill.deep_link_url` or `PurchaseOrder.ramp_url` value may be retained, otherwise null. Exact literal `https://demo.ramp.com`, no port, credentials, query (even empty), fragment (even empty), encoding or trailing slash. Path must match the same native UUID:

- Bill: `/bill-pay/bills/{id}` or `/s/bill-pay/bills/{id}`.
- PO: `/s/procurement/purchase-orders/{id}`.

These are retention allowlists, not generated link templates. The PO object shape is supplied by the official OpenAPI example on `app.ramp.com`; only a provider-returned sandbox-origin equivalent is accepted. Bill `deep_link_url` is documented as an **ERP link**, and its official example is null: an external ERP link is discarded. Bill path policy is a narrow allowed shape, not a claim that Ramp supplies it or that the sandbox route was verified. Root's previously observed pending bill returned null; the worker never invents a replacement. Runtime route resolution and any additional sanitized shape verification belong to root. No embedding/iframe/OAuth identity claim follows from a URL.

## Evidence and validation

Pinned local official OpenAPI SHA256: `2f7d60ff0a94859bd8ae94ac7a688c1a8df60ea281e3ef8f5d061b04b9ae849a`, supplied at `/Users/ronoktanvir/.local/share/uptime-engineering/reference/openapi.json`. Reviewed accompanying `procurement-intake.txt` and `webhooks.txt`. This pin does not establish that the currently deployed provider matches the document. The documented PO read requires Ramp Plus; scope success alone cannot establish product entitlement.

Restored existing independent Claude Opus replies 31–35 were read and each reply's packet SHA256 matches the corresponding local packet. No new model request was made. Their unresolved live verification concerns remain root's responsibility. This reader does not attempt a write to test provider enforcement: local refusal tests establish only the client's boundary, and the user forbids worker live transport.

Prior commit `bdcec90` is unavailable in this durable checkout; the reader was reconstructed against `tasks/ORIGINAL-WORKSPACE-INTERFACE.py` and the official schemas. The early shared interface is `tasks/INTERFACES-ramp-records.md`; final commit/status are published alongside it. No customer captures, credentials, gold/holdout files or remote API were used. Targeted synthetic tests cover grants, published shapes, independent/reciprocal PO coverage, unsafe URLs/cursors, bounded details, unknown scale, native associations, approval false refusals, local integrity and compatibility with the original adapter. Root must run `uv run --locked pytest` after integration.

The new `deep_link_url` field and PO `ramp_url,discovery,reciprocal_bill_ids` fields are additive: validation permits their absence in otherwise compatible saved records. Missing fields do not produce a link or reciprocal-association claim.

Final local verification: **161 passed, 2 deselected**, with:

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m pytest -q \
  tests/test_ramp_records_v4.py tests/test_ramp.py tests/test_ramp_v4.py \
  -k 'not sanitized_snapshot_and_fixture_are_distinct and not legacy_is_pinned_and_not_current_financial_input'
```

The two excluded tests load saved historical provider captures; the worker did not access them. The remaining existing adapter tests use injected/synthetic transports, including mocked redirects and draft mutations. No full suite or merge was performed in this worker; root owns post-merge verification.
