"""Signed public setup controls; source amounts remain gated by production joins."""
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from scripts import setup_northwind as setup
from uptime.auth import SCRIPT,DEFAULT_ORIGIN
from uptime.auth_client import ReviewerClient
from uptime.contracts import Principal
from uptime.server import create_app


def test_unconfigured_generic_route_is_null_and_never_creates_an_action(tmp_path):
    app=create_app(tmp_path/'empty.db',rehearsal=True,rehearsal_secret='local-synthetic-workflow-test-secret',approvals_enabled=True)
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=('127.0.0.1',1234)) as client:
        actor=ReviewerClient(client,DEFAULT_ORIGIN,SCRIPT,'local-synthetic-workflow-test-secret')
        assert client.get('/api/workspace/workflow',headers=actor.headers).json()=={'workflow':None}
        assert actor.post('/api/workspace/workflow/actions/invented',{}).status_code==409


def test_public_signed_setup_and_scripted_calyx_history_preserve_unknowns(tmp_path,monkeypatch):
    monkeypatch.delenv('UPTIME_PUBLIC_EXTRACTIONS',raising=False)
    app,private,events=setup.prepare(tmp_path/'owned',DEFAULT_ORIGIN)
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=('127.0.0.1',1234)) as client:
        actor,state=setup.seed(client,app,private,events)
        value=setup.checked(client.get('/api/workspace/workflow',headers=actor.headers))['workflow']
        assert value['company']['name']=='Harborline Analytics' and value['vendor']=='Northwind Cloud'
        from hashlib import sha256
        amendment=next(d for d in value['contract']['documents'] if d['version']=='amendment-v2')
        assert any('USD 11,000.00' in row['quote'] for row in amendment['citations'])
        assert all(sha256(row['quote'].encode()).hexdigest()==row['quote_sha256'] and row['source_sha256']==amendment['source_sha256'] for row in amendment['citations'])
        assert value['reviewer']['principal']==SCRIPT and value['reviewer']['authority_kind']=='SCRIPTED_REVIEWER'
        assert value['onboarding']['state']=='ACTIVE'
        assert any(row['event']=='Roll back activation' for row in value['onboarding']['history'])
        assert value['price_finding']['amount']=='1000.00'
        assert value['ledger']['posted']==value['ledger']['applied']=='0.00'
        assert value['next_actions'][0]['label']=='Approve January claim' and value['connection']['receipt_status']=='NOT_POSTED'
        assert [(m['outcome'],m['amount']) for m in value['months']]==[('ELIGIBLE','2400.00'),('INELIGIBLE',None),('INSUFFICIENT_EVIDENCE',None)]
        claim=client.get('/api/correspondence/claims/inbox-northwind-2026-01',headers=actor.headers).json()
        assert {row['label'] for row in claim['evidence']}=={'status','impact','invoice','coverage'}
        assert all(row['issuer'].startswith('northwind-2026-01-') for row in claim['evidence'])
        assert actor.post('/api/workspace/workflow/actions/invented',{}).status_code==409
        assert actor.post('/api/workspace/workflow/actions/invented',{'amount':'2400.00'}).status_code==422
        assert client.post('/api/workspace/workflow/actions/invented',headers=actor.headers,json={}).status_code==403
    reopened,_,_=setup.open_workspace(tmp_path/'owned')
    assert reopened.state.workflow.instance==app.state.workflow.instance


def seeded(tmp_path):
    app,private,events=setup.prepare(tmp_path/'owned',DEFAULT_ORIGIN)
    client=TestClient(app,base_url=DEFAULT_ORIGIN,client=('127.0.0.1',1234),raise_server_exceptions=False)
    actor,_=setup.seed(client,app,private,events)
    return app,client,actor,private


def read(client,actor):
    return setup.checked(client.get('/api/workspace/workflow',headers=actor.headers))['workflow']


def advance(client,actor):
    action=read(client,actor)['next_actions'][0]
    return setup.checked(actor.post('/api/workspace/workflow/actions/'+action['id'],{}))['workflow']


def test_result_calculations_use_current_evaluator_and_citations_keep_original_bytes(tmp_path):
    from decimal import localcontext
    from hashlib import sha256
    app,client,actor,_=seeded(tmp_path)
    try:
        with localcontext() as context:
            context.prec=2
            value=read(client,actor)
        january,february,march=value['months']
        assert january['calculation']==[
            '2 completed shortfall increments; 20% credit after the contractual cap.',
            'USD 12000.00 × 20% = USD 2400.00 after final-cent rounding.']
        assert february['calculation']==['0 completed shortfall increments; 0% credit after the contractual cap.']
        assert february['amount'] is None and march['amount'] is None and march['calculation']==[]
        source=app.state.workflow.package['document']['text']
        for month in value['months']:
            assert month['citations']
            for citation in month['citations']:
                assert citation['quote']==source[citation['start']:citation['end']]
                assert citation['source_sha256']==sha256(source.encode()).hexdigest()
            assert any('each completed 0.1 percentage point' in c['quote'] for c in month['citations'])
        assert any('USD 11,000.00' in c['quote'] for c in value['price_finding']['citations'])
        app.state.workflow.governing_fees.close()
        revoked=read(client,actor)['months'][0]
        assert revoked['amount'] is None and revoked['calculation']==[]
    finally:client.close()


def test_real_services_complete_denial_cure_award_and_idempotent_post(tmp_path):
    from uptime.storage import database
    app,client,actor,_=seeded(tmp_path)
    stages=[];ids=[]
    try:
        for _ in range(9):
            before=read(client,actor);offer=before['next_actions'][0];ids.append(offer['id'])
            after=advance(client,actor);stages.append(after['claim']['state'])
            duplicate=setup.checked(actor.post('/api/workspace/workflow/actions/'+offer['id'],{}))['workflow']
            assert duplicate==after
        assert stages==['CLAIM_APPROVED','AWAITING_VENDOR','NEEDS_EVIDENCE','NEEDS_EVIDENCE','RESPONSE_DRAFTED',
                        'RESPONSE_APPROVED','AWAITING_VENDOR','AWARDED','AWARDED']
        assert after['ledger']['claimed']==after['ledger']['awarded']==after['ledger']['posted']=='2400.00'
        assert after['ledger']['applied']=='0.00' and after['next_actions'][0]['label']=='Receive next invoice'
        assert after['ledger']['bill']['id'] is None
        assert after['connection']['receipt_status']=='VERIFIED_LOCAL_READBACK'
        assert after['ledger']['record_ids']['credit'].startswith('local-ledger:')
        claim=app.state.bench.case(Principal('bears',SCRIPT,'reviewer'),'inbox-northwind-2026-01')
        first,second=claim['submissions']
        assert first['at']<'2026-03-03' and second['at']<'2026-03-03'
        assert second['packet']['requested']=='2400.00'
        assert after['claim']['governing_pricing_version']=='order-v1'
        with database(app.state.bench.path) as db:
            assert db.execute("SELECT count(*) FROM workspace_workflow_intent WHERE status='COMPLETED'").fetchone()[0]==9
            assert {r[0] for r in db.execute('SELECT actor FROM workspace_workflow_intent')}=={SCRIPT}
        assert len(set(ids))==9
    finally:client.close()


@pytest.mark.parametrize('position',[0,1,2,3,4,5,6,7,8,9,10])
def test_restart_after_each_domain_effect_completes_same_intent_without_second_effect(tmp_path,position):
    app,client,actor,private=seeded(tmp_path)
    try:
        for _ in range(position):advance(client,actor)
        offer=read(client,actor)['next_actions'][0]
        app.state.workflow.failure_point='after-effect'
        assert actor.post('/api/workspace/workflow/actions/'+offer['id'],{}).status_code==500
        client.close()
        reopened,_,_=setup.open_workspace(tmp_path/'owned')
        with TestClient(reopened,base_url=DEFAULT_ORIGIN,client=('127.0.0.1',1234)) as second:
            reviewer=ReviewerClient(second,DEFAULT_ORIGIN,SCRIPT,private['rehearsal_secret'])
            assert read(second,reviewer)['next_actions'][0]['id']==offer['id']
            result=setup.checked(reviewer.post('/api/workspace/workflow/actions/'+offer['id'],{}))
            assert setup.checked(reviewer.post('/api/workspace/workflow/actions/'+offer['id'],{}))==result
    finally:client.close()


def test_april_only_application_preserves_march_exposure_and_distinct_versions(tmp_path):
    from uptime.storage import database
    app,client,actor,_=seeded(tmp_path)
    try:
        for _ in range(9):advance(client,actor)
        before=read(client,actor)
        assert before['as_of'].startswith('2026-03-02') and before['ledger']['bill']['id'] is None
        with database(app.state.bench.path) as db:
            assert db.execute('SELECT 1 FROM inbox_claim WHERE id=?',(app.state.workflow.bill_claim_id,)).fetchone() is None
        received=advance(client,actor)
        bill=received['ledger']['bill']
        assert received['as_of'].startswith('2026-04-01')
        assert bill['id']=='NW-2026-04' and bill['original_amount']==bill['outstanding_amount']=='11000.00'
        assert bill['issued_at']==bill['service_start']=='2026-04-01T00:00:00+00:00'
        assert bill['governing_pricing_version']=='amendment-v2'
        assert bill['award_eligibility_version']==before['claim']['eligibility_version']
        final=advance(client,actor)
        assert final['ledger']['applied']=='2400.00' and final['ledger']['bill']['outstanding_amount']=='8600.00'
        assert final['ledger']['unapplied_credit']=='0.00' and final['next_actions']==[]
        assert final['price_finding']['amount']=='1000.00' and final['price_finding']['credit_applied']=='0.00'
        with pytest.raises(KeyError):app.state.bench.allocations.bill_balance('bears','NW-2026-03')
    finally:client.close()


@pytest.mark.parametrize('point',['after-clock','after-invoice-source-0','after-invoice-source-1','after-invoice-source-2','after-invoice-authority'])
def test_april_intake_interruption_resumes_without_duplicate_capacity(tmp_path,point):
    app,client,actor,private=seeded(tmp_path)
    try:
        for _ in range(9):advance(client,actor)
        offer=read(client,actor)['next_actions'][0]
        app.state.workflow.failure_point=point
        assert actor.post('/api/workspace/workflow/actions/'+offer['id'],{}).status_code==500
        with pytest.raises(KeyError):app.state.bench.allocations.bill_balance('bears','NW-2026-04')
        client.close()
        new,_,_=setup.open_workspace(tmp_path/'owned')
        with TestClient(new,base_url=DEFAULT_ORIGIN,client=('127.0.0.1',1234)) as second:
            reviewer=ReviewerClient(second,DEFAULT_ORIGIN,SCRIPT,private['rehearsal_secret'])
            result=setup.checked(reviewer.post('/api/workspace/workflow/actions/'+offer['id'],{}))['workflow']
            assert result['ledger']['bill']['outstanding_amount']=='11000.00'
            assert setup.checked(reviewer.post('/api/workspace/workflow/actions/'+offer['id'],{}))['workflow']==result
            assert advance(second,reviewer)['ledger']['bill']['outstanding_amount']=='8600.00'
    finally:client.close()


@pytest.mark.parametrize('field,value',[('account','other'),('currency','EUR'),('source_ref','unbound'),('issued_at','2026-03-01T00:00:00Z')])
def test_changed_scope_currency_reference_or_date_cannot_create_capacity(tmp_path,field,value):
    app,client,actor,_=seeded(tmp_path)
    try:
        for _ in range(9):advance(client,actor)
        offer=read(client,actor)['next_actions'][0]
        app.state.workflow.settlement['opening_capacity'][field]=value
        assert actor.post('/api/workspace/workflow/actions/'+offer['id'],{}).status_code==409
        assert app.state.bench.allocations.list_bills('bears')==[]
    finally:client.close()


def test_missing_independent_capacity_verification_cannot_create_bill(tmp_path,monkeypatch):
    app,client,actor,_=seeded(tmp_path)
    try:
        for _ in range(9):advance(client,actor)
        deliver=app.state.workflow.deliver
        async def omit(claim,event):
            return None if event.body.kind=='billing_verification' else await deliver(claim,event)
        monkeypatch.setattr(app.state.workflow,'deliver',omit)
        offer=read(client,actor)['next_actions'][0]
        assert actor.post('/api/workspace/workflow/actions/'+offer['id'],{}).status_code==409
        assert app.state.bench.allocations.list_bills('bears')==[]
    finally:client.close()


def test_live_fee_revocation_removes_case_estimate_and_existing_response_action(tmp_path):
    app,client,actor,_=seeded(tmp_path)
    try:
        for _ in range(6):advance(client,actor)
        old=read(client,actor)['next_actions'][0]
        app.state.workflow.governing_fees.close()
        value=read(client,actor)
        assert value['next_actions']==[] and value['months'][0]['amount'] is None
        assert actor.post('/api/workspace/workflow/actions/'+old['id'],{}).status_code==409
    finally:client.close()


def test_browser_jwk_is_same_scripted_identity_and_private_file(tmp_path):
    import stat
    from uptime.auth_keys import public_bytes,rehearsal_key
    app,private,_=setup.prepare(tmp_path/'browser',DEFAULT_ORIGIN)
    path=tmp_path/'browser'/'scripted-reviewer.jwk'
    key=json.loads(path.read_text())
    assert stat.S_IMODE(path.stat().st_mode)==0o600 and key['uptime_rehearsal'] is True
    assert public_bytes(key)==public_bytes(rehearsal_key(private['rehearsal_secret']))
    with TestClient(app,base_url=DEFAULT_ORIGIN,client=('127.0.0.1',1234)) as client:
        assert ReviewerClient(client,DEFAULT_ORIGIN,SCRIPT,key)


def test_crash_after_clock_advance_resumes_without_backdating_or_reusing_prior_action(tmp_path):
    app,client,actor,_=seeded(tmp_path)
    try:
        for _ in range(3):advance(client,actor)
        old=read(client,actor);offer=old['next_actions'][0]
        app.state.workflow.failure_point='after-clock'
        assert actor.post('/api/workspace/workflow/actions/'+offer['id'],{}).status_code==500
        advanced=read(client,actor)
        assert advanced['as_of']>old['as_of'] and advanced['claim']==old['claim']
        app.state.workflow.failure_point=None
        done=setup.checked(actor.post('/api/workspace/workflow/actions/'+offer['id'],{}))['workflow']
        assert done['as_of']==advanced['as_of'] and done['claim']['state']=='NEEDS_EVIDENCE'
    finally:client.close()


def test_live_source_revocation_refuses_workflow_delivery_without_minting_evidence(tmp_path):
    import os
    app,client,actor,_=seeded(tmp_path)
    try:
        advance(client,actor);advance(client,actor)
        offer=read(client,actor)['next_actions'][0]
        path=tmp_path/'owned'/'sources.json'
        config=json.loads(path.read_text())
        config['services']=[s for s in config['services'] if s['subject']!='northwind-2026-01-vendor']
        path.write_text(json.dumps(config));path.chmod(0o600)
        assert actor.post('/api/workspace/workflow/actions/'+offer['id'],{}).status_code==403
        assert read(client,actor)['claim']['state']=='AWAITING_VENDOR'
    finally:client.close()


@pytest.mark.parametrize('change',[dict(mode='sandbox'),dict(rehearsal=False),dict(native_config='ignored.json'),dict(tenant='other')])
def test_operator_configuration_cannot_rebind_native_or_other_authority(tmp_path,change):
    args=dict(mode='replay',rehearsal=True,rehearsal_secret='local-synthetic-workflow-test-secret',workflow_config={})|change
    with pytest.raises(PermissionError):create_app(tmp_path/'rejected.db',**args)


def test_stepped_economic_pin_changes_with_parameters_and_preserves_legacy_preimage():
    from uptime.v4_routes import _economics
    from uptime.contracts import fingerprint
    from fixtures.northwind.loader import load_package
    package=load_package();manifest=package['manifest'];overlay=package['overlay']
    before=_economics(manifest,overlay)
    changed=manifest|{'credit_rule':manifest['credit_rule']|{'credit_units':5000000}}
    assert _economics(changed,overlay)!=before
    with pytest.raises(ValueError):_economics(manifest|{'tiers':[]},overlay)
    legacy={k:v for k,v in manifest.items() if k not in {'credit_rule','credit_rounding'}}
    legacy['tiers']=[dict(product=overlay['product'],plan=overlay['plan'],below_units=99900000,credit_units=20000000)]
    assert _economics(legacy,overlay)==fingerprint([legacy['family'],legacy['period'],legacy['remedy'],overlay['plan'],[(99900000,20000000)],legacy['filing_days']])
