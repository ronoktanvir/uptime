# Public evaluation 76 baseline protocol

The input/oracle package was frozen in `388b5ebed34dbb32be3d0c82b7ec732ec1097aff` before any implementation execution or model call. It measures the unchanged core at `fd6537cc4e3118a9b6e29f4804a505ed591ea9ea`. All six onboarding cases and twelve replies are fictional AUTHORED_PUBLIC material authorized for this bounded external inference. This is not a private or blind evaluation.

The corpus manifest SHA-256 is `6dc212c296dea38dc5ad7a39ccdda3fe8ad64e5e902d93d1329c66c8060ce82d`; the input/expected file-list digest is `f698047ef6b92c55d8c853e01bfdadcc61585f5610223939254656367def5fe9`. The [frozen package](../../fixtures/evaluation76_public/README.md) contains separate inputs, expectations and hand arithmetic. Expected outcomes were not derived from code or a model. Public entrypoint/serializer source was inspected only after that freeze to build evaluator plumbing.

The [request manifest](evaluation76/requests/manifest.json) pins eighteen exact requests and local evaluation contexts. Its SHA-256 is `067e9089eba0dfb876927d456967f8d13379778991d56e9194bb04308be33455`. The manifest also pins the runner bytes, comparison labels, concurrency limit and authority policy. No expected labels, oracle arithmetic, account overlay, pricing records or customer evidence are sent in onboarding prompts. Dispute requests contain only one exact reply and the existing adapter's minimal synthetic claim context.

## Frozen execution boundaries

The [runner](../../scripts/evaluate_public_76.py) calls `vendor_model.generate` for onboarding and `SafePublicClaude` with `BLOCK_SYSTEM`, `serialized_block_request`, `PublicBlockInterpretationAdapter` and `proposal_for_review` for replies. It performs at most two independent calls concurrently, at most one attempt per case, and rejects any request/core/corpus/harness digest change. A create-only attempt directory prevents silent retry after interruption or error.

Onboarding uses the existing legacy subprocess profile, **not SafePublicClaude isolation**. It requests an empty tool list but its JSON envelope does not verify the initialized tool inventory. Its 180-second limit and a 3,000,000-byte spool bound are recorded. The frozen legacy entrypoint itself recognizes a surrounding JSON fence before validation. The runner preserves raw output, reports that existing normalization separately, and does not count such output as unmodified strict JSON success. It does not add fence removal or other output repair.

Disputes retain the existing pinned binary/profile, 60-second timeout, 300,000-byte output limit, empty tool/MCP inventory checks and complete-request allowlist. This transport does not establish user-scope suppression or a provider retention guarantee. Credentials remain at the existing CLI authentication location; authentication values are absent from request/receipt files. Both paths spool process output from startup to protected files, including partial output on timeout.

Accepted onboarding proposals are compiled, bound to the unchanged authored overlay and passed to the documented evaluator with the frozen facts. The runner does not synthesize opaque governing-fee authority or source-meaning review contexts. Missing authority is reported as a separate downstream gate, not wrong arithmetic or a model semantic error. No reviewer action, activation, effect authorization, ledger mutation, live vendor communication, Ramp action or native qualification is executed. Extraction acceptance alone is not operational completion.

Results distinguish transport failure, strict JSON/schema/grounding, accepted extraction, mapped reply meaning, downstream outcome/amount, and unperformed action authorization. A transport abort on a negative case is a safe absence of financial action, not successful semantic recognition. Actual UNKNOWN mappings and failed attempts retain separate counts. No failed case is removed, rewritten or retried, and the cohort is not expanded.

## Preparation checks and execution

Preparation checked all ten input/expected file hashes, eighteen source text hashes, the six/twelve cohort counts and independently stated arithmetic. The runner passed syntax checking and controlled subprocess checks for stdout/stderr capture and preservation of partial output after timeout. These local checks made no model calls. Existing tests are unchanged.

After the harness/request commit, the authorized command is:

```sh
/Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python scripts/evaluate_public_76.py run-all \
  --request-manifest-sha256 067e9089eba0dfb876927d456967f8d13379778991d56e9194bb04308be33455 \
  --output-dir /Users/ronoktanvir/.local/share/uptime-engineering/review/public-evaluation-76/baseline
```

The scorer reads gold only after execution. Full process output remains protected outside Git; a later public receipt will preserve request/response hashes, actual identities, all errors and separate denominators. No runtime result was known when this protocol and its requests were committed.

## Completed baseline

The unchanged frozen target has now completed all eighteen one-attempt requests. [Results and failure taxonomy](evaluation76/BASELINE.md) retain the 0/4 supported onboarding acceptance result, 3/6 complete supported reply mappings, 6/6 review abstentions, actual identities and original errors. No case, request or expected answer was revised.
