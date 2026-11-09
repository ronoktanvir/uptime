# Strict, source-bound whole-month evidence

Status: team policy accepted November 9, 2026; implementation and independent verification pending.

## Decision and authority

The team answered **Add the strict monthly-evidence path** to the concrete proposal: for contracts measuring availability over an entire month without incident-specific filing, require a signed complete gap-free report tied to exact customer, agreement, service and month, resolved exclusions, and independently verified eligible fees. Missing or conflicting evidence remains unknown. Existing incident-based contracts keep their requirements.

Implement this as an optional, version-reviewed `complete_service_month/1` evidence basis grounded in an explicit governing source clause. Do not infer a waiver from silence and do not drop the incident requirement globally. Absence of the marker preserves the existing route and historical identity.

## Alternatives and rationale

- Keep incident-only: preserves all current behavior but cannot represent explicitly month-based contracts; retain this behavior for contracts without the new reviewed basis.
- Remove incident everywhere: rejected because the existing join derives downtime from a status/impact pair and reconciles a specific incident. Removing a schema field would manufacture evidence completeness.
- Separate source-grounded month path: chosen. Exact UTC month, service, account, agreement, currency and plan must agree. Complete coverage and exclusion/attribution assertions must be authenticated; eligible fees come from a distinct enrolled billing source. Durations and money remain deterministic and bounded.

An early worker proposal required a third customer-attribution source universally. Integration review rejected that requirement: the specification makes evidence contract-specific, and the accepted policy requires an authoritative complete report plus independent fees. Additional attribution is required only when the governing contract requires it; any contradictory attribution actually supplied must still block a positive result. Distinct keys/subjects establish distinct enrolled source identities, not independent real-world organizations or truth against a malicious host administrator.

## Verification contract

- Exact document spans and complete source validation establish opt-in; contradictory or conditional incident language refuses.
- The new basis validator, scope selector, evidence types, temporal validation and month join are pinned in adapter semantics so old approvals cannot silently cover changed rules.
- Complete reports cannot precede month end or omit intervals. Wrong month, unknown exclusions, inconsistent totals, mixed old/new records, duplicate conflicting sources and same-key billing must refuse or remain insufficient.
- Calendar boundaries, leap February, integer-minute validation, net eligible-fee mapping, source grants, replay protection and original filing clocks retain explicit tests.
- New independent controls are frozen before running the final implementation. Historical 0/4 and Backblaze results are never rescored. Old corpus setup failures remain distinct from new reasoning outcomes.

## Actual model work

Claude Code subscription workers use `claude-opus-5-5` with xhigh requested and restricted file tools. The first monthly worker is session `983dae98-68d4-479b-8328-755e37b99f57`; its initial three-source proposal must be reconciled with the two-source contract before acceptance. Initialization is not completed implementation or independent certification. Completed outputs and test receipts are recorded in workstream ledgers. D14 does not require another council.

## Rollback and effects

Revert the coordinated compiler, marker, scope and join changes together; preserve all recorded evidence and audit history. New-basis adapters must become unavailable pending compatible re-review rather than fall through to the incident path. Existing historical signed records and their identities are not rewritten. This decision grants no Ramp write, external claim, release signature or named human approval authority.
