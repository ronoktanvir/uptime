# Decision 62: authenticated tool-free public proposal transport

Review a narrow execution-profile change; this packet contains only public code/design facts. No credentials, customer data, private evaluation text or gold are included. We seek an actual critical Opus review before finalizing the profile. No runtime code change to remove `--bare` has been made.

## Observed blocker and existing authorization

Decision60 authorizes an optional LLM that only creates an untrusted candidate in a human interpretation-review bridge. It cannot update claim stage/money, close a denial, supply evidence, authorize follow-up or invoke any tool. A server-owned manifest hashes the complete serialized adapter request: fixed model/system prompt/schema, the approved public fixture text and minimal synthetic context, plus execution settings. Runtime is disabled by default. Private/customer/evaluator inputs fail before provider invocation. The human semantic review and separate existing effect mandates remain.

Two explicitly manifested public fixture attempts using `--bare` returned provider failure before any proposal. Both refusal receipts remain unchanged. Local `claude --help` states that bare mode skips hooks, plugin sync, auto-memory, keychain and CLAUDE.md discovery, but also disables OAuth/keychain authentication and requires an API key or explicit key helper. The available authorized subscription uses OAuth, as verified by prior actual sanitized consultations. We will not read/copy/extract credentials or invent an API key.

Root has already authorized bounded public engineering model calls. No new user permission is requested. A profile change still needs security analysis because dropping `--bare` removes isolation features.

## Options

A. Retain bare mode and record C's real-provider capability blocked while D and injected/mocked C tests run. Strongest minimality; no actual proposal demonstration through the available subscription.

B. Use the already verified consultation profile for manifest-approved public synthetics: a newly created empty temporary working directory, `-p`, fixed `--model claude-opus-5-5`, `--tools ''`, `--strict-mcp-config` plus explicit empty MCP server configuration, `--setting-sources ''`, `--disable-slash-commands`, fixed `--system-prompt`, `--system-prompt-snapshot off`, `--no-session-persistence`, output JSON, per-call USD1 budget ceiling and 60-second process timeout. No resume/session identifier, repository path, files, directory attachments, plugins, browser/IDE mode or client-controlled invocation flags. The stdin bytes are precisely the manifested request; stdout is strict typed candidate JSON plus provider receipt, not executable instructions. Calls run once without retry. This is root's preferred reversible option, subject to review.

C. Build a direct API transport with a separately provisioned key, or introduce a local model. These preserve a tighter known request boundary but require authentication/setup not presently available and create a different operational surface. No secret acquisition is authorized by this packet.

## What B can and cannot claim

The exact CLI invocation/help is locally observable. The SDK/provider's internal HTTP serialization is not. A request hash therefore commits to the full adapter-visible content and settings, not an invented network-wire capture. Tool-free means the model has no executable tools and strict empty MCP, not that the trusted CLI performs no internal network operations. Empty cwd prevents repository-local discovery; it does not by itself prove that user-global memory, plugins, hooks, account metadata or hidden prompt sections are absent. `--setting-sources ''` and explicit system prompt narrow that surface, but should not be treated as a proof without verification. Provider retention/training behavior is also not established by these flags. No confidential input is allowed even if B is adopted.

Proposed falsifiers: inspect process invocation with a test runner to enforce every fixed flag and exact stdin; add a harmless canary CLAUDE.md in the empty working directory (separate controlled public probe) and verify it is not sent/used if an actual CLI option disables that discovery; otherwise remove any claim that it is disabled. Refuse caller-supplied model, tool, server, system or path fields. Change one byte of prompt/schema/text/settings and verify zero provider invocations. Inject a model command/instruction as public reply text and verify tools remain absent and the candidate cannot alter business state. Keep both earlier refusal receipts and separately record all new attempts, actual model/session/usage, manifest hash and outcome.

## Questions

Is B sufficiently bounded for these already-public synthetics, or does a concrete residual automatic context source make it inappropriate even with explicit disclosure allowlisting and no business effect? Which claims about settings/system/CLAUDE.md isolation are justified by the actual flags, and which require a different transport or a blocker? Recommend a minimum testable invocation and exact residual disclosure. Distinguish this low-sensitivity engineering experiment from real customer processing, which remains disabled. Do not require fresh blanket approval for an already authorized public experiment; identify any *new* authority or actual exposure that would change that conclusion.
