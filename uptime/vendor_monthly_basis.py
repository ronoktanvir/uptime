"""Explicit source opt-in for complete-service-month evidence.

This validates a compiled, reviewed manifest; it does not replace adapter source
integrity or human review. Absence retains the legacy incident evidence path.
"""
import re

KIND = 'complete_service_month/1'
BASIS_CLAUSE = (
    r'(?:Claims (?:are based on|are supported by|use) (?:a )?complete UTC calendar-month report '
    r'for the entire service|A complete UTC calendar-month report for the entire service is required for claims)'
    r'; incident identifiers are not required'
)


def is_monthly_basis_clause(quote):
    """Recognize the entire explicit clause, never a substring or an inferred waiver."""
    if type(quote) is not str:
        return False
    text = ' '.join(quote.split()).removesuffix('.').strip()
    return re.fullmatch(BASIS_CLAUSE, text, re.IGNORECASE) is not None


def validate_monthly_evidence_basis(manifest):
    """Return False when absent, True when valid; refuse every malformed opt-in.

    Callers must already have verified the adapter version, source and approval.
    This check is deliberately pure and grants no authority on its own.
    """
    if type(manifest) is not dict:
        raise ValueError('A compiled agreement manifest is required.')
    if 'evidence_basis' not in manifest:
        return False
    if (manifest['evidence_basis'] != KIND or manifest.get('family') != 'monthly-availability/1'
            or manifest.get('period') != 'utc_calendar_month'
            or manifest.get('remedy') != 'affected_monthly_fees_future_invoice'):
        raise ValueError('Unsupported complete-month evidence basis.')
    if (type(manifest.get('filing_days')) is not int
            or not 1 <= manifest['filing_days'] <= 365):
        raise ValueError('Complete-month evidence requires a grounded filing window.')
    rows = manifest.get('citations')
    if type(rows) is not list or any(type(row) is not dict for row in rows):
        raise ValueError('Complete-month evidence requires source citations.')
    for field in ('period', 'filing_days', 'evidence_basis'):
        found = [row for row in rows if row.get('field') == field]
        if len(found) != 1:
            raise ValueError('Complete-month evidence requires one grounded ' + field + ' citation.')
    citation = next(row for row in rows if row.get('field') == 'evidence_basis')
    if (type(citation.get('id')) is not int or citation['id'] < 1
            or type(citation.get('start')) is not int or citation['start'] < 0
            or type(citation.get('end')) is not int or citation['end'] <= citation['start']
            or not is_monthly_basis_clause(citation.get('quote'))
            or citation['end'] - citation['start'] != len(citation['quote'])):
        raise ValueError('Complete-month evidence basis is not an exact explicit source span.')
    source = manifest.get('document')
    if (type(source) is not dict or type(source.get('sha256')) is not str
            or re.fullmatch('[0-9a-f]{64}', source['sha256']) is None):
        raise ValueError('Complete-month evidence basis requires an identified source.')
    scopes = set()
    if 'credit_rule' in manifest:
        if manifest.get('tiers'):
            raise ValueError('Mixed credit rules do not establish one service scope.')
        rules = [manifest['credit_rule']]
    else:
        rules = manifest.get('tiers')
    if type(rules) is not list or not rules:
        raise ValueError('Complete-month evidence requires a covered service scope.')
    for rule in rules:
        if (type(rule) is not dict or type(rule.get('product')) is not str
                or type(rule.get('plan')) is not str or not rule['product'] or not rule['plan']):
            raise ValueError('Complete-month evidence has an invalid service scope.')
        scopes.add((rule['product'], rule['plan']))
    if len(scopes) != 1:
        raise ValueError('Complete-month evidence requires one unambiguous service and plan.')
    return True
