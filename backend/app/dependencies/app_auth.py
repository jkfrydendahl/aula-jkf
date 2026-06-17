from fastapi import Depends, HTTPException, Request

from app.services.aula_service import AulaService
from app.services.auth_service import AuthService
from app.services.push_service import PushService
from app.session_utils import verify_session_token


async def require_app_auth(request: Request) -> str:
    """Returns user_id for the authenticated session."""
    settings = request.app.state.app_auth_settings
    if not settings.auth_enabled:
        users = settings.get_users()
        return users[0].user_id if users else "default"

    cookie = request.cookies.get(settings.session_cookie_name)
    secret = settings.session_secret
    if not cookie or not secret:
        raise HTTPException(status_code=401, detail={"app_auth_required": True})

    user_id = verify_session_token(
        token=cookie,
        secret=secret,
        max_age=settings.session_ttl_seconds,
    )
    if user_id is None:
        raise HTTPException(status_code=401, detail={"app_auth_required": True})

    users = settings.get_users()
    if not any(user.user_id == user_id for user in users):
        raise HTTPException(status_code=401, detail={"app_auth_required": True})
    return user_id


def _get_registry_entry(request: Request, user_id: str) -> dict:
    try:
        return request.app.state.user_registry[user_id]
    except KeyError as exc:
        raise HTTPException(status_code=401, detail={"app_auth_required": True}) from exc


def get_aula_service(
    request: Request,
    user_id: str = Depends(require_app_auth),
) -> AulaService:
    return _get_registry_entry(request, user_id)["aula_service"]


def get_push_service(
    request: Request,
    user_id: str = Depends(require_app_auth),
) -> PushService:
    return _get_registry_entry(request, user_id)["push_service"]


def get_auth_service(
    request: Request,
    user_id: str = Depends(require_app_auth),
) -> AuthService:
    return _get_registry_entry(request, user_id)["auth_service"]
