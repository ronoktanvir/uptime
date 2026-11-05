"""Source-grounded extraction for the monthly availability/future invoice credit family.

The bounded recognizer consumes every nonblank clause. A proposed model span can
join wrapped sentences, but cannot introduce values, code or unsupported terms.
"""
from datetime import date
from hashlib import sha256
import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .contracts import fingerprint

REVISION = 'monthly-availability/1'
PERCENT_SCALE = 1_000_000  # integer units per percent
MAX_PERCENT = 100 * PERCENT_SCALE
NUMBER = r'[0-9]{1,3}(?:\.[0-9]{1,6})?'
NAME = r"[A-Za-z0-9][A-Za-z0-9 &(),_'./+\-]{0,99}?"
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


class BillingPeriod(Strict):
    kind: str
    source_ref: str
    quote: str


class GoverningTerms(Strict):
    verified: bool
    agreement: str
    source_sha256: str
    effective_from: str
    source_ref: str
    evidence_sha256: str
    unamended_terms: list[str]


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
    resource_id: str | None = None
    billing_period: BillingPeriod | None = None
    governing_terms: GoverningTerms | None = None
    public_product: str | None = None
    public_plan: str | None = None
    public_agreement: str | None = None
    resource_label: str | None = None
    symptom_aliases: dict[str, str] | None = None
    cause_aliases: dict[str, str] | None = None


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
                         rf'({DAY})(?: (?:through|to|until and including) ({DAY}))?', clause):
            date.fromisoformat(m[1])
            if m[2] is not None and date.fromisoformat(m[1]) > date.fromisoformat(m[2]):
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
    resource = manifest['family'] == 'resource-month/1'
    scoped = (overlay.public_agreement or overlay.agreement, overlay.public_product or overlay.product,
              overlay.public_plan or overlay.plan)
    if not resource and any(getattr(overlay,k) is not None for k in
                            ('resource_id','billing_period','governing_terms','public_product','public_plan','public_agreement','resource_label','symptom_aliases','cause_aliases')):
        raise ValueError('Resource mappings require a resource-month contract.')
    if overlay.currency != 'USD' or manifest['agreement'] is not None and scoped[0] != manifest['agreement']:
        raise ValueError('Unsupported agreement or fee currency.')
    for value in (overlay.agreement, overlay.product, overlay.plan, overlay.account, overlay.fee_line_ref):
        if not _match(NAME, value):
            raise ValueError('Missing or ambiguous overlay binding.')
    if resource:
        from .vendor_resource_terms import norm
        if 'precedence' in manifest or overlay.governing_terms is not None:
            attestation=overlay.governing_terms
            required={'scope','measurement','exclusions','tiers','fee_basis','rounding','filing','remedy'}
            if (attestation is None or not attestation.verified or attestation.agreement!=overlay.agreement
                    or attestation.source_sha256!=manifest['document']['sha256'] or attestation.effective_from!=manifest['effective'][0]
                    or not _match(NAME,attestation.source_ref) or not re.fullmatch('[a-f0-9]{64}',attestation.evidence_sha256)
                    or set(attestation.unamended_terms)!=required or len(attestation.unamended_terms)!=len(required)
                    or overlay.override is not None):
                raise ValueError('Referenced governing terms require verified local source, effective date and unamended economics.')

        if manifest['period'] != 'resource_utc_calendar_month' or overlay.billing_period is not None:
            period=overlay.billing_period
            if (period is None or period.kind!='utc_calendar_month' or not _match(NAME,period.source_ref)
                    or 'utc' not in period.quote.casefold() or 'calendar month' not in period.quote.casefold()
                    or re.search(r'\b(?:not|unless|rolling|except|local time|pending|unconfirmed)\b',period.quote,re.I)):
                raise ValueError('Public clock requires cited private UTC calendar-month billing coverage.')
        if not overlay.resource_id or not _match(NAME, overlay.resource_id):
            raise ValueError('Resource contract requires a tenant/account resource identifier.')
        for aliases, labels in [(overlay.symptom_aliases, manifest['symptoms']),
                                (overlay.cause_aliases, manifest['provider_causes'] + manifest['exclusions'])]:
            if aliases and any(not norm(key) or value not in labels for key,value in aliases.items()):
                raise ValueError('Private observation aliases must map to cited service definitions.')
        if overlay.override and manifest['filing']['kind'] != 'calendar_days':
            raise ValueError('A calendar-day override cannot implicitly replace billing cycles.')
    if (scoped[1], scoped[2]) not in {(t['product'],t['plan']) for t in manifest['tiers']} and not (
            resource and manifest['scope']=={'product':scoped[1], 'plan':None}):
        raise ValueError('Product or plan has no published tier.')
    first, last = date.fromisoformat(overlay.effective_from), date.fromisoformat(overlay.effective_until)
    if not re.fullmatch(DAY, overlay.effective_from) or not re.fullmatch(DAY, overlay.effective_until) or first > last:
        raise ValueError('Invalid overlay effective interval.')
    source_until = manifest['effective'][1] or overlay.effective_until
    if max(manifest['effective'][0], overlay.effective_from) > min(source_until, overlay.effective_until):
        raise ValueError('Overlay has no governing interval in this agreement.')
    if override := overlay.override:
        match = _match(FILING, override.quote.strip().removesuffix('.'))
        if not match or int(match[1]) != override.filing_days or not _match(NAME, override.source_ref):
            raise ValueError('Private filing amendment must cite the matching contract clause.')
    return overlay.model_dump(exclude_none=True)


# A reviewed artifact is coupled to the actual source installed in this process.
# A comment-only change can conservatively require fresh review. Historical receipts stay readable.
_COMMON_SEMANTIC_FILES = ('contracts.py','vendor_terms.py','vendor_eval.py','vendor_model.py','vendor_registry.py')
_PROFILE_FILES = {REVISION: _COMMON_SEMANTIC_FILES,
                  'resource-month/1': _COMMON_SEMANTIC_FILES + ('vendor_resource_terms.py','vendor_resource_eval.py','twilio.py')}
SEMANTICS_REVISIONS = {
    family: fingerprint({'protocol':'reviewed-semantics/1','family':family,'files':{
        name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in files}})
    for family,files in _PROFILE_FILES.items()
}


def semantics_revision(manifest):
    revision=SEMANTICS_REVISIONS.get(manifest['family'])
    if not revision:
        raise ValueError('Unsupported evaluator family.')
    return revision


def candidate_version(manifest, overlay, extraction):
    return fingerprint({'manifest': manifest, 'overlay': overlay, 'extraction': extraction,
                        'semantics_revision':semantics_revision(manifest)})


def compile_propositions(document, clauses):
    """Ground a model interpretation without claiming automated semantic equivalence.

    This path accepts variable prose order. Source coverage, values, units, scopes,
    comparison direction and unexpressible material qualifiers are checked locally.
    Promotion requires a separate human interpretation acceptance.
    """
    _validate_document(document)
    spans = _clauses(document.text, [c['quote'] for c in clauses])
    manifest = {'family': REVISION, 'document': {'name': document.name, 'uri': document.uri,
                'classification': document.classification, 'sha256': sha256(document.text.encode()).hexdigest()},
                'tiers': [], 'citations': []}
    seen, scope, header = set(), None, None
    header_comparator = False
    qualifiers = r'\b(?:unless|except|exclud(?:e|es|ed|ing)|provided|subject to|only if|conditional|cap(?:ped)?|maximum|' \
                 r'discretion|refund|business days|rolling|not|greater than|above|at least|up to|at most|may|can|maintenance)\b|<=|≤'
    for index, (row, (start, end, quote)) in enumerate(zip(clauses, spans, strict=True), 1):
        field, value = row['field'], row['value']
        text = ' '.join(quote.split())
        lower = text.casefold()
        citation = {'id': index, 'start': start, 'end': end, 'quote': quote, 'field': field}
        manifest['citations'].append(citation)
        if not isinstance(field, str) or field == 'unsupported':
            raise ValueError(f'Model identified unsupported material at clause {index}.')
        if re.search(qualifiers, lower):
            raise ValueError(f'Unsupported material qualification at clause {index}.')
        if field in {'vendor', 'agreement'}:
            if (not isinstance(value, str) or not _match(NAME, value) or value.casefold() not in lower
                    or not re.search(r'\b(?:vendor|provider|agreement|contract)\b', lower)):
                raise ValueError('Ungrounded vendor or agreement identifier.')
        elif field == 'effective':
            if (not isinstance(value, list) or len(value) != 2 or not isinstance(value[0], str)
                    or value[1] is not None and not isinstance(value[1], str)
                    or re.findall(DAY, text) != [v for v in value if v is not None]
                    or not re.search(r'\b(?:effective|valid)\b', lower)):
                raise ValueError('Effective interval must match explicit source dates.')
            date.fromisoformat(value[0])
            if value[1] is not None and date.fromisoformat(value[0]) > date.fromisoformat(value[1]):
                raise ValueError('Reversed source effective interval.')
        elif field == 'period':
            if (value != 'utc_calendar_month' or 'utc' not in lower or 'calendar month' not in lower
                    or not re.search(r'\b(?:availability|uptime|measure|measured|measurement|period|calculated)\b', lower)
                    or re.search(r'[0-9%]|\b(?:prorat(?:e|ed|ion)|hours?|days?|subtract|adjust)\b', lower)):
                raise ValueError('Unsupported measurement denominator or timezone.')
        elif field == 'filing_days':
            if (type(value) is not int or not 1 <= value <= 365
                    or not re.search(rf'\b{value}\s+calendar days\b', lower)
                    or not re.search(r'\b(?:claims?|requests?)\b', lower)
                    or not re.search(r'\b(?:received|submitted|filed|due)\b', lower)
                    or not re.search(r'(?:after|following) (?:month end|(?:the )?end of (?:the |each )?(?:affected |applicable )?(?:calendar )?month)', lower)):
                raise ValueError('Unsupported filing origin, interval or units.')
            numbers = re.findall(r'\b[0-9]+\b', text)
            if numbers != [str(value)]:
                raise ValueError('Ambiguous filing number.')
        elif field == 'remedy':
            if (value != 'affected_monthly_fees_future_invoice' or 'credit' not in lower or 'affected' not in lower
                    or not re.search(r'monthly (?:service |product )?fees?', lower)
                    or not re.search(r'(?:future|next) invoice', lower)
                    or re.search(r'[0-9%]|\b(?:tax|expire|expire[sd]|annually|annual|cash|charged)\b', lower)):
                raise ValueError('Unsupported remedy or credit fee basis.')
        elif field == 'scope':
            if (not isinstance(value, dict) or set(value) != {'product', 'plan'}
                    or not all(isinstance(v, str) and _match(NAME, v) and v.casefold() in lower for v in value.values())
                    or not re.search(r'\b(?:applies|covers|scope|product|plan)\b', lower)
                    or '%' in lower or re.search(r'\b(?:must|required|when|if)\b', lower)):
                raise ValueError('Ambiguous scope clause.')
            scope = value | {'citation': index}
            header = None
            continue
        elif field == 'tier':
            if not isinstance(value, dict) or set(value) != {'product', 'plan', 'below', 'credit'}:
                raise ValueError('Malformed model tier proposition.')
            if not all(isinstance(v, str) for v in value.values()):
                raise ValueError('Model tier values must be source strings.')
            below, rate = percent_units(value['below']), percent_units(value['credit'])
            amounts = [percent_units(n) for n in re.findall(rf'({NUMBER})\s*%', text)]
            if sorted(amounts) != sorted([below, rate]):
                raise ValueError('Tier percentages do not match the cited source.')
            own_scope = all(_match(NAME, value[k]) and value[k].casefold() in lower for k in ('product', 'plan'))
            if not own_scope and not (scope and all(value[k] == scope[k] for k in ('product', 'plan'))):
                raise ValueError('Tier lacks an explicit product/plan source scope.')
            before = re.escape(value['below'])
            explicit_operator = re.search(rf'(?:below|less than|under|<)\s*{before}\s*%', lower)
            if not explicit_operator and not (header and header_comparator and '|' in text):
                raise ValueError('Unsupported or ungrounded tier comparison operator.')
            if not header and not re.search(rf'{re.escape(value["credit"])}\s*%\s*(?:service )?credit|credit (?:of|is)\s*{re.escape(value["credit"])}\s*%', lower):
                raise ValueError('Ungrounded credit rate.')
            if re.search(r'\b(?:days?|hours?|minutes?|if|when also|requires?|must|minimum|at most)\b', lower):
                raise ValueError('Unsupported tier condition.')
            term = {'product': value['product'], 'plan': value['plan'], 'below_units': below,
                    'credit_units': rate, 'citation': index}
            if not own_scope:
                term['scope_citation'] = scope['citation']
            if header:
                term['header_citation'] = header
            manifest['tiers'].append(term)
            continue
        elif field == 'table_header':
            if (value is not None or '|' not in text or not re.search(r'availability|uptime', lower)
                    or 'credit' not in lower
                    or '%' in re.sub(r'\(%\)', '', lower)):
                raise ValueError('Unsupported availability table header.')
            header = index
            header_comparator = bool(re.search(r'below|less than|<', lower))
            continue
        elif field == 'table_separator':
            if value is not None or not re.fullmatch(r'[| :\-]+', text) or not header:
                raise ValueError('Invalid table separator.')
            continue
        elif field == 'heading':
            if (value is not None or len(text) > 160 or len(text.split()) > 14
                    or not re.search(r'availability|service level|synthetic public', lower)
                    or re.search(r'[0-9%]|\b(?:must|shall|may|will|if|credit|fee|claim|day|rate|exclusion|condition)\b', lower)):
                raise ValueError('Unrecognized source material labeled as a heading.')
            continue
        else:
            raise ValueError('Unsupported proposed field.')
        if field in seen:
            raise ValueError('Duplicate or ambiguous proposed field.')
        seen.add(field)
        manifest[field] = value
        header = None
    required = {'vendor', 'agreement', 'effective', 'period', 'filing_days', 'remedy'}
    if seen != required or not manifest['tiers']:
        raise ValueError('Incomplete model propositions.')
    manifest['tiers'].sort(key=lambda t: (t['product'], t['plan'], t['below_units']))
    last = {}
    for tier in manifest['tiers']:
        key = (tier['product'], tier['plan'])
        lower, previous = last.get(key, (0, MAX_PERCENT + 1))
        if lower >= tier['below_units'] or previous <= tier['credit_units']:
            raise ValueError('Overlapping or nonmonotonic proposed credit tiers.')
        last[key] = tier['below_units'], tier['credit_units']
    manifest['interpretation'] = 'model_proposition_human_review_required'
    return manifest
