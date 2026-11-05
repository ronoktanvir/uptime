"""Independent fixed-period, attested aggregate instrument subscription controls."""
from copy import deepcopy
from hashlib import sha256

import pytest

from uptime.contracts import fingerprint
from uptime.vendor_model import validate_proposal
from uptime.vendor_terms import Document, Overlay, bind_overlay
from uptime.vendor_eval import evaluate

ROWS=[
    ('Provider: Heliograph Navigation',{'vendor':'Heliograph Navigation'}),
    ('The Compass Feed service uses the Marine plan.',{'scope':{'product':'Compass Feed','plan':'Marine'}}),
    ('This subscription covers 2027-02-01T00:00:00Z inclusive to 2027-03-01T00:00:00Z exclusive.',
     {'fixed_period':{'start':'2027-02-01T00:00:00Z','end':'2027-03-01T00:00:00Z'}}),
    ('Monthly availability is 100 times (40,320 minus unavailable minutes) divided by 40,320.',
     {'interval_measurement':['availability_ratio']}),
    ('Monthly availability below 98.75% receives a 17% service credit.',
     {'tiers':[{'below':'98.75','credit':'17','at_least':None}]}),
    ('Use the paid recurring subscription fee on the itemized invoice.',{'service_fee':'paid_recurring_subscription'}),
    ('Exclude compass installation charges.',{'fee_exclusions':['compass installation charges']}),
    ('Round credits to the nearest cent, half up.',{'rounding':'nearest_cent_half_up'}),
    ('The remedy is a noncash service credit.',{'remedy':'noncash_service_credit'}),
    ('The claim is due within 6 days after the service month, no later than 2027-03-07T00:00:00Z inclusive.',
     {'fixed_filing':{'at':'2027-03-07T00:00:00Z','endpoint':'inclusive'}}),
    ('The provider status record of unavailable minutes is authoritative.',{'aggregate_monitor':'authoritative_vendor_minutes'}),
    ('Records must have source identifiers, recorded timestamps and content hashes; missing records leave eligibility unknown.',
     {'record_integrity':['source_identifier','recorded_timestamp','content_hash','missing_unknown']}),
]
DOC={'name':'Synthetic Compass Terms','classification':'synthetic_public','uri':'urn:synthetic:compass','text':'\n'.join(q for q,_ in ROWS)}
OVERLAY={'agreement':'Compass-7','account':'shipping-7','product':'Compass Feed','plan':'Marine','effective_from':'2027-02-01',
         'effective_until':'2027-02-28','currency':'USD','fee_line_ref':'compass-subscription'}
SCOPE={k:OVERLAY[k] for k in ('agreement','account','product','plan')}
SCOPE['month']='2027-02'


def manifest(rows=ROWS):
    doc=DOC|{'text':'\n'.join(q for q,_ in rows)}
    return validate_proposal(Document(**doc),[{'quote':q,'field':'resource_terms','value':v} for q,v in rows],allow_propositions=True)


def record(ref,content):
    return dict(**SCOPE,ref=ref,verified=True,complete=True,recorded_at='2027-03-02T12:00:00Z',
                content=content,content_sha256=fingerprint(content))


def facts():
    return dict(**SCOPE,fee_line_ref=OVERLAY['fee_line_ref'],
        service_monitor=record('status-7',{'source':'simulated_vendor','unavailable_minutes':505}),
        service_invoice=record('invoice-7',{'currency':'USD','paid':True,'lines':[
            {'ref':'compass-subscription','kind':'recurring_subscription','category':'subscription','amount_cents':12345},
            {'ref':'compass-install','kind':'setup','category':'compass installation charges','amount_cents':7300}]}),
        filing_proof=dict(**SCOPE,verified=True,ref='claim-7',received_at='2027-03-07T00:00:00Z'))


def run(data, m=None):
    from test_vendor_semantic_bindings import reviewed_context
    m=m or manifest()
    bound=bind_overlay(m,Overlay(**OVERLAY))
    return evaluate(m,bound,data,'independent-compass',bindings=reviewed_context(m,bound,tenant='independent-compass'))


def test_attested_aggregate_source_exact_month_basis_threshold_and_fixed_clock():
    data=facts()
    assert run(data)['amount']=='20.99'
    data['service_monitor']=record('status-8',{'source':'simulated_vendor','unavailable_minutes':504})
    assert run(data)['outcome']=='INELIGIBLE'
    data=facts()
    data['filing_proof']['received_at']='2027-03-07T00:00:00.000001Z'
    assert run(data)['filing_status']=='OUTSIDE_WINDOW'


@pytest.mark.parametrize('minutes', [50.4, '50.4', '5.04e1'])
def test_fractional_minutes_at_strict_threshold_are_exact(minutes):
    rows = deepcopy(ROWS)
    rows[4] = (rows[4][0].replace('98.75', '99.875'),
               {'tiers':[{'below':'99.875','credit':'17','at_least':None}]})
    contract = manifest(rows)
    data = facts()
    data['service_monitor'] = record('fractional-equality', {'source':'simulated_vendor','unavailable_minutes':minutes})
    result = run(data, contract)
    assert result['outcome'] == 'INELIGIBLE' and result['amount'] is None
    assert result['downtime_microseconds'] == 3_024_000_000
    for duration, outcome in [('50.39999995', 'INELIGIBLE'), ('50.40000005', 'ELIGIBLE')]:
        data['service_monitor'] = record('fractional-boundary', {'source':'simulated_vendor','unavailable_minutes':duration})
        result = run(data, contract)
        assert result['outcome'] == outcome
        if outcome == 'ELIGIBLE':
            assert result['amount'] == '20.99'


@pytest.mark.parametrize('minutes', [True, None, [], 'NaN', 'Infinity', '-0.1', '0.000000001', 40320.1,
                                   '1e999', '1e-999', '1e99999999999999999999999', '1e-999999999'])
def test_invalid_or_out_of_month_durations_abstain(minutes):
    data = facts()
    data['service_monitor'] = record('invalid-duration', {'source':'simulated_vendor','unavailable_minutes':minutes})
    result = run(data)
    assert result['outcome'] == 'INSUFFICIENT_EVIDENCE' and result['amount'] is None


@pytest.mark.parametrize('record_name',['service_monitor','service_invoice'])
def test_missing_or_unbound_evidence_never_becomes_a_zero_observation(record_name):
    data=facts()
    evidence=data.pop(record_name)
    assert run(data)['outcome']=='INSUFFICIENT_EVIDENCE'
    for changes in ({'content_sha256':'0'*64},{'account':'other'},{'month':'2027-03'},{'recorded_at':'unknown'},{'verified':False}):
        assert run(data|{record_name:evidence|changes})['outcome']=='INSUFFICIENT_EVIDENCE'


def test_wrong_stated_duration_and_ungrounded_clock_are_rejected():
    rows=deepcopy(ROWS)
    rows[3]=(rows[3][0].replace('40,320','43,200'),rows[3][1])
    with pytest.raises(ValueError,match='denominator'):
        manifest(rows)
    rows=deepcopy(ROWS)
    rows[9]=(rows[9][0].replace('within 6 days','within 7 days'),rows[9][1])
    with pytest.raises(ValueError,match='relative filing'):
        manifest(rows)


def test_unpaid_or_unclassified_fee_and_unseen_invoiced_categories_abstain():
    data=facts()
    invoice=data['service_invoice']['content']
    invoice['paid']=False
    data['service_invoice']=record('unpaid',invoice)
    assert run(data)['outcome']=='INSUFFICIENT_EVIDENCE'
    data=facts()
    invoice=data['service_invoice']['content']
    invoice['lines'][1]['category']='unclassified setup'
    data['service_invoice']=record('unclassified',invoice)
    assert run(data)['outcome']=='INSUFFICIENT_EVIDENCE'


def test_service_aggregate_signed_api_produces_case_and_rollback(tmp_path, monkeypatch):
    import json
    from scripts.film_demo import serve
    from scripts.rehearse_vendor import exercise
    from uptime.vendor_model import MODEL
    from uptime.vendor_resource_terms import public_blocks
    from uptime.auth import SCRIPT
    import secrets

    proposal=[{'quote':q,'field':'resource_terms','value':v} for q,v in ROWS]
    blocks=public_blocks(DOC['text'])
    raw={'blocks':[{'id':b['id'],'value':r['value']} for b,r in zip(blocks,proposal,strict=True)]}
    digest=sha256(DOC['text'].encode()).hexdigest()
    staged={'model':MODEL,'source_sha256':digest,'session':'scripted-test-service-month','at':'2027-02-01T00:00:00Z',
            'proposal':proposal,'proposal_sha256':fingerprint(proposal),'protocol':'public_block_ids/1',
            'block_index':[{k:v for k,v in b.items() if k!='text'} for b in blocks],'raw_proposal_sha256':fingerprint(raw)}
    (tmp_path/(digest+'.json')).write_text(json.dumps(staged))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS',str(tmp_path))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS','1')
    data=facts()
    equality=facts()
    equality['service_monitor']=record('threshold',{'source':'simulated_vendor','unavailable_minutes':504})
    scenarios=[{'name':'scoped fee control','facts':data,'expected':{'outcome':'ELIGIBLE','amount':'20.99'}},
               {'name':'exact equality','facts':equality,'expected':{'outcome':'INELIGIBLE'}}]
    secret=secrets.token_urlsafe(32)
    from test_vendor_semantic_bindings import review_submission
    terms=manifest()
    review=review_submission(terms,bind_overlay(terms,Overlay(**OVERLAY)),DOC['text'])
    with serve(tmp_path/'replay.sqlite',secret) as origin:
        receipt=exercise(DOC,OVERLAY,scenarios,origin,secret,semantic_review=review)
    assert receipt['human_approval'] is False and receipt['authority']==SCRIPT
    assert receipt['results'][0]['amount']=='20.99'
    assert receipt['operations'][-2]['operation']=='rolled-back dispatch denied'


def test_source_version_required_heading_and_duplicate_zero_boundary_are_accounted():
    rows=deepcopy(ROWS)
    rows.insert(0,('Version G7-2028. Fictional source; no real commercial authority.',{'nonmaterial':'Source revision.'}))
    rows.insert(1,('5. Required evidence',{'nonmaterial':'Section heading.'}))
    text,term=rows[6]
    rows[6]=(text+' Availability equal to or above 98.75% earns no credit.',term|{'boundary':'strict_below'})
    assert manifest(rows)['zero_at_or_above']==98750000
    rows[6]=(rows[6][0].replace('above 98.75%','above 99%'),rows[6][1])
    with pytest.raises(ValueError,match='Zero-rate|percentage'):
        manifest(rows)


def test_symbolic_duration_definitions_and_formula_roles_are_enforced():
    from test_vendor_resource import compiled, extend_source
    rows=[
        ('Let A be every elapsed second in the month and B be the unavailable seconds.',
         {'measurement_symbols': {'total':{'symbol':'A','phrase':'Let A be every elapsed second in the month'},
                                  'down':{'symbol':'B','phrase':'B be the unavailable seconds'}}}),
        ('Availability is 100 multiplied by (A minus B) divided by A.',
         {'interval_measurement':['availability_ratio']}),
    ]
    assert compiled(*extend_source(rows))['formula_symbols']=={'total':'A','down':'B'}
    rows[1]=(rows[1][0].replace('(A minus B) divided by A','(B minus A) divided by B'),rows[1][1])
    with pytest.raises(ValueError,match='independent duration'):
        compiled(*extend_source(rows))


def test_zero_band_and_monthly_limit_must_match_positive_tiers():
    from test_vendor_resource import compiled, extend_source
    rows=[('At least 99 percent earns zero credit.', {'zero_band':{'at_least':'99'}}),
          ('One credit per month has a maximum of 45 percent.', {'monthly_limit':{'one_per_scope':True,'percent':'45'}})]
    assert compiled(*extend_source(rows))['monthly_maximum']==45000000
    rows[1]=(rows[1][0].replace('45','46'),{'monthly_limit':{'one_per_scope':True,'percent':'46'}})
    with pytest.raises(ValueError,match='ceiling'):
        compiled(*extend_source(rows))
