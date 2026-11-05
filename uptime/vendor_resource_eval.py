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
         'billing_cycles','issuance','fee_ref','filing_proof','condition_evidence','maintenance_evidence','prior_credit_evidence','region','customer_telemetry','provider_telemetry'}
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


def source_labels(manifest,key,bindings):
    if not manifest.get(key):
        return set()
    from .vendor_bindings import BindingContext, SemanticBindingRequired
    if not isinstance(bindings,BindingContext):
        raise SemanticBindingRequired('Reviewed literal meaning is required.')
    return {value for label in manifest.get(key,[]) for value in bindings.representations(key,label)}


def scoped_records(facts, overlay, key):
    receipt = facts.get(key)
    if (not isinstance(receipt, dict) or receipt.get('verified') is not True or receipt.get('complete') is not True
            or not relevant(receipt, overlay) or receipt.get('agreement') != overlay['agreement']
            or receipt.get('month') != facts['month']):
        raise Gap('Verified complete scoped statement required: ' + key)
    required_ref(receipt.get('ref'))
    return observation_rows(receipt, 'records', overlay)


def announced_windows(facts, overlay, manifest):
    rule = manifest.get('maintenance')
    if not rule:
        return []
    windows = []
    notice = rule['notice']
    lead = timedelta(**{notice['unit']: notice['count']}) if notice else timedelta()
    for row in scoped_records(facts, overlay, 'maintenance_evidence'):
        left, right = instant(row.get('start')), instant(row.get('end'))
        if right <= left:
            raise Gap('Empty or reversed announced maintenance window.')
        if row.get('state') == 'confirmed_unannounced' and row.get('announced_at') is None:
            continue
        announced = instant(row.get('announced_at'))
        if rule.get('customer_delivery'):
            required_ref(row.get('notice_ref'))
            if row.get('recipient_account') != overlay['account'] or row.get('delivered_verified') is not True:
                raise Gap('Account-specific proof of maintenance notice delivery required.')
            delivered=instant(row.get('delivered_at'))
            if delivered<announced:
                raise Gap('Notice delivery predates its announcement.')
            for key in rule.get('scope',[]):
                if row.get(key) != (overlay['product'] if key=='product' else facts.get('region')):
                    raise Gap('Delivered maintenance notice has a different service scope.')
            announced=delivered
        if row.get('state', 'announced') != 'announced':
            raise Gap('Contradictory maintenance announcement record.')
        if announced < left and left - announced >= lead:
            windows.append((left, right))
    return _merge(windows)


def prior_credit_cents(facts, overlay, manifest):
    if not manifest.get('prior_credit'):
        return 0
    credits = {}
    for row in scoped_records(facts, overlay, 'prior_credit_evidence'):
        for key in ('month', 'agreement'):
            required_ref(row.get(key))
        if row['month'] != facts['month'] or row['agreement'] != overlay['agreement']:
            continue
        credit_id = required_ref(row.get('credit_id'))
        amount = row.get('amount_cents')
        if (row.get('state') != 'issued' or row.get('currency') != 'USD' or type(amount) is not int
                or not 0 <= amount <= 10**15 or credits.get(credit_id, amount) != amount):
            raise Gap('Issued credit is unverified or conflicts with its scoped prior record.')
        credits[credit_id] = amount
    return sum(credits.values())


def measured(facts,overlay,manifest,start,end,excluded_refs,bindings):
    if facts.get('monitor_source') not in ('simulated_vendor','synthetic_customer') or facts.get('month_complete') is not True:
        raise Gap('Complete account-specific resource evidence required; a public incident is context alone.')
    required_ref(facts.get('monitor_ref'))
    from .vendor_bindings import literal
    symptoms=source_labels(manifest,'symptoms',bindings)
    providers=source_labels(manifest,'provider_causes',bindings)
    exclusions=source_labels(manifest,'exclusions',bindings)
    included,excluded=[],[]
    windows = announced_windows(facts, overlay, manifest)
    maintenance = manifest.get('maintenance', {})
    cause_specific = maintenance.get('basis') == 'caused_within_announced_window'
    if not cause_specific:
        excluded.extend(windows)
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
            cause=literal(cause)
            if cause in exclusions:
                excluded.append((left,right))
                continue
            if key=='exclusions':
                raise Gap('Excluded interval lacks a source-defined excluded cause.')
            symptom=required_ref(row.get('symptom'))
            symptom=literal(symptom)
            if symptom in {'unknown','unverified','unconfirmed'}:
                raise Gap('Unverified service symptom.')
            if symptom not in symptoms:
                raise Gap('Observed service symptom has no reviewed literal meaning.')
            if cause_specific and bindings.targets('maintenance_cause',cause):
                included.extend(_subtract([(left, right)], windows))
            elif cause in providers:
                included.append((left, right))
            else:
                raise Gap('Unconfirmed responsibility for qualifying service symptom.')
    if linked!=excluded_refs:
        raise Gap('Local exclusion references an unverified or out-of-scope interval.')
    return sum(micros(right-left) for left,right in _subtract(_merge(included),excluded))


def fees(facts,overlay,manifest,bindings):
    if facts.get('itemized_complete') is not True:
        raise Gap('An itemized complete affected-resource fee statement is required.')
    included=[]
    for row in observation_rows(facts,'fee_lines',overlay):
        fields = {'ref','account','resource_id','month','kind','amount_cents','currency','fee_line_ref','category'}
        if manifest.get('fee_settlement'):
            fields.update({'payment_state','refund_ref','refund_cents','region','product','recurring'})
        if manifest.get('fee_adjustment') or 'subtract_fee_refunds' in manifest.get('fee_settlement', []):
            fields.update({'discount_ref','gross_cents','discount_cents','amount_basis'})
        if set(row) - fields:
            raise Gap('Unrecognized fee-line fields.')
        if row.get('month')!=facts['month']:
            continue
        kind=row.get('kind')
        if kind not in ('resource_service','tax','support','one_time','other'):
            raise Gap('Unclassified affected-resource fee line.')
        if kind!='resource_service':
            # Non-service line categories are outside the positive affected-resource service fee basis.
            continue
        settlements = manifest.get('fee_settlement', [])
        if 'paid_recurring_only' in settlements:
            if row.get('product') != overlay['product'] or row.get('region') != facts.get('region', overlay['resource_id']):
                raise Gap('Paid fee line lacks the signed product and region.')
            if row.get('payment_state') in ('voided','unpaid') or row.get('recurring') is False:
                continue
            if row.get('payment_state') != 'paid' or row.get('recurring') is not True:
                raise Gap('Verified paid recurring charge status is required.')
        if row.get('fee_line_ref',row['ref'])!=overlay['fee_line_ref']:
            raise Gap('Resource service charge lacks the approved scope/fee reference.')
        cents=row.get('amount_cents')
        if row.get('currency')!='USD' or type(cents) is not int or not 0<=cents<=10**15:
            raise Gap('Invalid currency or amount on an affected service line.')
        from .vendor_bindings import literal
        if row.get('category') and literal(row['category']) in source_labels(manifest,'fee_exclusions',bindings):
            continue
        refund = 0
        if 'subtract_fee_refunds' in settlements:
            required_ref(row.get('refund_ref'))
            refund = row.get('refund_cents')
            if type(refund) is not int or not 0 <= refund <= 10**15:
                raise Gap('Complete amount of fee refunds is unverified.')
        if manifest.get('fee_adjustment') or 'subtract_fee_refunds' in settlements:
            if manifest.get('fee_adjustment'):
                required_ref(row.get('discount_ref'))
            basis = row.get('amount_basis')
            allowed_basis = 'net_after_discounts_and_refunds' if 'subtract_fee_refunds' in settlements else 'net_after_discounts'
            if basis not in (None, allowed_basis):
                raise Gap('Unverified net affected-resource charge.')
            if 'gross_cents' in row or 'discount_cents' in row:
                gross, discount = row.get('gross_cents'), row.get('discount_cents')
                if (type(gross) is not int or type(discount) is not int or not 0 <= discount <= gross <= 10**15
                        or gross - discount - refund != cents):
                    raise Gap('Discount and gross amounts do not reconcile to the cited net charge.')
            elif basis != allowed_basis:
                raise Gap('A referenced post-discount fee or reconciled discount breakdown is required.')
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


def check_submission(facts, overlay, manifest, received, cutoff, inclusive,bindings):
    items = manifest.get('request_fields', [])
    channel = manifest.get('submission_channel')
    if not items and not channel and not manifest.get('supplement') and not manifest.get('cure_clock') and not manifest.get('original_receipt'):
        return True
    proof = facts.get('filing_proof')
    if not isinstance(proof, dict) or proof.get('verified') is not True or not relevant(proof, overlay):
        raise Gap('Verified scoped filing receipt and request contents required.')
    from .vendor_resource_scopes import portal_clock, supplement_clock
    portal_clock(facts, overlay, manifest, proof, received)
    receipt = required_ref(proof.get('ref'))
    destination = proof.get('submitted_to')
    if channel and (not isinstance(destination,str) or destination.strip().casefold() != channel.strip().casefold()):
        raise Gap('Contractual filing channel unverified.')
    values = proof.get('fields', {})
    if not isinstance(values, dict):
        raise Gap('Malformed request fields.')
    def bound_fields(raw):
        if bindings is None:
            return {}
        result = {}
        for key,value in raw.items():
            for target in bindings.targets('request_fields',key):
                if target in result and result[target] != value:
                    raise Gap('Conflicting literal representations of one filing field.')
                result[target] = value
        return result
    values = bound_fields(values)
    if manifest.get('cure_clock') and not all(isinstance(values.get(k), str) and values[k].strip()
            for k in manifest['cure_clock']['initial_fields']):
        raise Gap('Required identity fields must appear on the timely original portal filing.')
    supplied = dict(values)
    observations = dict(values)
    late = set()
    supplements = proof.get('supplements', [])
    if not isinstance(supplements, list) or len(supplements) > 100 or supplements and not (manifest.get('supplement') or manifest.get('cure_clock')):
        raise Gap('Unsupported supplemental filing evidence.')
    known = {}
    for row in supplements:
        if (not isinstance(row, dict) or row.get('verified') is not True or not relevant(row, overlay)
                or row.get('agreement') != overlay['agreement'] or row.get('month') != facts['month']
                or row.get('original_ref') != receipt or row.get('submitted_to') != destination):
            raise Gap('Supplement lacks original receipt, destination or verified monthly scope.')
        reference = required_ref(row.get('ref'))
        if reference == receipt or known.get(reference, row) != row:
            raise Gap('Conflicting supplemental filing reference.')
        known[reference] = row
        delivered = instant(row.get('received_at'))
        if delivered < received:
            raise Gap('Supplement predates its initial filing.')
        additions = row.get('fields')
        if not isinstance(additions, dict) or not additions:
            raise Gap('Supplement contains no verified request items.')
        additions = bound_fields(additions)
        item_cutoff, item_inclusive = (supplement_clock(facts, overlay, manifest, proof, row, received)
                                       if manifest.get('cure_clock') else (cutoff, inclusive))
        for key, value in additions.items():
            if not isinstance(value, str) or not value.strip() or key not in items:
                raise Gap('Supplement contains an unsupported or empty filing item.')
            if observations.get(key) not in (None, '', value):
                raise Gap('Supplement contradicts an earlier filing item.')
            observations[key] = value
            if delivered < item_cutoff or delivered == item_cutoff and item_inclusive:
                supplied[key] = value
            else:
                late.add(key)
    missing = {key for key in items if not isinstance(supplied.get(key), str) or not supplied[key].strip()}
    if missing - late:
        raise Gap('Required source-defined claim fields missing from local receipt.')
    return not missing


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


def evaluate_resource(manifest,overlay,facts,tenant,*,bindings=None):
    if facts.get('tenant',tenant)!=tenant:
        raise PermissionError('Tenant mismatch.')
    base={'currency':'USD','amount':None,'trace':[],'missing':[],'filing_status':'UNDETERMINED',
          'issuance_status':'NOT_ESTABLISHED','basis':fingerprint(overlay),'observation_digest':fingerprint(facts),
          'remedy':manifest['remedy'],'citations':[c['id'] for c in manifest['citations']]}
    from .vendor_bindings import require_context, SemanticBindingRequired
    try:
        bindings = require_context(manifest,overlay,tenant,bindings)
    except SemanticBindingRequired as exc:
        return unresolved_semantics(manifest,overlay,facts,base,str(exc))
    if manifest.get('aggregate_monitor'):
        from .vendor_service_month import evaluate
        return evaluate(manifest, overlay, facts, tenant,bindings=bindings)
    try:
        if set(facts)-FACTS:
            raise Gap('Unexpected or precomputed resource observation fields.')
        if not all(facts.get(key)==overlay[key] for key in SCOPED):
            raise Gap('Agreement/account/resource/product/plan/fee reference mismatch.')
        start,end=month_bounds(facts.get('month'))
        if (start.date().isoformat()<max(manifest['effective'][0],overlay['effective_from']) or
                (end.date()-timedelta(days=1)).isoformat()>min(overlay['effective_until'],manifest['effective'][1] or overlay['effective_until'])):
            raise Unsupported('Entire service month must fall within the source and tenant overlay.')
        from .vendor_resource_scopes import subscription, dual_downtime
        region = subscription(facts, overlay, manifest, start, end)
        excluded_refs,blocked=condition_evidence(facts,overlay,manifest)
        if manifest.get('telemetry'):
            if excluded_refs or manifest.get('maintenance', {}).get('basis') == 'caused_within_announced_window':
                raise Unsupported('Additional cause-specific conditions require independent incident attribution.')
            down = dual_downtime(facts, overlay, manifest, start, end, region, announced_windows(facts, overlay, manifest),bindings)
        else:
            down=measured(facts,overlay,manifest,start,end,excluded_refs,bindings)
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
        fee=fees(facts,overlay,manifest,bindings)
        amount=usd_estimate(fee,rate)
        if manifest.get('rounding')=='nearest_cent_half_up':
            cents=(2*fee*rate+MAX_PERCENT)//(2*MAX_PERCENT)
            amount=f'{cents//100}.{cents%100:02d}'
        base.update(affected_fee_cents=fee,service_estimate=amount)
        if manifest.get('prior_credit'):
            prior = prior_credit_cents(facts, overlay, manifest)
            remaining_scaled_cents = max(0, fee * rate - prior * MAX_PERCENT)
            if manifest.get('rounding') == 'nearest_cent_half_up':
                cents = (2 * remaining_scaled_cents + MAX_PERCENT) // (2 * MAX_PERCENT)
                amount = f'{cents//100}.{cents%100:02d}'
            else:
                amount = usd_estimate(1, remaining_scaled_cents)
            base.update(prior_issued_cents=prior, remaining_estimate=amount)
            base['trace'].append(f'Prior verified credits for this resource and month: {prior} USD cents.')
        cutoff,inclusive=deadline(facts,overlay,manifest,end)
        base.update(claim_cutoff=cutoff.isoformat(),cutoff_inclusive=inclusive)
        if not inclusive:
            base['claim_cutoff_exclusive']=cutoff.isoformat()
        received=instant(facts.get('received_at'))
        if received<end or received>cutoff or received==cutoff and not inclusive:
            base.update(filing_status='OUTSIDE_WINDOW')
            base['trace'].append('Receipt outside the governing filing window.')
            return base|{'outcome':Outcome.INELIGIBLE.value}
        if not check_submission(facts, overlay, manifest, received, cutoff, inclusive,bindings):
            base['trace'].append('The required supplement arrived after the original filing deadline.')
            return base | {'outcome': Outcome.INELIGIBLE.value, 'filing_status': 'LATE_SUPPLEMENT'}
        if amount=='0.00':
            base['trace'].append('The governing fee and credit precision produce no positive claimable amount.')
            return base|{'outcome':Outcome.INELIGIBLE.value,'filing_status':'TIMELY','issuance_status':'NO_POSITIVE_CREDIT'}
        base['trace'].append(f'{fee} eligible service cents, rate {rate}/1000000%, modeled USD {amount}.')
        return base|{'outcome':Outcome.ELIGIBLE.value,'amount':amount,'filing_status':'TIMELY','issuance_status':issuance(facts,overlay,amount)}
    except Gap as exc:
        return base|{'outcome':Outcome.MISSING.value,'trace':base['trace']+[str(exc)],'missing':[str(exc)]}
    except (Unsupported,OverflowError) as exc:
        return base|{'outcome':Outcome.UNSUPPORTED.value,'trace':base['trace']+[str(exc)]}
    except SemanticBindingRequired as exc:
        return unresolved_semantics(manifest,overlay,facts,base,str(exc))


def unresolved_semantics(manifest,overlay,facts,base,reason):
    """No monetary intermediate escapes an absent, stale or revoked binding."""
    result = {key:value for key,value in base.items() if key not in
              {'amount','service_estimate','remaining_estimate','affected_fee_cents','rate_units','prior_issued_cents'}}
    result.update(outcome=Outcome.MISSING.value,amount=None,semantic_binding_status='REVIEW_REQUIRED',
                  trace=[reason],missing=['Reviewed source and evidence semantic binding'],issuance_status='NOT_ESTABLISHED')
    try:
        if all(facts.get(key)==overlay[key] for key in ('account','agreement','product','plan')):
            if manifest.get('fixed_filing'):
                cutoff=manifest['fixed_filing']['at']
                inclusive=manifest['fixed_filing']['endpoint']=='inclusive'
            else:
                _,end=month_bounds(facts.get('month'))
                stamp,inclusive=deadline(facts,overlay,manifest,end)
                cutoff=stamp.isoformat()
            result.update(claim_cutoff=cutoff,cutoff_inclusive=inclusive,
                          deadline_context='Published clock; source meaning remains under review.')
    except (ValueError,TypeError,KeyError,OverflowError):
        pass
    return result
