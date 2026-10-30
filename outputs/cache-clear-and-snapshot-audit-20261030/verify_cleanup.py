"""Independent readback after the scoped local-cache retirement."""
from pathlib import Path
from contextlib import closing
from urllib.parse import quote
from urllib.request import urlopen
import collections
import hashlib
import json
import sqlite3
import tempfile
import cache_cleanup as c


def main():
    m=c.manifest();before=c.read(c.HERE/'protected-before.json')
    done=c.read(c.HERE/'cache-retirement-complete.json')
    plan=c.read(c.HERE/'cache-retirement-plan.json')
    rows={r['path']:r for r in m['records']}
    removed={j['path']:j for j in (json.loads(x) for x in (c.HERE/'cache-journal.jsonl').read_text().splitlines()) if j['kind']=='CACHE_COPY_REMOVED'}
    assert set(removed)==set(plan['paths']) and len(removed)==done['files']
    assert all(not Path(p).exists() for p in removed)
    assert sum(r['bytes'] for r in removed.values())==done['logical_bytes_removed']
    current=c.snapshot()
    by_path={r['path']:r for r in current['protected_files']}
    for r in before['protected_files']:
        assert r['path'] in by_path,r['path']
        assert all(r[k]==by_path[r['path']][k] for k in ('bytes','mtime_ns','sha256')),r['path']
    active=set(current['protected_paths'])
    assert not active & set(removed)
    assert all(Path(p).is_file() for p in active)
    assert current['event_cutoff']==before['event_cutoff'],'Concurrent edits require explicit comparison'
    assert current['tables']==before['tables'],'Review database changed; inspect concurrent operations'
    old=c.read(c.a.AUDIT/'active-image-dependencies.json')['paths']
    samples={}
    for path,item in old.items():
        if Path(path).is_relative_to(c.CACHE) and path in active:
            key=Path(path).relative_to(c.CACHE).parts[0]
            samples.setdefault(key,item['asset_ids'][0])
    served=[]
    for name,aid in samples.items():
        with urlopen('http://127.0.0.1:8767/api/image?id='+quote(aid,safe='')+'&size=thumb',timeout=45) as response:
            data=response.read();assert response.status==200 and data
        served.append({'cache_area':name,'asset_id':aid,'served_bytes':len(data)})
    with urlopen('http://127.0.0.1:8767/api/health',timeout=20) as response:health=json.load(response)
    assert health['status']=='ok' and health['products']==181
    # Restore representative removed files from every retained source and compare bytes + metadata.
    sample_rows={}
    for row in m['records']:
        if row['path'] not in removed:continue
        key=m['blobs'][row['sha256']]['storage']+(' with Mac attributes' if row.get('xattrs_base64') else '')
        if key not in sample_rows or row['bytes']<sample_rows[key]['bytes']:sample_rows[key]=row
    restored=[]
    with tempfile.TemporaryDirectory(prefix='.post-removal-restore-',dir=c.HERE) as td:
        for source,row in sample_rows.items():
            dest=Path(td)/row['sha256']
            c.restore(row['path'],dest,True)
            assert c.native.digest(dest)==row['sha256']
            assert c.native.metadata(dest)==row['metadata']
            restored.append({'source':source,'original_path':row['path'],'sha256':row['sha256'],'bytes':row['bytes']})
    final_space=c.native.space();space_before=c.read(c.HERE/'space-before.json')
    remaining=[p for p in c.CACHE.rglob('*') if p.is_file() and not p.is_symlink()]
    archive=c.read(c.HERE/'cache-archive-verified.json')
    summary={'status':'PASS','completed_utc':c.now(),'cache_files_removed':len(removed),
             'cache_logical_bytes_removed':done['logical_bytes_removed'],'cloud_mutations':0,
             'retained_sources':dict(collections.Counter(m['blobs'][rows[p]['sha256']]['storage'] for p in removed)),
             'new_archive_bytes':archive['new_archive_bytes'],'skipped':done['skipped'],
             'protected_files_unchanged':len(before['protected_files']),'active_image_paths_preserved':len(active),
             'review_tables_unchanged':True,'live_app':health,'live_image_samples':served,'post_removal_restores':restored,
             'remaining_cache_files':len(remaining),'remaining_cache_bytes':sum(p.stat().st_size for p in remaining),
             'observed_available_space_increase_bytes':final_space['available_bytes']-space_before['available_bytes'],
             'space_after':final_space,'space_caveat':'Observed system free space includes concurrent activity and APFS sharing.',
             'snapshot_changes':0}
    c.write(c.HERE/'cache-cleanup-summary.json',summary)
    c.emit(**summary)


if __name__=='__main__':main()
