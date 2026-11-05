#!/bin/zsh
set -eu
umask 077
cd "$(dirname "$0")"
if command -v uv >/dev/null 2>&1; then
  uptime_uv=$(command -v uv)
elif [ -x "$HOME/.local/bin/uv" ]; then
  uptime_uv="$HOME/.local/bin/uv"
elif [ -x "/opt/homebrew/bin/uv" ]; then
  uptime_uv=/opt/homebrew/bin/uv
else
  printf '%s\n' 'Install uv, then reopen this launcher. See docs/v4/OPERATIONS.md.'
  exit 1
fi
uptime_db=${UPTIME_WORKSPACE_DB:-"$HOME/.local/share/uptime/workbench-sandbox.sqlite"}
uptime_viewer=${UPTIME_VIEWER_KEY:-"$HOME/.config/uptime/ramp-worklist-viewer.json"}
mkdir -p -- "$(dirname "$uptime_db")" "$(dirname "$uptime_viewer")"
if [[ ! -e "$uptime_viewer" ]]; then
  "$uptime_uv" run --locked python scripts/serve.py --mode sandbox --db "$uptime_db" \
    --enroll ramp.viewer --role viewer --credential-file "$uptime_viewer"
fi
printf 'Sign in as ramp.viewer. Select this private viewer file in the local page:\n%s\n' "$uptime_viewer"
printf '%s\n' 'On macOS press Command-Shift-G in the file chooser to enter its path.'
printf '%s\n' 'Stop the local server with Control-C. Refresh provider reads separately using docs/v4/OPERATIONS.md.'
exec "$uptime_uv" run --locked python scripts/serve.py --mode sandbox --db "$uptime_db" --open
