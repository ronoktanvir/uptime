"""Tests of witness accounting, using newly authored disposable synthetic data only."""
import importlib.util
from pathlib import Path


spec = importlib.util.spec_from_file_location("prospective_witness", Path(__file__).with_name("witness.py"))
witness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(witness)

PROTOCOL = {"expected_counts": {"evaluations": 2, "denials": 1, "workbench_cases_min": 1}}


def summarize(evaluations, denials, **kwargs):
    return witness.summarize(evaluations, denials, PROTOCOL, active=True, workbench=1, **kwargs)


def test_empty_or_partial_measurement_cannot_pass():
    empty = summarize([], [])
    assert empty["all_green"] is False
    assert empty["evaluations_blocked"] == 2
    assert empty["denials_blocked"] == 1
    partial = summarize([{"id": "a", "measured": True, "matched": True}], [])
    assert partial["all_green"] is False
    assert partial["evaluations_blocked"] == 1


def test_duplicate_identity_cannot_supply_missing_coverage():
    row = {"id": "a", "measured": True, "matched": True}
    denial = {"id": "d", "measured": True, "matched": True}
    assert not summarize([row, row], [denial])["all_green"]


def test_blocked_rows_and_fatal_setup_are_not_success():
    rows = [{"id": key, "measured": False, "matched": False} for key in ("a", "b")]
    denial = {"id": "d", "measured": False, "matched": False}
    result = summarize(rows, [denial])
    assert result["complete_result_rows"]
    assert not result["all_green"]
    for row in rows + [denial]:
        row.update(measured=True, matched=True)
    assert not summarize(rows, [denial], fatal="setup_failure")["all_green"]


def test_manifest_tampering_stops_before_any_app_operation(tmp_path):
    path = tmp_path / "freeze-manifest.json"
    path.write_text("{}")
    before = witness.digest(path.read_bytes())
    path.write_text('{"changed":true}')
    try:
        witness.verify_freeze(tmp_path, before)
    except ValueError as error:
        assert str(error) == "Freeze manifest changed"
    else:
        raise AssertionError("A changed manifest was accepted")


def test_all_green_requires_every_evidence_delivery_as_well_as_semantic_matches():
    rows = [{"id": key, "measured": True, "matched": True} for key in ("a", "b")]
    denial = {"id": "d", "measured": True, "matched": True}
    assert not summarize(rows, [denial])["all_green"]
    denial["evidence_http_statuses"] = [200] * 5 + [403]
    assert not summarize(rows, [denial])["all_green"]
    denial["evidence_http_statuses"] = [200] * 6
    assert summarize(rows, [denial])["all_green"]


def test_observer_requires_intact_seal_before_opening_any_oracle(tmp_path, monkeypatch):
    import pytest
    calls = []
    monkeypatch.setattr(witness, 'read_json', lambda p: calls.append(str(p)) or {})
    with pytest.raises(KeyError):
        witness.compare_sealed(tmp_path, tmp_path)
    assert calls == [str(tmp_path / 'seal.json')]


def test_tampered_observation_refused_before_oracle(tmp_path, monkeypatch):
    import pytest
    witness.save(tmp_path / 'observations.json', {'private': 'new disposable scenario'})
    witness.seal(tmp_path, ['observations.json'])
    (tmp_path / 'observations.json').write_text('{}')
    opened = []
    read = witness.read_json
    monkeypatch.setattr(witness, 'read_json', lambda p: opened.append(str(p)) or read(p))
    with pytest.raises(ValueError, match='Sealed observation changed'):
        witness.compare_sealed(tmp_path, tmp_path)
    assert not any('/gold/' in p for p in opened)
