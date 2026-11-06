"""Actual browser auth recovery with an explicitly expired disposable server session."""
from dataclasses import replace
import json
from pathlib import Path
import socket
import subprocess
import threading
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
import uvicorn

from uptime.auth import enroll
from uptime.auth_keys import generate_reviewer_key
from uptime.server import create_app
from uptime import vendor_registry
from test_vendor_model_jobs_runtime import DOC, OVERLAY, P, VENDOR, approved, runtime
from test_vendor_model_jobs_browser import CHROME

ROOT = Path(__file__).resolve().parent.parent


def test_v4_auth_recovery_dom_controls():
    result = subprocess.run(['node','--test','tests/helpers/vendor_auth83.test.cjs'], cwd=ROOT,
                            capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def test_expired_browser_session_recovers_same_job_without_resubmitting(runtime, tmp_path):
    db, _, provider, jobs, _ = runtime
    approved(runtime)
    key = generate_reviewer_key()
    enroll(db,P.subject,key,tenant=P.tenant,mode='replay')
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(25)
    origin='http://127.0.0.1:'+str(sock.getsockname()[1])
    app=create_app(db,tenant=P.tenant,origin=origin,proposal_jobs=jobs,approvals_enabled=False)
    server=uvicorn.Server(uvicorn.Config(app,log_level='critical',access_log=False))
    runner=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);runner.start()
    try:
        for _ in range(200):
            if server.started: break
            time.sleep(.01)
        assert server.started
        with sync_playwright() as browser_api:
            browser=browser_api.chromium.launch(headless=True,**({'executable_path':str(CHROME)} if CHROME.exists() else {}))
            context=browser.new_context(viewport={'width':390,'height':844})
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(origin+'/') else route.abort())
            page=context.new_page();responses=[];errors=[]
            page.on('response',lambda response:responses.append((response.request.method,urlsplit(response.url).path,response.status)))
            page.on('pageerror',lambda error:errors.append(str(error)))
            def login():
                page.get_by_role('heading',name='Sign in to Uptime',exact=True).wait_for()
                page.get_by_label('Account name',exact=True).fill(P.subject)
                page.get_by_label('Credential file',exact=True).set_input_files({
                    'name':'disposable-reviewer.json','mimeType':'application/json','buffer':json.dumps(key).encode()})
                page.get_by_role('button',name='Sign in',exact=True).click()
                page.get_by_role('button',name='Check generation access',exact=True).wait_for()
            def source():
                for label,value in [('Proposal vendor identifier',VENDOR),('Public document name',DOC['name']),
                                    ('Public document URI',DOC['uri']),('Exact public source text (sent exactly as entered)',DOC['text'])]:
                    page.get_by_label(label,exact=True).fill(value)
                page.get_by_label('Public document origin',exact=True).select_option(DOC['classification'])
                page.get_by_label('Extraction profile',exact=True).select_option('monthly')
                page.get_by_role('button',name='Check generation access',exact=True).click()
            def review():
                page.get_by_label('Private customer overlay for this proposal (JSON object; never sent for extraction)',exact=True).fill(json.dumps(OVERLAY))
                page.get_by_role('button',name='Review shadow candidate request',exact=True).click()
            page.goto(origin+'/#vendors');login();source()
            page.get_by_text('Generation is permitted for this exact request.',exact=False).wait_for()
            page.get_by_role('button',name='Generate proposal',exact=True).click()
            page.get_by_role('heading',name='Proposed public clauses',exact=True).wait_for(timeout=10000)
            assert 'SUCCEEDED' in page.locator('.v4-status').inner_text()
            assert len(provider.calls)==1
            original_job=page.locator('.v4-job dd').first.inner_text()
            review()
            old_confirm=page.get_by_role('button',name='Confirm shadow candidate',exact=True).element_handle()
            # Test-only deterministic expiry, with unchanged production lifetime/security policy.
            with app.state.auth.lock:
                assert len(app.state.auth.sessions)==1
                app.state.auth.sessions={key:replace(value,expires=0) for key,value in app.state.auth.sessions.items()}
            page.get_by_role('button',name='Confirm shadow candidate',exact=True).click()
            page.get_by_role('heading',name='Sign in to Uptime',exact=True).wait_for()
            page.screenshot(path=str(tmp_path/'expired-session-sign-in.png'),full_page=True)
            assert page.locator('#content').get_attribute('aria-busy') == 'false'
            assert ('POST','/api/auth/challenge',401) in responses
            assert old_confirm.evaluate('(button) => button.disabled') is True
            assert not any(method=='POST' and path.endswith('/candidate') for method,path,_ in responses)
            assert vendor_registry.catalog(db,P)['vendors']==[]
            assert jobs.get(P.tenant,P.subject,original_job)['status']=='SUCCEEDED'
            assert len(provider.calls)==1
            before=len(responses)
            old_confirm.evaluate("button => button.dispatchEvent(new Event('click'))")
            assert len(responses)==before
            login();source()
            page.get_by_role('heading',name='Proposed public clauses',exact=True).wait_for(timeout=10000)
            assert 'SUCCEEDED' in page.locator('.v4-status').inner_text()
            assert page.get_by_role('button',name='Generate proposal',exact=True).is_disabled()
            assert page.get_by_text(original_job,exact=True).count()>0
            assert len(provider.calls)==1
            assert len([1 for method,path,_ in responses if method=='POST' and path.endswith('/proposal-jobs')])==1
            old_confirm.evaluate("button => button.dispatchEvent(new Event('click'))")
            review();page.get_by_role('button',name='Confirm shadow candidate',exact=True).click()
            page.get_by_role('button',name='Submit independent tests',exact=True).wait_for()
            candidate=vendor_registry.get_vendor(db,P,VENDOR)
            assert candidate['state']=='SHADOW' and candidate['reviewer'] is None and candidate['active_version'] is None
            assert len(provider.calls)==1
            assert len([1 for method,path,_ in responses if method=='POST' and path.endswith('/candidate')])==1
            assert len([1 for method,path,_ in responses if method=='POST' and path.endswith('/proposal-jobs')])==1
            assert errors==[] and page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(tmp_path/'expired-session-recovered-shadow.png'),full_page=True)
            (tmp_path/'safe-response-evidence.json').write_text(json.dumps({'responses':responses,'job_id':original_job,
                'provider_calls':len(provider.calls),'candidate_state':candidate['state']},indent=2))
            browser.close()
    finally:
        server.should_exit=True;runner.join(timeout=5);sock.close()
