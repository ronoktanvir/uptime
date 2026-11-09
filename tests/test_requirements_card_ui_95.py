"""The vendor card renders the real requirements payload read-only (W7 view of decisions 90 and 97)."""
import json
from pathlib import Path
import subprocess

from uptime import vendor_requirements as req

from test_vendor_catalog import V, api, install  # noqa: F401 (fixture)

ROOT = Path(__file__).resolve().parents[1]


def render(tmp_path, c):
    detail, body = c.get(V).json(), c.get(V + '/requirements').json()
    payload = tmp_path / 'payload.json'
    payload.write_text(json.dumps({'vendor_id': detail['vendor_id'], 'detail': detail, 'requirements': body}))
    result = subprocess.run(['node', 'tests/helpers/render_requirements.cjs', str(payload)], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    return detail, body, json.loads(result.stdout)


def test_real_monthly_requirements_render_every_element_requirement_and_draft_read_only(api, tmp_path):
    c, _, _, _ = api
    install(c)
    detail, body, view = render(tmp_path, c)
    text, card = view['text'], body['card']
    assert [e['element'] for e in card['elements']] == list(req.ELEMENTS)
    for element in card['elements']:
        name = {'source_clauses': 'Source clauses', 'eligible_fee': 'Eligible fee', 'evidence': 'Evidence',
                'exclusions': 'Exclusions', 'deadline': 'Claim deadline', 'submission_channel': 'Submission channel'}[element['element']]
        assert name + ': ' in text
        if element['citations']:
            assert 'Cited clauses ' + ', '.join(map(str, element['citations'])) in text
    quotes = {cite['id']: cite['quote'] for cite in detail['manifest']['citations']}
    cited = [quotes[i] for e in card['elements'] for i in e['citations']]
    assert view['blockquotes'] == cited
    for line in card['review_requirements'] + body['family_selection']['review_requirements']:
        assert line in text
    assert 'Selected monthly-availability/1 by deterministic document parser.' in text
    assert body['drafts']['notice'] in text and 'Generated drafts (not independent tests; placeholder fee)' in text
    first = body['drafts']['scenarios'][0]
    assert first['name'] in text and 'USD ' + first['derived']['amount'] in text and 'USD 1000.00' in text
    assert 'Read only. These requirements grant no approval, activation or dispatch.' in text
    assert body['authority'] == {'approval_gate': False, 'dispatch_authorized': False}
    assert [call['method'] for call in view['calls']] == ['GET', 'GET', 'GET'] and view['markup'] == 0
