# ADR 0058 — Bounded source-label whitespace equivalence

Status: integrated and locally verified; separate source-meaning defects remain open.

## Decision and alternatives

Use the same existing source whitespace normalizer on both sides of the stable-label phrase comparison. Before normalization, permit only space, tab, LF, CR and NBSP among phrase whitespace characters. Preserve raw length, identifier, collision and nonempty checks, exact source bytes, citation offsets and block/source hashes. Matching stays within the cited block. Implementation `f6cb42b` is integrated at `704caa5`.

Strict raw-only matching would regress accepted normalized proposals. A raw-or-normalized fallback leaves two inconsistent predicates. Unrestricted `str.split()` admits invisible separators beyond the reviewed set. Token reordering, fuzzy matching and case folding change the grounding contract and are rejected. This change fixes inconsistent representation, not clause meaning.

## Independent review and root disposition

Actual `claude-opus-5-5` session `3260c123-b3f8-40ea-b234-b110d2cfb1b7` reviewed packet SHA-256 `8f1b80c93a4c9764da2c2852d6a854ff818966790526162d984ede574860a258`. The [complete review](reviews/58-source-label-whitespace-grounding.json) ranks bounded whitespace normalization first. Root adopts its option (a), preserving the existing block normalizer and adding the phrase allowlist. The review is engineering advice, not interpretation or activation authority.

Root accepts the review's separate objections to substring polarity and alias ambiguity. Later public evaluator probes confirm incorrect USD 12.51 shadow eligibility, so these are substantive correctness defects. They are tracked under decision 61 and must not disappear behind this correction's passing tests. Root does not adopt a minimum-token heuristic as proof of meaning: negation and omitted conditions survive token boundaries. Exact source spans improve provenance but also cannot prove contractual meaning.

## Tests, limits and rollback

The worker passed 399 vendor tests, including 185 new cases across all five label fields. Root independently passed the 185 cases, then passed 2,607 Python tests on `704caa5`. Controls cover all other Python whitespace characters, control/format characters, Unicode non-equivalence, joins/splits, reordering, block boundaries, empty/oversized phrases and raw-definition collisions. [Implementation and semantic-risk evidence](reviews/58-implementation-and-label-boundary.md) · [Root regression](../evidence/verification-704caa5.json)

Two genuine accepted public proposals remain accepted. Five original third-source refusals remain refused. The unchanged newest rejected proposal validates offline under this fix, but its original rejection and bytes remain immutable. It was not promoted into an accepted artifact, and no actual human interpretation or activation was manufactured.

Rollback removes only the bounded phrase-side correction and reruns its controls. Preserve every historical proposal, receipt and source digest; do not regenerate a rejected receipt or reinterpret a signature. Current semantic risk requires containment independently of whether this representation fix is retained. A regression result cannot authorize a monetary estimate, model extraction or adapter activation.
