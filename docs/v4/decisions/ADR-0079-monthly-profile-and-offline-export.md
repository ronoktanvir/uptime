# Phase79 — Existing monthly propositions and offline request export

This increment closes runtime setup and profile parity gaps within reviewed decisions73/74. It adds no contract grammar, compiler inference, fee authority, reviewer authority or automatic model retry. The lead authorized routine implementation without another architecture review round.

`monthly` retains its strict existing protocol. `monthly-propositions` explicitly selects the existing monthly proposal wire format and existing guarded proposition compiler fallback. `resource-month` retains its separate block protocol. The new profile is present in the complete request, proposal context, immutable result and install provenance. Exact permission for another profile does not authorize it; a resource manifest cannot be accepted under a monthly profile. Source text and receipt quotes are unchanged. Each profile pins its consumed semantic family.

A proposition-derived manifest still records `model_proposition_human_review_required`; normal SHADOW, independent tests, source interpretation acceptance, approval and activation remain separate. Merely selecting the new profile does not create interpretation acceptance. A strict clause accepted by the deterministic compiler remains deterministic under the opt-in profile, matching the existing legacy behavior. Missing governing fee or semantic authority still refuses monetary evaluation.

The public Juniper Reach source and authored proposal were frozen in `20412db` before implementation. They exercise known supported vocabulary, not unseen performance. Historical failed scores and receipts remain untouched. This code change updates existing source-code dependency pins; old jobs remain historical evidence and are not silently migrated to new authority.

The CLI export work is delegated to one actual bounded Claude Code worker with file tools only. Its completed contribution, exact session and tool inventory, and native verification will be appended after the worker exits. Export is an offline readable-request preparation step; approval and submission remain distinct actions.

The actual Claude Code worker completed with exit0 in 562.313 seconds: `claude-opus-5-5`, session `837cfba4-27be-4530-bc0c-71c1e21c4790`, requested effort xhigh, exactly Read/Edit/Write/Glob/Grep, no MCP servers. It wrote only the CLI file and its new tests. Its [execution receipt](reviews/79-actual-opus-cli-worker.json) retains the invocation, source hashes before native integration, public stream reference/hash, 19 file-tool calls, two failed literal-edit attempts and complete final response. It explicitly disclosed that it had not run tests and that its guessed import locations and provider double needed native verification. No repeat review or extraction model call was made.

Native integration connected the real `public_proposal_config`, `contracts` and `vendor_model_jobs` definitions, constructed typed `ProposalRequest`, and completed the test double's real required identity/profile. Identity limits now match the shared service's 160 characters; duplicate configured kinds and invalid approval paths follow existing server validation. The writer rejects zero-progress writes. These corrections add no provider invocation or authorization. The original import failure and a native new-test count mistake remain in the test ledger.

`export-vendor` loads the existing protected server configuration and the exact Document JSON, selects an explicit principal/target/profile, and calls the existing pure request helper. It constructs the configured provider only to pin the installed executable's help/version and transport settings. It never calls the provider, opens a job service, reads or writes the approval allowlist, or creates a database. It writes a new 0600 readable JSON file into an existing owned 0700 directory outside Git. Existing files, symlinks, traversal, oversized or malformed documents, weak permissions and disabled configurations refuse. Source text including CRLF is preserved. An interrupted process can leave an incomplete newly created file; strict readers refuse it and no approval is inferred.

Reproducible operator usage (paths are illustrative; use existing protected configuration and an explicitly authorized public document):

```sh
python scripts/public_proposals.py export-vendor \
  --document /public-documents/vendor-document.json \
  --config /protected/operator/public-proposals.json \
  --output /protected/operator/exports/vendor-request.json \
  --tenant workspace-name --subject submitting-account \
  --target vendor-catalog-id --profile monthly-propositions
python scripts/public_proposals.py show /protected/operator/exports/vendor-request.json
```

The configuration must enable `vendor` and identify the installed CLI; its `approvals_path` can be absent while preparing the first export. The export prints only its path, exact request digest and absence of permission. The existing separate `approve` command still requires review of the complete request, explicit authored-public confirmation, actor and expiry; the normal signed application submits a separately authorized request. A different profile, source, nonce, provider profile or consumed source revision requires its own matching request and permission. Use `--attempt-nonce retry-...` only for an explicitly separately approved retry; export itself never retries anything.
