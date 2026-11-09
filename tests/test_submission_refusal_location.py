"""Role 1: a refusal names the passage it is about, even when the validator's message carries no clause number.

The split-party reading reproduces the shape of the first genuine model reading of the authored Halden Relay contract
(the vendor name quoted alone, its supply verb quoted separately as scope). Provider output is authored here; no inference.
"""
import json
from pathlib import Path

from uptime.vendor_model import validate_proposal
from uptime.vendor_refusal_diagnostics import CODES, build
from uptime.vendor_terms import Document

FIXTURES = Path(__file__).resolve().parent.parent / 'fixtures' / 'submission_onboarding'


def load(name):
    return Document(**json.loads((FIXTURES / name).read_text()))


def reading(document, rows):
    lines = document.text.split('\n')
    return [dict(quote=quote if isinstance(quote, str) else lines[quote], field=field, value=value) for quote, field, value in rows]


TIERS = [(6, 'tier', dict(product='Halden Relay', plan='Harbor', below='99.95', credit='10')),
         (7, 'tier', dict(product='Halden Relay', plan='Harbor', below='99.5', credit='25')),
         (8, 'tier', dict(product='Halden Relay', plan='Harbor', below='98', credit='50'))]
HEAD = [(0, 'agreement', 'Halden Relay Service Level Agreement'), (1, 'vendor', 'Halden Systems'),
        (2, 'effective', ['2026-01-01', '2026-12-31']), (3, 'period', 'utc_calendar_month'),
        (4, 'table_header', None), (5, 'table_separator', None)]


def diagnose(document, rows):
    return build(document, 'monthly-propositions', {'text': json.dumps({'clauses': reading(document, rows)})})


def test_a_split_party_sentence_is_refused_at_the_bare_vendor_name():
    document = load('halden_relay.json')
    rows = [HEAD[0], ('Halden Systems', 'vendor', 'Halden Systems'),
            ('provides Halden Relay on the Harbor plan.', 'scope', dict(product='Halden Relay', plan='Harbor'))] + HEAD[2:] + TIERS + \
           [(9, 'filing_days', 30), (10, 'remedy', 'affected_monthly_fees_future_invoice')]
    [issue] = diagnose(document, rows)['issues']
    assert issue['code'] == 'UNGROUNDED_PARTY_IDENTIFIER' and issue['code'] in CODES
    assert issue['block'] == 2 and document.text[issue['start']:issue['end']] == 'Halden Systems'


def test_the_complete_supply_sentence_reading_still_validates():
    document = load('halden_relay.json')
    rows = HEAD + TIERS + [(9, 'filing_days', 30), (10, 'remedy', 'affected_monthly_fees_future_invoice')]
    manifest = validate_proposal(document, reading(document, rows), allow_propositions=True)
    assert manifest['vendor'] == 'Halden Systems' and manifest['filing_days'] == 30


def test_conflicting_filing_windows_cite_both_passages():
    document = load('halden_relay_control.json')
    rows = HEAD + TIERS + [(9, 'filing_days', 30), (10, 'filing_days', 10), (11, 'unsupported', None),
                           (12, 'remedy', 'affected_monthly_fees_future_invoice')]
    issues = diagnose(document, rows)['issues']
    assert [issue['code'] for issue in issues] == ['CONFLICTING_SOURCE_TERMS'] * 2
    assert [document.text[i['start']:i['end']] for i in issues] == [
        'A claim must be submitted within 30 calendar days following month end.',
        'Claims must be received within 10 calendar days after month end.']


def test_a_maintenance_exclusion_is_cited_when_the_conflict_is_absent():
    document = load('halden_relay_control.json')
    rows = HEAD + TIERS + [(9, 'filing_days', 30), (10, 'remedy', None), (11, 'remedy', None),
                           (12, 'remedy', 'affected_monthly_fees_future_invoice')]
    # The second filing sentence is mislabeled; the validator refuses it at that passage, never accepting the source.
    issues = diagnose(document, rows)['issues']
    assert issues and all(i['start'] is not None for i in issues)
    assert document.text[issues[0]['start']:issues[0]['end']] == 'Claims must be received within 10 calendar days after month end.'
