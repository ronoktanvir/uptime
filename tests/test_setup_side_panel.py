"""The walkthrough setup passes the side-panel framing option to the served app only.

It is a serving option: validated before anything is written, never stored in the
workspace and never part of the workspace digest. No browser is used.
"""
import json
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from scripts import setup_northwind as setup
from uptime.auth import DEFAULT_ORIGIN, SCRIPT
from uptime.auth_client import ReviewerClient

PANEL = 'chrome-extension://' + 'abcdefghijklmnop' * 2
PERSON = ['Approve January claim', 'Approve response', 'Post to Local ledger', 'Apply credit to eligible invoice']


def frame_ancestors(app):
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1', 1234)) as client:
        policy = client.get('/api/workspace/workflow').headers['content-security-policy']
    return policy.split('frame-ancestors ', 1)[1].split(';', 1)[0].strip()


def cli(directory, *extra):
    script = setup.ROOT / 'scripts' / 'setup_northwind.py'
    return subprocess.run([sys.executable, str(script), '--directory', str(directory), *extra],
                          capture_output=True, text=True, timeout=300, cwd=setup.ROOT)


def walk(app, private):
    with TestClient(app, base_url=private['origin'], client=('127.0.0.1', 1234), raise_server_exceptions=False) as client:
        actor = ReviewerClient(client, private['origin'], SCRIPT, private['rehearsal_secret'])
        read = lambda: setup.checked(client.get('/api/workspace/workflow', headers=actor.headers))['workflow']
        clicked = []
        while (view := read())['next_actions']:
            clicked.append(view['next_actions'][0]['label'])
            setup.checked(actor.post('/api/workspace/workflow/actions/' + view['next_actions'][0]['id'], {}))
        return clicked, read()['ledger']


def test_the_option_reaches_the_policy_on_create_and_resume_and_is_never_stored(tmp_path):
    directory = tmp_path / 'ws'
    app, private, events = setup.prepare(directory, DEFAULT_ORIGIN, side_panel_origin=PANEL)
    assert frame_ancestors(app) == PANEL
    stored = (directory / 'workspace.json').read_text()
    assert 'chrome-extension' not in stored and 'side_panel' not in stored
    resumed, _, _ = setup.open_workspace(directory, side_panel_origin=PANEL)
    assert frame_ancestors(resumed) == PANEL
    plain, _, _ = setup.open_workspace(directory)
    assert frame_ancestors(plain) == "'none'"


def test_without_the_option_framing_stays_refused(tmp_path):
    app, _, _ = setup.prepare(tmp_path / 'ws', DEFAULT_ORIGIN)
    assert frame_ancestors(app) == "'none'"


def test_digest_and_the_four_decision_walkthrough_are_identical_with_and_without_it(tmp_path):
    results = []
    for name, panel in (('with', PANEL), ('without', None)):
        app, private, events = setup.prepare(tmp_path / name, DEFAULT_ORIGIN, routine_automation=True, side_panel_origin=panel)
        with TestClient(app, base_url=private['origin'], client=('127.0.0.1', 1234)) as client:
            setup.seed(client, app, private, events)
        digest = app.state.workflow.package_digest
        clicked, ledger = walk(app, private)
        results.append((digest, clicked, ledger['applied']))
    assert results[0] == results[1]
    assert results[0][1] == PERSON and results[0][2] == '2400.00'


@pytest.mark.parametrize('value', ['https://example.com', 'chrome-extension://short', 'chrome-extension://' + 'z' * 32,
                                   PANEL + ' ' + PANEL, '*'])
def test_a_bad_value_is_refused_before_a_workspace_exists(tmp_path, value):
    directory = tmp_path / 'ws'
    refused = cli(directory, '--side-panel-origin', value)
    assert refused.returncode == 1 and 'Traceback' not in refused.stderr
    assert refused.stderr.strip().splitlines() == ['setup_northwind: The side panel option takes exactly one chrome-extension origin.']
    assert not directory.exists()
    with pytest.raises(ValueError):
        setup.prepare(tmp_path / 'api', DEFAULT_ORIGIN, side_panel_origin=value)
    assert not (tmp_path / 'api').exists()


def test_cli_create_and_resume_print_the_framing_line_only_when_given(tmp_path):
    directory = tmp_path / 'ws'
    created = cli(directory, '--side-panel-origin', PANEL)
    assert created.returncode == 0, created.stderr[-2000:]
    printed = json.loads(created.stdout.strip().splitlines()[-1])
    lines = created.stderr.strip().splitlines()
    assert printed['side_panel_origin'] == PANEL
    assert lines[-4] == 'Only the side panel of ' + PANEL + ' may frame this served workspace.'
    assert lines[-3:] == [str(directory / 'scripted-reviewer.jwk'), SCRIPT, printed['origin']]
    before = (directory / 'workspace.json').read_bytes()
    plain = cli(directory, '--resume')
    assert plain.returncode == 0 and 'side_panel_origin' not in plain.stdout
    assert not any('side panel' in line for line in plain.stderr.splitlines())
    refused = cli(directory, '--resume', '--side-panel-origin', 'https://example.com')
    assert refused.returncode == 1 and 'Traceback' not in refused.stderr
    assert (directory / 'workspace.json').read_bytes() == before
