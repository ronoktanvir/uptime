"""Demo line (November 10, 2026): the money link between an approved template's read and the credit engine.

An ACCEPTED template read (`TemplateBuilds.approved_readings()`) gives nine typed terms. This module states those
terms in the clause grammar of the existing `monthly-availability/1` engine family, lets the engine's own compiler
(`vendor_terms.compile_terms`) and overlay binder (`bind_overlay`) validate them, and evaluates one authored service
month with the engine's own evaluator (`vendor_eval.evaluate`). No model is called and no credit arithmetic is done
here: the rate, the amount and the sentence are the engine's.

The result is an agreement in SHADOW: an estimate from authored usage, not a claim, not installed as an ACTIVE vendor
agreement, never posted, filed, applied or added to Northwind's figures.

Term mapping (the engine's tier family: "availability below X% earns a Y% credit", only the most severe applicable
tier, tiers never summed):
- availability_target_percent + tier_1_credit_percent -> tier "below the commitment: tier 1 credit";
- tier_2_threshold_percent + tier_2_credit_percent -> tier "below the second threshold: tier 2 credit";
- credit_cap_percent: the tier family has no cap operator. Because exactly one tier applies in a month, the capped
  credit for a tier is min(tier credit, cap); each tier's rate is stated that way. Tiers the cap makes equal are
  stated as one tier below the commitment (the same schedule). For an ACCEPTED read the cap never binds, because the
  read's plausibility guard refuses a cap below the highest credit;
- claim_window_days -> the engine's filing window in calendar days after the month;
- measurement_period must be `calendar_month` (stated to the engine as the UTC calendar month; the Halcyon form
  names no time zone, so that is an assumption shown in the inputs); other periods are refused;
- credit_application must be `next_invoice` (the engine's only remedy, a future-invoice credit on the affected
  monthly fee); a refund or account balance is refused;
- maintenance_notice_hours: governs which downtime is excluded; the engine takes exclusion-adjusted minutes, so it
  is shown as an input and the authored usage states its exclusions were removed.
"""
from decimal import ROUND_DOWN, Decimal, localcontext
import json
from pathlib import Path

from . import demo_opportunities as corvid

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'fixtures' / 'template_builder_demo' / 'evidence'
FIELDS = ('availability_target_percent', 'measurement_period', 'tier_1_credit_percent', 'tier_2_threshold_percent',
          'tier_2_credit_percent', 'credit_cap_percent', 'claim_window_days', 'maintenance_notice_hours',
          'credit_application')
LABELS = {
    'availability_target_percent': 'Availability commitment', 'measurement_period': 'Measurement period',
    'tier_1_credit_percent': 'Credit, first tier below the commitment', 'tier_2_threshold_percent': 'Second tier starts below',
    'tier_2_credit_percent': 'Credit, second tier', 'credit_cap_percent': 'Credit cap', 'claim_window_days': 'Claim window',
    'maintenance_notice_hours': 'Scheduled-maintenance notice', 'credit_application': 'How a credit is applied'}
NEEDS_EVIDENCE = 'Needs usage evidence'


class TermsRefused(ValueError):
    """Carries a plain sentence: why these terms cannot be stated to the engine."""


def _percent(value):
    return value + '%'


def _min_percent(a, b):
    # A comparison of two read terms, not credit arithmetic: the engine computes every amount.
    return a if Decimal(a) <= Decimal(b) else b


def _restatement(values, *, vendor, document):
    """The read terms in the engine's clause grammar, one clause per line, with each clause's term fields."""
    # The engine takes exclusion-adjusted minutes, so the maintenance-notice term is the one it can do without.
    missing = [f for f in FIELDS if f != 'maintenance_notice_hours' and values.get(f) in (None, '')]
    if missing:
        raise TermsRefused('Cannot estimate a credit: the read has no value for '
                           + ', '.join(LABELS[f] + ' (' + f + ')' for f in missing) + '.')
    if values['measurement_period'] != 'calendar_month':
        raise TermsRefused('Cannot estimate a credit: the engine evaluates calendar months, and this contract measures '
                           'availability by ' + values['measurement_period'].replace('_', ' ') + '.')
    if values['credit_application'] != 'next_invoice':
        raise TermsRefused('Cannot estimate a credit: the engine estimates a credit against a future invoice, and this '
                           'contract applies credits as ' + values['credit_application'].replace('_', ' ') + '.')
    for f in ('claim_window_days', 'maintenance_notice_hours'):
        if f == 'maintenance_notice_hours' and values.get(f) in (None, ''):
            continue
        if not str(values[f]).isdigit():
            raise TermsRefused('Cannot estimate a credit: ' + LABELS[f] + ' is not a whole number.')
    for f in ('availability_target_percent', 'tier_1_credit_percent', 'tier_2_threshold_percent',
              'tier_2_credit_percent', 'credit_cap_percent'):
        try:
            Decimal(values[f])
        except ArithmeticError:
            raise TermsRefused('Cannot estimate a credit: ' + LABELS[f] + ' is not a number.') from None
    cap = values['credit_cap_percent']
    first = _min_percent(values['tier_1_credit_percent'], cap)
    second = _min_percent(values['tier_2_credit_percent'], cap)
    scope = 'For %s on the %s plan, availability below ' % (document['product'], document['plan'])
    tiers = [(scope + _percent(values['availability_target_percent']) + ' earns a ' + _percent(first) + ' service credit.',
              ('availability_target_percent', 'tier_1_credit_percent', 'credit_cap_percent'))]
    if Decimal(first) != Decimal(second):
        tiers.append((scope + _percent(values['tier_2_threshold_percent']) + ' earns a ' + _percent(second)
                      + ' service credit.', ('tier_2_threshold_percent', 'tier_2_credit_percent', 'credit_cap_percent')))
    effective = 'Effective: ' + document['effective_from']
    return [('Vendor: ' + vendor, ()), ('Agreement: ' + document['agreement'], ()), (effective, ()),
            ('Availability is measured over each full UTC calendar month.', ('measurement_period',)),
            *tiers,
            ('Credit requests must be received within %s calendar days after the end of each calendar month.'
             % int(values['claim_window_days']), ('claim_window_days',)),
            ('Credits are calculated as a percentage of the affected monthly fees and are applied to a future invoice.',
             ('credit_application',))]


def overlay_from_values(values, *, vendor, document):
    """(manifest, overlay): the read terms as the engine's own compiled agreement, bound to an account.

    `document` carries the account binding the nine terms do not: agreement, account, product, plan, currency,
    effective_from, effective_until and fee_line_ref (the shape of Corvid's overlay.json), plus optional `name`/`uri`.
    Raises TermsRefused with a sentence when the terms cannot be stated or the engine refuses them.
    """
    from .vendor_terms import Document, Overlay, bind_overlay, compile_terms
    lines = _restatement(values, vendor=vendor, document=document)
    text = '\n'.join(line for line, _ in lines) + '\n'
    source = Document(name=(document.get('name') or 'Template reading of ' + document['agreement'])[:160],
                      uri=document.get('uri') or 'urn:uptime:template-reading:' + document['agreement'],
                      classification='synthetic_public', text=text)
    binding = {k: document[k] for k in ('agreement', 'account', 'product', 'plan', 'currency', 'effective_from',
                                        'effective_until', 'fee_line_ref')}
    try:
        manifest = compile_terms(source)
        overlay = bind_overlay(manifest, Overlay(**binding))
    except ValueError as error:
        raise TermsRefused('The engine refused these terms: ' + str(error)) from None
    for citation, (_, fields) in zip(manifest['citations'], lines, strict=True):
        citation['terms'] = list(fields)  # which read terms each restated clause carries
    return manifest, overlay


def load_evidence(document_id):
    """The authored month for one document, or None when nothing is on file (a pasted contract)."""
    if not isinstance(document_id, str) or not document_id or '/' in document_id or document_id.startswith('.'):
        return None
    folder = EVIDENCE / document_id
    if not (folder / 'usage.json').is_file():
        return None
    read = lambda name: json.loads((folder / name).read_text())
    return dict(overlay=read('overlay.json'), usage=read('usage.json'), invoice=read('invoice.json'),
                estimate=read('estimate.json'))


def _display_percent(units):
    from .vendor_terms import PERCENT_SCALE
    return format((Decimal(units) / PERCENT_SCALE).normalize(), 'f')


def _availability(available, total):
    # Display only, rounded down so a value below a threshold never displays at it. The engine compares exactly.
    with localcontext() as context:
        context.prec = 40
        return str((Decimal(available) * 100 / Decimal(total)).quantize(Decimal('0.001'), rounding=ROUND_DOWN))


def _term_inputs(values):
    rows = []
    for f in FIELDS:
        value = values.get(f)
        if value is not None and f.endswith('_percent'):
            value = _percent(value)
        elif value is not None and f in ('measurement_period', 'credit_application'):
            from .template_rules import TERM
            value = TERM[f].get('options', {}).get(value, value)
        elif value is not None and f == 'claim_window_days':
            value = value + ' days after the month'
        elif value is not None and f == 'maintenance_notice_hours':
            value = value + ' hours (governs excluded downtime; the authored usage is exclusion-adjusted)'
        if value is None and f == 'maintenance_notice_hours':
            value = 'Not stated in hours in this contract (the authored usage is exclusion-adjusted)'
        rows.append({'label': LABELS[f] + ' (read by the template)', 'value': value})
    return rows


def _shadow(entry, *, agreement_id, evaluation, inputs, month=None):
    return {'agreement_id': agreement_id, 'state': 'SHADOW', 'read_by': 'template:' + entry['template']['id'],
            'month': month, 'availability_percent': None, 'credit_percent': None, 'monthly_fee': None,
            'credit': None, 'inputs': inputs, 'evaluation': evaluation}


def _run(entry, evidence, tenant='template-reading'):
    """(agreement, engine result or None, evidence)."""
    from .vendor_eval import evaluate as engine
    values = entry.get('values') or {}
    document = entry.get('document') or {}
    inputs = _term_inputs(values)
    if evidence is None:
        return _shadow(entry, agreement_id=document.get('id'), evaluation=NEEDS_EVIDENCE, inputs=inputs), None, None
    overlay_doc, usage, invoice = evidence['overlay'], evidence['usage'], evidence['invoice']
    agreement_id = overlay_doc['agreement']
    if (usage.get('vendor') != entry.get('vendor') or invoice.get('vendor') != entry.get('vendor')
            or document.get('customer') is not None and usage.get('customer') != document.get('customer')):
        return _shadow(entry, agreement_id=agreement_id, inputs=inputs, evaluation=
                       'The usage evidence on file names a different vendor or customer than this read; nothing was estimated.'), None, None
    try:
        manifest, overlay = overlay_from_values(values, vendor=entry['vendor'], document=dict(
            overlay_doc, name='Template reading %s of %s' % (entry.get('reading_id'), document.get('id')),
            uri='urn:uptime:template-reading:%s:%s' % (entry.get('build_id'), entry.get('reading_id'))))
        facts = corvid.facts(evidence)
    except (TermsRefused, ValueError, KeyError) as error:
        return _shadow(entry, agreement_id=agreement_id, evaluation=str(error), inputs=inputs, month=usage.get('month')), None, None
    result = engine(manifest, overlay, facts, tenant)
    line = corvid.fee_line(invoice, overlay_doc)
    minutes = None
    if result.get('trace') and '/' in result['trace'][0]:
        available, _, rest = result['trace'][0].partition('/')
        total = rest.split(' ', 1)[0]
        if available.isdigit() and total.isdigit():
            minutes = (int(available), int(total))
    inputs = inputs + [
        {'label': 'Covered service', 'value': overlay_doc['product'] + ', ' + overlay_doc['plan']},
        {'label': 'Measured as', 'value': 'UTC calendar month (the contract names no time zone; assumed UTC)'},
        {'label': 'Service month (authored usage)', 'value': usage['month']},
        {'label': 'Unavailable minutes (authored, exclusion-adjusted)', 'value': str(usage['unavailable_minutes'])},
        {'label': 'Minutes available', 'value': '%d of %d' % minutes if minutes else None},
        {'label': 'Affected monthly fee', 'value': line['amount'] + ' ' + invoice['currency'] + ' (' + line['description'] + ')'},
        {'label': 'Claim date used for the window check (nothing filed)', 'value': evidence['estimate']['as_of']},
        {'label': 'Claim window closes (exclusive)', 'value': result.get('claim_cutoff_exclusive')},
    ]
    eligible = result['outcome'] == 'ELIGIBLE' and result.get('amount') is not None
    trace = result['trace'][0] if result.get('trace') else None
    availability = _availability(*minutes) if minutes else None
    percent = _display_percent(result['rate_units']) if 'rate_units' in result else None
    agreement = {
        'agreement_id': agreement_id, 'state': 'SHADOW', 'read_by': 'template:' + entry['template']['id'],
        'month': usage['month'], 'availability_percent': _availability(*minutes) if minutes else None,
        'credit_percent': _display_percent(result['rate_units']) if 'rate_units' in result else (
            '0' if result['outcome'] == 'INELIGIBLE' and minutes else None),
        'monthly_fee': line['amount'],
        'credit': {'amount': result['amount'], 'currency': result['currency'], 'stage': 'ESTIMATED'} if eligible else None,
        'inputs': inputs, 'evaluation': _sentence(minutes, availability, percent, line['amount'], result, trace)}
    return agreement, result, evidence


def _money(amount):
    return '{:,.2f}'.format(Decimal(amount))


def _sentence(minutes, availability, percent, fee, result, trace):
    """One sentence for a person. Every figure in it is the engine's result or an input; nothing is computed here."""
    if not minutes or availability is None:
        return trace
    head = '{:,} of {:,} UTC minutes were available ({}%)'.format(minutes[0], minutes[1], availability)
    if result['outcome'] == 'ELIGIBLE' and result.get('amount') is not None and percent is not None:
        currency = result['currency']
        return head + ', so the {p}% credit tier applies: {p}% of {c} {fee} is {c} {amount}.'.format(
            p=percent, c=currency, fee=_money(fee), amount=_money(result['amount']))
    return head + ', so no credit tier applies.'


def evaluate(entry, evidence):
    """The `agreement` object for one approved_readings() entry and its authored month (or None)."""
    return _run(entry, evidence)[0]


def opportunity(entry, evidence=None, tenant='template-reading'):
    """One portfolio row in Corvid's shape, with "source": "template"; None unless the engine estimated a credit."""
    agreement, result, evidence = _run(entry, evidence, tenant)
    if result is None or agreement['credit'] is None:
        return None
    invoice, overlay_doc = evidence['invoice'], evidence['overlay']
    line = corvid.fee_line(invoice, overlay_doc)
    template = entry['template']
    return {
        'vendor': entry['vendor'], 'period': agreement['month'], 'kind': 'service_credit',
        'amount': result['amount'], 'currency': result['currency'], 'stage': 'ESTIMATED',
        'agreement': {'id': agreement['agreement_id'], 'read_by': agreement['read_by'], 'read_method': 'approved_template_rules',
                      'version': template['sha256'], 'clause': None,
                      'citation': 'Terms read from %s by approved template %s (sha256 %s), reading %s'
                                  % (entry['document'].get('title') or entry['document'].get('id'), template['id'],
                                     template['sha256'], entry['reading_id']),
                      'citations': [], 'source_sha256': None, 'state': 'SHADOW', 'build_id': entry['build_id'],
                      'reading_id': entry['reading_id'], 'document_id': entry['document'].get('id')},
        'inputs': agreement['inputs'],
        'invoice': {'id': invoice['id'], 'vendor': invoice['vendor'], 'total': invoice['total'], 'currency': invoice['currency'],
                    'issued_on': invoice['issued_on'], 'line': line['description']},
        'evaluation': {'outcome': result['outcome'], 'trace': list(result['trace']), 'rate_units': result['rate_units'],
                       'observation_digest': result['observation_digest'], 'issuance_status': result['issuance_status']},
        'route': corvid.ROUTE, 'source': 'template',
    }


def on_reading(entry):
    """For TemplateBuilds.on_reading: never raises; a failure becomes a sentence on a SHADOW agreement."""
    try:
        return evaluate(entry, load_evidence((entry.get('document') or {}).get('id')))
    except Exception as error:  # noqa: BLE001 - the read itself must not fail because the estimate did
        return {'agreement_id': (entry.get('document') or {}).get('id'), 'state': 'SHADOW',
                'read_by': 'template:' + str((entry.get('template') or {}).get('id')), 'month': None,
                'availability_percent': None, 'credit_percent': None, 'monthly_fee': None, 'credit': None,
                'inputs': [], 'evaluation': 'No estimate: ' + type(error).__name__ + '.'}


def listed(service, tenant='template-reading'):
    """Opportunity rows for every approved reading with an estimated credit; the latest read per template and document."""
    if service is None or not hasattr(service, 'approved_readings'):
        return []
    latest = {}
    for entry in service.approved_readings():
        key = (entry['template']['id'], (entry.get('document') or {}).get('id'))
        if key not in latest or str(entry.get('read_at')) >= str(latest[key].get('read_at')):
            latest[key] = entry
    rows = []
    for entry in latest.values():
        try:
            row = opportunity(entry, load_evidence(entry['document'].get('id')), tenant)
        except Exception:  # noqa: BLE001 - one bad entry must not hide the portfolio; its reading shows the sentence
            row = None
        if row:
            rows.append(row)
    return rows


def for_app(app):
    """(on_reading, lister): assign the first to app.state.template_builds.on_reading; the workflow calls lister(p)."""
    def lister(p):
        return listed(getattr(app.state, 'template_builds', None), getattr(p, 'tenant', None) or 'template-reading')
    return on_reading, lister


def connect(app):
    """Wire a served app started with --template-builder: estimates on accepted reads, listed on the portfolio."""
    service = getattr(app.state, 'template_builds', None)
    if service is None:
        return None
    service.on_reading, lister = for_app(app)
    workflow = getattr(app.state, 'workflow', None)
    if workflow is not None:
        workflow.template_opportunities = lister
    return service
