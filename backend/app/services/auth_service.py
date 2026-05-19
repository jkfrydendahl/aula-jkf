import time
import uuid
import threading
import logging
from typing import Optional

import httpx

from app.models.schemas import AuthFlowStatus, TokenData
from app.repositories.token_repository import TokenRepository

_LOGGER = logging.getLogger(__name__)


class AuthService:
    """Manages the MitID authentication flow lifecycle."""

    def __init__(self, token_repository: TokenRepository, login_client_class=None,
                 sync_target_url: str = "", admin_secret: str = ""):
        self._token_repository = token_repository
        self._sync_target_url = sync_target_url
        self._admin_secret = admin_secret
        # Default to real AulaLoginClient if not injected (for testing)
        if login_client_class is None:
            from app.aula_login_client.client import AulaLoginClient
            self._login_client_class = AulaLoginClient
        else:
            self._login_client_class = login_client_class
        self._flows: dict = {}

    def start_flow(self, username: str, auth_method: str = "APP",
                   password: Optional[str] = None, token: Optional[str] = None) -> str:
        """Start a new auth flow in a background thread. Returns flow_id."""
        flow_id = str(uuid.uuid4())
        self._flows[flow_id] = {
            "status": AuthFlowStatus.PENDING,
            "message": "Starting MitID authentication...",
            "error": None,
            "identities": None,
            "selected_identity": None,
            "identity_event": threading.Event(),
            "done_event": threading.Event(),
            "thread": None,
            "qr_data": None,
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
        """Get the current status of an auth flow, including live QR codes if available."""
        flow = self._flows.get(flow_id)
        if flow is None:
            return None

        # Try to get QR codes from the live login client
        client = flow.get("_client")
        if client and flow["status"] == AuthFlowStatus.PENDING:
            try:
                qr_svgs = client.get_qr_codes_svg()
                if qr_svgs:
                    flow["qr_svg"] = qr_svgs[0]
                    flow["qr_svg_2"] = qr_svgs[1]
                    flow["message"] = "Scan QR-koden med MitID app"
            except Exception:
                pass  # QR not ready yet

        return flow

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

            # Store client reference so status endpoint can access QR codes
            flow["_client"] = client

            # Set up identity selector callback that blocks until frontend responds
            def identity_selector(identity_names):
                flow["status"] = AuthFlowStatus.IDENTITY_SELECTION
                flow["identities"] = identity_names
                flow["message"] = "Vælg identitet"
                _LOGGER.info(f"Flow {flow_id}: waiting for identity selection from {identity_names}")

                # Block until the frontend selects an identity
                flow["identity_event"].wait(timeout=120)

                selected = flow.get("selected_identity", 1)
                _LOGGER.info(f"Flow {flow_id}: identity {selected} selected")
                flow["status"] = AuthFlowStatus.PENDING
                flow["message"] = "Completing login..."
                return str(selected)

            client.identity_selector = identity_selector

            flow["message"] = "Godkend i MitID app..."
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

                # Auto-sync tokens to remote (Railway) if configured
                self._sync_tokens_to_remote(token_model)

                flow["status"] = AuthFlowStatus.COMPLETE
                flow["message"] = "Login successful"
                _LOGGER.info(f"Flow {flow_id}: authentication complete")
            else:
                flow["status"] = AuthFlowStatus.ERROR
                flow["error"] = "Authentication failed"

        except TimeoutError as e:
            flow["status"] = AuthFlowStatus.ERROR
            flow["error"] = f"MitID timeout: {str(e)}"
        except Exception as e:
            flow["status"] = AuthFlowStatus.ERROR
            flow["error"] = str(e)
            _LOGGER.error(f"Flow {flow_id}: auth failed: {e}")
        finally:
            done_event = flow.get("done_event")
            if done_event:
                done_event.set()

    def _sync_tokens_to_remote(self, tokens: TokenData):
        """Push tokens to the remote Railway instance after local auth."""
        if not self._sync_target_url or not self._admin_secret:
            _LOGGER.debug("Token sync not configured, skipping")
            return

        try:
            url = f"{self._sync_target_url.rstrip('/')}/auth/upload-tokens"
            response = httpx.post(
                url,
                json=tokens.model_dump(),
                headers={"X-Admin-Secret": self._admin_secret},
                timeout=10.0,
            )
            if response.status_code == 200:
                _LOGGER.info(f"Tokens synced to remote: {self._sync_target_url}")
            else:
                _LOGGER.error(f"Token sync failed: {response.status_code} {response.text}")
        except Exception as e:
            _LOGGER.error(f"Token sync error: {e}")

    def upload_tokens(self, tokens: TokenData) -> bool:
        """Accept uploaded tokens (called from the upload endpoint on Railway)."""
        self._token_repository.save(tokens)
        _LOGGER.info("Tokens uploaded and saved successfully")
        return True
