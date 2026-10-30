"""Use the authorized Dropbox connector through a local, bounded tool dispatcher.

No credentials are exported. Requests contain only the already-approved file
identities and local JPEG paths. The dispatcher performs the connected tools;
the existing conversion engine verifies all source and output bytes.
"""
from __future__ import annotations

import argparse
import collections
import fcntl
import json
import os
import secrets
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import convert_bmps as w
from authorize import (
    EXPECTED_EMAIL,
    NAMESPACE_ID,
    ROOT_ID,
    ROOT_PATH,
    RUNTIME,
    private_json,
)
from dropbox.files import FileMetadata, FolderMetadata

RPC = RUNTIME / "connector-rpc"
TRANSPORT = "AUTHORIZED_DROPBOX_CONNECTOR"


class ConnectorError(RuntimeError):
    pass


def request(method, args):
    identifier = secrets.token_hex(16)
    response_path = RPC / "responses" / (identifier + ".json")
    private_json(RPC / "requests" / (identifier + ".json"), {
        "id": identifier, "method": method, "args": args, "created_utc": w.now(),
    })
    deadline = time.monotonic() + 600
    while not response_path.exists():
        if time.monotonic() > deadline:
            raise ConnectorError("DISPATCHER_RESPONSE_TIMEOUT")
        if w.STOP.wait(0.1):
            raise ConnectorError("RUN_STOPPED")
    response = json.loads(response_path.read_text())
    response_path.unlink()
    if response.get("error"):
        raise ConnectorError(response["error"])
    return response["result"]


class ConnectorAPI:
    def __init__(self, _grant=None):
        self.hashes = {}
        self.links = {}
        self.heads = {}

    def close(self):
        pass

    def new_link(self, metadata):
        link = request("download_link", {"entries": [metadata["id"]], "expiration_in_sec": 900})["entries"][0]
        if (link["id"] != metadata["id"] or link["size"] != metadata.get("size", 0)
                or not w.path_equal(link["path_display"], metadata["path_display"])):
            raise w.Hold("CONNECTOR_DOWNLOAD_LINK_IDENTITY_MISMATCH")
        if not link.get("content_hash") or not link.get("download_url", "").startswith("https://"):
            raise w.Hold("CONNECTOR_DOWNLOAD_LINK_INCOMPLETE")
        return {**link, "received_at": time.monotonic()}

    def metadata(self, path):
        result = request("metadata", {"path_or_file_id": path})
        if result is None:
            return None
        if result["metadata_type"] == "folder":
            item = result["folder"]
            return FolderMetadata(id=item["id"], name=item["name"], path_display=item["path_display"])
        item = result["file"]
        key = (item["id"], item["rev"])
        if key not in self.hashes:
            link = self.new_link(item)
            self.hashes[key] = link["content_hash"]
            self.links[key] = link
        metadata = FileMetadata(
            id=item["id"], name=item["name"], path_display=item["path_display"], rev=item["rev"],
            size=item.get("size", 0), content_hash=self.hashes[key],
            client_modified=datetime.fromisoformat(item["client_modified"]),
            server_modified=datetime.fromisoformat(item["server_modified"]),
        )
        self.heads[key] = metadata
        return metadata

    def download(self, destination, file_id, revision):
        key = (file_id, revision)
        metadata = self.heads[key]
        link = self.links.pop(key, None)
        if link is None or time.monotonic() - link["received_at"] > 850:
            link = self.new_link({"id": metadata.id, "path_display": metadata.path_display, "size": metadata.size})
        if link["content_hash"] != metadata.content_hash:
            raise w.Hold("CONTENT_CHANGED_BEFORE_CONNECTOR_DOWNLOAD")
        result = request("download", {"download_url": link["download_url"],
                         "file_id": file_id, "destination": str(destination)})
        if result.get("size") != metadata.size:
            raise w.Hold("CONNECTED_DOWNLOAD_SIZE_MISMATCH")
        # The engine compares downloaded bytes to this exact content hash and
        # subsequently rereads the live revision before upload / after readback.
        return metadata

    def upload(self, output, destination, _modified):
        result = request("upload", {"source_file": str(output), "destination_path": "ns:" + NAMESPACE_ID + "/" + destination})
        if result.get("status") != "completed" or not result.get("file", {}).get("file_id"):
            raise ConnectorError("UPLOAD_HAS_NO_TERMINAL_SUCCESS")
        return self.metadata(result["file"]["file_id"])


ORIGINAL_RECORD = w.record
ORIGINAL_STATUS = w.update_status


def record(row, state, **details):
    details["execution_transport"] = TRANSPORT
    details["configured_native_app_not_used"] = True
    return ORIGINAL_RECORD(row, state, **details)


def status(plan, state):
    with w.STATE_LOCK:
        result = ORIGINAL_STATUS(plan, state)
        result.pop("app_key", None)
        result.update(execution_transport=TRANSPORT, configured_native_app_not_used=True,
                      jpeg_quality=100, jpeg_subsampling=0)
        private_json(RUNTIME / "conversion-status.json", result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not args.run:
        parser.error("Use --run only with the connected dispatcher active.")
    os.umask(0o077)
    plan = json.loads(w.PLAN_PATH.read_text())
    w.validate_plan(plan)
    for directory in ("requests", "responses", "inflight", "receipts"):
        (RPC / directory).mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_fd = os.open(w.RUN_PATH / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    w.API, w.record, w.update_status = ConnectorAPI, record, status
    active_path = w.SHARED / "ACTIVE-WORKER.json"
    try:
        status(plan, "CONNECTOR_IDENTITY_CHECK")
        identity = request("who_am_i", {})
        if identity.get("email", "").casefold() != EXPECTED_EMAIL.casefold() or identity.get("root_namespace_id") != NAMESPACE_ID:
            raise ConnectorError("WRONG_CONNECTED_DROPBOX_ACCOUNT")
        root = ConnectorAPI().metadata(ROOT_ID)
        if not isinstance(root, FolderMetadata) or root.id != ROOT_ID or not w.path_equal(root.path_display, ROOT_PATH):
            raise ConnectorError("WRONG_CONNECTED_DROPBOX_ROOT")
        if shutil.disk_usage(RUNTIME).free < 6 * 1024**3:
            raise ConnectorError("INSUFFICIENT_DISK_SPACE")
        private_json(active_path, {"state": "RUNNING", "pid": os.getpid(), "started_utc": w.now(),
                     "execution_transport": TRANSPORT, "workers": 2, "jpeg_quality": 100,
                     "original_retirements_enabled": False})
        rows = [r for r in plan["rows"] if r["status"] == "ELIGIBLE"
                and w.saved_state(r).get("state") not in ("VERIFIED", "RECONCILED_JPEG_VERIFIED", "HELD")]
        if args.limit:
            rows = rows[:args.limit]
        families = collections.defaultdict(list)
        for row in rows:
            families[row["family_id"]].append(row)
        print(f"Connected conversion: {len(rows)} remaining files, two family workers, maximum JPEG quality.", flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(w.run_family, None, rows, plan) for rows in families.values()]
            try:
                for future in as_completed(futures):
                    future.result()
            except BaseException:
                w.STOP.set()
                for future in futures:
                    future.cancel()
                raise
        result = status(plan, "STOPPED_FOR_REVIEW" if w.STOP.is_set() else "BATCH_FINISHED")
        print(json.dumps(result), flush=True)
        return 1 if w.STOP.is_set() else 0
    except Exception:
        status(plan, "STOPPED_FOR_REVIEW")
        raise
    finally:
        private_json(active_path, {"state": "EXITED", "pid": os.getpid(), "exited_utc": w.now(),
                     "execution_transport": TRANSPORT, "original_retirements_enabled": False})
        os.close(lock_fd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001 -- Never expose token-bearing transport exceptions.
        print("Connected worker stopped; error type: " + type(error).__name__, flush=True)
        raise SystemExit(1) from None
