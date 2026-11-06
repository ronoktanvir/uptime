# Scoped read-only Ramp credit reconciliation

Decision72 preserves the operator-supplied Ramp business identity when native workspace captures enter the offline credit journal. It does not create a Ramp credit or perform a provider operation. The native workspace's already validated business ID now reaches `credit_observation(snapshot, provider_business_id=...)` and the journal unchanged in meaning.

## Current association requirements

A new observation may include `provider_business_id`, a nonzero native UUID. Credit sync normalizes explicit UUIDs and pins one business per tenant in an immutable `ramp_credit_scope` table. A different explicit business fails with `BUSINESS_CONFLICT` before storing the observation or changing allocations. Parallel imports share the existing immediate transaction boundary.

A new `link_award` binding must include the same explicit `provider_business_id`. It must also identify the exact current complete observation, independent existing award and source references, currency, vendor, account, product, contract/version and eligible bill. Missing business is not inferred from a vendor, bill, entity, award or tenant name. Exact money, reciprocal credit/bill applications, draft separation, eligible capacity and existing financial quarantine remain mandatory.

`provider_business_id` is a custody assertion made by the trusted caller. The summary's `business_scope_custody` expressly disclaims OAuth identity proof. Business pinning does not independently authenticate a provider capture or the business origin of an operator-recorded eligible bill. The enclosing workspace remains responsible for installation identity and authorization. AllocationLedger still accepts simulated awards only; the independently signed award-attribution store is unchanged.

## Migration without rewriting history

Missing or null business stays absent from normalized payloads, preserving old digests and duplicate-import identity. New unscoped observations retain their factual status and add `BUSINESS_SCOPE_MISSING`; they cannot create a binding or advance an application. A later scoped observation can resume safely because the new unscoped row was explicitly observation-only.

Old unmarked nonempty financial observations and any old unscoped binding report `LEGACY_UNSCOPED_HISTORY` and stop new projection. Existing historical recorded/applied amounts remain visible. No newly supplied business is copied into those old records. Empty old captures and unavailable/insufficient observations do not create a financial association and do not prevent a later explicit business pin. Existing real financial conflicts remain quarantined.

There is no automatic migration or clearance action for legacy money. A separate reviewed resolution would be needed; this increment does not mutate old rows. Ready workspace captures retain their existing duplicate behavior. An interrupted old pending import whose credit observation was already stored without scope cannot be silently relabelled with the same observation ID; it requires a new independently acquired capture or reviewed resolution.

## Reading amounts

`recorded_cents` and `applied_cents` are null until a native credit is linked to existing ledger evidence. A confirmed linked credit with complete readback and no bill applications has a real historical `applied_cents=0`. Captured native totals remain separate from those attributable ledger amounts. Draft applications stay separate from actual bill applications.

The summary retains the pinned `provider_business_id` and the latest `observation_provider_business_id` separately, so an unscoped later observation cannot inherit the pin in its audit identity. `scope_status` is `SCOPED`, `UNSCOPED`, or `LEGACY_UNSCOPED`. The state can be historical, stale or quarantined; a business label does not override those restrictions. `actual_recovery` remains null even when amounts are linked.

All new tests use authored observations and temporary local databases. The supplied actual sandbox inventory may contain no vendor credits; this repair establishes no live awarded credit, native posting, applied recovery or cash recovery.

[Decision and actual Opus contribution](decisions/ADR-0072-ramp-credit-business-scope.md) · [Exact test changes](TEST-CHANGES-72.md)
