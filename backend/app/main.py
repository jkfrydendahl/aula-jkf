import time
import logging

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from app.settings import AppAuthSettings, Settings
from app.aula_client import AulaClient
from app.models.schemas import TokenData
from app.services.aula_service import AulaService
from app.services.auth_service import AuthService
from app.services.push_service import PushService
from app.services.background_poller import BackgroundPoller
from app.repositories.token_repository import FileTokenRepository
from app.repositories.push_repository import FilePushRepository
from app.middleware.token_refresh import TokenRefreshMiddleware
from app.routers.auth_router import create_auth_router
from app.routers.data_router import create_data_router
from app.routers.action_router import create_action_router
from app.routers.push_router import create_push_router
from app.routers.app_auth_router import create_app_auth_router
from app.dependencies.app_auth import require_app_auth

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

    # Repositories
    token_repo = FileTokenRepository(settings.token_store_path)
    push_repo = FilePushRepository(settings.push_store_path)

    # Load stored tokens
    stored_tokens = token_repo.load()

    # Aula client for data fetching (uses stored tokens only, no credentials)
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

    aula_client = AulaClient(
        mitid_username="",  # Not needed for data fetching, only for re-auth
        stored_tokens=stored_tokens.model_dump() if stored_tokens else None,
        on_tokens_updated=_on_tokens_updated,
    )

    # Services
    aula_service = AulaService(aula_client, token_repository=token_repo)
    auth_service = AuthService(
        token_repository=token_repo,
        sync_target_url=settings.sync_target_url,
        admin_secret=settings.admin_secret,
    )
    push_service = PushService(
        push_repository=push_repo,
        vapid_private_key=settings.vapid_private_key,
        vapid_claim_email=settings.vapid_claim_email,
    )
    poller = BackgroundPoller(
        aula_service=aula_service,
        push_service=push_service,
    )

    # Store references on app state
    app.state.aula_client = aula_client
    app.state.aula_service = aula_service
    app.state.auth_service = auth_service
    app.state.push_service = push_service
    app.state.poller = poller

    # Token renewal function for middleware
    def renew_token(refresh_token: str) -> TokenData:
        """Renew the access token using the Aula login client."""
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

    # Middleware (order matters: last added = outermost)
    # TokenRefresh must be INNER (added first), CORS must be OUTER (added last)
    app.add_middleware(
        TokenRefreshMiddleware,
        token_repository=token_repo,
        renew_token_fn=renew_token,
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
            else {"detail": str(exc)}
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
    app.include_router(
        create_auth_router(auth_service, admin_secret=settings.admin_secret),
        dependencies=[Depends(require_app_auth)],
    )
    app.include_router(
        create_data_router(aula_service),
        dependencies=[Depends(require_app_auth)],
    )
    app.include_router(
        create_action_router(aula_service),
        dependencies=[Depends(require_app_auth)],
    )
    app.include_router(
        create_push_router(push_service),
        dependencies=[Depends(require_app_auth)],
    )

    # Background poller — only runs if VAPID keys are configured
    if settings.vapid_private_key:
        scheduler = BackgroundScheduler()
        scheduler.add_job(
            poller.tick,
            "interval",
            seconds=settings.poll_interval,
            id="aula_poller",
            replace_existing=True,
        )
        scheduler.start()
        _LOGGER.info(f"Background poller started (interval: {settings.poll_interval}s)")

        @app.on_event("shutdown")
        def shutdown_scheduler():
            scheduler.shutdown(wait=False)

    return app


app = create_app()
