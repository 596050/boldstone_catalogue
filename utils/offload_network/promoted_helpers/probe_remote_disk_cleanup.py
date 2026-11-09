"""What's taking space on kenne RIGHT NOW + what's safe to delete."""
import sys, subprocess, base64, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from lib.remote import ps

script = r"""
$ErrorActionPreference = 'SilentlyContinue'

Write-Output "=== TOP 10 DIRS under C:\Users\Kenneth\Downloads (largest first) ==="
$base = 'C:\Users\Kenneth\Downloads'
Get-ChildItem $base -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $sz = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
    [PSCustomObject]@{N=$_.Name; G=[math]::Round($sz,2)}
} | Sort-Object G -Descending | Select-Object -First 10 | ForEach-Object {
    Write-Output ("  {0,7:F2} GB  {1}" -f $_.G, $_.N)
}

Write-Output ""
Write-Output "=== fleet-offload\c_emd\results\ cohort dirs (per-cohort sizes) ==="
$rd = "$base\fleet-offload\c_emd\results"
if (Test-Path $rd) {
    Get-ChildItem $rd -Directory -Filter random_windows_* | ForEach-Object {
        $sz = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
        $mats = (Get-ChildItem $_.FullName -File -Filter *.mat -ErrorAction SilentlyContinue | Measure-Object).Count
        $chunks = (Get-ChildItem $_.FullName -Directory -Filter *_chunks -ErrorAction SilentlyContinue | Measure-Object).Count
        Write-Output ("  {0,7:F2} GB   mats={1,3}  chunks_dirs={2,3}   {3}" -f $sz, $mats, $chunks, $_.Name)
    }
}

Write-Output ""
Write-Output "=== *_chunks/ subdirs (safe-to-delete intermediate scratch) ==="
$total_chunks_gb = 0
if (Test-Path $rd) {
    Get-ChildItem $rd -Directory -Filter random_windows_* | ForEach-Object {
        $coh = $_
        Get-ChildItem $coh.FullName -Directory -Filter *_chunks* -ErrorAction SilentlyContinue | ForEach-Object {
            $sz = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
            $total_chunks_gb += $sz
        }
    }
}
Write-Output ("  TOTAL chunks across all cohorts: {0:F2} GB" -f $total_chunks_gb)

Write-Output ""
Write-Output "=== Temp + caches (low-value, mostly safe) ==="
$temps = @{
    'user temp' = "$env:TEMP"
    'win temp'  = 'C:\Windows\Temp'
    'pip cache' = 'C:\Users\Kenneth\AppData\Local\pip\cache'
    'msys64 tmp'= 'C:\msys64\tmp'
}
foreach ($k in $temps.Keys) {
    $p = $temps[$k]
    if (Test-Path $p) {
        $sz = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1GB
        Write-Output ("  {0,7:F2} GB   {1,-10}  {2}" -f $sz, $k, $p)
    }
}

Write-Output ""
Write-Output "=== Disk summary ==="
$d = Get-PSDrive C
Write-Output ("  C: free = {0:F2} GB / total = {1:F2} GB" -f ($d.Free/1GB), (($d.Used+$d.Free)/1GB))
"""

r = ps('kenne', script, timeout=240)
print(r.stdout)
if r.stderr and 'CLIXML' not in r.stderr[:20]:
    print("STDERR:", r.stderr[:300])
