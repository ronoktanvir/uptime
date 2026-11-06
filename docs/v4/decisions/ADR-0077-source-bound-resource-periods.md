# Decision 77: preserve resource periods and filing scope

Status: implemented; focused checks passed. Base: `d253553`. Authored public remediation controls; no unseen evaluation claim.

A source that explicitly identifies one complete UTC calendar month and gives its exact endpoints should retain those endpoints even when it says “from … until …”. A filing cutoff for one named service month must remain scoped to that month. The first correction adds a finite representation to an existing period primitive; the second adds a missing typed filing primitive.

## Evidence and decision

The preserved evaluation76 baseline refused the April period with `Fixed period is not one explicit complete UTC calendar month.` The pre-change Decision77 probe repeats that failure. Existing aggregate `fixed_filing` accepts an absolute November cutoff but retains no service-month discriminator, and ordinary resource evaluation only accepts rolling filing rules. These observations concern source interpretation and type preservation; no financial recovery or live provider behavior was measured.

Keep one fixed-period validator, requiring exact full-month UTC arithmetic and a bounded affirmative assertion that binds the month and both endpoints. Preserve original source citations. Add source-bound `scoped_filing` with explicit month, timestamp, endpoint and receipt basis. Compile it into the existing filing policy slot as a tagged `scoped_absolute` policy. Permit only exact matching service-month claims; absent and other-month policies produce insufficient evidence with an unknown amount. Reject conflicting policies and unsupported neighboring material.

Scope is limited to resource terms/operators, the fixed-period validator in service-month terms, deadline dispatch in resource evaluation, a narrow historical caller join, new tests and this record. Model transport, shared dispute runtime, registry, UI, money arithmetic and human authority are unchanged.

## Criticism and alternatives

The actual tool-free Opus criticism identified clause binding as the principal risk: loose word presence can join unrelated, reversed or negative endpoint statements. It also rejected inferring a global relative deadline from a single month and required an explicit filing basis. The implementation decision accepts those criticisms. Only a received-at clock is supported; filed-at semantics and year inference remain unsupported. The existing UTC parser already rejects fractional timestamps and nonzero offsets.

Retaining the old wording restriction is safe but leaves a supported period unrepresentable. Accepting arbitrary pairs of timestamps would lose calendar-month authority. Narrowing the agreement to its only known filing month would alter contract coverage. Deriving deadlines for all months would invent terms. Those alternatives are rejected.

The [public criticism and coding receipt](reviews/77-resource-period-and-filing-scope.json) records the actual model, sessions, tool inventory, final criticism and transcript hashes. Full process streams and the before probe remain protected outside Git. The [decision packet](packets/77-resource-period-and-filing-scope.md) records the pre-implementation falsification cases.

## Historical caller join and remaining finding

After the Opus coding session completed, the integration lead approved narrow wiring in `correspondence_history.procedure`: pass the already verified claim scope month and the independently observed original receipt body timestamp to the new deadline dispatch, preserving billing-cycle evidence. This lead-authored change does not use current time or model-proposed dates; existing destination and receipt-chain checks remain. Signed integration controls cover a matching month and an off-month refusal, including null money, zero claimed/awarded, no action and no manufactured submission.

The aggregate `fixed_filing` validator retains a demonstrated preexisting weakness: the recipient phrase “by the vendor” satisfies its inclusive-comparator search even when the same block states that no filing deadline applies. The [unchanged-base and current probe](reviews/77-preexisting-fixed-filing-finding.json) records the exact authored quote and both accepted manifests, with expected safe refusal. This isolated validator finding does not establish full contract acceptance or financial eligibility. It is outside the new scoped primitive and remains for a separate correction.

The lead added the new scoped operator description to the model-facing prompt after delegation. Future extraction requests therefore use new bytes; the frozen evaluation76 request manifests remain untouched. No fresh model extraction was run.

## Verification and limits

Before implementation, the existing resource, operator and service-month suites passed: 92 tests. After source freeze `ee44b3872e7d41847360b1f90e5d9b7ecc97e48f`, the eleven focused suites passed **352 tests in 20.78s**, with one existing Starlette/httpx deprecation warning. The [verification receipt](reviews/77-focused-verification.json) pins source hashes, command and output hash; [TEST-CHANGES-77](../TEST-CHANGES-77.md) records exact additions and failed preliminary assertions. No production or test source changed after this run. Root owns merge/full-suite verification.

The frozen evaluation76 inputs, independent expected outcomes, request manifests and first model outputs remain unchanged. These known examples are remediation controls. This decision does not establish that a new model request can extract every remaining condition in those contracts, and it does not promote a template or authorize a filing.

Rollback: revert the bounded implementation commit and its new tests. Existing immutable source and baseline evidence need no migration or rewriting.

## Integration correction: existing combined source blocks

The root full suite at `53bd7be` found **28 failed, 3355 passed, 1 warning in 158.87s**. The initial focused suite missed the existing CalyxQuay public block used by Northwind setup. Reproducing `test_public_signed_setup_and_scripted_calyx_history_preserve_unknowns` failed at block4 `fixed_period`, as reported. The earlier focused success did not establish whole-application compatibility.

The block contains an affirmative supplier/product/plan sentence, an explicitly inclusive-start/exclusive-end monthly period, exact days/minutes, a UTC assertion and a closed-coverage assertion. The new grammar omitted “that service for the single monthly period” and refused the bounded neighboring context. This was a compatibility regression introduced by77.

The correction adds that general explicit-period form and consumes only finite affirmative supply, mathematically exact duration, UTC and closed-coverage assertions. It retains the original full block and exact endpoint comparisons; arbitrary context, mismatched durations, reversed endpoints, contrary qualifiers, extra periods and exceptions still refuse. Added independent February leap-year and December rollover controls use different authored supplier/product/plan names. Existing sources, staged model responses and tests remain unchanged. This is lead-authored routine correction under the existing decision; no model call was made.

The unchanged `scripts.film_ramp_v4.public_intake` now returns the original April2031 endpoints and original accepted extraction session. Its direct invocation requires the existing reviewed-proposition opt-in; an initial probe without that setting refused before validation, and the corrected probe used the same setting as normal setup. Final legacy and new checks are recorded after the correction source freeze.
