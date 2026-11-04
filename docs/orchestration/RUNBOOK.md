# Operator runbook

## Start and verify

Use Python 3.11–3.14, `uv`, and Node for the browser unit tests. From the repository root, run:

```sh
uv sync --locked
UPTIME_QA_REQUIRE_SERVER=1 uv run --locked pytest -q
node --test web/*.test.cjs
uv run --locked python scripts/rehearse.py
uv run --locked python scripts/serve.py --mode sandbox --open
```

The default server listens at 127.0.0.1:8765. `--open` signs the local operator in as reviewer. Without it, the launcher prints the path to a private temporary HTML file containing reviewer and viewer links, not the secrets themselves. Use the file on the same machine. Session cookies expire after one hour. The local shell that starts the service controls these links. Keep it open while using the app. Ctrl-C stops the server.

On this Mac **Open Uptime.command** runs the locked environment outside Documents to avoid File Provider delays. If code files are still hydrating, extract the release ZIP into a nonsynchronized development directory and run the same commands. Use `--mode replay --db runtime/new-replay.sqlite` to create a separate, offline demo. Database files persist across restart. Choose a fresh name for reset; no destructive reset is needed. The case snapshot digest detects corrupt or modified payloads.

## Live provider checks

**Sandbox refresh** requires the private file already provisioned at `~/.config/uptime/ramp-sandbox.json` with the exact demo API origin. Never copy its contents into the repository, screen recording, model input or chat.

```sh
RAMP_ENV=sandbox uv run --locked python scripts/ramp_probe.py
```

Refresh overwrites the minimized observation with fresh read proof only. Inspect its capture date before the demo. The default web process never makes a Ramp write. The separate draft harness validates exact grants, pins the sandbox hostname, journals its own unique tag and verifies the same provider object. **Do not run the draft option on the current grant.** No real create/update was possible. There is no vendor-credit creation API integration. For an actual signed-in UI cross-check, open the official Ramp sandbox separately and locate the bill by its ID in `fixtures/ramp/verified.json`.

**Public status refresh** is explicit and retains minimized provenance. To inspect a new snapshot without changing the pinned fallback:

```sh
mkdir -p runtime
uv run --locked python -m uptime.evidence_refresh --live --output runtime/twilio-status.json
```

**Model replay** works without an authenticated model. To refresh the curated public Twilio plan, use `uv run --locked python scripts/refresh_model.py`. This uses Claude Code and may consume account usage. The public Atlassian acquisition additionally requires `pdftotext`. Use `uv run --locked python -m uptime.onboarding_extract > runtime/atlassian-proposal.json` to stage a new proposal. It does not approve or activate anything. Changed source text requires review before transmission. Review the extraction, version and held-out tests before adopting a new snapshot.

## Rehearsal and film

`scripts/rehearse.py` creates a temporary replay database, performs the three dispute outcomes plus partial award, posts and partially applies the cured award, restarts the workbench and exercises shadow → approved → active → rolled back with a scripted reviewer. It deletes only its own temporary workspace. Financial outcomes are identical on repeated runs; real audit wall-clock timestamps are not promised byte-identical.

For the narrated-by-captions visual sequence, see [filming instructions](../demo/filming.md). The output contains seventeen timed, authentic browser states. System Chrome, Playwright, FFmpeg and ffprobe are needed to regenerate it. The existing MP4 plays without any software installation or internet. The recording uses an offline database and contains no Ramp client credentials or production records.

## Deployment

For the supported private deployment, install the checkout and locked runtime on one machine under a dedicated local user, give only that user access to its runtime directory, and run one server process. Use `--mode replay` for judging without secrets or `--mode sandbox` for the saved provider evidence. Keep the default loopback host. A private remote presenter can tunnel the same loopback port over SSH; open the generated bootstrap link privately at the corresponding forwarded local address. Stop the process and close the SSH tunnel when the demo ends. Do not expose this capability-token service on a public interface. No production service was deployed.

A production deployment would require reviewed IdP/RBAC, TLS, customer authorization and signed contract/evidence ingestion, isolated tenant storage, immutable audit retention, external transport review, durable queue/idempotency and operational monitoring. These are separate release gates.

## Resume orchestration

Run `sh scripts/resume-orchestration.sh` from the checkout. It rebuilds the pinned environment, runs tests and the offline business path, checks Git status and points to the durable board. To resume with a coding agent, supply the repository and request: “Read STATUS.md, TASKS.md, BLOCKERS.md and the current ADR index, verify the suite, then take the next permitted task.” There is no unattended permanent worker. A shell server or coding agent must be restarted after its hosting session ends.
