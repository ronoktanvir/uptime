"""New authored controls after public76 unblinding; no inference or human-study claim."""
from copy import deepcopy
import pytest
from uptime.contracts import fingerprint
from uptime.correspondence_interpretation import Entry, Interpretation, Prepare, Review, primary_proposition_index, proposal_for_review
from test_correspondence import env, ID, REVIEWER
from test_correspondence_interpretation import meaning, span, start

TEXT = 'Our intake timestamp fell outside the permitted filing interval. No service credit is due.'


def bundle(text=TEXT, family='time_bar', reverse=False, slots=()):
    value=meaning(text,family,slots=slots).model_dump()
    denial=meaning(text,'award',polarity='negative').model_dump()['propositions'][0]
    value['propositions'].append(denial)
    if reverse:value['propositions'].reverse()
    return Interpretation.model_validate(value)


def context(text):
    return dict(text=text,scope={'month':'2026-06'},requested='19.80',filing_fields=[])


def body(ctx,annotation,verdicts=('accept','accept'),candidate=None):
    return Review(context_digest=ctx['digest'],interpretation=annotation,candidate_id=candidate,
                  resolutions=[dict(proposition=i,verdict=v,explanation='Scripted complete source review; all assertions remain explicit.') for i,v in enumerate(verdicts)],
                  residuals_reviewed=True,complete_meaning_reviewed=True)


@pytest.mark.parametrize('family',['availability','time_bar','maintenance'])
@pytest.mark.parametrize('reverse',[False,True])
def test_narrow_bundle_preserves_both_orders_and_no_award(family,reverse):
    text={'availability':'Availability meets the target. No credit is due.',
          'time_bar':TEXT,'maintenance':'Reported downtime occurred during maintenance. No credit is due.'}[family]
    value=bundle(text,family,reverse)
    proposal=proposal_for_review(context(text),value)
    assert proposal.reason==family and proposal.amount is None
    assert primary_proposition_index(context(text),value)==int(reverse)
    assert len(value.propositions)==2


@pytest.mark.parametrize('text,slots',[
    ('Availability for June 2026 was 99.96%, which meets the 99.90% target. No credit is due.', [('period','June 2026')]),
    ('Availability was 99.96 percent. No credit is due.',[]),
])
def test_availability_measurements_are_not_reported_credit(text,slots):
    assert proposal_for_review(context(text),bundle(text,'availability',slots=slots)).reason=='availability'


@pytest.mark.parametrize('change',[
    'positive_denial','quoted_denial','conditional_denial','other_claim','ambiguous','denial_condition','denial_money',
    'denial_artifact','denial_scope','denial_fields','third','competing','artifact','component','scope_error','filing_fields','downtime',
    'negative_primary','quoted_primary','primary_condition','unsupported_segment'])
def test_other_bundle_shapes_remain_unknown(change):
    value=bundle().model_dump();primary,denial=value['propositions']
    if change=='positive_denial':denial['polarity']='positive'
    elif change=='quoted_denial':denial['modality']='quoted'
    elif change=='conditional_denial':denial['modality']='conditional'
    elif change in {'other_claim','ambiguous'}:denial['referent']=change
    elif change=='denial_condition':denial['conditions']=[span(TEXT,'No service credit is due.')]
    elif change=='denial_money':denial['slots']=[dict(name='award',source=span(TEXT,'credit'))]
    elif change=='denial_artifact':denial['artifact_type']='resource_log'
    elif change=='denial_scope':denial['scope_field']='account'
    elif change=='denial_fields':denial['filing_fields']=['receipt']
    elif change=='third':value['propositions'].append(deepcopy(primary))
    elif change=='competing':denial.update(family='maintenance',polarity='positive')
    elif change in {'artifact','component','scope_error','filing_fields','downtime'}:primary['family']=change
    elif change=='negative_primary':primary['polarity']='negative'
    elif change=='quoted_primary':primary['modality']='quoted'
    elif change=='primary_condition':primary['conditions']=[span(TEXT,'filing interval')]
    elif change=='unsupported_segment':value['segments'][0]['role']='unsupported'
    assert proposal_for_review(context(TEXT),Interpretation.model_validate(value)).reason=='unknown'


@pytest.mark.parametrize('tail',[
    'No credit unless logs arrive.', 'No credit if records are absent.', 'No credit pending review.',
    'No credit subject to review.', 'No credit until another decision.', 'No credit except under a settlement.',
    'No credit beyond USD 5.', 'No credit beyond €5.', 'No credit beyond 5 dollars.', 'No further credit.',
    'No remaining service credit.', 'No credit beyond the 10% courtesy credit applied.',
    'No credit for March 2026.', 'No credit for 2026-07.', 'No credit for 4/5/2026.',
    'No credit for 15 minutes.', 'No credit for one hour.',
])
def test_full_source_loss_checks_do_not_trust_empty_secondary_slots(tail):
    text='Availability met the target. '+tail
    assert proposal_for_review(context(text),bundle(text,'availability')).reason=='unknown'


@pytest.mark.parametrize('text',[
    'Availability met target. A 10% credit was applied. No credit is due.',
    'Availability met target. 10% applied. No credit is due.',
])
def test_percentage_without_performance_context_is_not_silently_lost(text):
    assert proposal_for_review(context(text),bundle(text,'availability')).reason=='unknown'


def test_date_in_separate_denial_cannot_be_claimed_by_primary():
    first='Availability meets the target.\n'; second='No credit for June 2026.';text=first+second
    value=bundle(text,'availability').model_dump()
    value['propositions'][0]['source']=span(text,first)
    value['propositions'][1]['source']=span(text,second)
    assert proposal_for_review(context(text),Interpretation.model_validate(value)).reason=='unknown'


def test_assigned_wrong_month_stays_unknown():
    text='Availability for July 2026 meets target. No credit.'
    assert proposal_for_review(context(text),bundle(text,'availability',slots=[('period','July 2026')])).reason=='unknown'


@pytest.mark.parametrize('verdict',['accept','correct'])
def test_omission_requires_explicit_reject(env,verdict):
    desk,ctx=start(env,TEXT);value=bundle()
    desk.blind(REVIEWER,ID,Entry(context_digest=ctx['digest'],interpretation=value))
    with pytest.raises(ValueError,match='explicitly rejected'):
        desk.review(REVIEWER,ID,body(ctx,meaning(TEXT),('accept',verdict)))
    rid=desk.review(REVIEWER,ID,body(ctx,meaning(TEXT),('accept','reject')))['id']
    preview=desk.preview(REVIEWER,ID,rid)
    assert preview['interpretation']['reason']=='unknown' and not preview['prepare_allowed']
    assert preview['alignment'][1]['reviewed'] is None
    assert preview['alignment'][1]['blind']==fingerprint(value.model_dump()['propositions'][1])


@pytest.mark.parametrize('reverse',[False,True])
def test_review_preview_preserves_denial_and_only_drafts_with_existing_authority(env,reverse):
    desk,ctx=start(env,TEXT);value=bundle(reverse=reverse);before=env.get()
    desk.blind(REVIEWER,ID,Entry(context_digest=ctx['digest'],interpretation=value))
    rid=desk.review(REVIEWER,ID,body(ctx,value))['id']; preview=desk.preview(REVIEWER,ID,rid)
    assert preview['reviewed_interpretation']==value.model_dump()
    assert preview['primary_proposition_index']==int(reverse)
    assert preview['retained_propositions'][0]['polarity']=='negative'
    assert preview['retained_propositions'][0]['effect']=='informational_only'
    assert preview['reported_award'] is None and preview['external_actions']==[] and preview['ledger_unchanged']
    assert env.get()==before
    assert preview['prepare_allowed']
    prepared=desk.prepare(REVIEWER,ID,Prepare(review_id=rid,preview_digest=preview['digest']))
    assert prepared['approval'] is None and prepared['ledger']==before['ledger'] and prepared['submissions']==before['submissions']
    with pytest.raises(ValueError):env.act('submit-response')


def test_reordered_review_requires_correction_and_keeps_content_alignment(env):
    desk,ctx=start(env,TEXT);value=bundle();reordered=bundle(reverse=True)
    desk.blind(REVIEWER,ID,Entry(context_digest=ctx['digest'],interpretation=value))
    with pytest.raises(ValueError,match='explicit correction'):
        desk.review(REVIEWER,ID,body(ctx,reordered))
    rid=desk.review(REVIEWER,ID,body(ctx,reordered,('correct','correct')))['id']
    preview=desk.preview(REVIEWER,ID,rid)
    assert preview['primary_proposition_index']==1
    assert [row['reviewed_matches_blind'] for row in preview['alignment']]==[[1],[0]]
    assert preview['alignment'][0]['reviewed']==fingerprint(reordered.model_dump()['propositions'][0])


def test_candidate_only_secondary_cannot_disappear_as_correction(env):
    desk,ctx=start(env,TEXT);independent=meaning(TEXT);suggested=bundle()
    desk.blind(REVIEWER,ID,Entry(context_digest=ctx['digest'],interpretation=independent))
    candidate=desk.candidate(REVIEWER,ID,Entry(context_digest=ctx['digest'],interpretation=suggested))['id']
    with pytest.raises(ValueError,match='explicitly rejected'):
        desk.review(REVIEWER,ID,body(ctx,independent,('accept','correct'),candidate))
    rid=desk.review(REVIEWER,ID,body(ctx,independent,('accept','reject'),candidate))['id']
    preview=desk.preview(REVIEWER,ID,rid)
    assert preview['interpretation']['reason']=='unknown'
    assert preview['alignment'][1]['blind'] is None
    assert preview['alignment'][1]['candidate']==fingerprint(suggested.model_dump()['propositions'][1])
    assert preview['alignment'][1]['reviewed'] is None and preview['alignment'][1]['verdict']=='reject'


@pytest.mark.parametrize('code',['USD','EUR','GBP','JPY','CAD','AUD','NZD','CHF','CNY','RMB','HKD','SGD','INR','MXN','BRL','SEK','NOK','DKK','ZAR','KRW','PLN','ILS','AED'])
@pytest.mark.parametrize('case',['upper','lower','title'])
def test_all_listed_currency_codes_veto_source_money_regardless_of_case(code,case):
    # 'recorded' deliberately isolates the currency guard from the issuance guard.
    text=f'Availability met the target. {getattr(code,case)()} 10.00 was recorded. No credit is due.'
    annotation=bundle(text,'availability')
    before=annotation.model_dump()
    assert proposal_for_review(context(text),annotation).reason=='unknown'
    assert annotation.model_dump()==before


@pytest.mark.parametrize('clause',[
    'cad 10.00 was issued.', '10.00 was issued.', 'We credited 10.00.', 'We paid 10.00.',
    '10.00 was disbursed.', 'A payment of 10.00 was issued.', 'A credit of 10.00 was posted.',
])
def test_unassigned_decimal_issuance_cannot_be_dropped_by_denial_bundle(clause):
    text=f'Availability met the target. {clause} No credit is due.'
    annotation=bundle(text,'availability')
    before=annotation.model_dump()
    assert proposal_for_review(context(text),annotation).reason=='unknown'
    assert annotation.model_dump()==before


@pytest.mark.parametrize('value',['30','1,000','1.000','1 000','1\u00a0000','1\u202f000','1,000.00','1.000,00'])
def test_unassigned_integer_or_grouped_issuance_cannot_be_dropped(value):
    text=f'Availability met the target. We issued {value}. No credit is due.'
    annotation=bundle(text,'availability')
    before=annotation.model_dump()
    assert proposal_for_review(context(text),annotation).reason=='unknown'
    assert annotation.model_dump()==before
