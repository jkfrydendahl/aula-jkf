from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
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

    # Token sync: secret to protect the upload endpoint
    admin_secret: str = ""

    # Token sync: remote URL to push tokens to after local auth
    # Set this on local instance to auto-sync to Railway after login
    sync_target_url: str = ""

    model_config = {"env_prefix": "AULA_"}
