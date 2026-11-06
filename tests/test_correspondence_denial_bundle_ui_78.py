"""Authored scripted browser checks; no actual-human review accuracy claim."""
from copy import deepcopy
import pytest
from playwright.sync_api import expect
import test_correspondence_model_jobs_ui_75 as harness
from test_correspondence_denial_bundle_78 import TEXT, bundle
from test_correspondence_interpretation import meaning, span


@pytest.fixture
def ui(monkeypatch):
    js=harness.JS.replace("if(path.endsWith('/reviews'))return {id:'review'};", "if(path.endsWith('/reviews')){if(F.delayReview)await new Promise(r=>window.releaseReview=r);return {id:'review'};}")
    js=js.replace("if(path.endsWith('/preview'))return {", "if(path.endsWith('/preview'))return F.preview||{")
    monkeypatch.setattr(harness,'JS',js)
    return harness.page_for


def fixture(value,candidate=None,text=TEXT):
    primary=next(i for i,p in enumerate(value['propositions']) if p['family']!='award')
    data=harness.payload(text,value,None,[] if candidate is None else [candidate])
    return dict(data=data,submitted=None,states=[],preview=dict(disposition='RESPONSE_DRAFTED',reported_award=None,prepare_allowed=False,
                primary_proposition_index=primary,reviewed_interpretation=value,
                retained_propositions=[dict(index=i,**p) for i,p in enumerate(value['propositions']) if i!=primary]))


def decide(page,count=2,verdict='accept'):
    for i in range(count):
        suffix='' if i==0 else f' (proposition {i+1})'
        page.get_by_label('Your decision'+suffix,exact=True).select_option(verdict)
        page.get_by_label('Explanation of source meaning and any difference'+suffix,exact=True).fill('Scripted source review preserves each separate assertion.')
    for box in page.get_by_role('checkbox').all():box.check()


def review_body(page):
    return next(c['body'] for c in page.evaluate('window.calls') if c['path'].endswith('/reviews'))


def test_restored_reversed_bundle_keeps_all_propositions_and_preview(ui):
    value=bundle(reverse=True).model_dump()
    with ui(fixture(value)) as page:
        expect(page.get_by_label('Main assertion',exact=True)).to_have_value('award')
        expect(page.get_by_label('Main assertion (proposition 2)',exact=True)).to_have_value('time_bar')
        expect(page.get_by_text(TEXT,exact=True).first).to_be_visible()
        for label in ['Your decision','Your decision (proposition 2)']:
            expect(page.get_by_label(label,exact=True)).to_have_value('')
        expect(page.get_by_role('checkbox').nth(0)).not_to_be_checked()
        decide(page)
        page.get_by_role('button',name='Save meaning review and inspect preview').click()
        expect(page.get_by_role('heading',name='Deterministic preview')).to_be_visible()
        assert review_body(page)['interpretation']==value
        expect(page.get_by_text('Primary proposition 2 (time_bar) is the only input to the deterministic disposition.',exact=True)).to_be_visible()
        expect(page.get_by_text('Retained proposition 1:',exact=False)).to_be_visible()
        assert len(review_body(page)['resolutions'])==2
        page.get_by_label('Polarity',exact=True).select_option('uncertain')
        expect(page.get_by_role('heading',name='Deterministic preview')).to_have_count(0)
        expect(page.get_by_role('checkbox').nth(0)).not_to_be_checked()
        expect(page.get_by_label('Your decision',exact=True)).to_have_value('')


def test_explicit_candidate_load_preserves_slots_conditions_and_duplicate_spans(ui):
    text='No credit. No credit.'
    value=bundle(text,reverse=True).model_dump()
    value['propositions'][0]['source']=dict(start=11,end=21,quote='No credit.')
    value['propositions'][0]['conditions']=[dict(start=11,end=13,quote='No')]
    candidate=dict(id='5'*64,origin='model',interpretation=value)
    original=meaning(text).model_dump()
    with ui(fixture(original,candidate,text)) as page:
        page.get_by_text('Requested interpretation — requires your review',exact=True).click()
        page.get_by_role('button',name='Compare this suggestion').click()
        expect(page.get_by_label('Main assertion (proposition 2)',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Load these propositions into your review draft').click()
        expect(page.get_by_label('Your decision (proposition 2)',exact=True)).to_have_value('')
        expect(page.get_by_label('Exact source passage for this proposition (copy from the reply)',exact=True)).to_have_value('No credit.')
        decide(page,verdict='correct')
        page.get_by_role('button',name='Save meaning review and inspect preview').click()
        expect(page.get_by_role('heading',name='Deterministic preview')).to_be_visible()
        assert review_body(page)['interpretation']==value
        assert review_body(page)['candidate_id']==candidate['id']


def test_add_assertion_clears_decisions_and_renders_separate_editor(ui):
    value=meaning(TEXT).model_dump()
    with ui(fixture(value)) as page:
        decide(page,count=1)
        page.get_by_role('button',name='Add another proposition').click()
        expect(page.get_by_label('Main assertion (proposition 2)',exact=True)).to_have_value('')
        expect(page.get_by_label('Your decision (proposition 2)',exact=True)).to_have_value('')
        expect(page.get_by_label('Your decision',exact=True)).to_have_value('')
        expect(page.get_by_role('checkbox').nth(0)).not_to_be_checked()
        assert not [c for c in page.evaluate('window.calls') if c['body']]


def test_edit_during_save_does_not_publish_stale_preview(ui):
    f=fixture(bundle().model_dump());f['delayReview']=True
    with ui(f) as page:
        decide(page)
        page.get_by_role('button',name='Save meaning review and inspect preview').click()
        page.wait_for_function('typeof window.releaseReview === "function"')
        page.get_by_label('Polarity (proposition 2)',exact=True).select_option('uncertain')
        page.evaluate('window.releaseReview()')
        expect(page.get_by_role('status')).to_contain_text('review draft changed while saving')
        expect(page.get_by_role('heading',name='Deterministic preview')).to_have_count(0)
        expect(page.get_by_role('checkbox').nth(0)).not_to_be_checked()
