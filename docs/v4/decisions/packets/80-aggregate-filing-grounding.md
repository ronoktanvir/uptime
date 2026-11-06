# Decision80 packet: source-bound aggregate filing deadlines

Classification: AUTHORED PUBLIC source code and tests. Base c5dd4e4. No credentials, customer material, private holdouts or native qualification inputs.

## Observed mechanism and reach

`fixed_filing` currently requires a claim/filing word, the proposed timestamp anywhere, and any occurrence of inclusive/by/no later than for an inclusive endpoint (before/exclusive for an exclusive endpoint). It separately finds any “within N days after/following” phrase and writes fixed_filing_days before conflicting fixed_filing validation.

The exact previously documented quote “Claims may be received by the vendor at 2026-05-15T00:00:00Z; no filing deadline applies.” is accepted unchanged at c5dd4e4. In a public authored aggregate April source, replacing only its filing clause with that quote and manually proposing fixed_filing also compiles. Existing SCRIPTED meaning-review helper plus authored verified evidence yields ELIGIBLE amount10.00, TIMELY, unconfirmed service-credit status using that invented cutoff. This demonstrates compiler/evaluator reach under scripted review, not model extraction, human approval, a real claim or a real award. Expected safe result is source refusal before an eligibility preview.

## Bounded decision

Replace the fixed_filing keyword search with one finite full-source-block grammar binding the claim obligation, exact UTC timestamp and endpoint comparator. Distinguish “by the vendor/provider” as recipient from “by <timestamp>” as inclusive cutoff. Require all source material be consumed by affirmative supported deadline assertions and semantically consistent finite companion assertions. Refuse no-deadline, negation, conditional/exception, contradictory endpoint or multiple/unrelated deadline material. Never strip those qualifiers or guess a comparator. Keep source citations unchanged.

Preserve supported known forms verbatim:
1. “The claim is due within 6 days after the service month, no later than 2027-03-07T00:00:00Z inclusive.”
2. “The claim must be received no later than 2026-05-15T00:00:00Z inclusive.”
3. “The timestamped claim must be filed within 14 days after the monthly period ends, no later than 2031-05-15T00:00:00Z. Filing exactly at that timestamp is permitted. A claim filed later receives no credit.”

Preserve inclusive/exclusive exact-timestamp semantics, UTC parser restrictions, existing full compiler consistency of relative days against fixed period end, and mutation safety on validation failure. Relative days must come from the same supported filing assertion, not another obligation. Optional exact-boundary or late-no-credit companion statements must agree with the selected comparator; “exactly permitted” cannot coexist with exclusive. Do not broaden clock origins (business days, event-start clocks etc). Existing `fixed_period`, scoped_filing, money arithmetic, evidence authority and activation rules are outside ownership.

Alternatives: blacklist “no filing deadline” alone leaves recipient/comparator confusion and unrelated words; substring extraction drops operative clauses; unrestricted natural-language interpretation cannot fail closed. Full bounded matching is preferred but risks excluding valid existing combined blocks. Explicit compatibility controls for all three known source forms and the unchanged public CalyxQuay intake plus Northwind setup address that risk.

## Ownership and verification

Only fixed_filing helper(s)/branch in uptime/vendor_service_month.py; new tests and Decision80 docs. No77 period/resource modifications, shared model runtime, UI, source/proposal fixtures, old test edits, native runner or live calls. One tool-free actual Opus criticism then one restricted file-tool coding delegation. Lead supervises tests/Git. Record every failed/timeout model attempt and actual inventory. Freeze source before final focused tests; root owns merge suite.

Controls: old valid blocks unchanged; inclusive/exclusive at/before/after instants; recipient-only by, no deadline, no later than ... exclusive, before ... inclusive, negative/conditional/excepted clauses, two clocks, extra relative statements, unrelated substring matches, duplicate/conflicting days, invalid timestamps; full aggregate compile refusal for the original bug and preservation of valid exact monetary arithmetic without authorizing actions.

## Additional pre-implementation reach probe and critic disposition

The same full source also yields ELIGIBLE10.00 with no binding context: this aggregate control has no literal roles requiring meaning review. Both probes remain local authored evidence with no model extraction, promotion or real action. The single tool-free critic's atomic mutation and finite comparator/companion recommendations are accepted; ignoring arbitrary non-filing sentences is rejected because it could erase unsupported material and is unnecessary for the actual known filing blocks. Existing whitespace normalization remains unchanged.
