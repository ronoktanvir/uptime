from fastapi.testclient import TestClient
import pytest
from uptime.auth import DEFAULT_ORIGIN, enroll
from uptime.auth_client import ReviewerClient
from uptime.auth_keys import generate_reviewer_key
from uptime.contracts import Principal
from uptime.server import create_app


def test_nondefault_workspace_has_its_own_authority_and_no_demo_financial_records(tmp_path):
    tenant = 'tenant-silver'
    key = generate_reviewer_key()
    path = tmp_path / 'silver.db'
    enroll(path, 'silver.reviewer', key, 'reviewer', 'replay', tenant)
    app = create_app(path, tenant=tenant)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1',50000)) as client:
        actor = ReviewerClient(client, DEFAULT_ORIGIN, 'silver.reviewer', key)
        report = client.get('/api/dashboard', headers=actor.headers)
        assert report.status_code == 200
        assert report.json()['cases'] == []
        assert report.json()['workspace'] == tenant
        assert report.json()['ramp']['bills'] == []
        assert client.get('/api/onboarding', headers=actor.headers).status_code == 404
        assert client.get('/api/vendors', headers=actor.headers).json()['vendors'] == []
        assert client.get('/api/cases/dispute-cure', headers=actor.headers).status_code == 404
    with pytest.raises(PermissionError):
        app.state.bench.case(Principal('bears', 'signed-in', 'reviewer'), 'dispute-cure')
    with pytest.raises(ValueError):
        create_app(path, tenant='bears')
