"""Refused vendor proposal jobs explain themselves with fixed codes and verified public source slices only.

Provider doubles stand in for the model; no real inference occurs. Sentinel strings placed in
model-controlled output must never reach a stored row or an API projection, and only passages the
deterministic validator itself refused may be cited.
"""
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3

from uptime.public_proposal_jobs import PublicProposalJobs, canonical
from uptime.vendor_model_jobs import ProposalRefused, ProposalRequest, public_approval_request
from uptime.vendor_refusal_diagnostics import CODES, SCHEMA, DiagnosingVendorModelJobs, build, project
from uptime.vendor_resource_terms import public_blocks
from uptime.vendor_terms import Document

from test_vendor_model_jobs_runtime import DOC, P, PROPOSAL, VENDOR, finished, runtime, write_manifest  # noqa: F401
from test_vendor_catalog import proposition_document
import test_vendor_resource as resource

SENTINEL = 'MODEL_TEXT_SENTINEL_89'


def _approve(runtime, document, profile):
    _, manifest, provider, service, _ = runtime
    adapter = DiagnosingVendorModelJobs(service)
    body = ProposalRequest(document=document, profile=profile)
    _, context, request = adapter._prepare(VENDOR, body)
    record = public_approval_request(provider, P, VENDOR, body)
    assert record['context_sha256'] == context and canonical(record['request']) == request
    record.update({'approved_by': 'scripted-public-engineering-operator',
                   'approved_at': '2026-11-01T00:00:00Z', 'expires_at': '2026-12-01T00:00:00Z'})
    write_manifest(manifest, [record])
    return adapter, body, request


def _refused(runtime, document, profile='monthly'):
    db, _, provider, service, _ = runtime
    adapter, body, request = _approve(runtime, document, profile)
    job = finished(service, adapter.submit(P, VENDOR, body))
    assert job['status'] == 'REFUSED' and job['reason'] == 'proposal_validation_failed'
    assert 'public_diagnostic' not in job  # the shared service view never carries it
    assert provider.calls[-1] == request  # request bytes, so request/context hashes, are unchanged
    view = adapter.status(P, VENDOR, job['job_id'])
    with sqlite3.connect(db) as connection:
        stored = connection.execute('SELECT public_diagnostic_json FROM public_proposal_jobs WHERE id=?',
                                    (job['job_id'],)).fetchone()[0]
    assert SENTINEL not in json.dumps(view) and SENTINEL not in (stored or '')
    assert view['reason'] == 'proposal_validation_failed' and view['candidate_available'] is False
    return adapter, view, stored


def _only_issue(view):
    diagnostic = view['public_diagnostic']
    assert diagnostic['schema'] == SCHEMA
    [issue] = diagnostic['issues']
    assert issue['explanation'] == CODES[issue['code']]
    return diagnostic, issue


def test_validator_rejected_passage_is_cited_exactly_without_model_text(runtime):
    _, _, provider, _, _ = runtime
    sentence = 'Cash refunds replace service credits for annual plans.'
    document = DOC | {'text': DOC['text'] + '\n' + sentence}
    provider.proposal = deepcopy(PROPOSAL) + [{'quote': sentence, 'field': 'unsupported', 'value': SENTINEL}]
    diagnostic, issue = _only_issue(_refused(runtime, document)[1])
    start = document['text'].index(sentence)
    assert issue == {'code': 'UNSUPPORTED_SOURCE_MATERIAL', 'explanation': CODES['UNSUPPORTED_SOURCE_MATERIAL'],
                     'block': len(PROPOSAL) + 1, 'start': start, 'end': start + len(sentence),
                     'block_sha256': sha256(sentence.encode()).hexdigest(), 'quote': sentence}
    assert diagnostic['source_sha256'] == sha256(document['text'].encode()).hexdigest()
    assert diagnostic['document'] == {k: document[k] for k in ('name', 'uri', 'classification')}
    assert diagnostic['missing_terms'] == []


def test_extraction_flag_is_attributed_to_the_extraction(runtime):
    _, _, provider, _, _ = runtime
    document, proposal = proposition_document()
    sentence = 'Cash refunds may replace service credits.'
    document['text'] += '\n' + sentence
    provider.proposal = proposal + [{'quote': sentence, 'field': 'unsupported', 'value': SENTINEL}]
    _, issue = _only_issue(_refused(runtime, document, 'monthly-propositions')[1])
    assert issue['code'] == 'EXTRACTION_FLAGGED_UNSUPPORTED' and issue['quote'] == sentence
    assert issue['block'] == len(proposal) + 1


def test_a_model_label_alone_is_never_cited(runtime):
    _, _, provider, _, _ = runtime
    provider.proposal = deepcopy(PROPOSAL)
    provider.proposal[1] = provider.proposal[1] | {'field': 'unsupported', 'value': SENTINEL}  # a valid vendor line
    _, issue = _only_issue(_refused(runtime, DOC)[1])
    assert issue['code'] == 'PUBLIC_PROPOSITION_UNESTABLISHED'
    assert (issue['block'], issue['start'], issue['quote']) == (None, None, None)


def test_missing_terms_are_named_only_when_the_validator_establishes_them(runtime):
    _, _, provider, _, _ = runtime
    document, proposal = proposition_document()
    filing = next(c['quote'] for c in proposal if c['field'] == 'filing_days')
    document['text'] = document['text'].replace(filing + '\n', '')
    assert filing not in document['text']
    provider.proposal = [c for c in proposal if c['field'] != 'filing_days']
    diagnostic, issue = _only_issue(_refused(runtime, document, 'monthly-propositions')[1])
    assert issue['code'] == 'REQUIRED_TERMS_MISSING' and diagnostic['missing_terms'] == ['claim filing deadline']


def test_strict_profile_reports_incomplete_coverage_without_guessing_terms(runtime):
    _, _, provider, _, _ = runtime
    filing = next(c['quote'] for c in PROPOSAL if c['field'] == 'filing_days')
    document = DOC | {'text': DOC['text'].replace(filing + '\n', '')}
    assert filing not in document['text']
    provider.proposal = [c for c in deepcopy(PROPOSAL) if c['field'] != 'filing_days']
    diagnostic, issue = _only_issue(_refused(runtime, document)[1])
    assert issue['code'] == 'SOURCE_COVERAGE_INCOMPLETE' and diagnostic['missing_terms'] == []


def test_invented_quote_cannot_be_cited(runtime):
    _, _, provider, _, _ = runtime
    provider.proposal = deepcopy(PROPOSAL)
    provider.proposal[1]['quote'] += ' ' + SENTINEL
    _, issue = _only_issue(_refused(runtime, DOC)[1])
    assert issue['code'] == 'PROPOSAL_NOT_SOURCE_GROUNDED'
    assert (issue['block'], issue['start'], issue['end'], issue['quote'], issue['block_sha256']) == (None,) * 5


def test_unstructured_output_has_a_fixed_code(runtime):
    _, _, provider, _, _ = runtime
    provider.raw_text = 'Here is my reading: ' + SENTINEL
    assert _only_issue(_refused(runtime, DOC)[1])[1]['code'] == 'OUTPUT_NOT_STRUCTURED'


def test_resource_block_marked_unsupported_cites_that_public_block(runtime):
    _, _, provider, _, _ = runtime
    blocks = public_blocks(resource.DOC['text'])
    values = [deepcopy(value) for _, value in resource.ROWS]
    values[2] = {'unsupported': SENTINEL}
    provider.raw_text = json.dumps({'blocks': [{'id': b['id'], 'value': v} for b, v in zip(blocks, values, strict=True)]})
    diagnostic = _refused(runtime, resource.DOC, 'resource-month')[1]['public_diagnostic']
    assert diagnostic['profile'] == 'resource-month'
    flagged = [i for i in diagnostic['issues'] if i['code'] == 'UNSUPPORTED_BLOCK_PROPOSITION']
    assert flagged and flagged[0]['block'] == 3 and flagged[0]['quote'] == blocks[2]['text']
    for issue in diagnostic['issues']:
        if issue['quote'] is not None:
            assert resource.DOC['text'][issue['start']:issue['end']] == issue['quote']


def test_successful_jobs_carry_no_diagnostic(runtime):
    _, _, _, service, _ = runtime
    adapter, body, _ = _approve(runtime, DOC, 'monthly')
    job = finished(service, adapter.submit(P, VENDOR, body))
    assert job['status'] == 'SUCCEEDED' and 'public_diagnostic' not in job
    assert 'public_diagnostic' not in adapter.status(P, VENDOR, job['job_id'])
    assert service.refusal_diagnostic(P.tenant, P.subject, job['job_id']) is None


def test_only_vendor_refusals_store_a_bounded_diagnostic():
    stored = build(Document(**DOC), 'monthly', {'text': 'not structured'})
    refused = ProposalRefused('PROPOSAL_REFUSED')
    refused.public_diagnostic = stored
    assert PublicProposalJobs._public_diagnostic({'kind': 'vendor'}, refused) == canonical(stored)
    assert PublicProposalJobs._public_diagnostic({'kind': 'correspondence'}, refused) is None
    assert PublicProposalJobs._public_diagnostic({'kind': 'vendor'}, ValueError('x')) is None
    refused.public_diagnostic = stored | {'pad': 'x' * 300_001}
    assert PublicProposalJobs._public_diagnostic({'kind': 'vendor'}, refused) is None


def test_existing_job_table_gains_a_nullable_column_and_keeps_rows(tmp_path):
    db = tmp_path / 'old.sqlite'
    with sqlite3.connect(db) as connection:
        connection.execute('''CREATE TABLE public_proposal_jobs (
            id TEXT PRIMARY KEY, tenant TEXT NOT NULL, subject TEXT NOT NULL, kind TEXT NOT NULL, target TEXT NOT NULL,
            context_sha256 TEXT NOT NULL, request_sha256 TEXT NOT NULL, status TEXT NOT NULL, submitted_at TEXT NOT NULL,
            started_at TEXT, finished_at TEXT, approved_by TEXT NOT NULL, approved_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            budget_usd TEXT NOT NULL, result_json TEXT, receipt_json TEXT, response_json TEXT, reason TEXT,
            completed_after_expiry INTEGER NOT NULL DEFAULT 0, UNIQUE(tenant,kind,target,context_sha256,request_sha256))''')
        connection.execute("""INSERT INTO public_proposal_jobs VALUES ('old-job','t','s','vendor','v','{a}','{b}','REFUSED',
            '2026-11-01T00:00:00+00:00',NULL,'2026-11-01T00:00:01+00:00','op','2026-11-01T00:00:00+00:00',
            '2026-12-01T00:00:00+00:00','1.00',NULL,NULL,NULL,'proposal_validation_failed',0)""".format(a='a' * 64, b='b' * 64))
    root = tmp_path / 'protected'
    root.mkdir(mode=0o700)
    write_manifest(root / 'approvals.json')
    service = PublicProposalJobs(db, root / 'approvals.json', {'vendor': object()})
    try:
        old = service.get('t', 's', 'old-job')
        assert old['status'] == 'REFUSED' and old['reason'] == 'proposal_validation_failed'
        assert service.refusal_diagnostic('t', 's', 'old-job') is None
    finally:
        service.close()
    with sqlite3.connect(db) as connection:
        assert 'public_diagnostic_json' in {r[1] for r in connection.execute('PRAGMA table_info(public_proposal_jobs)')}


def test_forged_or_stale_records_are_not_projected(runtime):
    db, _, provider, _, _ = runtime
    sentence = 'Cash refunds replace service credits for annual plans.'
    document = DOC | {'text': DOC['text'] + '\n' + sentence}
    provider.proposal = deepcopy(PROPOSAL) + [{'quote': sentence, 'field': 'unsupported', 'value': None}]
    adapter, view, stored = _refused(runtime, document)
    assert view['public_diagnostic']
    original = json.loads(stored)
    forged_text = 'Forged policy text ' + SENTINEL
    forged_doc = original['document'] | {'text': forged_text}
    self_consistent_forgery = original | {'document': forged_doc, 'source_sha256': sha256(forged_text.encode()).hexdigest(),
                                          'issues': [{'code': 'UNSUPPORTED_SOURCE_MATERIAL', 'block': 1, 'start': 0,
                                                      'end': len(forged_text),
                                                      'block_sha256': sha256(forged_text.encode()).hexdigest()}]}
    wrong_offsets = original | {'issues': [original['issues'][0] | {'start': 0, 'end': 10}]}
    invented_code = original | {'issues': [original['issues'][0] | {'code': 'MODEL_INVENTED_CODE'}]}
    for damaged in (self_consistent_forgery, wrong_offsets, invented_code, original | {'profile': 'resource-month'}):
        with sqlite3.connect(db) as connection:
            connection.execute('UPDATE public_proposal_jobs SET public_diagnostic_json=? WHERE id=?',
                               (json.dumps(damaged), view['job_id']))
        projected = adapter.status(P, VENDOR, view['job_id'])
        assert 'public_diagnostic' not in projected and SENTINEL not in json.dumps(projected)
        assert projected['reason'] == 'proposal_validation_failed'
    assert project(original, vendor=VENDOR, context_sha256=view['context_sha256']) == view['public_diagnostic']
    assert project(original, vendor=VENDOR, context_sha256='0' * 64) is None  # a different pinned context is stale
