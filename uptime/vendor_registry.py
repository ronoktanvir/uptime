"""Append-only tenant catalog and lifecycle. Activation changes which evaluator can dispatch."""
from contextlib import contextmanager
import json
from hashlib import sha256
import re

from pydantic import Field, ValidationError

from .contracts import DraftReviewer, Outcome, Principal, Source, fingerprint
from .claim_identity import EconomicScopeReviewRequired, claim_key, vendor_economic_identity
from .onboarding import _atomic
from .storage import database, now, persist_case, _read_versions
from .vendor_eval import evaluate, generated_checks, rate_for
from .vendor_model import job_extraction, staged_extraction
from .vendor_terms import Document, Intake, Strict, bind_overlay, candidate_version, semantics_revision
from .vendor_public_diagnostics import selected_attachment, public_issues
from . import vendor_bindings

SOURCES = [Source.REPLAY.value, Source.CUSTOMER.value, Source.VENDOR.value]
SCOPE_REVIEW_REASON = 'Ambiguous economic scope requires manual reconciliation.'
PUBLIC_QUARANTINE_REASONS = {'Invalid intake schema.', SCOPE_REVIEW_REASON}
OPS = {'approve': 'Approve reviewed tests', 'activate': 'Activate for local evaluation',
       'rollback': 'Roll back activation', 'interpret': 'Accept source interpretation for this review', 'review': 'Begin fresh review', 'revoke': 'Revoke approval'}


class IndependentTest(Strict):
    name: str = Field(min_length=1, max_length=160)
    facts: dict
    expected: dict


class TestSubmission(Strict):
    revision: int
    tests: list[IndependentTest] = Field(min_length=1, max_length=60)


class SemanticSubmission(Strict):
    revision: int
    review: dict


class SemanticRevocation(Strict):
    revision: int


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS v4_vendor_artifact (
        tenant TEXT NOT NULL, vendor TEXT NOT NULL, version TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(tenant,vendor,version))""")
    db.execute("""CREATE TABLE IF NOT EXISTS v4_vendor_event (
        tenant TEXT NOT NULL, vendor TEXT NOT NULL, revision INTEGER NOT NULL, kind TEXT NOT NULL,
        actor TEXT NOT NULL, at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(tenant,vendor,revision))""")
    db.execute("""CREATE TABLE IF NOT EXISTS v4_vendor_semantic_review (
        tenant TEXT NOT NULL, vendor TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(tenant,vendor,digest))""")
    for table, key in [('v4_vendor_artifact', 'version'), ('v4_vendor_event', 'revision'), ('v4_vendor_semantic_review','digest')]:
        for op in ('UPDATE', 'DELETE'):
            db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_{op} BEFORE {op} ON {table}
                            BEGIN SELECT RAISE(ABORT,'immutable catalog record'); END""")
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_replace BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE tenant=NEW.tenant AND vendor=NEW.vendor AND {key}=NEW.{key})
            BEGIN SELECT RAISE(ABORT,'immutable catalog record'); END""")


@contextmanager
def transaction(path, principal, vendor=None, *, write=False, draft=False):
    if (not isinstance(principal, Principal) or not principal.tenant or not principal.subject
            or principal.role not in ('viewer', 'reviewer') or write and principal.role != 'reviewer'
            or write and isinstance(principal, DraftReviewer) and not draft):
        raise PermissionError('Authenticated tenant reviewer required for vendor mutations.')
    if vendor is not None and not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', vendor):
        raise ValueError('Invalid vendor catalog identifier.')
    with database(path) as db, _atomic(db):
        _schema(db)
        if draft and isinstance(principal, DraftReviewer):
            check_write_draft(db, principal, vendor)
        yield db



def check_write_draft(db, principal, vendor):
    if not vendor or principal.role != "reviewer":
        raise PermissionError("A named vendor draft and enrolled reviewer are required.")
    rows = db.execute("SELECT payload FROM v4_vendor_event WHERE tenant=? AND vendor=?",
                      (principal.tenant, vendor)).fetchall()
    for row in rows:
        state = json.loads(row[0])
        if (state["state"] not in {"DRAFT", "VALIDATED", "SHADOW", "QUARANTINED"}
                or state.get("active_version") or state.get("reviewer")):
            raise PermissionError("Draft-only access cannot alter a published or approved vendor history.")


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


def _compatible(artifact,version):
    try:
        return bool(artifact and artifact.get('semantics_revision')==semantics_revision(artifact['manifest'])
                    and version==candidate_version(artifact['manifest'],artifact['overlay'],artifact['extraction']))
    except (KeyError,TypeError,ValueError):
        return False


def _require_current(db,p,vendor,version):
    artifact=_artifact(db,p,vendor,version)
    if not _compatible(artifact,version):
        raise ValueError('Evaluator changed. Reinstall source, rerun tests and obtain a fresh human review.')
    return artifact


def binding_context_db(db, p, vendor, state=None, artifact=None):
    """Load exact current server authority; never accept context in an HTTP body."""
    state = state or _tail(db,p,vendor)
    artifact = artifact or _artifact(db,p,vendor,state['version'])
    if not artifact or not vendor_bindings.required(artifact['manifest']):
        return None
    digest = artifact['extraction'].get('semantic_binding')
    if not digest or state.get('semantic_binding') != digest:
        return None
    row = db.execute('SELECT payload FROM v4_vendor_semantic_review WHERE tenant=? AND vendor=? AND digest=?',
                     (p.tenant,vendor,digest)).fetchone()
    if not row:
        return None
    record = json.loads(row[0])
    if fingerprint(record) != digest or record.get('tenant') != p.tenant:
        return None
    version = state['version']
    def current():
        latest = _tail(db,p,vendor)
        return (latest['version'] == version and latest.get('semantic_binding') == digest
                and _compatible(artifact,version))
    try:
        context = vendor_bindings._from_record(record,current)
        return vendor_bindings.require_context(artifact['manifest'],artifact['overlay'],p.tenant,context)
    except vendor_bindings.SemanticBindingRequired:
        return None


def _capability(db,p,vendor,state,*,governing_fees=(),trusted_now=None):
    """Public capability is derived at read time, including across app restarts/deployments."""
    snapshot=dict(state)
    version=state['version']
    if version and not _compatible(_artifact(db,p,vendor,version),version):
        snapshot.update(state='REVIEW_REQUIRED',recorded_state=state['state'],actions=[],reinstall_required=True)
    active=state['active_version']
    if active and not _compatible(_artifact(db,p,vendor,active),active):
        snapshot.update(active_version=None,recorded_active_version=active)
    artifact = _artifact(db,p,vendor,version)
    if artifact and vendor_bindings.required(artifact['manifest']):
        context = binding_context_db(db,p,vendor,state,artifact)
        snapshot.update(semantic_binding_required=True, semantic_binding_status='REVIEWED' if context else 'REVIEW_REQUIRED')
        if not context:
            snapshot.update(semantic_binding=None, actions=[])
            if active or state['state'] in ('APPROVED','ACTIVE'):
                snapshot.update(state='REVIEW_REQUIRED',recorded_state=state['state'],active_version=None,recorded_active_version=active)
    # Previously reviewed results become history when their authority/dependency
    # is stale. Newly run unreviewed controls retain their actual null results.
    if snapshot.get('reinstall_required') or (
            snapshot.get('semantic_binding_status') == 'REVIEW_REQUIRED' and state.get('semantic_binding')):
        snapshot.update(recorded_checks=state.get('checks', []), checks=[], checks_status='REVIEW_REQUIRED')
    if artifact and artifact['manifest'].get('credit_rule'):
        from .governing_fees import context_for_digest,GoverningFeeRequired
        positive=[row for row in state.get('checks',[]) if row.get('actual',{}).get('amount') is not None]
        current=True
        path=db.execute('PRAGMA database_list').fetchone()[2]
        tests={test['name']:test['facts'] for test in state.get('tests',[])}
        for row in positive:
            try:
                context_for_digest(path,p.tenant,row.get('governing_fee_digest'),artifact['manifest'],artifact['overlay'],
                                   tests.get(row['name'],{}),governing_fees,trusted_now)
            except GoverningFeeRequired:
                current=False;break
        if positive:
            snapshot['pricing_binding_status']='CURRENT' if current else 'REVIEW_REQUIRED'
        if positive and not current:
            snapshot.update(state='REVIEW_REQUIRED',recorded_state=state['state'],active_version=None,
                recorded_active_version=active,recorded_checks=state.get('checks',[]),checks=[],
                checks_status='REVIEW_REQUIRED',actions=[])
    return snapshot


def _event(db, p, vendor, state, kind):
    state['revision'] += 1
    db.execute('INSERT INTO v4_vendor_event VALUES(?,?,?,?,?,?,?)',
               (p.tenant, vendor, state['revision'], kind, p.subject, now(), encode(state)))


def _actions(state):
    if state.get('semantic_binding_required') and state.get('semantic_binding_status') != 'REVIEWED':
        return []
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


def _view(db, p, vendor, state, *, governing_fees=(),trusted_now=None):
    artifact = _artifact(db, p, vendor, state['version'])
    audit = [dict(row) for row in db.execute(
        'SELECT revision,kind,actor,at FROM v4_vendor_event WHERE tenant=? AND vendor=? ORDER BY revision', (p.tenant, vendor))]
    state=_capability(db,p,vendor,state,governing_fees=governing_fees,trusted_now=trusted_now)
    result = {k: v for k, v in state.items() if k not in {'tests','public_source_document','public_source_diagnostic','public_source_issues'}}
    result.update(vendor_id=vendor, audit=audit, actions=[], sources=SOURCES)
    if state["state"] == "QUARANTINED":
        # Older append-only events may contain exception text from private input.
        reason = state.get("reason")
        result["reason"] = (reason if isinstance(reason, str) and reason in PUBLIC_QUARANTINE_REASONS
                            else "Source or overlay validation failed.")
        issues = public_issues(state.get('public_source_document'), state.get('public_source_diagnostic'))
        if issues:
            result['public_source_issues'] = issues
    if artifact:
        result.update(artifact)
        if vendor_bindings.required(artifact['manifest']):
            result['semantic_review_requirements'] = vendor_bindings.requirements(
                artifact['manifest'],artifact['overlay'],artifact['source_text'])
            result['semantic_review_requirements']['revision'] = state['revision']
    if p.role == 'reviewer' and not isinstance(p, DraftReviewer):
        result['actions'] = [{'id': _key(p, vendor, state, op), 'label': OPS[op], 'operation': op} for op in _actions(state)]
        if artifact and (grouping := artifact['manifest'].get('formula_grouping_review')):
            for action in result['actions']:
                if action['operation'] == 'interpret':
                    action['label'] = 'Accept reviewed availability formula ' + grouping['selected']
    return result


def catalog(path, p, *, governing_fees=(),trusted_now=None):
    with transaction(path, p) as db:
        rows = db.execute("""SELECT e.vendor,e.payload FROM v4_vendor_event e
            WHERE e.tenant=? AND revision=(SELECT MAX(revision) FROM v4_vendor_event v
            WHERE v.vendor=e.vendor AND v.tenant=e.tenant) ORDER BY e.vendor""", (p.tenant,))
        vendors = []
        for vendor, payload in rows:
            state = _capability(db,p,vendor,json.loads(payload),governing_fees=governing_fees,trusted_now=trusted_now)
            vendors.append({'vendor_id': vendor, **{key: state[key] for key in ('vendor', 'revision', 'version', 'state', 'active_version')}})
        return {'vendors': vendors}


def get_vendor(path, p, vendor, *, governing_fees=(),trusted_now=None):
    with transaction(path, p, vendor) as db:
        return _view(db, p, vendor, _tail(db, p, vendor),governing_fees=governing_fees,trusted_now=trusted_now)


def _fresh(old, vendor):
    return dict(vendor=vendor, version=None, state='DRAFT', revision=old['revision'] if old else 0,
                active_version=None, previous=None, reviewer=None, reviewer_kind=None,
                checks=[], tests=[], suite=None, test_author=None,semantic_binding=None)


def install(path, p, vendor, body, *, public_receipt=None):
    """`public_receipt` is a server-only seam resolved from an owned, pinned public proposal job.

    HTTP bodies never reach it. It is completely revalidated against the intake document
    here, and every other intake, quarantine, version and review gate is unchanged.
    """
    with transaction(path, p, vendor, write=True, draft=True) as db:
        old = _tail(db, p, vendor, required=False)
        state = _fresh(old, vendor)
        try:
            intake = Intake.model_validate(body)
            if public_receipt is None:
                manifest, extraction = staged_extraction(intake.document)
            else:
                manifest, extraction = job_extraction(intake.document, public_receipt)
            overlay = bind_overlay(manifest, intake.overlay)
        except (ValueError, OSError, TypeError, OverflowError) as exc:
            # Retain a safe digest and error category, never echo malformed/private raw inputs.
            reason = 'Source or overlay validation failed.'
            if isinstance(exc, ValidationError):
                reason = 'Invalid intake schema.'
            elif isinstance(exc, EconomicScopeReviewRequired):
                reason = SCOPE_REVIEW_REASON
            state.update(state='QUARANTINED', outcome=Outcome.UNSUPPORTED.value, rejected_digest=sha256(json.dumps(body, sort_keys=True, allow_nan=True).encode()).hexdigest(),
                         reason=reason)
            # Public diagnostics are independent of overlay success and always
            # accompany the generic refusal. Only an explicit offline attachment
            # for these exact approved public bytes may supply a source quote.
            try:
                document = Document.model_validate(body.get('document') if isinstance(body, dict) else None)
                attachment = selected_attachment(document)
                if attachment:
                    state.update(public_source_document=document.model_dump(), public_source_diagnostic=attachment)
            except (ValueError, TypeError):
                pass
            if (old and old.get('rejected_digest') == state['rejected_digest'] and old['state'] == 'QUARANTINED'
                    and old.get('public_source_diagnostic') == state.get('public_source_diagnostic')):
                return _view(db, p, vendor, old)
            _event(db, p, vendor, state, 'Quarantined intake; dispatch suspended')
            return _view(db, p, vendor, state)
        version = candidate_version(manifest, overlay, extraction)
        if old and old['version'] == version:
            return _view(db, p, vendor, old)
        artifact = {'semantics_revision':semantics_revision(manifest),'manifest': manifest, 'overlay': overlay, 'extraction': extraction, 'source_text': intake.document.text,
                    'generated_tests': generated_checks(manifest), 'source_received_at': now()}
        if not _artifact(db, p, vendor, version):
            db.execute('INSERT INTO v4_vendor_artifact VALUES(?,?,?,?)', (p.tenant, vendor, version, encode(artifact)))
        if old and old['active_version']:
            prior = _artifact(db, p, vendor, old['active_version'])
            if _compatible(prior,old['active_version']) and prior['manifest'] == manifest and prior['overlay'] == overlay:
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


def review_semantics(path,p,vendor,submission):
    with transaction(path,p,vendor,write=True) as db:
        state = _tail(db,p,vendor)
        if state['revision'] != submission.revision or state['state'] != 'SHADOW' or state['active_version']:
            raise ValueError('Semantic binding requires the current inactive shadow candidate.')
        artifact = _require_current(db,p,vendor,state['version'])
        if not vendor_bindings.required(artifact['manifest']):
            raise ValueError('This candidate has no unresolved literal definitions.')
        record = vendor_bindings.review_record(artifact['manifest'],artifact['overlay'],artifact['source_text'],
                                               p.tenant,p.subject,submission.review,now())
        record['reviewer_kind'] = 'scripted_test' if p.subject.startswith('scripted-') else 'authenticated_reviewer'
        digest = fingerprint(record)
        db.execute('INSERT INTO v4_vendor_semantic_review VALUES(?,?,?,?)',(p.tenant,vendor,digest,encode(record)))
        extraction = dict(artifact['extraction'],semantic_binding=digest)
        version = candidate_version(artifact['manifest'],artifact['overlay'],extraction)
        reviewed = dict(artifact,extraction=extraction)
        db.execute('INSERT INTO v4_vendor_artifact VALUES(?,?,?,?)',(p.tenant,vendor,version,encode(reviewed)))
        state.update(version=version,semantic_binding=digest,semantic_binding_required=True,semantic_binding_status='REVIEWED',
                     tests=[],checks=[],suite=None,test_author=None,reviewer=None,reviewer_kind=None,
                     interpretation_reviewer=None,previous=None)
        state.pop('formula_decision',None)
        _event(db,p,vendor,state,'Named pre-pricing source and literal evidence binding review')
        return _view(db,p,vendor,state)


def revoke_semantics(path,p,vendor,submission):
    with transaction(path,p,vendor,write=True) as db:
        state = _tail(db,p,vendor)
        if state['revision'] != submission.revision or not state.get('semantic_binding'):
            raise ValueError('A current semantic binding is required for revocation.')
        state.update(state='SHADOW',semantic_binding=None,semantic_binding_status='REVIEW_REQUIRED',active_version=None,
                     previous=None,tests=[],checks=[],suite=None,test_author=None,reviewer=None,reviewer_kind=None,
                     interpretation_reviewer=None)
        _event(db,p,vendor,state,'Revoked current semantic binding; immutable historical records retained')
        return _view(db,p,vendor,state)


def _fee_for(contexts,manifest,overlay,facts,tenant):
    from .governing_fees import require_governing_fee
    if type(contexts) is not tuple:
        raise ValueError('Trusted governing-fee contexts must be supplied as an immutable tuple.')
    matches=[]
    for context in contexts:
        try:matches.append(require_governing_fee(context,manifest,overlay,facts,tenant))
        except (ValueError,TypeError,KeyError):continue
    return matches[0] if len(matches)==1 else None


def submit_tests(path, p, vendor, submission, *, governing_fees=(),trusted_now=None):
    from .governing_fees import current_contexts
    governing_fees=current_contexts(path,p.tenant,governing_fees,trusted_now)
    with transaction(path, p, vendor, write=True, draft=True) as db:
        state = _tail(db, p, vendor)
        if state['revision'] != submission.revision or state['state'] != 'SHADOW':
            raise ValueError('Test submission requires the current shadow revision.')
        artifact = _require_current(db,p,vendor,state['version'])
        rows, outcomes, names = [], set(), set()
        manifest = artifact['manifest']
        distinguishes_grouping = False
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
            result = evaluate(artifact['manifest'], artifact['overlay'], test.facts, p.tenant,
                              bindings=binding_context_db(db,p,vendor,state,artifact),
                              governing_fee=_fee_for(governing_fees,manifest,artifact['overlay'],test.facts,p.tenant))
            actual = {k: result[k] for k in ('outcome', 'amount')}
            rows.append({'name': test.name, 'expected': expected, 'actual': actual, 'passed':
                         actual['outcome'] == expected['outcome'] and actual['amount'] == expected.get('amount')})
            if result.get('governing_fee_digest'):
                rows[-1]['governing_fee_digest']=result['governing_fee_digest']
            if manifest.get('formula_grouping_review') and rows[-1]['passed'] and actual['outcome'] == Outcome.ELIGIBLE:
                total, covered = result['total_microseconds'], result['downtime_microseconds']
                alternate_rate, _ = rate_for(manifest, manifest['scope']['product'], manifest['scope']['plan'] or '*',
                                             100 * total - covered, 100 * total)
                if alternate_rate == 0 and result['rate_units'] > 0:
                    distinguishes_grouping = True
        if manifest.get('formula_grouping_review'):
            rows.append({'name': 'Independent positive case distinguishes proposed availability formula grouping',
                         'passed': distinguishes_grouping})
        rows.append({'name': 'Independent positive and refusal coverage', 'passed':
                     Outcome.ELIGIBLE in outcomes and bool(outcomes - {Outcome.ELIGIBLE})})
        rows.append({'name': 'Generated exact threshold checks', 'passed': all(r['passed'] for r in artifact['generated_tests'])})
        state.update(tests=[t.model_dump() for t in submission.tests], checks=rows, test_author=p.subject, interpretation_reviewer=None)
        state.pop('formula_decision', None)
        state['suite'] = fingerprint({'tests':state['tests'],'pricing':[row.get('governing_fee_digest') for row in rows]}) if manifest.get('credit_rule') else fingerprint(state['tests'])
        if state.get('previous_suite') != state['suite']:
            state['previous'] = None
        _event(db, p, vendor, state, 'Executed reviewer-authored scenarios in shadow')
        return _view(db, p, vendor, state,governing_fees=governing_fees,trusted_now=trusted_now)



def shadow_preview(path, p, vendor, submission, *, governing_fee=None):
    with transaction(path, p, vendor, draft=True) as db:
        state = _tail(db, p, vendor)
        if state["revision"] != submission.revision or state["state"] != "SHADOW":
            raise ValueError("Preview requires the current shadow revision.")
        artifact = _require_current(db, p, vendor, state["version"])
        result = evaluate(artifact["manifest"], artifact["overlay"], submission.facts, p.tenant,
                          bindings=binding_context_db(db,p,vendor,state,artifact),governing_fee=governing_fee)
        return {"classification":"LOCAL_DRAFT_PREVIEW", "dispatch_authorized":False,
                "vendor_id":vendor, "revision":state["revision"], "evaluation":result}


def act(path, p, vendor, action, *, governing_fees=(),trusted_now=None):
    with transaction(path, p, vendor, write=True) as db:
        state = _tail(db, p, vendor)
        state = _capability(db,p,vendor,state,governing_fees=governing_fees,trusted_now=trusted_now)
        ops = {_key(p, vendor, state, op): op for op in _actions(state)}
        if action not in ops:
            raise ValueError('Stale or unavailable reviewer action.')
        op = ops[action]
        _require_current(db,p,vendor,state['version'])
        if op == 'interpret':
            state['interpretation_reviewer'] = p.subject
            artifact = _artifact(db, p, vendor, state['version'])
            if grouping := artifact['manifest'].get('formula_grouping_review'):
                state['formula_decision'] = {'selected': grouping['selected'], 'source_block': grouping['source_block'],
                                             'reviewer': p.subject, 'suite': state['suite'], 'version': state['version']}
        elif op == 'approve':
            if state.get('interpretation_required') and state.get('interpretation_reviewer') != p.subject:
                raise PermissionError('The approving reviewer must accept the cited source interpretation.')
            state.update(state='APPROVED', reviewer=p.subject,
                         reviewer_kind='scripted_test' if p.subject.startswith('scripted-') else 'authenticated_reviewer')
        elif op == 'activate':
            if state['reviewer'] != p.subject:
                raise PermissionError('Activation requires the same authenticated approving reviewer.')
            state.update(state='ACTIVE', active_version=state['version'])
        elif op == 'rollback':
            previous=state['previous']
            if previous and not _compatible(_artifact(db,p,vendor,previous),previous):
                previous=None
            state.update(state='REVOKED', active_version=previous, previous=None, reviewer=None)
        elif op == 'revoke':
            state.update(state='REVOKED', active_version=None, previous=None, reviewer=None)
        else:
            state.update(state='SHADOW', active_version=None, previous=None, checks=[], tests=[],
                         suite=None, reviewer=None, reviewer_kind=None, test_author=None, interpretation_reviewer=None)
        _event(db, p, vendor, state, OPS[op])
        return _view(db, p, vendor, state,governing_fees=governing_fees,trusted_now=trusted_now)


def dispatch(path, p, vendor, facts, *, governing_fee=None,governing_fees=(),trusted_now=None):
    with transaction(path, p, vendor, write=True) as db:
        state = _tail(db, p, vendor)
        if not state['active_version']:
            raise ValueError('An activated local adapter is required to create a workbench case.')
        version = state['active_version']
        artifact = _require_current(db,p,vendor,version)
        manifest, overlay = artifact['manifest'], artifact['overlay']
        result = evaluate(manifest, overlay, facts, p.tenant,bindings=binding_context_db(db,p,vendor,state,artifact),governing_fee=governing_fee)
        authority=governing_fees or ((governing_fee,) if governing_fee is not None else ())
        current=_capability(db,p,vendor,state,governing_fees=authority,trusted_now=trusted_now)
        if result['amount'] is not None and current.get('pricing_binding_status')=='REVIEW_REQUIRED':
            from .governing_fees import GoverningFeeRequired
            raise GoverningFeeRequired('Current pricing checks require fresh review before financial dispatch.')
        identity = [p.tenant, vendor, overlay['account'], overlay['agreement'], overlay['product'],overlay['plan'],facts.get('month')]
        if 'resource_id' in overlay:
            identity.append(overlay['resource_id'])
        if manifest.get('subscription') and overlay.get('subscription_record'):
            identity.append(overlay['subscription_record']['region'])
        # Case IDs retain their installation-specific history. Financial grouping
        # uses the contract's economic unit shared with filing reservations.
        case_id = 'availability-' + fingerprint(identity)
        try:
            economic_identity = vendor_economic_identity(p.tenant, manifest, overlay, facts.get('month'), version)
        except (KeyError, ValueError, TypeError):
            economic_identity = None  # An invalid observation can still be retained as a refusal.
        obligation = claim_key(**economic_identity) if economic_identity else None
        versions = list(_read_versions(db, p.tenant, case_id))
        if versions:
            saved = versions[-1]['payload']
            if (saved['observation_digest'] == result['observation_digest'] and saved['version'] == version
                    and saved.get('adapter_revision') == state['revision'] and saved.get('governing_fee_digest')==result.get('governing_fee_digest')):
                return saved
        at = now()
        doc = manifest['document']
        clauses = [dict(c, label=f'{doc["name"]}, clause {c["id"]}: {c["quote"]}', uri=doc['uri'],
                        source_sha256=doc['sha256']) for c in manifest['citations']]
        if governing := overlay.get('governing_terms'):
            # F6: the evidence digest is an operator-supplied reference. Nothing here verifies it against stored
            # signed evidence, so the citation says so rather than presenting it as verified customer evidence.
            clauses.append({'label':governing['source_ref'],'source':Source.CUSTOMER.value,'sha256':governing['evidence_sha256'],
                            'evidence_verification':'OPERATOR_SUPPLIED_UNVERIFIED',
                            'governing_source_sha256':governing['source_sha256'],'effective_from':governing['effective_from'],
                            'unamended_terms':governing['unamended_terms'],'uri':''})
        if period := overlay.get('billing_period'):
            clauses.append({'label':period['source_ref'],'quote':period['quote'],'source':Source.CUSTOMER.value,
                            'sha256':fingerprint(period),'uri':''})
        if override := overlay.get('override'):
            clauses.append({'label': override['source_ref'], 'quote': override['quote'], 'source': Source.CUSTOMER.value,
                            'sha256': fingerprint(override), 'uri': ''})
        received_at=artifact.get('source_received_at')
        if received_at is None:
            receipt=db.execute("SELECT at FROM v4_vendor_event WHERE tenant=? AND vendor=? AND json_extract(payload,'$.version')=? ORDER BY revision LIMIT 1",
                               (p.tenant,vendor,version)).fetchone()
            received_at=receipt[0] if receipt else None
        case = dict(result, id=case_id, vendor=manifest['vendor'], vendor_id=vendor, title='Monthly availability · ' + overlay['product'],
                    stage='EVALUATED', version=version, semantics_revision=artifact['semantics_revision'], obligation_id=obligation,
                    economic_identity=economic_identity, sources=SOURCES, clauses=clauses,
                    source_sha256=doc['sha256'], source_received_at=received_at,
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
        artifact = _require_current(db,p,vendor,state['active_version'])
        return {'semantics_revision':artifact['semantics_revision'],'version': state['active_version'], 'revision': state['revision'],
                'manifest': artifact['manifest'], 'overlay': artifact['overlay']}


def historical_economic_identity(path, tenant, case):
    """Project an old evaluation using its exact archived contract and observations.

    Current activation and evaluator code cannot rewrite historical scope. The
    immutable snapshot and archived artifact must agree before grouping money.
    """
    if not case.get('vendor_id') or not case['id'].startswith('availability-'):
        return None
    with database(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='v4_vendor_artifact'").fetchone():
            return None
        row = db.execute('SELECT payload FROM v4_vendor_artifact WHERE tenant=? AND vendor=? AND version=?',
                         (tenant, case['vendor_id'], case['version'])).fetchone()
    if row is None:
        raise ValueError('Historical evaluation has no bound contract artifact.')
    artifact = json.loads(row[0])
    manifest, overlay = artifact['manifest'], artifact['overlay']
    archived_version = fingerprint({k:artifact[k] for k in ('manifest','overlay','extraction','semantics_revision')})
    if (archived_version != case['version'] or manifest['vendor'] != case['vendor']
            or overlay['account'] != case['account'] or overlay['agreement'] != case['agreement']
            or sha256(artifact['source_text'].encode()).hexdigest() != manifest['document']['sha256']):
        raise ValueError('Historical evaluation and contract identity disagree.')
    observations = [e['detail'] for e in case.get('evidence', []) if isinstance(e.get('detail'), dict)
                    and fingerprint(e['detail']) == case.get('observation_digest')]
    if len(observations) != 1:
        raise ValueError('Historical evaluation has no exact bound observation.')
    try:
        return vendor_economic_identity(tenant, manifest, overlay, observations[0].get('month'), case['version'])
    except EconomicScopeReviewRequired:
        raise
    except (KeyError, ValueError, TypeError):
        if case.get('outcome') == Outcome.ELIGIBLE.value:
            raise ValueError('Eligible historical evaluation has unresolved economic scope.')
        return None


def require_case_semantics(path, tenant, case, *, governing_fees=(),trusted_now=None):
    """Current money requires current authority; never rewrite archived snapshots."""
    if not case.get('vendor_id') or not case['id'].startswith('availability-'):
        return
    with database(path) as db:
        p = Principal(tenant, 'local-semantic-projection', 'viewer')
        artifact = _artifact(db, p, case['vendor_id'], case['version'])
        if artifact and vendor_bindings.required(artifact['manifest']):
            context = binding_context_db(db, p, case['vendor_id'], artifact=artifact)
            vendor_bindings.require_context(artifact['manifest'], artifact['overlay'], tenant, context)
        if artifact and artifact['manifest'].get('credit_rule') and case.get('amount') is not None:
            from .governing_fees import context_for_digest,GoverningFeeRequired
            state=_tail(db,p,case['vendor_id'])
            current=_capability(db,p,case['vendor_id'],state,governing_fees=governing_fees,trusted_now=trusted_now)
            if current.get('pricing_binding_status')=='REVIEW_REQUIRED':
                raise GoverningFeeRequired('Current governing-fee checks require review.')
            observations=[e['detail'] for e in case.get('evidence',[]) if isinstance(e.get('detail'),dict)
                          and fingerprint(e['detail'])==case.get('observation_digest')]
            context_for_digest(path,tenant,case.get('governing_fee_digest'),artifact['manifest'],artifact['overlay'],
                               observations[0] if len(observations)==1 else {},governing_fees,trusted_now)


def resolve_case(path, p, case_id, *, require_active=True,governing_fees=(),trusted_now=None):
    """Resolve a previously dispatched estimate with its bound current agreement; never infer an award."""
    with transaction(path, p) as db:
        versions = list(_read_versions(db, p.tenant, case_id))
        if not versions:
            raise KeyError(case_id)
        case = versions[-1]['payload']
        if not case_id.startswith('availability-') or not case.get('vendor_id'):
            raise ValueError('Case is not an integrity-verified availability evaluation.')
        state = _tail(db, p, case['vendor_id'])
        if require_active and (state['active_version'] != case['version'] or state['revision'] != case.get('adapter_revision')):
            raise ValueError('The governing adapter is no longer active. Historical evaluation is preserved.')
        artifact = _artifact(db, p, case['vendor_id'], case['version'])
        if require_active and not _compatible(artifact,case['version']):
            raise ValueError('Historical case uses an incompatible evaluator revision.')
        if not artifact or (artifact['overlay']['agreement'], artifact['overlay']['account']) != (case['agreement'], case['account']):
            raise ValueError('Case agreement or account binding is inconsistent.')
        if require_active:
            vendor_bindings.require_context(artifact['manifest'], artifact['overlay'], p.tenant,
                                           binding_context_db(db,p,case['vendor_id'],state,artifact))
        if require_active:
            require_case_semantics(path,p.tenant,case,governing_fees=governing_fees,trusted_now=trusted_now)
        return case


def evaluate_active_db(db, p, vendor, facts, *, expected_version=None, expected_revision=None, governing_fee=None,governing_fees=(),trusted_now=None):
    """Evaluate with the active tenant-scoped version inside the caller's existing transaction."""
    if not isinstance(p,Principal) or not p.tenant or not p.subject or p.role not in {'viewer','reviewer'}:
        raise PermissionError('Authenticated tenant principal required.')
    state=_tail(db,p,vendor)
    version=state['active_version']
    if (not version or expected_version is not None and expected_version!=version
            or expected_revision is not None and expected_revision!=state['revision']):
        raise ValueError('Stale or inactive resource adapter binding.')
    artifact=_require_current(db,p,vendor,version)
    manifest,overlay=artifact['manifest'],artifact['overlay']
    result=evaluate(manifest,overlay,facts,p.tenant,bindings=binding_context_db(db,p,vendor,state,artifact),governing_fee=governing_fee)
    authority=governing_fees or ((governing_fee,) if governing_fee is not None else ())
    current=_capability(db,p,vendor,state,governing_fees=authority,trusted_now=trusted_now)
    if result['amount'] is not None and current.get('pricing_binding_status')=='REVIEW_REQUIRED':
        result={key:value for key,value in result.items() if key not in
                {'governing_fee_cents','governing_fee_digest','governing_pricing_version','pricing_as_of','service_estimate'}}
        result.update(outcome=Outcome.MISSING.value,amount=None,trace=['Current governing-fee checks require review.'],missing=['current_pricing_review'])
    return dict(result,version=version,semantics_revision=artifact['semantics_revision'],revision=state['revision'],manifest_digest=fingerprint(manifest),
                source_sha256=manifest['document']['sha256'],overlay_digest=fingerprint(overlay),
                vendor_id=vendor,agreement=overlay['agreement'],account=overlay['account'],resource_id=overlay.get('resource_id'))


def evaluate_active(path,p,vendor,facts,*,expected_version=None,expected_revision=None,governing_fee=None,governing_fees=(),trusted_now=None):
    with transaction(path,p,vendor) as db:
        return evaluate_active_db(db,p,vendor,facts,expected_version=expected_version,expected_revision=expected_revision,governing_fee=governing_fee,governing_fees=governing_fees,trusted_now=trusted_now)
