"""Phase 86 runner infrastructure. Providers/clients here are authored test doubles; no network or inference."""
import json
import os
from pathlib import Path
import stat
import sys
import textwrap

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evaluate_disputes_86 as runner  # noqa: E402
from uptime import correspondence_model_transport as transport  # noqa: E402
from uptime.correspondence_model_transport import SafePublicClaude  # noqa: E402

MODEL = 'claude-opus-5-5'

FAKE_CLI = '''#!{python}
import json, sys, time
from pathlib import Path
mode = (Path(__file__).parent / 'mode').read_text().strip()
if '--help' in sys.argv:
    print('usage --safe-mode --tools'); sys.exit(0)
if '--version' in sys.argv:
    print('0.0-fake'); sys.exit(0)
sys.stdin.buffer.read()
model = sys.argv[sys.argv.index('--model') + 1]
mcp = [{{'name': 'drift'}}] if mode == 'mcp' else []
print(json.dumps(dict(type='system', subtype='init', tools=[], mcp_servers=mcp, model=model, session_id='s1')), flush=True)
if mode == 'hang':
    time.sleep(30)
print(json.dumps(dict(type='result', subtype='success', is_error=False, session_id='s1',
                      modelUsage={{model: {{}}}}, result='{{"fake": true}}')), flush=True)
'''


@pytest.fixture
def fake_cli(tmp_path):
    folder = tmp_path / 'cli'
    folder.mkdir()
    script = folder / 'claude'
    script.write_text(FAKE_CLI.format(python=sys.executable))
    script.chmod(0o700)
    (folder / 'mode').write_text('ok')
    return script


def request_for(claude):
    return runner.canonical(dict(transport=claude.profile, model=MODEL, system='sys', tools=[], prompt='x'))


def test_create_json_is_create_only_0600(tmp_path):
    folder = runner.protected_directory(tmp_path / 'p')
    runner.create_json(folder / 'a.json', {'b': 1, 'a': 2})
    assert stat.S_IMODE((folder / 'a.json').stat().st_mode) == 0o600
    assert (folder / 'a.json').read_bytes() == b'{"a":2,"b":1}'
    with pytest.raises(FileExistsError):
        runner.create_json(folder / 'a.json', {})
    assert not [p for p in folder.iterdir() if p.name.startswith('.partial-')]
    loose = tmp_path / 'loose'
    loose.mkdir(mode=0o755); loose.chmod(0o755)
    with pytest.raises(PermissionError):
        runner.protected_directory(loose)


def test_verify_pins_detects_drift(tmp_path):
    path = tmp_path / 'source.json'
    path.write_text('{}')
    pins = runner.pin_files([path])
    assert runner.verify_pins(pins)
    path.write_text('{"x":1}')
    with pytest.raises(ValueError):
        runner.verify_pins(pins)


def test_public_read_whitelist_guards(tmp_path):
    public = tmp_path / 'public'; public.mkdir()
    allowed = public / 'case-1.json'; allowed.write_text('{"text":"reply"}')
    other = public / 'case-2.json'; other.write_text('{}')
    gold = tmp_path / 'expected'; gold.mkdir()
    gold_file = gold / 'case-1.json'; gold_file.write_text('{"label":"x"}')
    renamed = public / 'notes.json'; renamed.write_bytes(gold_file.read_bytes())
    link = public / 'link.json'; link.symlink_to(allowed)
    log = []
    assert runner.read_public_json(allowed, [allowed], log) == {'text': 'reply'}
    assert log == [dict(kind='public', path=str(allowed.resolve()), sha256=runner.digest(allowed.read_bytes()))]
    for refused, whitelist in [(other, [allowed]), (renamed, [allowed]), (gold_file, [gold_file]),
                               (link, [allowed, link]), (public / '..' / 'public' / 'case-1.json', [allowed])]:
        with pytest.raises(PermissionError):
            runner.read_public_json(refused, whitelist, log)
    assert len(log) == 1
    attempts = tmp_path / 'attempts'; attempts.mkdir()
    with pytest.raises(RuntimeError):
        runner.read_gold(gold_file, gold_paths=[gold_file], case_ids=['c1', 'c2'], attempt_root=attempts, access_log=log)
    runner.write_result(attempts, 'c1', {'outcome': 'SETUP_GAP'})
    (attempts / 'c2').mkdir(mode=0o700)
    (attempts / 'c2' / 'result.json').write_text('{"interrupted')  # partial, not create-only output
    with pytest.raises(RuntimeError):
        runner.read_gold(gold_file, gold_paths=[gold_file], case_ids=['c1', 'c2'], attempt_root=attempts, access_log=log)
    assert len(log) == 1
    assert runner.read_gold(gold_file, gold_paths=[gold_file], case_ids=['c1'], attempt_root=attempts,
                            access_log=log) == {'label': 'x'}
    assert log[-1]['kind'] == 'gold'


def test_import_does_not_read_expected():
    source = Path(runner.__file__).read_text()
    module_level = [line for line in source.splitlines() if line and not line[0].isspace()]
    assert not any('read_bytes' in line or 'open(' in line for line in module_level)


def test_spool_timeout_retains_partial_stream(tmp_path):
    folder = runner.protected_directory(tmp_path / 'attempt')
    code = 'import sys,time; print("partial", flush=True); sys.stderr.write("err\\n"); sys.stderr.flush(); time.sleep(30)'
    with pytest.raises(TimeoutError):
        runner.spool_run([sys.executable, '-c', code], cwd=tmp_path, env=dict(os.environ), timeout=1.5, folder=folder)
    assert (folder / 'provider.stdout').read_bytes() == b'partial\n'
    assert (folder / 'provider.stderr').read_bytes() == b'err\n'
    assert stat.S_IMODE((folder / 'provider.stdout').stat().st_mode) == 0o600
    termination = json.loads((folder / 'termination.json').read_text())
    assert termination['reason'] == 'TIMEOUT' and termination['stdout']['bytes'] == 8


def test_spool_output_limit_and_actual_returncode(tmp_path):
    big = runner.protected_directory(tmp_path / 'big')
    with pytest.raises(ValueError):
        runner.spool_run([sys.executable, '-c', 'print("x"*5000)'], cwd=tmp_path, env=dict(os.environ),
                         timeout=10, limit=1000, folder=big)
    assert json.loads((big / 'termination.json').read_text())['reason'] == 'OUTPUT_LIMIT'
    ok = runner.protected_directory(tmp_path / 'ok')
    result = runner.spool_run([sys.executable, '-c', 'import sys; print("o"); sys.exit(3)'], cwd=tmp_path,
                              env=dict(os.environ), timeout=10, folder=ok)
    assert result == (3, b'o\n', b'')
    assert not (ok / 'termination.json').exists()


def test_wrapper_uses_real_validation_and_spools_once(fake_cli, tmp_path):
    claude = SafePublicClaude(fake_cli, model=MODEL, system='sys')
    request = request_for(claude)
    folder = tmp_path / 'call'
    wrapped = runner.SpooledPublicClaude(claude, request_sha256=runner.digest(request), folder=folder)
    assert wrapped.profile is claude.profile
    original = transport.bounded_run
    result = wrapped(request)
    assert transport.bounded_run is original
    assert result['text'] == '{"fake": true}'
    assert b'"type": "result"' in (folder / 'provider.stdout').read_bytes()
    with pytest.raises(FileExistsError):  # no retry in the same folder/marker
        wrapped(request)
    other = runner.SpooledPublicClaude(claude, request_sha256=runner.digest(request), folder=tmp_path / 'drift')
    with pytest.raises(ValueError):
        other(request + b' ')
    assert not (tmp_path / 'drift').exists()


def test_wrapper_keeps_inner_mcp_rejection(fake_cli, tmp_path):
    claude = SafePublicClaude(fake_cli, model=MODEL, system='sys')
    (fake_cli.parent / 'mode').write_text('mcp')
    request = request_for(claude)
    folder = tmp_path / 'call'
    original = transport.bounded_run
    with pytest.raises(ValueError, match='MCP'):
        runner.SpooledPublicClaude(claude, request_sha256=runner.digest(request), folder=folder)(request)
    assert json.loads((folder / 'call-result.json').read_text())['status'] == 'FAILED'
    assert b'"drift"' in (folder / 'provider.stdout').read_bytes()
    assert transport.bounded_run is original and claude.blocked


# --- signed dispatch doubles ---------------------------------------------

class Response:
    def __init__(self, code, body):
        self.status_code, self._body = code, body

    def json(self):
        return json.loads(json.dumps(self._body))


class Client:
    """Authored double of an existing signed client; never a provider."""
    def __init__(self, view, job=None, final_view=None):
        self.view, self.job, self.final_view, self.posts, self.gets = view, job, final_view, [], 0

    def get(self, url):
        self.gets += 1
        if '/model-jobs/' in url:
            return Response(200, self.job)
        return Response(200, self.final_view if self.posts and self.final_view is not None else self.view)

    def post(self, url, body):
        self.posts.append((url, body))
        return Response(200, dict(self.job, state='QUEUED', terminal=False))


REQ = dict(model=MODEL, prompt='frozen')
REQ_SHA = 'a' * 64
BLIND = dict(interpretation=dict(blocks=['own']), label='SCRIPTED_NOT_ACTUAL_HUMAN')


def view(**changes):
    base = dict(context=dict(digest='ctx'), blind_entry=BLIND, candidates=[],
                model_job=dict(can_request=True, reason='approved', request_sha256=REQ_SHA,
                               approval_request=dict(context_sha256='ctx', request=REQ)))
    for key, value in changes.items():
        if key in ('can_request', 'request_sha256', 'reason'):
            base['model_job'][key] = value
        else:
            base[key] = value
    return base


def dispatch(client, folder):
    return runner.dispatch_model_job(client, 'http://local', expected_context_digest='ctx', frozen_request=REQ,
                                     expected_request_sha256=REQ_SHA, pinned_blind=BLIND,
                                     read_state=lambda: {'ledger': {'awarded': '0.00'}}, folder=folder,
                                     poll_seconds=1, poll_interval=.01)


@pytest.mark.parametrize('changes', [dict(can_request=False, reason='approval_required'),
                                     dict(context=dict(digest='drifted')),
                                     dict(request_sha256='b' * 64),
                                     dict(blind_entry=None),
                                     dict(blind_entry=dict(BLIND, label='other'))])
def test_missing_approval_or_drift_prevents_dispatch(tmp_path, changes):
    client = Client(view(**changes))
    record = dispatch(client, tmp_path / 'd')
    assert record['outcome'] == 'NOT_DISPATCHED' and record['model_calls'] == 0
    assert client.posts == [] and not (tmp_path / 'd' / 'dispatch.marker').exists()


def test_success_requires_served_candidate_matching_request(tmp_path):
    job = dict(id='j1', state='SUCCEEDED', terminal=True, request_sha256=REQ_SHA, context_digest='ctx')
    candidate = dict(id='c1', interpretation={'served': True}, provenance=dict(request_sha256=REQ_SHA))
    client = Client(view(), job, view(candidates=[candidate]))
    record = dispatch(client, tmp_path / 'ok')
    assert record['outcome'] == 'CANDIDATE_RECORDED' and record['verified_candidate'] == candidate
    assert record['state_unchanged'] and len(client.posts) == 1
    with pytest.raises(FileExistsError):  # once-only dispatch marker
        dispatch(Client(view(), job, view(candidates=[candidate])), tmp_path / 'ok')


@pytest.mark.parametrize('job_state, candidates', [
    ('SUCCEEDED', []),  # provider "receipt" but nothing served
    ('SUCCEEDED', [dict(id='c', provenance=dict(request_sha256='f' * 64))]),  # fabricated provenance
    ('FAILED', [dict(id='c', provenance=dict(request_sha256=REQ_SHA))]),
    ('UNCERTAIN', [])])
def test_fabricated_or_uncertain_receipt_is_not_success(tmp_path, job_state, candidates):
    job = dict(id='j1', state=job_state, terminal=True, request_sha256=REQ_SHA, context_digest='ctx',
               provider_receipt=dict(status='success'))
    client = Client(view(), job, view(candidates=candidates))
    record = dispatch(client, tmp_path / 'f')
    assert record['outcome'] == 'NO_VERIFIED_CANDIDATE' and record['verified_candidate'] is None
    assert record['candidates'] == candidates and len(client.posts) == 1


def test_parser_outcome_and_setup_gap_are_separate():
    outcome = runner.parser_outcome(source_text='We accept.', runtime_case='c1', parsed={'kind': 'accept'})
    assert outcome['model_calls'] == 0 and outcome['origin'] == 'deterministic_parser'
    assert outcome['source_text'] == 'We accept.' and 'state' not in outcome
    gap = runner.setup_gap(case_id='c1', missing=['contract'])
    assert gap['outcome'] == 'SETUP_GAP' and gap['model_calls'] == 0


def test_cli_prepare_and_run_are_not_ready(capsys):
    assert runner.main(['prepare']) == 2 and runner.main(['run']) == 2
    assert 'NOT READY' in capsys.readouterr().err
    with pytest.raises(NotImplementedError):
        runner.score()
