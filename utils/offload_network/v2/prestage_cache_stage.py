"""Pre-stage cache_stage .mat inputs outside sealed archives.

Cache-stage jobs intentionally do not bundle large EMD cache files. Run
this helper before the batch so each cache_stage job can read its source
from:

  <prestaged_cache_root>/<batch>/<instrument_id>/<instrument_id>_live_emd_cache.mat

The transfer uses resumable rsync directly to the target host, with
progress visible by default.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .spec import BatchSpec, SpecError, _resolve_vars
from .transport import push_path, remote_file_size, remote_remove
from .manifest import SealError
from .defaults import prestaged_cache_root


def remote_stage_path(batch_name: str, instrument_id: str) -> str:
    return remote_stage_path_with_root(
        batch_name=batch_name,
        instrument_id=instrument_id,
    )


def remote_stage_path_with_root(
    batch_name: str,
    instrument_id: str,
    *,
    base_root: str | None = None,
) -> str:
    """Build the remote cache file destination for cache-stage rsync."""
    batch_component = batch_name.replace("\\", "_").replace("/", "_")
    root = prestaged_cache_root().rstrip("/\\") if base_root is None else base_root.rstrip("/\\")
    return (
        f"{root}/{batch_component}/{instrument_id}/"
        f"{instrument_id}_live_emd_cache.mat"
    )


def _load_hosts(path: str | pathlib.Path | None) -> dict:
    hp = pathlib.Path(path) if path else (
        pathlib.Path(__file__).resolve().parent.parent / "hosts.json"
    )
    if not hp.is_file():
        raise SealError(f"hosts file not found: {hp}")
    raw = json.loads(hp.read_text())
    return raw.get("hosts", raw)


def _cache_stage_jobs(batch: BatchSpec, only: set[str]) -> list:
    jobs = []
    for j in batch.jobs:
        if j.metadata.get("phase_subkind") != "cache_stage":
            continue
        inst_id = str(j.metadata.get("instrument") or "")
        inst_key = j.name.split(".", 1)[1] if j.name.startswith("cache.") else j.name
        candidates = {j.name, inst_key, inst_id}
        if only and not (only & candidates):
            continue
        jobs.append(j)
    return jobs


def prestage_cache_stage(
    *,
    batch_path: str | pathlib.Path,
    hosts_path: str | pathlib.Path | None = None,
    only: set[str] | None = None,
    force: bool = False,
    dry_run: bool = False,
    quiet: bool = False,
    timeout: int = 7200,
) -> dict:
    batch = BatchSpec.from_path(batch_path)
    hosts = _load_hosts(hosts_path)
    selected = _cache_stage_jobs(batch, only or set())
    rows = []
    errors = []
    for j in selected:
        inst_id = str(j.metadata.get("instrument") or "")
        if not inst_id:
            errors.append({"job": j.name, "error": "missing metadata.instrument"})
            continue
        host_alias = j.host.alias
        if not host_alias:
            errors.append({
                "job": j.name,
                "error": "cache_stage prestage needs a fixed host.alias; set host_pool in workload",
            })
            continue
        hcfg = hosts.get(host_alias)
        if not hcfg:
            errors.append({"job": j.name, "error": f"host {host_alias!r} not in hosts.json"})
            continue
        ssh_alias = hcfg.get("ssh_alias", host_alias)
        cache_root = prestaged_cache_root(hcfg)
        local_cache = pathlib.Path(_resolve_vars(
            f"$CACHE_ROOT/{inst_id}/{inst_id}_live_emd_cache.mat",
            batch.roots,
        ))
        remote_cache = remote_stage_path_with_root(
            batch.batch, inst_id, base_root=cache_root
        )
        row = {
            "job": j.name,
            "instrument": inst_id,
            "host": host_alias,
            "ssh_alias": ssh_alias,
            "local": str(local_cache),
            "remote": remote_cache,
        }
        if not local_cache.is_file():
            row["status"] = "missing_local"
            row["error"] = f"local cache missing: {local_cache}"
            errors.append(row)
            rows.append(row)
            continue
        local_size = local_cache.stat().st_size
        row["size_bytes"] = local_size
        platform = hcfg.get("platform", "windows")
        existing = remote_file_size(
            ssh_alias, remote_cache, platform=platform, timeout=30
        )
        if existing == local_size and not force:
            row["status"] = "already_present"
            rows.append(row)
            continue
        if dry_run:
            row["status"] = "would_push"
            row["remote_size_bytes"] = existing
            rows.append(row)
            continue
        push_path(
            local_path=local_cache,
            host_alias=ssh_alias,
            remote_path=remote_cache,
            rsync_path=hcfg.get("rsync_path"),
            platform=platform,
            timeout=timeout,
            force=force,
            stream=not quiet,
        )
        row["status"] = "pushed"
        rows.append(row)
    return {
        "batch": batch.batch,
        "selected": len(selected),
        "errors": errors,
        "rows": rows,
    }


def purge_prestaged_caches(
    *,
    batch_path: str | pathlib.Path,
    hosts_path: str | pathlib.Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Remove the `<prestaged_cache_root>/<batch>/` directory this batch created on
    each host. Pre-staged cache `.mat` files dwarf the seals, so leaving them behind
    is the single largest remote-disk leak — there was previously NO mechanism to
    remove them. Call once all cache_stage jobs that read the prestaged caches are
    terminal (the batch executor calls this at teardown; also runnable manually via
    `--purge`)."""
    batch = BatchSpec.from_path(batch_path)
    hosts = _load_hosts(hosts_path)
    selected = _cache_stage_jobs(batch, set())
    batch_component = batch.batch.replace("\\", "_").replace("/", "_")
    removed: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for j in selected:
        host_alias = j.host.alias
        hcfg = hosts.get(host_alias) if host_alias else None
        if not hcfg:
            continue
        ssh_alias = hcfg.get("ssh_alias", host_alias)
        cache_root = prestaged_cache_root(hcfg).rstrip("/\\")
        batch_dir = f"{cache_root}/{batch_component}"
        key = (ssh_alias, batch_dir)
        if key in seen:
            continue
        seen.add(key)
        if dry_run:
            removed.append({"host": ssh_alias, "path": batch_dir, "status": "would_remove"})
            continue
        try:
            remote_remove(
                host_alias=ssh_alias, remote_path=batch_dir,
                platform=hcfg.get("platform", "windows"),
            )
            removed.append({"host": ssh_alias, "path": batch_dir, "status": "removed"})
        except Exception as exc:  # never fail a batch over cleanup
            removed.append({"host": ssh_alias, "path": batch_dir, "status": "error", "error": str(exc)})
    return {"batch": batch.batch, "removed": removed}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="v2.prestage_cache_stage",
        description="pre-stage cache_stage .mat inputs on their assigned remote hosts",
    )
    p.add_argument("batch", help="path to batch.json")
    p.add_argument("--hosts", default=None,
                   help="hosts.json path (default: utils/offload_network/hosts.json)")
    p.add_argument("--only", action="append", default=[],
                   help="limit to a job name, instrument key, or instrument id; repeatable")
    p.add_argument("--force", action="store_true",
                   help="push even if remote byte-size already matches")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would be pushed without transferring data")
    p.add_argument("--quiet", action="store_true",
                   help="suppress live rsync progress")
    p.add_argument("--timeout", type=int, default=7200,
                   help="per-transfer timeout seconds")
    p.add_argument("--purge", action="store_true",
                   help="REMOVE the batch's prestaged-cache dir on each host instead of "
                        "pushing (reclaims the large prestaged .mat files once cache_stage "
                        "jobs are done)")
    ns = p.parse_args(argv)
    try:
        if ns.purge:
            out = purge_prestaged_caches(
                batch_path=ns.batch, hosts_path=ns.hosts, dry_run=ns.dry_run,
            )
            print(json.dumps(out, indent=2))
            return 1 if any(r.get("status") == "error" for r in out["removed"]) else 0
        out = prestage_cache_stage(
            batch_path=ns.batch,
            hosts_path=ns.hosts,
            only=set(ns.only or []),
            force=ns.force,
            dry_run=ns.dry_run,
            quiet=ns.quiet,
            timeout=ns.timeout,
        )
    except (SealError, SpecError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 1 if out["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
