from __future__ import annotations

import json
import random
import socket
import time
from dataclasses import dataclass
from typing import Protocol

from .errors import RemoteError
from .util import native_reference, redact


@dataclass(frozen=True)
class Page:
    entries: list[dict]
    cursor: str
    has_more: bool
    raw: dict


class ReadOnlyDropbox(Protocol):
    def account(self) -> dict: ...
    def with_namespace(self, namespace_id: str) -> ReadOnlyDropbox: ...
    def metadata(self, reference: str) -> dict: ...
    def list_folder(self, reference: str, *, recursive=True, cursor=None) -> Page: ...
    def download(self, asset_id: str, revision: str, destination, *, max_bytes: int) -> dict: ...
    def links(self, asset_id: str) -> dict: ...
    def revisions(self, asset_id: str) -> dict: ...


def sdk_json(value):
    import importlib

    from dropbox.files import DeletedMetadata, FileMetadata, FolderMetadata
    from dropbox.stone_serializers import json_encode

    validator = getattr(
        importlib.import_module(type(value).__module__), type(value).__name__ + "_validator"
    )
    result = json.loads(json_encode(validator, value))
    for kind, cls in (
        ("file", FileMetadata),
        ("folder", FolderMetadata),
        ("deleted", DeletedMetadata),
    ):
        if isinstance(value, cls):
            result[".tag"] = kind
    return redact(result)


def _union_tag(value):
    return getattr(value, "_tag", None)


def translate_exception(exc):
    import dropbox.exceptions as dbx_errors
    import requests

    request_id = getattr(exc, "request_id", None)
    if isinstance(exc, dbx_errors.RateLimitError):
        return RemoteError("rate_limit", request_id=request_id, retry_after=exc.backoff or 1)
    if isinstance(exc, dbx_errors.AuthError):
        tag = _union_tag(exc.error)
        details = {}
        if tag == "missing_scope":
            details["required_scope"] = exc.error.get_missing_scope().required_scope
        return RemoteError(
            "missing_scope" if tag == "missing_scope" else "authentication",
            request_id=request_id,
            details=details,
        )
    if isinstance(exc, dbx_errors.PathRootError):
        return RemoteError("namespace_changed", request_id=request_id)
    if isinstance(exc, dbx_errors.ApiError):
        error = exc.error
        tag = _union_tag(error)
        if tag == "reset":
            return RemoteError("cursor_reset", request_id=request_id)
        if tag in ("path", "path_lookup"):
            error = getattr(error, "get_" + tag)()
            tag = _union_tag(error)
        kind = {
            "not_found": "not_found_or_inaccessible",
            "restricted_content": "permission",
            "no_permission": "permission",
            "not_file": "wrong_kind",
            "not_folder": "wrong_kind",
        }.get(tag, "api_error")
        return RemoteError(kind, request_id=request_id, details={"error_tag": tag})
    if isinstance(exc, requests.exceptions.SSLError):
        return RemoteError("tls")
    if isinstance(exc, (requests.exceptions.Timeout, TimeoutError)):
        return RemoteError("timeout")
    if isinstance(exc, (requests.exceptions.ConnectionError, socket.gaierror)):
        return RemoteError("network_or_dns")
    if isinstance(exc, dbx_errors.HttpError):
        return RemoteError(
            "http_error", request_id=request_id, details={"status_code": exc.status_code}
        )
    # Do not serialize arbitrary exception strings: they can contain bearer headers or URLs.
    return RemoteError("unexpected_read_error", details={"exception_type": type(exc).__name__})


class NativeDropbox:
    """A deliberately small SDK facade exposing no content mutation methods."""

    def __init__(self, client, *, policy=None, sleep=time.sleep):
        self._client = client
        self.policy = policy or {"max_attempts": 4, "max_retry_wait_seconds": 30}
        self.sleep = sleep

    def close(self):
        self._client.close()

    def with_namespace(self, namespace_id):
        from dropbox.common import PathRoot

        if not isinstance(namespace_id, str) or not namespace_id.isdecimal():
            raise RemoteError("invalid_namespace", "Namespace IDs must be native decimal IDs")
        return NativeDropbox(
            self._client.with_path_root(PathRoot.namespace_id(namespace_id)),
            policy=self.policy,
            sleep=self.sleep,
        )

    def _read(self, call):
        attempts = self.policy.get("max_attempts", 4)
        for attempt in range(attempts):
            try:
                return call()
            except Exception as exc:
                error = translate_exception(exc)
                if (
                    error.kind not in ("rate_limit", "timeout", "network_or_dns")
                    or attempt + 1 == attempts
                ):
                    raise error from None
                delay = (
                    error.retry_after
                    if error.retry_after is not None
                    else min(2**attempt + random.random(), 15)
                )
                if delay > self.policy.get("max_retry_wait_seconds", 30):
                    raise error from None
                self.sleep(delay)
        raise AssertionError("Unreachable retry state")

    def account(self):
        return sdk_json(self._read(self._client.users_get_current_account))

    def metadata(self, reference):
        native_reference(reference)
        return sdk_json(
            self._read(
                lambda: self._client.files_get_metadata(
                    reference, include_deleted=False, include_has_explicit_shared_members=True
                )
            )
        )

    def list_folder(self, reference, *, recursive=True, cursor=None):
        native_reference(reference)
        if cursor:
            result = self._read(lambda: self._client.files_list_folder_continue(cursor))
        else:
            result = self._read(
                lambda: self._client.files_list_folder(
                    reference,
                    recursive=recursive,
                    include_deleted=True,
                    include_has_explicit_shared_members=True,
                    include_mounted_folders=True,
                    limit=1000,
                )
            )
        raw = sdk_json(result)
        return Page(raw["entries"], raw["cursor"], raw["has_more"], raw)

    def download(self, asset_id, revision, destination, *, max_bytes):
        native_reference(asset_id)
        if not asset_id.startswith("id:") or not revision:
            raise RemoteError(
                "invalid_download", "Downloads require a stable ID and exact revision"
            )
        metadata, response = self._read(lambda: self._client.files_download(asset_id, rev=revision))
        transferred = 0
        try:
            with destination.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    transferred += len(chunk)
                    if transferred > max_bytes:
                        raise RemoteError(
                            "download_limit", "Download exceeded the configured byte limit"
                        )
                    output.write(chunk)
                output.flush()
                import os

                os.fsync(output.fileno())
            raw = sdk_json(metadata)
            raw["request_id"] = response.headers.get("X-Dropbox-Request-Id")
            return raw
        except RemoteError:
            raise
        except OSError:
            raise
        except Exception as exc:
            raise translate_exception(exc) from None
        finally:
            response.close()

    def links(self, asset_id):
        native_reference(asset_id)
        result = self._read(
            lambda: self._client.sharing_list_shared_links(path=asset_id, direct_only=True)
        )
        pages = [sdk_json(result)]
        seen = set()
        while pages[-1].get("has_more"):
            cursor = pages[-1].get("cursor")
            if not cursor or cursor in seen:
                raise RemoteError("pagination_invalid")
            seen.add(cursor)
            result = self._read(lambda: self._client.sharing_list_shared_links(cursor=cursor))
            pages.append(sdk_json(result))
        return {
            "pages": pages,
            "owned_direct_link_count": sum(len(p.get("links", [])) for p in pages),
            "visibility": "authorized_user_direct_links_only",
            "universal_no_sharing_proof": False,
        }

    def revisions(self, asset_id):
        from dropbox.files import ListRevisionsMode

        result = self._read(
            lambda: self._client.files_list_revisions(
                asset_id, mode=ListRevisionsMode.id, limit=100
            )
        )
        return {
            "response": sdk_json(result),
            "mode": "id",
            "available_history_complete": False,
            "limit": "ID-oriented query is bounded; retention and continuation limits remain",
        }
