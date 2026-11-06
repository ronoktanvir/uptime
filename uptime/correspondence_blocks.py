"""Source-locked newline blocks. Structural grounding only; never semantic validation."""
from hashlib import sha256
import re
import unicodedata
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from .correspondence_interpretation import Interpretation, Proposition, Segment, Slot, Span, validate_grounding
from .correspondence_types import Strict

def _bound(model, name, kind):
    return next(getattr(m, kind) for m in model.model_fields[name].metadata if hasattr(m, kind))


MAX_BLOCKS = _bound(Interpretation, 'segments', 'max_length')            # 64
MAX_PROPOSITIONS = _bound(Interpretation, 'propositions', 'max_length')  # 12
MAX_BLOCK_CHARS = _bound(Span, 'quote', 'max_length')                    # 3000
MAX_SOURCE_BYTES = _bound(Span, 'end', 'le')                             # 12000


def _same(model, name, annotation=None):
    """Reuse an existing field's type, enum and bounds so they cannot drift."""
    field = model.model_fields[name]
    annotation = annotation or field.annotation
    return Annotated[(annotation, *field.metadata)] if field.metadata else annotation


BlockId = Annotated[str, StringConstraints(pattern=r'^b[0-9]{2}-[0-9a-f]{16}$')]


class QuoteSelector(Strict):
    """Exact quote within one block; occurrence counts overlapping matches from 0."""
    quote: _same(Span, 'quote')
    occurrence: int = Field(ge=0, lt=MAX_BLOCK_CHARS)


class BlockSlot(QuoteSelector):
    name: _same(Slot, 'name')


# Category advice only. It narrows nothing by itself and cannot make unsupported text supported;
# the existing mapper gates and explicit human review still decide every meaning.
ARTIFACT_CATEGORY_GUIDANCE = (
    'artifact_type is the requested evidence category stated by the source wording, or null. '
    'resource_log = Incident or telemetry record (evidence of affected service operations; request/access '
    'logs when the source establishes operational context). '
    'invoice_detail = Itemized billing record (charges, fees or invoice detail). '
    'scope_mapping = Account or resource mapping (records linking account/resource ownership or scope). '
    'Never infer the type from artifact_ref or identifier spelling. Use null for an unstated, ambiguous or '
    'competing category. Negated, quoted or conditional requirements keep their polarity, modality and referent; '
    'do not choose a category solely from a negated mention. Category advice cannot assign a supported positive '
    'meaning to unsupported text.')


class BlockProposition(Strict):
    """Existing Proposition fields without a source; the source is always the whole block."""
    family: _same(Proposition, 'family')
    polarity: _same(Proposition, 'polarity')
    modality: _same(Proposition, 'modality')
    referent: _same(Proposition, 'referent')
    conditions: _same(Proposition, 'conditions', list[QuoteSelector])
    slots: _same(Proposition, 'slots', list[BlockSlot])
    # Description set here directly: _same() reuses type/metadata but not descriptions.
    artifact_type: _same(Proposition, 'artifact_type') = Field(default=None, description=ARTIFACT_CATEGORY_GUIDANCE)
    scope_field: _same(Proposition, 'scope_field') = None
    filing_fields: _same(Proposition, 'filing_fields')


class BlockAnnotation(Strict):
    block_id: BlockId
    role: _same(Segment, 'role')
    propositions: list[BlockProposition] = Field(max_length=MAX_PROPOSITIONS)

    @model_validator(mode='after')
    def _role_counts(self):
        if (self.role == 'courtesy') != (not self.propositions):
            raise ValueError('Courtesy blocks have no propositions; every other block needs at least one.')
        return self


class BlockInterpretation(Strict):
    blocks: list[BlockAnnotation] = Field(min_length=1, max_length=MAX_BLOCKS)


def _located(text):
    """(id, text, start_byte, end_byte) per block, split only after LF; bytes preserved."""
    if not isinstance(text, str) or not text:
        raise ValueError('Source blocks require nonempty text.')
    if len(text.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValueError('Source text exceeds the UTF-8 byte cap.')
    pieces = [line + '\n' for line in text.split('\n')]
    pieces[-1] = pieces[-1][:-1]
    if not pieces[-1]:
        pieces.pop()
    if len(pieces) > MAX_BLOCKS or any(len(p) > MAX_BLOCK_CHARS for p in pieces) or ''.join(pieces) != text:
        raise ValueError('Source text exceeds the block count or block size cap.')
    located, cursor = [], 0
    for index, piece in enumerate(pieces):
        raw = piece.encode('utf-8')
        located.append((f'b{index:02d}-{sha256(raw).hexdigest()[:16]}', piece, cursor, cursor + len(raw)))
        cursor += len(raw)
    return located


def source_blocks(text):
    """Public block view: ids and exact text only. Offsets stay server-side."""
    return [dict(id=block_id, text=piece) for block_id, piece, _, _ in _located(text)]


def _word(char):
    return char.isalnum() or unicodedata.category(char).startswith('M')


def _cuts_token(block, first, last):
    if first > 0 and _word(block[first - 1]) and _word(block[first]):
        return True
    if last < len(block) and _word(block[last]) and _word(block[last - 1]):
        return True
    # $1 of $1,000 / USD 17 of USD 17.20, and 000 of 1,000 from the left.
    return bool(re.match(r'[0-9][.,][0-9]', block[last - 1:last + 2]) or
                first >= 2 and re.match(r'[0-9][.,][0-9]', block[first - 2:first + 1]))


def _span(block, offset, selector, slot):
    quote, starts, i = selector.quote, [], block.find(selector.quote)
    while i != -1 and len(starts) <= selector.occurrence:
        starts.append(i)
        i = block.find(quote, i + 1)
    if len(starts) <= selector.occurrence:
        raise ValueError('A selector quote/occurrence does not exist in its source block.')
    first = starts[selector.occurrence]
    if slot and _cuts_token(block, first, first + len(quote)):
        raise ValueError('A slot selector truncates a token or amount.')
    start = offset + len(block[:first].encode('utf-8'))
    return dict(start=start, end=start + len(quote.encode('utf-8')), quote=quote)


def _check_ids(expected, got):
    if len(got) != len(set(got)):
        raise ValueError('A source block is annotated more than once.')
    if set(got) - set(expected):
        raise ValueError('An annotation names an unknown source block.')
    if set(expected) - set(got):
        raise ValueError('A source block is missing its annotation.')
    if got != expected:
        raise ValueError('Block annotations must follow the original order.')


_USD_LITERAL = re.compile(r'(?:\bUSD[ \t]*|\$[ \t]*)[0-9]+(?:[.,][0-9]+)*', re.I)
_PERIOD_LITERAL = re.compile(
    r'\b20[0-9]{2}-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12][0-9]|3[01]))?\b|'
    r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)'
    r'[ \t]+20[0-9]{2}\b', re.I)


def _conserve_literals(interpretation):
    """A potentially supported mapping cannot discard recognized USD/date literals.

    This is a narrow loss check, not a semantic classifier. Already unsupported,
    plural, negative, conditional or other-claim meanings remain unknown under
    the existing proposal gate and need not assign financial roles to literals.
    """
    if len(interpretation.propositions) != 1 or any(s.role == 'unsupported' for s in interpretation.segments):
        return
    p = interpretation.propositions[0]
    if (p.family == 'unsupported' or p.polarity != 'positive' or p.modality != 'asserted'
            or p.referent != 'current_claim' or p.conditions):
        return
    for pattern, names in ((_USD_LITERAL, {'award', 'claimed', 'remainder'}), (_PERIOD_LITERAL, {'period'})):
        assigned = {(s.source.start, s.source.end) for s in p.slots if s.name in names}
        for match in pattern.finditer(p.source.quote):
            start = p.source.start + len(p.source.quote[:match.start()].encode('utf-8'))
            end = start + len(match.group().encode('utf-8'))
            if (start, end) not in assigned:
                raise ValueError('A potentially supported mapping leaves a monetary or date literal unassigned.')


def hydrate_blocks(text, annotation):
    """Convert block selectors to the existing byte-span Interpretation, then reuse its grounding check."""
    located = _located(text)
    if not isinstance(annotation, BlockInterpretation):
        annotation = BlockInterpretation.model_validate(annotation)
    _check_ids([b[0] for b in located], [a.block_id for a in annotation.blocks])
    segments, propositions = [], []
    for (_, block, start, end), item in zip(located, annotation.blocks):
        source = dict(start=start, end=end, quote=block)
        segments.append(dict(source=source, role=item.role))
        for p in item.propositions:
            body = p.model_dump(exclude={'conditions', 'slots'})
            body.update(source=dict(source), conditions=[_span(block, start, c, False) for c in p.conditions],
                        slots=[dict(name=s.name, source=_span(block, start, s, True)) for s in p.slots])
            propositions.append(body)
    interpretation = Interpretation.model_validate(dict(propositions=propositions, segments=segments))
    validate_grounding(text, interpretation)
    _conserve_literals(interpretation)
    return interpretation
