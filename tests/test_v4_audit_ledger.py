"""Durable allocation probes with independent synthetic money and identities."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
import tempfile

from test_v4_audit_protocol import is_v4


def inputs(suffix, **scope_change):
    scope = dict(vendor_id='audit-vendor', account_id='audit-account', product_id='Jira',
                 contract_id='audit-contract', contract_version='2026-01', currency='USD') | scope_change
    base = scope | dict(amount_cents=8000, effective_date='2026-11-04')
    award = base | dict(id='award-'+suffix, source_ref='award-'+suffix, source='SIMULATED_VENDOR', confirmed=True, memo_ref='memo-'+suffix)
    credit = base | dict(id='credit-'+suffix, source_ref='credit-'+suffix, source='DETERMINISTIC_REPLAY', award_id=award['id'], memo_ref=award['memo_ref'])
    application = dict(id='app-'+suffix, source_ref='app-'+suffix, source='DETERMINISTIC_REPLAY', amount_cents=8000,
                       effective_date='2026-11-04', credit_id=credit['id'], bill_id='shared-bill')
    bill = base | dict(id='shared-bill', source_ref='shared-bill', source='SYNTHETIC_CUSTOMER', amount_cents=10000, eligible_cents=10000)
    return award, credit, application, bill


def provision(ledger, suffix):
    a, c, x, b = inputs(suffix)
    ledger.record_award('bears', 'case-'+suffix, a)
    ledger.record_credit('bears', c)
    ledger.record_bill('bears', b)
    return a, c, x, b


def allocation_counterexamples():
    from uptime.allocations import AllocationLedger
    with tempfile.TemporaryDirectory() as tmp:
        ledger = AllocationLedger(Path(tmp)/'cap.sqlite')
        a1, c1, x1, b = provision(ledger, 'one')
        a2, c2, x2, _ = provision(ledger, 'two')
        ledger.apply('bears', x1)
        try:
            ledger.apply('bears', x2)
        except ValueError:
            pass
        total = ledger.bill_balance('bears', b['id'])['applied']
        wrong = AllocationLedger(Path(tmp)/'scope.sqlite')
        a, c, x, b = provision(wrong, 'scope')
        bad_bill = b | dict(id='wrong-bill', source_ref='wrong-bill', product_id='Confluence', account_id='other-account', effective_date='2026-10-01')
        wrong.record_bill('bears', bad_bill)
        try:
            wrong.apply('bears', x | {'bill_id': bad_bill['id']})
        except ValueError:
            pass
        return total, wrong.reconcile('bears', a['id'])['applied']


def durable_allocations():
    from test_v4_audit_workflow import observation
    expected = {'positive_applied': '80.00', 'same_ids': True, 'duplicate_no_event': True,
                'restart_same': True, 'historical_unchanged': True}
    concurrent_expected = {'accepted': 1, 'refused': 1, 'total': '80.00', 'applications': 1}
    if not is_v4():
        return [observation('R-durable-identity-readback', {'interface_present': False}, expected),
                observation('R-serialized-concurrency', {'interface_present': False}, concurrent_expected)]
    from uptime.allocations import AllocationLedger
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'durable.sqlite'
        ledger = AllocationLedger(path)
        a, c, x, b = provision(ledger, 'identity')
        before = ledger.reconcile('bears', a['id'])
        ledger.apply('bears', x)
        after = ledger.reconcile('bears', a['id'])
        history = ledger.history('bears')
        ledger.apply('bears', x)
        observed = dict(positive_applied=after['applied'],
            same_ids=after['award_id']==a['id'] and after['credit_ids']==[c['id']]
                     and after['application_ids']==[x['id']] and after['bill_ids']==[b['id']]
                     and after['case_id']=='case-identity',
            duplicate_no_event=history==ledger.history('bears'),
            restart_same=AllocationLedger(path).reconcile('bears', a['id'])==after,
            historical_unchanged=ledger.reconcile('bears', a['id'], as_of=before['as_of_sequence'])==before)
        parallel = Path(tmp)/'parallel.sqlite'
        initial = AllocationLedger(parallel)
        one, two = provision(initial, 'one')[2], provision(initial, 'two')[2]
        barrier = Barrier(2)
        def attempt(application):
            other = AllocationLedger(parallel)
            barrier.wait(timeout=10)
            try:
                other.apply('bears', application)
                return 'accepted'
            except ValueError:
                return 'refused'
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, [one, two]))
        reopened = AllocationLedger(parallel)
        count = sum(len(reopened.reconcile('bears', 'award-'+name)['application_ids']) for name in ('one','two'))
        return [observation('R-durable-identity-readback', observed, expected, 'control'),
                observation('R-serialized-concurrency', dict(accepted=outcomes.count('accepted'), refused=outcomes.count('refused'),
                    total=reopened.bill_balance('bears', 'shared-bill')['applied'], applications=count), concurrent_expected)]
