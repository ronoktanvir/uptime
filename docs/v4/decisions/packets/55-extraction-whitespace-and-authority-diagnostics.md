# Existing operator consistency and public refusal explanations

The latest genuine extraction of the independently authored third public source still refuses on two blocks. One refusal follows an inconsistent treatment of wrapped whitespace. The other correctly rejects a proposed evidence authority that the cited block does not establish. The proposed work fixes the extraction hint inconsistency, tightens the existing duration predicate against demonstrated false positives, and explains remaining public source refusals through the ordinary onboarding detail. This packet requests independent review before application changes.

## Observed source and receipt

The inspection used integration commit `38bca3e` in the isolated onboarding worktree. Only the already approved synthetic public document, its recorded public model proposals, application source and ordinary committed tests were read. No private evaluation inputs, expected outputs, customer overlays or hidden adjudication records were consulted. No new model invocation, adapter activation or external message occurred.

The public source is `W/review/public/postfreeze.json`, where `W` is `/Users/ronoktanvir/.local/share/uptime-engineering`. Its contract-text SHA-256 is `f9e96913e9abbc341d66ca8a61c619f6619d78b068420fbf88c6a8ccfe1a99d5`. The JSON file's byte hash is `c330f9bd5b250b8d1429d60cbb0d86fd1b29c33913415155d4b3e1170c46b643`.

The latest recorded rejection is `W/review/extractions/rejections/f9e96913e9abbc341d66ca8a61c619f6619d78b068420fbf88c6a8ccfe1a99d5/b0fb6722739bea9d89554f5c783a6cbbbf893bcb02de457fc1d728534d0615b9.json`. Its actual model session is `10ee2734-7b63-44d0-9e9b-2dc7ec8d5cb5`, recorded at `2026-11-05T02:11:10.836295+00:00`. Its byte hash is `abef83cdf3ccb76ff683794342988685764452f04d69b4359efb877e5bb93394`. Historical status is `REJECTED`, with reason `Unsupported material in resource clause 11.`

The existing offline replay reports two current failures. Block 11 remains unsupported. Block 14 reports `Proposed evidence category lacks source wording: verification`. The earlier duration-symbol rejection has already been addressed in the compiler. It is not the current blocker.

## Whitespace mismatch and independent counterexamples

Public block 11 spans characters `[1551,1683)` and has SHA-256 `7bac940c9d7257a4965a2a8dcd781a81fb3cb429b0a242beda50e2f1da6f6011`. Its exact text is preserved below.

```text
Clip any incident crossing a month boundary to the claimed month. There is no
minimum incident duration. Exclusions do not reduce T.
```

`vendor_model.generate` supplies `interval_options(block['text'])` to the model. The raw block yields `fixed_denominator` and `clip_to_month`, omitting the already implemented `no_minimum_duration`. Reflowing whitespace within the same block adds that option. Meanwhile, `compile_resource` already reflows the block before applying its operators. The genuine proposal expressly reports that the duration operator was unavailable and retains an `unsupported` effect. That refusal must remain attached to the original proposal.

The mismatch has a small independent reproduction requiring no vendor fixture.

```python
from uptime.vendor_resource_operators import apply_operator, interval_options

plain = "There is no minimum incident duration."
wrapped = "There is no\nminimum incident duration."
assert "no_minimum_duration" in interval_options(plain)
assert "no_minimum_duration" not in interval_options(wrapped)
apply_operator({}, "interval_measurement", ["no_minimum_duration"],
               " ".join(wrapped.split()))
```

The same inspection identified two existing false positives in the duration predicate. Both currently offer and accept `no_minimum_duration` when passed to `apply_operator`.

```text
There is no minimum invoice fee. Incident duration must exceed two minutes.
The rejected example says "no minimum incident duration". That statement does not apply.
```

The predicate currently combines a `no minimum` match with a duration, incident or outage match anywhere in the block. It therefore joins unrelated sentences and treats quoted, disclaimed examples as operative. A whitespace fix must include controls for these cases. The proposed predicate requires an affirmative, unquoted duration statement in its own clause. Conditional, contradictory or merely quoted wording remains unresolved. The review should assess how narrowly this predicate must be bounded.

## Evidence authority

Public block 14 spans `[2239,2747)` and has SHA-256 `204aec2acb70d6363fd1d1e3ef87ac7241acda537ed1d23268f52870a83d14cc`. It requires the signed subscription record, provider incidents, customer operation records and the monthly fee statement. It requires the customer's recording system to have a signed custodian statement for the covered identity and intervals. Missing records leave eligibility unestablished.

The latest proposal maps this block to account records, resource intervals, itemized fees and `verification`, together with recording-system and custodian requirements. The first three evidence categories and the custodian operators already represent the supported obligations. The extra `verification` category lacks source wording establishing provider verification or an award condition. The extraction prompt currently lists these categories together without explaining the authority distinction precisely enough.

A local, manually edited, in-memory diagnostic confirms that existing schema can represent both blocks. Adding the existing duration operator to block 11 while removing its `unsupported` effect, and removing the unsupported `verification` category from block 14, permits all-source compiler validation under current code. This experiment produced no accepted extraction artifact and establishes no actual model acceptance or private-case result. The original receipt still replays as rejected. No fixture or expectation was changed.

## Proposed bounded implementation

1. Derive operator options from the same within-block whitespace normalization used by validation. Keep the original text, block boundaries, offsets and hashes for provenance. Tighten the existing no-minimum predicate so unrelated nearby phrases, quoted examples, negated statements and conditional exceptions cannot supply it.
2. Clarify extraction instructions for claimant evidence, recording-system custody and provider verification. Preserve the current rejection of unsupported extra authority. Do not auto-delete unsupported propositions or translate the old rejected receipt into an accepted artifact.
3. Add structured public-source issues to the normal onboarding detail. Current quarantine views return the generic `Source or overlay validation failed.` and cannot identify either public blocker. Issues should carry a stable reason code, document digest and URI, receipt identity, exact block ID and offsets, approved public quote, field and a bounded explanation of the required evidence authority. Private overlay failures retain their existing redaction.

For the third source, a normal intake currently falls back to deterministic parsing because the model receipt is in the rejection archive. A proposed diagnostic-only lookup may read a matching rejected receipt from the operator-configured public extraction directory after verifying its filename/content address, source digest, profile and block index. It must not make that receipt a candidate, select a new external model call, or accept an arbitrary path from an HTTP client. If that lookup is too broad, retain a generic source-link issue in the normal view and expose the precise verified replay through a separate operator-supplied diagnostic attachment. The root should choose the smaller trustworthy integration after this review.

The application changes would be isolated to operator hint generation/validation, extraction instructions, typed public-source diagnostics and their ordinary detail projection. Existing private input handling and immutable event history remain subject to their current integrity checks. New public diagnostics must be bounded and rendered as text. Only approved public clause content and evidence-authority metadata may appear. A malformed, mismatched or untrusted diagnostic produces a generic refusal.

## Verification and falsifiers

- Wrapped and unwrapped forms of the same affirmative duration clause must offer and validate the same operator. Source text, block offsets and hashes must remain byte-exact.
- An unrelated minimum invoice fee, a positive minimum outage duration, a quoted rejected example, and a conditional duration exception must fail the proposed no-minimum mapping. Copying an effect from an adjacent block must still fail.
- A signed customer custodian statement alone must fail an issuer-verification proposition. Explicit source-defined provider verification should retain its currently supported meaning.
- Replaying the original third receipt must remain rejected on both original issues. New code may diagnose a correctable hint inconsistency but must not silently repair the recorded proposal.
- Normal signed intake and subsequent reads must show a matched public issue with its exact source link. Overlay secrets, private error strings, unmatched document hashes, forged receipt hashes and attacker-controlled exception text must remain absent.
- Repeated reads must preserve receipt bytes, source bytes, historical status and event order. A successful local diagnostic must expose no activation action.

The initial post-merge full suite is running separately. The public reproductions above were executed on `38bca3e`. Application changes are pending this review, so no post-change test result is claimed.

## Questions for the independent review

Is the within-block normalization and narrowly bounded affirmative-duration predicate sufficient to correct this existing operator without introducing a new interpretation rule? Does the evidence-role proposal preserve the distinction between claimant custody and issuer authority? Which diagnostic integration safely reaches ordinary onboarding views while retaining private-error redaction and the rejected receipt's status? Identify any case in which the proposed fixes could accept an unsupported obligation or leak private evidence.

No extraction retry or final policy decision is included in this packet. Any later actual proposal requires its own receipt and the existing intake, independent tests and named human review process.
