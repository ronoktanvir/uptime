"""Real shared queue + signed API controls. Provider replies are authored test doubles."""
from datetime import timedelta
import json
from threading import Event
from time import monotonic, sleep

import pytest

from uptime.correspondence_blocks import hydrate_blocks
from uptime.public_proposal_jobs import PublicProposalJobs
from uptime.storage import database
from test_correspondence_blocks_71 import P, Provider, annotate
from test_correspondence_interpretation import TEXT
from test_correspondence_resource import deliver
from test_correspondence_service import service, filed  # noqa: F401


@pytest.mark.parametrize('source_changes', [False, True])
def test_real_queue_releases_signed_write_lock_and_guards_current_source(service, tmp_path, source_changes):
    original = filed(service)
    deliver(service, [('vendor-fixture', dict(kind='message', receipt_id=original['id'], text=TEXT))])
    base = service.url + '/interpretation'
    read = lambda path: service.client.get(path, headers=service.human.headers)
    context = read(base).json()['context']
    annotation = annotate(TEXT, ('substantive', [P('time_bar')]))
    entered, release = Event(), Event()

    class PendingProvider(Provider):
        def __call__(self, request):
            entered.set()
            assert release.wait(10), 'Test must release its provider.'
            return super().__call__(request)

    provider = PendingProvider(json.dumps(annotation), profile={'name': 'authored-queue-control-75'})
    directory = tmp_path / 'operator-approvals'
    directory.mkdir(mode=0o700)
    approvals = directory / 'public.json'
    artifact = dict(version=1, limits=dict(daily_jobs=2, daily_budget_usd='2.00'), approvals=[])
    approvals.write_text(json.dumps(artifact)); approvals.chmod(0o600)
    queue = PublicProposalJobs(service.inbox.path, approvals, {'correspondence': provider}, clock=lambda: service.now)
    service.inbox.public_proposal_jobs = queue
    try:
        reading = dict(context_digest=context['digest'], interpretation=hydrate_blocks(TEXT, annotation).model_dump())
        service.post(base + '/blind-entry', reading)
        assert service.human.post(base + '/model-jobs', {'context_digest': context['digest']}).status_code == 403
        assert not entered.is_set() and not provider.calls
        exported = read(base).json()['model_job']['approval_request']
        artifact['approvals'] = [dict(exported, approved_by='scripted-public-test-operator',
            approved_at=(service.now-timedelta(minutes=1)).isoformat(), expires_at=(service.now+timedelta(minutes=5)).isoformat())]
        approvals.write_text(json.dumps(artifact))
        before = service.read()
        job = service.post(base + '/model-jobs', {'context_digest': context['digest']})
        assert entered.wait(2) and job['state'] in {'QUEUED', 'RUNNING'}
        # This signed write returns while the provider remains blocked: HTTP's
        # global mutation lock is no longer held across inference.
        assert service.post(base + '/blind-entry', reading)['id']
        assert not release.is_set()
        if source_changes:
            changed = service.source('vendor-fixture', dict(kind='message', receipt_id=original['id'],
                text='A separate settlement also governs the requested relief.'), event_id='new-source-while-running')
            assert changed.status_code == 200
            before = service.read()
        release.set()
        deadline = monotonic() + 5
        while True:
            done = read(base + '/model-jobs/' + job['id']).json()
            if done['terminal']:
                break
            assert monotonic() < deadline
            sleep(.01)
        response = read(base)
        assert done['state'] == ('REFUSED' if source_changes else 'SUCCEEDED')
        if source_changes:
            assert response.status_code == 409  # newer response leaves the bridge's admissible context
            with database(service.inbox.path) as db:
                assert db.execute("SELECT COUNT(*) FROM inbox_interpretation WHERE kind='candidate'").fetchone()[0] == 0
        else:
            assert response.status_code == 200, response.text
            view = response.json()
            assert len(view['candidates']) == 1
        assert service.read() == before
        assert service.read()['ledger']['awarded'] == '0.00'
        assert len(provider.calls) == 1
        if not source_changes:
            assert view['candidates'][0]['provenance']['request_sha256'] == done['request_sha256']
            assert service.post(base + '/model-jobs', {'context_digest': context['digest']})['id'] == job['id']
            assert len(provider.calls) == 1
    finally:
        release.set()
        queue.close()
