"""New public authored route probes, independent of implementation and held-out gold."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from scripts.evaluate_disputes_finish import workspace

PUBLIC = Path(__file__).with_name('public-control-prepared.json')

@pytest.fixture
def fixture(tmp_path):
    prepared = json.loads(PUBLIC.read_bytes())
    with workspace(tmp_path / 'probe.sqlite', None, prepared) as (app, signed, deliver):
        base = '/api/vendors/' + prepared['vendor_slot']
        candidate = signed.post(base + '/candidates', prepared['candidate']); assert candidate.status_code == 200
        state = candidate.json()
        state = signed.post(base + '/tests', {'revision':state['revision'], 'tests':prepared['setup_tests']}).json()
        for op in ('approve','activate'):
            action = next(a for a in state['actions'] if a['operation'] == op)
            response = signed.post(base + '/actions/' + action['id'], {}); assert response.status_code == 200
            state = response.json()
        scope = prepared['claim']['scope'];url = '/api/correspondence/claims/' + prepared['claim']['claim_id']
        inbox = app.state.correspondence
        inbox.provision('bears', *(scope.get(k) for k in ('account','vendor','contract','service','component','region')))
        for role in ('status','customer','billing','vendor'):
            inbox.bind_sender('bears',scope['account'],role,role+'-evaluation-source',scope=scope)
        assert signed.post('/api/correspondence/claims',prepared['claim']).status_code == 200
        yield signed, lambda event,role,body:deliver(scope,url,event,role,body), url, deepcopy(prepared['evidence'])


def test_wrong_role_refusal_cannot_poison_the_later_authentic_month(fixture):
    client,send,url,events=fixture;report,fee=events
    assert send('same-report','billing',report['body']).status_code == 403
    assert send('same-report','status',report['body']).status_code == 200
    assert send('fee','billing',fee['body']).status_code == 200
    row=client.get(url).json()
    assert row['amount']=='90.00' and row['preflight']['outcome']=='ELIGIBLE'
    assert row['ledger']['awarded']==row['ledger']['applied']=='0.00'
    assert row['submissions']==[]


def test_changed_replay_cannot_reprice_a_signed_month(fixture):
    client,send,url,events=fixture;report,fee=events
    assert send('report','status',report['body']).status_code==200
    assert send('fee','billing',fee['body']).status_code==200
    before=client.get(url).json()
    assert send('report','status',report['body']|{'eligible_downtime_minutes':0}).status_code==409
    after=client.get(url).json()
    assert after['amount']==before['amount']=='90.00'
    assert after['ledger']==before['ledger'] and after['submissions']==[]


def test_extra_contradictory_customer_report_removes_financial_authority(fixture):
    client,send,url,events=fixture;report,fee=events
    assert send('report','status',report['body']).status_code==200
    assert send('fee','billing',fee['body']).status_code==200
    contradiction=report['body']|{'kind':'monthly_attribution','eligible_downtime_minutes':0,'source_ref':'other-measurement'}
    assert send('customer','customer',contradiction).status_code==200
    row=client.get(url).json()
    assert row['amount'] is None and not row['actions']
    assert row['ledger']['awarded']==row['ledger']['applied']=='0.00' and row['submissions']==[]


def test_body_identity_conflict_is_retained_as_refusal_without_claim_money(fixture):
    client,send,url,events=fixture;report,fee=events
    assert send('wrong-account','status',report['body']|{'account':'a-different-authored-account'}).status_code==409
    row=client.get(url).json()
    assert row['amount'] is None and not row['actions'] and row['submissions']==[]
    assert row['ledger']['awarded']==row['ledger']['applied']=='0.00'
