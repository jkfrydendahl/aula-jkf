from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from app.models.schemas import (
    AuthStartRequest,
    AuthStatusResponse,
    AuthFlowStatus,
    IdentitySelectRequest,
    TokenData,
)
from app.services.auth_service import AuthService


def create_auth_router(auth_service: AuthService, admin_secret: str = "") -> APIRouter:
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
            message=flow.get("message"),
            identities=flow.get("identities"),
            qr_data=flow.get("qr_svg"),
            qr_data_2=flow.get("qr_svg_2"),
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

    @router.post("/upload-tokens")
    def upload_tokens(
        tokens: TokenData,
        x_admin_secret: Optional[str] = Header(None),
    ):
        """Accept tokens synced from a local instance. Protected by admin secret."""
        if not admin_secret:
            raise HTTPException(status_code=503, detail="Token upload not configured")
        if x_admin_secret != admin_secret:
            raise HTTPException(status_code=403, detail="Invalid admin secret")

        auth_service.upload_tokens(tokens)
        return {"status": "ok", "message": "Tokens saved"}

    @router.get("/check")
    def check_auth():
        """Check if the backend has valid tokens."""
        # Quick check if tokens exist and are not expired
        from app.repositories.token_repository import TokenRepository
        import time
        repo = auth_service._token_repository
        stored = repo.load()
        if not stored:
            return {"authenticated": False, "reason": "no_tokens"}
        if stored.expires_at < time.time():
            return {"authenticated": False, "reason": "expired"}
        return {"authenticated": True}

    return router
