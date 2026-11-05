#!/usr/bin/env python3
"""Create an isolated authored workspace and seed through signed public services.

The protected directory contains fictional runtime credentials. It is never a
Ramp customer database, real authorization, or external-source attestation.
"""
from copy import deepcopy
import argparse
import json
import os
from pathlib import Path
import secrets
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from fixtures.northwind.loader import load_package
from uptime.auth import SCRIPT
from uptime.auth_client import ReviewerClient,service_headers
from uptime.contracts import fingerprint
from uptime.correspondence_types import Scope,Delivery,SOURCE
from uptime.source_config import SourceConfig,SourceRegistry,SenderCredential,create_source,_write_new,load_private
from uptime.server import create_app


def source_inputs(package):
    overlay=package['overlay'];scopes={};events={}
    for row in package['months']:
        month=row['month'];u=row['usage'];invoice=row['invoice']
        scope=Scope(account=overlay['account'],vendor=package['manifest']['vendor'],contract=overlay['agreement'],
            service=overlay['product'],component=u['component_id'],invoice=invoice.id,incident=u['incident_id'],
            currency=invoice.currency,month=month,region=u['region'])
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


def prepare(directory,origin):
    directory=Path(directory).absolute()
    if directory.exists():raise ValueError('Select a fresh directory; use --resume for an existing immutable workspace.')
    directory.mkdir(mode=0o700,parents=True)
    package=load_package();scopes,_=source_inputs(package)
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
    fd=os.open(directory/'workspace.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as handle:json.dump(private,handle);handle.flush();os.fsync(handle.fileno())
    return open_workspace(directory)


def open_workspace(directory):
    directory=Path(directory).resolve()
    from uptime.source_config import _protected_path,_check_file
    path=_protected_path(directory/'workspace.json')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'r') as handle:
        _check_file(handle.fileno());private=json.load(handle)
    # Only already committed public extraction receipts; this does not call a model.
    public_extractions=str(ROOT/'docs/v4/evidence/public-extractions')
    if os.environ.get('UPTIME_PUBLIC_EXTRACTIONS',public_extractions)!=public_extractions:
        raise ValueError('This authored workspace requires its exact committed public extraction directory.')
    os.environ['UPTIME_PUBLIC_EXTRACTIONS']=public_extractions
    os.environ['UPTIME_MODEL_PROPOSITIONS']='1'
    package=load_package()
    if private['schema']!='authored-workspace/1' or private['package_sha256']!=fingerprint(package['input_sha256']):
        raise ValueError('The verified package differs from this workspace; preserve it and create a new directory.')
    scopes,events=source_inputs(package)
    registry=SourceRegistry(directory/'sources.json','replay',private['origin'],'bears')
    senders={(grant.scope.month,grant.source):load_private(directory/(grant.subject+'.json'),SenderCredential) for grant in registry.config.services}
    config=dict(package=package,installation='northwind-cloud',onboarding_installation='calyxquay',
        claim_month='2026-01',bill_month='2026-03',claim_ids={m:'inbox-northwind-'+m for m in scopes},scopes=scopes,
        senders=senders,clock_start='2026-03-01T12:00:00Z',clock_steps={},
        correspondence=package['correspondence'],provider_path=directory/'local-ledger.db')
    app=create_app(directory/'workspace.db',mode='replay',rehearsal=True,approvals_enabled=True,
        rehearsal_secret=private['rehearsal_secret'],service_credentials=registry,origin=private['origin'],workflow_config=config)
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
    seed_calyx(post)
    return actor,state


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
    args=parser.parse_args()
    app,private,events=open_workspace(args.directory) if args.resume else prepare(args.directory,args.origin)
    if not args.resume:
        from fastapi.testclient import TestClient
        with TestClient(app,base_url=private['origin'],client=('127.0.0.1',4510)) as client:
            actor,_=seed(client,app,private,events)
            projection=checked(client.get('/api/workspace/workflow',headers=actor.headers))
            (args.directory/'initial-projection.json').write_text(json.dumps(projection,indent=2)+'\n')
    if args.serve:
        import uvicorn
        uvicorn.run(app,host='127.0.0.1',port=int(private['origin'].rsplit(':',1)[1]),log_level='warning')
    else:print(json.dumps(dict(directory=str(args.directory),origin=private['origin'],credential_file='workspace.json')))


if __name__=='__main__':main()
