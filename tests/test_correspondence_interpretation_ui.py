"""Synthetic browser behavior only; no claim of actual human review accuracy."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_blind_entry_precedes_model_display_and_no_effect_is_inferred():
    from playwright.sync_api import sync_playwright,expect,Error
    from test_correspondence_interpretation import TEXT,meaning
    context=dict(digest='0'*64,text=TEXT,text_sha256='1'*64,event_digest='2'*64,contract_version='3'*64,
                 contract_source_sha256='4'*64,scope=dict(month='2028-04',vendor='Public test vendor',service='Test service',region='east'),
                 claim='inbox-public-review',requested='46.25',currency='USD',filing_fields=[])
    candidate=dict(id='5'*64,origin='model',interpretation=meaning(TEXT).model_dump())
    payload=dict(context=context,visible_text=TEXT,blind_entry=None,candidates=[],model_enabled=True)
    html='<html><head><meta charset="utf-8"><link rel="stylesheet" href="/static/interpretation.css"><script defer src="/static/interpretation.js"></script><script defer src="/fixture.js"></script></head><body><main id="fixture"></main></body></html>'
    js='''window.calls=[]; window.fixtureData=DATA; window.fakeApi=async(path,body)=>{
      window.calls.push({path,body});
      if(path.endsWith('/blind-entry'))return {id:'blind'};
      if(path.endsWith('/candidates/model')){window.fixtureData.candidates=[CANDIDATE];return {id:'candidate'};}
      if(path.endsWith('/reviews'))return {id:'review'};
      if(path.endsWith('/preview'))return {disposition:'INFORMATIONAL_REVIEW',reported_award:'17.20',prepare_allowed:false};
      return window.fixtureData;
    }; window.UptimeInterpretation.mount(document.getElementById('fixture'),window.fakeApi,'inbox-public-review');'''.replace('DATA',json.dumps(payload)).replace('CANDIDATE',json.dumps(candidate))
    unexpected=[]; errors=[]
    def serve(route):
        path=urlsplit(route.request.url).path
        if path=='/':route.fulfill(body=html,content_type='text/html',headers={'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'none'"})
        elif path=='/fixture.js':route.fulfill(body=js,content_type='text/javascript')
        elif path in {'/static/interpretation.js','/static/interpretation.css'}:
            file=ROOT/'web'/path.rsplit('/',1)[-1]
            route.fulfill(body=file.read_text(),content_type='text/javascript' if file.suffix=='.js' else 'text/css')
        else:unexpected.append(path);route.abort()
    with sync_playwright() as pw:
        try:browser=pw.chromium.launch(channel='chrome' if Path('/Applications/Google Chrome.app').exists() else None)
        except Error:
            if os.environ.get('UPTIME_REQUIRE_BROWSER')=='1':raise
            pytest.skip('Browser unavailable')
        page=browser.new_page(viewport={'width':1200,'height':900});page.route('**/*',serve)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto('http://127.0.0.1:8765/')
        expect(page.get_by_role('heading',name='Review the vendor’s meaning')).to_be_visible()
        expect(page.get_by_role('button',name='Request interpretation')).to_be_hidden()
        for label,value in [('Main assertion','time_bar'),('Polarity','positive'),('Status of the assertion','asserted'),('Which claim?','current_claim'),('Additional objection or unresolved meaning?','no')]:
            page.get_by_label(label,exact=True).select_option(value)
        page.get_by_role('button',name='Save independent reading').click()
        expect(page.get_by_role('heading',name='Reconcile and attest the meaning')).to_be_visible()
        expect(page.get_by_role('checkbox').nth(0)).not_to_be_checked()
        expect(page.get_by_role('checkbox').nth(1)).not_to_be_checked()
        page.get_by_role('button',name='Request interpretation').click()
        expect(page.get_by_role('heading',name='Untrusted suggestions')).to_be_visible()
        page.get_by_text('Requested interpretation — requires your review',exact=True).click()
        page.get_by_role('button',name='Compare this suggestion').click()
        page.get_by_label('Your decision',exact=True).select_option('accept')
        page.get_by_label('Explanation of source meaning and any difference',exact=True).fill('Synthetic browser interaction; not an actual human study.')
        page.get_by_role('checkbox').nth(0).check();page.get_by_role('checkbox').nth(1).check()
        page.get_by_role('button',name='Save meaning review and inspect preview').click()
        expect(page.get_by_role('heading',name='Deterministic preview')).to_be_visible()
        expect(page.get_by_text('Interpreted reported award: USD 17.20; no ledger entry.',exact=True)).to_be_visible()
        expect(page.get_by_role('button',name='Prepare evidence-backed response draft')).to_have_count(0)
        calls=page.evaluate('window.calls')
        assert [row['path'].rsplit('/',1)[-1] for row in calls]==['interpretation','blind-entry','model','interpretation','reviews','preview']
        assert calls[1]['body']['interpretation']['propositions'][0]['source']['quote']==TEXT
        assert not errors and not unexpected
        browser.close()
