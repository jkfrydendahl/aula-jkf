from fastapi import APIRouter, HTTPException
import logging

from app.services.aula_service import AulaService

_LOGGER = logging.getLogger(__name__)


def create_data_router(aula_service: AulaService) -> APIRouter:
    router = APIRouter(tags=["data"])

    @router.get("/children")
    def get_children():
        aula_service.ensure_data_loaded()
        return aula_service.get_children()

    @router.get("/presence/{child_id}")
    def get_presence(child_id: str):
        aula_service.ensure_data_loaded()
        return aula_service.get_presence(child_id)

    @router.get("/messages")
    def get_messages():
        aula_service.ensure_data_loaded()
        return aula_service.get_messages()

    @router.get("/calendar/{child_id}")
    def get_calendar(child_id: str):
        aula_service.ensure_data_loaded()
        return aula_service.get_calendar(child_id)

    @router.get("/ugeplan/{child_id}")
    def get_ugeplan(child_id: str):
        aula_service.ensure_data_loaded()
        return aula_service.get_ugeplan(child_id)

    return router
