"""Local process falsifiers; no provider or credentials used by these tests."""
import json
import os
from pathlib import Path
import sys
import time

import pytest

from uptime.correspondence_model_transport import bounded_run, persistence_delta, public_environment, strict_json


def test_environment_drops_inherited_credentials_and_execution_overrides(monkeypatch):
    for name in ('NODE_OPTIONS','DYLD_INSERT_LIBRARIES','HTTP_PROXY','ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL'):
        monkeypatch.setenv(name,'must-not-leave-host')
    env=public_environment()
    assert env['HOME']==str(Path.home())
    assert env['DISABLE_UPDATES']=='1' and env['CLAUDE_CODE_DISABLE_AUTO_MEMORY']=='1'
    assert not set(env)&{'NODE_OPTIONS','DYLD_INSERT_LIBRARIES','HTTP_PROXY','ANTHROPIC_API_KEY','ANTHROPIC_BASE_URL'}


def test_process_timeout_rejects_partial_output_and_kills_descendant(tmp_path):
    marker=tmp_path/'escaped'
    code='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'+repr('import time; from pathlib import Path; time.sleep(.5); Path('+repr(str(marker))+').write_text("escaped")')+']); print("partial",flush=True); time.sleep(10)'
    with pytest.raises(TimeoutError):
        bounded_run([sys.executable,'-c',code],cwd=tmp_path,env=public_environment(),timeout=.1)
    time.sleep(.6)
    assert not marker.exists()


def test_descendant_cannot_hold_pipe_after_parent_exit(tmp_path):
    code='import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(10)"])'
    with pytest.raises(TimeoutError):
        bounded_run([sys.executable,'-c',code],cwd=tmp_path,env=public_environment(),timeout=.1)


def test_output_limit_is_combined_and_no_partial_success(tmp_path):
    with pytest.raises(ValueError,match='byte limit'):
        bounded_run([sys.executable,'-c','import sys; print("a"*90); print("b"*90,file=sys.stderr)'],cwd=tmp_path,env=public_environment(),limit=100)


def test_large_input_is_drained_and_exit_status_preserved(tmp_path):
    code,output,error=bounded_run([sys.executable,'-c','import sys; data=sys.stdin.buffer.read(); print(len(data)); sys.exit(7)'],payload=b'x'*100000,cwd=tmp_path,env=public_environment())
    assert (code,output,error)==(7,b'100000\n',b'')


def test_only_current_owned_project_persistence_is_attributed(tmp_path):
    key=str(tmp_path.resolve()).replace('/','-')
    before={}
    after={'user/projects/'+key+'/session.jsonl':(20,123,False),'user/projects/other/session.jsonl':(20,124,False)}
    delta=persistence_delta(before,after,tmp_path)
    assert delta['project_entries_changed']==1 and delta['all_metadata_changed']==2
    assert all('session.jsonl' not in s for s in delta['changed_path_hashes'])


@pytest.mark.parametrize('fault',['binary','tools','mcp','tool_event','persistence','request_profile'])
def test_pinned_transport_refuses_changed_authority_or_execution_surface(tmp_path,monkeypatch,fault):
    import uptime.correspondence_model_transport as transport
    executable=tmp_path/'public-fake-cli'; executable.write_text('public fixture binary')
    init=dict(type='system',subtype='init',tools=[],mcp_servers=[],model='public-model',session_id='public-session')
    result=dict(type='result',subtype='success',session_id='public-session',is_error=False,modelUsage={'public-model':{}},result='{}')
    events=[init,result]
    if fault=='tools': init['tools']=['Read']
    if fault=='mcp': init['mcp_servers']=[{'name':'unexpected'}]
    if fault=='tool_event':events.insert(1,dict(type='assistant',message={'content':[{'type':'tool_use','name':'Read'}]}))
    calls=[]
    def fake_run(argv,**kw):
        calls.append(argv)
        if '--help' in argv:return 0,b'--safe-mode --tools',b''
        if '--version' in argv:return 0,b'public fixture version',b''
        return 0,b'\n'.join(json.dumps(e).encode() for e in events),b''
    monkeypatch.setattr(transport,'bounded_run',fake_run)
    monkeypatch.setattr(transport,'metadata_inventory',lambda:{})
    if fault=='persistence':monkeypatch.setattr(transport,'persistence_delta',lambda *a:{'project_entries_changed':1})
    provider=transport.SafePublicClaude(executable,model='public-model',system='public-system')
    request=dict(model='public-model',system='public-system',tools=[],transport=provider.profile)
    if fault=='request_profile':request['transport']={}
    if fault=='binary':executable.write_text('different fixture binary')
    with pytest.raises(ValueError):provider(json.dumps(request).encode())
    assert len(calls)==(2 if fault in {'binary','request_profile'} else 3)
    if fault in {'tools','mcp','tool_event','persistence'}:
        with pytest.raises(PermissionError):provider(json.dumps(request).encode())
        assert len(calls)==3


@pytest.mark.parametrize('value',[
    '{"eligible":false,"eligible":true}',
    '{"nested":{"amount":"12","amount":"1200"}}',
    '{"amount":NaN}', '{"amount":Infinity}', '{"amount":-Infinity}',
    '{"amount":1e999}', b'\xff',
])
def test_strict_model_json_rejects_ambiguous_or_nonfinite_values(value):
    with pytest.raises(ValueError):
        strict_json(value)


def test_strict_model_json_preserves_exact_money_strings_and_utf8():
    assert strict_json('{"quote":"Crédit de $2,400.00","amount":"2400.00","fraction":0.5}') == {
        'quote':'Crédit de $2,400.00','amount':'2400.00','fraction':0.5}


@pytest.mark.parametrize('fault',[
    None, 'init_model', 'fallback_model', 'session', 'missing_session', 'result_error',
    'result_subtype', 'duplicate_result', 'structured_inventory', 'structured_tool',
    'structured_field', 'non_object', 'duplicate_key', 'nonfinite',
])
def test_public_transport_accepts_only_one_plain_matching_model_result(tmp_path, monkeypatch, fault):
    import uptime.correspondence_model_transport as transport
    executable=tmp_path/'public-fake-cli'; executable.write_text('public fixture binary')
    init=dict(type='system',subtype='init',tools=[],mcp_servers=[],model='public-model',session_id='session-a')
    result=dict(type='result',subtype='success',session_id='session-a',is_error=False,
                modelUsage={'public-model':{}},result='{"blocks":[]}')
    events=[init,result]
    if fault=='init_model':init['model']='other-model'
    if fault=='fallback_model':result['modelUsage']['other-model']={}
    if fault=='session':result['session_id']='session-b'
    if fault=='missing_session':init.pop('session_id');result.pop('session_id')
    if fault=='result_error':result['is_error']=True
    if fault=='result_subtype':result['subtype']='error_max_turns'
    if fault=='duplicate_result':events.append(result)
    if fault=='structured_inventory':init['tools']=['StructuredOutput']
    if fault=='structured_tool':events.insert(1,dict(type='assistant',message={'content':[{'type':'tool_use','name':'StructuredOutput','input':{'blocks':[]}}]}))
    if fault=='structured_field':result['structured_output']={'blocks':[]}
    if fault=='non_object':events.insert(1,[])
    stream=b'\n'.join(json.dumps(event).encode() for event in events)
    if fault=='duplicate_key':stream=stream.replace(b'"is_error": false',b'"is_error": true, "is_error": false')
    if fault=='nonfinite':stream+=b'\n{"cost":NaN}'
    calls=[]
    def run(argv,**kwargs):
        calls.append(argv)
        if '--help' in argv:return 0,b'--safe-mode --tools --json-schema',b''
        if '--version' in argv:return 0,b'public fixture version',b''
        return 0,stream,b''
    monkeypatch.setattr(transport,'bounded_run',run)
    monkeypatch.setattr(transport,'metadata_inventory',lambda:{})
    provider=transport.SafePublicClaude(executable,model='public-model',system='public-system')
    request=json.dumps(dict(model='public-model',system='public-system',tools=[],transport=provider.profile)).encode()
    if fault is None:
        answer=provider(request)
        assert answer['text']=='{"blocks":[]}' and answer['session']=='session-a'
        assert answer['transport']['tool_inventory']==[]
        assert '--json-schema' not in calls[-1]
        assert provider.profile['name']=='safe-public-experimental-v2'
    else:
        with pytest.raises(ValueError):provider(request)
    assert len(calls)==3
    if fault in {'structured_inventory','structured_tool'}:
        with pytest.raises(PermissionError):provider(request)
        assert len(calls)==3
