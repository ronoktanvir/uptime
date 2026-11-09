"""Read-only clause classifier for the strict deterministic monthly parser (`vendor_terms.compile_terms`).

`compile_terms` stops at the first clause it cannot read. This reports every clause at once: the template it
matches, or that it is unrecognized, plus which required terms no clause establishes. The report carries no
source text. It holds only clause numbers, offsets, lengths, SHA-256 values and fixed category names, so an
evaluation lane can share it without disclosing a sealed source.

It mirrors the parser's matching order using the parser's own patterns. `tests/test_vendor_strict_diagnostics_89.py`
pins parity: on every probe, the first non-recognized clause is the clause the parser itself refuses. It is outside
the reviewed-semantics file set and never accepts, compiles or stores anything.

The released remediation templates are classified by the parser's own `_remediated` predicate, with the same
clause context: a title is recognized only as the bare first line, and an inherited-scope tier only after an
explicitly scoped tier. Document-level conditions stay parser-only (a unique product/plan scope for inherited
tiers and party statements, duplicate terms, tier monotonicity), except that `missing_required` counts the
credit remedy as established by the fee-basis and future-invoice clauses only when both are present.
"""
from hashlib import sha256
import re

from .vendor_terms import (COMPLETED_STEPS, DAY, FILING, MEASUREMENT, NAME, REMEDY, STEP_ROUNDING, TABLE_HEADERS, TIER,
                           _clauses, _match, _remediated, _validate_document)

SCHEMA = 'strict-clause-classification/1'
HEADING = (r'(?:#*\s*)?(?:(?:Monthly )?Availability|Service Level) (?:Agreement|Schedule|Commitment)|'
           r'Synthetic public (?:test )?(?:contract|agreement)')
REQUIRED = ('vendor', 'agreement', 'effective', 'period', 'filing_days', 'remedy')
UNRECOGNIZED, TABLE_UNSUPPORTED = 'UNRECOGNIZED', 'TABLE_UNSUPPORTED'
# Remediation template categories that establish a required term on their own.
ESTABLISHES = {'agreement_title': 'agreement', 'vendor_party_statement': 'vendor', 'effective_sentence': 'effective',
               'filing_days_article': 'filing_days'}
# Either half alone is incomplete; together they establish the existing remedy.
REMEDY_HALVES = ('remedy_fee_basis', 'remedy_future_invoice')


def _category(clause, table, context=None):
    """(category, new table state). Same order and patterns as compile_terms.

    `context` carries the clause position (quote, index, text, start, end, scoped_tier_before) that the title and
    inherited-scope tier templates need; without it those two templates are never recognized.
    """
    if '|' in clause:
        cells = [cell.strip() for cell in clause.strip('|').split('|')]
        if table is not None and all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells) and len(cells) == 4:
            return 'table_separator', table
        if len(cells) == 4:
            fields = [next((i for i, names in enumerate(TABLE_HEADERS) if cell.casefold() in names), -1) for cell in cells]
            if set(fields) == {0, 1, 2, 3}:
                return 'table_header', [fields.index(i) for i in range(4)]
            if table is not None:
                below, rate = cells[table[2]], cells[table[3]]
                if below.endswith('%') and rate.endswith('%'):
                    return 'tier', table
        return TABLE_UNSUPPORTED, table
    for category, pattern in (
            ('vendor', rf'(?:Vendor|Provider|Service provider)\s*:\s*({NAME})'),
            ('agreement', rf'(?:Agreement(?: ID)?|Contract(?: ID)?)\s*:\s*({NAME})'),
            ('effective', rf'(?:Effective(?: period)?\s*:\s*|(?:This agreement is )?effective (?:from )?)'
                          rf'({DAY})(?: (?:through|to|until and including) ({DAY}))?'),
            ('period', MEASUREMENT), ('tier', TIER), ('credit_rule', COMPLETED_STEPS),
            ('credit_rounding', STEP_ROUNDING), ('filing_days', FILING), ('remedy', REMEDY), ('heading', HEADING)):
        if _match(pattern, clause):
            return category, None
    if found := _remediated(clause, **(context or {})):
        return found[0], None
    return UNRECOGNIZED, None


def classify(document, segments=None):
    """Per-clause categories and missing required terms for the strict parser. Carries no source text."""
    _validate_document(document)
    rows, table, scoped = [], None, False
    for index, (start, end, quote) in enumerate(_clauses(document.text, segments), 1):
        clause = ' '.join(quote.split()).removesuffix('.').strip()
        category, table = _category(clause, table, {'quote': quote, 'index': index, 'text': document.text,
                                                    'start': start, 'end': end, 'scoped_tier_before': scoped})
        scoped = scoped or category == 'tier'  # the parser's explicitly scoped tiers (sentence or table row)
        rows.append({'clause': index, 'start': start, 'end': end, 'characters': end - start,
                     'sha256': sha256(quote.encode()).hexdigest(), 'category': category})
    found = {row['category'] for row in rows}
    established = {ESTABLISHES.get(category, category) for category in found}
    if set(REMEDY_HALVES) <= found:
        established.add('remedy')
    needed = REQUIRED + (('credit_rule', 'credit_rounding') if 'credit_rule' in found else ())
    unread = [row['clause'] for row in rows if row['category'] in (UNRECOGNIZED, TABLE_UNSUPPORTED)]
    return {'schema': SCHEMA, 'source_sha256': sha256(document.text.encode()).hexdigest(), 'clauses': rows,
            'unrecognized_clauses': unread, 'missing_required': [term for term in needed if term not in established],
            'tier_present': 'tier' in found or 'credit_rule' in found}
