"""Decision81: artifact category guidance, request versioning and explicit human correction.

Authored public81 controls only. Supplied annotations below are scripted inputs; they do not
measure model extraction quality and are not a blind evaluation.
"""
from hashlib import sha256
import json
from pathlib import Path

import pytest

import uptime.correspondence_block_model as block_model
from uptime.contracts import fingerprint
from uptime.correspondence_block_model import (BLOCK_SCHEMA, BLOCK_SYSTEM, BLOCK_VERSION, PublicBlockInterpretationAdapter,
                                               parse_block_result, serialized_block_request)
from uptime.correspondence_blocks import ARTIFACT_CATEGORY_GUIDANCE, BlockInterpretation, BlockProposition, hydrate_blocks
from uptime.correspondence_interpretation import Entry, Prepare, Proposition, Review, proposal_for_review
from uptime.correspondence_model import MODEL
from test_correspondence import env, ID, REVIEWER  # noqa: F401  (pytest fixture)
from test_correspondence_blocks_71 import P, annotate, context_for
from test_correspondence_interpretation import meaning, start

CONTROLS = json.loads((Path(__file__).resolve().parents[1] / 'fixtures' / 'correspondence' / 'public-81' /
                       'controls.json').read_text())
CASES = {case['id']: case for case in CONTROLS['cases']}
LABELS = ('resource_log = Incident or telemetry record', 'invoice_detail = Itemized billing record',
          'scope_mapping = Account or resource mapping')
REFS = {'request-record': 'TRACE-Q', 'invoice-record': 'BILL-Q', 'scope-record': 'MAP-Q', 'identifier-only': 'resource-log-Q'}


def artifact(case, artifact_type=None, **changes):
    text = CASES[case]['text']
    slots = [('artifact_ref', REFS[case], 0)] if case in REFS else []
    return text, annotate(text, ('substantive', [P('artifact', slots=slots, artifact_type=artifact_type, **changes)]))


# --- schema and guidance -------------------------------------------------------------------------

def test_block_schema_description_carries_all_three_meanings_and_shape_is_unchanged():
    prop = BLOCK_SCHEMA['$defs']['BlockProposition']['properties']['artifact_type']
    for label in LABELS:
        assert label in prop['description']
    assert 'Never infer the type from artifact_ref' in prop['description']
    assert prop['default'] is None and 'artifact_type' not in BLOCK_SCHEMA['$defs']['BlockProposition'].get('required', [])
    reference = Proposition.model_json_schema()['properties']['artifact_type']
    strip = lambda d: {k: v for k, v in d.items() if k not in {'description', 'default'}}
    assert strip(prop) == strip(reference)  # same nullable enum, only guidance added
    assert BlockProposition.model_fields['artifact_type'].annotation == Proposition.model_fields['artifact_type'].annotation
    assert BlockProposition.model_validate(P('artifact')).artifact_type is None  # default stays null


def test_guidance_labels_match_ui_labels_exactly():
    js = (Path(__file__).resolve().parents[1] / 'web' / 'interpretation.js').read_text()
    for label in LABELS:
        key, ui = label.split(' = ')
        assert f"['{key}','{ui}']" in js


def test_current_request_names_v3_and_carries_guidance():
    request = json.loads(serialized_block_request(context_for(CASES['request-record']['text'])))
    assert BLOCK_VERSION == request['version'] == 'source_blocks_v3'
    assert ARTIFACT_CATEGORY_GUIDANCE in request['system'] and request['system'] == BLOCK_SYSTEM
    assert 'independent literal document identifier' in request['system']
    assert ARTIFACT_CATEGORY_GUIDANCE in json.dumps(request['schema'], ensure_ascii=False)


def _stale(context, **changes):
    request = json.loads(serialized_block_request(context))
    request.update(changes)
    return block_model._canonical(request)


STALE = {
    'v2_version': dict(version='source_blocks_v2'),
    'v2_system': dict(system=BLOCK_SYSTEM.replace(ARTIFACT_CATEGORY_GUIDANCE + ' ', '')),
    'v2_schema': dict(schema=json.loads(json.dumps(BLOCK_SCHEMA).replace(
        json.dumps(ARTIFACT_CATEGORY_GUIDANCE)[1:-1], 'x'))),
}


@pytest.mark.parametrize('change', sorted(STALE))
def test_stale_request_bytes_and_old_allowlist_are_refused_before_provider(change):
    text, value = artifact('request-record')
    context = context_for(text)
    stale = _stale(context, **STALE[change])
    assert stale != serialized_block_request(context)
    result = dict(model=MODEL, text=json.dumps(value))
    with pytest.raises(ValueError):
        parse_block_result(context, result, stale)
    calls = []

    def provider(encoded):
        calls.append(encoded)
        return result
    old = PublicBlockInterpretationAdapter(allowed_requests={sha256(stale).hexdigest()}, provider=provider, enabled=True)
    with pytest.raises(PermissionError):
        old.propose(context)
    assert calls == []
    # Positive control: only the complete current request hash is admitted, exactly once.
    current = sha256(serialized_block_request(context)).hexdigest()
    proposed = PublicBlockInterpretationAdapter(allowed_requests={current}, provider=provider, enabled=True).propose(context)
    assert len(calls) == 1 and proposed['provenance']['representation'] == 'source_blocks_v3'
    assert proposed['interpretation']['propositions'][0]['artifact_type'] is None


# --- hydration of supplied annotations ----------------------------------------------------------

@pytest.mark.parametrize('case', ['request-record', 'identifier-only'])
def test_missing_type_stays_null_and_reference_exact_without_autofill(case):
    text, value = artifact(case)
    hydrated = hydrate_blocks(text, value)
    p = hydrated.propositions[0]
    assert p.artifact_type is None
    assert p.source.quote == text and [s.source.quote for s in p.slots] == [REFS[case]]


@pytest.mark.parametrize('case', ['request-record', 'invoice-record', 'scope-record'])
def test_supplied_explicit_category_survives_grounding_unchanged(case):
    reviewed = CASES[case]['reviewed_type']
    text, value = artifact(case, reviewed)
    p = hydrate_blocks(text, value).propositions[0]
    assert p.artifact_type == reviewed and p.slots[0].source.quote == REFS[case]


def _unknown(text, value):
    hydrated = hydrate_blocks(text, value)
    return proposal_for_review(context_for(text), hydrated).reason == 'unknown'


def test_negated_mixed_and_ambiguous_annotations_remain_unknown():
    negated = CASES['negated-category']['text']
    assert _unknown(negated, annotate(negated, ('substantive', [P('artifact', polarity='negative', artifact_type='resource_log')])))
    mixed = CASES['mixed-categories']['text']
    assert _unknown(mixed, annotate(mixed, ('substantive', [P('artifact', artifact_type='invoice_detail'),
                                                             P('artifact', artifact_type='resource_log')])))
    assert _unknown(mixed, annotate(mixed, ('substantive', [P('artifact', referent='ambiguous', artifact_type='resource_log')])))
    assert _unknown(mixed, annotate(mixed, ('unsupported', [P('unsupported')])))


@pytest.mark.parametrize('family', ['time_bar', 'availability', 'maintenance', 'award'])
def test_artifact_type_on_non_artifact_family_remains_unknown(family):
    text = CASES['request-record']['text']
    assert _unknown(text, annotate(text, ('substantive', [P(family, artifact_type='resource_log')])))


# --- explicit human correction through the existing review desk -----------------------------------

def _review(ctx, value, verdict, candidate=None):
    return Review(context_digest=ctx['digest'], interpretation=value, candidate_id=candidate,
                  resolutions=[dict(proposition=0, verdict=verdict,
                                    explanation='Scripted authored control: the source names a request log; type chosen explicitly.')],
                  residuals_reviewed=True, complete_meaning_reviewed=True)


def test_explicit_category_correction_needs_correct_verdict_and_grants_no_authority(env):
    text = CASES['request-record']['text']
    desk, ctx = start(env, text)
    original = meaning(text, 'artifact', slots=[('artifact_ref', 'TRACE-Q')])
    assert original.propositions[0].artifact_type is None
    desk.blind(REVIEWER, ID, Entry(context_digest=ctx['digest'], interpretation=original))
    candidate = desk.candidate(REVIEWER, ID, Entry(context_digest=ctx['digest'], interpretation=original))['id']
    corrected = meaning(text, 'artifact', slots=[('artifact_ref', 'TRACE-Q')], artifact_type='resource_log')
    before = env.get()

    with pytest.raises(ValueError, match='explicit correction'):
        desk.review(REVIEWER, ID, _review(ctx, corrected, 'accept', candidate))  # a changed row is never silently accepted
    rid = desk.review(REVIEWER, ID, _review(ctx, corrected, 'correct', candidate))['id']
    preview = desk.preview(REVIEWER, ID, rid)
    row = preview['alignment'][0]
    assert row['reviewed'] == fingerprint(corrected.model_dump()['propositions'][0])
    assert row['reviewed'] != row['blind'] and row['reviewed'] != row['candidate']
    assert row['blind'] == row['candidate'] == fingerprint(original.model_dump()['propositions'][0])
    p = preview['reviewed_interpretation']['propositions'][0]
    assert p['artifact_type'] == 'resource_log' and p['source'] == original.model_dump()['propositions'][0]['source']
    assert p['slots'] == original.model_dump()['propositions'][0]['slots']
    assert [s['source']['quote'] for s in p['slots']] == ['TRACE-Q']
    assert preview['external_actions'] == [] and preview['ledger_unchanged'] and env.get() == before
    # The missing artifact is not supplied by a category correction. The only prepared
    # state is NEEDS_EVIDENCE, with no response packet, approval or submission authority.
    assert preview['disposition'] == 'NEEDS_EVIDENCE' and preview['prepare_allowed']
    assert preview['packet'] is None
    prepared = desk.prepare(REVIEWER, ID, Prepare(review_id=rid, preview_digest=preview['digest']))
    assert prepared['stage'] == 'NEEDS_EVIDENCE' and prepared['approval'] is None
    with pytest.raises(ValueError):
        env.act('submit-response')
    assert env.get()['ledger'] == before['ledger'] and env.get()['submissions'] == before['submissions']


def test_reference_only_reviewed_reading_remains_reviewable(env):
    text = CASES['identifier-only']['text']
    desk, ctx = start(env, text)
    value = meaning(text, 'artifact', slots=[('artifact_ref', 'resource-log-Q')])
    desk.blind(REVIEWER, ID, Entry(context_digest=ctx['digest'], interpretation=value))
    rid = desk.review(REVIEWER, ID, _review(ctx, value, 'accept'))['id']
    preview = desk.preview(REVIEWER, ID, rid)
    assert preview['reviewed_interpretation']['propositions'][0]['artifact_type'] is None
    assert preview['interpretation']['reason'] == 'artifact' and preview['interpretation']['reference'] == 'resource-log-Q'
    assert preview['external_actions'] == [] and preview['ledger_unchanged']


def test_actual_frozen_v2_request_remains_preserved_but_current_runtime_refuses_it():
    root = Path(__file__).resolve().parents[1]
    request = (root / 'docs/v4/evaluation76/requests/dispute-02.request.json').read_bytes()
    context = json.loads((root / 'docs/v4/evaluation76/requests/dispute-02.local.json').read_text())
    old = json.loads(request)
    assert old['version'] == 'source_blocks_v2'
    assert request != serialized_block_request(context, old['transport'])
    with pytest.raises(ValueError, match='does not match the current source context'):
        parse_block_result(context, dict(model=MODEL, text='{}'), request)


def test_corrected_category_only_narrows_independently_verified_reference_match():
    from copy import deepcopy
    from uptime.correspondence_artifacts import approved_artifact
    content = 'Public authored ownership record'
    digest = sha256(content.encode()).hexdigest()
    artifact = dict(kind='artifact',subject='source',digest='a'*64,
                    body=dict(artifact_ref='opaque-Q',artifact_type='scope_mapping',content=content,body_sha256=digest))
    proof = dict(kind='status_verification',subject='verifier',digest='b'*64,
                 body=dict(artifact_ref='opaque-Q',artifact_type='scope_mapping',body_sha256=digest,
                           linked_ref='status-Q',observed_at='2026-07-03T00:00:00Z'))
    record = dict(kind='status',event_id='status-Q',digest='c'*64,body=dict(observed_at='2026-07-02T00:00:00Z'))
    state = dict(requested_artifact=dict(ref='opaque-Q',type=None),submissions=[dict(evidence_digests=[])],
                 evidence=[artifact,proof,record])
    assert approved_artifact(state)['type'] == 'scope_mapping'  # legitimate exact reference-only match
    corrected = deepcopy(state);corrected['requested_artifact']['type'] = 'resource_log'
    assert approved_artifact(corrected) is None  # same reference, wrong category cannot satisfy corrected request
    corrected['requested_artifact']['type'] = 'scope_mapping'
    assert approved_artifact(corrected)['ref'] == 'opaque-Q'
    corrected['evidence'].remove(corrected['evidence'][1])
    assert approved_artifact(corrected) is None  # category never supplies independent verification
