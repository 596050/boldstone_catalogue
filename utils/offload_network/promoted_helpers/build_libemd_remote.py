"""Build libemd on scan-new via lib.remote (avoids SSH quote hell)."""
import sys, subprocess, base64, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

script = r"""
$env:PATH = 'C:\msys64\ucrt64\bin;C:\msys64\usr\bin;' + $env:PATH
Set-Location 'C:\Users\kenne\Downloads\fleet-offload\c_emd'
& 'C:\msys64\ucrt64\bin\mingw32-make.exe' -f Makefile.win 2>&1
if (Test-Path 'build\libemd.dll') {
    Write-Output ("BUILD_OK: libemd.dll size = " + (Get-Item 'build\libemd.dll').Length + " bytes")
} else {
    Write-Output "BUILD_FAIL: libemd.dll missing"
}
"""

enc = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
result = subprocess.run(
    ['ssh', '-o', 'ConnectTimeout=20', '-o', 'ControlPath=none',
     '-i', '/Users/tomprice/.ssh/id_ed25519_scan-new',
     'kenne@100.99.157.53',
     'powershell.exe', '-NoProfile', '-NonInteractive',
     '-EncodedCommand', enc],
    capture_output=True, text=True, timeout=600
)
print(result.stdout)
if result.stderr.strip():
    print("STDERR:", result.stderr[:1500])
