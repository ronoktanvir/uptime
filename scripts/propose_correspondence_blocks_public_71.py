"""Explicit authored-public experiment only; no database or private evaluator inputs."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uptime.correspondence_block_model import BLOCK_SYSTEM, PublicBlockInterpretationAdapter, serialized_block_request
from uptime.correspondence_blocks import BlockInterpretation
from uptime.correspondence_interpretation import Interpretation, proposal_for_review
from uptime.correspondence_model import MODEL
from uptime.correspondence_model_transport import SafePublicClaude, strict_json

FROZEN = '16e994d2876a954a4847cab213488a47b5bd8e70c5a5ceaaffb82c1eb42b682f'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-public', action='store_true')
    parser.add_argument('--output', type=Path, required=True, help='New directory; existing output is never overwritten.')
    parser.add_argument('--case', action='append', help='An ID in the frozen authored controls; defaults to all eight.')
    parser.add_argument('--executable', default=str(Path.home() / '.local/bin/claude'))
    args = parser.parse_args()
    if not args.execute_public:
        parser.error('External inference is disabled without explicit --execute-public.')
    raw = (ROOT / 'fixtures/correspondence/public-71/controls.json').read_bytes()
    if sha256(raw).hexdigest() != FROZEN:
        raise ValueError('The authored public controls changed after their freeze.')
    cases = strict_json(raw)['cases']
    selected = set(args.case or [r['id'] for r in cases])
    if not selected <= {r['id'] for r in cases}:
        raise ValueError('Only frozen public case IDs may be selected.')
    args.output.mkdir(parents=True, exist_ok=False)
    for row in cases:
        if row['id'] not in selected:
            continue
        provider = SafePublicClaude(args.executable, model=MODEL, system=BLOCK_SYSTEM)
        request = serialized_block_request(row['context'], provider.profile)
        digest = sha256(request).hexdigest()
        (args.output / (row['id'] + '.request.json')).write_bytes(request)

        class Capture:
            profile = provider.profile
            response = None

            def __call__(self, payload):
                self.response = provider(payload)
                return self.response

        captured = Capture()
        adapter = PublicBlockInterpretationAdapter(enabled=True, allowed_requests=[digest], provider=captured)
        result = dict(case=row['id'], classification='AUTHORED_PUBLIC_SYNTHETIC_NOT_BLIND',
                      request_sha256=digest, expected_reason=row['expected_reason'],
                      actual_human_review=False, operationally_reviewed=False, customer_processing=False,
                      status='NOT_RUN', json_schema_valid=False)
        try:
            result.update(adapter.propose(row['context']))
            result['status'] = 'STRUCTURALLY_VALID'
            interpretation = Interpretation.model_validate(result['interpretation'])
            result['deterministic_mapping'] = asdict(proposal_for_review(row['context'], interpretation))
            result['matches_authored_reason'] = result['deterministic_mapping']['reason'] == row['expected_reason']
        except Exception as exc:
            result.update(status='REFUSED', error=type(exc).__name__, detail=str(exc)[:400])
        if captured.response is not None:
            result['provider_text'] = captured.response['text']
            try:
                BlockInterpretation.model_validate(strict_json(captured.response['text']))
                result['json_schema_valid'] = True
            except ValueError:
                pass
        result['transport_observation'] = provider.last_receipt
        with (args.output / (row['id'] + '.result.json')).open('x') as output:
            output.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({key: result[key] for key in ('case', 'status', 'json_schema_valid')}
                         | {'deterministic_mapping': result.get('deterministic_mapping')}), flush=True)


if __name__ == '__main__':
    main()
