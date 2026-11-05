"""Explicit public-only proposal experiment; never loads a case DB or private evaluator."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from uptime.correspondence_model import PublicInterpretationAdapter, ToolFreeClaude, serialized_request


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('case_id')
    parser.add_argument('--execute-public',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--control-receipt',type=Path,required=True)
    args=parser.parse_args()
    if not args.execute_public:
        parser.error('External inference is disabled unless this public experiment is explicitly selected.')
    fixture=ROOT/'fixtures/correspondence/interpretation-60-public.json'
    manifest=ROOT/'fixtures/correspondence/interpretation-60-model-manifest-v2.json'
    data=json.loads(fixture.read_text()); approved=json.loads(manifest.read_text())
    control_bytes=args.control_receipt.read_bytes()
    control=json.loads(control_bytes)
    if sha256(control_bytes).hexdigest()!=approved['controls_sha256'] or control.get('status')!='PASS':
        raise ValueError('The actual public transport controls are absent or changed.')
    if sha256(fixture.read_bytes()).hexdigest()!=approved['fixture_sha256']:
        raise ValueError('The public fixture changed after its disclosure manifest was recorded.')
    rows=[row for row in data['cases'] if row['id']==args.case_id]
    if len(rows)!=1 or args.case_id not in approved['requests']:
        raise ValueError('Only a separately manifested public fixture may be sent.')
    context=dict(text=rows[0]['text'],scope={'month':data['trusted_context']['scope_month']},currency=data['trusted_context']['currency'],requested=data['trusted_context']['local_filed_requested'],filing_fields=[])
    provider=ToolFreeClaude(str(Path.home()/'.local/bin/claude'))
    if provider.profile!=approved['transport'] or provider.profile!=control['profile']:
        raise ValueError('The transport changed after its public controls and manifest.')
    request=serialized_request(context,provider.profile)
    if sha256(request).hexdigest()!=approved['requests'][args.case_id]:
        raise ValueError('Prompt, schema, invocation settings or public content changed after manifest approval.')
    adapter=PublicInterpretationAdapter(enabled=True,allowed_requests=[approved['requests'][args.case_id]],provider=provider)
    result=dict(case=args.case_id,request_sha256=sha256(request).hexdigest(),status='NOT_RUN',authority='proposal_only',scope='self-authored public synthetic; not independent coverage or human review')
    try:
        result.update(adapter.propose(context),status='PROPOSED')
    except Exception as exc:
        result.update(status='REFUSED',error=type(exc).__name__,detail=str(exc)[:300])
    result['transport_observation']=provider.last_receipt
    result['controls_sha256']=approved['controls_sha256']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as output:
        output.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('case','status','authority','request_sha256')}))

if __name__=='__main__': main()
