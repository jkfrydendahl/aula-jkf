from pydantic import BaseModel
from enum import Enum
from typing import Optional


class TokenData(BaseModel):
    """Aula OAuth tokens persisted between restarts."""
    access_token: str
    refresh_token: str
    expires_at: float


class AuthFlowStatus(str, Enum):
    PENDING = "pending"
    QR_READY = "qr_ready"
    IDENTITY_SELECTION = "identity_selection"
    COMPLETE = "complete"
    ERROR = "error"


class AuthStartRequest(BaseModel):
    username: str
    auth_method: str = "APP"
    password: Optional[str] = None
    token: Optional[str] = None


class AuthStatusResponse(BaseModel):
    flow_id: str
    status: AuthFlowStatus
    qr_svg: Optional[str] = None
    identities: Optional[list[dict]] = None
    error: Optional[str] = None


class IdentitySelectRequest(BaseModel):
    identity_index: int
