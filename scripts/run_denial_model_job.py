#!/usr/bin/env python3
"""Role 2: one genuine model job on an authored, unfamiliar January vendor reply.

A fresh Northwind workspace receives the chosen authored reply (``--variant``). The scripted
reviewer (SCRIPTED_NOT_ACTUAL_HUMAN) saves its own reading first, as decision 60/75 requires. One
exact, authored-public request is approved for a single model invocation with
scripts/public_proposals.py, submitted once through the ordinary signed model-job route, and never
retried. The model changes no claim state, money or scope.

- ``unclear``: the scripted semantic review follows in the same workspace (the earlier run).
- ``reworded-log-request``: the run stops once the model's candidate is stored, before any semantic
  review, so copies of that workspace can show a reviewer doing the review. The review, preview and,
  where the preview allows it, the preparation and the rest of the walkthrough then run on a separate
  scratch copy and are recorded under ``continuation``.

The source commit and a clean ``git status`` are captured before anything is written; the stored
transport fields are read from the job row after the run. Raw request and response stay in the run
directory, outside Git.
"""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import setup_northwind as setup  # noqa: E402
from uptime.auth import SCRIPT  # noqa: E402
from uptime.contracts import fingerprint  # noqa: E402

CLAIM = 'inbox-northwind-2026-01'
BASE = '/api/correspondence/claims/' + CLAIM
SCRIPTED = 'SCRIPTED_NOT_ACTUAL_HUMAN'
EXPORT_FIELDS = ('tenant', 'subject', 'kind', 'target', 'context_sha256', 'request', 'source_references')
VARIANTS = ('unclear', 'reworded-log-request')
CORRECTION = {
    'unclear': ('Scripted review: settlement at renewal and a disputed period are not grounds the system may act on; '
                'the case stays with a person.'),
    'reworded-log-request': ('Scripted review: the reply asks for the January resource log NW-JAN-LOG-001; the '
                             'reviewer keeps that reading.'),
}


def private_json(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def _span(text, quote):
    start = text.index(quote)
    return dict(start=len(text[:start].encode()), end=len(text[:start + len(quote)].encode()), quote=quote)


def _proposition(family, source, **changes):
    value = dict(family=family, source=source, polarity='positive', modality='asserted', referent='current_claim',
                 conditions=[], slots=[], artifact_type=None, scope_field=None, filing_fields=[])
    value.update(changes)
    return value


def own_reading(text, variant='unclear'):
    """The scripted reviewer's source-only reading, saved before any model output is visible."""
    whole = _span(text, text)
    if variant == 'reworded-log-request':
        found = _proposition('artifact', whole, artifact_type='resource_log',
                             slots=[dict(name='artifact_ref', source=_span(text, 'NW-JAN-LOG-001'))])
    else:
        found = _proposition('unsupported', whole)
    return dict(propositions=[found], segments=[dict(source=whole, role='substantive')])


def resolutions(mine, blind, candidate, variant='unclear'):
    rows = []
    for i in range(max(len(mine), len(blind), len(candidate))):
        if i >= len(mine):
            rows.append(dict(proposition=i, verdict='reject', explanation=(
                'Scripted review: the model proposed an additional meaning that the reviewer does not adopt.')))
        elif all(i < len(other) and other[i] == mine[i] for other in (blind, candidate)):
            rows.append(dict(proposition=i, verdict='accept', explanation=(
                "Scripted review: the reading matches the reviewer's own reading and the model proposal.")))
        else:
            rows.append(dict(proposition=i, verdict='correct', explanation=CORRECTION[variant]))
    return rows


def source_state(require_clean=True):
    """The commit the run executes, and whether any file differs from it. Refuses a dirty tree if asked."""
    git = lambda *args: subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True, check=True).stdout
    status = git('status', '--porcelain', '--untracked-files=all')
    state = dict(commit=git('rev-parse', 'HEAD').strip(), tree=git('rev-parse', 'HEAD^{tree}').strip(),
                 status_porcelain=status, clean=status == '', captured_at=datetime.now(UTC).isoformat())
    if require_clean and status:
        raise SystemExit('Refusing to run: the checkout has uncommitted or untracked files.\n' + status)
    return state


def provenance(database, job_id):
    """Stored transport fields of the job row, read after the job service has closed."""
    import sqlite3
    db = sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    try:
        row = db.execute('SELECT * FROM public_proposal_jobs WHERE id=?', (job_id,)).fetchone()
    finally:
        db.close()
    if row is None:
        return dict(job_row='NOT_FOUND')
    raw = json.loads(row['receipt_json']) if row['receipt_json'] else {}
    profile = raw.get('profile') or {}
    argv = list(profile.get('argv') or [])
    if '--system-prompt' in argv:
        i = argv.index('--system-prompt') + 1
        argv[i] = '<system prompt; sha256 ' + hashlib.sha256(argv[i].encode()).hexdigest() + '>'
    captured = lambda value: 'NOT_CAPTURED' if value is None else value
    return dict(
        job_row={k: row[k] for k in ('id', 'status', 'reason', 'request_sha256', 'context_sha256', 'submitted_at',
                                      'started_at', 'finished_at', 'approved_by', 'approved_at', 'expires_at', 'budget_usd')},
        profile=dict(name=captured(profile.get('name')), revision=captured(profile.get('revision')),
                     version=captured(profile.get('version')), binary_sha256=captured(profile.get('binary_sha256')),
                     retry_count=profile.get('retry_count'), timeout_seconds=profile.get('timeout_seconds'), argv=argv),
        **{k: captured(raw.get(k)) for k in ('model', 'session', 'returncode', 'tool_events', 'tool_inventory', 'mcp_inventory',
                                             'output_sha256', 'result_sha256', 'client_reported_cost_usd', 'hard_cost_cap')})


def _client(app, private):
    from fastapi.testclient import TestClient
    from uptime.auth_client import ReviewerClient
    client = TestClient(app, base_url=private['origin'], client=('127.0.0.1', 4510))
    return client, ReviewerClient(client, private['origin'], SCRIPT, private['rehearsal_secret'])


def _review(get, post, context, reading, candidate, variant):
    mine = reading['propositions']
    review_id = post(BASE + '/interpretation/reviews', dict(
        context_digest=context['digest'], interpretation=reading, candidate_id=candidate['id'],
        resolutions=resolutions(mine, mine, candidate['interpretation']['propositions'], variant),
        residuals_reviewed=True, complete_meaning_reviewed=True))['id']
    preview = get(BASE + '/interpretation/reviews/' + review_id + '/preview')
    return review_id, preview


def continuation(source_root, copy_root, reading, variant):
    """On a scratch copy only: semantic review, preview, preparation if allowed, then the walkthrough."""
    shutil.copytree(source_root / 'workspace', copy_root / 'workspace')
    app, private, _ = setup.open_workspace(copy_root / 'workspace')
    client, actor = _client(app, private)
    with client:
        get = lambda path: setup.checked(client.get(path, headers=actor.headers))
        post = lambda path, body: setup.checked(actor.post(path, body))
        view = get(BASE + '/interpretation')
        context, candidates = view['context'], view.get('candidates') or []
        if not candidates:
            return dict(location=str(copy_root), outcome='NO_CANDIDATE_TO_REVIEW')
        review_id, preview = _review(get, post, context, reading, candidates[0], variant)
        result = dict(location=str(copy_root), authority=SCRIPTED, review_id=review_id,
                      preview=dict(disposition=preview['disposition'], prepare_allowed=preview['prepare_allowed'],
                                   category=preview['assertions']['category'], ledger_unchanged=preview['ledger_unchanged'],
                                   external_actions=preview['external_actions']))
        if not preview['prepare_allowed']:
            result['outcome'] = 'STAYS_WITH_A_PERSON'
            return result
        prepared = post(BASE + '/interpretation/prepare-response', dict(review_id=review_id, preview_digest=preview['digest']))
        result['prepared'] = dict(stage=prepared['stage'], requested_artifact=prepared.get('requested_artifact'))
        clicked = []
        while (workflow := get('/api/workspace/workflow')['workflow'])['next_actions']:
            offer = workflow['next_actions'][0]
            clicked.append(offer['label'])
            post('/api/workspace/workflow/actions/' + offer['id'], {})
        workflow = get('/api/workspace/workflow')['workflow']
        result.update(outcome='WALKTHROUGH_COMPLETED' if workflow['automation']['state'] == 'COMPLETE' else 'STOPPED',
                      clicked=clicked, counts=workflow['automation']['counts'],
                      steps=[(s['operation'], s['authority']['kind']) for s in workflow['automation']['steps']],
                      ledger={k: workflow['ledger'][k] for k in ('claimed', 'awarded', 'posted', 'applied')},
                      bill=dict(original=workflow['ledger']['bill']['original_amount'],
                                outstanding=workflow['ledger']['bill']['outstanding_amount']))
        return result


def run(*, directory, executable, approved_by, origin='http://127.0.0.1:8823', variant='unclear',
        continuation_directory=None, require_clean=True):
    source = source_state(require_clean)  # before anything is written
    root = Path(directory).absolute()
    root.mkdir(mode=0o700, parents=True)
    proposals = root / 'proposals'
    proposals.mkdir(mode=0o700)
    approvals = proposals / 'approvals.json'
    private_json(approvals, dict(version=1, limits=dict(daily_jobs=1, daily_budget_usd='2.00'), approvals=[]))
    config = proposals / 'config.json'
    private_json(config, dict(version=1, executable=str(Path(executable).resolve()), approvals_path=str(approvals),
                              kinds=['correspondence']))
    workspace = root / 'workspace'
    app, private, events = setup.prepare(workspace, origin, routine_automation=True, counterparty_reply=variant)
    client, _ = _client(app, private)
    with client:
        setup.seed(client, app, private, events)
    app, private, _ = setup.open_workspace(workspace, proposal_config=config)
    receipt = dict(schema='role2-denial-model-job/2', recorded_at=datetime.now(UTC).isoformat(), authority=SCRIPTED,
                   variant=variant, source=source, one_call_no_retry=True,
                   counterparty='authored local reply (fixtures/northwind/counterparty-variants.json, variant "' + variant + '")')
    client, actor = _client(app, private)
    with client:
        get = lambda path: setup.checked(client.get(path, headers=actor.headers))
        post = lambda path, body: setup.checked(actor.post(path, body))
        workflow = get('/api/workspace/workflow')['workflow']
        workflow = post('/api/workspace/workflow/actions/' + workflow['next_actions'][0]['id'], {})['workflow']
        receipt['automation_after_person_approval'] = dict(
            pause=workflow['automation']['pause'], steps=[(s['operation'], s['authority']['kind']) for s in workflow['automation']['steps']])
        view = get(BASE + '/interpretation')
        context = view['context']
        text = context['text']
        reading = own_reading(text, variant)
        post(BASE + '/interpretation/blind-entry', dict(context_digest=context['digest'], interpretation=reading))
        view = get(BASE + '/interpretation')
        exported = {k: view['model_job']['approval_request'][k] for k in EXPORT_FIELDS if k in view['model_job']['approval_request']}
        export_path = proposals / 'request-export.json'
        private_json(export_path, exported)
        receipt['request'] = dict(request_sha256=view['model_job']['request_sha256'], request_bytes=view['model_job']['request_bytes'],
                                  context_sha256=context['digest'], text_sha256=context.get('text_sha256'),
                                  status_before_approval=view['model_job']['reason'])
        # The existing operator CLI; it grants one model invocation only (never a review or financial approval).
        command = [sys.executable, str(ROOT / 'scripts' / 'public_proposals.py'), 'approve', str(export_path),
                   '--approvals', str(approvals), '--approved-by', approved_by,
                   '--expected-request-sha256', view['model_job']['request_sha256'], '--confirm-authored-public', '--hours', '1']
        granted = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if granted.returncode != 0:
            raise SystemExit('Operator approval CLI refused: ' + granted.stderr[-500:])
        receipt['approval'] = dict(json.loads(granted.stdout), approved_by=approved_by,
                                   cli='scripts/public_proposals.py approve --confirm-authored-public --hours 1')
        assert get(BASE + '/interpretation')['model_job']['can_request'] is True
        submitted_at = time.monotonic()
        job = post(BASE + '/interpretation/model-jobs', dict(context_digest=context['digest']))
        job_id = job.get('id') or (job.get('job') or {}).get('id')
        polls = []
        while time.monotonic() - submitted_at < 200:
            state = get(BASE + '/interpretation/model-jobs/' + job_id)
            polls.append(state.get('state'))
            if state.get('terminal'):
                break
            time.sleep(1)
        receipt['job'] = dict(id=job_id, final=state, poll_states=sorted(set(polls)), poll_seconds=round(time.monotonic() - submitted_at, 1))
        view = get(BASE + '/interpretation')
        candidates = view.get('candidates') or []
        receipt['candidates'] = [dict(id=c['id'], propositions=[dict(
            family=p['family'], polarity=p['polarity'], modality=p['modality'], referent=p['referent'], cited=p['source']['quote'],
            span=[p['source']['start'], p['source']['end']], artifact_type=p.get('artifact_type'),
            slots={s['name']: s['source']['quote'] for s in p.get('slots', [])},
            conditions=[x['source']['quote'] if isinstance(x.get('source'), dict) else x for x in p.get('conditions', [])])
            for p in c['interpretation']['propositions']],
            provenance={k: c['provenance'].get(k) for k in ('model', 'session', 'request_sha256', 'response_sha256', 'elapsed_seconds',
                                                            'usage', 'client_reported_cost_usd', 'output_mode')}) for c in candidates]
        if variant == 'unclear' and candidates:
            review_id, preview = _review(get, post, context, reading, candidates[0], variant)
            receipt['semantic_review'] = dict(authority=SCRIPTED, review_id=review_id, disposition=preview['disposition'],
                                              prepare_allowed=preview['prepare_allowed'], category=preview['assertions']['category'],
                                              ledger_unchanged=preview['ledger_unchanged'])
        elif variant != 'unclear':
            receipt['stopped_before'] = 'semantic review (so copies can show a reviewer doing it)'
        case = get(BASE)
        workflow = get('/api/workspace/workflow')['workflow']
        receipt['after'] = dict(stage=case['stage'], actions=[a['id'] for a in case['actions']], ledger=case['ledger'],
                                submissions=len(case['submissions']), scope_sha256=fingerprint(case['scope']),
                                automation_pause=workflow['automation']['pause'])
    receipt['provenance'] = provenance(workspace / 'workspace.db', job_id)  # after the job service has closed
    receipt['raw_artifacts_location'] = 'run directory outside Git: ' + str(root)
    if variant != 'unclear':
        copy_root = Path(continuation_directory or root.parent / (root.name + '-continuation')).absolute()
        copy_root.mkdir(mode=0o700, parents=True)
        receipt['continuation'] = continuation(root, copy_root, reading, variant)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path, help='Fresh absolute directory outside the repository')
    parser.add_argument('--executable', required=True, type=Path, help='Absolute Claude Code executable')
    parser.add_argument('--approved-by', required=True, help='Truthful identity of the operator approving one invocation')
    parser.add_argument('--receipt', required=True, type=Path, help='New receipt file to create')
    parser.add_argument('--origin', default='http://127.0.0.1:8823')
    parser.add_argument('--variant', choices=VARIANTS, default='unclear')
    parser.add_argument('--continuation-directory', type=Path,
                        help='Scratch copy for the review and walkthrough (default: <directory>-continuation)')
    args = parser.parse_args()
    receipt = run(directory=args.directory, executable=args.executable, approved_by=args.approved_by, origin=args.origin,
                  variant=args.variant, continuation_directory=args.continuation_directory)
    private_json(args.receipt, receipt)
    print(json.dumps(dict(receipt=str(args.receipt), job=receipt['job']['final'].get('state'), candidates=len(receipt['candidates']),
                          stage=receipt['after']['stage'], continuation=(receipt.get('continuation') or {}).get('outcome'))))


if __name__ == '__main__':
    main()
