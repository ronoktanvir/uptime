"""Real Chrome against a live authored workspace: four destinations, one workspace name, reload and drag-and-drop sign-in."""
import json

from playwright.sync_api import expect

from test_finance_browser_90 import browser_page, intents, live_workspace, login

DESTINATIONS = [('Overview', '#overview', 'Northwind Cloud'), ('Cases', '#cases', None), ('Agreements', '#agreements', None),
                ('Activity', '#activity', 'Activity')]


def topbar(page):
    return page.locator('#workspace-name').inner_text()


def test_workspace_name_is_the_same_whatever_page_opens_first(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 1280, 'height': 900}) as (page, errors):
        # Open an advanced tool first; the name must not depend on visit order.
        page.goto(origin + '/#lab')
        page.get_by_role('heading', name='Sign in to Uptime', exact=True).wait_for()
        page.get_by_label('Account name', exact=True).fill('scripted-test-reviewer')
        page.get_by_label('Credential file', exact=True).set_input_files({
            'name': 'scripted-reviewer.jwk', 'mimeType': 'application/json', 'buffer': (directory / 'scripted-reviewer.jwk').read_bytes()})
        page.get_by_role('button', name='Sign in', exact=True).click()
        expect(page.locator('#workspace-name')).to_have_text('Harborline Analytics')
        assert page.title() == 'Harborline Analytics · Uptime'
        for label, route, title in DESTINATIONS:
            page.locator('nav.rail-primary').get_by_role('link', name=label, exact=True).click()
            assert page.url.endswith(route)
            if title:
                expect(page.get_by_role('heading', name=title, exact=True).first).to_be_visible()
            expect(page.locator('#workspace-name')).to_have_text('Harborline Analytics')
            assert page.title() == 'Harborline Analytics · Uptime'
            assert page.locator('nav.rail-primary a[aria-current=page]').inner_text().split('\n')[-1].strip() == label
        body = page.locator('body').inner_text()
        assert 'Finance workbench' not in body and 'Contract operations' not in body
        assert intents(directory) == 0 and errors == []


def test_reload_keeps_reading_but_disables_actions_with_one_way_back(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 1280, 'height': 900}) as (page, errors):
        page.goto(origin + '/')
        login(page, directory)
        approve = page.get_by_role('button', name='Approve January claim', exact=True)
        expect(approve).to_be_enabled()
        # A reload keeps the read session but clears the in-memory signing key.
        page.reload()
        page.get_by_role('heading', name='Needs attention', exact=True).wait_for()
        expect(page.locator('#finance-outcome')).to_contain_text('$2,400.00')
        expect(approve).to_be_disabled()
        expect(page.locator('#finance-recovery')).to_contain_text('Reading only: reloading the page cleared the signing key.')
        assert page.evaluate("""() => {
            const stores = [JSON.stringify(Object.entries(localStorage)), JSON.stringify(Object.entries(sessionStorage)), location.href];
            return stores.every(text => !/"d"\\s*:|\\bkty\\b|PRIVATE/.test(text));
        }""")
        approve.click(force=True)
        assert intents(directory) == 0
        page.get_by_role('button', name='Sign in again to take actions', exact=True).click()
        page.get_by_role('heading', name='Sign in to Uptime', exact=True).wait_for()
        expect(page.get_by_label('Account name', exact=True)).to_have_value('scripted-test-reviewer')
        page.get_by_label('Credential file', exact=True).set_input_files({
            'name': 'scripted-reviewer.jwk', 'mimeType': 'application/json', 'buffer': (directory / 'scripted-reviewer.jwk').read_bytes()})
        page.get_by_role('button', name='Sign in', exact=True).click()
        page.get_by_role('heading', name='Needs attention', exact=True).wait_for()
        page.get_by_role('button', name='Approve January claim', exact=True).click()
        expect(page.locator('#finance-recovery .help[role=status]')).to_contain_text('Recorded: Approve January claim.')
        assert intents(directory) == 1 and errors == []


def test_credential_file_can_be_dropped_on_the_sign_in_form_and_errors_name_the_file(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 390, 'height': 844}) as (page, errors):
        page.goto(origin + '/')
        page.get_by_role('heading', name='Sign in to Uptime', exact=True).wait_for()
        expect(page.locator('form')).to_contain_text('Workspace setup prints the account name and where its credential file was saved.')
        page.get_by_label('Account name', exact=True).fill('scripted-test-reviewer')
        page.get_by_role('button', name='Sign in', exact=True).click()
        expect(page.locator('form')).to_contain_text('Choose the credential file named in the setup output, or drag it here.')
        jwk = (directory / 'scripted-reviewer.jwk').read_text()
        page.evaluate("""text => {
            const form = document.querySelector('form'), transfer = new DataTransfer();
            transfer.items.add(new File([text], 'scripted-reviewer.jwk', {type: 'application/json'}));
            form.dispatchEvent(new DragEvent('drop', {dataTransfer: transfer, bubbles: true, cancelable: true}));
        }""", jwk)
        expect(page.locator('form')).to_contain_text('Credential file selected: scripted-reviewer.jwk')
        page.get_by_role('button', name='Sign in', exact=True).click()
        page.get_by_role('heading', name='Needs attention', exact=True).wait_for()
        assert page.evaluate('window.uptimeAuth.canSign()') is True
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert json.loads(jwk)['d'] not in page.content()
        assert intents(directory) == 0 and errors == []


def test_four_destinations_fit_a_phone_and_the_overview_leads_with_the_outcome(tmp_path):
    with live_workspace(tmp_path) as (app, origin, directory), browser_page(origin, {'width': 390, 'height': 844}) as (page, errors):
        page.goto(origin + '/')
        login(page, directory)
        outcome = page.locator('#finance-outcome')
        expect(outcome).to_contain_text('January service credit')
        expect(outcome).to_contain_text('March price exception')
        expect(outcome).to_contain_text('Separate from the service credit and not included in it.')
        steps = page.locator('.lifecycle-step .step-label')
        expect(steps).to_have_text(['Estimated', 'Claimed', 'Awarded', 'Posted to Local ledger', 'Applied to bill'])
        text = page.locator('#content').inner_text()
        assert '/1000000%' not in text
        for _, route, _ in DESTINATIONS:
            page.goto(origin + '/' + route)
            expect(page.locator('#content')).to_have_attribute('aria-busy', 'false')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), route
        activity = page.locator('#content')
        expect(activity).to_contain_text('Workflow history')
        assert intents(directory) == 0 and errors == []


def test_automation_workspace_needs_four_person_decisions_and_activity_shows_every_step(tmp_path):
    """The default setup runs routine steps on the server under recorded authority; the page only shows the record."""
    with live_workspace(tmp_path, routine_automation=True) as (app, origin, directory), \
            browser_page(origin, {'width': 1440, 'height': 900}) as (page, errors):
        page.goto(origin + '/')
        login(page, directory)
        recovery = page.locator('#finance-recovery')
        expect(recovery).to_contain_text('Routine steps: Paused · Waiting for a reviewer to approve.')
        clicks = []
        for _ in range(12):
            buttons = recovery.locator('.actions button:not([disabled])')
            if buttons.count() == 0:
                break
            label = buttons.first.inner_text().strip()
            buttons.first.click()
            clicks.append(label)
            expect(recovery.locator('.help[role=status]')).to_contain_text('Recorded: ' + label + '.')
        assert clicks[0] == 'Approve January claim' and clicks[-1] == 'Apply credit to eligible invoice', clicks
        assert len(clicks) == 4, clicks
        outcome = page.locator('#finance-outcome')
        expect(outcome).to_contain_text('April invoice NW-2026-04')
        expect(outcome).to_contain_text('$11,000.00')
        expect(outcome).to_contain_text('$8,600.00')
        page.locator('nav.rail-primary').get_by_role('link', name='Activity', exact=True).click()
        steps = page.locator('.automation-step')
        expect(steps).to_have_count(11)
        expect(page.locator('#content')).to_contain_text('Routine steps: Complete. 4 reviewer decisions and 7 automatic steps recorded.')
        assert page.locator('.automation-step', has_text='Decided by').count() == 4
        assert page.locator('.automation-step', has_text='Run automatically under the approval recorded by').count() == 2
        assert page.locator('.automation-step', has_text='Received automatically: event').count() == 5
        text = page.locator('#content').inner_text()
        assert 'Filing cutoff' in text and 'response cooldown' in text
        assert not any(token in text for token in ('T12:00:00', '+00:00'))
        assert errors == []
