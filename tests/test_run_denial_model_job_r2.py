"""The denial model-job driver for 'reworded-log-request', exercised with a stand-in provider (no model call).

The provider is replaced the same way tests/test_public_proposal_config.py does; everything else is the
real application, the real operator approval CLI and the real signed routes.
"""
import json
import sqlite3

import pytest

from scripts import run_denial_model_job as driver
from scripts import setup_northwind as setup
from uptime.auth import DEFAULT_ORIGIN
from uptime.correspondence_blocks import source_blocks
from uptime.correspondence_model import MODEL
from test_correspondence_blocks_71 import P, annotate

PROFILE = dict(name='stand-in-profile', retry_count=0)
RECEIPT = dict(profile=dict(name='stand-in-profile', version='0 (stand-in)', binary_sha256='0' * 64,
                            argv=['<pinned>', '--system-prompt', 'stand-in system prompt']),
               model=MODEL, session='stand-in-session', returncode=0, tool_events=0, tool_inventory=[], mcp_inventory=[],
               output_sha256='1' * 64, result_sha256='2' * 64, client_reported_cost_usd=0.0, hard_cost_cap=False)


def stand_in(text):
    items = []
    for block in source_blocks(text):
        if 'NW-JAN-LOG-001' in block['text']:
            items.append(('substantive', [P('artifact', slots=[('artifact_ref', 'NW-JAN-LOG-001', 0)], artifact_type='resource_log')]))
        else:
            items.append(('substantive', [P('unsupported')]))
    annotation = json.dumps(annotate(text, *items))

    class Provider:
        profile = PROFILE
        last_receipt = None

        def __init__(self, executable, **kwargs):
            pass

        def __call__(self, request):
            Provider.last_receipt = dict(RECEIPT)
            return dict(model=MODEL, text=annotation, session='stand-in-session', usage={'output_tokens': 1},
                        cost_usd=0.0, transport={'receipt': 'stand-in'})
    return Provider


@pytest.fixture
def stand_in_provider(monkeypatch):
    import uptime.public_proposal_config as proposal_config
    text = setup.correspondence_for(setup.load_package(), 'reworded-log-request')['denial']['text']
    monkeypatch.setattr(proposal_config, 'SafePublicClaude', stand_in(text))


def test_reworded_run_stops_after_the_candidate_and_continues_only_on_a_copy(tmp_path, stand_in_provider):
    run_dir, copy_dir = tmp_path / 'run', tmp_path / 'continuation'
    receipt = driver.run(directory=run_dir, executable='/usr/bin/true', approved_by='test operator (stand-in provider)',
                         origin=DEFAULT_ORIGIN, variant='reworded-log-request', continuation_directory=copy_dir,
                         require_clean=False)
    assert len(receipt['source']['commit']) == 40 and 'status_porcelain' in receipt['source']
    assert receipt['automation_after_person_approval']['pause']['reason'] == 'UNEXPECTED_GROUND'
    assert receipt['job']['final']['state'] == 'SUCCEEDED' and len(receipt['candidates']) == 1
    proposed = receipt['candidates'][0]['propositions']
    assert any(p['family'] == 'artifact' and p['slots'] == {'artifact_ref': 'NW-JAN-LOG-001'} for p in proposed)
    # The preserved run stops before any semantic review: the case still waits for a person.
    assert receipt['stopped_before'].startswith('semantic review') and 'semantic_review' not in receipt
    assert receipt['after']['stage'] == 'HUMAN_REVIEW' and receipt['after']['ledger']['awarded'] == '0.00'
    with sqlite3.connect(run_dir / 'workspace' / 'workspace.db') as db:
        kinds = {row[0] for row in db.execute('SELECT kind FROM inbox_interpretation')}
    assert 'review' not in kinds and {'blind', 'candidate'} <= kinds
    # Stored transport fields, captured from the job row; an absent field says so.
    trace = receipt['provenance']
    assert trace['model'] == MODEL and trace['session'] == 'stand-in-session' and trace['returncode'] == 0
    assert trace['tool_inventory'] == [] and trace['mcp_inventory'] == [] and trace['output_sha256'] == '1' * 64
    assert trace['profile']['name'] == 'stand-in-profile' and trace['profile']['revision'] == 'NOT_CAPTURED'
    assert trace['profile']['argv'][2].startswith('<system prompt; sha256 ')
    assert trace['job_row']['approved_by'] == 'test operator (stand-in provider)'
    # The review and the rest of the walkthrough ran on the scratch copy only.
    cont = receipt['continuation']
    assert cont['location'] == str(copy_dir) and cont['authority'] == 'SCRIPTED_NOT_ACTUAL_HUMAN'
    assert cont['preview']['disposition'] == 'NEEDS_EVIDENCE' and cont['preview']['prepare_allowed']
    assert cont['prepared']['requested_artifact'] == {'type': 'resource_log', 'ref': 'NW-JAN-LOG-001'}
    assert cont['outcome'] == 'WALKTHROUGH_COMPLETED' and cont['counts'] == dict(person_decisions=4, automatic_steps=7)
    assert cont['clicked'] == ['Continue routine steps', 'Approve response', 'Post to Local ledger', 'Apply credit to eligible invoice']
    assert cont['ledger'] == dict(claimed='2400.00', awarded='2400.00', posted='2400.00', applied='2400.00')
    assert cont['bill'] == dict(original='11000.00', outstanding='8600.00')


def test_a_dirty_checkout_is_refused_before_anything_is_written(tmp_path, monkeypatch):
    import subprocess
    real = subprocess.run

    def dirty(command, *args, **kwargs):
        if command[:3] == ['git', '-C', str(driver.ROOT)] and 'status' in command:
            return subprocess.CompletedProcess(command, 0, stdout=' M uptime/correspondence.py\n', stderr='')
        return real(command, *args, **kwargs)

    monkeypatch.setattr(driver.subprocess, 'run', dirty)
    with pytest.raises(SystemExit, match='uncommitted or untracked'):
        driver.run(directory=tmp_path / 'run', executable='/usr/bin/true', approved_by='x', variant='reworded-log-request')
    assert not (tmp_path / 'run').exists()


def test_the_unclear_run_keeps_its_earlier_shape(tmp_path, monkeypatch):
    import uptime.public_proposal_config as proposal_config
    text = setup.correspondence_for(setup.load_package(), 'unclear')['denial']['text']
    blocks = source_blocks(text)
    Provider = stand_in(text)
    annotation = json.dumps(annotate(text, *[('substantive', [P('unsupported')]) for _ in blocks]))
    original = Provider.__call__

    def call(self, request):
        result = original(self, request)
        return dict(result, text=annotation)

    Provider.__call__ = call
    monkeypatch.setattr(proposal_config, 'SafePublicClaude', Provider)
    receipt = driver.run(directory=tmp_path / 'run', executable='/usr/bin/true', approved_by='test operator (stand-in provider)',
                         origin=DEFAULT_ORIGIN, variant='unclear', require_clean=False)
    assert receipt['semantic_review']['category'] == 'AMBIGUOUS_GROUNDS' and not receipt['semantic_review']['prepare_allowed']
    assert 'continuation' not in receipt and 'stopped_before' not in receipt
    assert receipt['after']['stage'] == 'HUMAN_REVIEW' and receipt['after']['ledger']['awarded'] == '0.00'
