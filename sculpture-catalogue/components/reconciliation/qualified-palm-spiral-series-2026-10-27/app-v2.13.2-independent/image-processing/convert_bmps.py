"""Convert eligible, fully migrated BMP files with the separately authorized app.

Creates verified JPEG siblings and retains every original. No deletion, move,
overwrite, sharing change, plaintext credential storage, or upload retry.
"""
from __future__ import annotations

import argparse
import collections
import fcntl
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

import dropbox
from authorize import (
    APP_KEY,
    CREDENTIAL_ACCOUNT,
    NAMESPACE_ID,
    ROOT_ID,
    ROOT_PATH,
    RUNTIME,
    SERVICE,
    SetupError,
    keychain_backend,
    private_json,
    verify_grant,
)
from dropbox.common import PathRoot
from dropbox.exceptions import ApiError, RateLimitError
from dropbox.files import FileMetadata, FolderMetadata, WriteMode
from PIL import Image
from prepare_conversion import HANDOVER_PATH, PLAN_PATH, SHARED, read_csv
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout

RUN_PATH = RUNTIME / "conversion"
STATE_LOCK = threading.RLock()
PRINT_LOCK = threading.Lock()
STOP = threading.Event()
BLOCK_SIZE = 4 * 1024 * 1024


class Hold(RuntimeError):
    """A fixed, non-secret reason for retaining an individual file."""


def now():
    return datetime.now(UTC).isoformat()


def fingerprint(path):
    sha = hashlib.sha256()
    blocks = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        while data := stream.read(BLOCK_SIZE):
            size += len(data)
            sha.update(data)
            blocks.update(hashlib.sha256(data).digest())
    return {"sha256": sha.hexdigest(), "content_hash": blocks.hexdigest(), "size": size}


def path_equal(first, second):
    return first.casefold() == second.casefold()


def timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def head(metadata):
    if not isinstance(metadata, FileMetadata):
        raise Hold("SOURCE_OR_OUTPUT_IS_NOT_A_FILE")
    return {"id": metadata.id, "path": metadata.path_display, "rev": metadata.rev,
            "size": metadata.size, "content_hash": metadata.content_hash,
            "client_modified": metadata.client_modified.isoformat(),
            "server_modified": metadata.server_modified.isoformat()}


def check_source(row, metadata, expected=None):
    current = head(metadata)
    if current["id"] != row["source_id"] or not path_equal(current["path"], row["source_path"]):
        raise Hold("SOURCE_ID_OR_LOCATION_CHANGED")
    if current["size"] != row["size"]:
        raise Hold("SOURCE_SIZE_CHANGED_AFTER_MIGRATION")
    for field in ("client_modified", "server_modified"):
        if timestamp(current[field]) != timestamp(row[field]):
            raise Hold("SOURCE_TIMESTAMP_CHANGED_AFTER_MIGRATION")
    if not current["content_hash"] or not current["rev"]:
        raise Hold("SOURCE_HASH_OR_REVISION_UNAVAILABLE")
    if expected and any(current[k] != expected[k] for k in ("id", "rev", "content_hash", "size")):
        raise Hold("SOURCE_CHANGED_DURING_CONVERSION")
    return current


def decode_jpeg(path, dimensions):
    with Image.open(path) as image:
        if image.format != "JPEG" or image.size != tuple(dimensions):
            raise Hold("OUTPUT_FORMAT_OR_DIMENSIONS_FAILED")
        image.verify()
    with Image.open(path) as image:
        image.load()
        if image.size != tuple(dimensions):
            raise Hold("OUTPUT_DECODE_FAILED")


def encode_jpeg(source, output):
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    with Image.open(source) as image:
        detected = image.format
        dimensions = list(image.size)
        if detected not in ("BMP", "JPEG"):
            raise Hold("BMP_EXTENSION_CONTAINS_UNEXPECTED_FORMAT")
        image.verify()
    with Image.open(source) as image:
        image.load()
        if getattr(image, "n_frames", 1) != 1:
            raise Hold("MULTIFRAME_SOURCE")
        if detected == "JPEG":
            shutil.copyfile(source, output)
            method = "EXISTING_JPEG_BYTES_COPIED_WITHOUT_RECOMPRESSION"
            optimized = None
        else:
            if "A" in image.getbands() or "transparency" in image.info:
                raise Hold("TRANSPARENCY_REQUIRES_REVIEW")
            if image.mode not in ("1", "L", "P", "RGB"):
                raise Hold("UNSUPPORTED_COLOUR_MODE")
            options = {"quality": 100, "subsampling": 0, "optimize": True}
            for key in ("icc_profile", "exif"):
                if image.info.get(key):
                    options[key] = image.info[key]
            dpi = image.info.get("dpi")
            if dpi and len(dpi) == 2 and all(0 < d <= 65535 for d in dpi):
                options["dpi"] = tuple(round(d) for d in dpi)
            converted = image if image.mode in ("RGB", "L") else image.convert("RGB")
            optimized = True
            try:
                try:
                    converted.save(output, "JPEG", **options)
                except OSError:
                    # Some high-entropy images exceed libjpeg's optimization
                    # buffer. Huffman optimization changes size, not quality.
                    # Keep quality 100 and 4:4:4 for the fallback as well.
                    options["optimize"] = False
                    optimized = False
                    converted.save(output, "JPEG", **options)
            finally:
                if converted is not image:
                    converted.close()
            method = "BMP_TO_JPEG_QUALITY_100_SUBSAMPLING_0"
    os.chmod(output, 0o600)
    with open(output, "rb") as stream:
        os.fsync(stream.fileno())
    decode_jpeg(output, dimensions)
    return {"method": method, "source_format": detected, "dimensions": dimensions,
            "jpeg_huffman_optimized": optimized, **fingerprint(output)}


class Budget:
    def __init__(self):
        self.lock = threading.Lock()
        self.next_call = 0.0

    def wait(self):
        with self.lock:
            wait = max(0.0, self.next_call - time.monotonic())
            self.next_call = max(self.next_call, time.monotonic()) + 0.5
        if STOP.wait(wait):
            raise Hold("RUN_STOPPED")

    def backoff(self, seconds):
        with self.lock:
            self.next_call = max(self.next_call, time.monotonic() + max(60, seconds))


BUDGET = Budget()


class API:
    def __init__(self, grant):
        self.client = dropbox.Dropbox(app_key=APP_KEY, oauth2_refresh_token=grant["refresh_token"],
                                      timeout=90, max_retries_on_error=0, max_retries_on_rate_limit=0
                                      ).with_path_root(PathRoot.namespace_id(NAMESPACE_ID))

    def close(self):
        self.client.close()

    def read(self, method, *args, **kwargs):
        for attempt in range(3):
            BUDGET.wait()
            try:
                return getattr(self.client, method)(*args, **kwargs)
            except RateLimitError as error:
                BUDGET.backoff(getattr(error, "backoff", None) or 60)
                if attempt == 2:
                    raise Hold("RATE_LIMITED_READ") from None
            except (RequestsConnectionError, Timeout):
                if attempt == 2:
                    raise
                if STOP.wait(5 * (attempt + 1)):
                    raise Hold("RUN_STOPPED") from None

    def metadata(self, path):
        try:
            return self.read("files_get_metadata", path)
        except ApiError as error:
            if error.error.is_path() and error.error.get_path().is_not_found():
                return None
            raise

    def download(self, destination, file_id, revision):
        # Dropbox now rejects the separate rev parameter. Pin the download to
        # the revision address, then check the returned file identity as well.
        metadata = self.read("files_download_to_file", str(destination), "rev:" + revision)
        if metadata.id != file_id or metadata.rev != revision:
            raise Hold("DOWNLOAD_FILE_ID_OR_REVISION_MISMATCH")
        return metadata

    def upload(self, output, destination, modified):
        BUDGET.wait()
        try:
            return self.client.files_upload(output.read_bytes(), destination, mode=WriteMode.add,
                                            autorename=False, strict_conflict=True, mute=True,
                                            content_hash=fingerprint(output)["content_hash"],
                                            client_modified=datetime.fromisoformat(modified).replace(tzinfo=None))
        except RateLimitError as error:
            BUDGET.backoff(getattr(error, "backoff", None) or 60)
            raise


def state_path(row):
    name = hashlib.sha256(row["source_id"].encode()).hexdigest()
    return RUN_PATH / "states" / (name + ".json")


def saved_state(row):
    path = state_path(row)
    return json.loads(path.read_text()) if path.exists() else {}


def record(row, state, **details):
    with STATE_LOCK:
        previous = saved_state(row)
        payload = {**previous, "state": state, "updated_utc": now(), "source_id": row["source_id"],
                   "source_path": row["source_path"], "destination_path": row["destination_path"],
                   "family_id": row["family_id"], "source_retained": True,
                   "execution_transport": "NATIVE_AUTHORIZED_APP", "configured_native_app_not_used": False,
                   **details}
        private_json(state_path(row), payload)
        SHARED.mkdir(mode=0o700, parents=True, exist_ok=True)
        event = {"schema": "boldstone-bmp-jpeg-operation-v1", **payload}
        fd = os.open(SHARED / "operations.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return payload


def validate_folders(api, row):
    for identifier, expected in ((row["family_id"], row["family_path"]), (row["parent_id"], row["parent_path"])):
        folder = api.metadata(identifier)
        if not isinstance(folder, FolderMetadata) or folder.id != identifier or not path_equal(folder.path_display, expected):
            raise Hold("COMPLETED_FAMILY_OR_PARENT_MOVED")


def verify_uploaded(api, row, local, metadata, work):
    output_head = head(api.metadata(metadata.id))
    if not path_equal(output_head["path"], row["destination_path"]):
        raise Hold("UPLOADED_PATH_MISMATCH")
    if output_head["size"] != local["size"] or output_head["content_hash"] != local["content_hash"]:
        raise Hold("UPLOADED_HASH_OR_SIZE_MISMATCH")
    returned = work / "downloaded-output.jpg"
    downloaded = head(api.download(returned, output_head["id"], output_head["rev"]))
    if any(downloaded[k] != output_head[k] for k in ("id", "rev", "content_hash", "size")):
        raise Hold("OUTPUT_CHANGED_DURING_READBACK")
    if fingerprint(returned) != {k: local[k] for k in ("sha256", "content_hash", "size")}:
        raise Hold("UPLOADED_BYTES_FAILED_INDEPENDENT_DOWNLOAD")
    decode_jpeg(returned, local["dimensions"])
    final_head = head(api.metadata(output_head["id"]))
    if any(final_head[k] != output_head[k] for k in ("id", "path", "rev", "content_hash", "size")):
        raise Hold("OUTPUT_CHANGED_DURING_READBACK")
    return output_head


def process(api, row):
    prior = saved_state(row)
    if prior.get("state") in ("VERIFIED", "RECONCILED_JPEG_VERIFIED"):
        return prior["state"]
    if prior.get("state") == "HELD":
        return "HELD"
    if STOP.is_set():
        return "NOT_STARTED"
    work = RUN_PATH / "files" / hashlib.sha256(row["source_id"].encode()).hexdigest()
    work.mkdir(parents=True, mode=0o700, exist_ok=True)
    source = work / "original.bmp"
    output = work / "converted.jpg"
    uncertain_prior = prior.get("upload_intent")
    try:
        validate_folders(api, row)
        current = check_source(row, api.metadata(row["source_id"]))
        jpeg = api.metadata(row["destination_path"])
        other_jpeg = api.metadata(str(PurePosixPath(row["source_path"]).with_suffix(".jpeg")))
        if other_jpeg is not None or (jpeg is not None and not uncertain_prior):
            raise Hold("JPEG_DESTINATION_ALREADY_EXISTS")
        if uncertain_prior:
            if jpeg is None:
                raise Hold("UNRESOLVED_UPLOAD_INTENT_NO_AUTOMATIC_RESUBMISSION")
            if not output.exists() or "local_jpeg" not in prior or "source_head" not in prior:
                raise Hold("UNRESOLVED_UPLOAD_INTENT_MISSING_LOCAL_PROOF")
            check_source(row, api.metadata(row["source_id"]), prior["source_head"])
            local = prior["local_jpeg"]
            if fingerprint(output) != {k: local[k] for k in ("sha256", "content_hash", "size")}:
                raise Hold("LOCAL_OUTPUT_CHANGED_BEFORE_RECONCILIATION")
            if prior.get("output_head") and jpeg.id != prior["output_head"]["id"]:
                raise Hold("OUTPUT_ID_CHANGED_BEFORE_RECONCILIATION")
            verified = verify_uploaded(api, row, local, jpeg, work)
            check_source(row, api.metadata(row["source_id"]), prior["source_head"])
            record(row, "RECONCILED_JPEG_VERIFIED", output_head=verified,
                   attribution="Previous intent reconciled by exact bytes; source kept.")
            return "RECONCILED_JPEG_VERIFIED"
        record(row, "DOWNLOADING", source_head=current, work_directory=str(work))
        downloaded = head(api.download(source, current["id"], current["rev"]))
        if any(downloaded[k] != current[k] for k in ("id", "rev", "content_hash", "size")):
            raise Hold("SOURCE_DOWNLOAD_METADATA_MISMATCH")
        backup = fingerprint(source)
        if backup["size"] != current["size"] or backup["content_hash"] != current["content_hash"]:
            raise Hold("SOURCE_DOWNLOAD_HASH_MISMATCH")
        with source.open("rb") as stream:
            os.fsync(stream.fileno())
        local = encode_jpeg(source, output)
        if local["size"] > 140 * 1024 * 1024:
            raise Hold("OUTPUT_EXCEEDS_SINGLE_UPLOAD_LIMIT")
        record(row, "LOCAL_JPEG_READY", backup=backup, local_jpeg=local)
        validate_folders(api, row)
        check_source(row, api.metadata(row["source_id"]), current)
        if api.metadata(row["destination_path"]) is not None or api.metadata(str(PurePosixPath(row["source_path"]).with_suffix(".jpeg"))) is not None:
            raise Hold("JPEG_DESTINATION_APPEARED_DURING_CONVERSION")
        record(row, "UPLOAD_INTENT", upload_intent=True)
        try:
            uploaded = api.upload(output, row["destination_path"], current["client_modified"])
        except Exception as error:  # noqa: BLE001 -- Every unknown upload outcome must stop writes.
            record(row, "UPLOAD_OUTCOME_UNKNOWN", error_type=type(error).__name__)
            STOP.set()
            return "UPLOAD_OUTCOME_UNKNOWN"
        record(row, "UPLOADED", output_head=head(uploaded))
        verified = verify_uploaded(api, row, local, uploaded, work)
        check_source(row, api.metadata(row["source_id"]), current)
        record(row, "VERIFIED", output_head=verified)
        return "VERIFIED"
    except Hold as error:
        if str(error) == "RUN_STOPPED":
            record(row, "PAUSED", reason="RUN_STOPPED")
            return "PAUSED"
        record(row, "HELD", reason=str(error))
        return "HELD"
    except Exception as error:  # noqa: BLE001 -- Record only the type, never credential-bearing messages.
        # Do not log exception messages: transport errors may contain credentials.
        record(row, "ERROR", error_type=type(error).__name__)
        STOP.set()
        return "ERROR"


def validate_plan(plan):
    if (plan.get("namespace_id"), plan.get("root_id"), plan.get("root_path")) != (NAMESPACE_ID, ROOT_ID, ROOT_PATH):
        raise SetupError("Conversion plan root binding does not match this app.")
    handover = json.loads(HANDOVER_PATH.read_text())
    if hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest() != handover["plan"]["sha256"]:
        raise SetupError("Conversion plan differs from the shared handover.")
    for evidence in plan["evidence"].values():
        if hashlib.sha256(Path(evidence["path"]).read_bytes()).hexdigest() != evidence["sha256"]:
            raise SetupError("A frozen input changed; rebuild the conversion handover after review.")
    if plan["policy"]["source_retirement_enabled"] or plan["policy"]["overwrite_enabled"]:
        raise SetupError("This worker supports additive conversion only.")
    if plan["policy"]["jpeg_quality"] != 100 or plan["policy"]["jpeg_subsampling"] != 0:
        raise SetupError("The current instruction requires maximum JPEG quality and no chroma subsampling.")
    protected = {r["Dropbox ID"] for r in read_csv(Path(plan["evidence"]["protected"]["path"]))}
    held = {r[k] for r in read_csv(Path(plan["evidence"]["holds"]["path"])) for k in ("Target file ID", "Designated keeper ID")}
    ids, destinations = set(), set()
    for row in plan["rows"]:
        source = PurePosixPath(row["source_path"])
        try:
            relative = source.relative_to(ROOT_PATH)
        except ValueError:
            raise SetupError("Conversion source is outside the allowed root.") from None
        if len(relative.parts) != 3 or ".." in relative.parts or source.suffix.casefold() != ".bmp":
            raise SetupError("Conversion source depth or extension is invalid.")
        if str(source.with_suffix(".jpg")) != row["destination_path"]:
            raise SetupError("JPEG target must be the exact sibling of its BMP.")
        if row["source_id"] in ids:
            raise SetupError("Duplicate source ID in conversion plan.")
        ids.add(row["source_id"])
        if row["status"] == "ELIGIBLE":
            if row["source_id"] in protected | held or row["hold_reasons"]:
                raise SetupError("Protected or held source was marked eligible.")
            if row["destination_path"].casefold() in destinations:
                raise SetupError("Duplicate JPEG destinations in conversion plan.")
            destinations.add(row["destination_path"].casefold())


def update_status(plan, state):
    with STATE_LOCK:
        counts = collections.Counter(saved_state(r).get("state", "NOT_STARTED") for r in plan["rows"] if r["status"] == "ELIGIBLE")
        status = {"state": state, "updated_utc": now(), "plan_counts": plan["counts"],
                  "execution_counts": dict(counts), "source_files_deleted": 0,
                  "source_retirement_enabled": False, "app_key": APP_KEY,
                  "execution_transport": "NATIVE_AUTHORIZED_APP", "jpeg_quality": 100, "jpeg_subsampling": 0,
                  "shared_ledger": str(SHARED / "operations.jsonl")}
        private_json(RUNTIME / "conversion-status.json", status)
        return status


def run_family(grant, rows, plan):
    api = API(grant)
    try:
        for row in rows:
            if STOP.is_set():
                break
            state = process(api, row)
            with PRINT_LOCK:
                print(f"{state}: {row['family']} / {PurePosixPath(row['source_path']).name}", flush=True)
            update_status(plan, "RUNNING")
    finally:
        api.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Create and independently verify JPEG files in Dropbox.")
    parser.add_argument("--limit", type=int, help="Process at most this many eligible files.")
    args = parser.parse_args()
    os.umask(0o077)
    plan = json.loads(PLAN_PATH.read_text())
    validate_plan(plan)
    if not args.run:
        print(json.dumps(plan["counts"], indent=2))
        print("Prepared only. Use --run from your Mac Terminal to start; originals are retained.")
        return 0
    if args.limit is not None and args.limit < 1:
        raise SetupError("--limit must be positive.")
    RUN_PATH.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_fd = os.open(RUN_PATH / "worker.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise SetupError("A conversion worker already holds the run lock.") from None
    active = False
    try:
        update_status(plan, "CHECKING_KEYCHAIN")
        try:
            saved = keychain_backend().get_password(SERVICE, CREDENTIAL_ACCOUNT)
        except Exception:  # noqa: BLE001 -- Keychain errors must never expose credential payloads.
            update_status(plan, "NEEDS_MAC_TERMINAL_KEYCHAIN_ACCESS")
            raise SetupError("macOS denied Keychain access in this process. Run this same command in your Mac Terminal.") from None
        if not saved:
            raise SetupError("The app authorization is missing from macOS Keychain.")
        grant = json.loads(saved)
        verify_grant(grant)
        if shutil.disk_usage(RUNTIME).free < max(6 * 1024**3, 3 * plan["counts"]["eligible_bytes"]):
            raise SetupError("Insufficient free disk space for originals, JPEGs and verification downloads.")
        private_json(SHARED / "ACTIVE-WORKER.json", {"state": "STARTED", "pid": os.getpid(), "started_utc": now(),
                     "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(), "workers": 2,
                     "original_retirements_enabled": False})
        active = True
        rows = [r for r in plan["rows"] if r["status"] == "ELIGIBLE"
                and saved_state(r).get("state") not in ("VERIFIED", "RECONCILED_JPEG_VERIFIED", "HELD")]
        if args.limit:
            rows = rows[:args.limit]
        print(f"Starting {len(rows)} eligible files with two family workers. Originals stay in place.", flush=True)
        # The first file exercises all live gates before the larger queue starts.
        while rows and not STOP.is_set():
            run_family(grant, rows[:1], plan)
            pilot_verified = saved_state(rows[0]).get("state") in ("VERIFIED", "RECONCILED_JPEG_VERIFIED")
            rows = rows[1:]
            if pilot_verified:
                break
        families = collections.defaultdict(list)
        for row in rows:
            families[row["family_id"]].append(row)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_family, grant, family, plan) for family in families.values()]
            try:
                for future in as_completed(futures):
                    future.result()
            except KeyboardInterrupt:
                STOP.set()
                for future in futures:
                    future.cancel()
                raise
        result = update_status(plan, "STOPPED_FOR_REVIEW" if STOP.is_set() else "BATCH_FINISHED")
        print(json.dumps(result, indent=2), flush=True)
        return 1 if STOP.is_set() else 0
    finally:
        if active:
            active_path = SHARED / "ACTIVE-WORKER.json"
            active_record = json.loads(active_path.read_text())
            active_record.update(state="EXITED", exited_utc=now(),
                                 last_worker_state=json.loads((RUNTIME / "conversion-status.json").read_text())["state"])
            private_json(active_path, active_record)
        os.close(lock_fd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SetupError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except KeyboardInterrupt:
        STOP.set()
        print("Interrupted. Keep the files and rerun the same command to reconcile recorded work.", file=sys.stderr)
        raise SystemExit(130) from None
    except Exception as error:  # noqa: BLE001 -- Last-resort sanitized failure report.
        print("Worker stopped safely; error type: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
