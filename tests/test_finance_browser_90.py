"""Real Chrome against a live authored workspace: next actions, guide, keyboard, narrow screens and expired sessions."""
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import re
import socket
import sqlite3
import threading
import time

from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
import uvicorn

from scripts import setup_northwind as setup
from uptime.auth import SCRIPT

CHROME = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
PRODUCT_WORDS = re.compile(r'synthetic|simulat|replay|fixture|\bdemo\b|post to ramp', re.I)


@contextmanager
def live_workspace(tmp_path):
    sock = socket.socket(); sock.bind(('127.0.0.1', 0)); sock.listen(25)
    origin = 'http://127.0.0.1:' + str(sock.getsockname()[1])
    directory = tmp_path / 'owned'
    app, private, events = setup.prepare(directory, origin)
    with TestClient(app, base_url=origin, client=('127.0.0.1', 4510)) as client:
        setup.seed(client, app, private, events)
    server = uvicorn.Server(uvicorn.Config(app, log_level='critical', access_log=False))
    runner = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True); runner.start()
    try:
        for _ in range(300):
            if server.started: break
            time.sleep(.01)
        assert server.started
        yield app, origin, directory
    finally:
        server.should_exit = True; runner.join(timeout=5); sock.close()


@contextmanager
def browser_page(origin, viewport):
    with sync_playwright() as api:
        browser = api.chromium.launch(headless=True, **({'executable_path': str(CHROME)} if CHROME.exists() else {}))
        context = browser.new_context(viewport=viewport)
        context.route('**/*', lambda route: route.continue_() if route.request.url.startswith(origin + '/') else route.abort())
        page = context.new_page(); errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            yield page, errors
        finally:
            browser.close()


def login(page, directory):
    page.get_by_role('heading', name='Sign in to Uptime', exact=True).wait_for()
    page.get_by_label('Account name', exact=True).fill(SCRIPT)
    page.get_by_label('Credential file', exact=True).set_input_files({
        'name': 'scripted-reviewer.json', 'mimeType': 'application/json', 'buffer': (directory / 'scripted-reviewer.jwk').read_bytes()})
    page.get_by_role('button', name='Sign in', exact=True).click()
    page.get_by_role('heading', name='Needs attention', exact=True).wait_for()


def intents(directory):
    with sqlite3.connect(f'file:{directory / "workspace.db"}?mode=ro', uri=True) as db:
        return db.execute("SELECT count(*) FROM workspace_workflow_intent WHERE status='COMPLETED'").fetchone()[0]


def expire(app):
    app.state.auth.sessions = {key: replace(value, expires=0) for key, value in app.state.auth.sessions.items()}


def ask(page, question):
    box = page.get_by_label('Question', exact=True)
    box.fill(question); box.press('Enter')
    answer = page.locator('.guide-answer')
    expect(answer).not_to_contain_text('Reading this case')
    return answer


def test_attention_guide_keyboard_actions_and_expired_session_recovery(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 1360, 'height': 900}) as (page, errors):
        page.goto(origin + '/')
        login(page, directory)
        items = page.locator('.attention-item h3')
        expect(items).to_have_text(['File the January 2026 claim before the deadline', 'Approve the claim packet before it is filed',
                                    'Review invoice NW-2026-03 before payment', 'Complete March 2026 usage evidence',
                                    'Next step: Approve January claim'])
        expect(page.locator('#finance-ramp')).to_contain_text('Local ledger')
        expect(page.locator('#finance-ramp')).to_contain_text('No Ramp bill is linked to this agreement.')
        expect(page.locator('#finance-price table')).to_contain_text('amendment-v2')
        # Keyboard: a details button moves focus to its section heading without changing the route.
        page.locator('.attention-item').first.get_by_role('button', name='Show details').focus()
        page.keyboard.press('Enter')
        assert page.evaluate('document.activeElement.textContent') == 'January recovery'
        assert page.evaluate('location.hash') == ''
        # Keyboard guide: Enter submits; Tab reaches the citation; Enter on it focuses the cited section.
        answer = ask(page, 'When is the filing deadline?')
        expect(answer).to_contain_text('The January 2026 claim must be received before 2026-03-03T00:00:00+00:00. It has not been filed.')
        page.get_by_label('Question', exact=True).focus(); page.keyboard.press('Tab'); page.keyboard.press('Tab')
        assert page.evaluate('document.activeElement.textContent') == 'Source: Filing deadline'
        page.keyboard.press('Enter')
        assert page.evaluate('document.activeElement.textContent') == 'January recovery'
        expect(ask(page, 'What is the weather?')).to_contain_text("This case's records don't answer that.")
        expect(ask(page, 'Approve the claim')).to_contain_text("The guide is read-only and can't take that action.")
        assert intents(directory) == 0
        # An ordinary signed action, then a server-side session expiry before the next one.
        page.get_by_role('button', name='Approve January claim', exact=True).click()
        page.get_by_role('button', name='File January claim', exact=True).wait_for()
        expect(items).not_to_contain_text(['Approve the claim packet before it is filed'])
        assert intents(directory) == 1
        expire(app)
        page.get_by_role('button', name='File January claim', exact=True).click()
        login(page, directory)
        assert intents(directory) == 1
        page.get_by_role('button', name='File January claim', exact=True).click()
        page.get_by_role('button', name='Receive vendor response', exact=True).wait_for()
        assert intents(directory) == 2
        expect(items).not_to_contain_text(['File the January 2026 claim before the deadline'])
        # An expired session on a guide question also returns to sign-in and records nothing.
        expire(app)
        page.get_by_label('Question', exact=True).fill('What needs my attention?')
        page.get_by_label('Question', exact=True).press('Enter')
        login(page, directory)
        assert intents(directory) == 2
        content = page.locator('#content').inner_text()
        assert not PRODUCT_WORDS.search(content), PRODUCT_WORDS.search(content)
        for question in ['How was the January credit calculated?', 'Why is March unknown?', 'Did the credit reach Ramp?',
                         'Is CalyxQuay active?', 'What is the price finding?']:
            text = ask(page, question).inner_text()
            assert not PRODUCT_WORDS.search(text), (question, text)
        assert errors == []


def test_narrow_screen_error_empty_and_guide_failure_states(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 390, 'height': 844}) as (page, errors):
        page.goto(origin + '/')
        login(page, directory)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        answer = ask(page, 'How was the January credit calculated?')
        expect(answer).to_contain_text('January 2026 is eligible for a $2,400.00 service credit.')
        page.locator('#finance-months details.workflow-evidence', has_text='Calculation inputs').first.locator('summary').click()
        expect(page.locator('#finance-months')).to_contain_text('$12,000.00')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        # Empty question.
        page.get_by_label('Question', exact=True).fill('   '); page.get_by_label('Question', exact=True).press('Enter')
        expect(page.locator('.guide-answer')).to_have_text('Enter a question about this case.')
        # Guide failure: nothing changes and the message says so.
        page.route(origin + '/api/workspace/guide', lambda route: route.fulfill(status=500, json={'detail': 'unavailable'}))
        expect(ask(page, 'Why is March unknown?')).to_have_text('The guide could not answer just now. Nothing was changed. Try again.')
        page.unroute(origin + '/api/workspace/guide')
        # Load failure, then recovery with the same state.
        page.route(origin + '/api/workspace/workflow', lambda route: route.fulfill(status=500, json={'detail': 'Workspace unavailable'}))
        page.get_by_role('button', name='Refresh data', exact=True).click()
        page.get_by_role('heading', name='Unable to load this view', exact=True).wait_for()
        page.unroute(origin + '/api/workspace/workflow')
        page.get_by_role('button', name='Try again', exact=True).click()
        page.get_by_role('heading', name='Needs attention', exact=True).wait_for()
        # Empty state: a projection with nothing waiting.
        def empty(route):
            data = route.fetch().json()
            data['workflow']['finance']['attention'] = []
            data['workflow']['next_actions'] = []
            route.fulfill(json=data)
        page.route(origin + '/api/workspace/workflow', empty)
        page.get_by_role('button', name='Refresh data', exact=True).click()
        expect(page.locator('#finance-attention')).to_contain_text('Nothing in this case needs action now.')
        expect(page.locator('#finance-recovery')).to_contain_text('No actions available in the current state.')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert intents(directory) == 0
        assert errors == []
