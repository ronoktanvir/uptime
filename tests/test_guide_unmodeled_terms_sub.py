"""Judge reproduction (Nov 9): asked for the renewal date and notice period, the guide answered with an unrelated
clause heading. Both read-only guides must abstain when the case records do not establish the asked-about term,
and a bare heading is never offered as an answer.
"""
import copy
import re

import pytest
from fastapi.testclient import TestClient

from scripts import setup_northwind as setup
from uptime.auth import DEFAULT_ORIGIN
from uptime.finance_guide import ABSTAIN_SCOPE, answer, facts
from uptime.intelligence import explain

UNMODELED = ['What is the renewal date and notice period?',
             'What is the contract renewal date and notice period?',
             'When does the agreement renew?',
             'What is the notice period for termination under the contract?',
             'Does the contract auto-renew?',
             'How much notice do we need to give to cancel the agreement?',
             'What is the renewal date and notice period for this contract?']


@pytest.fixture(scope='module')
def run(tmp_path_factory):
    directory = tmp_path_factory.mktemp('guide-terms') / 'owned'
    app, private, events = setup.prepare(directory, DEFAULT_ORIGIN)
    client = TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234), raise_server_exceptions=False)
    actor, _ = setup.seed(client, app, private, events)
    read = lambda: setup.checked(client.get('/api/workspace/workflow', headers=actor.headers))['workflow']
    states = [read()]
    while states[-1]['next_actions']:
        setup.checked(actor.post('/api/workspace/workflow/actions/' + states[-1]['next_actions'][0]['id'], {}))
        states.append(read())
    yield dict(client=client, actor=actor, states=states)
    client.close()


@pytest.mark.parametrize('question', UNMODELED)
def test_workspace_guide_abstains_on_terms_the_case_does_not_record(run, question):
    headers = {**run['actor'].headers, 'X-Uptime-Action': '1', 'Origin': DEFAULT_ORIGIN}
    result = run['client'].post('/api/workspace/guide', headers=headers, json={'question': question}).json()
    assert result['abstained'] is True, result['answer']
    assert result['answer'].startswith(ABSTAIN_SCOPE)
    assert 'Clause' not in result['answer'] and not any(s['citations'] for s in result['sentences'])
    for state in run['states']:
        assert answer(question, state)['abstained'] is True


def test_no_guide_fact_offers_a_bare_heading_as_an_answer(run):
    for state in run['states']:
        for fact in facts(state):
            if fact['id'].startswith('clause.'):
                quote = fact['text'].split('“', 1)[-1].rstrip('”')
                assert re.search(r'[0-9%]|\b(?:must|shall|will|credit|claim|receive|measure)\w*', quote, re.I), fact['text']


CASE = {"id": "demo", "vendor": "Northwind Cloud", "outcome": "ELIGIBLE", "stage": "Draft", "sources": ["SYNTHETIC_CUSTOMER"],
        "trace": ["Fee basis USD 40.00 after exclusions."], "financials": [{"label": "Estimated", "value": "$40.00"}],
        "evidence": [{"label": "Status interval"}],
        "clauses": [{"label": 'Clause 1: "Service Level Agreement"'}, {"label": "Clause 4: credits"}], "actions": []}


@pytest.mark.parametrize('question', UNMODELED)
def test_case_inspector_guide_abstains_on_terms_the_case_does_not_record(question):
    before = copy.deepcopy(CASE)
    result = explain(CASE, question)
    assert result['abstained'] is True and 'Clause' not in result['answer'], result['answer']
    assert CASE == before


@pytest.mark.parametrize('question,phrase', [('What evidence supports this case?', 'Status interval'),
                                             ('How much is the credit?', '$40.00')])
def test_supported_case_questions_still_answer(question, phrase):
    result = explain(CASE, question)
    assert result['abstained'] is False and phrase in result['answer']


SAVINGS = ['How much money has Uptime saved us in total?', 'How much have we recovered so far?',
           'What are our total savings?']


@pytest.mark.parametrize('question', SAVINGS)
def test_savings_questions_report_stages_without_summing_or_claiming_ramp_recovery(run, question):
    for state in run['states']:
        result = answer(question, state)
        text = result['answer']
        assert not text.startswith('January'), text  # judge reproduction: month decision records are not an answer
        if result['abstained']:
            continue
        ids = [c for s in result['sentences'] for c in s['citations']]
        assert result['sentences'][0]['citations'] == [] and "doesn't total savings" in result['sentences'][0]['text']
        assert 'ledger.stages' in ids and 'These are stages of one credit, not amounts to add.' in text
        assert not any(i.startswith('month.') for i in ids)
        stated = {n for f in facts(state) if f['id'] in ids for n in re.findall(r'\$[\d,]+\.\d\d', f['text'])}
        assert set(re.findall(r'\$[\d,]+\.\d\d', text)) <= stated  # no new number, so no sum
        assert not re.search(r'\brecovered (?:in|from|through) Ramp\b', text, re.I)
        if any(f['id'] == 'price' for f in facts(state)):
            assert 'is not an awarded credit' in text

