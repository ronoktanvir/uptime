"""Explicit semantic authority precedes literal matching, independently of prices."""
from copy import deepcopy
from dataclasses import replace

import pytest

from uptime import vendor_bindings as bindings
from test_vendor_resource import DOC, OVERLAY, compiled, extend_source


def review_submission(manifest, overlay=OVERLAY, source=None):
    """Named synthetic-review fixture; never derive authority from expected money."""
    source = source or '\n'.join(c['quote'] for c in manifest['citations'])
    requirements = bindings.requirements(manifest, overlay, source)
    return {k:requirements[k] for k in ('source_sha256','manifest_sha256','overlay_sha256','dependency_sha256')} | {
        'attestations':{name:True for name in bindings.ATTESTATIONS},
        'block_reviews':[dict(block=b['block'],block_sha256=b['block_sha256'],effects=b['effects'],
                              conditions_and_overrides='Explicit synthetic fixture review: all stated conditions mapped; no unresolved override.')
                         for b in requirements['blocks']],
        'bindings':[dict(definition_id=d['id'],span_id=d['spans'][0]['id'],literals=[d['spans'][0]['quote']])
                    for d in requirements['definitions']]}


def reviewed_context(manifest=None, overlay=OVERLAY, *, source=None, tenant='weather-tenant', current=lambda:True):
    """Unit-test authority fixture. Production contexts come only from server storage."""
    manifest = manifest or compiled()
    source = source or '\n'.join(c['quote'] for c in manifest['citations'])
    record = bindings.review_record(manifest, overlay, source, tenant, 'scripted-semantic-fixture',
                                   review_submission(manifest, overlay, source), '2026-11-05T00:00:00Z')
    return bindings._from_record(record, current)


def test_context_pins_source_scope_dependency_and_live_authority():
    manifest = compiled()
    alive = [True]
    context = reviewed_context(manifest, current=lambda:alive[0])
    assert bindings.require_context(manifest, OVERLAY, 'weather-tenant', context) is context
    assert context.resolve('symptoms', 'rejected samples') == {'rejected samples'}
    for suspect in (None, {}, {'reviewed':True}, replace(context,_seal=object()),
                    replace(context,dependency_sha256='0'*64), replace(context,tenant='another')):
        with pytest.raises(bindings.SemanticBindingRequired):
            bindings.require_context(manifest, OVERLAY, 'weather-tenant', suspect)
    with pytest.raises(bindings.SemanticBindingRequired):
        bindings.require_context(manifest, OVERLAY | {'account':'other'}, 'weather-tenant', context)
    alive[0] = False
    with pytest.raises(bindings.SemanticBindingRequired):
        context.resolve('symptoms','rejected samples')


@pytest.mark.parametrize('phrase', ['available samples','samples unavailable','un available samples'])
def test_exact_token_spans_refuse_polarity_reordering_and_token_splits(phrase):
    assert bindings.source_spans('Downtime means unavailable samples.',phrase) == []


def test_original_span_and_each_occurrence_are_visible():
    original = 'Rejected\nsamples are reported. Rejected\nsamples are relevant.'
    spans = bindings.source_spans(original,'Rejected samples')
    assert len(spans) == 2
    assert all(original[s['start']:s['end']] == s['quote'] == 'Rejected\nsamples' for s in spans)


def test_opaque_aliases_never_enter_literal_namespace():
    document, proposal = extend_source([('A further symptom is stalled samples.', {'symptoms':[
        {'label':'successful_samples','phrase':'stalled samples'}, {'label':'event_a','phrase':'stalled samples'}]})])
    manifest = compiled(document, proposal)
    context = reviewed_context(manifest, source=document['text'])
    assert context.resolve('symptoms','stalled samples') == {'successful_samples','event_a'}
    for raw in ('successful samples','successful_samples','event_a','event a'):
        with pytest.raises(bindings.SemanticBindingRequired):
            context.resolve('symptoms',raw)
    with pytest.raises(bindings.SemanticBindingRequired):
        context.resolve('provider_causes','stalled samples')


@pytest.mark.parametrize('raw', ['rejected_samples','Rejected samples','rejected sample','rejected samples.',
                                  'rejected sam\u200bples','rejected \u202esamples','rejected s\u0430mples',
                                  'rejected sam\u00adples','rejected\u2060samples'])
def test_literal_identity_has_no_case_punctuation_unicode_or_identifier_folding(raw):
    with pytest.raises(bindings.SemanticBindingRequired):
        reviewed_context().resolve('symptoms',raw)


def test_reviewed_whitespace_equivalence_is_bounded():
    context = reviewed_context()
    assert context.resolve('symptoms','rejected\n\t\u00a0samples') == {'rejected samples'}
    with pytest.raises(bindings.SemanticBindingRequired):
        context.resolve('symptoms','rejected\u2028samples')


def test_explicit_review_can_bind_an_exact_external_representation_without_label_name_policy():
    manifest=compiled()
    body=review_submission(manifest)
    definition=next(d for d in bindings.definitions(manifest) if d['role']=='symptoms' and d['label']=='rejected samples')
    selected=next(row for row in body['bindings'] if row['definition_id']==definition['id'])
    selected['literals']=['sensor_code_61']
    record=bindings.review_record(manifest,OVERLAY,DOC['text'],'weather-tenant','scripted-semantic-fixture',body,'2026-11-05T00:00:00Z')
    context=bindings._from_record(record,lambda:True)
    assert context.resolve('symptoms','sensor_code_61')=={'rejected samples'}
    for raw in ('sensor code 61','rejected samples'):
        with pytest.raises(bindings.SemanticBindingRequired):
            context.resolve('symptoms',raw)


@pytest.mark.parametrize('false_authority',[1,'true',None,False])
def test_semantic_attestation_requires_explicit_json_true(false_authority):
    manifest=compiled()
    body=review_submission(manifest)
    body['attestations']['conditions_supported']=false_authority
    with pytest.raises(bindings.SemanticBindingRequired):
        bindings.review_record(manifest,OVERLAY,DOC['text'],'weather-tenant','scripted-semantic-fixture',body,'2026-11-05T00:00:00Z')


@pytest.mark.parametrize('fault', ['missing_block','wrong_source','wrong_overlay','wrong_dependency','missing_attestation',
                                   'unresolved_condition','wrong_occurrence','duplicate_definition','empty_literal'])
def test_review_is_explicit_and_complete(fault):
    manifest = compiled()
    body = review_submission(manifest)
    if fault == 'missing_block':body['block_reviews'].pop()
    elif fault == 'wrong_source':body['source_sha256'] = '0'*64
    elif fault == 'wrong_overlay':body['overlay_sha256'] = '0'*64
    elif fault == 'wrong_dependency':body['dependency_sha256'] = '0'*64
    elif fault == 'missing_attestation':body['attestations'].pop('complete_source_reviewed')
    elif fault == 'unresolved_condition':body['attestations']['conditions_supported'] = False
    elif fault == 'wrong_occurrence':body['bindings'][0]['span_id'] = '0'*64
    elif fault == 'duplicate_definition':body['bindings'][-1] = deepcopy(body['bindings'][0])
    elif fault == 'empty_literal':body['bindings'][0]['literals'] = [' ']
    with pytest.raises(bindings.SemanticBindingRequired):
        bindings.review_record(manifest,OVERLAY,DOC['text'],'weather-tenant','named-fixture',body,'2026-11-05T00:00:00Z')


def test_mid_token_proposal_cannot_acquire_a_reviewed_occurrence():
    document, proposal = extend_source([('The source descriptor is unavailable samples.',
                                        {'symptoms':[{'label':'event_a','phrase':'available samples'}]})])
    manifest = compiled(document,proposal)
    definition = next(d for d in bindings.definitions(manifest) if d['label']=='event_a')
    assert definition['spans'] == []


def test_direct_evaluation_requires_current_review_before_any_monetary_value():
    from uptime.vendor_eval import evaluate
    from uptime.vendor_terms import bind_overlay, Overlay
    from test_vendor_resource import FACTS
    manifest = compiled()
    overlay = bind_overlay(manifest,Overlay(**OVERLAY))
    unresolved = evaluate(manifest,overlay,FACTS,'weather-tenant')
    assert unresolved['amount'] is None and unresolved['outcome'] == 'INSUFFICIENT_EVIDENCE'
    assert unresolved['semantic_binding_status'] == 'REVIEW_REQUIRED'
    assert unresolved['claim_cutoff'] == '2026-07-10T18:00:00+00:00'
    assert not {'service_estimate','remaining_estimate','affected_fee_cents','rate_units'} & unresolved.keys()
    alive = [True]
    context = reviewed_context(manifest,overlay,current=lambda:alive[0])
    assert evaluate(manifest,overlay,FACTS,'weather-tenant',bindings=context)['amount'] == '12.51'
    alive[0] = False
    assert evaluate(manifest,overlay,FACTS,'weather-tenant',bindings=context)['amount'] is None


@pytest.mark.parametrize('raw', ['successful samples','successful_samples','event_a','event a','stalled_samples','Stalled samples'])
def test_actual_evaluator_never_prices_an_opaque_id_as_raw_evidence(raw):
    from uptime.vendor_eval import evaluate
    from uptime.vendor_terms import bind_overlay, Overlay
    from test_vendor_resource import FACTS, interval
    document, proposal = extend_source([('A further symptom is stalled samples.', {'symptoms':[
        {'label':'successful_samples','phrase':'stalled samples'}, {'label':'event_a','phrase':'stalled samples'}]})])
    manifest = compiled(document,proposal)
    overlay = bind_overlay(manifest,Overlay(**OVERLAY))
    context = reviewed_context(manifest,overlay,source=document['text'])
    facts = FACTS | {'intervals':[interval('opaque-raw',0,600,symptom=raw)],'exclusions':[]}
    assert evaluate(manifest,overlay,facts,'weather-tenant',bindings=context)['amount'] is None
    positive = deepcopy(facts)
    positive['intervals'][0]['symptom'] = 'stalled samples'
    assert evaluate(manifest,overlay,positive,'weather-tenant',bindings=context)['amount'] == '12.51'


@pytest.mark.parametrize('quote', ['Downtime does not mean rejected samples.',
    'Rejected samples count only when acknowledged by the signed controller report.',
    'The phrase "rejected samples" is a nonoperative example.'])
def test_negated_qualified_or_quoted_source_does_not_price_without_complete_review(quote):
    from uptime.vendor_eval import evaluate
    from uptime.vendor_terms import bind_overlay, Overlay
    from test_vendor_resource import FACTS
    document, proposal = extend_source([(quote,{'symptoms':['rejected samples']})])
    manifest = compiled(document,proposal)
    overlay = bind_overlay(manifest,Overlay(**OVERLAY))
    result = evaluate(manifest,overlay,FACTS,'weather-tenant')
    assert result['amount'] is None and result['semantic_binding_status'] == 'REVIEW_REQUIRED'
    needed = bindings.requirements(manifest,overlay,document['text'])
    assert quote in [b['quote'] for b in needed['blocks']]


def test_registry_binding_is_named_append_only_and_does_not_replace_final_approval(tmp_path,monkeypatch):
    import json
    from hashlib import sha256
    from uptime import vendor_registry as registry
    from uptime.storage import initialize, database
    from uptime.vendor_model import MODEL
    from uptime.vendor_api import Preview
    from uptime.contracts import fingerprint, DraftReviewer
    from test_vendor_resource import P, FACTS, PROPOSAL
    path=tmp_path/'semantic.sqlite'
    initialize(path)
    digest=sha256(DOC['text'].encode()).hexdigest()
    (tmp_path/(digest+'.json')).write_text(json.dumps(dict(model=MODEL,source_sha256=digest,
        session='synthetic-semantic-authority-test',at='2026-07-01T00:00:00Z',proposal=PROPOSAL,
        proposal_sha256=fingerprint(PROPOSAL))))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS',str(tmp_path))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS','1')
    shadow=registry.install(path,P,'semantic-test',dict(document=DOC,overlay=OVERLAY))
    old_version=shadow['version']
    missing=registry.shadow_preview(path,P,'semantic-test',Preview(revision=shadow['revision'],facts=FACTS))
    assert missing['evaluation']['amount'] is None
    submission=registry.SemanticSubmission(revision=shadow['revision'],review=review_submission(shadow['manifest'],shadow['overlay'],DOC['text']))
    with pytest.raises(PermissionError):
        registry.review_semantics(path,DraftReviewer(P.tenant,P.subject,P.role),'semantic-test',submission)
    reviewed=registry.review_semantics(path,P,'semantic-test',submission)
    assert reviewed['version'] != old_version and reviewed['actions'] == []
    assert reviewed['reviewer'] is None and reviewed['semantic_binding_status'] == 'REVIEWED'
    preview=registry.shadow_preview(path,P,'semantic-test',Preview(revision=reviewed['revision'],facts=FACTS))
    assert preview['evaluation']['amount'] == '12.51'
    with database(path) as db:
        original=list(db.execute('SELECT payload FROM v4_vendor_artifact ORDER BY version'))
        context=registry.binding_context_db(db,P,'semantic-test')
        assert context.resolve('symptoms','rejected samples')
    revoked=registry.revoke_semantics(path,P,'semantic-test',registry.SemanticRevocation(revision=reviewed['revision']))
    assert revoked['semantic_binding_status'] == 'REVIEW_REQUIRED' and revoked['actions'] == []
    assert registry.shadow_preview(path,P,'semantic-test',Preview(revision=revoked['revision'],facts=FACTS))['evaluation']['amount'] is None
    with database(path) as db:
        assert list(db.execute('SELECT payload FROM v4_vendor_artifact ORDER BY version')) == original
        assert db.execute('SELECT count(*) FROM v4_vendor_semantic_review').fetchone()[0] == 1
