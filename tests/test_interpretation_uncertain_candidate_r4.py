"""An UNCERTAIN denial request may leave a validated, request-linked candidate behind (PUBLIC-PROPOSAL-RUNTIME.md).
It stays visible and inert; its request's uncertain state and reason are shown right beside it."""
from playwright.sync_api import expect

from test_correspondence_model_jobs_ui_75 import AWARD, award_annotation, job, kinds, model_job, page_for, payload


def uncertain(reason='restart_after_dispatch'):
    row = job('UNCERTAIN')
    row.update(reason=reason, provider=dict(model='claude-opus-5-5'), finished_at='2026-11-09T21:01:40+00:00')
    return row


def test_uncertain_request_state_and_reason_sit_beside_its_validated_candidate():
    interpretation = award_annotation()
    linked = dict(id='5' * 64, origin='model', interpretation=interpretation.model_dump(), provenance=dict(request_sha256='9' * 64))
    blind = interpretation.model_dump()
    data = payload(AWARD, blind, model_job('existing_request', False, uncertain()), [linked])
    with page_for(dict(data=data, later=None, submitted=None, states=[uncertain()])) as page:
        expect(page.get_by_text('Request job-1: Request outcome uncertain.', exact=False)).to_be_visible()
        expect(page.get_by_text('Model claude-opus-5-5. Finished Nov 9, 2026, 21:01 UTC.', exact=False)).to_be_visible()
        summary = page.get_by_text('Requested interpretation — request outcome uncertain; requires your review', exact=True)
        expect(summary).to_be_visible()
        summary.click()
        expect(page.get_by_text('Request job-1 is UNCERTAIN (restart_after_dispatch). It did not complete cleanly.', exact=False)).to_be_visible()
        expect(page.get_by_text('State: proposed; not reviewed', exact=True)).to_be_visible()
        assert not any(k in {'model-jobs', 'reviews', 'preview'} for k in kinds(page))


def test_a_cleanly_completed_request_keeps_the_ordinary_candidate_label():
    interpretation = award_annotation()
    linked = dict(id='5' * 64, origin='model', interpretation=interpretation.model_dump(), provenance=dict(request_sha256='9' * 64))
    data = payload(AWARD, interpretation.model_dump(), model_job('existing_request', False, job('SUCCEEDED')), [linked])
    with page_for(dict(data=data, later=None, submitted=None, states=[job('SUCCEEDED')])) as page:
        expect(page.get_by_text('Requested interpretation — requires your review', exact=True)).to_be_visible()
        expect(page.get_by_text('did not complete cleanly', exact=False)).to_have_count(0)
