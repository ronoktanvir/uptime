# Opus55 local implementation and public-only validation

The bounded changes align extraction hints with existing compilation, preserve claimant proof without issuer authority, and make current refusal reasons inspectable through an explicit offline public attachment. They do not establish a fresh model acceptance. The independently selected third public source remains refused.

## Changes and controls

- `f09d261` shares the compiler's existing within-block `' '.join(text.split())` normalization with extraction hints. Space, LF, CRLF, tab and ordinary NBSP all produce the same typed operator. Original source text, offsets, quote digests and source digests are retained. NBSP was already accepted by the compiler; the change preserves that contract.
- `fb06019` uses exact affirmative no-minimum incident/outage-duration templates. Quoted, scoped, hyphenated and zero-width forms remain unresolved. Additional unsupported minimum, conditional or quantified-duration propositions refuse the entire block in either order. Independently supported clipping and fixed-denominator effects remain supported beside the affirmative assertion.
- `bb16bca` requires bounded source language establishing an issuer verification process or issuance condition. Customer records and custodian signatures alone cannot acquire issuer authority.
- `ca51d08` preserves the existing external evidence vocabulary. Explicit source-bound claimant proof, request fields and `request_contents` permit the legacy `verification` alias, but every occurrence becomes internal `claimant_supporting_proof`. The internal label cannot be supplied as an input category. Compiled-manifest and evaluation tests cover duplicate adversarial labels: no issuer verification remains, eligibility can be established, and issuance stays `PENDING_VENDOR_VERIFICATION`. The independent scoped issuance receipt checks remain in `vendor_resource_eval.issuance`.
- `9b6538a` adds explicit offline diagnostic export and exact-source selection through the existing operator-owned public extraction directory. Normal intake reads only the selected immutable report. It neither traverses rejection archives nor replays or invokes a model. The existing vendor detail renderer displays `public_source_issues` from fixed reason codes and bounded, source-checked public clauses. Raw model rationale and exception text are excluded. Altered spans, hashes, URIs, schemas and stale revisions fall back to the existing generic refusal. A private overlay failure remains generic even when the public attachment is available.

## Public receipt outcomes

Both committed genuinely accepted public proposals, `4c3c95a236e3eb5fe06718606ec55d0fdcc0d7652ecf0cc910f2857bf9a561f8` and `697b2b662246f6f08672cb23d59ca03cadfa506f117947ff12debd063e258cc1`, compile at baseline `38bca3e` and each implementation commit. Their proposals were not edited.

One historical third-source refusal changes its current offline result. Receipt `e3ff63da0b9f22395300fb10c37130680c193f08c16324cc94c6458db6d525ba` previously validated under baseline code after the symbol-grounding correction. From `fb06019`, its block 11 refuses with `Minimum-duration absence lacks an operative mapping.` The proposal omitted the now-enforced existing no-minimum-duration effect. This was always a historical rejected receipt; offline validation did not create an accepted receipt or authorize promotion.

The latest historical receipt `b0fb6722739bea9d89554f5c783a6cbbbf893bcb02de457fc1d728534d0615b9` remains rejected. Its exact public source digest is `f9e96913e9abbc341d66ca8a61c619f6619d78b068420fbf88c6a8ccfe1a99d5`. Offline export produces report `4289c892761a64a89ef23b5011f7be6306a3379e54e6c05663de000a0df092bf`, with these checked public issues:

| Block | Original offsets | Fixed reason code | Original block SHA-256 |
| --- | --- | --- | --- |
| 11 | 1551–1683 | `UNSUPPORTED_BLOCK_PROPOSITION` | `7bac940c9d7257a4965a2a8dcd781a81fb3cb429b0a242beda50e2f1da6f6011` |
| 14 | 2239–2747 | `ISSUER_AUTHORITY_UNESTABLISHED` | `204aec2acb70d6363fd1d1e3ef87ac7241acda537ed1d23268f52870a83d14cc` |

The public JSON file's byte digest remains `c330f9bd5b250b8d1429d60cbb0d86fd1b29c33913415155d4b3e1170c46b643`; the original rejection file's byte digest remains `abef83cdf3ccb76ff683794342988685764452f04d69b4359efb877e5bb93394`. The diagnostic was exported only to the isolated task directory, not selected in the live extraction directory. A changed validator revision requires a new explicit offline export.

## Validation evidence

The vendor suite passes 214 tests, including 13 diagnostic export, signed-intake and privacy controls. The full run passed 2,231 tests and failed only the frontend subprocess launch because the shell PATH omitted `/opt/homebrew/bin/node`. Rerunning that exact failed test with the installed Node directory on PATH passed. All 2,232 collected tests therefore passed across the full run and its environment-corrected rerun; no code changed between them. The existing Starlette/httpx deprecation warning remains. Test and audit logs are local under `$W/receipts`, where `$W` is the durable engineering workspace:

- `opus55-whitespace-before.log` and `opus55-whitespace-after.log`
- `opus55-templates-before.log` and `opus55-templates-after.log`
- `opus55-authority-before.log` and `opus55-authority-after.log`
- `opus55-all-vendor-final.log`
- `opus55-public-acceptance-audit.json`
- `opus55-full-final.log`
- `opus55-node-path-rerun.log`

Only public source/proposal artifacts and ordinary synthetic regression inputs were used for this work. No private evaluation fixture or oracle was consulted. No actual model retry, adapter activation or promotion was performed. A future extraction uses the changed prompt/configuration and needs its own genuine receipt and existing independent interpretation/promotion gates.
