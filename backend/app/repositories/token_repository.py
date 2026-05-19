from abc import ABC, abstractmethod
import json
import os
from pathlib import Path

from app.models.schemas import TokenData


class TokenRepository(ABC):
    """Abstract interface for token persistence."""

    @abstractmethod
    def save(self, tokens: TokenData) -> None: ...

    @abstractmethod
    def load(self) -> TokenData | None: ...

    @abstractmethod
    def delete(self) -> None: ...


class FileTokenRepository(TokenRepository):
    """Persists tokens as JSON on disk."""

    def __init__(self, path: str):
        self._path = Path(path)

    def save(self, tokens: TokenData) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(tokens.model_dump_json(indent=2))

    def load(self) -> TokenData | None:
        if not self._path.exists():
            return None
        data = json.loads(self._path.read_text())
        return TokenData(**data)

    def delete(self) -> None:
        if self._path.exists():
            self._path.unlink()
