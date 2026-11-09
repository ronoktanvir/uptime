# Release assessment, November 9, 2026

**Verdict: not releasable under the existing gate. The default installation stays read-only.** No signed release attestation or release-trust registry exists. The unseen-vendor and dispute gates cannot be assessed for two reasons: the team has not set a release bar (D13), and no corpus84 first attempt has run. This assessment invents no accuracy threshold. A passing test count is regression evidence, not production readiness.

| | |
|---|---|
| Assessed source | `work/release-evaluation-gent8`. Application core is unchanged from `v4/integration` `03b372e`; probes and receipts are at `c1fa513` and `52bea97`. |
| Bar | The implemented signed release gate ([RELEASE-EVIDENCE](../RELEASE-EVIDENCE.md), `uptime/gates.py`, `scripts/release_evidence.py`) plus ADR-0084's pre-registered interpretation rules. |
| Decision | [ADR-0092](../decisions/ADR-0092-evaluation-release-assessment.md) |

## Gate by gate

| Gate (role) | What the gate requires | Current evidence | Status |
|---|---|---|---|
| `regression` (INDEPENDENT_QA) | A precommitted collection count and hash. One `release_regression.py` run. An independent witness signature within 24 h. | Full `uv run --locked pytest` on this branch: see [Regression](#regression). Unsigned, and no precommitted collection. | **Not satisfied** (unsigned) |
| `security_financial` (INDEPENDENT_QA) | Audit gate before/after against a pinned V3 baseline, and a witness signature. | `v4_audit_gate` release phase: **118/118 PASS** on `c1fa513`, including both browser probes. Fresh V3 baseline `18afaa6`: 73 PASS / 45 FAIL. [release](../evidence/release-evaluation-gent8/audit-release-c1fa513.json) · [baseline](../evidence/release-evaluation-gent8/audit-baseline-v3-18afaa6.json). The committed `docs/v4/audit/baseline-v2.json` no longer passes provenance, because a probe file changed. | **Not satisfied** (unsigned). The evidence is supportive. |
| `unseen_vendor` (INDEPENDENT_QA) | A frozen blind cohort, a first-attempt receipt and an agreed bar. | No corpus84 inference yet; 6/6 inputs validated. Historical results: 0/4 supported onboarding extractions in eval76; blind witness not certified. | **Not assessable:** D13 absent and no first attempt |
| `unanticipated_dispute` (INDEPENDENT_QA) | Same. | 12/12 corpus84 replies blocked at claim intake (D03, D04). Historical results: 0/50 supported replies; eval76 3/6 complete. | **Not assessable:** D13, D03 and D04 absent |
| `human_review` (ACTUAL_HUMAN) | A separately registered person signs the four report digests. | No release-trust registry and no attestation. The CalyxQuay review is not this gate (see below). | **Not satisfied** |
| `native_install` (ACTUAL_NATIVE_OPERATOR, optional) | A signed installation grant for `bill.comment.create`. | The agent-run native posting retest was rejected by automatic approval review ("possible cybersecurity risk"). It is not retried or rerouted. | **Not satisfied**, blocked by execution policy |

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
| corpus84 onboarding (6) | Not run | Not run | Preflight: 0 setup blockers |
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
| Identity propagation, onboarding to claim intake | Offline schema check over all 12 corpus contexts | **Defect reproduced (D03).** Onboarding overlays accept names with spaces; claim `Scope` refuses them. |
| 118-probe audit gate: prompt injection, forged authority, tenant crossing, stale and replayed authority, financial miscalculation, overcounting, browser sibling origin | Mixed (unit, TestClient, browser) | 118/118 PASS (unsigned) |
| Real transport timeout and terminal state | Fake CLI through `SafePublicClaude` | PASS after the runner fix |
| `independent_final_fix_verifier.py` | — | **Exit 1.** Its preserved originals were edited in `5463bcb` after pinning. Integrity finding; not re-pinned. [log](../evidence/release-evaluation-gent8/final-fix-verifier-c1fa513.log) |

The coverage inventory found these remaining gaps:

- No test sends a space-containing identity through onboarding into claim intake over HTTP.
- Allocation conflicts are tested only in-process; the ledger has no HTTP route.
- Stale-authority, tenant-crossing and injection checks have no socket-level coverage.
- Release-attestation forgery is tested only at unit level.

## Regression

PENDING_FULL_SUITE

## What would change this verdict

1. The team records D13: which outcomes satisfy the unseen-vendor and dispute gates.
2. The user explicitly resumes evaluation, and the onboarding sub-cohort runs under [the pre-registered procedure](HARNESS-VALIDATION.md).
3. D03 and D04 are implemented through the normal route, then the dispute sub-cohort runs.
4. Independent witnesses and a registered human reviewer sign fresh reports for one tested commit.

None of these can be produced by code alone.
