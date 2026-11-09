#!/usr/bin/env python3
"""Consume a frozen supplementary cohort once; never open its expected outcomes.

The manifest contains only source/setup paths and hash commitments. A missing or
refused setup remains in the denominator. Every result is create-only, including
failures before model dispatch. Scripted local authority is not human approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.dispute_runtime_finish import create_json
from scripts.evaluate_onboarding_finish import verify_freeze


def compact_case(case, result):
    if case['kind'] == 'onboarding':
        jobs = result.get('jobs', [])
        return {'id': case['id'], 'kind': case['kind'], 'outcome': result.get('outcome'),
                'stage': result.get('stage'), 'model_jobs': len(jobs),
                'job_states': [r.get('status') for r in jobs], 'candidate': result.get('candidate'),
                'shadow_previews': len(result.get('previews', [])), 'error_type': result.get('error_type'),
                'promotion_performed': False}
    return {'id': case['id'], 'kind': case['kind'], 'outcome': result.get('outcome'),
            'stage': result.get('stage'), 'model_dispatched': result.get('model_dispatched', False),
            'raw_model_outcome': result.get('dispatch', {}).get('outcome'),
            'scripted_projection': result.get('review_action'), 'continuation': result.get('continuation'),
            'error_type': result.get('error_type'), 'error': result.get('error'),
            'actual_human_review': False}


def run(manifest_path, run_dir, *, manifest_sha256, source_commit):
    from scripts import evaluate_onboarding_finish as onboarding
    from scripts import evaluate_disputes_finish as disputes
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink() or manifest_path.resolve() != manifest_path:
        raise ValueError('Manifest must be an absolute regular path without aliases.')
    raw = manifest_path.read_bytes()
    if sha256(raw).hexdigest() != manifest_sha256:
        raise ValueError('Execution manifest commitment changed.')
    manifest = json.loads(raw)
    if manifest.get('schema') != 'supplementary-execution-manifest/1':
        raise ValueError('Unsupported execution manifest.')
    cases = manifest['cases']
    if len(cases) != 14 or Counter(c['kind'] for c in cases) != {'onboarding': 6, 'dispute': 8}:
        raise ValueError('Retain every preregistered case, including setup refusals.')
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate case ID.')
    if any('/' in c['id'] or '..' in c['id'] for c in cases):
        raise ValueError('Case IDs cannot be paths.')
    pins = manifest['pins']
    for case in cases:
        required = ('document', 'overlay', 'config') if case['kind'] == 'onboarding' else ('prepared', 'blind', 'config')
        if not case.get('preflight_refusal') and any(case.get(key) not in pins for key in required):
            raise ValueError('Every consumed case input and provider config must be pinned.')
        if case.get('scenarios') and case['scenarios'] not in pins:
            raise ValueError('Scenario input must be pinned.')
    verify_freeze(source_commit=source_commit, pinned_inputs=pins)
    folder = Path(run_dir)
    folder.mkdir(mode=0o700)
    create_json(folder / 'started.json', {'manifest_sha256': manifest_sha256, 'source_commit': source_commit,
                                        'at': datetime.now(UTC).isoformat(), 'gold_read': False})
    summaries = []
    for case in cases:
        # Check again between cases, preventing a mid-cohort source edit from
        # silently evaluating different code. A refusal is terminal, not a skip.
        attempt = folder / case['id']
        try:
            verify_freeze(source_commit=source_commit, pinned_inputs=pins)
            if case.get('preflight_refusal'):
                result = {'outcome': 'SOURCE_MAPPING_REFUSAL', 'stage': 'source_setup',
                          'error': case['preflight_refusal'], 'model_dispatched': False, 'gold_read': False}
                attempt.mkdir(mode=0o700)
                create_json(attempt / 'result.json', result)
            elif case['kind'] == 'onboarding':
                result = onboarding.run(document_path=case['document'], overlay_path=case['overlay'],
                    scenarios_path=case.get('scenarios'), run_dir=attempt, config_path=case['config'],
                    approve=True, approved_by='scripted-evaluation-operator')
            else:
                result = disputes.run_case(prepared_path=Path(case['prepared']), blind_path=Path(case['blind']),
                    attempt_dir=attempt, config_path=Path(case['config']),
                    approved_by='scripted-evaluation-operator', expected_pins=pins)
        except Exception as error:
            # Never overwrite a runner receipt, even if its finalization raised.
            result = {'outcome': 'RUNNER_ERROR', 'stage': 'runner', 'error_type': type(error).__name__,
                      'error': str(error), 'model_dispatched': None, 'gold_read': False}
            create_json(folder / (case['id'] + '-runner-error.json'), result)
        summary = compact_case(case, result)
        summaries.append(summary)
        create_json(folder / (case['id'] + '-summary.json'), summary)
        print(json.dumps(summary), flush=True)
    result = {'schema': 'supplementary-ungraded-results/1', 'source_commit': source_commit,
              'manifest_sha256': manifest_sha256, 'cases': summaries, 'declared_cases': 14,
              'terminal_case_records': len(summaries), 'gold_read': False,
              'outcomes': dict(Counter(c.get('outcome') or 'UNREACHED' for c in summaries)),
              'authority': 'scripted local evaluation; no actual-human review or external financial action'}
    create_json(folder / 'ungraded-results.json', result)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--manifest-sha256', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    a = p.parse_args(argv)
    run(a.manifest, a.run_dir, manifest_sha256=a.manifest_sha256, source_commit=a.source_commit)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
