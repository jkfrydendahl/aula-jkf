from pydantic_settings import BaseSettings


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


class AppAuthSettings(BaseSettings):
    app_auth_enabled: bool = True
    app_auth_password: str = ""
    app_session_secret: str = ""
    app_session_cookie_name: str = "aula_jkf_session"
    app_session_ttl_seconds: int = 604800
    # Set to false when testing locally over HTTP (e.g. via SSH tunnel)
    app_session_secure_cookie: bool = True

    model_config = {"env_prefix": "APP_"}
