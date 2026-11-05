"""Pure interpreter. Percentages and UTC-minute comparisons are exact integer ratios."""
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
import re

from .contracts import Outcome, fingerprint
from .vendor_terms import MAX_PERCENT, PERCENT_SCALE

FACT_FIELDS = {'agreement', 'account', 'product', 'plan', 'month', 'eligible_downtime_minutes',
               'monitor_source', 'monitor_ref', 'monitor_month', 'month_complete', 'exclusions_removed',
               'monthly_fee_cents', 'fee_line_ref', 'fee_month', 'fee_ref', 'received_at', 'tenant'}


def rate_for(manifest, product, plan, available, total):
    for tier in manifest['tiers']:
        if (tier['product'], tier['plan']) == (product, plan) and MAX_PERCENT * available < tier['below_units'] * total:
            return tier['credit_units'], tier['citation']
    return 0, None


def generated_checks(manifest):
    rows = []
    groups = {}
    for tier in manifest['tiers']:
        groups.setdefault((tier['product'], tier['plan']), []).append(tier)
    for (product, plan), tiers in groups.items():
        for i, tier in enumerate(tiers):
            threshold = tier['below_units']
            for units, expected in [(threshold - 1, tier['credit_units']),
                                    (threshold, tiers[i + 1]['credit_units'] if i + 1 < len(tiers) else 0)]:
                actual, _ = rate_for(manifest, product, plan, units, MAX_PERCENT)
                rows.append(dict(product=product, plan=plan, availability_units=units, expected=expected,
                                 actual=actual, passed=actual == expected))
    return rows


def usd_estimate(fee_cents, credit_units):
    # A percent has six fractional decimal places; keep sub-cent estimates exact.
    value = fee_cents * credit_units
    whole, fraction = divmod(value, MAX_PERCENT * 100)
    tail = f'{fraction:010d}'.rstrip('0').ljust(2, '0')
    return f'{whole}.{tail}'


def evaluate(manifest, overlay, facts, tenant):
    if manifest['family'] == 'resource-month/1':
        from .vendor_resource_eval import evaluate_resource
        return evaluate_resource(manifest,overlay,facts,tenant)
    if facts.get('tenant', tenant) != tenant:
        raise PermissionError('Tenant mismatch.')
    if set(facts) - FACT_FIELDS:
        raise ValueError('Unexpected observation fields.')
    base = {'outcome': None, 'amount': None, 'currency': 'USD', 'trace': [], 'missing': [],
            'filing_status': 'UNDETERMINED', 'issuance_status': 'NOT_ESTABLISHED', 'basis': fingerprint(overlay),
            'observation_digest': fingerprint(facts), 'remedy': manifest['remedy'],
            'citations': [c['id'] for c in manifest['citations'] if c['field'] != 'heading']}

    def stop(outcome, message, missing=()):
        return base | {'outcome': outcome.value, 'trace': [message], 'missing': list(missing)}

    for key in ('agreement', 'account', 'product', 'plan', 'fee_line_ref'):
        if facts.get(key) != overlay[key]:
            return stop(Outcome.MISSING, 'Observation requires matching agreement/account/product/plan/monthly fee scope.', [key])
    month = facts.get('month')
    if not isinstance(month, str) or not re.fullmatch(r'[0-9]{4}-(?:0[1-9]|1[0-2])', month):
        return stop(Outcome.MISSING, 'A full UTC measurement month is required.', ['month'])
    try:
        year, number = map(int, month.split('-'))
        total_days = monthrange(year, number)[1]
        start = date(year, number, 1)
        last = date(year, number, total_days)
        end = datetime(year, number, total_days, tzinfo=UTC) + timedelta(days=1)
        days = overlay.get('override', {}).get('filing_days', manifest['filing_days'])
        cutoff = end + timedelta(days=days)
    except (OverflowError, ValueError):
        return stop(Outcome.UNSUPPORTED, 'Calendar interval outside supported range.')
    base['claim_cutoff_exclusive'] = cutoff.isoformat()
    if (start.isoformat() < max(overlay['effective_from'], manifest['effective'][0])
            or last.isoformat() > min(overlay['effective_until'], manifest['effective'][1] or overlay['effective_until'])):
        return stop(Outcome.UNSUPPORTED, 'The complete month must be governed by both the contract and the account overlay.')
    if (facts.get('monitor_source') != 'simulated_vendor' or facts.get('month_complete') is not True
            or facts.get('exclusions_removed') is not True or facts.get('monitor_month', month) != month):
        return stop(Outcome.MISSING, 'Simulated scoped, exclusion-adjusted, full-month vendor measurement is required.', ['monitor'])
    minutes = total_days * 24 * 60
    down = facts.get('eligible_downtime_minutes')
    if type(down) is not int or not 0 <= down <= minutes:
        return stop(Outcome.MISSING, 'Confirmed downtime minutes are missing or out of range.', ['eligible_downtime_minutes'])
    fee = facts.get('monthly_fee_cents')
    if type(fee) is not int or not 0 <= fee <= 10**15 or facts.get('fee_month', month) != month:
        return stop(Outcome.MISSING, 'Verified affected fee line in cents for this month is required.', ['monthly_fee_cents'])
    for key in ('monitor_ref', 'fee_ref'):
        if key in facts and (not isinstance(facts[key], str) or not facts[key].strip() or len(facts[key]) > 160):
            return stop(Outcome.MISSING, 'Malformed observation source reference.', [key])
    # The observation digest itself is a local immutable reference if no external reference is supplied.
    base['monitor_ref'] = facts.get('monitor_ref', base['observation_digest'])
    base['fee_ref'] = facts.get('fee_ref', overlay['fee_line_ref'])
    try:
        received = datetime.fromisoformat(facts['received_at'])
        if received.tzinfo is None:
            raise ValueError
        received = received.astimezone(UTC)
    except (ValueError, TypeError, KeyError, OverflowError):
        return stop(Outcome.MISSING, 'An offset-aware as-filed receipt is required.', ['received_at'])
    if not end <= received < cutoff:
        base['filing_status'] = 'OUTSIDE_WINDOW'
        return stop(Outcome.INELIGIBLE, 'Simulated receipt is outside the contractual claim window.')
    base['filing_status'] = 'TIMELY'
    rate, citation = rate_for(manifest, overlay['product'], overlay['plan'], minutes - down, minutes)
    message = f'{minutes - down}/{minutes} UTC minutes available. Exact comparison gives {rate}/{PERCENT_SCALE}% credit.'
    if not rate:
        return stop(Outcome.INELIGIBLE, message)
    if fee == 0:
        base['issuance_status']='NO_POSITIVE_CREDIT'
        base['service_estimate']='0.00'
        return stop(Outcome.INELIGIBLE,'Verified zero affected fee produces no claimable service credit.')
    base['issuance_status'] = 'FUTURE_INVOICE_CREDIT_UNCONFIRMED'
    return base | {'outcome': Outcome.ELIGIBLE.value, 'amount': usd_estimate(fee, rate),
                   'tier_citation': citation, 'rate_units': rate,
                   'trace': [message, f'Affected fee {fee} USD cents; source-clause future invoice credit only.']}
