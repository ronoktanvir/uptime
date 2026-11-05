"""Signed public setup controls; source amounts remain gated by production joins."""
from pathlib import Path
import json

import pytest
from fastapi.testclient import TestClient

from scripts import setup_northwind as setup
from uptime.auth import SCRIPT,DEFAULT_ORIGIN
from uptime.auth_client import ReviewerClient
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
        assert value['next_actions']==[] and value['connection']['receipt_status']=='NOT_POSTED'
        claim=client.get('/api/correspondence/claims/inbox-northwind-2026-01',headers=actor.headers).json()
        assert {row['label'] for row in claim['evidence']}=={'status','impact','invoice','coverage'}
        assert all(row['issuer'].startswith('northwind-2026-01-') for row in claim['evidence'])
        assert actor.post('/api/workspace/workflow/actions/invented',{}).status_code==409
        assert actor.post('/api/workspace/workflow/actions/invented',{'amount':'2400.00'}).status_code==422
        assert client.post('/api/workspace/workflow/actions/invented',headers=actor.headers,json={}).status_code==403
    reopened,_,_=setup.open_workspace(tmp_path/'owned')
    assert reopened.state.workflow.instance==app.state.workflow.instance


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
