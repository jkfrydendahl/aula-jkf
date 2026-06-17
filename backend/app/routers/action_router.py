from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.dependencies.app_auth import get_aula_service
from app.services.aula_service import AulaService


class SendMessageRequest(BaseModel):
    recipient_id: str
    subject: str
    text: str


class UpdatePresenceRequest(BaseModel):
    child_id: str
    status: str


class UpdateSickRequest(BaseModel):
    child_id: str
    is_sick: bool


class UpdatePresenceTemplateRequest(BaseModel):
    child_id: str
    date: str
    activity_type: int
    entry_time: str
    exit_time: str
    exit_with: Optional[str] = None
    comment: Optional[str] = None


def create_action_router() -> APIRouter:
    router = APIRouter(tags=["actions"])

    @router.post("/messages/send")
    def send_message(
        request: SendMessageRequest,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        return aula_service.send_message(
            recipient_id=request.recipient_id,
            subject=request.subject,
            text=request.text,
        )

    @router.post("/presence/update")
    def update_presence(
        request: UpdatePresenceRequest,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        return aula_service.update_presence(
            child_id=request.child_id,
            status=request.status,
        )

    @router.post("/presence/sick")
    def update_sick_status(
        request: UpdateSickRequest,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        return aula_service.update_sick_status(
            child_id=request.child_id,
            is_sick=request.is_sick,
        )

    @router.get("/presence/{child_id}/pickup-responsibles")
    def get_pickup_responsibles(
        child_id: str,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        return aula_service.get_pickup_responsibles(child_id)

    @router.get("/presence/{child_id}/go-home-with-list")
    def get_go_home_with_list(
        child_id: str,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        return aula_service.get_go_home_with_list(child_id)

    @router.post("/presence/update-template")
    def update_presence_template(
        request: UpdatePresenceTemplateRequest,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        return aula_service.update_presence_template(
            child_id=request.child_id,
            date=request.date,
            activity_type=request.activity_type,
            entry_time=request.entry_time,
            exit_time=request.exit_time,
            exit_with=request.exit_with,
            comment=request.comment,
        )

    return router
