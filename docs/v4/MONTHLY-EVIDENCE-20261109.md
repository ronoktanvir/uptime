# Complete-service-month evidence contract

The user approved a separate strict whole-month evidence path on November 9, 2026. The governing source must explicitly permit a complete UTC calendar-month report for the entire service and state that incident identifiers are not required. Silence does not opt in. The legacy generic monthly incident path and built-in Twilio path retain their original scope requirements.

## Source capability and financial identity

The deterministic compiler emits `evidence_basis="complete_service_month/1"` with an exact `evidence_basis` citation. `vendor_monthly_basis.validate_monthly_evidence_basis` validates the explicit supported clause, UTC monthly family, future-invoice remedy, filing window, and single product/plan. `claim_scope.complete_service_month` uses that shared validator and verifies unique citation IDs, exact citation shape and the source digest/span wherever retained source text is available. Only an absent key means legacy; a present null or malformed marker refuses.

The resulting `ServiceMonthScope` has exact account, vendor, agreement, service, currency and UTC month, with no component, incident or region. An invoice identifier may narrow the evidence association without changing the economic obligation. Existing monthly obligation identity remains unchanged; the new path cannot create a second monetary obligation for the same service month. Overlapping activated publications that change the evidence basis are material conflicts and cannot be selected without supported precedence.

## Evidence and authority

Required records are one `monthly_coverage` report from the enrolled status source and one existing `invoice` record from independently enrolled billing. A customer `monthly_attribution` report is optional. If supplied, it must corroborate the status measurement; it cannot overwrite a contradiction. Every included record must have distinct retained subject, signing-key ID and grant ID, plus its content digest. Cryptographic verification, current source enrollment and exact envelope-scope checks remain upstream at ordinary authenticated intake. Authored HMAC sources in an explicitly isolated local workspace retain their existing fixture authority; their signatures are not proof of customer evidence.

Each report states `source_ref`, `observed_at`, exact UTC `start`/`end`, plan, strict booleans `complete` and `exclusions_removed`, explicit `gaps` and `unresolved_exclusions` lists, and strict integer `eligible_downtime_minutes`. To establish sufficiency both booleans must be true and both lists empty. The measured integer is bounded by the actual calendar month's minutes, including leap years. Missing, boolean, floating-point or negative minutes never become zero. Optional repeated account/vendor/contract/service/month/currency must match the envelope exactly; explicit null is refused.

Intake rejects partial or foreign report periods and reports observed before month end. Evaluation requires `month end <= observed_at <= received_at <= known_at <= evaluation time`. It does not let a later `known_at` hide a premature server receipt. Duplicate kinds, wrong roles, legacy incident evidence mixed into the strict path, unsupported kinds, gaps, unresolved exclusions and disagreeing optional attribution all yield insufficient evidence.

Billing uses the existing typed invoice. The join requires unique line IDs and exactly one `affected_api` line matching `overlay.fee_line_ref`, with an exact decimal amount in cents. Repeated identities must match; component/incident/region lines, inconsistent invoice identities, nonzero tax or unsupported currency refuse. Existing governing-fee resolution remains authoritative for stepped-credit rules. No missing fee becomes zero.

## Evaluation and citations

`monthly_observation(scope, events, overlay, filed, at)` translates these facts into the existing deterministic evaluator input. It does not calculate a rate, amount, deadline or entitlement. Original `filed` remains `received_at` in the evaluator observation even when later evidence is assessed. Rates, rounding, filing cutoffs and eligible-fee interpretation remain with the existing engines. Report and invoice digests are retained as monitor and fee references; ordinary case evidence supplies source citations.

The historical `monitor_source="simulated_vendor"` vocabulary is an evaluator input category, not a claim that real evidence was produced. Actual provenance remains in event authority metadata and audit exports.

## Review, tests and limits

The initial genuine Opus xhigh worker produced the core schema, join, scope switch and tests. Parent falsification controls exposed its unnecessary three-source requirement, weak duplicate marker validator and null-marker fallback. The parent corrected these to the user-approved contract and added receipt chronology and duplicate-source controls. The worker's dataclass object-identity assertion was corrected to value equality. Only new tests were edited; no frozen expected outcomes or existing tests were weakened.

The public setup artifact is `docs/v4/examples/monthly-public-20261109.json`. It describes ordinary source-derived installation, scoped claim intake and authenticated deliveries. It contains authored data, no keys and no independent evaluation answers. A local scripted lifecycle is not an actual human review. Adapter semantics changes require current version-bound review before real activation; none is performed by this workstream.

Unsupported source languages, alternative period semantics, resource-specific or non-USD fee interpretation remain unsupported. Passing focused controls does not establish production readiness or independent unseen success. The integration owner must bind these source files into semantic hashes and run the full merge suite before the independent evaluation manager scores the frozen build.
