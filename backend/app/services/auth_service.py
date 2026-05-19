import time
import uuid
import threading
import logging
from typing import Optional

from app.models.schemas import AuthFlowStatus, TokenData
from app.repositories.token_repository import TokenRepository

_LOGGER = logging.getLogger(__name__)


class AuthService:
    """Manages the MitID authentication flow lifecycle."""

    def __init__(self, token_repository: TokenRepository, login_client_class=None):
        self._token_repository = token_repository
        self._login_client_class = login_client_class
        self._flows: dict = {}

    def start_flow(self, username: str, auth_method: str = "APP",
                   password: Optional[str] = None, token: Optional[str] = None) -> str:
        """Start a new auth flow in a background thread. Returns flow_id."""
        flow_id = str(uuid.uuid4())
        self._flows[flow_id] = {
            "status": AuthFlowStatus.PENDING,
            "error": None,
            "thread": None,
            "done_event": threading.Event(),
        }

        thread = threading.Thread(
            target=self._run_auth_flow,
            args=(flow_id, username, auth_method, password, token),
            daemon=True,
        )
        self._flows[flow_id]["thread"] = thread
        thread.start()
        return flow_id

    def get_status(self, flow_id: str) -> Optional[dict]:
        """Get the current status of an auth flow."""
        return self._flows.get(flow_id)

    def select_identity(self, flow_id: str, identity_index: int) -> bool:
        """Select an identity for a flow waiting on identity selection."""
        flow = self._flows.get(flow_id)
        if not flow or flow["status"] != AuthFlowStatus.IDENTITY_SELECTION:
            return False
        flow["selected_identity"] = identity_index
        event = flow.get("identity_event")
        if event:
            event.set()
        return True

    def _wait_for_flow(self, flow_id: str, timeout: float = 30):
        """Wait for a flow to complete (for testing)."""
        flow = self._flows.get(flow_id)
        if flow and "done_event" in flow:
            flow["done_event"].wait(timeout=timeout)

    def _run_auth_flow(self, flow_id: str, username: str, auth_method: str,
                       password: Optional[str], token: Optional[str]):
        """Run the full auth flow in a background thread."""
        flow = self._flows[flow_id]
        try:
            client = self._login_client_class(
                mitid_username=username,
                auth_method=auth_method,
                mitid_password=password,
                mitid_token=token,
            )

            result = client.authenticate()

            if result.get("success"):
                tokens_data = result["tokens"]
                expires_at = time.time() + tokens_data.get("expires_in", 3600)
                token_model = TokenData(
                    access_token=tokens_data["access_token"],
                    refresh_token=tokens_data["refresh_token"],
                    expires_at=expires_at,
                )
                self._token_repository.save(token_model)
                flow["status"] = AuthFlowStatus.COMPLETE
            else:
                flow["status"] = AuthFlowStatus.ERROR
                flow["error"] = "Authentication failed"

        except TimeoutError as e:
            flow["status"] = AuthFlowStatus.ERROR
            flow["error"] = f"MitID timeout: {str(e)}"
        except Exception as e:
            flow["status"] = AuthFlowStatus.ERROR
            flow["error"] = str(e)
        finally:
            done_event = flow.get("done_event")
            if done_event:
                done_event.set()
