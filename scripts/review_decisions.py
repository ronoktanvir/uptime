from pathlib import Path
import sys, json, subprocess, tempfile, datetime
root=Path(__file__).resolve().parents[1]
folder=root/'docs/decisions'
items=sorted((folder/'packets').glob('*.md'))
def review(file):
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    prompt="Independently review this sanitized decision packet for a sandbox-only hackathon. Return preferred option, strongest dissent, falsification tests and boundary; <=180 words. No tools. Initial evidence is greenfield, tests prospective unless explicitly marked.\n"+file.read_text()
    with tempfile.TemporaryDirectory() as cwd:
        try:
            r=subprocess.run(['claude','-p',prompt,'--model','claude-opus-5-5','--tools','','--strict-mcp-config','--setting-sources','','--no-session-persistence','--output-format','json'],cwd=cwd,capture_output=True,text=True,timeout=150)
            x=json.loads(r.stdout); models=list(x.get('modelUsage',{}))
            ok=r.returncode==0 and x.get('is_error') is False and 'claude-opus-5-5' in models
            reply=x.get('result','') if ok else 'Authenticated invocation failed or model identity unconfirmed.'
            result=dict(status='REVIEWED' if ok else 'OPUS_BLOCKED',utc=stamp,models=models,reply=reply,session=x.get('session_id'))
        except Exception as exc:
            result=dict(status='OPUS_BLOCKED',utc=stamp,error=type(exc).__name__)
    (folder/'reviews'/file.with_suffix('.json').name).write_text(json.dumps(result,indent=2)+'\n')
    print(file.name,result['status'],flush=True)
if __name__=='__main__':
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool: list(pool.map(review,[i for i in items if not sys.argv[1:] or i.stem in sys.argv[1:]]))
