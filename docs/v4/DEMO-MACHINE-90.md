# Demo machine: readiness, backup and recovery

**Scope, November 9, 2026:** D11 is decided as *stay local for now*. Every demo process runs on this Mac, bound to `127.0.0.1`, with no tunnel and no hosting. This page covers making the machine ready and recovering it if something breaks. **What to show and say** is in W8's [demo](DEMO.md) and [person-operated path](DEMO-PATH-87.md). Commands below are read-only unless marked *writes*.

## Processes and their state

| Process | Port | State on disk | How to reset or recover |
| --- | --- | --- | --- |
| Northwind walkthrough (`setup_northwind.py --serve`) | 8776 | One directory: `workspace.db`, a separate `local-ledger.db` and authored inputs | **Start a new directory** with `setup_northwind.py`, or restart the same one with `--resume`. Do not restore `workspace.db` alone: the local ledger is a separate file and would no longer match. |
| CalyxQuay review session | 8777 | Its own `workspace.db` | Restart the same command. Do not change its review state for the demo. |
| Progress map (`serve_progress.py`) | 8780 | Read-only view of the checkout | Restart the same command. |
| Sandbox workbench (`serve.py --mode sandbox`), if shown | 8765 by default | One workspace database | Back up and restore with `workspace_recovery.py` (below). |

Every restart ends all sign-in sessions, which is by design. Presenters sign in again with their own key file; never paste a key into chat.

## Night before

1. On the checkout you will present from, run `git pull`, then `uv sync --locked`. Full suites go through the integration owner (`agent0`), one at a time. Do not start one on the demo machine.
2. Keep at least 2 GiB free on the data volume. If space is short, `uv cache prune` is the safe first step. Never delete other workspaces or worktrees to make room.
3. Back up each workspace that will be shown (*writes a new folder only*):

   ```sh
   umask 077; mkdir -p "$HOME/.local/share/uptime-backups"; chmod 700 "$HOME/.local/share/uptime-backups"
   uv run --locked python scripts/workspace_recovery.py backup --db <workspace.db> \
     --output "$HOME/.local/share/uptime-backups/<name>-$(date -u +%Y%m%dT%H%M%SZ)"
   ```

   For the sandbox workbench, refresh first so the capture is current. The refresh only reads:

   ```sh
   RAMP_ENV=sandbox RAMP_BASE_URL=https://demo-api.ramp.com \
     uv run --locked python scripts/ramp_refresh_workspace.py --db <sandbox.db> --attempts 2
   ```

4. Run the preflight (below) and resolve every `ATTENTION` finding.

## 30 minutes before

```sh
uv run --locked python scripts/operations_preflight.py \
  --workspace <northwind>/workspace.db --workspace <review>/workspace.db [--workspace <sandbox.db>] \
  --port 8776 --port 8777 --port 8780 \
  --backup-dir "$HOME/.local/share/uptime-backups" \
  [--config "$HOME/.config/uptime/ramp-sandbox.json"]
```

Exit `0` means READY and `2` means ATTENTION. The preflight checks:
- free disk;
- that `RAMP_ENV` and `RAMP_BASE_URL` are sandbox-only;
- that no public tunnelling client is running (it reads process names, not arguments);
- that each port listens on loopback only;
- the health of each workspace;
- a verified backup under 24 hours old, matched by exact workspace binding;
- the custody of credential files, without reading their contents.

A `PORT_NOT_LISTENING` INFO entry only means that server hasn't been started yet.

On the sandbox workspace, `operations_check.py` gives detail:
- `RAMP_CAPTURE_NEAR_LIMIT` or `RAMP_CAPTURE_STALE`: rerun the refresh.
- `CLOCK_BEHIND_CAPTURE`: fix the system clock.
- `CLAIM_DEADLINE_APPROACHING`: mention it; nothing is filed automatically.

A read-only preflight run on this machine at 04:30 PST on November 9 returned READY:
- 8777 and 8780 were listening on `127.0.0.1` only.
- 8776 was not yet serving.
- The prepared Northwind workspace was healthy and unchanged.

A backup → verify → restore drill on that workspace's copy also passed (45 tables, case history verified). The restored copy was correctly marked as awaiting reconciliation.

## If something breaks during the demo

| Symptom | Do this | Say this |
| --- | --- | --- |
| A page stops responding or the server exits | Restart the same command (Northwind: same `--directory` with `--resume`). Sign in again. | "Restarting ends sessions by design; the recorded state is unchanged." |
| The Northwind state is wrong or half-finished | Start a **new** directory with `setup_northwind.py --serve`. If time is short, use W8's saved fallback screen and socket receipt. | "This is a fresh authored workspace." |
| The sandbox workbench database is damaged | `workspace_recovery.py restore --backup <folder> --target <new.sqlite> --tenant <tenant> --mode sandbox --previous <old.sqlite if readable>`, then serve with `--db <new.sqlite>`. | "Restored from last night's verified backup; native actions stay blocked until we reconcile." |
| The Ramp sandbox is unreachable | Nothing. The last capture stays, with its `as_of` time. | "Ramp is unreachable; this is the capture from \<time\>." |
| The disk is full | Stop the demo processes, run `uv cache prune`, then restart. | — |

After a restore, run `workspace_recovery.py acknowledge` only once a person has actually checked the Ramp bill threads and vendor channels for anything done after the backup. Native posting stays blocked regardless (D02 and the execution-policy rejection). Restoring never unblocks it.

## Do not claim

- That a backup is tamper-proof. It carries a checksum, not a signature.
- That uninstall or revocation called Ramp. It is a local refusal; disabling the Ramp app is a Ramp-admin action.
- That any of this is a hosted or customer installation. That is designed, not built (D11).
- That a Northwind award or credit application is money recovered in Ramp. It is the local ledger.

Related: [operations runbook](OPERATIONS-RECOVERY-90.md) · [customer installation design](CUSTOMER-INSTALLATION-DESIGN.md) · [ADR 96](decisions/ADR-0096-operations-recovery.md)
