# Decision 77 packet: source-bound resource periods and filing scope

Classification: sanitized public source implementation context. Baseline 76 is preserved public remediation evidence, not a blind evaluation. No customer, credential or private evaluation material is included.

## Observed defects

The frozen 76 aggregate source explicitly names a complete April UTC calendar month, bounded by `2026-04-01T00:00:00Z` and `2026-05-01T00:00:00Z`, using “from … until …”. Its `fixed_period` proposal is refused with `Fixed period is not one explicit complete UTC calendar month.` The validator in `vendor_service_month.validate` requires the literal words `inclusive|including` and `exclusive|excluding`, despite also checking exact first-of-month midnight and next-month endpoints. This is a missing finite representation of an existing typed period; it is not missing period arithmetic. Merely accepting any two timestamps would be incorrect.

The ordinary resource source covers a year but states an absolute filing cutoff only for a named service month. The baseline proposal marks the absence of other months' deadlines unsupported. Existing `fixed_filing` is an aggregate-month primitive; ordinary resource compilation requires relative `filing`, and `vendor_resource_eval.deadline` cannot retain a service-month discriminator. Safe support needs a new source-bound scoped absolute filing primitive. A known November deadline cannot be reused for December.

The captured model outputs also contain other unresolved fields and fences. This repair does not edit them, erase `unsupported`, invent model fields or claim the whole baseline source will newly compile. Public cases are now remediation controls. A fresh genuine model request, if later authorized, is a separate measurement.

## Preferred bounded design

1. Preserve existing `fixed_period` start/end types. Extend the single period validator with a finite affirmative complete-UTC-calendar-month form, tying the named month and both exact endpoints together. Keep the actual original citation. Require mathematical equality to a whole UTC month. Reject reversed, partial, shifted, multi-month, conflicting-label, ambiguous-endpoint, negative, conditional and exception-bearing interpretations. Do not add `inclusive/exclusive` to a quote or normalize away a contrary qualifier. Retain old explicitly inclusive/exclusive forms only when they establish the same exact bounds.
2. Add a typed source-bound absolute filing operator carrying `{month: YYYY-MM, at: explicit UTC timestamp, endpoint: inclusive|exclusive, basis: received}`. The public source block must assert the exact service month, deadline, receipt/filing role and comparator. This is separate from aggregate fixed filing. Preserve both its source citation and its service-month scope. Conflicting/duplicate relative or scoped policies must refuse rather than silently overwrite.
3. Extend ordinary resource deadline dispatch for that primitive. Only the matching service month can obtain that cutoff. Missing or different months yield missing evidence (`INSUFFICIENT_EVIDENCE`/unknown amount) rather than inheriting a deadline. No changes to money, remedy, review, source custody, human authority, claim submission or actual provider behavior.
4. If a material condition cannot be represented, keep the refusal. No source-name/vendor-name branching, no whole-source substring veto presented as full semantic validation, and no dropping unsupported neighboring material.

Approved ownership: `vendor_resource_terms.py`, `vendor_resource_operators.py`; narrowly the fixed-period validation helper in `vendor_service_month.py` and deadline dispatch in `vendor_resource_eval.py`; new focused tests and decision77 documentation. Shared `vendor_model.py`, `vendor_registry.py`, dispute runtime and UI are excluded.

## Alternatives and strongest counterargument

Retain the current grammar and label every new surface form unsupported: safe but leaves the documented complete-month representation gap. Translate the named month's absolute cutoff to a global relative day count: rejected because it fabricates deadlines for other months. Narrow the agreement's entire effective interval to the one filing month: rejected because it silently changes coverage. Loosen keyword matching or remove unsupported blocks: rejected because it loses qualifiers and source meaning.

The strongest concern with the preferred design is overinterpreting “until” or a month label as endpoint authority. Support must therefore require an affirmative complete UTC calendar-month assertion plus exact matching boundaries, not general prose or arbitrary intervals. One named month's supported deadline must coexist with explicit unknown filing rules elsewhere.

## Falsification and evidence plan

- Before/after: the explicit complete April UTC interval fails under the old validator and succeeds only under the new finite representation; the same input and endpoints stay unchanged.
- Reject a March label with April endpoints; non-midnight starts; 29-day/31-day substitutes; two-month spans; “until … inclusive”; “not a complete UTC calendar month”; conditional or excepted coverage; additional conflicting interval bounds.
- Accept a source-bound single November cutoff with inclusive/exclusive boundary fidelity; assert exact timestamp and service-month metadata/citation.
- Reject ungrounded service months, cutoff/comparator mismatches, missing UTC, other-month inference, duplicate/conflicting filing policies and material unsupported neighbors.
- Evaluate a matching month at, before and after the cutoff; evaluate an otherwise complete off-month claim and require unknown amount with no inherited cutoff. Preserve all prior resource/service-month regressions and their authority assertions.

The lead requests one concise actual tool-free Opus criticism, then actual restricted Opus coding delegation. Parent supervision runs tests/Git, records actual sessions/tools/edits and preserves failure receipts. Freeze implementation before final tests; root runs the merge suite. No model decides expected truth, and no captured 76 response or gold is rewritten.
