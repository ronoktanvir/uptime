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


def reviewed_context(manifest=None, overlay=OVERLAY, *, source=None, current=lambda:True):
    """Unit-test authority fixture. Production contexts come only from server storage."""
    manifest = manifest or compiled()
    source = source or '\n'.join(c['quote'] for c in manifest['citations'])
    record = bindings.review_record(manifest, overlay, source, 'weather-tenant', 'scripted-semantic-fixture',
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
