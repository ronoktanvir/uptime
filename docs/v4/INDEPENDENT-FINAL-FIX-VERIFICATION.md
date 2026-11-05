# Independent verification of the four final-review fixes

**All four previously reproduced defects pass the post-fix controls on frozen product source `14c343d4f215388eac88e4c5cc7bc4d16917341e`.** The result covers mounted application flows with a real promoted generic adapter, disposable synthetic inputs, and the operator attribution entrypoints. It does not certify real provider observations, external delivery, legal entitlement, browser behavior, or the complete product.

The [new verifier](../../scripts/independent_final_fix_verifier.py) asserts corrected behavior. The [recorded JSON result](INDEPENDENT-FINAL-FIX-VERIFICATION.json) contains its successful complete execution. The original [review](INDEPENDENT-FINAL-REVIEW.md) and [defect reproducer](../../scripts/independent_final_review_probes.py) remain bytewise unchanged. An exit 0 from that original reproducer would mean a defect reproduced; it is not used as evidence of correction here.

## Frozen source and execution boundary

- Worktree: `/Users/ronoktanvir/.local/share/uptime-engineering/worktrees/final_fix_verifier`; branch: `remediate/final_fix_verifier`.
- Product SHA: `14c343d4f215388eac88e4c5cc7bc4d16917341e`; tree: `ce6ee3bea1ad2e84f938a4bbc7c849609ef2817d`. The initial worktree was clean. Only this report, its JSON receipt, and the new verifier were added; no application file or original test was edited.
- Existing interpreter: `/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python`. Nothing was installed. No full-suite run, private holdout, saved native capture, current Ramp credential, or installed operator database was accessed.
- Every execution creates disposable databases and fresh account/resource/claim identifiers, reviewer keys, source credentials, issuer keys, and office witnesses. The underlying contract and native-shaped declarations are explicitly synthetic public test fixtures. The fixed UUIDs in the synthetic native reader have no provider identity claim.
- The setup helper clears inherited `UPTIME_*` and `RAMP_*` configuration, blocks socket connections and DNS, and points packaged native capture paths at nonexistent locations. The new verifier prohibits child processes after collecting Git metadata, which also blocks model CLIs. Synthetic extraction receipts are local parser inputs, not model runs.
- `create_app`, middleware, signing, exact reviewer mandates, mounted onboarding/evaluation/correspondence/dashboard/native-summary routes, real resolver, and durable SQLite stores are exercised. Product resolution and financial logic are never replaced. `RampWorkspace.import_observation` and `AwardAttributionStore` methods are the operator import/registration/award/allocation entrypoints; the native summary is read through `GET /api/ramp/workspace`.
- Direct database reads establish retained history. Direct writes appear only in explicitly labeled negative corruption controls after a positive native lifecycle succeeds. No claim, award, reservation, or financial table is fabricated to establish a passing case.

## Observed results

| Finding | Positive result | Controls against an overbroad repair |
| --- | --- | --- |
| Native attribution after lawful response | Current signed original receipt accepted; active binding stays `1` after the approved zero-dollar response; later award accepted and freshly attributed; restart remains bound | Five corruptions suspend attribution and reject subsequent awards; custody digest substitution, excess minor unit, and reservation rewrite are rejected |
| Independent resource totals | Equal credits `$12.51 + $12.51 = $25.02`; unequal credits `$12.51 + $25.01 = $37.52` | Same-obligation aliases total `$12.51`; conflicting alias values display `Not additive`; evaluation and claim views share the same obligation |
| Regional intake | Same resource in separately covered North and South enters with HTTP 200 for both; distinct economic identities and `$30.06` portfolio total | Idempotent repeat intake preserves state; same-region aliases return 409; region aliases under nonregional terms also return 409 |
| Compound denial | Exact earlier waiver text and a separately composed licensing/arbitration condition both become `HUMAN_REVIEW`, reason `unknown`, with no response actions | A factual numeric denial alone and the same denial with benign closing text both draft, approve, and submit the factual response |

### Native lifecycle and retained evidence

The native probe promotes the generic resource adapter through candidate intake, positive/refusal tests, interpretation, approval, and activation. It creates a correspondence claim, ingests independent signed evidence, and obtains `contract_version` and `contract_source_sha256` from the public claim GET. Those exact values are included in the vendor-signed original receipt. The resolved correspondence version is not assumed to equal the adapter version; the active adapter version remains present in the preflight citations.

The original is accepted as `HISTORICAL_FILING`. Separate registrar/vendor-verifier witnesses then register that actual-verifier-mode filing, vendor/finance witnesses confirm an award, and a reciprocal generated credit/bill observation receives a finance-signed allocation. The mounted native summary reports `RAMP_APPLIED_ATTRIBUTED` with one active binding.

The vendor requests missing log references. The ordinary `approve-response` and `submit-response` routes produce exactly one `procedural_evidence_only` receipt requesting `0.00`, with the exact original predecessor. The binding remains active. A later award is then accepted, a new snapshot of the generated native facts is signed and observed, and a new explicit allocation attributes that post-response award. The snapshot has one active binding and two historical bindings; older bindings are not replayed into the new snapshot. Restarting the real app with its public office configuration preserves the valid state.

Across this lifecycle, the original evidence's canonical bytes, original reservation row, registered claim row, and raw signed custody event rows remain unchanged. `filing_identity` also remains unchanged after the response. `actual_recovered_cash` stays null. `ACTUAL_NATIVE` identifies the exercised verifier mode; every supplied native fact here is generated test data.

The following negative controls mutate only the disposable persisted claim state after the positive lifecycle. Every mutation is committed before the mounted summary is read. The exact clean state byte string is restored afterward, and attribution must become valid again.

| Corruption | Summary/new-award refusal |
| --- | --- |
| Procedural receipt and packet changed to `0.01`, including recomputed local packet/approval digests | `INVALID_PROCEDURAL_RESPONSE` |
| Response predecessor changed, including recomputed local digests | `INVALID_PROCEDURAL_RESPONSE` |
| Original receipt timestamp changed | `EXTERNAL_RECEIPT_CONFLICT` |
| Response ID has no canonical reservation | `CANONICAL_PROCEDURAL_RESPONSE_REQUIRED` |
| Additional local initial filing appended | `INVALID_PROCEDURAL_RESPONSE` |

Each corruption produces zero active bindings and refuses a newly signed award. An attempted SQL update of the canonical reservation independently raises `immutable claim reservation`; no trigger is removed or bypassed. Consequently these controls establish fail-closed behavior under retained reservation integrity, not behavior after an administrator removes the database's protection.

### Economic identity and correspondence coverage

The equal-resource case also delivers signed source evidence and files both claims. Four estimate contributions then represent two economic obligations: the evaluation and correspondence views do not double the `$25.02` estimate, and claimed totals also equal `$25.02`. The unequal-resource case verifies estimate aggregation only. Alias controls use separate adapter installations for one resource, demonstrating both same-value deduplication and explicit refusal to choose between conflicting values.

The regional probe repeats the original collision conditions using the supported account-and-region subscription terms. Both regions resolve through the promoted adapter before intake, each produces `$15.03`, and each intake exposes the same economic identity as its corresponding evaluation. This probe verifies intake and estimation, not a complete regional filing/award lifecycle.

The denial probes start from approved, filed claims and ingest independently signed vendor messages. Both unknown compound grounds retain the full original text in the public case response. The two positive controls complete response authorization and submission after the cooldown. This supports bounded complete-clause handling for these texts; it does not establish general natural-language or legal interpretation accuracy.

## Commands, artifacts, and verification limits

Executed from the frozen worktree:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python scripts/independent_final_fix_verifier.py > /tmp/uptime-independent-fix-verifier-result.json
```

The final complete invocation exited **0**, with `status: PASS` and all four groups in the recorded JSON. Targeted iterations used `--probe verify_native_lifecycle`. These are four assertion-based probe groups, not a claimed pytest count. The only warning in the final execution was Starlette's existing httpx TestClient deprecation warning.

Harness preparation exposed and corrected three fixture assumptions: the public resolved contract version differs from the cited adapter version; macOS temporary paths must be resolved before office configuration loading; and direct SQLite mutations must explicitly commit before another connection can observe them. The canonical reservation update was rejected by the actual immutability trigger and retained as its own negative control. No failed harness iteration was counted as evidence of a product fix. No product source changed during those iterations.

The verifier records both its original source pin and the executing HEAD/tree so an integrated rerun does not masquerade as this frozen-source execution. This report makes no claim about later commits. The separate bounded historical resource-identifier delimiter guard was outside this four-fix scope and was not incorporated, retested, or duplicated here. Socket-listener and browser checks belong to the integration owner; TestClient establishes ASGI behavior only. Default release-closed launcher behavior and external authority assumptions are unchanged by this test composition.

Original artifact SHA-256 checks ran before and after execution:

| Artifact | SHA-256 |
| --- | --- |
| `scripts/independent_final_review_probes.py` | `16f071557f95b9fd93c850a123e51a497d53a4aa1ba772923ad6363aaec3b202` |
| `docs/v4/INDEPENDENT-FINAL-REVIEW.md` | `9633e9089125d051ad1bfc6a20e9287efe1dab80d76443a4c972b07f6adedf6f` |

Relevant frozen-file SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `uptime/claim_identity.py` | `29563c9374b59ba6c0a1decf1b62061575a63b73497071da7d114524b89e9363` |
| `uptime/correspondence.py` | `068cde4bf48225b690ef36c35596b0aa9f9537e6f84adb059464a3a2c61e5865` |
| `uptime/correspondence_reason.py` | `43cc4d3d851456367b4e871d02cdb084700d26a4e87c1affef0acfb9fce6bc43` |
| `uptime/correspondence_language.py` | `7bb6f41100e87cf49f50595f177d4a7ecc24d81f3d648b1ce756f35db3c9245f` |
| `uptime/correspondence_history.py` | `022db324e3d6e64cb2feba9c7d98b56d9a0dbfb0b43d049f3e4ad18a024b21bb` |
| `uptime/ramp_award_attribution.py` | `5ce1541d58ff87176c7b03927b6fa36d7fed969030d7536bfda5675812a1bc02` |
| `uptime/vendor_registry.py` | `e039cc901b2c05750b669723b9c463b1a4e5370e4a83b85c262b20b02ff88e49` |
| `uptime/workbench.py` | `e4f86e677eb89f3ce2e363e9ba0f3aa6151af891ed5b64ea051f6c64fe13bbc0` |
| `uptime/v4_routes.py` | `1da058743f418663f714c5a960bf8dc01cd9cfdef3b0c5f530b88aa86f4c4509` |
| `scripts/independent_final_fix_verifier.py` | `40cfced0c5d8e8d0373d81c3559cb236f4cc49be1f89dc05d2daf63a6bd517c4` |

No additional financial or security regression was demonstrated by these bounded checks. The verified conclusion is that the four reported combinations now succeed while the listed authority, identity, and corruption controls continue to close unsafe paths.
