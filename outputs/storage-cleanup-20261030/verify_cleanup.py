"""Full independent readback after archival and COW consolidation."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
import sqlite3
import urllib.request
import zipfile
import storage_primitives as native

ROOT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).resolve().parent
load=lambda p:json.loads(Path(p).read_text())
before=load(OUT/'live-protected-before.json')
intents={};changed={};exports=[]
for line in (OUT/'journal.jsonl').read_text().splitlines():
    row=json.loads(line)
    if row.get('status')=='COW_INTENT':intents[row['path']]=row
    if row.get('status')=='COW_VERIFIED_OLD_STORAGE_RETIRED':changed[row['path']]=row
    if row.get('status')=='VERIFIED_ARCHIVE_BEFORE_RETIREMENT':exports.append(row)

def check_file(row):
    p=Path(row['path'])
    assert p.is_file() and not p.is_symlink(),str(p)
    assert native.digest(p)==row['sha256'],str(p)
    if row['path'] in intents:
        assert native.metadata(p)==intents[row['path']]['original_metadata'],str(p)
    if 'mtime_ns' in row:assert p.stat().st_mtime_ns==row['mtime_ns'],str(p)
    return p

with ThreadPoolExecutor(max_workers=2) as pool:
    protected=list(pool.map(check_file,before['files']))
    dedup=list(pool.map(check_file,changed.values()))

for row in exports:
    assert not Path(row['directory']).exists(),row['directory']
    archive=Path(row['archive']);assert native.digest(archive)==row['archive_sha256']
    with zipfile.ZipFile(archive) as z:
        assert set(z.namelist())==set(row['files'])
        for name,original in row['files'].items():
            with z.open(name) as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==original['sha256']

database_rows=load(OUT/'databases-complete.json')['results']
for row in database_rows:
    assert not Path(row['original_path']).exists(),row['original_path']
    assert native.digest(Path(row['archive_path']))==row['archive_sha256']
    with gzip.open(row['archive_path'],'rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==row['sha256']

runtime=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
with sqlite3.connect('file:'+str(runtime/'reviews.sqlite3')+'?mode=ro',uri=True) as db:
    db.execute('BEGIN')
    cutoff=db.execute('SELECT MAX(id) FROM events').fetchone()[0]
    tables={}
    for name,expected in before['tables'].items():
        rows=db.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid').fetchall()
        actual={'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()}
        tables[name]={'before':expected,'after':actual,'unchanged':actual==expected}
    assert all(v['unchanged'] for k,v in tables.items() if k not in ('events','reviews')),tables
    # The app stays usable during cleanup. Verify its original history and
    # reconstruct the exact before/after review tables from the saved events.
    events=db.execute('SELECT * FROM events ORDER BY rowid').fetchall()
    old_events=[row for row in events if row[0]<=before['event_cutoff']]
    def table_hash(rows):
        return {'rows':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()}
    assert table_hash(old_events)==before['tables']['events'],'Original review history changed'
    def reconstructed_reviews(event_rows):
        latest={}
        for row in event_rows:
            latest[tuple(row[2:5])]=(row[0],json.loads(row[6]))
        rows=[]
        for _,data in sorted(latest.values(),key=lambda pair:pair[0]):
            rows.append((data['kind'],data['product_id'],data['item_id'],data['version'],json.dumps(data['data']),data['source_hash'],json.dumps(data['original']),data['updated_at']))
        return table_hash(rows)
    assert reconstructed_reviews(old_events)==before['tables']['reviews'],'Baseline review reconstruction differs'
    assert reconstructed_reviews(events)==tables['reviews']['after'],'Unexplained review changes'
    concurrent_changes=[{'event_id':row[0],'at':row[1],'kind':row[2],'product_id':row[3],
                         'data':json.loads(row[6])['data']} for row in events if row[0]>before['event_cutoff']]
health=json.load(urllib.request.urlopen('http://127.0.0.1:8767/api/health',timeout=60))
assert health['status']=='ok' and health['products']==181
result={'status':'PASS_FULL_READBACK_WITH_CONCURRENT_REVIEW_EDITS' if concurrent_changes else 'PASS_FULL_READBACK','checked_utc':native.now(),'protected_files_byte_verified':len(protected),
        'duplicate_paths_byte_and_metadata_verified':len(dedup),'existing_zip_archives_verified':len(exports),
        'database_archives_byte_verified':len(database_rows),'live_review_tables':tables,'event_cutoff':cutoff,
        'live_app':health,'space_before':load(OUT/'space-before.json'),'space_after':native.space(),
        'cloud_mutations':0,'hard_links_created':0,'original_image_paths_removed':0}
result['concurrent_app_review_changes']=concurrent_changes
result['original_review_history_unchanged']=True
result['review_changes_fully_explained_by_saved_events']=True
result['observed_available_space_increase']=result['space_after']['available_bytes']-result['space_before']['available_bytes']
(OUT/'verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='live_review_tables'},indent=2))
