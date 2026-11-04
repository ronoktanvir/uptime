#!/bin/zsh
set -eu
cd "$(dirname "$0")"
umask 077
if ! command -v uv >/dev/null; then
  echo 'Install uv first, then run this launcher again. See docs/orchestration/RUNBOOK.md.'
  exit 1
fi
env_dir=$(mktemp -d "${TMPDIR:-/tmp}/uptime-launch-env.XXXXXX")
trap 'rm -rf -- "$env_dir"' EXIT
export UV_PROJECT_ENVIRONMENT="$env_dir/venv"
uv run --locked python scripts/serve.py --mode sandbox --open
