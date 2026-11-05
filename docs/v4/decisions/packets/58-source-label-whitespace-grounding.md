# Source-label grounding across ordinary whitespace

Review a bounded compiler correctness fix. A fresh genuine extraction of an explicitly approved, independently authored synthetic public agreement was rejected because its exact original phrase contained a line feed while the validator compared it against a whitespace-normalized source block. The proposed correction normalizes both sides with the already established within-block whitespace function. No legal grammar, evidence role, economics, source text or model proposal changes are proposed.

## Evidence and authorization

Root explicitly authorized this sanitized public-only Opus 5.5 consultation and reserved decision 58. The agreement itself states that public-only extraction is approved and represents no real provider, customer or commercial authority. No private evaluation inputs, oracle, credentials, customer contracts or confidential evidence were inspected or included. The implementation remains isolated at integration `07d24c3`; its full post-merge suite passed 2,266 tests with one existing deprecation warning.

Actual model `claude-opus-5-5`, session `cc7d3b05-2261-48aa-8a75-16903e81050d`, produced a new immutable rejected proposal. Source digest: `f9e96913e9abbc341d66ca8a61c619f6619d78b068420fbf88c6a8ccfe1a99d5`. Rejection content address: `ea5d0da85701cf81fe9947bc025a905992b507dd8bdc3e3a4d3adb565bc1aa61`. Raw proposal digest: `2ea482b00048afb105ba4e4460e1922f35d39eca9c0e5e96eee8e9a4298e2bfb`. All original public source and rejection bytes remain unchanged. This is a post-remediation refusal, not first-pass success.

Offline diagnostics identify only block 13, field `provider_causes`: `Ungrounded provider_causes labels.` Its source offsets are `[1716,2237)`, with block SHA-256 `7a653e2ba145dfd2fd7e33ccadef098b80d28e3f3e1b4123f5228008e4e97d32`. The model supplied this exact contiguous original source phrase:

```json
{"label":"provider_incident_unavailable","phrase":"provider incident record marked\nunavailable"}
```

The surrounding public clause requires both provider incident records and separately attributed customer operation records for the same account, product, region and second. This review does not reconsider that existing typed telemetry rule or add issuer authority.

## Existing implementation

The compiler preserves `original`, offsets and its block hash in the citation. It separately sets `quote = normalize_source_block(original)`, whose established implementation is `' '.join(text.split())`. This handles spaces, line feeds, CRLF, tabs and ordinary NBSP. It does not remove punctuation, hyphens or zero-width characters.

For each of the existing `symptoms`, `provider_causes`, `exclusions`, `fee_exclusions` and `request_fields` lists, it accepts a stable-label dictionary only when:

```python
isinstance(item, dict) and set(item) == {'label', 'phrase'}
and isinstance(item['label'], str)
and re.fullmatch(r'[a-z][a-z0-9_]{0,63}', item['label'])
and isinstance(item['phrase'], str)
and 0 < len(item['phrase']) <= 256
and item['phrase'] in quote
```

The exact supplied phrase and the source block identity/hash are stored in `label_bindings`. A repeated stable label with a different raw phrase currently fails as conflicting definitions. Plain string list entries follow a separate existing grounding rule and are outside this change.

The independent pre-fix reproduction uses `Responsibility includes provider equipment\nfailure.` and stable label `equipment_failure`. Its exact wrapped phrase refuses. Exact CRLF, tab and NBSP versions also refuse. The ordinary-space version accepts. The normalized proposal phrase `provider equipment failure` already accepts against the wrapped source. Thus the current validator rejects the more faithful verbatim representation while accepting the normalized equivalent.

## Proposed correction and boundaries

Keep the existing dictionary shape, identifier format and raw 1–256-character phrase bound. Compute `normalized_phrase = normalize_source_block(item['phrase'])`, require it to be nonempty, and check it is a contiguous substring of the already normalized **current block**. Store the original model phrase and original citation unchanged. The empty check prevents whitespace-only phrases from degenerating into universal empty-string substring matches; such phrases do not identify a source definition.

Retain the existing raw-phrase conflict check for repeated stable labels. Distinct phrases that collapse to the same whitespace sequence could be equivalent, but permitting their reuse would broaden collision policy beyond this repair. A repeated label with different raw wording continues to refuse; a different stable label pointing to the same supported phrase retains current behavior. No cross-block lookup, token reordering, word insertion, synonym mapping, case folding, punctuation removal, hyphen repair or zero-width removal is added.

The correction makes exact original phrases and already-supported normalized phrases consistent. It also accepts other equivalent combinations of the existing whitespace characters. That is the main incremental trust boundary: the proposed phrase need not be byte-exact, while its normalized text must occur contiguously in the exact cited block. This is consistent with previously accepted normalized proposals, and original source provenance remains available for named human interpretation review.

The predicate retains the current substring granularity. It does not establish that an arbitrary matching substring represents the entire rule; existing whole-block material-coverage and authority checks still apply. Repairing those independent semantic boundaries is outside this correction.

An alternative is `phrase in original or phrase in normalized_block`. It repairs the observed exact original phrase and preserves old normalized input, but remains inconsistent for equivalent mixed whitespace. A strict `phrase in original` alternative would reject normalized phrases already accepted today. A broad token-based or semantic fuzzy match is rejected because it can accept reordered or added meaning.

## Falsifiers and validation

- Actual compiler tests for all five stable-label list fields: space, LF, CRLF, tab and NBSP produce equivalent labels while preserving raw phrase, citation text, offsets, block digest and whole-source digest.
- Existing normalized proposals still compile against wrapped sources. Raw phrase length and stable-label format limits remain enforced before normalization; whitespace-only phrases refuse.
- Reordered, added, truncated-to-foreign or neighboring-block-only phrases refuse. Punctuation, zero-width and hyphen changes do not become equivalent merely because surrounding whitespace is normalized.
- A repeated label with a different phrase refuses, including whitespace-different raw definitions. Unchanged repeated definitions preserve their existing behavior. Distinct labels for an identical phrase retain current behavior without creating a new economic or evidence operator.
- Each committed genuinely accepted public proposal keeps its current acceptance. Revalidation of every relevant public third-source receipt reports any changed current result explicitly while keeping historical status and source/receipt bytes intact.
- No private evaluation fixture is read. No adapter is activated. No new model generation occurs until the fix is independently validated and root separately authorizes a fresh attempt. A previously refused proposal that validates offline still does not become an accepted artifact.

## Questions for the independent reviewer

Does shared whitespace normalization after the existing raw bounds repair the demonstrated defect without changing source meaning or evidence authority? Is retaining raw-phrase collision refusal the appropriate bounded choice, or does this proposal miss a collision that could admit ambiguous authority? Identify any concrete reordered, injected, neighboring or empty-phrase counterexample that passes the proposed predicate incorrectly. Rank the alternatives, name any dissent, and specify required falsification tests. Give advice only; do not treat your review as human interpretation or activation approval.
