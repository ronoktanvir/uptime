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


def make_router(db_path, actor, reviewer, check_write, mutex, *, governing_fees=None, trusted_now=None):
    from .governing_fees import FeeRegistry
    if governing_fees is not None and type(governing_fees) is not FeeRegistry:
        raise TypeError('A fixed server FeeRegistry is required; arbitrary fee callbacks are not supported.')
    clock=trusted_now or (lambda:datetime.now(UTC))
    router = APIRouter(prefix='/api/vendors')

    def mutate(p, fn, *args):
        with mutex:
            if not isinstance(p, DraftReviewer):
                check_write(p)
            elif fn not in {registry.install, registry.submit_tests, registry.shadow_preview}:
                raise PermissionError("Draft capability cannot authorize this operation.")
            extra={}
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
