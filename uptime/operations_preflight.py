"""Read-only readiness check for the local demo machine (D11: stay local).

It changes no database and contacts no provider. Its only host probes are
listing listening sockets (``lsof``), listing process *names* (``ps``) and
reading free disk space. It never reads process arguments, environment
secrets or credential contents, so a token on a command line cannot reach
the report.

Findings use the health-check levels: ATTENTION needs an operator before the
demo; INFO is context.
"""
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys

from .operations_health import check as health_check, config_custody
from .ramp import ORIGIN as RAMP_SANDBOX_ORIGIN
from .workspace_recovery import MANIFEST, RecoveryError, read_only, verify

SCHEMA = "uptime-operations-preflight/1"
MIN_FREE_BYTES = 2 * 1024 ** 3
BACKUP_MAX_AGE = timedelta(hours=24)
# Public tunnelling clients. Names only; the arguments are never read.
TUNNEL_NAMES = {"ngrok", "cloudflared", "localtunnel", "lt", "bore", "frpc", "zrok", "pinggy", "expose"}
LOOPBACK = {"127.0.0.1", "[::1]", "localhost"}


def _listeners():
    """(command, address, port) for every TCP listener, from lsof's NAME column."""
    try:
        out = subprocess.run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "cn"], capture_output=True,
                             text=True, timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_lsof(out)


def parse_lsof(output):
    rows, command = [], None
    for line in output.splitlines():
        if line.startswith("c"):
            command = line[1:]
        elif line.startswith("n"):
            match = re.fullmatch(r"(.+):(\d+)", line[1:])
            if match:
                rows.append((command or "?", match.group(1), int(match.group(2))))
    return rows


def _process_names():
    try:
        out = subprocess.run(["ps", "-axo", "comm="], capture_output=True, text=True, timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [Path(line.strip()).name for line in out.splitlines() if line.strip()]


def _backups(folder):
    """Valid-looking backup directories directly under ``folder`` (not verified yet)."""
    try:
        return [p for p in Path(folder).iterdir() if p.is_dir() and not p.is_symlink() and (p / MANIFEST).is_file()]
    except OSError:
        return []


def _binding(path):
    try:
        db = read_only(path)
        try:
            row = db.execute("SELECT mode,rehearsal,tenant FROM authority_workspace WHERE id=1").fetchone()
            realm = db.execute("SELECT realm FROM mandate_workspace WHERE id=1").fetchone() if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='mandate_workspace'").fetchone() else None
        finally:
            db.close()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return {"mode": row[0], "rehearsal": bool(row[1]), "tenant": row[2],
            "realm_sha256": sha256(realm[0].encode()).hexdigest() if realm else None}


def check(workspaces, *, ports=(), backup_dir=None, config_files=(), now=None, environ=None,
          listeners=_listeners, processes=_process_names, disk_usage=shutil.disk_usage):
    now = (now or datetime.now(UTC)).astimezone(UTC)
    environ = os.environ if environ is None else environ
    findings = []

    def note(level, code, detail, **extra):
        findings.append(dict(level=level, code=code, detail=detail, **extra))

    report = {"schema": SCHEMA, "checked_at": now.isoformat(), "python": ".".join(map(str, sys.version_info[:3])),
              "uv": bool(shutil.which("uv")), "provider_requests": 0, "writes": 0}

    # Disk: SQLite writes and test temp trees need headroom; the shared volume has filled before.
    volumes = {}
    for path in [*workspaces, *([backup_dir] if backup_dir else [])]:
        anchor = Path(path) if Path(path).is_dir() else Path(path).parent
        try:
            free = disk_usage(anchor).free
        except OSError:
            continue
        volumes[str(anchor)] = free
        if free < MIN_FREE_BYTES:
            note("ATTENTION", "DISK_LOW", "Less than 2 GiB free near a demo workspace or backup folder.",
                 path=str(anchor), free_bytes=free)
    report["free_bytes"] = volumes

    # Ramp environment: only the sandbox origin is ever acceptable on this machine.
    ramp_env, base = environ.get("RAMP_ENV"), environ.get("RAMP_BASE_URL")
    report["ramp_environment"] = {"RAMP_ENV": ramp_env, "RAMP_BASE_URL": base}
    if ramp_env not in (None, "sandbox") or base not in (None, RAMP_SANDBOX_ORIGIN):
        note("ATTENTION", "RAMP_ENV_NOT_SANDBOX", "RAMP_ENV must be sandbox and RAMP_BASE_URL the demo API origin.")

    # Nothing hosted or tunnelled.
    names = processes()
    if names is None:
        note("ATTENTION", "PROCESS_LIST_UNAVAILABLE", "Could not list process names to rule out a public tunnel.")
    else:
        running = sorted({n for n in names if n.lower() in TUNNEL_NAMES})
        if running:
            note("ATTENTION", "TUNNEL_PROCESS_RUNNING",
                 "A public tunnelling client is running; D11 keeps this deliverable local. Stop it before the demo.",
                 processes=running)

    rows = listeners() if ports else []
    if ports and rows is None:
        note("ATTENTION", "LISTENERS_UNAVAILABLE", "Could not list listening sockets.")
        rows = []
    report["ports"] = {}
    for port in ports:
        bound = sorted({address for _, address, p in rows if p == port})
        exposed = [a for a in bound if a not in LOOPBACK]
        report["ports"][str(port)] = {"listening": bool(bound), "addresses": bound}
        if exposed:
            note("ATTENTION", "LISTENER_NOT_LOOPBACK",
                 "A demo port accepts connections beyond this machine; restart it bound to 127.0.0.1.",
                 port=port, addresses=exposed)
        elif not bound:
            note("INFO", "PORT_NOT_LISTENING", "Nothing is serving this demo port yet.", port=port)

    backups = []
    if backup_dir is not None:
        for folder in _backups(backup_dir):
            try:
                manifest = json.loads((folder / MANIFEST).read_text())
                backups.append((folder, manifest))
            except (OSError, ValueError):
                continue

    report["workspaces"] = []
    for path in workspaces:
        entry = {"path": str(path)}
        report["workspaces"].append(entry)
        if not Path(path).is_file():
            entry["status"] = "MISSING"
            note("ATTENTION", "WORKSPACE_MISSING", "Demo workspace database is unavailable.", path=str(path))
            continue
        try:
            health = health_check(Path(path), now=now)
        except (sqlite3.Error, OSError):
            entry["status"] = "UNREADABLE"
            note("ATTENTION", "WORKSPACE_UNREADABLE", "The workspace could not be read.", path=str(path))
            continue
        entry.update(status=health["status"], binding=health.get("binding"),
                     attention=[f["code"] for f in health["findings"] if f["level"] == "ATTENTION"])
        if health["status"] != "OK":
            note("ATTENTION", "WORKSPACE_HEALTH", "Run operations_check.py on this workspace for details.",
                 path=str(path), codes=entry["attention"])
        if backup_dir is None:
            continue
        binding = _binding(path)
        matching = sorted(((m.get("created_at", ""), f) for f, m in backups
                           if m.get("binding") == binding and m.get("source_name") == Path(path).name), reverse=True)
        if not matching:
            entry["backup"] = None
            note("ATTENTION", "BACKUP_MISSING", "No backup of this workspace exists in the backup folder.", path=str(path))
            continue
        created, folder = matching[0]
        try:
            verify(folder.resolve())
        except (RecoveryError, OSError, KeyError, TypeError, ValueError):
            entry["backup"] = {"folder": folder.name, "verified": False}
            note("ATTENTION", "BACKUP_INVALID", "The newest backup of this workspace failed verification.",
                 path=str(path), backup=folder.name)
            continue
        try:
            age = now - datetime.fromisoformat(created)
        except ValueError:
            age = None
        entry["backup"] = {"folder": folder.name, "verified": True, "created_at": created}
        if age is None or age > BACKUP_MAX_AGE:
            note("ATTENTION", "BACKUP_STALE", "The newest verified backup is older than 24 hours.",
                 path=str(path), backup=folder.name)

    if config_files:
        report["configuration"] = [{"path": str(p), "custody": config_custody(p)} for p in config_files]
        for item in report["configuration"]:
            if item["custody"] != "PROTECTED":
                note("ATTENTION", "CONFIGURATION_CUSTODY", f"{item['path']}: {item['custody']}")

    report["findings"] = findings
    report["status"] = "ATTENTION" if any(f["level"] == "ATTENTION" for f in findings) else "READY"
    return report
