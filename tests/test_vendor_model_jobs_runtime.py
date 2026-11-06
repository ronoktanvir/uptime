"""Actual durable queue with authored public inputs; provider and actor are explicit test doubles."""
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import time

import pytest

from uptime.auth import bind_workspace
from uptime.contracts import DraftReviewer, fingerprint
from uptime.public_proposal_jobs import PublicProposalJobs, canonical
from uptime.storage import database, initialize
from uptime import vendor_registry
from uptime.vendor_model import MODEL, VENDOR_SYSTEM
from uptime.vendor_model_jobs import ProposalRequest, VendorModelJobs, public_approval_request

FIXTURE = Path(__file__).resolve().parent.parent/'fixtures/opus70_public'
DOC = json.loads((FIXTURE/'document.json').read_text())
OVERLAY = json.loads((FIXTURE/'overlay.json').read_text())
PROPOSAL = json.loads((FIXTURE/'proposal.authored.json').read_text())
# Disposable generated-key account used only for draft tests; never human approval.
P = DraftReviewer('runtime74-test', 'runtime74-test-reviewer', 'reviewer')
VENDOR = 'new-approved-vendor'
NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)


class PublicProviderDouble:
    model, system = MODEL, VENDOR_SYSTEM
    profile = {'name': 'explicit-public-test-provider', 'revision': 1}

    def __init__(self, proposal=None):
        self.calls = []
        self.proposal = deepcopy(PROPOSAL if proposal is None else proposal)
        self.raw_text = None

    def __call__(self, request):
        self.calls.append(request)
        return {'model': MODEL, 'session': 'scripted-runtime74-provider',
                'text': self.raw_text if self.raw_text is not None else json.dumps({'clauses': self.proposal})}


def write_manifest(path, approvals=()):
    path.write_bytes(canonical({'version': 1, 'limits': {'daily_jobs': 20, 'daily_budget_usd': '20.00'},
                               'approvals': list(approvals)}))
    path.chmod(0o600)


@pytest.fixture
def runtime(tmp_path):
    root = tmp_path/'protected'; root.mkdir(mode=0o700)
    manifest = root/'approvals.json'; write_manifest(manifest)
    db = tmp_path/'runtime.sqlite'
    bind_workspace(db, 'replay', False, P.tenant)
    initialize(db)
    provider = PublicProviderDouble()
    service = PublicProposalJobs(db, manifest, {'vendor': provider}, clock=lambda: NOW)
    adapter = VendorModelJobs(service)
    yield db, manifest, provider, service, adapter
    service.close()


def approved(runtime, document=None):
    db, manifest, provider, service, adapter = runtime
    body = ProposalRequest(document=DOC if document is None else document, profile='monthly')
    document, context, request = adapter._prepare(VENDOR, body)
    record = public_approval_request(provider, P, VENDOR, body)
    assert record['context_sha256'] == context and canonical(record['request']) == request
    record.update({'approved_by': 'scripted-public-engineering-operator',
              'approved_at': '2026-11-01T00:00:00Z', 'expires_at': '2026-12-01T00:00:00Z'})
    write_manifest(manifest, [record])
    return body, request


def finished(service, job):
    for _ in range(200):
        value = service.get(P.tenant, P.subject, job['job_id'])
        if value['status'] not in ('QUEUED', 'RUNNING'):
            return value
        time.sleep(.01)
    pytest.fail('Local provider double did not complete its durable job.')


def test_actual_queue_exact_request_recovery_and_inactive_candidate(runtime):
    db, manifest, provider, service, adapter = runtime
    body, request = approved(runtime)
    assert adapter.access(P, VENDOR, body)['enabled'] is True
    assert provider.calls == []
    submitted = adapter.submit(P, VENDOR, body)
    complete = finished(service, submitted)
    assert complete['status'] == 'SUCCEEDED'
    assert provider.calls == [request]
    assert adapter.submit(P, VENDOR, body)['job_id'] == submitted['job_id']
    assert adapter.access(P, VENDOR, body)['existing_job']['job_id'] == submitted['job_id']
    assert provider.calls == [request]
    for private in (OVERLAY['account'], OVERLAY['fee_line_ref']):
        assert private.encode() not in request
    view = adapter.status(P, VENDOR, submitted['job_id'])
    assert view['candidate_available'] is True
    intake, receipt = adapter.candidate(P, VENDOR, submitted['job_id'], OVERLAY)
    candidate = vendor_registry.install(db, P, VENDOR, intake, public_receipt=receipt)
    assert candidate['state'] == 'SHADOW'
    assert candidate['active_version'] is None and candidate['reviewer'] is None and candidate['actions'] == []
    again = vendor_registry.install(db, P, VENDOR, intake, public_receipt=receipt)
    assert again['revision'] == candidate['revision'] and again['version'] == candidate['version']
    with pytest.raises((KeyError, PermissionError)):
        adapter.status(DraftReviewer(P.tenant, 'different-reviewer', 'reviewer'), VENDOR, submitted['job_id'])
    with pytest.raises((KeyError, PermissionError)):
        adapter.status(P, 'different-vendor', submitted['job_id'])


def test_actual_queue_requires_complete_request_approval_before_call(runtime):
    db, manifest, provider, service, adapter = runtime
    body = ProposalRequest(document=DOC, profile='monthly')
    access = adapter.access(P, VENDOR, body)
    assert access['enabled'] is False and access['reason'] == 'exact_request_not_approved'
    with pytest.raises(PermissionError):
        adapter.submit(P, VENDOR, body)
    assert provider.calls == []
    body, _ = approved(runtime)
    changed = body.model_copy(update={'document': body.document.model_copy(update={'text': DOC['text']+'\n'})})
    assert adapter.access(P, VENDOR, changed)['enabled'] is False
    with pytest.raises(PermissionError):
        adapter.submit(P, VENDOR, changed)
    assert provider.calls == []


def test_actual_queue_retains_refusal_without_exposing_provider_body(runtime):
    db, manifest, provider, service, adapter = runtime
    body, _ = approved(runtime)
    provider.proposal[1]['value'] = 'unsupported-public-provider-marker'
    complete = finished(service, adapter.submit(P, VENDOR, body))
    assert complete['status'] == 'REFUSED' and complete['result'] is None
    view = adapter.status(P, VENDOR, complete['job_id'])
    assert view['candidate_available'] is False and view['reason'] == 'proposal_validation_failed'
    assert 'unsupported-public-provider-marker' not in json.dumps(view)
    with database(db) as connection:
        raw = connection.execute('SELECT response_json FROM public_proposal_jobs WHERE id=?', (complete['job_id'],)).fetchone()[0]
    assert json.loads(json.loads(raw)['text']) == {'clauses': provider.proposal}


def test_corrupt_job_receipt_cannot_advertise_or_create_candidate(runtime):
    db, manifest, provider, service, adapter = runtime
    body, _ = approved(runtime)
    complete = finished(service, adapter.submit(P, VENDOR, body))
    assert complete['status'] == 'SUCCEEDED'
    broken = deepcopy(complete['result'])
    broken['receipt']['proposal'][1]['value'] = 'Different company'
    broken['receipt']['proposal_sha256'] = fingerprint(broken['receipt']['proposal'])
    # Explicit disposable-storage corruption control; production offers no update route.
    with database(db) as connection:
        connection.execute('UPDATE public_proposal_jobs SET result_json=? WHERE id=?',
                           (canonical(broken).decode(), complete['job_id']))
        connection.commit()
    assert adapter.status(P, VENDOR, complete['job_id'])['candidate_available'] is False
    with pytest.raises((ValueError, PermissionError)):
        adapter.candidate(P, VENDOR, complete['job_id'], OVERLAY)
    assert vendor_registry.catalog(db, P)['vendors'] == []


def test_fenced_runtime_output_is_retained_and_refused_without_candidate(runtime):
    db, manifest, provider, service, adapter = runtime
    body, _ = approved(runtime)
    provider.raw_text = '```json\n'+json.dumps({'clauses': PROPOSAL})+'\n```'
    complete = finished(service, adapter.submit(P, VENDOR, body))
    assert complete['status'] == 'REFUSED' and complete['result'] is None
    assert adapter.status(P, VENDOR, complete['job_id'])['candidate_available'] is False
    with pytest.raises(ValueError):
        adapter.candidate(P, VENDOR, complete['job_id'], OVERLAY)
    with database(db) as connection:
        raw = connection.execute('SELECT response_json FROM public_proposal_jobs WHERE id=?', (complete['job_id'],)).fetchone()[0]
    assert json.loads(raw)['text'] == provider.raw_text
    assert len(provider.calls) == 1 and vendor_registry.catalog(db, P)['vendors'] == []


@pytest.mark.parametrize('profile,consumed,unused', [
    ('monthly', 'monthly-availability/1', 'resource-month/1'),
    ('resource-month', 'resource-month/1', 'monthly-availability/1'),
])
def test_proposal_context_pins_only_consumed_family(monkeypatch, profile, consumed, unused):
    from uptime import vendor_terms
    from uptime.vendor_model_jobs import proposal_context
    document = vendor_terms.Document.model_validate(DOC)
    before = proposal_context(VENDOR, document, profile)
    monkeypatch.setitem(vendor_terms.SEMANTICS_REVISIONS, unused, 'unused-family-revision')
    assert proposal_context(VENDOR, document, profile) == before
    monkeypatch.setitem(vendor_terms.SEMANTICS_REVISIONS, consumed, 'consumed-family-revision')
    assert proposal_context(VENDOR, document, profile) != before
