"""Seal five owner-executed deletions without importing other review choices."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
import hashlib
import json
import sqlite3

H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'availability-overlay.json').exists()
pfile=B/'current-master.json';p=read(pfile)
assert sha(pfile)=='7d736342277e040da4423ce6113553e230f582f2e238bb5916d1df44fa37057f'
assert sha(B/p['register'])==p['register_sha256']
g=read(B/p['register']);assets=read(B/p['current_asset_reference_map']['path'])
assert sha(B/p['current_asset_reference_map']['path'])==p['current_asset_reference_map']['sha256']
inspection=read(H/'native-inspection.json')
targets={x['target'] for x in inspection['metadata'] if x['target'].startswith('id:')}
assert targets=={'id:cnqzTNngPVsAAAAAAAt4Uw','id:cnqzTNngPVsAAAAAAAt4DA','id:cnqzTNngPVsAAAAAAAt_xw','id:cnqzTNngPVsAAAAAAAt_yQ','id:cnqzTNngPVsAAAAAAAuVxg'}
for r in inspection['metadata']:
    if r['target'] in targets:assert r['isError'] and 'NOT_FOUND' in r['text']
    else:assert not r['isError'] and r['metadata_type']=='folder'
present={x['file_id'] for f in inspection['folder_listings'] for x in f['entries']}
assert present.isdisjoint(targets) and len(present)==3
assert all(not f['has_more'] and not f['cursor'] for f in inspection['folder_listings'])
collaborator_files=[B.parent/'catalogue-review/reviews'/name for name in ['acanthus-flower-deletion-readback-20261025.json','acanthus-and-moon-white-deletion-readback-20261025.json']]
independent={r['file_id']:{'file_id':r['file_id'],**r.get('current_dropbox_status',r)}
    for f in collaborator_files for r in read(f)['results']}
assert set(independent)==targets
assert all(r['state']=='deleted' and r['verified_absent'] for r in independent.values())
snapshot=Path('/Users/tprice/Library/Application Support/BoldstoneReview/publisher-snapshots/acanthus-native-availability-20261025.sqlite3')
snapshot.parent.mkdir(parents=True,exist_ok=True)
live=Path('/Users/tprice/Library/Application Support/BoldstoneReview/reviews.sqlite3')
if not snapshot.exists():
    src=sqlite3.connect('file:'+quote(str(live))+'?mode=ro',uri=True)
    dest=sqlite3.connect(snapshot);src.backup(dest);src.close();dest.close()
dest=sqlite3.connect('file:'+quote(str(snapshot))+'?mode=ro',uri=True)
dest.row_factory=sqlite3.Row
cutoff=dest.execute('SELECT MAX(id) FROM events').fetchone()[0]
jobs=[dict(r) for r in dest.execute("SELECT * FROM deletion_jobs WHERE state='deleted'") if r['file_id'] in targets]
assert len(jobs)==5
batches={r['id']:dict(r) for r in dest.execute('SELECT * FROM deletion_batches')}
gallery=(B/p['current_published_gallery_projection']['path']).parent/'complete-image-platform-register.sqlite'
c=sqlite3.connect('file:'+quote(str(gallery))+'?mode=ro',uri=True)
rows=[]
for j in jobs:
    payload=json.loads(j['payload']);result=json.loads(j['result']);fid=j['file_id'];a=assets[fid]
    assert result['state']=='deleted' and result['verified_absent'] and result['delete_response_confirmed']
    assert result['confirmed_file_id']==fid and payload['file']['id']==fid
    assert payload['binding']['bytes']==a['bytes'] and payload['binding']['content_hash']==a['source_content_hash']
    batch=batches[payload['batch_id']];bp=json.loads(batch['payload']);br=json.loads(batch['result'])
    assert batch['state']=='deleted' and {'id':fid,'revision':payload['file']['revision']} in br['confirmed_files']
    assert j['id'] in bp['operation_ids'] and bp['files']==br['confirmed_files']
    events=[{'id':r['id'],'at':r['at'],'kind':r['kind'],
        'before_sha256':hashlib.sha256(r['before_json'].encode()).hexdigest() if r['before_json'] else None,
        'after_sha256':hashlib.sha256(r['after_json'].encode()).hexdigest()}
        for r in dest.execute("SELECT * FROM events WHERE kind='deletion' AND item_id=? ORDER BY id",(fid,))]
    assert len(events)>=2
    associations=[{'product_id':r[0],'association_rows':r[1]} for r in c.execute('SELECT product_id,COUNT(*) FROM associations WHERE file_id=? GROUP BY product_id',(fid,))]
    selected=[o['product_id'] for o in g['options'] if o.get('file_id')==fid]
    context=[o['product_id'] for o in g['options'] if o.get('context_file_id')==fid]
    folder_options=[o['product_id'] for o in g['options'] if o.get('folder_id')==a['folder_id'] and o['product_id'] in g['active_option_ids']]
    rows.append({'file_id':fid,'status':'OWNER_CONFIRMED_DELETED_NATIVE_ABSENCE_VERIFIED',
        'name':a['name'],'historical_path':a['path'],'historical_image_url':a['image_url'],
        'folder_id':a['folder_id'],'folder_url':a['folder_url'],
        'revision_at_deletion':payload['file']['revision'],'bytes_at_deletion':payload['file']['bytes'],
        'content_hash_at_deletion':payload['file']['content_hash'],
        'operation_id':j['id'],'batch_id':payload['batch_id'],'reason':payload['reason'],
        'user_confirmation_utc':result['confirmation_at'],'deletion_readback_utc':result['checked_utc'],
        'independent_native_readback':independent[fid],
        'root_connector_lookup':'Exact-ID NOT_FOUND; both actual containing folders and complete direct child lists verified separately.',
        'audit_events':events,'source_master_example_option_ids':selected,
        'source_master_context_option_ids':context,'retained_association_impacts':associations,
        'same_folder_option_ids':folder_options,
        'replacement_primary_selected':False,'historical_source_records_retained':True})
c.close();dest.close()
selected_options=sorted({oid for r in rows for oid in r['source_master_example_option_ids']})
assert selected_options==['BSI-C02D6DF365D3']
folder_options=sorted({oid for r in rows for oid in r['same_folder_option_ids']})
assert folder_options==['BSI-9C7406B46836','BSI-C02D6DF365D3']
surviving_example=next(o for o in g['options'] if o['product_id']=='BSI-9C7406B46836')
assert surviving_example['file_id'] in present
counts={'active_options_unchanged':188,'confirmed_deleted_native_files':5,
    'affected_source_master_examples':1,'affected_option_folders':2,'baseline_current_wall_files':6360,
    'effective_wall_files_after_this_overlay':6355,'baseline_wall_objects_including_root':6802,
    'effective_wall_objects_after_this_overlay':6797,'folders_unchanged_by_these_operations':442,
    'global_new_root_inventory_performed':False}
overlay={'schema':'boldstone.native-availability/v1','status':'SEALED_FIXED_CUTOFF_NATIVE_AVAILABILITY',
    'recorded_utc':datetime.now(timezone.utc).isoformat(),'review_event_cutoff':cutoff,
    'baseline_pointer_sha256':sha(pfile),'baseline_register_sha256':p['register_sha256'],
    'baseline_asset_map':p['current_asset_reference_map'],'baseline_native_map':p['current_native_reference_map'],
    'gallery_database':str(gallery),'gallery_database_sha256':sha(gallery),
    'review_snapshot':{'path':str(snapshot),'sha256':sha(snapshot)},
    'rows':sorted(rows,key=lambda r:r['file_id']),'affected_example_option_ids':selected_options,
    'affected_folder_option_ids':folder_options,
    'surviving_master_example':{k:surviving_example[k] for k in ['product_id','name','file_id','folder_id','image_url','folder_url']},
    'remaining_verified_files':inspection['remaining_files'],'verified_folder_listings':inspection['folder_listings'],
    'counts':counts,'scope':'Exact five owner-confirmed native deletions. Prior inventories are retained snapshots; effective counts subtract only these five. No replacement primary, review-choice import, sculpture identity change or physical verification.',
    'native_mutations_by_this_phase':0,'active_review_db_writes':0,
    'source_evidence':{str(f):sha(f) for f in [H/'native-inspection.json',*collaborator_files]}}
dump(H/'availability-overlay.json',overlay)
packet={'status':'READY_FIXED_CUTOFF_WORKBOOK_AVAILABILITY_ANNOTATIONS',
    'overlay_path':str(H/'availability-overlay.json'),'overlay_sha256':sha(H/'availability-overlay.json'),
    'register_path':str(B/p['register']),'register_sha256':p['register_sha256'],
    'source_workbook':str(B/p['preferred_review_workbook']),
    'source_workbook_sha256':p['current_comprehensive_workbook']['sha256'],
    'output_workbook':str(B/'outputs/01a13fe6-495b-7253-b923-31823b4cbca8/all-source-register-2026-10-25/Boldstone_Wall_Sculptures_Unified_2026-10-25_v3.xlsx'),
    'review_event_cutoff':cutoff,'deleted_file_ids':sorted(targets),'affected_example_option_ids':selected_options,
    'affected_folder_option_ids':folder_options,
    'instructions':['New file only; retain all22 existing sheets, all413 primary rows and all raw source/specification/identity values.',
        'Add Native Availability with all five file IDs/revisions/deletion status, actual folder IDs/links, source receipts and cutoff.',
        'Annotate affected primary rows as historical source image deleted; current master primary not selected. No alternate photo approval inferred.',
        'Flower 001 is the only deleted master example. Acanthus and Moon White master example002 survives; qualify its three deleted gallery files without replacing or marking002 deleted.005 is also still present.',
        'Keep historical source file IDs and URL text. Replace the current clickable action for the deleted Flower master example with its verified containing folder or app review.',
        'Preserve raw source sheets as historical captures; label availability counts as baseline adjusted for these five only.',
        'No canonical, app source, review database, native or platform write. Further deletions are outside this fixed cutoff.']}
assert sha(packet['source_workbook'])==packet['source_workbook_sha256']
dump(H/'workbook-cutoff-packet.json',packet)
print(json.dumps({'status':overlay['status'],'event_cutoff':cutoff,'overlay_sha256':sha(H/'availability-overlay.json'),
    'packet_sha256':sha(H/'workbook-cutoff-packet.json'),'counts':counts},ensure_ascii=False,indent=2))
