# Reproduce Uptime from a fresh checkout

Verified on November 9, 2026, by cloning `work/integration-90` into an empty directory and running the commands below. Results: [STATUS.md](../STATUS.md#november-9-integration) and the fresh-checkout receipt under `docs/v4/evidence/integration-90/`.

## Requirements

- macOS or Linux with Git, [uv](https://docs.astral.sh/uv/) (0.10 or later) and Node 20 or later. CI uses Python 3.13 and Ubuntu.
- Python 3.11–3.14; `uv` selects or installs one that matches `pyproject.toml`.
- Chromium or Chrome for the browser tests. CI installs Chromium with `uv run --locked python -m playwright install --with-deps chromium`. Browser-dependent tests skip when no browser is available, unless `UPTIME_QA_REQUIRE_SERVER=1` is set.
- About 3 GiB of free disk for one full test run. Do not run two full suites on the same volume at once.
- No credentials. Tests, the rehearsal and the authored Northwind walkthrough need no Ramp, model or vendor access.

## Build and verify

```sh
git clone https://github.com/ronoktanvir/uptime.git
cd uptime
git checkout work/integration-90          # or main after this branch merges
uv sync --locked
uv run --locked pytest -p no:cacheprovider -o tmp_path_retention_policy=failed --basetemp="$(mktemp -d)/uptime-tests"
node --test web/*.test.cjs tests/helpers/*.test.cjs
node scripts/test_progress_graph.cjs
uv run --locked python scripts/rehearse.py
uv run --locked python scripts/check_repo.py
uv run --locked python scripts/render_requirements.py --check
```

The pytest options keep disk use bounded: passing tests' temporary directories are removed as they finish. Delete the base directory afterwards. Expect one known FastAPI/Starlette `TestClient` deprecation warning.

## Run the application

Authored Northwind walkthrough (local only, loopback):

```sh
uv run --locked python scripts/setup_northwind.py \
  --directory "$HOME/.local/share/uptime/northwind-session-002" \
  --origin http://127.0.0.1:8776 --serve
```

Open http://127.0.0.1:8776 and sign in as `scripted-test-reviewer` with `scripted-reviewer.jwk` from that directory. Use a new directory for each fresh presentation, and add `--resume` to restart without resetting state. The walkthrough's contract, usage, vendor replies and ledger are authored demonstration inputs; see `fixtures/northwind/README.md` and [the rehearsal](REHEARSAL.md).

Progress map (read-only snapshot): `python3 scripts/serve_progress.py --port 8780`, then open http://127.0.0.1:8780.

Live Ramp sandbox reads need the protected local credential setup in [RAMP-DEMO-CONNECTION.md](../RAMP-DEMO-CONNECTION.md) and [OPERATIONS.md](../OPERATIONS.md). Never put credentials, reviewer keys, local databases or sealed evaluation answers in Git or in a model prompt.

## What a fresh checkout cannot reproduce

- Live Ramp observations and the human-posted note: they need the team's sandbox access. Committed receipts record what was observed.
- The recorded CalyxQuay review: it lives in a private local workspace and host authority store. The [receipt](../evidence/local-review-88/recorded-review-20261109.json) is the reproducible record; the grant is spent.
- Sealed evaluation gold and paused evaluation runners (not on this branch).
