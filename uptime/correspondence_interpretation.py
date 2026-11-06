"""Untrusted, byte-grounded meanings. No evidence, effect, or financial authority."""
from decimal import Decimal
from hashlib import sha256
import re
import unicodedata
from typing import Literal

from pydantic import Field

from .contracts import fingerprint
from .correspondence_reason import Proposal
from .correspondence_types import Digest, Strict

Family = Literal['availability', 'time_bar', 'artifact', 'component', 'maintenance', 'downtime', 'scope_error', 'filing_fields', 'award', 'unsupported']


class Span(Strict):
    start: int = Field(ge=0, le=12000)
    end: int = Field(gt=0, le=12000)
    quote: str = Field(min_length=1, max_length=3000)


class Segment(Strict):
    source: Span
    role: Literal['substantive', 'courtesy', 'unsupported']


class Slot(Strict):
    name: Literal['period', 'award', 'remainder', 'claimed', 'artifact_ref', 'scope_ref', 'downtime']
    source: Span


class Proposition(Strict):
    family: Family
    source: Span
    polarity: Literal['positive', 'negative', 'uncertain']
    modality: Literal['asserted', 'quoted', 'conditional', 'future', 'offered', 'uncertain']
    referent: Literal['current_claim', 'other_claim', 'ambiguous']
    conditions: list[Span] = Field(max_length=12)
    slots: list[Slot] = Field(max_length=12)
    artifact_type: Literal['resource_log', 'invoice_detail', 'scope_mapping'] | None = None
    scope_field: Literal['account', 'component', 'invoice'] | None = None
    filing_fields: list[str] = Field(max_length=32)


class Interpretation(Strict):
    propositions: list[Proposition] = Field(min_length=1, max_length=12)
    segments: list[Segment] = Field(min_length=1, max_length=64)


class Entry(Strict):
    context_digest: Digest
    interpretation: Interpretation


class CandidateRequest(Entry):
    origin: Literal['manual'] = 'manual'


class ModelRequest(Strict):
    context_digest: Digest


class Resolution(Strict):
    proposition: int = Field(ge=0, le=11)
    verdict: Literal['accept', 'correct', 'reject']
    explanation: str = Field(min_length=12, max_length=1000)


class Review(Entry):
    candidate_id: Digest | None = None
    resolutions: list[Resolution] = Field(min_length=1, max_length=12)
    residuals_reviewed: bool
    complete_meaning_reviewed: bool


class Prepare(Strict):
    review_id: Digest
    preview_digest: Digest


_COURTESY = re.compile(r'(?:\s|[.!;,])*?(?:thank you|thanks|regards|best regards|sincerely)?(?:\s|[.!;,])*', re.I | re.ASCII)
_MONEY = re.compile(r'(?:USD[ ]*|\$[ ]*)(0|[1-9][0-9]{0,11})(?:\.([0-9]{1,2}))?', re.I | re.ASCII)
_MONTHS = {name: i for i, name in enumerate(('january','february','march','april','may','june','july','august','september','october','november','december'),1)}


def source_bytes(text, span):
    raw = text.encode('utf-8')
    if span.start >= span.end or raw[span.start:span.end] != span.quote.encode('utf-8'):
        raise ValueError('A source span must match the exact original UTF-8 bytes.')
    return span.quote


def validate_grounding(text, interpretation):
    """Check a complete byte partition and pointers, never semantic truth."""
    cursor = 0
    substantive = []
    for segment in interpretation.segments:
        source_bytes(text, segment.source)
        if segment.source.start != cursor:
            raise ValueError('Source segments must partition the entire original text exactly once.')
        cursor = segment.source.end
        if segment.role == 'courtesy' and not _COURTESY.fullmatch(segment.source.quote):
            raise ValueError('Unrecognized residual text cannot be classified as courtesy.')
        if segment.role != 'courtesy':
            substantive.append(segment)
    if cursor != len(text.encode('utf-8')):
        raise ValueError('The interpretation omits original text.')
    for proposition in interpretation.propositions:
        source_bytes(text, proposition.source)
        if not any(s.source.start <= proposition.source.start and proposition.source.end <= s.source.end for s in substantive):
            raise ValueError('A proposition must belong to a substantive source segment.')
        names = [slot.name for slot in proposition.slots]
        if len(names) != len(set(names)):
            raise ValueError('Repeated semantic slot roles are ambiguous.')
        for span in proposition.conditions + [slot.source for slot in proposition.slots]:
            source_bytes(text, span)
            if not proposition.source.start <= span.start < span.end <= proposition.source.end:
                raise ValueError('A semantic slot or condition is outside its proposition.')
    for segment in substantive:
        covered=segment.source.start
        ranges=sorted((p.source.start,p.source.end) for p in interpretation.propositions
                      if segment.source.start <= p.source.start and p.source.end <= segment.source.end)
        for start,end in ranges:
            if start>covered:
                raise ValueError('A substantive source segment contains unannotated bytes.')
            covered=max(covered,end)
        if covered != segment.source.end:
            raise ValueError('Every substantive or unsupported byte needs a proposition.')
    return interpretation


def visible_source(text):
    """Display cues do not replace or normalize the signed source bytes."""
    return ''.join(f'⟦U+{ord(c):04X} {unicodedata.name(c, "CONTROL")}⟧' if unicodedata.category(c) in {'Cf', 'Cc'} and c not in '\n\t' else c for c in text)


def _amount(raw):
    match = _MONEY.fullmatch(raw)
    if not match:
        raise ValueError('Money requires one literal, exact USD amount.')
    return Decimal(match[1] + '.' + (match[2] or '00'))


def _period(raw):
    if re.fullmatch(r'20[0-9]{2}-(?:0[1-9]|1[0-2])', raw):
        return raw
    match = re.fullmatch(r'([A-Za-z]+) (20[0-9]{2})', raw)
    if match and match[1].lower() in _MONTHS:
        return f'{match[2]}-{_MONTHS[match[1].lower()]:02d}'
    raise ValueError('An explicit period must identify one exact month.')


# --- Decision 78: one narrow reviewed denial bundle -------------------------------------
# Exactly two propositions: one positive primary (availability/time_bar/maintenance) and one
# negative, slot-free award statement ("no credit"). The denial is retained for display only;
# it never carries award authority. The guard below is a conservative loss check over the
# complete source, not a semantic proof; mandatory human review remains.
BUNDLE_PRIMARY_FAMILIES = frozenset({'availability', 'time_bar', 'maintenance'})

_CURRENCY_CODE = re.compile(r'\b(?:USD|US\$|EUR|GBP|JPY|CAD|AUD|NZD|CHF|CNY|RMB|HKD|SGD|INR|MXN|BRL|SEK|NOK|DKK|ZAR|KRW|PLN|ILS|AED)\b', re.I)
_MONEY_WORD = re.compile(r'\b(?:dollars?|cents?|euros?|pounds?|sterling|pence|penny|pennies|yen|yuan|renminbi|rupees?|francs?|pesos?'
                         r'|kron(?:a|e|or|er)|rands?|bucks?|quid|money|monetary|cash|refund\w*|reimburs\w*)\b', re.I)
_CREDIT_QUALIFIER = re.compile(r'\b(?:partial|goodwill|good[- ]will|courtesy|further|remaining|additional|pro[- ]?rated|pro[- ]rata)\b'
                               r'(?:[ \t]+[\w-]+){0,2}?[ \t]+(?:credits?|refunds?|compensation|awards?|amounts?|balance)\b'
                               r'|\b(?:goodwill|good[- ]will|courtesy|gesture)\b', re.I)
_CONDITION_CUE = re.compile(r'\b(?:unless|if|until|till|pending|provided|providing|subject[ \t]+to|once|upon|except\w*)\b', re.I)
_DURATION_UNIT = r'(?:milliseconds?|seconds?|minutes?|hours?|days?|weeks?|fortnights?|months?|years?)'
_DURATION_QUAL = r'(?:(?:business|calendar|working|full|consecutive|clock)[ \t]+)?'
_DURATION_WORD = (r'(?:an?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen'
                  r'|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|several|few|half)')
_DURATION = re.compile(
    rf'[0-9]+(?:[.,][0-9]+)*[ \t]*-?[ \t]*{_DURATION_QUAL}(?:{_DURATION_UNIT}|ms|secs?|mins?|hrs?|wks?|yrs?|h|m|s|d)\b'
    rf'|\b{_DURATION_WORD}(?:[ \t]+|-){_DURATION_QUAL}{_DURATION_UNIT}\b'
    r'|\bP(?:T?[0-9]+[YMWDHS])+\b', re.I)
_PERCENT = re.compile(r'[0-9]+(?:[.,][0-9]+)*[ \t]*(?:[%％‰]|percent(?:age)?s?\b|per[ \t]?cent\b|pct\b)'
                      r'|[%％‰]|\b(?:percent(?:age)?s?|per[ \t]cent|pct)\b', re.I)
_PERCENT_TIED = re.compile(r'\b(?:credit\w*|award\w*|refund\w*|rebate\w*|discount\w*|fees?|charges?|invoice\w*|bill\w*|payment\w*'
                           r'|compensat\w*|courtesy|partial\w*|goodwill|reimburs\w*)\b', re.I)
_PERFORMANCE_PERCENT = re.compile(r'\b(?:availability|uptime|target|threshold|service[ \t]+levels?)\b', re.I)
_DECIMAL_LITERAL = re.compile(r'\b[0-9]+[.,][0-9]+\b')
_ISSUANCE_VERB = re.compile(r'\b(?:issued|credited|paid|disbursed|remitted|refunded|reimbursed|posted)\b', re.I)
_CLAUSE_BREAK = re.compile(r'[;,!?:\n]|\.(?=\s|$)')
_MONTH_NAME = r'(?:january|february|march|april|may|june|july|august|september|october|november|december)'
_MONTH_ANY = rf'(?:{_MONTH_NAME}|(?:jan|feb|mar|apr|jun|jul|aug|sept?|oct|nov|dec)\.?)'
_DAY = r'(?:[0-9]{1,2}(?:st|nd|rd|th)?)'
# Ordered most specific first; finditer consumes the leftmost specific form before bare forms.
_DATE = re.compile(
    rf'\b(?:{_DAY}[ \t]+(?:of[ \t]+)?{_MONTH_ANY}(?:,?[ \t]+[0-9]{{4}})?'
    rf'|{_MONTH_ANY}[ \t]+{_DAY}(?:,?[ \t]+[0-9]{{4}})?'
    rf'|{_MONTH_ANY},?[ \t]+[0-9]{{4}}'
    r'|(?:19|20)[0-9]{2}-[0-9]{1,2}(?:-[0-9]{1,2})?'
    r'|[0-9]{1,2}[/.][0-9]{1,2}[/.][0-9]{2,4}'
    r'|[0-9]{1,2}/[0-9]{4}'
    rf'|{_MONTH_NAME}'
    r'|(?:19|20)[0-9]{2}'
    r')\b', re.I)


def _byte_span(text, match):
    start = len(text[:match.start()].encode('utf-8'))
    return start, start + len(match.group().encode('utf-8'))


def _clause(text, start, end):
    left = 0
    for brk in _CLAUSE_BREAK.finditer(text):
        if brk.end() <= start:
            left = brk.end()
        elif brk.start() >= end:
            return text[left:brk.start()]
    return text[left:]


def _unconditional_current(p, polarity):
    return p.polarity == polarity and p.modality == 'asserted' and p.referent == 'current_claim' and not p.conditions


def _bundle_primary(p):
    return (p.family in BUNDLE_PRIMARY_FAMILIES and _unconditional_current(p, 'positive')
            and {s.name for s in p.slots} <= {'period'} and not p.filing_fields
            and p.artifact_type is None and p.scope_field is None)


def _bundle_denial(p):
    return (p.family == 'award' and _unconditional_current(p, 'negative') and not p.slots and not p.filing_fields
            and p.artifact_type is None and p.scope_field is None)


def bundle_loses_meaning(text, primary):
    """True when the complete source holds content this narrow bundle could silently drop."""
    if any(unicodedata.category(c) == 'Sc' for c in text):
        return True
    if any(p.search(text) for p in (_CURRENCY_CODE, _MONEY_WORD, _CREDIT_QUALIFIER, _CONDITION_CUE, _DURATION)):
        return True
    # An issued value with no currency token still exceeds this slot-free denial's meaning.
    # This conservative clause check refuses the bundle; it never infers money or a currency.
    for match in _DECIMAL_LITERAL.finditer(text):
        if _ISSUANCE_VERB.search(_clause(text, match.start(), match.end())):
            return True
    for match in _PERCENT.finditer(text):
        start, end = _byte_span(text, match)
        # Percentages may only be availability measurements/targets inside the primary itself.
        if (primary.family != 'availability' or not primary.source.start <= start < end <= primary.source.end
                or _PERCENT_TIED.search(_clause(text, match.start(), match.end()))
                or not _PERFORMANCE_PERCENT.search(_clause(text, match.start(), match.end()))):
            return True
    periods = {(s.source.start, s.source.end) for s in primary.slots if s.name == 'period'}
    if {_byte_span(text, m) for m in _DATE.finditer(text)} != periods:
        return True
    return False


def primary_proposition_index(context, interpretation):
    """Deterministic index of the proposition that may drive the existing engine, else None.

    One proposition: index 0 (the existing single gate still decides). Two propositions: only
    the narrow reviewed denial bundle, in either order. Every other plural shape is None.
    """
    text = context['text']
    validate_grounding(text, interpretation)
    props = interpretation.propositions
    if len(props) == 1:
        return 0
    if (len(props) != 2 or any(s.role == 'unsupported' for s in interpretation.segments)
            or any(unicodedata.category(c) == 'Cf' for c in text)):
        return None
    primary = [i for i, p in enumerate(props) if _bundle_primary(p)]
    denial = [i for i, p in enumerate(props) if _bundle_denial(p)]
    if len(primary) != 1 or len(denial) != 1:
        return None
    p = props[primary[0]]
    for slot in p.slots:
        try:
            _period(slot.source.quote)
        except ValueError:
            return None
    if bundle_loses_meaning(text, p):
        return None
    return primary[0]


def proposal_for_review(context, interpretation):
    """A reviewed semantic mapping is still an allegation for deterministic checking."""
    validate_grounding(context['text'], interpretation)
    if (any(s.role == 'unsupported' for s in interpretation.segments)
            or any(unicodedata.category(c) == 'Cf' for c in context['text'])):
        return Proposal('unknown')
    index = primary_proposition_index(context, interpretation)
    if index is None:
        return Proposal('unknown')
    p = interpretation.propositions[index]
    if p.family == 'unsupported' or p.polarity != 'positive' or p.modality != 'asserted' or p.referent != 'current_claim' or p.conditions:
        return Proposal('unknown')
    slots = {slot.name:slot.source.quote for slot in p.slots}
    allowed = {'availability':{'period'}, 'time_bar':{'period'}, 'maintenance':{'period'}, 'component':{'period'},
               'artifact':{'period','artifact_ref'}, 'scope_error':{'period','scope_ref'}, 'downtime':{'period','downtime'},
               'filing_fields':{'period'}, 'award':{'period','award','claimed','remainder'}}[p.family]
    if set(slots) - allowed:
        return Proposal('unknown')
    if 'period' in slots and _period(slots['period']) != context['scope']['month']:
        return Proposal('unknown')
    if (p.artifact_type is not None and p.family != 'artifact' or p.scope_field is not None and p.family != 'scope_error'
            or p.filing_fields and p.family != 'filing_fields'):
        return Proposal('unknown')
    values = dict(reason=p.family, span=(p.source.start,p.source.end))
    if p.family == 'award':
        if context['requested'] is None or 'award' not in slots:
            return Proposal('unknown')
        award, claimed = _amount(slots['award']), Decimal(context['requested'])
        if (award <= 0 or award > claimed or 'claimed' in slots and _amount(slots['claimed']) != claimed
                or 'remainder' in slots and award + _amount(slots['remainder']) != claimed):
            return Proposal('unknown')
        values['amount'] = format(award,'.2f')
    if p.family == 'artifact':
        if not p.artifact_type and 'artifact_ref' not in slots:
            return Proposal('unknown')
        values.update(artifact_type=p.artifact_type, reference=slots.get('artifact_ref'))
    if p.family == 'scope_error':
        if not p.scope_field or 'scope_ref' not in slots:
            return Proposal('unknown')
        values.update(scope_field=p.scope_field, reference=slots['scope_ref'])
    if values.get('reference') and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,95}',values['reference']):
        return Proposal('unknown')
    if p.family == 'downtime':
        match = re.fullmatch(r'([0-9]{1,8}(?:\.[0-9]{1,6})?) (hours?|minutes?|seconds?)', slots.get('downtime',''), re.I | re.ASCII)
        if not match:
            return Proposal('unknown')
        values['downtime_us'] = int(Decimal(match[1]) * {'hour':3600000000,'minute':60000000,'second':1000000}[match[2].lower().rstrip('s')])
    if p.family == 'filing_fields' and (not p.filing_fields or len(p.filing_fields) != len(set(p.filing_fields)) or not set(p.filing_fields) <= set(context['filing_fields'])):
        return Proposal('unknown')
    return Proposal(**values)


def text_digest(text):
    return sha256(text.encode('utf-8')).hexdigest()
