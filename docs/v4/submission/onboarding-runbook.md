# Demonstration runbook: model-assisted contract onboarding

What a viewer sees:
- A public or authored contract goes through the ordinary application.
- A real Claude Opus 5.5 call proposes typed terms, each quoted exactly from the source.
- Deterministic validation accepts or refuses that reading.
- Automatic family selection picks the rule family, and the accepted reading is staged in SHADOW.

A person still accepts the interpretation, authors tests and approves; generating a proposal never activates anything.

## Results to state alongside the demonstration

| Run | What happened | Status |
|---|---|---|
| **Authored: Corvid Ledger** | One genuine call per family. The monthly reading validated (11 exact quotations), automatic selection chose monthly, and the adapter is staged in **SHADOW** with no actions and no activation. | Authored demonstration success |
| **Authored: Halden Relay** | The monthly reading quoted the vendor name ("Halden Systems") apart from its supply verb. The identifier-grounding rule refused it, and the resource reading was refused. **NO_SUPPORTED_FAMILY.** | Authored demonstration refusal |
| **Authored control** (conflicting filing windows, maintenance exclusion) | **NO_SUPPORTED_FAMILY.** The monthly reading failed first for the same split-party reason. The resource reading cited both filing passages and the measurement block as unsupported. | Authored refusal; the conflict and exclusion refusals are shown by deterministic tests, not by this call |
| **Independent cohort**, published [RESULTS.md](../evaluation-finish-20261109/RESULTS.md) | 12 genuine calls; all 12 proposals failed validation. Every monthly reading first failed identifier grounding. **0 of 4 intended positives reached SHADOW; 6 of 6 refused.** | Independent generalization result. Never combined with the authored runs |

**Why the authored runs differ from the cohort.**
- Before any call, both positive contracts were checked with no model: the strict offline parser does not accept them, so a model is required, and a correct reading of each validates. They were written inside the published grammar.
- The independent contracts were not, which is why the cohort measures generalization and these runs do not.
- Even inside the grammar, one of the two authored positives failed for the same identifier-grounding reason as the cohort. The same model output style breaks both.
- Natural party introductions and titles still need explicit, source-grounded treatment. That is the next generalization workstream. It is deliberately not part of this push, and no grounding check was relaxed for this demonstration.

## Reproduce

Run from a checkout of this branch. Use a new empty folder outside Git, here `R`.

1. **Protected configuration.** Create `R/protected/` with mode 0700.
   - `config.json`, mode 0600: `{"version":1,"executable":"<absolute claude CLI path>","approvals_path":"R/protected/approvals.json","kinds":["vendor"]}`.
   - An empty catalog: `{"version":1,"limits":{"daily_jobs":10,"daily_budget_usd":"8.00"},"approvals":[]}`.
2. **Reviewer account.** Enroll a disposable reviewer account. It is not a human review identity.

   ```bash
   uv run --locked python scripts/serve.py --enroll demo-operator --credential-file R/demo-operator.jwk --db R/workspace.sqlite --mode replay --tenant submission-onboarding
   ```

3. **Server.** Start it on a free port in 8811–8819:

   ```bash
   uv run --locked python scripts/serve.py --db R/workspace.sqlite --mode replay --tenant submission-onboarding --port 8811 --public-proposal-config R/protected/config.json
   ```

4. **Selection access.** Read it for a contract. The result lists each family's exact request digest and `APPROVAL_REQUIRED`:

   ```bash
   uv run --locked python scripts/run_onboarding_demo.py access --origin http://127.0.0.1:8811 --account demo-operator --credential R/demo-operator.jwk --vendor corvid-ledger --document fixtures/submission_onboarding/corvid_ledger.json
   ```

5. **Operator approval of every family request.** This is model invocation only. Export first:

   ```bash
   uv run --locked python scripts/public_proposals.py export-vendor --profile auto --document fixtures/submission_onboarding/corvid_ledger.json --config R/protected/config.json --output R/exports/corvid-ledger.json --tenant submission-onboarding --subject demo-operator --target corvid-ledger
   ```

   Confirm each printed digest equals the app's, review the export with `show`, then approve each file separately:

   ```bash
   uv run --locked python scripts/public_proposals.py approve R/exports/corvid-ledger.monthly-propositions.json --approvals R/protected/approvals.json --approved-by "<operator name>" --expected-request-sha256 <digest> --confirm-authored-public --hours 6
   ```

6. **Submit, wait and stage.** Run `submit`, then `wait` (GET-only polling), then `access` (`SELECTED`), then `stage --overlay fixtures/submission_onboarding/overlays/corvid_ledger.json` (SHADOW). Finish with `record --evidence <new file>`.
7. **Show it in the browser** at `http://127.0.0.1:8811/#vendors`. Sign in with the account and its credential file.
   - **Generate a public proposal:** no profile choice; selection outcome, family states, refusal passages.
   - **Proposed public clauses:** exact quotes and typed values.
   - **Vendor card:** SHADOW state and **Show review requirements** (requirement card, family selection, generated drafts).

No step approves an interpretation, adapter or activation. Failed and timed-out calls show their own codes (`provider_failed`, `provider_timeout`), and the only recovery is a new attempt identifier with its own approval.

## Evidence

[`docs/v4/evidence/submission-onboarding-20261109/`](../evidence/submission-onboarding-20261109/):
- [`genuine-calls-summary.json`](../evidence/submission-onboarding-20261109/genuine-calls-summary.json): the six jobs, verified model, sessions, costs, timestamps, approvals and provenance notes;
- one `*-initial.json` per contract: source, selection view, job views with provider receipts, and the adapter and requirements for the staged contract.

## What not to claim

- The authored success is not a generalization score; the independent result is 0/4.
- The SHADOW adapter is not approved or active. Nobody reviewed its interpretation.
- The approvals recorded here grant model invocation only; `approved_by` names an agent.
- These authored contracts and the reviewer account are demonstration inputs. Disclose them in the README and narration.
