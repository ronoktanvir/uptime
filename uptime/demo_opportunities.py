"""Demo line (film of November 10, 2026): a second vendor's estimated service credit.

Corvid Data Cooperative's authored agreement CDC-SLA-07 was read by claude-opus-5-5 in a recorded run on
November 9 (job 26ee4e3f, session 41f4dcb6). The scripted preparation installs that recorded reading, and this
module evaluates the authored October 2026 usage and invoice with the installed ACTIVE agreement's own
evaluator. Nothing here files a claim, approves, posts or applies anything, and nothing is added to Northwind's
figures. The amount, outcome, rate and citations are the evaluator's; this module only labels them.
"""
from decimal import Decimal
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'fixtures' / 'corvid_ledger_demo'
DOCUMENT = ROOT / 'fixtures' / 'submission_onboarding' / 'corvid_ledger.json'
VENDOR_ID = 'corvid-ledger'
ROUTE = 'agreements'


def _read(name):
    return json.loads((FIXTURES / name).read_text())


def load():
    return dict(document=json.loads(DOCUMENT.read_text()), overlay=_read('overlay.json'), usage=_read('usage.json'),
                invoice=_read('invoice.json'), estimate=_read('estimate.json'))


def fee_line(invoice, overlay):
    lines = [line for line in invoice['lines'] if line['ref'] == overlay['fee_line_ref']]
    if len(lines) != 1:
        raise ValueError('The invoice must carry exactly one covered fee line.')
    return lines[0]


def cents(amount):
    value = Decimal(amount) * 100
    if value != value.to_integral_value() or value < 0:
        raise ValueError('Invoice amounts must be whole, non-negative cents.')
    return int(value)


def facts(package):
    """The evaluator's observation fields, built only from the authored usage, invoice and estimate instant."""
    overlay, usage, invoice = package['overlay'], package['usage'], package['invoice']
    if invoice['service_month'] != usage['month'] or invoice['currency'] != overlay['currency']:
        raise ValueError('Usage and invoice must cover the same month and currency.')
    line = fee_line(invoice, overlay)
    return dict(agreement=overlay['agreement'], account=overlay['account'], product=overlay['product'], plan=overlay['plan'],
                month=usage['month'], eligible_downtime_minutes=usage['unavailable_minutes'],
                monitor_source='simulated_vendor', monitor_ref=usage['monitor_ref'], monitor_month=usage['month'],
                month_complete=usage['month_complete'], exclusions_removed=usage['exclusions_removed'],
                monthly_fee_cents=cents(line['amount']), fee_line_ref=line['ref'], fee_month=invoice['service_month'],
                fee_ref=invoice['id'], received_at=package['estimate']['as_of'])


def _percent(units):
    from .vendor_terms import PERCENT_SCALE
    return format((Decimal(units) / PERCENT_SCALE).normalize(), 'f') + '%'


def build(vendor, result, package):
    """One opportunity row from the installed agreement and the evaluator's result; None unless ELIGIBLE."""
    if not vendor or result.get('outcome') != 'ELIGIBLE' or result.get('amount') is None:
        return None
    manifest_citations = {c['id']: c for c in (vendor.get('manifest') or {}).get('citations', [])}
    extraction = vendor.get('extraction') or {}
    usage, invoice, overlay = package['usage'], package['invoice'], package['overlay']
    tier, remedy = manifest_citations.get(result.get('tier_citation')), next(
        (c for c in manifest_citations.values() if c.get('field') == 'remedy'), None)
    if tier is None or remedy is None:
        return None
    sha = vendor['manifest']['document']['sha256']
    line = fee_line(invoice, overlay)
    return {
        'vendor': vendor['manifest']['vendor'], 'period': usage['month'], 'kind': 'service_credit',
        'amount': result['amount'], 'currency': result['currency'], 'stage': 'ESTIMATED',
        'agreement': {'id': vendor['manifest']['agreement'], 'read_by': extraction.get('model'),
                      'read_method': extraction.get('method'), 'version': result.get('version'),
                      'clause': remedy['quote'],
                      'citation': 'Clauses %d and %d of %s (source sha256 %s)' % (tier['id'], remedy['id'], vendor['manifest']['agreement'], sha),
                      'citations': [{k: c[k] for k in ('id', 'field', 'quote', 'start', 'end')} for c in (tier, remedy)],
                      'source_sha256': sha},
        'inputs': [
            {'label': 'Covered service', 'value': overlay['product'] + ', ' + overlay['plan'] + ' plan'},
            {'label': 'Unavailable minutes', 'value': str(usage['unavailable_minutes'])},
            {'label': 'Availability', 'value': result['trace'][0].split('. ')[0]},
            {'label': 'Credit rate (tier ' + repr(tier['quote']) + ')', 'value': _percent(result['rate_units'])},
            {'label': 'Affected monthly fee', 'value': line['amount'] + ' ' + invoice['currency'] + ' (' + line['description'] + ')'},
            {'label': 'Request date used for the window check (nothing filed)', 'value': package['estimate']['as_of']},
            {'label': 'Request window closes (exclusive)', 'value': result.get('claim_cutoff_exclusive')},
        ],
        'invoice': {'id': invoice['id'], 'vendor': invoice['vendor'], 'total': invoice['total'], 'currency': invoice['currency'],
                    'issued_on': invoice['issued_on'], 'line': line['description']},
        'evaluation': {'outcome': result['outcome'], 'trace': list(result['trace']), 'rate_units': result['rate_units'],
                       'observation_digest': result['observation_digest'], 'issuance_status': result['issuance_status']},
        'route': ROUTE,
    }


def opportunities(path, p, *, governing_fees=(), trusted_now=None, templates=None):
    """Read-only: evaluate the authored month with the installed ACTIVE Corvid agreement. Never opens a case.

    `templates`, when the template builder is on, is a callable of the principal returning the SHADOW estimates of
    approved template reads (`uptime/template_agreements.py`), appended after Corvid's row."""
    return _corvid(path, p, governing_fees=governing_fees, trusted_now=trusted_now) + (list(templates(p)) if templates else [])


def _corvid(path, p, *, governing_fees=(), trusted_now=None):
    from .vendor_registry import evaluate_active, get_vendor
    try:
        vendor = get_vendor(path, p, VENDOR_ID, governing_fees=governing_fees, trusted_now=trusted_now)
    except KeyError:
        return []
    if not vendor or vendor.get('state') != 'ACTIVE' or not vendor.get('active_version'):
        return []
    package = load()
    result = evaluate_active(path, p, VENDOR_ID, facts(package), expected_version=vendor['active_version'])
    row = build(vendor, result, package)
    return [row] if row else []


def controls(overlay):
    """Authored engine controls for installation, on other months and fees than the opportunity."""
    base = dict(agreement=overlay['agreement'], account=overlay['account'], product=overlay['product'], plan=overlay['plan'],
                month='2026-04', monitor_source='simulated_vendor', monitor_ref='control-status', month_complete=True,
                exclusions_removed=True, monthly_fee_cents=10000, fee_line_ref=overlay['fee_line_ref'], fee_ref='control-invoice',
                received_at='2026-05-02T00:00:00Z')
    return [dict(name='Source control: ' + name, facts=dict(base, **change), expected=expected) for name, change, expected in (
        ('60 of 43,200 minutes unavailable; 5 percent of USD 100', dict(eligible_downtime_minutes=60), dict(outcome='ELIGIBLE', amount='5.00')),
        ('no unavailability earns no credit', dict(eligible_downtime_minutes=0), dict(outcome='INELIGIBLE')),
        ('a request at the exclusive 45-day cutoff is refused', dict(eligible_downtime_minutes=60, received_at='2026-06-15T00:00:00Z'),
         dict(outcome='INELIGIBLE')))]


def seed(post, catalog_action, scripted_literal_review):
    """Install the recorded claude-opus-5-5 reading through the ordinary vendor routes (scripted reviewer only)."""
    from unittest.mock import patch
    package = load()
    with patch.dict(os.environ, {'UPTIME_PUBLIC_EXTRACTIONS': str(FIXTURES / 'extractions'), 'UPTIME_MODEL_PROPOSITIONS': '1'}):
        base = '/api/vendors/' + VENDOR_ID
        state = post(base + '/candidates', dict(document=package['document'], overlay=package['overlay']))
        if state.get('extraction', {}).get('model') != 'claude-opus-5-5':
            raise ValueError('The recorded Corvid Ledger reading was not used.')
        if state.get('semantic_review_requirements'):
            state = post(base + '/semantic-bindings', dict(revision=state['revision'],
                         review=scripted_literal_review(state['semantic_review_requirements'])))
        state = post(base + '/tests', dict(revision=state['revision'], tests=controls(package['overlay'])))
        if any(not row['passed'] for row in state['checks']):
            raise ValueError('Authored Corvid Ledger source controls failed.')
        if state.get('interpretation_required'):
            state = catalog_action(post, base, state, 'interpret')
        return catalog_action(post, base, catalog_action(post, base, state, 'approve'), 'activate')
