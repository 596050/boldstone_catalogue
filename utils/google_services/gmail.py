import base64
import email.utils
import logging
from collections import defaultdict
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from .auth import GoogleAuth

logger = logging.getLogger(__name__)


class GmailService:
    """Wrapper around the Gmail API for drafts and messages."""

    def __init__(self, auth: GoogleAuth | None = None):
        self._auth = auth or GoogleAuth()
        self._service = self._auth.build_service("gmail", "v1")
        self._user_email: str | None = None

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _build_mime_message(to: str, subject: str, html_body: str) -> str:
        """Build a MIME multipart message and return its base64url-encoded form."""
        msg = MIMEMultipart("alternative")
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
        return raw

    # -- drafts --------------------------------------------------------------

    def create_draft(self, to: str, subject: str, html_body: str) -> dict[str, Any]:
        """Create a Gmail draft and return the draft resource."""
        raw = self._build_mime_message(to, subject, html_body)
        body = {"message": {"raw": raw}}
        draft = (
            self._service.users()
            .drafts()
            .create(userId="me", body=body)
            .execute()
        )
        logger.info("Created draft id=%s", draft.get("id"))
        return draft

    def list_drafts(self, max_results: int = 20) -> list[dict[str, Any]]:
        """Return a list of draft summaries."""
        resp = (
            self._service.users()
            .drafts()
            .list(userId="me", maxResults=max_results)
            .execute()
        )
        drafts = resp.get("drafts", [])
        logger.info("Listed %d drafts", len(drafts))
        return drafts

    def get_draft(self, draft_id: str) -> dict[str, Any]:
        """Return the full draft resource for *draft_id*."""
        draft = (
            self._service.users()
            .drafts()
            .get(userId="me", id=draft_id)
            .execute()
        )
        return draft

    # -- messages ------------------------------------------------------------

    def list_messages(
        self, query: str = "", max_results: int = 20
    ) -> list[dict[str, Any]]:
        """List messages matching a Gmail search *query* (e.g. ``is:unread``)."""
        resp = (
            self._service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = resp.get("messages", [])
        logger.info("Listed %d messages (query=%r)", len(messages), query)
        return messages

    def get_message(self, message_id: str) -> dict[str, Any]:
        """Return the full message resource for *message_id*."""
        msg = (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id)
            .execute()
        )
        return msg

    # -- parsing helpers (private) -------------------------------------------

    def _get_user_email(self) -> str:
        """Lazy-load and cache the authenticated user's email address."""
        if self._user_email is None:
            profile = (
                self._service.users()
                .getProfile(userId="me")
                .execute()
            )
            self._user_email = profile["emailAddress"].lower()
        return self._user_email

    @staticmethod
    def _extract_domain(addr: str) -> str:
        """Return the lowercased domain part of an email address."""
        return addr.rsplit("@", 1)[-1].lower()

    @staticmethod
    def _get_participants(msg: dict[str, Any]) -> set[str]:
        """Return the set of all email addresses on a parsed message."""
        addrs: set[str] = set()
        addrs.add(msg["from_email"])
        addrs.update(msg["to"])
        addrs.update(msg["cc"])
        addrs.discard("")
        return addrs

    @staticmethod
    def _is_self_sent(msg: dict[str, Any]) -> bool:
        """True when the only recipient is the sender (sent to themselves)."""
        recipients = set(msg["to"]) | set(msg["cc"])
        recipients.discard("")
        return recipients == {msg["from_email"]}

    @staticmethod
    def _decode_body(payload: dict) -> tuple[str, str]:
        """Walk a Gmail payload tree and return ``(html_body, text_body)``."""
        html_body = ""
        text_body = ""

        def _walk(part: dict) -> None:
            nonlocal html_body, text_body
            mime = part.get("mimeType", "")
            body_data = part.get("body", {}).get("data")
            if body_data:
                decoded = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
                if mime == "text/html" and not html_body:
                    html_body = decoded
                elif mime == "text/plain" and not text_body:
                    text_body = decoded
            for sub in part.get("parts", []):
                _walk(sub)

        _walk(payload)
        return html_body, text_body

    @classmethod
    def _parse_message(cls, raw_msg: dict) -> dict[str, Any]:
        """Normalise a full Gmail API message resource into a flat dict."""
        payload = raw_msg.get("payload", {})
        headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

        # Parse address lists via stdlib
        to_pairs = email.utils.getaddresses([headers.get("to", "")])
        cc_pairs = email.utils.getaddresses([headers.get("cc", "")])
        from_name, from_email = email.utils.parseaddr(headers.get("from", ""))

        html_body, text_body = cls._decode_body(payload)

        return {
            "id": raw_msg.get("id", ""),
            "thread_id": raw_msg.get("threadId", ""),
            "subject": headers.get("subject", ""),
            "from_email": from_email.lower(),
            "from_name": from_name,
            "to": [addr.lower() for _, addr in to_pairs if addr],
            "cc": [addr.lower() for _, addr in cc_pairs if addr],
            "date": headers.get("date", ""),
            "snippet": raw_msg.get("snippet", ""),
            "label_ids": raw_msg.get("labelIds", []),
            "html_body": html_body,
            "text_body": text_body,
        }

    # -- inbox reading -------------------------------------------------------

    def get_inbox(
        self, query: str = "", max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch inbox messages, returning a list of parsed message dicts.

        Parameters
        ----------
        query:
            Gmail search query (e.g. ``"is:unread"``).  Passed through to
            :meth:`list_messages`.
        max_results:
            Maximum number of messages to fetch.
        """
        summaries = self.list_messages(query=query, max_results=max_results)
        parsed: list[dict[str, Any]] = []
        for summary in summaries:
            raw = self.get_message(summary["id"])
            parsed.append(self._parse_message(raw))
        logger.info("get_inbox returned %d parsed messages", len(parsed))
        return parsed

    # -- filtering by recipient ----------------------------------------------

    @staticmethod
    def filter_by_recipient(
        messages: list[dict[str, Any]], addr: str
    ) -> list[dict[str, Any]]:
        """Return messages where *addr* appears in ``to``, ``cc``, or ``from_email``.

        Comparison is case-insensitive.
        """
        target = addr.lower()
        return [
            m
            for m in messages
            if target == m["from_email"]
            or target in m["to"]
            or target in m["cc"]
        ]

    # -- grouping by organisation (domain) -----------------------------------

    def group_by_organisation(
        self, messages: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Group messages by the domain of external participants.

        The authenticated user's own domain is excluded.  Each message may
        appear under multiple domain keys if it involves participants from
        more than one external organisation.
        """
        user_email = self._get_user_email()
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for msg in messages:
            addrs = set(msg["to"]) | set(msg["cc"]) | {msg["from_email"]}
            addrs.discard(user_email)
            seen_domains: set[str] = set()
            for a in addrs:
                domain = self._extract_domain(a)
                if domain and domain not in seen_domains:
                    seen_domains.add(domain)
                    groups[domain].append(msg)
        return dict(groups)

    # -- grouping by thread --------------------------------------------------

    @staticmethod
    def group_by_thread(
        messages: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Group messages by ``thread_id``, sorted by date within each thread."""
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for msg in messages:
            groups[msg["thread_id"]].append(msg)
        # Sort each thread's messages by the Date header
        for thread_msgs in groups.values():
            thread_msgs.sort(
                key=lambda m: email.utils.parsedate_to_datetime(m["date"])
                if m["date"]
                else email.utils.parsedate_to_datetime("1 Jan 1970 00:00:00 +0000"),
            )
        return dict(groups)

    # -- enriched draft listing ----------------------------------------------

    def list_drafts_parsed(
        self, max_results: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch drafts and return normalised message dicts via :meth:`_parse_message`."""
        summaries = self.list_drafts(max_results=max_results)
        parsed: list[dict[str, Any]] = []
        for summary in summaries:
            full = self.get_draft(summary["id"])
            msg_resource = full.get("message", {})
            parsed.append(self._parse_message(msg_resource))
        logger.info("list_drafts_parsed returned %d drafts", len(parsed))
        return parsed

    # -- thread-level contact analysis ---------------------------------------

    def get_thread_contacts(
        self, messages: list[dict[str, Any]], addr: str
    ) -> set[str]:
        """Return every email address that shares a thread with *addr*.

        Self-sent messages (where the only recipient is the sender) are
        excluded.  The target *addr* itself and the authenticated user's
        own address are stripped from the result so only "other people"
        are returned.
        """
        target = addr.lower()
        user_email = self._get_user_email()

        # Build thread_id -> set of participants (skipping self-sent)
        thread_participants: dict[str, set[str]] = defaultdict(set)
        for msg in messages:
            if self._is_self_sent(msg):
                continue
            thread_participants[msg["thread_id"]].update(
                self._get_participants(msg)
            )

        # Collect addresses from every thread the target appears in
        contacts: set[str] = set()
        for _tid, participants in thread_participants.items():
            if target in participants:
                contacts.update(participants)

        contacts.discard(target)
        contacts.discard(user_email)
        contacts.discard("")
        return contacts

    def get_thread_contact_groups(
        self, messages: list[dict[str, Any]]
    ) -> list[set[str]]:
        """Return groups of email addresses that co-occur on the same threads.

        Each element is a ``set`` of addresses that participated together
        in at least one thread.  Self-sent messages are excluded, and
        the authenticated user's own address is removed from every group.

        Returns
        -------
        list[set[str]]
            One set per thread (threads with fewer than two external
            participants are omitted).
        """
        user_email = self._get_user_email()

        thread_participants: dict[str, set[str]] = defaultdict(set)
        for msg in messages:
            if self._is_self_sent(msg):
                continue
            thread_participants[msg["thread_id"]].update(
                self._get_participants(msg)
            )

        groups: list[set[str]] = []
        for participants in thread_participants.values():
            participants.discard(user_email)
            participants.discard("")
            if len(participants) >= 2:
                groups.append(participants)
        return groups

    # -- date-based inbox query ----------------------------------------------

    def get_inbox_by_date(
        self,
        *,
        after: date | str | None = None,
        before: date | str | None = None,
        query: str = "",
        max_results: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch parsed inbox messages filtered by date range.

        Parameters
        ----------
        after:
            Only messages after this date (inclusive).  Accepts a
            :class:`~datetime.date`, :class:`~datetime.datetime`, or an
            ISO-format string (``"YYYY-MM-DD"``).
        before:
            Only messages before this date (exclusive).  Same types as
            *after*.
        query:
            Additional Gmail search query appended to the date filters.
        max_results:
            Maximum number of messages to fetch.

        Notes
        -----
        Uses Gmail's ``after:`` / ``before:`` search operators which work
        on epoch seconds and use **midnight UTC** as the boundary.
        """
        parts: list[str] = []

        for label, value in (("after", after), ("before", before)):
            if value is None:
                continue
            if isinstance(value, str):
                value = date.fromisoformat(value)
            if isinstance(value, datetime):
                epoch = int(value.timestamp())
            else:
                epoch = int(datetime(value.year, value.month, value.day).timestamp())
            parts.append(f"{label}:{epoch}")

        if query:
            parts.append(query)

        combined = " ".join(parts)
        return self.get_inbox(query=combined, max_results=max_results)
