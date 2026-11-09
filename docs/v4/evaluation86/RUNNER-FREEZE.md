# Evaluation86 runner freeze

**Status:** frozen at `e1b6657` on `work/dispute-evaluation-86-run` (November 9, 2026). **No evaluation has started.** No first attempt has been spent, no model has been called, the sealed gold root has not been opened, and `prepare` and `run` report NOT READY.

## Who decided what

- **Ronok, "3a":** resume evaluation86 when D04-C lands. Only first attempts are allowed, with no retries. agent3 executes; gent8 validates and grades.
- **gent8, as grader:** proposed the accept-denial scoring addendum, rule A, at `work/release-evaluation-gent8` `1fdc2b5`. gent8 reviewed and approved `957f56a`, and approved `e1b6657` for freeze "as implemented". In a clean detached worktree, gent8 found 32 passed and the frozen scorers byte-identical to `03b372e`.
- **Still open, with Ronok:** whether evaluation86 runs at all. agent1 confirms that under D04-C (claim-scope/1) the monthly-tier family requires an incident. None of the 12 public sources states one, and no harness may invent one. Running now would therefore record 12 zero-call setup refusals (`InvalidClaimScope`, 409) as the cases' only first attempts. Only Ronok's open decision on whole-month evidence would change that.

## Pins

| Item | SHA-256 |
|---|---|
| Runner `scripts/evaluate_disputes_86.py` | `22fab53740600bda253bd2d548cbe2e50b8f79a430fa79debb645e07c8f08111` |
| Runner tests `tests/test_disputes_evaluation_86.py` (32 passed) | `9996531f49c1a8477175777cf5e55f7b08a4f8fcecb893c2c52d794e4b5e2a79` |
| Corpus manifest `docs/v4/evaluation84/manifest.json` (corpus commit `042d701`, merged unchanged) | `1b2ecd449c7eea2b6fe0bcaae9b58304a7bffa02579a43e246230cc09bcd8619` |
| Source-only readings manifest `docs/v4/evaluation86/blind-readings/manifest.json` (`9e49ac9`, merged unchanged) | `5f1ab847b84f34daea5e4189edf4a3064044e0a1cfac3dcd7356423ca4deb831` |
| Offline plan output (`plan` subcommand; 12 cases: 11 monthly_tier, 1 resource_month) | `a7cab7e7bde2ee6ff5aba53d165d5c415edc077c1a1ca47116fd04aa3c66ca7e` |
| Core `uptime/` + `web/` tree at freeze, unchanged versus base `23805c9` (`verify` subcommand, 119 files) | `9b929b94d6983ecc3f6514b375f0c98652c62df0a14a7527288e30c40a904f51` |

At run time, the core tree is pinned again against the then-current, committed integration base. That base must contain D04-C and the onboarding activation fix, and the run is refused if the core is uncommitted or differs from that base. The runner, its tests, both manifests and the plan output must still match the hashes above. Any change to them needs a new freeze record.

## Frozen behavior

- **Plan:** verifies all 24 public files and the 12 readings, and binds each reading to its exact source and reply digest. It records the scope each source states and the scope it leaves unstated, and lists customer facts, the claimed amount and the scripted readings as excluded from model requests. An audit-hook test proves the sealed root is never opened.
- **Intake:** sends only the stated scope. A refusal is one create-only, zero-call `SETUP_REFUSAL` record and is never retried.
- **Model dispatch:** at most once, only for a pinned approved request with the reviewer's own blind entry. It needs the existing exact-request operator approval, which this runner never grants. After dispatch, the job pool is drained and the server's own terminal state is recorded.
- **Accept-denial (rule A):** the judgment view is met only at `DENIAL_REVIEW` when the offered actions are exactly `['accept-denial']`. Only then is there one create-only scripted acceptance labeled `SCRIPTED_NOT_ACTUAL_HUMAN`. The authority view records `DENIAL_ACCEPTED`, or `AUTHORIZATION_STAGE_FAILURE` when the scripted acceptance is refused.
- **Gold:** read only after every declared case has a terminal result. The scorer is committed before its output is read.
