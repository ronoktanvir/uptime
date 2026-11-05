"""Synthetic instrument contract extension with independent integer time and currency expectations."""
from copy import deepcopy

import pytest

from test_vendor_resource import FACTS, LINE, OVERLAY, compiled, extend_source, interval, result

EXTENSION = [
    ('Count overlapping outages once and retain fractional minutes of elapsed time.',
     {'interval_measurement': ['union_overlaps', 'exact_elapsed']}),
    ('Subtract only time inside a maintenance window announced at least 2 hours before its start.',
     {'maintenance': {'basis': 'within_announced_window', 'notice': {'count': 2, 'unit': 'hours'}}}),
    ('Use affected station fees after discounts for the month.', {'fee_adjustment': 'after_discounts'}),
    ('An incomplete claim may supplement its missing fields by the same deadline.',
     {'supplement': 'same_filing_deadline'}),
    ('Deduct any prior credits issued for that same station and service month from its remaining entitlement.',
     {'prior_credit': 'subtract_issued_same_resource_month'}),
]
SCOPE = {k: OVERLAY[k] for k in ('account', 'resource_id', 'agreement')}
SCOPE['month'] = FACTS['month']


def statement(ref, records):
    return {**SCOPE, 'verified': True, 'complete': True, 'ref': ref, 'records': records}


def readings():
    outage = interval('reader-A', 0, 650)
    duplicate = interval('reader-B', 125, 300)
    window = {'ref': 'operations-bulletin-A', 'account': SCOPE['account'], 'resource_id': SCOPE['resource_id'],
              'start': '2026-06-05T00:30:00Z', 'end': '2026-06-05T02:30:00Z',
              'announced_at': '2026-06-04T22:30:00Z'}
    credit = {**SCOPE, 'ref': 'ledger-entry-A', 'credit_id': 'credit-A', 'amount_cents': 231,
              'currency': 'USD', 'state': 'issued'}
    fees = LINE | {'amount_cents': 10201, 'gross_cents': 11000, 'discount_cents': 799,
                   'discount_ref': 'statement-detail-A'}
    return deepcopy(FACTS) | {
        'received_at': '2026-07-07T08:00:00Z', 'intervals': [outage, duplicate], 'exclusions': [],
        'fee_lines': [fees], 'maintenance_evidence': statement('notice-register', [window]),
        'prior_credit_evidence': statement('credit-statement', [credit, credit | {'ref': 'same-credit-readback'},
            credit | {'resource_id': 'sibling-station', 'credit_id': 'sibling'},
            credit | {'ref': 'prior-month-entry', 'month': '2026-05', 'credit_id': 'may'}]),
    }


@pytest.fixture
def manifest():
    return compiled(*extend_source(EXTENSION))


def test_scoped_rounded_residual_and_conditional_notice(manifest):
    facts = readings()
    # 650 observed minutes less the 120-minute published overlap. 12.5% of $102.01 gives $12.75;
    # the duplicate $2.31 credit counts once. Other months and station IDs have separate obligations.
    r = result(facts, manifest)
    assert (r['outcome'], r['service_estimate'], r['prior_issued_cents'], r['amount']) == ('ELIGIBLE', '12.75', 231, '10.44')
    assert r['downtime_microseconds'] == 530 * 60_000_000
    facts['maintenance_evidence']['records'][0]['announced_at'] = '2026-06-04T22:30:00.000001Z'
    assert result(facts, manifest)['downtime_microseconds'] == 650 * 60_000_000
    facts['prior_credit_evidence']['records'][0]['amount_cents'] = 10750
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'
    facts['prior_credit_evidence']['records'] = facts['prior_credit_evidence']['records'][:1]
    assert result(facts, manifest)['outcome'] == 'INELIGIBLE'


@pytest.mark.parametrize('missing', ['maintenance_evidence', 'prior_credit_evidence'])
def test_missing_mismatched_or_incomplete_register_never_implies_zero(manifest, missing):
    facts = readings()
    evidence = facts.pop(missing)
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'
    for mismatch in ({'complete': False}, {'verified': False}, {'agreement': 'other agreement'},
                     {'month': '2026-04'}, {'ref': ''}):
        assert result(facts | {missing: evidence | mismatch}, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'


def test_cause_bound_maintenance_only_removes_matching_measurements():
    rows = list(EXTENSION)
    rows[1] = ('Exclude outages caused by station maintenance within a window announced before it begins.',
               {'maintenance': {'basis': 'caused_within_announced_window', 'cause': 'station maintenance', 'notice': None}})
    manifest = compiled(*extend_source(rows))
    facts = readings()
    facts['intervals'] = [interval('service', 0, 60), interval('maintenance', 0, 200, 'station maintenance')]
    # The published window covers minutes 30..150. A separate qualifying gateway outage covers 30..60.
    assert result(facts, manifest)['downtime_microseconds'] == 110 * 60_000_000


def test_supplement_must_be_linked_and_received_by_original_deadline(manifest):
    facts = readings()
    proof = facts['filing_proof']
    proof['fields'].pop('log references')
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'
    supplement = {**SCOPE, 'ref': 'registered-supplement', 'original_ref': proof['ref'], 'verified': True,
                  'received_at': '2026-07-10T18:00:00Z', 'submitted_to': proof['submitted_to'],
                  'fields': {'log references': 'reader-A,reader-B'}}
    proof['supplements'] = [supplement]
    assert result(facts, manifest)['amount'] == '10.44'
    supplement['received_at'] = '2026-07-10T18:00:00.000001Z'
    assert result(facts, manifest)['filing_status'] == 'LATE_SUPPLEMENT'
    supplement['original_ref'] = 'other-case'
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'


def test_net_line_must_reconcile_or_carry_explicit_net_provenance(manifest):
    facts = readings()
    fee = facts['fee_lines'][0]
    fee['amount_cents'] += 1
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'
    fee.pop('gross_cents')
    fee.pop('discount_cents')
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'
    fee['amount_basis'] = 'net_after_discounts'
    assert result(facts, manifest)['amount'] == '10.44'
    fee.pop('discount_ref')
    assert result(facts, manifest)['outcome'] == 'INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('index', range(len(EXTENSION)))
def test_new_terms_cannot_be_silently_dropped_or_mislabeled(index):
    rows = list(EXTENSION)
    rows[index] = rows[index][0], {'nonmaterial': 'Notes.'}
    with pytest.raises(ValueError):
        compiled(*extend_source(rows))


def test_reversed_table_columns_with_header_units_and_explicit_floors():
    from test_vendor_resource import DOC, PROPOSAL

    rows = [(' | Credit rate (% of fees) | Availability (%) |', {'nonmaterial': 'Table header.'}),
            ('| 45 | < 98 |', {'tiers': [{'below': '98', 'credit': '45', 'at_least': None}]}),
            ('| 12.5 | 98 ≤ uptime < 99 |', {'tiers': [{'below': '99', 'credit': '12.5', 'at_least': '98'}]})]
    def compile_rows(rows):
        proposal = deepcopy(PROPOSAL)
        old = proposal[7]['quote']
        proposal[7:8] = [{'quote': text.strip(), 'field': 'resource_terms', 'value': value} for text, value in rows]
        document = DOC | {'text': DOC['text'].replace(old, '\n'.join(text.strip() for text, _ in rows))}
        return compiled(document, proposal)

    manifest = compile_rows(rows)
    assert [(r['below_units'], r['credit_units']) for r in manifest['tiers']] == [(98000000, 45000000), (99000000, 12500000)]
    bad_lower = list(rows)
    bad_lower[2] = (rows[2][0].replace('≤', '<'), rows[2][1])
    with pytest.raises(ValueError):
        compile_rows(bad_lower)
    bad_header = list(rows)
    bad_header[0] = ('| Credit rate | Availability |', rows[0][1])
    with pytest.raises(ValueError):
        compile_rows(bad_header)


def test_block_local_options_prevent_a_contextual_effect_on_scope_only_text():
    from uptime.vendor_resource_operators import interval_options
    from uptime.vendor_resource_terms import validate_filing

    assert interval_options('This schedule covers a single observation station each month.') == []
    assert set(interval_options('Count overlapping outages once and retain fractional minutes of elapsed time.')) == {
        'union_overlaps', 'exact_elapsed'}
    wrongly_attached = [('This schedule covers north and south stations each month.', {'interval_measurement': ['exact_elapsed']})]
    with pytest.raises(ValueError, match='Block .* field interval_measurement'):
        compiled(*extend_source(wrongly_attached))
    policy = {'kind': 'billing_cycles', 'count': 2, 'utc_time': None, 'endpoint': 'whole_cycle'}
    validate_filing(policy, 'Requests are due by the close of the second full billing cycle after the service month.')


@pytest.mark.parametrize('expression', [
    '100 × (1 minus qualifying interruption minutes divided by all minutes in the service month)',
    '(one minus downtime / total seconds of the calendar month) times 100',
    '100 × (1 minus covered seconds divided by all seconds in the month)',
])
def test_availability_formula_binds_seconds_and_minutes_to_their_operand_roles(expression):
    from uptime.vendor_resource_operators import interval_options
    source = 'Availability is ' + expression + '. A threshold boundary belongs to its higher band.'
    assert interval_options(source) == ['availability_ratio']
    assert compiled(*extend_source([(source, {'interval_measurement': ['availability_ratio']})]))


@pytest.mark.parametrize('expression', [
    '100 × (1 minus all seconds in the month divided by covered seconds)',
    '100 × (1 minus covered seconds multiplied by all seconds in the month)',
    '100 × (1 minus covered seconds divided by all seconds in the month) + 2',
    '100 × (1 minus covered minutes divided by all seconds in the month)',
])
def test_wrong_formula_is_unsupported_even_if_labeled_nonmaterial(expression):
    from uptime.vendor_resource_operators import interval_options
    source = 'Availability is ' + expression + '.'
    assert 'availability_ratio' not in interval_options(source)
    for mapping in [{'interval_measurement': ['availability_ratio']}, {'nonmaterial': 'Definition.'}]:
        with pytest.raises(ValueError):
            compiled(*extend_source([(source, mapping)]))


def test_ungrouped_text_requires_case_distinction_and_explicit_recorded_formula_decision(tmp_path, monkeypatch):
    import json
    from hashlib import sha256
    from test_vendor_resource import P
    from uptime import vendor_registry as registry
    from uptime.contracts import fingerprint
    from uptime.storage import initialize
    from uptime.vendor_model import MODEL

    sentence = 'Station availability is 100 multiplied by one minus covered minutes divided by all minutes in the month.'
    doc, proposal = extend_source([(sentence, {'interval_measurement': ['availability_ratio']})])
    digest = sha256(doc['text'].encode()).hexdigest()
    receipt = {'model': MODEL, 'source_sha256': digest, 'session': 'scripted-test-formula', 'at': '2026-05-01T00:00:00Z',
               'proposal': proposal, 'proposal_sha256': fingerprint(proposal)}
    (tmp_path / (digest + '.json')).write_text(json.dumps(receipt))
    monkeypatch.setenv('UPTIME_MODEL_PROPOSITIONS', '1')
    monkeypatch.setenv('UPTIME_PUBLIC_EXTRACTIONS', str(tmp_path))
    path = tmp_path / 'sandbox.sqlite'
    initialize(path)
    shadow = registry.install(path, P, 'instruments', {'document': doc, 'overlay': OVERLAY})
    from test_vendor_semantic_bindings import review_submission
    shadow = registry.review_semantics(path,P,'instruments',registry.SemanticSubmission(revision=shadow['revision'],
        review=review_submission(shadow['manifest'],shadow['overlay'],doc['text'])))
    grouping = shadow['manifest']['formula_grouping_review']
    assert grouping['endpoint_vectors'][-1] == {'covered_fraction': '1', 'selected_percent': '0', 'alternative_percent': '99'}
    refusal = {'name': 'complete observations without an outage', 'facts': FACTS | {'intervals': []},
               'expected': {'outcome': 'INELIGIBLE'}}
    def test_cases(current, cases):
        return registry.submit_tests(path, P, 'instruments', registry.TestSubmission(revision=current['revision'], tests=cases))
    isolated = test_cases(shadow, [refusal])
    assert not isolated['actions'] and any('grouping' in c['name'] and not c['passed'] for c in isolated['checks'])
    positive = {'name':'independent June value', 'facts': FACTS, 'expected':{'outcome':'ELIGIBLE','amount':'12.51'}}
    tested = test_cases(isolated, [positive, refusal])
    action = tested['actions'][0]
    assert action['operation'] == 'interpret' and grouping['selected'] in action['label']
    accepted = registry.act(path, P, 'instruments', action['id'])
    assert accepted['formula_decision'] == {'selected':grouping['selected'], 'source_block':grouping['source_block'],
            'suite':tested['suite'], 'version':tested['version'], 'reviewer':P.subject}


def test_claimant_proof_never_establishes_issuer_verification():
    row = ('Include proof of failed samples in the claim.',
           {'request_fields': ['failed samples'], 'evidence': ['verification', 'request_contents']})
    manifest = compiled(*extend_source([row]))
    assert 'claimant_supporting_proof' in manifest['evidence']
    # The original fixture has its own separate issuer-verification clause.
    from test_vendor_resource import DOC, PROPOSAL
    standalone = deepcopy(PROPOSAL)
    standalone[-1]['value'].pop('evidence')
    text = standalone[-1]['quote']
    fresh = text.replace('After verification, ', '')
    standalone[-1]['quote'] = fresh
    standalone.append({'quote': row[0], 'field': 'resource_terms', 'value': row[1]})
    doc = DOC | {'text': DOC['text'].replace(text, fresh) + '\n' + row[0]}
    assert 'verification' not in compiled(doc, standalone)['evidence']
    with pytest.raises(ValueError, match='verification'):
        compiled(*extend_source([('Include the station identifier in the claim.', row[1] | {'request_fields':['station identifier']})]))


def test_reflow_joins_only_continuations_and_old_receipts_preserve_their_source_index():
    from uptime.vendor_resource_terms import public_blocks, project_blocks
    source = ('## 4. Measurement\r\n\r\nThe period includes the exact duration of every\r\n'
              'qualifying interruption in this station month.\r\n'
              '| Availability below | Credit |\r\n| 99% | 10% |\r\n\r\nEnd note.')
    old = public_blocks(source)
    new = public_blocks(source, protocol='public_block_ids/2')
    assert len(old) == 6 and len(new) == 5
    assert new[1]['text'] == source[new[1]['start']:new[1]['end']]
    assert '\r\nqualifying interruption' in new[1]['text']
    response = {'blocks': [{'id': b['id'], 'value': {'nonmaterial': 'test only'}} for b in old]}
    rows, _ = project_blocks(source, response)
    assert [row['quote'] for row in rows] == [b['text'] for b in old]
    with pytest.raises(ValueError):
        project_blocks(source, response, protocol='public_block_ids/2')


def test_markdown_numbered_headings_and_public_processing_notes_do_not_waive_conditions():
    ok = [('## 2. Service measurement', {'nonmaterial': 'Section heading.'}),
          ('Public-only model extraction of this fictional document is authorized.', {'nonmaterial': 'Source provenance.'})]
    assert compiled(*extend_source(ok))
    for text in ('## 4. Claims must be approved', 'Public-only model extraction is authorized. Credits only cover weekday outages.'):
        with pytest.raises(ValueError):
            compiled(*extend_source([(text, {'nonmaterial': 'Heading or source note.'})]))


def test_duration_definition_phrase_can_follow_its_source_symbol():
    rows=[('Let K be every elapsed second in the month and Q the covered outage seconds.',
           {'measurement_symbols':{'total':{'symbol':'K','phrase':'every elapsed second in the month'},
                                   'down':{'symbol':'Q','phrase':'the covered outage seconds'}}}),
          ('Availability is 100 times (K minus Q) divided by K.',{'interval_measurement':['availability_ratio']})]
    assert compiled(*extend_source(rows))['measurement_symbols']=={'total':'K','down':'Q'}
    bad=deepcopy(rows)
    bad[0][1]['measurement_symbols']['down']['symbol']='K'
    with pytest.raises(ValueError,match='grounded|definitions'):
        compiled(*extend_source(bad))


def test_prior_credit_can_reference_an_already_defined_rounding_step():
    row=('Subtract prior credit issued for the same station and month from the rounded monthly credit.',
         {'prior_credit':'subtract_issued_same_resource_month'})
    assert compiled(*extend_source([row]))['prior_credit']
    bad=('Round the monthly credit down and subtract prior credit issued for the same station and month.',
         row[1])
    with pytest.raises(ValueError,match='typed calculation'):
        compiled(*extend_source([bad]))
