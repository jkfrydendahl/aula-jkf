import hashlib
import hmac
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.app_auth_router import create_app_auth_router
from app.session_utils import verify_session_token
from app.settings import AppAuthSettings


def _build_app(settings: AppAuthSettings) -> FastAPI:
    app = FastAPI()
    app.state.app_auth_settings = settings
    app.include_router(create_app_auth_router())
    return app


def test_app_auth_settings_returns_multi_user_configs():
    settings = AppAuthSettings(
        user_1_name="Jesper",
        user_1_password="pw1",
        user_1_token_path="tokens1.json",
        user_1_push_store_path="push1.json",
        user_2_name="Ada",
        user_2_password="pw2",
        user_2_token_path="tokens2.json",
        user_2_push_store_path="push2.json",
    )

    users = settings.get_users()

    assert [user.user_id for user in users] == ["1", "2"]
    assert users[0].name == "Jesper"
    assert users[1].token_path == "tokens2.json"


def test_app_auth_settings_falls_back_to_default_user():
    settings = AppAuthSettings(auth_password="legacy-password")

    users = settings.get_users()

    assert len(users) == 1
    assert users[0].user_id == "default"
    assert users[0].name == ""
    assert users[0].token_path == "data/tokens.json"


def test_verify_session_token_supports_legacy_payload():
    payload = f"app-auth:{int(time.time())}"
    signature = hmac.new("secret".encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = f"{payload}.{signature}"

    assert verify_session_token(token, "secret", 60) == "default"


def test_multi_user_login_and_me_endpoint():
    settings = AppAuthSettings(
        session_secret="secret",
        session_secure_cookie=False,
        user_1_name="Jesper",
        user_1_password="pw1",
        user_2_name="Ada",
        user_2_password="pw2",
    )
    client = TestClient(_build_app(settings))

    users = client.get("/app-auth/users")
    assert users.status_code == 200
    assert users.json() == [
        {"user_id": "1", "name": "Jesper"},
        {"user_id": "2", "name": "Ada"},
    ]

    response = client.post("/app-auth/login", json={"username": "ada", "password": "pw2"})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True}

    me = client.get("/app-auth/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": True, "username": "Ada"}


def test_single_default_user_login_matches_by_password_only():
    settings = AppAuthSettings(
        session_secret="secret",
        session_secure_cookie=False,
        auth_password="legacy-password",
    )
    client = TestClient(_build_app(settings))

    response = client.post(
        "/app-auth/login",
        json={"username": "", "password": "legacy-password"},
    )

    assert response.status_code == 200
    assert verify_session_token(
        response.cookies.get(settings.session_cookie_name),
        settings.session_secret,
        settings.session_ttl_seconds,
    ) == "default"
