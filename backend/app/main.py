from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.settings import Settings


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

    return app
