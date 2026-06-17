from fastapi import HTTPException, Request

from app.session_utils import verify_session_token


async def require_app_auth(request: Request) -> None:
    settings = request.app.state.app_auth_settings

    if not settings.auth_enabled:
        return

    cookie = request.cookies.get(settings.session_cookie_name)
    secret = settings.session_secret or settings.auth_password
    if not cookie or not secret:
        raise HTTPException(status_code=401, detail={"app_auth_required": True})

    is_valid = verify_session_token(
        token=cookie,
        secret=secret,
        max_age=settings.session_ttl_seconds,
    )
    if not is_valid:
        raise HTTPException(status_code=401, detail={"app_auth_required": True})
