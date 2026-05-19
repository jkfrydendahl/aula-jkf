from pydantic import BaseModel


class TokenData(BaseModel):
    """Aula OAuth tokens persisted between restarts."""
    access_token: str
    refresh_token: str
    expires_at: float
