"""Phase79 offline vendor request export: exact, create-only and permission-free.

The provider constructor is replaced by an explicit double whose provider refuses to be
called, so no model, approval, queue or database is reached. The public approval request
helper itself is the real pure helper.
"""
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = ROOT / 'fixtures' / 'onboarding79_public' / 'document.json'
TENANT, SUBJECT, TARGET = 'tenant-phase79', 'operator-phase79', 'juniper-reach-cloud'
PROFILES = ('monthly', 'monthly-propositions', 'resource-month')
REJECTED = (OSError, ValueError)

_spec = importlib.util.spec_from_file_location('public_proposals_phase79', ROOT / 'scripts' / 'public_proposals.py')
public_proposals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(public_proposals)


from uptime.vendor_model import MODEL, VENDOR_SYSTEM


class RefusingProvider:
    """Explicit provider double: export may construct it but must never invoke it."""

    model, system = MODEL, VENDOR_SYSTEM
    profile = {'name': 'explicit-phase79-public-provider-double', 'revision': 1}

    def __init__(self, executable):
        self.executable = executable
        self.invoked = []

    def __call__(self, *args, **kwargs):
        self.invoked.append((args, kwargs))
        raise AssertionError('export must never invoke the provider')


@pytest.fixture
def providers(monkeypatch):
    built = []

    def build_vendor_provider(executable):
        provider = RefusingProvider(executable)
        built.append(provider)
        return provider

    monkeypatch.setattr(public_proposals, 'build_vendor_provider', build_vendor_provider)
    yield built
    assert all(provider.invoked == [] for provider in built)


@pytest.fixture(autouse=True)
def no_approval(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('export must not approve or read approvals')

    monkeypatch.setattr(public_proposals, 'approve', refuse)
    monkeypatch.setattr(public_proposals, 'load_approvals', refuse)


def _private_dir(path):
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def _write_private_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(value, handle)


def _config(executable, approvals, kinds=('vendor',)):
    return dict(version=1, executable=str(executable), approvals_path=str(approvals), kinds=list(kinds))


@pytest.fixture
def private(tmp_path):
    config_dir = _private_dir(tmp_path / 'server-config')
    executable = config_dir / 'pinned-claude'
    executable.write_text('#!/bin/sh\nexit 97\n', encoding='utf-8')
    executable.chmod(0o700)
    approvals = config_dir / 'approvals.json'
    config = config_dir / 'public-proposals.json'
    _write_private_json(config, _config(executable, approvals))
    return SimpleNamespace(root=tmp_path, config_dir=config_dir, config=config, executable=executable,
                           approvals=approvals, exports=_private_dir(tmp_path / 'exports'))


def _export_to(private, output, document=DOCUMENT, config=None, **overrides):
    options = dict(tenant=TENANT, subject=SUBJECT, target=TARGET, profile='monthly-propositions')
    options.update(overrides)
    return public_proposals.export_vendor(document, config or private.config, output, **options)


def _export(private, name, **overrides):
    output = private.exports / name
    return _export_to(private, output, **overrides), output


def _tree(root):
    return {str(path.relative_to(root)) for path in root.rglob('*')}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_export_is_exact_pure_helper_output_readable_by_show(private, providers):
    before = _tree(private.root)
    result, output = _export(private, 'vendor-request.json')
    again, second = _export(private, 'vendor-request-again.json')

    direct = RefusingProvider(str(private.executable))
    body = dict(document=json.loads(DOCUMENT.read_bytes()), profile='monthly-propositions', attempt_nonce='initial')
    expected = public_proposals.public_approval_request(
        direct, public_proposals.DraftReviewer(TENANT, SUBJECT, 'reviewer'), TARGET, body)
    assert direct.invoked == []
    exact = (json.dumps(expected, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')
    assert output.read_bytes() == exact
    assert second.read_bytes() == exact

    value, digest = public_proposals.read_export(output)
    assert digest == sha256(public_proposals.canonical(expected['request'])).hexdigest()
    assert result == dict(output_path=str(output), request_sha256=digest, permission=public_proposals.EXPORT_NOTICE)
    assert again['request_sha256'] == digest
    assert (value['tenant'], value['subject'], value['kind'], value['target']) == (TENANT, SUBJECT, 'vendor', TARGET)
    assert [provider.executable for provider in providers] == [str(private.executable)] * 2

    for path in (output, second):
        info = os.lstat(path)
        assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
        assert info.st_uid == os.getuid() and info.st_nlink == 1
    assert _tree(private.root) - before == {'exports/vendor-request.json', 'exports/vendor-request-again.json'}
    assert _tree(private.root) >= before
    assert not private.approvals.exists()


def test_source_text_and_crlf_are_preserved_exactly(private, providers, tmp_path):
    document = json.loads(DOCUMENT.read_bytes())
    crlf = dict(document, text=document['text'].replace('\n', '\r\n'))
    assert '\r\n' in crlf['text']
    source = tmp_path / 'sources'
    source.mkdir()
    path = source / 'document-crlf.json'
    path.write_bytes(json.dumps(crlf, ensure_ascii=False, indent=2).replace('\n', '\r\n').encode('utf-8'))

    output = private.exports / 'crlf.json'
    result = _export_to(private, output, document=path)
    lf_result, _ = _export(private, 'lf.json')
    value, digest = public_proposals.read_export(output)
    assert digest == result['request_sha256'] != lf_result['request_sha256']
    assert any(crlf['text'] in text for text in _strings(value['request']))
    assert not any(document['text'] in text for text in _strings(value['request']))


def test_profiles_and_nonces_give_distinct_requests(private, providers):
    exports = {profile: _export(private, f'{profile}.json', profile=profile) for profile in PROFILES}
    exports['retry'] = _export(private, 'retry.json', attempt_nonce='retry-1')
    digests = {name: result['request_sha256'] for name, (result, _) in exports.items()}
    assert len(set(digests.values())) == len(digests)
    for name, (result, output) in exports.items():
        assert public_proposals.read_export(output)[1] == digests[name]
    assert not private.approvals.exists()


def test_invalid_profile_and_identity_are_rejected_before_construction(private, providers):
    cases = [dict(profile='weekly'), dict(profile='monthly '), dict(tenant=''), dict(tenant='tenant\nphase79'),
             dict(tenant=79), dict(subject='s' * 161), dict(subject=' operator'), dict(subject='operator' + chr(0x202E)),
             dict(attempt_nonce=''), dict(attempt_nonce='retry\x00'), dict(target=79)]
    for index, overrides in enumerate(cases):
        with pytest.raises(ValueError):
            _export(private, f'invalid-{index}.json', **overrides)
    assert public_proposals._opaque('tenant-phase79', 'tenant') == 'tenant-phase79'
    assert providers == []
    assert list(private.exports.iterdir()) == []


def test_invalid_source_or_extra_fields_are_rejected_before_construction(private, providers, tmp_path):
    document = json.loads(DOCUMENT.read_bytes())
    encoded = json.dumps(document).encode('utf-8')
    variants = {
        'extra-field': json.dumps(dict(document, license='CC0')).encode(),
        'missing-text': json.dumps({k: v for k, v in document.items() if k != 'text'}).encode(),
        'private-classification': json.dumps(dict(document, classification='private')).encode(),
        'non-string-text': json.dumps(dict(document, text=79)).encode(),
        'top-level-list': json.dumps([document]).encode(),
        'duplicate-key': b'{"name": "Other", ' + encoded[1:],
        'non-finite': json.dumps(dict(document, text=float('nan'))).encode(),
        'invalid-utf8': encoded[:-1] + b'\xff}',
        'byte-order-mark': b'\xef\xbb\xbf' + encoded,
        'truncated': encoded[:-1],
        'oversized': json.dumps(dict(document, text='x' * public_proposals.MAX_DOCUMENT_BYTES)).encode(),
    }
    sources = tmp_path / 'sources'
    sources.mkdir()
    for name, raw in variants.items():
        path = sources / f'{name}.json'
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            _export_to(private, private.exports / f'{name}.json', document=path)
    with pytest.raises(ValueError):
        _export_to(private, private.exports / 'directory.json', document=sources)
    link = sources / 'linked.json'
    link.symlink_to(DOCUMENT)
    with pytest.raises(OSError):
        _export_to(private, private.exports / 'linked.json', document=link)
    assert providers == []
    assert list(private.exports.iterdir()) == []


def test_disabled_or_invalid_vendor_config_is_rejected(private, providers):
    cases = [
        (['correspondence'], private.executable),
        (['vendor', 'correspondence', 'correspondence'], private.executable),
        ([], private.executable),
        (['vendor'], 'pinned-claude'),
        (['vendor'], private.config_dir / 'missing-claude'),
        (['vendor'], private.config_dir),
    ]
    for index, (kinds, executable) in enumerate(cases):
        config = private.config_dir / f'config-{index}.json'
        _write_private_json(config, _config(executable, private.approvals, kinds))
        with pytest.raises((PermissionError, ValueError)):
            _export(private, f'config-{index}.json', config=config)
    private.executable.chmod(0o600)
    with pytest.raises(PermissionError):
        _export(private, 'not-executable.json')
    assert providers == []
    assert list(private.exports.iterdir()) == []
    assert not private.approvals.exists()


def test_weak_config_permissions_are_rejected(private, providers):
    for mode in (0o640, 0o644, 0o666):
        private.config.chmod(mode)
        with pytest.raises(REJECTED):
            _export(private, f'weak-{mode:o}.json')
    private.config.chmod(0o600)
    linked = private.config_dir / 'linked-config.json'
    linked.symlink_to(private.config)
    with pytest.raises(REJECTED):
        _export(private, 'linked-config.json', config=linked)
    private.config_dir.chmod(0o777)
    try:
        with pytest.raises(REJECTED):
            _export(private, 'weak-directory.json')
    finally:
        private.config_dir.chmod(0o700)
    assert providers == []
    assert list(private.exports.iterdir()) == []


def test_output_is_new_private_and_outside_git(private, providers, tmp_path):
    existing = private.exports / 'existing.json'
    existing.write_bytes(b'keep')
    existing.chmod(0o600)
    with pytest.raises(REJECTED):
        _export(private, 'existing.json')
    assert existing.read_bytes() == b'keep'

    target = private.exports / 'link-target.json'
    link = private.exports / 'link.json'
    link.symlink_to(target)
    with pytest.raises(REJECTED):
        _export(private, 'link.json')
    assert link.is_symlink() and not os.path.lexists(target)

    linked_dir = tmp_path / 'exports-link'
    linked_dir.symlink_to(private.exports, target_is_directory=True)
    rejected = [linked_dir / 'via-link.json', private.exports / '..' / 'exports' / 'traversal.json',
                Path('relative-phase79-export.json'), tmp_path / 'missing' / 'export.json']
    fake_repo = tmp_path / 'repo'
    (fake_repo / '.git').mkdir(parents=True)
    rejected.append(_private_dir(fake_repo / 'private') / 'export.json')
    rejected.append(ROOT / 'tests' / 'onboarding79' / 'phase79-export-must-not-exist.json')
    for output in rejected:
        with pytest.raises(REJECTED):
            _export_to(private, output)
        assert not os.path.lexists(output)
    assert not (private.exports / 'via-link.json').exists()
    assert not (private.exports / 'traversal.json').exists()

    for mode in (0o750, 0o755):
        weak = tmp_path / f'weak-{mode:o}'
        weak.mkdir()
        weak.chmod(mode)
        with pytest.raises(PermissionError):
            _export_to(private, weak / 'export.json')
        assert list(weak.iterdir()) == []

    with pytest.raises(PermissionError):
        _export_to(private, private.approvals)
    assert not private.approvals.exists()
    assert providers == []
    assert sorted(path.name for path in private.exports.iterdir()) == ['existing.json', 'link.json']


def test_write_failure_leaves_no_partial_output(private, providers, monkeypatch):
    real_write = os.write

    def short_write(fd, data):
        real_write(fd, bytes(data[:10]))
        raise OSError(5, 'Input/output error')

    def failing_fsync(fd):
        raise OSError(28, 'No space left on device')

    for name, replacement in (('write', short_write), ('fsync', failing_fsync)):
        with monkeypatch.context() as patch:
            patch.setattr(os, name, replacement)
            with pytest.raises(OSError):
                _export(private, f'{name}-failure.json')
        assert list(private.exports.iterdir()) == []
    assert len(providers) == 2
    assert not private.approvals.exists()


def test_cli_prints_only_path_digest_and_notice_and_show_still_reads(private, providers, monkeypatch, capsys):
    output = private.exports / 'cli.json'
    monkeypatch.setattr(sys, 'argv', [
        'public_proposals.py', 'export-vendor', '--document', str(DOCUMENT), '--config', str(private.config),
        '--output', str(output), '--tenant', TENANT, '--subject', SUBJECT, '--target', TARGET,
        '--profile', 'monthly-propositions', '--attempt-nonce', 'retry-cli1'])
    public_proposals.main()
    captured = capsys.readouterr()
    _, digest = public_proposals.read_export(output)
    assert captured.out.splitlines() == [
        f'Request export: {output}', f'Complete request SHA256: {digest}', public_proposals.EXPORT_NOTICE]
    assert captured.err == ''
    document_text = json.loads(DOCUMENT.read_bytes())['text']
    for hidden in (str(private.executable), str(private.config), document_text):
        assert hidden not in captured.out

    with pytest.raises(SystemExit) as exited:
        public_proposals.main()
    assert exited.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err.startswith('Request export was not written.')
    for hidden in (str(private.executable), str(private.config), 'Traceback'):
        assert hidden not in captured.err

    monkeypatch.setattr(sys, 'argv', ['public_proposals.py', 'show', str(output)])
    public_proposals.main()
    assert capsys.readouterr().out.splitlines()[-1] == f'Complete request SHA256: {digest}'
    assert len(providers) == 1  # the rejected rerun stopped before provider construction
    assert not private.approvals.exists()


def test_export_config_preserves_server_approval_path_validation(private, providers):
    config = private.config_dir / 'relative-approval.json'
    _write_private_json(config, _config(private.executable, 'relative-approval.json'))
    with pytest.raises(ValueError):
        _export(private, 'unusable.json', config=config)
    assert providers == [] and list(private.exports.iterdir()) == []


def test_real_export_entrypoint_only_pins_cli_and_matches_runtime_helper(private):
    """Actual CLI process + real SafePublicClaude/helper, with a CLI that permits only identity probes."""
    import subprocess
    from uptime.vendor_model_jobs import ProposalRequest, build_vendor_provider, public_approval_request
    from uptime.contracts import DraftReviewer
    log = private.config_dir / 'cli-invocations.jsonl'
    private.executable.write_text(
        '#!' + sys.executable + '\n'
        'import json,sys\n'
        'from pathlib import Path\n'
        f'log=Path({str(log)!r})\n'
        'with log.open("a") as f: f.write(json.dumps(sys.argv[1:])+"\\n")\n'
        'if sys.argv[1:]==["--help"]: print("--safe-mode --tools")\n'
        'elif sys.argv[1:]==["--version"]: print("phase79-public-test-cli")\n'
        'else: raise SystemExit(97)\n', encoding='utf-8')
    output = private.exports / 'real-entrypoint.json'
    before = _tree(private.root)
    process = subprocess.run([sys.executable, str(ROOT/'scripts/public_proposals.py'), 'export-vendor',
        '--document', str(DOCUMENT), '--config', str(private.config), '--output', str(output),
        '--tenant', TENANT, '--subject', SUBJECT, '--target', TARGET, '--profile', 'monthly-propositions'],
        cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert process.returncode == 0, process.stderr
    assert [json.loads(line) for line in log.read_text().splitlines()] == [['--help'], ['--version']]
    exported, digest = public_proposals.read_export(output)
    provider = build_vendor_provider(str(private.executable))
    expected = public_approval_request(provider, DraftReviewer(TENANT,SUBJECT,'reviewer'), TARGET,
        ProposalRequest(document=json.loads(DOCUMENT.read_bytes()), profile='monthly-propositions'))
    assert exported == expected and exported['context_sha256'] == expected['context_sha256']
    assert digest == sha256(public_proposals.canonical(expected['request'])).hexdigest()
    assert provider.last_receipt is None
    assert [json.loads(line) for line in log.read_text().splitlines()] == [['--help'], ['--version']] * 2
    assert _tree(private.root) - before == {'exports/real-entrypoint.json', 'server-config/cli-invocations.jsonl'}
    assert not private.approvals.exists()
