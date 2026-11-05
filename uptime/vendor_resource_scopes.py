"""Private synthetic attestations for scoped subscriptions and intersecting independent monitors."""
from datetime import date, timedelta

from .twilio import _merge, _subtract
from .vendor_resource_eval import Gap, Unsupported, instant, micros, required_ref
from .vendor_resource_predicates import folded


def subscription(facts, overlay, manifest, start, end):
    terms = manifest.get('subscription')
    if not terms:
        return overlay.get('resource_id')
    record = overlay.get('subscription_record')
    if (not isinstance(record, dict) or record.get('verified') is not True or record.get('signed') is not True
            or any(record.get(k) != overlay[k] for k in ('account', 'agreement', 'product', 'plan'))):
        raise Gap('A verified signed subscription for this account, agreement, product and edition is required.')
    required_ref(record.get('ref'))
    region = required_ref(record.get('region'))
    if facts.get('region') != region:
        raise Gap('Observation must identify the signed subscription region.')
    if terms.get('version') and record.get('contract_version') != terms['version']:
        raise Gap('Subscription does not attest the governing source version.')
    if terms.get('regions') and folded(region) not in {folded(x) for x in terms['regions']}:
        raise Unsupported('Region falls outside the covered subscription.')
    if (folded(record.get('subscription_type')) in {folded(x) for x in terms.get('excluded_types', [])}
            or folded(overlay['product']) in {folded(x) for x in terms.get('excluded_products', [])}):
        raise Unsupported('Subscription class or product is outside the contractual remedy.')
    try:
        opened, closed = date.fromisoformat(record['active_from']), date.fromisoformat(record['active_until'])
    except (KeyError, TypeError, ValueError):
        raise Gap('Signed active subscription interval is missing or malformed.') from None
    if not opened <= start.date() <= end.date() - timedelta(days=1) <= closed:
        raise Unsupported('The signed subscription does not cover the complete service month.')
    return region


def scope_match(record, facts, overlay, region):
    return (isinstance(record, dict) and record.get('region') == region
            and record.get('month') == facts['month']
            and all(record.get(k) == overlay[k] for k in ('account','product','resource_id','agreement')))


def _clocked(report, facts, overlay, region, start, end, positive, nonqualifying):
    if (not scope_match(report, facts, overlay, region) or report.get('verified') is not True
            or report.get('complete') is not True):
        raise Gap('Independent verified full-month monitor statement required.')
    ref, source_id = required_ref(report.get('ref')), required_ref(report.get('source_id'))
    records = report.get('records')
    if not isinstance(records, list) or len(records) > 1000:
        raise Gap('Monitor must supply a bounded complete interval list.')
    included, excluded, known = [], [], {}
    for row in records:
        if not isinstance(row, dict) or any(not row.get(k) for k in ('account','product','region','resource_id')):
            raise Gap('Missing interval identity.')
        if row['region'] != region or any(row[k] != overlay[k] for k in ('account','product','resource_id')):
            continue
        record_id = required_ref(row.get('ref'))
        if known.get(record_id, row) != row:
            raise Gap('Conflicting records under the same monitor reference.')
        known[record_id] = row
        left, right = instant(row.get('start')), instant(row.get('end'))
        if right <= left:
            raise Gap('Invalid authoritative monitor interval.')
        status = folded(required_ref(row.get('status')))
        if status == folded(positive):
            target = included
        elif status in {folded(x) for x in nonqualifying}:
            target = excluded
        else:
            raise Gap('Observed status is absent from the source-defined monitor vocabulary.')
        if max(start, left) < min(end, right):
            target.append((max(start,left), min(end,right)))
    included, excluded = _merge(included), _merge(excluded)
    if _intersections(included, excluded):
        raise Gap('A monitor contradicts itself for the same scoped interval.')
    if not known and report.get('no_events_verified') is not True:
        raise Gap('An absent scoped stream cannot establish zero outages without an explicit negative finding.')
    return included, ref, source_id


def _intersections(first, second):
    overlap = []
    a = b = 0
    while a < len(first) and b < len(second):
        left, right = max(first[a][0], second[b][0]), min(first[a][1], second[b][1])
        if left < right:
            overlap.append((left, right))
        if first[a][1] <= second[b][1]:
            a += 1
        else:
            b += 1
    return overlap


def dual_downtime(facts, overlay, manifest, start, end, region, windows):
    if facts.get('intervals'):
        raise Gap('Direct outage totals cannot replace two independently attested source streams.')
    cfg = manifest['telemetry']
    customer = facts.get('customer_telemetry')
    c, cref, cid = _clocked(customer, facts, overlay, region, start, end, cfg['customer_status'],
                            cfg.get('customer_nonqualifying', []))
    p, pref, pid = _clocked(facts.get('provider_telemetry'), facts, overlay, region, start, end,
                            cfg['provider_status'], cfg.get('provider_nonqualifying', []))
    if cref == pref or cid == pid:
        raise Gap('Both observations trace to the same source.')
    if cfg.get('custodian'):
        custody = customer.get('custodian')
        if (not isinstance(custody, dict) or custody.get('verified') is not True or custody.get('signed') is not True or not custody.get('ref')
                or custody.get('source_id') != cid or custody.get('region') != region
                or any(custody.get(k) != overlay[k] for k in ('account','product','resource_id'))):
            raise Gap('Missing signed local custodian attestation for the scoped recording system.')
        required_ref(custody['ref'])
    excluded = list(windows)
    rows = facts.get('exclusions', [])
    if not isinstance(rows, list) or len(rows) > 1000:
        raise Gap('Malformed exclusion report list.')
    causes = {folded(x) for x in manifest.get('exclusions', [])}
    for row in rows:
        if not scope_match(row, facts, overlay, region) or folded(row.get('cause')) not in causes:
            raise Gap('Exclusion lacks a source-grounded cause and scoped supporting record.')
        required_ref(row.get('ref'))
        if manifest.get('causal_report'):
            if row.get('verified') is not True or row.get('sole_cause') is not True:
                raise Gap('Independently verified sole-cause finding required.')
            required_ref(row.get('root_cause_ref'))
        left, right = instant(row.get('start')), instant(row.get('end'))
        if right <= left:
            raise Gap('Invalid established exclusion interval.')
        excluded.append((left,right))
    return sum(micros(b-a) for a,b in _subtract(_intersections(c,p), excluded))


def portal_clock(facts, overlay, manifest, proof, received):
    clock = manifest.get('cure_clock')
    if not manifest.get('original_receipt') and not clock:
        return
    region = facts.get('region', overlay['resource_id'])
    if not scope_match(proof, facts, overlay, region) or instant(proof.get('received_at')) != received:
        raise Gap('Original filing requires the matching scoped portal arrival receipt.')
    required_ref(proof.get('ticket_id'))


def supplement_clock(facts, overlay, manifest, proof, row, original):
    clock = manifest['cure_clock']
    region = facts.get('region', overlay['resource_id'])
    response = proof.get('response_receipt')
    if (not scope_match(response, facts, overlay, region) or response.get('verified') is not True
            or response.get('ref') == proof.get('ref') or response.get('ticket_id') != proof['ticket_id'] or row.get('ticket_id') != proof['ticket_id']
            or row.get('response_ref') != required_ref(response.get('ref')) or response.get('kind') not in clock['trigger']):
        raise Gap('Supplement requires a separately verified response delivery on the original ticket.')
    delivered = instant(response.get('delivered_at'))
    if delivered < original or instant(row.get('received_at')) < delivered:
        raise Gap('Contradictory original, response-delivery or supplemental timestamps.')
    return delivered + timedelta(days=clock['count']), clock['endpoint'] == 'inclusive'
