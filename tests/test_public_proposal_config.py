from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pytest

from scripts.public_proposals import approve, read_export
from uptime.auth import Authority
from uptime.public_proposal_config import PublicProposalConfig, open_public_jobs
from uptime.public_proposal_jobs import canonical, load_approvals


def exported(tmp_path):
    operator = tmp_path/'operator'
    operator.mkdir(mode=0o700)
    value = dict(tenant='t', subject='r', kind='correspondence', target='inbox-public',
                 context_sha256='a'*64, request=dict(model='public-only-test', tools=[], input='Public authored reply.\n'),
                 source_references=[dict(reference='new public control', sha256=sha256(b'Public authored reply.\n').hexdigest())])
    source = tmp_path/'export.json'
    source.write_text(json.dumps(value))
    return source, operator/'approvals.json', value


def test_offline_public_approval_preserves_whole_request_and_only_grants_inference(tmp_path):
    source, approval, value = exported(tmp_path)
    digest = sha256(canonical(value['request'])).hexdigest()
    result = approve(source, approval, approved_by='engineering-operator', expected_digest=digest, public_confirmed=True)
    accepted = load_approvals(approval)
    assert accepted['approvals'][0]['request'] == value['request']
    assert accepted['approvals'][0]['approved_by'] == 'engineering-operator'
    assert result['scope'] == 'model invocation only'
    assert set(accepted['approvals'][0]) == set(value) | {'approved_by', 'approved_at', 'expires_at'}
    assert approval.stat().st_mode & 0o777 == 0o600
    approve(source, approval, approved_by='renewed-operator', expected_digest=digest, public_confirmed=True)
    assert len(load_approvals(approval)['approvals']) == 1
    assert load_approvals(approval)['approvals'][0]['approved_by'] == 'renewed-operator'


@pytest.mark.parametrize('changed', [dict(public_confirmed=False), dict(expected_digest='b'*64), dict(hours=0), dict(hours=169)])
def test_no_approval_written_without_public_confirmation_exact_reviewed_bytes_and_expiry(tmp_path, changed):
    source, approval, value = exported(tmp_path)
    params = dict(approved_by='operator', expected_digest=sha256(canonical(value['request'])).hexdigest(), public_confirmed=True)
    with pytest.raises((ValueError, PermissionError)):
        approve(source, approval, **{**params, **changed})
    assert not approval.exists()


def test_invalid_new_approval_preserves_existing_catalog(tmp_path):
    source, approval, value = exported(tmp_path)
    digest = sha256(canonical(value['request'])).hexdigest()
    approve(source, approval, approved_by='operator', expected_digest=digest, public_confirmed=True)
    before = approval.read_bytes()
    with pytest.raises(ValueError):
        approve(source, approval, approved_by='', expected_digest=digest, public_confirmed=True)
    assert approval.read_bytes() == before
    assert list(approval.parent.glob('.proposal-approval-*')) == []


@pytest.mark.parametrize('field,value', [('request', {'input': float('nan')}), ('request_sha256', 'a'*64), ('permission', 'PUBLIC')])
def test_malformed_export_or_browser_permission_label_is_not_approval(tmp_path, field, value):
    source, _, data = exported(tmp_path)
    data[field] = value
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        read_export(source)


@pytest.mark.parametrize('suffix,allowed', [
    ('proposal-access', True), ('proposal-jobs', True),
    ('proposal-jobs/27e719fd-18d4-4047-915f-c35e7534041e/candidate', True),
    ('proposal-jobs/27e719fd-18d4-4047-915f-c35e7534041e/approve', False),
    ('proposal-jobs/27e719fd-18d4-4047-915f-c35e7534041e/activate', False),
    ('actions/approve', False), ('actions/activate', False), ('semantic-bindings', False),
    ('proposal-jobs/../../actions/activate/candidate', False),
])
def test_draft_signing_paths_do_not_expand_to_adapter_or_financial_approval(suffix, allowed):
    assert Authority.draft_path('/api/vendors/example/'+suffix) is allowed


def test_runtime_configuration_is_private_and_has_no_request_selected_executable(tmp_path, monkeypatch):
    source, approval, value = exported(tmp_path)
    digest = sha256(canonical(value['request'])).hexdigest()
    approve(source, approval, approved_by='operator', expected_digest=digest, public_confirmed=True)
    config = approval.with_name('config.json')
    config.write_text(json.dumps(dict(version=1, executable='/usr/bin/true', approvals_path=str(approval), kinds=['correspondence'])))
    config.chmod(0o600)
    import uptime.public_proposal_config as module
    calls = []
    class Provider:
        def __init__(self, executable, **kwargs):
            calls.append((executable, kwargs))
    monkeypatch.setattr(module, 'SafePublicClaude', Provider)
    jobs = open_public_jobs(tmp_path/'jobs.sqlite', config)
    try:
        assert calls[0][0] == '/usr/bin/true'
        assert calls[0][1]['model'] == 'claude-opus-5-5'
        assert 'vendor' not in jobs.providers
    finally:
        jobs.close()
    config.chmod(0o644)
    with pytest.raises(ValueError):
        open_public_jobs(tmp_path/'jobs.sqlite', config)
    assert len(calls) == 1


def test_runtime_config_cannot_enable_unknown_kinds_or_processing_flags():
    base = dict(version=1, executable='/usr/bin/true', approvals_path='/private/approval.json', kinds=['correspondence'])
    for changed in ({'kinds': ['customer']}, {'customer_processing': True}, {'url': 'http://example.invalid'}):
        with pytest.raises(ValueError):
            PublicProposalConfig.model_validate({**base, **changed})


def test_correspondence_only_service_binds_to_app_and_closes_with_lifecycle(tmp_path):
    from fastapi.testclient import TestClient
    from uptime.public_proposal_jobs import PublicProposalJobs
    from uptime.auth import bind_workspace
    from uptime.server import create_app
    source, approval, value = exported(tmp_path)
    approve(source, approval, approved_by='operator', expected_digest=sha256(canonical(value['request'])).hexdigest(), public_confirmed=True)
    provider_calls = []
    db = tmp_path/'workspace.sqlite'
    bind_workspace(db, 'replay', False)
    jobs = PublicProposalJobs(db, approval, {'correspondence': lambda request: provider_calls.append(request)})
    app = create_app(db, proposal_jobs=jobs)
    with TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 4312)) as client:
        assert client.get('/health').status_code == 200
        assert app.state.correspondence.public_proposal_jobs is jobs
        assert not jobs.closed
    assert jobs.closed
    assert provider_calls == []
