from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # MitID credentials
    mitid_username: str = ""
    mitid_password: Optional[str] = None
    mitid_token: Optional[str] = None
    auth_method: str = "APP"

    # Aula
    poll_interval: int = 300

    # VAPID keys for Web Push
    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_claim_email: str = ""

    # Storage paths
    token_store_path: str = "data/tokens.json"
    push_store_path: str = "data/push_subs.json"

    # CORS
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_prefix": "AULA_"}
