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
        if not any(segment.source.start <= p.source.start and p.source.end <= segment.source.end for p in interpretation.propositions):
            raise ValueError('Every substantive or unsupported segment needs a proposition.')
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


def proposal_for_review(context, interpretation):
    """A reviewed semantic mapping is still an allegation for deterministic checking."""
    validate_grounding(context['text'], interpretation)
    if (len(interpretation.propositions) != 1 or any(s.role == 'unsupported' for s in interpretation.segments)
            or any(unicodedata.category(c) == 'Cf' for c in context['text'])):
        return Proposal('unknown')
    p = interpretation.propositions[0]
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
