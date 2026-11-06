# Ramp credit observations and local reconciliation

`uptime.ramp_credit_sync.RampCreditSync` journals operator-imported provider
observations and links them to an independently recorded local award only after
exact scope and reciprocal bill checks. It performs no network calls and exposes
no vendor-credit create/apply operation. Original V3 modules remain unchanged.

Decision 72 now requires explicit provider business identity for new financial
links and prevents cross-business observation advancement. See the current
[association and migration rules](RAMP-RECONCILIATION-72.md) and actual
[Opus review](decisions/reviews/72-ramp-credit-business-scope.json). Earlier
review availability statements below describe the original implementation.

## Evidence and financial boundaries

The reviewed local official OpenAPI defines:

| Read operation | Required scope |
| --- | --- |
| `GET /developer/v1/vendors/credits` | `vendors:read` |
| `GET /developer/v1/vendors/credits/{vendor_credit_id}` | `vendors:read` |
| Bill readback | `bills:read` |

The published schema has no vendor-credit creation/application REST operation.
Credit `total_amount`, `remaining_amount`, and `total_applied_amount` are
`CurrencyAmount` objects with integer `amount`, explicit `currency_code`, and
`minor_unit_conversion_rate`. No omitted currency or conversion rate is inferred.
The total applied amount includes both `applied_bills` and `applied_draft_bills`.
Draft applications remain a separate observed quantity; they are not reconciled
as applied bills. Each bill's `applied_vendor_credits` must reciprocate the credit
ID and exact amount. Those reciprocal amounts are in the credit's currency;
cross-currency cases are rejected rather than converted.

An archived credit's remaining amount is historical information, not usable
capacity. Its balance may be displayed as observed, but it cannot be linked or
advance an existing allocation. A bill's full amount does not establish eligible
contract capacity. Every reconciled bill must already exist in AllocationLedger
with verified opening eligible capacity and the exact same vendor, account,
product, contract, contract version, and currency as the award. This sync never
creates an award or a bill, modifies a bill, or interprets spend as entitlement.

The current AllocationLedger accepts only `SIMULATED_VENDOR` awards and USD
settlement. This module preserves that limitation. Native sandbox observations
can reconcile those explicitly simulated awards, but `actual_recovery` remains
`null` in every result. Supporting independently verified real awards requires a
separate reviewed change to the shared ledger and source vocabulary. A receipt
string, local timestamp, or `LIVE_RAMP_SANDBOX` label does not authenticate a live
transport, grant, business identity, vendor confirmation, or commercial right.

## Python interface

```python
from uptime.ramp_credit_sync import RampCreditSync

sync = RampCreditSync(database_path)
receipt = sync.import_snapshot(tenant, observation)
state = sync.summary(tenant)
history = sync.history(tenant)
# Only after upstream confirmation and verified bill-capacity intake:
result = sync.link_award(tenant, binding)
```

The constructor, `import_snapshot`, and `summary` entrypoints remain. The
workspace supplies `credit_observation(snapshot, provider_business_id=...)`.
Omitting the business retains observation-only compatibility; it cannot create
or advance financial links. The envelope contains:

```text
id, observed_at, source, provenance_ref, scopes, provider_business_id,
available, list_complete, credits, bills
```

`source` is `LIVE_RAMP_SANDBOX` or `DETERMINISTIC_REPLAY`. Replay can be observed
but cannot establish a native link. `scopes` accepts a list or space-separated
OAuth scope text. Omitted/null scopes remain unknown. `available` and
`list_complete` must be actual booleans when supplied. Credit and bill projections
use official field names; extra fields such as vendor names, invoice descriptions,
credit reference text, and accounting details are discarded. `history` returns
receipt metadata, normalized-payload digests and reason codes, never raw records.

`link_award(tenant, binding)` requires all these fields:

```text
credit_id, award_id, bill_id, observation_id, provider_business_id,
provider_provenance_ref, provenance_ref,
award_source, award_source_ref, memo_ref,
vendor_id, account_id, product_id, contract_id, contract_version, currency
```

`provider_provenance_ref` must equal the selected current observation receipt.
`provider_business_id` must equal the immutable tenant business pin and the
explicit business on that observation. Historical unknown scope is never
backfilled from a new observation.
`provenance_ref` identifies upstream independent confirmation of the mapping and
scope. `award_source`, `award_source_ref`, and `memo_ref` must match an already
confirmed AllocationLedger award. `bill_id` names an explicitly scoped bill with
provider readback even if the credit has no applied bills yet. Every additional
applied bill needs its own existing ledger capacity and reciprocal readback.
IDs are exact canonical native UUIDs, never display-name matches. Linking an
award to a credit does not imply that a reference bill generated that award.

Bindings are immutable and idempotent. Changed bindings fail with
`BINDING_CONFLICT`; a retry of the same binding reports the historical operation's
success, not a fresh confirmation of provider state. Consult `summary` for the
current observation's status and freshness. Workbench routes must enforce tenant
authorization before invoking this trusted local interface. The enclosing
workspace must bind the tenant to the actual Ramp business through its independently
verified installation; this envelope deliberately makes no OAuth identity claim.

## Journal and failure semantics

`BEGIN IMMEDIATE` serializes separate SQLite writers. Observation journaling,
credit recording, and cumulative application deltas share one transaction using
the existing AllocationLedger transaction helpers. Capacity and award ceilings
remain enforced by the ledger's SQL constraints. Financial failures roll back
all allocation changes for that observation, then durably record a quarantined
receipt. Repeated delivery IDs return their original receipt; altered contents
under the same ID raise `OBSERVATION_ID_CONFLICT`.

Compatible older observations remain history and cannot add allocations again.
Amounts are compared in observation-time order; decreasing per-bill or total
applications, changed currency/vendor/identity, contradictory same-time values,
and changes after a recorded archive fail closed. A draft-to-bill transition may
increase bill application while leaving total applied unchanged. Missing linked
credits in a subsequent complete list produce a conflict, not an automatic
reversal or loss of historical accounting.

Financial conflicts quarantine the tenant's sync journal: later apparently valid
imports cannot silently resume allocation, and delayed conflicts remain visible
even if their observation timestamp precedes the latest successful read. Summary
exposes `quarantined: true`; new links and promotions stop with
`PRIOR_CONFLICT_REQUIRES_REVIEW`. There is intentionally no automatic conflict
clearance or reversal endpoint in this version. Root must review a separate
resolution workflow before resuming that journal; historical evidence is retained.

Statuses are `RECORDED`, `EMPTY`, `PARTIAL`, `STALE`, `UNAVAILABLE`,
`INSUFFICIENT_EVIDENCE`, or `CONFLICT`. Unknown quantities and missing required
scopes never become numeric zero. Partial/unavailable data cannot promote
allocations. Imports more than 24 hours old or from the future are historical
only. Freshness is checked again when linking and reading summary. Methods accept
an explicit timezone-aware `as_of` for deterministic offline replay; the default
clock is current UTC. This clock is not evidence of acquisition time.

Summary distinguishes:

- `captured_credits` and `unmatched_credits`: records in the latest observation.
- `observed_totals`: per-currency recorded, provider-applied, bill-applied,
  draft-applied, remaining quantities and archived record counts.
- `recorded_cents` and `applied_cents`: historical linked USD ledger quantities,
  null before linked evidence exists, carrying `award_provenance: SIMULATED_VENDOR`
  and `recovery_status: UNVERIFIED`.
- `awards_without_native_credit`: confirmed local awards lacking a native link.
- `claimed_only` and `claims_balance`: `null`, with `claims_status: NOT_SUPPLIED`.
  Claims are outside this module's inputs and cannot be inferred from credits.

A genuine complete live empty list reports `EMPTY` and zero captured records.
It does not report zero claims, receivables, or recoveries. Historical allocated
amounts remain explicitly historical even when the latest observation is stale,
unavailable or conflicting. An empty observation is not a reconciliation success.

## Offline operational entrypoint

Use a controlled local JSON projection, never credentials or raw customer exports:

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m uptime.ramp_credit_sync --db /tmp/credit-sync.db --tenant example import observation.json
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m uptime.ramp_credit_sync --db /tmp/credit-sync.db --tenant example link binding.json
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m uptime.ramp_credit_sync --db /tmp/credit-sync.db --tenant example summary
```

All commands are local. The CLI emits aggregate results or reason-code receipts;
invalid file/JSON input produces a generic error without echoing payloads. Root
owns actual transport, credentials, live execution, business verification and
workbench authorization. Store the local database under the same protected
filesystem policy as the existing workbench ledger.

## Reference and review record

Reviewed the provided official `reference/openapi.json`, `procurement-intake.txt`
and `webhooks.txt` under
`/Users/ronoktanvir/.local/share/uptime-engineering/`, together with the V3
handoff/specification/DAG/credential guide and `tasks/RAMP-DIRECTION.md`.
Procurement approvals and webhook notifications are separate workflows; neither
provides a credit entitlement or a credit-application operation. The webhook guide
requires readback, durable idempotency and handling out-of-order events. There is
no webhook receiver in this module and no assumed vendor-credit webhook.

The requested current independent Claude replies 31–35 were unavailable: the
durable `review/replies/` directory was empty during this task. No review result
was invented, and no external consultation, live API, credential, customer file,
or evaluation gold/holdout access was attempted. The design remains an offline
reversible implementation for root's integration review.

Run the assigned offline checks with:

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python -m pytest tests/test_ramp_credit_sync_v4.py tests/test_allocation_ledger.py -q
```

These use generated synthetic IDs and financial fixtures. The integration owner
runs the required full `uv run --locked pytest` gate after merging.
