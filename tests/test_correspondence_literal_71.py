"""Narrow source-literal loss controls; these do not establish semantic truth."""
import pytest

from uptime.correspondence_blocks import hydrate_blocks
from uptime.correspondence_interpretation import proposal_for_review
from test_correspondence_blocks_71 import P, annotate, context_for


@pytest.mark.parametrize('text,slots', [
    ('USD 17.20 is approved; USD 44.93 remains declined.', [('award', 'USD 17.20', 0)]),
    ('USD 17.20 is approved for April 2028.', [('award', 'USD 17.20', 0)]),
    ('USD 17.20 is approved for 2028-04-15.', [('award', 'USD 17.20', 0), ('period', '2028-04', 0)]),
    ('USD 17.20 is approved, against USD 17.20 requested.', [('award', 'USD 17.20', 0)]),
    ('The filing for 2028-04 was late.', []),
])
def test_potentially_supported_mapping_refuses_unassigned_money_or_dates(text, slots):
    with pytest.raises(ValueError, match='literal unassigned'):
        hydrate_blocks(text, annotate(text, ('substantive', [P('award' if slots else 'time_bar', slots=slots)])))


def test_literal_conservation_accepts_distinct_award_remainder_and_period():
    text = 'Crédit: USD 17.20 is approved for April 2028; USD 44.93 remains declined.'
    slots = [('award', 'USD 17.20', 0), ('remainder', 'USD 44.93', 0), ('period', 'April 2028', 0)]
    interpretation = hydrate_blocks(text, annotate(text, ('substantive', [P('award', slots=slots)])))
    proposal = proposal_for_review(context_for(text), interpretation)
    assert proposal.reason == 'award' and proposal.amount == '17.20'


@pytest.mark.parametrize('changes', [
    {'family': 'unsupported'}, {'polarity': 'negative'}, {'modality': 'conditional'},
    {'referent': 'other_claim'}, {'conditions': [('If approved', 0)]},
])
def test_nonactionable_meanings_do_not_require_invented_financial_roles(changes):
    text = 'If approved, USD 17.20 may be issued for April 2028.'
    proposition = P(**{'family': 'award', **changes})
    interpretation = hydrate_blocks(text, annotate(text, ('substantive', [proposition])))
    assert proposal_for_review(context_for(text), interpretation).reason == 'unknown'
