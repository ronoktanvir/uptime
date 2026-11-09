"""Resumable coordinator for walkthrough steps that already have authority (role 2, D06).

It creates no authority. It executes only:
- intake of configured source events through the ordinary signed source route; and
- dispatch of an operation a person already approved, bound to that approval's recorded
  actor and digest.

It stops with a typed pause at every person decision (approvals, judgment and financial
mutations), at an uncertain delivery, contradictory evidence, an unexpected ground, or
missing authority. There is no timer or scheduler: it runs inside the signed reviewer
request that completed a person decision, or on an explicit reviewer "continue" after an
interruption. Every executed step goes through the workflow's exact-intent machinery
(pin, expected effect, read-back) and is recorded in an append-only table that the view
projects. Progress is never inferred by a client.
"""
import json
from datetime import UTC, datetime

from .correspondence_types import SOURCE
from .storage import database

CLASSES = {'approve-claim': 'APPROVAL', 'approve-response': 'APPROVAL',
           'submit-claim': 'DELIVERY', 'submit-response': 'DELIVERY',
           'receive-denial': 'INTAKE', 'receive-artifact': 'INTAKE', 'receive-verification': 'INTAKE',
           'receive-award': 'INTAKE', 'receive-invoice': 'INTAKE',
           'record-credit': 'FINANCIAL_MUTATION', 'apply-balance': 'FINANCIAL_MUTATION'}
ROUTINE = frozenset(op for op, kind in CLASSES.items() if kind in {'DELIVERY', 'INTAKE'})
DISPATCH_APPROVAL = {'submit-claim': 'approve-claim', 'submit-response': 'approve-response'}
CONTINUE = 'continue'
MAX_STEPS = 16
PAUSES = ('APPROVAL_REQUIRED', 'FINANCIAL_APPROVAL_REQUIRED', 'JUDGMENT_REQUIRED', 'UNEXPECTED_GROUND',
          'CONTRADICTORY_EVIDENCE', 'MISSING_AUTHORITY', 'UNCERTAIN_DELIVERY', 'ROUTINE_READY', 'WAITING')


def setup(path):
    with database(path) as db, db:
        db.execute('''CREATE TABLE IF NOT EXISTS workspace_workflow_step (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT NOT NULL, class TEXT NOT NULL,
            authority TEXT NOT NULL, state TEXT NOT NULL, at TEXT NOT NULL, recorded_at TEXT NOT NULL,
            intent_id TEXT, detail TEXT)''')
        for operation in ('UPDATE', 'DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS workflow_step_no_{operation.lower()} BEFORE {operation} "
                       "ON workspace_workflow_step BEGIN SELECT RAISE(ABORT,'Workflow step history is append-only'); END")


def record(workflow, operation, authority, state, intent_id=None, detail=None):
    with database(workflow.bench.path) as db, db:
        db.execute('INSERT INTO workspace_workflow_step(operation,class,authority,state,at,recorded_at,intent_id,detail) '
                   'VALUES(?,?,?,?,?,?,?,?)',
                   (operation, CLASSES.get(operation, 'UNKNOWN'), json.dumps(authority, sort_keys=True), state,
                    workflow.now().isoformat(), datetime.now(UTC).isoformat(), intent_id, detail))


def authority(workflow, p, claim, operation, effect, *, person):
    """Who or what authorizes this exact step; read before it executes."""
    if person:
        return dict(kind='PERSON', actor=p.subject)
    if operation in DISPATCH_APPROVAL:
        approval = claim['approval'] or {}
        return dict(kind='APPROVED_OPERATION', actor=approval.get('actor'), approval_action=approval.get('action'),
                    approval_digest=approval.get('digest'), approved_at=approval.get('at'))
    if operation == 'receive-invoice':
        return dict(kind='EVENT_INTAKE', event_id='invoice-' + workflow.bill_id,
                    source_subject=workflow.senders[(workflow.settlement['month'], 'billing')].subject,
                    source_sha256=effect['source_sha256'])
    event = effect['event']
    sender = workflow.senders[(event['scope']['month'], SOURCE[event['body']['kind']])]
    return dict(kind='EVENT_INTAKE', event_id=event['event_id'], source_subject=sender.subject)


def pause(workflow, p, claim, descriptor):
    """The typed reason this coordinator must not act now, or None when the next step is routine and authorized."""
    with database(workflow.bench.path) as db:
        executing = db.execute("SELECT operation FROM workspace_workflow_intent WHERE status='EXECUTING' "
                               "ORDER BY rowid LIMIT 1").fetchone()
    if executing:
        return ('UNCERTAIN_DELIVERY', executing['operation'] + ' started but its result is not confirmed. '
                'Resume reconciles it by exact read-back before anything else runs.')
    if workflow.bench.setting(p)['mode'] == 'OBSERVE':
        return 'MISSING_AUTHORITY', 'The workspace is in observe-only mode.'
    if claim:
        if any(row.get('blocking') for row in claim.get('contradicting_deliveries') or []):
            return 'CONTRADICTORY_EVIDENCE', 'A source sent a record that contradicts this claim; a person must review it.'
        if claim['stage'] == 'DENIAL_REVIEW':
            return 'JUDGMENT_REQUIRED', 'The vendor denial is substantiated; accepting it is a reviewer decision.'
        if claim['stage'] == 'HUMAN_REVIEW':
            last = (claim.get('replies') or [{}])[-1].get('reason')
            if last in {'unknown', 'contradictory_correspondence'}:
                return 'UNEXPECTED_GROUND', 'The vendor reply needs the reviewer\'s reading and semantic review.'
            return 'CONTRADICTORY_EVIDENCE', 'Later evidence no longer supports the next step; a person must review it.'
    if descriptor is None:
        return None
    operation = descriptor['operation']
    if operation in {'approve-claim', 'approve-response'}:
        return 'APPROVAL_REQUIRED', 'A reviewer approves the exact packet.'
    if operation in {'record-credit', 'apply-balance'}:
        return 'FINANCIAL_APPROVAL_REQUIRED', 'A reviewer approves this financial change.'
    if operation in DISPATCH_APPROVAL:
        approval = claim['approval'] if claim else None
        if not approval or approval.get('action') != DISPATCH_APPROVAL[operation]:
            return 'MISSING_AUTHORITY', 'No current approval binds this dispatch.'
    if operation not in ROUTINE:
        return 'MISSING_AUTHORITY', 'This step has no recorded authority for automatic execution.'
    return None


async def advance(workflow, p):
    """Run routine, authorized steps until a pause. Errors stop the run; they never retry."""
    for _ in range(MAX_STEPS):
        claim = workflow._claim(p)
        descriptor = workflow._descriptor(p, claim)
        if descriptor is None or pause(workflow, p, claim, descriptor) is not None:
            return
        try:
            await workflow._run(p, descriptor['id'], person=False)
        except Exception as error:  # recorded once; an EXECUTING intent pauses as UNCERTAIN_DELIVERY
            record(workflow, descriptor['operation'], dict(kind='COORDINATOR'), 'FAILED',
                   detail=type(error).__name__ + ': ' + str(error)[:300])
            return


def steps(workflow):
    with database(workflow.bench.path) as db:
        rows = db.execute('SELECT * FROM workspace_workflow_step ORDER BY seq').fetchall()
    return [dict(seq=row['seq'], operation=row['operation'], label=workflow.labels.get(row['operation'], row['operation']),
                 **{'class': row['class']}, authority=json.loads(row['authority']), state=row['state'], at=row['at'],
                 recorded_at=row['recorded_at'], intent_id=row['intent_id'], detail=row['detail']) for row in rows]


def view(workflow, p, claim):
    rows = steps(workflow)
    if not workflow.automation:
        return dict(enabled=False, state=None, pause=None, steps=rows,
                    counts=dict(person_decisions=sum(r['authority'].get('kind') == 'PERSON' for r in rows),
                                automatic_steps=0))
    descriptor = workflow._descriptor(p, claim)
    reason = pause(workflow, p, claim, descriptor)
    if reason is None and descriptor is None:
        done = bool(claim and claim['ledger']['applied'] != '0.00')
        state, reason = ('COMPLETE', None) if done else ('PAUSED', ('WAITING', 'No further step is available yet.'))
    elif reason is None:
        state, reason = 'PAUSED', ('ROUTINE_READY', 'Routine steps are ready; continue to run them.')
    else:
        state = 'PAUSED'
    since = rows[-1]['at'] if rows else None
    return dict(enabled=True, state=state,
                pause=None if reason is None else dict(reason=reason[0], detail=reason[1],
                                                       operation=descriptor['operation'] if descriptor else None, since=since),
                steps=rows,
                counts=dict(person_decisions=sum(r['authority'].get('kind') == 'PERSON' for r in rows),
                            automatic_steps=sum(r['authority'].get('kind') in {'APPROVED_OPERATION', 'EVENT_INTAKE'}
                                                and r['state'] == 'COMPLETED' for r in rows)))
