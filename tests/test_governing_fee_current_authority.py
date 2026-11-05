"""Independent reviewer findings: exact lookup identity and current fee authority."""
from dataclasses import replace

import pytest

from fixtures.northwind.loader import load_package,build_fee_registry
from test_governing_fees import snapshot,entry,NOW
from uptime import vendor_registry as catalog
from uptime.contracts import Principal
from uptime.governing_fees import FeeRegistry,GoverningFeeRequired
from uptime.storage import initialize,case_versions,database
from uptime.workbench import Workbench


@pytest.mark.parametrize('change',[{'plan':'Enterprise'},{'fee_line_id':'other-line'}])
def test_duplicate_authenticated_lookup_never_overwrites_by_entry_order(change):
    p=load_package();first=entry(p);other=replace(first,entry_id='other',**change)
    for pair in ((first,other),(other,first)):
        with pytest.raises(ValueError,match='lookup scope'):FeeRegistry(pair)


def setup_case(tmp_path):
    p=load_package();p['tenant']='independent-fee-scope';path=tmp_path/'review.sqlite';initialize(path)
    actor=Principal(p['tenant'],'scripted-current-fee-review','reviewer')
    reg=build_fee_registry(p);ctx=reg.resolve(snapshot(p),as_of=NOW)
    state=catalog.install(path,actor,'northwind',dict(document=p['document'],overlay=p['overlay']))
    controls=[dict(name='January',facts=p['months'][0]['facts'],expected=dict(outcome='ELIGIBLE',amount='2400.00')),
              dict(name='March',facts=p['months'][2]['facts'],expected=dict(outcome='INSUFFICIENT_EVIDENCE'))]
    state=catalog.submit_tests(path,actor,'northwind',catalog.TestSubmission(revision=state['revision'],tests=controls),governing_fees=(ctx,))
    return p,path,actor,reg,ctx,state


def test_closed_authority_archives_checks_and_blocks_old_approve_token(tmp_path):
    p,path,actor,reg,ctx,state=setup_case(tmp_path)
    token=next(a['id'] for a in state['actions'] if a['operation']=='approve')
    before=state['checks']
    reg.close()
    stale=catalog.get_vendor(path,actor,'northwind',governing_fees=(ctx,))
    assert stale['state']=='REVIEW_REQUIRED' and stale['checks']==[] and stale['actions']==[]
    assert stale['recorded_checks']==before and stale['pricing_binding_status']=='REVIEW_REQUIRED'
    with pytest.raises(ValueError):catalog.act(path,actor,'northwind',token,governing_fees=(ctx,))
    assert catalog.catalog(path,actor,governing_fees=(ctx,))['vendors'][0]['active_version'] is None


def test_closed_authority_blocks_previously_issued_activation_token(tmp_path):
    p,path,actor,reg,ctx,state=setup_case(tmp_path)
    state=catalog.act(path,actor,'northwind',next(a['id'] for a in state['actions'] if a['operation']=='approve'),governing_fees=(ctx,))
    token=next(a['id'] for a in state['actions'] if a['operation']=='activate')
    reg.close()
    with pytest.raises(ValueError):catalog.act(path,actor,'northwind',token,governing_fees=(ctx,))


def activate(path,actor,ctx,state):
    for op in ('approve','activate'):
        state=catalog.act(path,actor,'northwind',next(a['id'] for a in state['actions'] if a['operation']==op),governing_fees=(ctx,))
    return state


def test_current_case_totals_and_resolver_refuse_closed_authority_without_rewriting_history(tmp_path):
    p,path,actor,reg,ctx,state=setup_case(tmp_path)
    activate(path,actor,ctx,state)
    created=catalog.dispatch(path,actor,'northwind',p['months'][0]['facts'],governing_fee=ctx)
    bench=Workbench(path,'replay',tenant=p['tenant'],governing_fees=(ctx,))
    assert bench.case(actor,created['id'])['amount']=='2400.00'
    assert catalog.resolve_case(path,actor,created['id'],governing_fees=(ctx,))['amount']=='2400.00'
    history=case_versions(path,p['tenant'],created['id'])
    reg.close()
    current=bench.case(actor,created['id'])
    assert current['amount'] is None and current['stage']=='REVIEW_REQUIRED' and current['recorded_amount']=='2400.00'
    assert not {'governing_fee_cents','rate_units','completed_steps','service_estimate'} & current.keys()
    assert current['claim_cutoff_exclusive']=='2026-03-03T00:00:00+00:00'
    metric=next(m for m in bench.dashboard(actor)['cohorts']['portfolio']['metrics'] if m['key']=='estimated')
    assert metric['amount'] is None and metric['financial_scope_status']=='REVIEW_REQUIRED'
    with pytest.raises(GoverningFeeRequired):catalog.resolve_case(path,actor,created['id'],governing_fees=(ctx,))
    assert catalog.resolve_case(path,actor,created['id'],require_active=False)['amount']=='2400.00'
    assert case_versions(path,p['tenant'],created['id'])==history


def test_same_database_other_app_instance_cannot_borrow_pricing_authority(tmp_path):
    p,path,actor,reg,ctx,state=setup_case(tmp_path)
    activate(path,actor,ctx,state)
    created=catalog.dispatch(path,actor,'northwind',p['months'][0]['facts'],governing_fee=ctx)
    app_with_authority=Workbench(path,'replay',tenant=p['tenant'],governing_fees=(ctx,))
    other_app=Workbench(path,'replay',tenant=p['tenant'])
    assert app_with_authority.case(actor,created['id'])['amount']=='2400.00'
    assert other_app.case(actor,created['id'])['amount'] is None
    assert catalog.get_vendor(path,actor,'northwind')['state']=='REVIEW_REQUIRED'
    assert catalog.get_vendor(path,actor,'northwind',governing_fees=(ctx,))['state']=='ACTIVE'


def test_current_signed_record_is_reread_and_replacement_is_not_implicitly_selected(tmp_path):
    import json
    p,path,actor,reg,ctx,state=setup_case(tmp_path)
    activate(path,actor,ctx,state)
    created=catalog.dispatch(path,actor,'northwind',p['months'][0]['facts'],governing_fee=ctx)
    snap=snapshot(p)
    event=dict(source='billing',kind='invoice',body=json.loads(snap.body_json),digest=snap.evidence_digest,subject=snap.subject,
               source_key_id=snap.source_key_id,source_grant_id=snap.source_grant_id,received_at=snap.received_at)
    with database(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS inbox_claim (tenant TEXT,scope TEXT,state TEXT)')
        db.execute('INSERT INTO inbox_claim (tenant,scope,state) VALUES (?,?,?)',(p['tenant'],snap.scope.model_dump_json(),json.dumps({'evidence':[event]})))
        db.commit()
    bench=Workbench(path,'replay',tenant=p['tenant'],governing_fees=reg,trusted_now=lambda:NOW)
    assert bench.case(actor,created['id'])['amount']=='2400.00'
    replacement=build_fee_registry(p)
    reg.close()
    assert bench.case(actor,created['id'])['amount'] is None
    bench.governing_fees=replacement
    assert bench.case(actor,created['id'])['amount']=='2400.00'
    with database(path) as db:
        event['body']['lines'][0]['amount']='12001.00'
        db.execute('UPDATE inbox_claim SET state=?',(json.dumps({'evidence':[event]}),));db.commit()
    assert bench.case(actor,created['id'])['amount'] is None
    assert catalog.get_vendor(path,actor,'northwind',governing_fees=replacement,trusted_now=lambda:NOW)['state']=='REVIEW_REQUIRED'
