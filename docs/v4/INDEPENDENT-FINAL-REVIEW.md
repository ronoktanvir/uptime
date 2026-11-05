# Independent final review

Four defects reproduced on frozen source **`f8fe4eb50f070e5b13b15e78eb25e45ae058565d`**: a normal procedural response breaks native award attribution; portfolio totals collapse distinct resources; claim intake collides across separately covered regions; and a signed compound denial bypasses the intended ambiguity escalation. These are implementation findings, not evidence of real loss, commercial authority, or a successful external attack. No application code was changed.

The highest priority is preserving the original external filing through its permitted response lifecycle. The next two findings concern inconsistent economic identities across otherwise working subsystems. The fourth concerns incomplete interpretation of signed, untrusted correspondence. I did not pad the report to five findings with unsupported capabilities or hypothetical attacks.

## Source, scope, and execution boundary

- Review worktree: `/Users/ronoktanvir/.local/share/uptime-engineering/worktrees/final_review`, branch `remediate/final_review`.
- Frozen source commit: `f8fe4eb50f070e5b13b15e78eb25e45ae058565d`; Git tree: `6cc0b1e8570b747c73638061665204af47741713`. Initial tracked and untracked state was clean.
- Reviewed against the V3 [handoff](../uptime-v3/Uptime_V3_Orchestrator_Handoff.md), [specification](../uptime-v3/Uptime_V3_Product_Technical_Spec.md), [DAG](../uptime-v3/Uptime_V3_Work_DAG.md), and [credential guide](../uptime-v3/Uptime_V3_Credentials.md), together with V4 architecture, capabilities, release/draft rules, source/mandate interfaces, native pricing, reconciliation and attribution documentation. External terms were not freshly verified; this review makes no current-provider or legal-entitlement claim.
- All reproduction databases and generated credentials were disposable and created under fresh temporary directories. No existing credential, customer database, private holdout, holdout gold, or saved native capture was opened. Only source, explicitly synthetic committed test inputs, project specifications and the published audit documentation were consulted. No outbound network, model call, provider write, or external publication occurred.
- The [reproduction script](../../scripts/independent_final_review_probes.py) blocks socket connections and DNS, disables access to packaged native captures, and removes inherited `UPTIME_*` / `RAMP_*` configuration from its process. Native-shaped data, P-256 reviewer keys, Ed25519 source/office/issuer keys, and extraction receipts are generated test inputs. The extraction fixture's model label is schema input, **not an actual model invocation**.
- Probes mount `create_app` and use its real middleware, authentication, routers, registry, evidence joins and durable SQLite stores. The native probe restarts the actual app with an operator-installed office configuration, imports through `RampWorkspace.import_observation`, and reads attribution through `GET /api/ramp/workspace`. No resolver, claim table, monetary evaluator or route authorization dependency is replaced.
- Consequential domain probes explicitly enable the app's test composition. Sandbox probes enroll distinct fake authorities and install exact one-use reviewer mandates; vendor messages use scoped Ed25519 source signatures. The default release-closed launcher is a separate boundary described below. TestClient exercises ASGI, not a real browser or socket listener.

## Prioritized reproducible defects

### 1. P1 — A permitted procedural response invalidates the original external filing used by native reconciliation

**Normal path.** Activate a resource agreement with the supported same-deadline supplement clause. Open an inbox claim through `POST /api/correspondence/claims`, ingest a signed `original_filing_receipt`, and register that external filing using the separate registrar/vendor-verifier witnesses. A finance-approved award and exact reciprocal native observation can then be attributed. When the vendor asks for missing logs, the normal `approve-response` and `submit-response` actions create a zero-dollar procedural response on that original filing.

**Observed.** `probe_historical_native_join` first obtains `active_binding_count=1` and `RAMP_APPLIED_ATTRIBUTED`. Immediately after the authorized `submit-response`, the mounted native overview reports `active_binding_count=0`, `APPLIED_UNATTRIBUTED`, and `ORIGINAL_EXTERNAL_RECEIPT_REQUIRED`. A separately signed subsequent award is rejected with the same error. The original authenticated receipt and independent custody attestation remain present and unchanged. Cash remains null throughout.

**Cause and consequence.** [`uptime/ramp_award_attribution.py:611–614`](../../uptime/ramp_award_attribution.py) rejects a historical original whenever `state["submissions"]` is nonempty. But [`uptime/correspondence.py:430–445, 543–559`](../../uptime/correspondence.py) expressly creates a local, zero-dollar `procedural_evidence_only` supplement for that historical route. The native verifier treats this permitted supplement as evidence that the original external filing is no longer valid. `_claim` and `summary` recheck this condition, so the defect affects both later awards and existing attribution. `_dispatch` also scans other initial filings in the tenant; source inspection indicates potential collateral blocking beyond the reproduced claim.

**Required correction.** Validate the immutable original independently of later procedural submissions. Permit only an authenticated, zero-dollar supplement with the exact historical predecessor and canonical supplement reservation; continue rejecting a second local initial filing, changed original, nonzero procedural claim, or conflicting history. Add the entire original → response → vendor award → native attribution lifecycle to mounted-route tests. Do not solve this by weakening external-filing witness requirements.

**Basis.** V3 §§3, 5 and 13.4 require follow-ups, durable original receipts, and distinct award/posting/application stages. V4 [attribution](RAMP-ATTRIBUTION.md) requires a proven original external filing; it does not justify destroying that provenance when a permitted response is recorded.

### 2. P2 — Portfolio aggregation silently halves equal-valued credits for separate resources

**Normal path.** Import the synthetic resource contract under two resource-specific installations, run independent positive/refusal checks, interpret, approve, activate, and dispatch each through `POST /api/vendors/{id}/evaluate`. Both resources are independently eligible for `$12.51` under terms that explicitly measure each station separately.

**Observed.** `probe_resource_totals` gets two distinct persisted case IDs and two `$12.51` contributions from `GET /api/dashboard`. Nevertheless, `cohorts.portfolio.metrics[estimated].amount` is **`12.51`**, while the sum of the two independent entitlements is **`25.02`**. Both contributions carry the same dashboard obligation ID. This is the portfolio cohort, not the deliberately nonadditive seeded-demo aggregate.

**Cause and consequence.** [`uptime/vendor_registry.py:332–338`](../../uptime/vendor_registry.py) includes resource and, when applicable, region in the persisted evaluation identity. [`uptime/workbench.py:57–70`](../../uptime/workbench.py) discards that distinction and reconstructs an obligation from vendor/account/agreement/product/month. `_metrics` then overwrites an equal-valued contribution at lines 110–119. Different values instead become “Not additive”; equal values produce a plausible but wrong numeric total. The same grouping function is used for all monetary stages, although this probe directly establishes the estimate error only.

**Required correction.** Carry a shared, contract-derived economic identity through evaluation, correspondence, and portfolio projection. Preserve resource/region where the agreement measures them separately while still deduplicating aliases and the evaluation/claim views of one obligation. Add both equal-amount and unequal-amount multi-resource controls; simply summing every row would reintroduce double counting.

**Basis.** V3 §§4–5 require shared case/financial interfaces and service-specific fee attribution. V4 [architecture](ARCHITECTURE.md) makes exact scoped joins central to financial truth. Correct per-case arithmetic is insufficient when the displayed portfolio changes its grouping scope.

### 3. P2 — A valid second region cannot enter the dispute workflow

**Normal path.** Activate two independently applicable subscriptions for the same station/account/service/month, one in `North` and one in `South`. The supported subscription clause requires separate account-and-region coverage. Each goes through the actual intake/test/promotion/evaluation routes, producing a `$15.03` eligible result. Provision the exact source scope for each and create their correspondence cases.

**Observed.** `probe_region_intake` obtains `North=15.03`, `South=15.03` from the active evaluators. Creating the North inbox succeeds. Creating the South inbox returns **HTTP 409**, `Claim ID or monthly business obligation already exists.`, despite a different claim ID and correctly provisioned regional scope.

**Cause and consequence.** [`uptime/correspondence.py:185–195`](../../uptime/correspondence.py) adds component to the non-Twilio draft key but omits region. Meanwhile, [`uptime/vendor_registry.py:335–336`](../../uptime/vendor_registry.py) and [`uptime/v4_routes.py:72, 254`](../../uptime/v4_routes.py) distinguish regional subscriptions and regional remedies. Thus a supported second entitlement is blocked before evidence intake or authorization; it is not an unsupported-contract refusal or missing-source grant.

**Required correction.** Derive intake uniqueness from the supported economic scope, or allow provisional scoped intakes and enforce canonical obligation uniqueness at filing. Keep whole-service obligations and same-obligation aliases locked. Add a same-resource/two-region mounted API test alongside the existing single-region cases.

### 4. P2 — A recognized factual objection hides an additional legal ground in a signed denial

**Normal path.** After a resource claim is approved and filed, the separately enrolled vendor source sends this newly composed Ed25519-signed text to `POST /api/correspondence/claims/{id}/events`:

> We denied your claim because we measured 5 minutes of downtime. You waived all service credit claims in a separate settlement agreement.

**Observed.** `probe_compound_denial` classifies the whole message as `downtime`, moves the case to **`RESPONSE_DRAFTED`**, and offers `approve-response`. After exact approval and the cooldown, `submit-response` succeeds with the sole argument: `The scoped, exclusion-adjusted measurements exceed the duration cited in the denial.` The alleged settlement is absent from the packet. The independent measurements establish 433 qualifying minutes, but do not establish whether a separate waiver exists or controls the claim.

**Cause and consequence.** [`uptime/correspondence_reason.py:119–160`](../../uptime/correspondence_reason.py) counts recognized cue matches, rather than requiring all substantive denial grounds to be understood. Unknown additional grounds do not increase `found`. [`uptime/correspondence.py:414–418`](../../uptime/correspondence.py) therefore converts the recognized numeric disagreement into an ordinary rebuttal. This contradicts the intended escalation for ambiguous or novel legal interpretations. It is **not** a signing bypass: human/reviewer mandates are still required and delivery remains in the local simulator.

**Required correction.** Preserve and classify all substantive denial grounds; escalate when any material ground remains unresolved. A bounded grammar can require full clause coverage, or retain an unresolved-reason flag that prevents the ordinary response path. Do not merely add “waiver” to a word blacklist. Regression controls should include a supported factual denial alone, the same denial plus an unknown legal condition, and benign non-substantive closing text.

**Basis.** V3 §3 requires escalation for novel legal claims and no unapproved legal interpretation. V4 [architecture](ARCHITECTURE.md) and [capabilities](CAPABILITIES.md) state that unknown or conflicting language escalates. A signature authenticates the source; it does not make incomplete interpretation safe.

## Reproduction commands and actual results

Run from the frozen review worktree using the already installed project environment; these commands install nothing:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python scripts/independent_final_review_probes.py
PYTHONDONTWRITEBYTECODE=1 /Users/ronoktanvir/.local/share/uptime-engineering/venv/bin/python scripts/independent_final_review_probes.py --regressions
```

For one reproduction append `--probe probe_historical_native_join`, `--probe probe_resource_totals`, `--probe probe_region_intake`, or `--probe probe_compound_denial`. `--probe probe_draft_isolation` is a passing security control. Probe assertions intentionally assert the observed defect, so exit 0 means **reproduced on this source**, not corrected.

The independent probes completed successfully. The bounded regression command completed **145 passed, 1 warning in 13.53 seconds**, exit 0. The earlier equivalent six-module invocation also passed 145 tests. The warning concerns pytest assertion rewriting of already imported `anyio`; import also emits a Starlette/httpx deprecation warning. The selected modules are:

```text
tests/test_vendor_draft_authority.py
tests/test_correspondence_resource.py
tests/test_correspondence_regional.py
tests/test_ramp_award_claim_integration.py
tests/test_vendor_resource.py
tests/test_portfolio_v4.py
```

Runtime observed: Python 3.13.12, pytest 9.2.0, FastAPI 0.162.0, Starlette 1.10.0, httpx 0.28.1, cryptography 46.0.7. The script disables pytest cache output and uses a new temporary `--basetemp`. No full-suite or browser-pass claim is made. No merge was performed, so the project’s post-merge `uv run --locked pytest` rule was not triggered. Full-suite execution was deliberately avoided because this task excludes saved native/private state and holdout access.

Passing independent controls: an enrolled reviewer with approvals disabled can stage, test and preview an unapproved draft; activation challenge and altered-body proof both return 403. The native chain rejects a substituted original-receipt digest even with properly signed witness statements, and rejects an extra minor unit above award/credit capacity. These bounded controls support their specific checks, not a claim that authorization is exhaustively verified.

## Unsupported paths, trust assumptions, and evidence limits

**Launcher availability is separate from the reproduced domain defects.** The supported launcher refuses `--enable-local-approvals` with sandbox mode (`scripts/serve.py:64–66`). Without it, ordinary correspondence creation/service intake is release-closed by `Authority.require_gate`; the native-specific gate only covers `/api/ramp/native/*`. This leaves the complete sandbox inbox-to-award operational path unavailable through that launch configuration. Existing operator imports and native comments are separate. I classify this as an integration/availability limitation, not a bypass or proof that live filing works. The domain probes explicitly enable test composition and verify its real route/mandate behavior. An attempted real launcher check with `--mode sandbox --port 0 --enable-local-approvals` exited 1 at socket binding with `Port unavailable. Select a different --port.`; the mode refusal is established by source, not by that failed listener experiment.

**Other unsupported functionality is not counted as a defect.** The docs explicitly limit native writeback to informational comments, with no demonstrated payment stop, production settlement, general vendor-credit creation, or cash recovery. Finite DSL support and safe `UNSUPPORTED_RULE` results are legitimate limitations. An actual native award requires separately trusted external evidence; no real award or commercial authority was supplied here.

**Custody and commercial identity remain trust assumptions.** Local administrators can enroll public keys and change code/state; independent witnesses must truthfully verify vendor identity, original filing, beneficiary and authority. Distinct generated keys in a test do not establish independent humans or enforceable commercial rights. Signed document hashes bind bytes but do not authenticate the truth of a contract. No finding relies on calling those explicit assumptions an exploit.

**The independent holdout remains unassessed.** No private input projection, gold or customer corpus was consumed. [BLIND-RESULTS.md](BLIND-RESULTS.md) describes bounded harness validation and acceptance not run by that document’s author; this does not establish the status of unseen later private runs. [audit/RESULTS.md](audit/RESULTS.md) records 116 passing executed observations and two unavailable browser observations on `dc0929957075d0f7392283a705b876c28cd343d8`, an older source. Those receipts cannot certify this frozen SHA. I did not rerun their private campaign or infer an unseen-vendor success rate.

**The demonstrated test weakness is lifecycle composition.** All 145 selected tests pass while the four new combinations fail. In particular, existing award integration tests can construct a historical intake with a bounded resolver fixture; they do not establish that a real promoted adapter, authorized procedural response, and mounted native summary remain joined. A single-region success does not test regional cardinality, and matching single-case amounts does not test portfolio grouping. The new denial text is an independently composed regression probe, not a secret heldout sample or statistical generalization study.

## Source-change log and later-main applicability

1. Initial inspection pinned clean `f8fe4eb50f070e5b13b15e78eb25e45ae058565d` on `remediate/final_review`. All executions above used that application source.
2. Only `scripts/independent_final_review_probes.py` and this report were added. No application, existing tests, fixtures, dependencies, audit reports or orchestration documents were edited. Temporary files were removed by their context managers.
3. During review, the integration branch advanced to **`64f077d5787a4ca3ef7738ee526900670b8e87e8`**. I read the commit list and diffs from the frozen SHA, including `claim_identity.py`, `correspondence.py`, `correspondence_history.py`, `correspondence_resource.py`, and `v4_routes.py`; no merge, checkout or execution of later main occurred.
4. **All four findings still apply by source inspection at `64f077d`.** `ramp_award_attribution.py`, `workbench.py`, `correspondence_reason.py` and `vendor_registry.py` are unchanged. The changed `correspondence.py` portion adds evidence display fields, leaving the faulty region key and denial transition intact. The canonical historical-backfill repair preserves legitimate historical reservations but does not change the native verifier’s blanket `state["submissions"]` rejection. New aggregate-service handling does not repair resource/region grouping or these resource-specific probes. This is an applicability assessment by read, not a newer-branch test result.
5. Final integration comparison observed **`157bb47705d80a3d65d76d7a1014c417c82d9e26`**. Relative to `64f077d`, this adds review documents and changes `scripts/rehearse_vendor.py`; no application module or launcher changed. The four applicability conclusions therefore remain unchanged at this later observed SHA.

Frozen-file SHA-256 checks recorded during review:

| File | SHA-256 |
| --- | --- |
| `uptime/ramp_award_attribution.py` | `572bbe6ea6183a3a8eeef2fb5bfaf1d56320ba51a8e105cddbc6f0910ccd7a35` |
| `uptime/workbench.py` | `cb88bbf57bf21260b3759855a1fde6fa224d404b9851cafdc5d6d59512ad5c4c` |
| `uptime/correspondence.py` | `0c8b4cbf6779a86147531617b59dbcb2cd29f2ad6adb934dd30c8a161003b305` |
| `uptime/correspondence_reason.py` | `35dfc77748d5eaf7358d0cd3a253d98bd472284d623b2d89d151fc26292d38d1` |
| `uptime/vendor_registry.py` | `a2fb0cd3bd1eaac1b664716f7982b9720dc232bc7b1efced027a17c51c63c4b0` |
| `uptime/v4_routes.py` | `0e13c6a71339c060536119c0b67e21f1b1b81d0afdfb5e2c4ec58ffc7642ec67` |
| `scripts/serve.py` | `978cd072f79d726c1ba2d4f077a8cbf4e3a1d85d09249a893b6be8a804fe2be6` |

The review artifact commit is intentionally separate from the frozen product SHA. It is a report and reproduction delivery, not a release attestation or authorization to change financial behavior.
