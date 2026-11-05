"""Public synthetic server input authority; no real source or human claims."""
from copy import copy,deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
from decimal import Decimal
import json
import pickle

import pytest

from fixtures.northwind.loader import load_package,build_fee_registry
from uptime.contracts import fingerprint,Principal
from uptime.correspondence_types import Scope
from uptime.governing_fees import FeeRegistry,FeeEntry,authenticated_invoice_snapshot,require_governing_fee
from uptime.vendor_eval import evaluate
from uptime.vendor_terms import Overlay,bind_overlay

NOW=datetime.fromisoformat('2026-03-01T12:00:00Z')


def snapshot(package,index=0,**changes):
    """Explicit synthetic adapter unit-test input, not an authenticated receipt."""
    row=package['months'][index]
    body={'kind':'invoice','lines':[{'id':x.id,'kind':'affected_api','amount':str(x.net)} for x in row['invoice'].lines]}
    event=dict(source='billing',kind='invoice',body=body,digest=fingerprint(body),subject='scripted-fixture-billing',
        source_key_id='unit-test-key',source_grant_id='unit-test-grant',received_at=NOW.isoformat())
    event.update(changes)
    return authenticated_invoice_snapshot(package['tenant'],Scope(**row['scope']),event)


def entry(package,index=0,**changes):
    row=package['months'][index];overlay=bind_overlay(package['manifest'],Overlay(**package['overlay']))
    base=dict(entry_id='entry-'+str(index),tenant=package['tenant'],scope=Scope(**row['scope']),plan=overlay['plan'],
        fee_line_id=overlay['fee_line_ref'],agreement=package['pricing_agreement'],invoice=row['invoice'],
        sla_source_sha256=package['manifest']['document']['sha256'],manifest_sha256=fingerprint(package['manifest']),overlay_sha256=fingerprint(overlay))
    return FeeEntry(**(base|changes))


def test_trusted_context_prices_january_and_flat_fee_never_controls():
    package=load_package();registry=build_fee_registry(package);ctx=registry.resolve(snapshot(package),as_of=NOW)
    facts=package['months'][0]['facts'];overlay=bind_overlay(package['manifest'],Overlay(**package['overlay']))
    assert ctx.fee_minor==1200000 and ctx.minor_exponent==2 and ctx.currency=='USD'
    for assertion in (None,1,999999999,False,'browser'):
        result=evaluate(package['manifest'],overlay,facts|{'monthly_fee_cents':assertion},package['tenant'],governing_fee=ctx)
        assert result['amount']=='2400.00' and result['governing_pricing_version']=='order-v1'
        assert result['governing_fee_digest']==ctx.digest
    assert evaluate(package['manifest'],overlay,facts,package['tenant'])['amount'] is None


def test_known_zero_needs_no_fee_and_unknown_usage_is_null():
    package=load_package()
    zero=evaluate(package['manifest'],package['overlay'],package['months'][1]['facts']|{'monthly_fee_cents':None},package['tenant'])
    unknown=evaluate(package['manifest'],package['overlay'],package['months'][2]['facts'],package['tenant'])
    assert zero['outcome']=='INELIGIBLE' and zero['rate_units']==0 and zero['amount'] is None
    assert 'governing_fee_digest' not in zero
    assert unknown['outcome']=='INSUFFICIENT_EVIDENCE' and unknown['amount'] is None and 'rate_units' not in unknown


def test_context_copies_replacements_and_deserialization_are_not_issued():
    p=load_package();reg=build_fee_registry(p);ctx=reg.resolve(snapshot(p),as_of=NOW)
    for forged in (replace(ctx,fee_minor=2400000),replace(ctx),copy(ctx),deepcopy(ctx),pickle.loads(pickle.dumps(ctx)),{}):
        with pytest.raises(ValueError):require_governing_fee(forged,p['manifest'],p['overlay'],p['months'][0]['facts'],p['tenant'])
    reg.close()
    with pytest.raises(ValueError,match='revoked'):require_governing_fee(ctx,p['manifest'],p['overlay'],p['months'][0]['facts'],p['tenant'])


@pytest.mark.parametrize('quantity',[Decimal(0),Decimal(2),Decimal('0.5'),True])
def test_contractual_fixed_quantity_cannot_be_minted_by_arrears_invoice(quantity):
    p=load_package();item=entry(p);invoice=replace(item.invoice,lines=(replace(item.invoice.lines[0],quantity=quantity),))
    reg=FeeRegistry((replace(item,invoice=invoice),))
    with pytest.raises(ValueError):reg.resolve(snapshot(p),as_of=NOW)


def test_absent_duplicate_split_and_credit_memo_inputs_refuse():
    p=load_package();item=entry(p)
    for lines in ((),item.invoice.lines*2,(replace(item.invoice.lines[0],id='credit-memo'),)):
        reg=FeeRegistry((replace(item,invoice=replace(item.invoice,lines=lines)),))
        with pytest.raises(ValueError):reg.resolve(snapshot(p),as_of=NOW)
    with pytest.raises(ValueError,match='Duplicate'):FeeRegistry((item,replace(item,entry_id='alias')))


@pytest.mark.parametrize('field,value',[('account','other'),('vendor','Other Vendor'),('contract','other'),('service','Other'),('month','2026-02'),('invoice','other'),('currency','EUR'),('region','other')])
def test_authenticated_envelope_mismatch_never_selects_another_fee(field,value):
    p=load_package();snap=snapshot(p)
    snap=replace(snap,scope=Scope(**(snap.scope.model_dump()|{field:value})))
    with pytest.raises(ValueError):build_fee_registry(p).resolve(snap,as_of=NOW)


@pytest.mark.parametrize('mutate',[lambda b:b['lines'][0].update(amount='24000.00'),lambda b:b['lines'][0].update(account='other'),lambda b:b['lines'].append(dict(b['lines'][0])),lambda b:b['lines'][0].update(kind='unaffected_api')])
def test_signed_body_mismatch_refuses(mutate):
    p=load_package();snap=snapshot(p);body=json.loads(snap.body_json);mutate(body)
    with pytest.raises(ValueError):build_fee_registry(p).resolve(replace(snap,body_json=json.dumps(body)),as_of=NOW)


def test_missing_source_authority_future_known_and_changed_dependencies_refuse(monkeypatch):
    p=load_package()
    with pytest.raises(ValueError):snapshot(p,source_grant_id=None)
    reg=build_fee_registry(p)
    with pytest.raises(ValueError):reg.resolve(snapshot(p),as_of=NOW-timedelta(days=1))
    ctx=reg.resolve(snapshot(p),as_of=NOW)
    monkeypatch.setattr('uptime.governing_fees.dependency_digest',lambda:'f'*64)
    with pytest.raises(ValueError):require_governing_fee(ctx,p['manifest'],p['overlay'],p['months'][0]['facts'],p['tenant'])


def test_positive_registry_lifecycle_requires_current_context_and_preserves_identity(tmp_path):
    from uptime import vendor_registry as catalog
    from uptime.storage import initialize
    p=load_package();path=tmp_path/'registry.sqlite';initialize(path)
    actor=Principal(p['tenant'],'scripted-financial-reviewer','reviewer')
    reg=build_fee_registry(p);ctx=reg.resolve(snapshot(p),as_of=NOW)
    state=catalog.install(path,actor,'northwind',dict(document=p['document'],overlay=p['overlay']))
    controls=[dict(name='January',facts=p['months'][0]['facts'],expected=dict(outcome='ELIGIBLE',amount='2400.00')),
              dict(name='March missing',facts=p['months'][2]['facts'],expected=dict(outcome='INSUFFICIENT_EVIDENCE'))]
    submission=catalog.TestSubmission(revision=state['revision'],tests=controls)
    failed=catalog.submit_tests(path,actor,'northwind',submission)
    assert not failed['checks'][0]['passed']
    state=catalog.submit_tests(path,actor,'northwind',catalog.TestSubmission(revision=failed['revision'],tests=controls),governing_fees=(ctx,))
    assert all(row['passed'] for row in state['checks'])
    for op in ('approve','activate'):
        action=next(a['id'] for a in state['actions'] if a['operation']==op)
        state=catalog.act(path,actor,'northwind',action,governing_fees=(ctx,))
    result=catalog.dispatch(path,actor,'northwind',p['months'][0]['facts'],governing_fee=ctx)
    assert result['amount']=='2400.00'
    missing=catalog.dispatch(path,actor,'northwind',p['months'][0]['facts'])
    assert missing['amount'] is None and missing['id']==result['id'] and missing['obligation_id']==result['obligation_id']
    assert catalog.evaluate_active(path,actor,'northwind',p['months'][0]['facts'],governing_fee=ctx)['amount']=='2400.00'


def test_context_is_stable_across_clock_ticks_but_source_and_interpretation_pins_change():
    p=load_package();reg=build_fee_registry(p);snap=snapshot(p)
    first=reg.resolve(snap,as_of=NOW);later=reg.resolve(snap,as_of=NOW+timedelta(hours=1))
    assert first.digest==later.digest and first.as_of==snap.received_at
    for manifest,overlay in ((p['manifest']|{'filing_days':31},p['overlay']),(p['manifest'],p['overlay']|{'account':'other'})):
        with pytest.raises(ValueError):require_governing_fee(first,manifest,overlay,p['months'][0]['facts'],p['tenant'])
    item=entry(p);versions=(*item.agreement.versions[:-1],replace(item.agreement.versions[-1],signed_at=NOW+timedelta(days=1),effective_at=NOW+timedelta(days=2)))
    reg=FeeRegistry((replace(item,agreement=replace(item.agreement,versions=versions)),))
    with pytest.raises(ValueError,match='not known'):reg.resolve(snap,as_of=NOW+timedelta(days=3))


def test_exact_source_schedule_extra_qualification_or_changed_span_refuses():
    from uptime.pricing_terms import compile_fixed_monthly,validate_fixed_monthly
    terms=load_package()['pricing_agreement'].versions[0].rates[0].fixed_monthly
    for source in (terms.source_text+'Unless later terminated.\n',terms.source_text.replace('must equal one','may equal two'),terms.source_text.replace('UTC','local')):
        with pytest.raises(ValueError):compile_fixed_monthly(source,terms.citation)
    with pytest.raises(ValueError):validate_fixed_monthly(replace(terms,start=1),product=terms.product,version=terms.citation.version,rate=terms.monthly_fee)


def test_catalog_http_uses_only_registered_authenticated_inbox_sources(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from threading import RLock
    from uptime.storage import initialize,database
    from uptime.vendor_api import make_router
    from uptime import vendor_registry as catalog
    p=load_package();path=tmp_path/'api.sqlite';initialize(path)
    actor=Principal(p['tenant'],'scripted-fee-api-reviewer','reviewer')
    state=catalog.install(path,actor,'northwind',dict(document=p['document'],overlay=p['overlay']))
    snap=snapshot(p)
    event=dict(source='billing',kind='invoice',body=json.loads(snap.body_json),digest=snap.evidence_digest,subject=snap.subject,
               source_key_id=snap.source_key_id,source_grant_id=snap.source_grant_id,received_at=snap.received_at)
    # The adapter table is seeded with explicit unit-test records. C's separate
    # signed ingress integration tests establish authentication before this seam.
    with database(path) as db:
        db.execute('CREATE TABLE inbox_claim (tenant TEXT,scope TEXT,state TEXT)')
        db.execute('INSERT INTO inbox_claim VALUES (?,?,?)',(p['tenant'],snap.scope.model_dump_json(),json.dumps({'evidence':[event]})))
        db.commit()
    app=FastAPI();reg=build_fee_registry(p)
    app.include_router(make_router(path,lambda:actor,lambda:actor,lambda p:None,RLock(),governing_fees=reg,trusted_now=lambda:NOW))
    body={'revision':state['revision'],'tests':[dict(name='positive',facts=p['months'][0]['facts'],expected=dict(outcome='ELIGIBLE',amount='2400.00')),dict(name='unknown',facts=p['months'][2]['facts'],expected=dict(outcome='INSUFFICIENT_EVIDENCE'))]}
    with TestClient(app) as client:
        response=client.post('/api/vendors/northwind/tests',json=body)
        assert response.status_code==200,response.text
        tested=response.json();assert all(x['passed'] for x in tested['checks'])
        preview=client.post('/api/vendors/northwind/shadow-preview',json=dict(revision=tested['revision'],facts=p['months'][0]['facts']))
        assert preview.status_code==200 and preview.json()['evaluation']['amount']=='2400.00'
        with database(path) as db:
            event['body']['lines'][0]['amount']='24000.00'
            db.execute('UPDATE inbox_claim SET state=?',(json.dumps({'evidence':[event]}),));db.commit()
        refused=client.post('/api/vendors/northwind/shadow-preview',json=dict(revision=tested['revision'],facts=p['months'][0]['facts']))
        assert refused.json()['evaluation']['amount'] is None
    with pytest.raises(TypeError):make_router(path,lambda:actor,lambda:actor,lambda p:None,RLock(),governing_fees=lambda:1200000)
