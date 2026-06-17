import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.session_utils import create_session_token, verify_session_token


class LoginRequest(BaseModel):
    username: str
    password: str


def create_app_auth_router() -> APIRouter:
    router = APIRouter(prefix="/app-auth", tags=["app-auth"])

    @router.post("/login")
    async def app_login(request: Request, payload: LoginRequest):
        settings = request.app.state.app_auth_settings

        if not settings.auth_enabled:
            return {"authenticated": True}

        users = settings.get_users()
        user = None
        if len(users) == 1 and users[0].user_id == "default" and users[0].name == "":
            candidate = users[0]
            if secrets.compare_digest(payload.password, candidate.password):
                user = candidate
        else:
            normalized_username = payload.username.strip().lower()
            for candidate in users:
                if candidate.name.lower() != normalized_username:
                    continue
                if secrets.compare_digest(payload.password, candidate.password):
                    user = candidate
                    break

        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_session_token(
            secret=settings.session_secret,
            user_id=user.user_id,
            ttl_seconds=settings.session_ttl_seconds,
        )

        response = JSONResponse(content={"authenticated": True})
        secure = settings.session_secure_cookie
        response.set_cookie(
            key=settings.session_cookie_name,
            value=token,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
            max_age=settings.session_ttl_seconds,
        )
        return response

    @router.post("/logout")
    async def app_logout(request: Request):
        settings = request.app.state.app_auth_settings
        response = JSONResponse(content={"authenticated": False})
        secure = settings.session_secure_cookie
        response.set_cookie(
            key=settings.session_cookie_name,
            value="",
            path="/",
            secure=secure,
            httponly=True,
            samesite="lax",
            max_age=0,
        )
        return response

    @router.get("/me")
    async def app_me(request: Request):
        settings = request.app.state.app_auth_settings
        if not settings.auth_enabled:
            users = settings.get_users()
            username = users[0].name if users else None
            return {"authenticated": True, "username": username}

        token = request.cookies.get(settings.session_cookie_name)
        secret = settings.session_secret
        if not token or not secret:
            return {"authenticated": False}

        user_id = verify_session_token(
            token=token,
            secret=secret,
            max_age=settings.session_ttl_seconds,
        )
        if user_id is None:
            return {"authenticated": False}

        user = next((candidate for candidate in settings.get_users() if candidate.user_id == user_id), None)
        if user is None:
            return {"authenticated": False}
        return {"authenticated": True, "username": user.name}

    @router.get("/users")
    async def app_users(request: Request):
        settings = request.app.state.app_auth_settings
        users = settings.get_users()
        # Return only names — no IDs needed for the login selector
        return [{"name": user.name} for user in users]

    return router
