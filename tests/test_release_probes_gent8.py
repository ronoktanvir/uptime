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
