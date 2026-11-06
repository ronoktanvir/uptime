# Worker implementation note (decision70)

Worker-authored with file tools in a tool-enabled Claude Code session. This note is
not a tool-free extraction receipt, model proposal, test result, blind evaluation,
real contract, provider proof or human approval. It is not listed in `freeze.json`,
and the frozen files were not edited.

## Change

`uptime/vendor_model.py` `validate_proposal` now accepts a public `credit_rule` value
for a source span that the existing `compile_terms` grammar already compiled as
`completed_steps`:

```json
{"kind": "completed_steps", "product": "...", "plan": "...",
 "target": "99.8", "step": "0.2", "credit": "7.5", "cap": "30"}
```

- Key set must be exactly these seven, and every value must be a `str`. Mixed internal/external
  keys, extra keys (`citation`, `units`, ...), a missing or unknown `kind`, floats, ints,
  bools and nulls all refuse.
- Percent strings must be the shortest plain ASCII decimal: no sign, exponent,
  whitespace, `%`, extra leading zero, trailing fractional zero, or more than six
  fractional digits. They are then converted with the existing `percent_units`.
- The citation id is the compiler's own id for the same clause position. The model never
  supplies it. The converted value must equal the compiler's `credit_rule` exactly.
- The legacy normalized form (the compiler's exact `credit_rule` dict, including `citation`)
  is still accepted unchanged, with an explicit type check before the equality test.
- `credit_rounding` must be exactly `nearest_cent_half_up`, as before. That value only
  exists when the existing source grammar matched the explicit rounding sentence.
- Tier proposals are unchanged, including their tolerant percent strings.
- `PROMPT` now lists `credit_rule` and `credit_rounding`.

The compiler grammar, financial math, fee authority, classification, offsets/hashes
and approval policy are not changed. Tier and step rules still cannot share a
scope (the compiler refuses).

## Consequence

`vendor_model.py` is in `_COMMON_SEMANTIC_FILES`, so this edit changes
`SEMANTICS_REVISIONS` for `monthly-availability/1`. Previously reviewed monthly
adapters therefore read as `REVIEW_REQUIRED` until reinstalled, retested and re-reviewed.
That is intended: the code is coupled to the review.

Focused tests: `tests/test_vendor_step_proposals.py` (run by the parent, not the worker).
