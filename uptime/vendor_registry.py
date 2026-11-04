"""Append-only tenant catalog and lifecycle. Activation changes which evaluator can dispatch."""
from contextlib import contextmanager
import json
from hashlib import sha256
import re

from pydantic import Field, ValidationError

from .contracts import Outcome, Principal, Source, fingerprint
from .onboarding import _atomic
from .storage import database, now, persist_case, _read_versions
from .vendor_eval import evaluate, generated_checks
from .vendor_model import staged_extraction
from .vendor_terms import Intake, Strict, bind_overlay, candidate_version

SOURCES = [Source.REPLAY.value, Source.CUSTOMER.value, Source.VENDOR.value]
OPS = {'approve': 'Approve reviewed tests', 'activate': 'Activate for local evaluation',
       'rollback': 'Roll back activation', 'interpret': 'Accept source interpretation for this review', 'review': 'Begin fresh review', 'revoke': 'Revoke approval'}


class IndependentTest(Strict):
    name: str = Field(min_length=1, max_length=160)
    facts: dict
    expected: dict


class TestSubmission(Strict):
    revision: int
    tests: list[IndependentTest] = Field(min_length=1, max_length=60)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS v4_vendor_artifact (
        tenant TEXT NOT NULL, vendor TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(tenant,vendor,version))""")
    db.execute("""CREATE TABLE IF NOT EXISTS v4_vendor_event (
        tenant TEXT NOT NULL, vendor TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL,
        actor TEXT NOT NULL, at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant,vendor,revision))""")
    for table, key in [('v4_vendor_artifact', 'version'), ('v4_vendor_event', 'revision')]:
        for op in ('UPDATE', 'DELETE'):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table}
                            BEGIN SELECT RAISE(ABORT,'immutable catalog record'); END""")
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE tenant=NEW.tenant AND vendor=NEW.vendor AND {key}=NEW.{key})
            BEGIN SELECT RAISE(ABORT,'immutable catalog record'); END""")


@contextmanager
def transaction(path, principal, vendor=None, *, write=False):
    if (not isinstance(principal, Principal) or not principal.tenant or not principal.subject
            or principal.role not in ('viewer', 'reviewer') or write and principal.role != 'reviewer'):
        raise PermissionError('Authenticated tenant reviewer required for vendor mutations.')
    if vendor is not None and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', vendor):
        raise ValueError('Invalid vendor catalog identifier.')
    with database(path) as db, _atomic(db):
        _schema(db)
        yield db


def _tail(db, p, vendor, required=True):
    row = db.execute('SELECT payload FROM v4_vendor_event WHERE tenant=? AND vendor=? ORDER BY revision DESC LIMIT 1',
                     (p.tenant, vendor)).fetchone()
    if not row and required:
        raise KeyError(vendor)
    return json.loads(row[0]) if row else None


def _artifact(db, p, vendor, version):
    if not version:
        return None
    row = db.execute('SELECT payload FROM v4_vendor_artifact WHERE tenant=? AND vendor=? AND version=?',
                     (p.tenant, vendor, version)).fetchone()
    return json.loads(row[0]) if row else None


def _event(db, p, vendor, state, kind):
    state['revision'] += 1
    db.execute('INSERT INTO v4_vendor_event VALUES(?,?,?,?,?,?,?)',
               (p.tenant, vendor, state['revision'], kind, p.subject, now(), encode(state)))


def _actions(state):
    if state['state'] == 'SHADOW':
        if state['checks'] and all(r['passed'] for r in state['checks']):
            return ['interpret'] if state.get('interpretation_required') and not state.get('interpretation_reviewer') else ['approve']
        return []
    if state['state'] == 'APPROVED':
        return ['activate', 'revoke']
    if state['state'] == 'ACTIVE':
        return ['rollback', 'revoke']
    if state['state'] == 'REVOKED':
        return ['review', 'revoke'] if state['active_version'] else ['review']
    return []


def _key(p, vendor, state, op):
    return f'{op}~{state["revision"]}~' + fingerprint([p.tenant, p.subject, vendor, state['version'], state['revision'], op])


def _view(db, p, vendor, state):
    artifact = _artifact(db, p, vendor, state['version'])
    audit = [dict(row) for row in db.execute(
        'SELECT revision,kind,actor,at FROM v4_vendor_event WHERE tenant=? AND vendor=? ORDER BY revision', (p.tenant, vendor))]
    result = {k: v for k, v in state.items() if k != 'tests'}
    result.update(vendor_id=vendor, audit=audit, actions=[], sources=SOURCES)
    if artifact:
        result.update(artifact)
    if p.role == 'reviewer':
        result['actions'] = [{'id': _key(p, vendor, state, op), 'label': OPS[op], 'operation': op} for op in _actions(state)]
    return result


def catalog(path, p):
    with transaction(path, p) as db:
        rows = db.execute("""SELECT e.vendor,e.payload FROM v4_vendor_event e
            WHERE e.tenant=? AND revision=(SELECT MAX(revision) FROM v4_vendor_event v
            WHERE v.vendor=e.vendor AND v.tenant=e.tenant) ORDER BY e.vendor""", (p.tenant,))
        vendors = []
        for vendor, payload in rows:
            state = json.loads(payload)
            vendors.append({'vendor_id': vendor, **{key: state[key] for key in ('vendor', 'revision', 'version', 'state', 'active_version')}})
        return {'vendors': vendors}


def get_vendor(path, p, vendor):
    with transaction(path, p, vendor) as db:
        return _view(db, p, vendor, _tail(db, p, vendor))


def _fresh(old, vendor):
    return dict(vendor=vendor, version=None, state='DRAFT', revision=old['revision'] if old else 0,
                active_version=None, previous=None, reviewer=None, reviewer_kind=None,
                checks=[], tests=[], suite=None, test_author=None)


def install(path, p, vendor, body):
    with transaction(path, p, vendor, write=True) as db:
        old = _tail(db, p, vendor, required=False)
        state = _fresh(old, vendor)
        try:
            intake = Intake.model_validate(body)
            manifest, extraction = staged_extraction(intake.document)
            overlay = bind_overlay(manifest, intake.overlay)
        except (ValueError, OSError, TypeError, OverflowError) as exc:
            # Retain a safe digest and error category, never echo malformed/private raw inputs.
            state.update(state='QUARANTINED', outcome=Outcome.UNSUPPORTED.value, rejected_digest=sha256(json.dumps(body, sort_keys=True, allow_nan=True).encode()).hexdigest(),
                         reason='Invalid intake schema.' if isinstance(exc, ValidationError) else str(exc)[:240])
            if old and old.get('rejected_digest') == state['rejected_digest'] and old['state'] == 'QUARANTINED':
                return _view(db, p, vendor, old)
            _event(db, p, vendor, state, 'Quarantined intake; dispatch suspended')
            return _view(db, p, vendor, state)
        version = candidate_version(manifest, overlay, extraction)
        if old and old['version'] == version:
            return _view(db, p, vendor, old)
        artifact = {'manifest': manifest, 'overlay': overlay, 'extraction': extraction, 'source_text': intake.document.text,
                    'generated_tests': generated_checks(manifest), 'source_received_at': now()}
        if not _artifact(db, p, vendor, version):
            db.execute('INSERT INTO v4_vendor_artifact VALUES(?,?,?,?)', (p.tenant, vendor, version, encode(artifact)))
        if old and old['active_version']:
            prior = _artifact(db, p, vendor, old['active_version'])
            if prior['manifest'] == manifest and prior['overlay'] == overlay:
                state['previous'] = old['active_version']
                state['previous_suite'] = old['suite']
        state.update(version=version, vendor=manifest['vendor'],
                     interpretation_required=extraction.get('method') == 'tool_free_model_propositions',
                     interpretation_reviewer=None)
        _event(db, p, vendor, state, 'Imported public document and separate tenant overlay')
        state.update(state='VALIDATED')
        _event(db, p, vendor, state, 'Validated source coverage, typed thresholds and governing dates')
        state.update(state='SHADOW')
        _event(db, p, vendor, state, 'Shadow only; waiting for independent reviewer cases')
        return _view(db, p, vendor, state)


def submit_tests(path, p, vendor, submission):
    with transaction(path, p, vendor, write=True) as db:
        state = _tail(db, p, vendor)
        if state['revision'] != submission.revision or state['state'] != 'SHADOW':
            raise ValueError('Test submission requires the current shadow revision.')
        artifact = _artifact(db, p, vendor, state['version'])
        rows, outcomes, names = [], set(), set()
        for test in submission.tests:
            expected = test.expected
            if not set(expected) <= {'outcome', 'amount'} or expected.get('outcome') not in set(Outcome):
                raise ValueError('An independent outcome and optional decimal amount are required.')
            if expected['outcome'] == Outcome.ELIGIBLE:
                if not isinstance(expected.get('amount'), str) or not re.fullmatch(r'[0-9]+\.[0-9]{2,10}', expected['amount']):
                    raise ValueError('Provide the expected eligible USD estimate as a decimal string.')
            elif expected.get('amount') is not None:
                raise ValueError('Only eligible cases may carry expected money.')
            if test.name in names:
                raise ValueError('Independent case names must be unique.')
            names.add(test.name)
            outcomes.add(expected['outcome'])
            result = evaluate(artifact['manifest'], artifact['overlay'], test.facts, p.tenant)
            actual = {k: result[k] for k in ('outcome', 'amount')}
            rows.append({'name': test.name, 'expected': expected, 'actual': actual, 'passed':
                         actual['outcome'] == expected['outcome'] and actual['amount'] == expected.get('amount')})
        rows.append({'name': 'Independent positive and refusal coverage', 'passed':
                     Outcome.ELIGIBLE in outcomes and bool(outcomes - {Outcome.ELIGIBLE})})
        rows.append({'name': 'Generated exact threshold checks', 'passed': all(r['passed'] for r in artifact['generated_tests'])})
        state.update(tests=[t.model_dump() for t in submission.tests], checks=rows, test_author=p.subject)
        state['suite'] = fingerprint(state['tests'])
        if state.get('previous_suite') != state['suite']:
            state['previous'] = None
        _event(db, p, vendor, state, 'Executed reviewer-authored scenarios in shadow')
        return _view(db, p, vendor, state)


def act(path, p, vendor, action):
    with transaction(path, p, vendor, write=True) as db:
        state = _tail(db, p, vendor)
        ops = {_key(p, vendor, state, op): op for op in _actions(state)}
        if action not in ops:
            raise ValueError('Stale or unavailable reviewer action.')
        op = ops[action]
        if op == 'interpret':
            state['interpretation_reviewer'] = p.subject
        elif op == 'approve':
            if state.get('interpretation_required') and state.get('interpretation_reviewer') != p.subject:
                raise PermissionError('The approving reviewer must accept the cited source interpretation.')
            state.update(state='APPROVED', reviewer=p.subject,
                         reviewer_kind='scripted_test' if 'test' in p.subject.lower() else 'authenticated_reviewer')
        elif op == 'activate':
            if state['reviewer'] != p.subject:
                raise PermissionError('Activation requires the same authenticated approving reviewer.')
            state.update(state='ACTIVE', active_version=state['version'])
        elif op == 'rollback':
            state.update(state='REVOKED', active_version=state['previous'], previous=None, reviewer=None)
        elif op == 'revoke':
            state.update(state='REVOKED', active_version=None, previous=None, reviewer=None)
        else:
            state.update(state='SHADOW', active_version=None, previous=None, checks=[], tests=[],
                         suite=None, reviewer=None, reviewer_kind=None, test_author=None, interpretation_reviewer=None)
        _event(db, p, vendor, state, OPS[op])
        return _view(db, p, vendor, state)


def dispatch(path, p, vendor, facts):
    with transaction(path, p, vendor, write=True) as db:
        state = _tail(db, p, vendor)
        if not state['active_version']:
            raise ValueError('An activated local adapter is required to create a workbench case.')
        version = state['active_version']
        artifact = _artifact(db, p, vendor, version)
        manifest, overlay = artifact['manifest'], artifact['overlay']
        result = evaluate(manifest, overlay, facts, p.tenant)
        obligation = fingerprint([p.tenant, vendor, overlay['account'], overlay['agreement'], overlay['product'],
                                  overlay['plan'], facts.get('month')])
        case_id = 'availability-' + obligation
        versions = list(_read_versions(db, p.tenant, case_id))
        if versions:
            saved = versions[-1]['payload']
            if saved['observation_digest'] == result['observation_digest'] and saved['version'] == version:
                return saved
        at = now()
        doc = manifest['document']
        clauses = [dict(c, label=f'{doc["name"]}, clause {c["id"]}: {c["quote"]}', uri=doc['uri'],
                        source_sha256=doc['sha256']) for c in manifest['citations']]
        if override := overlay.get('override'):
            clauses.append({'label': override['source_ref'], 'quote': override['quote'], 'source': Source.CUSTOMER.value,
                            'sha256': fingerprint(override), 'uri': ''})
        case = dict(result, id=case_id, vendor=manifest['vendor'], vendor_id=vendor, title='Monthly availability · ' + overlay['product'],
                    stage='EVALUATED', version=version, obligation_id=obligation, sources=SOURCES, clauses=clauses,
                    source_sha256=doc['sha256'], source_received_at=artifact['source_received_at'],
                    source_currentness='Version supplied at intake; current external terms unverified',
                    agreement=overlay['agreement'], account=overlay['account'], adapter_revision=state['revision'],
                    evidence=[{'label': 'Scoped synthetic customer and vendor observations', 'detail': facts, 'sources': SOURCES}],
                    financials=[{'label': 'Modeled filing estimate', 'value': result['amount'] or 'Unavailable', 'sources': SOURCES}],
                    actions=[], timeline=[{'at': at, 'event': 'Dispatched active adapter by ' + p.subject, 'sources': SOURCES}])
        persist_case(db, p.tenant, case)
        return case


def active_binding(path, p, vendor):
    """Trusted read seam for workbench integrations. Never accepts client-provided rule data."""
    with transaction(path, p, vendor) as db:
        state = _tail(db, p, vendor)
        if not state['active_version']:
            raise ValueError('No active adapter for this vendor and tenant.')
        artifact = _artifact(db, p, vendor, state['active_version'])
        return {'version': state['active_version'], 'revision': state['revision'],
                'manifest': artifact['manifest'], 'overlay': artifact['overlay']}


def resolve_case(path, p, case_id, *, require_active=True):
    """Resolve a previously dispatched estimate with its bound current agreement; never infer an award."""
    with transaction(path, p) as db:
        versions = list(_read_versions(db, p.tenant, case_id))
        if not versions:
            raise KeyError(case_id)
        case = versions[-1]['payload']
        if not case_id.startswith('availability-') or not case.get('vendor_id'):
            raise ValueError('Case is not an integrity-verified availability evaluation.')
        state = _tail(db, p, case['vendor_id'])
        if require_active and state['active_version'] != case['version']:
            raise ValueError('The governing adapter is no longer active. Historical evaluation is preserved.')
        artifact = _artifact(db, p, case['vendor_id'], case['version'])
        if not artifact or (artifact['overlay']['agreement'], artifact['overlay']['account']) != (case['agreement'], case['account']):
            raise ValueError('Case agreement or account binding is inconsistent.')
        return case
