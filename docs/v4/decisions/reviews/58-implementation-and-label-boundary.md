# Decision 58 implementation and separate label risks

Root selected Opus58 option (a): allow only space, tab, LF, CR and NBSP in proposed stable-label phrases before applying the existing shared normalization. The bounded implementation is `f6cb42b`. Raw shape, identifier and 256-character limits remain in force, and the normalized phrase must be nonempty. Matching stays within the current block. Original phrase text, citation offsets, block digest and source digest remain unchanged. Repeated labels with different raw phrases still refuse.

The actual independent review is session `3260c123-b3f8-40ea-b234-b110d2cfb1b7`, model `claude-opus-5-5`, on packet SHA-256 `8f1b80c93a4c9764da2c2852d6a854ff818966790526162d984ede574860a258`. Its complete response and dissent are in [the review](58-source-label-whitespace-grounding.json). This implementation adds no new source grammar, authority category, semantic fuzzy matching or adapter activation.

## Validation and provenance

All 399 vendor tests pass, including 185 new compiler cases across all five stable-label fields. Controls cover ordinary and mixed whitespace, all other Python `isspace()` characters, source-control-character rejection, case and punctuation changes, token joins/splits, Unicode composition, zero-width/BOM/soft-hyphen substitutions, source-block boundaries, empty and oversized phrases, raw-definition collisions, identical duplicates and aliases. Existing normalized proposals still accept against source whitespace already supported by the compiler. Invalid source control characters remain rejected by the document boundary; the phrase allowlist does not loosen that check.

Both committed genuine accepted public proposals still compile. All five original third-source rejected receipts still refuse. Only the fresh `ea5d0da8...` proposal changes its current offline result to `VALIDATES_UNDER_CURRENT_CODE`. Its historical `REJECTED` receipt and every original file remain unchanged. No acceptance artifact, model retry or promotion was produced from that revalidation. Root's independent validation is required before a further actual extraction.

Local evidence under `$W/receipts` includes `opus58-vendor-after-final.log`, `opus58-labels-baseline-final.log`, and `opus58-public-revalidation.json`. The initial test run also exposed a mistaken test expectation that source control characters were accepted; the existing document validator already rejects them. The final tests explicitly preserve that boundary. The pre-patch post-merge full run passed 2,266 tests; the post-patch verification reported here is the focused vendor suite.

## Separate correctness risks with financial effects

The review identified existing substring and alias weaknesses. They are outside the whitespace correction, but the full evaluator reproduction establishes that their consequence is an eligible monetary estimate.

`scripts/probe_vendor_label_boundary.py` runs a disposable loopback server with the explicitly isolated scripted replay principal. It supplies a clearly labeled adversarial extraction test double, then uses actual compilation, signed candidate intake, evaluator preview, test submission and review gates. It invokes no external model, uses no private heldout inputs, creates no workbench cases and performs no interpretation, approval or activation. Its result is `$W/receipts/opus58-label-boundary-probe.json`.

| Public source and adversarial proposal | Observation passed to the evaluator | Actual preview |
| --- | --- | --- |
| Source says `unavailable samples`; proposed phrase `available samples` matches inside that token. | `available samples` | `ELIGIBLE`, `$12.51`, `PENDING_VENDOR_VERIFICATION` |
| Source phrase `rejected samples` is assigned both `failed_samples` and `successful_samples` aliases. | `successful samples` | `ELIGIBLE`, `$12.51`, `PENDING_VENDOR_VERIFICATION` |

The substring case demonstrates a polarity mismatch between the cited word and the accepted observation. The alias case demonstrates that an opaque identifier whose spelling describes success can become an accepted observation for a failure phrase; normalization also equates spaces and underscores. Alias names cannot be assumed to carry ordinary-language meaning, but the evaluator currently does not distinguish a declared opaque alias from a raw observation with that same spelling. That ambiguity requires an explicit evidence-binding decision, not merely a display correction.

An honest negative scenario expecting no entitlement fails in both cases and removes review actions. A self-confirming scenario expecting `$12.51`, paired with an incomplete-month refusal, passes the automatic positive/refusal coverage and generated threshold checks. The only available next operation is `interpret`; the state remains `SHADOW`, `active_version` remains null, and no interpretation reviewer is recorded. The named review gate therefore contains deployment, but the automatic evaluator and tests do not independently identify the semantic defect. These results do not establish that a human would approve either proposal.

## Next separate decision

Treat token-boundary grounding and observation-alias authority as concrete correctness work. A bounded token-boundary rule could reject `available` inside `unavailable`, but it would not by itself resolve truncated clauses or misleading aliases. Alias identity may require a distinct typed namespace or evidence explicitly bound to the declared source definition. Root should review those alternatives and their compatibility implications independently. This patch intentionally preserves current substring and alias behavior with characterization tests; passing the whitespace suite is not evidence that those semantics are safe.
