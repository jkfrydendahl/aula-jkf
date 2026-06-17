from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.dependencies.app_auth import get_auth_service
from app.models.schemas import (
    AuthFlowStatus,
    AuthStartRequest,
    AuthStatusResponse,
    IdentitySelectRequest,
    TokenData,
)
from app.services.auth_service import AuthService


def create_auth_router() -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/start")
    def start_auth(
        request: AuthStartRequest,
        auth_service: AuthService = Depends(get_auth_service),
    ):
        flow_id = auth_service.start_flow(
            username=request.username,
            auth_method=request.auth_method,
            password=request.password,
            token=request.token,
        )
        return {"flow_id": flow_id}

    @router.get("/status/{flow_id}")
    def get_auth_status(
        flow_id: str,
        auth_service: AuthService = Depends(get_auth_service),
    ):
        flow = auth_service.get_status(flow_id)
        if flow is None:
            raise HTTPException(status_code=404, detail="Flow not found")

        return AuthStatusResponse(
            flow_id=flow_id,
            status=flow["status"],
            error=flow.get("error"),
            message=flow.get("message"),
            identities=flow.get("identities"),
            qr_data=flow.get("qr_svg"),
            qr_data_2=flow.get("qr_svg_2"),
        )

    @router.post("/select-identity/{flow_id}")
    def select_identity(
        flow_id: str,
        request: IdentitySelectRequest,
        auth_service: AuthService = Depends(get_auth_service),
    ):
        success = auth_service.select_identity(flow_id, request.identity_index)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Flow not found or not waiting for identity selection",
            )
        return {"status": "ok"}

    @router.post("/upload-tokens")
    def upload_tokens(
        request: Request,
        tokens: TokenData,
        x_admin_secret: Optional[str] = Header(None),
    ):
        """Accept tokens synced from a local instance. Protected by admin secret."""
        admin_secret = request.app.state.settings.admin_secret
        if not admin_secret:
            raise HTTPException(status_code=503, detail="Token upload not configured")
        if x_admin_secret != admin_secret:
            raise HTTPException(status_code=403, detail="Invalid admin secret")

        # Resolve target user's auth service by user_id in the token payload, or default
        user_id = tokens.user_id if hasattr(tokens, "user_id") and tokens.user_id else "default"
        registry = request.app.state.user_registry
        entry = registry.get(user_id) or next(iter(registry.values()), None)
        if not entry:
            raise HTTPException(status_code=404, detail="No user configured")
        entry["auth_service"].upload_tokens(tokens)
        return {"status": "ok", "message": "Tokens saved"}

    @router.get("/check")
    def check_auth(auth_service: AuthService = Depends(get_auth_service)):
        """Check if the backend has valid tokens."""
        import time

        repo = auth_service._token_repository
        stored = repo.load()
        if not stored:
            return {"authenticated": False, "reason": "no_tokens"}
        if stored.expires_at < time.time():
            return {"authenticated": False, "reason": "expired"}
        return {"authenticated": True}

    return router
