"""Decision81 browser controls: untyped artifact note and explicit category correction. No model IO."""
from test_correspondence_model_jobs_ui_75 import kinds, model_job, page_for, payload

TEXT = 'Please supply the request log TRACE-Q with this claim.'
NOTE = 'Document type not recorded.'


def untyped():
    from test_correspondence_interpretation import meaning
    return meaning(TEXT, 'artifact', slots=[('artifact_ref', 'TRACE-Q')]).model_dump()


def candidate():
    return dict(id='5' * 64, origin='model', interpretation=untyped(), provenance=dict(request_sha256='9' * 64))


def test_note_is_absent_before_blind_entry():
    fixture = dict(data=payload(TEXT, None, model_job('independent_reading_required', False), [candidate()]),
                   later=None, submitted=None, states=[])
    with page_for(fixture) as page:
        page.get_by_role('button', name='Save independent reading').wait_for()
        assert page.locator('.interpretation-artifact-note').count() == 0
        assert page.get_by_text(NOTE, exact=False).count() == 0
        assert kinds(page) == ['interpretation']


def test_untyped_candidate_note_then_explicit_category_correction_keeps_source_and_ref():
    from playwright.sync_api import expect
    fixture = dict(data=payload(TEXT, untyped(), model_job('existing_request', False), [candidate()]),
                   later=None, submitted=None, states=[])
    with page_for(fixture) as page:
        page.get_by_text('Requested interpretation — requires your review', exact=True).click()
        note = page.locator('.interpretation-artifact-note')
        expect(note).to_have_count(1)
        expect(note).to_be_visible()
        expect(note).to_contain_text('Reference-only matching can still be legitimate')
        expect(page.get_by_text('Document type: ', exact=False)).to_have_count(0)
        doc_type = page.get_by_label('Document type, if requested', exact=True)
        expect(doc_type).to_have_value('none')  # nothing auto-selected from the identifier
        page.get_by_role('button', name='Compare this suggestion').click()
        page.get_by_role('button', name='Load these propositions into your review draft').click()
        expect(doc_type).to_have_value('none')  # loading copies the null type unchanged
        decision = page.get_by_label('Your decision', exact=True)
        decision.select_option('accept')
        doc_type.select_option('resource_log')  # explicit, reviewer-initiated category change
        expect(page.get_by_label('Your decision', exact=True)).to_have_value('')  # decisions reset
        assert not any(p.endswith(('reviews', 'preview')) for p in kinds(page))
        page.get_by_label('Your decision', exact=True).select_option('correct')
        page.get_by_label('Explanation of source meaning and any difference', exact=True).fill(
            'Synthetic browser interaction; the source names a request log, so the type is chosen explicitly.')
        page.get_by_role('checkbox').nth(0).check(); page.get_by_role('checkbox').nth(1).check()
        page.get_by_role('button', name='Save meaning review and inspect preview').click()
        expect(page.get_by_role('heading', name='Deterministic preview')).to_be_visible()
        calls = page.evaluate('window.calls')
        assert kinds(page) == ['interpretation', 'reviews', 'preview']
        body = calls[1]['body']
        assert body['candidate_id'] == '5' * 64
        assert body['resolutions'][0]['verdict'] == 'correct'
        reviewed, original = body['interpretation']['propositions'][0], untyped()['propositions'][0]
        assert reviewed['artifact_type'] == 'resource_log'
        assert reviewed['source'] == original['source'] and reviewed['slots'] == original['slots']
        assert {k: v for k, v in reviewed.items() if k != 'artifact_type'} == \
            {k: v for k, v in original.items() if k != 'artifact_type'}
        assert not any('model' in row['path'] or row['path'].endswith(('prepare-response', 'submit-response'))
                       or '/actions/' in row['path'] for row in calls)
