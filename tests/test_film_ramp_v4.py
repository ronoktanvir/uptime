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
