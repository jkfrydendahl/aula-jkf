from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.dependencies.app_auth import get_push_service
from app.repositories.push_repository import PushSubscription
from app.services.push_service import PushService


class UnsubscribeRequest(BaseModel):
    endpoint: str


def create_push_router() -> APIRouter:
    router = APIRouter(prefix="/push", tags=["push"])

    @router.post("/subscribe")
    def subscribe(
        subscription: PushSubscription,
        push_service: PushService = Depends(get_push_service),
    ):
        push_service.subscribe(subscription)
        return {"status": "subscribed"}

    @router.post("/unsubscribe")
    def unsubscribe(
        request: UnsubscribeRequest,
        push_service: PushService = Depends(get_push_service),
    ):
        push_service.unsubscribe(request.endpoint)
        return {"status": "unsubscribed"}

    return router
