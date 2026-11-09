r"""Confirm cdec state + run nq-realdecomp migrate + offload-bonds-cdec direct delete."""
import sys, subprocess, base64, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Check what's still on cdec
script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$dirs = @('fleet-offload-goal-20260602', 'fleet-offload-nq-realdecomp-20260602',
          'fleet-offload-offload-bonds-cdec', 'fleet-offload-validation-20260602')
foreach ($d in $dirs) {
    $full = 'C:\Users\kenne\Downloads\' + $d
    if (Test-Path $full) {
        $sz = (Get-ChildItem $full -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
        Write-Output ("  PRESENT  {0,7:F2} GB   {1}" -f $sz, $d)
    } else {
        Write-Output ("  GONE             {0}" -f $d)
    }
}
"""

enc = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
r = subprocess.run(
    ['ssh', '-o', 'ConnectTimeout=15', '-o', 'ControlPath=none',
     '-i', '/Users/tomprice/.ssh/id_ed25519_cdec',
     'kenne@cdec-24core', 'powershell.exe', '-NoProfile', '-NonInteractive',
     '-EncodedCommand', enc],
    capture_output=True, text=True, timeout=120
)
print("=== cdec state after kill ===")
print(r.stdout)
