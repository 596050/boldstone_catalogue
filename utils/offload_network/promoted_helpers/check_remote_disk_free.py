import sys, subprocess, base64
script = r"""
$d = Get-PSDrive C
Write-Output ("free_bytes:  " + $d.Free)
Write-Output ("free_GB:     " + [math]::Round($d.Free/1GB, 2))
Write-Output ("used_GB:     " + [math]::Round($d.Used/1GB, 2))
Write-Output ("total_GB:    " + [math]::Round(($d.Used + $d.Free)/1GB, 2))
"""
enc = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
r = subprocess.run(
    ['ssh', '-o', 'ConnectTimeout=15', '-o', 'ControlPath=none',
     '-i', '/Users/tomprice/.ssh/id_ed25519_kenne',
     'kenne@scan-amd64-w11', 'powershell.exe', '-NoProfile', '-NonInteractive',
     '-EncodedCommand', enc],
    capture_output=True, text=True, timeout=30
)
print(r.stdout)
