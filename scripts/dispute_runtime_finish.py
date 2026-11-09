"""Supplementary dispute runtime helpers, adapted from frozen evaluation86.

This additive module preserves the original runner. It performs no action on import.
Source-only scripted setup is composed separately; expected outcomes are never inputs.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

RUNNER = Path(__file__).resolve()
GOLD_PATTERN = re.compile(r'(expected|gold|oracle|answer)', re.I)


# --- canonical JSON / create-only storage -------------------------------

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(data):
    return sha256(data).hexdigest()


def protected_directory(path):
    """Create 0700, or validate an existing owned non-symlink 0700 directory."""
    path = Path(path)
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError(f'{path} is not an owned 0700 directory.')
    return path


def create_bytes(path, data):
    """Create-only 0600; atomic via link so an interrupted write never leaves the target."""
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix='.partial-')
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)  # raises FileExistsError: never overwrite
    finally:
        os.unlink(temporary)
    return digest(data)


def create_json(path, value):
    return create_bytes(path, canonical(value))


# --- byte pins ----------------------------------------------------------

def pin_files(paths):
    return {str(Path(p).resolve(strict=True)): digest(Path(p).read_bytes()) for p in paths}


def verify_pins(pins):
    drift = sorted(p for p, h in pins.items() if not Path(p).is_file() or digest(Path(p).read_bytes()) != h)
    if drift:
        raise ValueError(f'Pinned bytes changed: {drift}')
    return True


def _git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f'git {args[0]} failed: {result.stderr.decode(errors="replace")[:300]}')
    return result.stdout


def pin_current_code(root, base_commit):
    """Hash tracked uptime/ and web/ sources plus this runner; require core unchanged vs base."""
    root = Path(root).resolve(strict=True)
    tracked = [line for line in _git(root, 'ls-files', '-z', '--', 'uptime', 'web').decode().split('\0') if line]
    changed = _git(root, 'diff', '--name-only', base_commit, '--', 'uptime', 'web').decode().split()
    untracked = _git(root, 'status', '--porcelain', '--', 'uptime', 'web').decode().split('\n')
    if changed or any(line.strip() for line in untracked):
        raise ValueError(f'Core source differs from {base_commit}: {changed or untracked}')
    files = {name: digest((root / name).read_bytes()) for name in sorted(tracked)}
    return dict(base_commit=base_commit, head=_git(root, 'rev-parse', 'HEAD').decode().strip(),
                files=files, tree_sha256=digest(canonical(files)),
                runner=dict(path=str(RUNNER.relative_to(root)) if RUNNER.is_relative_to(root) else RUNNER.name,
                            sha256=digest(RUNNER.read_bytes())))


# --- guarded reads ------------------------------------------------------

def _resolved_regular(path):
    path = Path(path)
    if '..' in path.parts:
        raise PermissionError('Path traversal refused.')
    if any(Path(*path.parts[:i]).is_symlink() for i in range(1, len(path.parts) + 1)):
        raise PermissionError('Symlinked path refused.')
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise PermissionError('Not a regular file.')
    return resolved


def _read_logged(resolved, access_log, kind):
    data = resolved.read_bytes()
    access_log.append(dict(kind=kind, path=str(resolved), sha256=digest(data)))
    return data


def read_public_json(path, allowed_paths, access_log):
    """Only exact, explicitly frozen, resolved public source paths."""
    resolved = _resolved_regular(path)
    allowed = {Path(p).resolve(strict=True) for p in allowed_paths}
    # Name and nearest two directories: avoids matching unrelated ancestors (e.g. temp roots).
    if any(GOLD_PATTERN.search(part) for part in resolved.parts[-3:]):
        raise PermissionError('Expected/gold material is never a public input.')
    if resolved not in allowed:
        raise PermissionError('Path is not an explicitly frozen public source.')
    return json.loads(_read_logged(resolved, access_log, 'public'))


def read_gold(path, *, gold_paths, case_ids, attempt_root, access_log):
    """Gold access only after every declared case has a terminal result."""
    assert_all_terminal(case_ids, attempt_root)
    resolved = _resolved_regular(path)
    if resolved not in {Path(p).resolve(strict=True) for p in gold_paths}:
        raise PermissionError('Not a declared gold path.')
    return json.loads(_read_logged(resolved, access_log, 'gold'))


# --- spooling subprocess (same signature as transport.bounded_run + folder) ---

def spool_run(argv, *, payload=b'', cwd, env, timeout=60, limit=300000, folder):
    """Stream actual stdout/stderr into create-only 0600 files from startup.

    Same timeout/output cap/process-group cleanup as bounded_run. On failure
    partial bytes stay on disk and termination.json records the reason.
    Returns actual (code, stdout, stderr); nothing is normalized.
    """
    folder = Path(folder)
    started = time.monotonic()
    out_path, err_path = folder / 'provider.stdout', folder / 'provider.stderr'
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    out_fd, err_fd = os.open(out_path, flags, 0o600), None
    reason, process = None, None
    try:
        err_fd = os.open(err_path, flags, 0o600)
        with tempfile.TemporaryFile() as incoming:
            incoming.write(payload)
            incoming.seek(0)
            process = subprocess.Popen(argv, stdin=incoming, stdout=out_fd, stderr=err_fd,
                                       cwd=cwd, env=env, start_new_session=True)
        create_json(folder / 'process-start.json', dict(pid=process.pid, timeout_seconds=timeout,
                                                         output_limit_bytes=limit, attempt=1))
        while True:
            if out_path.stat().st_size + err_path.stat().st_size > limit:
                reason = 'OUTPUT_LIMIT'
                raise ValueError('Public provider output exceeded its byte limit; partial output retained.')
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                reason = 'TIMEOUT'
                raise TimeoutError('Public provider timed out; partial output retained; no retry.')
            try:
                code = process.wait(timeout=min(.05, remaining))
                break
            except subprocess.TimeoutExpired:
                pass
        if out_path.stat().st_size + err_path.stat().st_size > limit:
            reason = 'OUTPUT_LIMIT'
            raise ValueError('Public provider output exceeded its byte limit; partial output retained.')
    except BaseException as error:
        reason = reason or type(error).__name__
        raise
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        for fd in (out_fd, err_fd):
            if fd is not None:
                os.close(fd)
        if reason is not None:
            create_json(folder / 'termination.json', dict(
                reason=reason, returncode=None if process is None else process.returncode,
                stdout=_file_meta(out_path), stderr=_file_meta(err_path)))
    return code, out_path.read_bytes(), err_path.read_bytes()


def _file_meta(path):
    if not path.exists():
        return None
    data = path.read_bytes()
    return dict(bytes=len(data), sha256=digest(data))


# --- composition wrapper around SafePublicClaude --------------------------

_ACTIVE = threading.Lock()


class SpooledPublicClaude:
    """Delegates to SafePublicClaude; only transport.bounded_run is swapped, per call.

    The inner transport keeps all identity/empty-tools/MCP/profile checks.
    One frozen request, one marker, one active call per process, no retry.
    """

    def __init__(self, inner, *, request_sha256, folder):
        self.inner, self.request_sha256, self.folder = inner, request_sha256, Path(folder)

    @property
    def profile(self):
        return self.inner.profile

    @property
    def last_receipt(self):
        return self.inner.last_receipt

    def __call__(self, request):
        from uptime import correspondence_model_transport as transport
        if digest(request) != self.request_sha256:
            raise ValueError('Request differs from the frozen request digest.')
        protected_directory(self.folder)
        create_json(self.folder / 'call.marker', dict(request_sha256=self.request_sha256))  # once only
        if not _ACTIVE.acquire(blocking=False):
            raise RuntimeError('Another spooled inference call is active.')
        original = transport.bounded_run
        try:
            def spooled(argv, *, payload=b'', cwd, env, timeout=60, limit=300000):
                return spool_run(argv, payload=payload, cwd=cwd, env=env, timeout=timeout,
                                 limit=limit, folder=self.folder)
            transport.bounded_run = spooled
            try:
                result = self.inner(request)
            except Exception as error:
                create_json(self.folder / 'call-result.json', dict(
                    status='FAILED', error=type(error).__name__, message=str(error)[:500],
                    receipt=self.inner.last_receipt))
                raise
            create_json(self.folder / 'call-result.json', dict(status='RETURNED', result=result))
            return result
        finally:
            transport.bounded_run = original
            _ACTIVE.release()


# --- signed job dispatch ----------------------------------------------------

def _json(response):
    return response.status_code, response.json()


def dispatch_model_job(client, base_url, *, expected_context_digest, frozen_request,
                       expected_request_sha256, pinned_blind, read_state, folder,
                       poll_seconds=120, poll_interval=.25, drain=None, read_job=None):
    """Signed POST /interpretation/model-jobs at most once for a pinned, approved UNKNOWN.

    ``client`` is an existing signed client: get(url)->response, post(url, body)->response.
    ``read_state`` returns the signed ledger/submissions state (recorded, not acted on).
    No prepare/approve/submit is performed. The candidate is saved as served.

    Harness lessons (gent8 c1fa513): the poll bound (default 120s) exceeds the provider bound
    (10s help + 10s version + 60s call). After polling, ``drain()`` (for example lifespan
    shutdown) lets the job pool finish before the snapshot, and ``read_job(job_id)`` records the
    server's own terminal state separately from what the poll saw. Neither ever re-dispatches.
    """
    folder = protected_directory(folder)
    base = base_url.rstrip('/') + '/interpretation'
    status, view = _json(client.get(base))
    model_job = (view or {}).get('model_job') or {}
    exported = model_job.get('approval_request') or {}
    checks = dict(
        context=(view or {}).get('context', {}).get('digest') == expected_context_digest,
        approval_context=exported.get('context_sha256') == expected_context_digest,
        request=('request' in exported and canonical(exported['request']) == canonical(frozen_request)),
        request_sha256=model_job.get('request_sha256') == expected_request_sha256,
        can_request=model_job.get('can_request') is True,
        own_blind=((view or {}).get('blind_entry') is not None
                   and canonical(view['blind_entry']) == canonical(pinned_blind)))
    if status != 200 or not all(checks.values()):
        record = dict(outcome='NOT_DISPATCHED', http_status=status, checks=checks,
                      reason=model_job.get('reason'), model_calls=0)
        create_json(folder / 'dispatch.json', record)
        return record
    before = read_state()
    create_json(folder / 'dispatch.marker', dict(context=expected_context_digest, request=expected_request_sha256))
    post_status, job = _json(client.post(base + '/model-jobs', {'context_digest': expected_context_digest}))
    job = job if isinstance(job, dict) else {'body': job}
    polls, deadline = [], time.monotonic() + poll_seconds
    while post_status == 200 and job.get('id'):
        _, polled = _json(client.get(base + '/model-jobs/' + job['id']))
        job = polled if isinstance(polled, dict) else {'id': job['id'], 'body': polled}
        polls.append(job.get('state'))
        if job.get('terminal') or time.monotonic() >= deadline:
            break
        time.sleep(poll_interval)
    poll_deadline_reached = bool(polls) and not job.get('terminal')
    final_status, final_view = _json(client.get(base))
    after = read_state()
    server_job = None
    if drain is not None:
        drain()
    if read_job is not None and job.get('id'):
        try:
            server_job = read_job(job['id'])
        except Exception as error:  # recorded, never retried
            server_job = dict(read_error=type(error).__name__)
    candidates = ((final_view or {}).get('candidates') or []) if final_status == 200 else []
    matching = [c for c in candidates
                if (c.get('provenance') or {}).get('request_sha256') == expected_request_sha256]
    verified = (post_status == 200 and job.get('state') == 'SUCCEEDED' and job.get('terminal') is True
                and job.get('request_sha256') == expected_request_sha256
                and job.get('context_digest') == expected_context_digest and len(matching) == 1)
    record = dict(outcome='CANDIDATE_RECORDED' if verified else 'NO_VERIFIED_CANDIDATE',
                  post_status=post_status, job=job, poll_states=polls, final_view_status=final_status,
                  candidates=candidates, verified_candidate=matching[0] if verified else None,
                  state_unchanged=canonical(before) == canonical(after),
                  state_before_sha256=digest(canonical(before)), state_after_sha256=digest(canonical(after)),
                  poll_deadline_reached=poll_deadline_reached, server_terminal=server_job)
    create_json(folder / 'dispatch.json', record)
    return record


