import json
from pathlib import Path
from pydantic import BaseModel


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict[str, str]


class PushRepository:
    """Abstract push subscription storage."""

    def save(self, subscription: PushSubscription) -> None:
        raise NotImplementedError

    def remove(self, endpoint: str) -> None:
        raise NotImplementedError

    def load_all(self) -> list[PushSubscription]:
        raise NotImplementedError


class FilePushRepository(PushRepository):
    """File-based push subscription storage."""

    def __init__(self, path: str):
        self._path = Path(path)

    def save(self, subscription: PushSubscription) -> None:
        subs = self.load_all()
        # Replace if same endpoint exists
        subs = [s for s in subs if s.endpoint != subscription.endpoint]
        subs.append(subscription)
        self._write(subs)

    def remove(self, endpoint: str) -> None:
        subs = [s for s in self.load_all() if s.endpoint != endpoint]
        self._write(subs)

    def load_all(self) -> list[PushSubscription]:
        if not self._path.exists():
            return []
        data = json.loads(self._path.read_text())
        return [PushSubscription(**item) for item in data]

    def _write(self, subs: list[PushSubscription]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([s.model_dump() for s in subs], indent=2))
