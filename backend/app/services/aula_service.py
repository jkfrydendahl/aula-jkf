"""AulaService: Facade wrapping the Aula client for data access."""
from typing import Any, Optional
import logging
import time

from app.aula_client import AulaClient, AulaClientError, AulaAuthRequiredError
from app.repositories.token_repository import TokenRepository

_LOGGER = logging.getLogger(__name__)

# Thread cache: {thread_id: (data, timestamp)}
_thread_cache: dict[int, tuple[dict, float]] = {}
_THREAD_CACHE_TTL = 300  # 5 minutes


class AulaService:
    """Wraps the Aula client and normalizes data for API consumption."""

    def __init__(self, client: AulaClient, token_repository: Optional[TokenRepository] = None):
        self._client = client
        self._token_repo = token_repository

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
        """Ensure the client has data; fetch if empty."""
        self._ensure_tokens_loaded()
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
            messages.append({
                "id": str(thread.get("id", "")),
                "subject": thread.get("subject", "(ingen emne)"),
                "sender": sender,
                "timestamp": latest.get("sendDateTime", ""),
                "is_read": thread.get("read", True),
                "preview": latest.get("text", {}).get("html", "")[:150] if isinstance(latest.get("text"), dict) else str(latest.get("text", ""))[:150],
                "child_profile_ids": child_profile_ids,
                "recipients": [r.get("fullName", "") for r in recipients[:5]],
            })
        return messages

    def get_posts(self) -> list[dict[str, Any]]:
        """Return recent posts/opslag."""
        try:
            result = self._client.get_posts(index=0, limit=20)
            raw_posts = result.get("posts", [])
            last_seen = result.get("profileLastSeenPostDate", "")
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

            post_timestamp = post.get("publishAt") or post.get("timestamp", "")
            is_read = bool(last_seen and post_timestamp and post_timestamp <= last_seen)

            # Child association from relatedProfiles
            related = post.get("relatedProfiles", [])
            child_profile_ids = [
                str(rp.get("profileId")) for rp in related
                if isinstance(rp, dict) and rp.get("role") == "child"
            ]

            posts.append({
                "id": str(post.get("id", "")),
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
        cached = _thread_cache.get(thread_id)
        if cached and (time.time() - cached[1]) < _THREAD_CACHE_TTL:
            return cached[0]

        self._ensure_tokens_loaded()
        try:
            data = self._client.get_thread_messages(thread_id)
        except Exception as e:
            _LOGGER.warning(f"Failed to fetch thread {thread_id}: {e}")
            return {"messages": []}

        messages = []
        for msg in data.get("messages", []):
            if msg.get("messageType") == "Message":
                text = ""
                if isinstance(msg.get("text"), dict):
                    text = msg["text"].get("html", "")
                elif msg.get("text"):
                    text = str(msg["text"])

                attachments = []
                for att in msg.get("attachments", []):
                    file_info = att.get("file", {})
                    attachments.append({
                        "id": att.get("id"),
                        "name": att.get("name", file_info.get("name", "unknown")),
                        "url": file_info.get("url", ""),
                    })

                messages.append({
                    "id": str(msg.get("id", "")),
                    "sender": msg.get("sender", {}).get("fullName", "Ukendt"),
                    "timestamp": msg.get("sendDateTime", ""),
                    "text": text,
                    "attachments": attachments,
                })
        result = {
            "subject": data.get("subject", ""),
            "messages": messages,
        }
        _thread_cache[thread_id] = (result, time.time())
        return result

    def mark_thread_read(self, thread_id: int) -> bool:
        """Mark a thread as read."""
        self._ensure_tokens_loaded()
        return self._client.mark_thread_read(thread_id)

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
        return {"success": True, "data": result}

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
        return {"success": True, "data": result}

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
        return {"success": success, "data": result}

    def get_unread_count(self) -> int:
        """Return number of unread messages."""
        return self._client.unread_messages

