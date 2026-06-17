import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.session_utils import create_session_token, verify_session_token


class LoginRequest(BaseModel):
    password: str


def create_app_auth_router() -> APIRouter:
    router = APIRouter(prefix="/app-auth", tags=["app-auth"])

    @router.post("/login")
    async def app_login(request: Request, payload: LoginRequest):
        settings = request.app.state.app_auth_settings

        if not settings.app_auth_enabled:
            return {"authenticated": True}

        if not secrets.compare_digest(payload.password, settings.app_auth_password):
            raise HTTPException(status_code=401, detail="Invalid password")

        secret = settings.app_session_secret or settings.app_auth_password
        token = create_session_token(secret=secret, ttl_seconds=settings.app_session_ttl_seconds)

        response = JSONResponse(content={"authenticated": True})
        secure = settings.app_session_secure_cookie
        response.set_cookie(
            key=settings.app_session_cookie_name,
            value=token,
            httponly=True,
            secure=secure,
            samesite="none" if secure else "lax",
            path="/",
            max_age=settings.app_session_ttl_seconds,
        )
        return response

    @router.post("/logout")
    async def app_logout(request: Request):
        settings = request.app.state.app_auth_settings
        response = JSONResponse(content={"authenticated": False})
        secure = settings.app_session_secure_cookie
        response.set_cookie(
            key=settings.app_session_cookie_name,
            value="",
            path="/",
            secure=secure,
            httponly=True,
            samesite="none" if secure else "lax",
            max_age=0,
        )
        return response

    @router.get("/me")
    async def app_me(request: Request):
        settings = request.app.state.app_auth_settings
        if not settings.app_auth_enabled:
            return {"authenticated": True}

        token = request.cookies.get(settings.app_session_cookie_name)
        secret = settings.app_session_secret or settings.app_auth_password
        if not token or not secret:
            return {"authenticated": False}

        is_valid = verify_session_token(
            token=token,
            secret=secret,
            max_age=settings.app_session_ttl_seconds,
        )
        return {"authenticated": is_valid}

    return router
