"""Verified, non-overwriting retrieval of sealed-job results."""
from __future__ import annotations

import json
import os
import pathlib
import tempfile

from .manifest import SealedManifest, SealError, SealStatus, sha256_of_file
from .safe_archive import extract_tar, open_archive
from .transport import pull_result


def fetch_and_unpack(manifest: SealedManifest, *, workdir_remote: str,
                     pull_into: pathlib.Path | str, remote_status=None) -> dict:
    archive_name = f"{manifest.job_id}.result.{manifest.result.archive_format}"
    if remote_status and remote_status.get("result_archive"):
        archive_name = remote_status["result_archive"].replace("\\", "/").rsplit("/", 1)[-1]
        if archive_name not in {f"{manifest.job_id}.result.tar.gz", f"{manifest.job_id}.result.tar.zst"}:
            raise SealError("unexpected result archive name")
    remote_path = f"{workdir_remote.rstrip('/')}/{archive_name}"
    pull_into = pathlib.Path(pull_into).resolve()
    pull_into.mkdir(parents=True, exist_ok=True)
    archive_local = pull_into / archive_name
    partial = pull_into / (archive_name + ".partial")
    pull_result(remote_path=remote_path, host_alias=manifest.host.ssh_alias,
                local_dest=partial, rsync_path=manifest.host.rsync_path,
                platform=manifest.host.platform)
    digest = sha256_of_file(partial)
    expected = (remote_status or {}).get("result_sha256")
    if not expected or digest != expected:
        raise SealError("missing or mismatched remote result SHA-256; remote evidence retained")
    os.replace(partial, archive_local)
    manifest.status = SealStatus.PULLED
    extract_to = pathlib.Path(manifest.result.local_dir).resolve()
    extract_to.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".result-", dir=extract_to.parent) as temp:
        staging = pathlib.Path(temp) / "content"
        staging.mkdir()
        n_files = _safe_extract(archive_local, staging,
                               max_bytes=manifest.result.max_size_mb * (1 << 20))
        final = json.loads((staging / "status.json").read_text())
        if final.get("job_id") != manifest.job_id or final.get("phase") != "exited":
            raise SealError("result is missing its terminal execution identity")
        if final.get("exit_code") != (remote_status or {}).get("exit_code"):
            raise SealError("result exit code does not match remote receipt")
        if extract_to.exists():
            raise SealError(f"result destination already exists; refusing to mix results: {extract_to}")
        os.replace(staging, extract_to)
    manifest.status = SealStatus.DONE if final["exit_code"] == 0 else SealStatus.FAILED
    return {"archive_local": str(archive_local), "extracted_to": str(extract_to),
            "n_files": n_files, "size_bytes": archive_local.stat().st_size, "sha256": digest}


def _safe_extract(archive: pathlib.Path, dest: pathlib.Path, **limits) -> int:
    try:
        with open_archive(archive) as tar:
            return extract_tar(tar, dest, **limits)
    except (ValueError, OSError) as exc:
        raise SealError(str(exc)) from exc
