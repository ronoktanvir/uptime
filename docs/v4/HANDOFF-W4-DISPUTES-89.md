# W4 disputes handoff (workstream 89, agent3)

November 9, 2026. All W4 code is merged into `work/integration-90`. One item is blocked only on a Ronok decision: the evaluation86 run (section 6). It has its own frozen runner branch, which is deliberately not merged.

## 1. Commits

| Increment | Branch @ commit | Integrated as | What |
|---|---|---|---|
| Frozen authored controls | `work/dispute-disposition-89` @ `4e50dbc` | `b5cd49e` | 12 novel vendor replies plus 2 counterparty loops, committed before any code |
| 89: reviewed denial acceptance + trace | `3454b33`, `8083ab5`, `16116ee` | `b5cd49e` | Explicit `accept-denial`, `DENIAL_REVIEW`, stale-rebuttal fix, `GET /trace`, counterparty decision/wording split, Opus critique fixes, ADR-0089 |
| 89b: one intake boundary on every channel | `work/dispute-intake-scope-89b` @ `a794d55`, `99a603c` | `39ee3f0` | W5 F1/F2/F8: out-of-scope evidence refused before storage, identity contradictions hold actions, status-origin label |
| 89c: exact source identity, legacy route | `work/dispute-wire-identity-89c` @ `0af939d`, `f29b260` | `1f2b8b4` | D03-A for legacy account, vendor and service names |
| 89d: narrow month-coverage rule | `work/dispute-coverage-89d` @ `a350019` | `ada6c78` | D07 / F3 option A |
| 89e: explicit closure for every denial | `work/dispute-explicit-closure-89e` @ `53e29ee` | `4f918a1` (with 89f) | D06: familiar-wording denials also wait for `accept-denial`; `oracle-v2-d06.json` |
| 89f: closure-bound mandate | `work/dispute-closure-mandate-89f` @ `7579fdd` | `4f918a1` | Ronok's 2a wired through `check_closure_decision` |
| 89g: ADR addenda | `work/dispute-docs-89g` @ `52f64e9` | `1a36ecd` | Decision attribution for 89c–89f |
| 89h: item 8 via signed routes | `work/dispute-adversarial-89h` @ `a659e15` | `a99365e` | 14 adversarial tests over HTTP |
| 89i: round-4 fix | `work/dispute-blind-acceptance-89i` @ `f3bb0cc` | `9b2097c` | Late-denial control performs the explicit acceptance |
| Evaluation86 runner (frozen, **not merged**) | `work/dispute-evaluation-86-run` @ `e1b6657` (freeze record `ea920e9`) | — | Offline plan, stated-scope intake, dispatch drain, accept-denial rule A; no case run |
| This handoff | `work/dispute-handoff-89j` | — | Docs only |

## 2. Files changed (W4 lane)

- **Code:** `uptime/correspondence.py`, `uptime/correspondence_review.py`, `uptime/correspondence_vendor.py`, `uptime/correspondence_api.py` (router), `uptime/correspondence_rules.py` (89d), new `uptime/correspondence_disposition.py`, and `uptime/disputes_wire.py`, `disputes_claimant.py`, `disputes_vendor.py` (89c).
- **Script fix:** `scripts/blind_acceptance.py` (89i).
- **Fixtures:** `fixtures/correspondence/novel-89/` (frozen) and `fixtures/correspondence/oracle-v2-d06.json`. `oracle.json` is untouched.
- **New tests:** `test_correspondence_disposition_89.py`, `test_correspondence_intake_scope_89b.py`, `test_disputes_identity_89c.py`, `test_correspondence_month_coverage_89d.py`, `test_correspondence_adversarial_http_89h.py`. Changed existing tests are listed by name in the ledgers below.
- **Docs:**
  - `docs/v4/decisions/ADR-0089-reviewed-denial-acceptance.md`, with addenda 89b and 89c–89f
  - packet `decisions/packets/89-…`
  - Opus receipt `decisions/reviews/89-…-critique.json`
  - ledgers `TEST-CHANGES-89-disputes.md`, `-89c`, `-89d`, `-89e`, `-89f`, `-89h`
  - receipts `evidence/dispute-*-89*/verification.json`
- **Not touched:** W0 shared schemas (`correspondence_types.py` Scope, `claim_identity.py`, `mandates.py`, `auth*`, `server.py`, `v4_routes.py`), `web/` and shared status records. All of these went through owner requests.

## 3. Behavior implemented

- **Three outcomes for unfamiliar vendor wording.** A justified cure drafts one supplement that keeps the original filing time and window. A correct contractual denial reaches `DENIAL_REVIEW` in either message order and closes only through explicit `accept-denial`. Ambiguous, legal, compound, changed-scope and injected text escalates to a person.
- **No automatic closure.** Under D06 no denial closes a claim by itself, including familiar wording. Acceptance needs the exact `basis_digest` the reviewer was offered (`POST /denial-acceptance`). The basis is re-derived inside the write transaction. Under a mandate it also needs the zero-amount `ClosureDecision` bound to basis and claim state. Money, awards and submissions never change.
- **Reopening.** An accepted denial reopens for a person when its own ground fails or a conflicting reply arrives. The acceptance is kept as history.
- **Stale drafts.** A drafted rebuttal or cure returns to `HUMAN_REVIEW` when later evidence removes its basis.
- **Read-only trace (`GET /trace`).** It shows evidence; each reply with its exact text, interpretation origin, source span, ground and category (8 categories); governing clauses and filing times; deterministic checks (including `month_coverage_basis`, `status_origin` and unresolved contradictions); permitted actions; disposition; and a digest. Only the requester's own reading sets the headline category.
- **Counterparty.** The local counterparty decides from its own records (`decide_claim`), independent of wording (`render`). The historical wording is byte-identical, and it ignores claimant-asserted outcomes.
- **Intake boundary.** Embedded and HMAC evidence that is out of scope or out of period is refused before storage, idempotently. A wrong-month misroute voids approval; an identity contradiction holds every action.
- **Coverage (89d).** In the ordinary Twilio profile, a target-met result built from one status record, with no signed month report, is `INSUFFICIENT_EVIDENCE`.
- **Legacy route (89c).** It refuses, and never rewrites, account, vendor and service names outside `source-identity/1`.

## 4. Tests and actual results

- **Full suites** (agent0, fresh clones; only agent0 runs full suites):
  - round 4 on `3758164`: **1 failed, 4581 passed** (`evidence/integration-90/full-suite-3758164-FAILED.log`). The failure was mine, fixed by 89i.
  - round 5 on `6f43a91` (includes D04-C): **4663 passed, 1 warning**.
  - round 6 on `3f60647`: **4664 passed, 1 warning** (`evidence/integration-90/full-suite-3f60647.log`).
- **My focused runs,** each recorded in the ledgers with commands:
  - 89: 849, then 904 passed; one earlier attempt hung on an unchanged browser test and is kept.
  - 89b: first design 2 failed / 1666 passed, which exposed a safety regression fixed before commit; then 1669 passed.
  - 89c: 248. 89d: 1004. 89e: 1024. 89f: 1187. 89h: first run 2 failed (wrong expectations), then 14 passed.
  - Blind acceptance: 37.
  - On the integration head `e10d95d`: see section 4a.
- **Mutation checks** recorded: digest binding, ground re-derivation, tenant view, D06 hold, and the 89d rule.
- **Frozen bytes on the head:** `novel-89/` cases and README, `oracle.json`, `vendor_record.json`, `oracle-v2-d06.json` and the legacy `fixtures/disputes` oracle and traces are unchanged.
- **Opus critique:** one Claude Opus 5.5 critique (session `95a8f57d`, read-only tools) of `3454b33`. Verdict: adopt with changes. All 6 findings were accepted and fixed in `8083ab5`.

### 4a. Verification on the integration head

Run on `e10d95d` (includes D04-C at `6f43a91`, `2026-11-09T13:54:56Z`–`13:57:50Z`):

```sh
uv run --locked --offline pytest -q -p no:cacheprovider --basetemp=<unique> -o tmp_path_retention_policy=failed \
  tests/test_correspondence*.py tests/test_disputes*.py tests/test_blind_acceptance.py tests/test_mandate_claim_closure_2a.py \
  tests/test_local_review_exception_disputes.py tests/test_cross_claims.py tests/test_v4_routes_integration.py tests/test_northwind_workflow.py
```

Result: **1032 passed, 1 warning, 172.49s.** This is a focused run, not the full suite.

## 5. Decision references

| Decision | Who | Applied in |
|---|---|---|
| D03-A bounded exact source identity, extended to vendor and service names | **Ronok** | 89c |
| D04-C server-selected claim scope, "monthly keeps incident" | **Ronok** (implemented by agent1) | Harness mapping recorded in `TEST-CHANGES-89-disputes.md` |
| D06 "Humans gate judgment" | **Ronok** | 89, 89e |
| D07 narrow published matrix | **Ronok** | 89d |
| D10 public material only to models; D13 release bar; D14 no mandatory Opus critique | **Ronok** | Evaluation86 runner design |
| 2a closure-bound accept-denial mandate | **Ronok** (agent0 `b36827f`) | 89f |
| 3a resume evaluation86 when D04-C lands | **Ronok** | Runner branch (frozen; run held, section 6) |
| Q1 F3 narrow option A | **Delegated**: overview session under Ronok's (Recommended) authority, 04:28 PST | 89d |
| Q2 explicit closure for familiar wording, option A | **Delegated**: same authority | 89e |
| ADR-0089 option 3 (`DENIAL_REVIEW` + explicit acceptance) | W4 lead within D06 boundary, after one Opus critique | 89 |
| W5 findings: F1/F2/F8 accepted; F3 → D07; F7 blocked on retraction authority | W4 lead | 89b, 89d |
| Accept-denial scoring rule A | Grader gent8 (preregistered; Ronok may override) | Runner `957f56a`, `e1b6657` |

## 6. Blocked only on a Ronok decision: evaluation86

The runner is frozen at `e1b6657` and approved by gent8. See `docs/v4/evaluation86/RUNNER-FREEZE.md` on `work/dispute-evaluation-86-run`. No case has run, no model has been called and the sealed root has not been opened.

Under D04-C, monthly-tier claims require an incident. None of the 12 public sources states one, and no harness may invent one. Running now would therefore record 12 zero-call setup refusals as the cases' only first attempts.

- **Recommended: hold** until Ronok's whole-month evidence decision.
- **Alternative:** record the 12 refusals.

The D13 new-dispute gate stays unmet until then.

## 7. Remaining gaps and external proof still missing

- **No independent result.** No independent, unseen dispute result exists. The novel controls are same-team authored with a scripted reviewer (`SCRIPTED_NOT_ACTUAL_HUMAN`), and human review accuracy is unmeasured.
- **No real vendor channel (D08).** The counterparty is a local simulator, and nothing in W4 touches Ramp.
- **Retraction (F7).** There is no path to retract or acknowledge an identity contradiction, so a mistaken contradiction holds the claim until that decision is made.
- **Signed-channel refusals.** Contradictions on the signed channel stop at the grant's 403 and leave no per-case record (W0 refusal-audit item).
- **Full F3 (option B)** is recorded as a later option. Measured as a reverted experiment, it failed 168 cases.
- **Semantic residual risk** (named by Opus): a reviewer could label a waiver as maintenance while the deterministic maintenance check holds. Proposition-level review narrows this but does not remove it.
- **Frozen scorers.** `blind_expectations.py`, `prospective/witness.py` and `adequate_holdout/scoring.py` expect `DENIAL_ACCEPTED`. A new run of those harnesses needs rule A or a runner-side explicit acceptance; the scorers are unedited.
- **Legacy fixture-replay desk.** `/api/cases/dispute-*`, used by `rehearse.py` and `film_demo.py`, still auto-accepts its scripted correct denial. It was left as historical replay.
- **Trace ledger.** `posted` and `applied` in the trace ledger always read 0.00, because posting lives in the Local ledger. The W7 panel shows only Claimed and Awarded.
- **`disputed_remainder` semantics.** It is 0.00 while awaiting the vendor and equals the claim once in human review. This is pre-existing and documented in the 89h ledger.

## 8. Rollback

Revert in reverse merge order: `9b2097c` (89i), `a99365e` (89h), `4f918a1` (89e/89f), `ada6c78` (89d), `1f2b8b4` (89c), `39ee3f0` (89b), `b5cd49e` (89). Notes:

- **Before reverting 89 or 89e** on a database with stored cases, map stored `DENIAL_REVIEW` rows to `HUMAN_REVIEW`. `denial_acceptance` and `superseded_denial_acceptances` stay as inert history.
- **89b.** `inbox_refusal` rows and `contradicting_deliveries` become inert history.
- **89b depends on W5.** `39ee3f0` imports W5's `uptime.evidence_applicability.temporal_refusal` and `uptime.source_config.event_in_scope` (W5 evidence-custody-90, merged before it). Reverting 89b alone is safe. Reverting W5's evidence-custody merge requires reverting 89b first, or `correspondence._scope_refusal` fails at import time on the first embedded or HMAC delivery.
- **No change to accepted evidence.** No accepted evidence, hash, signature or idempotency key changes in any increment.
- **Reverting 89f** restores fail-closed acceptance for mandated principals. Reverting 89e restores the frozen `oracle.json` expectations (`oracle-v2-d06.json` becomes unused).
