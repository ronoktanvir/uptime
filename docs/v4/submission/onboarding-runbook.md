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

## Preserved recorded workspace (for the film)

> **Never serve the preserved folder, not even for a read-only look.** Any serve of its `workspace.sqlite` writes to the file. Serve only a scratch copy (below), delete the copy afterwards, and check the preserved folder by hash only.

The six recorded jobs and the SHADOW Corvid Ledger adapter are kept in an owner-only folder:

`~/.local/share/uptime-engineering/tasks/submission-onboarding-20261109/recorded-workspace/`

It holds `workspace.sqlite`, `protected/config.json` (pointing at its own `protected/approvals.json`), the disposable `role1-operator.jwk` credential and the request exports. The original run folder `~/.local/share/uptime-engineering/runtime/submission-onboarding-20261109/` is also kept; its database still has the recorded hash.

**Hashes of `workspace.sqlite` (SHA-256).**
- **Recorded:** `9043eaaf356071a1f45a841daf075a8cb3ee1945c009cd6b8437f95cb3241736`. The original run folder and the preserved folder must both show this.
- **Changed, do not use:** `41fecca2f491a181331bf1ce2dafe806fad9dc3c64b93eadf16e8d315b63d07f`. It is kept beside the restored file as `workspace.sqlite.CHANGED-by-8812-sign-in-20261109T133135-0800`.

```bash
shasum -a 256 ~/.local/share/uptime-engineering/tasks/submission-onboarding-20261109/recorded-workspace/workspace.sqlite
```

**What happened.**
- At 13:31:35 PST, seconds after making the copy, agent2 served the preserved folder itself on port 8812 and made signed reads as `role1-operator`: the selection view, the Corvid Ledger job and the vendor. That serve changed the database to `41fecca2…`.
- From then until the restore, this section was wrong twice: it called the copy unmodified, and it said signing in adds only a session record.
- At 15:42 PST the changed file was moved aside and the original was copied back from the run folder with `cp -p`. The preserved database again equals the original byte for byte, and the other preserved files (credential, approvals, exports, logs) always did. `protected/config.json` differs from the original only by design: it points at the copy's own approvals.

**What differs between the two databases.** This was found without reading any row.
- The files are the same size and differ in 2 bytes, both in the SQLite header: the file change counter and the version-valid-for number, each 28 → 29.
- The schema, every other page and the contents of all 44 tables (compared by digest) are identical. No session row or any other record was added.
- Serving a scratch copy and making the same reads produced exactly `41fecca2…` again. Any serve leaves one write transaction in the file even when no record changes, which is why the rule above has no exceptions.

**Viewing it: scratch copy only.** Run in one shell, from a checkout of the integrated build that contains this branch. The last setup line points the copy at its own approvals catalog; without it, the server would read the preserved folder's catalog.

```bash
S=$(mktemp -d)
cp -Rp ~/.local/share/uptime-engineering/tasks/submission-onboarding-20261109/recorded-workspace/. "$S/"
rm "$S"/workspace.sqlite.CHANGED-*
python3 -c 'import json, sys; p = sys.argv[1] + "/protected/config.json"; c = json.load(open(p)); c["approvals_path"] = sys.argv[1] + "/protected/approvals.json"; json.dump(c, open(p, "w"))' "$S"
```

```bash
uv run --locked python scripts/serve.py --db "$S/workspace.sqlite" --mode replay --tenant submission-onboarding --port 8813 --public-proposal-config "$S/protected/config.json"
```

Sign in at `http://127.0.0.1:8813/#vendors` as `role1-operator` with `$S/role1-operator.jwk`. When finished, stop the server, delete the copy and recheck the preserved hash:

```bash
rm -rf "$S"
```

Checked this way at `7a6db64` (integration head), 15:45 PST:
- the selection outcomes were Corvid Ledger SELECTED and both Halden Relay contracts NO_SUPPORTED_FAMILY;
- job `26ee4e3f` was SUCCEEDED with 11 clauses from `claude-opus-5-5`;
- the adapter was SHADOW `ff76ed67` with no actions.

The copy was then deleted, and the preserved hash was still `9043eaaf…`.

**Read-only in effect, for the records.**
- All six jobs are terminal. Re-submitting the same request returns the same job.
- The stored approvals expire at 2026-11-10T03:15Z. A new model call needs a new attempt identifier and a new operator approval.
- Requests change no job, approval or adapter record, and staging again returns the same SHADOW revision. The database file still changes, so this does not make serving the preserved folder safe.

**Newer builds.** No migration is needed: the job table and registry tables are created idempotently. The recorded jobs and the adapter stay readable as `SELECTED`/SHADOW only while the build keeps these pins unchanged:
- `uptime/vendor_model_jobs.py` SHA-256 `b90f74d8cc6c1bc0c0ba42031fd752b76e8d71fefa612c4c18cd60f8aa70268c`;
- semantics revisions monthly `1b53500d662220505d125983684ec1753a937ad172fe12472acca712456dbf4a` and resource `7a9b09ee450f8e93affdede4b464c5052ed93a85ce258bc42f88dd34f3952b54`;
- the Claude CLI binary at `~/.local/share/claude/versions/2.1.318`.

If any changes, the selection view no longer finds the jobs, and the adapter shows REVIEW_REQUIRED. That is correct staleness, not damage. The job pages and their receipts remain readable. To check a build:

```bash
uv run --locked python -c "from uptime import vendor_terms; print(vendor_terms.SEMANTICS_REVISIONS)"
```

```bash
shasum -a 256 uptime/vendor_model_jobs.py
```

As of `a40fd84` and again at `7a6db64` (integration), every pinned file equals the code that ran. The only difference is `public_proposal_jobs.py`, which this branch changes.

**Film labelling.** Label the beat as a recorded run: job `26ee4e3f-e5e2-47c7-aebe-e1f4dc7c7402`, model `claude-opus-5-5`, session `41f4dcb6-ca5e-4c43-ac01-95d222de9737`, finished 2026-11-09 21:17:38Z. State that it is an authored contract, staged in SHADOW, not approved or active.

## What not to claim

- The authored success is not a generalization score; the independent result is 0/4.
- The SHADOW adapter is not approved or active. Nobody reviewed its interpretation.
- The approvals recorded here grant model invocation only; `approved_by` names an agent.
- These authored contracts and the reviewer account are demonstration inputs. Disclose them in the README and narration.
