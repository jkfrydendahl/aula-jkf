"""AulaService: Facade wrapping the Aula client for data access."""
from typing import Any, Optional
import logging
import time

from app.aula_client import AulaClient, AulaClientError, AulaAuthRequiredError, REQUEST_TIMEOUT
from app.repositories.token_repository import TokenRepository

_LOGGER = logging.getLogger(__name__)

_THREAD_CACHE_TTL = 300  # 5 minutes


import threading

class AulaService:
    """Wraps the Aula client and normalizes data for API consumption."""

    def __init__(self, client: AulaClient, token_repository: Optional[TokenRepository] = None):
        self._client = client
        self._token_repo = token_repository
        self._load_lock = threading.Lock()
        self._thread_cache: dict[int, tuple[dict, float]] = {}
        self._subscription_id_cache: dict[str, int] = {}
        # Post read-state tracking (in-memory; no Aula API equivalent for posts).
        # _seen_post_ids: used by the poller to detect genuinely *new* posts.
        #   None = uninitialized (first poll seeds baseline, returns 0 new posts).
        # _user_read_post_ids: posts the user has explicitly opened in our app.
        self._seen_post_ids: set[str] | None = None
        self._user_read_post_ids: set[str] = set()
        # Pickup states we've set ourselves — suppresses spurious poller notifications.
        self._known_pickup_states: dict[str, dict] = {}
        # Presence statuses we've set ourselves — suppresses spurious poller notifications.
        self._known_presence_states: dict[str, str] = {}

    def _ensure_tokens_loaded(self):
        """Reload tokens from repository into client if missing or stale."""
        if self._token_repo:
            stored = self._token_repo.load()
            if stored:
                # Reload if client has no tokens or if stored tokens are newer
                current = self._client._tokens
                if (not current or not current.get("access_token") or
                        current.get("access_token") != stored.access_token):
                    self._client._tokens = {
                        "access_token": stored.access_token,
                        "refresh_token": stored.refresh_token,
                        "expires_at": stored.expires_at,
                    }
                    self._client._apply_token_to_session(stored.access_token)
                    _LOGGER.info("Loaded tokens from repository into client")

    @property
    def is_authenticated(self) -> bool:
        """Check if the client has valid tokens."""
        self._ensure_tokens_loaded()
        return bool(self._client._tokens and self._client._tokens.get("access_token"))

    def refresh_data(self) -> None:
        """Call update_data() on the underlying client to refresh all cached data."""
        self._ensure_tokens_loaded()
        if not hasattr(self._client, 'apiurl') or not self._client.apiurl:
            self._client.login()
        self._client.update_data()

    def ensure_data_loaded(self) -> None:
        """Ensure the client has data; fetch if empty. Thread-safe."""
        self._ensure_tokens_loaded()
        if not self._client._children:
            with self._load_lock:
                # Re-check inside lock — another thread may have loaded while we waited
                if not self._client._children:
                    _LOGGER.info("No cached data, calling login() + update_data()")
                    self._client.login()
                    self._client.update_data()

    def get_children(self) -> list[dict[str, Any]]:
        """Return list of child profiles."""
        children = []
        for child in self._client._children:
            children.append({
                "id": str(child["id"]),
                "profile_id": str(child.get("profileId", child["id"])),
                "name": child.get("name", ""),
                "institution": self._client._institutions.get(child["id"], ""),
            })
        return children

    def get_presence(self, child_id: str) -> dict[str, Any]:
        """Return presence info for a child (always fetches fresh data)."""
        self._ensure_tokens_loaded()

        # Fetch fresh daily overview (not cached)
        overview = self._client.get_daily_overview(int(child_id))
        if not overview:
            return {"child_id": child_id, "status": "unknown"}

        # Get the real presence state from Aula
        presence_states = self._client.get_presence_states()
        aula_state = None
        for entry in presence_states:
            if str(entry.get("uniStudentId")) == str(child_id):
                aula_state = entry.get("state")
                break

        # Map Aula state codes to our status strings
        # Known states from getPresenceStates:
        # 0=ikke til stede, 1=syg, 8=gået hjem
        # Unknown yet: which code = "til stede" (checked in)
        state_map = {
            0: "not_present",
            1: "sick",
            8: "checked_out",
        }

        if aula_state is not None:
            status = state_map.get(aula_state, "not_present")
            # Fallback: if state code unknown but checkInTime is set, treat as checked in
            if status == "not_present" and overview.get("checkInTime"):
                status = "checked_in"
        else:
            # Fallback to checkInTime/checkOutTime
            check_in = overview.get("checkInTime")
            check_out = overview.get("checkOutTime")
            if check_out:
                status = "checked_out"
            elif check_in:
                status = "checked_in"
            else:
                status = "not_present"

        # Also check activityType from daily overview as backup
        activity_type = overview.get("activityType", 0)
        if activity_type == 1 and status != "sick":
            status = "sick"
        elif activity_type == 2:
            status = "absent"

        check_in = overview.get("checkInTime")
        check_out = overview.get("checkOutTime")
        location = overview.get("location")
        location_name = location.get("name", "") if isinstance(location, dict) else None

        return {
            "child_id": child_id,
            "status": status,
            "state_code": aula_state,
            "planned_start": overview.get("entryTime"),
            "planned_end": overview.get("exitTime"),
            "check_in_time": check_in,
            "check_out_time": check_out,
            "exit_with": overview.get("exitWith"),
            "location": location_name,
            "comment": overview.get("comment"),
        }

    def get_messages(self) -> list[dict[str, Any]]:
        """Return recent message threads with latest message preview."""
        self._ensure_tokens_loaded()
        try:
            threads = self._client.get_message_threads(page=0)
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch message threads: {e}", exc_info=True)
            return []

        messages = []
        for thread in threads[:20]:
            latest = thread.get("latestMessage", {})
            # Sender from thread creator
            creator = thread.get("creator", {})
            sender = creator.get("fullName", "Ukendt")
            # Child filter: use regardingChildren profileIds
            regarding = thread.get("regardingChildren", [])
            child_profile_ids = [str(rc.get("profileId", "")) for rc in regarding]
            recipients = thread.get("recipients", [])
            thread_id = str(thread.get("id", ""))
            subscription_id = thread.get("subscriptionId") or thread.get("id")
            # Cache subscription ID for use in mark-as-read
            if thread_id:
                self._subscription_id_cache[thread_id] = subscription_id
            # Attachments from latest message (if present in thread list response)
            latest_attachments = latest.get("attachments") or []
            messages.append({
                "id": thread_id,
                "subject": thread.get("subject", "(ingen emne)"),
                "sender": sender,
                "timestamp": latest.get("sendDateTime", ""),
                "is_read": thread.get("read", True),
                "preview": latest.get("text", {}).get("html", "")[:150] if isinstance(latest.get("text"), dict) else str(latest.get("text", ""))[:150],
                "child_profile_ids": child_profile_ids,
                "recipients": [r.get("fullName", "") for r in recipients[:5]],
                "attachments": [{"id": str(a.get("id", "")), "name": a.get("name", "")} for a in latest_attachments],
            })
        return messages

    def get_posts(self) -> list[dict[str, Any]]:
        """Return recent posts/opslag.

        is_read is tracked locally: a post is considered read only after the user
        has explicitly opened it in our app (see mark_post_read).  We do NOT use
        Aula's profileLastSeenPostDate because that field is a profile-level
        watermark updated whenever the user opens the Aula website — not a per-post
        indicator — which caused every post to appear read.
        """
        try:
            result = self._client.get_posts(index=0, limit=20)
            raw_posts = result.get("posts", [])
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch posts: {e}")
            return []

        posts = []
        for post in raw_posts:
            content = post.get("content", {})
            html = content.get("html", "") if isinstance(content, dict) else str(content)

            owner = post.get("ownerProfile", {})
            sender = owner.get("fullName", "Ukendt") if isinstance(owner, dict) else "Ukendt"
            institution = ""
            if isinstance(owner, dict) and isinstance(owner.get("institution"), dict):
                institution = owner["institution"].get("institutionName", "")

            attachments = []
            for att in post.get("attachments", []):
                file_info = att.get("file") or {}
                attachments.append({
                    "id": att.get("id"),
                    "name": att.get("name") or file_info.get("name", "unknown"),
                    "url": file_info.get("url", ""),
                })

            post_id = str(post.get("id", ""))
            post_timestamp = post.get("publishAt") or post.get("timestamp", "")
            # Read status is managed locally — only True after mark_post_read() is called.
            is_read = post_id in self._user_read_post_ids

            # Child association from relatedProfiles
            related = post.get("relatedProfiles", [])
            child_profile_ids = [
                str(rp.get("profileId")) for rp in related
                if isinstance(rp, dict) and rp.get("role") == "child"
            ]

            posts.append({
                "id": post_id,
                "title": post.get("title", "(intet emne)"),
                "content": html,
                "sender": sender,
                "institution": institution,
                "timestamp": post_timestamp,
                "is_important": post.get("isImportant", False),
                "is_read": is_read,
                "allow_comments": post.get("allowComments", False),
                "comment_count": post.get("commentCount", 0),
                "attachments": attachments,
                "child_profile_ids": child_profile_ids,
            })
        return posts

    def mark_post_read(self, post_id: str) -> bool:
        """Mark a post as read in our local tracking set."""
        self._user_read_post_ids.add(post_id)
        return True

    def mark_post_unread(self, post_id: str) -> bool:
        """Mark a post as unread in our local tracking set."""
        self._user_read_post_ids.discard(post_id)
        return True

    def get_vacation_registrations(self) -> list[dict[str, Any]]:
        """Return pending vacation registrations for all children."""
        try:
            raw_data = self._client.get_vacation_registrations()
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch vacation registrations: {e}")
            return []

        registrations = []
        for child_entry in (raw_data or []):
            child = child_entry.get("child", {})
            child_name = child.get("name", "Ukendt")
            child_id = str(child.get("id", ""))
            child_profile_id = str(child.get("profileId", ""))

            for reg in child_entry.get("vacationRegistrations", []):
                registrations.append({
                    "id": reg.get("vacationRegistrationId"),
                    "response_id": reg.get("responseId"),
                    "title": reg.get("title", ""),
                    "note": reg.get("noteToGuardian", ""),
                    "start_date": reg.get("startDate", ""),
                    "end_date": reg.get("endDate", ""),
                    "deadline": reg.get("responseDeadline", ""),
                    "is_editable": reg.get("isEditable", False),
                    "is_missing_answer": reg.get("isMissingAnswer", False),
                    "child_name": child_name,
                    "child_id": child_id,
                    "child_profile_id": child_profile_id,
                })
        return registrations

    def submit_vacation_response(self, response_id: int, child_id: int, days: list[dict], comment: str | None = None) -> dict[str, Any]:
        """Submit a vacation registration response."""
        result = self._client.submit_vacation_response(response_id, child_id, days, comment)
        status = result.get("status", {})
        if status.get("code") == 0:
            return {"success": True}
        return {"success": False, "error": status.get("message", "Unknown error")}

    def get_thread_detail(self, thread_id: int) -> dict[str, Any]:
        """Return full messages for a specific thread (cached for 5 min)."""
        # Check cache first
        cached = self._thread_cache.get(thread_id)
        if cached and (time.time() - cached[1]) < _THREAD_CACHE_TTL:
            return cached[0]

        self._ensure_tokens_loaded()
        try:
            data = self._client.get_thread_messages(thread_id)
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch thread {thread_id}: {e}")
            return {"messages": []}

        messages = []
        for msg in (data.get("messages") or []):
            if msg.get("messageType") == "Message":
                text = ""
                if isinstance(msg.get("text"), dict):
                    text = msg["text"].get("html", "")
                elif msg.get("text"):
                    text = str(msg["text"])

                attachments = []
                for att in (msg.get("attachments") or []):
                    file_info = att.get("file") or {}
                    attachments.append({
                        "id": att.get("id"),
                        "name": att.get("name", file_info.get("name", "unknown")),
                        "url": file_info.get("url", ""),
                    })

                messages.append({
                    "id": str(msg.get("id", "")),
                    "sender": (msg.get("sender") or {}).get("fullName", "Ukendt"),
                    "timestamp": msg.get("sendDateTime", ""),
                    "text": text,
                    "attachments": attachments,
                })
        result = {
            "subject": data.get("subject", ""),
            "messages": messages,
        }
        self._thread_cache[thread_id] = (result, time.time())
        return result

    def mark_thread_read(self, thread_id: int) -> bool:
        """Mark a thread as read using subscription ID."""
        self._ensure_tokens_loaded()
        subscription_id = self._subscription_id_cache.get(str(thread_id), thread_id)
        return self._client.mark_thread_read(thread_id, subscription_id=subscription_id)

    def mark_thread_unread(self, thread_id: int) -> bool:
        """Mark a thread as unread."""
        self._ensure_tokens_loaded()
        subscription_id = self._subscription_id_cache.get(str(thread_id), thread_id)
        return self._client.mark_thread_unread(thread_id, subscription_id=subscription_id)

    def get_calendar(self, child_id: str) -> list[dict[str, Any]]:
        """Return calendar events for a child."""
        events = []
        if hasattr(self._client, '_skoleskema') and child_id in self._client._skoleskema:
            for event in self._client._skoleskema[child_id]:
                events.append({
                    "title": event.get("title", ""),
                    "start": event.get("startDateTime", ""),
                    "end": event.get("endDateTime", ""),
                    "all_day": event.get("allDay", False),
                    "description": event.get("description", ""),
                })
        return events

    def get_ugeplan(self, child_id: str) -> dict[str, Any]:
        """Return weekly plan for a child."""
        if hasattr(self._client, 'ugeplaner') and child_id in self._client.ugeplaner:
            return self._client.ugeplaner[child_id]
        return {}

    def send_message(self, recipient_id: str, subject: str, text: str) -> dict[str, Any]:
        """Send a message via the Aula API."""
        result = self._client.custom_api_call(
            uri="messaging.sendMessage",
            post_data={
                "subject": subject,
                "text": {"html": text},
                "recipients": [{"id": int(recipient_id)}],
            },
        )
        success = (result.get("status") or {}).get("message") == "OK"
        return {"success": success, "data": result}

    def update_presence(self, child_id: str, status: str) -> dict[str, Any]:
        """Update child presence status (check-in via updateDailyOverview)."""
        import json
        result = self._client.custom_api_call(
            uri="presence.updateDailyOverview",
            post_data=json.dumps({
                "childId": int(child_id),
                "status": status,
            }),
        )
        success = (result.get("status") or {}).get("message") == "OK"
        if success:
            # Pre-acknowledge so the poller doesn't fire a notification for our own change.
            self._known_presence_states[str(child_id)] = status
        return {"success": success, "data": result}

    def update_sick_status(self, child_id: str, is_sick: bool) -> dict[str, Any]:
        """Mark child as sick or not sick."""
        self._ensure_tokens_loaded()
        csrf_token = self._client._get_csrf_token()
        headers = {"content-type": "application/json"}
        if csrf_token:
            headers["csrfp-token"] = csrf_token
        payload = {
            "institutionProfileIds": [int(child_id)],
            "status": 1 if is_sick else 0,
        }
        res = self._client._session.post(
            self._client.apiurl
            + "?method=presence.updateStatusByInstitutionProfileIds"
            + self._client._get_access_token_param(),
            json=payload,
            headers=headers,
            verify=True,
            timeout=REQUEST_TIMEOUT,
        )
        data = res.json()
        success = data.get("status", {}).get("message") == "OK"
        return {"success": success, "data": data}

    def get_pickup_responsibles(self, child_id: str) -> list[dict[str, Any]]:
        """Return pickup responsibles for a child."""
        self._ensure_tokens_loaded()
        raw = self._client.get_pickup_responsibles(int(child_id))
        # raw is list of {uniStudentId, relatedPersons: [...]}
        responsibles = []
        for entry in raw:
            for person in entry.get("relatedPersons", []):
                responsibles.append({
                    "id": str(person.get("institutionProfileId", "")),
                    "name": person.get("name", ""),
                    "relation": person.get("relation", ""),
                })
        return responsibles

    def get_go_home_with_list(self, child_id: str) -> list[dict[str, Any]]:
        """Return list of children that this child can go home with."""
        self._ensure_tokens_loaded()
        raw = self._client.get_go_home_with_list(int(child_id))
        children = []
        for entry in raw:
            children.append({
                "id": str(entry.get("institutionProfileId", "")),
                "name": entry.get("fullName", ""),
                "group": entry.get("mainGroup", ""),
            })
        return children

    def update_presence_template(
        self,
        child_id: str,
        date: str,
        activity_type: int,
        entry_time: str,
        exit_time: str,
        exit_with: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Update presence template (pickup/departure info)."""
        self._ensure_tokens_loaded()

        # Build presenceActivity based on activityType
        if activity_type == 0:
            # Hentes af (pickup)
            presence_activity = {
                "activityType": 0,
                "pickup": {
                    "entryTime": entry_time,
                    "exitTime": exit_time,
                    "exitWith": exit_with or "",
                },
            }
        elif activity_type == 1:
            # Selvbestemmer (self-decider)
            presence_activity = {
                "activityType": 1,
                "selfDecider": {
                    "entryTime": entry_time,
                    "exitStartTime": "",
                    "exitEndTime": "",
                },
            }
        elif activity_type == 2:
            # Send hjem
            presence_activity = {
                "activityType": 2,
                "sendHome": {
                    "entryTime": entry_time,
                    "exitTime": exit_time,
                },
            }
        elif activity_type == 3:
            # Gå hjem med
            presence_activity = {
                "activityType": 3,
                "goHomeWith": {
                    "entryTime": entry_time,
                    "exitTime": exit_time,
                    "exitWith": exit_with or "",
                },
            }
        else:
            return {"success": False, "error": f"Unknown activityType: {activity_type}"}

        result = self._client.update_presence_template(
            institution_profile_id=int(child_id),
            date=date,
            presence_activity=presence_activity,
            comment=comment,
        )

        success = result.get("status", {}).get("message") == "OK"
        if success:
            # Update our known pickup state so the poller doesn't fire a
            # spurious "pickup changed" notification for our own change.
            self._known_pickup_states[str(child_id)] = {
                "activity_type": activity_type,
                "exit_with": exit_with or "",
            }
        return {"success": success, "data": result}

    def get_unread_count(self) -> int:
        """Return number of unread messages."""
        return self._client.unread_messages

    def refresh_messages(self) -> None:
        """Fetch fresh message threads from Aula and update unread count."""
        try:
            self.ensure_data_loaded()
            threads = self._client.get_message_threads(page=0)
            self._client._threads = threads
            self._client.unread_messages = sum(
                1 for thread in threads if not thread.get("read", True)
            )
        except Exception as e:
            _LOGGER.warning(f"refresh_messages failed: {e}")

    def refresh_all(self) -> None:
        """Fetch fresh data for all event types (messages, vacation)."""
        self.refresh_messages()
        try:
            self.ensure_data_loaded()
            self._client.get_vacation_registrations()
        except Exception as e:
            _LOGGER.warning(f"refresh_all partial failure: {e}")

    def get_new_item_counts(self) -> dict[str, int]:
        """Return counts of new/unread items across all event types."""
        try:
            threads = self._client._threads or []
            unread_messages = sum(1 for t in threads if not t.get("read", True))
        except Exception:
            unread_messages = self._client.unread_messages

        try:
            result = self._client.get_posts(index=0, limit=20)
            raw_posts = result.get("posts", [])
            current_ids = {str(p.get("id", "")) for p in raw_posts if p.get("id")}

            if self._seen_post_ids is None:
                # First poll: seed baseline so we don't spam notifications for
                # pre-existing posts on startup.
                self._seen_post_ids = current_ids
                unread_posts = 0
            else:
                new_ids = current_ids - self._seen_post_ids
                unread_posts = len(new_ids)
                # Grow the seen set so each new post only triggers once.
                self._seen_post_ids = self._seen_post_ids | current_ids
        except Exception:
            unread_posts = 0

        try:
            raw_vacation = self._client.get_vacation_registrations() or []
            pending_vacations = sum(
                1 for child_entry in raw_vacation
                for reg in child_entry.get("vacationRegistrations", [])
                if reg.get("isMissingAnswer", False)
            )
        except Exception:
            pending_vacations = 0

        return {
            "messages": unread_messages,
            "posts": unread_posts,
            "vacations": pending_vacations,
        }

    def get_pickup_states(self) -> dict[str, dict]:
        """Return pickup state for each child.

        Returns:
            {child_id: {"activity_type": int, "exit_with": str}}
            activity_type: 0=hentes af, 1=selvbestemmer, 2=send hjem, 3=gå hjem med
        """
        self._ensure_tokens_loaded()
        states: dict[str, dict] = {}
        for child in self._client._children:
            child_id = str(child["id"])
            try:
                overview = self._client.get_daily_overview(int(child_id))
                if overview:
                    states[child_id] = {
                        "activity_type": overview.get("activityType", 0),
                        "exit_with": overview.get("exitWith") or "",
                    }
            except Exception as e:
                _LOGGER.warning(f"get_pickup_states failed for child {child_id}: {e}")
        return states

    def get_presence_states_for_poller(self) -> dict[str, str]:
        """Return {child_id: status} for all children. Used by the poller to detect check-ins."""
        self._ensure_tokens_loaded()
        states: dict[str, str] = {}
        for child in self._client._children:
            child_id = str(child["id"])
            try:
                presence = self.get_presence(child_id)
                states[child_id] = presence.get("status", "unknown")
            except Exception as e:
                _LOGGER.warning(f"get_presence_states_for_poller failed for child {child_id}: {e}")
        return states

    def get_child_name(self, child_id: str) -> str:
        """Return the display name for a child by ID, falling back to the ID itself."""
        for child in self._client._children:
            if str(child["id"]) == str(child_id):
                return child.get("name", child_id)
        return child_id
