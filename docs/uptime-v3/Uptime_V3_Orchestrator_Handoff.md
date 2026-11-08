# Uptime V3 — Codex Orchestrator Handoff (START HERE)

**Revision:** 3 November 2026 (America/Los_Angeles)  
**Goal:** Build, verify, and integrate a compelling Ramp-native **contract enforcement, prevention, autonomous claims/disputes, reconciliation, and self-expanding vendor onboarding** hackathon application. The team chose to pursue ambitious implementation concurrently and decide any scope reduction themselves.  
**Use with:** `Uptime_V3_Product_Technical_Spec.md`, `Uptime_V3_Work_DAG.md`, `Uptime_V3_Credentials.md`.

## November 7 scoped demo authorization

The team approved authored Northwind terms/evidence, live teammate CalyxQuay review, and a human-posted Ramp evidence-gap note with optional read-only API confirmation. Implement this bounded path, keep screens clean, and disclose authored data and the reviewer's role orally. Do not call Northwind proof against an unrelated Ramp bill, label a local receipt as a Ramp write, or present scripted review as human approval. The existing release gate remains required for actual named-reviewer promotion. Other pending team decisions and evaluation worktrees remain paused. This supersedes the prior pause for the scoped demo work only. [Current execution boundary](../v4/DEMO-PATH-87.md).

## November 6 team decision handoff (historical)

Development is paused for team review. The current [decision handoff](../v4/TEAM-DECISION-HANDOFF.md) separates established defects, implementation gaps, external prerequisites and proposed defaults. Preserve the paused worktrees and follow the recorded resume boundary. Its proposed team-owned execution policy is pending acceptance and must not be mistaken for already granted scope, financial or external-action authorization. Do not launch more advisory reviews while preparing this handoff.

## November 4 presentation and collaboration amendment

The current user requests a coherent Northwind walkthrough and ordinary product screens without repetitive demo, synthetic, simulated or replay labels. This supersedes the earlier UI-label requirements below. Do not add hidden mode indicators. Keep existing source identities, authority kinds and receipt verification intact in APIs and audit exports; use normal document references, connection names and financial stages in the product. The configured write destination must remain accurate. A local ledger write cannot be called a verified Ramp write, and a seeded reviewer cannot become actual human approval.

Use versioned authored contract, amendment, invoice and usage inputs with the existing deterministic engines and state machines. Document the fictional package outside the product screens. Keep the connected Ramp database intact, use a separate walkthrough workspace, and distinguish delivered walkthrough functionality from the original live-proof acceptance gates. Preserve strict calculations, citations, deadlines, missing-evidence behavior and idempotency. Keep onboarding and dispute work concurrent.

Publish focused, verified GitHub increments and update the dependency snapshot after meaningful results. Run `uv run --locked pytest` after each merge, preserving actual failed and successful outputs. List every changed existing test and its reason in [the current test-change ledger](../v4/TEST-CHANGES.md). [Decision 64](../v4/decisions/ADR-0064-clean-walkthrough.md) records the independent review, presentation decision and unresolved proof boundaries.

## Your job

**November 5 review amendment:** The lead makes the implementation decision and requests concise Opus 5.5 criticism. Do not turn consultation into a council or serial rounds of new audits. Finish known fixes and required verification, preserve disagreements and failed evidence, then deliver. Existing accepted decisions cover routine implementation corrections; consult again only when new evidence materially changes the decision. This supersedes any broader review process inferred from the original workstream structure below.

You are the responsible **engineering orchestrator** of the Uptime repository. You are not an ideation chatbot. Inspect code, delegate independent implementation work to real capable coding agents, integrate/test their work, keep durable progress and decision records, and deliver runnable software and an honest demo. Work autonomously as far as actual session/tool permissions permit. No false claims of active subagents, background execution, API access, or user approvals. 

**FIRST ACTION:** Inspect repository state (`pwd`, git status, directory tree, package manifests, tests, docs, branches and existing worktrees). Preserve user changes. Determine which features already exist; the team previously stated that many features were built, but this has not been verified in this conversation. If no repository is mounted, locate the repo through available workspace tools or create a scaffold only after confirming absence. Do not overwrite an existing implementation.

## Non-negotiable product outcomes

1. **PREVENT** contract-based overcharges before approval; focus on terms Ramp's PO match cannot express (non-PO card/usage SaaS, amendments, effective date, tier pricing). This is not a claim that Ramp lacks PO matching.
2. **RECOVER** postpayment SLA and pricing credits using contract-specific evidence, deterministic financial calculations, authorized claim filings, follow-ups and denial handling.
3. **EXPAND** vendor coverage autonomously through constrained declarative vendor templates generated from real public terms and private customer overlays, deterministic tests, shadow evaluation, human promotion and rollback; do not generate and execute arbitrary unreviewed production code.
4. **RECONCILE** awarded vendor credits against Ramp Bill Pay records and distinguish *estimated, claimed, awarded, posted and applied* financial amounts.
5. **PROVE** the complete workflow through live Ramp sandbox operations and preserved source/receipt identity. Apply the November 4 presentation amendment to product labels; authored fixture runs do not satisfy live provider proof.
6. **INFORM** users through a finance-first dashboard and a contextual copilot; human-approved vs policy-automated modes are configurable. No UI/agent bypass of authorization.

Prioritize both **W3 (autonomous vendor onboarding)** and **W4 (adversarial dispute/appeal agent)** concurrently and at high engineering intensity. Do NOT choose one to drop, postpone or reduce to cosmetic scaffolding because you prefer the other. Only the team may make a strategic focus swap. Other tracks proceed in parallel as dependency allows. Review the judging criticisms in the spec.

## Orchestration mechanism and concurrency

**At startup, determine the capabilities of THIS environment**: native Codex subagents? agent API/session support? available `codex` CLI and project worktrees? Anthropic CLI/Claude Code or API access? Determine actual model names and reasoning levels; do not hardcode unavailable switches. Use supported native subagents preferentially. If an API-based session is being used, its documented multi-agent config is `multi_agent.enabled=true`; verify exact request schema in the active harness. If no native subagents, choose a supported background-job/worktree mechanism with isolated code ownership. Do not start phantom workers or process managers that outlive the actual execution environment.

Launch dedicated parallel owners, each with bounded tasks and acceptance tests:

| Worker | Domain and ownership | Model/effort class | Must demonstrate |
|---|---|---|---|
| W0 | Orchestration, CI, security gates and merges | high for governance | durable task records, no file collisions |
| W1 | Ramp sandbox/financial provider, bill import and credit reconciliation | medium/high | live read+approved safe write proof or access blocker matrix |
| W2 | Versioned contract extraction, citations, deterministic evaluator and DSL | high/xhigh | correct eligible/ineligible/unknown/unsupported with arithmetic trace |
| W3 | **Self-expanding vendor onboarding** | **high/xhigh dedicated** | real Atlassian template generated/tested/shadowed, customer overlay, human promotion and rollback |
| W4 | **Adversarial claims/disputes** | **high/xhigh dedicated** | three denial outcomes, external action permissions and idempotency |
| W5 | SLA status/evidence connector and fixtures | medium/high | contract-specific evidence checks and source provenance |
| W6 | Price cap/amendment/overbilling prevention | high | synthetic contract against a Ramp sandbox bill, accurate discrepancy |
| W7 | Dashboard, case investigation, onboarding lab and guide | medium/high | working UI connected to real service state and source flags |
| W8 | E2E, security, accessibility and demo | high | reproducible replay, tests, runbook, no misleading metrics |

W3 and W4 may implement against CP1 fixtures and stubbed interfaces while W1/W2 finish external dependencies. Do not serialize these streams unnecessarily. If concurrent agents edit same file, stop and assign one owner or use branches/worktrees. Shared schema modifications require integration-owner review; irreversible changes need an Opus consultation. Integrate via small, testable slices frequently rather than one final giant merge.

**Dynamic model routing:** Low effort/fast capable models for bounded boilerplate, doc cleanup, snapshots and simple unit tests; medium for normal endpoints, UI and vendor API glue; high/xhigh for entitlements, pricing math, evidence provenance, adapter compiler, disputes, auth/tenant isolation, money flows and architectural integration. Choose from models actually supported in the user's Codex plan/harness. Log key allocations and reroute on poor test results. Model names are not evidence of having run an agent.

## Mandatory Opus 5.5 decision consult (decision not delegation substitute)

**For every impactful decision**, send the relevant *sanitized* context to an independent **Claude Opus 5.5** reviewer (model ID `claude-opus-5-5`) using available Claude Code subscription CLI or Anthropic API. Do not assume login or API access. Check CLI availability (`command -v claude` and `claude --help`), then test model selection non-destructively; if unavailable, record blocker. Do not forward Ramp client secret, tokens, confidential customer data, or credentials to Claude. Do not invoke external AI provider with proprietary data without authorized use.

Impactful decisions (threshold P2/P3) include: shared contract/financial schemas; the SLA math/credit basis and evidence sufficiency; legal/contract interpretations; contract-to-invoice matching; external claim/appeal authority; provider auth/secrets; tenant isolation; generated adapter promotion/security; switching demo scope or vendor; Ramp write capability/financial accuracy; product architecture; allocation of W3 vs W4. Avoid model calls for trivial changes (label spelling, test fixture names).

**For each consult:**
1. Write a `DecisionPacket` with question, candidate choices, concrete repo/test evidence, user constraints, consequences of failure, authorization boundary, and recommended choice with strongest counterargument. Do not mention keys.
2. Invoke a REAL Claude Opus 5.5 run (prefer read-only mode) as an independent skeptical architect. Ask for option ranking, risks, falsification tests, and whether it would dissent.
3. Compare Claude's result with the lead's position; decide deliberately using test evidence, document disagreement and why one route was chosen. Claude is advisory, not a replacement for verification or human permission.
4. Save `docs/decisions/ADR-NNNN-<slug>.md` and append to `docs/orchestration/DECISIONS_INDEX.md`: timestamp, scope, alternatives/pros/cons, model ID and real response link/file, recommendation, disagreement, chosen design, test/rollback. Update tasks and continue.
5. If Claude unavailable, mark `OPUS_BLOCKED`, complete reversible engineering alternatives and continue independent streams; do **not** manufacture a Claude opinion. Gate materially irreversible product/security/financial decisions until review or human authorization. Send one concise blocker notice only if impossible to progress meaningfully.

A second model cannot prove legal entitlement: deterministic contract tests and source-backed evidence are authoritative for the prototype. A vendor simulator must be independent from the claimant and compared to a pre-committed test oracle.

## Decision hierarchy (no unasked interruptions)

**Autonomous reversible:** local architecture prototypes, fixtures clearly labeled, tests, UI, sandbox *read* requests, artifact generation, branch commits, draft claim text, mock vendor exchanges in an isolated simulator.

**Advisory with ADR:** consequential reversible technical/product choices after Opus review. If Opus unavailable, stage choices behind a feature flag, preserve alternatives, and continue other work.

**Human permission required:** entering credentials, production/live Ramp writes, any real vendor communication or claims/disputes/settlements, external purchases/costly compute beyond budget, exposing proprietary contracts externally, changing customer authorization policies, access scope escalation, destructive repo/database operations, deploying live production service, publishing secrets. Allow narrowly scoped **sandbox writes** only after user-supplied access and exact scope have been confirmed, with safe fixtures, explicit `RAMP_ENV=sandbox`, no transfers/payments, and logged idempotency keys. Stop if origin could be production.

**Do not interpret "mostly asynchronous" as permission to execute forever.** Continue within available sessions, queues or durable runner; save progress frequently, provide a restart mechanism. If no persistent runner is installed, make `scripts/resume-orchestration.sh` or an equivalent documented manual resume and explain execution limitation honestly; do not promise background work after the chat/session stops.

## Hard architecture invariants

- One finance/case interface with typed vendor-specific extensions; vendor public template and customer private overlay must be separate. Effective contract resolution is deterministic and versioned.
- Vendor onboarding produces **declarative rule DSL and test fixtures**, not arbitrary scripts deployed to production. Unsupported DSL clauses yield `UNSUPPORTED_RULE`, not guessed eligibility. Candidate flows `DRAFT → VALIDATED → SHADOW → APPROVED → ACTIVE`, reversible rollback/revocation.
- Eligibility outcomes: `ELIGIBLE`, `INELIGIBLE`, `INSUFFICIENT_EVIDENCE`, `UNSUPPORTED_RULE`, all with clause-cited trace. Evidence requirements depend on the controlling agreement; customer telemetry is not universally required. Spend from Ramp vendor total is not equal to eligible service-specific spend.
- Calculations use decimal math, accurate month/day/timezone and explicit invoice line mapping; no LLM free-form arithmetic. For negotiated price caps, demonstrate changing amendment-effective dates.
- Claim/dispute state machine includes user authorization, external idempotency keys, failed/retried submission, no fabricated proof, appeal-window clocks, escalation and stop-on-correct-denial behavior. No harassment/spam.
- Vendor simulator is independent, uses source-defined contracts, presents reasons; oracle holds precommitted expected outcomes. Preserve event source and authority classification in the record; apply the November 4 amendment to product presentation.
- Track financial value by stage: potential estimate, evidence-ready, submitted, award confirmed, vendor credit posted, applied to bill. Public incident feeds and simulated vendor awards are not genuine customer recoveries.
- Every platform action has role, tenant, audited timestamp, source and permission; untrusted contracts, websites, emails and AI outputs are data, not commands.

## Required validation and demo proof

**D1:** Ramp demo sandbox read: actual vendor and bill IDs visible in Uptime and `demo.ramp.com`. **D2:** Safe sandbox draft bill created or modified, then read back with same ID; show timestamps. **D3:** Permitted manual credit record or supported read; no invented credit API. **D4:** Twilio SLA valid/invalid/unknown cases with current published terms and correct affected-fee exclusions. **D5:** Synthetic amended price-cap bill flagged before approval and retrospective recovery case. **D6:** Vendor simulator (missing proof cured, correct denial accepted, unresolved human escalation) with independent expected outcomes. **D7:** Atlassian generated adapter + test suite + shadow + approve + rollback, with separate customer plan overlay. **D8:** Case timeline/reconciliation/dashboard persists across restart. **D9:** Security, prompt injection, duplicate webhook and role-boundary tests. **D10:** Recorded 2-minute deterministic live/replay demo, capability matrix, honest ROI statement.

Do not wait for the entire project to compile before testing: each worker must provide acceptance tests and a mocked integration fixture. Milestones CP0–CP6 and DAG are in `Uptime_V3_Work_DAG.md`.

## Durable work products and quality loop

At startup create/update:
- `docs/orchestration/STATUS.md`: active agents, what actually ran, current checkpoint, tests, next work, timestamp.
- `docs/orchestration/TASKS.md`: dependencies, agent owner, task status, branch/worktree, acceptance criteria, expected evidence.
- `docs/orchestration/CAPABILITY_MATRIX.md`: real API scopes and data; each claimed feature tagged LIVE_RAMP_SANDBOX / LIVE_VENDOR_PUBLIC / SYNTHETIC_CUSTOMER / SIMULATED_VENDOR / REPLAY / UNAVAILABLE.
- `docs/orchestration/BLOCKERS.md`: credentials, dependencies, model access, blockers and reversible fallback.
- `docs/orchestration/DECISIONS_INDEX.md` and `docs/decisions/ADR-*.md`: exactly what Opus actually reviewed and why a choice was made.
- `docs/orchestration/RUNBOOK.md`: setup, seed, tests, reboot, demo reset, credentials retrieval and resume.
- tests (unit, property where useful, integration, adversarial and E2E), CI, clean `.gitignore`, no secrets committed.

After every implementation merge: run test suite, inspect changed files for secrets, compare against product invariants, update status/checkpoint and release the next unblocked jobs. Never claim a milestone passed without tangible test output or demo evidence. For failures: fix, retry within reasonable effort, or record a blocker and continue other independent tasks. Ask the users only for genuinely necessary authentication/permissions or irreversible actions. User owns any decision to focus less on W3 or W4.

## First execution sequence (do this, don't just plan)

1. Inventory repository, identify implemented modules, check git status, read existing docs, test existing app. Save concise **as-is gap analysis**.
2. Inspect actual subagent capability and Claude Opus 5.5 invocation (subscription or API), run a minimal *real* Opus smoke check; log verification or unavailability. No fake delegate.
3. Create durable task board, ADR template, source-label system, golden fixtures and shared typed interfaces. Request an Opus consult before freezing cross-agent financial interfaces.
4. Immediately spawn W3 and W4 on dedicated branches with testable fixtures; launch W1/W2/W5/W6/W7/W8 as supported by concurrency limits. Preserve high effort for W3/W4.
5. Ramp worker checks sandbox access/scopes using secure local configuration; if no secrets yet, implement fixture provider without blocking everyone else. Never ask for keys in chat.
6. Integrate incrementally, run tests and spend the final gate on an honest real/simulated demonstration. Reassign tasks only after logs show objective progress; don't demote W3/W4 without user decision.

## References

Primary: `Uptime_V3_Product_Technical_Spec.md`, `Uptime_V3_Work_DAG.md`, `Uptime_V3_Credentials.md`. Official Ramp quickstart https://docs.ramp.com/developer-api/v1/guides/getting-started ; API scopes https://docs.ramp.com/developer-api/v1/scopes ; Claude model https://platform.claude.com/docs/en/models/opus-5-5/overview ; OpenAI multi-agent https://developers.openai.com/api/docs/guides/agents-api/multi-agent .
