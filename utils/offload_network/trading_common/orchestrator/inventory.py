"""Cross-host inventory probes — what data lives where.

Probes each host's fleet-offload* directories for cohort outputs, then writes
per-host JSON snapshots under ~/.fleet/orchestrator/inventory/<host>.json.
Cached: refresh only if older than TTL_HOURS.
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import pathlib
import subprocess
import sys
from typing import Optional

from .schema import (
    ArtifactType, StorageTier,
)
from .store import OrchestratorStore, get_store, _now_iso


TTL_HOURS_DEFAULT = 2

# Hardcoded host probe map. In a fuller impl this comes from hosts.json,
# but for now stay aligned with the session's hosts.
_HOST_PROBES = [
    # (alias_for_ssh, identity_file, user, downloads_base)
    ("scan-amd64-w11", "~/.ssh/id_ed25519_kenne",     "kenne",   r"C:\Users\Kenneth\Downloads"),
    ("cdec-24core",    "~/.ssh/id_ed25519_cdec",      "kenne",   r"C:\Users\kenne\Downloads"),
    ("scan-xeon",      "~/.ssh/id_ed25519_scan-xeon", "Kenneth", r"C:\Users\Kenneth\Downloads"),
    ("100.99.157.53",  "~/.ssh/id_ed25519_scan-new",  "kenne",   r"C:\Users\kenne\Downloads"),
]
# Map back to canonical fleet aliases for storage
_ALIAS_MAP = {
    "scan-amd64-w11": "kenne",
    "cdec-24core":    "cdec",
    "scan-xeon":      "scan-xeon",
    "100.99.157.53":  "scan-new",
}


def _probe_one_host(ssh_alias: str, identity: str, user: str,
                    downloads_base: str, timeout: int = 300) -> dict:
    """Run a PowerShell inventory probe on one host. Returns a dict of
    cohort-name → (size_mb, file_count, last_modified_iso, container_dir, full_path).
    """
    identity_expanded = str(pathlib.Path(identity).expanduser())
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$bases = @('{downloads_base}', '{downloads_base}\\offload')
$now = Get-Date

foreach ($base in $bases) {{
    if (-not (Test-Path $base)) {{ continue }}
    Get-ChildItem $base -Directory -Filter 'fleet-offload*' -ErrorAction SilentlyContinue | ForEach-Object {{
        $top = $_
        $resroots = @(
            (Join-Path $top.FullName 'c_emd\\results'),
            (Join-Path $top.FullName 'repo\\c_emd\\results')
        )
        foreach ($r in $resroots) {{
            if (-not (Test-Path $r)) {{ continue }}
            Get-ChildItem $r -Directory -ErrorAction SilentlyContinue | ForEach-Object {{
                $cohort = $_
                $mats = Get-ChildItem $cohort.FullName -File -Filter *.mat -ErrorAction SilentlyContinue
                if ($mats.Count -gt 0) {{
                    $sz_b = ($mats | Measure-Object -Property Length -Sum).Sum
                    $newest_iso = ($mats | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime.ToString('o')
                    Write-Output ("$($top.Name)|$($cohort.FullName)|$($cohort.Name)|$($mats.Count)|$sz_b|$newest_iso")
                }}
            }}
        }}
    }}
}}
"""
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "ControlPath=none",
             "-o", "StrictHostKeyChecking=no",
             "-i", identity_expanded, f"{user}@{ssh_alias}",
             "powershell.exe", "-NoProfile", "-NonInteractive",
             "-EncodedCommand", enc],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"_error": f"timeout after {timeout}s", "_cohorts": []}
    except Exception as e:
        return {"_error": str(e), "_cohorts": []}

    cohorts = []
    for line in (r.stdout or "").strip().splitlines():
        parts = line.split("|", 5)
        if len(parts) != 6:
            continue
        container, full_path, name, n, sz_b, last = parts
        try:
            cohorts.append({
                "container": container,
                "full_path": full_path,
                "name": name,
                "file_count": int(n),
                "size_bytes": int(sz_b),
                "last_modified": last,
            })
        except Exception:
            continue
    return {
        "_error": None if r.returncode == 0 else f"ssh rc={r.returncode}",
        "_cohorts": cohorts,
    }


def probe_host_inventory(canonical_host: str,
                         store: Optional[OrchestratorStore] = None,
                         emit_artifact_events: bool = True) -> dict:
    """Probe one host and persist results."""
    store = store or get_store()
    match = next(((s, i, u, d) for s, i, u, d in _HOST_PROBES
                  if _ALIAS_MAP.get(s) == canonical_host), None)
    if not match:
        return {"_error": f"unknown host: {canonical_host}", "_cohorts": []}
    ssh_alias, identity, user, base = match
    res = _probe_one_host(ssh_alias, identity, user, base)
    res["host"] = canonical_host
    res["probed_at"] = _now_iso()

    out_path = store.base_dir / "inventory" / f"{canonical_host}.json"
    out_path.write_text(json.dumps(res, indent=2))

    if emit_artifact_events and res.get("_cohorts"):
        for c in res["_cohorts"]:
            artifact_id = f"cohort:{c['name']}@{canonical_host}"
            store.observe_artifact(
                id=artifact_id,
                artifact_type=ArtifactType.COHORT_OUTPUT,
                storage_tier=StorageTier.HOT_REMOTE,
                host=canonical_host,
                path=c["full_path"],
                size_bytes=c["size_bytes"],
                file_count=c["file_count"],
                cohort_name=c["name"],
                notes=f"container={c['container']} last_modified={c['last_modified']}",
            )
    return res


def refresh_inventory(hosts: list[str] | None = None,
                      max_age_hours: float = TTL_HOURS_DEFAULT,
                      parallel: bool = True) -> dict[str, dict]:
    """Refresh inventory for each host if older than max_age_hours."""
    store = get_store()
    targets = hosts or list(_ALIAS_MAP.values())
    results: dict[str, dict] = {}

    def _needs_refresh(host: str) -> bool:
        p = store.base_dir / "inventory" / f"{host}.json"
        if not p.exists():
            return True
        try:
            d = json.loads(p.read_text())
            ts = _dt.datetime.fromisoformat(d.get("probed_at", "1970-01-01T00:00:00+00:00"))
            age = _dt.datetime.now(_dt.timezone.utc) - ts
            return age.total_seconds() > max_age_hours * 3600
        except Exception:
            return True

    to_probe = [h for h in targets if _needs_refresh(h)]
    cached   = [h for h in targets if h not in to_probe]

    if parallel and to_probe:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(probe_host_inventory, h): h for h in to_probe}
            for fut in futures:
                h = futures[fut]
                try:
                    results[h] = fut.result()
                except Exception as e:
                    results[h] = {"_error": str(e), "_cohorts": []}
    else:
        for h in to_probe:
            results[h] = probe_host_inventory(h)

    for h in cached:
        try:
            results[h] = json.loads((store.base_dir / "inventory" / f"{h}.json").read_text())
        except Exception:
            results[h] = {"_error": "cache read failed", "_cohorts": []}
    return results


def load_inventory(host: str) -> Optional[dict]:
    """Read the cached inventory for a host (no probe)."""
    store = get_store()
    p = store.base_dir / "inventory" / f"{host}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None
