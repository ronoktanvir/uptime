"""Public fictional provider exercises real allocation checks and crash windows."""
from copy import deepcopy
import sqlite3
from uuid import uuid4

import pytest

from uptime.allocations import AllocationLedger
from uptime.auth import bind_workspace
from uptime.northwind_workflow import LocalLedgerProvider
from test_allocation_ledger import rows,bill,SCOPE

CONFIG=dict(claim_id="inbox-january",bill_id="shared-bill",scope={k:v for k,v in SCOPE.items() if k!="contract_version"})


@pytest.fixture
def local(tmp_path):
    financial=tmp_path/'financial.db'; bind_workspace(financial,'replay',True)
    provider=LocalLedgerProvider(financial,tmp_path/'provider.db',str(uuid4()),**CONFIG)
    ledger=AllocationLedger(financial)
    award,_=rows(amount=240000)
    credit=provider.credit('bears',award,case_id=CONFIG['claim_id'])
    return ledger,provider,dict(award=award,credits=[credit])


def post(local):
    ledger,provider,plan=local
    return ledger.ingest('bears','inbox-january',**plan,confirm=lambda:provider.confirm('bears','record-credit',plan,case_id=CONFIG['claim_id']))


def test_local_write_readback_and_allocation_are_distinct_durable_records(local):
    ledger,provider,plan=local
    result=post(local)
    assert result['posted']=='2400.00' and result['applied']=='0.00'
    identity=plan['credits'][0]['id']
    assert identity.startswith('local-ledger:') and provider.read('bears',identity)['payload']==plan['credits'][0]
    assert post(local)['credit_ids']==[identity]
    restarted=LocalLedgerProvider(ledger.path,provider.path,provider.instance,**CONFIG)
    restarted.confirm('bears','record-credit',plan,case_id=CONFIG['claim_id'])
    assert AllocationLedger(ledger.path).reconcile('bears',plan['award']['id'])['credit_ids']==[identity]


@pytest.mark.parametrize('point',['after-write','after-readback'])
def test_provider_crash_before_intake_commit_reuses_exact_record(local,point):
    ledger,provider,plan=local; provider.failure_point=point
    with pytest.raises(RuntimeError):post(local)
    assert not ledger.list_awards('bears')
    identity=plan['credits'][0]['id']; previous=provider.read('bears',identity)
    assert previous is not None
    provider.failure_point=None
    result=post(local)
    assert result['posted']=='2400.00' and provider.read('bears',identity)==previous


@pytest.mark.parametrize('field,value',[('id','local-ledger:wrong'),('tenant','other'),('payload_sha256','0'*64)])
def test_wrong_readback_never_commits_posted_money(local,monkeypatch,field,value):
    ledger,provider,plan=local; read=provider.read
    monkeypatch.setattr(provider,'read',lambda *a:dict(read(*a),**{field:value}))
    with pytest.raises(ValueError,match='readback'):post(local)
    assert not ledger.list_awards('bears')


@pytest.mark.parametrize('fault',['amount','currency','scope'])
def test_financial_validation_precedes_local_provider_write(local,fault):
    ledger,provider,plan=local
    if fault=='amount':plan['credits'][0]['amount_cents']+=1
    elif fault=='currency':plan['credits'][0]['currency']='EUR'
    else:plan['credits'][0]['account_id']='other-account'
    with pytest.raises(ValueError):post(local)
    assert provider.read('bears',plan['credits'][0]['id']) is None
    assert not ledger.list_awards('bears')


def test_application_preserves_original_bill_and_exact_remaining_capacity(local):
    ledger,provider,plan=local; post(local)
    ledger.record_bill('bears',bill(amount=1200000))
    application=provider.application('bears',dict(credit_id=plan['credits'][0]['id'],bill_id='shared-bill',amount_cents=240000,effective_date='2026-11-01',source='DETERMINISTIC_REPLAY'),case_id=CONFIG['claim_id'])
    for _ in range(2):
        ledger.apply('bears',application,confirm=lambda:provider.confirm('bears','apply-balance',application,case_id=CONFIG['claim_id']))
    balance=ledger.bill_balance('bears','shared-bill')
    assert balance['amount_cents']==1200000 and balance['remaining_eligible_cents']==960000
    assert ledger.reconcile('bears',plan['award']['id'])['applied']=='2400.00'
    assert len(ledger.reconcile('bears',plan['award']['id'])['application_ids'])==1


def test_changed_provider_payload_is_refused_during_recovery(local):
    ledger,provider,plan=local; provider.failure_point='after-write'
    with pytest.raises(RuntimeError):post(local)
    # Test-only corruption models an untrusted or damaged provider file.
    with sqlite3.connect(provider.path) as db:
        db.execute('DROP TRIGGER local_ledger_no_update')
        db.execute("UPDATE local_ledger_record SET payload='{}'")
    provider.failure_point=None
    with pytest.raises(ValueError,match='Conflicting'):post(local)
    assert not ledger.list_awards('bears')


@pytest.mark.parametrize('mode,rehearsal,tenant',[('replay',False,'bears'),('sandbox',False,'bears'),('replay',True,'other')])
def test_provider_refuses_real_or_other_authority_bindings(tmp_path,mode,rehearsal,tenant):
    financial=tmp_path/'financial.db';bind_workspace(financial,mode,rehearsal,tenant)
    with pytest.raises(PermissionError):LocalLedgerProvider(financial,tmp_path/'provider.db',str(uuid4()),**CONFIG)


def test_provider_rejects_shared_transaction_storage_and_new_instance(local):
    ledger,provider,_=local
    with pytest.raises(ValueError):LocalLedgerProvider(ledger.path,ledger.path,provider.instance,**CONFIG)
    with pytest.raises(ValueError):LocalLedgerProvider(ledger.path,provider.path,str(uuid4()),**CONFIG)


@pytest.mark.parametrize('field,value',[('account_id','other'),('vendor_id','other'),('contract_id','other'),('product_id','other')])
def test_provider_allowlist_refuses_other_exact_financial_scope(local,field,value):
    _,provider,plan=local
    with pytest.raises(PermissionError):
        provider.credit('bears',dict(plan['award'],**{field:value}),case_id=CONFIG['claim_id'])
    with pytest.raises(PermissionError):
        provider.credit('bears',plan['award'],case_id='inbox-unconfigured')


def test_generic_signed_case_route_cannot_use_configured_provider_for_another_claim(tmp_path):
    from test_v4_routes_integration import App
    env=App(tmp_path/'shared.db')
    try:
        env.scope.update(vendor='Twilio',service='Twilio Messaging API')
        env.provision();env.create();env.evidence()
        env.action('approve-claim');first=env.action('submit-claim')['submissions'][0]
        response=env.source('vendor-fixture',dict(kind='message',receipt_id=first['id'],text='We approved a service credit of USD 40.00.'))
        assert response.status_code==200
        scope=dict(vendor_id=env.scope['vendor'],account_id=env.scope['account'],product_id=env.scope['service'],contract_id=env.scope['contract'],currency='USD')
        provider=LocalLedgerProvider(env.inbox.path,tmp_path/'provider.db',str(uuid4()),claim_id='inbox-configured-only',bill_id='configured-bill',scope=scope)
        env.app.state.bench.settlement_provider=provider
        view=env.client.get('/api/cases/'+env.id,headers=env.human.headers).json()
        assert 'record-credit' not in {a['id'] for a in view['actions']}
        assert env.human.post('/api/cases/'+env.id+'/actions/record-credit',{}).status_code==403
        assert env.human.post('/api/cases/price-high/actions/record-credit',{}).status_code==403
        assert not env.app.state.bench.allocations.list_awards('bears')
        with sqlite3.connect(provider.path) as db:
            assert db.execute('SELECT COUNT(*) FROM local_ledger_record').fetchone()[0]==0
    finally:env.client.close()
