"""Authenticated vendor catalog router. The application supplies session and mutation guards."""
from fastapi import APIRouter, Depends
from datetime import datetime,UTC

from . import vendor_registry as registry
from .contracts import DraftReviewer
from .vendor_terms import Strict


class Empty(Strict):
    pass


class Observation(Strict):
    facts: dict


class Preview(Observation):
    revision: int


def make_router(db_path, actor, reviewer, check_write, mutex, *, governing_fees=None, trusted_now=None,
                proposal_jobs=None):
    """`proposal_jobs` is the server-injected shared PublicProposalJobs service, or None (fail closed)."""
    from .governing_fees import FeeRegistry
    from .vendor_model_jobs import ProposalCandidate, ProposalRequest, VendorModelJobs, unconfigured_access
    if governing_fees is not None and type(governing_fees) is not FeeRegistry:
        raise TypeError('A fixed server FeeRegistry is required; arbitrary fee callbacks are not supported.')
    clock=trusted_now or (lambda:datetime.now(UTC))
    router = APIRouter(prefix='/api/vendors')
    jobs = None if proposal_jobs is None else VendorModelJobs(proposal_jobs)

    def mutate(p, fn, *args, resolve=None):
        with mutex:
            if not isinstance(p, DraftReviewer):
                check_write(p)
            elif fn not in {registry.install, registry.submit_tests, registry.shadow_preview}:
                raise PermissionError("Draft capability cannot authorize this operation.")
            extra={}
            if resolve is not None:
                # Server-only arguments resolved after authorization, inside the same mutex.
                args, resolved = resolve(p)
                extra.update(resolved)
            if fn in {registry.act,registry.dispatch}:
                extra.update(governing_fees=governing_fees or (),trusted_now=clock)
            if governing_fees is not None and not isinstance(p,DraftReviewer) and fn in {registry.submit_tests,registry.shadow_preview,registry.dispatch}:
                contexts=governing_fees.contexts_from_inbox(db_path,p.tenant,as_of=clock())
                if fn is registry.submit_tests:
                    extra['governing_fees']=contexts
                else:
                    artifact=registry.get_vendor(db_path,p,args[0],governing_fees=governing_fees or (),trusted_now=clock)
                    facts=args[1].facts if fn is registry.shadow_preview else args[1]
                    extra['governing_fee']=registry._fee_for(contexts,artifact['manifest'],artifact['overlay'],facts,p.tenant)
            return fn(db_path, p, *args,**extra)

    @router.get('')
    def catalog(p=Depends(actor)):
        return registry.catalog(db_path, p,governing_fees=governing_fees or (),trusted_now=clock)

    @router.get('/{vendor_id}')
    def vendor(vendor_id: str, p=Depends(actor)):
        return registry.get_vendor(db_path, p, vendor_id,governing_fees=governing_fees or (),trusted_now=clock)

    @router.post('/{vendor_id}/candidates')
    def candidate(vendor_id: str, body: dict, p=Depends(reviewer)):
        return mutate(p, registry.install, vendor_id, body)

    # ---- Public proposal generation: draft-level operations only, zero provider calls here ----

    def permit_proposal(p, vendor_id):
        """Same reviewer/draft authority as candidate intake; no domain mutation and no provider call."""
        with mutex:
            if not isinstance(p, DraftReviewer):
                check_write(p)
            with registry.transaction(db_path, p, vendor_id, write=True, draft=True):
                pass

    def configured():
        if jobs is None:
            raise PermissionError('Public proposal generation is not configured for this deployment.')
        return jobs

    @router.post('/{vendor_id}/proposal-access')
    def proposal_access(vendor_id: str, body: ProposalRequest, p=Depends(reviewer)):
        permit_proposal(p, vendor_id)
        return unconfigured_access(vendor_id, body) if jobs is None else jobs.access(p, vendor_id, body)

    @router.post('/{vendor_id}/proposal-jobs')
    def proposal_job(vendor_id: str, body: ProposalRequest, p=Depends(reviewer)):
        service = configured()
        permit_proposal(p, vendor_id)
        return service.submit(p, vendor_id, body)

    @router.get('/{vendor_id}/proposal-jobs/{job_id}')
    def proposal_job_status(vendor_id: str, job_id: str, p=Depends(actor)):
        return configured().status(p, vendor_id, job_id)

    @router.post('/{vendor_id}/proposal-jobs/{job_id}/candidate')
    def proposal_candidate(vendor_id: str, job_id: str, body: ProposalCandidate, p=Depends(reviewer)):
        service = configured()

        def resolve(principal):
            intake, receipt = service.candidate(principal, vendor_id, job_id, body.overlay)
            return (vendor_id, intake), {'public_receipt': receipt}
        return mutate(p, registry.install, resolve=resolve)

    @router.post('/{vendor_id}/tests')
    def tests(vendor_id: str, body: registry.TestSubmission, p=Depends(reviewer)):
        return mutate(p, registry.submit_tests, vendor_id, body)

    @router.post('/{vendor_id}/semantic-bindings')
    def semantic_review(vendor_id: str, body: registry.SemanticSubmission, p=Depends(reviewer)):
        return mutate(p, registry.review_semantics, vendor_id, body)

    @router.post('/{vendor_id}/semantic-bindings/revoke')
    def semantic_revocation(vendor_id: str, body: registry.SemanticRevocation, p=Depends(reviewer)):
        return mutate(p, registry.revoke_semantics, vendor_id, body)

    @router.post('/{vendor_id}/shadow-preview')
    def preview(vendor_id: str, body: Preview, p=Depends(reviewer)):
        return mutate(p, registry.shadow_preview, vendor_id, body)

    @router.post('/{vendor_id}/actions/{action}')
    def act(vendor_id: str, action: str, body: Empty, p=Depends(reviewer)):
        return mutate(p, registry.act, vendor_id, action)

    @router.post('/{vendor_id}/evaluate')
    def evaluate(vendor_id: str, body: Observation, p=Depends(reviewer)):
        return mutate(p, registry.dispatch, vendor_id, body.facts)

    return router
