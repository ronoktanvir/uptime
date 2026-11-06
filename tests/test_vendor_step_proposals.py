"""Decision70: public completed-step proposal wire form for the monthly flow.

The fixtures in fixtures/opus70_public are openly authored public controls, frozen
before implementation. They are not blind evidence, a real contract, provider
proof or human approval. Expected answers are only test assertions and reviewer
controls; no engine input is derived from them. Billing events below are explicit
synthetic adapter unit-test inputs, not authentication or signature verification.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

import pytest

from uptime import vendor_registry as catalog
from uptime.contracts import Citation, Principal, fingerprint
from uptime.correspondence_types import Scope
from uptime.credit_steps import rate as step_rate
from uptime.governing_fees import FeeEntry, FeeRegistry, authenticated_invoice_snapshot
from uptime.pricing import Agreement, ContractVersion, Invoice, InvoiceLine, Rate, Tier
from uptime.pricing_terms import compile_fixed_monthly
from uptime.storage import initialize
from uptime.vendor_eval import evaluate
from uptime.vendor_model import MODEL, PROMPT, RejectedProposal, _typed_values, generate, validate_proposal
from uptime.vendor_terms import Document, Overlay, bind_overlay, compile_terms

FIXTURE = Path(__file__).resolve().parent.parent / 'fixtures' / 'opus70_public'


def load(name):
    return json.loads((FIXTURE / name).read_text())


DOC = load('document.json')
OVERLAY = load('overlay.json')
PRICING = load('pricing.json')
CONTROLS = load('controls.json')
BEFORE = load('before.json')
CASES = {case['name']: case for case in CONTROLS['monthly_cases']}
TENANT = 'opus70-authored-tenant'
REVIEWER = Principal(TENANT, 'scripted-opus70-test-reviewer', 'reviewer')
VENDOR = 'aster-cove'
# A disposable test-authored staged proposal; never a model session or retained receipt.
SESSION = 'synthetic-test-authored-public-wire-not-a-model-session'
OBSERVED = datetime.fromisoformat(PRICING['observed_at'])
CLAIM_RECEIVED = '2026-02-02T12:00:00Z'  # test-authored timely claim receipt
REGION = 'synthetic-unspecified'  # the authored pricing facts name no region


def proposal():
    return deepcopy(load(CONTROLS['positive_wire']))


def _rule(rows):
    return next(row for row in rows if row['field'] == 'credit_rule')


def _rounding(rows):
    return next(row for row in rows if row['field'] == 'credit_rounding')


def compiled():
    manifest = compile_terms(Document(**DOC))
    return manifest, bind_overlay(manifest, Overlay(**OVERLAY))


def facts(case):
    return {key: OVERLAY[key] for key in ('account', 'agreement', 'product', 'plan', 'fee_line_ref')} | {
        'month': case['month'], 'eligible_downtime_minutes': case['downtime'], 'monitor_source': 'simulated_vendor',
        'month_complete': True, 'exclusions_removed': True, 'received_at': CLAIM_RECEIVED}


def control_tests():
    return [dict(name=case['name'], facts=facts(case),
                 expected={'outcome': case['outcome']} | ({'amount': case['amount']} if case['amount'] else {}))
            for case in CONTROLS['monthly_cases']]


# ---- typed pricing inputs built only from the authored pricing.json facts ----

def at(value):
    return datetime.fromisoformat(value)


def billing_scope():
    invoice = PRICING['invoice']
    return Scope(account=OVERLAY['account'], vendor=PRICING['vendor'], contract=PRICING['agreement_id'],
                 service=OVERLAY['product'], month=invoice['start'][:7], invoice=invoice['id'],
                 currency=PRICING['currency'], region=REGION,
                 component='authored-queue-relay-service', incident='authored-january')


def pricing_entry(manifest, overlay, tenant=TENANT):
    p, inv = PRICING, PRICING['invoice']
    citation = Citation(p['agreement_id'] + ' authored order form', p['version'], 'fixed_schedule',
                        'urn:authored:opus70:pricing.json#fixed_schedule')
    terms = compile_fixed_monthly(p['fixed_schedule'], citation)
    version = ContractVersion(id=p['version'], effective_at=at(p['effective_at']), signed_at=at(p['signed_at']),
                              signatories=(p['customer'], p['vendor']), supersedes=None,
                              rates=(Rate(product=terms.product, unit=inv['unit'], tiers=(Tier(None, Decimal(p['monthly_fee'])),),
                                          fixed_monthly=terms),),
                              excluded_products=(), citation=citation, currency=p['currency'])
    agreement = Agreement(id=p['agreement_id'], customer=p['customer'], vendor=p['vendor'],
                          expires_at=at(p['expires_at']), versions=(version,))
    line = InvoiceLine(id=overlay['fee_line_ref'], product=overlay['product'], quantity=Decimal(inv['quantity']),
                       unit=inv['unit'], start=at(inv['start']), end=at(inv['end']), net=Decimal(inv['net']),
                       tax=Decimal(inv['tax']), allocation_ref=inv['allocation_ref'],
                       allocation_complete=inv['allocation_complete'])
    invoice = Invoice(id=inv['id'], customer=p['customer'], vendor=p['vendor'], issued_at=at(inv['issued_at']),
                      payment_status=inv['payment_status'], currency=p['currency'],
                      total=Decimal(inv['net']) + Decimal(inv['tax']), lines=(line,))
    return FeeEntry(entry_id='opus70-authored-' + inv['id'], tenant=tenant, scope=billing_scope(), plan=overlay['plan'],
                    fee_line_id=overlay['fee_line_ref'], agreement=agreement, invoice=invoice,
                    sla_source_sha256=manifest['document']['sha256'], manifest_sha256=fingerprint(manifest),
                    overlay_sha256=fingerprint(overlay))


def signed_snapshot(tenant=TENANT):
    """Explicit synthetic adapter unit-test input; NOT an authenticated receipt or signature check."""
    body = {'kind': 'invoice', 'lines': [{'id': OVERLAY['fee_line_ref'], 'kind': 'affected_api',
                                          'amount': PRICING['invoice']['net']}]}
    event = dict(source='billing', kind='invoice', body=body, digest=fingerprint(body),
                 subject='scripted-opus70-unit-test-billing', source_key_id='unit-test-key-not-authentication',
                 source_grant_id='unit-test-grant-not-authentication', received_at=OBSERVED.isoformat())
    return authenticated_invoice_snapshot(tenant, billing_scope(), event)


def issued_context(manifest, overlay, entry=None, tenant=TENANT):
    registry = FeeRegistry((entry or pricing_entry(manifest, overlay),))
    return registry, registry.resolve(signed_snapshot(tenant), as_of=OBSERVED)


# ---- frozen inputs and wire form ----

def test_frozen_authored_public_controls_are_unchanged():
    freeze = load('freeze.json')
    assert set(freeze['inputs']) == {'README.md', 'before.json', 'controls.json', 'document.json', 'overlay.json',
                                     'pricing.json', 'proposal.authored.json'}
    for name, digest in freeze['inputs'].items():
        assert sha256((FIXTURE / name).read_bytes()).hexdigest() == digest, name
    assert CONTROLS['classification'] == 'authored_public_controls_not_blind'


def test_prompt_lists_public_step_fields_without_internal_representation():
    for text in ('credit_rule', 'credit_rounding', '"completed_steps"', '"target"', '"step"', '"credit"', '"cap"',
                 'nearest_cent_half_up', 'without percent signs'):
        assert text in PROMPT
    assert '_units' not in PROMPT and 'citation' not in PROMPT


def test_authored_wire_validates_to_compiled_manifest_with_exact_offsets_and_digests():
    document = Document(**DOC)
    rows = proposal()
    expected = compile_terms(document)
    for flag in (False, True):
        assert validate_proposal(document, deepcopy(rows), allow_propositions=flag) == expected
    manifest = validate_proposal(document, rows)
    digest = sha256(DOC['text'].encode()).hexdigest()
    assert manifest['document']['sha256'] == digest == BEFORE['source_sha256']
    cursor = 0
    for citation, row in zip(manifest['citations'], rows, strict=True):
        assert citation['start'] >= cursor and not DOC['text'][cursor:citation['start']].strip()
        assert DOC['text'][citation['start']:citation['end']] == citation['quote'] == row['quote']
        assert citation['field'] == row['field']
        cursor = citation['end']
    assert not DOC['text'][cursor:].strip()
    rule = manifest['credit_rule']
    assert manifest['citations'][rule['citation'] - 1]['field'] == 'credit_rule'
    assert rule == BEFORE['compiler_credit_rule']
    assert manifest['credit_rounding'] == 'nearest_cent_half_up' and 'tiers' not in manifest
    # The public wire is never echoed into the manifest: only compiler-form values exist.
    assert set(rule) == {'kind', 'product', 'plan', 'citation', 'target_units', 'step_units', 'credit_units', 'cap_units'}


def test_legacy_normalized_and_tier_proposals_are_preserved():
    document = Document(**DOC)
    manifest = compile_terms(document)
    legacy = [dict(quote=c['quote'], field=field, value=value)
              for c, (field, value) in zip(manifest['citations'], _typed_values(manifest), strict=True)]
    assert _rule(legacy)['value'] == manifest['credit_rule']
    assert validate_proposal(document, legacy) == manifest
    tier_sentence = 'For Queue Relay on the Scale plan, monthly uptime below 99.8% earns a 7.5% service credit.'
    tier_text = DOC['text'].replace(_rule(proposal())['quote'], tier_sentence).replace(_rounding(proposal())['quote'] + '\n', '')
    tier_document = Document(**(DOC | {'text': tier_text}))
    tiers = compile_terms(tier_document)

    def tier_rows(value, field='tier'):
        return [dict(quote=c['quote'], field=field if c['field'] == 'tier' else c['field'],
                     value=value if c['field'] == 'tier' else tiers.get(c['field'])) for c in tiers['citations']]

    tier = {'product': 'Queue Relay', 'plan': 'Scale', 'below': '99.8', 'credit': '7.5'}
    assert validate_proposal(tier_document, tier_rows(tier)) == tiers
    # Tier strings keep their pre-existing tolerance; canonical form applies only to the new step wire.
    assert validate_proposal(tier_document, tier_rows(tier | {'below': '99.80', 'credit': '7.50'})) == tiers
    for bad in (tier_rows({'product': 'Queue Relay', 'plan': 'Scale', 'below_units': 99800000, 'credit_units': 7500000}),
                tier_rows(_rule(proposal())['value']), tier_rows(_rule(proposal())['value'], field='credit_rule'),
                tier_rows(tier | {'credit': '8'})):
        with pytest.raises(ValueError):
            validate_proposal(tier_document, bad)


def set_rule(**changes):
    return lambda rows: _rule(rows)['value'].update(changes)


def rule_value(value):
    return lambda rows: _rule(rows).update(value=value)


def legacy(**changes):
    return lambda rows: _rule(rows).update(value=compile_terms(Document(**DOC))['credit_rule'] | changes)


def split_rule(rows):
    row = _rule(rows)
    index = rows.index(row)
    head, tail = row['quote'].split('; ', 1)
    rows[index:index + 1] = [dict(quote=head + ';', field='credit_rule', value=row['value']),
                             dict(quote=tail, field='unsupported', value=None)]


def without_target(rows):
    value = _rule(rows)['value']
    _rule(rows)['value'] = {k: v for k, v in value.items() if k != 'target'} | {'target_units': 99800000}


WIRE_MUTATIONS = {
    'wrong target': set_rule(target='99.9'),
    'wrong step': set_rule(step='0.1'),
    'wrong credit': set_rule(credit='7'),
    'wrong cap': set_rule(cap='25'),
    'swapped step and credit': set_rule(step='7.5', credit='0.2'),
    'wrong product': set_rule(product='Queue relay'),
    'padded product': set_rule(product='Queue Relay '),
    'wrong plan': set_rule(plan='Scale Plus'),
    'non-string product': set_rule(product=['Queue Relay']),
    'numeric float': set_rule(target=99.8),
    'numeric integer': set_rule(cap=30),
    'boolean': set_rule(cap=True),
    'null percentage': set_rule(step=None),
    'exponent percentage': set_rule(target='9.98e1'),
    'percent sign in value': set_rule(target='99.8%'),
    'trailing fractional zero': set_rule(target='99.80'),
    'integral trailing zero': set_rule(cap='30.0'),
    'leading zero': set_rule(target='099.8'),
    'bare fraction': set_rule(step='.2'),
    'trailing point': set_rule(cap='30.'),
    'signed': set_rule(cap='+30'),
    'leading whitespace': set_rule(cap=' 30'),
    'trailing newline': set_rule(cap='30\n'),
    'non-ascii digits': set_rule(cap='٣٠'),
    'zero percent': set_rule(step='0'),
    'above one hundred percent': set_rule(cap='100.5'),
    'precision beyond micro-percent': set_rule(step='0.2000001'),
    'mixed internal/external fields': set_rule(target_units=99800000),
    'internal unit replaces external field': without_target,
    'unknown kind': set_rule(kind='started_steps'),
    'tier kind': set_rule(kind='tier'),
    'case-changed kind': set_rule(kind='Completed_Steps'),
    'missing kind': lambda rows: _rule(rows)['value'].pop('kind'),
    'extra citation on external shape': set_rule(citation=6),
    'extra units on external shape': set_rule(units='percent'),
    'tier-shaped value': rule_value({'product': 'Queue Relay', 'plan': 'Scale', 'below': '99.8', 'credit': '7.5'}),
    'prose value': rule_value('7.5% per completed 0.2 points, capped at 30%'),
    'null value': rule_value(None),
    'rule relabeled tier': lambda rows: _rule(rows).update(field='tier'),
    'rule relabeled unsupported': lambda rows: _rule(rows).update(field='unsupported', value=None),
    'extra clause key': lambda rows: _rule(rows).update(citation=6),
    'missing rounding value': lambda rows: _rounding(rows).update(value=None),
    'rounding relabeled unsupported': lambda rows: _rounding(rows).update(field='unsupported', value=None),
    'missing rounding block': lambda rows: rows.remove(_rounding(rows)),
    'alternate rounding': lambda rows: _rounding(rows).update(value='nearest_cent_half_even'),
    'case-changed rounding': lambda rows: _rounding(rows).update(value='NEAREST_CENT_HALF_UP'),
    'boolean rounding': lambda rows: _rounding(rows).update(value=True),
    'missing source block': lambda rows: rows.remove(_rule(rows)),
    'wrong copied quote': lambda rows: _rule(rows).update(quote=_rule(rows)['quote'].replace('99.8%', '99.9%')),
    'whitespace-altered quote': lambda rows: _rule(rows).update(quote=_rule(rows)['quote'].replace('; each', ';  each')),
    'split rule quote': split_rule,
    'legacy internal citation mismatch': legacy(citation=7),
    'legacy internal float units': legacy(target_units=99800000.0),
    'legacy internal boolean citation': legacy(citation=True),
    'legacy internal string units': legacy(cap_units='30'),
    'legacy internal with external field': legacy(target='99.8'),
}


@pytest.mark.parametrize('name', WIRE_MUTATIONS)
@pytest.mark.parametrize('flag', [False, True])
def test_wire_mutations_refuse(name, flag):
    rows = proposal()
    WIRE_MUTATIONS[name](rows)
    assert rows != proposal()
    with pytest.raises(ValueError):
        validate_proposal(Document(**DOC), rows, allow_propositions=flag)


def mutated_source(old, new):
    assert DOC['text'].count(old) == 1
    rows = proposal()
    for row in rows:
        row['quote'] = row['quote'].replace(old, new)
    return Document(**(DOC | {'text': DOC['text'].replace(old, new)})), rows


def with_clause(sentence, field, value, after):
    rows = proposal()
    index = next(i for i, row in enumerate(rows) if row['field'] == after)
    anchor = rows[index]['quote']
    rows.insert(index + 1, dict(quote=sentence, field=field, value=value))
    return Document(**(DOC | {'text': DOC['text'].replace(anchor, anchor + '\n' + sentence)})), rows


NEIGHBOR = 'Credits are void for any month with an overdue customer balance.'
TIER_UNION = 'For Queue Relay on the Scale plan, monthly uptime below 99% earns a 10% service credit.'
SOURCE_MUTATIONS = {
    'source started step': lambda: mutated_source('each completed', 'each started'),
    'source partial step': lambda: mutated_source('0.2 percentage point', '0.2 percent or part thereof'),
    'source conditional exception': lambda: mutated_source('capped at 30%.', 'capped at 30%, unless an exception applies.'),
    'source monetary cap': lambda: mutated_source('capped at 30%', 'capped at USD 30'),
    'source half-even rounding': lambda: mutated_source('with half cents rounded up', 'with half cents rounded to even'),
    'unsupported neighboring clause': lambda: with_clause(NEIGHBOR, 'unsupported', None, 'credit_rule'),
    'neighboring clause labeled heading': lambda: with_clause(NEIGHBOR, 'heading', None, 'credit_rule'),
    'trailing unsupported clause': lambda: with_clause(NEIGHBOR, 'unsupported', None, 'remedy'),
    'tier and step union': lambda: with_clause(TIER_UNION, 'tier', {'product': 'Queue Relay', 'plan': 'Scale',
                                                                     'below': '99', 'credit': '10'}, 'credit_rule'),
}


@pytest.mark.parametrize('name', SOURCE_MUTATIONS)
def test_source_mutations_refuse_without_ignoring_neighboring_clauses(name):
    document, rows = SOURCE_MUTATIONS[name]()
    with pytest.raises(ValueError, match='Unsupported source language|cannot share'):
        validate_proposal(document, rows)
    with pytest.raises(ValueError):
        validate_proposal(document, rows, allow_propositions=True)
    with pytest.raises(ValueError):
        compile_terms(document)


def test_tool_free_generator_accepts_wire_and_rejects_mismatch_in_memory_only(monkeypatch):
    from types import SimpleNamespace
    sent, reply = [], [proposal()]

    def fake_run(argv, **kwargs):
        sent.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'is_error': False, 'modelUsage': {MODEL: {}}, 'session_id': 'synthetic-test-fake-subprocess',
            'result': json.dumps({'clauses': reply[0]})}))

    monkeypatch.setattr('uptime.vendor_model.subprocess.run', fake_run)
    digest = sha256(DOC['text'].encode()).hexdigest()
    artifact = generate(Document(**DOC), digest)
    assert artifact['proposal'] == proposal() and artifact['proposal_sha256'] == fingerprint(proposal())
    argv, kwargs = sent[0]
    assert argv[argv.index('--system-prompt') + 1] == PROMPT and argv[argv.index('--tools') + 1] == ''
    for private in (OVERLAY['account'], OVERLAY['fee_line_ref'], PRICING['customer'], PRICING['monthly_fee']):
        assert private not in kwargs['input']
    bad = proposal()
    _rule(bad)['value']['cap'] = '25'
    reply[0] = bad
    with pytest.raises(RejectedProposal) as caught:
        generate(Document(**DOC), digest)
    assert caught.value.receipt['status'] == 'REJECTED' and caught.value.receipt['raw_proposal'] == {'clauses': bad}


def test_generator_retains_os_login_identity_without_execution_overrides(monkeypatch):
    import os
    import pwd
    from types import SimpleNamespace
    captured = []
    overrides = {'USER': 'not-the-os-user', 'LOGNAME': 'not-the-os-user',
                 'NODE_OPTIONS': '--require /public-test-override', 'BASH_ENV': '/public-test-override',
                 'DYLD_INSERT_LIBRARIES': '/public-test-override', 'LD_PRELOAD': '/public-test-override',
                 'HTTPS_PROXY': 'http://public-test.invalid', 'ANTHROPIC_BASE_URL': 'http://public-test.invalid',
                 'ANTHROPIC_API_KEY': 'synthetic-not-a-credential',
                 'CLAUDE_CODE_OAUTH_TOKEN': 'synthetic-not-a-credential'}
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)
    def fake_run(argv, **kwargs):
        captured.append(kwargs['env'])
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'is_error': False, 'modelUsage': {MODEL: {}}, 'session_id': 'synthetic-environment-check',
            'result': json.dumps({'clauses': proposal()})}))
    monkeypatch.setattr('uptime.vendor_model.subprocess.run', fake_run)
    generate(Document(**DOC), sha256(DOC['text'].encode()).hexdigest())
    env = captured[0]
    assert env['USER'] == env['LOGNAME'] == pwd.getpwuid(os.getuid()).pw_name
    assert env['HOME'] == str(Path.home()) and env['PATH'] == os.environ['PATH']
    assert not (set(overrides) - {'USER', 'LOGNAME'}) & env.keys()
    assert env['CLAUDE_CODE_DISABLE_AUTO_MEMORY'] == '1'


# ---- engine controls and pricing authority ----

@pytest.mark.parametrize('invalid', [
    '{"clauses":[],"clauses":[]}',
    '{"clauses":[{"value":{"cap":"30","cap":"25"}}]}',
    '{"clauses":[],"extra":NaN}',
    '{"clauses":[],"extra":Infinity}',
    '{"clauses":[],"extra":-Infinity}',
    '{"clauses":[],"extra":1e999}',
])
@pytest.mark.parametrize('layer', ['envelope', 'proposal'])
def test_generator_refuses_ambiguous_json_before_proposal_validation(monkeypatch, invalid, layer):
    from types import SimpleNamespace
    envelope = {'is_error': False, 'modelUsage': {MODEL: {}},
                'session_id': 'synthetic-json-rejection', 'result': invalid}
    output = invalid if layer == 'envelope' else json.dumps(envelope)
    monkeypatch.setattr('uptime.vendor_model.subprocess.run',
                        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output))
    with pytest.raises(ValueError, match='Duplicate JSON key|Non-finite JSON'):
        generate(Document(**DOC), sha256(DOC['text'].encode()).hexdigest())


def test_frozen_ratio_and_monthly_controls_use_engine_results():
    manifest, overlay = compiled()
    rule = manifest['credit_rule']
    for vector in CONTROLS['ratio_vectors']:
        assert step_rate(rule, vector['available'], vector['total']) == vector['credit_units'], vector
    registry, context = issued_context(manifest, overlay)
    assert context.fee_minor == int(Decimal(PRICING['monthly_fee']) * 100) and context.currency == 'USD'
    assert context.governing_pricing_version == PRICING['version'] and context.provenance_class == 'local_synthetic'
    for case in CONTROLS['monthly_cases']:
        result = evaluate(manifest, overlay, facts(case), TENANT, governing_fee=context)
        assert (result['outcome'], result['amount']) == (case['outcome'], case['amount']), case['name']
        unpriced = evaluate(manifest, overlay, facts(case), TENANT)
        assert unpriced['amount'] is None
        if case['outcome'] == 'ELIGIBLE':
            assert unpriced['outcome'] == 'INSUFFICIENT_EVIDENCE' and unpriced['missing'] == ['governing_fee_context']
    two = evaluate(manifest, overlay, facts(CASES['two-completed-steps']), TENANT, governing_fee=context)
    assert two['completed_steps'] == 2 and two['rate_units'] == 2 * rule['credit_units']
    assert '44340/44640' in two['trace'][0] and two['governing_fee_digest'] == context.digest
    capped = evaluate(manifest, overlay, facts(CASES['cap']), TENANT, governing_fee=context)
    assert capped['rate_units'] == rule['cap_units'] and capped['completed_steps'] * rule['credit_units'] > rule['cap_units']
    zero = evaluate(manifest, overlay, facts(CASES['no-completed-step']), TENANT, governing_fee=context)
    assert zero['completed_steps'] == 0 and 'governing_fee_digest' not in zero
    incomplete = evaluate(manifest, overlay, facts(CASES['incomplete']), TENANT, governing_fee=context)
    assert incomplete['missing'] == ['eligible_downtime_minutes'] and 'rate_units' not in incomplete
    asserted_fee = facts(CASES['two-completed-steps']) | {'monthly_fee_cents': 1}
    assert evaluate(manifest, overlay, asserted_fee, TENANT, governing_fee=context)['amount'] == two['amount']
    registry.close()
    stale = evaluate(manifest, overlay, facts(CASES['two-completed-steps']), TENANT, governing_fee=context)
    assert stale['amount'] is None and stale['missing'] == ['governing_fee_context']


@pytest.mark.parametrize('pin', ['tenant', 'overlay', 'sla_source', 'manifest', 'forged_copy'])
def test_wrong_tenant_overlay_source_or_forged_context_never_prices(pin):
    manifest, overlay = compiled()
    january = facts(CASES['two-completed-steps'])
    _, baseline = issued_context(manifest, overlay)
    assert evaluate(manifest, overlay, january, TENANT, governing_fee=baseline)['amount'] == CASES['two-completed-steps']['amount']
    entry, tenant = pricing_entry(manifest, overlay), TENANT
    if pin == 'tenant':
        tenant = 'other-opus70-tenant'
        entry = replace(entry, tenant=tenant)
    elif pin == 'overlay':
        entry = replace(entry, overlay_sha256=fingerprint(overlay | {'account': 'other-account'}))
    elif pin == 'sla_source':
        entry = replace(entry, sla_source_sha256=sha256(b'other public source').hexdigest())
    elif pin == 'manifest':
        entry = replace(entry, manifest_sha256=fingerprint(manifest | {'filing_days': 22}))
    context = replace(baseline) if pin == 'forged_copy' else issued_context(manifest, overlay, entry, tenant)[1]
    result = evaluate(manifest, overlay, january, TENANT, governing_fee=context)
    assert (result['outcome'], result['amount'], result['missing']) == ('INSUFFICIENT_EVIDENCE', None, ['governing_fee_context'])


# ---- disposable catalog lifecycle ----

def stage(folder, rows, monkeypatch):
    """Disposable test-authored staged proposal. Not model output and never retained."""
    folder.mkdir()
    digest = sha256(DOC['text'].encode()).hexdigest()
    artifact = dict(source_sha256=digest, model=MODEL, session=SESSION, at='2026-11-05T00:00:00+00:00',
                    proposal=rows, proposal_sha256=fingerprint(rows))
    (folder / (digest + '.json')).write_text(json.dumps(artifact))
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(folder))
    monkeypatch.delenv('UPTIME_MODEL_PROPOSITIONS', raising=False)


def action(view, operation):
    return next(a['id'] for a in view['actions'] if a['operation'] == operation)


def test_unseen_authored_source_catalog_lifecycle_requires_current_pricing_authority(tmp_path, monkeypatch):
    path = tmp_path / 'opus70.sqlite'
    initialize(path)
    stage(tmp_path / 'staged', proposal(), monkeypatch)
    shadow = catalog.install(path, REVIEWER, VENDOR, {'document': DOC, 'overlay': OVERLAY})
    manifest, overlay = compiled()
    assert shadow['state'] == 'SHADOW' and shadow['actions'] == [] and shadow['reviewer'] is None
    assert shadow['manifest'] == manifest and shadow['overlay'] == overlay
    assert shadow['extraction']['session'] == SESSION
    assert shadow['extraction']['proposal_sha256'] == fingerprint(proposal())
    assert shadow['extraction']['source_sha256'] == manifest['document']['sha256'] == sha256(shadow['source_text'].encode()).hexdigest()
    assert shadow['generated_tests'] and all(row['passed'] for row in shadow['generated_tests'])

    tests = control_tests()
    unpriced = catalog.submit_tests(path, REVIEWER, VENDOR, catalog.TestSubmission(revision=shadow['revision'], tests=tests))
    rows = {row['name']: row for row in unpriced['checks']}
    for case in CONTROLS['monthly_cases']:
        if case['outcome'] == 'ELIGIBLE':
            assert rows[case['name']]['actual'] == {'outcome': 'INSUFFICIENT_EVIDENCE', 'amount': None}
            assert not rows[case['name']]['passed']
        else:
            assert rows[case['name']]['passed']
    assert unpriced['actions'] == []

    registry, context = issued_context(manifest, overlay)
    assert context.manifest_sha256 == fingerprint(shadow['manifest']) and context.overlay_sha256 == fingerprint(shadow['overlay'])
    assert context.sla_source_sha256 == manifest['document']['sha256']
    authority = (context,)
    priced = catalog.submit_tests(path, REVIEWER, VENDOR, catalog.TestSubmission(revision=unpriced['revision'], tests=tests),
                                  governing_fees=authority)
    assert all(row['passed'] for row in priced['checks']) and priced['pricing_binding_status'] == 'CURRENT'
    assert [a['operation'] for a in priced['actions']] == ['approve']
    assert {row['governing_fee_digest'] for row in priced['checks'] if 'governing_fee_digest' in row} == {context.digest}

    absent = catalog.get_vendor(path, REVIEWER, VENDOR)
    assert absent['state'] == 'REVIEW_REQUIRED' and absent['actions'] == []
    assert absent['pricing_binding_status'] == 'REVIEW_REQUIRED'
    with pytest.raises(ValueError, match='Stale or unavailable'):
        catalog.act(path, REVIEWER, VENDOR, action(priced, 'approve'))
    approved = catalog.act(path, REVIEWER, VENDOR, action(priced, 'approve'), governing_fees=authority)
    assert approved['state'] == 'APPROVED' and approved['reviewer'] == REVIEWER.subject
    assert approved['reviewer_kind'] == 'scripted_test'  # scripted test principal, not human approval

    other = Principal(TENANT, 'scripted-opus70-other-reviewer', 'reviewer')
    foreign = action(catalog.get_vendor(path, other, VENDOR, governing_fees=authority), 'activate')
    with pytest.raises(PermissionError):
        catalog.act(path, other, VENDOR, foreign, governing_fees=authority)
    with pytest.raises(ValueError, match='Stale or unavailable'):
        catalog.act(path, REVIEWER, VENDOR, action(approved, 'activate'))
    active = catalog.act(path, REVIEWER, VENDOR, action(approved, 'activate'), governing_fees=authority)
    assert active['state'] == 'ACTIVE' and active['active_version'] == shadow['version']
    assert catalog.get_vendor(path, REVIEWER, VENDOR, governing_fees=authority)['active_version'] == active['version']
    hidden = catalog.get_vendor(path, REVIEWER, VENDOR)
    assert hidden['active_version'] is None and hidden['recorded_active_version'] == active['version'] and hidden['actions'] == []

    january = facts(CASES['two-completed-steps'])
    case = catalog.dispatch(path, REVIEWER, VENDOR, january, governing_fee=context)
    assert (case['outcome'], case['amount']) == ('ELIGIBLE', CASES['two-completed-steps']['amount'])
    assert case['governing_fee_digest'] == context.digest and case['completed_steps'] == 2
    assert case['version'] == active['version'] and case['source_sha256'] == manifest['document']['sha256']
    for clause in case['clauses']:
        assert DOC['text'][clause['start']:clause['end']] == clause['quote']
    without = catalog.dispatch(path, REVIEWER, VENDOR, january)
    assert without['amount'] is None and without['missing'] == ['governing_fee_context']
    assert without['id'] == case['id'] and without['obligation_id'] == case['obligation_id']
    for control in CONTROLS['monthly_cases']:
        result = catalog.evaluate_active(path, REVIEWER, VENDOR, facts(control), governing_fee=context)
        assert (result['outcome'], result['amount']) == (control['outcome'], control['amount']), control['name']

    rollback = action(active, 'rollback')
    registry.close()
    stale = catalog.get_vendor(path, REVIEWER, VENDOR, governing_fees=authority)
    assert stale['state'] == 'REVIEW_REQUIRED' and stale['actions'] == [] and stale['active_version'] is None
    assert catalog.evaluate_active(path, REVIEWER, VENDOR, january, governing_fee=context)['amount'] is None
    assert catalog.dispatch(path, REVIEWER, VENDOR, january, governing_fee=context)['amount'] is None
    with pytest.raises(ValueError, match='Stale or unavailable'):
        catalog.act(path, REVIEWER, VENDOR, rollback, governing_fees=authority)

    _, renewed = issued_context(manifest, overlay)
    assert renewed is not context and renewed.digest == context.digest
    rolled = catalog.act(path, REVIEWER, VENDOR, rollback, governing_fees=(renewed,))
    assert rolled['state'] == 'REVOKED' and rolled['active_version'] is None and rolled['reviewer'] is None
    with pytest.raises(ValueError, match='activated local adapter'):
        catalog.dispatch(path, REVIEWER, VENDOR, january, governing_fee=renewed)
    audit = [(row['kind'], row['actor']) for row in rolled['audit']]
    for kind in ('Approve reviewed tests', 'Activate for local evaluation', 'Roll back activation'):
        assert (kind, REVIEWER.subject) in audit


def test_catalog_quarantines_mismatched_wire_and_wrong_overlay(tmp_path, monkeypatch):
    path = tmp_path / 'opus70-refusals.sqlite'
    initialize(path)
    bad = proposal()
    _rule(bad)['value']['cap'] = '25'
    stage(tmp_path / 'staged', bad, monkeypatch)
    refused = catalog.install(path, REVIEWER, VENDOR, {'document': DOC, 'overlay': OVERLAY})
    assert refused['state'] == 'QUARANTINED' and refused['active_version'] is None and refused['actions'] == []
    monkeypatch.delenv('UPTIME_PUBLIC_EXTRACTIONS')
    for vendor, changed in (('aster-cove-plan', {'plan': 'Scale Plus'}), ('aster-cove-product', {'product': 'Queue Relay Plus'}),
                            ('aster-cove-agreement', {'agreement': 'ACC-2026-18'}), ('aster-cove-currency', {'currency': 'EUR'})):
        state = catalog.install(path, REVIEWER, vendor, {'document': DOC, 'overlay': OVERLAY | changed})
        assert state['state'] == 'QUARANTINED' and state['active_version'] is None, vendor
    parser = catalog.install(path, REVIEWER, 'aster-cove-parser', {'document': DOC, 'overlay': OVERLAY})
    assert parser['state'] == 'SHADOW' and parser['extraction']['method'] == 'deterministic_document_parser'
    assert parser['manifest'] == compiled()[0]
