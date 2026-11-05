"""Scoped synthetic service observations. All interval math is exact UTC microseconds."""
from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
import re

from .contracts import Outcome, fingerprint
from .twilio import _merge, _subtract
from .vendor_eval import rate_for, usd_estimate
from .vendor_resource_terms import norm
from .vendor_terms import MAX_PERCENT

FACTS = {'tenant','agreement','account','product','plan','resource_id','month','received_at','monitor_source',
         'monitor_ref','month_complete','intervals','exclusions','fee_lines','fee_line_ref','itemized_complete',
         'billing_cycles','issuance','fee_ref','filing_proof','condition_evidence'}
SCOPED = {'agreement','account','product','plan','resource_id','fee_line_ref'}


class Gap(ValueError):
    pass


class Unsupported(ValueError):
    pass


def instant(value):
    if not isinstance(value,str) or not re.fullmatch(
            r'\d{4}-\d{2}-\d{2}[T ]\d\d:\d\d(?::\d\d(?:\.\d{1,6})?)?(?:Z|[+-]\d\d:\d\d)',value):
        raise Gap('Offset-aware evidence timestamp required.')
    try:
        return datetime.fromisoformat(value).astimezone(UTC)
    except (ValueError,OverflowError) as exc:
        raise Gap('Malformed evidence timestamp.') from exc


def required_ref(value):
    if not isinstance(value,str) or not value.strip() or len(value)>200:
        raise Gap('Missing or ambiguous source reference.')
    return value


def month_bounds(month):
    if not isinstance(month,str) or not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])',month):
        raise Gap('Expected UTC service month.')
    try:
        start=datetime.fromisoformat(month+'-01').replace(tzinfo=UTC)
        return start,start+timedelta(days=monthrange(start.year,start.month)[1])
    except (ValueError,OverflowError) as exc:
        raise Unsupported('Unsupported calendar interval.') from exc


def micros(delta):
    return (delta.days*86400+delta.seconds)*1000000+delta.microseconds


def relevant(record,overlay):
    for key in ('account','resource_id'):
        required_ref(record.get(key))
    return all(record[key]==overlay[key] for key in ('account','resource_id'))


def observation_rows(facts,key,overlay, *, optional=False):
    rows=facts.get(key,[] if optional else None)
    if not isinstance(rows,list) or len(rows)>1000:
        raise Gap('A complete list of '+key+' is required.')
    known={}
    for row in rows:
        if not isinstance(row,dict):
            raise Gap('Malformed source record.')
        if not relevant(row,overlay):
            continue
        ref=required_ref(row.get('ref'))
        digest=fingerprint(row)
        if ref in known:
            if known[ref]!=digest:
                raise Gap('Conflicting records for the same source reference.')
            continue
        known[ref]=digest
        yield row


def condition_evidence(facts,overlay,manifest):
    conditions=manifest.get('account_conditions',[])
    if not conditions:
        return set(),[]
    records=facts.get('condition_evidence')
    if not isinstance(records,list) or len(records)!=len(conditions):
        raise Gap('Local attestation required for every governing account/compliance condition.')
    excluded_refs=set()
    blocked=[]
    for condition in conditions:
        op=condition['op']
        matched=[r for r in records if isinstance(r,dict) and r.get('op')==op]
        if len(matched)!=1:
            raise Gap('Missing or ambiguous local account-condition evidence.')
        record=matched[0]
        if (record.get('verified') is not True or not relevant(record,overlay)
                or record.get('agreement')!=overlay['agreement'] or record.get('month')!=facts.get('month')):
            raise Gap('Account-condition attestation does not establish the governing account/resource/month.')
        required_ref(record.get('ref'))
        if op=='contract_noncompliance':
            terms_digest=record.get('terms_sha256')
            if record.get('terms_reviewed') is not True or not isinstance(terms_digest,str) or not re.fullmatch('[a-f0-9]{64}',terms_digest):
                raise Gap('Referenced compliance terms require a pinned, locally reviewed record.')
            required_ref(record.get('terms_ref'))
        finding=record.get('finding')
        refs=record.get('affected_refs',[])
        if (finding not in ('clear','applies') or not isinstance(refs,list)
                or not all(isinstance(ref,str) and ref.strip() for ref in refs)):
            raise Gap('Unresolved account or compliance finding.')
        if finding=='clear':
            if refs:
                raise Gap('Clear condition contradicts linked excluded intervals.')
            continue
        if condition['effect']=='causal_intervals':
            if not refs:
                raise Gap('An interval-specific exclusion requires linked scoped observations.')
            excluded_refs.update(refs)
        elif refs:
            raise Gap('Account filing precondition cannot be inferred from unrelated intervals.')
        else:
            blocked.append(op)
    return excluded_refs,blocked


def source_labels(manifest,key):
    return {norm(v) for v in manifest[key]} | {norm(v['phrase']) for v in manifest.get('label_bindings',{}).get(key,{}).values()}


def measured(facts,overlay,manifest,start,end,excluded_refs):
    if facts.get('monitor_source') not in ('simulated_vendor','synthetic_customer') or facts.get('month_complete') is not True:
        raise Gap('Complete account-specific resource evidence required; a public incident is context alone.')
    required_ref(facts.get('monitor_ref'))
    symptoms=source_labels(manifest,'symptoms')
    providers=source_labels(manifest,'provider_causes')
    exclusions=source_labels(manifest,'exclusions')
    s_alias=overlay.get('symptom_aliases',{})
    c_alias=overlay.get('cause_aliases',{})
    included,excluded=[],[]
    linked=set()
    for key in ('intervals','exclusions'):
        for row in observation_rows(facts,key,overlay,optional=key=='exclusions'):
            if set(row)-{'ref','account','resource_id','start','end','symptom','cause'}:
                raise Gap('Unexpected service interval fields.')
            left,right=instant(row.get('start')),instant(row.get('end'))
            if right<=left:
                raise Gap('Reversed or empty observation interval.')
            left,right=max(left,start),min(right,end)
            if left>=right:
                continue
            if row['ref'] in excluded_refs:
                linked.add(row['ref'])
                excluded.append((left,right))
                continue
            cause=required_ref(row.get('cause'))
            cause=norm(c_alias.get(cause,cause))
            if cause in exclusions:
                excluded.append((left,right))
                continue
            if key=='exclusions':
                raise Gap('Excluded interval lacks a source-defined excluded cause.')
            symptom=required_ref(row.get('symptom'))
            symptom=norm(s_alias.get(symptom,symptom))
            if symptom in {'unknown','unverified','unconfirmed'}:
                raise Gap('Unverified service symptom.')
            if symptom not in symptoms:
                continue
            if cause not in providers:
                raise Gap('Unconfirmed responsibility for qualifying service symptom.')
            included.append((left,right))
    if linked!=excluded_refs:
        raise Gap('Local exclusion references an unverified or out-of-scope interval.')
    return sum(micros(right-left) for left,right in _subtract(_merge(included),excluded))


def fees(facts,overlay,manifest):
    if facts.get('itemized_complete') is not True:
        raise Gap('An itemized complete affected-resource fee statement is required.')
    included=[]
    for row in observation_rows(facts,'fee_lines',overlay):
        if set(row)-{'ref','account','resource_id','month','kind','amount_cents','currency','fee_line_ref','category'}:
            raise Gap('Unrecognized fee-line fields.')
        if row.get('month')!=facts['month']:
            continue
        kind=row.get('kind')
        if kind not in ('resource_service','tax','support','one_time','other'):
            raise Gap('Unclassified affected-resource fee line.')
        if kind!='resource_service':
            # Non-service line categories are outside the positive affected-resource service fee basis.
            continue
        if row.get('fee_line_ref',row['ref'])!=overlay['fee_line_ref']:
            raise Gap('Resource service charge lacks the approved scope/fee reference.')
        cents=row.get('amount_cents')
        if row.get('currency')!='USD' or type(cents) is not int or not 0<=cents<=10**15:
            raise Gap('Invalid currency or amount on an affected service line.')
        if norm(row.get('category','')) in source_labels(manifest,'fee_exclusions'):
            continue
        included.append(cents)
    if not included:
        raise Gap('Missing itemized matched service charges for this resource and month.')
    return sum(included)


def deadline(facts,overlay,manifest,end):
    policy=manifest['filing']
    count=overlay.get('override',{}).get('filing_days',policy['count'])
    endpoint=policy['endpoint']
    if endpoint=='unclear':
        raise Unsupported('Contractual filing endpoint is unclear.')
    if policy['kind']=='calendar_days':
        if endpoint=='whole_day':
            return end+timedelta(days=count),False
        day=end.date()+timedelta(days=count-1)
        return datetime.combine(day,time.fromisoformat(policy['utc_time']),tzinfo=UTC),endpoint=='inclusive'
    if manifest.get('cycle_calendar_month') or overlay.get('billing_period',{}).get('kind')=='utc_calendar_month':
        year,month=divmod(end.year*12+end.month-1+count,12)
        return datetime(year,month+1,1,tzinfo=UTC),False
    cycles=facts.get('billing_cycles')
    if not isinstance(cycles,list) or len(cycles)!=count:
        raise Gap('Verified billing cycle boundaries are required to resolve the contractual filing deadline.')
    cursor=end
    for row in cycles:
        if not isinstance(row,dict) or set(row)-{'start','end','ref'} or instant(row.get('start'))!=cursor:
            raise Gap('Billing cycles must be contiguous and anchored to service month end.')
        required_ref(row.get('ref'))
        closing=instant(row.get('end'))
        if closing<=cursor:
            raise Gap('Invalid billing cycle interval.')
        cursor=closing
    return cursor,False


def check_submission(facts,overlay,manifest):
    items=manifest.get('request_fields',[])
    channel=manifest.get('submission_channel')
    if not items and not channel:
        return
    proof=facts.get('filing_proof')
    if not isinstance(proof,dict) or proof.get('verified') is not True or not relevant(proof,overlay):
        raise Gap('Verified scoped filing receipt and request contents required.')
    required_ref(proof.get('ref'))
    destination=proof.get('submitted_to')
    if channel and (not isinstance(destination,str) or destination.strip().casefold()!=channel.strip().casefold()):
        raise Gap('Contractual filing channel unverified.')
    values=proof.get('fields',{})
    if not isinstance(values,dict) or not all(isinstance(values.get(k),str) and values[k].strip() for k in items):
        raise Gap('Required source-defined claim fields missing from local receipt.')


def issuance(facts,overlay,amount):
    receipt=facts.get('issuance')
    if not isinstance(receipt,dict) or receipt.get('verified') is not True:
        return 'PENDING_VENDOR_VERIFICATION'
    try:
        required_ref(receipt.get('ref'))
    except Gap:
        return 'UNVERIFIED_ISSUANCE_REFERENCE'
    cents=receipt.get('amount_cents')
    if (receipt.get('account')!=overlay['account'] or receipt.get('resource_id')!=overlay['resource_id']
            or receipt.get('kind')!='future_invoice_credit' or receipt.get('currency')!='USD'
            or type(cents) is not int or cents<0 or f'{cents//100}.{cents%100:02d}'!=amount):
        return 'ISSUANCE_REQUIRES_REVIEW'
    return 'SIMULATED_FUTURE_CREDIT_VERIFIED'


def evaluate_resource(manifest,overlay,facts,tenant):
    if facts.get('tenant',tenant)!=tenant:
        raise PermissionError('Tenant mismatch.')
    base={'currency':'USD','amount':None,'trace':[],'missing':[],'filing_status':'UNDETERMINED',
          'issuance_status':'NOT_ESTABLISHED','basis':fingerprint(overlay),'observation_digest':fingerprint(facts),
          'remedy':manifest['remedy'],'citations':[c['id'] for c in manifest['citations']]}
    try:
        if set(facts)-FACTS:
            raise Gap('Unexpected or precomputed resource observation fields.')
        if not all(facts.get(key)==overlay[key] for key in SCOPED):
            raise Gap('Agreement/account/resource/product/plan/fee reference mismatch.')
        start,end=month_bounds(facts.get('month'))
        if (start.date().isoformat()<max(manifest['effective'][0],overlay['effective_from']) or
                (end.date()-timedelta(days=1)).isoformat()>min(overlay['effective_until'],manifest['effective'][1] or overlay['effective_until'])):
            raise Unsupported('Entire service month must fall within the source and tenant overlay.')
        excluded_refs,blocked=condition_evidence(facts,overlay,manifest)
        down=measured(facts,overlay,manifest,start,end,excluded_refs)
        total=micros(end-start)
        rate,citation=rate_for(manifest,manifest['scope']['product'],manifest['scope']['plan'] or '*',total-down,total)
        base.update(downtime_microseconds=down,total_microseconds=total,rate_units=rate,tier_citation=citation,
                    service_eligibility='QUALIFYING_DOWNTIME' if rate else 'NO_THRESHOLD_BREACH')
        base['trace'].append(f'{down}/{total} UTC microseconds of qualifying downtime after overlap union and exclusion subtraction.')
        if not rate:
            return base|{'outcome':Outcome.INELIGIBLE.value}
        if blocked:
            base['filing_status']='BLOCKED_ACCOUNT_CONDITION'
            base['trace'].append('Verified source-defined filing precondition failed: '+', '.join(blocked))
            return base|{'outcome':Outcome.INELIGIBLE.value}
        fee=fees(facts,overlay,manifest)
        amount=usd_estimate(fee,rate)
        if manifest.get('rounding')=='nearest_cent_half_up':
            cents=(2*fee*rate+MAX_PERCENT)//(2*MAX_PERCENT)
            amount=f'{cents//100}.{cents%100:02d}'
        base.update(affected_fee_cents=fee,service_estimate=amount)
        cutoff,inclusive=deadline(facts,overlay,manifest,end)
        base.update(claim_cutoff=cutoff.isoformat(),cutoff_inclusive=inclusive)
        if not inclusive:
            base['claim_cutoff_exclusive']=cutoff.isoformat()
        check_submission(facts,overlay,manifest)
        received=instant(facts.get('received_at'))
        if received<end or received>cutoff or received==cutoff and not inclusive:
            base.update(filing_status='OUTSIDE_WINDOW')
            base['trace'].append('Receipt outside the governing filing window.')
            return base|{'outcome':Outcome.INELIGIBLE.value}
        if amount=='0.00':
            base['trace'].append('The governing fee and credit precision produce no positive claimable amount.')
            return base|{'outcome':Outcome.INELIGIBLE.value,'filing_status':'TIMELY','issuance_status':'NO_POSITIVE_CREDIT'}
        base['trace'].append(f'{fee} eligible service cents, rate {rate}/1000000%, modeled USD {amount}.')
        return base|{'outcome':Outcome.ELIGIBLE.value,'amount':amount,'filing_status':'TIMELY','issuance_status':issuance(facts,overlay,amount)}
    except Gap as exc:
        return base|{'outcome':Outcome.MISSING.value,'trace':base['trace']+[str(exc)],'missing':[str(exc)]}
    except (Unsupported,OverflowError) as exc:
        return base|{'outcome':Outcome.UNSUPPORTED.value,'trace':base['trace']+[str(exc)]}
