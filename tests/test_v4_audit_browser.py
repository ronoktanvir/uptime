"""Real system Chrome and two sibling loopback origins. No skip or browser fallback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import secrets
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.request

from test_v4_audit_protocol import is_v4, generate_key, SUBJECT

CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')


def browser_sibling_origin():
    import uvicorn
    from playwright.sync_api import sync_playwright
    from uptime.server import create_app
    from test_v4_audit_workflow import observation
    if not CHROME.is_file():
        raise FileNotFoundError('RequiredSystemChromeUnavailable')
    with tempfile.TemporaryDirectory() as tmp:
        sock = socket.socket()
        neighbor = service = runner = None
        try:
            sock.bind(('127.0.0.1', 0))
            sock.listen(25)
            base = 'http://127.0.0.1:'+str(sock.getsockname()[1])
            db = Path(tmp)/'browser.sqlite'
            modern = is_v4()
            if modern:
                from uptime.auth import enroll
                key = generate_key()
                enroll(db, SUBJECT, key)
                app = create_app(db, mode='replay', approvals_enabled=True, origin=base)
            else:
                secret = secrets.token_urlsafe(32)
                app = create_app(db, session_secret=secret, mode='replay')
            captured = []
            class Neighbor(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass
                def do_GET(self):
                    captured.append(self.headers.get('Cookie', ''))
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body>Synthetic sibling origin</body></html>')
            neighbor = ThreadingHTTPServer(('127.0.0.1', 0), Neighbor)
            threading.Thread(target=neighbor.serve_forever, daemon=True).start()
            sibling = 'http://127.0.0.1:'+str(neighbor.server_port)
            service = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False, proxy_headers=False))
            runner = threading.Thread(target=service.run, kwargs={'sockets':[sock]}, daemon=True)
            runner.start()
            for _ in range(200):
                if service.started:
                    break
                time.sleep(.025)
            if not service.started:
                raise RuntimeError('LocalServerUnavailable')
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=str(CHROME),
                    args=['--disable-background-networking', '--disable-component-update', '--no-first-run'])
                try:
                    context = browser.new_context()
                    context.route('**/*', lambda route: route.continue_() if
                        any(route.request.url.startswith(origin+'/') for origin in (base,sibling)) else route.abort())
                    page = context.new_page()
                    if modern:
                        page.goto(base+"/#dashboard")
                        page.get_by_label('Account name', exact=True).fill(SUBJECT)
                        page.get_by_label('Credential file', exact=True).set_input_files({
                            'name':'synthetic-qa-key.json', 'mimeType':'application/json', 'buffer':json.dumps(key).encode()})
                        page.get_by_role('button', name='Sign in', exact=True).click()
                    else:
                        page.goto(base+'/session/'+secret)
                    page.get_by_role("heading",name=("Evidence ledger" if modern else "Contract ledger"),exact=True).wait_for()
                    case_id = 'dispute-partial'
                    path = '/api/cases/'+case_id
                    def read_case():
                        if modern:
                            return page.evaluate('(path) => window.uptimeAPI(path)', path)
                        return context.request.get(base+path).json()
                    initial = read_case()
                    page.locator('tr').filter(has=page.get_by_text(case_id, exact=True)).get_by_role('button').click()
                    with page.expect_response(lambda r: r.request.method=='POST' and r.url==base+path+'/actions/approve-claim') as posted:
                        page.get_by_role('button', name='Approve simulated claim', exact=True).click()
                    response = posted.value
                    positive = response.status
                    # These capabilities stay in memory; only selected status/identity predicates leave the probe.
                    signed_headers = response.request.all_headers()
                    signed_body = response.request.post_data or '{}'
                    accepted = response.json()
                    readback = read_case()
                    case = readback
                    attack_before = page.evaluate("() => window.uptimeAPI('/api/cases/dispute-cure')") if modern else context.request.get(base+'/api/cases/dispute-cure').json()
                    # Navigation delivers cookies by host, even across loopback ports, in actual Chrome.
                    attacker = context.new_page()
                    attacker.goto(sibling+'/owned')
                    if not captured:
                        raise RuntimeError('SiblingRequestNotObserved')
                    exposed = bool(captured[-1])
                    # Attack from the sibling context also attempts the signed request in the browser.
                    browser_attempt = attacker.evaluate('''async ({url,body,headers}) => {
                        try { const r=await fetch(url,{method:'POST',body,headers,credentials:'include'});
                              return {completed:true,status:r.status}; }
                        catch (_) { return {completed:true,status:null}; }
                    }''', {'url':base+path+'/actions/approve-claim','body':signed_body,
                            'headers':{k:v for k,v in signed_headers.items() if k.lower() in
                                       ('authorization','content-type','x-uptime-action','x-uptime-challenge','x-uptime-proof')}})
                    # Replay with a forged allowed Origin as well: origin filtering alone is insufficient.
                    replay_path = path+'/actions/approve-claim' if modern else '/api/cases/dispute-cure/actions/approve-claim'
                    headers = {k:v for k,v in signed_headers.items() if k.lower() in
                               ('authorization','content-type','x-uptime-action','x-uptime-challenge','x-uptime-proof')}
                    headers.update({'Cookie':captured[-1], 'Origin':base})
                    request = urllib.request.Request(base+replay_path, data=signed_body.encode(), headers=headers)
                    try:
                        with urllib.request.urlopen(request, timeout=4) as reply:
                            replay = reply.status
                    except urllib.error.HTTPError as exc:
                        replay = exc.code
                    # Same identity used for readback, with the browser's actual token or cookie.
                    read_headers = {'Authorization':signed_headers['authorization']} if modern else {'Cookie':captured[-1]}
                    def read(path):
                        with urllib.request.urlopen(urllib.request.Request(base+path,headers=read_headers), timeout=4) as reply:
                            return json.load(reply)
                    final = read(path)
                    attack_after = read('/api/cases/dispute-cure')
                    observed = dict(positive_ui_status=positive, same_case_readback=accepted.get('id')==readback['id']==initial['id']==case_id
                        and readback['stage']=='CLAIM_APPROVED', sibling_request_observed=bool(captured),
                        browser_attack_attempted=browser_attempt['completed'], sibling_cookie_exposed=exposed,
                        replay_denied=replay in (401,403), state_unchanged=final['stage']==case['stage']
                            and final['submissions']==case['submissions'] and attack_before['stage']==attack_after['stage'])
                    expected = dict(positive_ui_status=200, same_case_readback=True, sibling_request_observed=True,
                                    browser_attack_attempted=True, sibling_cookie_exposed=False, replay_denied=True, state_unchanged=True)
                    rows = [observation('W-browser-sibling-origin', observed, expected)]
                    try:
                        for label in ('Submit to vendor simulator', 'Record simulated credit',
                                      'Apply part to a simulated bill', 'Apply the remaining simulated balance'):
                            if not page.locator('dialog').is_visible():
                                page.locator('tr').filter(has=page.get_by_text(case_id, exact=True)).get_by_role('button').click()
                            with page.expect_response(lambda r: r.request.method=='POST' and '/actions/' in r.url) as changed:
                                page.get_by_role('button', name=label, exact=True).click()
                            if changed.value.status!=200:
                                raise RuntimeError('PositiveReconciliationUIRejected')
                        page.locator('#case-content').get_by_text('No actions are available in the current server state.', exact=True).wait_for()
                        rendered = page.locator('#case-content').inner_text()
                        case = read_case()
                        rec = case['reconciliation']
                        joins = {'receipt': bool(case['submissions']) and case['submissions'][0]['id'] in rendered,
                                 **{k: bool(rec[k+'_ids']) and all(i in rendered for i in rec[k+'_ids'])
                                    for k in ('credit','bill','application')}}
                        rows.append(observation('A-ui-financial-join-ids', joins, dict.fromkeys(joins,True)))
                    except Exception as exc:
                        rows.append(dict(id='A-ui-financial-join-ids', category='defect',
                                         unavailable={'error_type':type(exc).__name__, 'stage':'financial-ui-after-security-control'}))
                    for row in rows:
                        row['browser_version'] = browser.version
                    return rows
                finally:
                    browser.close()
        finally:
            if neighbor is not None:
                neighbor.shutdown()
                neighbor.server_close()
            if service is not None:
                service.should_exit=True
            if runner is not None:
                runner.join(5)
            sock.close()
