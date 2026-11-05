#!/usr/bin/env python3
"""Capture a captioned, two-minute walkthrough of the *real* offline web application."""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time

WIDTH, UI_HEIGHT, HEIGHT = 1280, 760, 900
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


@dataclass
class Shot:
    image: Path
    seconds: int
    chapter: str
    lines: tuple
    still: str = ''


@contextmanager
def serve(db, secret):
    from uptime.server import create_app
    import uvicorn
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(128)
        origin = 'http://127.0.0.1:' + str(listener.getsockname()[1])
        app = create_app(db, rehearsal_secret=secret, mode='replay', rehearsal=True,
                         approvals_enabled=True, origin=origin)
        server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False, log_config=None))
        worker = Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        worker.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not worker.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError('Loopback server failed to start')
                time.sleep(.04)
            yield 'http://127.0.0.1:' + str(listener.getsockname()[1])
        finally:
            server.should_exit = True
            worker.join(timeout=10)


class Director:
    def __init__(self, page, origin, work):
        self.page, self.origin, self.work = page, origin, work
        self.shots = []
        self.case_id = None

    def get(self, path):
        return self.page.evaluate("path => window.uptimeAPI(path)", path)

    def view(self, route):
        page = self.page
        if page.locator('dialog[open]').count():
            page.locator('#close-inspector').click()
        page.goto(self.origin + '/#' + route, wait_until='networkidle')
        page.locator('#content[aria-busy=false] :is(h1, h2)').first.wait_for()
        page.evaluate('window.scrollTo(0,0)')
        self.case_id = None

    def case(self, case_id):
        self.view('dashboard')
        data = self.get('/api/cases/' + case_id)
        self.page.locator('tbody tr').filter(has=self.page.get_by_text(case_id, exact=True)).get_by_role('button').click()
        self.page.get_by_role('heading', name=data['title'], exact=True).wait_for()
        self.case_id = case_id
        self.page.locator('#inspector').evaluate('e=>e.scrollTop=0')
        return data

    def action(self, key):
        page = self.page
        path = '/api/cases/' + self.case_id if self.case_id else '/api/onboarding'
        state = self.get(path)
        offered = [a for a in state['actions'] if a['id'].split('~')[0] == key]
        assert len(offered) == 1, f'Action {key} is not currently offered'
        action = offered[0]
        scope = page.locator('#inspector' if self.case_id else '#content')
        with page.expect_response(lambda r: r.request.method == 'POST' and '/actions/' in r.url) as sent:
            scope.get_by_role('button', name=action['label'], exact=True).click()
        response = sent.value
        assert response.ok, f'Server rejected {key}'
        data = response.json()
        page.wait_for_load_state('networkidle')
        if self.case_id:
            page.get_by_role('heading', name=data['title'], exact=True).wait_for()
            page.locator('#inspector').evaluate('e=>e.scrollTop=0')
        else:
            page.locator('.lab-state').get_by_text(data['state'], exact=True).wait_for()
            page.evaluate('window.scrollTo(0,0)')
        return data

    def focus(self, locator, top=84):
        # Scroll the actual document or inspector. Do not move or rewrite any product content.
        locator.evaluate("""(el, top) => {
          const box=el.closest('dialog');
          if (box) box.scrollTop += el.getBoundingClientRect().top - box.getBoundingClientRect().top - top;
          else window.scrollBy(0, el.getBoundingClientRect().top - top);
        }""", top)

    def shot(self, seconds, chapter, first, second, still=''):
        path = self.work / f'scene-{len(self.shots)+1:02}.png'
        self.page.screenshot(path=str(path), animations='disabled')
        self.shots.append(Shot(path, seconds, chapter, (first, second), still))
        print(f'Captured scene {len(self.shots):02} / {chapter}', flush=True)

    def perform(self):
        self.view('dashboard')
        dashboard = self.get('/api/dashboard')
        assert dashboard['mode'] == 'replay' and dashboard['actual_applied'] is None
        assert any(m['value'] == '$7,500.00' for m in dashboard['metrics'])
        self.shot(6, 'Finance workbench', 'An unpaid invoice shows $7,500 of exposure. Recovery starts at $0 applied.',
                  'The dashboard keeps those measures separate.', 'dashboard')
        case = self.case('price-prepayment')
        assert case['amount'] == '7500.00'
        self.shot(7, 'Prevent  /  Flag before approval', 'The pending invoice comes to $30,000. Uptime isolates the usage line',
                  'and applies the signed amendment for the month of performance.')
        self.focus(self.page.locator('.trace li').filter(has_text='billed net').first, 208)
        self.shot(9, 'Prevent  /  Recompute the line', 'Usage billed at $27,500 prices to $20,000 under the negotiated tiers.',
                  'The $7,500 difference is flagged for review. No savings have been booked.')
        assert self.case('sla-eligible')['outcome'] == 'ELIGIBLE'
        self.shot(7, 'Recover  /  Qualifying SLA', 'A synthetic Twilio outage qualifies for a $100 candidate credit.',
                  'The 10% rate applies to $1,000 in eligible API fees. Carrier fees and taxes are excluded.')
        assert self.case('sla-ineligible')['outcome'] == 'INELIGIBLE'
        self.focus(self.page.locator('.trace li').filter(has_text='Excluded').first, 135)
        self.shot(7, 'Recover  /  Refuse the excluded interval', 'The same hour inside an excluded maintenance window contributes no downtime.',
                  'Availability meets the threshold and the contract yields no service credit.')
        self.case('dispute-cure')
        self.action('approve-claim')
        denied = self.action('submit-claim')
        assert denied['stage'] == 'NEEDS_EVIDENCE'
        self.shot(7, 'Dispute  /  Missing evidence', 'The simulated vendor requests proof of the affected component and interval.',
                  'The claim remains open. Its estimated amount is still unawarded.')
        supplemented = self.action('prepare-response')
        assert supplemented['stage'] == 'RESPONSE_DRAFTED'
        self.focus(self.page.get_by_role('heading', name='Decision trace', exact=True))
        self.shot(7, 'Dispute  /  Cure the gap', 'The claimant locates the existing attachment in its scoped archive.',
                  'The scripted reviewer must authorize the supplement before a follow-up can leave.')
        self.action('approve-response')
        self.action('advance-cooldown')
        award = self.action('submit-response')
        assert award['ledger']['awarded'] == '100.00' and award['ledger']['applied'] == '0.00'
        self.focus(self.page.locator('#inspector h3').get_by_text('Awarded', exact=True))
        self.shot(7, 'Dispute  /  Simulated award', 'After the permitted follow-up, the vendor simulator awards $100.',
                  'The award has not yet been posted or applied to a bill.')
        self.case('dispute-denial')
        self.action('approve-claim')
        denial = self.action('submit-claim')
        assert denial['stage'] == 'DENIAL_ACCEPTED' and not denial['actions']
        self.focus(self.page.get_by_role('heading', name='Decision trace', exact=True))
        self.shot(7, 'Dispute  /  Accept a correct denial', 'A different customer record confirms the advance maintenance notice.',
                  'Uptime accepts the denial and closes the case without another appeal.', 'denial')
        self.case('dispute-review')
        self.action('approve-claim')
        review = self.action('submit-claim')
        assert review['stage'] == 'HUMAN_REVIEW' and not review['actions']
        self.focus(self.page.get_by_role('heading', name='Decision trace', exact=True))
        self.shot(7, 'Dispute  /  Escalate a genuine disagreement', 'Here the records cannot establish when maintenance notice was given.',
                  'The $100 dispute goes to human review and automated correspondence stops.')
        self.case('dispute-cure')
        posted = self.action('record-credit')
        assert posted['stage'] == 'POSTED'
        self.focus(self.page.locator('#inspector h3').get_by_text('Posted', exact=True))
        self.shot(6, 'Reconcile  /  Record the credit', 'Back in the cured case, the reviewer records the $100 simulated credit.',
                  'Posting creates a credit record. It leaves the applied balance at $0.')
        partial = self.action('apply-partial')
        assert partial['stage'] == 'PARTIALLY_APPLIED' and partial['ledger']['applied'] == '50.00'
        self.view('dashboard')
        self.focus(self.page.get_by_role('region', name='Financial stages'), 32)
        self.shot(8, 'Reconcile  /  Partial application', 'Only $50 of the $100 posted credit has been matched to a simulated bill.',
                  'The ledger preserves the other $50 as unapplied.', 'partial-application')
        self.view('onboarding')
        lab = self.get('/api/onboarding')
        assert lab['state'] == 'SHADOW' and lab['reviewer'] is None and all(c['passed'] for c in lab['checks'])
        self.focus(self.page.locator('.lab-state'), 38)
        self.shot(9, 'Expand  /  Generated adapter in shadow', 'Atlassian’s published rules generated a candidate with a separate Jira plan overlay.',
                  'It passed 14 generated tests, 23 independent term checks and 18 held-out cases.', 'shadow')
        approved = self.action('approve')
        assert approved['state'] == 'APPROVED' and approved['reviewer'] == 'scripted-test-reviewer'
        self.shot(5, 'Expand  /  Scripted approval', 'The scripted test reviewer approves this specific version in the disposable database.',
                  'Approval leaves the adapter inactive.')
        active = self.action('activate')
        assert active['state'] == 'ACTIVE' and active['active_version'] == active['version']
        self.shot(5, 'Expand  /  Local activation', 'A separate action activates the reviewed version only in this rehearsal.',
                  'There is no external deployment or vendor filing.')
        rolled = self.action('rollback')
        assert rolled['state'] == 'REVOKED' and rolled['active_version'] is None
        self.shot(7, 'Expand  /  Rollback', 'Rolling back the first version clears the local activation.',
                  'Its approval, activation and rollback remain in the candidate history.', 'rollback')
        self.view('dashboard')
        self.shot(9, 'Finance workbench  /  Provenance', 'The $50 applied here is simulated. Separate read-only Ramp sandbox evidence',
                  'verifies provider access. This offline walkthrough shows no actual customer recovery.')
        assert sum(s.seconds for s in self.shots) == 120


def encode(shots, work, dest):
    def timestamp(seconds):
        return f'0:{seconds//60:02}:{seconds%60:02}.00'
    # Put captions in a separate editorial band below the unmodified browser image.
    styles = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 900
WrapStyle: 2
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Line,Avenir Next,29,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: Label,Avenir Next,17,&H00ABE9C0,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0.7,0,1,0,0,7,0,0,0,1
Style: Stamp,Avenir Next,15,&H00DDD3C7,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0.5,0,1,0,0,9,0,0,0,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    concat, subs, timing = [], [styles], []
    cursor = 0
    for i, shot in enumerate(shots, 1):
        concat += [f"file '{shot.image.name}'", f'duration {shot.seconds:.2f}']
        def caption(style, tag, line):
            subs.append(f'Dialogue: 0,{timestamp(cursor)},{timestamp(cursor+shot.seconds)},{style},,0,0,0,,{{{tag}}}{line}\n')
        caption('Label', r'\pos(46,772)', f'{i:02}   /   {shot.chapter.upper()}')
        caption('Stamp', r'\pos(1234,774)', 'OFFLINE REHEARSAL  ·  SCRIPTED TEST REVIEWER')
        caption('Line', r'\pos(46,804)', r'\N'.join(shot.lines))
        timing.append({'start_s': cursor, 'duration_s': shot.seconds, 'chapter': shot.chapter})
        cursor += shot.seconds
    concat.append(f"file '{shots[-1].image.name}'")
    (work / 'frames.txt').write_text('\n'.join(concat) + '\n')
    (work / 'captions.ass').write_text(''.join(subs))
    mp4 = dest / 'walkthrough.mp4'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','concat','-safe','1','-i','frames.txt',
                    '-vf','fps=24,pad=1280:900:0:0:0x171c40,ass=captions.ass','-c:v','libx264','-preset','fast',
                    '-crf','17','-pix_fmt','yuv420p','-t','120','-movflags','+faststart',str(mp4)],cwd=work,check=True)
    for shot, row in zip(shots, timing):
        if shot.still:
            subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(row['start_s']+1),
                            '-i',str(mp4),'-frames:v','1',str(dest/(shot.still+'.png'))],check=True)
    probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
                        'stream=codec_name,width,height,pix_fmt,duration,nb_frames','-of','json',str(mp4)]))['streams'][0]
    assert probe['codec_name']=='h264' and probe['pix_fmt']=='yuv420p' and int(probe['nb_frames'])==2880
    assert (probe['width'],probe['height'],float(probe['duration'])) == (WIDTH,HEIGHT,120.0)
    (dest/'manifest.json').write_text(json.dumps({'video':probe,'scenes':timing,'identity':'scripted-test-reviewer',
        'database':'fresh disposable replay','network':'loopback only','capture':'actual browser frames with timed editorial captions'},indent=2)+'\n')


def record(app_root, destination):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, str(app_root.resolve()))
    from scripts.browser_replay import local_connections_only, allowed_browser_url, REDACT_RENDERED_TEXT, scripted_login
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Output must be a new or empty directory')
    destination.mkdir(parents=True, exist_ok=True)
    # Stage the media in a private directory. A failed capture cannot masquerade as completed output.
    with tempfile.TemporaryDirectory(prefix='uptime-film-') as temp:
        work = Path(temp)
        media = work/'complete'
        media.mkdir()
        secret = secrets.token_urlsafe(32)
        with local_connections_only(), serve(work/'replay.sqlite', secret) as origin, sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME,headless=True,
                                         args=['--disable-background-networking','--disable-sync'])
            try:
                context = browser.new_context(viewport={'width':WIDTH,'height':UI_HEIGHT},device_scale_factor=1,
                                              service_workers='block',reduced_motion='reduce')
                failures = []
                def intercept(route):
                    if allowed_browser_url(route.request.url, origin):
                        route.continue_()
                    else:
                        failures.append('nonlocal connection')
                        route.abort()
                context.route('**/*',intercept)
                context.route_web_socket('**/*',lambda ws: ws.close())
                context.add_init_script(REDACT_RENDERED_TEXT)
                page = context.new_page()
                scripted_login(page, origin, secret)
                page.on('pageerror',lambda _: failures.append('browser script error'))
                page.on('response',lambda r: failures.append('HTTP error') if r.status>=400 else None)
                page.set_default_timeout(8000)
                director = Director(page,origin,work)
                director.perform()
                assert not failures, str(failures)
            finally:
                browser.close()
        encode(director.shots,work,media)
        import shutil
        for item in sorted(media.iterdir()):
            shutil.copy2(item,destination/item.name)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        record(args.app_root,args.output)
    except Exception as error:
        # Browser exceptions may include credential-bearing requests; print only safe local diagnostics.
        print('Recording failed:',type(error).__name__,file=sys.stderr)
        if isinstance(error,(AssertionError,ValueError,RuntimeError)) and error.args:
            print(str(error).splitlines()[0][:150],file=sys.stderr)
        raise SystemExit(1)
