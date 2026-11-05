"""Decision65 primitive and compiler controls; money remains gated pending65a."""
from copy import deepcopy
import pytest
from uptime.credit_steps import completed, rate, final_cents
from uptime.vendor_terms import Document, Overlay, compile_terms, bind_overlay
from uptime.vendor_eval import evaluate, rate_for, generated_checks

DOCUMENT = {'name': 'Northwind Cloud Service Level Agreement', 'classification': 'synthetic_public', 'uri': 'urn:northwind:NW-2026-001:sla', 'text': 'Service Level Agreement\nVendor: Northwind Cloud\nAgreement: NW-2026-001\nEffective: 2026-01-01 through 2026-12-31\nAvailability is measured over each UTC calendar month.\nFor Cloud Hosting on the Business plan, the monthly uptime target is 99.9%; each completed 0.1 percentage point of shortfall below the target earns a 10% service credit, capped at 100%.\nRound the resulting service credit once to the nearest cent, with half cents rounded up; do not round availability or shortfall before counting completed increments.\nClaims must be received within 30 calendar days after month end.\nService credits apply to affected monthly fees on a future invoice.'}


def manifest():
    return compile_terms(Document(**DOCUMENT))


@pytest.mark.parametrize('available,steps,units',[(1000000,0,0),(999000,0,0),(998001,0,0),(998000,1,10000000),(997999,1,10000000),(997000,2,20000000),(989001,9,90000000),(989000,10,100000000),(0,999,100000000)])
def test_completed_steps_exact_boundaries(available,steps,units):
    rule=manifest()['credit_rule']
    assert completed(rule,available,1000000)==steps
    assert rate(rule,available,1000000)==units


@pytest.mark.parametrize('down,steps',[(89,0),(90,1),(133,1),(134,2),(135,2)])
def test_completed_steps_january_integer_grid(down,steps):
    assert completed(manifest()['credit_rule'],44640-down,44640)==steps


@pytest.mark.parametrize('fee,cents',[(5,1),(15,2),(1234565,123457)])
def test_completed_steps_final_half_up(fee,cents):
    from decimal import localcontext
    for precision in (2,60):
        with localcontext() as ctx:
            ctx.prec=precision
            assert final_cents(fee,10000000)==cents


def test_completed_steps_cap_and_other_contract_parameters():
    rule=manifest()['credit_rule']|{'cap_units':25000000}
    assert [rate(rule,a,1000000) for a in (997000,996500,996000,0)]==[20000000,20000000,25000000,25000000]
    doc=deepcopy(DOCUMENT)
    doc['text']=doc['text'].replace('Northwind Cloud','Juniper Transit').replace('Cloud Hosting','Signal Feed').replace('Business','Enterprise').replace('99.9%','99.5%').replace('completed 0.1','completed 0.25').replace('a 10%','a 5%').replace('capped at 100%','capped at 50%')
    parsed=compile_terms(Document(**doc))
    assert rate_for(parsed,'Signal Feed','Enterprise',990000,1000000)[0]==10000000
    assert rate(parsed['credit_rule'],0,1000000)==50000000


@pytest.mark.parametrize('before,after',[('each completed','each started'),('each completed','each partial'),('0.1 percentage point','0.1 percent or part thereof'),('capped at 100%','capped at USD 100'),('capped at 100%','capped at 101%'),('completed 0.1','completed 0'),('completed 0.1','completed 0.0000001'),('capped at 100%','with no cap'),('capped at 100%.','capped at 100%, unless an exception applies.'),('with half cents rounded up','with half cents rounded to even')])
def test_completed_steps_unsupported_language_refuses(before,after):
    with pytest.raises(ValueError):
        compile_terms(Document(**(DOCUMENT|{'text':DOCUMENT['text'].replace(before,after)})))


def test_completed_steps_export_generated_and_unknown_variant():
    from uptime.vendor_model import validate_proposal,_typed_values
    m=manifest()
    assert 'tiers' not in m and all(x['passed'] for x in generated_checks(m))
    rows=[dict(quote=c['quote'],field=field,value=value) for c,(field,value) in zip(m['citations'],_typed_values(m),strict=True)]
    assert validate_proposal(Document(**DOCUMENT),rows)==m
    for broken in (m|{'tiers':[]},m|{'credit_rule':m['credit_rule']|{'kind':'unknown'}}):
        with pytest.raises(ValueError): rate_for(broken,'Cloud Hosting','Business',44505,44640)
        with pytest.raises(ValueError): generated_checks(broken)


def test_completed_steps_cannot_use_untrusted_billed_fee():
    overlay={'account':'harborline-001','agreement':'NW-2026-001','product':'Cloud Hosting','plan':'Business','fee_line_ref':'cloud-hosting-monthly','effective_from':'2026-01-01','effective_until':'2026-12-31'}
    facts=overlay|{'month':'2026-01','eligible_downtime_minutes':135,'monitor_source':'simulated_vendor','month_complete':True,'exclusions_removed':True,'monthly_fee_cents':1200000,'received_at':'2026-03-01T12:00:00Z'}
    facts.pop('effective_from');facts.pop('effective_until')
    result=evaluate(manifest(),overlay,facts,'bears')
    assert result['outcome']=='INSUFFICIENT_EVIDENCE' and result['amount'] is None
    assert result['missing']==['governing_fee_context']
    assert result['claim_cutoff_exclusive']=='2026-03-03T00:00:00+00:00'
