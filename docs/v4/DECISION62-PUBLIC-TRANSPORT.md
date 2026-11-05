# Decision 62: bounded public proposal experiment

Root approved the reversible experimental safe-mode profile after reading the complete actual Opus 62 and 62a responses. The decision preserves the manual bridge, default-disabled runtime inference, customer/private-evaluator exclusion, and existing financial/effect mandates. No model candidate changes claim state or money.

The actual reviews are [62](decisions/reviews/62-public-proposal-cli-isolation.json), session `3dc52e0b-c5fd-435c-b7f3-4994f13def89`, and [62a](decisions/reviews/62a-public-safe-mode-confirmation.json), session `211542da-1764-4e8f-9072-8e78e896a3fc`. Both received sanitized design facts only. Original bare attempts were REFUSED because that profile did not use existing OAuth authentication; their receipts and v1 manifest remain unchanged.

## Choice and alternatives

The chosen existing-auth CLI profile pins binary hash, help hash, version, argv, environment hash, system prompt, schema and exact public input. It uses safe mode, empty tools, strict explicit empty MCP, disabled commands/Chrome/settings/history/auto-memory/updates, a fresh owned cwd, bounded combined output, a process-group timeout, and no retry. The environment is an allowlist. HOME retains its existing location; OS-derived USER/LOGNAME identify the normal authentication account. No credentials are extracted, copied, created or passed in the model input. The separate public script requires a recorded passing control receipt and an exact v2 request manifest.

Alternatives were remaining manual-only, waiting for bare OAuth support, obtaining a new direct API credential, or using another OS account/VM. Manual-only remains the operational baseline. New credentials/accounts were unnecessary for this authorized public experiment and would require a separate exposure/resource decision. A direct API would not itself establish the absence of provider-internal context or retention.

Root rejects the adviser's blanket demand for fresh permission for each already authorized public engineering call. This does not authorize customer processing, private evaluator disclosure, user-configuration writes, new accounts or real vendor/financial actions.

## Actual controls and limitations

Installed CLI was `2.1.318`, binary SHA256 `677a2ea7bf576cedd20e191d973914ed8a41796f53a63b1923381ddc4d5b5e7d`. Control attempt001 failed before inference: the initial scrubbed environment omitted USER/LOGNAME; normal read-only auth status showed unauthenticated. Adding only the OS-derived identity fields restored existing authentication. That refusal remains recorded.

Attempt002 observed all five positive canaries: parent CLAUDE.md, project CLAUDE.md, a harmless owned hook, an owned MCP initialization sentinel, and a Read tool retrieving an owned public token. Under the complete negative profile none appeared, the initialization reported empty tool/MCP inventories, no tool calls occurred, and neither run changed owned-project persistence metadata. The positive run explicitly enabled only these controlled surfaces. Only temporary sentinel files were removed; no existing user state was cleaned.

Receipt `W/receipts/interpretation-62-safe-controls-002.json` SHA256 is `0a84fbdde0cd2592d5758711ed872a9882d4b5ecd4b7c5cc46c9d1b8d1b1f26f`. The exact profile is included in `fixtures/correspondence/interpretation-60-model-manifest-v2.json`. Local process tests verify timeout kills a descendant before its delayed sentinel write, including when the leader exits while a child holds output open. Unexpected tool/MCP activity or owned-project persistence blocks further calls from that adapter.

User-scope canaries: **NOT_RUN**; writing real user configuration was not authorized or necessary. User/policy inventories read names and metadata internally and emit only class flags/counts/hashes. User settings exist; user CLAUDE.md and the inspected local managed-policy directories were absent. User-scope suppression is **NOT_ESTABLISHED**. Managed-policy content inspection and network observation are **NOT_RUN**. Concurrent unrelated session metadata changes are not attributed to this adapter. No claim is made about provider-hidden context, full model-visible context, provider HTTP wire, retention, or complete host isolation. Receipts establish adapter-supplied bytes/settings and the named observations only.

## Four measured requests

These exact requests were public and self-authored before implementation, not independent evaluation. The v2 manifest was frozen before inference. Each received one attempt:

| Public case | Mechanical output | Deterministic mapping without correction | Client-reported USD |
|---|---|---|---:|
| availability_paraphrase | Schema/span valid | UNKNOWN: two negative propositions | 0.043068 |
| lateness_paraphrase | REFUSED: invalid JSON | Unavailable | 0.030884 |
| invoice_paraphrase | REFUSED: invalid JSON | Unavailable | 0.036212 |
| award_paraphrase | REFUSED: invalid JSON | Unavailable | 0.046772 |

At initial measurement: **1/4 schema/segment-valid candidates, 0/4 directly compatible interpretations without correction**. A subsequent generic validator review found that complete segments could contain bytes not covered by any proposition. The final validator requires proposition coverage of every substantive byte as well. Replaying the stored availability output locally, without another model call, refuses those uncovered bytes. Under this final validator the result is **0/4 fully grounded candidates and 0/4 directly compatible interpretations**. Both source stages are preserved; this refinement is not a new model measurement. No model-based completion gain is established. No malformed response was stripped, repaired or retried. All four transports reported zero tool use and no owned-project persistence. Their separate receipts are `W/receipts/interpretation-60-safe-{availability,lateness,invoice,award}-001.json`; identical public copies are committed under `docs/v4/validation/interpretation-60/`.

USD0.156936 is the aggregate client-reported estimate for these four calls; it is neither a verified charge nor a hard subscription spending cap. Response stream hashes were retained for every request. The initial error receipts did not retain model-result session/usage separately; this is a measurement limitation, not evidence that inference did not occur. Future transport receipts now capture those fields before strict candidate parsing.

The runtime remains disabled and customer-ineligible. Human correction may make an unusable candidate useful, but human false-attestation, review time and throughput remain **NOT_RUN**. The existing private 0/50 supported result and mandatory-review 50/50 remain unchanged; these public engineering measurements do not overwrite that independent evidence.
