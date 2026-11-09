"""Cross-component probe: SIGKILL and restart of the served authored Northwind flow (real OS processes).

Existing restart coverage reopens SQLite inside one interpreter; this exercises two server processes over
loopback HTTP. Scripted local reviewer only; no Ramp, model or credential.
"""
from __future__ import annotations

from decimal import Decimal

from scripts import probe_restart_gent8 as probe


def test_hard_kill_mid_flow_preserves_state_idempotency_and_final_ledger(tmp_path):
    result = probe.run(tmp_path / 'probe', tmp_path / 'receipt.json', actions_before_kill=4)

    assert result['before_kill']['actions'] == 4
    assert result['first_process_returncode'] == -9 and result['second_process_returncode'] == -9
    assert result['after_restart']['state_equal_to_pre_kill'] is True
    assert result['after_restart']['duplicate_replay'] == {'http_status': 200, 'unchanged': True}

    completion = result['completion']
    assert completion['remaining_actions'] == 0
    assert completion['actions_after_restart'] + result['before_kill']['actions'] == 11
    assert completion['every_duplicate_unchanged'] is True and completion['every_readback_equal'] is True

    ledger = completion['ledger']
    # A local ledger result: never reported as a Ramp write.
    assert ledger['destination'] == 'Local ledger' and ledger['currency'] == 'USD'
    assert all(Decimal(ledger[stage]) == Decimal('2400.00') for stage in ('claimed', 'awarded', 'posted', 'applied'))
    assert Decimal(ledger['unapplied_credit']) == 0
    assert Decimal(ledger['bill']['original_amount']) == Decimal('11000.00')
    assert Decimal(ledger['bill']['outstanding_amount']) == Decimal('8600.00')
    assert result['authority_kind'] == 'SCRIPTED_REVIEWER'


def test_d03a_exact_source_identity_flows_from_onboarding_into_claim_intake(tmp_path, monkeypatch):
    """Decision D03-A (decided November 9; implemented in 6ebaffe): one bounded exact source identity.

    Replaces the earlier defect reproduction from 0403ec5. The signed vendor route evaluates a spaced exact
    account/agreement identity, and signed claim intake now accepts the same identity: it reaches the
    provisioning gate (403) and, once provisioned, opens the claim with the exact bytes preserved. Values
    outside source-identity/1 are still refused at intake, never rewritten.
    """
    monkeypatch.delenv('UPTIME_PUBLIC_EXTRACTIONS', raising=False)
    from tests.test_v4_routes_integration import App, SMALL, TEXT

    account, agreement = 'Cedar Orrery Studio', 'Talus Signal Availability Agreement'
    app = App(tmp_path / 'authority.db')
    try:
        facts = SMALL | {'agreement': agreement, 'account': account}
        overlay = {k: facts[k] for k in ('agreement', 'account', 'product', 'plan', 'fee_line_ref')}
        overlay.update(currency='USD', effective_from='2026-01-01', effective_until='2026-12-31')
        base = '/api/vendors/north-install'
        document = dict(name='Synthetic agreement', uri='urn:synthetic:identity-probe', classification='synthetic_public',
                        text=TEXT.replace('Agreement: BR-74', 'Agreement: ' + agreement))
        installed = app.human.post(base + '/candidates', dict(document=document, overlay=overlay))
        assert installed.status_code == 200 and installed.json()['state'] == 'SHADOW'
        tested = app.human.post(base + '/tests', dict(revision=installed.json()['revision'], tests=[
            dict(name='Spaced identity above trigger', facts=facts, expected=dict(outcome='ELIGIBLE', amount='52.17'))]))
        assert tested.status_code == 200
        spaced_check = next(check for check in tested.json()['checks'] if check['name'] == 'Spaced identity above trigger')
        assert spaced_check['passed'] is True and spaced_check['actual'] == {'outcome': 'ELIGIBLE', 'amount': '52.17'}

        spaced = dict(app.scope, account=account, contract=agreement)
        unprovisioned = app.human.post('/api/correspondence/claims', dict(claim_id='inbox-identity-spaced', scope=spaced))
        assert unprovisioned.status_code == 403  # identity accepted; the binding gate still applies

        for malformed in (' ' + account, account + ' ', 'Cedar  Orrery Studio', 'Cedar\tOrrery Studio',
                          'Cafe\u0301 Studio', 'Cedar\u2014Orrery', 'Cedar#Orrery'):
            refused = app.human.post('/api/correspondence/claims',
                                     dict(claim_id='inbox-identity-bad', scope=dict(spaced, account=malformed)))
            assert refused.status_code == 422, malformed
            assert [error['loc'][-1] for error in refused.json()['detail']] == ['account'], malformed

        app.scope, app.id = spaced, 'inbox-identity-spaced'
        app.url = '/api/correspondence/claims/' + app.id
        app.provision()
        created = app.human.post('/api/correspondence/claims', dict(claim_id=app.id, scope=spaced))
        retried = app.human.post('/api/correspondence/claims', dict(claim_id=app.id, scope=spaced))
        assert created.status_code == 200 and retried.status_code == 200 and retried.json() == created.json()
        stored = app.read()['scope']
        assert stored['account'] == account and stored['contract'] == agreement  # exact bytes, not rewritten
    finally:
        app.client.close()
