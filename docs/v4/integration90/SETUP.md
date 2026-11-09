# Reproduce Uptime from a fresh checkout

Verified on November 9, 2026: every integration round cloned the branch into an empty directory and ran exactly the commands under "Build and verify". `main` was fast-forwarded to the integration head `a8c4c22`; its post-merge run gave 4,684 passed with 1 warning, and 104 JavaScript checks; the other checks passed. Receipts: `docs/v4/evidence/integration-90/verification-<commit>.json`, with the full pytest logs beside them. The local clones came from the same pushed commits as GitHub.

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
git checkout main                         # carries the integration work since November 9
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

Before a presentation (optional, both read-only):

```sh
uv run --locked python scripts/operations_preflight.py
RAMP_ENV=sandbox UPTIME_RAMP_CREDENTIAL_FILE=~/.config/uptime/ramp-demo-native.json \
  python scripts/ramp_prefilm_check.py --output-dir ~/.local/share/uptime-engineering/runtime/ramp-lineage-20261109
```

The first checks disk space, loopback-only ports, the absence of tunnels, workspace health and backups. The second needs the protected sandbox credential, refuses to run under CI and makes no writes. See [DEMO-MACHINE-90.md](../DEMO-MACHINE-90.md) and [the rehearsal](REHEARSAL.md).

For a presentation, serve a frozen checkout of a tested commit (`git worktree add --detach <dir> <commit>`) rather than a branch other people are editing.

Live Ramp sandbox reads need the protected local credential setup in [RAMP-DEMO-CONNECTION.md](../RAMP-DEMO-CONNECTION.md) and [OPERATIONS.md](../OPERATIONS.md). Never put credentials, reviewer keys, local databases or sealed evaluation answers in Git or in a model prompt.

## What a fresh checkout cannot reproduce

- Live Ramp observations and the human-posted note: they need the team's sandbox access. Committed receipts record what was observed.
- The recorded CalyxQuay review: it lives in a private local workspace and host authority store. The [receipt](../evidence/local-review-88/recorded-review-20261109.json) is the reproducible record; the grant is spent.
- Sealed evaluation gold and paused evaluation runners (not on this branch).
