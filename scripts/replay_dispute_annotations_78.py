"""Offline remediation replay of unchanged public76 annotations; never calls a provider.

The old corpus, requests, responses, annotations and baseline remain immutable.
This measures deterministic mapping after a representation correction, not a blind
score, new extraction quality, actual human review or operational authorization.
"""
from dataclasses import asdict
from hashlib import sha256
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from uptime.correspondence_interpretation import Interpretation, proposal_for_review, validate_grounding

REASONS = {'LATE_FILING':'time_bar','MISSING_EVIDENCE':'artifact','THRESHOLD_NOT_BREACHED':'availability',
           'EXCLUDED_DOWNTIME':'maintenance','AWARD':'award','PARTIAL_AWARD':'award','UNKNOWN':'unknown'}
BASE = 'c14df32'


def replay():
    inputs = ['fixtures/evaluation76_public', 'docs/v4/evaluation76']
    subprocess.run(['git','diff','--exit-code',BASE,'--',*inputs],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    pins = {}
    def read(relative):
        raw = (ROOT / relative).read_bytes()
        pins[relative] = sha256(raw).hexdigest()
        return json.loads(raw)
    manifest = read('fixtures/evaluation76_public/manifest.json')
    for item in manifest['inputs_and_expected_files']:
        raw = (ROOT/'fixtures/evaluation76_public'/item['path']).read_bytes()
        assert len(raw) == item['bytes'] and sha256(raw).hexdigest() == item['sha256']
    golds = read('fixtures/evaluation76_public/expected/disputes.json')['cases']
    rows = []
    for gold in golds:
        ident = gold['id']
        old = read(f'docs/v4/evaluation76/results/{ident}.json')
        context = read(f'docs/v4/evaluation76/requests/{ident}.local.json')
        annotation = old['candidate']['interpretation']
        parsed = Interpretation.model_validate(annotation)
        validate_grounding(context['text'], parsed)
        error = None
        try:
            mapped = asdict(proposal_for_review(context, parsed))
        except ValueError as exc:
            mapped = dict(reason='unknown', amount=None, artifact_type=None, reference=None)
            error = str(exc)
        expected = REASONS[gold['expected_semantic_family']]
        reason_matches = mapped['reason'] == expected
        full_matches = reason_matches and mapped.get('amount') == gold.get('reported_award')
        if gold.get('artifact'):
            full_matches = full_matches and mapped.get('reference') == gold['artifact']['reference'] and mapped.get('artifact_type') == 'resource_log'
        rows.append(dict(id=ident, baseline_mapping=old['mapped_proposal'], remediated_mapping=mapped,
                         unchanged_annotation_sha256=sha256(json.dumps(annotation,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                         expected_reason=expected, expected_supported=gold['expected_supported_mapping'],
                         reason_matches=reason_matches, full_semantics_match=bool(full_matches), mapping_error=error,
                         human_review_performed=False, action_authority_evaluated=False, actions_executed=0))
    supported = [r for r in rows if r['expected_supported']]
    controls = [r for r in rows if not r['expected_supported']]
    return dict(schema='uptime-dispute-remediation78/1', label='OFFLINE_UNCHANGED_PUBLIC76_ANNOTATIONS_NOT_NEW_BLIND_SCORE',
                baseline_commit=BASE, source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                source_files_sha256={p:sha256((ROOT/p).read_bytes()).hexdigest() for p in
                    ['uptime/correspondence_interpretation.py','uptime/correspondence_review.py','web/interpretation.js']},
                model_calls=0, frozen_inputs_sha256=pins, cases=rows,
                summary=dict(grounded=12,total=12,supported_family_matches=sum(r['reason_matches'] for r in supported),
                             supported_full_semantics_matches=sum(r['full_semantics_match'] for r in supported), supported_total=len(supported),
                             unknown_review_controls=sum(r['remediated_mapping']['reason']=='unknown' for r in controls),review_controls_total=len(controls)),
                limitations=['Frozen76 baseline remains 4/6 supported family mappings and3/6 full semantics.',
                             'No new extraction, independent unseen score, actual human review, preparation or financial action.',
                             'Artifact category is not inferred from a document identifier.'])


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=replay()
    with args.output.open('x') as out:
        json.dump(result,out,indent=2,sort_keys=True);out.write('\n')
    print(json.dumps(result['summary']))
