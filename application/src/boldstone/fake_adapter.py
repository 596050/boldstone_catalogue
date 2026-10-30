"""In-memory read-only test adapter. This module never opens a network connection."""

from __future__ import annotations

from copy import deepcopy

from .dropbox_adapter import Page
from .errors import RemoteError
from .util import native_reference, within_path


class FakeDropbox:
    def __init__(
        self,
        metadata=(),
        contents=None,
        *,
        account_id="test-account",
        namespace="111",
        page_size=2,
        backend=None,
    ):
        self.account_id, self.namespace, self.page_size = account_id, namespace, page_size
        self.backend = (
            backend
            if backend is not None
            else {
                "metadata": {m["id"]: deepcopy(m) for m in metadata},
                "contents": contents or {},
                "calls": [],
                "failures": {},
                "pages": {},
                "changes": [],
                "downloads": {},
                "writes": [],
            }
        )

    def account(self):
        self.backend["calls"].append(("account",))
        return {
            "account_id": self.account_id,
            "name": {
                "given_name": "Test",
                "surname": "Account",
                "familiar_name": "Test",
                "display_name": "Test Account",
                "abbreviated_name": "TA",
            },
            "root_info": {
                ".tag": "user",
                "root_namespace_id": self.namespace,
                "home_namespace_id": self.namespace,
            },
        }

    def with_namespace(self, namespace_id):
        if namespace_id != self.namespace:
            raise RemoteError("namespace_changed")
        return FakeDropbox(
            account_id=self.account_id,
            namespace=self.namespace,
            page_size=self.page_size,
            backend=self.backend,
        )

    def _fail(self, key):
        failure = self.backend["failures"].get(key)
        if failure:
            if isinstance(failure, list):
                error = failure.pop(0) if failure else None
            else:
                error = failure
            if error:
                raise error

    def metadata(self, reference):
        native_reference(reference)
        self.backend["calls"].append(("metadata", reference))
        self._fail(reference)
        values = self.backend["metadata"]
        metadata = values.get(reference) or next(
            (m for m in values.values() if m.get("path_lower") == reference.lower()), None
        )
        if not metadata:
            raise RemoteError("not_found_or_inaccessible")
        return deepcopy(metadata)

    def list_folder(self, reference, *, recursive=True, cursor=None):
        self.backend["calls"].append(("list_folder", reference, recursive, cursor))
        self._fail(cursor or "listing")
        if cursor:
            if cursor not in self.backend["pages"]:
                # A terminal census cursor is also the starting incremental cursor.
                pending = self.backend["changes"]
                self.backend["changes"] = []
                return self._page(pending, "change-" + str(len(self.backend["calls"])))
            return deepcopy(self.backend["pages"][cursor])
        folder = self.metadata(reference)
        entries = [
            deepcopy(m)
            for m in self.backend["metadata"].values()
            if m["id"] != folder["id"] and within_path(m.get("path_lower"), folder["path_lower"])
        ]
        if not recursive:
            entries = [
                m for m in entries if m["path_lower"].rsplit("/", 1)[0] == folder["path_lower"]
            ]
        return self._page(entries, "listing-" + str(len(self.backend["calls"])))

    def _page(self, entries, prefix):
        chunks = [
            entries[n : n + self.page_size] for n in range(0, len(entries), self.page_size)
        ] or [[]]
        pages = [
            Page(
                chunk,
                f"{prefix}:{n}",
                n + 1 < len(chunks),
                {"entries": chunk, "cursor": f"{prefix}:{n}", "has_more": n + 1 < len(chunks)},
            )
            for n, chunk in enumerate(chunks)
        ]
        for n in range(len(pages) - 1):
            self.backend["pages"][pages[n].cursor] = pages[n + 1]
        return pages[0]

    def download(self, asset_id, revision, destination, *, max_bytes):
        self.backend["calls"].append(("download", asset_id, revision))
        self._fail("download:" + asset_id)
        current = self.metadata(asset_id)
        if current.get("rev") != revision:
            raise RemoteError("revision_unavailable")
        data = self.backend["contents"].get((asset_id, revision))
        if data is None:
            raise RemoteError("content_unavailable")
        if len(data) > max_bytes:
            raise RemoteError("download_limit")
        destination.write_bytes(data)
        return deepcopy(self.backend["downloads"].get(asset_id, current))

    def links(self, asset_id):
        self._fail("links:" + asset_id)
        return {
            "owned_direct_link_count": 0,
            "pages": [{"links": [], "has_more": False}],
            "visibility": "authorized_user_direct_links_only",
            "universal_no_sharing_proof": False,
        }

    def revisions(self, asset_id):
        self._fail("revisions:" + asset_id)
        return {
            "response": {"entries": [self.metadata(asset_id)]},
            "mode": "id",
            "available_history_complete": False,
        }
