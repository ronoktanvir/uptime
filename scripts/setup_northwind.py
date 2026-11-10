#!/usr/bin/env python3
"""Create an isolated authored workspace and seed through signed public services.

The protected directory contains fictional runtime credentials. It is never a
Ramp customer database, real authorization, or external-source attestation.
"""
from copy import deepcopy
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import stat
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from fixtures.northwind.loader import load_package,build_fee_registry
from uptime.auth import SCRIPT
from uptime.auth_client import ReviewerClient,service_headers
from uptime.contracts import fingerprint
from uptime.correspondence_types import Scope,Delivery,SOURCE
from uptime.source_config import SourceConfig,SourceRegistry,SenderCredential,create_source,_write_new,load_private
from uptime.server import create_app


VARIANTS_PATH=ROOT/'fixtures'/'northwind'/'counterparty-variants.json'
VARIANTS_SHA256='9e0e4750b7e6e8ed560bee0a299f7ffaabc3e7f3e9f9fc57ca2672c301846f10'
COUNTERPARTY_REPLIES=('request-log','unclear')


def correspondence_for(package,reply):
    """The authored January reply: the package's own log request, or a pinned authored variant."""
    if reply=='request-log':return package['correspondence']
    raw=VARIANTS_PATH.read_bytes()
    if sha256(raw).hexdigest()!=VARIANTS_SHA256:raise ValueError('The authored counterparty variants changed.')
    chosen=deepcopy(package['correspondence'])
    chosen['denial']=json.loads(raw)['variants'][reply]['denial']
    return chosen


class CredentialRefused(ValueError):
    """A visible reviewer-credential path that setup will not use; reported as one plain line."""


def credential_target(path):
    """Check a visible reviewer-credential path before anything is written."""
    target=Path(path).expanduser().absolute()
    if not target.parent.is_dir():
        raise CredentialRefused('The folder for the reviewer file does not exist: '+str(target.parent))
    if target.is_symlink() or target.resolve()!=target:
        raise CredentialRefused('Choose a reviewer-file path without symlinks: '+str(target))
    if target.is_relative_to(ROOT.resolve()):
        raise CredentialRefused('Keep the reviewer file outside the repository: '+str(target))
    return target


def place_credential(target,credential):
    """Write the visible copy once; reuse an identical protected file; never overwrite."""
    from uptime.auth_keys import write_credential
    if target.exists():
        try:
            with os.fdopen(os.open(target,os.O_RDONLY|os.O_NOFOLLOW),'r') as handle:
                info=os.fstat(handle.fileno());existing=json.load(handle)
        except (OSError,ValueError):
            existing,info=None,None
        if existing!=credential:
            raise CredentialRefused('A different file already exists at '+str(target)+'; choose another path. Nothing was overwritten.')
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:
            raise CredentialRefused('The existing reviewer file at '+str(target)+' is not owner-only (0600); nothing was changed.')
        return 'REUSED'
    write_credential(target,credential,ROOT)
    return 'WRITTEN'


def source_inputs(package):
    overlay=package['overlay'];scopes={};events={}
    for row in package['months']:
        month=row['month'];u=row['usage'];invoice=row['invoice']
        # Decision D04-C: the loader's intake scope omits obligation fields the monthly family does not need.
        scope=Scope(**row['scope'])
        scopes[month]=scope
        bodies=[('northwind-invoice-'+month,dict(kind='invoice',lines=[
            dict(id=line.id,kind='affected_api',amount=str(line.net)) for line in invoice.lines]))]
        spans=u['eligible_intervals']
        if len(spans)>1:raise ValueError('This authored monthly intake requires exactly one declared incident interval.')
        if spans:
            span=spans[0];interval={k:span[k] for k in ('start','end')}
            bodies.extend([(u['status_event_id'],dict(kind='status',**interval)),
                ('northwind-impact-'+month,dict(kind='impact',affected=span['affected'],exclusion=span['exclusion'],**interval))])
        if u['month_complete']:
            bodies.append((u['monitor_ref'],dict(kind='coverage',start=u['start'],end=u['end'],complete=True,
                exclusions_removed=u['exclusions_removed'],incident_ids=[u['incident_id']],total_eligible_minutes=u['eligible_downtime_minutes'])))
        events[month]=[Delivery(event_id=ref,scope=scope,body=body) for ref,body in bodies]
    return scopes,events


def prepare(directory,origin,*,routine_automation=False,reviewer_credential=None,counterparty_reply='request-log',
            side_panel_origin=None):
    directory=Path(directory).absolute()
    if directory.exists():raise ValueError('Select a fresh directory; use --resume for an existing immutable workspace.')
    from uptime.server import panel_origin
    side_panel_origin=panel_origin(side_panel_origin)  # a serving option: checked first, never stored
    target=None
    if reviewer_credential is not None:
        # Checked before anything is written, so a refused path never leaves a half-created workspace.
        target=credential_target(reviewer_credential)
        if target.exists():
            raise CredentialRefused('A file already exists at '+str(target)+'; a new workspace needs a new path. Nothing was written.')
    directory.mkdir(mode=0o700,parents=True)
    package=load_package();scopes,_=source_inputs(package)
    scopes[package['settlement']['month']]=Scope(**package['settlement']['scope'])
    config=SourceConfig(version=1,channel='LOCAL_SYNTHETIC',tenant='bears',mode='replay',origin=origin,services=[])
    grants=[]
    for month,scope in scopes.items():
        for role in ('billing','customer','status','vendor'):
            subject='northwind-'+month+'-'+role
            grant,sender=create_source(config,subject,role,scope);grants.append(grant)
            _write_new(directory/(subject+'.json'),sender)
    _write_new(directory/'sources.json',config.model_copy(update={'services':grants}))
    private=dict(schema='authored-workspace/1',origin=origin,rehearsal_secret=secrets.token_urlsafe(48),
                 package_sha256=fingerprint(package['input_sha256']))
    if routine_automation:
        # Role 2: persisted with the workspace; projected as workflow.automation.enabled.
        private['routine_automation']=True
    if counterparty_reply not in COUNTERPARTY_REPLIES:raise ValueError('Unknown authored counterparty reply.')
    if counterparty_reply!='request-log':private['counterparty_reply']=counterparty_reply
    fd=os.open(directory/'workspace.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as handle:json.dump(private,handle);handle.flush();os.fsync(handle.fileno())
    from uptime.auth_keys import rehearsal_key,write_credential
    write_credential(directory/'scripted-reviewer.jwk',rehearsal_key(private['rehearsal_secret']),ROOT)
    if target is not None:
        # A visible, operator-chosen copy (0600, exclusive create, outside the repository). Only its path is printed.
        place_credential(target,rehearsal_key(private['rehearsal_secret']))
    return open_workspace(directory,side_panel_origin=side_panel_origin)


def open_workspace(directory, *, proposal_config=None, side_panel_origin=None):
    directory=Path(directory).resolve()
    from uptime.source_config import _protected_path,_check_file
    path=_protected_path(directory/'workspace.json')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'r') as handle:
        _check_file(handle.fileno());private=json.load(handle)
    package=load_package()
    if private['schema']!='authored-workspace/1' or private['package_sha256']!=fingerprint(package['input_sha256']):
        raise ValueError('The verified package differs from this workspace; preserve it and create a new directory.')
    scopes,events=source_inputs(package)
    registry=SourceRegistry(directory/'sources.json','replay',private['origin'],'bears')
    senders={(grant.scope.month,grant.source):load_private(directory/(grant.subject+'.json'),SenderCredential) for grant in registry.config.services}
    config=dict(package=package,installation='northwind-cloud',onboarding_installation='calyxquay',
        claim_month='2026-01',bill_month='2026-03',claim_ids={m:'inbox-northwind-'+m for m in scopes},scopes=scopes,
        senders=senders,clock_start='2026-03-01T12:00:00Z',clock_steps={},
        correspondence=correspondence_for(package,private.get('counterparty_reply','request-log')),provider_path=directory/'local-ledger.db',governing_fees=build_fee_registry(package),
        routine_automation=bool(private.get('routine_automation',False)))
    app=create_app(directory/'workspace.db',mode='replay',rehearsal=True,approvals_enabled=True,
        rehearsal_secret=private['rehearsal_secret'],service_credentials=registry,origin=private['origin'],workflow_config=config,
        proposal_config=proposal_config,side_panel_origin=side_panel_origin)
    return app,private,events


def checked(response):
    if response.status_code!=200:raise ValueError(str(response.status_code)+': '+response.text)
    return response.json()


def seed(client,app,private,events):
    actor=ReviewerClient(client,private['origin'],SCRIPT,private['rehearsal_secret'])
    post=lambda path,body:checked(actor.post(path,body))
    workflow=app.state.workflow
    post('/api/policy',dict(mode='ASSISTED',cap='10000.00'))
    package=workflow.package
    state=post('/api/vendors/northwind-cloud/candidates',dict(document=package['document'],overlay=package['overlay']))
    for month,deliveries in events.items():
        claim=workflow.claim_ids[month];scope=workflow.scopes[month]
        post('/api/correspondence/claims',dict(claim_id=claim,scope=scope.model_dump()))
        for event in deliveries:
            path='/api/correspondence/claims/'+claim+'/events'
            sender=workflow.senders[(month,SOURCE[event.body.kind])]
            raw=event.model_dump_json(exclude_unset=True).encode()
            headers=service_headers(instance=app.state.auth.instance,origin=private['origin'],subject=sender.subject,key=sender,path=path,body=raw)
            checked(client.post(path,content=raw,headers=headers))
    state=seed_northwind(post,state,package)
    seed_calyx(post)
    return actor,state


def seed_northwind(post,state,package):
    base='/api/vendors/northwind-cloud'
    # Authored controls, independently declared from the engine output. These
    # are scripted tests, never a claim of independent commercial authority.
    expectations={'2026-01':dict(outcome='ELIGIBLE',amount='2400.00'),
                  '2026-02':dict(outcome='INELIGIBLE'),'2026-03':dict(outcome='INSUFFICIENT_EVIDENCE')}
    controls=[dict(name='Source-backed '+row['month'],facts=row['facts'],expected=expectations[row['month']]) for row in package['months']]
    state=post(base+'/tests',dict(revision=state['revision'],tests=controls))
    if any(not row['passed'] for row in state['checks']):raise ValueError('Authored Northwind source controls failed.')
    state=catalog_action(post,base,catalog_action(post,base,state,'approve'),'activate')
    for row in package['months']:post(base+'/evaluate',dict(facts=row['facts']))
    return state


def scripted_literal_review(requirements):
    """Explicit authored fixture review; its actor remains scripted-test-reviewer."""
    from uptime.vendor_bindings import ATTESTATIONS
    review={k:requirements[k] for k in ('source_sha256','manifest_sha256','overlay_sha256','dependency_sha256')}
    review.update(attestations={k:True for k in ATTESTATIONS},
        block_reviews=[dict(block=b['block'],block_sha256=b['block_sha256'],effects=b['effects'],
            conditions_and_overrides='Authored public scenario: complete cited source and all conditions reviewed by the scripted reviewer.')
            for b in requirements['blocks']],
        bindings=[dict(definition_id=d['id'],span_id=d['spans'][0]['id'],
            literals=['subscription'] if d['role']=='fee_inclusions' and d['label']=='service_fee' else [d['spans'][0]['quote']])
            for d in requirements['definitions']])
    return review


def catalog_action(post,base,state,operation):
    offer=next((a for a in state['actions'] if a['operation']==operation),None)
    if offer is None:raise ValueError('Current catalog does not authorize '+operation)
    return post(base+'/actions/'+offer['id'],{})


def seed_calyx(post):
    # Scope the already accepted public artifact opt-in to this installation.
    # Never leave a process-wide proposition capability behind after setup.
    from unittest.mock import patch
    with patch.dict(os.environ,{'UPTIME_PUBLIC_EXTRACTIONS':str(ROOT/'docs/v4/evidence/public-extractions'),
                                'UPTIME_MODEL_PROPOSITIONS':'1'}):
        return _seed_calyx_public(post)


def _seed_calyx_public(post):
    from scripts.film_ramp_v4 import public_intake,demo_controls
    body,manifest,_=public_intake()
    body=deepcopy(body)
    body['document']['name']='CalyxQuay Beacon Cache Service Agreement'
    body['overlay'].update(account='harborline-calyx',agreement='CQ-2031-04',fee_line_ref='beacon-cache-monthly')
    _,controls=demo_controls(body['overlay'],manifest)
    for row in controls:row['name']=row['name'].replace('Editor demo: ','Source control: ')
    base='/api/vendors/calyxquay'
    state=post(base+'/candidates',body)
    if state.get('semantic_review_requirements'):
        state=post(base+'/semantic-bindings',dict(revision=state['revision'],review=scripted_literal_review(state['semantic_review_requirements'])))
    state=post(base+'/tests',dict(revision=state['revision'],tests=controls))
    if any(not row['passed'] for row in state['checks']):raise ValueError('Authored CalyxQuay source controls failed.')
    if state.get('interpretation_required'):state=catalog_action(post,base,state,'interpret')
    state=catalog_action(post,base,catalog_action(post,base,state,'approve'),'activate')
    state=catalog_action(post,base,state,'rollback')
    state=catalog_action(post,base,state,'review')
    state=post(base+'/tests',dict(revision=state['revision'],tests=controls))
    if state.get('interpretation_required'):state=catalog_action(post,base,state,'interpret')
    return catalog_action(post,base,catalog_action(post,base,state,'approve'),'activate')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--origin',default='http://127.0.0.1:8776')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--public-proposal-config',type=Path,help='Protected exact-request model configuration for the served workspace')
    parser.add_argument('--step-by-step',action='store_true',
                        help='Offer every routine step as its own reviewer action (the earlier behavior); default runs routine steps automatically')
    parser.add_argument('--counterparty-reply',choices=COUNTERPARTY_REPLIES,default='request-log',
                        help="Authored January reply: the package's log request, or the unclear reply for the escalation branch")
    parser.add_argument('--side-panel-origin',metavar='chrome-extension://ID',
                        help='Let exactly this Chrome extension frame the served workspace in its side panel (not stored)')
    parser.add_argument('--reviewer-credential',type=Path,
                        help='Also write the reviewer sign-in file to this visible absolute path outside the repository (mode 0600)')
    args=parser.parse_args()
    from uptime.server import panel_origin
    try:
        # Checked before anything is written or served; a serving option, never workspace state.
        side_panel=panel_origin(args.side_panel_origin)
    except ValueError as refused:
        parser.exit(1,'setup_northwind: '+str(refused)+'\n')
    if side_panel and not args.serve:
        # Framing only affects a served app; without --serve the option would silently do nothing.
        parser.error('--side-panel-origin requires --serve')
    if args.public_proposal_config and not args.serve:
        parser.error('--public-proposal-config requires --serve')
    if args.resume and (args.step_by_step or args.counterparty_reply!='request-log'):
        parser.error('--step-by-step and --counterparty-reply apply when a workspace is created')
    copy_state=None
    try:
        if args.resume:
            target=credential_target(args.reviewer_credential) if args.reviewer_credential else None
            app,private,events=open_workspace(args.directory,side_panel_origin=side_panel)
            if target is not None:
                from uptime.auth_keys import rehearsal_key
                copy_state=place_credential(target,rehearsal_key(private['rehearsal_secret']))
        else:
            app,private,events=prepare(args.directory,args.origin,routine_automation=not args.step_by_step,
                                       reviewer_credential=args.reviewer_credential,counterparty_reply=args.counterparty_reply,
                                       side_panel_origin=side_panel)
            copy_state='WRITTEN' if args.reviewer_credential else None
    except CredentialRefused as refused:
        parser.exit(1,'setup_northwind: '+str(refused)+'\n')
    if not args.resume:
        from fastapi.testclient import TestClient
        with TestClient(app,base_url=private['origin'],client=('127.0.0.1',4510)) as client:
            actor,_=seed(client,app,private,events)
            projection=checked(client.get('/api/workspace/workflow',headers=actor.headers))
            (args.directory/'initial-projection.json').write_text(json.dumps(projection,indent=2)+'\n')
    credential=(args.reviewer_credential.expanduser().absolute() if args.reviewer_credential
                else args.directory.absolute()/'scripted-reviewer.jwk')
    print(json.dumps(dict(directory=str(args.directory),origin=private['origin'],account=SCRIPT,
                          reviewer_credential_file=str(credential),reviewer_credential_copy=copy_state,
                          routine_automation=bool(private.get('routine_automation',False)),
                          **({'side_panel_origin':side_panel} if side_panel else {}))),flush=True)
    # Plain sign-in block; only the path of the private key file is ever printed.
    if side_panel:
        print('Only the side panel of '+side_panel+' may frame this served workspace.',file=sys.stderr)
    print("Sign in with the reviewer file below (private key, mode 0600; never share or commit it).",file=sys.stderr)
    print(str(credential),file=sys.stderr)
    print(SCRIPT,file=sys.stderr)
    print(private['origin'],file=sys.stderr,flush=True)
    if args.serve:
        if args.public_proposal_config:
            # Seeding closes its TestClient lifecycle. Construct the configured
            # job service only for the process that will serve requests.
            app,private,events=open_workspace(args.directory,proposal_config=args.public_proposal_config,
                                              side_panel_origin=side_panel)
        import uvicorn
        uvicorn.run(app,host='127.0.0.1',port=int(private['origin'].rsplit(':',1)[1]),log_level='warning')


if __name__=='__main__':main()
