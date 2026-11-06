"""Decision 71: additive source-locked block adapter.

Structural coverage here is not semantic-accuracy evidence. The eight authored controls
are public development controls with handcrafted annotations, not blind evaluation.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import uptime.correspondence_block_model as block_model
from uptime import storage
from uptime.correspondence_block_model import PublicBlockInterpretationAdapter, serialized_block_request
from uptime.correspondence_blocks import (BlockInterpretation, BlockProposition, _located, hydrate_blocks,
                                          source_blocks)
from uptime.correspondence_interpretation import Interpretation, Proposition, proposal_for_review, validate_grounding
from uptime.correspondence_model import MODEL, PublicInterpretationAdapter, serialized_request

CONTROLS_PATH = Path(__file__).resolve().parents[1] / 'fixtures' / 'correspondence' / 'public-71' / 'controls.json'
FROZEN_SHA256 = '16e994d2876a954a4847cab213488a47b5bd8e70c5a5ceaaffb82c1eb42b682f'


def P(family='time_bar', polarity='positive', modality='asserted', referent='current_claim',
      conditions=(), slots=(), **extra):
    return dict(family=family, polarity=polarity, modality=modality, referent=referent,
                conditions=[dict(quote=q, occurrence=o) for q, o in conditions],
                slots=[dict(name=n, quote=q, occurrence=o) for n, q, o in slots], filing_fields=[], **extra)


def annotate(text, *items):
    ids = [b['id'] for b in source_blocks(text)]
    assert len(ids) == len(items)
    return dict(blocks=[dict(block_id=i, role=role, propositions=list(props)) for i, (role, props) in zip(ids, items)])


def context_for(text, **scope):
    return dict(text=text, scope=dict(month='2028-04', **scope), currency='USD', requested='62.13',
                filing_fields=['invoice_id', 'account_id'])


# Handcrafted human semantic annotations for the frozen controls (one block each).
SEMANTIC = {
    'deadline-paraphrase': lambda t: annotate(t, ('substantive', [P('time_bar')])),
    'invoice-paraphrase': lambda t: annotate(t, ('substantive', [P('artifact', artifact_type='invoice_detail')])),
    'unicode-award': lambda t: annotate(t, ('substantive', [P('award', slots=[('award', 'USD 17.20', 0),
                                                                              ('remainder', 'USD 44.93', 0)])])),
    'negated-deadline': lambda t: annotate(t, ('substantive', [P('time_bar', polarity='negative')])),
    'conditional-credit': lambda t: annotate(t, ('substantive', [P('award', modality='conditional',
                                                                   conditions=[('If the missing invoice is supplied', 0)],
                                                                   slots=[('award', 'USD 17.20', 0)])])),
    'unsupported-mixed': lambda t: annotate(t, ('unsupported', [P('time_bar'), P('unsupported')])),
    'quoted-other': lambda t: annotate(t, ('substantive', [P('award', modality='quoted', referent='other_claim',
                                                             slots=[('award', 'USD 17.20', 0)]),
                                                           P('award', polarity='negative')])),
    'injection': lambda t: annotate(t, ('unsupported', [P('unsupported', polarity='uncertain', referent='ambiguous')])),
}


def controls():
    raw = CONTROLS_PATH.read_bytes()
    canonical = json.dumps(json.loads(raw), ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    # Tamper check: any content change alters both digests.
    assert FROZEN_SHA256 in {sha256(raw).hexdigest(), sha256(canonical).hexdigest()}
    return raw, {case['id']: case for case in json.loads(raw)['cases']}


class Provider:
    def __init__(self, text='', *, profile=None, model=MODEL, result=None):
        self.calls, self.text, self.model, self.result = [], text, model, result
        if profile is not None:
            self.profile = profile

    def __call__(self, request):
        self.calls.append(request)
        if self.result is not None:
            return self.result
        return dict(model=self.model, text=self.text, session='session-1', usage={'output_tokens': 1},
                    cost_usd=0.01, transport={'receipt': 'fake'})


def enabled_adapter(context, provider):
    digest = sha256(serialized_block_request(context, getattr(provider, 'profile', None))).hexdigest()
    return PublicBlockInterpretationAdapter(allowed_requests={digest}, provider=provider, enabled=True), digest


# --- deterministic source blocks -------------------------------------------------

def test_blocks_split_only_at_lf_and_preserve_unicode_crlf_bytes():
    text = 'Crédit\r\nok\n\nfin' + chr(0x2028) + 'x\rend'  # U+2028 and a lone CR are not split points
    located = _located(text)
    assert [b[1] for b in located] == ['Crédit\r\n', 'ok\n', '\n', 'fin' + chr(0x2028) + 'x\rend']
    assert [(b[2], b[3]) for b in located] == [(0, 9), (9, 12), (12, 13), (13, 24)]
    raw = text.encode('utf-8')
    assert all(raw[s:e] == piece.encode('utf-8') for _, piece, s, e in located)
    assert b''.join(p.encode('utf-8') for _, p, _, _ in located) == raw
    assert [set(b) for b in source_blocks(text)] == [{'id', 'text'}] * 4  # no offsets leave the server
    assert [b['text'] for b in source_blocks('a\n')] == ['a\n']
    assert [b['text'] for b in source_blocks('\r\n')] == ['\r\n']


def test_duplicate_text_gets_distinct_deterministic_ids():
    first = source_blocks('Thanks\nThanks\n')
    assert first == source_blocks('Thanks\nThanks\n')
    a, b = (block['id'] for block in first)
    assert a != b and a[:4] == 'b00-' and b[:4] == 'b01-' and a[4:] == b[4:]
    assert source_blocks('Thanks\nThanks!\n')[1]['id'][4:] != b[4:]


def test_strict_count_and_size_caps():
    for bad in ('', None, b'late'):
        with pytest.raises(ValueError):
            source_blocks(bad)
    assert len(source_blocks('x\n' * 64)) == 64
    with pytest.raises(ValueError):
        source_blocks('x\n' * 65)
    assert len(source_blocks('a' * 3000)) == 1
    with pytest.raises(ValueError):
        source_blocks('a' * 3001)
    wide = ('é' * 2999 + '\n') * 2  # 6000 chars, 11998 UTF-8 bytes
    assert len(source_blocks(wide + 'é')) == 3  # exactly 12000 bytes
    with pytest.raises(ValueError):
        source_blocks(wide + 'éa')
    with pytest.raises(ValueError):
        source_blocks('\ud800')  # not encodable source bytes


def test_proposition_bounds_come_from_existing_types():
    for name in ('family', 'polarity', 'modality', 'referent', 'artifact_type', 'scope_field', 'filing_fields'):
        assert BlockProposition.model_fields[name].annotation == Proposition.model_fields[name].annotation
    assert 'source' not in BlockProposition.model_fields
    one = 'We deny this as late.'
    with pytest.raises(ValidationError):  # > 12 in one block
        hydrate_blocks(one, annotate(one, ('substantive', [P()] * 13)))
    many = 'late\n' * 13
    with pytest.raises(ValidationError):  # > 12 overall, enforced by the unchanged Interpretation
        hydrate_blocks(many, annotate(many, *[('substantive', [P()])] * 13))


# --- complete, ordered, unique coverage ----------------------------------------

def test_gaps_duplicates_unknown_and_order_are_rejected():
    text = 'The filing was late.\nThanks\n'
    good = annotate(text, ('substantive', [P()]), ('courtesy', []))
    assert len(hydrate_blocks(text, good).segments) == 2
    a, b = good['blocks']
    with pytest.raises(ValueError, match='missing'):
        hydrate_blocks(text, dict(blocks=[a]))
    with pytest.raises(ValueError, match='more than once'):
        hydrate_blocks(text, dict(blocks=[a, a, b]))
    with pytest.raises(ValueError, match='order'):
        hydrate_blocks(text, dict(blocks=[b, a]))
    for forged in ('b01-' + '0' * 16, a['block_id'][:4] + 'f' * 16):
        with pytest.raises(ValueError, match='unknown'):
            hydrate_blocks(text, dict(blocks=[{**a, 'block_id': forged}, b]))
    other = 'The filing was late!\nThanks\n'  # annotation for different source text cannot be reused
    with pytest.raises(ValueError):
        hydrate_blocks(other, good)


def test_courtesy_cannot_hide_substantive_text_and_role_counts_are_strict():
    hidden = 'The filing was late.\nA settlement also extinguished all rights.\n'
    with pytest.raises(ValueError, match='courtesy'):
        hydrate_blocks(hidden, annotate(hidden, ('substantive', [P()]), ('courtesy', [])))
    padded = 'The filing was late.\nThanks, we also reject the remainder.\n'
    with pytest.raises(ValueError, match='courtesy'):
        hydrate_blocks(padded, annotate(padded, ('substantive', [P()]), ('courtesy', [])))
    text = 'Thanks\nWe deny the claim as late.\n'
    with pytest.raises(ValidationError):
        hydrate_blocks(text, annotate(text, ('courtesy', [P()]), ('substantive', [P()])))
    with pytest.raises(ValidationError):
        hydrate_blocks(text, annotate(text, ('courtesy', []), ('substantive', [])))
    with pytest.raises(ValidationError):
        hydrate_blocks(text, annotate(text, ('courtesy', []), ('unsupported', [])))


# --- selectors ------------------------------------------------------------------

def test_selectors_require_exact_quote_occurrence_within_their_block():
    text = 'If aaa then late.'
    hydrated = hydrate_blocks(text, annotate(text, ('substantive', [P(conditions=[('aa', 1)])])))
    assert hydrated.propositions[0].conditions[0].model_dump() == dict(start=4, end=6, quote='aa')  # overlapping count
    for bad in [('aa', 2), ('absent', 0)]:
        with pytest.raises(ValueError, match='does not exist'):
            hydrate_blocks(text, annotate(text, ('substantive', [P(conditions=[bad])])))
    two = 'If the invoice arrives\nwe deny it as late.'
    with pytest.raises(ValueError, match='does not exist'):  # present in the text, but not in this block
        hydrate_blocks(two, annotate(two, ('substantive', [P()]), ('substantive', [P(conditions=[('If the invoice', 0)])])))
    base = annotate(text, ('substantive', [P(conditions=[('aa', 0)])]))
    for selector in (dict(quote='aa'), dict(quote='aa', occurrence=-1), dict(quote='aa', occurrence=True),
                     dict(quote='', occurrence=0), dict(quote='aa', occurrence=0, start=4)):
        bad = deepcopy(base)
        bad['blocks'][0]['propositions'][0]['conditions'] = [selector]
        with pytest.raises(ValidationError):
            hydrate_blocks(text, bad)


@pytest.mark.parametrize('text,quote', [
    ('We approve a credit of $40 for the current claim.', '$4'),
    ('We approve a credit of $1,000 for the current claim.', '$1'),
    ('We approve USD 17.20 for the current claim.', 'USD 17'),
    ('We approve USD17.20 for the current claim.', 'USD17'),
    ('We approve USD 17.20 for the current claim.', 'USD 17.2'),
    ('We approve USD 117.20 for the current claim.', '17.20'),
    ('We approve $1,000 for the current claim.', '000'),
    ('We approve xUSD 17.20 for the current claim.', 'USD 17.20'),
    ('Cre' + chr(0x301) + 'dit approved.', 'Cre'),  # a combining mark continues the token
])
def test_slot_token_prefix_attacks_are_rejected(text, quote):
    with pytest.raises(ValueError, match='truncates'):
        hydrate_blocks(text, annotate(text, ('substantive', [P('award', slots=[('award', quote, 0)])])))
    # Conditions may legitimately be ordinary substrings.
    hydrate_blocks(text, annotate(text, ('substantive', [P('award', conditions=[(quote, 0)])])))


@pytest.mark.parametrize('text,quote', [('A credit of $40 is approved.', '$40'), ('A credit of $1,000, approved.', '$1,000'),
                                        ('Approved USD 17.20.', 'USD 17.20'), ('Approved (USD17.20)', 'USD17.20')])
def test_whole_slot_tokens_are_accepted(text, quote):
    hydrated = hydrate_blocks(text, annotate(text, ('substantive', [P('award', slots=[('award', quote, 0)])])))
    assert hydrated.propositions[0].slots[0].source.quote == quote


def test_hydration_equals_hand_built_byte_spans():
    _, cases = controls()
    text = cases['unicode-award']['context']['text']
    raw = text.encode('utf-8')

    def span(quote):
        start = raw.index(quote.encode('utf-8'))
        return dict(start=start, end=start + len(quote.encode('utf-8')), quote=quote)
    whole = dict(start=0, end=len(raw), quote=text)
    hand = Interpretation.model_validate(dict(
        segments=[dict(source=whole, role='substantive')],
        propositions=[dict(family='award', source=whole, polarity='positive', modality='asserted', referent='current_claim',
                           conditions=[], slots=[dict(name='award', source=span('USD 17.20')),
                                                 dict(name='remainder', source=span('USD 44.93'))], filing_fields=[])]))
    validate_grounding(text, hand)
    hydrated = hydrate_blocks(text, SEMANTIC['unicode-award'](text))
    assert hydrated.model_dump() == hand.model_dump()
    assert raw.index(b'USD 17.20') == text.index('USD 17.20') + 2  # byte, not character, offsets
    crlf = 'Thanks,\r\nUSD 17.20 is approved for the current claim.\r\n'
    multi = hydrate_blocks(crlf, annotate(crlf, ('courtesy', []), ('substantive', [P('award', slots=[('award', 'USD 17.20', 0)])])))
    assert multi.propositions[0].slots[0].source.start == crlf.encode().index(b'USD 17.20') == 9
    assert multi.segments[1].source.end == len(crlf.encode())


def test_structural_validity_is_not_semantic_validity():
    _, cases = controls()
    context = cases['negated-deadline']['context']
    wrong = annotate(context['text'], ('substantive', [P('time_bar')]))  # human error: drops the negation
    assert proposal_for_review(context, hydrate_blocks(context['text'], wrong)).reason == 'time_bar'


# --- adapter: disabled, pinned, one attempt -------------------------------------

def test_default_disabled_never_invokes_provider():
    context = context_for('The filing was late.')
    provider = Provider('{}')
    digest = sha256(serialized_block_request(context)).hexdigest()
    for adapter in (PublicBlockInterpretationAdapter(allowed_requests={digest}, provider=provider),
                    PublicBlockInterpretationAdapter(allowed_requests={digest}, enabled=True),
                    PublicBlockInterpretationAdapter(provider=provider, enabled=True)):
        with pytest.raises(PermissionError):
            adapter.propose(context)
    assert provider.calls == []


def test_exact_allowlist_pins_text_schema_profile_and_domain(monkeypatch):
    context = context_for('The filing was late.')
    provider = Provider('{}', profile=dict(name='profile-a'))
    adapter, digest = enabled_adapter(context, provider)
    with pytest.raises(PermissionError):
        adapter.propose(context_for('The filing was late!'))
    provider.profile = dict(name='profile-b')
    with pytest.raises(PermissionError):
        adapter.propose(context)
    provider.profile = dict(name='profile-a')
    monkeypatch.setattr(block_model, 'BLOCK_SCHEMA', {**block_model.BLOCK_SCHEMA, 'title': 'Changed'})
    with pytest.raises(PermissionError):
        adapter.propose(context)
    monkeypatch.undo()
    old = sha256(serialized_request(context, provider.profile)).hexdigest()
    with pytest.raises(PermissionError):
        PublicBlockInterpretationAdapter(allowed_requests={old}, provider=provider, enabled=True).propose(context)
    with pytest.raises(PermissionError):
        PublicInterpretationAdapter(allowed_requests={digest}, provider=provider, enabled=True).propose(context)
    assert provider.calls == []


def test_request_is_public_scope_only_with_existing_budgets():
    context = context_for('The filing was late.', account='acct-private-991', invoice='inv-private-7')
    new = json.loads(serialized_block_request(context, dict(name='p')))
    old = json.loads(serialized_request(context, dict(name='p')))
    for key in ('model', 'tools', 'max_output_chars', 'timeout_seconds', 'max_budget_usd', 'transport'):
        assert new[key] == old[key]
    assert new['tools'] == [] and new['model'] == MODEL == 'claude-opus-5-5'
    assert new['domain'] != old.get('domain') and new['system'] != old['system'] and new['schema'] != old['schema']
    assert new['version'] == 'source_blocks_v2' and new['schema'] == BlockInterpretation.model_json_schema()
    assert set(new['input']) == {'source_blocks', 'scope_month', 'currency', 'requested', 'filing_fields'}
    encoded = serialized_block_request(context)
    assert b'acct-private-991' not in encoded and b'inv-private-7' not in encoded


def test_plain_mode_refuses_output_schema_profiles_without_fallback():
    context = context_for('The filing was late.')
    plain = json.loads(serialized_block_request(context, dict(name='p')))
    assert plain['output_mode'] == 'plain_profile' and 'structured_output' not in plain
    assert plain['schema'] == BlockInterpretation.model_json_schema()  # schema travels in the prompt only
    assert json.loads(serialized_block_request(context))['output_mode'] == 'plain_profile'
    assert not hasattr(block_model, 'output_schema') and not hasattr(block_model, 'BLOCK_SCHEMA_SHA256')
    schema_sha = sha256(json.dumps(BlockInterpretation.model_json_schema(), ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':')).encode()).hexdigest()
    for pinned in (schema_sha, '0' * 64, None):
        profile = dict(name='p', output_schema_sha256=pinned)
        with pytest.raises(ValueError, match='plain profile only'):
            serialized_block_request(context, profile)
        # Even an allowlist built from the plain-profile request cannot enable a structured profile.
        plain_digest = sha256(serialized_block_request(context, dict(name='p'))).hexdigest()
        provider = Provider('{}', profile=profile)
        adapter = PublicBlockInterpretationAdapter(allowed_requests={plain_digest}, provider=provider, enabled=True)
        with pytest.raises(ValueError, match='plain profile only'):
            adapter.propose(context)
        assert provider.calls == []


def test_enabled_adapter_hydrates_once_with_block_provenance():
    _, cases = controls()
    context = cases['unicode-award']['context']
    body = json.dumps(SEMANTIC['unicode-award'](context['text']))
    provider = Provider(body)
    adapter, digest = enabled_adapter(context, provider)
    result = adapter.propose(context)
    assert len(provider.calls) == 1 and sha256(provider.calls[0]).hexdigest() == digest
    provenance = result['provenance']
    assert provenance['representation'] == 'source_blocks_v2'
    assert provenance['structural_grounding_not_semantic_validation'] is True
    assert (provenance['model'], provenance['request_sha256'], provenance['session']) == (MODEL, digest, 'session-1')
    assert provenance['response_sha256'] == sha256(body.encode()).hexdigest()
    assert provenance['transport'] == {'receipt': 'fake'}
    interpretation = Interpretation.model_validate(result['interpretation'])
    assert interpretation.model_dump() == hydrate_blocks(context['text'], json.loads(body)).model_dump()
    assert proposal_for_review(context, interpretation).amount == '17.20'


def _mutated(text, mutate):
    value = SEMANTIC['unicode-award'](text)
    mutate(value)
    return json.dumps(value)


@pytest.mark.parametrize('mutate', [
    lambda v: v.update(notes='extra'),
    lambda v: v['blocks'][0].update(confidence=0.9),
    lambda v: v['blocks'][0]['propositions'][0].update(source=dict(start=0, end=3, quote='Cré')),
    lambda v: v['blocks'][0]['propositions'][0].update(family='refund'),
    lambda v: v['blocks'][0]['propositions'][0]['slots'][0].update(quote='USD 71.20'),
    lambda v: v['blocks'][0]['propositions'][0]['slots'][0].update(start=17),
    lambda v: v['blocks'][0].update(block_id='b00-' + 'a' * 16),
])
def test_hallucinated_or_extra_fields_reject_after_one_attempt(mutate):
    _, cases = controls()
    context = cases['unicode-award']['context']
    provider = Provider(_mutated(context['text'], mutate))
    adapter, _ = enabled_adapter(context, provider)
    with pytest.raises(ValueError):
        adapter.propose(context)
    assert len(provider.calls) == 1


@pytest.mark.parametrize('result', [
    dict(model='claude-sonnet-5-5', text='{}'), dict(model=MODEL, text='x' * 30001), dict(model=MODEL, text=None),
    dict(model=MODEL, text='{"blocks":[],"blocks":[]}'), dict(model=MODEL, text='NaN'), ['not', 'a', 'dict'],
])
def test_invalid_provider_results_reject_without_retry(result):
    context = context_for('The filing was late.')
    provider = Provider(result=result)
    adapter, _ = enabled_adapter(context, provider)
    with pytest.raises(ValueError):
        adapter.propose(context)
    assert len(provider.calls) == 1


# --- frozen authored controls ---------------------------------------------------

def test_eight_frozen_controls_with_handcrafted_semantics(monkeypatch):
    raw, cases = controls()
    assert set(cases) == set(SEMANTIC) and len(cases) == 8

    def forbidden(*args, **kwargs):
        raise AssertionError('A financial or case write was attempted.')
    for name in ('persist_case', 'save_cases', 'transition_settlement'):
        monkeypatch.setattr(storage, name, forbidden)
    for case_id, case in cases.items():
        context = case['context']
        before = deepcopy(context)
        annotation = SEMANTIC[case_id](context['text'])
        direct = proposal_for_review(context, hydrate_blocks(context['text'], annotation))
        request = serialized_block_request(context)
        assert b'expected_reason' not in request and case_id.encode() not in request
        provider = Provider(json.dumps(annotation))
        adapter, _ = enabled_adapter(context, provider)
        result = adapter.propose(context)
        via_adapter = proposal_for_review(context, Interpretation.model_validate(result['interpretation']))
        assert direct == via_adapter
        assert direct.reason == case['expected_reason'], case_id
        assert len(provider.calls) == 1 and context == before
        if case_id == 'unicode-award':
            assert direct.amount == '17.20' and direct.span == (0, len(context['text'].encode('utf-8')))
        else:
            assert direct.amount is None
    assert CONTROLS_PATH.read_bytes() == raw
