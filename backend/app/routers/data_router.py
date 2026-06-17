from fastapi import APIRouter, Depends
from pydantic import BaseModel
import logging

from app.dependencies.app_auth import get_aula_service
from app.services.aula_service import AulaService

_LOGGER = logging.getLogger(__name__)


def create_data_router() -> APIRouter:
    router = APIRouter(tags=["data"])

    @router.get("/children")
    def get_children(aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_children()

    @router.get("/presence/{child_id}")
    def get_presence(child_id: str, aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_presence(child_id)

    @router.get("/messages")
    def get_messages(aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_messages()

    @router.get("/messages/{thread_id}")
    def get_thread(thread_id: int, aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_thread_detail(thread_id)

    @router.post("/messages/{thread_id}/read")
    def mark_read(thread_id: int, aula_service: AulaService = Depends(get_aula_service)):
        try:
            aula_service.ensure_data_loaded()
            success = aula_service.mark_thread_read(thread_id)
            return {"success": success}
        except Exception as e:
            _LOGGER.warning(f"Failed to mark thread {thread_id} as read: {e}")
            return {"success": False}

    @router.get("/calendar/{child_id}")
    def get_calendar(child_id: str, aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_calendar(child_id)

    @router.get("/ugeplan/{child_id}")
    def get_ugeplan(child_id: str, aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_ugeplan(child_id)

    @router.get("/posts")
    def get_posts(aula_service: AulaService = Depends(get_aula_service)):
        try:
            aula_service.ensure_data_loaded()
            return aula_service.get_posts()
        except Exception as e:
            _LOGGER.error(f"Error in get_posts: {e}", exc_info=True)
            raise

    @router.get("/vacation-registrations")
    def get_vacation_registrations(aula_service: AulaService = Depends(get_aula_service)):
        aula_service.ensure_data_loaded()
        return aula_service.get_vacation_registrations()

    class VacationDay(BaseModel):
        date: str
        isComing: bool
        entryTime: str = ""
        exitTime: str = ""

    class VacationResponseRequest(BaseModel):
        response_id: int
        child_id: int
        days: list[VacationDay]
        comment: str | None = None

    @router.get("/vacation-registrations/{response_id}")
    def get_vacation_response(
        response_id: int,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        data = aula_service._client.get_vacation_registration_response(response_id)
        response = data.get("vacationRegistrationResponse", {})
        days = response.get("days", [])
        return {"days": days}

    @router.post("/vacation-registrations/respond")
    def respond_vacation(
        request: VacationResponseRequest,
        aula_service: AulaService = Depends(get_aula_service),
    ):
        aula_service.ensure_data_loaded()
        days = [d.model_dump() for d in request.days]
        return aula_service.submit_vacation_response(
            request.response_id, request.child_id, days, request.comment
        )

    return router
