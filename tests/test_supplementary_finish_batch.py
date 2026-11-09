"""Retain refusals in the denominator and prevent unnoticed cohort/input drift."""
import json
from hashlib import sha256

import pytest
from scripts import run_supplementary_finish as runner


def manifest(tmp_path):
    value = {'schema': 'supplementary-execution-manifest/1', 'pins': {'unused': 'pinned'},
             'cases': [{'id': f'case-{i}', 'kind': 'onboarding' if i < 6 else 'dispute',
                        'preflight_refusal': 'source missing a required binding'} for i in range(14)]}
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(value))
    return path, sha256(path.read_bytes()).hexdigest(), value


def test_mapping_refusals_are_terminal_cases_and_cannot_be_repeated(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'verify_freeze', lambda **_: True)
    path, digest, _ = manifest(tmp_path)
    result = runner.run(path, tmp_path / 'attempt', manifest_sha256=digest, source_commit='frozen')
    assert result['terminal_case_records'] == 14
    assert result['outcomes'] == {'SOURCE_MAPPING_REFUSAL': 14}
    assert result['gold_read'] is False
    with pytest.raises(FileExistsError):
        runner.run(path, tmp_path / 'attempt', manifest_sha256=digest, source_commit='frozen')


def test_dropping_or_relabeling_a_refused_case_cannot_raise_success_rate(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'verify_freeze', lambda **_: True)
    path, _, value = manifest(tmp_path)
    value['cases'].pop()
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='every preregistered'):
        runner.run(path, tmp_path / 'attempt', manifest_sha256=sha256(path.read_bytes()).hexdigest(), source_commit='frozen')
    assert not (tmp_path / 'attempt').exists()


def test_unpinned_consumed_input_cannot_start_a_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'verify_freeze', lambda **_: True)
    path, _, value = manifest(tmp_path)
    value['cases'][0].pop('preflight_refusal')
    value['cases'][0].update(document='/unfrozen/source', overlay='/unfrozen/customer', config='/unfrozen/config')
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='must be pinned'):
        runner.run(path, tmp_path / 'attempt', manifest_sha256=sha256(path.read_bytes()).hexdigest(), source_commit='frozen')
    assert not (tmp_path / 'attempt').exists()


def test_expected_outcomes_stay_sealed_until_all_cases_and_jobs_are_terminal(tmp_path, monkeypatch):
    from scripts.dispute_runtime_finish import read_gold
    monkeypatch.setattr(runner, 'verify_freeze', lambda **_: True)
    path, digest, value = manifest(tmp_path)
    gold = tmp_path / 'expected.json'
    gold.write_text('{"control":"sealed value"}')
    log = []
    ids = [c['id'] for c in value['cases']]
    with pytest.raises(FileNotFoundError):
        read_gold(gold, gold_paths=[gold], case_ids=ids, attempt_root=tmp_path / 'attempt', access_log=log)
    assert log == []
    runner.run(path, tmp_path / 'attempt', manifest_sha256=digest, source_commit='frozen')
    case_result = tmp_path / 'attempt' / ids[0] / 'result.json'
    prior = json.loads(case_result.read_bytes())
    case_result.write_text(json.dumps(prior | {'jobs': [{'status': 'RUNNING'}]}))
    with pytest.raises(PermissionError, match='still pending'):
        read_gold(gold, gold_paths=[gold], case_ids=ids, attempt_root=tmp_path / 'attempt', access_log=log)
    assert log == []
    case_result.write_text(json.dumps(prior))
    assert read_gold(gold, gold_paths=[gold], case_ids=ids, attempt_root=tmp_path / 'attempt', access_log=log) == {'control': 'sealed value'}
    assert len(log) == 1 and log[0]['kind'] == 'gold'
