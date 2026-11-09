"""Authenticated reviewer routes and an independently signed local source channel.

The server's security middleware owns request-size, origin and action-header
guards. The service dependency verifies the exact request bytes and nonce.
"""
from fastapi import APIRouter, Depends

from .correspondence import CorrespondenceDesk
from .correspondence_types import Claim, Delivery, Empty
from .correspondence_interpretation import Entry, CandidateRequest, ModelRequest, Review, Prepare
from .correspondence_model_jobs import CorrespondenceModelJobs
from .correspondence_review import InterpretationDesk
from .correspondence_disposition import DenialAcceptance, dispute_trace


def make_correspondence_router(desk: CorrespondenceDesk, actor, reviewer, check_write, service):
    router = APIRouter(prefix="/api/correspondence/claims")
    interpretations = InterpretationDesk(desk, getattr(desk, "interpretation_adapter", None))
    # The shared proposal-job service is looked up on each request, so route creation order does not matter.
    model_jobs = CorrespondenceModelJobs(desk, interpretations)

    @router.get("")
    def cases(p=Depends(actor)):
        return desk.cases(p)

    @router.post("")
    def create(body: Claim, p=Depends(reviewer)):
        check_write(p)
        return desk.create(p, body)

    @router.get("/{claim_id}")
    def detail(claim_id: str, p=Depends(actor)):
        return desk.case(p, claim_id)

    @router.post("/{claim_id}/denial-acceptance")
    def accept_denial(claim_id: str, body: DenialAcceptance, p=Depends(reviewer)):
        check_write(p)
        return desk.accept_denial(p, claim_id, body.basis_digest)

    @router.get("/{claim_id}/trace")
    def trace(claim_id: str, p=Depends(actor)):
        return dispute_trace(desk, interpretations, p, claim_id)

    @router.post("/{claim_id}/actions/{action}")
    def act(claim_id: str, action: str, body: Empty, p=Depends(reviewer)):
        check_write(p)
        return desk.act(p, claim_id, action)

    @router.post("/{claim_id}/events")
    def receive(claim_id: str, body: Delivery, p=Depends(service)):
        return desk.receive(p, claim_id, body)

    @router.get("/{claim_id}/interpretation")
    def interpretation(claim_id: str, p=Depends(actor)):
        return model_jobs.view(p, claim_id)

    @router.post("/{claim_id}/interpretation/model-jobs")
    def request_interpretation(claim_id: str, body: ModelRequest, p=Depends(reviewer)):
        check_write(p)
        return model_jobs.submit(p, claim_id, body)

    @router.get("/{claim_id}/interpretation/model-jobs/{job_id}")
    def interpretation_request_status(claim_id: str, job_id: str, p=Depends(actor)):
        return model_jobs.get(p, claim_id, job_id)

    @router.post("/{claim_id}/interpretation/blind-entry")
    def blind(claim_id: str, body: Entry, p=Depends(reviewer)):
        check_write(p)
        return interpretations.blind(p, claim_id, body)

    @router.post("/{claim_id}/interpretation/candidates/manual")
    def manual_candidate(claim_id: str, body: CandidateRequest, p=Depends(reviewer)):
        check_write(p)
        return interpretations.candidate(p, claim_id, body)

    @router.post("/{claim_id}/interpretation/candidates/model")
    def model_candidate(claim_id: str, body: ModelRequest, p=Depends(reviewer)):
        check_write(p)
        return interpretations.model(p, claim_id, body)

    @router.post("/{claim_id}/interpretation/reviews")
    def review_interpretation(claim_id: str, body: Review, p=Depends(reviewer)):
        check_write(p)
        return interpretations.review(p, claim_id, body)

    @router.get("/{claim_id}/interpretation/reviews/{review_id}/preview")
    def interpretation_preview(claim_id: str, review_id: str, p=Depends(actor)):
        return interpretations.preview(p, claim_id, review_id)

    @router.post("/{claim_id}/interpretation/prepare-response")
    def prepare_interpretation(claim_id: str, body: Prepare, p=Depends(reviewer)):
        check_write(p)
        return interpretations.prepare(p, claim_id, body)

    return router
