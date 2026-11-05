"""Post-exercise scoring. This module never chooses an application request."""
from .witness import Witness


def score_case(observed, gold):
    measured = observed.get('measurements', {})
    scored = Witness(observed['observations'])
    wants_response = gold['denial_expected'] == 'APPROVE_AND_SUBMIT_ONE_RESPONSE'
    for name, row in observed['observations'].items():
        passed, reason = row['passed'], row['reason']
        if row['measured'] and name == 'evaluation':
            actual = measured['evaluation']
            result = actual['result']
            expected = {'MISSING_EVIDENCE':'INSUFFICIENT_EVIDENCE'}.get(gold['expected_outcome'], gold['expected_outcome'])
            passed = (actual['status'] == 200 and result.get('outcome') == expected
                      and (result.get('amount') or '0.00') == gold['expected_amount'])
            reason = 'EVALUATION_MISMATCH'
        elif row['measured'] and name == 'original_filing' and passed and 'original_submissions' in measured:
            passed = measured['original_submissions'][0]['requested'] == gold['expected_amount']
            reason = 'ORIGINAL_AMOUNT_MISMATCH'
        elif row['measured'] and name == 'denial_outcome':
            actual = measured['denial_view']
            # Use the public API's actual stage and ledger field names.
            if wants_response:
                passed = actual.get('stage') == 'RESPONSE_DRAFTED'
            else:
                wanted = {'ACCEPT_DENIAL':'DENIAL_ACCEPTED','REVIEW_NO_RESPONSE':'HUMAN_REVIEW',
                          'PARTIAL_AWARD_REVIEW_REMAINDER':'PARTIAL_AWARD_REVIEW'}[gold['denial_expected']]
                ledger = actual.get('ledger', {})
                passed = (actual.get('stage') == wanted and not actual.get('actions')
                          and ledger.get('awarded') == gold['awarded'])
                if gold['remainder'] is not None:
                    passed &= ledger.get('disputed_remainder') == gold['remainder']
            reason = 'DENIAL_DISPOSITION_MISMATCH'
        elif row['measured'] and name in ('response_approval', 'response_submit'):
            actual = measured[name]
            if wants_response:
                passed = actual['executed'] and actual['view'].get('stage') == (
                    'RESPONSE_APPROVED' if name == 'response_approval' else 'AWAITING_VENDOR')
                if name == 'response_submit':
                    replies = [r for r in actual['view'].get('submissions', []) if r['action'] == 'submit-response']
                    passed &= len(replies) == 1 and replies[0]['requested'] == gold['expected_amount']
            else:
                passed = not actual['offered'] and not actual['executed']
            reason = 'RESPONSE_ACTION_MISMATCH'
        scored.record(name, measured=row['measured'], passed=passed,
                      evidence=row['evidence_sha256'], reason=None if passed else reason)
    return scored.report()
