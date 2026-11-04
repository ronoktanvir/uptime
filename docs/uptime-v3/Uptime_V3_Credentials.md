# Uptime V3 — Secure Ramp sandbox credential setup (macOS)

**Never paste keys into ChatGPT, Claude, GitHub, logs, screenshots or an agent prompt.** Use only *sandbox* credentials from a Ramp developer app and verify the API URL is `https://demo-api.ramp.com` (not the production host). The Ramp UI is `https://demo.ramp.com`.

## Recommended local development: private JSON outside the repository

Run the following in your **Mac Terminal**. It prompts without echoing credentials, writes outside the project, and makes the directory and file accessible only to your user account:

```bash
umask 077
mkdir -p "$HOME/.config/uptime"
chmod 700 "$HOME/.config/uptime"
python3 - <<'PY'
from getpass import getpass
from pathlib import Path
import json, os
path = Path.home() / '.config' / 'uptime' / 'ramp-sandbox.json'
client_id = getpass('Ramp sandbox CLIENT ID (input hidden): ').strip()
client_secret = getpass('Ramp sandbox CLIENT SECRET (input hidden): ').strip()
if not client_id or not client_secret:
    raise SystemExit('Both credentials are required; nothing saved.')
payload = {'base_url': 'https://demo-api.ramp.com',
           'client_id': client_id, 'client_secret': client_secret}
with path.open('w', encoding='utf-8', opener=lambda p, flags: os.open(p, flags, 0o600)) as file:
    json.dump(payload, file)
path.chmod(0o600)
print('Saved sandbox credentials to', path, '(contents not displayed).')
PY
stat -f '%Sp %N' "$HOME/.config/uptime/ramp-sandbox.json"
```

**Note:** This is a private file protected by macOS user filesystem permissions, not encrypted-at-rest secret management. For longer-term production deployments, use a proper secret manager/Keychain and scoped service accounts. Do not sync this file to Git or cloud storage.

## Loading credentials into a local backend process

In the backend, read the JSON file with Python (the agent should implement this only for local development):

```python
from pathlib import Path
import json
creds = json.loads((Path.home() / '.config/uptime/ramp-sandbox.json').read_text())
assert creds['base_url'] == 'https://demo-api.ramp.com'
# Use creds only in a server-side HTTP client. Never log or send them to browser code.
```

Or explicitly export variables in a *single trusted terminal session* (avoid `set -x`, printing or `env | grep` on secrets):

```bash
export RAMP_ENV=sandbox
export RAMP_BASE_URL=https://demo-api.ramp.com
export RAMP_CLIENT_ID="$(python3 -c 'import json,pathlib;print(json.loads((pathlib.Path.home()/".config/uptime/ramp-sandbox.json").read_text())["client_id"])')"
export RAMP_CLIENT_SECRET="$(python3 -c 'import json,pathlib;print(json.loads((pathlib.Path.home()/".config/uptime/ramp-sandbox.json").read_text())["client_secret"])')"
# Start the backend process IN THIS TERMINAL; unset variables when finished:
# unset RAMP_CLIENT_ID RAMP_CLIENT_SECRET
```

`export`ed secrets can be inherited by child processes. Prefer direct file loading into the backend and limit which workers/processes can read the credential file. **Do not store credentials inside a repo `.env` or attach them to a chat.**

## What to ask the Ramp sandbox administrator for

Ask for a **sandbox** developer application's Client ID / Client Secret with least-privilege scopes needed for the demo (for example `vendors:read`, `bills:read`, and, only if specifically testing draft bill creation, `bills:write`; check the current official scope catalog before enabling). Do not request unrelated payroll, bank-account or card-vault scopes. It may also require business admin privileges to create the app.

Ramp uses a Client Credentials token exchange with HTTP Basic Auth at `/developer/v1/token` and an explicit `scope` request; the agent should implement and test token acquisition securely on the backend without echoing it. Do not assume the presence of a vendor credit create endpoint. Use existing Ramp sandbox UI for credit entry if possible, otherwise a clearly labeled simulation.

## Important Codex/local-vs-remote limitation

A file saved in your **Mac's** `~/.config/uptime` is readable only by processes running on that Mac with your user access. A remote Codex/Work cloud environment **cannot automatically read it**. If your agent is remote, use its approved secrets-injection mechanism. Do not paste the secret into the Codex chat. The orchestrator must confirm its execution environment and, if needed, explain exactly which secure secrets interface to use.

## Claude Opus 5.5 access

Try your *already-authenticated* local Claude Code installation first:

```bash
command -v claude
claude --version
claude --help
# A minimal, non-sensitive model smoke test in an authenticated environment:
claude -p 'Respond with only OPUS_READY' --model claude-opus-5-5
```

This test checks a *real invocation*. Running it may incur usage. If not authenticated or the model is unavailable to your plan, use an authorized Anthropic API key through the same secure secret mechanism or note a blocker. No fake Opus review is acceptable.

References: https://docs.ramp.com/developer-api/v1/guides/getting-started ; https://docs.ramp.com/developer-api/v1/scopes ; https://platform.claude.com/docs/en/models/opus-5-5/overview
