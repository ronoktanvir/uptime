"""Public synthetic interpretation controls; scripted principals are not human-study evidence."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
import json

import pytest

from uptime.contracts import Principal
from uptime.correspondence_interpretation import Entry, Interpretation, ModelRequest, Prepare, Review, proposal_for_review, validate_grounding, visible_source
from uptime.correspondence_model import MODEL, PublicInterpretationAdapter, serialized_request
from uptime.correspondence_review import InterpretationDesk
from test_correspondence import env, ID, REVIEWER, VIEWER
from test_correspondence_service import service, filed
from test_correspondence_resource import deliver

TEXT='Our intake timestamp fell outside the permitted filing interval.'


def span(text, quote=None):
    quote=quote or text
    start=text.index(quote)
    return dict(start=len(text[:start].encode()),end=len(text[:start+len(quote)].encode()),quote=quote)


def meaning(text, family='time_bar', slots=(), **changes):
    proposition=dict(family=family,source=span(text),polarity='positive',modality='asserted',referent='current_claim',
                     conditions=[],slots=[dict(name=name,source=span(text,quote)) for name,quote in slots],
                     artifact_type=None,scope_field=None,filing_fields=[])
    proposition.update(changes)
    return Interpretation.model_validate(dict(propositions=[proposition],segments=[dict(source=span(text),role='substantive')]))


def start(env, text=TEXT):
    env.file()
    assert env.message(text)['stage']=='HUMAN_REVIEW'
    desk=InterpretationDesk(env.desk)
    context=desk.view(REVIEWER,ID)['context']
    return desk,context


def review(desk, context, interpretation, candidate_id=None):
    desk.blind(REVIEWER,ID,Entry(context_digest=context['digest'],interpretation=interpretation))
    body=Review(context_digest=context['digest'],interpretation=interpretation,candidate_id=candidate_id,
                resolutions=[dict(proposition=0,verdict='accept',explanation='Reviewed the entire signed message and its current claim referent.')],
                residuals_reviewed=True,complete_meaning_reviewed=True)
    return desk.review(REVIEWER,ID,body)['id']


def test_manual_review_and_preview_are_inert_until_draft_then_existing_approval(env):
    desk,context=start(env)
    before=env.get()
    rid=review(desk,context,meaning(TEXT))
    preview=desk.preview(REVIEWER,ID,rid)
    assert preview['prepare_allowed'] and preview['packet']['requested']==before['ledger']['claimed']
    assert env.get()==before
    draft=desk.prepare(REVIEWER,ID,Prepare(review_id=rid,preview_digest=preview['digest']))
    assert draft['stage']=='RESPONSE_DRAFTED' and draft['approval'] is None
    assert draft['submissions']==before['submissions'] and draft['ledger']==before['ledger']
    assert draft['replies'][0]['text']==TEXT and draft['replies'][0]['original_reason']=='unknown'
    assert draft['replies'][0]['reviewed_interpretation']==rid
    assert desk.prepare(REVIEWER,ID,Prepare(review_id=rid,preview_digest=preview['digest']))==draft
    with pytest.raises(ValueError):
        env.act('submit-response')
    env.act('approve-response')
    env.now+=timedelta(days=1)
    sent=env.act('submit-response')
    assert len(sent['submissions'])==2 and sent['submissions'][1]['packet']['in_reply_to']==before['submissions'][0]['id']
    assert sent['ledger']['awarded']==sent['ledger']['applied']=='0.00'


@pytest.mark.parametrize('change',['scope','text','terms','source','amount','state'])
def test_all_original_context_pins_are_server_derived_and_cannot_be_changed(env,change):
    desk,context=start(env)
    context[{'scope':'scope','text':'text','terms':'contract_version','source':'contract_source_sha256','amount':'requested','state':'state_digest'}[change]]='different'
    from uptime.contracts import fingerprint
    digest=fingerprint({k:v for k,v in context.items() if k!='digest'})
    with pytest.raises(ValueError):
        desk.blind(REVIEWER,ID,Entry(context_digest=digest,interpretation=meaning(TEXT)))
    assert env.get()['stage']=='HUMAN_REVIEW'


def test_stale_expired_cross_tenant_and_viewer_reviews_cannot_prepare(env):
    desk,context=start(env)
    with pytest.raises(PermissionError):
        desk.blind(VIEWER,ID,Entry(context_digest=context['digest'],interpretation=meaning(TEXT)))
    with pytest.raises(KeyError):
        desk.view(Principal('elsewhere','operator','reviewer'),ID)
    rid=review(desk,context,meaning(TEXT))
    env.now+=timedelta(minutes=31)
    with pytest.raises(ValueError):
        desk.preview(REVIEWER,ID,rid)
    assert env.get()['stage']=='HUMAN_REVIEW'


def test_later_signed_message_invalidates_accepted_semantics(env):
    desk,context=start(env)
    rid=review(desk,context,meaning(TEXT))
    preview=desk.preview(REVIEWER,ID,rid)
    env.message('A settlement also governs this request.','another-message')
    with pytest.raises(ValueError):
        desk.prepare(REVIEWER,ID,Prepare(review_id=rid,preview_digest=preview['digest']))
    assert env.get()['stage']=='HUMAN_REVIEW'


@pytest.mark.parametrize('change',['offset','quote','gap','overlap','courtesy','slot','unsupported'])
def test_grounding_and_residual_obligation_falsifiers(change):
    text='An itemized invoice is required. A settlement extinguished your rights.'
    value=meaning(text,'artifact',artifact_type='invoice_detail').model_dump()
    if change=='offset': value['propositions'][0]['source']['start']=1
    if change=='quote': value['propositions'][0]['source']['quote']='Made up statement'
    if change=='gap': value['segments'][0]['source']['start']=1
    if change=='overlap': value['segments']*=2
    if change=='courtesy': value['segments'][0]['role']='courtesy'
    if change=='slot': value['propositions'][0]['slots']=[dict(name='artifact_ref',source=dict(start=0,end=8,quote='BILL-999'))]
    if change=='unsupported':
        value['segments'][0]['role']='unsupported'
        annotation=Interpretation.model_validate(value)
        assert proposal_for_review(dict(text=text,scope={'month':'2028-04'},requested='46.25',filing_fields=[]),annotation).reason=='unknown'
    else:
        with pytest.raises(ValueError): validate_grounding(text,Interpretation.model_validate(value))


@pytest.mark.parametrize('family,changes',[
    ('award',{'modality':'conditional'}),('time_bar',{'polarity':'negative'}),('time_bar',{'referent':'ambiguous'}),
    ('award',{'modality':'quoted'}),('award',{'modality':'future'}),('unsupported',{})])
def test_semantic_uncertainty_cannot_prepare_a_disposition(env,family,changes):
    desk,context=start(env)
    rid=review(desk,context,meaning(TEXT,family,**changes))
    preview=desk.preview(REVIEWER,ID,rid)
    assert preview['interpretation']['reason']=='unknown' and not preview['prepare_allowed']
    with pytest.raises(ValueError): desk.prepare(REVIEWER,ID,Prepare(review_id=rid,preview_digest=preview['digest']))
    assert env.get()['stage']=='HUMAN_REVIEW' and env.get()['ledger']['awarded']=='0.00'


def test_invisible_source_is_preserved_but_cannot_prepare(env):
    text='Your claim\u202e arrived outside the window.'
    desk,context=start(env,text)
    assert context['text']==text and 'U+202E' in desk.view(REVIEWER,ID)['visible_text']
    rid=review(desk,context,meaning(text))
    assert not desk.preview(REVIEWER,ID,rid)['prepare_allowed']


def test_reviewed_award_is_informational_only_and_preserves_pending_balance(env):
    text='A service credit of USD 17.20 is now on our approved list; USD 44.93 remains declined.'
    desk,context=start(env,text)
    assert context['requested']=='62.13'
    rid=review(desk,context,meaning(text,'award',slots=[('award','USD 17.20'),('remainder','USD 44.93')]))
    before=env.get()
    preview=desk.preview(REVIEWER,ID,rid)
    assert preview['reported_award']=='17.20' and not preview['prepare_allowed']
    assert env.get()==before and before['ledger']['disputed_remainder']=='62.13'
    with pytest.raises(ValueError): desk.prepare(REVIEWER,ID,Prepare(review_id=rid,preview_digest=preview['digest']))


def test_provider_requires_blind_entry_and_exact_full_outbound_manifest(env):
    desk,context=start(env)
    result=json.dumps(meaning(TEXT).model_dump())
    calls=[]
    def provider(payload):
        calls.append(payload)
        return dict(model=MODEL,text=result)
    request=serialized_request(context)
    desk.adapter=PublicInterpretationAdapter(enabled=True,allowed_requests=[sha256(request).hexdigest()],provider=provider)
    with pytest.raises(ValueError): desk.model(REVIEWER,ID,ModelRequest(context_digest=context['digest']))
    assert not calls
    desk.blind(REVIEWER,ID,Entry(context_digest=context['digest'],interpretation=meaning(TEXT)))
    before=env.get()
    candidate=desk.model(REVIEWER,ID,ModelRequest(context_digest=context['digest']))
    assert calls==[request] and env.get()==before
    assert desk.view(REVIEWER,ID)['candidates'][0]['id']==candidate['id']
    assert desk.view(VIEWER,ID)['candidates']==[]
    assert b'account-71' not in request and context['event_digest'].encode() not in request
    assert b'schema' in request and b'system' in request and b'tools' in request
    private=deepcopy(context); private['text']='Confidential customer or evaluator text'
    with pytest.raises(PermissionError): desk.adapter.propose(private)
    assert calls==[request]
    desk.adapter.enabled=False
    with pytest.raises(PermissionError): desk.adapter.propose(context)
    assert calls==[request]


@pytest.mark.parametrize('fault',['model','json','span','extra'])
def test_invalid_provider_outputs_never_change_claim(env,fault):
    desk,context=start(env)
    annotation=meaning(TEXT).model_dump()
    if fault=='span': annotation['propositions'][0]['source']['start']=1
    if fault=='extra': annotation['execute']='send money'
    response=dict(model='other' if fault=='model' else MODEL,text='broken' if fault=='json' else json.dumps(annotation))
    desk.adapter=PublicInterpretationAdapter(enabled=True,allowed_requests=[sha256(serialized_request(context)).hexdigest()],provider=lambda _:response)
    desk.blind(REVIEWER,ID,Entry(context_digest=context['digest'],interpretation=meaning(TEXT)))
    before=env.get()
    with pytest.raises(ValueError): desk.model(REVIEWER,ID,ModelRequest(context_digest=context['digest']))
    assert env.get()==before


def test_mounted_authenticated_bridge_keeps_existing_signed_submission_boundary(service):
    original=filed(service)
    deliver(service,[('vendor-fixture',dict(kind='message',receipt_id=original['id'],text=TEXT))])
    base=service.url+'/interpretation'
    context=service.client.get(base,headers=service.human.headers).json()['context']
    body=dict(context_digest=context['digest'],interpretation=meaning(TEXT).model_dump())
    assert service.client.post(base+'/blind-entry',json=body).status_code==403
    service.post(base+'/blind-entry',body)
    assert service.human.post(base+'/candidates/model',dict(context_digest=context['digest'])).status_code==403
    rid=service.post(base+'/reviews',dict(**body,candidate_id=None,resolutions=[dict(proposition=0,verdict='accept',explanation='Full signed source and original filing chronology reviewed.')],residuals_reviewed=True,complete_meaning_reviewed=True))['id']
    preview=service.client.get(base+'/reviews/'+rid+'/preview',headers=service.human.headers).json()
    assert service.read()['stage']=='HUMAN_REVIEW'
    draft=service.post(base+'/prepare-response',dict(review_id=rid,preview_digest=preview['digest']))
    assert draft['stage']=='RESPONSE_DRAFTED' and draft['submissions']==[original]
    assert service.human.post(service.url+'/actions/submit-response',{}).status_code==409
    service.action('approve-response')
    service.now+=timedelta(days=1)
    sent=service.action('submit-response')
    assert sent['submissions'][1]['requested']=='20.99' and sent['ledger']['awarded']=='0.00'
