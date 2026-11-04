"""Source-grounded extraction for the monthly availability/future invoice credit family.

The bounded recognizer consumes every nonblank clause. A proposed model span can
join wrapped sentences, but cannot introduce values, code or unsupported terms.
"""
from datetime import date
from hashlib import sha256
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .contracts import fingerprint

REVISION = 'monthly-availability/1'
PERCENT_SCALE = 1_000_000  # integer units per percent
MAX_PERCENT = 100 * PERCENT_SCALE
NUMBER = r'[0-9]{1,3}(?:\.[0-9]{1,6})?'
NAME = r"[A-Za-z0-9][A-Za-z0-9 &()_'./+\-]{0,99}?"
DAY = r'[0-9]{4}-[0-9]{2}-[0-9]{2}'


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Document(Strict):
    name: str = Field(min_length=1, max_length=160)
    uri: str = Field(min_length=1, max_length=512)
    classification: str
    text: str = Field(min_length=1, max_length=50000)


class FilingOverride(Strict):
    filing_days: int = Field(ge=1, le=365)
    source_ref: str = Field(min_length=1, max_length=160)
    quote: str = Field(min_length=1, max_length=512)


class Overlay(Strict):
    agreement: str
    account: str
    product: str
    plan: str
    effective_from: str
    effective_until: str
    fee_line_ref: str
    currency: str
    override: FilingOverride | None = None


class Intake(Strict):
    document: Document
    overlay: Overlay


def percent_units(token):
    if not re.fullmatch(NUMBER, token):
        raise ValueError('Unrepresentable percentage precision.')
    whole, _, frac = token.partition('.')
    value = int(whole) * PERCENT_SCALE + int(frac.ljust(6, '0'))
    if not 0 < value <= MAX_PERCENT:
        raise ValueError('Percentage outside the supported interval.')
    return value


def _match(pattern, clause):
    return re.fullmatch(pattern, clause, re.IGNORECASE)


FILING = (
    r'(?:complete )?(?:claims?|credit requests?) (?:must be (?:received|filed|submitted)|are due) '
    r'(?:within|no later than) ([0-9]{1,3}) calendar days (?:after|following) '
    r'(?:month end|the end of (?:the |each )?(?:affected |applicable )?(?:calendar |measurement )?month)'
)
MEASUREMENT = (
    r'(?:(?:monthly )?(?:service )?(?:availability|uptime) is (?:measured|calculated) '
    r'(?:over|for|in|across) (?:each |the )?(?:full )?UTC calendar month|'
    r'(?:the )?measurement period is (?:each |a |the )?UTC calendar month|'
    r'(?:each |a )?calendar month in UTC is the measurement period)'
)
REMEDY = (
    r'(?:service )?credits (?:apply to|are calculated (?:on|as a percentage of)|are based on) '
    r'(?:the )?affected (?:product.s |service.s )?monthly fees? '
    r'(?:on|and (?:apply|are applied) to|and (?:will be|are) (?:applied|credited) (?:to|on)) '
    r'(?:a |the |your )?(?:future|next) invoice'
)
TIER = (
    rf'For (?:the )?(?P<product>{NAME}) (?:on (?:the )?|under (?:the )?)(?P<plan>{NAME}) plan,? '
    rf'(?:monthly )?(?:availability|uptime) (?:below|less than|under) (?P<below>{NUMBER})% '
    rf'(?:earns|qualifies for|results in|receives) (?:a |an )?(?P<rate>{NUMBER})% (?:service )?credit'
)
TABLE_HEADERS = (
    {'product', 'service', 'covered product'}, {'plan', 'subscription plan'},
    {'monthly availability below', 'monthly uptime below', 'availability below', 'uptime below',
     'monthly availability (<)', 'monthly uptime (<)'},
    {'service credit', 'service credit (%)', 'credit', 'credit rate'},
)


def _clauses(text, segments):
    if segments is None:
        # Periods inside percentages, product names and ISO dates are retained.
        return [(m.start(), m.end(), m[0]) for m in re.finditer(
            r'[^\s].*?(?:\.(?=\s+[A-Z])|(?=\s*$))', text, re.MULTILINE)]
    if not isinstance(segments, list) or not 1 <= len(segments) <= 200:
        raise ValueError('Invalid proposed clause index.')
    rows, cursor = [], 0
    for quote in segments:
        if not isinstance(quote, str) or not quote or len(quote) > 4096:
            raise ValueError('Invalid proposed clause span.')
        start = text.find(quote, cursor)
        if start < cursor or text[cursor:start].strip():
            raise ValueError('Model proposal dropped or invented source material.')
        end = start + len(quote)
        rows.append((start, end, quote))
        cursor = end
    if text[cursor:].strip():
        raise ValueError('Incomplete proposed source coverage.')
    return rows


def _validate_document(document):
    if document.classification not in {'synthetic_public', 'public'}:
        raise ValueError('Only approved public or explicitly synthetic public source text is supported.')
    uri = urlsplit(document.uri)
    if not ((uri.scheme == 'https' and uri.hostname and not uri.username and not uri.password)
            or (document.classification == 'synthetic_public' and document.uri.startswith('urn:'))):
        raise ValueError('Expected HTTPS provenance or a synthetic URN.')
    if any(ord(char) < 32 and char not in '\n\r\t' for char in document.text):
        raise ValueError('Unsupported document encoding.')


def compile_terms(document, *, segments=None):
    _validate_document(document)
    digest = sha256(document.text.encode()).hexdigest()
    manifest = {'family': REVISION, 'document': {
        'name': document.name, 'uri': document.uri, 'classification': document.classification, 'sha256': digest},
        'tiers': [], 'citations': []}
    seen = set()
    table = None

    def atom(key, value, citation):
        if key in seen:
            raise ValueError('Duplicate or conflicting source clause: ' + key)
        seen.add(key)
        manifest[key] = value
        citation['field'] = key

    def tier(product, plan, below, credit, citation):
        if not _match(NAME, product) or not _match(NAME, plan):
            raise ValueError('Ambiguous product/plan scope.')
        manifest['tiers'].append(dict(product=product, plan=plan, below_units=percent_units(below),
                                      credit_units=percent_units(credit), citation=citation['id']))
        citation['field'] = 'tier'

    clauses = _clauses(document.text, segments)
    if not 1 <= len(clauses) <= 200:
        raise ValueError('Document requires one to two hundred supported source clauses.')
    cursor = 0
    for start, end, quote in clauses:
        if document.text[cursor:start].strip():
            raise ValueError('Unrecognized source material between clauses.')
        cursor = end
        c = {'id': len(manifest['citations']) + 1, 'start': start, 'end': end, 'quote': quote}
        manifest['citations'].append(c)
        clause = ' '.join(quote.split()).removesuffix('.').strip()
        if '|' in clause:
            cells = [cell.strip() for cell in clause.strip('|').split('|')]
            if table is not None and all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells) and len(cells) == 4:
                c['field'] = 'table_separator'
                continue
            if len(cells) == 4:
                fields = [next((i for i, names in enumerate(TABLE_HEADERS) if cell.casefold() in names), -1)
                          for cell in cells]
                if set(fields) == {0, 1, 2, 3}:
                    table = [fields.index(i) for i in range(4)]
                    c['field'] = 'table_header'
                    continue
                if table is not None:
                    product, plan, below, rate = [cells[i] for i in table]
                    if below.endswith('%') and rate.endswith('%'):
                        tier(product, plan, below[:-1], rate[:-1], c)
                        continue
            raise ValueError(f'Unsupported percentage table at clause {c["id"]}.')
        table = None
        if m := _match(rf'(?:Vendor|Provider|Service provider)\s*:\s*({NAME})', clause):
            atom('vendor', m[1], c)
        elif m := _match(rf'(?:Agreement(?: ID)?|Contract(?: ID)?)\s*:\s*({NAME})', clause):
            atom('agreement', m[1], c)
        elif m := _match(rf'(?:Effective(?: period)?\s*:\s*|(?:This agreement is )?effective (?:from )?)'
                         rf'({DAY}) (?:through|to|until and including) ({DAY})', clause):
            if date.fromisoformat(m[1]) > date.fromisoformat(m[2]):
                raise ValueError('Reversed effective interval.')
            atom('effective', [m[1], m[2]], c)
        elif _match(MEASUREMENT, clause):
            atom('period', 'utc_calendar_month', c)
        elif m := _match(TIER, clause):
            tier(m['product'], m['plan'], m['below'], m['rate'], c)
        elif m := _match(FILING, clause):
            if not 1 <= int(m[1]) <= 365:
                raise ValueError('Filing window outside supported interval.')
            atom('filing_days', int(m[1]), c)
        elif _match(REMEDY, clause):
            atom('remedy', 'affected_monthly_fees_future_invoice', c)
        elif _match(r'(?:#*\s*)?(?:(?:Monthly )?Availability|Service Level) (?:Agreement|Schedule|Commitment)|'
                    r'Synthetic public (?:test )?(?:contract|agreement)', clause):
            c['field'] = 'heading'
        else:
            raise ValueError(f'Unsupported source language at clause {c["id"]}.')
    if document.text[cursor:].strip() or seen != {'vendor', 'agreement', 'effective', 'period', 'filing_days', 'remedy'}:
        raise ValueError('Document lacks complete, unambiguous source coverage.')
    if not manifest['tiers']:
        raise ValueError('At least one source-cited credit tier is required.')
    manifest['tiers'].sort(key=lambda t: (t['product'], t['plan'], t['below_units']))
    last = {}
    for t in manifest['tiers']:
        key = (t['product'], t['plan'])
        lower, previous_credit = last.get(key, (0, MAX_PERCENT + 1))
        if lower >= t['below_units'] or previous_credit <= t['credit_units']:
            raise ValueError('Overlapping or nonmonotonic credit tiers.')
        last[key] = (t['below_units'], t['credit_units'])
    return manifest


def bind_overlay(manifest, overlay):
    if overlay.agreement != manifest['agreement'] or overlay.currency != 'USD':
        raise ValueError('Unsupported agreement or fee currency.')
    for value in (overlay.agreement, overlay.product, overlay.plan, overlay.account, overlay.fee_line_ref):
        if not _match(NAME, value):
            raise ValueError('Missing or ambiguous overlay binding.')
    if (overlay.product, overlay.plan) not in {(t['product'], t['plan']) for t in manifest['tiers']}:
        raise ValueError('Product or plan has no published tier.')
    first, last = date.fromisoformat(overlay.effective_from), date.fromisoformat(overlay.effective_until)
    if not re.fullmatch(DAY, overlay.effective_from) or not re.fullmatch(DAY, overlay.effective_until) or first > last:
        raise ValueError('Invalid overlay effective interval.')
    if max(manifest['effective'][0], overlay.effective_from) > min(manifest['effective'][1], overlay.effective_until):
        raise ValueError('Overlay has no governing interval in this agreement.')
    if override := overlay.override:
        match = _match(FILING, override.quote.strip().removesuffix('.'))
        if not match or int(match[1]) != override.filing_days or not _match(NAME, override.source_ref):
            raise ValueError('Private filing amendment must cite the matching contract clause.')
    return overlay.model_dump(exclude_none=True)


def candidate_version(manifest, overlay, extraction):
    return fingerprint({'manifest': manifest, 'overlay': overlay, 'extraction': extraction})
