"""Public authored financial inputs; exact stepped math and existing pricing engine."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime,timedelta
from decimal import Decimal,localcontext
from hashlib import sha256
import json
from pathlib import Path
import shutil

import pytest

from fixtures.northwind.loader import ROOT,load_package,governing_fee,verify_package,build_fee_registry
from uptime.credit_steps import completed,rate,final_cents
from uptime.vendor_eval import evaluate,rate_for,generated_checks
from uptime.vendor_terms import Document,Overlay,compile_terms,bind_overlay,candidate_version


def fee_contexts(package):
    from uptime.governing_fees import authenticated_invoice_snapshot
    from uptime.correspondence_types import Scope
    from uptime.contracts import fingerprint
    registry=build_fee_registry(package);contexts=[]
    for row in package['months']:
        body={'kind':'invoice','lines':[{'id':line.id,'kind':'affected_api','amount':str(line.net)} for line in row['invoice'].lines]}
        event=dict(source='billing',kind='invoice',body=body,digest=fingerprint(body),subject='scripted-financial-source',
            source_key_id='unit-test-key',source_grant_id='unit-test-grant',received_at=row['facts']['received_at'])
        snap=authenticated_invoice_snapshot(package['tenant'],Scope(**row['scope']),event)
        contexts.append(registry.resolve(snap,as_of=datetime.fromisoformat(row['facts']['received_at'])))
    return tuple(contexts)


def actual_rows(package):
    result={}
    for row,context in zip(package['months'],fee_contexts(package),strict=True):
        actual=evaluate(package['manifest'],package['overlay'],row['facts'],package['tenant'],governing_fee=context)
        result[row['month']]=dict(outcome=actual['outcome'],amount=actual['amount'],credit_units=actual.get('rate_units'),
            completed_steps=actual.get('completed_steps'),governing_fee=str(row['pricing_result'].lines[0].expected),
            price_exposure=str(row['pricing_result'].overcharge),price_version=row['governing_fee_version'],
            cutoff_exclusive=actual['claim_cutoff_exclusive'])
    return result


def test_three_months_follow_source_and_pricing_without_shared_financial_obligation():
    package=load_package()
    assert actual_rows(package)==json.loads((ROOT/'expectations.json').read_text())
    assert package['months'][2]['pricing_result'].stage=='PREPAYMENT_REVIEW'
    assert package['months'][1]['invoice'].issued_at==datetime.fromisoformat('2026-03-01T09:00:00Z')
    assert package['months'][1]['governing_fee_version']=='order-v1'
    assert 'tiers' not in package['manifest']
    assert package['manifest']['credit_rule']['kind']=='completed_steps'


@pytest.mark.parametrize('available,expected_steps,expected_rate',[
    (1000000,0,0),(999000,0,0),(998001,0,0),(998000,1,10000000),
    (997999,1,10000000),(997000,2,20000000),(989001,9,90000000),(989000,10,100000000),(0,999,100000000)])
def test_exact_integer_ratio_boundaries_and_cap(available,expected_steps,expected_rate):
    rule=load_package()['manifest']['credit_rule']
    assert completed(rule,available,1000000)==expected_steps
    assert rate(rule,available,1000000)==expected_rate


@pytest.mark.parametrize('downtime,steps',[(89,0),(90,1),(133,1),(134,2),(135,2)])
def test_real_january_minute_grid_never_rounds_uptime(downtime,steps):
    rule=load_package()['manifest']['credit_rule']
    assert completed(rule,44640-downtime,44640)==steps


@pytest.mark.parametrize('fee,cents',[(5,1),(15,2),(1234565,123457)])
def test_final_half_up_ties_are_nonvacuous_and_context_independent(fee,cents):
    for precision in (2,60):
        with localcontext() as context:
            context.prec=precision
            assert final_cents(fee,10000000)==cents
    # 0.5 cent at the first vector distinguishes HALF_UP from HALF_EVEN.
    if fee==5:
        assert Decimal('0.5').quantize(Decimal('1'))==0 and cents==1


def test_nonmultiple_cap_and_second_vendor_parameters_are_generic():
    package=load_package()
    document=deepcopy(package['document'])
    document['text']=document['text'].replace('Northwind Cloud','Juniper Transit').replace('NW-2026-001','JT-41').replace(
        'Cloud Hosting','Signal Feed').replace('Business','Enterprise').replace('99.9%','99.5%').replace(
        'completed 0.1','completed 0.25').replace('a 10%','a 5%').replace('capped at 100%','capped at 50%')
    manifest=compile_terms(Document(**document))
    rule=manifest['credit_rule']
    assert rate_for(manifest,'Signal Feed','Enterprise',990000,1000000)==(10000000,rule['citation'])
    assert rate(rule,0,1000000)==50000000
    original=package['manifest']['credit_rule']|{'cap_units':25000000}
    assert [rate(original,a,1000000) for a in (997000,996500,996000,0)]==[20000000,20000000,25000000,25000000]


@pytest.mark.parametrize('available,total',[(True,100),(1,False),(1.0,100),(-1,100),(101,100),(0,0),(1,10**19)])
def test_invalid_ratio_never_becomes_a_number(available,total):
    with pytest.raises(ValueError):
        rate(load_package()['manifest']['credit_rule'],available,total)


@pytest.mark.parametrize('replacement',[
    ('each completed','each started'),('each completed','each partial'),('0.1 percentage point','0.1 percent or part thereof'),
    ('capped at 100%','capped at USD 100'),('capped at 100%','capped at 101%'),
    ('completed 0.1','completed 0'),('completed 0.1','completed 0.0000001'),
    ('capped at 100%','with no cap'),('capped at 100%.','capped at 100%, unless a special exception applies.'),
    ('with half cents rounded up','with half cents rounded to even'),
    ('the resulting service credit once','the Signal Feed service credit once')])
def test_alternate_or_ambiguous_material_language_refuses(replacement):
    document=deepcopy(load_package()['document'])
    assert replacement[0] in document['text']
    document['text']=document['text'].replace(*replacement)
    with pytest.raises(ValueError):compile_terms(Document(**document))


def test_missing_rounding_duplicate_steps_and_mixed_rules_refuse():
    document=load_package()['document']
    rows=document['text'].splitlines()
    variants=[rows[:6]+rows[7:],rows+[rows[5]],rows+[
        'For Cloud Hosting on the Business plan, monthly availability below 99% earns a 50% service credit.']]
    for lines in variants:
        with pytest.raises(ValueError):compile_terms(Document(**(document|{'text':'\n'.join(lines)})))


def test_unknown_variant_or_tier_injection_cannot_silently_return_zero():
    package=load_package();manifest=package['manifest'];facts=package['months'][0]['facts']
    for broken in (manifest|{'tiers':[]},manifest|{'credit_rule':manifest['credit_rule']|{'kind':'future_unknown'}}):
        with pytest.raises(ValueError):rate_for(broken,'Cloud Hosting','Business',44505,44640)
        with pytest.raises(ValueError):generated_checks(broken)
        with pytest.raises(ValueError):bind_overlay(broken,Overlay(**package['overlay']))
        actual=evaluate(broken,package['overlay'],facts,package['tenant'])
        assert actual['outcome']=='UNSUPPORTED_RULE' and actual['amount'] is None


def test_source_export_and_rule_parameter_changes_are_pinned():
    from uptime.vendor_model import validate_proposal,_typed_values
    package=load_package();manifest=package['manifest'];document=Document(**package['document'])
    rows=[dict(quote=c['quote'],field=field,value=value) for c,(field,value) in
          zip(manifest['citations'],_typed_values(manifest),strict=True)]
    assert validate_proposal(document,rows)==manifest
    for field in ('target_units','step_units','credit_units','cap_units','citation'):
        changed=deepcopy(manifest);changed['credit_rule'][field]+=1
        assert candidate_version(changed,package['overlay'],{})!=candidate_version(manifest,package['overlay'],{})
    broken=deepcopy(rows);broken[5]['value']['step_units']+=1
    with pytest.raises(ValueError):validate_proposal(document,broken)
    assert all(document.text[c['start']:c['end']]==c['quote'] for c in manifest['citations'])


def test_filing_cutoff_is_exclusive_after_thirty_full_days_and_receipt_is_required():
    package=load_package();base=package['months'][0]['facts'];manifest=package['manifest'];overlay=package['overlay']
    for month,cutoff in [('2026-01','2026-03-03T00:00:00Z'),('2026-02','2026-03-31T00:00:00Z'),('2028-02','2028-03-31T00:00:00Z')]:
        terms=deepcopy(manifest);terms['effective'][1]='2028-12-31'
        mapping=overlay|{'effective_until':'2028-12-31'}
        facts=base|{'month':month,'monitor_month':month,'fee_month':month,'eligible_downtime_minutes':150}
        stamp=datetime.fromisoformat(cutoff)
        actual=evaluate(terms,mapping,facts|{'received_at':(stamp-timedelta(microseconds=1)).isoformat()},package['tenant'])
        assert actual['filing_status']=='TIMELY' and actual['claim_cutoff_exclusive']==stamp.isoformat()
        assert actual['amount'] is None and actual['missing']==['governing_fee_context']
        assert evaluate(terms,mapping,facts|{'received_at':stamp.isoformat()},package['tenant'])['filing_status']=='OUTSIDE_WINDOW'
        missing=evaluate(terms,mapping,{k:v for k,v in facts.items() if k!='received_at'},package['tenant'])
        assert missing['outcome']=='INSUFFICIENT_EVIDENCE' and missing['amount'] is None


def test_fee_base_comes_from_governing_price_and_tax_and_extras_are_excluded():
    from uptime.pricing import InvoiceLine
    package=load_package();row=package['months'][2];invoice=row['invoice'];agreement=package['pricing_agreement']
    lines=(replace(invoice.lines[0],tax=Decimal('100.00')),InvoiceLine('support','Premium Support',None,None,
        invoice.lines[0].start,invoice.lines[0].end,Decimal('250.00'),Decimal('25.00'),None))
    changed=replace(invoice,lines=lines,total=Decimal('12375.00'))
    cents,finding,result=governing_fee(agreement,changed,'Cloud Hosting','cloud-hosting-monthly',as_of=datetime.fromisoformat(row['facts']['received_at']))
    assert cents==1100000 and result.overcharge==Decimal('1000.00')
    january=package['months'][0]
    assert governing_fee(agreement,replace(january['invoice'],issued_at=invoice.issued_at),'Cloud Hosting','cloud-hosting-monthly')[0]==1200000
    with pytest.raises(ValueError):governing_fee(agreement,replace(changed,lines=(replace(lines[0],tax=None),lines[1])),'Cloud Hosting','cloud-hosting-monthly')


def test_price_never_infers_a_fee_from_an_unpriced_ceiling_and_missing_signatures_refuse():
    package=load_package();agreement=package['pricing_agreement'];invoice=package['months'][2]['invoice']
    # A ceiling with no priced service rate is not a payable fee.
    versions=(*agreement.versions[:-1],replace(agreement.versions[-1],rates=()))
    with pytest.raises(ValueError):governing_fee(replace(agreement,versions=versions),invoice,'Cloud Hosting','cloud-hosting-monthly')
    versions=(*agreement.versions[:-1],replace(agreement.versions[-1],signatories=()))
    with pytest.raises(ValueError):governing_fee(replace(agreement,versions=versions),invoice,'Cloud Hosting','cloud-hosting-monthly')


def test_expectations_are_not_engine_inputs_and_wrong_comparison_fails(tmp_path):
    copied=tmp_path/'package';shutil.copytree(ROOT,copied)
    expected=json.loads((copied/'expectations.json').read_text());original=actual_rows(load_package(copied))
    (copied/'expectations.json').unlink()
    assert actual_rows(load_package(copied))==original
    expected['2026-01']['amount']='999999.99'
    (copied/'expectations.json').write_text(json.dumps(expected))
    assert actual_rows(load_package(copied))==original
    with pytest.raises(AssertionError):assert actual_rows(load_package(copied))==json.loads((copied/'expectations.json').read_text())


def test_local_signature_specimens_and_source_hashes_cannot_be_relabeled_as_external(tmp_path):
    package=load_package()
    assert all(s['kind']=='LOCAL_TEST_SIGNATURE' and s['certificate'] is None for s in package['signature_records'])
    assert all(s['payload']['scenario_signed_at']!=s['payload']['created_at'] for s in package['signature_records'])
    copied=tmp_path/'package';shutil.copytree(ROOT,copied)
    (copied/'order-form.txt').write_text((copied/'order-form.txt').read_text().replace('12,000.00','13,000.00'))
    with pytest.raises(ValueError,match='input changed'):verify_package(copied)


def test_ordinary_registry_test_lifecycle_and_export_keep_step_variant(tmp_path):
    from uptime import vendor_registry as registry
    from uptime.contracts import Principal
    from uptime.storage import initialize
    package=load_package();path=tmp_path/'steps.sqlite';initialize(path)
    principal=Principal(package['tenant'],'scripted-northwind-financial-test','reviewer')
    state=registry.install(path,principal,'cloud',dict(document=package['document'],overlay=package['overlay']))
    assert state['state']=='SHADOW' and all(t['passed'] for t in state['generated_tests'])
    controls=[dict(name='complete month',facts=package['months'][0]['facts'],expected=dict(outcome='ELIGIBLE',amount='2400.00')),
              dict(name='incomplete month',facts=package['months'][2]['facts'],expected=dict(outcome='INSUFFICIENT_EVIDENCE'))]
    state=registry.submit_tests(path,principal,'cloud',registry.TestSubmission(revision=state['revision'],tests=controls),governing_fees=fee_contexts(package))
    for operation in ('approve','activate'):
        action=next(a['id'] for a in state['actions'] if a['operation']==operation)
        state=registry.act(path,principal,'cloud',action,governing_fees=fee_contexts(package))
    actual=registry.dispatch(path,principal,'cloud',package['months'][0]['facts'],governing_fee=fee_contexts(package)[0])
    assert actual['amount']=='2400.00'
    assert 'tiers' not in registry.get_vendor(path,principal,'cloud')['manifest']
