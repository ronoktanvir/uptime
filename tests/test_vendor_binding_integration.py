"""Public synthetic source cases and signed consumer controls for decision 61."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from uptime.vendor_eval import evaluate
from uptime.vendor_terms import Overlay, bind_overlay
from uptime.storage import database, case_versions
from test_vendor_resource import DOC, PROPOSAL, FACTS, OVERLAY, compiled
from test_vendor_semantic_bindings import reviewed_context
from test_correspondence_resource import env, install, deliver, reports

CASES=json.loads((Path(__file__).parents[1]/'docs/v4/decisions/preregistrations/61-public-label-semantics.json').read_text())['source_cases']


@pytest.mark.parametrize('case',[c for c in CASES if c['expected']=='REFUSE_OR_REVIEW_WITHOUT_AMOUNT'],ids=lambda c:c['id'])
def test_frozen_public_meaning_cases_never_mint_unreviewed_money(case):
    proposal=deepcopy(PROPOSAL)
    index=5 if case['field']=='exclusions' else 4
    if case['field']=='fee_exclusions':
        proposal.append(dict(quote=case['quote'],field='resource_terms',value={case['field']:case['items']}))
    else:
        proposal[index]['quote']=case['quote']
        proposal[index]['value'][case['field']]=case['items']
    document=DOC|{'text':'\n'.join(c['quote'] for c in proposal)}
    try:
        manifest=compiled(document,proposal)
    except ValueError:
        return  # Existing independent source coverage may already refuse it.
    facts=deepcopy(FACTS)
    for row in facts['intervals']:
        row['symptom']=case.get('observed_symptom',row['symptom'])
        row['cause']=case.get('observed_cause',row['cause'])
    for row in facts['exclusions']:
        row['cause']=case.get('observed_exclusion',row['cause'])
    if 'observed_fee_category' in case:
        facts['fee_lines'][0]['category']=case['observed_fee_category']
    result=evaluate(manifest,bind_overlay(manifest,Overlay(**OVERLAY)),facts,'weather-tenant')
    assert result['amount'] is None and result['semantic_binding_status']=='REVIEW_REQUIRED'
    assert not {'service_estimate','remaining_estimate','rate_units','affected_fee_cents'} & result.keys()
    assert all(document['text'][c['start']:c['end']]==c['quote'] for c in manifest['citations'])


def test_removed_union_mutation_exposes_the_original_financial_error(monkeypatch):
    from uptime import vendor_resource_eval as evaluator
    from uptime.vendor_resource_terms import norm
    proposal=deepcopy(PROPOSAL)
    proposal[4]['value']['symptoms']=[dict(label='successful_samples',phrase='rejected samples')]
    manifest=compiled(proposal=proposal)
    overlay=bind_overlay(manifest,Overlay(**OVERLAY))
    context=reviewed_context(manifest,overlay)
    facts=deepcopy(FACTS)
    facts['exclusions']=[]
    for row in facts['intervals']: row['symptom']='successful samples'
    assert evaluate(manifest,overlay,facts,'weather-tenant',bindings=context)['amount'] is None
    def old_union(manifest,key,_context):
        return {norm(label) for label in manifest.get(key,[])} | {
            norm(value['phrase']) for value in manifest.get('label_bindings',{}).get(key,{}).values()}
    monkeypatch.setattr(evaluator,'source_labels',old_union)
    assert evaluate(manifest,overlay,facts,'weather-tenant',bindings=context)['amount']=='12.51'


def test_signed_revocation_blocks_pending_claim_and_rollup_without_rewriting_history(env,tmp_path,monkeypatch):
    state=install(env,tmp_path,monkeypatch)
    deliver(env,reports())
    before=env.read()
    assert before['amount']=='12.51'
    approved=env.action('approve-claim')
    case=env.post('/api/vendors/altitude-service/evaluate',{'facts':FACTS})
    path=env.app.state.bench.path
    versions=case_versions(path,'bears',case['id'])
    with database(path) as db:
        originals=[tuple(r) for r in db.execute('SELECT * FROM inbox_delivery ORDER BY rowid')]
    revoked=env.post('/api/vendors/altitude-service/semantic-bindings/revoke',{'revision':state['revision']})
    assert revoked['active_version'] is None
    after=env.read()
    assert after['amount'] is None and after['actions']==[]
    assert env.human.post(env.url+'/actions/submit-claim',{}).status_code==409
    detail=env.client.get('/api/cases/'+case['id'],headers=env.human.headers).json()
    assert detail['amount'] is None and detail['recorded_amount']=='12.51'
    assert detail['obligation_id']==case['obligation_id']
    dashboard=env.client.get('/api/dashboard',headers=env.human.headers).json()
    estimated=next(m for m in dashboard['cohorts']['portfolio']['metrics'] if m['key']=='estimated')
    assert estimated['amount'] is None
    assert case_versions(path,'bears',case['id'])==versions
    with database(path) as db:
        assert [tuple(r) for r in db.execute('SELECT * FROM inbox_delivery ORDER BY rowid')]==originals
    assert approved['submissions']==after['submissions']==[]


def test_wire_literal_and_obligation_survive_new_explicit_binding(env,tmp_path,monkeypatch):
    from test_vendor_semantic_bindings import review_submission
    state=install(env,tmp_path,monkeypatch)
    deliver(env,reports())
    original=env.read()
    env.action('approve-claim')
    receipt=env.action('submit-claim')['submissions'][0]
    path=env.app.state.bench.path
    with database(path) as db:
        reservations=[tuple(r) for r in db.execute('SELECT * FROM claim_dispatch_identity_v2')]
    env.post('/api/vendors/altitude-service/semantic-bindings/revoke',{'revision':state['revision']})
    state=env.client.get('/api/vendors/altitude-service',headers=env.human.headers).json()
    state=env.post('/api/vendors/altitude-service/semantic-bindings',dict(revision=state['revision'],
        review=review_submission(state['manifest'],state['overlay'],state['source_text'])))
    state=env.post('/api/vendors/altitude-service/tests',dict(revision=state['revision'],tests=[
        dict(name='unchanged source observations',facts=FACTS,expected=dict(outcome='ELIGIBLE',amount='12.51')),
        dict(name='complete empty observation',facts=FACTS|{'intervals':[]},expected=dict(outcome='INELIGIBLE'))]))
    for op in ('interpret','approve','activate'):
        action=next(a['id'] for a in state['actions'] if a['operation']==op)
        state=env.post('/api/vendors/altitude-service/actions/'+action,{})
    current=env.read()
    assert current['contract_version']!=original['contract_version']
    assert current['obligation_id']==original['obligation_id']
    assert current['submissions'][0]==receipt
    with database(path) as db:
        assert [tuple(r) for r in db.execute('SELECT * FROM claim_dispatch_identity_v2')]==reservations
