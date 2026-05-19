from fastapi import APIRouter
from pydantic import BaseModel

from app.services.aula_service import AulaService


class SendMessageRequest(BaseModel):
    recipient_id: str
    subject: str
    text: str


class UpdatePresenceRequest(BaseModel):
    child_id: str
    status: str


def create_action_router(aula_service: AulaService) -> APIRouter:
    router = APIRouter(tags=["actions"])

    @router.post("/messages/send")
    def send_message(request: SendMessageRequest):
        return aula_service.send_message(
            recipient_id=request.recipient_id,
            subject=request.subject,
            text=request.text,
        )

    @router.post("/presence/update")
    def update_presence(request: UpdatePresenceRequest):
        return aula_service.update_presence(
            child_id=request.child_id,
            status=request.status,
        )

    return router
