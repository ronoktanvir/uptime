# Decision 65a: governing fee authority and fixed-month advance billing

This sanitized packet contains only authored public synthetic examples and repository interfaces. No customer/private cases, oracle, credentials or external contract are included. Decision 65 approved exact completed-step credits in the existing monthly family: an explicit `credit_rule.kind=completed_steps`, no `tiers` field, exact integer availability and floor, one final HALF_UP currency rounding. This packet requests an independent architecture review before implementing the remaining joins. No commercial execution or actual human approval is claimed.

## Confirmed failures and requested business behavior

The current signed monthly correspondence join derives `monthly_fee_cents` from authenticated invoice lines. That establishes billed fees, not the governing contractual fee. The authored SLA explicitly bases credit on the governing covered monthly fee, excluding overbilling and taxes. A future complete March month would otherwise credit a USD 12,000 invoice although the governing fee is USD 11,000. Passing a loader-computed number into JSON is not a production authority boundary.

The authored agreement is Northwind Cloud / buyer Harborline Analytics / account harborline-001 / NW-2026-001 / Cloud Hosting / Business / fee line cloud-hosting-monthly. The original fixed fee and matching ceiling are USD 12,000. A February 20 signed amendment, effective March 1, changes BOTH the fixed fee and matching ceiling to USD 11,000. The existing pricing engine resolves terms by complete service interval, not invoice issuance. A February service invoice dated March 1 remains USD 12,000. A ceiling alone cannot establish the payable fee.

January has an authored 135-minute outage in its 44,640-minute complete month, producing two completed shortfall steps and USD 2,400. February has five minutes in 40,320 and is known ineligible. March has no complete usage as of March 1 and must have no SLA estimate. Separately its pending fixed monthly invoice of USD 12,000 can show USD 1,000 price exposure if validly billed in advance. The requested continuous story inspects that March invoice and files January on March 1, with a cure March 2, before the exclusive March 3 cutoff. An April-issued invoice cannot be observed then; backdating a filing is unacceptable.

Existing `pricing._evaluate` explicitly requires `line.end <= invoice.issued_at`, otherwise UNSUPPORTED: “future performance requires separate advance-billing rules.” The original April-issued authored package passed 46 focused tests; correcting March invoice to March 1 exposed this refusal (36 package-loading failures, 10 pure tests passed). Both receipts are retained. No failure has been suppressed and no advance operator has been implemented.

## Existing authority and interfaces

Pricing inputs are frozen dataclasses `Agreement`, version chain with bilateral signatures and source citation, `Rate`, `Invoice` and `InvoiceLine`. Pricing validates currency, separate tax, exact complete line allocation, source classification, amendment chronology and scope. It computes line expected amounts; a partial assessment leaves total discrepancy unknown. A source tag is not authentication. Current pricing is explicitly synthetic, with optional independently verified sandbox bill binding.

Signed monthly invoice wire contains `kind=invoice`, lines of exact `id`, classified `kind` (affected_api/tax/etc.), exact decimal amount and optional scope fields. The signed delivery has tenant/server principal and account/vendor/contract/service/component/invoice/incident/currency/month/region scope. The wire does not itself carry quantity, invoice issuance, or exact service interval. These remain registered immutable trusted adapter inputs. No rewrite of signed JSON or historical receipts is permitted.

Decision 61 already requires trusted, role-scoped semantic bindings for affected literal meanings. Its context is server supplied and sealed, absent meaning produces no monetary estimate, and dependency changes stale approvals. Economic claim identity intentionally excludes version changes. Neither semantic review nor fixture signature establishes verified provider data or a real human action.

C's workflow uses a fresh isolated `bears` rehearsal database and existing signed allowlist. It proposes injecting a typed registry at application construction, with no new public registration route and no per-request registration. The authored package is fixed server configuration, not browser input. C owns server/inbox joins; this agent owns generic pricing/credit modules and fixture inputs.

## Proposed governing-fee authority boundary

A fixed server `FeeRegistry` accepts immutable `Agreement + Invoice` entries plus exact tenant/account/vendor/agreement/product/plan/month/fee-line identity and SLA source/overlay digests. No entry stores an authoritative answer in cents. Input and pricing dependency digests are pinned.

`resolve` accepts an authenticated signed invoice snapshot/digest from the existing adapter, verifies exact invoice identity, envelope scope, all represented lines and amounts/currency against registered inputs, and verifies the fee line's full registered service month. Optional explicit signed scope fields must agree; unknown, duplicate or changed covered lines refuse. Quantity, source version, issuance and allocation are not inferred from the sparse wire: the immutable trusted registered Invoice supplies them. Registration does not claim provider verification. The adapter already determines whether this is local synthetic evidence or a real provider source.

Only then call the existing pricing engine. Require a complete pricing assessment, exactly one matching eligible expected fee line, an exact nonnegative cent result, matching scope and source pins. Return a frozen, module-sealed `GoverningFeeContext` carrying computed cents, governing version, contract/source/input/dependency/signed-evidence digests and scope. The evaluator checks that seal and exact matching source, overlay, month and fee-line identity. A dict or arbitrary cents callback is rejected. The seal prevents accidental external request injection, not malicious Python with full process access.

Every completed-step monetary boundary requires this context: direct evaluation, candidate test evaluation, shadow, registry dispatch and correspondence. Missing/mismatching context yields insufficient evidence and no amount or provisional monetary total; a justified nonmonetary deadline and known availability may remain visible. A known ineligible rate zero is distinct from an unknown rate, but no positive money is computed without the fee context. Existing tier-family contracts retain their original fee behavior and economic preimages. Binding/input changes alter assessment/approval dependency versions while preserving economic identity and existing reservations.

A conflicting flat `monthly_fee_cents` must not silently be replaced with the governing fee. Proposed step path: omit that untrusted derived field from monetary inputs and consume only the sealed result; if a caller explicitly supplies a fee assertion inconsistent with the sealed context, refuse. Signed invoice bytes continue to carry billed amounts and are never rewritten to the governing amount. Public test fixtures can register typed inputs and issue explicitly synthetic snapshots; these confer no human or external authority.

## Proposed bounded advance operator

Add an explicit rate-level tagged billing timing, defaulting to today's arrears behavior. Proposed tag: `fixed_calendar_month_at_start_or_arrears`. Its independent source citation must refer to the same contract version and an authored affirmative clause. This is an ordinary contractual operator, never a Northwind/demo/source-name branch or provenance flag.

The source clause permits one complete fixed UTC calendar-month subscription unit invoiced exactly at its service start or after its completed service interval. The advance variant requires quantity exactly Decimal(1), one unbounded flat tier, the unit `service-month`, complete allocation with strict boolean true, UTC calendar-month start at midnight and exact next-month end, and invoice issuance exactly equal to service start. No intervening amendment boundary, usage-variable charge, partial month, arbitrary future issue or unknown scope is accepted. The current default continues to refuse all future performance. Existing arrears lines remain accepted without the new operator. The March invoice will be honestly authored at 2026-03-01T00:00:00Z under that clause; February remains March 1 at 09:00 after February ends. March usage remains incomplete, observed March 1, with no future telemetry.

The tag and citation are trusted extracted contractual inputs; existing pricing consumes typed legal terms rather than pretending to be a free-prose parser. Exact source quote/hash binding for the new tag should be required by its adapter or dedicated immutable clause proof, not inferred from a boolean or the word “monthly.” Please assess whether a source-checked typed `BillingTiming` proof (raw source SHA, exact start/end/quote plus citation and fixed grammar) is preferable to an enum/citation alone in this bounded change.

## Alternatives and recommendation

1. Recommended: typed, server-registered governing-fee resolver plus the narrow source-grounded fixed-month timing operator. Preserves the intended chronology and monetary authority boundary without a public fee endpoint.
2. Keep existing April invoice and retrospective presentation. Preserves current pricing capability but fails the requested continuous March 1 walkthrough. It cannot be disguised by moving the clock backward.
3. Let the browser, fixture expectation, generic cents callback, invoice amount or ceiling supply the fee; skip future-performance validation for this vendor. Reject: these invent authority or change contract meaning.
4. Create a general contract registry/auth service now. Unnecessary scope unless the existing immutable registration/allowlist cannot constrain use. No new approval policy or second reviewer is proposed.

## Preregistered falsifiers and tests

- Full signed invoice snapshot mismatch: tenant/account/vendor/contract/service/month/currency/invoice/fee line/amount/extra covered line, absent or duplicate records; no fee context and no money.
- Forged dict/context, copied context on another scope, mutation via dataclass replacement, stale pricing dependency/source/overlay/version, context without authenticated adapter snapshot, and conflicting flat fee assertion refuse. Registered inputs produce fee by engine execution, never fixture expected answers.
- January 12,000 -> 2,400; March complete hypothetical uses 11,000, not billed 12,000; March actual incomplete remains null. February March-issued invoice uses original 12,000. Ceiling-only or incomplete version cannot create fee.
- Advance success only exact one unit, full UTC calendar month and exact issue=start. One microsecond earlier/later, partial month, local-time monthly boundary, future month, quantity0/2/fraction/bool, variable tiers, omitted/unknown tag, missing/mismatched citation/source/quote/version, `allocation_complete` false/1/string, overlapping lines and amendment crossing refuse. Default arrears still refuses same advance invoice.
- Full caller tests at pure pricing, loader, direct monthly evaluation, registry candidate/test/shadow dispatch and signed correspondence. Mutation of signed evidence stales current assessment without changing economic identity or historical receipt bytes.
- Known zero versus unknown: no positive monetary rollups from absent fee or usage; nonmonetary deadlines remain justified. Final financial operator tests retain exact integer boundaries and HALF_UP ties from decision65.
- Separate fixture expectations file absent/wrong does not affect computation. Authored interval records are inputs, not synthesized from expected outcomes.

Please return a concrete recommendation, strongest objection, minimal exact data contract, missing falsifiers, and any condition under which these joins should remain unsupported. Distinguish an internal process trust boundary from provider/human authority. Do not assume root approval of architecture until this actual response is reviewed.
