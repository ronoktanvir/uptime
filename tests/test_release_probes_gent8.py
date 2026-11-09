"""Cross-component probe: SIGKILL and restart of the served authored Northwind flow (real OS processes).

Existing restart coverage reopens SQLite inside one interpreter; this exercises two server processes over
loopback HTTP. Scripted local reviewer only; no Ramp, model or credential.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

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


def test_socket_authority_attacks_are_refused_without_state_change(tmp_path):
    """Real loopback HTTP to a separate server process; complements the in-process authority tests."""
    from scripts import probe_socket_authority_gent8 as authority

    result = authority.run(tmp_path / 'probe', tmp_path / 'receipt.json')
    names = {probe['name'] for probe in result['probes']}
    assert names == {'body_tampered_after_signing', 'proof_rebound_to_other_path', 'cross_origin_header',
                     'missing_action_header', 'bearer_session_without_proof', 'forged_rehearsal_key_login',
                     'exact_replay_of_accepted_request'}
    for probe in result['probes']:
        assert probe['refused'] is True and probe['http_status'] in (401, 403, 409), probe
        assert probe['state_unchanged'] is True, probe
    # Control: the same signed route accepts one fresh legitimate request.
    assert result['legitimate_action']['http_status'] == 200 and result['legitimate_action']['state_changed'] is True
    assert result['authority_kind'] == 'SCRIPTED_REVIEWER'


def test_socket_tenant_crossing_is_refused_between_two_installations(tmp_path):
    """Two installations (different tenants, databases and listeners) over real loopback HTTP.

    A session token, enrolled key or subject from one installation must not authenticate or read on the other.
    """
    import contextlib
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    from uptime.auth import enroll
    from uptime.auth_client import ReviewerClient
    from uptime.auth_keys import generate_reviewer_key
    from uptime.server import create_app

    @contextlib.contextmanager
    def served(tenant, subject, key):
        path = tmp_path / f'{tenant}.db'
        enroll(path, subject, key, 'reviewer', 'replay', tenant)
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        origin = f'http://127.0.0.1:{sock.getsockname()[1]}'
        server = uvicorn.Server(uvicorn.Config(create_app(path, tenant=tenant, origin=origin), log_level='error'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        try:
            with httpx.Client(base_url=origin, timeout=15, trust_env=False) as client:
                yield origin, client
        finally:
            server.should_exit = True
            thread.join(10)
            sock.close()

    silver_key, gold_key = generate_reviewer_key(), generate_reviewer_key()
    with served('tenant-silver', 'silver.reviewer', silver_key) as (silver_origin, silver), \
            served('tenant-gold', 'gold.reviewer', gold_key) as (gold_origin, gold):
        silver_actor = ReviewerClient(silver, silver_origin, 'silver.reviewer', silver_key)
        assert silver.get('/api/dashboard', headers=silver_actor.headers).json()['workspace'] == 'tenant-silver'
        gold_actor = ReviewerClient(gold, gold_origin, 'gold.reviewer', gold_key)
        assert gold.get('/api/dashboard', headers=gold_actor.headers).json()['workspace'] == 'tenant-gold'

        # 1. A silver session token presented to the gold listener (with gold's own origin header).
        carried = {**silver_actor.headers, 'Origin': gold_origin}
        assert gold.get('/api/dashboard', headers=carried).status_code in (401, 403)
        # 2. The silver subject and key cannot sign in on gold, where they are not enrolled.
        with pytest.raises(httpx.HTTPStatusError) as unenrolled:
            ReviewerClient(gold, gold_origin, 'silver.reviewer', silver_key)
        assert unenrolled.value.response.status_code in (401, 403)
        # 3. The silver key cannot impersonate gold's enrolled subject.
        with pytest.raises(httpx.HTTPStatusError) as impersonated:
            ReviewerClient(gold, gold_origin, 'gold.reviewer', silver_key)
        assert impersonated.value.response.status_code in (401, 403)
        # 4. Gold still reports only its own workspace afterwards.
        assert gold.get('/api/dashboard', headers=gold_actor.headers).json()['workspace'] == 'tenant-gold'
