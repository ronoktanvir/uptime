"""Frozen public evaluation plumbing; no production edits, output repair or retries.

Expected truth is read only by score(), after attempts. Each case gets a create-only
protected attempt directory. Public requests are prepared and committed beforehand.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CORPUS = ROOT / 'fixtures/evaluation76_public'
REQUESTS = ROOT / 'docs/v4/evaluation76/requests'
PIN = 'fd6537cc4e3118a9b6e29f4804a505ed591ea9ea'
CORPUS_MANIFEST = '6dc212c296dea38dc5ad7a39ccdda3fe8ad64e5e902d93d1329c66c8060ce82d'
MODEL = 'claude-opus-5-5'
CLI = '/Users/ronoktanvir/.local/bin/claude'
REASON_MAP = {'LATE_FILING': 'time_bar', 'MISSING_EVIDENCE': 'artifact',
              'THRESHOLD_NOT_BREACHED': 'availability', 'EXCLUDED_DOWNTIME': 'maintenance',
              'AWARD': 'award', 'PARTIAL_AWARD': 'award', 'UNKNOWN': 'unknown'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(data):
    return sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def create_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(canonical(value))


def verify_corpus():
    assert digest((CORPUS / 'manifest.json').read_bytes()) == CORPUS_MANIFEST, 'Frozen corpus manifest changed'
    manifest = read(CORPUS / 'manifest.json')
    for entry in manifest['inputs_and_expected_files']:
        data = (CORPUS / entry['path']).read_bytes()
        assert len(data) == entry['bytes'] and digest(data) == entry['sha256'], 'Frozen corpus file changed'
    subprocess.run(['git', 'diff', '--exit-code', PIN, '--', 'uptime'], cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL)
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--', 'uptime'], cwd=ROOT), 'Core is not frozen'
    return manifest


def cases():
    onboarding = [read(CORPUS / item['input']) for item in read(CORPUS / 'inputs/onboarding-index.json')['cases']]
    return onboarding + read(CORPUS / 'inputs/disputes.json')['cases']


def legacy_request(argv, kwargs):
    """Pin actual legacy generate() arguments without persisting authentication values."""
    exe = Path(shutil.which(argv[0], path=kwargs['env']['PATH'])).resolve(strict=True)
    return dict(domain='uptime.public-evaluation76.legacy-onboarding', model=MODEL,
                argv=argv, stdin=kwargs['input'], stdin_sha256=digest(kwargs['input'].encode()),
                executable_sha256=digest(exe.read_bytes()), environment_keys=sorted(kwargs['env']),
                timeout_seconds=kwargs['timeout'], output_limit_bytes=3_000_000, output_format='json',
                transport_class='LEGACY_VENDOR_MODEL_SUBPROCESS_NOT_SAFEPUBLICCLAUDE',
                tools_requested=[], initialized_tools_verified=False,
                credential_values_stored=False, cwd='fresh-temporary-directory')


class CapturedRequest(Exception):
    pass


def capture_legacy(case):
    from uptime import vendor_model
    from uptime.vendor_terms import Document
    captured = None

    def collect(argv, **kwargs):
        nonlocal captured
        captured = legacy_request(argv, kwargs)
        raise CapturedRequest

    with patch.object(vendor_model, 'subprocess', SimpleNamespace(run=collect)):
        try:
            vendor_model.generate(Document.model_validate(case['document']),
                                  digest(case['document']['text'].encode()), allow_propositions=True,
                                  profile=case['requested_profile'])
        except CapturedRequest:
            pass
    if captured is None:
        raise ValueError('No request was produced by the frozen public entrypoint')
    return canonical(captured)


def context_for(case):
    supplied = case['context']
    return dict(text=case['text'], scope={'month': supplied['scope_month']}, currency=supplied['currency'],
                requested=supplied['claimed'], filing_fields=[])


def mapped_evaluation_input(case):
    keys = ('agreement', 'account', 'product', 'plan', 'month', 'fee_line_ref', 'resource_id')
    facts = {key: case['scope'][key] for key in keys if key in case['scope']}
    facts.update(case['evidence'])
    # filing_ref is a neutral receipt reference, not an evaluator observation field.
    # Preserve it in the mapping record; no proof/verified status is invented from it.
    unmapped = {}
    if 'filing_ref' in facts:
        unmapped['filing_ref'] = facts.pop('filing_ref')
    return dict(overlay=case['overlay'], facts=facts, tenant='authored-public76',
                unconsumed_evidence=unmapped, pricing_evidence=case.get('pricing_evidence'),
                authority_policy='No opaque fee authority or semantic-review context is synthesized. Report required gates separately.')


def prepare():
    verify_corpus()
    from uptime.correspondence_block_model import BLOCK_SYSTEM, serialized_block_request
    from uptime.correspondence_model_transport import SafePublicClaude
    provider = SafePublicClaude(CLI, model=MODEL, system=BLOCK_SYSTEM)  # help/version only; no model call
    REQUESTS.mkdir(parents=True, exist_ok=False)
    entries = []
    for case in cases():
        ident = case['id']
        if ident.startswith('onboarding'):
            request = capture_legacy(case)
            context = mapped_evaluation_input(case)
            kind = 'onboarding'
        else:
            context = context_for(case)
            request = serialized_block_request(context, provider.profile)
            kind = 'dispute'
        request_path = REQUESTS / f'{ident}.request.json'
        request_path.write_bytes(request)
        context_path = REQUESTS / f'{ident}.local.json'
        create_json(context_path, context)
        entries.append(dict(id=ident, kind=kind, request_file=request_path.name,
                            request_sha256=digest(request), local_file=context_path.name,
                            local_sha256=digest(context_path.read_bytes())))
    manifest = dict(schema='uptime-public-evaluation76-requests/1', implementation_commit=PIN,
                    corpus_manifest_sha256=CORPUS_MANIFEST, harness_sha256=digest(Path(__file__).read_bytes()),
                    cases=entries, expected_answers_outbound=False, max_calls_per_request=1,
                    max_concurrent_calls=2, onboarding_allow_propositions=True,
                    strict_output_policy='Record native legacy fence normalization separately; it is not strict-output success.',
                    action_policy='Candidate meaning only; no human review, approval, ledger mutation or provider write.',
                    score_reason_mapping=REASON_MAP,
                    score_artifact_mapping={'request_log': 'resource_log'},
                    evaluation_authority_policy='Do not manufacture opaque financial/semantic authority; report missing gates separately.')
    create_json(REQUESTS / 'manifest.json', manifest)
    print(json.dumps(dict(prepared=len(entries), manifest_sha256=digest((REQUESTS / 'manifest.json').read_bytes()))), flush=True)


def check_requests(expected_digest):
    verify_corpus()
    data = (REQUESTS / 'manifest.json').read_bytes()
    assert digest(data) == expected_digest, 'Request manifest digest mismatch'
    manifest = json.loads(data)
    assert manifest['harness_sha256'] == digest(Path(__file__).read_bytes()), 'Frozen harness changed'
    for entry in manifest['cases']:
        assert digest((REQUESTS / entry['request_file']).read_bytes()) == entry['request_sha256']
        assert digest((REQUESTS / entry['local_file']).read_bytes()) == entry['local_sha256']
    return manifest


def spool(argv, *, payload, cwd, env, timeout, limit, folder):
    """Persist bytes from process startup, including a bounded timeout's partial output."""
    started = time.monotonic()
    stdout_path, stderr_path = folder / 'provider.stdout', folder / 'provider.stderr'
    with tempfile.TemporaryFile() as incoming, stdout_path.open('xb') as outgoing, stderr_path.open('xb') as errors:
        incoming.write(payload)
        incoming.seek(0)
        process = subprocess.Popen(argv, stdin=incoming, stdout=outgoing, stderr=errors,
                                   cwd=cwd, env=env, start_new_session=True)
        create_json(folder / 'process-start.json', dict(pid=process.pid, started_at=datetime.now(timezone.utc).isoformat(),
                    timeout_seconds=timeout, output_limit_bytes=limit, request_attempt=1))
        try:
            while True:
                if stdout_path.stat().st_size + stderr_path.stat().st_size > limit:
                    raise ValueError('Provider output exceeded the pinned byte bound; no retry')
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError('Provider timed out; partial output retained; no retry')
                try:
                    code = process.wait(timeout=min(.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    pass
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    output, error = stdout_path.read_bytes(), stderr_path.read_bytes()
    if len(output) + len(error) > limit:
        raise ValueError('Provider output exceeded the pinned byte bound; no retry')
    return code, output, error


def output_metadata(folder):
    return {name: dict(sha256=digest((folder / name).read_bytes()), bytes=(folder / name).stat().st_size)
            for name in ('provider.stdout', 'provider.stderr') if (folder / name).exists()}


def legacy_output_details(folder):
    """Observe raw legacy bytes; do not strip fences or repair JSON in this harness."""
    from uptime.correspondence_model_transport import strict_json
    try:
        envelope = strict_json((folder / 'provider.stdout').read_bytes())
        raw = envelope.get('result')
        valid = False
        if isinstance(raw, str):
            try:
                strict_json(raw)
                valid = True
            except (ValueError, TypeError):
                pass
        return dict(model_usage=envelope.get('modelUsage'), session=envelope.get('session_id'),
                    provider_is_error=envelope.get('is_error'), strict_json_output=valid,
                    legacy_fence_normalization_eligible=isinstance(raw, str) and raw.strip().startswith('```json')
                    and raw.strip().endswith('```'), raw_result_sha256=digest(raw.encode()) if isinstance(raw, str) else None)
    except (ValueError, OSError, TypeError, AttributeError):
        return dict(strict_json_output=False, raw_envelope_readable=False)


def run_onboarding(case, entry, folder):
    from uptime import vendor_model
    from uptime.vendor_terms import Document, Overlay, bind_overlay
    from uptime.vendor_eval import evaluate
    expected_request = (REQUESTS / entry['request_file']).read_bytes()
    local = read(REQUESTS / entry['local_file'])
    result = dict(id=case['id'], kind='onboarding', extraction_accepted=False,
                  schema_grounding_accepted=False, evaluator_called=False, financial_mutation=False,
                  human_approval=False, transport_class='LEGACY_VENDOR_MODEL_SUBPROCESS_NOT_SAFEPUBLICCLAUDE')

    def observed_run(argv, **kwargs):
        assert canonical(legacy_request(argv, kwargs)) == expected_request, 'Actual legacy request differs from pin'
        code, output, error = spool(argv, payload=kwargs['input'].encode(), cwd=kwargs['cwd'], env=kwargs['env'],
                                    timeout=kwargs['timeout'], limit=3_000_000, folder=folder)
        return subprocess.CompletedProcess(argv, code, output.decode(), error.decode())

    try:
        with patch.object(vendor_model, 'subprocess', SimpleNamespace(run=observed_run)):
            artifact = vendor_model.generate(Document.model_validate(case['document']),
                digest(case['document']['text'].encode()), allow_propositions=True, profile=case['requested_profile'])
        result.update(extraction_accepted=True, schema_grounding_accepted=True, extraction=artifact)
        manifest = vendor_model.validate_proposal(Document.model_validate(case['document']), artifact['proposal'],
                                                  allow_propositions=True)
        result['compiled_manifest'] = manifest
        overlay = bind_overlay(manifest, Overlay.model_validate(local['overlay']))
        result['overlay_accepted'] = True
        result['evaluator_called'] = True
        result['evaluation'] = evaluate(manifest, overlay, local['facts'], local['tenant'])
        result['action_eligibility'] = 'NOT_AUTHORIZED_NO_REVIEW_OR_EFFECT_AUTHORITY'
    except vendor_model.RejectedProposal as exc:
        result.update(stage='proposal_validation_refusal', error_type=type(exc).__name__, error=str(exc),
                      rejection=exc.receipt)
    except Exception as exc:
        result.update(stage='downstream_or_transport_failure', error_type=type(exc).__name__, error=str(exc))
    result['legacy_raw_output'] = legacy_output_details(folder)
    return result


def run_dispute(case, entry, folder):
    from uptime import correspondence_model_transport as transport
    from uptime.correspondence_block_model import BLOCK_SYSTEM, PublicBlockInterpretationAdapter, serialized_block_request
    from uptime.correspondence_interpretation import Interpretation, proposal_for_review
    context = read(REQUESTS / entry['local_file'])
    provider = transport.SafePublicClaude(CLI, model=MODEL, system=BLOCK_SYSTEM)
    encoded = serialized_block_request(context, provider.profile)
    assert encoded == (REQUESTS / entry['request_file']).read_bytes(), 'Actual block request differs from pin'
    result = dict(id=case['id'], kind='dispute', schema_grounding_accepted=False,
                  financial_mutation=False, human_approval=False, action_eligibility='NOT_AUTHORIZED_NO_REVIEW_OR_EFFECT_AUTHORITY')

    def observed_run(argv, *, payload=b'', cwd, env, timeout=60, limit=300000):
        assert payload == encoded, 'Actual outbound payload differs from pin'
        return spool(argv, payload=payload, cwd=cwd, env=env, timeout=timeout, limit=limit, folder=folder)

    try:
        with patch.object(transport, 'bounded_run', observed_run):
            candidate = PublicBlockInterpretationAdapter(allowed_requests=[entry['request_sha256']],
                                                        provider=provider, enabled=True).propose(context)
        result.update(schema_grounding_accepted=True, candidate=candidate)
        proposal = proposal_for_review(context, Interpretation.model_validate(candidate['interpretation']))
        result['mapped_proposal'] = asdict(proposal)
    except Exception as exc:
        result.update(stage='transport_or_grounding_or_mapping_failure', error_type=type(exc).__name__, error=str(exc))
    result['transport_receipt'] = provider.last_receipt
    return result


def run_case(ident, expected_digest, output):
    manifest = check_requests(expected_digest)
    entry = next(item for item in manifest['cases'] if item['id'] == ident)
    case = next(item for item in cases() if item['id'] == ident)
    output.mkdir(parents=True, exist_ok=True)
    output.chmod(0o700)
    folder = output / ident
    folder.mkdir(mode=0o700, exist_ok=False)  # No second attempt, including after interruption.
    create_json(folder / 'attempt.json', dict(id=ident, request_sha256=entry['request_sha256'],
                request_manifest_sha256=expected_digest, implementation_commit=PIN,
                harness_sha256=manifest['harness_sha256'], started_at=datetime.now(timezone.utc).isoformat()))
    started = time.monotonic()
    try:
        result = run_onboarding(case, entry, folder) if entry['kind'] == 'onboarding' else run_dispute(case, entry, folder)
    except Exception as exc:
        result = dict(id=ident, kind=entry['kind'], stage='harness_or_pre_dispatch_failure',
                      error_type=type(exc).__name__, error=str(exc), financial_mutation=False, human_approval=False)
    result.update(request_sha256=entry['request_sha256'], elapsed_seconds=time.monotonic() - started,
                  process_output=output_metadata(folder), request_attempts=int((folder / 'process-start.json').exists()))
    create_json(folder / 'result.json', result)
    print(json.dumps(dict(id=ident, status='RECORDED', request_attempts=result['request_attempts'])), flush=True)


def run_all(expected_digest, output):
    manifest = check_requests(expected_digest)

    def child(entry):
        return subprocess.run([sys.executable, str(Path(__file__).resolve()), 'case', '--case', entry['id'],
            '--request-manifest-sha256', expected_digest, '--output-dir', str(output)], cwd=ROOT).returncode

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = list(pool.map(child, manifest['cases']))
    if any(codes):
        raise SystemExit('One or more case runners failed; preserve existing attempts and do not rerun them')


def score(output):
    verify_corpus()
    gold_o = {case['id']: case for case in read(CORPUS / 'expected/onboarding.json')['cases']}
    gold_d = {case['id']: case for case in read(CORPUS / 'expected/disputes.json')['cases']}
    rows = []
    for ident, gold in {**gold_o, **gold_d}.items():
        path = output / ident / 'result.json'
        if not path.exists():
            rows.append(dict(id=ident, status='NO_COMPLETED_RECEIPT', pass_expected=False))
            continue
        observed = read(path)
        row = dict(id=ident, result_sha256=digest(path.read_bytes()), request_attempts=observed['request_attempts'],
                   schema_grounding_accepted=observed.get('schema_grounding_accepted', False),
                   stage=observed.get('stage', 'mapped'), error=observed.get('error'))
        if ident in gold_o:
            evaluation = observed.get('evaluation', {})
            row.update(expected_outcome=gold['expected_outcome'], expected_amount=gold['expected_amount'],
                       extraction_accepted=observed.get('extraction_accepted', False),
                       strict_json_output=observed.get('legacy_raw_output', {}).get('strict_json_output', False),
                       observed_outcome=evaluation.get('outcome'), observed_amount=evaluation.get('amount'),
                       evaluation_missing=evaluation.get('missing', []))
            row['expected_math_observed'] = (evaluation.get('outcome') == gold['expected_outcome'] and
                                            evaluation.get('amount') == gold['expected_amount'])
            row['safe_refusal_without_positive_money'] = (gold['expected_amount'] is None and
                evaluation.get('amount') is None and not observed.get('extraction_accepted', False))
            row['pass_expected'] = row['expected_math_observed'] and row['strict_json_output']
        else:
            mapped = observed.get('mapped_proposal', {})
            expected = REASON_MAP[gold['expected_semantic_family']]
            row.update(expected_reason=expected, observed_reason=mapped.get('reason'),
                       expected_award=gold['reported_award'], observed_award=mapped.get('amount'),
                       mandatory_review=gold['mandatory_review'])
            row['pass_expected'] = (row['schema_grounding_accepted'] and mapped.get('reason') == expected
                                    and mapped.get('amount') == gold['reported_award'])
            if gold.get('artifact'):
                row['pass_expected'] = row['pass_expected'] and mapped.get('reference') == gold['artifact']['reference']
                row['pass_expected'] = row['pass_expected'] and mapped.get('artifact_type') == 'resource_log'
            row['safe_abstention'] = gold['mandatory_review'] and (not mapped or mapped.get('reason') == 'unknown')
        rows.append(row)
    report = dict(schema='uptime-public-evaluation76-result/1', implementation_commit=PIN,
                  corpus_manifest_sha256=CORPUS_MANIFEST, rows=rows,
                  public_authored_not_blind=True, actual_human_approval=False, financial_mutation=False,
                  denominators=dict(onboarding=6, onboarding_supported=4, onboarding_refusal=2,
                                    disputes_supported=6, disputes_mandatory_review=6))
    create_json(output / 'score.json', report)
    print(json.dumps(dict(scored=len(rows), report=str(output / 'score.json'))), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'case', 'run-all', 'score'])
    parser.add_argument('--case')
    parser.add_argument('--request-manifest-sha256')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'case':
        if not all((args.case, args.request_manifest_sha256, args.output_dir)):
            parser.error('case requires exact ID, manifest hash and protected output directory')
        run_case(args.case, args.request_manifest_sha256, args.output_dir)
    elif args.command == 'run-all':
        if not args.request_manifest_sha256 or not args.output_dir:
            parser.error('run-all requires manifest hash and protected output directory')
        run_all(args.request_manifest_sha256, args.output_dir)
    else:
        if not args.output_dir:
            parser.error('score requires the retained output directory')
        score(args.output_dir)


if __name__ == '__main__':
    main()
