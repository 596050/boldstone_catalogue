import logging
from datetime import datetime, timezone
from typing import Any

from .auth import GoogleAuth

logger = logging.getLogger(__name__)


class CalendarService:
    """Wrapper around the Google Calendar API (read-only)."""

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        self._service = self._auth.build_service("calendar", "v3")

    def list_events(
        self,
        calendar_id: str = "primary",
        time_min: str | None = None,
        time_max: str | None = None,
        max_results: int = 25,
    ) -> list[dict[str, Any]]:
        """List upcoming events from *calendar_id*.

        *time_min* / *time_max* should be RFC 3339 timestamps.  If
        *time_min* is ``None`` it defaults to now (UTC).
        """
        if time_min is None:
            time_min = datetime.now(timezone.utc).isoformat()

        kwargs: dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": time_min,
            "maxResults": max_results,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if time_max is not None:
            kwargs["timeMax"] = time_max

        resp = self._service.events().list(**kwargs).execute()
        events = resp.get("items", [])
        logger.info("Listed %d events from %s", len(events), calendar_id)
        return events

    def get_event(
        self, event_id: str, calendar_id: str = "primary"
    ) -> dict[str, Any]:
        """Return a single event resource."""
        event = (
            self._service.events()
            .get(calendarId=calendar_id, eventId=event_id)
            .execute()
        )
        return event
