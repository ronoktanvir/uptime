"""Authenticated reviewer routes and an independently signed local source channel.

The server's security middleware owns request-size, origin and action-header
guards. The service dependency verifies the exact request bytes and nonce.
"""
from fastapi import APIRouter, Depends

from .correspondence import CorrespondenceDesk
from .correspondence_types import Claim, Delivery, Empty


def make_correspondence_router(desk: CorrespondenceDesk, actor, reviewer, check_write, service):
    router = APIRouter(prefix="/api/correspondence/claims")

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

    @router.post("/{claim_id}/actions/{action}")
    def act(claim_id: str, action: str, body: Empty, p=Depends(reviewer)):
        check_write(p)
        return desk.act(p, claim_id, action)

    @router.post("/{claim_id}/events")
    def receive(claim_id: str, body: Delivery, p=Depends(service)):
        return desk.receive(p, claim_id, body)

    return router
