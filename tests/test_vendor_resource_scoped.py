"""Independently composed regional capability, intersecting monitors and a supplier-response filing clock."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from test_vendor_resource import FACTS, OVERLAY, LINE, compiled, extend_source, result

ROW = [
    ('The signed subscription must bind each account and region separately and accept version R3.',
     {'subscription': {'scope': 'account_product_region', 'signed_record': True, 'version': 'R3'}}),
    ('Regions include North and South. Trial accounts and the separate Archive product are excluded.',
     {'subscription': {'regions':['North','South'], 'excluded_types':['Trial'], 'excluded_products':['Archive']}}),
    ('A subscription must be active for the whole month.', {'subscription': {'active_full_month': True}}),
    ('Both customer status "samples lost" and provider status "station unavailable" must overlap for time to count. '
     'Customer "degraded" and provider "running" do not qualify.',
     {'telemetry': {'join':'intersect_customer_provider', 'provider_status':'station unavailable','customer_status':'samples lost',
                      'provider_nonqualifying':['running'],'customer_nonqualifying':['degraded']}}),
    ('The customer recording system needs a signed custodian statement; missing records leave the result unknown.',
     {'telemetry': {'custodian':True, 'missing_unknown':True}}),
    ('Use only paid recurring station fees after discounts and fee refunds in USD.',
     {'fee_settlement':['paid_recurring_only','subtract_fee_refunds','usd_only'], 'fee_adjustment':'after_discounts'}),
    ('The support portal receipt timestamp controls the filing deadline.', {'original_receipt':'portal_received_at'}),
    ('An initial ticket must include the station identifier. Submit any outstanding log references to the same ticket '
     'within four elapsed days of delivery of an evidence request or written denial, inclusive.',
     {'cure_clock':{'count':4,'unit':'elapsed_days','trigger':['evidence_request','denial'],'endpoint':'inclusive',
                    'scope':'same_ticket','initial_fields':['station identifier']}}),
]
SCOPE = {k: OVERLAY[k] for k in ('account','agreement','product','resource_id')}
SCOPE.update(region='North',month=FACTS['month'])
BASE = datetime(2026,6,1,tzinfo=UTC)


def subscription():
    return OVERLAY | {'subscription_record':{k:v for k,v in dict(verified=True,signed=True,ref='order-29',**SCOPE,
                contract_version='R3',plan=OVERLAY['plan'],active_from='2026-04-01',active_until='2026-11-30',
                subscription_type='Paid Survey').items() if k not in ('month','resource_id')}}


def monitor(source, status, intervals):
    ident = {k:SCOPE[k] for k in ('account','product','region','resource_id')}
    records = [{**ident,'ref':source+'-'+str(i),'status':status,'start':(BASE+timedelta(minutes=a)).isoformat(),
                'end':(BASE+timedelta(minutes=b)).isoformat()} for i,(a,b) in enumerate(intervals)]
    return {**SCOPE,'verified':True,'complete':True,'source_id':source,'ref':'report-'+source,'records':records,
            'custodian':{**ident,'signed':True,'verified':True,'ref':'custody-'+source,'source_id':source}}


def facts():
    facts = deepcopy(FACTS)
    facts.update(region='North',intervals=[],exclusions=[],customer_telemetry=monitor('local-radio','samples lost',[(0,750)]),
                 provider_telemetry=monitor('provider-station','station unavailable',[(300,900)]))
    facts['fee_lines'] = [LINE | {'payment_state':'paid','recurring':True,'region':'North','product':SCOPE['product'],
           'gross_cents':18040,'discount_cents':2820,'refund_cents':3200,'amount_cents':12020,
           'discount_ref':'discount-line','refund_ref':'refund-register'}]
    facts['filing_proof'].update(SCOPE,received_at=facts['received_at'],ticket_id='ticket-654',submitted_to='claims@example.invalid')
    return facts


@pytest.fixture
def manifest():
    return compiled(*extend_source(ROW))


def test_independent_intersection_and_paid_post_refund_cents(manifest):
    data, overlay = facts(), subscription()
    r = result(data,manifest,overlay)
    # 450 shared minutes exceed 1% of a 43,200-minute month. 12.5% × $120.20 = $15.025, rounded to $15.03.
    assert r['outcome']=='ELIGIBLE' and r['amount']=='15.03' and r['downtime_microseconds']==450*60000000
    data['provider_telemetry']=monitor('provider-station','station unavailable',[(750,900)])
    assert result(data,manifest,overlay)['outcome']=='INELIGIBLE'
    data['provider_telemetry']['records']=[]
    assert result(data,manifest,overlay)['outcome']=='INSUFFICIENT_EVIDENCE'
    data['provider_telemetry']['no_events_verified']=True
    assert result(data,manifest,overlay)['outcome']=='INELIGIBLE'


@pytest.mark.parametrize(('key','change'),[
    ('subscription',{'contract_version':'R2'}),('subscription',{'signed':False}),
    ('subscription',{'active_from':'2026-06-02'}),('subscription',{'subscription_type':'Trial'}),
    ('custodian',{'region':'South'}),('custodian',{'signed':False}),
    ('provider',{'source_id':'local-radio'}),('provider',{'complete':False}),
    ('fee',{'refund_cents':0}),('fee',{'recurring':False}),('fee',{'payment_state':'unpaid'}),
])
def test_missing_out_of_scope_or_contradictory_private_attestations(manifest,key,change):
    data, overlay=facts(),subscription()
    target={'subscription':overlay['subscription_record'],'custodian':data['customer_telemetry']['custodian'],
            'fee':data['fee_lines'][0],'provider':data['provider_telemetry']}[key]
    target.update(change)
    r=result(data,manifest,overlay)
    assert r['outcome'] in ('INSUFFICIENT_EVIDENCE','UNSUPPORTED_RULE') and r['amount'] is None


def test_portal_response_window_can_cure_late_missing_evidence_but_never_a_late_original(manifest):
    data, overlay=facts(),subscription()
    proof=data['filing_proof']
    proof['fields'].pop('log references')
    response=dict(**SCOPE,verified=True,ref='portal-response',ticket_id=proof['ticket_id'],kind='denial',
                  delivered_at='2026-07-14T18:01:00Z')
    supplement=dict(**SCOPE,verified=True,ref='custodian-response',original_ref=proof['ref'],response_ref=response['ref'],
                    received_at='2026-07-18T18:01:00Z',ticket_id=proof['ticket_id'],submitted_to=proof['submitted_to'],
                    fields={'log references':'local-radio-0'})
    proof.update(response_receipt=response,supplements=[supplement])
    assert result(data,manifest,overlay)['amount']=='15.03'
    supplement['received_at']='2026-07-18T18:01:00.000001Z'
    assert result(data,manifest,overlay)['filing_status']=='LATE_SUPPLEMENT'
    supplement['received_at']='2026-07-18T18:01:00Z'
    response['ticket_id']='other'
    assert result(data,manifest,overlay)['outcome']=='INSUFFICIENT_EVIDENCE'
    response['ticket_id']=proof['ticket_id']
    data['received_at']=proof['received_at']='2026-07-10T18:00:01Z'
    assert result(data,manifest,overlay)['filing_status']=='OUTSIDE_WINDOW'
