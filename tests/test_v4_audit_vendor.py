"""Mounted production router exercise with declared synthetic public terms.

No test router, compiler patch, external extraction or candidate-derived gold.
"""
from test_v4_audit_protocol import SUBJECT


def vendor_inputs():
    text = '''Vendor: Audit Service
Agreement: QA Availability
Effective: 2026-01-01 through 2026-12-31
Availability is measured over each UTC calendar month.
Complete claims must be received within 15 calendar days after month end.
Credits apply to affected monthly fees on a future invoice.
For Jira on Premium plan, availability below 99.9% earns a 10% credit.
'''
    intake = dict(document=dict(name='Synthetic QA availability terms', uri='urn:synthetic:qa-availability',
                                classification='synthetic_public', text=text),
                  overlay=dict(agreement='QA Availability', account='qa-account', product='Jira', plan='Premium',
                    effective_from='2026-01-01', effective_until='2026-12-31', fee_line_ref='qa-fee', currency='USD'))
    facts = dict(agreement='QA Availability', account='qa-account', product='Jira', plan='Premium',
        month='2026-06', eligible_downtime_minutes=60, monitor_source='simulated_vendor',
        monitor_month='2026-06', monitor_ref='qa-monitor', month_complete=True, exclusions_removed=True,
        monthly_fee_cents=120000, fee_line_ref='qa-fee', fee_month='2026-06', fee_ref='qa-invoice',
        received_at='2026-07-13T12:00:00Z')
    tests = [dict(name='independent positive 1200 times 10 percent', facts=facts,
                  expected=dict(outcome='ELIGIBLE', amount='120.00')),
             dict(name='independent zero downtime', facts=facts | {'eligible_downtime_minutes':0},
                  expected=dict(outcome='INELIGIBLE', amount=None))]
    return intake, facts, tests


def mounted_activation():
    from test_v4_audit_workflow import workspace, successful, observation
    with workspace() as (u, _, _, _):
        intake, facts, tests = vendor_inputs()
        stem = '/api/vendors/qa-availability'
        state = successful(u.post(stem+'/candidates', json=intake))
        before = u.post(stem+'/evaluate', json={'facts':facts})
        state = successful(u.post(stem+'/tests', json={'revision':state['revision'], 'tests':tests}))
        for operation in ('approve', 'activate'):
            action = next(a['id'] for a in state['actions'] if a['id'].startswith(operation+'~'))
            state = successful(u.post(stem+'/actions/'+action, json={}))
        active = state
        dispatched = successful(u.post(stem+'/evaluate', json={'facts':facts}))
        ident = dispatched['id']
        dashboard = successful(u.get('/api/dashboard'))
        detail = successful(u.get('/api/cases/'+ident))
        rollback = next(a['id'] for a in state['actions'] if a['id'].startswith('rollback~'))
        state = successful(u.post(stem+'/actions/'+rollback, json={}))
        refused = u.post(stem+'/evaluate', json={'facts':facts})
        historical = successful(u.get('/api/cases/'+ident))
        final_dashboard = successful(u.get('/api/dashboard'))
        expected = dict(preactivation_refused=True, active_amount='120.00', same_case_in_dashboard=True,
                        rollback_refused=True, history_preserved=True, same_reviewer=True)
        observed = dict(preactivation_refused=before.status_code==409, active_amount=dispatched['amount'],
            same_case_in_dashboard=any(c['id']==ident and c['amount']=='120.00' for c in dashboard['cases']) and detail['id']==ident,
            rollback_refused=refused.status_code==409 and state['active_version'] is None,
            history_preserved=historical['id']==ident and historical['version']==dispatched['version']
                and historical['amount']=='120.00' and historical['timeline']==detail['timeline']
                and any(c['id']==ident for c in final_dashboard['cases']),
            same_reviewer=active['reviewer']==SUBJECT and all(a['actor']==SUBJECT for a in active['audit']))
        return [observation('W-activation-runtime', observed, expected)]
