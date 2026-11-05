"""Independent synthetic contract and service observations for the second declarative family."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
import sqlite3
import pytest

from uptime.contracts import Principal, fingerprint
from uptime.storage import database, initialize
from uptime.vendor_model import MODEL, validate_proposal
from uptime.vendor_terms import Document,Overlay,bind_overlay
from uptime.vendor_eval import evaluate
from uptime import vendor_registry as registry

P=Principal('weather-tenant','scripted-test-resource-reviewer','reviewer')
ROWS=[
    ('Copper Mesa Networks — altitude service schedule',{'vendor':'Copper Mesa Networks','agreement':'altitude service schedule'}),
    ('Version effective February 1, 2026.',{'effective':['2026-02-01',None]}),
    ('This schedule covers each Barometer Station in the Altitude Survey service.',
     {'scope':{'product':'Altitude Survey','plan':None}}),
    ('Each station has its own availability measurement over each monthly billing cycle.',
     {'period':'resource_billing_month'}),
    ('Downtime means rejected samples or lost acknowledgments caused by instrument gateway failure.',
     {'symptoms':['rejected samples','lost acknowledgments'],'provider_causes':['instrument gateway failure']}),
    ('Customer cable damage and approved calibration windows are excluded.',
     {'exclusions':['Customer cable damage','approved calibration windows']}),
    ('File dated station logs showing account and resource, start and end times, and itemized fees for the affected station.',
     {'evidence':['account_records','resource_intervals','itemized_fees'],'fee_basis':'affected_resource_fees'}),
    ('Below 98%, the credit is 45%; below 99% but at least 98%, the credit is 12.5%.',
     {'tiers':[{'below':'98','credit':'45','at_least':None},{'below':'99','credit':'12.5','at_least':'98'}]}),
    ('Round the credit to the nearest cent, with half cents rounded up.',
     {'rounding':'nearest_cent_half_up'}),
    ('Credit requests must be received by 18:00 UTC on the tenth calendar day after the service month.',
     {'filing':{'kind':'calendar_days','count':10,'utc_time':'18:00','endpoint':'inclusive'}}),
    ('Send the claim to claims@example.invalid. Include the station identifier and log references.',
     {'submission_channel':'claims@example.invalid','request_fields':['station identifier','log references'],'evidence':['request_contents']}),
    ('After verification, Copper Mesa will issue a noncash credit on a future invoice.',
     {'remedy':'future_noncash_credit','evidence':['verification']}),
]
DOC={'name':'Synthetic public instrument service','classification':'synthetic_public','uri':'urn:synthetic:altitude',
     'text':'\n'.join(q for q,_ in ROWS)}
PROPOSAL=[{'quote':q,'field':'resource_terms','value':v} for q,v in ROWS]
OVERLAY={'agreement':'tenant-agreement-A','public_agreement':'altitude service schedule','account':'acc-QW',
         'product':'Field Survey','public_product':'Altitude Survey','plan':'Silver-Private','resource_id':'station-21',
         'currency':'USD','fee_line_ref':'inv-resource-group','effective_from':'2026-03-01','effective_until':'2029-12-31',
         'billing_period':{'kind':'utc_calendar_month','source_ref':'signed-order-page-3','quote':'Our billing periods are UTC calendar months.'}}
BASE=datetime(2026,6,5,tzinfo=UTC)
def interval(ref,left,right,cause='instrument gateway failure',symptom='rejected samples'):
    return {'ref':ref,'account':'acc-QW','resource_id':'station-21',
            'start':(BASE+timedelta(minutes=left)).isoformat(),'end':(BASE+timedelta(minutes=right)).isoformat(),
            'symptom':symptom,'cause':cause}
LINE={'ref':'line-weather','fee_line_ref':'inv-resource-group','account':'acc-QW','resource_id':'station-21',
      'month':'2026-06','kind':'resource_service','amount_cents':10004,'currency':'USD'}
FACTS={k:OVERLAY[k] for k in ('agreement','account','product','plan','resource_id','fee_line_ref')}
FACTS.update(month='2026-06',received_at='2026-07-10T18:00:00Z',monitor_source='synthetic_customer',monitor_ref='monitor-X',
             month_complete=True,itemized_complete=True,intervals=[interval('n1',0,500),interval('n2',400,600)],
             exclusions=[interval('s1',100,267,'Customer cable damage')],
             fee_lines=[LINE,LINE|{'ref':'fee-tax','kind':'tax','amount_cents':1200},LINE|{'ref':'other','resource_id':'unaffected','amount_cents':999999}],
             filing_proof={'verified':True,'ref':'msg-R','account':'acc-QW','resource_id':'station-21',
                           'submitted_to':'claims@example.invalid','fields':{'station identifier':'station-21','log references':'n1,n2'}})
def compiled(doc=DOC,proposal=PROPOSAL):
    return validate_proposal(Document(**doc),proposal,allow_propositions=True)

def result(facts=FACTS,manifest=None,overlay=OVERLAY):
    m=manifest or compiled()
    return evaluate(m,bind_overlay(m,Overlay(**overlay)),facts,P.tenant)


def test_source_quoted_intervals_tiers_monthly_fees_and_credit_rounding():
    m=compiled()
    assert m['effective']==['2026-02-01',None] and m['family']=='resource-month/1'
    assert all(DOC['text'][c['start']:c['end']]==c['quote'] for c in m['citations'])
    r=result()
    assert r['outcome']=='ELIGIBLE' and r['amount']=='12.51'
    assert r['affected_fee_cents']==10004 and r['downtime_microseconds']==433*60000000
    assert r['filing_status']=='TIMELY' and r['issuance_status']=='PENDING_VENDOR_VERIFICATION'


@pytest.mark.parametrize('facts,outcome',[
    ({'monitor_source':'public_status'},'INSUFFICIENT_EVIDENCE'),
    ({'itemized_complete':False},'INSUFFICIENT_EVIDENCE'),
    ({'resource_id':'other-station'},'INSUFFICIENT_EVIDENCE'),
    ({'fee_lines':[LINE|{'resource_id':'other'}]},'INSUFFICIENT_EVIDENCE'),
    ({'fee_lines':[LINE,LINE|{'amount_cents':123}]},'INSUFFICIENT_EVIDENCE'),
    ({'intervals':[interval('a',0,500,'unverified attribution')]},'INSUFFICIENT_EVIDENCE'),
    ({'intervals':[interval('a',0,500,symptom='cosmetic display delay')]},'INELIGIBLE'),
    ({'intervals':[interval('a',0,500,'Customer cable damage')]},'INELIGIBLE'),
    ({'received_at':'2026-07-10T18:00:01Z'},'INELIGIBLE'),
    ({'filing_proof':FACTS['filing_proof']|{'submitted_to':'wrong@example.invalid'}},'INSUFFICIENT_EVIDENCE'),
    ({'filing_proof':FACTS['filing_proof']|{'fields':{}}},'INSUFFICIENT_EVIDENCE'),
    ({'month':'2026-01'},'UNSUPPORTED_RULE'),
    ({'received_at':'2026-07-10T11:00:00-07:00'},'ELIGIBLE'),
    ({'eligible_downtime_minutes':1000},'INSUFFICIENT_EVIDENCE'),
])
def test_contractual_negative_controls(facts,outcome):
    r=result(FACTS|facts)
    assert r['outcome']==outcome
    if outcome!='ELIGIBLE':
        assert r['amount'] is None


def test_exact_seconds_threshold_and_leap_month():
    facts=FACTS|{'intervals':[interval('n',0,432)],'exclusions':[]}
    assert result(facts)['outcome']=='INELIGIBLE'
    with_second=deepcopy(facts)
    with_second['intervals'][0]['end']=(BASE+timedelta(minutes=432,seconds=1)).isoformat()
    assert result(with_second)['outcome']=='ELIGIBLE'
    facts=deepcopy(FACTS)
    facts.update(month='2028-02',received_at='2028-03-10T18:00:00Z',exclusions=[],
                 intervals=[interval('n',0,500)|{'start':'2028-02-29T00:00:00Z','end':'2028-03-01T01:00:00Z'}],
                 fee_lines=[LINE|{'month':'2028-02'}])
    r=result(facts)
    assert r['total_microseconds']==29*86400*1000000 and r['downtime_microseconds']==86400*1000000


def test_rounding_only_when_source_explicit_and_issuance_is_separate():
    m=compiled()
    del m['rounding']
    assert result(manifest=m)['amount']=='12.505'
    receipt={'ref':'sim-voucher-2','verified':True,'kind':'future_invoice_credit','currency':'USD','amount_cents':1251,
             'account':OVERLAY['account'],'resource_id':OVERLAY['resource_id']}
    assert result(FACTS|{'issuance':receipt})['issuance_status']=='SIMULATED_FUTURE_CREDIT_VERIFIED'
    r=result(FACTS|{'issuance':receipt|{'amount_cents':1252}})
    assert r['issuance_status']=='ISSUANCE_REQUIRES_REVIEW' and r['outcome']=='ELIGIBLE'


def test_cycle_cutoff_uses_private_billing_calendar_or_abstains():
    m=compiled()
    m['filing']={'kind':'billing_cycles','count':2,'utc_time':None,'endpoint':'whole_cycle'}
    assert result(FACTS|{'received_at':'2026-08-31T23:59:59Z'},m)['outcome']=='ELIGIBLE'
    assert result(FACTS|{'received_at':'2026-09-01T00:00:00Z'},m)['outcome']=='INELIGIBLE'
    m['filing']['endpoint']='unclear'
    assert result(manifest=m)['outcome']=='UNSUPPORTED_RULE'
    m['filing']['endpoint']='whole_cycle'
    m['period']='resource_utc_calendar_month'
    assert result(manifest=m,overlay=OVERLAY|{'billing_period':None})['outcome']=='INSUFFICIENT_EVIDENCE'
    assert result(FACTS|{'billing_cycles':[{'start':'2026-07-01T00:00:00Z','end':'2026-07-24T00:00:00Z','ref':'cycle-a'},
                                          {'start':'2026-07-24T00:00:00Z','end':'2026-08-24T00:00:00Z','ref':'cycle-b'}]},m,overlay=OVERLAY|{'billing_period':None})['outcome']=='ELIGIBLE'


def test_unknown_references_and_dropped_or_invented_effects_cannot_compile():
    with pytest.raises(ValueError,match='dropped|invented'):
        compiled(proposal=PROPOSAL[:2]+PROPOSAL[3:])
    for text in ['All eligibility is subject to Section 9 of another agreement.','The customer must pay an extra fee.']:
        doc=DOC|{'text':DOC['text']+'\n'+text}
        with pytest.raises(ValueError):
            compiled(doc,PROPOSAL+[{'quote':text,'field':'resource_terms','value':{'nonmaterial':'Introduction.'}}])
    bad=deepcopy(PROPOSAL)
    bad[4]['value']['symptoms']=['absent source definition']
    with pytest.raises(ValueError):
        compiled(proposal=bad)
    overlay=OVERLAY|{'billing_period':None}
    with pytest.raises(ValueError,match='clock'):
        result(overlay=overlay)


def test_review_gate_and_transaction_scoped_active_resolution(monkeypatch,tmp_path):
    path=tmp_path/'test.sqlite'
    initialize(path)
    digest=sha256(DOC['text'].encode()).hexdigest()
    capture={'model':MODEL,'source_sha256':digest,'session':'synthetic-test-model-3','at':'2026-06-01T00:00:00Z',
             'proposal':PROPOSAL,'proposal_sha256':fingerprint(PROPOSAL)}
    (tmp_path/(digest+'.json')).write_text(json.dumps(capture))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS',str(tmp_path))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS','1')
    shadow=registry.install(path,P,'meters',{'document':DOC,'overlay':OVERLAY})
    assert shadow['state']=='SHADOW',shadow
    with pytest.raises(ValueError,match='inactive'):
        registry.evaluate_active(path,P,'meters',FACTS)
    suite=registry.TestSubmission(revision=shadow['revision'],tests=[
        {'name':'June hand calculation','facts':FACTS,'expected':{'outcome':'ELIGIBLE','amount':'12.51'}},
        {'name':'June no delivery loss','facts':FACTS|{'intervals':[]},'expected':{'outcome':'INELIGIBLE'}}])
    current=registry.submit_tests(path,P,'meters',suite)
    for op in ('interpret','approve','activate'):
        action=next(a['id'] for a in current['actions'] if a['operation']==op)
        current=registry.act(path,P,'meters',action)
    with database(path) as db:
        db.execute('BEGIN IMMEDIATE')
        actual=registry.evaluate_active_db(db,P,'meters',FACTS,expected_version=current['active_version'])
        assert actual['amount']=='12.51' and actual['source_sha256']==digest
        db.rollback()
    historical=registry.dispatch(path,P,'meters',FACTS)
    assert historical['version']==actual['version']
    assert any(c['label']=='signed-order-page-3' for c in historical['clauses'])


def test_immutable_public_block_projection_rejects_missing_duplicates_and_model_text():
    from uptime.vendor_resource_terms import project_blocks,public_blocks
    text='  Copper — survey’s system.\r\n\r\n  Next… term.  '
    blocks=public_blocks(text)
    assert [b['text'] for b in blocks]==['Copper — survey’s system.','Next… term.']
    source={'blocks':[{'id':b['id'],'value':{'nonmaterial':'Heading.'}} for b in blocks]}
    projected,index=project_blocks(text,source)
    assert all(text[b['start']:b['end']]==c['quote'] and b['sha256']==sha256(c['quote'].encode()).hexdigest() for b,c in zip(index,projected))
    for wrong in [source['blocks'][::-1],source['blocks'][:1],source['blocks']+source['blocks'][:1],
                  [source['blocks'][0]]*2,[source['blocks'][0]|{'text':'altered text'},source['blocks'][1]]]:
        with pytest.raises(ValueError):
            project_blocks(text,{'blocks':wrong})


def test_cli_block_response_reconstructs_verified_public_artifact(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from uptime.vendor_model import generate,staged_extraction
    def fake_run(args,**kwargs):
        blocks=json.loads(kwargs['input'])['blocks']
        assert [b['text'] for b in blocks]==[r[0] for r in ROWS]
        assert kwargs['env'].get('CLAUDE_CODE_OAUTH_TOKEN')=='test-provider-auth'
        assert 'test-provider-auth' not in kwargs['input']
        response={'blocks':[{'id':b['id'],'value':r[1]} for b,r in zip(blocks,ROWS,strict=True)]}
        return SimpleNamespace(returncode=0,stdout=json.dumps({'session_id':'synthetic-test-blocks','is_error':False,'modelUsage':{MODEL:{}},'result':json.dumps(response)}))
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN','test-provider-auth')
    monkeypatch.setattr('uptime.vendor_model.subprocess.run',fake_run)
    artifact=generate(Document(**DOC),sha256(DOC['text'].encode()).hexdigest(),allow_propositions=True,profile='resource-month')
    assert artifact['protocol']=='public_block_ids/1' and 'test-provider-auth' not in str(artifact)
    dest=tmp_path/(artifact['source_sha256']+'.json')
    dest.write_text(json.dumps(artifact))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS',str(tmp_path))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS','1')
    manifest,receipt=staged_extraction(Document(**DOC))
    assert manifest['family']=='resource-month/1' and receipt['method']=='tool_free_model_propositions'
    artifact['block_index'][0]['end']-=1
    dest.write_text(json.dumps(artifact))
    with pytest.raises(ValueError,match='index'):
        staged_extraction(Document(**DOC))


def test_filing_utc_cannot_supply_missing_measurement_clock():
    wrong=deepcopy(PROPOSAL)
    wrong[3]['value']['period']='resource_utc_calendar_month'
    with pytest.raises(ValueError,match='denominator'):
        compiled(proposal=wrong)
    proof=FACTS['filing_proof']|{'submitted_to':'claims.example@invalid'}
    assert result(FACTS|{'filing_proof':proof})['outcome']=='INSUFFICIENT_EVIDENCE'
    contradiction=OVERLAY|{'billing_period':OVERLAY['billing_period']|{'quote':'Billing uses calendar months but not UTC.'}}
    with pytest.raises(ValueError,match='clock'):
        result(overlay=contradiction)


def test_dst_fold_interval_counts_real_elapsed_time():
    row=interval('fold',0,1)|{'start':'2026-11-01T01:10:00-07:00','end':'2026-11-01T01:10:00-08:00'}
    r=result(FACTS|{'month':'2026-11','intervals':[row],'exclusions':[]})
    assert r['downtime_microseconds']==3600*1000000 and r['outcome']=='INELIGIBLE'


def test_half_up_estimate_matches_independent_decimal_for_cent_residues():
    from decimal import Decimal,ROUND_HALF_UP,localcontext
    manifest=compiled()
    with localcontext() as ctx:
        ctx.prec=40
        for amount in list(range(1,66))+[10**15-1]:
            expected=(Decimal(amount)*Decimal('0.00125')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
            actual=result(FACTS|{'fee_lines':[LINE|{'amount_cents':amount}]},manifest)
            assert actual['service_estimate']==str(expected)
            assert actual['amount']==(str(expected) if expected else None)
            assert actual['outcome']==('ELIGIBLE' if expected else 'INELIGIBLE')


def test_tier_must_bind_percentage_to_correct_threshold_within_same_source_block():
    wrong=deepcopy(PROPOSAL)
    # All four numbers occur in the cited block; this swap would still be a valid decreasing schedule.
    wrong[7]['value']['tiers']=[{'below':'45','credit':'98','at_least':None},
                               {'below':'99','credit':'12.5','at_least':None}]
    with pytest.raises(ValueError,match='tier values'):
        compiled(proposal=wrong)


def extend_source(rows):
    doc=DOC|{'text':DOC['text']+'\n'+'\n'.join(quote for quote,_ in rows)}
    return doc,PROPOSAL+[{'quote':quote,'field':'resource_terms','value':values} for quote,values in rows]


def test_limited_precedence_requires_pinned_private_unamended_record_and_rejects_external_terms():
    phrase='this schedule controls'
    scope='the availability and service credits addressed here'
    text=f'If the customer order conflicts with this schedule, {phrase} only with respect to {scope}.'
    row={'precedence':{'op':'this_sla_controls_conflicts_in_scope','phrase':phrase,'scope':scope}}
    doc,proposal=extend_source([(text,row)])
    m=compiled(doc,proposal)
    attestation={'verified':True,'agreement':OVERLAY['agreement'],'source_sha256':m['document']['sha256'],
                 'effective_from':'2026-02-01','source_ref':'signed-order-4','evidence_sha256':'7'*64,
                 'unamended_terms':['scope','measurement','exclusions','tiers','fee_basis','rounding','filing','remedy']}
    overlay=OVERLAY|{'governing_terms':attestation}
    assert result(manifest=m,overlay=overlay)['amount']=='12.51'
    for invalid in [None,attestation|{'source_sha256':'0'*64},attestation|{'verified':False},
                    attestation|{'effective_from':'2026-02-02'},attestation|{'unamended_terms':['tiers']},
                    attestation|{'agreement':'another-order'}]:
        with pytest.raises(ValueError,match='governing terms'):
            result(manifest=m,overlay=overlay|{'governing_terms':invalid})
    changed=text+' Additional requirements under Section 8 also apply.'
    d,p=extend_source([(changed,row)])
    with pytest.raises(ValueError,match='External terms'):
        compiled(d,p)
    wrong=text.replace('this schedule controls','the master terms control')
    d,p=extend_source([(wrong,{'precedence':row['precedence']|{'phrase':'the master terms control'}})])
    with pytest.raises(ValueError,match='limited controlling'):
        compiled(d,p)


def test_account_conditions_require_scoped_local_findings_and_pinned_referenced_terms():
    one='Downtime due to customer account suspension is excluded.'
    two='Customers in breach of their agreement are ineligible to file a claim.'
    d,p=extend_source([(one,{'account_conditions':[{'op':'account_restriction','effect':'causal_intervals','phrase':'customer account suspension'}]}),
                       (two,{'account_conditions':[{'op':'contract_noncompliance','effect':'filing_precondition','phrase':'breach of their agreement'}]})])
    m=compiled(d,p)
    common=dict(account=OVERLAY['account'],resource_id=OVERLAY['resource_id'],agreement=OVERLAY['agreement'],month=FACTS['month'],
                verified=True,finding='clear',affected_refs=[])
    status=common|{'op':'account_restriction','ref':'local-status-5'}
    compliance=common|{'op':'contract_noncompliance','ref':'local-compliance-7','terms_reviewed':True,
                       'terms_ref':'signed-terms-v3','terms_sha256':'1'*64}
    assert result(manifest=m)['outcome']=='INSUFFICIENT_EVIDENCE'
    for bad in [compliance|{'terms_reviewed':False},compliance|{'terms_sha256':''},compliance|{'account':'another'}]:
        assert result(FACTS|{'condition_evidence':[status,bad]},m)['outcome']=='INSUFFICIENT_EVIDENCE'
    assert result(FACTS|{'condition_evidence':[status,compliance]},m)['outcome']=='ELIGIBLE'
    denied=result(FACTS|{'condition_evidence':[status,compliance|{'finding':'applies'}]},m)
    assert denied['outcome']=='INELIGIBLE' and denied['filing_status']=='BLOCKED_ACCOUNT_CONDITION'
    linked=status|{'finding':'applies','affected_refs':['n1']}
    corrected=result(FACTS|{'condition_evidence':[linked,compliance]},m)
    assert corrected['outcome']=='INELIGIBLE' and corrected['downtime_microseconds']==100*60000000
    wrong=linked|{'affected_refs':['not-in-this-record']}
    assert result(FACTS|{'condition_evidence':[wrong,compliance]},m)['outcome']=='INSUFFICIENT_EVIDENCE'


def test_stable_service_predicate_identifier_requires_literal_source_grounding():
    proposal=deepcopy(PROPOSAL)
    proposal[4]['value']['symptoms']=[{'label':'sample_loss','phrase':'rejected samples'},'lost acknowledgments']
    m=compiled(proposal=proposal)
    assert m['label_bindings']['symptoms']['sample_loss']['block']==5
    assert result(manifest=m)['amount']=='12.51'
    rows=[r|{'symptom':'sample_loss'} for r in FACTS['intervals']]
    assert result(FACTS|{'intervals':rows},m)['amount']=='12.51'
    proposal[4]['value']['symptoms'][0]['phrase']='silent data distortion'
    with pytest.raises(ValueError):
        compiled(proposal=proposal)


def test_omitting_an_entire_payout_band_and_reversing_filing_endpoint_fail_closed():
    omitted = deepcopy(PROPOSAL)
    omitted[7]['value']['tiers'].pop()
    with pytest.raises(ValueError, match='Every percentage'):
        compiled(proposal=omitted)
    wrong_endpoint = deepcopy(PROPOSAL)
    wrong_endpoint[9]['value']['filing']['endpoint'] = 'exclusive'
    with pytest.raises(ValueError, match='clock comparator'):
        compiled(proposal=wrong_endpoint)


@pytest.mark.parametrize(('text', 'mislabeled'), [
    ('The customer must prepay a filing fee.', {'evidence': ['account_records']}),
    ('Submit itemized fees only if the customer purchases priority support.', {'evidence': ['itemized_fees']}),
    ('Public notices appear on our portal.', {'evidence': ['resource_intervals']}),
    ('Round the result to the nearest dollar.', {'nonmaterial': 'Example calculation.'}),
    ('Credit claims expire after a year.', {'evidence': ['request_contents']}),
    ('Cloud support costs 9% of monthly fees.', {'fee_basis': 'affected_resource_fees'}),
    ('The claim has a deadline of two billing cycles following month end.', {'evidence': ['request_contents']}),
])
def test_unmapped_conditions_cannot_hide_behind_a_valid_proposition(text, mislabeled):
    document, proposal = extend_source([(text, mislabeled)])
    with pytest.raises(ValueError):
        compiled(document, proposal)
