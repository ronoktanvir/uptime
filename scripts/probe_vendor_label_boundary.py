"""Local synthetic probe of existing label risks; no external model or activation.

The extraction seam is an explicit adversarial test double. Actual compilation,
evaluation, signed HTTP intake, test submission and review gates remain in use.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import secrets
import socket
import sys
import tempfile
import threading
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
import httpx
import uvicorn
from uptime.auth import SCRIPT
from uptime.auth_client import ReviewerClient
from uptime.server import create_app
from uptime.storage import database
from uptime.vendor_model import validate_proposal
from test_vendor_resource import DOC, PROPOSAL, FACTS, OVERLAY


def scenarios():
    for kind in ('substring', 'contrary_alias'):
        proposal, facts = deepcopy(PROPOSAL), deepcopy(FACTS)
        original = proposal[4]['quote']
        if kind == 'substring':
            quote = 'Downtime means unavailable samples caused by instrument gateway failure.'
            proposal[4]['value']['symptoms'] = [{'label':'available_samples', 'phrase':'available samples'}]
            observed = 'available samples'
        else:
            quote = original
            proposal[4]['value']['symptoms'] = [
                {'label':label, 'phrase':'rejected samples'} for label in ('failed_samples', 'successful_samples')]
            observed = 'successful samples'
        proposal[4]['quote'] = quote
        document = DOC | {'name':'Synthetic label-boundary probe ' + kind,
                          'text':DOC['text'].replace(original, quote)}
        for interval in facts['intervals']:
            interval['symptom'] = observed
        yield kind, document, proposal, facts


def run():
    cases = list(scenarios())
    proposals = {sha256(document['text'].encode()).hexdigest():proposal for _,document,proposal,_ in cases}

    def adversarial_fixture(document):
        manifest = validate_proposal(document, proposals[sha256(document.text.encode()).hexdigest()], allow_propositions=True)
        return manifest, {'method':'tool_free_model_propositions', 'synthetic_adversarial_fixture':True,
                          'actual_model_invoked':False}

    report = {'classification':'SYNTHETIC_ENGINEERING_PROBE', 'extraction':'explicit adversarial test double',
              'actual_model_invoked':False, 'private_heldout_inputs_used':False, 'activation_performed':False, 'cases':[]}
    with tempfile.TemporaryDirectory(prefix='uptime-label-boundary-') as folder:
        db = Path(folder) / 'probe.sqlite'
        key = secrets.token_urlsafe(32)
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(10)
        origin = 'http://127.0.0.1:' + str(listener.getsockname()[1])
        app = create_app(db, mode='replay', origin=origin, approvals_enabled=True,
                         rehearsal=True, rehearsal_secret=key)
        service = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
        worker = threading.Thread(target=service.run, kwargs={'sockets':[listener]}, daemon=True)
        worker.start()
        try:
            for _ in range(200):
                if service.started:
                    break
                time.sleep(.01)
            assert service.started
            with database(db) as connection:
                before = connection.execute('SELECT count(*) FROM case_snapshot').fetchone()[0]
            with patch('uptime.vendor_registry.staged_extraction', adversarial_fixture), httpx.Client(base_url=origin, trust_env=False) as client:
                reviewer = ReviewerClient(client, origin, SCRIPT, key)

                def post(path, value):
                    response = reviewer.post(path, value)
                    response.raise_for_status()
                    return response.json()

                for kind, document, proposal, facts in cases:
                    base = '/api/vendors/label-' + kind
                    state = post(base + '/candidates', {'document':document, 'overlay':OVERLAY})
                    assert state['state'] == 'SHADOW' and state['active_version'] is None
                    preview = post(base + '/shadow-preview', {'revision':state['revision'], 'facts':facts})
                    outcome = preview['evaluation']
                    assert outcome['outcome'] == 'ELIGIBLE' and outcome['amount'] == '12.51'
                    honest = post(base + '/tests', {'revision':state['revision'], 'tests':[
                        {'name':'Successful observations cannot establish the cited failed operation',
                         'facts':facts, 'expected':{'outcome':'INELIGIBLE'}}]})
                    assert honest['checks'][0]['passed'] is False and honest['actions'] == []
                    confirming = post(base + '/tests', {'revision':honest['revision'], 'tests':[
                        {'name':'Self-confirming mislabeled positive', 'facts':facts,
                         'expected':{'outcome':'ELIGIBLE', 'amount':'12.51'}},
                        {'name':'Incomplete month refuses', 'facts':facts | {'month_complete':False},
                         'expected':{'outcome':'INSUFFICIENT_EVIDENCE'}}]})
                    assert all(check['passed'] for check in confirming['checks'])
                    assert [action['operation'] for action in confirming['actions']] == ['interpret']
                    assert confirming['interpretation_reviewer'] is None and confirming['active_version'] is None
                    report['cases'].append({'risk':kind, 'public_quote':proposal[4]['quote'],
                        'proposed_symptoms':proposal[4]['value']['symptoms'], 'observed_symptom':facts['intervals'][0]['symptom'],
                        'preview':{k:outcome[k] for k in ('outcome','amount','issuance_status')},
                        'dispatch_authorized':preview['dispatch_authorized'], 'honest_counterexample_check':honest['checks'][0],
                        'self_confirming_checks':confirming['checks'], 'remaining_actions':['interpret'],
                        'state':confirming['state'], 'active_version':confirming['active_version'],
                        'interpretation_reviewer':confirming['interpretation_reviewer']})
            with database(db) as connection:
                after = connection.execute('SELECT count(*) FROM case_snapshot').fetchone()[0]
            assert before == after
            report['workbench_cases_created'] = 0
        finally:
            service.should_exit = True
            worker.join(timeout=5)
            listener.close()
    return report


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
