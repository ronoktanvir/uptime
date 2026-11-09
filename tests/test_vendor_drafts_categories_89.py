"""Generated draft categories (ONB-4): timezone receipts and private filing amendment months.

Expected figures are hand-computed. Every draft must equal the real evaluator. Drafts remain the adapter's own
reading with a placeholder fee; they are never the independent suite.
"""
from uptime import vendor_requirements as req
from uptime.vendor_eval import evaluate
from uptime.vendor_terms import Document, Overlay, bind_overlay, compile_terms

from test_vendor_catalog import DOC, OVERLAY

QUOTE = 'Claims must be received within 19 calendar days after month end.'
AMENDED = OVERLAY | {'override': {'filing_days': 19, 'quote': QUOTE, 'source_ref': 'private-addendum-section-2',
                                  'effective_from': '2026-07-01'}}


def drafts_for(overlay):
    manifest = compile_terms(Document(**DOC))
    bound = bind_overlay(manifest, Overlay(**overlay))
    drafts = req.scenario_drafts(manifest, bound)
    assert drafts['generated'], drafts['reason']
    for scenario in drafts['scenarios']:
        result = evaluate(manifest, bound, scenario['facts'], 'demo-tenant')
        assert {'outcome': result['outcome'], 'amount': result['amount']} == scenario['derived'], scenario['name']
    return {s['name']: s for s in drafts['scenarios']}


def test_timezone_drafts_convert_offsets_and_refuse_a_missing_offset():
    by_name = drafts_for(OVERLAY)
    # April 2026; the 12-day source window closes 2026-05-13T00:00Z (exclusive).
    assert by_name['Last timely second stated in UTC-07:00']['facts']['received_at'] == '2026-05-12T16:59:59-07:00'
    assert by_name['Last timely second stated in UTC-07:00']['derived'] == {'outcome': 'ELIGIBLE', 'amount': '125.00'}
    assert by_name['Window close stated in UTC+05:30']['facts']['received_at'] == '2026-05-13T05:30:00+05:30'
    assert by_name['Window close stated in UTC+05:30']['derived']['outcome'] == 'INELIGIBLE'
    assert by_name['Receipt time without a UTC offset']['derived']['outcome'] == 'INSUFFICIENT_EVIDENCE'


def test_amendment_month_drafts_use_the_private_window_only_from_its_month():
    by_name = drafts_for(AMENDED)
    # The draft month (April) keeps the 12-day source rule.
    assert by_name['Received at the last timely second']['facts']['received_at'] == '2026-05-12T23:59:59Z'
    # July 2026: 44,640 minutes; 0.25% is 111.6, so 112 minutes down is the first below 99.75% (12.5% of $1,000).
    # The 19-day private window closes 2026-08-20T00:00Z (exclusive).
    timely = by_name['Amendment month 2026-07: last timely second of the private 19-day window']
    assert timely['facts']['month'] == '2026-07' and timely['facts']['eligible_downtime_minutes'] == 112
    assert timely['facts']['received_at'] == '2026-08-19T23:59:59Z'
    assert timely['derived'] == {'outcome': 'ELIGIBLE', 'amount': '125.00'}
    closed = by_name['Amendment month 2026-07: private window closes']
    assert closed['facts']['received_at'] == '2026-08-20T00:00:00Z' and closed['derived']['outcome'] == 'INELIGIBLE'


def test_no_amendment_drafts_without_an_override_or_from_the_first_governed_month():
    assert not any(name.startswith('Amendment month') for name in drafts_for(OVERLAY))
    whole = AMENDED | {'override': AMENDED['override'] | {'effective_from': OVERLAY['effective_from']}}
    by_name = drafts_for(whole)
    assert not any(name.startswith('Amendment month') for name in by_name)
    assert by_name['Received at the last timely second']['facts']['received_at'] == '2026-05-19T23:59:59Z'
