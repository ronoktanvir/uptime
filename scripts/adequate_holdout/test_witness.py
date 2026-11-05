import pytest
from scripts.adequate_holdout.witness import Witness, verify_freeze, canonical, digest, LABEL
from scripts.adequate_holdout.projection import project_facts, project_record, pin_original


def test_unmeasured_is_not_green():
    result = Witness(['onboard', 'evaluate', 'denial']).report()
    assert result['unmeasured'] == 3 and not result['all_green']


def test_partial_success_is_not_green():
    w = Witness(['onboard', 'evaluate'])
    w.record('onboard', measured=True, passed=True, evidence='a'*64)
    assert w.report()['passed'] == 1 and not w.report()['all_green']


@pytest.mark.parametrize('measured,evidence', [(False, 'a'*64), (True, None), (False, None)])
def test_reject_fabricated_green(measured, evidence):
    with pytest.raises(ValueError):
        Witness(['x']).record('x', measured=measured, passed=True, evidence=evidence)


def test_failure_remains_in_denominator():
    w = Witness(['a', 'b'])
    w.record('a', measured=True, passed=True, evidence='a'*64)
    w.record('b', measured=True, passed=False, evidence='b'*64, reason='WRONG_AMOUNT')
    r = w.report()
    assert (r['required'], r['passed'], r['failed'], r['unmeasured'], r['all_green']) == (2, 1, 1, 0, False)


def test_no_duplicate_replacement():
    w = Witness(['x'])
    w.record('x', measured=True, passed=False, reason='REFUSED')
    with pytest.raises(ValueError):
        w.record('x', measured=True, passed=True, evidence='a'*64)


def test_complete_measured_green():
    w = Witness(['a', 'b'])
    for name in w.required:
        w.record(name, measured=True, passed=True, evidence='a'*64)
    assert w.report()['all_green']


def test_projection_never_fills_missing_evidence_or_receipt():
    facts = {'account':'x', 'service_invoice':{'complete':False}, 'filing_proof':{'fields':[]}}
    assert project_facts(facts) == {'account':'x', 'service_invoice':{'complete':False}, 'filing_proof':{'fields':{}}}
    assert 'received_at' not in project_facts(facts)['filing_proof']


def test_projection_retains_fractional_threshold():
    facts = {'service_monitor':{'content':{'unavailable_minutes':43.2}}}
    assert project_facts(facts) == facts


def test_label_projection_preserves_fees_completeness_and_source_time():
    body = {'kind':'service_invoice','complete':False,'recorded_at':'fixed',
            'content':{'lines':[{'category':'training','amount_cents':391,'kind':'other'}]}}
    out = project_record(body, ['training fees'])
    assert out['content']['lines'][0]['amount_cents'] == 391
    assert out['content']['lines'][0]['category'] == 'training fees'
    assert out['complete'] is False and out['recorded_at'] == 'fixed'
    assert body['content']['lines'][0]['category'] == 'training'


def test_projection_refuses_duplicate_field_collapse():
    with pytest.raises(ValueError, match='Duplicate'):
        project_facts({'filing_proof': {'fields': [dict(name='account',refs=['a']),dict(name='account',refs=['b'])]}})


def test_current_get_does_not_invent_original_pins():
    original = dict(receipt_id='original',received_at='2031-05-01T00:00:00Z',fields=[])
    assert pin_original({'original_filing':original},dict(contract_version='new',contract_source_sha256='a'*64),'') == original


@pytest.mark.parametrize('tamper', ['source','public_version','overlay','scope','existing_pin',None])
def test_original_pin_requires_exact_prior_commitments(tamper):
    from copy import deepcopy
    source = 'SYNTHETIC\nVersion Example-1.\n'
    overlay = {'account':'fixture-account'}
    scope = {'account':'fixture-account','contract':'fixture-order'}
    case = dict(scope=scope,overlay=overlay,original_filing={'receipt_id':'historical'},
                original_contract=dict(public_version='Example-1',source_sha256=digest(source.encode()),overlay_sha256=digest(canonical(overlay))))
    view = dict(scope=deepcopy(scope),contract_version='derived-version',contract_source_sha256=digest(source.encode()))
    if tamper == 'source': view['contract_source_sha256'] = '0'*64
    if tamper == 'public_version': case['original_contract']['public_version'] = 'Example-2'
    if tamper == 'overlay': case['overlay']['account'] = 'different'
    if tamper == 'scope': view['scope']['account'] = 'different'
    if tamper == 'existing_pin': case['original_filing']['contract_version'] = 'earlier'
    before = deepcopy(case)
    if tamper:
        with pytest.raises(ValueError): pin_original(case,view,source)
    else:
        projected = pin_original(case,view,source)
        assert projected['contract_version'] == view['contract_version']
        assert projected['contract_source_sha256'] == digest(source.encode())
    assert before == case


def test_freeze_rejects_changed_file(tmp_path):
    import json
    (tmp_path/'inputs.private.json').write_bytes(b'original')
    manifest = dict(label=LABEL,preexercise=True,api_exercised=False,files={'inputs.private.json':digest(b'original')})
    (tmp_path/'manifest.json').write_text(json.dumps(manifest))
    verify_freeze(tmp_path)
    (tmp_path/'inputs.private.json').write_bytes(b'edited')
    with pytest.raises(ValueError, match='Frozen file changed'):
        verify_freeze(tmp_path)


def test_observer_does_not_read_gold_or_call_scorer():
    import ast
    import inspect
    from scripts.adequate_holdout import run
    for function in (run.run_case, run.exercise_denial, run.authorized_action, run.schedule):
        tree = ast.parse(inspect.getsource(function))
        names = {node.id for node in ast.walk(tree) if isinstance(node,ast.Name)}
        assert not {'gold','expected','score_case'} & names
    main = inspect.getsource(run.main)
    assert main.index("save(attempt/'observed.private.json'") < main.index("args.cohort/'gold.private.json'")


def test_exact_mandate_uses_observed_packet_not_expected_amount():
    from scripts.adequate_holdout.run import authorized_action
    class Session:
        def post(self,path,body,claim):
            assert path == '/claim/actions/approve-response'
            assert claim == dict(max_amount_cents=971,packet_sha256='a'*64)
            return 200, {'stage':'RESPONSE_APPROVED'}
    detail = {'actions':[dict(id='approve-response',mandate_claim=dict(max_amount_cents=971,packet_sha256='a'*64))]}
    assert authorized_action(Session(),'/claim',detail,'approve-response')['stage'] == 'RESPONSE_APPROVED'


def test_scoring_changes_neither_evidence_nor_denominator():
    from copy import deepcopy
    from scripts.adequate_holdout.scoring import score_case
    witness = Witness(['evaluation','rollback'])
    witness.record('evaluation',measured=True,passed=True,evidence='a'*64)
    observed = witness.report()
    observed['measurements'] = {'evaluation':dict(status=200,result=dict(outcome='ELIGIBLE',amount='7.31'))}
    before = deepcopy(observed)
    gold = dict(expected_outcome='ELIGIBLE',expected_amount='7.31',denial_expected=None)
    correct = score_case(observed,gold)
    wrong = score_case(observed,dict(gold,expected_amount='7.32'))
    assert correct['passed'] == 1 and wrong['passed'] == 0
    assert correct['required'] == wrong['required'] == 2
    assert correct['unmeasured'] == wrong['unmeasured'] == 1
    assert not correct['all_green'] and not wrong['all_green']
    assert observed == before


def test_response_submit_scores_actual_api_stage():
    from scripts.adequate_holdout.scoring import score_case
    witness = Witness(['response_submit'])
    witness.record('response_submit',measured=True,passed=True,evidence='a'*64)
    observed = witness.report()
    observed['measurements'] = {'response_submit':dict(offered=True,executed=True,view=dict(
        stage='AWAITING_VENDOR',submissions=[dict(action='submit-response',requested='7.31')]))}
    gold = dict(denial_expected='APPROVE_AND_SUBMIT_ONE_RESPONSE',expected_amount='7.31')
    assert score_case(observed,gold)['all_green']
    observed['measurements']['response_submit']['view']['submissions'][0]['requested'] = '7.32'
    assert not score_case(observed,gold)['all_green']


def test_missing_response_observation_cannot_pass_correct_denial():
    from scripts.adequate_holdout.scoring import score_case
    observed = Witness(['response_submit']).report()
    assert score_case(observed,{'denial_expected':'ACCEPT_DENIAL'})['unmeasured'] == 1
