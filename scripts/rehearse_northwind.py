#!/usr/bin/env python3
"""Exercise the configured workflow over actual loopback HTTP, with readback.

Only the separately owned fictional workspace is eligible. No real Ramp or
commercial source credentials are loaded, and no action supplies a money value.
"""
import argparse
from datetime import UTC,datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from uptime.auth import SCRIPT,valid_origin
from uptime.auth_client import ReviewerClient
from uptime.source_config import _protected_path,_check_file


def run(directory,receipt,max_actions=20):
    import httpx
    directory=Path(directory).resolve()
    path=_protected_path(directory/'workspace.json')
    with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'r') as handle:
        _check_file(handle.fileno());private=json.load(handle)
    origin=valid_origin(private['origin'])
    with sqlite3.connect('file:'+str(directory/'workspace.db')+'?mode=ro',uri=True) as db:
        binding=db.execute('SELECT mode,rehearsal,tenant FROM authority_workspace WHERE id=1').fetchone()
        instance=db.execute('SELECT instance FROM workspace_workflow WHERE id=1').fetchone()[0]
    if binding!=('replay',1,'bears'):raise PermissionError('Only the exact isolated authored workspace may be rehearsed.')
    result=dict(schema='workspace-socket-receipt/1',started_at=datetime.now(UTC).isoformat(),
        transport='REAL_LOOPBACK_HTTP',reviewer=SCRIPT,authority_kind='SCRIPTED_REVIEWER',origin=origin,
        client_source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),steps=[])
    with httpx.Client(base_url=origin,timeout=30,trust_env=False) as client:
        context=client.get('/api/auth/context');context.raise_for_status()
        if any(context.json()[k]!=v for k,v in dict(origin=origin,mode='replay',tenant='bears').items()):
            raise PermissionError('Listener authority differs from the configured workspace.')
        actor=ReviewerClient(client,origin,SCRIPT,private['rehearsal_secret'])
        def view():
            response=client.get('/api/workspace/workflow',headers=actor.headers);response.raise_for_status()
            value=response.json()['workflow']
            if (not value or value['workspace_instance']!=instance
                    or value['source_package_sha256']!=private['package_sha256']):
                raise PermissionError('Listener instance/package differs from the owned workspace.')
            return value
        current=view();result['initial']=current
        for _ in range(max_actions):
            if not current['next_actions']:break
            if len(current['next_actions'])!=1:raise ValueError('An ambiguous action requires explicit review.')
            offer=current['next_actions'][0];route='/api/workspace/workflow/actions/'+offer['id']
            response=actor.post(route,{});response.raise_for_status();after=response.json()['workflow']
            duplicate=actor.post(route,{});duplicate.raise_for_status()
            if duplicate.json()['workflow']!=after:raise ValueError('Duplicate action changed the authoritative projection.')
            readback=view()
            if readback!=after:raise ValueError('Action result differs from separately read authoritative state.')
            result['steps'].append(dict(action=offer,before=current['claim'],after=after['claim'],ledger=after['ledger'],
                event_at=after['as_of'],duplicate_unchanged=True,readback_equal=True))
            current=after
        result.update(final=current,finished_at=datetime.now(UTC).isoformat(),
                      available_actions_remaining=len(current['next_actions']))
    receipt=Path(receipt)
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    parser.add_argument('--max-actions',type=int,default=20,choices=range(0,31))
    args=parser.parse_args()
    result=run(args.directory,args.receipt,args.max_actions)
    print(json.dumps(dict(receipt=str(args.receipt),actions=len(result['steps']),
        available_actions_remaining=result['available_actions_remaining'],ledger=result['final']['ledger']),sort_keys=True))


if __name__=='__main__':main()
