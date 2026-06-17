from pydantic import BaseModel
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


class UserConfig(BaseModel):
    user_id: str
    name: str
    password: str
    token_path: str
    push_store_path: str


class AppAuthSettings(BaseSettings):
    auth_enabled: bool = True
    session_secret: str = ""
    session_cookie_name: str = "aula_jkf_session"
    session_ttl_seconds: int = 604800
    session_secure_cookie: bool = True

    # Single-user backward compat
    auth_password: str = ""

    # Multi-user
    user_1_name: str = ""
    user_1_password: str = ""
    user_1_token_path: str = "data/tokens_user1.json"
    user_1_push_store_path: str = "data/push_subs_user1.json"

    user_2_name: str = ""
    user_2_password: str = ""
    user_2_token_path: str = "data/tokens_user2.json"
    user_2_push_store_path: str = "data/push_subs_user2.json"

    model_config = {"env_prefix": "APP_"}

    def get_users(self) -> list[UserConfig]:
        users: list[UserConfig] = []
        if self.user_1_name and self.user_1_password:
            users.append(
                UserConfig(
                    user_id="1",
                    name=self.user_1_name,
                    password=self.user_1_password,
                    token_path=self.user_1_token_path,
                    push_store_path=self.user_1_push_store_path,
                )
            )
        if self.user_2_name and self.user_2_password:
            users.append(
                UserConfig(
                    user_id="2",
                    name=self.user_2_name,
                    password=self.user_2_password,
                    token_path=self.user_2_token_path,
                    push_store_path=self.user_2_push_store_path,
                )
            )
        if not users and self.auth_password:
            users.append(
                UserConfig(
                    user_id="default",
                    name="",
                    password=self.auth_password,
                    token_path="data/tokens.json",
                    push_store_path="data/push_subs.json",
                )
            )
        return users
