# Release assessment, November 9, 2026

**Verdict: not releasable under the existing gate. The default installation stays read-only.** No signed release attestation or release-trust registry exists.

Ronok's D13 bar is reported as decided but was not yet recorded when this was written. Under it, neither coverage gate is met:
- **New vendor:** the corpus84 onboarding first attempts had **no ordinary application-path success** (0/4 supported extractions accepted), and correct refusal of the two controls is unproven. Under D05, a cohort that supplies the contract family could not prove autonomous family selection in any case.
- **New dispute:** no first attempt has run. All 12 replies remain blocked at claim intake by D04 scope.

D13 sets no numeric threshold, and none is added here. A passing test count is regression evidence, not production readiness.

| | |
|---|---|
| Assessed source | `work/release-evaluation-gent8`. Application core is unchanged from `v4/integration` `03b372e`; probes and receipts are at `c1fa513` and `52bea97`. |
| Bar | The implemented signed release gate ([RELEASE-EVIDENCE](../RELEASE-EVIDENCE.md), `uptime/gates.py`, `scripts/release_evidence.py`) plus ADR-0084's pre-registered interpretation rules. For the two coverage gates: D13 "Bar without native proof", as reported (see [team decisions](#team-decisions-november-9)). |
| Decision | [ADR-0092](../decisions/ADR-0092-evaluation-release-assessment.md) |

## Gate by gate

| Gate (role) | What the gate requires | Current evidence | Status |
|---|---|---|---|
| `regression` (INDEPENDENT_QA) | A precommitted collection count and hash. One `release_regression.py` run. An independent witness signature within 24 h. | Full `uv run --locked pytest` on this branch: see [Regression](#regression). Unsigned, and no precommitted collection. | **Not satisfied** (unsigned) |
| `security_financial` (INDEPENDENT_QA) | Audit gate before/after against a pinned V3 baseline, and a witness signature. | `v4_audit_gate` release phase: **118/118 PASS** on `c1fa513`, including both browser probes. Fresh V3 baseline `18afaa6`: 73 PASS / 45 FAIL. [release](../evidence/release-evaluation-gent8/audit-release-c1fa513.json) · [baseline](../evidence/release-evaluation-gent8/audit-baseline-v3-18afaa6.json). The committed `docs/v4/audit/baseline-v2.json` no longer passes provenance, because a probe file changed. | **Not satisfied** (unsigned). The evidence is supportive. |
| `unseen_vendor` (INDEPENDENT_QA) | D13 conditions: ordinary app-path success on independently authored supported cases; separate correct-refusal controls; zero unsafe financial/action acceptances; first-attempt receipts; parser, model, review and authority outcomes reported separately. D05 adds automatic family selection and human approval on an independently selected unseen vendor. | corpus84 onboarding first attempts on `89fe25c` ([receipt](../evidence/release-evaluation-gent8/onboarding84-first-attempts.json)): 6 genuine `claude-opus-5-5` calls.<br>• App-path success: **0/4**.<br>• Correct refusal: **unproven** (0/2 shown).<br>• Unsafe acceptances: **0** (met).<br>• First-attempt receipts: present (met).<br>• Separate outcome reporting: met.<br>• D05 selection and approval proof: not attempted (the family was supplied).<br>Historical: 0/4 in eval76. | **Not satisfied.** No supported case succeeded on the app path; D05 proof is absent. |
| `unanticipated_dispute` (INDEPENDENT_QA) | The same D13 conditions. | No first attempt. Two setup blockers apply to all 12 replies. **(1)** Claim intake: D03-A is now implemented, D04-C is not. **(2)** Claim basis: claims resolve terms only through an active adapter, and both claim-basis contracts (monthly_tier for 11 replies, resource_month for 1) are QUARANTINED on the deterministic route ("Source or overlay validation failed"); their model proposals were also refused ([receipt](../evidence/release-evaluation-gent8/preflight-evaluation84-claim-basis.json)). Historical: 0/50 supported replies; eval76 3/6 complete. | **Not satisfied.** There are no first-attempt receipts. |
| `human_review` (ACTUAL_HUMAN) | A separately registered person signs the four report digests. | No release-trust registry and no attestation. The CalyxQuay review is not this gate (see below). | **Not satisfied** |
| `native_install` (ACTUAL_NATIVE_OPERATOR, optional) | A signed installation grant for `bill.comment.create`. Under D13, a native Ramp proof is an external dependency, not a coverage-gate condition. | The agent-run native posting retest was rejected by automatic approval review ("possible cybersecurity risk"). It is not retried or rerouted. | **Not satisfied**, blocked by execution policy. This does not block the coverage gates. |

Any run made today would also be stale for release after 24 hours. The gate requires fresh signatures over the tested source.

## Evidence classes, kept separate

| Class | What exists | What it does not establish |
|---|---|---|
| **Controlled-provider tests** | Onboarding runner with recording doubles (41 tests). Real `SafePublicClaude` with a fake CLI (answering, and hanging past 60 s). Dispute-runner infrastructure (20 tests). | Model quality or real-provider latency. |
| **Genuine model calls** | eval76: 18 calls, all `claude-opus-5-5`. Earlier Opus coding delegations and decision critiques. This lane: one ADR-0092 critique, session `6d98fd01-1326-48cb-9508-f5949a066746`. | **Zero corpus84 calls.** A critique is advice, not verification. |
| **Browser and socket observations** | Audit-gate browser probes PASS (system Chrome, loopback). Hard-kill restart probe: two OS processes over loopback, 11 authored Northwind actions. Earlier browser proofs listed in [DEMO-PATH-87](../DEMO-PATH-87.md). | Hosted operation. All of this is localhost. |
| **Actual Ramp receipts** | Read-only API reads of demo business `1569e402-…` and bill `f74ba12c-…` (USD 840.00). Observed `bills:write` grant. A person-posted comment `376563cf-950c-409d-b3d8-a68599c45fa0`, verified by read-back at 2026-11-08T01:46:45Z. | Any Uptime-origin Ramp write, payment hold, vendor award, Ramp vendor credit or applied Ramp credit. |
| **Local ledger** | Authored Northwind: $2,400 credit reduces the $11,000 April invoice to $8,600. The separate $1,000 March price finding remains open. | Money recovered in Ramp, or a real customer's contract. |
| **Reviewer authority** | CalyxQuay events 1–5 are by `scripted-test-reviewer` (2026-11-08T01:50:33Z). Events 6–9 are recorded under account `ronok-tanvir` as `authenticated_reviewer` (2026-11-09T10:07:28Z–10:08:51Z): interpret, approve, activate, then roll back. The final state is **REVOKED at revision 9**. Integration owner's receipt: `docs/v4/evidence/local-review-88/recorded-review-20261109.json` on `work/integration-90`. | Actions recorded under an authenticated local account under a 48-hour local exception. Not `ACTUAL_HUMAN` release witnessing, independent certification, or customer contract approval. Scripted events are not Ronok's actions. |

## Results by stage

ADR-0084 rules apply: no pooled percentage. Supported-case success, correct negatives and technical refusals are counted separately.

| Cohort | Useful supported-case success | Correct negative / review outcome | Technical or setup refusal |
|---|---|---|---|
| Independent replies (historical, preserved) | **0/50** supported replies recognized | 50/50 mandatory-review cases refused | Not separable in the original receipt |
| eval76 onboarding (historical) | **0/4** supported extractions accepted | 2/2 refusal controls produced no money, but refused at coverage validation, so correct recognition is unproved | 0 transport failures |
| eval76 replies (historical) | **3/6** complete supported meanings (4/6 by reason family) | 6/6 review controls UNKNOWN; 0 false supported mappings | 0 transport failures |
| corpus84 onboarding (6), first attempts November 9 | **0/4** supported extractions accepted (all 6 responses were bare strict JSON; eval76 had 0/6) | 2/2 refusal controls produced no candidate or money, but were refused by an early validation rule; correct recognition is **unproved** | 0 transport failures, 0 setup failures; all 6 refused at post-model deterministic proposal validation |
| corpus84 disputes (12) | Not run | Not run | Preflight: **12/12 blocked at claim `Scope`**, by D03 and D04 |

| Stage | Known failures and gaps |
|---|---|
| Setup | All 12 corpus84 replies: the identity domain (D03) and universally required scope (D04). Two actual HTTP 422 receipts are preserved. |
| Extraction | eval76: 0/6 strict JSON (fenced), 0/4 supported accepted after fence normalization. Validator refusals: ungrounded identifier, dropped/invented source, unsupported clause, fixed-period month. |
| Interpretation | eval76: compound denials (03, 04) are refused by the single-proposition mapper, and one artifact category is omitted (02). Finite meanings remain a residual risk. |
| Validation | Draft-path shadow preview cannot reach governing-fee authority, so 2 of 4 supported corpus84 contracts cannot show money on this path. |
| Authorization | Native posting rejected by execution-policy review. No release witness. Human promotion exists only under the expired, revoked local exception. |
| Delivery | No real vendor channel (D08). Local outbox idempotency holds: duplicate actions were unchanged across a SIGKILL. |
| Reconciliation | No Ramp vendor credit or application observed (D09). Local ledger stages are separate and unsummed. |

## Cross-component and security probes run in this lane

| Probe | Transport | Result |
|---|---|---|
| Hard-kill restart mid-flow, with duplicate replay across the kill ([receipt](../evidence/release-evaluation-gent8/restart-probe-c1fa513.json)) | Two OS processes over loopback | PASS. State equal after restart, replay unchanged, 11/11 actions, $8,600 outstanding. |
| Identity propagation, onboarding to claim intake | Offline schema check over all 12 corpus contexts, plus signed TestClient across both routes | **Defect reproduced (D03).** The vendor route evaluates a spaced identity as ELIGIBLE 52.17 in shadow. Claim intake refuses the same identity with 422 on `account` and `contract` only. A provisioned identifier-domain control is accepted. |
| Socket authority attacks ([receipt](../evidence/release-evaluation-gent8/socket-authority-probe.json)) | Separate OS server process over loopback | PASS. 7/7 refused with HTTP 403, and the authoritative workflow and ledger were unchanged after each: body tampered after signing, proof rebound to another path, cross-origin header, missing action header, bearer session without proof, forged-key login, exact replay of an accepted request. A fresh legitimate signed action was accepted (200). |
| Tenant crossing between two installations (`test_socket_tenant_crossing_is_refused_between_two_installations`) | Two loopback listeners (one process), separate tenants and databases | PASS. A carried session token and the other tenant's subject or key are refused (401/403); each listener reports only its own workspace. |
| Source change after approval (`test_socket_source_change_after_approval_blocks_submission`) | Real loopback listener, signed routes | PASS on the gate: after a revised source becomes active, the claim reads UNSUPPORTED_RULE and submission is refused with 409; no submission is created. **Observation:** the read view still shows the earlier approval record. It is not usable, but it is displayed; a UI or explanation owner may want to label it stale. |
| Injected vendor reply, duplicate delivery, signed replay (`test_socket_injected_reply_duplicate_delivery_and_replay_create_no_money`) | Real loopback listener, signed vendor source | PASS. A reply demanding a USD 999,999 award and immediate posting creates no award, submission or action. An exact replay of the signed delivery is refused; a re-signed redelivery of the same event leaves state identical. |
| 118-probe audit gate: prompt injection, forged authority, tenant crossing, stale and replayed authority, financial miscalculation, overcounting, browser sibling origin | Mixed (unit, TestClient, browser) | 118/118 PASS (unsigned) |
| Real transport timeout and terminal state | Fake CLI through `SafePublicClaude` | PASS after the runner fix |
| `independent_final_fix_verifier.py` | — | **Exit 1.** Its preserved originals were edited in `5463bcb` after pinning. Integrity finding; not re-pinned. [log](../evidence/release-evaluation-gent8/final-fix-verifier-c1fa513.log) |

The coverage inventory found these remaining gaps:

- Space-containing identities: the HTTP-level gap is now covered by the D03 reproduction test. It stays TestClient-level, not socket-level.
- Allocation conflicts are tested only in-process; the ledger has no HTTP route.
- Signed-request authority now has socket-level coverage (proof replay, body/path rebinding, forged key, origin, CSRF header). Tenant crossing now has listener-level coverage. Stale authority after a source change, reply injection and duplicate delivery now have listener-level coverage. Allocation conflicts stay in-process only: the ledger has no HTTP route.
- Release-attestation forgery is tested only at unit level.

## Regression

`uv run --locked pytest` on `487a32f` (clean tree; same commit before and after): **4,035 passed, 1 warning in 791.25 s, exit 0**. It ran 11:30:49Z–11:44:05Z, alone in the shared full-suite slot. The warning is a Starlette TestClient deprecation.

The 4,035 tests are the 3,967-test integration baseline plus the 68 tests new on this branch (41 onboarding runner, 20 dispute infrastructure, 5 preflight, 2 probes). No existing test was changed. [receipt](../evidence/release-evaluation-gent8/verification-487a32f.json) · [log](../evidence/release-evaluation-gent8/full-suite-487a32f.log)

This is unsigned regression evidence. The `regression` gate additionally requires a precommitted collection hash, one `release_regression.py` run and an independent witness signature. A green suite does not establish production readiness, unseen-source accuracy or Ramp behavior.

## Team decisions, November 9

All of these are Ronok's choices from his overview session, relayed by the overview session. They were recorded by the integration owner as follows. D05, D06, D07 and D11: `work/integration-90` `93d896a`. D03-A: `work/integration-90`, implemented on `work/identity-pricing-89`, commit `6ebaffe`. **D10, D13 and D14: reported decided, but still "Pending" in the committed decision sheet when this was written.**

| Decision | Choice | Effect on this assessment |
|---|---|---|
| D13 | **Bar without native proof.** The unseen-vendor and new-dispute gates require: ordinary app-path success on independently authored supported cases; separate correct-refusal controls; zero unsafe financial or action acceptances; first-attempt receipts; parser, model, review and authority outcomes reported separately. A native Ramp proof is an external dependency, not a gate condition. **No numeric threshold.** | Applied in the gate table. No threshold is added. Onboarding fails the success condition (0/4) and the correct-refusal condition (unproven). It meets the safety, receipt and reporting conditions. Disputes have no receipts. |
| D05 | Auto-select among supported families, with human approval before activation, proven on an independently selected unseen vendor | corpus84 supplied each contract's family, so it could not prove autonomous selection even with successful extractions. That proof still needs a separate, independently selected vendor. |
| D06 | Humans gate judgment | Review controls stay human-gated; a model's UNKNOWN or refusal on a judgment case is not expected to become an action. |
| D07 | Narrow published matrix: one currency, calendar months, everything else unsupported, one real evidence source, no PDF | The corpus84 contracts are USD calendar-month cases, inside the matrix. W5's public status source was merged as the first real evidence source on `work/integration-90` (`6a5136c`); this lane has not independently verified it. |
| D10 | Public-only data, Claude as provider, bounded budgets, no retries on uncertain outcomes | The corpus84 run complied: authored public text only, `claude-opus-5-5`, a $1.00 cap per call (about $0.39 in total), and no retry. |
| D11 | Stay local | Loopback-only installation; hosted OAuth, webhooks and deployment are out of scope. |
| D14 | Mandatory Opus critique no longer required | ADR-0092's single critique stands as recorded; none is needed for further routine work. |

## What would change this verdict

1. **New-vendor gate:** independently authored supported cases succeed through the ordinary app path, with separately demonstrated correct refusals. Per D05, that includes automatic family selection and human approval on an independently selected unseen vendor. The examined corpus84 contracts cannot be re-scored: a repair to the refusing validation rules is a named remediation, and measuring it needs a new independent cohort.
2. **New-dispute gate:** D04-C is implemented through the normal route, **and** the claim-basis contracts can be activated through an ordinary path. That needs either a remediation of the refusing onboarding validators, with the onboarding first-attempt score kept at 0/4, or a protocol decision (asked of the team on November 9). The preflight then shows which replies are admissible without invented scope, and the dispute first attempts run once each against the D13 conditions.
3. **Signed gates:** independent witnesses and a registered human reviewer sign fresh reports for one tested commit (regression, security/financial and human review).

None of these can be produced by code alone.
