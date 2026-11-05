"""Authenticated vendor catalog router. The application supplies session and mutation guards."""
from fastapi import APIRouter, Depends

from . import vendor_registry as registry
from .contracts import DraftReviewer
from .vendor_terms import Strict


class Empty(Strict):
    pass


class Observation(Strict):
    facts: dict


class Preview(Observation):
    revision: int


def make_router(db_path, actor, reviewer, check_write, mutex):
    router = APIRouter(prefix='/api/vendors')

    def mutate(p, fn, *args):
        with mutex:
            if not isinstance(p, DraftReviewer):
                check_write(p)
            elif fn not in {registry.install, registry.submit_tests, registry.shadow_preview}:
                raise PermissionError("Draft capability cannot authorize this operation.")
            return fn(db_path, p, *args)

    @router.get('')
    def catalog(p=Depends(actor)):
        return registry.catalog(db_path, p)

    @router.get('/{vendor_id}')
    def vendor(vendor_id: str, p=Depends(actor)):
        return registry.get_vendor(db_path, p, vendor_id)

    @router.post('/{vendor_id}/candidates')
    def candidate(vendor_id: str, body: dict, p=Depends(reviewer)):
        return mutate(p, registry.install, vendor_id, body)

    @router.post('/{vendor_id}/tests')
    def tests(vendor_id: str, body: registry.TestSubmission, p=Depends(reviewer)):
        return mutate(p, registry.submit_tests, vendor_id, body)

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
