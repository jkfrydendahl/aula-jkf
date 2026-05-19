from fastapi import APIRouter, HTTPException

from app.models.schemas import (
    AuthStartRequest,
    AuthStatusResponse,
    AuthFlowStatus,
    IdentitySelectRequest,
)
from app.services.auth_service import AuthService


def create_auth_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/start")
    def start_auth(request: AuthStartRequest):
        flow_id = auth_service.start_flow(
            username=request.username,
            auth_method=request.auth_method,
            password=request.password,
            token=request.token,
        )
        return {"flow_id": flow_id}

    @router.get("/status/{flow_id}")
    def get_auth_status(flow_id: str):
        flow = auth_service.get_status(flow_id)
        if flow is None:
            raise HTTPException(status_code=404, detail="Flow not found")

        response = AuthStatusResponse(
            flow_id=flow_id,
            status=flow["status"],
            error=flow.get("error"),
            identities=flow.get("identities"),
        )
        return response

    @router.post("/select-identity/{flow_id}")
    def select_identity(flow_id: str, request: IdentitySelectRequest):
        success = auth_service.select_identity(flow_id, request.identity_index)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Flow not found or not waiting for identity selection",
            )
        return {"status": "ok"}

    return router
