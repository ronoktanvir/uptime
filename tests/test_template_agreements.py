"""Money link: an accepted template read becomes a SHADOW agreement whose credit the existing engine computes."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from uptime import demo_opportunities as corvid
from uptime import template_agreements as ta
from uptime.vendor_eval import evaluate as engine

EXPECTED = json.loads((ta.ROOT / 'fixtures/template_builder_demo/expected.json').read_text())['halcyon-c']
TEMPLATE = {'id': 'halcyon-availability-addendum/1', 'sha256': 'ab' * 32}


def entry(values=None, document_id='halcyon-c', read_at='2026-11-10T13:05:00Z', reading_id='rd_4be1'):
    return {'build_id': 'tb_3f9a2c', 'reading_id': reading_id, 'template': dict(TEMPLATE),
            'vendor': 'Halcyon Grid Services',
            'document': {'id': document_id, 'title': 'Halcyon Grid: Platform Availability Addendum (Brightwater)',
                         'customer': EXPECTED['customer']},
            'values': dict(EXPECTED['terms'] if values is None else values), 'read_at': read_at}


def evidence():
    package = ta.load_evidence('halcyon-c')
    assert package is not None
    return package


class StandIn:
    """The three members the engine agent adds to TemplateBuilds."""
    def __init__(self, entries):
        self.entries, self.attached, self.on_reading = entries, {}, None

    def approved_readings(self):
        return deepcopy(self.entries)

    def set_agreement(self, build_id, reading_id, agreement):
        self.attached[(build_id, reading_id)] = agreement


def test_overlay_from_halcyon_c_terms_is_the_engines_tier_family():
    package = evidence()
    manifest, overlay = ta.overlay_from_values(EXPECTED['terms'], vendor='Halcyon Grid Services', document=package['overlay'])
    assert manifest['family'] == 'monthly-availability/1'
    product, plan = package['overlay']['product'], package['overlay']['plan']
    # Commitment 99.99% -> 15%; second threshold 99.9% -> 35%; sorted by threshold as the engine stores them.
    assert [(t['product'], t['plan'], t['below_units'], t['credit_units']) for t in manifest['tiers']] == [
        (product, plan, 99_900_000, 35_000_000), (product, plan, 99_990_000, 15_000_000)]
    assert (manifest['vendor'], manifest['agreement'], manifest['period'], manifest['filing_days'], manifest['remedy']) == (
        'Halcyon Grid Services', 'HGS-PAA-2026-0457', 'utc_calendar_month', 60, 'affected_monthly_fees_future_invoice')
    assert manifest['effective'] == ['2026-08-03', None]
    assert overlay['agreement'] == 'HGS-PAA-2026-0457' and overlay['fee_line_ref'] == 'halcyon-covered-services-line'
    carried = {term for citation in manifest['citations'] for term in citation['terms']}
    assert carried == set(ta.FIELDS) - {'maintenance_notice_hours'}  # the engine takes exclusion-adjusted minutes


def test_authored_month_is_estimated_by_the_engine_to_the_cent():
    agreement = ta.evaluate(entry(), evidence())
    # October 2026: 31 days x 1,440 = 44,640 minutes; 95 unavailable -> 44,545 available.
    # 44,545 / 44,640 = 99.7871...% is below the second-tier threshold 99.9% (and the 99.99% commitment), so the
    # second tier applies alone: 35%. The cap (50%) is not reached. 35% x USD 12,000.00 = USD 4,200.00.
    assert agreement == dict(agreement, agreement_id='HGS-PAA-2026-0457', state='SHADOW',
                             read_by='template:halcyon-availability-addendum/1', month='2026-10',
                             availability_percent='99.787', credit_percent='35', monthly_fee='12000.00',
                             credit={'amount': '4200.00', 'currency': 'USD', 'stage': 'ESTIMATED'})
    assert agreement['evaluation'] == ('44,545 of 44,640 UTC minutes were available (99.787%), so the 35% credit tier applies: '
                                       '35% of USD 12,000.00 is USD 4,200.00.')
    assert {'label': "The credit engine's own line", 'value': '44545/44640 UTC minutes available. Exact comparison gives '
            '35000000/1000000% credit.'} in agreement['inputs']
    assert set(agreement) == {'agreement_id', 'state', 'read_by', 'month', 'availability_percent', 'credit_percent',
                              'monthly_fee', 'credit', 'inputs', 'evaluation'}
    assert all(set(row) == {'label', 'value'} for row in agreement['inputs'])
    # The amount is the engine's: the same compiled agreement through vendor_eval.evaluate gives the same result.
    package = evidence()
    manifest, overlay = ta.overlay_from_values(EXPECTED['terms'], vendor='Halcyon Grid Services', document=package['overlay'])
    assert engine(manifest, overlay, corvid.facts(package), 'bears')['amount'] == '4200.00'


def test_first_tier_month():
    package = evidence()
    package['usage']['unavailable_minutes'] = 30
    # 44,610 / 44,640 = 99.9327...%: below 99.99% but not below 99.9% -> first tier 15% x 12,000.00 = 1,800.00.
    agreement = ta.evaluate(entry(), package)
    assert (agreement['credit_percent'], agreement['credit']['amount'], agreement['availability_percent']) == (
        '15', '1800.00', '99.932')


def test_no_unavailability_earns_no_credit_and_no_invented_amount():
    package = evidence()
    package['usage']['unavailable_minutes'] = 0
    agreement = ta.evaluate(entry(), package)
    assert agreement['credit'] is None and agreement['credit_percent'] == '0'
    assert agreement['evaluation'] == '44,640 of 44,640 UTC minutes were available (100.000%), so no credit tier applies.'


@pytest.mark.parametrize('cap, rates, amount', [
    # Cap 30%: the second tier's 35% is capped -> 30% x 12,000.00 = 3,600.00 (tiers 15% and 30% stay distinct).
    ('30', [(99_900_000, 30_000_000), (99_990_000, 15_000_000)], '3600.00'),
    # Cap 10%: both tiers are capped to 10%, the same rate, so one tier below the commitment -> 1,200.00.
    ('10', [(99_990_000, 10_000_000)], '1200.00'),
])
def test_cap_applies_when_a_tier_credit_would_exceed_it(cap, rates, amount):
    values = dict(EXPECTED['terms'], credit_cap_percent=cap)
    manifest, _ = ta.overlay_from_values(values, vendor='Halcyon Grid Services', document=evidence()['overlay'])
    assert [(t['below_units'], t['credit_units']) for t in manifest['tiers']] == rates
    agreement = ta.evaluate(entry(values), evidence())
    assert agreement['credit']['amount'] == amount and agreement['credit_percent'] == cap


def test_reading_with_no_evidence_has_no_credit():
    for document_id in ('pasted-20261110-1', '../halcyon-c', ''):
        assert ta.load_evidence(document_id) is None
    agreement = ta.on_reading(entry(document_id='pasted-20261110-1'))
    assert agreement['credit'] is None and agreement['evaluation'] == 'Needs usage evidence'
    assert (agreement['month'], agreement['availability_percent'], agreement['credit_percent'], agreement['monthly_fee']) == (
        None, None, None, None)
    assert agreement['state'] == 'SHADOW' and agreement['read_by'] == 'template:halcyon-availability-addendum/1'


def test_the_maintenance_notice_term_may_be_missing_because_the_engine_does_not_use_it():
    # Some contracts give notice in days or business days; the template then has no hours value. The engine takes
    # exclusion-adjusted minutes, so the estimate is unchanged: 35% x USD 12,000.00 = USD 4,200.00.
    values = dict(EXPECTED['terms'], maintenance_notice_hours=None)
    agreement = ta.evaluate(entry(values), evidence())
    assert agreement['credit'] == {'amount': '4200.00', 'currency': 'USD', 'stage': 'ESTIMATED'}
    assert {'label': 'Scheduled-maintenance notice (read by the template)',
            'value': 'Not stated in hours in this contract (the authored usage is exclusion-adjusted)'} in agreement['inputs']


def test_a_missing_cap_gives_no_credit():
    # A cap may exist in another form (for example over twelve months), so the estimate is refused, not guessed.
    agreement = ta.evaluate(entry(dict(EXPECTED['terms'], credit_cap_percent=None)), evidence())
    assert agreement['credit'] is None and 'no value for Credit cap' in agreement['evaluation']


def test_missing_term_gives_no_credit_and_names_the_term():
    values = dict(EXPECTED['terms'], tier_2_credit_percent=None)
    agreement = ta.evaluate(entry(values), evidence())
    assert agreement['credit'] is None and agreement['credit_percent'] is None
    assert agreement['evaluation'] == ('Cannot estimate a credit: the read has no value for Credit, second tier '
                                       '(tier_2_credit_percent).')


@pytest.mark.parametrize('change, sentence', [
    (dict(credit_application='refund'), 'applies credits as refund'),
    (dict(measurement_period='calendar_quarter'), 'measures availability by calendar quarter'),
    (dict(tier_2_threshold_percent='99.995'), 'The engine refused these terms: Overlapping or nonmonotonic credit tiers.'),
])
def test_terms_the_engine_cannot_express_are_refused(change, sentence):
    agreement = ta.evaluate(entry(dict(EXPECTED['terms'], **change)), evidence())
    assert agreement['credit'] is None and sentence in agreement['evaluation']


def test_evidence_for_another_customer_is_not_used():
    other = entry()
    other['document']['customer'] = 'Larkspur Analytics LLC'
    agreement = ta.evaluate(other, evidence())
    assert agreement['credit'] is None and 'different vendor or customer' in agreement['evaluation']


def corvid_row():
    from tests.test_demo_opportunities import recorded_manifest
    manifest, extraction = recorded_manifest()
    package = corvid.load()
    result = engine(manifest, package['overlay'], corvid.facts(package), 'bears')
    return corvid.build({'manifest': manifest, 'extraction': extraction}, result, package)


def test_opportunity_has_corvids_shape_and_says_where_it_came_from():
    row = ta.opportunity(entry(), evidence())
    reference = corvid_row()
    assert reference is not None
    assert set(row) == set(reference) | {'source'} and row['source'] == 'template'
    assert set(reference['agreement']) <= set(row['agreement'])
    assert set(row['evaluation']) == set(reference['evaluation']) and set(row['invoice']) == set(reference['invoice'])
    assert row['agreement']['read_by'].startswith('template:') and row['agreement']['id'] == 'HGS-PAA-2026-0457'
    assert (row['vendor'], row['period'], row['kind'], row['stage'], row['amount'], row['currency'], row['route']) == (
        'Halcyon Grid Services', '2026-10', 'service_credit', 'ESTIMATED', '4200.00', 'USD', 'agreements')
    assert row['agreement']['state'] == 'SHADOW' and row['evaluation']['outcome'] == 'ELIGIBLE'
    assert row['invoice']['id'] == 'HGS-INV-2026-10-3318' and row['invoice']['total'] == '12000.00'
    assert ta.opportunity(entry(document_id='pasted-1')) is None


def test_wiring_sets_on_reading_and_lists_latest_estimates_only():
    service = StandIn([entry(read_at='2026-11-10T13:05:00Z', reading_id='rd_old'),
                       entry(read_at='2026-11-10T13:09:00Z', reading_id='rd_new'),
                       entry(document_id='pasted-1', reading_id='rd_pasted')])
    workflow = SimpleNamespace()
    app = SimpleNamespace(state=SimpleNamespace(template_builds=service, workflow=workflow))
    assert ta.connect(app) is service and service.on_reading is ta.on_reading
    # What the engine does on an accepted read: store on_reading's return as the reading's agreement.
    service.set_agreement('tb_3f9a2c', 'rd_new', service.on_reading(service.entries[1]))
    assert service.attached[('tb_3f9a2c', 'rd_new')]['credit']['amount'] == '4200.00'
    p = SimpleNamespace(tenant='bears')
    [row] = workflow.template_opportunities(p)
    assert row['agreement']['reading_id'] == 'rd_new'
    # Without --template-builder nothing extra is listed and nothing is wired.
    bare = SimpleNamespace(state=SimpleNamespace(workflow=SimpleNamespace()))
    assert ta.connect(bare) is None and not hasattr(bare.state.workflow, 'template_opportunities')
    assert ta.listed(None) == []


def test_portfolio_appends_template_rows_after_corvid(monkeypatch):
    monkeypatch.setattr(corvid, '_corvid', lambda path, p, **_: [{'vendor': 'Corvid Data Cooperative'}])
    p = SimpleNamespace(tenant='bears')
    assert corvid.opportunities('unused', p) == [{'vendor': 'Corvid Data Cooperative'}]
    rows = corvid.opportunities('unused', p, templates=lambda principal: [{'vendor': 'Halcyon Grid Services'}])
    assert [r['vendor'] for r in rows] == ['Corvid Data Cooperative', 'Halcyon Grid Services']


def test_on_reading_never_raises():
    agreement = ta.on_reading({'template': {'id': 'x/1'}, 'document': {'id': 'halcyon-c'}, 'values': None,
                               'vendor': 'Halcyon Grid Services'})
    assert agreement['credit'] is None and agreement['state'] == 'SHADOW'
