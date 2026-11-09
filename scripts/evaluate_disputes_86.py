"""Phase 86 dispute evaluation runner infrastructure (not a completed evaluation).

Infrastructure only: no setup facts, semantic labels, or score schema are
invented here. The parent wires native setup, pins blind entries
(SCRIPTED_NOT_ACTUAL_HUMAN), and finishes CLI glue after corpus freeze.
Nothing in this module reads expected/gold material on import.
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


# --- outcomes ------------------------------------------------------------------

def parser_outcome(*, source_text, runtime_case, parsed):
    """Recognized reply: recorded unchanged, zero model calls; route state untouched."""
    return dict(origin='deterministic_parser', model_calls=0, runtime_case=runtime_case,
                source_text=source_text, source_sha256=digest(source_text.encode('utf-8')), parsed=parsed)


def setup_gap(*, case_id, missing):
    return dict(outcome='SETUP_GAP', case_id=case_id, missing=sorted(missing), model_calls=0)


def write_result(attempt_root, case_id, value):
    folder = protected_directory(Path(attempt_root) / case_id)
    return create_json(folder / 'result.json', value)


def assert_all_terminal(case_ids, attempt_root):
    missing = []
    for case_id in case_ids:
        path = Path(attempt_root) / case_id / 'result.json'
        try:
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise ValueError
            json.loads(path.read_bytes())
        except (OSError, ValueError):
            missing.append(case_id)
    if missing or not case_ids:
        raise RuntimeError(f'Not all declared cases are terminal: {missing or "no cases declared"}')
    return True


def score(*_args, **_kwargs):
    raise NotImplementedError('Deferred until the sealed oracle schema exists; fields are not guessed.')


# --- offline per-case plan (agent3; no model, no server, no gold) ----------------

CORPUS_MANIFEST = 'docs/v4/evaluation84/manifest.json'
CORPUS_MANIFEST_SHA256 = '1b2ecd449c7eea2b6fe0bcaae9b58304a7bffa02579a43e246230cc09bcd8619'
READINGS_MANIFEST = 'docs/v4/evaluation86/blind-readings/manifest.json'
READINGS_MANIFEST_SHA256 = '5f1ab847b84f34daea5e4189edf4a3064044e0a1cfac3dcd7356423ca4deb831'
# Claim-scope fields as the public source states them. Nothing is derived, slugged or invented.
SOURCE_SCOPE = (('account', ('context', 'account')), ('vendor', ('vendor',)), ('contract', ('context', 'agreement')),
                ('service', ('context', 'product')), ('currency', ('context', 'currency')), ('month', ('context', 'month')))
NOT_STATED = ('component', 'incident', 'invoice', 'region')


def _pinned_bytes(root, relative, expected):
    data = (Path(root) / relative).read_bytes()
    if digest(data) != expected:
        raise ValueError(f'Pinned public input changed: {relative}')
    return data


def plan_cases(root):
    """Verify every pinned public input and map each frozen reading to its source; read no gold."""
    root = Path(root).resolve(strict=True)
    manifest = json.loads(_pinned_bytes(root, CORPUS_MANIFEST, CORPUS_MANIFEST_SHA256))
    files = {}
    for item in manifest['files']:
        data = _pinned_bytes(root, item['path'], item['sha256'])
        if len(data) != item['bytes']:
            raise ValueError(f'Pinned public input size changed: {item["path"]}')
        files[item['path']] = data
    families = {e['public_document']: e['id'] for e in manifest['entries'] if e['kind'] == 'onboarding'}
    readings = json.loads(_pinned_bytes(root, READINGS_MANIFEST, READINGS_MANIFEST_SHA256))
    if readings.get('gold_read') or readings.get('provider_results_seen') or readings.get('normal_runtime_outcomes_seen'):
        raise ValueError('Frozen readings must be source-only.')
    cases = []
    for entry in readings['readings']:
        reading_bytes = _pinned_bytes(root, entry['path'], entry['sha256'])
        reading = json.loads(reading_bytes)
        source_path = reading['public_source']
        if source_path not in files or digest(files[source_path]) != reading['source_file_sha256']:
            raise ValueError(f'Reading {entry["id"]} is not bound to a pinned public source.')
        source = json.loads(files[source_path])
        if digest(source['reply'].encode('utf-8')) != reading['reply_sha256']:
            raise ValueError(f'Reading {entry["id"]} reply digest differs.')
        context = source['context']
        stated = {}
        for field, keys in SOURCE_SCOPE:
            value = source
            for key in keys:
                value = value[key]
            stated[field] = value
        basis = context['claim_basis']
        cases.append(dict(
            id=entry['id'], public_source=source_path, source_sha256=reading['source_file_sha256'],
            reply_sha256=reading['reply_sha256'], reading=entry['path'], reading_sha256=entry['sha256'],
            stated_scope=stated, not_stated=[f for f in NOT_STATED if f not in stated],
            claim_basis_family=families.get(basis['document_path']), scenario_name=basis['scenario_name'],
            setup_only_inputs=[basis['document_path'], basis['customer_path']],
            filing=dict(context['filing']),
            model_request_excludes=['customer facts', 'claimed amount', 'scripted reading', 'contract facts', 'expected outcomes']))
    return dict(corpus_manifest_sha256=CORPUS_MANIFEST_SHA256, readings_manifest_sha256=READINGS_MANIFEST_SHA256,
                sealed_gold_root_opened=False, model_calls=0, cases=cases)


def intake_claim(client, *, case, claim_id, folder):
    """Ordinary claim intake with exactly the scope the public source states; never fills a field.

    A refusal is a zero-call setup outcome, recorded with the server's own response. It is
    never retried with derived, slugged or invented values.
    """
    folder = protected_directory(folder)
    request = dict(claim_id=claim_id, scope=dict(case['stated_scope']))
    status, response = _json(client.post('/api/correspondence/claims', request))
    record = dict(opaque_case_id=case['id'], phase='NATIVE_CLAIM_INTAKE', authority='SCRIPTED_NOT_ACTUAL_HUMAN',
                  source_file_sha256=case['source_sha256'], route='/api/correspondence/claims', request=request,
                  http_status=status, response=response, model_calls=0, financial_or_external_actions=0,
                  normalized_or_invented_scope_values=False, not_stated=list(case['not_stated']),
                  outcome='INTAKE_ACCEPTED' if status == 200 else 'SETUP_REFUSAL')
    create_json(folder / 'intake.json', record)
    return record


# --- D06 accept-denial views (gent8 prereg addendum, rule A; work/release-evaluation-gent8 1fdc2b5) ---

PREREG_DENIAL_ADDENDUM = 'docs/v4/evaluation-gent8/PREREG-ADDENDUM-DENIAL-ACCEPTANCE.md @ 1fdc2b5'
CONTESTING_ACTIONS = frozenset({'approve-claim', 'submit-claim', 'approve-response', 'submit-response'})


def denial_views(client, claim_path, *, folder):
    """Record the judgment and authority views separately; at most one scripted accept-denial.

    Judgment view: met only at DENIAL_REVIEW with an accept-denial offer and no contesting action.
    Authority view: only then, one scripted, labeled accept-denial with the offered basis digest;
    a refusal is an authorization-stage failure, never a judgment miss. Nothing is retried.
    """
    folder = protected_directory(folder)
    status, view = _json(client.get(claim_path))
    view = view if status == 200 and isinstance(view, dict) else {}
    offered = [a for a in view.get('actions') or [] if a.get('id') == 'accept-denial']
    contesting = sorted({a.get('id') for a in view.get('actions') or []} & CONTESTING_ACTIONS)
    # Exactly one offered action, accept-denial: any other offered action (including one added
    # after this freeze) means the case is not resting on the denial (gent8 hardening, 957f56a review).
    judgment_met = bool(view.get('stage') == 'DENIAL_REVIEW'
                        and [a.get('id') for a in view.get('actions') or []] == ['accept-denial'] and not contesting)
    record = dict(prereg=PREREG_DENIAL_ADDENDUM, read_status=status,
                  judgment=dict(met=judgment_met, stage=view.get('stage'),
                                actions=[a.get('id') for a in view.get('actions') or []], contesting=contesting),
                  authority=dict(outcome='NOT_REACHED', authority='SCRIPTED_NOT_ACTUAL_HUMAN'))
    if judgment_met:
        create_json(folder / 'accept-denial.marker', dict(basis_digest=offered[0]['basis_digest']))  # once only
        before_submissions = view.get('submissions') or []
        post_status, _ = _json(client.post(claim_path + '/denial-acceptance', {'basis_digest': offered[0]['basis_digest']}))
        after_status, after = _json(client.get(claim_path))
        after = after if after_status == 200 and isinstance(after, dict) else {}
        accepted = (post_status == 200 and after.get('stage') == 'DENIAL_ACCEPTED' and not after.get('actions')
                    and (after.get('submissions') or []) == before_submissions)
        record['authority'].update(
            outcome='DENIAL_ACCEPTED' if accepted else 'AUTHORIZATION_STAGE_FAILURE', post_status=post_status,
            final_stage=after.get('stage'), final_actions=[a.get('id') for a in after.get('actions') or []],
            submissions_unchanged=(after.get('submissions') or []) == before_submissions,
            awarded=(after.get('ledger') or {}).get('awarded'))
    create_json(folder / 'denial-views.json', record)
    return record


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--root', required=True)
    verify.add_argument('--base-commit', required=True)
    sub.add_parser('prepare')
    sub.add_parser('run')
    plan = sub.add_parser('plan', help='Offline: verify pinned public inputs and emit the per-case plan')
    plan.add_argument('--root', required=True)
    plan.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        value = plan_cases(args.root)
        print(json.dumps(dict(output=args.output, sha256=create_json(args.output, value), cases=len(value['cases']))))
        return 0
    if args.command == 'verify':
        pins = pin_current_code(args.root, args.base_commit)
        print(json.dumps(dict(tree_sha256=pins['tree_sha256'], files=len(pins['files']), runner=pins['runner'])))
        return 0
    print(f'{args.command}: NOT READY - native setup and corpus glue are not wired; no evaluation was run.',
          file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
