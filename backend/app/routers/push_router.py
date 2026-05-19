from fastapi import APIRouter
from pydantic import BaseModel

from app.repositories.push_repository import PushSubscription
from app.services.push_service import PushService


class UnsubscribeRequest(BaseModel):
    endpoint: str


def create_push_router(push_service: PushService) -> APIRouter:
    router = APIRouter(prefix="/push", tags=["push"])

    @router.post("/subscribe")
    def subscribe(subscription: PushSubscription):
        push_service.subscribe(subscription)
        return {"status": "subscribed"}

    @router.post("/unsubscribe")
    def unsubscribe(request: UnsubscribeRequest):
        push_service.unsubscribe(request.endpoint)
        return {"status": "unsubscribed"}

    return router
