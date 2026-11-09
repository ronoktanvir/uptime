"""Role 2: routine walkthrough steps run under existing authority; person decisions and pauses stay.

The Northwind package, its counterparty replies and the reviewer are authored and scripted
(SCRIPTED_REVIEWER). Intake of the authored replies is not evidence of a real vendor channel.
"""
from fastapi.testclient import TestClient
import pytest

from scripts import setup_northwind as setup
from uptime import workflow_coordinator as coordinator
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.contracts import Principal

PERSON = ['Approve January claim', 'Approve response', 'Post to Local ledger', 'Apply credit to eligible invoice']
UNFAMILIAR = ('Our records do not line up with the window you describe, so we are not in a position to '
              'honour this request as filed.')


def world(directory):
    app, private, events = setup.prepare(directory, DEFAULT_ORIGIN, routine_automation=True)
    client = TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234), raise_server_exceptions=False)
    actor, _ = setup.seed(client, app, private, events)
    return app, client, actor


def reopen(directory):
    app, private, _ = setup.open_workspace(directory)
    client = TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234), raise_server_exceptions=False)
    from uptime.auth_client import ReviewerClient
    return app, client, ReviewerClient(client, private['origin'], SCRIPT, private['rehearsal_secret'])


def read(client, actor):
    return setup.checked(client.get('/api/workspace/workflow', headers=actor.headers))['workflow']


def act(client, actor, identity):
    return setup.checked(actor.post('/api/workspace/workflow/actions/' + identity, {}))['workflow']


def case(app):
    return app.state.bench.case(Principal('bears', SCRIPT, 'reviewer'), 'inbox-northwind-2026-01')


def test_routine_steps_run_under_existing_authority_and_only_person_decisions_are_offered(tmp_path):
    app, client, actor = world(tmp_path / 'auto')
    try:
        start = read(client, actor)
        assert start['automation']['enabled'] and start['automation']['pause']['reason'] == 'APPROVAL_REQUIRED'
        clicked = []
        while (view := read(client, actor))['next_actions']:
            offer = view['next_actions'][0]
            clicked.append(offer['label'])
            assert read(client, actor) == view  # a read never advances anything
            act(client, actor, offer['id'])
        assert clicked == PERSON
        final = read(client, actor)
        automation = final['automation']
        assert automation['state'] == 'COMPLETE' and automation['pause'] is None
        assert automation['counts'] == dict(person_decisions=4, automatic_steps=7)
        assert [s['operation'] for s in automation['steps']] == [
            'approve-claim', 'submit-claim', 'receive-denial', 'receive-artifact', 'receive-verification',
            'approve-response', 'submit-response', 'receive-award', 'record-credit', 'receive-invoice', 'apply-balance']
        for step in automation['steps']:
            assert step['state'] == 'COMPLETED' and step['class'] == coordinator.CLASSES[step['operation']]
            kind = step['authority']['kind']
            if step['class'] in {'APPROVAL', 'FINANCIAL_MUTATION'}:
                assert step['authority'] == dict(kind='PERSON', actor=SCRIPT)
            elif step['class'] == 'DELIVERY':
                assert kind == 'APPROVED_OPERATION' and step['authority']['actor'] == SCRIPT
                assert step['authority']['approval_action'] == coordinator.DISPATCH_APPROVAL[step['operation']]
                assert len(step['authority']['approval_digest']) == 64
            else:
                assert kind == 'EVENT_INTAKE' and step['authority']['event_id'] and step['authority']['source_subject']
        ledger = final['ledger']
        assert ledger['claimed'] == ledger['awarded'] == ledger['posted'] == ledger['applied'] == '2400.00'
        assert ledger['bill']['month'] == '2026-04' and final['price_finding']['month'] == '2026-03'
        claim = case(app)
        first, second = claim['submissions']
        assert second['packet']['in_reply_to'] == first['id']  # original filing lineage
        assert second['packet']['filing_cutoff'] == first['packet']['filing_cutoff']
        sent = next(s for s in automation['steps'] if s['operation'] == 'submit-response')
        responded = next(s for s in automation['steps'] if s['operation'] == 'approve-response')
        assert sent['at'] >= responded['at']  # never before the response cooldown
        assert second['at'] >= claim['timeline'][0]['at']
    finally:
        client.close()


def test_duplicate_posts_and_reloads_never_duplicate_claims_responses_or_allocations(tmp_path):
    app, client, actor = world(tmp_path / 'dup')
    try:
        first = read(client, actor)['next_actions'][0]['id']
        after = act(client, actor, first)
        again = act(client, actor, first)  # the reviewer's click is repeated
        assert again['automation']['steps'] == after['automation']['steps']
        assert len(case(app)['submissions']) == 1
        assert setup.checked(actor.post('/api/workspace/workflow/actions/continue', {}))['workflow'] == after
        while (view := read(client, actor))['next_actions']:
            act(client, actor, view['next_actions'][0]['id'])
        done = read(client, actor)
        assert act(client, actor, first) == done
        assert len(case(app)['submissions']) == 2 and done['ledger']['applied'] == '2400.00'
        assert done['automation']['counts'] == dict(person_decisions=4, automatic_steps=7)
    finally:
        client.close()


def test_interrupted_automatic_step_stays_uncertain_across_restart_until_a_person_reconciles_it(tmp_path):
    directory = tmp_path / 'interrupt'
    app, client, actor = world(directory)
    workflow = app.state.workflow
    original, fired = workflow._run, []

    async def interrupt_first_automatic(p, identity, *, person):
        if not person and not fired:
            fired.append(identity)
            workflow.failure_point = 'after-effect'
        try:
            return await original(p, identity, person=person)
        finally:
            workflow.failure_point = None

    workflow._run = interrupt_first_automatic
    try:
        view = act(client, actor, read(client, actor)['next_actions'][0]['id'])
        assert view['automation']['pause']['reason'] == 'UNCERTAIN_DELIVERY'
        assert view['next_actions'] == [dict(id=fired[0], label='Resume interrupted action', group='claim')]
        assert [s['state'] for s in view['automation']['steps']] == ['COMPLETED', 'FAILED']
        assert len(case(app)['submissions']) == 1  # the filing happened once; confirmation did not
    finally:
        client.close()
    app, client, actor = reopen(directory)  # process restart
    try:
        restarted = read(client, actor)
        assert restarted['automation']['pause']['reason'] == 'UNCERTAIN_DELIVERY'
        assert restarted['next_actions'][0]['label'] == 'Resume interrupted action'
        resumed = act(client, actor, restarted['next_actions'][0]['id'])
        assert len(case(app)['submissions']) == 1  # reconciled by read-back, not filed again
        assert resumed['automation']['pause']['reason'] == 'APPROVAL_REQUIRED'
        assert resumed['next_actions'][0]['label'] == 'Approve response'
        resume_step = next(s for s in resumed['automation']['steps'] if s['authority'].get('resumed'))
        assert resume_step['operation'] == 'submit-claim' and resume_step['authority']['actor'] == SCRIPT
    finally:
        client.close()


def test_an_unfamiliar_vendor_reply_pauses_for_the_reviewer_instead_of_continuing(tmp_path):
    app, client, actor = world(tmp_path / 'unclear')
    app.state.workflow.correspondence['denial']['text'] = UNFAMILIAR
    try:
        view = act(client, actor, read(client, actor)['next_actions'][0]['id'])
        assert view['automation']['pause']['reason'] == 'UNEXPECTED_GROUND' and view['next_actions'] == []
        assert [s['operation'] for s in view['automation']['steps']] == ['approve-claim', 'submit-claim', 'receive-denial']
        claim = case(app)
        assert claim['stage'] == 'HUMAN_REVIEW' and claim['replies'][-1]['reason'] == 'unknown'
        assert claim['ledger']['awarded'] == '0.00' and len(claim['submissions']) == 1
        assert setup.checked(actor.post('/api/workspace/workflow/actions/continue', {}))['workflow'] == view
    finally:
        client.close()


@pytest.mark.parametrize('claim,expected', [
    (dict(stage='DENIAL_REVIEW', replies=[], contradicting_deliveries=[]), 'JUDGMENT_REQUIRED'),
    (dict(stage='HUMAN_REVIEW', replies=[dict(reason='unknown')], contradicting_deliveries=[]), 'UNEXPECTED_GROUND'),
    (dict(stage='HUMAN_REVIEW', replies=[dict(reason='component')], contradicting_deliveries=[]), 'CONTRADICTORY_EVIDENCE'),
    (dict(stage='AWAITING_VENDOR', replies=[], contradicting_deliveries=[dict(blocking=True)]), 'CONTRADICTORY_EVIDENCE'),
])
def test_judgment_ground_and_contradiction_pause_before_any_routine_step(tmp_path, claim, expected):
    app, client, actor = world(tmp_path / 'pause')
    try:
        p = Principal('bears', SCRIPT, 'reviewer')
        reason, _ = coordinator.pause(app.state.workflow, p, claim, dict(operation='submit-claim'))
        assert reason == expected
    finally:
        client.close()


def test_dispatch_without_a_matching_approval_and_observe_mode_have_no_authority(tmp_path):
    app, client, actor = world(tmp_path / 'authority')
    try:
        p = Principal('bears', SCRIPT, 'reviewer')
        claim = dict(stage='CLAIM_APPROVED', replies=[], contradicting_deliveries=[], approval=dict(action='approve-response'))
        assert coordinator.pause(app.state.workflow, p, claim, dict(operation='submit-claim'))[0] == 'MISSING_AUTHORITY'
        setup.checked(actor.post('/api/policy', dict(mode='OBSERVE', cap='0.00')))
        assert coordinator.pause(app.state.workflow, p, None, None)[0] == 'MISSING_AUTHORITY'
        assert read(client, actor)['next_actions'] == []
    finally:
        client.close()


def test_step_history_is_append_only(tmp_path):
    import sqlite3
    app, client, actor = world(tmp_path / 'append')
    try:
        act(client, actor, read(client, actor)['next_actions'][0]['id'])
        from uptime.storage import database
        with database(app.state.bench.path) as db:
            with pytest.raises(sqlite3.DatabaseError):
                db.execute("UPDATE workspace_workflow_step SET state='COMPLETED'")
            with pytest.raises(sqlite3.DatabaseError):
                db.execute('DELETE FROM workspace_workflow_step')
    finally:
        client.close()


def test_dispatch_happens_on_the_workspace_timeline_at_the_cooldown_and_inside_the_cutoff(tmp_path):
    app, client, actor = world(tmp_path / 'timeline')
    try:
        while (view := read(client, actor))['next_actions']:
            act(client, actor, view['next_actions'][0]['id'])
        steps = {s['operation']: s for s in read(client, actor)['automation']['steps']}
        filed, sent = steps['submit-claim']['timing'], steps['submit-response']['timing']
        assert filed['clock'] == sent['clock'] == 'WORKSPACE'
        assert filed['at'] < filed['filing_cutoff']
        # Sent exactly when the 24-hour cooldown ends on the workspace's own timeline, never earlier.
        assert sent['at'] == sent['not_before'] and sent['at'] < sent['filing_cutoff']
        assert steps['submit-response']['at'] == sent['at']
        assert steps['approve-response']['timing']['at'] < sent['not_before']
    finally:
        client.close()


def test_setup_prints_a_plain_sign_in_block_and_writes_a_visible_protected_copy(tmp_path):
    import json
    import os
    import stat
    import subprocess
    import sys
    script = setup.ROOT / 'scripts' / 'setup_northwind.py'
    directory, copy, again = tmp_path / 'ws', tmp_path / 'visible' / 'reviewer.jwk', tmp_path / 'visible' / 'again.jwk'
    copy.parent.mkdir()
    run = lambda *extra: subprocess.run([sys.executable, str(script), '--directory', str(directory), *extra],
                                        capture_output=True, text=True, timeout=300, cwd=setup.ROOT)
    created = run('--reviewer-credential', str(copy))
    assert created.returncode == 0, created.stderr[-2000:]
    printed = json.loads(created.stdout.strip().splitlines()[-1])
    assert printed['reviewer_credential_file'] == str(copy) and printed['routine_automation'] is True
    origin = printed['origin']
    assert created.stderr.strip().splitlines()[-3:] == [str(copy), SCRIPT, origin]
    assert stat.S_IMODE(os.stat(copy).st_mode) == 0o600
    key = json.loads(copy.read_text())
    assert key['d'] not in created.stdout + created.stderr  # never the key material, only its path
    assert copy.read_text() == (directory / 'scripted-reviewer.jwk').read_text()
    resumed = run('--resume', '--reviewer-credential', str(again))
    assert resumed.returncode == 0, resumed.stderr[-2000:]
    assert again.read_text() == copy.read_text() and resumed.stderr.strip().splitlines()[-3:] == [str(again), SCRIPT, origin]
    plain = run('--resume')
    assert plain.stderr.strip().splitlines()[-3:] == [str(directory / 'scripted-reviewer.jwk'), SCRIPT, origin]


def _setup(directory, *extra):
    import subprocess
    import sys
    script = setup.ROOT / 'scripts' / 'setup_northwind.py'
    return subprocess.run([sys.executable, str(script), '--directory', str(directory), *extra],
                          capture_output=True, text=True, timeout=300, cwd=setup.ROOT)


def test_resume_reuses_an_identical_credential_and_refuses_a_different_one_without_overwriting(tmp_path):
    import os
    directory, visible = tmp_path / 'ws', tmp_path / 'visible-reviewer.jwk'
    first = _setup(directory, '--reviewer-credential', str(visible))
    assert first.returncode == 0, first.stderr[-2000:]
    before = (visible.read_bytes(), os.stat(visible).st_mtime_ns)
    for _ in range(2):  # the documented resume command, re-run
        again = _setup(directory, '--resume', '--reviewer-credential', str(visible))
        assert again.returncode == 0 and 'Traceback' not in again.stderr, again.stderr[-2000:]
        assert '"reviewer_credential_copy": "REUSED"' in again.stdout
        assert again.stderr.strip().splitlines()[-2:-1] == [SCRIPT]
        assert (visible.read_bytes(), os.stat(visible).st_mtime_ns) == before
    other = tmp_path / 'other.jwk'
    other.write_text('{"kty":"EC","note":"someone else"}\n')
    os.chmod(other, 0o600)
    refused = _setup(directory, '--resume', '--reviewer-credential', str(other))
    assert refused.returncode == 1 and 'Traceback' not in refused.stderr
    assert refused.stderr.strip().splitlines() == [
        'setup_northwind: A different file already exists at ' + str(other) + '; choose another path. Nothing was overwritten.']
    assert other.read_text() == '{"kty":"EC","note":"someone else"}\n'


@pytest.mark.parametrize('where', ['existing', 'repository', 'missing-folder'])
def test_a_refused_credential_path_leaves_no_half_created_workspace(tmp_path, where):
    directory = tmp_path / 'ws'
    if where == 'existing':
        target = tmp_path / 'taken.jwk'
        target.write_text('occupied\n')
    elif where == 'repository':
        target = setup.ROOT / 'never-written-reviewer.jwk'
    else:
        target = tmp_path / 'no-such-folder' / 'reviewer.jwk'
    refused = _setup(directory, '--reviewer-credential', str(target))
    assert refused.returncode == 1 and 'Traceback' not in refused.stderr, refused.stderr[-2000:]
    assert len(refused.stderr.strip().splitlines()) == 1 and refused.stderr.startswith('setup_northwind: ')
    assert not directory.exists()
    if where == 'existing':
        assert target.read_text() == 'occupied\n'
    else:
        assert not target.exists()


def test_a_stale_approval_binding_is_never_dispatched(tmp_path):
    app, client, actor = world(tmp_path / 'stale')
    workflow = app.state.workflow
    try:
        workflow.automation = False  # approve without letting the coordinator run in the same request
        act(client, actor, read(client, actor)['next_actions'][0]['id'])
        workflow.automation = True
        assert case(app)['stage'] == 'CLAIM_APPROVED' and case(app)['approval']['action'] == 'approve-claim'
        # The governing binding changes after approval; the approved packet is no longer current.
        desk = app.state.bench.inbox
        original = desk._approval_binding
        desk._approval_binding = lambda current: [original(current), 'changed-after-approval']
        view = setup.checked(actor.post('/api/workspace/workflow/actions/continue', {}))['workflow']
        assert case(app)['submissions'] == []  # nothing was filed under the stale approval
        assert view['automation']['pause']['reason'] == 'APPROVAL_REQUIRED'
        assert view['next_actions'][0]['label'] == 'Approve January claim'
        assert [s['operation'] for s in view['automation']['steps']] == ['approve-claim']
    finally:
        client.close()


def test_a_workspace_recorded_before_step_timing_opens_without_losing_history(tmp_path):
    import sqlite3
    from uptime.storage import database
    path = tmp_path / 'recorded.db'
    with database(path) as db, db:
        db.execute('''CREATE TABLE workspace_workflow_step (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, operation TEXT NOT NULL, class TEXT NOT NULL,
            authority TEXT NOT NULL, state TEXT NOT NULL, at TEXT NOT NULL, recorded_at TEXT NOT NULL,
            intent_id TEXT, detail TEXT)''')
        db.execute("CREATE TRIGGER workflow_step_no_update BEFORE UPDATE ON workspace_workflow_step "
                   "BEGIN SELECT RAISE(ABORT,'Workflow step history is append-only'); END")
        db.execute("INSERT INTO workspace_workflow_step(operation,class,authority,state,at,recorded_at) "
                   "VALUES('approve-claim','APPROVAL','{\"actor\": \"x\", \"kind\": \"PERSON\"}','COMPLETED','t','r')")
    coordinator.setup(path)
    coordinator.setup(path)  # idempotent
    with database(path) as db:
        rows = db.execute('SELECT operation,timing FROM workspace_workflow_step').fetchall()
        assert [tuple(r) for r in rows] == [('approve-claim', None)]
        with pytest.raises(sqlite3.DatabaseError):
            db.execute("UPDATE workspace_workflow_step SET state='X'")
