# Financial coverage matrix — decision 89

**Status:** published support matrix for the deterministic financial engines, audited on source `03b372e`, with the identity rows updated for decision D03-A. It describes behaviour; the financial rows are unchanged by D03-A. The engines and their refusals remain the only authority: a consumer must evaluate, never consult this table instead.

**Machine-readable form:** [`coverage/financial-coverage-89.json`](coverage/financial-coverage-89.json) (`financial-coverage/1`). `tests/test_financial_coverage_89.py` checks that every row cites existing tests and enforcement symbols, that every requested dimension has an explicit refusal row, and that this page lists exactly the machine rows. Every cited test must pass in the normal suite.

**What “supported” means:** exact decimal or integer arithmetic under the stated semantics, with cited clauses and a trace. It is not general contract coverage. Anything outside these rows — other currencies, tax allocation, business-day calendars, partial-period proration, new tier forms, ambiguous amendments — must refuse as unsupported or missing, never fall back to a convenient formula.

## Audit result

Amendment precedence, effective dates, usage tiers, eligible fee bases, exclusions, rounding and claim deadlines were audited across the six engines below. **No path was found where contradictory or unsupported terms produce a payable amount.** Every refusal row keeps the amount unknown (`None`), and the aggregate stays unknown when any invoice line is unassessed.

The audit did find classification and representation issues. None of them creates money. They are recorded here rather than changed, because each fix edits a file whose bytes are pinned by reviewed approvals (`vendor_terms.SEMANTICS_REVISIONS`, `governing_fees.dependency_digest`) and would force renewed review of active adapters and fee contexts:

| Review item | Observed behaviour | Why it matters | Owner / dependency |
| --- | --- | --- | --- |
| `PRC-EXC-2` | A product both covered and excluded, or two rates for one product, returns INSUFFICIENT_EVIDENCE. | More evidence cannot cure contradictory terms; UNSUPPORTED_RULE or review-required would describe it accurately. | Pricing owner; independent of D03/D04. |
| `PRC-BAS-2` | When one line lacks evidence and another is unsupported, the invoice reports INSUFFICIENT_EVIDENCE. Both reasons appear in the trace. | Curing the evidence only reveals the unsupported term. No amount either way. | Pricing owner; independent of D03/D04. |
| `MON-IDS-1` | An observation whose account or fee line *contradicts* the overlay is reported as missing, like an absent fact. | Missing and contradictory evidence should stay distinguishable. | Evaluator owner; overlaps D03 identity semantics. |
| `MON-DL-2` | A receipt before the service month ends is INELIGIBLE / OUTSIDE_WINDOW (also in the resource evaluator). | A premature filing is “not yet fileable”, not a lost entitlement; workflows must not close the obligation. | Evaluator owner; independent of D03/D04. |
| `MON-RND-1`, `RES-RND-1` | Sources without a rounding clause yield exact sub-cent estimates (for example `0.00125`, `12.505`) with issuance unconfirmed. | Correctly not invented; presenters must not call such an estimate a payable amount. | Presentation only. |
| Historical import | `claim_identity._backfill` assigns the availability remedy to an unreserved historical inbox record when the vendor label folds to `twilio` (`uptime/claim_identity.py:275`). | A vendor-name rule on a history-only path; current filings reserve explicitly. | Identity owner; unchanged by D03-A because it governs only already-stored history. |
| Governing-fee month | `FeeRegistry` compares the service month using the line's own offset (`uptime/governing_fees.py:187`). | Safe today because the fixed-month pricer requires zero-offset lines and fails closed first. Keep the coupling if either side changes. | Pricing owner. |

## Fixture-name independence

`test_northwind_financial_results_do_not_depend_on_fixture_names` renames every Northwind party, agreement, account, product, plan, fee line, invoice and incident to neutral values, recompiles the source and reruns the unchanged engines: January–March and the April settlement reproduce `fixtures/northwind/expectations.json` exactly. `test_negotiated_pricing_results_do_not_depend_on_fixture_names` does the same for all pricing demo cases, using identities that contain spaces.

The name-shaped dependencies that remain are deliberate or decision-bound:

- On audited source `03b372e`, Northwind worked end to end partly because its authored IDs (`harborline-001`, `NW-2026-001`) fit the restricted claim-intake domain, and a source-shaped account such as `Harborline Analytics` was stranded. Decision D03-A removes that dependency: the same account now produces the same Northwind economics (`IDS-D03-2`). See [identity and scope](IDENTITY-SCOPE-CONTRACT-89.md).
- The Twilio evaluator is intentionally specific to Twilio's April 9, 2026 published SLA; its evidence requirements and fee exclusions are preserved (`TWL-*`).
- Generic interval helpers `_merge` and `_subtract` live in `uptime/twilio.py` and are imported by the resource evaluators. This is structural only; moving them would change pinned evaluator hashes, so it is not done here.

## Matrix

### Negotiated pricing

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `PRC-CUR-1` | currency | Agreement version or invoice in a non-USD currency | UNSUPPORTED_RULE | No conversion is attempted; no amount. |
| `PRC-CUR-2` | currency | Verified sandbox bill whose currency, amount, status or origin conflicts with the mapping | FAIL_CLOSED_MIXED | Binding refuses; the evaluator revalidates and withholds any amount. |
| `PRC-TAX-1` | tax | Tax itemized separately on each line under `separate_excluded` | SUPPORTED | Tax is excluded from the discrepancy and never adjudicated. |
| `PRC-TAX-2` | tax | Line tax absent | INSUFFICIENT_EVIDENCE | The whole invoice is unassessed; no aggregate amount. |
| `PRC-TAX-3` | tax | Any other tax treatment, such as tax-inclusive pricing | UNSUPPORTED_RULE | No allocation formula is substituted. |
| `PRC-RND-1` | rounding | Contract rounding `line_half_up_cent` | SUPPORTED | Each priced line is rounded HALF_UP to cents once; the invoice total is not rounded; ambient decimal context is irrelevant. |
| `PRC-RND-2` | rounding | Any other rounding rule | UNSUPPORTED_RULE | No default rounding is applied. |
| `PRC-CAL-1` | calendar | Performance instants in any UTC offset | SUPPORTED | The governing version is chosen by the exact UTC instant of performance; the invoice date never chooses the rate. |
| `PRC-CAL-2` | calendar | Offset-less (naive) performance or signing timestamps | INSUFFICIENT_EVIDENCE | No timezone is assumed. |
| `PRC-PRO-1` | proration | Usage line spanning an amendment boundary | INSUFFICIENT_EVIDENCE | No time-based proration; explicit complete split allocations price each part under its own version. |
| `PRC-PRO-2` | proration | Fixed monthly fee for a partial, non-UTC or non-unit month | FAIL_CLOSED_MIXED | No partial-month proration; no amount. |
| `PRC-PRO-3` | proration | Performance after the invoice date (advance billing) | UNSUPPORTED_RULE | Only an exact source-backed fixed calendar-month advance with a trusted observation time is priced. |
| `PRC-AMD-1` | amendment | Amendment precedence at the performance boundary | SUPPORTED | The latest version effective at or before performance start governs; an amendment exactly at the start governs, one exactly at the end does not. |
| `PRC-AMD-2` | amendment | Broken or ambiguous supersession chain, missing signature or signatory | INSUFFICIENT_EVIDENCE | No version is guessed. |
| `PRC-AMD-3` | amendment | Version signed after its effective date, or not known at the trusted observation time | UNSUPPORTED_RULE | Retroactive or later-known terms need commercial interpretation. |
| `PRC-AMD-4` | amendment | Equal or decreasing amendment effective dates, or a version effective at expiry | INSUFFICIENT_EVIDENCE | The chain is refused as ambiguous. |
| `PRC-AMD-5` | amendment | Price increase permitted by a signed amendment | INELIGIBLE | Billing at the amended rate is not a discrepancy. |
| `PRC-EFF-1` | effective dates | Performance before the first version or after expiry | INELIGIBLE | Ending exactly at expiry is in term; one microsecond later is not. |
| `PRC-TIER-1` | usage tiers | Graduated tiers with integral, upper-inclusive thresholds | SUPPORTED | Tiers reset for each complete performance slice; marginal rates change exactly after each threshold. |
| `PRC-TIER-2` | usage tiers | Volume pricing, cumulative scope, unknown boundary, bounded final tier, repeated thresholds | UNSUPPORTED_RULE | No alternative tier formula is substituted. |
| `PRC-TIER-3` | usage tiers | Overlapping same-product allocations, duplicate allocation or line IDs, fractional/zero quantity, unit mismatch | INSUFFICIENT_EVIDENCE | Tier attainment is not guessed. |
| `PRC-BAS-1` | fee basis | Overcharge and undercharge on the same invoice | SUPPORTED | Both directions are reported without netting; an undercharge alone carries no claim amount. |
| `PRC-BAS-2` | fee basis | Any unassessed line on the invoice | INSUFFICIENT_EVIDENCE | Verified lines stay inspectable but the aggregate stays unknown; missing evidence outranks unsupported terms. |
| `PRC-EXC-1` | exclusions | Explicitly non-covered products | INELIGIBLE | Non-covered lines and their tax are excluded; an invoice of only such lines has no discrepancy. |
| `PRC-EXC-2` | exclusions | Product both covered and excluded, or two rates for one product | INSUFFICIENT_EVIDENCE | Contradictory terms never price. Review item: classified as missing evidence rather than unsupported. |

### Governing fee

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `FEE-BAS-1` | fee basis | Completed-step credit fee base | SUPPORTED | Only a current server-issued context priced by the negotiated engine is used; billed or browser fees never control. |
| `FEE-BAS-2` | fee basis | Absent, duplicate, split or credit-memo fee lines; quantity other than one | REFUSED_NO_CONTEXT | No fee context is issued. |
| `FEE-TAX-1` | tax | Nonzero tax on the governing fee line | REFUSED_NO_CONTEXT | Tax allocation is not attempted. |
| `FEE-CUR-1` | currency | Non-USD or otherwise mismatched authenticated envelope scope | REFUSED_NO_CONTEXT | An envelope never selects another registered fee. |
| `FEE-CAL-1` | calendar | Envelope month differs from the fee line's single-unit UTC service month | REFUSED_NO_CONTEXT | No month is inferred from a filing timestamp. |
| `FEE-AMD-1` | amendment | Invoice or versions not known at the trusted observation time; changed pricing dependencies | REFUSED_NO_CONTEXT | Later-known terms and revoked registries issue nothing. |

### Monthly availability (tiers)

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `MON-CUR-1` | currency | Non-USD account overlay | REFUSED_AT_ONBOARDING | bind_overlay refuses the binding. |
| `MON-CAL-1` | calendar | Measurement other than a UTC calendar month, or business-day filing | REFUSED_AT_ONBOARDING | The source does not compile. |
| `MON-PRO-1` | proration | Month not wholly governed by both the contract and the account overlay | UNSUPPORTED_RULE | No partial-month proration, even with a valid fee context. |
| `MON-PRO-2` | proration | Incomplete month measurement or exclusions not removed | INSUFFICIENT_EVIDENCE | Never treated as zero downtime. |
| `MON-TIER-1` | usage tiers | Availability credit tiers | SUPPORTED | Strict less-than thresholds compared as exact integer ratios; nonmonotonic tiers refuse at compile. |
| `MON-RND-1` | rounding | Tier family whose source states no rounding rule | ESTIMATE_ONLY | An exact unrounded estimate (for example 0.00125) with issuance unconfirmed; no payable cents are asserted. |
| `MON-BAS-1` | fee basis | Tier family fee cents missing, from another month, or for another fee line | INSUFFICIENT_EVIDENCE | Vendor totals are never substituted. |
| `MON-EXC-1` | exclusions | Exclusions not attested removed; qualified exclusion language | INSUFFICIENT_EVIDENCE | Qualified language refuses at compile; unattested measurement is missing evidence. |
| `MON-DL-1` | deadlines | Filing window of N calendar days after month end | SUPPORTED | The cutoff is exclusive at month end + N days in UTC; one microsecond earlier is timely. |
| `MON-DL-2` | deadlines | Receipt before the service month ends | INELIGIBLE | OUTSIDE_WINDOW; exactly at month end is timely. Review item: a premature filing is reported as ineligible rather than not yet fileable. |
| `MON-DL-3` | deadlines | Absent or offset-less receipt time | INSUFFICIENT_EVIDENCE | No receipt time is assumed. |
| `MON-AMD-1` | amendment | Private filing-day amendment | SUPPORTED | Applies only with a cited matching clause and only to the bound account. |
| `MON-IDS-1` | identity scope | Observation agreement, account, product, plan or fee line absent or different from the overlay | INSUFFICIENT_EVIDENCE | No amount. Review item: a contradiction is reported like an absent fact. |

### Completed steps

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `STP-TIER-1` | usage tiers | Completed percentage-point shortfall increments | SUPPORTED | Counted from exact integer ratios and capped. |
| `STP-RND-1` | rounding | Source states one final nearest-cent half-up rounding | SUPPORTED | One final HALF_UP to cents; no intermediate rounding. |
| `STP-RND-2` | rounding | Completed-step rule without explicit final HALF_UP, or combined with tiers | UNSUPPORTED_RULE | Refused even when a valid governing fee context is supplied. |
| `STP-BAS-1` | fee basis | Positive credit rate without a current matching governing-fee context | INSUFFICIENT_EVIDENCE | No amount; another scope's context is never borrowed. |

### Resource and service month

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `RES-RND-1` | rounding | Resource or service-month credit rounding | SUPPORTED | HALF_UP to cents only when the source states it; otherwise an exact unrounded estimate. |
| `RES-DL-1` | deadlines | Compiled inclusive or exclusive filing cutoffs | SUPPORTED | Evaluated before, at and after the cutoff according to the compiled comparator. |
| `RES-DL-2` | deadlines | Unsupported or contradictory filing language | REFUSED_AT_ONBOARDING | The source does not compile and stored state is unchanged. |
| `RES-BAS-1` | fee basis | Unpaid or unclassified fees; unseen invoiced categories | INSUFFICIENT_EVIDENCE | The evaluator abstains rather than assuming an eligible base. |
| `RES-EXC-1` | exclusions | Missing, out-of-scope or contradictory private attestations | FAIL_CLOSED_MIXED | No amount. |

### Twilio API SLA

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `TWL-CUR-1` | currency | Non-USD input or fee lines; negative adjustments | UNSUPPORTED_RULE | No conversion or netting. |
| `TWL-TAX-1` | tax | Taxes, carrier fees and third-party charges | SUPPORTED | Excluded from the eligible fee base; the vendor total is never the base. |
| `TWL-RND-1` | rounding | 10 percent of eligible fees | SUPPORTED | Exact Decimal product; no rounding rule is invented. |
| `TWL-CAL-1` | calendar | Month bounds and deadline in an evidenced IANA timezone | SUPPORTED | Includes DST transitions and leap years. |
| `TWL-PRO-1` | proration | Incomplete, partial-month or future coverage | INSUFFICIENT_EVIDENCE | No proration of the measurement month. |
| `TWL-EXC-1` | exclusions | Defined exclusions and scheduled maintenance | SUPPORTED | Excluded spans are never recounted through another record; maintenance needs at least 24 hours notice; an unknown exclusion is missing evidence. |
| `TWL-DL-1` | deadlines | Thirty-day submission window after month end | SUPPORTED | Inclusive local date: last day of the month plus 30 days; a timely receipt is preserved. |
| `TWL-BAS-1` | fee basis | Unresolved fee classification, mapping or evidence | INSUFFICIENT_EVIDENCE | Never silently excluded or included. |
| `TWL-BAS-2` | fee basis | No fee, not actually incurred, or another month | INELIGIBLE | No claim amount. |

### Claim identity and scope

| ID | Dimension | Case | Status | Result |
| --- | --- | --- | --- | --- |
| `IDS-D03-1` | identity scope | Account, agreement, vendor or service name with spaces, punctuation or non-ASCII letters (source-identity/1) | SUPPORTED | Accepted byte-identically by onboarding, claim intake, signed evidence, the claim registry and the ledger; padded, repeated-space, non-NFC, control and other characters are refused everywhere, never rewritten. |
| `IDS-D03-2` | identity scope | Onboarded source-shaped account such as `Harborline Analytics` | SUPPORTED | Northwind January keeps ELIGIBLE 2400.00 with the same governing fee and completed steps; another account's fee context is still never borrowed. |
| `IDS-D03-3` | identity scope | Second filing whose account or agreement differs only by case or spacing | REFUSED_AT_FILING | Refused before dispatch; exact retries and distinct obligations proceed. No override path exists; override authority is not approved. |
| `IDS-D04-1` | identity scope | Claim scope fields component, incident, region and invoice | SUPPORTED | claim-scope/1: the server resolves the governing family from installed terms; required fields must be present, not-applicable fields absent (no placeholders), invoice is an optional evidence reference, and an unknown or ambiguous family refuses at intake with a distinct InvalidClaimScope. Monthly keeps incident. Stored ten-field claims serialize byte-identically and keep their governing fee via an explicit legacy alias. |

## Outside this matrix

These are not covered and must not be implied: multicurrency or FX; tax allocation other than separately itemized exclusion; business-day or holiday calendars; time-based proration; volume, cumulative or minimum-commit pricing; MFN or parity rights; rebate and renewal portfolios beyond the single authored Northbank example (`uptime/other_obligations.py`); the legacy Atlassian onboarding lab; dispute and reconciliation monetary flows (awards, posted and applied credits), which belong to their own workstreams. The resource evaluator's non-USD fee-line refusal exists in code but is not independently probed by a cited test here.

## Rollback

This increment adds documentation and tests only. Rollback removes `docs/v4/FINANCIAL-COVERAGE-89.md`, `docs/v4/coverage/financial-coverage-89.json` and the two decision-89 test files. No source, fixture, stored record, hash or signature changes.
