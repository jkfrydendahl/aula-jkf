import hashlib
import hmac
import time

try:
    from itsdangerous import BadSignature, SignatureExpired, TimestampSigner
except Exception:  # pragma: no cover
    TimestampSigner = None
    BadSignature = Exception
    SignatureExpired = Exception


def create_session_token(secret: str, ttl_seconds: int) -> str:
    _ = ttl_seconds
    if TimestampSigner is not None:
        signer = TimestampSigner(secret)
        token = signer.sign("app-auth")
        return token.decode() if isinstance(token, bytes) else token

    issued_at = int(time.time())
    payload = f"app-auth:{issued_at}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_session_token(token: str, secret: str, max_age: int) -> bool:
    if TimestampSigner is not None:
        signer = TimestampSigner(secret)
        try:
            signer.unsign(token, max_age=max_age)
            return True
        except (BadSignature, SignatureExpired):
            return False

    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        _, issued_at = payload.split(":", 1)
        return int(time.time()) - int(issued_at) <= max_age
    except Exception:
        return False
