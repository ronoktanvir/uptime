"""Local Atlassian onboarding lab. HTTP integration calls get_lab/act with a trusted Principal."""
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
import sqlite3

from .contracts import Principal, Source, fingerprint
from .onboarding_extract import FIXTURES, PDF, SLA, SUPPORT
from .onboarding_rules import compile_template, evaluate, fixture, generated_cases, rate_for

ENGINE_REVISION = 'jira-local-1'
PUBLIC_SOURCES = [Source.PUBLIC.value, Source.REPLAY.value]
LOCAL_SOURCES = [*PUBLIC_SOURCES, Source.CUSTOMER.value]
ACTIONS = {'approve': 'Approve candidate', 'activate': 'Activate locally', 'rollback': 'Roll back activation',
           'revoke': 'Revoke approval', 'shadow': 'Replay shadow checks', 'review': 'Begin a new review'}


def _encode(value):
    return json.dumps(value, separators=(',', ':'), sort_keys=True, allow_nan=False)


def _suite(template):
    generated = generated_cases(template)
    generated_fail = [r for r in generated if rate_for(template, r['plan'], Decimal(r['uptime'])) != Decimal(r['rate'])]
    oracle = fixture('terms_gold')
    rules = template['rules']
    expected = [
        ('Effective date', rules['effective'] == oracle['effective']),
        ('Covered Jira experiences', sorted(rules['experiences']) == oracle['jira_experiences']),
        ('Downtime minute error threshold', Decimal(rules['error_rate_gt']) == Decimal(oracle['error_rate_gt'])),
        ('Calendar-day claim window', rules['claim']['calendar_days'] == oracle['claim_calendar_days']),
        ('Business-day credit amount challenge', rules['challenge']['business_days'] == oracle['challenge_business_days']),
    ]
    for plan, cases in oracle['tier_checks'].items():
        for uptime, wanted in cases.items():
            expected.append((f'{plan} at {uptime}%', rate_for(template, plan, Decimal(uptime)) == Decimal(wanted)))
    base, facts = fixture('overlay'), fixture('observations')
    fake = Principal(base['tenant'], 'fixture-evaluator', 'viewer')
    cases = fixture('shadow_gold')
    scenario_failures = []
    for case in cases:
        result = evaluate(template, fake, base | case.get('overlay', {}), facts | case.get('facts', {}))
        money = str(result.amount.amount) if result.amount else None
        if (result.outcome.value, money) != (case['outcome'], case.get('amount')):
            scenario_failures.append(case['name'])
    wrong = [name for name, passed in expected if not passed]

    def check(label, size, failed):
        return {'label': label, 'passed': not failed,
                'detail': f'{size - len(failed)}/{size} passed' + ('. Mismatch: ' + ', '.join(failed) if failed else '.')}

    checks = [check('Generated threshold tests', len(generated), [r['uptime'] for r in generated_fail]),
              check('Independent public-term checks', len(expected), wrong),
              check('Held-out synthetic scenarios', len(cases), scenario_failures)]
    suite_hash = fingerprint({'generated': generated, 'oracle': oracle, 'scenarios': cases, 'base': base, 'facts': facts})
    return checks, suite_hash


def build_candidate(extraction=None):
    """Deterministically regenerate the reviewed, content-addressed public manifest and boundary tests."""
    record = fixture('extraction') if extraction is None else extraction
    template = compile_template(record)
    return {'template': template, 'generated_tests': generated_cases(template),
            'engine': ENGINE_REVISION, 'version': fingerprint({'template': template, 'engine': ENGINE_REVISION})}


@contextmanager
def _atomic(db):
    # Obtain a write reservation before reading schema/state. Two deferred readers
    # attempting to upgrade simultaneously can deadlock even with a busy timeout.
    nested = db.in_transaction
    db.execute('SAVEPOINT onb_request' if nested else 'BEGIN IMMEDIATE')
    try:
        yield
    except BaseException:
        if nested:
            db.execute('ROLLBACK TO onb_request')
            db.execute('RELEASE onb_request')
        else:
            db.rollback()
        raise
    else:
        if nested:
            db.execute('RELEASE onb_request')
        else:
            db.commit()


def _schema(db):
    db.execute('''CREATE TABLE IF NOT EXISTS onb_candidates (
        version TEXT PRIMARY KEY, manifest TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS onb_events (
        id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, recorded_at TEXT NOT NULL, actor TEXT NOT NULL,
        role TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS onb_tenant_history ON onb_events (tenant,id)')
    for table in ('onb_candidates', 'onb_events'):
        pk = 'version' if table == 'onb_candidates' else 'id'
        # REPLACE can skip delete triggers when SQLite recursive triggers are off.
        db.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table}
                   WHEN EXISTS(SELECT 1 FROM {table} WHERE {pk}=NEW.{pk})
                   BEGIN SELECT RAISE(ABORT, 'immutable onboarding record'); END''')
        for operation in ('UPDATE', 'DELETE'):
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS {table}_{operation} BEFORE {operation} ON {table}
                    BEGIN SELECT RAISE(ABORT, 'immutable onboarding record'); END''')


def _authorize(principal):
    if not isinstance(principal, Principal) or not principal.tenant or not principal.subject or principal.role not in ('viewer', 'reviewer'):
        raise PermissionError('An authenticated tenant principal is required.')


def _tail(db, tenant):
    row = db.execute('SELECT payload,id FROM onb_events WHERE tenant=? ORDER BY id DESC LIMIT 1', (tenant,)).fetchone()
    return (json.loads(row[0]) | {'revision': row[1]}) if row else None


def _event(db, tenant, actor, role, kind, state):
    state['revision'] = db.execute('SELECT COALESCE(MAX(id),0)+1 FROM onb_events').fetchone()[0]
    db.execute('INSERT INTO onb_events(tenant,recorded_at,actor,role,kind,payload) VALUES(?,?,?,?,?,?)',
               (tenant, datetime.now(UTC).isoformat(), actor, role, kind, _encode(state)))


def _overlay(tenant):
    overlay = fixture('overlay')
    allowed = {'tenant', 'agreement', 'plan', 'product', 'instance', 'experience', 'surface', 'currency',
               'effective_from', 'effective_until', 'fee_line_ref', 'source', 'site'}
    if set(overlay) != allowed or overlay.get('source') != Source.CUSTOMER or overlay.get('tenant') != tenant:
        return None
    return overlay


def _prepare(db, p, record):
    candidate = build_candidate(record)
    template, version = candidate['template'], candidate['version']
    overlay = _overlay(p.tenant)
    checks, suite_hash = _suite(template)
    terms = fingerprint({'sources': template['sources'], 'rules': template['rules']})
    basis = fingerprint({'tenant': p.tenant, 'version': version, 'overlay': overlay, 'suite': suite_hash})
    # The first write serializes same-tenant transitions across SQLite connections.
    db.execute('INSERT INTO onb_candidates(version,manifest) SELECT ?,? '
               'WHERE NOT EXISTS(SELECT 1 FROM onb_candidates WHERE version=?)',
               (version, _encode(candidate), version))
    old = _tail(db, p.tenant)
    if old and old['basis'] == basis:
        return candidate, checks, overlay, old
    # On changed terms, overlay or oracle, all previous approvals must be reviewed again.
    carry = old and old['terms'] == terms and old['overlay_hash'] == fingerprint(overlay) and old['suite'] == suite_hash
    active = old['active'] if carry else None
    state = {'version': version, 'terms': terms, 'basis': basis, 'overlay_hash': fingerprint(overlay), 'suite': suite_hash,
             'state': 'DRAFT', 'active': active, 'previous': active, 'reviewer': None}
    machine = ('onboarding-generator', 'system')
    if old and not carry:
        invalid = old | {'state': 'REVOKED', 'active': None, 'previous': None, 'reviewer': None}
        _event(db, p.tenant, *machine, 'Approval invalidated by changed source, overlay, or tests', invalid)
    _event(db, p.tenant, *machine, 'Generated public candidate', state)
    state['state'] = 'VALIDATED'
    _event(db, p.tenant, *machine, 'Validated allowlisted DSL and source pins', state)
    state['checks'] = checks
    state['state'] = 'SHADOW'
    _event(db, p.tenant, *machine, 'Shadow checks passed' if all(c['passed'] for c in checks) else 'Shadow checks failed', state)
    return candidate, checks, overlay, state


def _available(p, checks, overlay, state):
    if p.role != 'reviewer':
        return []
    if state['state'] == 'SHADOW':
        return ['shadow'] + (['approve'] if overlay and all(c['passed'] for c in checks) else [])
    if state['state'] == 'APPROVED':
        return ['activate', 'revoke']
    if state['state'] == 'ACTIVE':
        return ['rollback', 'revoke']
    if state['state'] == 'REVOKED':
        return ['review', 'revoke'] if state['active'] else ['review']
    return []


def _action_id(op, state):
    # Bind the action to the exact artifact, overlay, gate evidence and displayed state.
    return f"{op}~{state['basis']}~{state['state']}~{state['revision']}"


def _view(db, p, candidate, checks, overlay, state, record):
    history_rows = db.execute('SELECT recorded_at, actor, role, kind, payload FROM onb_events '
                              'WHERE tenant=? ORDER BY id', (p.tenant,))
    audit = [{'at': at, 'actor': actor, 'role': role, 'event': event, 'version': json.loads(payload)['version'],
              'state': json.loads(payload)['state'], 'sources': LOCAL_SOURCES if overlay else PUBLIC_SOURCES}
             for at, actor, role, event, payload in history_rows]
    rules = candidate['template']['rules']
    view = {'vendor': 'Atlassian', 'state': state['state'], 'version': candidate['version'], 'active_version': state['active'],
            'revision': state['revision'], 'reviewer': state['reviewer'], 'sources': LOCAL_SOURCES if overlay else PUBLIC_SOURCES,
            'checks': checks, 'history': [f"{a['at']} · {a['event']} · {a['actor']}" for a in audit], 'audit': audit,
            'actions': [{'id': _action_id(op, state), 'label': ACTIONS[op]} for op in _available(p, checks, overlay, state)],
            'scope': 'Local shadow simulator for Jira in a supported browser on Premium or Enterprise.',
            'effective': rules['effective'], 'template': candidate['template'], 'overlay': overlay, 'generated_tests': candidate['generated_tests'],
            'clauses': [{'label': 'Atlassian SLA §§1–3, Appendices A & B', 'uri': SLA},
                        {'label': 'Official SLA PDF with Enterprise table', 'uri': PDF},
                        {'label': 'Support ticket and amount challenge procedure', 'uri': SUPPORT}],
            'extraction': {key: record[key] for key in ('recorded_at', 'model', 'sources')},
            'limits': ['Direct purchase, verified USD monthly product line, full effective UTC month only.',
                       'Public status cannot establish customer impact. Shadow fixtures stand in for vendor monitoring.',
                       'A complete compensation ticket is due by the 15th after month end, with a separate technical ticket during the incident.',
                       'Three business days to challenge the amount posted to the ticket. Exact due date needs a confirmed timezone and holiday calendar.',
                       'Credits apply to a future affected-product invoice subject to its cap. No cash, real filing or credit application.']}
    observations = fixture('observations')
    if overlay and observations.get('tenant') == p.tenant:
        sample = evaluate(candidate['template'], p, overlay, observations)
        view['sample'] = {'outcome': sample.outcome.value, 'trace': list(sample.trace),
                          'amount': str(sample.amount.amount) if sample.amount else None,
                          'filing_status': sample.filing_status, 'issuance_status': sample.issuance_status, 'sources': [*LOCAL_SOURCES, Source.VENDOR.value]}
    return view


def _quarantine(db, p, record):
    # A newly deployed extraction with unknown/injected clauses cannot reuse existing approval.
    version = fingerprint(repr(record))
    prior = _tail(db, p.tenant)
    if not prior or prior['version'] != version or prior['state'] != 'DRAFT':
        state = {'state': 'DRAFT', 'version': version, 'active': None, 'previous': None, 'terms': None,
                 'basis': None, 'overlay_hash': None, 'suite': None, 'reviewer': None}
        _event(db, p.tenant, 'onboarding-generator', 'system', 'Unsupported extraction quarantined; approval cleared', state)
    history = [f'{at} · {event} · {actor}' for at, event, actor in db.execute(
        'SELECT recorded_at, kind, actor FROM onb_events WHERE tenant=? ORDER BY id', (p.tenant,))]
    return {'vendor': 'Atlassian', 'state': 'DRAFT', 'version': version, 'active_version': None,
            'outcome': 'UNSUPPORTED_RULE', 'sources': PUBLIC_SOURCES, 'reviewer': None, 'history': history, 'actions': [],
            'checks': [{'label': 'Allowlisted DSL', 'passed': False,
                        'detail': 'Extraction rejected. A reviewed public-source rule is required.'}]}


def _request(db, principal, action=None):
    _authorize(principal)
    if action is not None and principal.role != 'reviewer':
        raise PermissionError('An interactive local reviewer is required.')
    # Read only deployed, locally packaged fixture. HTTP callers cannot supply terms or overlays.
    stale = False
    with _atomic(db):
        _schema(db)
        record = None
        try:
            record = fixture('extraction')
            candidate, checks, overlay, state = _prepare(db, principal, record)
        except (ValueError, TypeError, OSError, OverflowError):
            if record is None:
                try:
                    record = sha256((FIXTURES / 'extraction.json').read_bytes()).hexdigest()
                except OSError:
                    record = 'unreadable deployed extraction'
            view = _quarantine(db, principal, record)
            stale = action is not None
        else:
            if action is not None:
                allowed = {_action_id(op, state): op for op in _available(principal, checks, overlay, state)}
                op = allowed.get(action)
                if op is None:
                    stale = True
                else:
                    if op == 'approve':
                        state.update(state='APPROVED', reviewer=principal.subject)
                    elif op == 'activate':
                        state.update(state='ACTIVE', previous=state['active'], active=state['version'])
                    elif op == 'rollback':
                        state.update(state='REVOKED', active=state['previous'], previous=None)
                    elif op == 'review':
                        state.update(state='SHADOW', reviewer=None)
                    elif op == 'revoke':
                        state.update(state='REVOKED', active=None, previous=None)
                    _event(db, principal.tenant, principal.subject, principal.role, ACTIONS[op], state)
            view = _view(db, principal, candidate, checks, overlay, state, record)
    if stale:
        raise ValueError('Stale or unavailable onboarding action. Reload the candidate.')
    return view


def get_lab(db: sqlite3.Connection, principal: Principal):
    return _request(db, principal)


def act(db: sqlite3.Connection, principal: Principal, action: str):
    if not isinstance(action, str) or not action:
        raise ValueError('Action ID required')
    return _request(db, principal, action)


if __name__ == '__main__':
    # Safe offline demonstration: deterministic regeneration only, no reviewer or promotion.
    print(json.dumps(build_candidate(), indent=2))
