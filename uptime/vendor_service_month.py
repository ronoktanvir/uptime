"""Attested aggregate service-month evidence and its explicit UTC and filing clocks."""
from datetime import UTC, datetime, timedelta
from calendar import monthrange
from decimal import Decimal, DecimalException, Inexact, localcontext
import re

from .contracts import Outcome, fingerprint
from .vendor_eval import rate_for, usd_estimate
from .vendor_terms import MAX_PERCENT

FIELDS = {'fixed_period','fixed_filing','aggregate_monitor','service_fee','record_integrity','denial_policy'}
PROMPT = """
For an agreement on an entire SERVICE/plan using vendor-reported monthly unavailable minutes, use
aggregate_monitor="authoritative_vendor_minutes" on the block establishing that measure. Do NOT invent
resource_intervals, per-incident symptoms or required provider causes for aggregated status records.
service_fee="paid_recurring_subscription" for the scoped paid recurring service fee or itemized invoice subscription line.
fixed_period={"start":"ISO UTC inclusive timestamp","end":"ISO UTC exclusive timestamp"} when the public text specifies the
two ends of one whole UTC calendar month. Emit this instead of duplicating inferred effective dates or a separate period.
fixed_filing={"at":"ISO UTC cutoff","endpoint":"inclusive" or "exclusive"} when the contract gives an exact receipt cutoff.
Use this instead of a separate rolling filing_days operator. If both relative days and an exact timestamp appear, preserve
the exact timestamp; deterministic validation checks their consistency against the fixed service period.
record_integrity=["source_identifier","recorded_timestamp","content_hash","missing_unknown","no_customer_telemetry", "filing_timestamp"]
for the requirements explicitly stated by this span. Different blocks may contribute.
remedy="noncash_service_credit" if a service credit is noncash but there is no explicit future invoice commitment.
denial_policy list of "accept_correct","cure_missing","escalate_unsupported","no_automatic_appeal", "synthetic_only" only
as supported by the clause; these are reviewed local simulated claim controls, never permission to transmit.
For a fixed month of N elapsed minutes, the explicit formula 100 * (N - unavailable minutes) / N is supported as
interval_measurement=["availability_ratio"]. A zero-credit equality or above-threshold sentence is boundary="strict_below".
Do not type authoritative account-scoped aggregate status records as resource_intervals. The explicit fixed period
and scope can coexist with vendor or agreement identity when a source block contains more than one effect.
"""


def utc(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:Z|\+00:00)', value):
        raise ValueError('A fixed source timestamp must explicitly identify UTC.')
    return datetime.fromisoformat(value)


def validate(manifest, key, value, quote):
    text = ' '.join(quote.casefold().split())
    if key == 'fixed_period':
        if not isinstance(value, dict) or set(value) != {'start','end'}:
            raise ValueError('Expected fixed service-month bounds.')
        start,end = utc(value['start']),utc(value['end'])
        if (value['start'].lower() not in text or value['end'].lower() not in text
                or not re.search('inclusive|including',text) or not re.search('exclusive|excluding',text)
                or start.day != 1 or start != start.replace(hour=0,minute=0,second=0)
                or end != start + timedelta(days=monthrange(start.year,start.month)[1])):
            raise ValueError('Fixed period is not one explicit complete UTC calendar month.')
    elif key == 'fixed_filing':
        if (not isinstance(value, dict) or set(value) != {'at','endpoint'} or value['endpoint'] not in ('inclusive','exclusive')
                or not re.search('claim|filing|filed|receive',text)):
            raise ValueError('Unsupported fixed filing clock.')
        utc(value['at'])
        if value['at'].lower() not in text or not re.search(
                r'no later than|inclusive|exactly.{0,40}permitted|\bby\b' if value['endpoint']=='inclusive' else r'\bbefore\b|exclusive', text):
            raise ValueError('Source does not establish the stated filing cutoff and comparator.')
        count = re.search(r'within (\d+) (?:calendar )?days? (?:after|following)', text)
        if count:
            manifest['fixed_filing_days'] = int(count[1])
    elif key == 'aggregate_monitor':
        if (value != 'authoritative_vendor_minutes' or not re.search(r'status|provider|vendor',text)
                or not re.search(r'unavailab.{0,20}minutes?|authoritative.{0,30}availability',text)):
            raise ValueError('Missing public vendor-status or unavailable-minute authority.')
    elif key == 'service_fee':
        if (value != 'paid_recurring_subscription' or 'paid' not in text
                or not re.search(r'recurring|subscription',text) or not re.search(r'fee|charge|invoice|line',text)):
            raise ValueError('Paid recurring service fee scope is unverified.')
    elif key in ('record_integrity','denial_policy'):
        patterns={'source_identifier':r'(?:source|record) identifiers?|source ids?|identif.{0,40}recording system', 'recorded_timestamp':r'recorded timestamp|timestamped',
                  'content_hash':r'content hash|sha.256', 'missing_unknown':r'unknown|unestablished|insufficient',
                  'no_customer_telemetry':r'customer telemetry (?:is |are )?not required',
                  'filing_timestamp':r'filing timestamp|timestamped claim|time of filing|(?:receipt|received|arrival) timestamp',
                  'accept_correct':r'(?:correct|valid).{0,140}(?:accept|upheld)', 'cure_missing':r'missing.{0,90}(?:supply|provide|supplement)|supporting records.{0,45}supplied|corrections? and supplements?',
                  'escalate_unsupported':r'escalat.{0,35}review|refer.{0,35}review','no_automatic_appeal':r'no.{0,60}automatic appeal|do not.{0,100}automatic appeal',
                  'synthetic_only':r'synthetic testing only|only synthetic'}
        permitted = ({'source_identifier','recorded_timestamp','content_hash','missing_unknown','no_customer_telemetry','filing_timestamp'}
                     if key == 'record_integrity' else {'accept_correct','cure_missing','escalate_unsupported','no_automatic_appeal','synthetic_only'})
        if not isinstance(value,list) or not value or any(not isinstance(v,str) or v not in permitted or not re.search(patterns[v],text) for v in value):
            raise ValueError('Ungrounded service evidence or denial obligation.')
        manifest[key] = sorted(set(manifest.get(key,[])) | set(value))
        return
    if key in manifest and manifest[key] != value:
        raise ValueError('Conflicting service month term.')
    manifest[key] = value


def _report(facts,key,overlay):
    from .vendor_resource_eval import Gap, instant, required_ref
    record = facts.get(key)
    if not isinstance(record,dict) or record.get('verified') is not True or record.get('complete') is not True:
        raise Gap('Complete verified record required: ' + key)
    scope = ('agreement','account','product','plan')
    if record.get('month') != facts['month'] or any(record.get(k) != overlay[k] for k in scope):
        raise Gap('Source record does not cover this account, service, plan and month.')
    required_ref(record.get('ref'))
    instant(record.get('recorded_at'))
    content = record.get('content')
    if not isinstance(content,dict) or record.get('content_sha256') != fingerprint(content):
        raise Gap('Record content does not match its source hash.')
    return content


def minute_microseconds(value):
    """Interpret a preserved JSON number/string as an exact bounded duration."""
    if type(value) not in (int, float, str):
        raise ValueError('Unavailable minutes must be a finite decimal quantity.')
    text = str(value)
    if len(text) > 64 or not re.fullmatch(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?', text):
        raise ValueError('Unavailable minutes must be a finite decimal quantity.')
    try:
        minutes = Decimal(text)
        if not minutes.is_finite() or not 0 <= minutes <= 44640:
            raise ValueError('Unavailable minutes must be within a calendar month.')
        # Decimal is only an input parser. Every comparison thereafter uses integer
        # microseconds, avoiding floating-point threshold drift and silent rounding.
        with localcontext() as context:
            context.prec = 80
            context.traps[Inexact] = True
            duration = minutes * 60_000_000
            if duration != duration.to_integral_value():
                raise ValueError('Unavailable minutes exceed the supported microsecond precision.')
    except DecimalException as exc:
        raise ValueError('Unavailable minutes exceed the supported exact duration range.') from exc
    return int(duration)


def evaluate(manifest, overlay, facts, tenant,*,bindings=None):
    from .vendor_resource_eval import Gap, instant, required_ref, source_labels, unresolved_semantics
    from .vendor_bindings import require_context, SemanticBindingRequired, literal
    if facts.get('tenant',tenant) != tenant:
        raise PermissionError('Tenant mismatch.')
    result={'amount':None,'currency':'USD','trace':[],'missing':[],'basis':fingerprint(overlay),'observation_digest':fingerprint(facts),
            'remedy':manifest['remedy'],'citations':[c['id'] for c in manifest['citations']],
            'issuance_status':'NOT_ESTABLISHED','filing_status':'UNDETERMINED'}
    try:
        bindings = require_context(manifest,overlay,tenant,bindings)
        scope=('account','product','plan','agreement','fee_line_ref')
        if set(facts)-set(scope)-{'tenant','month','service_monitor','service_invoice','filing_proof','received_at','resource_id'}:
            raise Gap('Unrecognized aggregate service observations.')
        if any(facts.get(k)!=overlay[k] for k in scope):
            raise Gap('Agreement, account, product, plan or fee scope mismatch.')
        start,end=utc(manifest['fixed_period']['start']),utc(manifest['fixed_period']['end'])
        if (facts.get('month') != start.strftime('%Y-%m') or start.date().isoformat()<overlay['effective_from']
                or (end.date()-timedelta(days=1)).isoformat()>overlay['effective_until']):
            return result|{'outcome':Outcome.UNSUPPORTED.value,'trace':['Service month outside the governing interval.']}
        monitor=_report(facts,'service_monitor',overlay)
        invoice=_report(facts,'service_invoice',overlay)
        minutes=(end-start)//timedelta(minutes=1)
        try:
            down = minute_microseconds(monitor.get('unavailable_minutes'))
        except ValueError as exc:
            raise Gap(str(exc)) from exc
        total = minutes * 60_000_000
        if monitor.get('source')!='simulated_vendor' or down > total:
            raise Gap('Verified scoped vendor status and bounded unavailable minutes required.')
        if invoice.get('paid') is not True or invoice.get('currency')!='USD' or not isinstance(invoice.get('lines'),list):
            raise Gap('Paid complete itemized USD subscription invoice required.')
        fees=[]; seen={}
        from .vendor_resource_eval import excluded_fee
        for line in invoice['lines']:
            if not isinstance(line,dict):
                raise Gap('Invalid itemized service-line evidence.')
            ref=required_ref(line.get('ref'))
            if ref in seen:
                if seen[ref]!=line:
                    raise Gap('Conflicting fee records under one source reference.')
                continue
            seen[ref]=line
            category=literal(required_ref(line.get('category')))
            if excluded_fee(manifest,category,bindings):
                continue
            if line.get('kind')!='recurring_subscription' or ref!=overlay['fee_line_ref']:
                raise Gap('Unclassified service charge or unmatched recurring fee.')
            cents=line.get('amount_cents')
            if type(cents) is not int or not 0<=cents<=10**15:
                raise Gap('Invalid paid recurring fee.')
            fees.append(cents)
        if len(fees)!=1:
            raise Gap('One unambiguous affected subscription fee line is required.')
        proof=facts.get('filing_proof')
        if (not isinstance(proof,dict) or proof.get('verified') is not True or proof.get('month')!=facts['month']
                or any(proof.get(k)!=overlay[k] for k in ('account','agreement','product','plan'))):
            raise Gap('Verified scoped timestamped claim receipt required.')
        required_ref(proof.get('ref'))
        fields = proof.get('fields', {})
        if not isinstance(fields, dict):
            raise Gap('Malformed claim contents.')
        supplied = {}
        for raw,value in fields.items():
            for key in bindings.resolve('request_fields',raw) if bindings else ():
                if key in supplied and supplied[key] != value:
                    raise Gap('Conflicting literal representations of one filing field.')
                supplied[key] = value
        if not all(isinstance(supplied.get(k), str) and supplied[k].strip()
                for k in manifest.get('request_fields', [])):
            raise Gap('Required claim contents are absent from the verified original filing.')
        received=instant(proof.get('received_at'))
        if 'received_at' in facts and received!=instant(facts['received_at']):
            raise Gap('Contradictory filing timestamp.')
        cutoff=utc(manifest['fixed_filing']['at'])
        inclusive=manifest['fixed_filing']['endpoint']=='inclusive'
        result.update(claim_cutoff=cutoff.isoformat(), cutoff_inclusive=inclusive, affected_fee_cents=fees[0],
                      downtime_microseconds=down,total_microseconds=total)
        if not end<=received<=cutoff or received==cutoff and not inclusive:
            return result|{'outcome':Outcome.INELIGIBLE.value,'filing_status':'OUTSIDE_WINDOW','trace':['Outside the fixed UTC filing window.']}
        rate,citation=rate_for(manifest,manifest['scope']['product'],manifest['scope']['plan'] or '*',total-down,total)
        amount=usd_estimate(fees[0],rate)
        if manifest.get('rounding')=='nearest_cent_half_up':
            cents=(2*fees[0]*rate+MAX_PERCENT)//(2*MAX_PERCENT);amount=f'{cents//100}.{cents%100:02d}'
        result.update(rate_units=rate,tier_citation=citation,filing_status='TIMELY',service_estimate=amount,
                      trace=[f'{total-down}/{total} microseconds available; {fees[0]} verified affected USD cents.'])
        if amount=='0.00':
            return result|{'outcome':Outcome.INELIGIBLE.value}
        return result|{'outcome':Outcome.ELIGIBLE.value,'amount':amount,'issuance_status':'NONCASH_SERVICE_CREDIT_UNCONFIRMED'}
    except Gap as exc:
        return result|{'outcome':Outcome.MISSING.value,'trace':[str(exc)],'missing':[str(exc)]}
    except SemanticBindingRequired as exc:
        return unresolved_semantics(manifest,overlay,facts,result,str(exc))
