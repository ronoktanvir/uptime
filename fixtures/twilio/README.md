# Twilio API SLA evaluator (W2)

`uptime.twilio.evaluate(TwilioInput) -> uptime.contracts.EvaluationResult` is an
offline deterministic evaluator. `uptime.twilio.demo_cases() -> list[dict]`
exposes four case-detail objects under `sla-` IDs with the frozen CP1 UI fields,
including title, currency, trace, citations, evidence and financial stages.
`uptime.twilio_demo.input_from_dict` decodes trusted local fixtures; it is not a
browser API, authorization check or proof-verification service.

## Source and fixture provenance

The orchestrator supplied the complete official page text, last updated April 9,
2026, at `terms.local.txt`. Its SHA-256 is recorded in `cases.json`; the raw text
is temporary input and must not be committed. The source is
https://www.twilio.com/en-us/legal/service-level-agreement/twilio-apis.
No retrieval timestamp was supplied; this worker made no network requests.
The `LIVE_VENDOR_PUBLIC` tag applies only to that supplied public source, not a
claim that the worker fetched it live or that it is the customer's agreement.

All incidents, coverage attestations, customer subscriptions, fee allocations,
invoice lines and times in these fixtures are **SYNTHETIC_CUSTOMER**, replayed as
**DETERMINISTIC_REPLAY**. Status URLs identify the required evidence origin; they
are not fabricated links to real historical incidents. There is no real customer
entitlement, claim submission, vendor award, posted credit or applied recovery.
Expected fixture outcomes are stored independently from the evaluator.

The eligible October case has 60 qualifying minutes in 44,640 monthly minutes.
Availability is `(44640 - 60) / 44640 * 100`, below 99.95%. The $1,730 synthetic
invoice includes $1,000 affected-API fees, $200 carrier fees, $80 taxes, $50
third-party fees and $400 for another API. The candidate credit is exactly
`1000.00 * 0.10 = 100.0000 USD`. No rounding policy is invented. The other cases
exercise excluded maintenance, missing fee allocation, and an unsupported
SendGrid connection-rate claim. Unknown/unsupported outcomes carry no amount.

## Complete-term rule coverage

| SLA provision | Implemented behavior |
| --- | --- |
| §1, availability and monthly time | `(A-B)/A*100`; explicit sourced IANA timezone, whole-month coverage, exact strict threshold comparison |
| §1/§3, base plan | 99.95% threshold; **10%** credit, not 5% |
| §1/§3, Enterprise | 99.99% threshold; 10% credit |
| §1/§3, Administration | 99.99% only when purchased **before** October 24, 2024; otherwise base threshold; absent purchase date is missing evidence |
| §1/§3, SendGrid | Mail Send availability uses email-package fees; all five listed enhanced packages use 99.99%, base uses 99.95% |
| §1/§2/§3, Successful Connection Rate | Dedicated failure evaluator unsupported: geography-dependent 15,000/10,000 requests/s, 202 responses, sufficient concurrency, 6/4 Gbps ceilings and DNS TTL conditions cannot be inferred from downtime. An enhanced SendGrid availability pass cannot deny the alternate remedy without a qualified report attesting rate success. The monthly right to request the prior-30-day report does not itself establish a failure. |
| §2/§3, evidence | Status-page-derived dates/times and documentation, affected-service/customer attribution and exclusion review required. General internal telemetry is neither a substitute nor a universal extra requirement. Full monthly status coverage must be attested. |
| §3, filing | Support-channel URL and exact `SLA Claim` subject; 30 days from month end; past submission needs a receipt reference. No outbound behavior. |
| §4(a–f), exclusions | Outside-control events, customer/third-party causes (except Twilio agents/subcontractors), customer technology (except Twilio-controlled), scheduled maintenance with ≥24h notice, emergency maintenance, preview/not-generally-available APIs |
| §4(g), continuity | Union overlapping/touching intervals, subtract known excluded time, reject residual continuous spans <300 seconds, then clip to month. Duplicate records do not multiply downtime. |
| §4, other products | Segment, Stytch and Flex Critical Scenarios explicitly outside this API SLA; their separate agreements are not evaluated. Discontinued/unsupported services excluded. |
| §1, credit basis | Actually incurred affected Twilio API fees or affected SendGrid email-package fees for the month; exclude tax/levy/duty, carrier fees/surcharges, all third-party charges, unrelated APIs and other months; unknown classifications/mappings fail closed |
| §3/§5, remedy | Candidate credit against future API service amounts, not cash/refund or award. Sole/exclusive SLA remedy does not authorize settlement or filing. |
| §6, versions | Only April 9, 2026 implemented; governing whole-month applicability reference required; older service months fail closed; no auto-adoption of later updates |

## Consequential assumptions for central-lead review

ADR/review 06 favors exact public terms and rejects incident-only/total-spend
entitlement. These are reversible local rules, with no production promotion or
commercial authority. The central lead retains ownership of additional Opus
decisions. New interpretation boundaries to review:

1. **Timezone and deadline edge:** the page says calendar month and 30 days from
   its last day, but specifies no timezone or time-of-day cutoff. The prototype
   requires an explicit timezone/reference and uses the local last-day date +
   30 days, inclusive through that date. DST changes elapsed monthly minutes.
   The UTC reference in the fixture is a synthetic assumption, not a vendor
   promise. Confirm calendar/cutoff policy before real claims.
2. **Partial plan coverage / effective version:** a sourced whole-month
   subscription/plan and agreement attestation is required. Mid-month edition
   changes or application of the April 9 update to April 1–8 need upstream
   agreement resolution. No proration is inferred. The dated public page alone
   cannot establish applicability to a customer's service month.
3. **Conflicting overlap:** excluded portions take precedence over another
   overlapping candidate record; residual spans must independently meet the
   five-minute minimum. This conservative choice prevents a duplicate record
   from restoring excluded downtime. Material contradictory evidence needs
   upstream review; the evaluator is not an evidence adjudicator.
4. **Money precision:** exact Decimal credit values may include fractional
   cents because the public SLA gives no rounding method. Rounding, negative
   adjustments, currency conversion and negotiated fee rules are not invented.
   The shared prototype supports USD only; negative affected-fee adjustments
   return `UNSUPPORTED_RULE`.
5. **SendGrid:** availability-based claims are evaluated separately from the
   unsupported Successful Connection Rate failure branch. No double credit is
   inferred and a connection-rate claim never becomes eligible through the
   generic availability calculator. A supplied rate-success attestation is a
   qualified input, not validation of the underlying throughput conditions.

The data boundary is trusted typed evidence: references are required and traced,
but this module does not fetch/hash remote artifacts, verify a signature, or
authenticate a tenant. W0/W5 must supply evidence qualification and access
controls. Non-eligible paths intentionally omit monetary values; successful
evaluation does not confer permission to submit.

## Verification

Run from this worktree using the existing environment, without dependency sync:

```sh
../../../outputs/uptime/.venv/bin/python -m pytest
```

Tests cover the four golden outcomes, plan thresholds/cutoff, exact five-minute
and percentage edges, overlapping/adjacent/cross-month intervals, all exclusions,
status/customer evidence, calendar coverage, deadline/receipt boundaries,
timezone/DST/leap calendars, fee allocation and unknowns, unsupported rules,
decimal precision and the UI contract. The parent must run its mandated full
suite after integration; this worker does not merge branches.

Worker validation: **77 tests passed** (72 parameterized Twilio cases plus 5
existing tests). The supplied interpreter stalled on dependency file reads before
collection; the successful run used an already installed local cache, with no
install/download or environment modification:

```sh
PYTHONPATH=/Users/ronoktanvir/.cache/uv/archive-v0/z3s_sJI4mB5loMn2AoeSd/lib/python3.13/site-packages \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
../../../outputs/uptime/.venv/bin/python -m pytest -q
```
