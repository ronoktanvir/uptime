"""Rehearse an external synthetic installation through signed HTTP on an owned loopback socket."""
import argparse
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.film_demo import serve
from uptime.auth import SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.contracts import fingerprint


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exercise(document, overlay, scenarios, origin, secret):
    digest = sha256(document['text'].encode()).hexdigest()
    slot = 'rehearsal-' + digest[:16]
    prefix = '/api/vendors/' + slot
    statuses = []
    require(document.get('classification') == 'synthetic_public', 'Rehearsal requires explicitly synthetic public terms.')
    require(isinstance(scenarios, list) and scenarios, 'Provide independently authored synthetic scenarios.')

    with httpx.Client(base_url=origin, trust_env=False, timeout=20) as client:
        signed = ReviewerClient(client, origin, SCRIPT, secret)

        def call(operation, method, path, payload=None, status=200):
            if method == 'POST':
                response = signed.post(path, payload)
            else:
                response = client.get(path, headers=signed.headers)
            statuses.append({'operation': operation, 'http_status': response.status_code})
            require(response.status_code == status, f'{operation} expected HTTP {status}, got {response.status_code}.')
            return response.json()

        def transition(state, op):
            links = [item['id'] for item in state['actions'] if item['operation'] == op]
            require(len(links) == 1, f'Current revision does not offer {op}.')
            return call(op, 'POST', prefix + '/actions/' + links[0], {})

        require(not call('initial catalog', 'GET', '/api/vendors')['vendors'], 'Rehearsal requires a fresh workspace.')
        shadow = call('submit public terms and separate overlay', 'POST', prefix + '/candidates',
                      {'document': document, 'overlay': overlay})
        require(shadow['state'] == 'SHADOW', 'Candidate failed closed: ' + str(shadow.get('reason', shadow['state'])))
        require(not shadow['actions'] and not shadow['active_version'], 'Untested candidate exposed authority.')
        observation = {'facts': scenarios[0]['facts']}
        call('shadow dispatch denied', 'POST', prefix + '/evaluate', observation, status=409)
        tested = call('submit independent scenarios', 'POST', prefix + '/tests',
                      {'revision': shadow['revision'], 'tests': scenarios})
        require(all(check['passed'] for check in tested['checks']), 'Independent or generated shadow checks failed.')
        if tested.get('interpretation_required'):
            tested = transition(tested, 'interpret')
        approved = transition(tested, 'approve')
        require(approved['reviewer_kind'] == 'scripted_test' and approved['reviewer'] == SCRIPT,
                'Rehearsal authority must be explicitly scripted.')
        active = transition(approved, 'activate')
        require(active['active_version'] == shadow['version'], 'Activation used a different candidate.')
        results = []
        for i, scenario in enumerate(scenarios, 1):
            case = call(f'dispatch {i}', 'POST', prefix + '/evaluate', {'facts': scenario['facts']})
            expected = scenario['expected']
            require(case['outcome'] == expected['outcome'] and case['amount'] == expected.get('amount'),
                    'Dispatched result differs from supplied expectation.')
            detail = call(f'workbench case {i}', 'GET', '/api/cases/' + case['id'])
            require(detail == case, 'Workbench returned a different case.')
            results.append({'scenario_sha256': fingerprint(scenario), 'case_id': case['id'],
                            'outcome': case['outcome'], 'amount': case['amount'], 'currency': case['currency']})
        portfolio = call('portfolio', 'GET', '/api/dashboard')
        require({row['case_id'] for row in results} <= {row['id'] for row in portfolio['cases']},
                'Workbench portfolio is missing dispatched obligations.')
        rolled = transition(active, 'rollback')
        require(not rolled['active_version'], 'Rollback left the new installation active.')
        call('rolled-back dispatch denied', 'POST', prefix + '/evaluate', observation, status=409)
        historical = call('historical workbench case', 'GET', '/api/cases/' + results[-1]['case_id'])
        require(historical['version'] == shadow['version'], 'Rollback lost case provenance.')

    return {'kind': 'signed_loopback_rehearsal', 'at': datetime.now(UTC).isoformat(),
            'authority': SCRIPT, 'human_approval': False, 'source_sha256': digest,
            'overlay_sha256': fingerprint(overlay), 'suite_sha256': fingerprint(scenarios),
            'version': shadow['version'], 'semantics_revision': shadow['semantics_revision'],
            'family': shadow['manifest']['family'], 'extraction': shadow['extraction'],
            'generated_checks': len(shadow['generated_tests']), 'results': results, 'operations': statuses}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--document', required=True, type=Path)
    parser.add_argument('--overlay', required=True, type=Path)
    parser.add_argument('--scenarios', required=True, type=Path)
    args = parser.parse_args()
    documents = [json.loads(path.read_text()) for path in (args.document, args.overlay, args.scenarios)]
    secret = secrets.token_urlsafe(32)
    with TemporaryDirectory(prefix='uptime-synthetic-onboarding-') as directory:
        with serve(Path(directory) / 'rehearsal.sqlite', secret) as origin:
            receipt = exercise(*documents, origin, secret)
    print(json.dumps(receipt, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
