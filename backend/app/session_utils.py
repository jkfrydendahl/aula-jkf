import hashlib
import hmac
import time

try:
    from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
except Exception:  # pragma: no cover
    TimestampSigner = None
    BadSignature = Exception
    SignatureExpired = Exception


def _decode_payload(payload: str | bytes) -> str:
    return payload.decode() if isinstance(payload, bytes) else payload


def create_session_token(secret: str, user_id: str, ttl_seconds: int) -> str:
    _ = ttl_seconds
    payload = f"user:{user_id}"
    if TimestampSigner is not None:
        signer = TimestampSigner(secret)
        token = signer.sign(payload)
        return token.decode() if isinstance(token, bytes) else token

    issued_at = int(time.time())
    signed_payload = f"{payload}:{issued_at}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"{signed_payload}.{signature}"


def verify_session_token(token: str, secret: str, max_age: int) -> str | None:
    if TimestampSigner is not None:
        signer = TimestampSigner(secret)
        try:
            payload = _decode_payload(signer.unsign(token, max_age=max_age))
            if payload == "app-auth":
                return "default"
            if payload.startswith("user:"):
                return payload.split(":", 1)[1]
            return None
        except (BadSignature, SignatureExpired):
            return None

    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        if payload.startswith("app-auth:"):
            _, issued_at = payload.split(":", 1)
            if int(time.time()) - int(issued_at) <= max_age:
                return "default"
            return None
        if payload.startswith("user:"):
            _, user_id, issued_at = payload.split(":", 2)
            if int(time.time()) - int(issued_at) <= max_age:
                return user_id
            return None
    except Exception:
        return None
    return None
