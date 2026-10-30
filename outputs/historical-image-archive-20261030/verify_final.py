"""Independent final readback of retirement, protected media and live review history."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
import collections
import hashlib
import json
import sqlite3
import zipfile
import archive_images as a

m=a.manifest();before=a.read(a.HERE/'live-protected-before.json')
done=a.read(a.HERE/'retirement-complete.json');plan=a.read(a.HERE/'retirement-plan.json')
removed={r['path']:r for r in (json.loads(line) for line in (a.HERE/'journal.jsonl').read_text().splitlines()) if r['kind']=='LOCAL_COPY_REMOVED'}
assert len(removed)==done['files'] and set(removed)==set(plan['paths'])
by_path={r['path']:r for r in m['records']}
assert all(not (a.ROOT/p).exists() for p in removed)
cloud={r['id']:r for r in a.read(a.HERE/'dropbox-before-retirement.json')['files']}
counts=collections.Counter()
with zipfile.ZipFile(a.HERE/m['archive']) as z:
    for p,r in removed.items():
        row=by_path[p];b=m['blobs'][row['sha256']];counts[b['storage']]+=1
        assert row['sha256']==r['sha256']
        if b['storage']=='archive':assert z.getinfo(b['member']).file_size==row['bytes']
        elif b['storage']=='dropbox':
            current=cloud[b['cloud']['id']]
            assert (current['revision'],current['content_hash'],current['bytes'])==(b['cloud']['revision'],row['dropbox_content_hash'],row['bytes'])
        else:assert Path(b['keeper']).is_file()
assert a.native.digest(a.HERE/m['archive'])==a.read(a.HERE/'archive-verified.json')['archive_sha256']

def protected(row):
    path=Path(row['path'])
    assert path.is_file() and not path.is_symlink(),row['path']
    assert path.stat().st_mtime_ns==row['mtime_ns'],row['path']
    assert a.native.digest(path)==row['sha256'],row['path']
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(protected,before['files']))
active=a.fresh_dependencies()
assert not active & {str(a.ROOT/p) for p in removed}
assert all(Path(p).is_file() for p in active)
# Check live HTTP image serving as well as path existence, across repository source folders.
old=a.read(a.AUDIT/'active-image-dependencies.json')['paths']
samples={}
for path,entry in old.items():
    if Path(path).is_relative_to(a.ROOT):
        key='/'.join(Path(path).relative_to(a.ROOT).parts[:3])
        samples.setdefault(key,(path,entry['asset_ids'][0]))
http=[]
for path,aid in samples.values():
    with urlopen('http://127.0.0.1:8767/api/image?id='+quote(aid,safe=''),timeout=60) as response:
        body=response.read();assert response.status==200
    http.append({'asset_id':aid,'bytes':len(body),'path':path})

def table_hash(rows):
    return {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()}
runtime=a.RUNTIME/'reviews.sqlite3'
with sqlite3.connect('file:'+str(runtime)+'?mode=ro',uri=True) as db:
    db.execute('BEGIN')
    events=db.execute('SELECT * FROM events ORDER BY rowid').fetchall()
    old_events=[r for r in events if r[0]<=before['event_cutoff']]
    assert table_hash(old_events)==before['tables']['events'],'Original event history changed'
    tables={}
    for name,expected in before['tables'].items():
        rows=db.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid').fetchall()
        actual=table_hash(rows);tables[name]={'unchanged':actual==expected,'before':expected,'after':actual}
    concurrent=[r[0] for r in events if r[0]>before['event_cutoff']]
    if not concurrent:
        assert tables['reviews']['unchanged'],'Review choices changed without an event'
health=json.load(urlopen('http://127.0.0.1:8767/api/health',timeout=30))
assert health['status']=='ok' and health['products']==181
after=a.native.space();space_before=a.read(a.HERE/'space-before.json')
result={'status':'PASS_RETIREMENT_ARCHIVE_AND_LIVE_APP_READBACK','verified_utc':a.now(),
        'local_image_copies_removed':len(removed),'logical_image_bytes_removed':done['logical_bytes_removed'],
        'restore_source_paths':dict(counts),'archive_bytes':(a.HERE/m['archive']).stat().st_size,
        'archive_images_full_restore_verified':a.read(a.HERE/'archive-verified.json')['images'],
        'protected_files_byte_verified':len(before['files']),'current_local_app_image_paths_verified':len(active),
        'live_http_image_checks':http,'live_app':health,'original_event_history_unchanged':True,
        'concurrent_user_event_ids':concurrent,'live_review_tables':tables,
        'files_retained_for_extended_metadata':len(m['skipped']),'retirement_skips':done['skipped'],
        'space_before':space_before,'space_after':after,
        'observed_available_space_increase':after['available_bytes']-space_before['available_bytes'],
        'space_measurement_note':'Observed system-wide change; concurrent activity and APFS sharing prevent exact attribution.',
        'cloud_mutations':0,'archive_viewer':'http://127.0.0.1:8778/'}
a.write(a.HERE/'verification.json',result)
a.emit(**{k:v for k,v in result.items() if k not in ('live_http_image_checks','live_review_tables','space_before','space_after','retirement_skips')})
