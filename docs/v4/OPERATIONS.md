# Run, deploy and resume

Run these commands from the Uptime V4 checkout. Use Python 3.11 or later, uv, and Node for the web tests. The actual browser acceptance run also needs Chromium or Google Chrome. Rendering the film needs ffmpeg and ffprobe. The repository is a single-host local deployment. Never expose its listener through a public proxy.

## Open the application

For the current authored Northwind walkthrough, use [the isolated workspace procedure](NORTHWIND-WORKFLOW.md). Its default port is 8776 and its generated reviewer credential belongs only to that private workspace. Keep it separate from the connected Ramp database and credentials described below. `--resume` preserves state; a fresh directory starts a new run. The [two-minute script](DEMO.md#current-northwind-walkthrough) and readback receipts describe what was actually demonstrated.

On macOS run `./Open\ Uptime.command`. It provisions a local view-only key on first launch, uses a private application database, and opens the loopback sign-in page. Sign in as `ramp.viewer` and select `~/.config/uptime/ramp-worklist-viewer.json`. In the macOS file chooser press Command-Shift-G to enter that path. Close the server with Control-C. The viewer can inspect the worklist, evidence and history. Its key carries no reviewer or financial authority.

For a separate named installation:

```sh
umask 077
uv sync --locked
mkdir -p "$HOME/.config/uptime" "$HOME/.local/share/uptime"
uptime_db="$HOME/.local/share/uptime/workbench-sandbox.sqlite"
uv run --locked python scripts/serve.py --mode sandbox --db "$uptime_db" \
  --enroll analyst.one --role viewer --credential-file "$HOME/.config/uptime/analyst-one.json"
uv run --locked python scripts/serve.py --mode sandbox --db "$uptime_db" --open
```

Keep exactly the same mode, tenant and database on subsequent launches. Enrollment is an offline operator action. Existing accounts or keys cannot be overwritten. Select a new absolute credential filename when deliberately provisioning a new account. Browser authentication uses origin-bound proof of possession. A replay server needs its own database and separate enrollment.

## Install current sandbox observations

The operator's `~/.config/uptime/ramp-sandbox.json` must be owner-readable only and contain the documented sandbox configuration. The importer does no financial writes. A fresh database starts with a clearly labeled packaged historical read available to the demonstration tenant. A refresh replaces its display with the installed business observation.

```sh
umask 077
export RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com
uv run --locked python scripts/ramp_refresh_workspace.py \
  --db "$HOME/.local/share/uptime/workbench-sandbox.sqlite" \
  --all-purchase-orders --page-size 20 --max-pages 2 --detail-limit 12
```

Use the same local database in the launcher. Larger page budgets trade more provider requests for wider coverage. If a list is truncated, its row count is a sample. Changing the capture invalidates previously signed price evidence and the constructed demonstration cap. The film and replay preserve their original observation.

To inspect app grants, run `python scripts/ramp_capabilities.py --output /private/operator/path/grants.json` in the locked environment. The command records scope and read status without credentials. A sandbox administrator must check allowed scopes, update the app if permitted and obtain a fresh token. The effective grant and exact object read-back are authoritative. Bill comments require `bills:write`, procurement metadata separately requires an entitled configured Blank Canvas step and `blank_canvas:write`. Do not use user CLI credentials to route around an app refusal. [Native operator runbook](NATIVE-OPERATOR.md) · [Ramp configuration](https://support.ramp.com/accessing-the-developer-api)

Private agreement evidence never belongs in the repository. To enable an actual typed pricing review, use `scripts/ramp_bind_terms.py` and its externally held finance verifier. For verified vendor awards use `scripts/ramp_match_award.py` and configure `--award-office` with the same installation's protected key scopes. [Price operator procedure](RAMP-PRICE-EVIDENCE.md) · [Award operator procedure](RAMP-ATTRIBUTION.md)

## Reproduce the evidence

```sh
uv run --locked pytest -q
node --test web/*.test.cjs
uv run --locked python scripts/rehearse.py
uv run --locked python scripts/rehearse_vendor.py --help
uv run --locked python scripts/film_ramp_v4.py --browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --output /tmp/uptime-v4-new-film
```

Select a new empty directory for filming. The scripted reviewer, vendor and payment application in this film are synthetic. For baseline comparisons with provenance, run `scripts/v4_audit_gate.py` in both phases following its exact usage. Private independent blind inputs stay with their custodian. Use the input-only projection and a fresh receipt path, then compare the sealed observations against frozen gold. The prospectively selected contracts, received model outputs and refusals must each retain their original evaluator and attempt classification. [Audit protocol](QA-design.md) · [Demo](DEMO.md)

Check `docs/v4/checkpoints.jsonl`, the latest source commit and `docs/v4/STATUS.md` before restarting work. Restart the local process explicitly after an environment shutdown. A Git checkout alone cannot restore an uncommitted worktree, an in-flight remote model session, a private operator database or an external role grant.
