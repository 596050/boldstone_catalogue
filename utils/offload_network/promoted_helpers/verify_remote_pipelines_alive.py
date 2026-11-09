"""For each supposedly-active cohort, check:
   - Is the cohort dir on disk growing? (size at T vs T+30s)
   - Is the wrapper PID alive locally on Mac?
   - Are there active python.exe processes on the remote?"""
import sys, subprocess, base64, json, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from fleet.paths import fleet_state_file

JOBS = [
    # (job_id, ssh_alias, identity_file, user, remote_cohort_path)
    (48, "scan-amd64-w11", "/Users/tomprice/.ssh/id_ed25519_kenne", "kenne",
     r"C:\Users\Kenneth\Downloads\fleet-offload\c_emd\results\random_windows_new10_n40_seed500_kenne_20260604"),
    (49, "scan-amd64-w11", "/Users/tomprice/.ssh/id_ed25519_kenne", "kenne",
     r"C:\Users\Kenneth\Downloads\fleet-offload\c_emd\results\random_windows_orig10_n40_seed600_kenne_20260604"),
    (52, "cdec-24core", "/Users/tomprice/.ssh/id_ed25519_cdec", "kenne",
     r"C:\Users\kenne\Downloads\fleet-offload\c_emd\results\random_windows_new10_n40_seed900_cdec_20260604"),
]

def probe_remote_dir(jid, ssh_alias, identity, user, path):
    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$p = '{path}'
if (Test-Path $p) {{
    $files = Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue
    $sz = ($files | Measure-Object -Property Length -Sum).Sum
    $n = ($files | Measure-Object).Count
    $newest = ($files | Sort-Object LastWriteTime -Descending | Select-Object -First 1)
    $ago_min = if ($newest) {{ [math]::Round(((Get-Date) - $newest.LastWriteTime).TotalMinutes, 1) }} else {{ 'n/a' }}
    Write-Output "$jid|$sz|$n|$ago_min"
}} else {{
    Write-Output "$jid|MISSING|0|n/a"
}}
""".replace("$jid", str(jid))
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "ControlPath=none",
             "-i", identity, f"{user}@{ssh_alias}",
             "powershell.exe", "-NoProfile", "-NonInteractive",
             "-EncodedCommand", enc],
            capture_output=True, text=True, timeout=60,
        )
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"{jid}|TIMEOUT|0|n/a"


# T=0 snapshot
print("=== T=0 sample ===")
sample_0 = {}
for jid, ssh_alias, identity, user, path in JOBS:
    line = probe_remote_dir(jid, ssh_alias, identity, user, path)
    sample_0[jid] = line
    print(f"  {line}")

print("\n  ...sleeping 30s to detect growth...\n")
time.sleep(30)

# T=30 snapshot
print("=== T=30 sample ===")
sample_30 = {}
for jid, ssh_alias, identity, user, path in JOBS:
    line = probe_remote_dir(jid, ssh_alias, identity, user, path)
    sample_30[jid] = line
    print(f"  {line}")

# Diff
print("\n=== VERDICT ===")
for jid in [48, 49, 52]:
    p0 = sample_0[jid].split("|")
    p30 = sample_30[jid].split("|")
    try:
        sz0, sz30 = int(p0[1]), int(p30[1])
        delta_mb = (sz30 - sz0) / 1e6
        newest_ago_min = float(p30[3])
        if delta_mb > 1:
            verdict = f"✓ ACTIVE — grew {delta_mb:.1f} MB in 30s; newest file {newest_ago_min} min ago"
        elif newest_ago_min < 5:
            verdict = f"~ IDLE BUT FRESH — no growth but newest file only {newest_ago_min} min ago (between batches?)"
        elif newest_ago_min < 60:
            verdict = f"⚠ STALE — last write {newest_ago_min} min ago — pipeline may have stopped"
        else:
            hr = newest_ago_min / 60
            verdict = f"✗ DEAD — last write {hr:.1f} hours ago — pipeline is over"
    except Exception:
        verdict = f"? UNPARSEABLE — p0={p0} p30={p30}"
    print(f"  job {jid}: {verdict}")

# Check Mac-side wrapper PIDs from state.json
print("\n=== Mac-side wrapper PID alive check ===")
s = json.loads(fleet_state_file().read_text())
import os
for jid in [48, 49, 52]:
    j = next((j for j in s["jobs"] if j["id"] == jid), None)
    if not j:
        print(f"  job {jid}: not in state.json")
        continue
    pid = j.get("wrapper_pid")
    if pid is None:
        print(f"  job {jid}: no wrapper_pid")
        continue
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    except PermissionError:
        alive = True  # exists but ours can't signal
    print(f"  job {jid}: wrapper_pid={pid}  {'ALIVE' if alive else 'DEAD'}")
