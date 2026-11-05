"""Shape-only projection. No completeness, fee, time, or receipt defaults."""
from copy import deepcopy
from decimal import Decimal
import re

from .witness import canonical, digest


def project_facts(facts):
    result = deepcopy(facts)
    # A field list and a name/value map are two published representations.
    proof = result.get('filing_proof')
    if isinstance(proof, dict) and isinstance(proof.get('fields'), list):
        if len({row['name'] for row in proof['fields']}) != len(proof['fields']):
            raise ValueError('Duplicate filing fields cannot be collapsed')
        proof['fields'] = {row['name']: ', '.join(row['refs']) for row in proof['fields']}
    return result


def bind_shadow(template, overlay):
    """Bind independent scenarios to this reviewed tenant scope, retaining all observations."""
    result = deepcopy(template)
    facts = result['facts']
    old_fee = facts['fee_line_ref']
    replacements = {facts[field]: overlay[field] for field in
                    ('account', 'agreement', 'product', 'plan', 'fee_line_ref', 'resource_id')}
    for field in ('account', 'agreement', 'product', 'plan', 'fee_line_ref', 'resource_id'):
        facts[field] = overlay[field]
    for kind in ('service_monitor', 'service_invoice'):
        record = facts[kind]
        for field in ('account', 'agreement', 'product', 'plan'):
            record[field] = overlay[field]
        if kind == 'service_invoice':
            for row in record['content']['lines']:
                if row['ref'] == old_fee:
                    row['ref'] = overlay['fee_line_ref']
        record['content_sha256'] = digest(canonical(record['content']))
    proof = facts['filing_proof']
    for field in ('account', 'agreement', 'product', 'plan', 'resource_id'):
        if field in proof:
            proof[field] = overlay[field]
    for row in proof.get('fields', []):
        row['refs'] = [replacements.get(ref, ref) for ref in row['refs']]
    result['facts'] = project_facts(facts)
    return result


def source_categories(document):
    """Literal fee exclusions only, never an inference from evaluator results."""
    return re.findall(r'Exclude\s+([^\n.]+?)\s+from the credit base', document, flags=re.I)


def project_record(body, exclusions):
    result = deepcopy(body)
    if result['kind'] == 'service_invoice':
        for row in result['content']['lines']:
            category = row['category']
            # Expand only the grammatical fee suffix; retain amounts and classifications.
            for literal in exclusions:
                if literal.casefold() == category.casefold() + ' fees':
                    row['category'] = literal
        result['content_sha256'] = digest(canonical(result['content']))
    return result


def filing_fields(scope, overlay, invoice_body):
    """An outgoing packet built from existing records; this is never a receipt."""
    lines = invoice_body['content']['lines']
    subscription = [r['ref'] for r in lines if r['ref'] == overlay['fee_line_ref']]
    coaching = [r['ref'] for r in lines if r['kind'] != 'recurring_subscription']
    # A typed ref names the existing source record containing the service/plan;
    # the public display name is not an identifier (it can contain spaces).
    return [dict(name='account', refs=[scope['account']]),
            dict(name='service', refs=[invoice_body['source_ref']]),
            dict(name='plan', refs=[invoice_body['source_ref']]),
            dict(name='monthly period', refs=[scope['month']]),
            dict(name='subscription fee', refs=subscription),
            dict(name='any operator coaching fee', refs=coaching)]


def cents(amount):
    value = Decimal(amount) * 100
    if value != value.to_integral_value():
        raise ValueError('Expected an exact independently specified cent amount')
    return int(value)


def pin_original(case, claim_view, source_text):
    """Translate an explicit frozen source/version/order commitment to public API pins.

    A GET is not historical evidence. Without the independent original commitment,
    preserve the absent pins. Never infer them from the current active publication.
    """
    body = deepcopy(case['original_filing'])
    commitment = case.get('original_contract')
    if commitment is None:
        return body
    if (commitment['source_sha256'] != digest(source_text.encode())
            or commitment['source_sha256'] != claim_view.get('contract_source_sha256')
            or claim_view.get('scope') != case['scope']
            or not re.search(r'\bVersion\s+' + re.escape(commitment['public_version']) + r'\.', source_text)
            or commitment['overlay_sha256'] != digest(canonical(case['overlay']))
            or not claim_view.get('contract_version')):
        raise ValueError('Original source/version/order commitment does not match the public claim view')
    for name, value in (('contract_version', claim_view['contract_version']),
                        ('contract_source_sha256', commitment['source_sha256'])):
        if name in body and body[name] != value:
            raise ValueError('Cannot replace an original contract pin')
        body[name] = value
    return body
