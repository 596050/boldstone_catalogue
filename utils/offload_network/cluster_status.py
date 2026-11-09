#!/usr/bin/env python3
"""Probe every known cluster machine in parallel and report:
  - capacity (cores, CPU%, free RAM/disk)
  - what's running right now (fleet-offload pipelines + Mac-side ssh wrappers)
  - cache-generation capability (legacy libemd or v2 sealed-bundle bootstrap)
  - whether new work can be accepted

Usage:  scripts/cluster_status.py
"""
from __future__ import annotations

import concurrent.futures as cf
import base64
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional


HERE = os.path.dirname(os.path.abspath(__file__))
HOSTS_JSON = os.path.join(HERE, "hosts.json")

# (alias, type, notes)
MACHINES = [
    ("mac",       "local"),
    ("kenne",     "ssh"),     # scan-amd64-w11 via fritz.box LAN
    ("scan-xeon", "ssh"),     # scan-xeon via fritz.box LAN
    ("cdec",      "tailssh"), # cdec_24core via tailnet
    ("scan-new",  "tailssh"), # scan-amd64-new via tailnet
]

# Patterns that mark a "fleet-offload" pipeline so we can count + describe them
FAMOUS_PATTERNS = (
    "random_windows_pipeline",
    "cache_replay_experiments",
    "emd_feature_walkforward",
    "breakthrough_strict_holdout_combined",
    "adaptive_strategy_experiments",
    "extract_raw_mat_features",
    "recompute_with_ig_costs",
    "run_full_regen",
    "generate_cache_chunk",
    "chunk_generator",
    "run_bonds_pipeline.sh",
    "run_tier1_pipeline.sh",
    "iqfeed_downloader",
)


@dataclass
class State:
    alias: str
    reachable: bool = False
    error: Optional[str] = None
    hostname: Optional[str] = None
    cpu_count: Optional[int] = None
    cpu_pct: Optional[float] = None
    mem_total_gb: Optional[float] = None
    mem_free_gb: Optional[float] = None
    disk_free_gb: Optional[float] = None
    famous_procs: int = 0
    proc_summary: list = field(default_factory=list)
    libemd: Optional[bool] = None
    cache_gen_capable: Optional[bool] = None
    elapsed_s: float = 0.0


def _load_inventory() -> dict:
    try:
        with open(HOSTS_JSON, "r", encoding="utf-8") as fh:
            return json.load(fh).get("hosts", {})
    except Exception:
        return {}


def _inventory_cache_capable(cfg: dict | None) -> bool:
    if not cfg:
        return False
    if "cache_gen_capable" in cfg:
        return bool(cfg.get("cache_gen_capable"))
    if cfg.get("has_msys64"):
        return bool(cfg.get("rsync_path"))
    return bool(cfg.get("has_libemd"))


def _safe_float(x):
    try: return float(x)
    except: return None


def probe_mac(s: State) -> None:
    t0 = time.time()
    try:
        s.reachable = True
        s.hostname = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
        s.cpu_count = int(subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True).stdout)
        mem_bytes = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout)
        s.mem_total_gb = mem_bytes / (1024**3)

        top = subprocess.run(["top", "-l", "1", "-n", "0", "-s", "0"], capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"CPU usage:\s+([\d.]+)% user,\s+([\d.]+)% sys", top)
        if m:
            s.cpu_pct = float(m.group(1)) + float(m.group(2))

        vm = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        page_size = 16384  # Apple Silicon default
        pf = re.search(r"Pages free:\s+(\d+)", vm)
        ps = re.search(r"Pages speculative:\s+(\d+)", vm)
        if pf:
            free_pages = int(pf.group(1)) + (int(ps.group(1)) if ps else 0)
            s.mem_free_gb = free_pages * page_size / (1024**3)

        df = subprocess.run(["df", "-g", "/System/Volumes/Data"], capture_output=True, text=True).stdout
        lines = df.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 4:
                s.disk_free_gb = _safe_float(parts[3])

        ps_out = subprocess.run(["ps", "-ef"], capture_output=True, text=True).stdout
        for line in ps_out.split("\n"):
            if any(p in line for p in FAMOUS_PATTERNS):
                # filter out grep itself + this script
                if "grep" in line or "cluster_status" in line:
                    continue
                cols = line.split(None, 7)
                if len(cols) >= 8:
                    cmd = cols[7]
                    # boil down to identifier
                    short = _summarize_cmd(cmd)
                    s.proc_summary.append(short)
        s.famous_procs = len(s.proc_summary)
        # libemd presence
        s.libemd = os.path.exists(os.path.expanduser("~/Developer/fleet-offload/c_emd/build/libemd.dylib"))
    except Exception as e:
        s.error = f"{type(e).__name__}: {e}"
        s.reachable = False
    s.elapsed_s = time.time() - t0


# PowerShell probe — emits a single JSON line we can parse Mac-side
_PROBE_PS = """
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
$cpuP = (Get-Counter '\\Processor(_Total)\\% Processor Time' -SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue
$disk = Get-PSDrive C
$procs = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -match 'random_windows_pipeline|cache_replay_experiments|emd_feature_walkforward|breakthrough_strict|adaptive_strategy_experiments|extract_raw_mat_features|recompute_with_ig|run_full_regen|generate_cache_chunk|chunk_generator|iqfeed_downloader'
})
$details = @()
foreach ($p in $procs | Select-Object -First 8) {
    if ($null -ne $p.CommandLine) {
        $details += $p.CommandLine.Substring(0,[math]::Min(160, $p.CommandLine.Length))
    }
}
# look for libemd in the standard offload locations
$libemd = $false
foreach ($cand in 'C:\\Users\\Kenneth\\Downloads\\fleet-offload\\repo\\c_emd\\build\\libemd.dll','C:\\Users\\Kenneth\\Downloads\\fleet-offload\\c_emd\\build\\libemd.dll','C:\\Users\\kenne\\Downloads\\fleet-offload\\c_emd\\build\\libemd.dll') {
    if (Test-Path $cand) { $libemd = $true; break }
}
@{
    hostname     = $env:COMPUTERNAME
    cpu_count    = $cs.NumberOfLogicalProcessors
    cpu_pct      = [math]::Round($cpuP,1)
    mem_total_gb = [math]::Round($os.TotalVisibleMemorySize/1MB,1)
    mem_free_gb  = [math]::Round($os.FreePhysicalMemory/1MB,1)
    disk_free_gb = [math]::Round($disk.Free/1GB,1)
    famous_procs = $procs.Count
    proc_details = $details
    libemd       = $libemd
} | ConvertTo-Json -Compress -Depth 3
"""


def probe_ssh(s: State, use_tailnet: bool) -> None:
    t0 = time.time()
    try:
        encoded_probe = base64.b64encode(_PROBE_PS.encode("utf-16le")).decode("ascii")
        # On the Mac side we map cdec/scan-new through ~/.ssh/config aliases already.
        # use_tailnet is informational only — alias is what ssh resolves.
        # LAN-first routing (config-driven; Tailscale backup). See lib/routing.py.
        try:
            from lib import routing
            route_opts = routing.ssh_route_opts(s.alias)
        except Exception:
            route_opts = []
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=8",
             "-o", "BatchMode=yes",
             "-o", "ServerAliveInterval=5",
             *route_opts,
             s.alias,
             "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_probe],
            capture_output=True, text=True, timeout=45,
        )
        if r.returncode != 0:
            s.error = f"ssh exit {r.returncode}: {r.stderr.strip()[:160] or '(no stderr)'}"
            return
        # find the JSON line
        for line in r.stdout.split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                d = json.loads(line)
                s.reachable = True
                s.hostname     = d.get("hostname")
                s.cpu_count    = d.get("cpu_count")
                s.cpu_pct      = d.get("cpu_pct")
                s.mem_total_gb = d.get("mem_total_gb")
                s.mem_free_gb  = d.get("mem_free_gb")
                s.disk_free_gb = d.get("disk_free_gb")
                s.famous_procs = d.get("famous_procs", 0)
                s.proc_summary = [_summarize_cmd(x) for x in (d.get("proc_details") or [])]
                s.libemd       = d.get("libemd")
                return
        s.error = f"no JSON in output: {r.stdout[:120]!r}"
    except subprocess.TimeoutExpired:
        s.error = "timeout (>45s)"
    except Exception as e:
        s.error = f"{type(e).__name__}: {e}"
    finally:
        s.elapsed_s = time.time() - t0


def _summarize_cmd(cmd: str) -> str:
    """Boil a full command line down to one-line identifier."""
    cmd = cmd.replace("\n", " ").strip()
    # cherry-pick the most informative piece
    pat = re.search(r"(random_windows_pipeline|cache_replay_experiments|emd_feature_walkforward|breakthrough_strict[a-z_]*|adaptive_strategy_experiments|extract_raw_mat_features|recompute_with_ig_costs|run_full_regen|generate_cache_chunk|chunk_generator|iqfeed_downloader|run_bonds_pipeline|run_tier1_pipeline)", cmd)
    label = pat.group(1) if pat else "?"
    inst = re.search(r"--instruments-list\s+(\S+)", cmd)
    instr = inst.group(1) if inst else ""
    out = re.search(r"--out-root\s+(\S+)", cmd)
    out_dir = (out.group(1).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]) if out else ""
    rd = re.search(r"--run-date\s+(\S+)", cmd)
    runlbl = rd.group(1) if rd else ""
    bits = [b for b in (label, instr, out_dir, runlbl) if b]
    return " :: ".join(bits)


def _fmt_table(states: list[State]) -> None:
    h1 = ("machine","cores","CPU%","RAM GB","free GB","disk free GB","cache-gen","running","capacity")
    rows = []
    for s in states:
        if not s.reachable:
            rows.append((s.alias, "—","—","—","—","—","—","—", f"UNREACHABLE — {s.error or '?'}"))
            continue
        cap = "IDLE" if (s.cpu_pct or 0) < 20 else ("partial" if (s.cpu_pct or 0) < 60 else "BUSY")
        cache_gen = (
            "legacy" if s.libemd
            else ("sealed" if s.cache_gen_capable else ("no" if s.cache_gen_capable is False else "?"))
        )
        rows.append((
            s.alias,
            str(s.cpu_count or "—"),
            f"{s.cpu_pct:.1f}" if s.cpu_pct is not None else "—",
            f"{s.mem_total_gb:.0f}" if s.mem_total_gb else "—",
            f"{s.mem_free_gb:.0f}" if s.mem_free_gb else "—",
            f"{s.disk_free_gb:.0f}" if s.disk_free_gb else "—",
            cache_gen,
            str(s.famous_procs),
            cap,
        ))
    widths = [max(len(str(r[i])) for r in [h1] + rows) for i in range(len(h1))]
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*h1))
    print("-+-".join("-" * w for w in widths))
    for r in rows:
        print(fmt.format(*r))


def main():
    states = [State(alias=a) for a, _ in MACHINES]
    types  = {a: t for a, t in MACHINES}
    inventory = _load_inventory()

    print("probing 5 machines in parallel (~5-15s)...\n")
    with cf.ThreadPoolExecutor(max_workers=len(MACHINES)) as exe:
        futs = []
        for s in states:
            if types[s.alias] == "local":
                futs.append(exe.submit(probe_mac, s))
            else:
                futs.append(exe.submit(probe_ssh, s, types[s.alias] == "tailssh"))
        cf.wait(futs, timeout=60)

    for s in states:
        cfg = inventory.get(s.alias, {})
        s.cache_gen_capable = bool(s.libemd) or _inventory_cache_capable(cfg)

    _fmt_table(states)
    print()
    print("=== running pipelines per machine ===")
    any_running = False
    for s in states:
        if s.proc_summary:
            any_running = True
            print(f"\n[{s.alias}]  ({s.famous_procs} matched proc(s))")
            for line in s.proc_summary[:8]:
                print(f"  • {line}")
    if not any_running:
        print("  (no fleet-offload pipelines running anywhere)")

    print()
    print("=== capacity recommendation ===")
    for s in states:
        if not s.reachable:
            print(f"  {s.alias}: unreachable — fix tailnet/ssh before sending work")
            continue
        spare = (s.cpu_count or 1) * (1 - (s.cpu_pct or 0) / 100)
        spare = int(spare)
        if spare >= 4 and (s.disk_free_gb or 0) > 10:
            suffix = "" if s.cache_gen_capable else "  (not cache-generation capable)"
            print(f"  {s.alias}: ~{spare}/{s.cpu_count} cores free, {s.disk_free_gb:.0f}GB disk — can accept new work{suffix}")
        else:
            print(f"  {s.alias}: ~{spare}/{s.cpu_count} cores free — busy; hold new work")


if __name__ == "__main__":
    main()
