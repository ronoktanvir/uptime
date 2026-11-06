"""Workstream 75: operator-approved queued interpretation requests around InterpretationDesk.

The fake shared service below follows the confirmed duck interface of the root
PublicProposalJobs service (inspect/submit/get/provider). It is a test double, not
an alternate queue. Annotations are handcrafted public synthetic controls; they say
nothing about semantic accuracy of an actual model.
"""
from datetime import timedelta
from hashlib import sha256
import json

import pytest

from uptime.contracts import Principal
from uptime.correspondence_block_model import (PublicBlockInterpretationAdapter, parse_block_result,
                                               serialized_block_request)
from uptime.correspondence_blocks import hydrate_blocks, source_blocks
from uptime.correspondence_interpretation import Entry, Interpretation, ModelRequest, Prepare, Review
from uptime.correspondence_model_jobs import KIND, CorrespondenceModelJobs, serialized_runtime_request
from uptime.storage import database
from test_correspondence import env, ID, REVIEWER, VIEWER  # noqa: F401 (fixture)
from test_correspondence_blocks_71 import P, Provider, annotate
from test_correspondence_interpretation import TEXT, start
from test_correspondence_service import service, filed  # noqa: F401 (fixture)
from test_correspondence_resource import deliver

PROFILE = dict(name='public-test-profile-75', retry_count=0)
AWARD = 'A service credit of USD 17.20 is now on our approved list; USD 44.93 remains declined.'
CONDITIONAL = 'If our engineering team agrees, a service credit of USD 17.20 may be placed on our approved list.'
OTHER = Principal('bears', 'second-reviewer', 'reviewer')


class FakeJobs:
    """Durable-queue stand-in: provider runs only in run(), once, outside desk locks."""
    def __init__(self, provider=None):
        self.providers = {'correspondence': provider} if provider is not None else {}
        self.approved, self.jobs, self.inspected = set(), {}, []

    def provider(self, name):
        return self.providers[name]

    @staticmethod
    def key(tenant, subject, kind, target, context_sha256, request):
        return (tenant, subject, kind, target, context_sha256, sha256(request).hexdigest())

    def _public(self, job):
        return None if job is None else {k: v for k, v in job.items() if k not in {'validate', 'request', 'key'}}

    def _existing(self, key):
        return next((j for j in self.jobs.values() if j['key'] == key), None)

    def inspect(self, *, tenant, subject, kind, target, context_sha256, request):
        key = self.key(tenant, subject, kind, target, context_sha256, request)
        self.inspected.append(key)
        return dict(enabled=key in self.approved, reason='approved' if key in self.approved else 'approval_required',
                    request_sha256=key[-1], existing_job=self._public(self._existing(key)))

    def submit(self, *, validate, **args):
        key = self.key(**args)
        if self._existing(key):
            return self._public(self._existing(key))
        if key not in self.approved:
            raise PermissionError('not approved')
        job = dict(id=f'job-{len(self.jobs) + 1}', tenant=args['tenant'], subject=args['subject'], kind=args['kind'],
                   target=args['target'], context_sha256=args['context_sha256'], request_sha256=key[-1],
                   state='QUEUED', result=None, reason=None, key=key, request=args['request'], validate=validate)
        self.jobs[job['id']] = job
        return self._public(job)

    def run(self, job_id):
        job = self.jobs[job_id]
        job['state'] = 'RUNNING'
        try:
            result = self.providers['correspondence'](job['request'])
        except Exception:
            job['state'] = 'UNCERTAIN'
            return job
        try:
            job['result'], job['state'] = job['validate'](result), 'SUCCEEDED'
        except (ValueError, PermissionError, KeyError) as error:
            job['state'], job['reason'] = 'REFUSED', type(error).__name__
        return job

    def get(self, tenant, subject, job_id):
        job = self.jobs.get(job_id)
        if job is None or job['tenant'] != tenant or job['subject'] != subject:
            raise KeyError(job_id)
        return self._public(job)


def setup(env, text=TEXT, annotation=None, approve=True, blind=True):
    desk, context = start(env, text)
    annotation = annotation or annotate(text, ('substantive', [P('time_bar')]))
    provider = Provider(json.dumps(annotation), profile=PROFILE)
    fake = FakeJobs(provider)
    env.desk.public_proposal_jobs = fake
    jobs = CorrespondenceModelJobs(env.desk, desk)
    request = serialized_runtime_request(context, PROFILE)
    if approve:
        fake.approved.add(FakeJobs.key(REVIEWER.tenant, REVIEWER.subject, KIND, ID, context['digest'], request))
    if blind:
        desk.blind(REVIEWER, ID, Entry(context_digest=context['digest'], interpretation=hydrate_blocks(text, annotation)))
    return desk, jobs, fake, provider, context, request


def candidate_rows(env):
    with database(env.desk.path) as db:
        return db.execute("SELECT COUNT(*) FROM inbox_interpretation WHERE kind='candidate'").fetchone()[0]


def submit(jobs, context, p=REVIEWER, claim=ID):
    return jobs.submit(p, claim, ModelRequest(context_digest=context['digest']))


def test_missing_service_provider_or_approval_and_absent_blind_never_enqueue_or_call(env):
    desk, context = start(env)
    jobs = CorrespondenceModelJobs(env.desk, desk)
    info = jobs.view(REVIEWER, ID)['model_job']
    assert (info['enabled'], info['can_request'], info['reason']) == (False, False, 'not_configured')
    desk.blind(REVIEWER, ID, Entry(context_digest=context['digest'],
                                   interpretation=hydrate_blocks(TEXT, annotate(TEXT, ('substantive', [P()])))))
    with pytest.raises(PermissionError):
        submit(jobs, context)
    env.desk.public_proposal_jobs = FakeJobs()
    assert jobs.view(REVIEWER, ID)['model_job']['reason'] == 'provider_not_configured'
    with pytest.raises(PermissionError):
        submit(jobs, context)

    provider = Provider('{}', profile=PROFILE)
    fake = FakeJobs(provider)
    env.desk.public_proposal_jobs = fake
    info = jobs.view(REVIEWER, ID)['model_job']
    assert not info['enabled'] and not info['can_request'] and info['reason'] == 'approval_required'
    assert info['request_sha256'] == sha256(serialized_runtime_request(context, PROFILE)).hexdigest()
    with pytest.raises(PermissionError):
        submit(jobs, context)
    with pytest.raises(PermissionError):
        submit(jobs, context, VIEWER)
    assert fake.jobs == {} and provider.calls == []


def test_approval_without_own_independent_reading_cannot_enqueue(env):
    desk, jobs, fake, provider, context, _ = setup(env, blind=False)
    view = jobs.view(REVIEWER, ID)
    assert view['model_job']['enabled'] and view['model_job']['reason'] == 'independent_reading_required'
    assert view['candidates'] == [] and view['blind_entry'] is None
    with pytest.raises(ValueError, match='own semantic judgment'):
        submit(jobs, context)
    # Another reviewer's reading never substitutes for the requester's.
    desk.blind(OTHER, ID, Entry(context_digest=context['digest'],
                                interpretation=hydrate_blocks(TEXT, annotate(TEXT, ('substantive', [P()])))))
    with pytest.raises(ValueError, match='own semantic judgment'):
        submit(jobs, context)
    assert fake.jobs == {} and provider.calls == []


def test_request_hash_binds_source_scope_amount_profile_and_actor_target_context(env):
    desk, jobs, fake, provider, context, request = setup(env)
    info = jobs.view(REVIEWER, ID)['model_job']
    assert info['can_request'] and info['request_sha256'] == sha256(request).hexdigest()
    assert (info['target'], info['context_digest'], info['profile']) == (ID, context['digest'], PROFILE['name'])
    assert fake.inspected[-1] == (REVIEWER.tenant, REVIEWER.subject, KIND, ID, context['digest'], info['request_sha256'])
    body = json.loads(request)
    assert body['transport'] == PROFILE and body['input']['source_blocks'] == source_blocks(TEXT)
    assert (body['input']['scope_month'], body['input']['requested']) == (context['scope']['month'], context['requested'])
    assert context['event_digest'].encode() not in request and context['scope']['account'].encode() not in request
    for changed in (dict(context, text=TEXT + ' '), dict(context, requested='1.00'),
                    dict(context, scope=dict(context['scope'], month='2020-01'))):
        assert serialized_runtime_request(changed, PROFILE) != request
    assert serialized_runtime_request(context, dict(PROFILE, name='other')) != request
    # Approval is pinned to the actor, target and context as well as the bytes.
    for p, claim, digest in ((OTHER, ID, context['digest']), (REVIEWER, 'inbox-other', context['digest']),
                             (REVIEWER, ID, '0' * 64)):
        assert FakeJobs.key(p.tenant, p.subject, KIND, claim, digest, request) not in fake.approved
    desk.blind(OTHER, ID, Entry(context_digest=context['digest'],
                                interpretation=hydrate_blocks(TEXT, annotate(TEXT, ('substantive', [P()])))))
    assert not jobs.view(OTHER, ID)['model_job']['can_request']
    with pytest.raises(PermissionError):
        submit(jobs, context, OTHER)
    provider.profile = dict(PROFILE, name='changed-profile')
    assert not jobs.view(REVIEWER, ID)['model_job']['enabled']
    with pytest.raises(PermissionError):
        submit(jobs, context)
    assert fake.jobs == {} and provider.calls == []


def test_submit_only_queues_then_separate_run_attaches_one_inert_exact_source_candidate(env):
    desk, jobs, fake, provider, context, request = setup(env)
    before = env.get()
    job = submit(jobs, context)
    assert job['state'] == 'QUEUED' and not job['terminal'] and job['result'] is None
    assert provider.calls == [] and candidate_rows(env) == 0 and env.get() == before
    assert jobs.get(REVIEWER, ID, job['id'])['state'] == 'QUEUED'
    assert submit(jobs, context)['id'] == job['id'] and len(fake.jobs) == 1  # duplicate returns the same job

    fake.run(job['id'])
    assert provider.calls == [request]
    done = jobs.get(REVIEWER, ID, job['id'])
    assert done['state'] == 'SUCCEEDED' and done['terminal']
    result = done['result']
    assert result['external_actions'] == [] and result['ledger_unchanged'] and result['semantic_review_required']
    assert (result['context_digest'], result['request_sha256']) == (context['digest'], sha256(request).hexdigest())
    rows = jobs.view(REVIEWER, ID)['candidates']
    assert [row['id'] for row in rows] == [result['candidate_id']]
    row = rows[0]
    assert row['origin'] == 'model' and row['provenance']['request_sha256'] == sha256(request).hexdigest()
    assert row['provenance']['structural_grounding_not_semantic_validation'] is True
    assert row['source'] == dict(context_digest=context['digest'], event_digest=context['event_digest'],
                                 text_sha256=context['text_sha256'], original_digest=context['original_digest'])
    assert row['interpretation']['segments'][0]['source']['quote'] == TEXT
    assert env.get() == before  # no source-state, ledger, submissions, approvals or actions
    assert jobs.view(OTHER, ID)['candidates'] == []  # withheld until that reviewer's own blind entry
    assert submit(jobs, context)['id'] == job['id'] and len(provider.calls) == 1  # never resubmitted


def test_approval_export_contains_complete_initial_request_without_grant_authority(env):
    _, jobs, fake, provider, context, request = setup(env, approve=False)
    info = jobs.view(REVIEWER, ID)['model_job']
    exported = info['approval_request']
    assert set(exported) == {'tenant', 'subject', 'kind', 'target', 'context_sha256', 'request', 'source_references'}
    assert exported['request'] == json.loads(request)
    assert exported['request']['attempt_nonce'] == 'initial'
    assert 'attempt_nonce' not in json.loads(serialized_block_request(context, PROFILE))
    assert exported['source_references'] == [dict(
        reference='correspondence/'+ID+'/reply/'+context['event_digest'], sha256=context['text_sha256'])]
    assert not info['can_request'] and fake.jobs == {} and provider.calls == []
    response = provider(request)
    assert parse_block_result(context, response, request)['provenance']['request_sha256'] == sha256(request).hexdigest()
    changed = dict(exported['request'], attempt_nonce='retry-without-new-approval')
    with pytest.raises(ValueError, match='initial runtime'):
        parse_block_result(context, response, json.dumps(changed, sort_keys=True, separators=(',', ':')).encode())


def test_uncertain_after_candidate_commit_is_correlated_and_never_retried(env):
    _, jobs, fake, provider, context, request = setup(env)
    before = env.get()
    job = submit(jobs, context)
    fake.run(job['id'])  # candidate transaction committed before durable job completion
    fake.jobs[job['id']].update(state='UNCERTAIN', result=None, reason='restart_after_dispatch')
    uncertain = jobs.get(REVIEWER, ID, job['id'])
    assert uncertain['state'] == 'UNCERTAIN' and uncertain['result'] is None
    candidate = jobs.view(REVIEWER, ID)['candidates'][0]
    assert candidate['provenance']['request_sha256'] == uncertain['request_sha256'] == sha256(request).hexdigest()
    assert submit(jobs, context)['id'] == job['id'] and len(provider.calls) == 1
    assert env.get() == before and before['ledger']['awarded'] == '0.00'


@pytest.mark.parametrize('change', ['message', 'expired'])
def test_context_change_or_blind_expiry_while_pending_leaves_no_candidate(env, change):
    desk, jobs, fake, provider, context, _ = setup(env)
    job = submit(jobs, context)
    if change == 'message':
        env.message('A settlement also governs this request.', 'another-message')
    else:
        env.now += timedelta(minutes=31)
    before = env.get()
    assert fake.run(job['id'])['state'] == 'REFUSED'
    assert len(provider.calls) == 1 and candidate_rows(env) == 0 and env.get() == before


@pytest.mark.parametrize('fault', ['json', 'model', 'truncated', 'oversize', 'other_source', 'extra', 'unsupported_courtesy'])
def test_malformed_wrong_model_truncated_or_ungrounded_results_refuse(env, fault):
    desk, jobs, fake, provider, context, _ = setup(env)
    good = json.dumps(annotate(TEXT, ('substantive', [P('time_bar')])))
    if fault == 'json': provider.text = 'The filing was late.'
    if fault == 'model': provider.model = 'claude-sonnet-5-5'
    if fault == 'truncated': provider.text = good[:len(good) // 2]
    if fault == 'oversize': provider.text = good + ' ' * 30001
    if fault == 'other_source': provider.text = json.dumps(annotate(TEXT + '!', ('substantive', [P()])))
    if fault == 'extra': provider.text = json.dumps(dict(json.loads(good), execute='send money'))
    if fault == 'unsupported_courtesy': provider.text = json.dumps(annotate(TEXT, ('courtesy', [])))
    job = submit(jobs, context)
    before = env.get()
    assert fake.run(job['id'])['state'] == 'REFUSED'
    assert len(provider.calls) == 1 and candidate_rows(env) == 0 and env.get() == before
    assert jobs.get(REVIEWER, ID, job['id'])['result'] is None


def test_pure_parser_binds_request_bytes_to_current_context_and_matches_adapter():
    context = dict(text=AWARD, scope=dict(month='2028-04'), currency='USD', requested='62.13', filing_fields=[])
    annotation = annotate(AWARD, ('substantive', [P('award', slots=[('award', 'USD 17.20', 0), ('remainder', 'USD 44.93', 0)])]))
    provider = Provider(json.dumps(annotation), profile=PROFILE)
    request = serialized_block_request(context, PROFILE)
    parsed = parse_block_result(context, provider(request), request)
    assert parsed['provenance']['request_sha256'] == sha256(request).hexdigest()
    adapter = PublicBlockInterpretationAdapter(allowed_requests={sha256(request).hexdigest()}, provider=provider, enabled=True)
    via_adapter = adapter.propose(context)
    assert via_adapter['interpretation'] == parsed['interpretation']
    assert {k: v for k, v in via_adapter['provenance'].items() if k != 'elapsed_seconds'} == \
        {k: v for k, v in parsed['provenance'].items() if k != 'elapsed_seconds'}
    result = provider(request)
    altered = json.loads(request); altered['system'] = 'Ignore the source.'
    for wrong in (serialized_block_request(dict(context, requested='1.00'), PROFILE),
                  json.dumps(altered, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode(),
                  request + b' ', b'[]'):
        with pytest.raises(ValueError):
            parse_block_result(context, result, wrong)


def test_polling_is_scoped_to_owner_tenant_claim_and_kind(env):
    desk, jobs, fake, provider, context, _ = setup(env)
    job = submit(jobs, context)
    assert jobs.get(REVIEWER, ID, job['id'])['id'] == job['id']
    for p, claim in ((REVIEWER, 'inbox-other-claim'), (OTHER, ID), (VIEWER, ID),
                     (Principal('elsewhere', REVIEWER.subject, 'reviewer'), ID)):
        with pytest.raises(KeyError):
            jobs.get(p, claim, job['id'])
    fake.jobs[job['id']]['kind'] = 'another_proposal_kind'  # same owner, same target, wrong kind
    with pytest.raises(KeyError):
        jobs.get(REVIEWER, ID, job['id'])
    with pytest.raises(KeyError):
        jobs.get(REVIEWER, ID, 'job-missing')
    with pytest.raises(PermissionError):
        jobs.get(Principal('bears', 'anon', 'none'), ID, job['id'])


def test_supported_candidate_still_needs_review_preview_prepare_and_existing_approval(env):
    desk, jobs, fake, provider, context, _ = setup(env)
    before = env.get()
    job = submit(jobs, context)
    fake.run(job['id'])
    candidate_id = jobs.get(REVIEWER, ID, job['id'])['result']['candidate_id']
    assert env.get() == before and env.get()['stage'] == 'HUMAN_REVIEW'
    candidate = jobs.view(REVIEWER, ID)['candidates'][0]
    interpretation = Interpretation.model_validate(candidate['interpretation'])
    rid = desk.review(REVIEWER, ID, Review(
        context_digest=context['digest'], interpretation=interpretation, candidate_id=candidate_id,
        resolutions=[dict(proposition=0, verdict='accept', explanation='Reviewed the complete signed reply and claim referent.')],
        residuals_reviewed=True, complete_meaning_reviewed=True))['id']
    assert env.get() == before
    preview = desk.preview(REVIEWER, ID, rid)
    assert preview['prepare_allowed'] and preview['external_actions'] == [] and preview['ledger_unchanged']
    assert env.get() == before
    draft = desk.prepare(REVIEWER, ID, Prepare(review_id=rid, preview_digest=preview['digest']))
    assert draft['stage'] == 'RESPONSE_DRAFTED' and draft['approval'] is None
    assert draft['submissions'] == before['submissions'] and draft['ledger'] == before['ledger']
    with pytest.raises(ValueError):
        env.act('submit-response')
    env.act('approve-response')
    env.now += timedelta(days=1)
    sent = env.act('submit-response')
    assert sent['ledger']['awarded'] == sent['ledger']['applied'] == '0.00'
    assert sent['submissions'][1]['packet']['interpretation_review']['review_id'] == rid
    assert len(provider.calls) == 1


@pytest.mark.parametrize('text,annotation,reason', [
    (AWARD, lambda t: annotate(t, ('substantive', [P('award', slots=[('award', 'USD 17.20', 0), ('remainder', 'USD 44.93', 0)])])), 'award'),
    (CONDITIONAL, lambda t: annotate(t, ('substantive', [P('award', modality='conditional',
                                                          conditions=[('If our engineering team agrees', 0)],
                                                          slots=[('award', 'USD 17.20', 0)])])), 'unknown'),
])
def test_award_and_conditional_candidates_stay_human_review_without_money(env, text, annotation, reason):
    value = annotation(text)
    desk, jobs, fake, provider, context, _ = setup(env, text, value)
    before = env.get()
    job = submit(jobs, context)
    fake.run(job['id'])
    candidate_id = jobs.get(REVIEWER, ID, job['id'])['result']['candidate_id']
    interpretation = hydrate_blocks(text, value)
    rid = desk.review(REVIEWER, ID, Review(
        context_digest=context['digest'], interpretation=interpretation, candidate_id=candidate_id,
        resolutions=[dict(proposition=0, verdict='accept', explanation='Reviewed the complete signed reply and its conditions.')],
        residuals_reviewed=True, complete_meaning_reviewed=True))['id']
    preview = desk.preview(REVIEWER, ID, rid)
    assert preview['interpretation']['reason'] == reason and not preview['prepare_allowed']
    assert preview['reported_award'] == ('17.20' if reason == 'award' else None)
    with pytest.raises(ValueError):
        desk.prepare(REVIEWER, ID, Prepare(review_id=rid, preview_digest=preview['digest']))
    after = env.get()
    assert after == before and after['stage'] == 'HUMAN_REVIEW' and after['ledger']['awarded'] == '0.00'


def test_model_jobs_api_requires_signed_reviewer_write_and_scopes_status(service):
    original = filed(service)
    deliver(service, [('vendor-fixture', dict(kind='message', receipt_id=original['id'], text=TEXT))])
    base = service.url + '/interpretation'
    read = lambda path: service.client.get(path, headers=service.human.headers)
    view = read(base).json()
    assert view['model_job']['reason'] == 'not_configured' and not view['model_job']['can_request']
    assert view['source_blocks'] == source_blocks(TEXT) and view['candidates'] == []
    context = view['context']
    annotation = annotate(TEXT, ('substantive', [P('time_bar')]))
    provider = Provider(json.dumps(annotation), profile=PROFILE)
    fake = FakeJobs(provider)
    service.inbox.public_proposal_jobs = fake  # installed after router creation
    info = read(base).json()['model_job']
    assert info['reason'] == 'approval_required' and info['request_sha256']
    fake.approved.add(fake.inspected[-1])  # out-of-band operator approval of that exact request
    body = dict(context_digest=context['digest'])
    assert service.human.post(base + '/model-jobs', body).status_code == 409  # no independent reading yet
    service.post(base + '/blind-entry', dict(context_digest=context['digest'],
                                             interpretation=hydrate_blocks(TEXT, annotation).model_dump()))
    assert service.client.post(base + '/model-jobs', json=body).status_code == 403  # unsigned
    for extra in (dict(text='other'), dict(classification='public'), dict(grant='approved')):
        assert service.human.post(base + '/model-jobs', dict(body, **extra)).status_code in {400, 422}
    assert fake.jobs == {}
    job = service.post(base + '/model-jobs', body)
    assert job['state'] == 'QUEUED' and provider.calls == []
    assert service.client.get(base + '/model-jobs/' + job['id']).status_code == 401
    fake.run(job['id'])
    status = read(base + '/model-jobs/' + job['id'])
    assert status.status_code == 200 and status.json()['state'] == 'SUCCEEDED'
    assert read(service.url + '-other/interpretation/model-jobs/' + job['id']).status_code == 404
    rows = read(base).json()['candidates']
    assert [r['id'] for r in rows] == [status.json()['result']['candidate_id']]
    assert service.read()['stage'] == 'HUMAN_REVIEW' and service.read()['submissions'] == [original]
