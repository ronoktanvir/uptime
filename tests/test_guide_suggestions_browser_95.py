"""Real Chrome on a live authored workspace: one-click guide questions stay read-only and keyboard-usable."""
from playwright.sync_api import expect

from test_finance_browser_90 import browser_page, intents, live_workspace, login


def test_suggested_questions_answer_read_only_by_click_and_keyboard_on_a_narrow_screen(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 390, 'height': 844}) as (page, errors):
        posts = []
        page.on('request', lambda r: posts.append(r.url.split(origin)[-1]) if r.method == 'POST' else None)
        page.goto(origin + '/')
        login(page, directory)
        group = page.get_by_role('group', name='Suggested questions')
        expect(group.get_by_role('button')).to_have_count(4)
        group.get_by_role('button', name='Did the credit reach Ramp?').click()
        answer = page.locator('.guide-answer')
        expect(answer).to_contain_text('Credits in this workspace are recorded in Local ledger.')
        expect(page.get_by_label('Question', exact=True)).to_have_value('Did the credit reach Ramp?')
        # Keyboard: the next suggestion is reachable with Tab and runs with Enter.
        group.get_by_role('button', name='Did the credit reach Ramp?').focus()
        page.keyboard.press('Shift+Tab')
        assert page.evaluate('document.activeElement.textContent') == 'Why is March undetermined?'
        page.keyboard.press('Enter')
        expect(answer).to_contain_text('March 2026 is undetermined, not ineligible')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        before = [p for p in posts if not p.startswith('/api/auth/')]
        assert before == ['/api/workspace/guide', '/api/workspace/guide']
        assert intents(directory) == 0 and errors == []
