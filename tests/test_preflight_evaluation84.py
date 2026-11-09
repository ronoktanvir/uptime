"""Offline evaluation84 preflight: pins, current input contracts and claim-scope dependencies.

No model, CLI, server or network. Sealed gold is represented here by sentinel files in a temporary
root; the preflight may only lstat them.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

from scripts import preflight_evaluation84 as preflight

_OPENED: dict = {'log': None, 'installed': False}


def _hook(event, args):
    if _OPENED['log'] is not None and event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
        _OPENED['log'].append(os.fsdecode(args[0]))


@pytest.fixture
def sentinel_gold(tmp_path):
    manifest = json.loads((preflight.ROOT / preflight.MANIFEST).read_bytes())
    root = tmp_path / 'sealed'
    for entry in manifest['entries']:
        path = root / entry['gold_relative_path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"sentinel": "SEALED_GOLD_MUST_NOT_BE_OPENED"}')
        path.chmod(0o600)
    return root


@pytest.fixture
def receipt(sentinel_gold):
    if not _OPENED['installed']:
        sys.addaudithook(_hook)
        _OPENED['installed'] = True
    _OPENED['log'] = []
    try:
        built = preflight.build(gold_root=str(sentinel_gold))
        opened = list(_OPENED['log'])
    finally:
        _OPENED['log'] = None
    return built, opened, sentinel_gold


def test_preflight_never_opens_gold_and_makes_no_model_call(receipt):
    built, opened, gold_root = receipt
    assert [path for path in opened if os.path.realpath(path).startswith(os.path.realpath(gold_root))] == []
    assert [path for path in opened if os.path.basename(path) == 'expected.json'] == []
    assert built['model_calls'] == 0 and built['gold_opened'] is False and built['network'] is False
    assert built['summary']['sealed_gold_present'] == 18
    assert all(value == {'present': True, 'regular': True, 'owner_only': True, 'owned_by_operator': True}
               for value in built['gold_metadata'].values())


def test_frozen_inputs_match_manifest_and_frozen_commit(receipt):
    built, _, _ = receipt
    assert built['summary']['inputs_pinned'] is True
    assert built['summary']['frozen_commit_mismatch'] == 0
    assert len(built['pins']) == 24


def test_all_onboarding_inputs_fit_current_runner_and_profile_contracts(receipt):
    built, _, _ = receipt
    cases = {case['id']: case['checks'] for case in built['onboarding']}
    assert len(cases) == 6
    assert all(check['runner_inputs'] == 'ACCEPTED' and check['profile_input'] == 'ACCEPTED'
               and check['runner_family_route'] is True for check in cases.values())
    # Monthly fee sources are local facts; the draft path cannot turn them into fee authority.
    assert {name for name, check in cases.items() if check['governing_fee_source_supplied']} == {'monthly_tier', 'completed_step'}
    assert all(check['fee_authority_reachable_on_draft_path'] is False for check in cases.values())
    assert {name for name, check in cases.items() if not check['scenarios']} == {'unsupported_variable_fee', 'ambiguous_deadline'}


def test_after_d03a_every_dispute_case_is_blocked_at_claim_scope_only_by_d04(receipt):
    # Replaces the pre-D03 assertion (12/12 blocked by D03 and D04; receipt preflight-evaluation84.json).
    # D03-A accepts the exact spaced names; D04-C is decided but not yet implemented.
    built, _, _ = receipt
    cases = built['disputes']
    assert len(cases) == 12
    for case in cases:
        assert case['outcome'] == 'SCOPE_REFUSED' and case['model_calls'] == 0
        assert case['blockers']['D03'] == []
        assert {item['field'] for item in case['blockers']['D04']} == {'component', 'incident', 'invoice', 'region'}
        assert case['blockers']['other'] == []
    assert built['summary']['dispute_blocked_by_D03'] == 0
    assert built['summary']['dispute_blocked_by_D04'] == 12


def test_derived_scope_uses_only_literal_context_values():
    source = json.loads((preflight.ROOT / 'fixtures/evaluation84_public/disputes/05_full_award/source.json').read_bytes())
    scope = preflight._derived_scope(source)
    assert scope == {'account': 'Cedar Orrery Studio', 'vendor': 'Talus Signal',
                     'contract': 'Talus Signal Availability Agreement', 'service': 'Event Relay',
                     'currency': 'USD', 'month': '2033-10'}
