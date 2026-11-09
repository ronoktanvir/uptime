"""Compose frozen authored setup and real public model jobs through signed app routes.

No expected answers are read. Setup is an explicitly scripted local evaluation,
not a human review, release certification, native write, or real vendor delivery.
Every case has one create-only attempt folder. A setup refusal is preserved.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.dispute_runtime_finish import create_json, dispatch_model_job


class SetupRefusal(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


@contextmanager
def workspace(path, config, prepared):
    from fastapi.testclient import TestClient
    from uptime.auth import DEFAULT_ORIGIN, SCRIPT
    from uptime.auth_client import ReviewerClient, service_headers
    from uptime.server import create_app
    secret = secrets.token_urlsafe(32)
    keys = {f'{role}-evaluation-source': secrets.token_hex(32) for role in ('status', 'customer', 'billing', 'vendor')}
    app = create_app(path, rehearsal=True, rehearsal_secret=secret, approvals_enabled=True,
                     service_credentials=keys, proposal_config=config)
    clock = datetime.fromisoformat(prepared['filing_clock'].replace('Z', '+00:00'))
    app.state.correspondence.clock = lambda: clock
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 4510)) as client:
        signed = ReviewerClient(client, DEFAULT_ORIGIN, SCRIPT, secret)

        def deliver(scope, claim_url, event_id, role, body):
            subject = f'{role}-evaluation-source'
            raw = canonical({'event_id': event_id, 'scope': scope, 'body': body})
            target = claim_url + '/events'
            headers = service_headers(instance=app.state.auth.instance, origin=DEFAULT_ORIGIN,
                                      subject=subject, key=keys[subject], path=target, body=raw)
            return client.post(target, content=raw, headers=headers)

        class Signed:
            def get(self, url):
                return client.get(url, headers=signed.headers)
            def post(self, url, body):
                return signed.post(url, body)
        yield app, Signed(), deliver


def response_record(response):
    try:
        body = response.json()
    except ValueError:
        body = {'non_json': True}
    return {'http_status': response.status_code, 'body': body}


def run_case(*, prepared_path, blind_path, attempt_dir, config_path, approved_by, expected_pins):
    from scripts.public_proposals import approve
    for path in (Path(prepared_path), Path(blind_path)):
        if path.is_symlink() or path.resolve() != path or sha256(path.read_bytes()).hexdigest() != expected_pins[str(path)]:
            raise ValueError('Frozen setup or source-only reading changed.')
    prepared = json.loads(Path(prepared_path).read_bytes())
    blind = json.loads(Path(blind_path).read_bytes())
    if prepared.get('schema') != 'supplementary-dispute-setup/1' or prepared.get('authority') != 'SCRIPTED_NOT_ACTUAL_HUMAN':
        raise ValueError('Use the explicitly scripted authored setup schema.')
    if sha256(prepared['reply']['text'].encode()).hexdigest() != blind['reply_sha256']:
        raise ValueError('Source-only reading belongs to another reply.')
    folder = Path(attempt_dir)
    folder.mkdir(mode=0o700)  # exclusive: never repeat a first attempt
    create_json(folder / 'started.json', {'setup_sha256': expected_pins[str(Path(prepared_path))],
                                         'blind_sha256': expected_pins[str(Path(blind_path))]})
    report = {'schema': 'supplementary-dispute-result/1', 'case_id': prepared['case_id'],
              'authority': 'SCRIPTED_NOT_ACTUAL_HUMAN', 'stage': 'setup', 'steps': [],
              'model_dispatched': False, 'gold_read': False, 'external_actions': []}
    claim_url = '/api/correspondence/claims/' + prepared['claim']['claim_id']
    vendor_url = '/api/vendors/' + prepared['vendor_slot']

    def checked(response, name):
        value = response_record(response)
        report['steps'].append({'name': name, **value})
        if response.status_code != 200:
            raise SetupRefusal(name)
        return value['body']

    try:
        with workspace(folder / 'workspace.sqlite', config_path, prepared) as (app, signed, deliver):
            state = checked(signed.post(vendor_url + '/candidates', prepared['candidate']), 'candidate')
            if state.get('state') != 'SHADOW':
                raise SetupRefusal('candidate_not_shadow')
            # Setup tests are separately source-derived before model evaluation, never scored gold.
            state = checked(signed.post(vendor_url + '/tests', {'revision': state['revision'],
                                                               'tests': prepared['setup_tests']}), 'source_setup_tests')
            for operation in ('approve', 'activate'):
                action = next((a for a in state.get('actions', []) if a.get('operation') == operation), None)
                if action is None:
                    raise SetupRefusal(f'no_scripted_{operation}_permission')
                state = checked(signed.post(vendor_url + '/actions/' + action['id'], {}), 'scripted_' + operation)
            scope = prepared['claim']['scope']
            inbox = app.state.correspondence
            inbox.provision('bears', *(scope.get(k) for k in ('account', 'vendor', 'contract', 'service', 'component', 'region')))
            for role in ('status', 'customer', 'billing', 'vendor'):
                inbox.bind_sender('bears', scope['account'], role, f'{role}-evaluation-source', scope=scope)
            checked(signed.post('/api/correspondence/claims', prepared['claim']), 'claim_intake')
            for event in prepared['evidence']:
                checked(deliver(scope, claim_url, event['event_id'], event['role'], event['body']), 'evidence_' + event['event_id'])
            for operation in ('approve-claim', 'submit-claim'):
                checked(signed.post(claim_url + '/actions/' + operation, {}), operation)
            filed = checked(signed.get(claim_url), 'filed_readback')
            if not filed.get('submissions'):
                raise SetupRefusal('no_original_filing')
            reply = dict(kind='message', text=prepared['reply']['text'], receipt_id=filed['submissions'][0]['id'])
            checked(deliver(scope, claim_url, 'evaluation-reply', 'vendor', reply), 'vendor_reply')
            report['stage'] = 'interpretation'
            view = checked(signed.get(claim_url + '/interpretation'), 'interpretation_context')
            context = view.get('context') or {}
            if 'digest' not in context:
                report['outcome'] = 'NATIVE_PARSER_RESULT'
                report['case'] = checked(signed.get(claim_url), 'native_case')
                return report
            checked(signed.post(claim_url + '/interpretation/blind-entry', {
                'context_digest': context['digest'], 'interpretation': blind['interpretation']}), 'scripted_source_reading')
            view = checked(signed.get(claim_url + '/interpretation'), 'public_request')
            job = view.get('model_job') or {}
            exported = job.get('approval_request')
            if not exported:
                raise SetupRefusal('no_exact_public_request')
            export = folder / 'request-export.json'
            create_json(export, exported)
            from uptime.public_proposal_config import PublicProposalConfig
            from uptime.source_config import load_private
            config = load_private(Path(config_path), PublicProposalConfig)
            approve(export, Path(config.approvals_path), approved_by=approved_by,
                    expected_digest=job['request_sha256'], public_confirmed=True, hours=6)
            view = checked(signed.get(claim_url + '/interpretation'), 'approved_request')
            if view.get('context', {}).get('digest') != context['digest']:
                raise SetupRefusal('context_changed_before_dispatch')
            report['stage'] = 'model'
            report['dispatch'] = dispatch_model_job(
                signed, claim_url, expected_context_digest=context['digest'], frozen_request=exported['request'],
                expected_request_sha256=job['request_sha256'], pinned_blind=view['blind_entry'],
                read_state=lambda: signed.get(claim_url).json(), folder=folder / 'dispatch')
            report['model_dispatched'] = (folder / 'dispatch' / 'dispatch.marker').exists()
            report['case'] = checked(signed.get(claim_url), 'final_case')
            report['outcome'] = report['dispatch']['outcome']
            # No automatic semantic acceptance. Raw model output and source reading stay separate.
            report['review_action'] = 'NOT_PERFORMED'
            if prepared.get('review_mode') == 'scripted_source_projection':
                # A separately frozen source reading exercises deterministic disposition.
                # This is not an acceptance/correction of the raw model candidate and is
                # never counted as model accuracy or actual independent human authority.
                report['stage'] = 'scripted_source_projection'
                projection = {'context_digest': context['digest'], 'interpretation': blind['interpretation'],
                              'candidate_id': None, 'residuals_reviewed': True, 'complete_meaning_reviewed': True,
                              'resolutions': [{'proposition': i, 'verdict': 'accept',
                                               'explanation': 'Scripted evaluation of the separately frozen source-only reading.'}
                                              for i, _ in enumerate(blind['interpretation']['propositions'])]}
                review = checked(signed.post(claim_url + '/interpretation/reviews', projection), 'scripted_projection_review')
                preview = checked(signed.get(claim_url + '/interpretation/reviews/' + review['id'] + '/preview'),
                                  'scripted_projection_preview')
                report['source_projection'] = preview
                report['review_action'] = 'SCRIPTED_SOURCE_PROJECTION_NOT_MODEL_ACCEPTANCE'
                if preview.get('prepare_allowed'):
                    report['prepared_case'] = checked(signed.post(claim_url + '/interpretation/prepare-response',
                        {'review_id': review['id'], 'preview_digest': preview['digest']}), 'scripted_projection_prepare')
                report['case'] = checked(signed.get(claim_url), 'post_projection_case')
            return report
    except Exception as error:
        report['model_dispatched'] = (folder / 'dispatch' / 'dispatch.marker').exists()
        report['outcome'] = 'SETUP_REFUSAL' if not report['model_dispatched'] else 'ATTEMPT_ERROR'
        report['error_type'] = type(error).__name__
        report['error'] = str(error)
        return report
    finally:
        create_json(folder / 'result.json', report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('prepared-path', 'blind-path', 'attempt-dir', 'config-path', 'pins-path'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--approved-by', required=True)
    args = parser.parse_args(argv)
    from scripts.evaluate_onboarding_finish import verify_freeze
    pins = json.loads(args.pins_path.read_bytes())
    verify_freeze(source_commit=args.source_commit, pinned_inputs=pins)
    result = run_case(prepared_path=args.prepared_path, blind_path=args.blind_path, attempt_dir=args.attempt_dir,
                      config_path=args.config_path, approved_by=args.approved_by, expected_pins=pins)
    print(json.dumps({k: result.get(k) for k in ('case_id', 'outcome', 'stage', 'model_dispatched', 'error_type')}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
