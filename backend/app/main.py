import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import Settings
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


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title="Aula PWA Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings

    # Repositories
    token_repo = FileTokenRepository(settings.token_store_path)
    push_repo = FilePushRepository(settings.push_store_path)

    # Load stored tokens
    stored_tokens = token_repo.load()

    # Aula client for data fetching (uses stored tokens only, no credentials)
    aula_client = AulaClient(
        mitid_username="",  # Not needed for data fetching, only for re-auth
        stored_tokens=stored_tokens.model_dump() if stored_tokens else None,
        on_tokens_updated=lambda tokens: token_repo.save(tokens),
    )

    # Services
    aula_service = AulaService(aula_client)
    auth_service = AuthService(token_repository=token_repo)
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
        # The login client's renew uses its internal session and client_id
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

    # Middleware
    app.add_middleware(
        TokenRefreshMiddleware,
        token_repository=token_repo,
        renew_token_fn=renew_token,
    )

    # Routers
    app.include_router(create_auth_router(auth_service))
    app.include_router(create_data_router(aula_service))
    app.include_router(create_action_router(aula_service))
    app.include_router(create_push_router(push_service))

    return app

