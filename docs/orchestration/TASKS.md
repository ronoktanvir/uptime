# Executed workstreams

The initial audit found no Uptime code. The first commit, `328e060`, contains the handoff, lockfile and project scaffold. CP1 commit `5a77194` established provisional shared types, a gold fixture and five passing tests before implementation branches started.

| Owner | Actual execution | Worktree / first integrated revision | Acceptance evidence |
|---|---|---|---|
| W0 | Primary Codex agent, native tools | main | API, persistence, typed contracts, 13 authenticated independent decisions, guide, final release QA |
| W1 | Native `ramp`, GPT-6 Astra / high | feat/ramp · 4f16ce8; 1b90ba7 | Scoped provider reads and same-ID proof, fail-closed draft, source-safe reconciliation and independent security reproductions |
| W2 | Authenticated Codex CLI, GPT-6 Astra / high | feat/twilio · 2a6b188 | Twilio clause and plan/evidence evaluators, threshold and calendar tests |
| W3 | Native `onboarding`, GPT-6 Astra / xhigh | feat/onboarding · 22ae8ce | Genuine public extraction, strict manifest, held-out shadow, reviewer gate, rollback, no arbitrary code |
| W4 | Native `disputes`, GPT-6 Astra / xhigh | feat/disputes · a01e9f8 oracle, 1880af3 workflow | Frozen oracle precedes implementations; three denial outcomes plus partial credit, idempotency and retry tests |
| W5 | Authenticated Codex CLI, GPT-6 Astra / medium | feat/evidence · d327dc5 | Fifty minimized real status observations, hash/allowlist validation, freshness and scoped synthetic telemetry |
| W6 | Authenticated Codex CLI, GPT-6 Astra / high | feat/pricing · 98a90cb | Amendment and tier engine, prevention vs retrospective recovery, incomplete real line mapping, cent arithmetic |
| W7 | Authenticated Codex CLI, GPT-6 Astra / medium | feat/dashboard · 15e0cdb | Responsive case ledger, inspector, onboarding views, policies, provenance, contextual guide; seven Node tests |
| W8 | Authenticated Codex CLI, GPT-6 Astra / high; additional native W3 filming after its gate | feat/qa · f83c0ff; film · 6e7056d | Independent HTTP/security tests, real browser walkthrough, screenshots, deterministic backup |
| Supplemental gold | Native W4 after its gate | feat/disputes · f1b9239 | Net-spend rebate, nonmonetary receipt clock and unsupported parity cases |

W3 and W4 were staffed concurrently from CP1. The native harness exposed three worker slots besides the lead; W1 occupied the third. Five additional isolated CLI worktrees supplied W2/W5/W6/W7/W8. CLI version 0.156.1 authenticated. Its catalog listed GPT-6.1 Sol, but the CLI account rejected that model at execution, so those workers were restarted with confirmed GPT-6 Astra. An unrelated executable named `codex` shadowed the CLI in some shell environments; those processes were stopped and the verified OpenAI CLI absolute path was used. Neither the rejected model calls nor the collision are counted as workers. No standing agent or remote service was installed.

Original source, branch ownership and task dependencies are in `docs/uptime-v3/Uptime_V3_Work_DAG.md`. The release is integrated. Remaining externally controlled work is listed in BLOCKERS.md.
