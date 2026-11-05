"""Restricted compiler and interpreter for the supported Atlassian Jira direct-purchase scope."""
import calendar
from datetime import UTC, date, datetime, timedelta
from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
import json
import re
from fractions import Fraction
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .contracts import Citation, EvaluationResult, Money, Outcome
from .onboarding_extract import FIXTURES, PDF, SLA, SUPPORT

SCHEMA = 'atlassian-utc-tiers/1'


def fixture(name):
    return json.loads((FIXTURES / (name + '.json')).read_text())


def fields(value, *names):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError('Unknown or missing declarative field')


def percent(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,3}(?:\.\d{1,6})?', value):
        raise ValueError('Invalid decimal percentage')
    number = Decimal(value)
    if number > 100:
        raise ValueError('Percentage outside 0 to 100')
    return number


def compile_template(record):
    """Consume only typed source facts. No callable, scripts, arbitrary URLs or private fields."""
    fields(record, 'recorded_at', 'sources', 'model', 'session', 'prompt_sha256', 'raw_result_sha256', 'rules')
    if record['model'] != 'claude-opus-5-5' or not isinstance(record['session'], str):
        raise ValueError('Extraction model or session unrecognized')
    UUID(record['session'])
    if not isinstance(record['recorded_at'], str) or datetime.fromisoformat(record['recorded_at']).tzinfo is None:
        raise ValueError('Timestamped extraction required')
    for key in ('prompt_sha256', 'raw_result_sha256'):
        if not isinstance(record[key], str) or not re.fullmatch(r'[a-f0-9]{64}', record[key]):
            raise ValueError('Invalid generation digest')
    fields(record['sources'], 'legal', 'support')
    anchors = {}
    for name, uri in [('legal', PDF), ('support', SUPPORT)]:
        source = record['sources'][name]
        fields(source, 'uri', 'bytes_sha256', 'text_sha256')
        if source['uri'] != uri or not all(isinstance(source[k], str) and re.fullmatch(r'[a-f0-9]{64}', source[k])
                                            for k in ('bytes_sha256', 'text_sha256')):
            raise ValueError('Unrecognized public source')
        anchors[name] = source['text_sha256']
    r = record['rules']
    fields(r, 'effective', 'product', 'surface', 'experiences', 'bands', 'zone', 'error_rate_gt',
           'monitor', 'claim', 'challenge', 'basis')
    if (r['product'], r['surface'], r['zone'], r['monitor'], r['basis']) != (
            'Jira', 'browser', 'UTC', 'vendor_logs', 'affected_product_monthly_fees'):
        raise ValueError('Unsupported operation or product scope')
    if not isinstance(r['effective'], str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', r['effective']):
        raise ValueError('Full ISO effective date required')
    date.fromisoformat(r['effective'])
    percent(r['error_rate_gt'])
    fields(r['claim'], 'origin', 'calendar_days')
    fields(r['challenge'], 'origin', 'business_days')
    for clause, origin, name in [('claim', 'utc_month_end', 'calendar_days'),
                                  ('challenge', 'amount_posted_to_ticket', 'business_days')]:
        n = r[clause][name]
        if r[clause]['origin'] != origin or type(n) is not int or not 1 <= n <= 31:
            raise ValueError('Unsupported clock')
    allowed_experiences = {'view issue', 'create issue', 'edit issue', 'view board'}
    ex = r['experiences']
    if not isinstance(ex, list) or not ex or any(not isinstance(v, str) or v not in allowed_experiences for v in ex) or len(set(ex)) != len(ex):
        raise ValueError('Unsupported experience')
    fields(r['bands'], 'Premium', 'Enterprise')
    for bands in r['bands'].values():
        if not isinstance(bands, list) or not 1 <= len(bands) <= 10:
            raise ValueError('Invalid band count')
        lower, last_credit = Decimal(0), Decimal(101)
        for band in bands:
            fields(band, 'below', 'credit')
            upper, credit = percent(band['below']), percent(band['credit'])
            if upper <= lower or credit >= last_credit or credit <= 0:
                raise ValueError('Overlapping or unordered bands')
            lower, last_credit = upper, credit
    # Copy to decouple the immutable candidate from later changes to the extraction object.
    return {'schema': SCHEMA, 'sources': anchors, 'rules': json.loads(json.dumps(r)),
            'capabilities': {'status_context': {'connector': 'jira-public-status',
                                                'uri': 'https://jira-software.status.atlassian.com/',
                                                'entitlement_evidence': False},
                             'claim_channel': {'connector': 'atlassian-support-manual',
                                               'uri': 'https://support.atlassian.com/contact',
                                               'external_submission': False},
                             'evidence': 'vendor-confirmed, exclusion-adjusted product-month downtime minutes'}}


def rate_for(template, plan, monthly_uptime):
    for band in template['rules']['bands'][plan]:
        if monthly_uptime < Decimal(band['below']):
            return Decimal(band['credit'])
    return Decimal(0)


def month_bounds(month):
    if not isinstance(month, str) or not re.fullmatch(r'\d{4}-\d{2}', month):
        raise ValueError('Expected UTC YYYY-MM')
    year, number = map(int, month.split('-'))
    start = datetime(year, number, 1, tzinfo=UTC)
    return start, start + timedelta(days=calendar.monthrange(year, number)[1])


def claim_cutoff(template, month):
    """Exclusive upper bound. Includes the entire 15th calendar day after month end."""
    return month_bounds(month)[1] + timedelta(days=template['rules']['claim']['calendar_days'])


def challenge_through(template, posted_at, zone, holidays):
    """Planning date only. Caller must supply confirmed holiday list and local business zone."""
    if not isinstance(posted_at, datetime) or not posted_at.tzinfo or not zone or holidays is None:
        return None
    if not isinstance(holidays, (set, frozenset)) or any(type(day) is not date for day in holidays):
        raise ValueError('Confirmed holiday dates required')
    try:
        day = posted_at.astimezone(ZoneInfo(zone)).date()
    except ZoneInfoNotFoundError:
        return None
    count = template['rules']['challenge']['business_days']
    while count:
        day += timedelta(days=1)
        if day.weekday() < 5 and day not in holidays:
            count -= 1
    return day


@dataclass(frozen=True)
class JiraEvaluation(EvaluationResult):
    filing_status: str = 'UNDETERMINED'
    issuance_status: str = 'NOT_ESTABLISHED'


def generated_cases(template):
    """Synthesize boundary tests on either side of every exclusive breakpoint."""
    rows = []
    for plan, bands in template['rules']['bands'].items():
        for index, band in enumerate(bands):
            threshold = Decimal(band['below'])
            next_credit = bands[index + 1]['credit'] if index + 1 < len(bands) else '0'
            with localcontext(Context(prec=40)):
                adjacent = threshold - Decimal('0.0000001')
            rows.append({'plan': plan, 'uptime': str(adjacent), 'rate': band['credit']})
            rows.append({'plan': plan, 'uptime': str(threshold), 'rate': next_credit})
    return rows


def evaluate(template, principal, overlay, facts):
    """Replay against a scoped synthetic month. Only authoritative, exclusion-adjusted minute totals count."""
    if overlay.get('tenant') != principal.tenant or facts.get('tenant') != principal.tenant:
        raise PermissionError('Tenant mismatch')
    r = template['rules']

    def result(outcome, clause, detail, missing=(), money=None, support=False, filing="UNDETERMINED", issuance="NOT_ESTABLISHED"):
        uri = SUPPORT if support else SLA
        citation = Citation('Atlassian support' if support else 'Atlassian SLA', r['effective'], clause, uri)
        return JiraEvaluation(outcome, (citation,), (detail,), tuple(missing), money, filing, issuance)

    def missing(clause, fact, support=False):
        return result(Outcome.MISSING, clause, 'Missing or unverified: ' + fact, [fact], support=support)

    if overlay.get('agreement') != 'public-direct' or overlay.get('currency') != 'USD':
        return result(Outcome.UNSUPPORTED, '§2.3 / Appendix B', 'Only direct USD purchases on unmodified public terms are supported.')
    if not overlay.get('product') or not overlay.get('plan') or not overlay.get('site'):
        return missing('Appendix A', 'tenant product, plan and site mapping')
    if overlay['product'] != r['product']:
        return result(Outcome.UNSUPPORTED, 'Appendix A', 'This adapter implements Jira only.')
    if overlay['plan'] not in ('Premium', 'Enterprise', 'Standard', 'Free'):
        return result(Outcome.UNSUPPORTED, '§1', 'Unknown plan or plan alias.')
    if overlay['plan'] not in r['bands']:
        return result(Outcome.INELIGIBLE, '§1', 'Plan has no public commitment in this SLA.')
    if not overlay.get('instance') or not overlay.get('surface') or not overlay.get('experience'):
        return missing('§3 / Appendix A', 'instance class, surface and covered experience')
    if overlay['instance'] not in ('production', 'sandbox', 'trial', 'beta'):
        return result(Outcome.UNSUPPORTED, '§3', 'Unrecognized instance classification.')
    if overlay['instance'] != 'production' or overlay['surface'] != r['surface'] or overlay['experience'] not in r['experiences']:
        return result(Outcome.INELIGIBLE, '§3 / Appendix A', 'Instance or experience is outside the public Jira commitment.')
    try:
        start, end = month_bounds(facts.get('month'))
        valid_from = date.fromisoformat(overlay['effective_from'])
        valid_until = date.fromisoformat(overlay['effective_until'])
    except (KeyError, TypeError, ValueError):
        return missing('§1 / Appendix B', 'measurement month and governing overlay dates')
    if start.date() < max(date.fromisoformat(r['effective']), valid_from) or (end - timedelta(days=1)).date() > valid_until:
        return result(Outcome.UNSUPPORTED, '§1 / Appendix B', 'Measurement month is outside the full effective interval.')
    if facts.get('site') != overlay['site'] or facts.get('product') != overlay['product']:
        return missing('§2.1 / Appendix A', 'matching tenant site and product evidence')
    for key, required, clause, support in (
        ('breach', False, '§3', False), ('provisioned', True, '§3', False),
        ('tech_ticket_during_incident', True, 'Process to get compensation', True),
        ('authorized_ticket_submitter', True, 'Request a compensation credit', True),
        ('compensation_ticket_complete', True, '§2.1', False), ('requested_documentation_complete', True, '§2.1', False)):
        if type(facts.get(key)) is not bool:
            return missing(clause, key, support)
        if facts[key] is not required:
            if key in ('compensation_ticket_complete', 'requested_documentation_complete'):
                return missing(clause, key, support)
            return result(Outcome.INELIGIBLE, clause, f'Condition for this as-filed credit failed: {key}.', support=support)
    try:
        receipt = datetime.fromisoformat(facts['received_at'])
        if receipt.tzinfo is None:
            raise ValueError('missing timezone')
    except (KeyError, TypeError, ValueError):
        return missing('§2.1', 'timestamped complete compensation ticket receipt')
    if not end <= receipt < claim_cutoff(template, facts['month']):
        return result(Outcome.INELIGIBLE, '§2.1', 'Compensation request receipt falls outside the calendar-day window.', filing='OUTSIDE_WINDOW')
    if (facts.get('monitor_source') != 'simulated_atlassian_logs' or facts.get('vendor_month') != facts['month']
            or facts.get('excluded_minutes_removed') is not True or facts.get('monitor_month_complete') is not True
            or facts.get('monitor_rate_operator') != 'strictly_greater'
            or facts.get('monitor_rate_threshold_percent') != r['error_rate_gt']):
        return missing('§2.1, §3 / Appendix B', 'Atlassian-confirmed, exclusion-adjusted product-month monitoring')
    total = int((end - start) / timedelta(minutes=1))
    down = facts.get('downtime_minutes')
    if type(down) is not int or not 0 <= down <= total:
        return missing('Appendix B', 'count of vendor-confirmed minutes exceeding the error threshold')
    ratio = Fraction(100 * (total - down), total)
    rate = rate_for(template, overlay['plan'], ratio)
    with localcontext(Context(prec=40)):
        uptime = Decimal(ratio.numerator) / ratio.denominator
    trace = f'{total} UTC minutes, {down} confirmed qualifying minutes; {uptime:.8f}% uptime gives a {rate}% rate.'
    if not rate:
        return result(Outcome.INELIGIBLE, 'Appendix B', trace)
    fee = facts.get('monthly_fee')
    if (facts.get('fee_basis') != r['basis'] or not overlay.get('fee_line_ref')
            or facts.get('fee_line_ref') != overlay['fee_line_ref'] or facts.get('fee_month') != facts['month']
            or not isinstance(fee, str) or not re.fullmatch(r'\d{1,12}(?:\.\d{1,2})?', fee)):
        return missing('Appendix B', 'verified affected product-month fee allocation')
    with localcontext(Context(prec=40)):
        amount = (Decimal(fee) * rate / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount == 0:
        return result(Outcome.INELIGIBLE, 'Appendix B / §2.2',
                      trace + f' The verified USD fee {fee} produces no positive credit at modeled cent precision.',
                      filing='TIMELY', issuance='NO_POSITIVE_CREDIT')
    standing = facts.get('good_standing')
    issuance = ('CONDITIONAL_ON_VENDOR_REVIEW' if standing is True else
                'BLOCKED_ACCOUNT_STANDING' if standing is False else 'ACCOUNT_STANDING_UNKNOWN')
    detail = f' USD {fee} × {rate}% = {amount} modeled filing amount. Issuance: {issuance}.'
    return result(Outcome.ELIGIBLE, 'Appendix B / §2.2', trace + detail, money=Money(amount),
                  filing='TIMELY', issuance=issuance)
