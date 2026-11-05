"""Assemble authored inputs through existing engines; never read expectations.

The local signatures verify specimen integrity, not operational authority or
execution by a real commercial party. See README.md before using this package.
"""
from datetime import datetime
from decimal import Decimal,localcontext
from hashlib import sha256
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from uptime.contracts import Citation,fingerprint
from uptime.pricing_terms import compile_fixed_monthly
from uptime.pricing import Agreement,ContractVersion,Rate,Tier,Invoice,InvoiceLine,evaluate_price
from uptime.vendor_terms import Document,Overlay,bind_overlay,compile_terms

ROOT=Path(__file__).resolve().parent
INPUTS=('order-form.txt','amendment-2026-03.txt','document.json','overlay.json','agreement.json',
        'invoices.json','usage.json','citations.json','signatures.json',
        'january-resource-log.txt','supplements.json','correspondence.json',
        'order-monthly-rate.txt','amendment-monthly-rate.txt','settlement_invoice.json')


def _at(value):
    return datetime.fromisoformat(value)


def _json(root,name):
    return json.loads((root/name).read_text())


def verify_package(root):
    index=_json(root,'package.json')
    if index.get('schema')!='northwind-authored-inputs/1' or set(index.get('input_sha256',{}))!=set(INPUTS):
        raise ValueError('Unexpected authored package input index.')
    for name in INPUTS:
        if sha256((root/name).read_bytes()).hexdigest()!=index['input_sha256'][name]:
            raise ValueError('Authored package input changed: '+name)
    for record in _json(root,'signatures.json'):
        payload=record['payload']
        if (record['kind']!='LOCAL_TEST_SIGNATURE' or record['algorithm']!='Ed25519' or record['certificate'] is not None
                or payload['source_file'] not in INPUTS
                or payload['source_sha256']!=index['input_sha256'][payload['source_file']]
                or payload['pricing_input_sha256']!=index['input_sha256']['agreement.json']):
            raise ValueError('Unbound local signature specimen.')
        canonical=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
        Ed25519PublicKey.from_public_bytes(base64.b64decode(record['public_key_base64'],validate=True)).verify(
            base64.b64decode(record['signature_base64'],validate=True),canonical)
    for citation in _json(root,'citations.json'):
        text=(root/citation['source_file']).read_text()
        if (citation['source_sha256']!=index['input_sha256'][citation['source_file']]
                or text[citation['start']:citation['end']]!=citation['quote']
                or sha256(citation['quote'].encode()).hexdigest()!=citation['quote_sha256']):
            raise ValueError('Source citation bytes changed.')
    for version in _json(root,'agreement.json')['versions']:
        for rate in version['rates']:
            terms=rate.get('fixed_monthly')
            if terms and (terms['source_sha256']!=index['input_sha256'].get(terms['source_file'])
                          or terms['source_text']!=(root/terms['source_file']).read_text()):
                raise ValueError('Typed fixed monthly schedule does not match its complete source bytes.')
    for row in _json(root,'usage.json'):
        spans=sorted(row['eligible_intervals'],key=lambda span:span['start'])
        total=0;previous=None
        for span in spans:
            start,end=_at(span['start']),_at(span['end'])
            if (not _at(row['start'])<=start<end<=_at(row['end']) or previous and start<previous
                    or span['incident_id']!=row['incident_id'] or span['affected'] is not True or span['exclusion']!='none'):
                raise ValueError('Authored interval scope or chronology mismatch.')
            total+=(end-start).total_seconds();previous=end
        if row['month_complete'] is True:
            if total!=row['eligible_downtime_minutes']*60 or _at(row['observed_at'])<_at(row['end']):
                raise ValueError('Declared complete-month measurement disagrees with interval evidence.')
        elif row['eligible_downtime_minutes'] is not None:
            raise ValueError('Incomplete authored coverage cannot assert a monthly total.')
    for row in _json(root,'supplements.json'):
        artifact,verification=row['artifact'],row['verification']
        if (artifact['content']!=(root/'january-resource-log.txt').read_text()
                or sha256(artifact['content'].encode()).hexdigest()!=artifact['body_sha256']
                or any(artifact[k]!=verification[k] for k in ('artifact_ref','artifact_type','body_sha256'))):
            raise ValueError('Supplement source bytes or independent verification descriptor disagree.')
    return index


def _agreement(data):
    versions=[]
    for row in data['versions']:
        rates=tuple(Rate(r['product'],r['unit'],tuple(Tier(Decimal(t['upper']) if t['upper'] is not None else None,
            Decimal(t['rate'])) for t in r['tiers']),r['mode'],r['quantity_scope'],r['boundary'],
            compile_fixed_monthly(r['fixed_monthly']['source_text'],Citation(**r['fixed_monthly']['citation'])) if r.get('fixed_monthly') else None) for r in row['rates'])
        versions.append(ContractVersion(row['id'],_at(row['effective_at']),_at(row['signed_at']),tuple(row['signatories']),
            row['supersedes'],rates,tuple(row['excluded_products']),Citation(**row['citation']),row['currency'],
            row['tax_treatment'],row['rounding']))
    return Agreement(data['id'],data['customer'],data['vendor'],_at(data['expires_at']),tuple(versions))


def _invoice(data):
    lines=tuple(InvoiceLine(r['id'],r['product'],Decimal(r['quantity']) if r['quantity'] is not None else None,
        r['unit'],_at(r['start']),_at(r['end']),Decimal(r['net']),Decimal(r['tax']) if r['tax'] is not None else None,
        r['allocation_ref'],r['allocation_complete']) for r in data['lines'])
    return Invoice(data['id'],data['customer'],data['vendor'],_at(data['issued_at']),data['payment_status'],
                   data['currency'],Decimal(data['total']),lines)


def governing_fee(agreement,invoice,product,fee_line_ref,*,as_of=None):
    """Only a complete priced eligible line can establish an SLA fee base."""
    result=evaluate_price(agreement,invoice,as_of=as_of)
    matches=[line for line in result.lines if line.product==product and line.line_id==fee_line_ref]
    if result.overcharge is None or len(matches)!=1 or matches[0].expected is None:
        raise ValueError('A complete governing eligible service fee is unavailable.')
    expected=matches[0].expected
    with localcontext() as context:
        context.prec=60
        cents=expected*100
        if cents!=cents.to_integral_value() or cents<0:
            raise ValueError('Governing fee does not have exact nonnegative cents.')
        return int(cents),matches[0],result


def load_package(directory=None):
    root=Path(directory) if directory is not None else ROOT
    index=verify_package(root)
    document,overlay=_json(root,'document.json'),_json(root,'overlay.json')
    manifest=compile_terms(Document(**document))
    bound=bind_overlay(manifest,Overlay(**overlay))
    agreement_data=_json(root,'agreement.json')
    agreement=_agreement(agreement_data)
    usage={row['month']:row for row in _json(root,'usage.json')}
    months=[]
    for row in _json(root,'invoices.json'):
        month=row['month']; observation=usage[month]; invoice=_invoice(row['invoice'])
        price=evaluate_price(agreement,invoice,as_of=_at(row['received_at']))
        if price.overcharge is None:
            cents,finding=None,None
        else:
            cents,finding,price=governing_fee(agreement,invoice,overlay['product'],overlay['fee_line_ref'],as_of=_at(row['received_at']))
        facts={k:bound[k] for k in ('agreement','account','product','plan','fee_line_ref')}
        facts.update(month=month,eligible_downtime_minutes=observation['eligible_downtime_minutes'],
            monitor_source=observation['monitor_source'],monitor_ref=observation['monitor_ref'],monitor_month=month,
            month_complete=observation['month_complete'],exclusions_removed=observation['exclusions_removed'],
            monthly_fee_cents=cents,fee_month=month,fee_ref=invoice.id+':'+(finding.version if finding else 'unresolved'),received_at=row['received_at'])
        months.append(dict(month=month,facts=facts,invoice=invoice,invoice_input=row['invoice'],usage=observation,
            pricing_result=price,scope=dict(account=overlay['account'],vendor=document['text'].splitlines()[1].removeprefix('Vendor: '),contract=overlay['agreement'],
                service=overlay['product'],component=observation['component_id'],invoice=invoice.id,incident=observation['incident_id'],
                currency='USD',month=month,region=observation['region']),
            governing_fee_cents=cents,governing_fee_version=finding.version if finding else None,
            receipt_ref=row['receipt_ref'],citations=[v['citation'] for v in agreement_data['versions'] if finding is not None and v['id']==finding.version]))
    settlement=_json(root,'settlement_invoice.json')
    settlement_invoice=_invoice(settlement['invoice'])
    settlement=dict(settlement,invoice_input=settlement['invoice'],invoice=settlement_invoice,
        pricing_result=evaluate_price(agreement,settlement_invoice,as_of=_at(settlement['observed_at'])))
    return dict(settlement=settlement,tenant=index['tenant'],document=document,overlay=overlay,manifest=manifest,pricing_agreement=agreement,
                pricing_agreement_input=agreement_data,months=months,citations=_json(root,'citations.json'),
                signature_records=_json(root,'signatures.json'),supplements=_json(root,'supplements.json'),
                correspondence=_json(root,'correspondence.json'),input_sha256=index['input_sha256'])


def build_fee_registry(package):
    """Trusted fixed input registration only; no synthetic signature/grant minting."""
    from uptime.correspondence_types import Scope
    from uptime.governing_fees import FeeEntry,FeeRegistry
    overlay=bind_overlay(package['manifest'],Overlay(**package['overlay']))
    return FeeRegistry(tuple(FeeEntry('northwind-fee-'+row['month'],package['tenant'],Scope(**row['scope']),
        overlay['plan'],overlay['fee_line_ref'],package['pricing_agreement'],row['invoice'],
        package['manifest']['document']['sha256'],fingerprint(package['manifest']),fingerprint(overlay)) for row in package['months']))
