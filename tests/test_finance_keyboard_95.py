"""Real Chrome, keyboard only, at phone width: the authored demo path from skip link to applied credit."""
from playwright.sync_api import expect

from test_finance_browser_90 import browser_page, intents, live_workspace, login

STEPS = ['Approve January claim', 'File January claim', 'Receive vendor response', 'Attach requested log', 'Verify supplied log',
         'Approve response', 'Send response', 'Receive credit decision', 'Post to Local ledger', 'Receive next invoice',
         'Apply credit to eligible invoice']


def focused(page):
    return page.evaluate("(() => { const e = document.activeElement; return [e.tagName, (e.textContent || '').trim()]; })()")


def test_keyboard_only_demo_path_needs_a_deliberate_tab_before_each_decision(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 390, 'height': 844}) as (page, errors):
        page.goto(origin + '/#recovery')
        login(page, directory)
        # The skip link moves focus into the workbench without changing the view.
        page.locator('a.skip').focus()
        page.keyboard.press('Enter')
        assert page.evaluate('document.activeElement.id') == 'workspace'
        expect(page.get_by_role('heading', name='Northwind Cloud', exact=True)).to_be_visible()
        # Reach the first step by keyboard. After each recorded step focus returns to the recovery heading, so a
        # second Enter records nothing; one Tab reaches the next offered step.
        for _ in range(80):
            page.keyboard.press('Tab')
            if focused(page) == ['BUTTON', STEPS[0]]:
                break
        assert focused(page) == ['BUTTON', STEPS[0]]
        for index, label in enumerate(STEPS):
            assert focused(page) == ['BUTTON', label], (index, focused(page))
            page.keyboard.press('Enter')
            expect(page.locator('#finance-recovery .help[role=status]')).to_contain_text('Recorded: ' + label + '.')
            assert focused(page) == ['H2', 'January recovery'], (index, focused(page))
            assert intents(directory) == index + 1
            page.keyboard.press('Enter')
            assert intents(directory) == index + 1, 'Enter on the heading must not record the next step'
            if index + 1 < len(STEPS):
                expect(page.locator('#finance-recovery .help[role=status]')).to_contain_text('Next: ' + STEPS[index + 1] + '.')
                page.keyboard.press('Tab')
        expect(page.get_by_text('No actions available in the current state.', exact=True)).to_be_visible()
        assert focused(page) == ['H2', 'January recovery']
        assert intents(directory) == len(STEPS)
        expect(page.locator('#finance-bill')).to_contain_text('$8,600.00')
        # The guide by keyboard: Tab from the recovery heading reaches the question box; Enter asks.
        box = page.get_by_label('Question', exact=True)
        for _ in range(120):
            if page.evaluate("document.activeElement === document.querySelector('.guide-form input')"):
                break
            page.keyboard.press('Tab')
        expect(box).to_be_focused()
        page.keyboard.type('Did the credit reach Ramp?')
        page.keyboard.press('Enter')
        expect(page.locator('.guide-answer')).to_contain_text('Credits in this workspace are recorded in Local ledger.')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert intents(directory) == len(STEPS) and errors == []


def test_a_held_enter_records_one_decision_only(tmp_path):
    """A held key repeats keydown; only the first press may act, and focus leaves the next decision."""
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 1280, 'height': 900}) as (page, errors):
        page.goto(origin + '/#recovery')
        login(page, directory)
        page.get_by_role('button', name=STEPS[0], exact=True).focus()
        page.keyboard.down('Enter')
        for _ in range(12):
            page.keyboard.down('Enter')  # auto-repeat while held
            page.wait_for_timeout(40)
        page.keyboard.up('Enter')
        expect(page.locator('#finance-recovery .help[role=status]')).to_contain_text('Recorded: ' + STEPS[0] + '.')
        page.wait_for_timeout(300)
        assert intents(directory) == 1
        expect(page.get_by_role('button', name=STEPS[1], exact=True)).to_be_enabled()
        expect(page.get_by_role('button', name=STEPS[1], exact=True)).not_to_be_focused()
        assert errors == []
