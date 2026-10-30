from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import gzip
import html
import json
import os

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).resolve().parent
load = lambda name: json.loads((OUT / name).read_text())
plan = load('first-pass-space-plan.json')
dups = load('duplicates-summary.json')
archives = load('verified-test-export-candidates.json')
dbs = load('database-archive-candidates.json')
files = json.load(gzip.open(OUT / 'file-inventory.json.gz', 'rt'))
groups = json.load(gzip.open(OUT / 'exact-duplicates.json.gz', 'rt'))
required = load('live-app-required-files.json')
top = defaultdict(int)
for f in files:
    top[f['path'].split('/')[0]] += f['allocated']
info = os.statvfs(ROOT)
summary = {'checked_utc': datetime.now(timezone.utc).isoformat(),
           'root': str(ROOT), 'workspace_file_allocated_bytes': sum(f['allocated'] for f in files),
           'workspace_logical_bytes': sum(f['bytes'] for f in files), 'host_available_bytes': info.f_bavail * info.f_frsize,
           'file_count': len(files), 'first_pass': plan, 'duplicates': dups,
           'live_app_files_within_workspace': len(required),
           'live_app_allocated_bytes_within_workspace': sum(Path(p).stat().st_blocks * 512 for p in required),
           'no_files_deleted': True,
           'qualifications': ['Do not add duplicate and compression totals: they overlap.',
                              'Reported allocation may include shared APFS extents; it is not a guaranteed free-space increase.',
                              'Existing ZIP byte comparisons passed for six historical test exports. Retain ZIP files; old export paths can be restored from them.',
                              'Compression was measured in memory. No new archive has been created. Verify archive restoration before removing raw historical copies.',
                              'Keep the live app database, metadata receipts, current master, source exports, current upload package, source code and unique image/evidence files.',
                              'Live review database and most runtime caches are outside this directory; they are not included in these cleanup figures.']}
(OUT / 'space-audit-summary.json').write_text(json.dumps(summary, indent=2))
esc = lambda s: html.escape(str(s), quote=True)
gib = lambda n: f'{n / 1024**3:.2f} GiB'
def link(path, label=None):
    return f'<a href="{esc((ROOT / path).as_uri())}">{esc(label or path)}</a>'
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Boldstone space audit</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;color:#25372c;background:#f7f6f0}h1{font:38px Georgia,serif}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}th,td{border:1px solid #d7dfd3;padding:10px;text-align:left;vertical-align:top}th{background:#e6eddf}a{color:#416b49;overflow-wrap:anywhere}code{overflow-wrap:anywhere;font-size:13px}.note{padding:16px;background:#e8ecdf}details{margin:14px 0}li{margin:6px 0}.small{font-size:13px}</style><h1>Boldstone disk-space assessment</h1>'''
page += f'<p>{esc(summary["checked_utc"])}. <strong>Read-only assessment; no files deleted.</strong></p><p>The directory contains {gib(summary["workspace_file_allocated_bytes"])} of reported file allocation in {len(files):,} files. The Mac has {gib(summary["host_available_bytes"])} available.</p>'
page += '<table><tr><th>Cleanup step</th><th>Measured candidate saving</th><th>Evidence and remaining step</th></tr>'
page += f'<tr><td>Remove extracted historical test exports, retaining their existing ZIPs</td><td>{gib(plan["existing_archive_extracted_copy_bytes"])}</td><td>Six directories; all 72 files byte-compared against existing archives. No current app dependency or open file found. Keep the ZIPs and audit receipts.</td></tr>'
page += f'<tr><td>Losslessly compress 83 other historical review database copies</td><td>{gib(plan["additional_compression_savings_bytes"])}</td><td>{gib(plan["remaining_database_allocated_bytes"])} measured to become approximately {gib(plan["remaining_database_gzip_bytes"])}. Create archives, verify restoration, and retain a restoration index before removing raw copies.</td></tr>'
page += f'<tr><td><strong>Conservative first pass, without double-counting</strong></td><td><strong>{gib(plan["nonoverlapping_first_pass_candidate_bytes"])}</strong></td><td>Preserves current data, image sources and historical records.</td></tr>'
page += f'<tr><td>Broader exact-duplicate consolidation</td><td>{gib(dups["duplicate_allocated_bytes"])}</td><td>{dups["duplicate_files"]:,} byte-identical repeated copies in {dups["groups"]:,} groups. Paths may be needed by historical reports. Use path-preserving consolidation or indexed archives. This total overlaps the first pass.</td></tr></table>'
page += '<div class="note">These are measured allocation and compression figures, not space already recovered. APFS may share blocks between copies, so the actual free-space increase must be checked after cleanup. Do not add the broader duplicate total to the first-pass total.</div>'
page += '<h2>Directory breakdown</h2><table><tr><th>Directory</th><th>Reported file allocation</th></tr>'
for name, size in sorted(top.items(), key=lambda r: r[1], reverse=True):
    if size > 10 * 1024 * 1024:
        page += f'<tr><td>{link(name)}</td><td>{gib(size)}</td></tr>'
page += '</table><h2>Existing archive verification</h2><table><tr><th>Extracted test export</th><th>Result</th><th>Allocation</th><th>Keep this archive</th></tr>'
for r in archives['results']:
    page += f'<tr><td>{link(r["directory"])}</td><td>{esc(r["status"])}{("<br>" + esc("; ".join(r["errors"]))) if r["errors"] else ""}</td><td>{gib(r["allocated_bytes"])}</td><td>{link(r["archive"])}</td></tr>'
page += '</table><p>The export whose file set differs is excluded from the removal total.</p>'
page += '<details><summary>83 additional database copies proposed for lossless archiving</summary><table><tr><th>Path</th><th>Current allocation</th><th>Measured compressed size</th></tr>'
done = [r['directory'] + '/' for r in archives['results'] if r['status'].startswith('PASS')]
for r in dbs:
    if any(r['path'].startswith(p) for p in done):
        continue
    page += f'<tr><td><code>{esc(r["path"])}</code></td><td>{gib(r["allocated"])}</td><td>{r["gzip_bytes"] / 1024**2:.2f} MiB</td></tr>'
page += '</table></details><details><summary>Largest 20 byte-identical duplicate groups</summary><table><tr><th>Example retained copy</th><th>Copies</th><th>Repeated allocation</th></tr>'
for g in groups[:20]:
    page += f'<tr><td><code>{esc(g["files"][0]["path"])}</code></td><td>{len(g["files"])}</td><td>{gib(g["duplicate_allocated_bytes"])}</td></tr>'
page += '</table><p>Examples are reporting keepers, not deletion instructions. Exact path/hash manifests are retained alongside this report.</p></details>'
page += f'<h2>Protected live data</h2><p>{len(required)} files within this directory currently support the app, accounting for {gib(summary["live_app_allocated_bytes_within_workspace"])}. This includes the current catalogue database and cached image sources in older review directories. Clearing whole reports or sculpture-catalogue folders would break the app.</p>'
page += '<p>The authoritative reviews database is <code>/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3</code>, outside this directory. Preserve that database, review events, native job/deletion history and original-image metadata receipts. Also retain the current upload package, source exports, canonical records, scripts and unique evidence.</p><p>Audit methods: same-filesystem inventory without following symlinks; SHA-256 comparisons of 10,741 same-size candidate files; current app path resolution; open-file check; read-only gzip size measurement; byte-for-byte ZIP validation. No Dropbox originals or app choices were modified.</p></html>'
(OUT / 'space-cleanup-assessment.html').write_text(page)
print(json.dumps({k:v for k,v in summary.items() if k not in ('duplicates','qualifications')},indent=2))
