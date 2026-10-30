from __future__ import annotations

import hashlib
import io
import os
import tempfile
import warnings
from pathlib import Path

from .errors import Blocked, IntegrityError, RemoteError
from .hashing import hash_file
from .util import (
    canonical,
    check_no_symlinks,
    digest,
    file_sha256,
    new_id,
    private_directory,
    utc_now,
)


def decode_image(path, *, max_frames=250):
    from PIL import Image, ImageCms

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as probe:
            probe.verify()
        with Image.open(path) as image:
            result = {
                "actual_format": image.format,
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "frame_count": getattr(image, "n_frames", 1),
                "orientation": image.getexif().get(274),
                "dpi": image.info.get("dpi"),
                "transparency": "transparency" in image.info or "A" in image.getbands(),
                "icc_present": bool(image.info.get("icc_profile")),
                "icc_valid": None,
                "exif_present": bool(image.getexif()),
                "full_pixel_decode": False,
            }
            icc = image.info.get("icc_profile")
            if icc:
                result["icc_sha256"] = hashlib.sha256(icc).hexdigest()
                try:
                    ImageCms.getOpenProfile(io.BytesIO(icc))
                    result["icc_valid"] = True
                except Exception:
                    result["icc_valid"] = False
            if image.getexif():
                result["exif_sha256"] = hashlib.sha256(image.getexif().tobytes()).hexdigest()
            if result["frame_count"] > max_frames:
                raise IntegrityError("Image exceeds the bounded frame-decode policy")
            for frame in range(result["frame_count"]):
                image.seek(frame)
                image.load()
            result["full_pixel_decode"] = True
            return result


def check_binary(state, run, scope, asset_id, *, expected_format=None):
    """Always downloads fresh; neither an old cache nor metadata alone is a pass."""
    check_id = new_id("binary")
    checks = {
        name: "unknown"
        for name in (
            "metadata",
            "transfer",
            "revision",
            "size",
            "hash",
            "decode",
            "format",
            "post_read",
        )
    }
    evidence = {
        "checks": checks,
        "expected_format": expected_format,
        "ordinary_sha256_is_dropbox_hash": False,
        "fresh_download": True,
    }
    temporary = None
    metadata = {}
    sha = dbx_hash = cache_path = byte_size = None
    outcome, exit_code = "BLOCKED", 3
    try:
        metadata = scope.resolve(asset_id, expected_kind="file")
        checks["metadata"] = "pass"
        if (
            not metadata.get("rev")
            or not metadata.get("content_hash")
            or metadata.get("size") is None
        ):
            raise Blocked("Current ID, revision, size and content hash are required")
        limit = state.config.data["read_policy"]["max_download_bytes"]
        if metadata["size"] > limit:
            raise Blocked("File exceeds the configured per-file download limit")
        directory = private_directory(
            state.config.directory("cache")
            / digest({"binding": scope.binding, "id": asset_id, "revision": metadata["rev"]})
        )
        fd, path = tempfile.mkstemp(prefix=".download-", dir=directory)
        os.close(fd)
        temporary = Path(path)
        returned = scope.adapter.download(asset_id, metadata["rev"], temporary, max_bytes=limit)
        checks["transfer"] = "pass"
        evidence["returned_metadata"] = returned
        if returned.get("id") != asset_id or returned.get("rev") != metadata["rev"]:
            checks["revision"] = "fail"
            raise IntegrityError("Downloaded stream has a different ID or revision")
        checks["revision"] = "pass"
        byte_size = temporary.stat().st_size
        if byte_size != metadata["size"] or returned.get("size") != metadata["size"]:
            checks["size"] = "fail"
            raise IntegrityError("Downloaded byte size differs from current metadata")
        checks["size"] = "pass"
        sha, dbx_hash = file_sha256(temporary), hash_file(temporary)
        if dbx_hash != metadata["content_hash"] or returned.get("content_hash") != dbx_hash:
            checks["hash"] = "fail"
            raise IntegrityError("Downloaded content hash differs from server metadata")
        checks["hash"] = "pass"
        try:
            decoded = decode_image(
                temporary, max_frames=state.config.data["read_policy"]["max_frames"]
            )
        except Exception as exc:
            checks["decode"] = "fail"
            raise IntegrityError(
                "Image failed full structural/pixel decoding",
                details={"decoder_error_type": type(exc).__name__},
            ) from None
        checks["decode"] = "pass"
        evidence["image"] = decoded
        if expected_format and decoded["actual_format"] != expected_format:
            checks["format"] = "fail"
            raise IntegrityError("Decoded image format differs from the batch's required format")
        checks["format"] = "pass" if expected_format else "not_applicable"
        post_read = scope.resolve(asset_id, expected_kind="file")
        evidence["independent_post_read"] = post_read
        if any(
            post_read.get(key) != metadata.get(key) for key in ("id", "rev", "size", "content_hash")
        ):
            checks["post_read"] = "fail"
            raise IntegrityError(
                "Source changed during binary retrieval; review the new current revision"
            )
        checks["post_read"] = "pass"
        destination = check_no_symlinks(directory / (sha + ".verified-original"))
        if destination.exists():
            if file_sha256(destination) != sha or hash_file(destination) != dbx_hash:
                raise IntegrityError("Existing verified cache content changed")
        else:
            os.link(temporary, destination)
        cache_path = str(destination)
        outcome, exit_code = "BINARY_INTEGRITY_VERIFIED", 0
    except RemoteError as exc:
        if checks["transfer"] == "pass":
            checks["post_read"] = "fail"
        elif checks["metadata"] == "pass":
            checks["transfer"] = "fail"
        else:
            checks["metadata"] = "fail"
        evidence["error"] = exc.public()
        outcome, exit_code = "CAPABILITY_FAILED", 5
    except (Blocked, IntegrityError) as exc:
        evidence["error"] = {"message": str(exc), **exc.details}
        outcome, exit_code = (
            ("INTEGRITY_FAILED", 7) if isinstance(exc, IntegrityError) else ("BLOCKED", 3)
        )
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    result = {
        "binary_check_id": check_id,
        "asset_id": asset_id,
        "revision": metadata.get("rev"),
        "objective_outcome": outcome,
        "exit_code": exit_code,
        "cache_path": cache_path,
        "sha256": sha,
        "dropbox_content_hash": dbx_hash,
        "byte_size": byte_size,
        **evidence,
    }
    with state.conn:
        state.conn.execute(
            "INSERT INTO binary_checks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                check_id,
                run.id,
                asset_id,
                metadata.get("rev") or "unknown",
                utc_now(),
                cache_path,
                sha,
                dbx_hash,
                byte_size,
                outcome,
                canonical(result),
            ),
        )
        state.event(
            "asset",
            asset_id,
            "binary_check_finished",
            {"binary_check_id": check_id, "outcome": outcome, "checks": checks},
            run.id,
        )
    return result


def require_capability(state, scope=None):
    row = state.conn.execute("""SELECT a.objective_outcome,r.account_id,r.namespace_id,r.root_folder_id
        FROM attempts a JOIN runs r USING(run_id) WHERE a.batch_id='S02'
        ORDER BY a.started_utc DESC LIMIT 1""").fetchone()
    if (
        not row
        or row[0] != "CAPABILITY_PASSED"
        or (
            scope
            and tuple(row)[1:] != (scope.run.account_id, scope.run.namespace_id, scope.run.root_id)
        )
    ):
        raise Blocked("A successful local S02 attempt is required for this binary-dependent review")
