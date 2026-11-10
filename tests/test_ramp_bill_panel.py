"""Real Chrome at the width of a side panel: the one-bill page beside Ramp, on a live authored workspace."""
from urllib.parse import urlsplit

from playwright.sync_api import expect

from uptime.auth import SCRIPT
from test_finance_browser_90 import browser_page, intents, live_workspace

BILL = 'f74ba12c-95d0-582d-9f62-26d8057d1d37'
PANEL = {'width': 420, 'height': 900}
WALKTHROUGH = ('Northwind', 'service credit', 'price exception', '$2,400.00', '$8,600.00', '$11,000.00', '$1,000.00')


def sign_in(page, directory):
    page.get_by_role('heading', name='Sign in to Uptime', exact=True).wait_for()
    page.get_by_label('Account name', exact=True).fill(SCRIPT)
    page.get_by_label('Credential file', exact=True).set_input_files({
        'name': 'scripted-reviewer.json', 'mimeType': 'application/json', 'buffer': (directory / 'scripted-reviewer.jwk').read_bytes()})
    page.get_by_role('button', name='Sign in', exact=True).click()


def api_reads(requests):
    return [path for method, path in requests if method == 'GET' and path.startswith('/api/')]


def test_the_verified_bill_card_is_in_the_first_viewport_of_a_420_px_panel(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, PANEL) as (page, errors):
        requests = []
        page.on('request', lambda r: requests.append((r.method, urlsplit(r.url).path)))
        # Ramp's own bill id, in another letter case than the saved record holds.
        page.goto(origin + '/#ramp-bill/' + BILL.upper())
        sign_in(page, directory)
        card = page.locator('.ramp-bill-card')
        expect(card).to_be_visible()
        expect(page.get_by_role('heading', name='DocuSign', exact=True)).to_be_visible()
        # The whole card, with its amount and the statement that it is a saved read, sits in the first viewport.
        box = card.bounding_box()
        assert box['y'] >= 0 and box['y'] + box['height'] <= PANEL['height'], box
        assert page.evaluate('scrollY') == 0
        for text in ('USD 840', 'OPEN', 'APPROVAL_PENDING', BILL, 'started by a person. Not a live read.'):
            expect(card).to_contain_text(text)
        # The navigation is a slim header at this width, not the first screen.
        assert page.locator('aside.rail').bounding_box()['height'] <= 140
        content = page.locator('#content').inner_text()
        for text in ('Evidence gap: the governing agreement or usage evidence is missing', 'No agreement on file for this bill.',
                     'No contract finding is attached to this bill.', 'No credits applied to this bill.',
                     'Posted by a person in Ramp; Uptime read it back on this bill', 'Uptime has made no write to Ramp.'):
            assert text in content, text
        # Nothing from the walkthrough's own agreement is beside this bill, and one read served the page.
        for text in WALKTHROUGH:
            assert text not in content, text
        assert api_reads(requests) == ['/api/ramp/workspace'], api_reads(requests)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        expect(page.get_by_role('link', name='Open the full record', exact=True)).to_have_attribute('href', '#records')
        assert intents(directory) == 0 and errors == []


def test_an_unknown_bill_says_so_and_ramp_records_opens_without_filling_the_panel_with_navigation(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, PANEL) as (page, errors):
        page.goto(origin + '/#ramp-bill/00000000-0000-0000-0000-000000000000')
        sign_in(page, directory)
        expect(page.locator('#content')).to_contain_text('This workspace has no saved record for this Ramp bill.')
        for text in WALKTHROUGH + ('DocuSign', 'USD 840'):
            assert text not in page.locator('#content').inner_text(), text
        page.get_by_role('link', name='Open Ramp records', exact=True).click()
        assert page.url.endswith('#records')
        expect(page.get_by_role('heading', name='Verified Ramp record', exact=True)).to_be_visible()
        assert page.locator('aside.rail').bounding_box()['height'] <= 140
        assert page.get_by_role('heading', name='Verified Ramp record', exact=True).bounding_box()['y'] < PANEL['height']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert intents(directory) == 0 and errors == []
