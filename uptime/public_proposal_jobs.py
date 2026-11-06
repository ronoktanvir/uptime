"""Durable, opt-in jobs for an operator's exact public-request allowlist.

This queue grants inference permission only. It never grants review or action
authority. One process owns each local database; unfinished work is not retried.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from threading import RLock
from uuid import uuid4

from .correspondence_model_transport import strict_json

KINDS = frozenset({'vendor', 'correspondence'})
TERMINAL = frozenset({'SUCCEEDED', 'REFUSED', 'CANCELLED', 'UNCERTAIN'})


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _instant(value):
    if not isinstance(value, str):
        raise ValueError('A timezone-aware approval timestamp is required.')
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('A timezone-aware approval timestamp is required.')
    return at.astimezone(timezone.utc)


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('A canonical SHA256 is required.')
    return value


def _money(value):
    if not isinstance(value, str):
        raise ValueError('A decimal budget string is required.')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError('Invalid proposal budget.') from None
    if not amount.is_finite() or amount <= 0 or amount > 100:
        raise ValueError('Proposal budget is outside the supported bounds.')
    return amount


def load_approvals(path):
    """Read an operator-owned, owner-only artifact without following its symlink."""
    path = Path(path)
    directory = path.parent.stat()
    if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) & 0o077:
        raise PermissionError('Proposal approvals need an owner-only directory.')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077 or info.st_nlink != 1
                or info.st_size > 2_000_000):
            raise PermissionError('Proposal approvals need a bounded owner-only regular file.')
        chunks = bytearray()
        while len(chunks) <= 2_000_000:
            part = os.read(fd, min(65536, 2_000_001-len(chunks)))
            if not part:
                break
            chunks.extend(part)
        if len(chunks) > 2_000_000:
            raise ValueError('Proposal approvals exceeded the file limit.')
        value = strict_json(bytes(chunks))
    finally:
        os.close(fd)
    if not isinstance(value, dict) or set(value) != {'version', 'limits', 'approvals'} or value['version'] != 1:
        raise ValueError('Invalid public proposal approval format.')
    limits = value['limits']
    if (not isinstance(limits, dict) or set(limits) != {'daily_jobs', 'daily_budget_usd'}
            or type(limits['daily_jobs']) is not int or not 1 <= limits['daily_jobs'] <= 100):
        raise ValueError('Invalid proposal job limits.')
    _money(limits['daily_budget_usd'])
    approvals = value['approvals']
    if not isinstance(approvals, list) or len(approvals) > 100:
        raise ValueError('Public request allowlist exceeds its bounds.')
    expected = {'tenant', 'subject', 'kind', 'target', 'context_sha256', 'request',
                'approved_by', 'approved_at', 'expires_at', 'source_references'}
    seen = set()
    for item in approvals:
        if not isinstance(item, dict) or set(item) != expected:
            raise ValueError('Approvals must contain the complete readable public request.')
        for key in ('tenant', 'subject', 'target', 'approved_by'):
            if not isinstance(item[key], str) or not 1 <= len(item[key]) <= 160:
                raise ValueError('Invalid approval identity.')
        if item['kind'] not in KINDS or not isinstance(item['request'], dict):
            raise ValueError('Unknown proposal kind or request.')
        _hash(item['context_sha256'])
        if _instant(item['approved_at']) >= _instant(item['expires_at']):
            raise ValueError('Approval expiry must follow approval time.')
        refs = item['source_references']
        if not isinstance(refs, list) or not 1 <= len(refs) <= 32:
            raise ValueError('Public source references are required.')
        for ref in refs:
            if (not isinstance(ref, dict) or set(ref) != {'reference', 'sha256'}
                    or not isinstance(ref['reference'], str) or not 1 <= len(ref['reference']) <= 512):
                raise ValueError('Invalid public source reference.')
            _hash(ref['sha256'])
        encoded = canonical(item['request'])
        if len(encoded) > 80000:
            raise ValueError('Approved request exceeds its input budget.')
        key = tuple(item[k] for k in ('tenant', 'subject', 'kind', 'target', 'context_sha256')) + (sha256(encoded).hexdigest(),)
        if key in seen:
            raise ValueError('Duplicate exact request approval.')
        seen.add(key)
    return value


class PublicProposalJobs:
    def __init__(self, path, approvals_path, providers, *, clock=None, max_workers=2, max_pending=4):
        if not set(providers) <= KINDS or not providers:
            raise ValueError('Only configured public proposal kinds are supported.')
        if not 1 <= max_workers <= 2 or not max_workers <= max_pending <= 8:
            raise ValueError('Proposal concurrency is outside its bounds.')
        self.path, self.approvals_path = str(Path(path).resolve()), Path(approvals_path)
        self.providers = dict(providers)
        self.provider_locks = {kind: RLock() for kind in providers}
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.max_pending = max_pending
        self.mutex = RLock()
        self.closed = False
        load_approvals(self.approvals_path)
        lock_path = self.path + '.public-proposals.lock'
        self.lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(self.lock_fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise PermissionError('Unsafe proposal ownership lock.')
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self._db() as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('''CREATE TABLE IF NOT EXISTS public_proposal_jobs (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL, subject TEXT NOT NULL,
                    kind TEXT NOT NULL, target TEXT NOT NULL, context_sha256 TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL, status TEXT NOT NULL,
                    submitted_at TEXT NOT NULL, started_at TEXT, finished_at TEXT,
                    approved_by TEXT NOT NULL, approved_at TEXT NOT NULL, expires_at TEXT NOT NULL,
                    budget_usd TEXT NOT NULL, result_json TEXT, receipt_json TEXT, response_json TEXT,
                    reason TEXT, completed_after_expiry INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(tenant,kind,target,context_sha256,request_sha256))''')
                now = self._now()
                db.execute("UPDATE public_proposal_jobs SET status='CANCELLED', reason='restart_before_dispatch', finished_at=? WHERE status='QUEUED'", (now,))
                db.execute("UPDATE public_proposal_jobs SET status='UNCERTAIN', reason='restart_after_dispatch', finished_at=? WHERE status='RUNNING'", (now,))
            self.pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='public-proposal')
        except BaseException:
            os.close(self.lock_fd)
            raise

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _now(self):
        at = self.clock()
        if at.tzinfo is None:
            raise ValueError('Proposal clock must be timezone-aware.')
        return at.astimezone(timezone.utc).isoformat()

    def provider(self, kind):
        if self.closed or kind not in self.providers:
            raise PermissionError('Proposal generation is not configured.')
        return self.providers[kind]

    def _pins(self, *, tenant, subject, kind, target, context_sha256, request):
        for item in (tenant, subject, target):
            if not isinstance(item, str) or not 1 <= len(item) <= 160:
                raise ValueError('Invalid proposal identity.')
        if kind not in KINDS or not isinstance(request, bytes) or len(request) > 80000:
            raise ValueError('Invalid proposal kind or request size.')
        value = strict_json(request)
        if not isinstance(value, dict) or canonical(value) != request:
            raise ValueError('Proposal requests must use canonical UTF-8 JSON.')
        _hash(context_sha256)
        return dict(tenant=tenant, subject=subject, kind=kind, target=target,
                    context_sha256=context_sha256, request_sha256=sha256(request).hexdigest())

    @staticmethod
    def _key(pins):
        return tuple(pins[k] for k in ('tenant', 'kind', 'target', 'context_sha256', 'request_sha256'))

    def _find(self, db, pins):
        row = db.execute('''SELECT * FROM public_proposal_jobs WHERE tenant=? AND kind=?
            AND target=? AND context_sha256=? AND request_sha256=?''', self._key(pins)).fetchone()
        if row and row['subject'] != pins['subject']:
            raise PermissionError('This proposal belongs to another submitting subject.')
        return row

    def _approval(self, pins):
        artifact = load_approvals(self.approvals_path)
        now = _instant(self._now())
        for item in artifact['approvals']:
            if all(item[k] == pins[k] for k in ('tenant', 'subject', 'kind', 'target', 'context_sha256')):
                if sha256(canonical(item['request'])).hexdigest() == pins['request_sha256']:
                    if not _instant(item['approved_at']) <= now < _instant(item['expires_at']):
                        raise PermissionError('Exact request approval has expired or is not yet valid.')
                    return item, artifact['limits']
        raise PermissionError('The complete public request has no operator approval.')

    @staticmethod
    def _view(row):
        keys = ('id', 'kind', 'target', 'context_sha256', 'request_sha256', 'status',
                'submitted_at', 'started_at', 'finished_at', 'reason')
        value = {k: row[k] for k in keys}
        value['job_id'] = row['id']
        value['completed_after_expiry'] = bool(row['completed_after_expiry'])
        value['result'] = strict_json(row['result_json']) if row['status'] == 'SUCCEEDED' else None
        return value

    def inspect(self, **kwargs):
        pins = self._pins(**kwargs)
        with self._db() as db:
            row = self._find(db, pins)
        reason = None
        try:
            self.provider(pins['kind'])
            self._approval(pins)
        except (OSError, ValueError, PermissionError):
            reason = 'exact_request_not_approved'
        return dict(enabled=reason is None, reason=reason, request_sha256=pins['request_sha256'],
                    existing_job=self._view(row) if row else None)

    def submit(self, *, validate, **kwargs):
        pins = self._pins(**kwargs)
        if not callable(validate):
            raise TypeError('A server-side proposal validator is required.')
        with self.mutex:
            self.provider(pins['kind'])
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = self._find(db, pins)
                if existing:
                    return self._view(existing)
                approved, limits = self._approval(pins)
                request_value = strict_json(kwargs['request'])
                # This is a reservation against a configured request budget, not a
                # claim that the provider enforces a hard billing cap.
                budget = max(Decimal('1.00'), _money(request_value.get('max_budget_usd', '1.00')))
                now = self._now()
                day = now[:10]
                charges = db.execute('SELECT budget_usd FROM public_proposal_jobs WHERE tenant=? AND substr(submitted_at,1,10)=?', (pins['tenant'], day)).fetchall()
                if len(charges) >= limits['daily_jobs'] or sum((Decimal(r[0]) for r in charges), Decimal(0)) + budget > _money(limits['daily_budget_usd']):
                    raise PermissionError('The daily proposal reservation limit has been reached.')
                if db.execute("SELECT count(*) FROM public_proposal_jobs WHERE status IN ('QUEUED','RUNNING')").fetchone()[0] >= self.max_pending:
                    raise PermissionError('The proposal queue is full.')
                job_id = str(uuid4())
                db.execute('''INSERT INTO public_proposal_jobs
                    (id,tenant,subject,kind,target,context_sha256,request_sha256,status,submitted_at,approved_by,approved_at,expires_at,budget_usd)
                    VALUES (?,?,?,?,?,?,?,'QUEUED',?,?,?,?,?)''',
                    (job_id,pins['tenant'],pins['subject'],pins['kind'],pins['target'],pins['context_sha256'],pins['request_sha256'],
                     now,approved['approved_by'],approved['approved_at'],approved['expires_at'],str(budget)))
            try:
                self.pool.submit(self._run, job_id, pins, kwargs['request'], validate)
            except RuntimeError:
                self._finish(job_id, 'CANCELLED', reason='dispatch_unavailable')
            return self.get(pins['tenant'], pins['subject'], job_id)

    def _run(self, job_id, pins, request, validate):
        # A provider owns its mutable transport receipt and block state. Different
        # kinds can run concurrently; the same provider cannot race its receipt.
        with self.provider_locks[pins['kind']]:
            self._dispatch(job_id, pins, request, validate)

    def _dispatch(self, job_id, pins, request, validate):
        provider = None
        with self.mutex:
            if self.closed:
                self._finish(job_id, 'CANCELLED', reason='disabled_before_dispatch')
                return
            try:
                provider = self.provider(pins['kind'])
                self._approval(pins)
            except (OSError, ValueError, PermissionError):
                self._finish(job_id, 'REFUSED', reason='approval_unavailable_before_dispatch')
                return
            with self._db() as db:
                changed = db.execute("UPDATE public_proposal_jobs SET status='RUNNING', started_at=? WHERE id=? AND status='QUEUED'", (self._now(), job_id)).rowcount
            if not changed:
                return
        try:
            raw = provider(request)
            # Preserve bounded public provider evidence separately from accepted
            # application results. No API projection exposes this audit column.
            encoded_response = canonical(raw)
            if len(encoded_response) > 300000:
                raise ValueError('Provider result exceeded its evidence budget.')
            with self._db() as db:
                db.execute("UPDATE public_proposal_jobs SET response_json=? WHERE id=? AND status='RUNNING' AND response_json IS NULL",
                           (encoded_response.decode(), job_id))
            result = validate(raw)
            if not isinstance(result, dict) or len(canonical(result)) > 300000:
                raise ValueError('Invalid or oversized proposal result.')
            self._finish(job_id, 'SUCCEEDED', result=result, receipt=getattr(provider, 'last_receipt', None))
        except TimeoutError:
            self._finish(job_id, 'UNCERTAIN', reason='provider_timeout', receipt=getattr(provider, 'last_receipt', None))
        except (ValueError, TypeError, PermissionError, KeyError):
            self._finish(job_id, 'REFUSED', reason='proposal_validation_failed', receipt=getattr(provider, 'last_receipt', None))
        except Exception:
            self._finish(job_id, 'UNCERTAIN', reason='provider_outcome_unknown', receipt=getattr(provider, 'last_receipt', None))

    def _finish(self, job_id, status, *, result=None, reason=None, receipt=None):
        now = self._now()
        # Provider receipts contain bounded metadata, never raw stdout/stderr.
        try:
            receipt_bytes = canonical(receipt) if receipt is not None else None
        except (ValueError, TypeError):
            receipt_bytes = None
        if receipt_bytes is not None and len(receipt_bytes) > 100000:
            receipt_bytes = None
        with self._db() as db:
            row = db.execute('SELECT expires_at FROM public_proposal_jobs WHERE id=?', (job_id,)).fetchone()
            db.execute('''UPDATE public_proposal_jobs SET status=?,result_json=?,receipt_json=?,reason=?,finished_at=?,completed_after_expiry=?
                WHERE id=? AND status IN ('QUEUED','RUNNING')''',
                (status, canonical(result).decode() if result is not None else None,
                 receipt_bytes.decode() if receipt_bytes is not None else None, reason, now,
                 int(_instant(now) >= _instant(row['expires_at'])), job_id))

    def get(self, tenant, subject, job_id):
        with self._db() as db:
            row = db.execute('SELECT * FROM public_proposal_jobs WHERE id=? AND tenant=? AND subject=?', (job_id, tenant, subject)).fetchone()
        if not row:
            raise KeyError('Proposal job not found.')
        return self._view(row)

    def close(self):
        with self.mutex:
            if self.closed:
                return
            self.closed = True
            with self._db() as db:
                db.execute("UPDATE public_proposal_jobs SET status='CANCELLED',reason='disabled_before_dispatch',finished_at=? WHERE status='QUEUED'", (self._now(),))
        self.pool.shutdown(wait=True, cancel_futures=True)
        fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
        os.close(self.lock_fd)
