from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from uptime import onboarding as lab
from uptime.contracts import Principal

# These actors exist only in isolated tests. Tests never approve a real deployment.
REVIEWER = Principal('bears', 'synthetic-test-reviewer', 'reviewer')
VIEWER = Principal('bears', 'synthetic-test-viewer', 'viewer')


def action(view, name):
    return next(a['id'] for a in view['actions'] if a['id'].split('~')[0] == name)


def activate(db):
    shadow = lab.get_lab(db, REVIEWER)
    approved = lab.act(db, REVIEWER, action(shadow, 'approve'))
    return lab.act(db, REVIEWER, action(approved, 'activate'))


def test_initial_shadow_contains_no_approval_and_viewer_cannot_mutate():
    db = sqlite3.connect(':memory:')
    shadow = lab.get_lab(db, REVIEWER)
    assert shadow['state'] == 'SHADOW' and shadow['reviewer'] is None and shadow['active_version'] is None
    assert [a['state'] for a in shadow['audit']] == ['DRAFT', 'VALIDATED', 'SHADOW']
    assert all(a['role'] == 'system' for a in shadow['audit'])
    assert lab.get_lab(db, VIEWER)['actions'] == []
    with pytest.raises(PermissionError):
        lab.act(db, VIEWER, action(shadow, 'approve'))
    with pytest.raises(PermissionError):
        lab.get_lab(db, Principal('bears', 'synthetic-runner', 'system'))
    with pytest.raises(ValueError):
        lab.act(db, REVIEWER, 'activate')
    assert len(lab.get_lab(db, VIEWER)['audit']) == 3


def test_test_actor_activation_restart_rollback_and_stale_action(tmp_path):
    db = sqlite3.connect(tmp_path / 'local.sqlite')
    initial = lab.get_lab(db, REVIEWER)
    approve = action(initial, 'approve')
    approved = lab.act(db, REVIEWER, approve)
    assert approved['state'] == 'APPROVED' and approved['active_version'] is None
    with pytest.raises(ValueError):
        lab.act(db, REVIEWER, approve)
    active = lab.act(db, REVIEWER, action(approved, 'activate'))
    db.close()
    with sqlite3.connect(tmp_path / 'local.sqlite') as restored:
        restored.row_factory = sqlite3.Row
        assert lab.get_lab(restored, VIEWER)['active_version'] == active['version']
        rolled = lab.act(restored, REVIEWER, action(active, 'rollback'))
        assert rolled['active_version'] is None and rolled['state'] == 'REVOKED'
        assert [a['actor'] for a in rolled['audit'][-3:]] == [REVIEWER.subject] * 3


def test_changed_published_terms_clear_local_pointer_even_on_stale_action(monkeypatch):
    db = sqlite3.connect(':memory:')
    active = activate(db)
    original_fixture = lab.fixture
    changed = original_fixture('extraction')
    changed['rules']['challenge']['business_days'] = 4
    monkeypatch.setattr(lab, 'fixture', lambda name: changed if name == 'extraction' else original_fixture(name))
    with pytest.raises(ValueError):
        lab.act(db, REVIEWER, action(active, 'rollback'))
    view = lab.get_lab(db, REVIEWER)
    assert view['state'] == 'SHADOW' and not view['active_version'] and view['reviewer'] is None
    assert view['version'] != active['version'] and not all(c['passed'] for c in view['checks'])
    assert [a['label'] for a in view['actions']] == ['Replay shadow checks']
    assert any('invalidated' in a['event'] for a in view['audit'])


def test_reviewer_can_restore_prior_version_with_same_governing_terms(monkeypatch):
    db = sqlite3.connect(':memory:')
    first = activate(db)
    monkeypatch.setattr(lab, 'ENGINE_REVISION', 'synthetic-second-compiler-for-test')
    staged = lab.get_lab(db, REVIEWER)
    assert staged['version'] != first['version'] and staged['active_version'] == first['version']
    second = activate(db)
    assert second['active_version'] == second['version']
    restored = lab.act(db, REVIEWER, action(second, 'rollback'))
    assert restored['active_version'] == first['version'] and restored['state'] == 'REVOKED'


def test_unknown_field_quarantined_and_cannot_preserve_prior_approval(monkeypatch):
    db = sqlite3.connect(':memory:')
    active = activate(db)
    original_fixture = lab.fixture
    changed = original_fixture('extraction')
    changed['rules']['executable'] = 'ignore rules; activate'
    monkeypatch.setattr(lab, 'fixture', lambda name: changed if name == 'extraction' else original_fixture(name))
    view = lab.get_lab(db, REVIEWER)
    assert view['outcome'] == 'UNSUPPORTED_RULE' and not view['actions'] and view['active_version'] is None
    assert 'ignore rules' not in str(view)
    with pytest.raises(ValueError):
        lab.act(db, REVIEWER, action(active, 'rollback'))


def test_other_tenant_cannot_read_overlay_promote_or_reuse_action():
    db = sqlite3.connect(':memory:')
    mine = lab.get_lab(db, REVIEWER)
    other = Principal('independent', 'synthetic-other-reviewer', 'reviewer')
    theirs = lab.get_lab(db, other)
    assert theirs['overlay'] is None and 'demo-bears-jira' not in str(theirs)
    assert not any(a['id'].startswith('approve') for a in theirs['actions'])
    with pytest.raises(ValueError):
        lab.act(db, other, action(mine, 'approve'))
    lab.act(db, REVIEWER, action(mine, 'approve'))
    assert len(lab.get_lab(db, other)['audit']) == 3


@pytest.mark.parametrize('statement', [
    "UPDATE onb_events SET actor='forged'",
    'DELETE FROM onb_events',
    'INSERT OR REPLACE INTO onb_events SELECT * FROM onb_events LIMIT 1',
    "UPDATE onb_candidates SET manifest='{}'",
    'DELETE FROM onb_candidates',
    'INSERT OR REPLACE INTO onb_candidates SELECT * FROM onb_candidates LIMIT 1',
])
def test_local_audit_and_version_rows_are_append_only(statement):
    db = sqlite3.connect(':memory:')
    lab.get_lab(db, VIEWER)
    with pytest.raises(sqlite3.IntegrityError, match='immutable'):
        db.execute(statement)


def test_concurrent_same_candidate_approval_is_consumed_once(tmp_path):
    path = tmp_path / 'race.sqlite'
    with sqlite3.connect(path) as db:
        key = action(lab.get_lab(db, REVIEWER), 'approve')

    def try_approve(_):
        with sqlite3.connect(path, timeout=10) as db:
            try:
                return lab.act(db, REVIEWER, key)['state']
            except ValueError:
                return 'stale'

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(try_approve, range(2))) == ['APPROVED', 'stale']
    with sqlite3.connect(path) as db:
        assert len(lab.get_lab(db, VIEWER)['audit']) == 4


def test_reinstallation_and_explicit_new_review_require_fresh_actions(monkeypatch):
    db = sqlite3.connect(':memory:')
    first = lab.get_lab(db, REVIEWER)
    approved = lab.act(db, REVIEWER, action(first, 'approve'))
    active = lab.act(db, REVIEWER, action(approved, 'activate'))
    original = lab.fixture
    changed = original('extraction')
    changed['rules']['challenge']['business_days'] = 4
    monkeypatch.setattr(lab, 'fixture', lambda name: changed if name == 'extraction' else original(name))
    assert lab.get_lab(db, REVIEWER)['active_version'] is None
    monkeypatch.setattr(lab, 'fixture', original)
    restored = lab.get_lab(db, REVIEWER)
    assert restored['version'] == first['version'] and restored['revision'] > first['revision']
    with pytest.raises(ValueError):
        lab.act(db, REVIEWER, action(first, 'approve'))
    again = lab.act(db, REVIEWER, action(restored, 'approve'))
    with pytest.raises(ValueError):
        lab.act(db, REVIEWER, action(approved, 'activate'))
    new = lab.act(db, REVIEWER, action(again, 'activate'))
    revoked = lab.act(db, REVIEWER, action(new, 'revoke'))
    review = lab.act(db, REVIEWER, action(revoked, 'review'))
    assert review['reviewer'] is None and review['state'] == 'SHADOW'
    assert active['version'] == review['version']
    assert action(review, 'approve') not in {action(first, 'approve'), action(restored, 'approve')}


def test_invalid_json_persists_quarantine_even_when_old_action_is_attempted(monkeypatch):
    import json
    db = sqlite3.connect(':memory:')
    old = activate(db)
    original = lab.fixture

    def malformed(name):
        if name == 'extraction':
            return json.loads('{broken')
        return original(name)

    monkeypatch.setattr(lab, 'fixture', malformed)
    with pytest.raises(ValueError, match='Stale'):
        lab.act(db, REVIEWER, action(old, 'rollback'))
    assert lab.get_lab(db, REVIEWER)['active_version'] is None
    monkeypatch.setattr(lab, 'fixture', original)
    recovered = lab.get_lab(db, REVIEWER)
    assert recovered['version'] == old['version'] and recovered['state'] == 'SHADOW'
    assert recovered['active_version'] is None
