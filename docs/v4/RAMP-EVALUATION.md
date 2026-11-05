# Ramp contextual evaluation

`uptime.ramp_findings.evaluate_snapshot` produces offline workbench cases from the typed `uptime-ramp-records/1` snapshot. Ramp remains the financial system of record. Findings are provisional review material, never money recovered, money prevented, legal adjudication, a native payment block, or permission to publish.

## Preserved integration contract

```python
from uptime.ramp_findings import evaluate_snapshot
cases = evaluate_snapshot(snapshot, as_of=audit_clock, bindings=())
```

The function calls the records owner's `_validate_snapshot` before evaluating anything. A checksum verifies local integrity; it does not authenticate a Ramp business, operator, or organization. The root importer owns trusted transport custody and tenant isolation. The evaluator does not load a snapshot file, credentials, customer documents, incidents, model responses, or holdout data. It performs no network requests or writes.

The central workspace fields are preserved: `id`, `title`, `vendor`, `stage`, `outcome`, `amount`, `currency`, `sources`, `provider_object_type`, `provider_id`, `provider_uri`, `native_status`, `native_approval_status`, `native_amount`, `finding_kind`, `finding_digest`, `data_provenance`, `trace`, `actual_recovery`, `publishable`. Detail includes `evidence`, `clauses`, `missing`, `actions`, `timeline`, `financials`, `line_findings`, `linked_records`, and `workflow_recommendation`. `payment_timing` retains the prepayment/retrospective classification even if evaluation later requires review. Agreement renewal enums are retained separately as `native_renewal_status`.

`amount` is a positive provisional contractual discrepancy, or null. PO comparisons use a separate `difference`; they never populate `amount`. All values are JSON-native; monetary arithmetic uses Decimal. `native_amount` preserves the complete normalized money object, including signed minor units and unknown scale where applicable. Native states are never lowercased or rewritten: `OPEN` remains `OPEN`, `PAID` remains `PAID`, and card states remain their actual enum values. Only `CLEARED` card transactions are explicitly classified as settled retrospective review. A pending card authorization is not represented as a prevented payment.

Every observed readable bill, draft, transaction, vendor/payee, PO and agreement gets a case. Unavailable resource groups produce no invented records. Partial groups retain their resource status/completeness. Unbound observations remain `INSUFFICIENT_EVIDENCE`, even when a vendor agreement exists or a line exceeds its PO amount. Vendor equality supplies context, not governing contractual scope. Foreign or ambiguous merchant identities are never joined by name.

## Explicit terms and service bindings

`PriceBinding` contains an exact object type/ID, capture digest, operator reference, existing `pricing.Agreement`, immutable `ServiceMapping` tuple, terms mode, terms evidence reference/digest, and signed-terms attestation. `line_digest(normalized_line)` pins each exact native line; `binding_digest(binding)` pins all terms and mapping operands.

A `ServiceMapping` contains:

- Exact bill line ID and digest.
- Explicit product/SKU, unit and timezone-aware half-open service interval.
- Reviewed service evidence reference and SHA256 digest.
- Explicit complete-quantity and net-without-tax attestations.
- `quantity_source`, default `BILL_INVENTORY`.
- Optional PO ID, PO line ID and PO line digest for the alternative PO lane.

The preferred `BILL_INVENTORY` lane uses `ApiBillInventoryLineItem` quantity, unit price and amount directly. Set all PO mapping fields to null. Native quantity multiplied by native rate must exactly reconcile to native line amount. The line amounts must reconcile to the bill total. The operator supplies service identity/dates only through reviewed evidence; these fields are unavailable in the current minimized provider schema. Any present conflicting native service fact is refused.

The optional `ATTESTED_FULL_PO_LINE` lane requires the exact provider bill→PO→PO-line association, matching entity/vendor, structured PO quantity/rate/amount, and reviewed evidence that the whole PO quantity was actually billed on this one line. PO spending dates must match the explicitly reviewed service interval. A PO planned quantity alone never proves usage. A PO external ID is not assumed to be a SKU. Neither binding type accepts a caller-supplied quantity or invoice amount.

Both lanes currently require positive whole units, USD, separate net fees with documented absence of tax in the mapped bill amounts, complete line scope and positive negotiated rates. Fractional quantities, tax allocation, FX and incomplete scopes refuse monetary findings. Ordinary expense lines without sufficient linked structured evidence remain observable and unbound. No quantity is inferred by dividing total spend by a chosen rate.

Agreement `vendor` is the actual provider vendor ID; `customer` is the actual provider entity ID. Versions, signatures, date precedence, SKU/unit matching, graduated tiers, exclusions, line rounding and invoice reconciliation reuse `uptime.pricing.evaluate_price`. The V3 engine is unchanged. Its synthetic input dataclasses are used as an arithmetic projection; this wrapper owns the actual provenance and removes only the V3 fixture-custody sentence. Opaque citation URIs must use `urn:`, `sha256:` or `fixture:`; raw contract text, document download URLs and private document titles are not rendered.

`terms_mode="SYNTHETIC_NEGOTIATED"` is the default. It yields `MIXED` provenance, `LIVE_RAMP_SANDBOX` plus `SYNTHETIC_CUSTOMER`, a separate `ramp-synthetic-price-...` case namespace and `SIMULATION_ONLY` workflow recommendation. Root may supply this explicit overlay on a real sandbox bill **only when the native facts and reviewed mapping are sufficient**. This worker uses artificial test observations and makes no claim to have run against real sandbox data. An eligible result is hypothetical, not real savings.

`terms_mode="OPERATOR_ATTESTED"` also requires `signed_terms_attested=True`. It yields `PROVIDER_WITH_OPERATOR_EVIDENCE` and `OPERATOR_ATTESTED_CUSTOMER`. This is an additive output string, not a change to the V3 `Source` enum. It records the trusted operator's assertion that the supplied signed terms govern the mapped service; it is not independent signature verification or proof of legal enforceability. Root must authenticate and authorize bindings before calling this internal API. Hashes and booleans are not authentication.

No binding is selected by vendor name or automatically loaded. Missing target records and multiple bindings for one target are rejected. Binding/capture/line mismatches, stale or future captures, missing required evidence, conflicting parties and unsupported rules fail closed. Freshness requires `observed_at <= completed_at <= as_of` and observation age at most 24 hours. A historical replay must explicitly supply its historical clock; before any real action the root workflow owner must refresh provider state.

## Native workflow boundary

Only actual provider-supplied vetted sandbox URLs are returned. Current supported literal paths are `/bill-pay/bills/{id}`, `/s/bill-pay/bills/{id}`, and `/s/procurement/purchase-orders/{id}`, on `https://demo.ramp.com`. No userinfo, query, fragment or alternate host is accepted. No detail link is manufactured from an ID.

The documented comments surface supports `bills`, `draft-bills`, and `transactions`; unsupported object types have no invented endpoint. Recommendations preserve exact object IDs and show the required scope, unknown grant, `NOT_SENT` delivery and null approval-trigger instance. They do not infer Blank Canvas identity from a bill/PO/approval record. Every case remains `publishable=False`; the separate workflow adapter must establish current grants, exact-object operator authority, freshness and safe delivery. No UI embedding, OAuth identity, scope grant, writeback or native savings is assumed.

`finding_digest` hashes the complete case before its own digest field is inserted, including evaluator version, evaluation clock, capture/record/binding digests, native state, citations, outcome and recommendation. A changed capture, status, binding, evidence or evaluation clock changes the review artifact.

## Source review and validation

Implementation reviewed the supplied official `reference/openapi.json`, including `Bill`, `ApiBillLineItem`, `ApiBillInventoryLineItem`, `ApiPurchaseOrderLineItem`, `ApiVendorAgreementDetailResource`, `SingleTransaction`, and the comments object-type enum, plus `procurement-intake.txt` and `webhooks.txt`. These are local pinned references; this worker did not verify them against a live endpoint. Restored independent Claude Opus replies 31–35 were read. Their warnings about stale snapshots, ambiguous joins, overlay isolation, grants versus authority, and unsupported write receipts are reflected above. Root owns consultations and actual sandbox execution.

Tests use artificial provider-shaped records only. Integration tests run the records owner's real sanitizers and validator, not a replacement validator. Before the records module is integrated, three dependency tests skip explicitly; root should run them after integrating that owner. During worker validation, the dependency modules were imported directly from the records owner's durable worktree, without editing it or making provider calls. The evaluator plus existing pricing/binding/invariant/evidence suites passed (167 tests at the final integration checkpoint). No merge was performed by this worker; the project requires `uv run --locked pytest` after each integration merge.

The original V3 implementation and fixtures remain unchanged. Root wires the UI, accepts authenticated operator mappings, executes any permitted sandbox reads, and independently verifies any proposed real action.
