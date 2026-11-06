# ADR 69: reject ambiguous public model results; retain plain transport

The proposed structured CLI profile was **refused after actual measurement**. The existing plain, bounded public transport remains the selected profile. Customer runtime inference remains disabled. New source-block work in decision 71 continues independently.

## Evidence and decision

The [decision packet](packets/69-structured-public-proposals.md) preferred an opt-in pinned `--json-schema` profile if it retained an empty tool surface. Actual Opus 5.5 [criticism](reviews/69-structured-public-proposals.json), session `e91f309c-2e2f-404d-8b3e-7d0e480fc102`, warned that this flag might introduce an internal structured-output tool and recommended measuring that before implementation. Root accepted that criticism.

The one authored public probe completed under actual Opus 5.5, session `9af289bc-8dfe-45d9-8251-3d0baaa62775`. The CLI advertised `StructuredOutput` and emitted a `tool_use` event despite `--tools ''`. The predeclared rule refuses any such tool, so no structured profile or exception was added. The [original refusal receipt](../evidence/structured-probe-69.json) preserves the actual result and stream hash. This is not a dispute-interpretation measurement, an API write, or evidence of a harmful tool effect.

Alternatives remain plain JSON, output repair, a new direct API credential or a separately designed structured tool profile. Plain JSON preserves the existing authorization and measured process boundaries. Repair/fallback would change the measured candidate; new credentials are unnecessary here. A future structured tool profile would require its own explicit decision rather than retroactively changing this probe's pass rule.

## Implemented correction

The criticism also exposed result-framing ambiguity in the existing transport. It now rejects duplicate JSON keys, non-finite constants/overflow, non-object stream events, model fallback or mixed model use, mismatched/missing sessions, unsuccessful terminal subtypes, duplicate terminal events and an unexpected structured payload. Tool inventories and actual tool calls continue to block further calls. The existing plain adapter uses the strict decoder before its unchanged typed grounding validator. Exact financial strings remain strings.

Default CLI arguments, binary/help pinning, bounded output/time, process cleanup, retry count and public-only eligibility are unchanged. The validator does not infer semantic truth, enforce arbitrary JSON Schemas or authorize money. Schema and semantic validation remain the typed adapter's responsibility. This differs from Opus's proposal to add a general local JSON Schema validator because the structured profile was not adopted. We retain the existing HOME for authorized login and explicitly retain `user_scope_suppression: NOT_ESTABLISHED`; no host/provider isolation claim is added.

## Validation and rollback

Focused transport and interpretation checks: **98 passed, 1 warning in 2.11s**. Negative controls include the observed StructuredOutput inventory/event, model/session substitution, duplicate error keys and non-finite JSON. Existing timeout/descendant and default profile checks remain. The warning is the existing Starlette/httpx deprecation.

Rollback is reverting this focused framing correction; no database, customer setting, external record or financial state changes. Do not enable the refused structured profile as a rollback. Full integration results are recorded separately after merges.
