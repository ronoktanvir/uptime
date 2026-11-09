#!/usr/bin/env python3
"""Role 2: one genuine model job on an authored unfamiliar vendor denial (escalation branch).

A fresh Northwind workspace receives the authored "unclear" January reply. The scripted reviewer
(SCRIPTED_NOT_ACTUAL_HUMAN) saves its own reading first, as decision 60/75 requires. One exact,
authored-public request is approved for a single model invocation with scripts/public_proposals.py,
submitted once through the ordinary signed model-job route, and never retried. The proposed
reading is recorded before the scripted semantic review. The model changes no claim state, money
or scope. Raw request and response stay in the workspace directory, outside Git; the receipt
written to --receipt holds digests, identities, states and the proposed reading of the public text.
"""
import argparse
from datetime import UTC, datetime
import json
import os
import subprocess
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import setup_northwind as setup  # noqa: E402
from uptime.auth import SCRIPT  # noqa: E402
from uptime.contracts import fingerprint  # noqa: E402

CLAIM = 'inbox-northwind-2026-01'
SCRIPTED = 'SCRIPTED_NOT_ACTUAL_HUMAN'
EXPORT_FIELDS = ('tenant', 'subject', 'kind', 'target', 'context_sha256', 'request', 'source_references')


def private_json(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write('\n')


def own_reading(text):
    """The scripted reviewer's source-only reading: no recognized ground the system can act on."""
    whole = dict(start=0, end=len(text.encode()), quote=text)
    return dict(propositions=[dict(family='unsupported', source=whole, polarity='positive', modality='asserted',
                                   referent='current_claim', conditions=[], slots=[], artifact_type=None,
                                   scope_field=None, filing_fields=[])],
                segments=[dict(source=whole, role='substantive')])


def resolutions(mine, blind, candidate):
    rows = []
    count = max(len(mine), len(blind), len(candidate))
    for i in range(count):
        if i >= len(mine):
            rows.append(dict(proposition=i, verdict='reject', explanation=(
                'Scripted review: the model proposed an additional meaning that the reviewer does not adopt.')))
        elif all(i < len(other) and other[i] == mine[i] for other in (blind, candidate)):
            rows.append(dict(proposition=i, verdict='accept', explanation=(
                'Scripted review: the reading matches the reviewer\'s own reading and the model proposal.')))
        else:
            rows.append(dict(proposition=i, verdict='correct', explanation=(
                'Scripted review: settlement at renewal and a disputed period are not grounds the system may act '
                'on; the case stays with a person.')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path, help='Fresh absolute directory outside the repository')
    parser.add_argument('--executable', required=True, type=Path, help='Absolute Claude Code executable')
    parser.add_argument('--approved-by', required=True, help='Truthful identity of the operator approving one invocation')
    parser.add_argument('--receipt', required=True, type=Path, help='New receipt file to create')
    parser.add_argument('--origin', default='http://127.0.0.1:8823')
    args = parser.parse_args()
    root = args.directory.absolute()
    root.mkdir(mode=0o700, parents=True)
    proposals = root / 'proposals'
    proposals.mkdir(mode=0o700)
    approvals = proposals / 'approvals.json'
    private_json(approvals, dict(version=1, limits=dict(daily_jobs=1, daily_budget_usd='2.00'), approvals=[]))
    config = proposals / 'config.json'
    private_json(config, dict(version=1, executable=str(args.executable.resolve()), approvals_path=str(approvals),
                              kinds=['correspondence']))
    workspace = root / 'workspace'
    app, private, events = setup.prepare(workspace, args.origin, routine_automation=True, counterparty_reply='unclear')
    from fastapi.testclient import TestClient
    with TestClient(app, base_url=private['origin'], client=('127.0.0.1', 4510)) as client:
        setup.seed(client, app, private, events)
    app, private, _ = setup.open_workspace(workspace, proposal_config=config)
    from uptime.auth_client import ReviewerClient
    receipt = dict(schema='role2-denial-model-job/1', recorded_at=datetime.now(UTC).isoformat(), authority=SCRIPTED,
                   counterparty='authored local reply (fixtures/northwind/counterparty-variants.json, variant "unclear")',
                   one_call_no_retry=True)
    with TestClient(app, base_url=private['origin'], client=('127.0.0.1', 4510)) as client:
        actor = ReviewerClient(client, private['origin'], SCRIPT, private['rehearsal_secret'])
        get = lambda path: setup.checked(client.get(path, headers=actor.headers))
        post = lambda path, body: setup.checked(actor.post(path, body))
        workflow = get('/api/workspace/workflow')['workflow']
        workflow = post('/api/workspace/workflow/actions/' + workflow['next_actions'][0]['id'], {})['workflow']
        receipt['automation_after_person_approval'] = dict(
            pause=workflow['automation']['pause'], steps=[(s['operation'], s['authority']['kind']) for s in workflow['automation']['steps']])
        base = '/api/correspondence/claims/' + CLAIM + '/interpretation'
        view = get(base)
        context = view['context']
        text = context['text']
        reading = own_reading(text)
        post(base + '/blind-entry', dict(context_digest=context['digest'], interpretation=reading))
        view = get(base)
        exported = {k: view['model_job']['approval_request'][k] for k in EXPORT_FIELDS if k in view['model_job']['approval_request']}
        export_path = proposals / 'request-export.json'
        private_json(export_path, exported)
        receipt['request'] = dict(request_sha256=view['model_job']['request_sha256'], request_bytes=view['model_job']['request_bytes'],
                                  context_sha256=context['digest'], text_sha256=context.get('text_sha256'),
                                  status_before_approval=view['model_job']['reason'])
        # The existing operator CLI; it grants one model invocation only (never a review or financial approval).
        command = [sys.executable, str(Path(__file__).resolve().parent / 'public_proposals.py'), 'approve', str(export_path),
                   '--approvals', str(approvals), '--approved-by', args.approved_by,
                   '--expected-request-sha256', view['model_job']['request_sha256'], '--confirm-authored-public', '--hours', '1']
        granted = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if granted.returncode != 0:
            raise SystemExit('Operator approval CLI refused: ' + granted.stderr[-500:])
        receipt['approval'] = dict(json.loads(granted.stdout), approved_by=args.approved_by,
                                   cli='scripts/public_proposals.py approve --confirm-authored-public --hours 1')
        assert get(base)['model_job']['can_request'] is True
        submitted_at = time.monotonic()
        job = post(base + '/model-jobs', dict(context_digest=context['digest']))
        job_id = job.get('id') or (job.get('job') or {}).get('id')
        polls = []
        while time.monotonic() - submitted_at < 200:
            state = get(base + '/model-jobs/' + job_id)
            polls.append(state.get('state'))
            if state.get('terminal'):
                break
            time.sleep(1)
        receipt['job'] = dict(id=job_id, final=state, poll_states=sorted(set(polls)), poll_seconds=round(time.monotonic() - submitted_at, 1))
        view = get(base)
        candidates = view.get('candidates') or []
        receipt['candidates'] = [dict(id=c['id'], propositions=[dict(family=p['family'], polarity=p['polarity'],
                                       modality=p['modality'], referent=p['referent'], cited=p['source']['quote'],
                                       span=[p['source']['start'], p['source']['end']],
                                       conditions=[x['source']['quote'] if isinstance(x.get('source'), dict) else x for x in p.get('conditions', [])])
                                       for p in c['interpretation']['propositions']],
                                  provenance={k: c['provenance'].get(k) for k in (
                                      'model', 'session', 'request_sha256', 'response_sha256', 'elapsed_seconds',
                                      'usage', 'client_reported_cost_usd', 'output_mode')}) for c in candidates]
        if candidates:
            candidate = candidates[0]
            mine = reading['propositions']
            review_id = post(base + '/reviews', dict(
                context_digest=context['digest'], interpretation=reading, candidate_id=candidate['id'],
                resolutions=resolutions(mine, mine, candidate['interpretation']['propositions']),
                residuals_reviewed=True, complete_meaning_reviewed=True))['id']
            preview = get(base + '/reviews/' + review_id + '/preview')
            receipt['semantic_review'] = dict(authority=SCRIPTED, review_id=review_id, disposition=preview['disposition'],
                                              prepare_allowed=preview['prepare_allowed'], category=preview['assertions']['category'],
                                              ledger_unchanged=preview['ledger_unchanged'])
        case = get('/api/correspondence/claims/' + CLAIM)
        workflow = get('/api/workspace/workflow')['workflow']
        receipt['after'] = dict(stage=case['stage'], actions=[a['id'] for a in case['actions']], ledger=case['ledger'],
                                submissions=len(case['submissions']), scope_sha256=fingerprint(case['scope']),
                                automation_pause=workflow['automation']['pause'])
    receipt['raw_artifacts_location'] = 'workspace directory outside Git: ' + str(root)
    private_json(args.receipt, receipt)
    print(json.dumps(dict(receipt=str(args.receipt), job=receipt['job']['final'].get('state'),
                          candidates=len(receipt['candidates']), stage=receipt['after']['stage'])))


if __name__ == '__main__':
    main()
