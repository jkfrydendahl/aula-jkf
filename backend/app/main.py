import time
import logging
from typing import Callable

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s: %(message)s")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.settings import AppAuthSettings, Settings, UserConfig
from app.aula_client import AulaClient
from app.models.schemas import TokenData
from app.services.aula_service import AulaService
from app.services.auth_service import AuthService
from app.services.push_service import PushService
from app.services.background_poller import BackgroundPoller
from app.repositories.token_repository import FileTokenRepository
from app.repositories.push_repository import FilePushRepository
from app.middleware.token_refresh import TokenRefreshMiddleware
from app.session_utils import verify_session_token
from app.routers.auth_router import create_auth_router
from app.routers.data_router import create_data_router
from app.routers.action_router import create_action_router
from app.routers.push_router import create_push_router
from app.routers.app_auth_router import create_app_auth_router

_LOGGER = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    app_auth_settings: AppAuthSettings | None = None,
) -> FastAPI:
    if settings is None:
        settings = Settings()
    if app_auth_settings is None:
        app_auth_settings = AppAuthSettings()

    app = FastAPI(title="Aula PWA Backend", version="0.1.0")

    app.state.settings = settings
    app.state.app_auth_settings = app_auth_settings

    def make_on_tokens_updated(token_repo: FileTokenRepository) -> Callable[[TokenData | dict], None]:
        def _on_tokens_updated(tokens):
            """Persist tokens — handles both TokenData and raw dict from login flow."""
            if isinstance(tokens, TokenData):
                token_repo.save(tokens)
            elif isinstance(tokens, dict):
                try:
                    token_repo.save(TokenData(
                        access_token=tokens["access_token"],
                        refresh_token=tokens["refresh_token"],
                        expires_at=tokens.get("expires_at", tokens.get("expires_in", 3600) + time.time()),
                    ))
                except Exception as e:
                    _LOGGER.warning(f"Could not persist tokens from dict: {e}")
            else:
                _LOGGER.warning(f"Unknown token type: {type(tokens)}")

        return _on_tokens_updated

    def make_renew_fn(aula_client: AulaClient) -> Callable[[str], TokenData]:
        # Shared with AulaClient._token_refresh_lock so both paths serialize on the same lock
        def renew_token(refresh_token: str) -> TokenData:
            """Renew the access token using the Aula login client (serialized per user)."""
            with aula_client._token_refresh_lock:
                login_client = aula_client._aula_client
                login_client.tokens = {"refresh_token": refresh_token}
                success = login_client.renew_access_token()
                if not success:
                    raise Exception("Token renewal failed")
                tokens = login_client.tokens
                expires_at = time.time() + tokens.get("expires_in", 3600)
                return TokenData(
                    access_token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"],
                    expires_at=expires_at,
                )

        return renew_token

    configured_users = app_auth_settings.get_users()
    if not configured_users:
        if app_auth_settings.auth_enabled:
            raise RuntimeError(
                "APP_AUTH is enabled but no users are configured. "
                "Set APP_USER_1_NAME, APP_USER_1_PASSWORD, APP_USER_1_TOKEN_PATH."
            )
        configured_users = [
            UserConfig(
                user_id="default",
                name="",
                password="",
                token_path=settings.token_store_path,
                push_store_path=settings.push_store_path,
            )
        ]

    user_registry: dict[str, dict[str, object]] = {}
    for user in configured_users:
        token_repo = FileTokenRepository(user.token_path)
        push_repo = FilePushRepository(user.push_store_path)
        stored_tokens = token_repo.load()
        aula_client = AulaClient(
            mitid_username="",
            stored_tokens=stored_tokens.model_dump() if stored_tokens else None,
            on_tokens_updated=make_on_tokens_updated(token_repo),
        )
        aula_service = AulaService(aula_client, token_repository=token_repo)
        auth_service = AuthService(
            token_repository=token_repo,
            sync_target_url=settings.sync_target_url,
            admin_secret=settings.admin_secret,
        )
        push_service = PushService(
            push_repository=push_repo,
            vapid_private_key=settings.vapid_private_key,
            vapid_public_key=settings.vapid_public_key,
            vapid_claim_email=settings.vapid_claim_email,
        )
        renew_fn = make_renew_fn(aula_client)
        user_registry[user.user_id] = {
            "aula_client": aula_client,
            "aula_service": aula_service,
            "auth_service": auth_service,
            "push_service": push_service,
            "token_repo": token_repo,
            "renew_fn": renew_fn,
            "poller": BackgroundPoller(
                aula_service=aula_service,
                push_service=push_service,
            ),
        }

    app.state.user_registry = user_registry

    def get_user_context(request: Request):
        cookie = request.cookies.get(app_auth_settings.session_cookie_name)
        if not cookie or not app_auth_settings.session_secret:
            return None
        user_id = verify_session_token(
            cookie,
            app_auth_settings.session_secret,
            app_auth_settings.session_ttl_seconds,
        )
        if not user_id or user_id not in user_registry:
            return None
        entry = user_registry[user_id]
        return (entry["token_repo"], entry["renew_fn"])

    # Middleware (order matters: last added = outermost)
    # TokenRefresh must be INNER (added first), CORS must be OUTER (added last)
    app.add_middleware(
        TokenRefreshMiddleware,
        get_user_context_fn=get_user_context,
    )
    # CORS — support multiple origins (comma-separated)
    origins = [o.strip() for o in settings.frontend_url.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler — manually adds CORS headers because FastAPI's
    # exception_handler fires before CORSMiddleware can wrap the response.
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        from app.aula_client import AulaAuthRequiredError
        _LOGGER.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")

        status = 401 if isinstance(exc, AulaAuthRequiredError) else 500
        content = (
            {"detail": "Authentication required", "re_auth_required": True}
            if isinstance(exc, AulaAuthRequiredError)
            else {"detail": "Internal server error"}
        )

        response = JSONResponse(status_code=status, content=content)

        # Manually add CORS headers so the browser can read the error body
        origin = request.headers.get("origin", "")
        if origin in origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"

        return response

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Routers
    app.include_router(create_app_auth_router())
    app.include_router(create_auth_router())
    app.include_router(create_data_router())
    app.include_router(create_action_router())
    app.include_router(create_push_router())

    # Background scheduler — token renewal always runs; poller runs if VAPID configured
    scheduler = BackgroundScheduler()

    for user_id, entry in user_registry.items():
        token_repo = entry["token_repo"]
        renew_fn = entry["renew_fn"]

        def make_token_renewal_job(repo, renew, uid):
            def _renew_token_if_needed():
                try:
                    tokens = repo.load()
                    if tokens is None:
                        return
                    time_until_expiry = tokens.expires_at - time.time()
                    if time_until_expiry < 600:  # Renew if less than 10 minutes left
                        _LOGGER.info(f"Proactive token renewal for user {uid} (expires in {int(time_until_expiry)}s)")
                        new_tokens = renew(tokens.refresh_token)
                        repo.save(new_tokens)
                        _LOGGER.info(f"Token renewed for user {uid}")
                except Exception as e:
                    _LOGGER.warning(f"Proactive token renewal failed for user {uid}: {e}")
            return _renew_token_if_needed

        scheduler.add_job(
            make_token_renewal_job(token_repo, renew_fn, user_id),
            "interval",
            seconds=300,  # Check every 5 minutes
            id=f"token_renewal_{user_id}",
            replace_existing=True,
        )

    if settings.vapid_private_key:
        for user_id, entry in user_registry.items():
            scheduler.add_job(
                entry["poller"].tick,
                "interval",
                seconds=settings.poll_interval,
                id=f"aula_poller_{user_id}",
                replace_existing=True,
            )
        _LOGGER.info(f"Background poller started (interval: {settings.poll_interval}s)")

    scheduler.start()
    _LOGGER.info("Background scheduler started (token renewal every 5 min)")

    @app.on_event("shutdown")
    def shutdown_scheduler():
        scheduler.shutdown(wait=False)

    return app


app = create_app()
