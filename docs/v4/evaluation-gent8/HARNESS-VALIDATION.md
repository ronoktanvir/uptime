# Evaluation84 harness validation and pre-registration addendum

**Executed for the onboarding sub-cohort, November 9, 2026, 11:48–11:50Z.** After the user's explicit go-ahead, all six onboarding first attempts ran on `89fe25c` (core identical to `03b372e`). There were six genuine `claude-opus-5-5` calls, sequential, with no retry and empty tool and MCP inventories. Result: **0/4 supported extractions accepted**; all six were refused at post-model deterministic proposal validation. [Stage-count receipt](../evidence/release-evaluation-gent8/onboarding84-first-attempts.json). Per-case causes stay in the owner-only evaluation directory under the firewall below. **No dispute inference has run. Sealed gold was not opened.**

*Original pre-execution status:* The first attempts need the user's explicit go-ahead to resume the paused evaluation (project instructions: the November 7 scope "does not … resume frozen evaluation worktrees"). The dispute half also needs the D03/D04 implementation. **Update, November 9:** Ronok decided D03-A (one bounded exact source identity, blocking near-duplicate guard, no override) and D04-C (server-derived scope requirements by governing family; invoice as evidence). The integration owner recorded this on `work/integration-90`, and agent1 is implementing it on `work/identity-pricing-89`. The 12/12 preflight result below describes source before that implementation. The preflight is re-run when the implementation lands, and the frozen sources are not edited. Decision record: [ADR-0092](../decisions/ADR-0092-evaluation-release-assessment.md).

Branch `work/release-evaluation-gent8`, from `v4/integration` `03b372e`. The integration owner keeps this evaluation branch out of `work/integration-90` until the team approves resuming it.

## What was brought together, unchanged

| Commit | Content |
|---|---|
| `dae8af8` | Octopus merge of the unchanged frozen corpus `042d701`, the onboarding harness interface and test control `a542a21`, and the source-only scripted dispute prereadings `9e49ac9`. Every change is an added file. |
| `adc1c83` | The eight uncommitted paused files, copied byte for byte. Their SHA-256 matched [the pause checkpoint](../evidence/pause-20261106/checkpoint.json) before and after the copy. The originals remain in their paused worktrees. |

## What was validated (current source, no model call)

| Check | Result | Evidence |
|---|---|---|
| Corpus pins | 24/24 inputs match manifest SHA-256/bytes and the frozen commit's Git blobs | [preflight receipt](../evidence/release-evaluation-gent8/preflight-evaluation84.json) |
| Sealed gold custody | 18/18 expected files present, regular, owner-only. Checked with `lstat` only; the files were not opened or hashed. | same |
| Onboarding inputs | 6/6 pass the runner's strict input checks and the current extraction-profile input validator. Family routing matches the manifest. | same |
| Dispute claim intake | **12/12 refused at the claim `Scope` schema.** Account and agreement names contain spaces and fail the `Id` domain (**D03**). Component, incident, invoice and region are universally required and absent from every reply context (**D04**). No other blocker. | same; matches the two preserved HTTP 422 receipts in `docs/v4/evaluation86/setup-refusals/` |
| Runner mechanics with provider doubles | 41 onboarding tests: 35 original tests unchanged plus 6 added. 20 dispute-infrastructure tests. | [focused log](../evidence/release-evaluation-gent8/focused-tests.log) (67 passed with the restart probe and preflight) |
| Real transport, fake CLI answering | 1 model-call invocation, SUCCEEDED, terminal state observed, a second run refused with `FileExistsError` | [dry run ok](../evidence/release-evaluation-gent8/transport-dryrun-ok.json) |
| Real transport, fake CLI hanging 75 s | Transport stopped at its 60 s bound. Job recorded `UNCERTAIN`/`provider_timeout` as terminal. 1 invocation, no retry. Elapsed 63.8 s. | [dry run hang](../evidence/release-evaluation-gent8/transport-dryrun-hang.json) |

The dry runs used only the authored harness control, through the real `SafePublicClaude` profile checks. They are controlled-provider evidence, not model calls.

## Defects found and fixed before any inference (`c1fa513`)

1. **Terminal state could be lost.** The provider bound is 10 s for `--help`, 10 s for `--version` and 60 s for the call. The runner polled for only 90 s and then tore the server down after a 10 s join. A slow job could therefore still be `RUNNING` when the queue was snapshotted, and its result would be lost.
   - **Fix:** poll for the provider bound plus 40 s, then wait for lifespan shutdown. Shutdown closes the job pool with `wait=True`.
   - **Record:** the server's own post-shutdown status goes into `report.queue`, separately from what the poll saw.
2. **Only selected core files were pinned.** Prepare and run now also pin a digest of every tracked `uptime/` file and refuse uncommitted core changes.

## Known structural limits, pre-registered before any result

- **Fee authority cap.** The runner signs as a draft reviewer. `uptime/vendor_api.py` resolves governing-fee contexts only for non-draft principals, so `monthly_tier` and `completed_step` cannot produce exact money in shadow preview. Their authored fee sources stay local facts. Those two cases report extraction and shadow outcomes plus `FEE_AUTHORITY_NOT_EXERCISED` for money. That is a structural cap on 2 of the 4 supported contracts, not an arithmetic error. The release path (non-draft reviewer under the release gate) is a different path, so this onboarding evidence does not transfer to it automatically.
- **Family supplied.** The author declared each contract's family. Autonomous family discovery is not measured (D05).
- **Single cohort.** One cohort of independently authored fiction. It is not a generalization or production-reliability estimate.

## Pre-registration addendum (adopted after the Opus critique)

1. **Two sub-cohorts, never pooled.** `84-onboarding` (6 contracts) and `84-disputes` (12 replies) each get their own freeze commit and report. ADR-0084's four views apply within each. Neither is presented as "the evaluation" without the other's status beside it.
2. **Transport failures.**
   - A failure after the single proposal-job POST is accepted counts as that case's first attempt, at its actual stage: `UNCERTAIN` transport, `REFUSED` validation, or a shadow/evaluation error. It is never voided or retried.
   - A refusal before any provider call (`frozen_inputs` or `permission`, zero calls) is a setup failure, not a semantic result. It stays in the report. Any later run is a separately named attempt with the original preserved.
3. **Contamination firewall.** Raw provider output and per-case onboarding results stay in owner-only attempt directories outside Git. Only per-stage counts are published until the D03/D04 designs (integration packet 94) are committed. Nobody implementing D03/D04 receives onboarding outputs.
4. **Disputes.** No dispute first attempt runs until D03 and D04 are implemented through the normal claim route. The frozen reply sources are not edited. The harness never slugs a name or invents a component, incident, invoice or region.
5. **Gold and scoring.** No scorer exists yet. `score()` in the dispute runner raises `NotImplementedError` because the comparison rules are sealed with the gold. The scorer is written only after every first attempt in a sub-cohort is terminal; `read_gold` enforces this. It must verify each gold file and the comparison rules against the manifest SHA-256 before decoding them, and its code is committed before its output is read.

## Go-ahead procedure for the onboarding sub-cohort (NOT EXECUTED)

Run only after the user explicitly resumes evaluation. Prepare, inspect, approve and run in one sitting: a Claude CLI auto-update between prepare and run changes the pinned transport profile, and a drifted attempt stops with zero calls.

```bash
R="$HOME/.local/share/uptime-engineering/review/evaluation84-onboarding"; mkdir -m 700 "$R" "$R/attempts"
# config.json (0600): {"version":1,"executable":"<absolute claude path>","approvals_path":"$R/approvals.json","kinds":["vendor"]}
# approvals.json (0600): {"version":1,"limits":{"daily_jobs":6,"daily_budget_usd":"6.00"},"approvals":[]}
for CASE in monthly_tier completed_step resource_month aggregate_fixed_month unsupported_variable_fee ambiguous_deadline; do
  uv run --locked python scripts/evaluate_onboarding_85.py prepare --case-id "$CASE" --family "$CASE" \
    --document-path "$PWD/fixtures/evaluation84_public/onboarding/$CASE/document.json" \
    --customer-path "$PWD/fixtures/evaluation84_public/onboarding/$CASE/customer.json" \
    --document-sha256 "<manifest pin>" --customer-sha256 "<manifest pin>" \
    --config-path "$R/config.json" --attempt-dir "$R/attempts/$CASE" --tenant eval84 --subject eval84-onboarding
done
uv run --locked python scripts/public_proposals.py show "$R/attempts/<case>/request-export.json"   # a person inspects all six
uv run --locked python scripts/public_proposals.py approve "$R/attempts/<case>/request-export.json" --approvals "$R/approvals.json" \
  --approved-by "<person>" --expected-request-sha256 "<request_sha256>" --confirm-authored-public
uv run --locked python scripts/evaluate_onboarding_85.py run --attempt-dir "$R/attempts/<case>" --config-path "$R/config.json"   # sequentially, once each
```

Before the first real call, re-run `scripts/preflight_evaluation84.py` and the focused suites on the frozen commit. Confirm each `request.json` contains only the document text and existing instructions; the tests check this structurally. Then record the frozen commit in a new receipt.

## Reproduce this validation

```bash
uv run --locked python scripts/preflight_evaluation84.py
uv run --locked pytest -q tests/test_preflight_evaluation84.py tests/test_onboarding_evaluation_85.py tests/test_disputes_evaluation_86.py tests/test_release_probes_gent8.py
uv run --locked python scripts/dryrun_onboarding_85_transport.py --mode hang --workdir NEW_DIR --receipt NEW_FILE
```
