"""Read-only adapter requirement card and generated review drafts.

This module reports what an installed, compiled adapter already establishes and
what a reviewer still has to supply. It never extracts, evaluates for authority,
approves, activates or dispatches anything, and it never reads overlays from an
HTTP body: callers pass the server's own artifact.

It is deliberately outside the reviewed-semantics file set in
``vendor_terms._PROFILE_FILES``. Installing it changes no evaluator revision, so
existing reviewed adapters (including recorded review history) keep their
current state. The flip side is that nothing here can be an approval gate, and
its statuses are derived from the manifest it is given rather than from claims
about compiler behavior. Each card names the evaluator revision it was read
against; this module's own logic is not part of that hash.

Generated drafts carry ``derived`` rather than ``expected``. The registry's
``IndependentTest`` schema forbids extra fields, so a draft cannot be posted
unchanged as the independent reviewer suite: a reviewer must re-author each
expectation from the cited clauses. Reuse of draft facts is reported, not blocked.
"""
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction

from .contracts import Outcome, fingerprint
from .vendor_terms import PERCENT_SCALE, semantics_revision

SCHEMA = 'adapter-requirements/1'
MONTHLY = 'monthly-availability/1'
RESOURCE = 'resource-month/1'
ELEMENTS = ('source_clauses', 'eligible_fee', 'evidence', 'exclusions', 'deadline', 'submission_channel')
# Status vocabulary. Only REVIEW_REQUIRED leaves an open requirement.
PRESENT, FAMILY_DEFINED, NONE_STATED, REVIEW_REQUIRED = 'PRESENT', 'FAMILY_DEFINED', 'NONE_STATED', 'REVIEW_REQUIRED'
# Placeholder affected fee for draft observations. Drafts are shadow material, never a customer amount.
DRAFT_FEE_CENTS = 100_000
_NONOPERATIVE = {'heading', 'table_header', 'table_separator', 'nonmaterial'}
# Every operative citation field and manifest key the monthly compilers currently emit.
# Anything else is reported for review instead of being assumed harmless.
_MONTHLY_FIELDS = {'vendor', 'agreement', 'effective', 'period', 'filing_days', 'remedy', 'tier', 'scope',
                   'credit_rule', 'credit_rounding'}
_MONTHLY_KEYS = _MONTHLY_FIELDS - {'tier'} | {'family', 'document', 'citations', 'tiers', 'interpretation'}

# Resource-month proposition keys that ground each element in a cited source block.
_RESOURCE_KEYS = {
    'source_clauses': ('vendor', 'effective', 'scope', 'period', 'fixed_period', 'tiers', 'remedy'),
    'eligible_fee': ('fee_basis', 'fee_exclusions', 'service_fee'),
    'evidence': ('evidence', 'symptoms', 'provider_causes', 'aggregate_monitor', 'record_integrity', 'telemetry'),
    'exclusions': ('exclusions', 'maintenance'),
    'deadline': ('filing', 'fixed_filing', 'cure_clock', 'supplement'),
    'submission_channel': ('submission_channel', 'request_fields'),
}


class _Unreadable(Exception):
    """Internal: an artifact this module cannot summarize. Never surfaces as a server error."""


def _element(name, status, citations=(), detail=None, requirement=None):
    return {'element': name, 'status': status, 'citations': sorted(set(citations)),
            'detail': detail or {}, 'requirement': requirement}


def _monthly_cites(manifest):
    cites = {}
    for clause in manifest.get('citations', []):
        if clause.get('field') not in _NONOPERATIVE:
            cites.setdefault(clause['field'], []).append(clause['id'])
    return cites


def _resource_cites(manifest, keys):
    return [clause['id'] for clause in manifest.get('citations', [])
            if any(key in (clause.get('propositions') or {}) for key in keys)]


def _missing(name, what):
    return _element(name, REVIEW_REQUIRED, requirement=f'No cited source clause establishes {what}. '
                    'Locate the governing clause or record that this adapter cannot support the agreement.')


def _monthly_card(manifest, overlay):
    cites = _monthly_cites(manifest)
    step = 'credit_rule' in manifest
    rule_fields = ('credit_rule', 'credit_rounding') if step else ('tier',)
    required = ('vendor', 'agreement', 'effective', 'period') + rule_fields
    absent = [field for field in required if not cites.get(field)]
    elements = [
        _missing('source_clauses', 'the ' + ', '.join(absent)) if absent else
        _element('source_clauses', PRESENT, [i for f in required for i in cites[f]],
                 {'fields': {f: cites[f] for f in required}}),
    ]
    if cites.get('remedy') and manifest.get('remedy'):
        detail = {'remedy': manifest['remedy'], 'fee_line_ref': overlay.get('fee_line_ref'),
                  'currency': overlay.get('currency')}
        if step:
            detail['governing_fee_context_required'] = True
        elements.append(_element('eligible_fee', PRESENT, cites['remedy'], detail))
    else:
        elements.append(_missing('eligible_fee', 'the affected-fee basis or remedy'))
    observation = ['scoped vendor measurement covering the complete UTC month',
                   'exclusion-adjusted eligible downtime minutes',
                   'trusted governing-fee context' if step else 'verified affected fee line amount for the same month',
                   'offset-aware filing receipt time']
    elements.append(_element('evidence', FAMILY_DEFINED, cites.get('period', []) + cites.get('remedy', []),
                             {'observation': observation, 'basis': 'Fixed by the supported monthly family evaluator; '
                              'the source cites the measurement period and fee basis these items prove.'}))
    uncategorized = sorted((set(cites) - _MONTHLY_FIELDS) | (set(manifest) - _MONTHLY_KEYS))
    if uncategorized:
        elements.append(_element('exclusions', REVIEW_REQUIRED, detail={'uncategorized': uncategorized},
                                 requirement='The adapter contains uncategorized content (' + ', '.join(uncategorized) +
                                 '). Confirm from the source that it states no exclusion or condition.'))
    else:
        elements.append(_element('exclusions', NONE_STATED, detail={
            'basis': 'Every cited clause in this adapter is a recognized vendor, date, period, tier, fee or filing '
                     'field; none states an exclusion. Observations must still attest exclusion-adjusted downtime.'}))
    if cites.get('filing_days') and type(manifest.get('filing_days')) is int:
        detail = {'filing_days': manifest['filing_days'], 'measured_from': 'end of the UTC calendar month'}
        override = overlay.get('override')
        if isinstance(override, dict):
            detail['private_override'] = {'filing_days': override.get('filing_days'), 'source_ref': override.get('source_ref'),
                                          'effective_from': override.get('effective_from'),
                                          'governs': 'months starting on or after effective_from; earlier months keep the source rule'}
        elements.append(_element('deadline', PRESENT, cites['filing_days'], detail))
    else:
        elements.append(_missing('deadline', 'the claim filing deadline'))
    elements.append(_element('submission_channel', NONE_STATED, detail={
        'basis': 'The monthly family records no claim submission channel or request fields. Claims are delivered '
                 'only through a separately configured and authorized channel (D08).'}))
    requirements = ['Author independent expectations, including at least one eligible case with an exact amount '
                    'and one refusal, from the cited clauses rather than from generated drafts.']
    if manifest.get('interpretation'):
        requirements.append('Accept or reject the model-proposed interpretation of each cited clause.')
    return elements, requirements


def _resource_card(manifest, overlay):
    elements = []
    for name, keys in _RESOURCE_KEYS.items():
        cited = _resource_cites(manifest, keys)
        present = {key: manifest[key] for key in keys if manifest.get(key) not in (None, [], {})}
        if present and cited:
            elements.append(_element(name, PRESENT, cited, present))
        elif name == 'evidence' and present and manifest.get('aggregate_monitor') and set(present) == {'evidence'}:
            # The fixed service-month profile supplies its default evidence set from the family.
            elements.append(_element(name, FAMILY_DEFINED, detail=present))
        elif present:
            elements.append(_element(name, REVIEW_REQUIRED, detail=present, requirement=(
                f'The adapter states {", ".join(sorted(present))} without a cited source block. '
                'Tie it to the governing source text or refuse the adapter.')))
        elif name == 'exclusions':
            elements.append(_element(name, NONE_STATED, detail={
                'basis': 'Every source block was accounted for and none states an exclusion.'}))
        elif name == 'submission_channel':
            # Informational: delivery uses a separately configured and authorized channel (D08); never sent from here.
            elements.append(_element(name, NONE_STATED, detail={
                'basis': 'No source block states a claim submission channel or required request fields.'}))
        else:
            elements.append(_missing(name, ' / '.join(keys)))
    requirements = ['Accept or reject the model-proposed interpretation of every cited block.',
                    'Author independent expectations from the cited blocks, including interval, fee-line and filing records.']
    if manifest.get('formula_grouping_review'):
        requirements.append('Choose the availability-formula grouping with a positive case that distinguishes both readings.')
    return elements, requirements


def _unsupported(family, requirement):
    return {'schema': SCHEMA, 'family': family, 'supported': False, 'no_open_requirements': False, 'elements': [],
            'review_requirements': [requirement]}


def requirement_card(manifest, overlay):
    """Five-element requirement card for one compiled artifact. Pure; never raises."""
    family = manifest.get('family') if isinstance(manifest, dict) else None
    try:
        if family == MONTHLY:
            elements, requirements = _monthly_card(manifest, overlay or {})
        elif family == RESOURCE:
            elements, requirements = _resource_card(manifest, overlay or {})
        else:
            return _unsupported(family, 'No supported evaluator family is established for this source; '
                                        'it cannot become an adapter without a reviewed family.')
        revision = semantics_revision(manifest)
    except (KeyError, TypeError, ValueError, AttributeError):
        return _unsupported(family, 'This installed artifact could not be summarized. Review its cited clauses directly.')
    missing = [e['requirement'] for e in elements if e['status'] == REVIEW_REQUIRED]
    return {'schema': SCHEMA, 'family': family, 'supported': True, 'no_open_requirements': not missing,
            'evaluator_semantics': revision, 'source_sha256': manifest.get('document', {}).get('sha256'),
            'elements': elements, 'review_requirements': missing + requirements}


def _governed_month(manifest, overlay):
    source_from, source_until = manifest['effective']
    first = max(date.fromisoformat(source_from), date.fromisoformat(overlay['effective_from']))
    last = date.fromisoformat(overlay['effective_until'])  # inclusive, as in the evaluator
    if source_until is not None:
        last = min(last, date.fromisoformat(source_until))
    year, month = first.year, first.month
    if first.day != 1:
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = date(year, month, monthrange(year, month)[1])
    return (date(year, month, 1), end) if end <= last else None, last


def _money(fee_cents, credit_units):
    """Exact USD text, preserving fractional cents as the monthly evaluator does (no settlement rounding)."""
    with localcontext() as context:
        context.prec = 60
        text = format(Decimal(fee_cents) * Decimal(credit_units) / Decimal(PERCENT_SCALE * 10_000), 'f')
    whole, _, fraction = text.partition('.')
    return f'{whole}.{fraction.rstrip("0").ljust(2, "0")}'


def _credit_at(tiers, minutes, down):
    """Most severe tier whose exclusive threshold the availability falls below; None when none applies."""
    available = Fraction(100 * (minutes - down), minutes)
    reached = [t for t in tiers if available < Fraction(t['below_units'], PERCENT_SCALE)]
    return max(reached, key=lambda t: t['credit_units']) if reached else None


def _utc(moment):
    return moment.isoformat().replace('+00:00', 'Z')


def scenario_drafts(manifest, overlay):
    """Generated shadow drafts for the monthly tiered family, with independently derived outcomes. Never raises."""
    try:
        return _drafts(manifest, overlay)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return _no_drafts('This installed artifact could not be turned into drafts.')


def _no_drafts(reason):
    return {'generated': False, 'reason': reason, 'scenarios': []}


def _drafts(manifest, overlay):
    if not isinstance(manifest, dict) or manifest.get('family') != MONTHLY:
        return _no_drafts('Drafts are generated only for monthly tiered availability adapters. Resource-month cases '
                          'need interval, fee-line and filing records whose identities come from the customer’s own evidence.')
    if 'credit_rule' in manifest:
        return _no_drafts('Completed-step credits need a trusted governing-fee context, so a draft cannot establish an amount.')
    tiers = [t for t in manifest['tiers'] if (t['product'], t['plan']) == (overlay['product'], overlay['plan'])]
    governed, governed_end = _governed_month(manifest, overlay)
    if not tiers:
        return _no_drafts('The overlay product and plan have no cited tier.')
    if governed is None:
        return _no_drafts('No complete calendar month lies inside both the source and overlay intervals.')
    from .vendor_terms import private_filing_days
    start, end = governed
    minutes = ((end - start).days + 1) * 1440
    month = start.strftime('%Y-%m')
    # The draft month's own filing window: a private amendment governs only from its stated month (F4).
    filing_days = private_filing_days(overlay, month, manifest['filing_days'])
    if type(filing_days) is not int:
        return _no_drafts('The filing window is not a whole number of days.')
    window_open = datetime(end.year, end.month, end.day, tzinfo=UTC) + timedelta(days=1)
    cutoff = window_open + timedelta(days=filing_days)
    cite = _monthly_cites(manifest)
    base = dict(agreement=overlay['agreement'], account=overlay['account'], product=overlay['product'],
                plan=overlay['plan'], month=month, monitor_source='simulated_vendor', monitor_ref='draft-monitor-' + month,
                month_complete=True, exclusions_removed=True, monthly_fee_cents=DRAFT_FEE_CENTS,
                fee_line_ref=overlay['fee_line_ref'], fee_ref='draft-fee-' + month, received_at=_utc(window_open))
    scenarios, seen = [], set()

    def add(name, facts, outcome, amount, derivation, citations):
        if name not in seen:
            seen.add(name)
            scenarios.append({'name': name, 'facts': facts, 'derived': {'outcome': outcome, 'amount': amount},
                              'placeholder_fee_cents': facts.get('monthly_fee_cents'),
                              'derivation': derivation, 'citations': sorted(set(citations))})

    positive = None
    for tier in sorted(tiers, key=lambda t: -t['below_units']):
        threshold = Fraction(tier['below_units'], PERCENT_SCALE)
        # Smallest whole-minute downtime whose availability falls strictly below the threshold.
        first_down = int(minutes * (1 - threshold / 100)) + 1
        if not 0 < first_down <= minutes:
            continue
        label = format(Decimal(tier['below_units']) / PERCENT_SCALE, 'f').rstrip('0').rstrip('.')
        for down, phrase in ((first_down, 'one minute past'), (first_down - 1, 'exactly at or above')):
            reached = _credit_at(tiers, minutes, down)
            outcome = Outcome.ELIGIBLE.value if reached else Outcome.INELIGIBLE.value
            amount = _money(DRAFT_FEE_CENTS, reached['credit_units']) if reached else None
            facts = base | {'eligible_downtime_minutes': down}
            add(f'Availability {phrase} the {label}% threshold ({down} of {minutes} minutes down)', facts, outcome, amount,
                f'{minutes - down}/{minutes} available in {month}; exclusive comparison against {label}%; '
                f'placeholder fee USD {DRAFT_FEE_CENTS // 100:,}.00.',
                [reached['citation']] if reached else cite.get('tier', []))
            if reached and positive is None:
                positive = (facts, amount, [reached['citation']])
    if positive is None:
        return _no_drafts('No whole-minute downtime reaches a cited credit tier in the governed month.')
    facts, amount, cited = positive
    deadline, missing = cite.get('filing_days', []), Outcome.MISSING.value
    for name, change in (('Public status page only', {'monitor_source': 'public_status'}),
                         ('Measurement month not complete', {'month_complete': False}),
                         ('Exclusions not yet removed from downtime', {'exclusions_removed': False}),
                         ('Different account', {'account': overlay['account'] + '-other'})):
        add(name, facts | change, missing, None, 'Required evidence or scope is not established.', cited)
    add('Affected fee unknown', {k: v for k, v in facts.items() if k != 'monthly_fee_cents'}, missing, None,
        'An unknown fee leaves the amount unknown.', cite.get('remedy', []))
    add('Received at the last timely second', facts | {'received_at': _utc(cutoff - timedelta(seconds=1))},
        Outcome.ELIGIBLE.value, amount, f'Filing window closes {filing_days} days after month end (exclusive).',
        cited + deadline)
    add('Received when the filing window closes', facts | {'received_at': _utc(cutoff)}, Outcome.INELIGIBLE.value, None,
        f'{filing_days}-day window has closed.', deadline)
    # Timezone: receipt offsets are converted to UTC before the exclusive comparison; a time without an offset is unknown.
    west, east = timezone(timedelta(hours=-7)), timezone(timedelta(hours=5, minutes=30))
    add('Last timely second stated in UTC-07:00', facts | {'received_at': (cutoff - timedelta(seconds=1)).astimezone(west).isoformat()},
        Outcome.ELIGIBLE.value, amount, 'The stated offset is converted to UTC before comparing with the window close.',
        cited + deadline)
    add('Window close stated in UTC+05:30', facts | {'received_at': cutoff.astimezone(east).isoformat()},
        Outcome.INELIGIBLE.value, None, 'The same instant as the window close, in another offset, is not timely.', deadline)
    add('Receipt time without a UTC offset', facts | {'received_at': _utc(cutoff - timedelta(days=1)).removesuffix('Z')},
        missing, None, 'A receipt time must state its offset.', deadline)
    # Private filing amendment (F4): its own window governs from its stated month onward.
    override = overlay.get('override')
    if isinstance(override, dict) and isinstance(override.get('effective_from'), str):
        amended = date.fromisoformat(override['effective_from'])
        amended_end = date(amended.year, amended.month, monthrange(amended.year, amended.month)[1])
        if start < amended and amended_end <= governed_end:
            amended_month, amended_minutes = amended.strftime('%Y-%m'), ((amended_end - amended).days + 1) * 1440
            top = max(tiers, key=lambda t: t['below_units'])
            down = int(amended_minutes * (1 - Fraction(top['below_units'], PERCENT_SCALE) / 100)) + 1
            reached = _credit_at(tiers, amended_minutes, down)
            days = private_filing_days(overlay, amended_month, manifest['filing_days'])
            close = datetime(amended_end.year, amended_end.month, amended_end.day, tzinfo=UTC) + timedelta(days=1 + days)
            if reached and 0 < down <= amended_minutes:
                monthly = base | {'month': amended_month, 'monitor_ref': 'draft-monitor-' + amended_month,
                                  'fee_ref': 'draft-fee-' + amended_month, 'eligible_downtime_minutes': down}
                late_amount = _money(DRAFT_FEE_CENTS, reached['credit_units'])
                add(f'Amendment month {amended_month}: last timely second of the private {days}-day window',
                    monthly | {'received_at': _utc(close - timedelta(seconds=1))}, Outcome.ELIGIBLE.value, late_amount,
                    f'The private amendment governs from {override["effective_from"]}; {days} days after month end.',
                    [reached['citation']] + deadline)
                add(f'Amendment month {amended_month}: private window closes',
                    monthly | {'received_at': _utc(close)}, Outcome.INELIGIBLE.value, None,
                    f'The private {days}-day window has closed.', deadline)
    # The month containing the first ungoverned day is never wholly governed.
    add('Month outside the governed interval', facts | {'month': (governed_end + timedelta(days=1)).strftime('%Y-%m')},
        Outcome.UNSUPPORTED.value, None, 'The complete month must be governed by both the source and the overlay.',
        cite.get('effective', []))
    return {'generated': True, 'reason': None, 'month': month, 'draft_fee_cents': DRAFT_FEE_CENTS,
            'notice': 'Generated from this adapter’s own reading of the source, with a placeholder fee. Use them to '
                      'inspect behavior; they are not independent expectations and cannot be submitted unchanged.',
            'scenarios': scenarios}


def draft_overlap(drafts, submitted_tests):
    """Names of submitted reviewer tests whose facts are identical to a generated draft's facts."""
    generated = {fingerprint(s['facts']) for s in drafts.get('scenarios', [])}
    return [t['name'] for t in submitted_tests or [] if isinstance(t, dict) and fingerprint(t.get('facts')) in generated]
