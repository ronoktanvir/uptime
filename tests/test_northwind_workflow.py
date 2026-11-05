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
        assert value['reviewer']['principal']==SCRIPT and value['reviewer']['authority_kind']=='SCRIPTED_REVIEWER'
        assert value['onboarding']['state']=='ACTIVE'
        assert any(row['event']=='Roll back activation' for row in value['onboarding']['history'])
        assert value['price_finding']['amount'] is None
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
        assert after['ledger']['applied']=='0.00' and after['next_actions']==[]
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


@pytest.mark.parametrize('position',[0,1,2,3,4,5,6,7,8])
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
