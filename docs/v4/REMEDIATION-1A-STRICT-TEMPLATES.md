# Ronok's "1a" repair: strict-template remediation

**Current status (2026-11-09): implemented and focused-tested; combined integration and independent evaluation pending.** Ronok resumed onboarding/disputes and approved a separate explicit whole-month evidence path. Nine released phrasing classes now compile through generic templates with exact citations. Focused checks passed **433 tests, 1 warning in 3.17s**. The source marker also flows through public model proposal compilation and receipt revalidation. [Test ledger](TEST-CHANGES-onboarding-finish-20261109.md).

**Historical deferral:** The overview session decided this at 06:00 PST on 2026-11-09 under Ronok's delegated (Recommended) authority; it is not his personal decision, and he can override it. Implementation starts as soon as Ronok decides whole-month sufficiency for monthly disputes, batched with any other `vendor_terms.py` change into a single adapter re-review. Estimate: about two hours, plus that re-review. Owner: W3 (`agent2`).

## Why the earlier session deferred

The deterministic `/candidates` route parses monthly sources only with the strict canonical-template parser.
- The verification lane ran `scripts/diagnose_strict_terms.py` (`e73d8e1`) on the monthly claim-basis contract. It recognized 2 of 11 clauses (measurement period, one scoped tier); missing required terms: vendor, agreement, effective dates, filing window, remedy.
- Even if the contract activated, the 11 monthly dispute replies in evaluation 86 state no incident and stay setup-blocked under D04-C until whole-month sufficiency is decided. Implementing now would cost another re-review and unblock nothing.
- The resource-month claim-basis contract cannot activate on the deterministic route at all, because no deterministic resource parser exists. It needs the model path (setup only, D10) or a team decision.

The first-attempt score (0/4) is never rescored.

## Clause classes and generic design

Inputs are the verification lane's phrasing-class summaries only; no contract text was seen. Each template states a supported term in a common, unambiguous way. Anything carrying an exclusion or condition stays refused (D07).

| # | Phrasing class | Generic template | Refuse when |
|---|---|---|---|
| 1 | Bare title line naming the agreement, ending in "Agreement" | The document's first clause, title-cased, at most 12 words, no sentence punctuation or dates, sets the agreement to the whole line | Not the first clause, or a labeled agreement also exists |
| 2 | Unlabeled party statement | `<Vendor> provides\|supplies\|offers\|delivers\|operates <Product> on\|under the <Plan> plan` sets the vendor and declares one product/plan scope | A qualifier is present, or the vendor is not the exact subject |
| 3 | Effective sentence | `This agreement (takes effect\|is effective) on <date> (and ends on\|through\|until and including) <date>` sets the effective dates | The dates are reversed or not ISO |
| 5 | Availability formula in words | Accepted only when it equals the evaluator's formula: 100 × (1 − eligible downtime minutes ÷ total minutes in the month), with operator variants | Any other formula, denominator or adjustment |
| 7 | Tier without product/plan, after a scoped tier | `Monthly availability below <x>% earns a <y>% service credit` takes its scope only when the document declares exactly one product/plan | More than one scope is declared (ambiguous) |
| 8 | "Only the highest applicable percentage applies; percentages do not accumulate" | Recognized only as a statement of the evaluator's existing rule: `rate_for` already applies only the most severe tier, without accumulation | It says credits accumulate, or adds any other qualifier |
| 9 | Fee basis and currency | `The credit percentage applies to the affected monthly service fee in USD` sets the fee basis | The currency is not USD (D07) |
| 10 | Remedy | `Credits are applied to a future invoice` | — |
| 9 + 10 | Together | Establish the existing remedy `affected_monthly_fees_future_invoice`; either alone is incomplete | One half is missing |
| 11 | Filing sentence with an article | The existing `FILING` template plus an optional leading "A"/"An" | Outside 1–365 days |

## Tests to write first

- One authored analogue per class (accept), with the negative control from the "Refuse when" column.
- A whole authored contract combining all nine classes, accepted, with hand-computed boundary cases through the evaluator.
- Parity: `vendor_strict_diagnostics` updated in step, with the parser parity tests extended.
- After the merge, the verification lane reruns the classifier and preflight on the sealed contract and reports the result as it is.

## Remaining limits

Bare “until” remains refused because end-date inclusion is ambiguous. The supported party grammar remains conservative about qualifiers, punctuation and names; arbitrary prose, unsupported currencies, exclusions, rolling periods and alternative formula semantics still refuse. A strict resource parser was not added. No vendor names or sealed corpus text were used in implementation.

This remediation changes reviewed source semantics and therefore requires fresh ordinary review; it does not reuse the recorded CalyxQuay review for changed code. Monthly core integration must include every evaluator and admission dependency in the monthly semantics pin. Development controls do not replace the independent first-attempt cohort, which remains historically 0/4 until a separately frozen new cohort is reported.
