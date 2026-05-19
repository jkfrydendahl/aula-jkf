from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import Settings
from app.aula_client import AulaClient
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

    # Aula client with token persistence callback
    aula_client = AulaClient(
        mitid_username=settings.mitid_username,
        auth_method=settings.auth_method,
        mitid_password=settings.mitid_password,
        mitid_token=settings.mitid_token,
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

    # Middleware
    app.add_middleware(
        TokenRefreshMiddleware,
        token_repository=token_repo,
        renew_token_fn=None,  # TODO: wire to aula_client.renew_access_token
    )

    # Routers
    app.include_router(create_auth_router(auth_service))
    app.include_router(create_data_router(aula_service))
    app.include_router(create_action_router(aula_service))
    app.include_router(create_push_router(push_service))

    return app

