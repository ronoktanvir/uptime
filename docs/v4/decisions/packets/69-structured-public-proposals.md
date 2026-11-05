# Decision 69: opt-in structured public model proposals

## Context and preferred choice

The manual dispute interpretation bridge is source locked and remains operational. Four earlier public model proposals yielded zero fully grounded compatible candidates; malformed JSON and source offsets were distinct failures. Customer runtime model inference remains disabled. The user now explicitly requests real Claude Code Opus 5.5 implementation delegation as well as concise criticism of substantial decisions.

Prefer an additive, explicitly configured structured-output option in the existing bounded public transport. Pin the complete JSON Schema in the transport profile; require the exact request schema and structured-output flag to match; use the installed CLI's documented `--json-schema` flag. Accept only a successful result from the exact requested model, empty tool/MCP inventories, no tool calls, and a dictionary structured result. Return canonical JSON to the existing typed adapter. Do not repair malformed output, retry, silently fall back, change financial authority, or enable customer inference. The default transport and existing experiment receipts remain unchanged.

The implementation team is separately replacing model-authored byte offsets with deterministic source block identifiers. The transport cannot establish semantic truth or source completeness; the typed grounding validator and human review still do that work. New authored public controls must remain distinct from prior independent results.

## Alternatives and costs

- Keep plain text JSON only: no additional CLI dependency, but repeats an observed format failure. Retained as the existing explicitly selected profile, not an automatic fallback.
- Strip fences or repair output: cheap implementation but changes the measured response and can hide unsupported semantic content. Rejected.
- Use structured output only when configured: small constructor/request/result validation change and process-level regression tests; requires verifying actual CLI behavior because structured output might expose an internal tool. Preferred only if the empty-tool constraint actually holds.
- Switch providers or obtain a new API credential: unnecessary auth/integration work for this bounded public experiment and does not itself solve grounding.

## Tests and failure risks

Freeze public input before invocation. Verify actual CLI model/session/tool inventory and original output receipt. Test schema/flag/profile mismatch rejection before dispatch; reject missing, scalar, non-finite or ambiguous structured results; preserve output/time/process limits; preserve existing default behavior and blocked transport state. If the CLI exposes a tool to implement structured output, refuse the candidate and record the failure rather than weakening the tool policy. Passing a small authored experiment cannot replace the private 0/50 supported-reply result.

Engineering coding delegates may edit only explicitly assigned public source/test directories using restricted Claude file tools. Parent agents run tests and Git. They do not receive credentials, customer captures or private holdouts. The native-posting retest previously rejected by automatic approval review stays disabled; no task is delegated to work around that rejection.

## Rollback

Remove the additive structured profile and use the existing manual bridge/plain public experiment. No database migration, external effect, financial state change or customer inference is part of this decision.

## Independent criticism requested

Critically assess the preferred choice. Identify concrete missing controls and implementation pitfalls. Distinguish essential corrections from optional work; avoid a review council or unneeded authorization requests for the user's already authorized public engineering work.
