"""Public designation and financial boundaries must survive before browser capture."""
import copy
import json

import pytest

from scripts.film_ramp_v4 import BINDING, DURATIONS, boundaries
from uptime.server import create_app


def test_film_timeline_and_designated_capture(tmp_path):
    workspace = create_app(tmp_path/'replay.sqlite', rehearsal=True,
                           rehearsal_secret='disposable-film-test-secret-00000000').state.ramp_workspace
    designation = json.loads(BINDING.read_text())
    overview = workspace.overview()
    bill = workspace.detail('ramp-bills-' + designation['bill_id'])
    cap = workspace.detail('rehearsal-cap-' + designation['bill_id'])
    boundaries(overview, bill, cap, designation)
    assert sum(DURATIONS) == 120
    assert len(DURATIONS) == 13
    assert bill['native_projection']['vendor_id'] == bill['vendor']
    assert any(e.get('label') == 'Native approval observation' and e.get('status') == 'PENDING'
               for e in bill['evidence'])
    for key, value in [('provider_id', 'another-bill'), ('amount', '39.00'),
                       ('publishable', True), ('actual_recovery', '40.00')]:
        altered = copy.deepcopy(cap)
        altered[key] = value
        with pytest.raises(RuntimeError):
            boundaries(overview, bill, altered, designation)


def test_public_general_draft_over_signed_http(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from uptime.auth import DEFAULT_ORIGIN, SCRIPT
    from uptime.auth_client import ReviewerClient
    from uptime.auth_keys import rehearsal_key
    from scripts import film_ramp_v4 as film

    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(film.EXTRACTIONS))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS', '1')
    intake, manifest, extraction = film.public_intake()
    facts, controls = film.demo_controls(intake['overlay'], manifest)
    secret = 'disposable-film-test-secret-00000000'
    app = create_app(tmp_path/'draft.sqlite', rehearsal=True, rehearsal_secret=secret,
                     approvals_enabled=False)
    with TestClient(app, base_url=DEFAULT_ORIGIN, client=('127.0.0.1',12345)) as client:
        reviewer = ReviewerClient(client, DEFAULT_ORIGIN, SCRIPT, rehearsal_key(secret))
        prefix = '/api/vendors/' + film.VENDOR
        def post(suffix, body):
            response = reviewer.post(prefix+suffix, body)
            assert response.status_code == 200
            return response.json()
        state = post('/candidates', intake)
        assert state['state'] == 'SHADOW', state.get('reason')
        state = post('/tests', dict(revision=state['revision'], tests=controls))
        film.draft_boundaries(state, extraction)
        assert state['actions'] == []
        preview = post('/shadow-preview', dict(revision=state['revision'], facts=facts))
        assert preview['classification'] == 'LOCAL_DRAFT_PREVIEW'
        assert preview['dispatch_authorized'] is False
        assert preview['evaluation']['amount'] == '12.00'
        for field in ('reviewer', 'active_version', 'interpretation_reviewer'):
            altered = copy.deepcopy(state)
            altered[field] = 'fabricated-approval'
            with pytest.raises(RuntimeError):
                film.draft_boundaries(altered, extraction)
        # No dispatch or case creation is part of this preview.
        after = client.get(prefix, headers=reviewer.headers).json()
        assert after['revision'] == state['revision']


def test_public_intake_requires_accepted_artifact(tmp_path, monkeypatch):
    from scripts import film_ramp_v4 as film
    monkeypatch.setattr(film, 'EXTRACTIONS', tmp_path)
    with pytest.raises(RuntimeError, match='Accepted public extraction missing'):
        film.public_intake()
