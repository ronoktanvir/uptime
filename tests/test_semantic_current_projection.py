"""Independent review regressions from frozen5463bcb, plus current-shape controls."""
from test_correspondence_resource import env, install
from test_vendor_resource import FACTS
from uptime import vendor_bindings
from uptime.storage import case_versions

MONETARY_INTERMEDIATES = {'service_estimate','remaining_estimate','affected_fee_cents','rate_units','prior_issued_cents'}

def test_current_case_removes_revoked_semantic_monetary_intermediates(env, tmp_path, monkeypatch):
    state = install(env, tmp_path, monkeypatch)
    case = env.post('/api/vendors/altitude-service/evaluate', {'facts': FACTS})
    historical = case_versions(env.app.state.bench.path, 'bears', case['id'])
    env.post('/api/vendors/altitude-service/semantic-bindings/revoke', {'revision': state['revision']})
    detail = env.client.get('/api/cases/' + case['id'], headers=env.human.headers).json()
    observed = {k: detail.get(k) for k in sorted(MONETARY_INTERMEDIATES | {'amount','recorded_amount','semantic_binding_status','stage','trace'})}
    observed['archived_snapshots_unchanged'] = case_versions(env.app.state.bench.path, 'bears', case['id']) == historical
    assert detail['amount'] is None
    assert detail['semantic_binding_status'] == 'REVIEW_REQUIRED'
    assert not MONETARY_INTERMEDIATES & detail.keys(), observed

def test_current_vendor_stale_semantics_removes_test_actual_money(env, tmp_path, monkeypatch):
    state = install(env, tmp_path, monkeypatch)
    assert state['checks'][0]['actual']['amount'] == '12.51'
    original = vendor_bindings.dependency
    monkeypatch.setattr(vendor_bindings, 'dependency', lambda manifest: '0' * 64)
    stale = env.client.get('/api/vendors/altitude-service', headers=env.human.headers).json()
    observed = {k: stale.get(k) for k in ('state','recorded_state','active_version','semantic_binding_status','checks')}
    assert stale['semantic_binding_status'] == 'REVIEW_REQUIRED'
    assert stale['checks_status'] == 'REVIEW_REQUIRED'
    assert stale['checks'] == [] and stale['recorded_checks'] == state['checks']
    assert all(r.get('actual', {}).get('amount') is None for r in stale['checks']), observed


def test_review_projection_allowlist_drops_future_evaluator_fields():
    from uptime.workbench import review_observation, REVIEW_OBSERVATION_FIELDS
    historical = dict(id='availability-public', version='version-a', sources=[], currency='USD',
        recorded_amount='12.51', financial_scope_reason='Source review was revoked.',
        service_estimate='12.51', future_money={'nested':'999.00'}, future_rate=5,
        trace=['Modeled USD12.51'], amount='12.51')
    result = review_observation(historical)
    assert set(result) <= REVIEW_OBSERVATION_FIELDS | {'stage','outcome','amount','actions','trace','missing','financials'}
    assert result['amount'] is None and result['recorded_amount'] == '12.51'
    assert not {'future_money','future_rate','service_estimate'} & result.keys()
    assert '12.51' not in ''.join(result['trace']) and 'version-a' in result['trace'][0]
    assert historical['future_money'] == {'nested':'999.00'}


def test_new_unreviewed_shadow_controls_remain_current_null_observations(env,tmp_path,monkeypatch):
    state=install(env,tmp_path,monkeypatch)
    state=env.post('/api/vendors/altitude-service/semantic-bindings/revoke',{'revision':state['revision']})
    state=env.post('/api/vendors/altitude-service/tests',dict(revision=state['revision'],tests=[
        dict(name='Authored positive remains a hypothesis',facts=FACTS,expected=dict(outcome='ELIGIBLE',amount='12.51')),
        dict(name='Empty observation remains unknown without meaning',facts=FACTS|{'intervals':[]},
             expected=dict(outcome='INSUFFICIENT_EVIDENCE'))]))
    current=env.client.get('/api/vendors/altitude-service',headers=env.human.headers).json()
    assert current['checks'] == state['checks'] and current['checks']
    assert not current.get('recorded_checks') and current['actions'] == []
    assert all(r.get('actual',{}).get('amount') is None for r in current['checks'])

import pytest


def telemetry_review(state):
    from test_vendor_semantic_bindings import review_submission
    body=review_submission(state['manifest'],state['overlay'],state['source_text'])
    definitions={d['id']:d for d in vendor_bindings.definitions(state['manifest'])}
    for row in body['bindings']:
        if definitions[row['definition_id']]['role']=='provider_status':
            row['literals']=['running']
    return body


def telemetry_shadow(env,tmp_path,monkeypatch):
    from test_vendor_resource_scoped import ROW, facts, subscription
    state=install(env,tmp_path,monkeypatch,extra_terms=ROW,shadow=facts(),expected='15.03',overlay_override=subscription())
    env.post('/api/vendors/altitude-service/semantic-bindings/revoke',{'revision':state['revision']})
    return env.client.get('/api/vendors/altitude-service',headers=env.human.headers).json()


def test_rejected_contradictory_review_is_atomic(env,tmp_path,monkeypatch):
    from uptime.storage import database
    state=telemetry_shadow(env,tmp_path,monkeypatch)
    with database(env.app.state.bench.path) as db:
        before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)]
                for t in ('v4_vendor_event','v4_vendor_semantic_review')}
    response=env.human.post('/api/vendors/altitude-service/semantic-bindings',
        dict(revision=state['revision'],review=telemetry_review(state)))
    assert response.status_code==409
    with database(env.app.state.bench.path) as db:
        assert {t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in before} == before


def test_stored_legacy_collision_is_scanned_without_rewriting_authority(env,tmp_path,monkeypatch):
    from uptime.storage import database
    state=telemetry_shadow(env,tmp_path,monkeypatch)
    # Model a review accepted before the consistency guard; preserve its bytes.
    with monkeypatch.context() as old:
        old.setattr(vendor_bindings,'require_disjoint',lambda entries:None)
        stored=env.post('/api/vendors/altitude-service/semantic-bindings',
            dict(revision=state['revision'],review=telemetry_review(state)))
    with database(env.app.state.bench.path) as db:
        before=[tuple(r) for r in db.execute('SELECT * FROM v4_vendor_semantic_review')]
        conflicts=vendor_bindings.review_conflicts(db,'bears')
        assert conflicts==[dict(vendor_id='altitude-service',review_digest=stored['semantic_binding'],status='REVIEW_REQUIRED')]
        assert vendor_bindings.review_conflicts(db,'another-tenant')==[]
        assert [tuple(r) for r in db.execute('SELECT * FROM v4_vendor_semantic_review')]==before
    current=env.client.get('/api/vendors/altitude-service',headers=env.human.headers).json()
    assert current['semantic_binding_status']=='REVIEW_REQUIRED' and current['actions']==[]


def test_evaluation_refuses_contradiction_even_if_old_context_reaches_it(monkeypatch):
    from dataclasses import replace
    from test_vendor_resource_scoped import ROW, facts, subscription
    from test_vendor_resource import compiled, extend_source
    from test_vendor_semantic_bindings import reviewed_context
    from uptime.vendor_terms import Overlay, bind_overlay
    from uptime.vendor_eval import evaluate
    doc,proposal=extend_source(ROW); manifest=compiled(doc,proposal)
    overlay=bind_overlay(manifest,Overlay(**subscription()))
    context=reviewed_context(manifest,overlay,source=doc['text'])
    entries=tuple((role,label,('running',) if role=='provider_status' else values) for role,label,values in context.entries)
    old_context=replace(context,entries=entries)
    data=facts()
    for row in data['provider_telemetry']['records']:row['status']='running'
    result=evaluate(manifest,overlay,data,'weather-tenant',bindings=old_context)
    assert result['outcome']=='INSUFFICIENT_EVIDENCE' and result['amount'] is None
    assert 'conflict' in ' '.join(result['trace'])

@pytest.mark.parametrize('side,nonqualifying', [('provider','running'), ('customer','degraded')])
def test_contradictory_telemetry_literal_cannot_authorize_money(side, nonqualifying):
    from test_vendor_resource_scoped import ROW, facts, subscription
    from test_vendor_resource import compiled, extend_source
    from test_vendor_semantic_bindings import review_submission
    from uptime.vendor_terms import Overlay, bind_overlay
    from uptime.vendor_eval import evaluate
    document, proposal = extend_source(ROW)
    manifest = compiled(document, proposal)
    overlay = bind_overlay(manifest, Overlay(**subscription()))
    body = review_submission(manifest, overlay, document['text'])
    data = facts()
    for row in data[side + '_telemetry']['records']:
        row['status'] = nonqualifying
    baseline_record = vendor_bindings.review_record(manifest, overlay, document['text'], 'weather-tenant',
        'scripted-independent-review', body, '2026-11-05T00:00:00Z')
    baseline = evaluate(manifest, overlay, data, 'weather-tenant',
        bindings=vendor_bindings._from_record(baseline_record, lambda: True))
    assert baseline['outcome'] == 'INELIGIBLE' and baseline['amount'] is None
    definitions = {d['id']: d for d in vendor_bindings.definitions(manifest)}
    for row in body['bindings']:
        if definitions[row['definition_id']]['role'] == side + '_status':
            row['literals'] = [nonqualifying]
    try:
        record = vendor_bindings.review_record(manifest, overlay, document['text'], 'weather-tenant',
            'scripted-independent-review', body, '2026-11-05T00:00:00Z')
    except vendor_bindings.SemanticBindingRequired:
        return  # Rejecting the contradictory review is the preferred safe boundary.
    context = vendor_bindings._from_record(record, lambda: True)
    result = evaluate(manifest, overlay, data, 'weather-tenant', bindings=context)
    observed = dict(side=side, raw=nonqualifying, baseline=baseline,
        qualifying=sorted(context.targets(side + '_status', nonqualifying)),
        nonqualifying=sorted(context.targets(side + '_nonqualifying', nonqualifying)), evaluation=result)
    assert result['amount'] is None and result['outcome'] in {'INSUFFICIENT_EVIDENCE','UNSUPPORTED_RULE'}, observed
