#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
run_env=$(mktemp -d "${TMPDIR:-/tmp}/uptime-resume.XXXXXX")
trap 'rm -rf -- "$run_env"' EXIT
export UV_PROJECT_ENVIRONMENT="$run_env/venv"
uv sync --locked
UPTIME_QA_REQUIRE_SERVER=1 uv run --locked pytest -q
node --test web/*.test.cjs
uv run --locked python scripts/rehearse.py
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  uv run --locked python scripts/check_repo.py
  git status --short
fi
printf '\nSee docs/orchestration/STATUS.md, BLOCKERS.md and RUNBOOK.md for the next permitted action.\n'
