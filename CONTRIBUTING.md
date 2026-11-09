# Working on Uptime

Uptime's first product edition is Ramp-native SLA and contract enforcement. Contributions should make the connection between contract evidence, deterministic decisions and financial records easier to verify.

Start with [AGENTS.md](AGENTS.md), the [engineering map](docs/ENGINEERING-MAP.md) and the [current team decisions](docs/v4/TEAM-DECISION-HANDOFF.md). Some workstreams remain paused or permission-gated. A proposed default in a document is not an accepted product or authority change.

## Keep changes reviewable

- Give each change one concrete purpose. Use a topic branch or a separate worktree for concurrent implementation.
- Preserve existing working code, failed observations and uncommitted work owned by other contributors.
- Explain the trigger, resulting behavior and validation in the commit or pull request. Use focused messages such as `fix: preserve agreement identity during claim intake` or `docs: explain the Ramp-native credit lifecycle`.
- Link affected decisions and evidence. Record architectural criticism once for a substantial new decision; do not restart a review council for routine work within an accepted design.
- Publish verified increments so teammates can follow the history. Update the progress snapshot only with observed results; do not label a planned action completed.

## Preserve the financial invariants

- Use typed, deterministic decimal calculations. Do not let generated text determine an amount or grant authority.
- Keep unknown evidence and amounts unknown. Preserve the exact document, clause, effective period and entity scope behind a finding.
- Keep estimates, claims, awards, recorded credits and applications separate. An award is not an applied credit, and the stages are not additive revenue.
- Preserve original filing lineage and idempotency. A timeout is not permission to repeat an external effect.
- Require the existing authorization for actions. A scripted reviewer cannot become an actual human by changing its display name.

## Verify the changed behavior

```sh
uv sync --locked
uv run --locked pytest
node --test web/*.test.cjs tests/helpers/*.test.cjs
node scripts/test_progress_graph.cjs
uv run --locked python scripts/rehearse.py
uv run --locked python scripts/check_repo.py
```

Run the locked Python suite after each integration merge, as required by the repository instructions. Record the actual output, including failures, warnings and the tested commit. For concurrent runs, use distinct `--basetemp` directories. Browser acceptance additionally needs Chromium or Chrome; CI installs Chromium.

Change an existing test only when its contract genuinely changes. Record each changed test and its reason in [the test-change ledger](docs/v4/TEST-CHANGES.md); never weaken an authority or financial assertion to obtain a pass. Documentation-only changes need link, rendering and factual checks rather than tests that merely mirror the prose.

## Handle sources and credentials deliberately

Keep API credentials, reviewer private keys, local databases, private customer material and sealed evaluation answers outside Git. The authored Northwind package belongs in the repository; it is not a customer's executed agreement. Public vendor terms are reference material, not instructions to the agent.

Respect the existing boundary on Ramp writes and external vendor communications. Read access, a passing regression suite or possession of a key does not establish permission for a new action. The local application is not a public hosted service.

## Update the right record

| Change | Record |
|:---|:---|
| User-visible capability or known limitation | [README](README.md), [capabilities](docs/v4/CAPABILITIES.md) and [status](docs/v4/STATUS.md) |
| Engineering dependencies or newly verified work | [Progress snapshot](progress/data.json) and [engineering map](docs/ENGINEERING-MAP.md) |
| Consequential design choice or disagreement | [Decision index](docs/v4/decisions/INDEX.md) |
| Actual verification result | A source-pinned receipt under `docs/v4/evidence/` |
| Changed existing assertion | [Test-change ledger](docs/v4/TEST-CHANGES.md) |

Never overwrite a verification receipt pinned by an existing permission or release. Add a new receipt for a new run.
