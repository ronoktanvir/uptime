"""Exercise a pre-frozen local cohort over actual authenticated application routes.

No application functions, routes, providers, or dependency overrides are replaced.
The existing correspondence clock seam is explicitly configured for synthetic time.
Only offline identity/source enrollment and exact signed mandate installation write
configuration; all tested application behavior uses HTTP. No external network.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.adequate_holdout.witness import LABEL, ADDITIVE_LABEL, Witness, canonical, digest, verify_freeze
from scripts.adequate_holdout.projection import bind_shadow, filing_fields, pin_original, project_facts, project_record, source_categories
from scripts.adequate_holdout.scoring import score_case


BASE = ('candidate', 'shadow_refusal', 'shadow_tests', 'interpretation_review', 'approval', 'activation',
        'evaluation', 'case_audit', 'rollback', 'rollback_refusal', 'historical_audit', 'changed_version_refusal')
DENIAL = ('claim_open', 'signed_records', 'original_filing', 'denial_delivery', 'denial_outcome')
CURE = ('artifact_delivery', 'response_approval', 'response_submit')


def schedule(case):
    required = list(BASE)
    if case['denial_text']:
        required += list(DENIAL)
    if case['supplement']:
        required += list(CURE)
    elif case.get('original_contract') and case['denial_text']:
        # Additive cohort checks both successful responses and actual refusal to offer one.
        required += list(CURE[1:])
    return required


def save(path, value):
    with path.open('x') as file:
        json.dump(value, file, indent=2, sort_keys=True, allow_nan=False)
        file.write('\n')
    path.chmod(0o600)
    return digest(path.read_bytes())


def tree_state(root):
    """Hash every application source, fixture, lockfile and asset without reporting contents."""
    paths = []
    for directory in ('uptime', 'fixtures', 'web', 'prospective/public'):
        paths.extend(p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts
                     and p.suffix not in {'.pyc', '.sqlite', '.db'})
    paths.extend(root/name for name in ('pyproject.toml', 'uv.lock') if (root/name).exists())
    hashes = {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(paths)}
    if (root/'.adequate-pinned-sha').exists():
        revision = (root/'.adequate-pinned-sha').read_text().strip()
    else:
        revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    return dict(sha=revision, tree_sha256=digest(canonical(hashes)), files=hashes)


def archive_source(root, target):
    """Every attempt imports its own detached source; mutable main is never imported."""
    if (root/'.adequate-pinned-sha').is_file():
        shutil.copytree(root, target, ignore=shutil.ignore_patterns('.git', '.venv', '__pycache__', '.pytest_cache'))
    else:
        import io
        import tarfile
        revision = subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        archive = subprocess.check_output(['git','-C',str(root),'archive',revision])
        target.mkdir(mode=0o700)
        with tarfile.open(fileobj=io.BytesIO(archive)) as saved:
            saved.extractall(target, filter='data')
        (target/'.adequate-pinned-sha').write_text(revision+'\n')
    return target


class Clock:
    def __init__(self, at):
        self.at = datetime.fromisoformat(at.replace('Z', '+00:00'))

    def __call__(self):
        return self.at

    def advance(self, at):
        value = datetime.fromisoformat(at.replace('Z', '+00:00'))
        if value < self.at:
            raise ValueError('Synthetic clock cannot go backwards within a case')
        self.at = value


@contextmanager
def transport(app, kind, origin, listener):
    if kind == 'testclient':
        from fastapi.testclient import TestClient
        with TestClient(app, base_url=origin, client=('127.0.0.1', 41221), raise_server_exceptions=False) as client:
            yield client
        return
    import httpx
    import uvicorn
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', access_log=False, log_level='error', proxy_headers=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets':[listener]}, daemon=True)
    thread.start()
    try:
        until = time.monotonic()+15
        while not server.started:
            if time.monotonic()>until or not thread.is_alive():
                raise RuntimeError('Local socket server failed to start')
            time.sleep(.02)
        with httpx.Client(base_url=origin, trust_env=False, timeout=30) as client:
            yield client
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()


class Session:
    def __init__(self, app, client, origin, db, directory, issuer_key, reviewer_key, subject, tenant):
        from uptime.auth_client import ReviewerClient
        self.app, self.client, self.origin, self.db = app, client, origin, db
        self.directory, self.issuer_key, self.subject, self.tenant = directory, issuer_key, subject, tenant
        self.signed = ReviewerClient(client, origin, subject, reviewer_key)
        self.counter = 0
        self.last_digest = None
        self.trace = []

    def mandate(self, path, payload, claim=None):
        from uptime import mandates
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        description = mandates.describe(self.db, self.subject)
        now = int(time.time())
        raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        body = dict(schema_version='uptime-reviewer-mandate/1', mandate_id=str(uuid.uuid4()),
                    **description, issuer='adequate-independent-issuer', valid_from=now-5, valid_until=now+300,
                    path=path, body_sha256=digest(raw), claim=claim)
        mandate = mandates.Mandate.model_validate(body)
        key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(self.issuer_key))
        signed = dict(mandate=mandate.model_dump(mode='json'), signature=key.sign(mandate.signing_bytes()).hex())
        mandates.install(self.db, signed)
        save(self.directory/f'mandate-{self.counter+1:04d}-{uuid.uuid4().hex[:8]}.private.json', signed)

    def capture(self, method, path, response):
        self.counter += 1
        try:
            body = response.json()
        except ValueError:
            body = {'raw':response.text}
        row = dict(sequence=self.counter, method=method, path=path, status=response.status_code, body=body)
        self.last_digest = save(self.directory/f'http-{self.counter:04d}.private.json', row)
        self.trace.append(dict(sequence=self.counter, status=response.status_code, sha256=self.last_digest))
        return response.status_code, body

    def post(self, path, payload, claim=None):
        self.mandate(path, payload, claim)
        return self.capture('POST', path, self.signed.post(path, payload))

    def get(self, path):
        return self.capture('GET', path, self.client.get(path, headers=self.signed.headers))

    def event(self, claim_id, scope, body, sender, event_id):
        from uptime.auth_client import service_headers
        path = f'/api/correspondence/claims/{claim_id}/events'
        raw = json.dumps(dict(event_id=event_id, scope=scope, body=body), separators=(',', ':'),
                         ensure_ascii=False, allow_nan=False).encode()
        headers = service_headers(instance=self.app.state.auth.instance, origin=self.origin,
                                  subject=sender.subject, key=sender, path=path, body=raw, tenant=self.tenant)
        status, receipt = self.capture('POST', path, self.client.post(path, content=raw, headers=headers))
        if status == 200:
            # Event intake returns a delivery receipt, not the refreshed case.
            get_status, detail = self.get(f'/api/correspondence/claims/{claim_id}')
            if get_status != 200:
                return get_status, detail
            return status, detail
        return status, receipt


class Halt(Exception):
    pass


def run_case(case, bundle, keys, manifest, args, attempt, public_text):
    from uptime.server import create_app
    from uptime.auth import enroll
    from uptime.auth_keys import generate_reviewer_key
    from uptime import mandates
    from uptime.source_config import SourceConfig, SenderCredential
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    case = deepcopy(case)
    # Public title to private order mapping, from the already frozen source bytes.
    # This changes neither the customer's identity nor any observation.
    overlay = dict(case['overlay'], public_agreement=public_text.splitlines()[0])
    cid = case['id']
    directory = attempt/cid
    directory.mkdir(mode=0o700)
    witness = Witness(schedule(case))
    measured = {}
    exclusions = source_categories(public_text)
    listener = None
    if args.transport == 'socket':
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        port = listener.getsockname()[1]
    else:
        port = 18763
    origin = f'http://127.0.0.1:{port}'
    db = directory/'application.sqlite'
    tenant, subject = 'adequate-tests', 'adequate-scripted-evaluator'
    reviewer = generate_reviewer_key()
    save(directory/'reviewer.private.json', reviewer)
    enroll(db, subject, reviewer, mode='replay', tenant=tenant)
    public = lambda role: Ed25519PrivateKey.from_private_bytes(bytes.fromhex(keys[role])).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    services = [dict(subject='adequate-'+role, source=role, scope=case['scope'], public_key=public(role))
                for role in ('status','billing','customer','vendor')]
    config = SourceConfig.model_validate(dict(version=1, channel='LOCAL_SYNTHETIC', tenant=tenant,
                                              mode='replay', origin=origin, services=services))
    senders = {role:SenderCredential.model_validate(dict(version=1, channel='LOCAL_SYNTHETIC', tenant=tenant,
                mode='replay', origin=origin, subject='adequate-'+role, source=role, scope=case['scope'], private_key=keys[role]))
               for role in ('status','billing','customer','vendor')}
    app = create_app(db, mode='replay', approvals_enabled=True, tenant=tenant, origin=origin,
                     service_credentials=config.credentials('replay', origin, tenant))
    config.bind(app.state.correspondence)
    clock = Clock(case['run_clock'])
    # Existing documented test clock configuration; all handlers, resolvers and stores are unchanged.
    app.state.correspondence.clock = clock
    if app.dependency_overrides:
        raise RuntimeError('Application dependency overrides are prohibited')
    mandates.register_issuer(db, dict(subject='adequate-independent-issuer', public_key=public('issuer'),
                            local_purposes=('workspace','claim-filing','vendor-promotion','policy-change')))
    # Check original frozen source signatures before projecting them onto the wire.
    for record in case['records'].values():
        a = record['authority']
        signed = dict(scope=case['scope'], body=record['event_body'], source=a['role'])
        if digest(canonical(signed)) != a['frozen_assertion_sha256']:
            raise ValueError('Frozen source assertion digest mismatch')
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(a['public_key'])).verify(bytes.fromhex(a['frozen_signature']), canonical(signed))
    if case.get('original_contract') and not case.get('original_authority'):
        raise ValueError('Original source/version commitment lacks its independent signature')
    if case.get('original_authority'):
        a = case['original_authority']
        signed = dict(scope=case['scope'],body=case['original_filing'],original_contract=case['original_contract'],source='vendor')
        if digest(canonical(signed)) != a['frozen_assertion_sha256']:
            raise ValueError('Original filing commitment changed')
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(a['public_key'])).verify(bytes.fromhex(a['frozen_signature']),canonical(signed))
    session = None
    try:
        with transport(app, args.transport, origin, listener) as client:
            session = Session(app, client, origin, db, directory, keys['issuer'], reviewer, subject, tenant)
            prefix = '/api/vendors/adequate-'+cid
            def mark(name, passed, reason=None):
                witness.record(name, measured=True, passed=bool(passed), evidence=session.last_digest,
                               reason=None if passed else reason or 'PREDICATE_MISMATCH')
            def needed(name, condition, reason):
                mark(name, condition, reason)
                if not condition:
                    raise Halt(reason)
            def transition(state, op):
                actions = [a['id'] for a in state.get('actions',[]) if a['operation'] == op]
                if len(actions) != 1:
                    return 0, {'local_error':'ACTION_NOT_OFFERED', 'operation':op}
                return session.post(prefix+'/actions/'+actions[0], {})
            document = dict(name='CalyxQuay Beacon Cache', uri='urn:synthetic:calyxquay:beacon-cache:CQ-2031-04',
                            classification='synthetic_public', text=public_text)
            status, state = session.post(prefix+'/candidates', dict(document=document, overlay=overlay))
            needed('candidate', status == 200 and state.get('state') == 'SHADOW', 'CANDIDATE_REFUSED')
            candidate_version = state['version']
            status, _ = session.post(prefix+'/evaluate', {'facts':project_facts(case['facts'])})
            mark('shadow_refusal', status == 409, 'SHADOW_DISPATCH_NOT_REFUSED')
            # Shadow fixtures are separately authored and never used as private cohort gold.
            # Their explicit, hypothetical receipt material is local reviewer test data only.
            tests = []
            for template in bundle['shadow_templates']:
                test = bind_shadow(template, overlay)
                f = test['facts']
                invoice = project_record(dict(kind='service_invoice',content=f['service_invoice']['content'],
                                              source_ref=f['service_invoice']['ref']), exclusions)
                f['service_invoice'].update(content=invoice['content'],content_sha256=invoice['content_sha256'])
                tests.append(test)
            save(directory/'independent-shadow.private.json', tests)
            status, state = session.post(prefix+'/tests', dict(revision=state['revision'] if 'revision' in state else 1, tests=tests))
            needed('shadow_tests', status == 200 and bool(state.get('checks')) and all(c['passed'] for c in state['checks']), 'SHADOW_EXPECTATIONS_FAILED')
            if state.get('interpretation_required'):
                status, state = transition(state, 'interpret')
                needed('interpretation_review', status == 200, 'INTERPRETATION_REFUSED')
            else:
                mark('interpretation_review', True)
            status, state = transition(state, 'approve')
            needed('approval', status == 200 and state.get('state') == 'APPROVED', 'APPROVAL_REFUSED')
            status, active = transition(state, 'activate')
            needed('activation', status == 200 and active.get('active_version') == candidate_version, 'ACTIVATION_REFUSED')
            # Projection retains missing scope and missing records. It never fills a historical receipt.
            facts = project_facts(case['facts'])
            for kind in ('service_monitor','service_invoice'):
                if kind in facts:
                    b = project_record(case['records'][kind]['event_body'], exclusions)
                    facts[kind].update(content=b['content'],content_sha256=b['content_sha256'])
            # Full identity is the frozen signed envelope's scope, not an assertion about received fields.
            proof = facts.get('filing_proof')
            if proof:
                proof.update({k:case['facts'][k] for k in ('agreement','product','plan','month')})
            status, result = session.post(prefix+'/evaluate', {'facts':facts})
            measured['evaluation'] = dict(status=status,result=result)
            mark('evaluation', status == 200, 'EVALUATION_HTTP_REFUSED')
            case_id = result.get('id')
            if case_id:
                status, audit = session.get('/api/cases/'+case_id)
                mark('case_audit', status == 200 and audit.get('version') == candidate_version
                     and audit.get('outcome') == result.get('outcome') and audit.get('amount') == result.get('amount'), 'CASE_AUDIT_MISMATCH')
            if case['denial_text']:
                try:
                    exercise_denial(case,session,senders,clock,exclusions,witness,measured,public_text)
                except Halt:
                    pass
                except Exception:
                    (directory/'denial-error.private.txt').write_text(traceback.format_exc())
            status, rolled = transition(active, 'rollback')
            mark('rollback', status == 200 and not rolled.get('active_version'), 'ROLLBACK_FAILED')
            status, _ = session.post(prefix+'/evaluate', {'facts':facts})
            mark('rollback_refusal', status == 409, 'ROLLBACK_DISPATCH_NOT_REFUSED')
            if case_id:
                status, audit = session.get('/api/cases/'+case_id)
                mark('historical_audit', status == 200 and audit.get('version') == candidate_version, 'HISTORY_LOST')
            changed = deepcopy(overlay)
            changed['fee_line_ref'] += '-changed-version'
            status, changed_state = session.post(prefix+'/candidates', dict(document=document, overlay=changed))
            changed_ok = status == 200 and changed_state.get('version') != candidate_version and not changed_state.get('active_version')
            status, _ = session.post(prefix+'/evaluate', {'facts':facts})
            mark('changed_version_refusal', changed_ok and status == 409, 'CHANGED_VERSION_NOT_REFUSED')
    except Halt:
        pass
    except Exception:
        (directory/'error.private.txt').write_text(traceback.format_exc())
    report = witness.report()
    report['measurements'] = measured
    report['scored'] = False
    save(directory/'witness.private.json', report)
    if session:
        save(directory/'http-index.private.json', session.trace)
    return report


def exercise_denial(case, session, senders, clock, exclusions, witness, measured, public_text):
    claim_id = 'inbox-adequate-'+case['id']
    base = '/api/correspondence/claims/'+claim_id
    def mark(name, condition, reason):
        witness.record(name, measured=True, passed=bool(condition), evidence=session.last_digest,
                       reason=None if condition else reason)
        if not condition:
            raise Halt(reason)
    status, detail = session.post('/api/correspondence/claims', dict(claim_id=claim_id, scope=case['scope']))
    mark('claim_open',status == 200,'CLAIM_OPEN_REFUSED')
    passed = True
    for number,(kind,record) in enumerate(case['records'].items()):
        body = project_record(record['event_body'], exclusions)
        role = record['authority']['role']
        status, detail = session.event(claim_id,case['scope'],body,senders[role],case['id']+'-record-'+str(number))
        passed &= status == 200
    mark('signed_records',passed,'SIGNED_RECORD_REFUSED')
    if case.get('filing_material'):
        status, detail = session.event(claim_id,case['scope'],case['filing_material'],senders['customer'],case['id']+'-filing-material')
        measured['filing_material'] = dict(status=status,detail=detail)
    if case['original_method'] == 'ordinary_approved_submission':
        if not case.get('filing_material'):
            # Prospective preparation is distinct from an imported historical receipt.
            fields = filing_fields(case['scope'],case['overlay'],case['records']['service_invoice']['event_body'])
            body = dict(kind='filing_material',source_ref='outgoing-material-'+case['id'],observed_at=clock().isoformat(),
                        channel=case['original_filing']['submitted_to'],fields=fields)
            status, detail = session.event(claim_id,case['scope'],body,senders['customer'],case['id']+'-outgoing-material')
        try:
            for action in ('approve-claim','submit-claim'):
                detail = authorized_action(session,base,detail,action)
        except Halt as error:
            measured['original_action_refusal'] = dict(reason=str(error),view=detail)
            mark('original_filing',False,str(error))
        originals = [s for s in detail.get('submissions',[]) if s['action'] == 'submit-claim']
        measured['original_submissions'] = originals
        mark('original_filing',len(originals) == 1, 'ORIGINAL_FILING_NOT_ESTABLISHED')
        receipt = originals[0]['id']
    else:
        status, view = session.get(base)
        body = pin_original(case,view,public_text)
        save(session.directory/'original-wire.private.json',body)
        status, detail = session.event(claim_id,case['scope'],body,senders['vendor'],case['id']+'-original')
        mark('original_filing',status == 200 and any(e.get('receipt_id') == case['original_filing']['receipt_id'] for e in detail.get('evidence',[])), 'ORIGINAL_RECEIPT_REFUSED')
        receipt = case['original_filing']['receipt_id']
    body = dict(kind='message',receipt_id=receipt,text=case['denial_text'])
    status, detail = session.event(claim_id,case['scope'],body,senders['vendor'],case['id']+'-denial')
    mark('denial_delivery',status == 200 and any(r.get('text') == case['denial_text'] for r in detail.get('replies',[])), 'DENIAL_NOT_WITNESSED')
    if case['supplement']:
        # Every attachment byte was frozen originally; delivery happens only after the independent request.
        clock.advance(case['supplement'][0]['observed_at'])
        passed = True
        for n,body in enumerate(case['supplement']):
            role = 'customer' if body['kind'] == 'artifact' else 'billing'
            status, detail = session.event(claim_id,case['scope'],body,senders[role],case['id']+'-supplement-'+str(n))
            passed &= status == 200
        mark('artifact_delivery',passed,'FROZEN_CURE_REFUSED')
    measured['denial_view'] = detail
    mark('denial_outcome',True,'SCORING_PENDING')
    # The action schedule depends only on offered public actions, never on gold.
    for action,stage in (('approve-response','response_approval'),('submit-response','response_submit')):
        if action == 'submit-response' and detail.get('next_contact'):
            contact = datetime.fromisoformat(detail['next_contact'].replace('Z','+00:00'))
            if contact > clock():
                clock.advance(detail['next_contact'])
            _,detail = session.get(base)
        offered = any(a['id']==action for a in detail.get('actions',[]))
        result = dict(offered=offered,executed=False)
        if offered:
            try:
                detail = authorized_action(session,base,detail,action)
                result['executed'] = True
            except Halt as error:
                result['error'] = str(error)
        result['view'] = detail
        measured[stage] = result
        if stage in witness.required:
            witness.record(stage,measured=True,passed=True,evidence=session.last_digest)
    status,audit = session.get(base)
    measured['final_correspondence'] = audit
    save(session.directory/'final-correspondence.private.json',audit)


def authorized_action(session, base, detail, action):
    offers = [a for a in detail.get('actions',[]) if a['id']==action]
    if len(offers) != 1:
        # Preserve the missing offered action and the ordinary route refusal as an observation.
        # An absent exact packet digest cannot authorize a financial action.
        raise Halt('FINANCIAL_ACTION_NOT_OFFERED')
    binding = deepcopy(offers[0]['mandate_claim'])
    # Exact local SCRIPTED_TEST mandate for the offered packet. The separate
    # scorer verifies its actual amount against frozen independent gold later.
    status,result = session.post(base+'/actions/'+action,{},claim=binding)
    if status != 200:
        raise Halt('EXACT_ACTION_REFUSED')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root',type=Path,required=True)
    parser.add_argument('--cohort',type=Path,required=True)
    parser.add_argument('--shadow-cohort',type=Path,help='Separately frozen, fully specified reviewer scenarios')
    parser.add_argument('--extractions',type=Path,required=True)
    parser.add_argument('--transport',choices=('testclient','socket'),required=True)
    parser.add_argument('--public-report',type=Path,required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.public_report.exists():
        raise FileExistsError('Public reports are create-only; choose a new path')
    args.app_root=args.app_root.resolve();args.cohort=args.cohort.resolve();args.extractions=args.extractions.resolve()
    harness_root=Path(__file__).resolve().parent
    if args.cohort.is_relative_to(harness_root.parents[1]):
        raise ValueError('Private cohort and attempt artifacts must be outside the repository')
    manifest,manifest_hash=verify_freeze(args.cohort)
    shadow_root=(args.shadow_cohort or args.cohort).resolve()
    shadow_manifest,shadow_hash=verify_freeze(shadow_root)
    if shadow_manifest['source_sha256'] != manifest['source_sha256']:
        raise ValueError('Reviewer scenarios must use the same frozen public source')
    extraction=args.extractions/(manifest['source_sha256']+'.json')
    extraction_hash=digest(extraction.read_bytes())
    attempt=args.cohort/'attempts'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    attempt.mkdir(parents=True,mode=0o700,exist_ok=False)
    harness_before={p.name:digest(p.read_bytes()) for p in sorted(harness_root.glob('*.py'))}
    (attempt/'harness-source').mkdir(mode=0o700)
    for name in harness_before:
        shutil.copyfile(harness_root/name,attempt/'harness-source'/name)
    extraction_root=attempt/'public-extractions'
    extraction_root.mkdir(mode=0o700)
    shutil.copyfile(extraction,extraction_root/extraction.name)
    args.app_root=archive_source(args.app_root,attempt/'app-source')
    source=args.app_root/manifest['source_path']
    if digest(source.read_bytes()) != manifest['source_sha256']:
        raise ValueError('Pinned application public source differs from frozen approved source')
    # App imports occur only after verification of the saved freeze. Ambient provider credentials are removed.
    for name in list(os.environ):
        if name.startswith(('RAMP_','ANTHROPIC_','OPENAI_','CLAUDE_')):
            os.environ.pop(name)
    os.environ.update(UPTIME_PUBLIC_EXTRACTIONS=str(extraction_root),UPTIME_MODEL_PROPOSITIONS='1')
    sys.path.insert(0,str(args.app_root))
    import uptime
    if not Path(uptime.__file__).resolve().is_relative_to(args.app_root):
        raise RuntimeError('Application import escaped the attempt source archive')
    before=tree_state(args.app_root)
    save(attempt/'source-before.private.json',before)
    inputs=json.loads((args.cohort/'inputs.private.json').read_text())
    shadow=json.loads((shadow_root/'inputs.private.json').read_text())
    keys=json.loads((args.cohort/'keys.private.json').read_text())
    observations=[]
    for case in inputs['cases']:
        try:
            observations.append(run_case(case,shadow,keys,manifest,args,attempt,source.read_text()))
        except Exception:
            (attempt/(case['id']+'-setup-error.private.txt')).write_text(traceback.format_exc())
            observations.append(Witness(schedule(case)).report())
    # Freeze the complete observation transcript before loading private expected results.
    observation_hash=save(attempt/'observed.private.json',observations)
    gold=json.loads((args.cohort/'gold.private.json').read_text())
    gold_by_id={r['id']:r for r in gold['cases']}
    if set(gold_by_id) != {c['id'] for c in inputs['cases']}:
        raise ValueError('Gold and input denominators differ')
    reports=[score_case(observed,gold_by_id[case['id']]) for case,observed in zip(inputs['cases'],observations,strict=True)]
    after=tree_state(args.app_root)
    save(attempt/'source-after.private.json',after)
    _,after_manifest_hash=verify_freeze(args.cohort)
    _,after_shadow_hash=verify_freeze(shadow_root)
    harness_after={p.name:digest(p.read_bytes()) for p in sorted(harness_root.glob('*.py'))}
    stable=(before==after and manifest_hash==after_manifest_hash and shadow_hash==after_shadow_hash
            and harness_before==harness_after and extraction_hash==digest(extraction.read_bytes())
            and extraction_hash==digest((extraction_root/extraction.name).read_bytes()))
    sums={name:sum(r[name] for r in reports) for name in ('required','measured','passed','failed','unmeasured')}
    per_stage={stage:{'required':sum(stage in r['observations'] for r in reports),
                      'measured':sum(r['observations'].get(stage,{}).get('measured',False) for r in reports),
                      'passed':sum(r['observations'].get(stage,{}).get('passed',False) for r in reports)}
               for stage in BASE+DENIAL+CURE}
    public=dict(label=manifest['label'],classification=manifest['classification'],vendor_population_generalization=False,
                virgin_public_vendor_firstpass=False,authority='SCRIPTED_TEST',human_approval=False,
                reviewer_application_label='authenticated_reviewer; automated local named credential, no human approval',
                original_cohorts=dict(touched=False,recounted=False,failed_first_pass_counts='unchanged'),
                tested_app_sha=before['sha'],app_tree_sha256_before=before['tree_sha256'],app_tree_sha256_after=after['tree_sha256'],
                stable_before_after=stable,source_sha256=manifest['source_sha256'],manifest_sha256=manifest_hash,
                detached_source=True,shadow_manifest_sha256=shadow_hash,harness_sha256=digest(canonical(harness_before)),
                harness_stable_before_after=harness_before==harness_after,
                observations_sha256=observation_hash,scoring='gold parsed only after complete observation transcript was saved; hashes checked before and after',
                extraction_sha256=extraction_hash,inputs_sha256=manifest['files']['inputs.private.json'],gold_sha256=manifest['files']['gold.private.json'],
                transport=args.transport,clock='existing correspondence clock configured explicitly from frozen synthetic UTC time',
                dependencies={n:importlib.metadata.version(n) for n in ('fastapi','httpx','pydantic','cryptography','uvicorn')},
                cohort_count=len(reports),complete_case_passes=sum(r['all_green'] for r in reports),
                aggregates=sums,stages=per_stage,all_green=stable and all(r['all_green'] for r in reports),
                limitations=['Studied fictional public vendor; separate in-family denominators; no vendor generalization.',
                            'Original 10-case denominator and all completed attempts remain unchanged.',
                            'Original empty filing fields are inadequate test design and cannot be synthesized.',
                            'Historical receipt fields are never inferred from current evidence.',
                            'Public GET pins require an explicit independently frozen original source/version/order commitment.',
                            'Fully specified additive scenarios are also used as separate reviewer templates.'],
                frozen_at=manifest['frozen_at'],exercised_at=datetime.now(timezone.utc).isoformat())
    public['attempt_evidence_sha256']=save(attempt/'outcomes.private.json',reports)
    save(attempt/'public-report.json',public)
    args.public_report.parent.mkdir(parents=True,exist_ok=True)
    save(args.public_report,public)
    print(json.dumps({k:public[k] for k in ('label','tested_app_sha','stable_before_after','cohort_count','complete_case_passes','aggregates','all_green')}))
    return 0 if public['all_green'] else 1


if __name__=='__main__':
    raise SystemExit(main())
