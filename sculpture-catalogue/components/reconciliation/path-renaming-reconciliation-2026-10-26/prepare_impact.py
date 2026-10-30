"""Read-only stable-ID impact plan; proposed paths are not published as current."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,sqlite3
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest_path=Path('/Users/tprice/BoldstoneMigration/path-renaming-20261026/manifest.json')
assert sha(manifest_path)=='22e87874738bc52126366ac348c801819f49ae729a65eb541e86fd2ea4d2b1ce'
m=read(manifest_path);p=read(B/'current-master.json');g=read(B/p['register'])
files=[f for group in m['groups'] for f in group['files']]
ids={f['id']:f for f in files}
assert len(files)==len(ids)==6205 and sum(f['changed'] for f in files)==4784
assert len({f['new_path'].casefold() for f in files})==len(files)
for group in m['groups']:
    assert [f['sequence'] for f in group['files']]==list(range(1,len(group['files'])+1))
    for f in group['files']:
        assert f['new_path']==str(Path(f['path']).parent/f['new_name'])
        assert Path(f['name']).suffix==Path(f['new_name']).suffix
        assert f['new_name'].rsplit('__',1)[-1]==str(f['sequence']).zfill(3)+Path(f['name']).suffix
        assert f['new_path'].startswith('/BOLDSTONE MASTER/')
        assert bool(f['parent_id']) and len(f['content_hash'])==64 and f['size']>=0
gallery=(B/p['current_published_gallery_projection']['path']).parent/'complete-image-platform-register.sqlite'
db=sqlite3.connect(gallery.resolve().as_uri()+'?mode=ro',uri=True)
try:
    old_ids={r[0] for r in db.execute('SELECT file_id FROM images')}
    table_counts={r[0]:db.execute('SELECT COUNT(*) FROM "'+r[0]+'"').fetchone()[0]
        for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
finally:db.close()
active=set(g['active_option_ids']);option_impacts=[]
for o in g['options']:
    if o['product_id'] not in active:continue
    refs=[]
    for role,key in [('individual','file_id'),('context','context_file_id')]:
        fid=o.get(key)
        if fid in ids:
            f=ids[fid];refs.append({'role':role,'file_id':fid,'parent_id':f['parent_id'],
                'filename_will_change':f['changed'],'old_path':f['path'],'proposed_path':f['new_path']})
    design=o.get('owner_confirmed_design_reference',{})
    if design.get('file_id') in ids:
        f=ids[design['file_id']];refs.append({'role':'owner-confirmed design reference','file_id':f['id'],
            'parent_id':f['parent_id'],'filename_will_change':f['changed'],'old_path':f['path'],'proposed_path':f['new_path']})
    if refs:option_impacts.append({'product_id':o['product_id'],'name':o['name'],'references':refs})
workshop=[f for f in files if f['new_path'].startswith('/BOLDSTONE MASTER/Products/Workshop and Moulding/')]
assert len(workshop)==196 and len({f['parent_id'] for f in workshop})==7
report={'status':'PREPARED_STABLE_ID_IMPACT_ONLY_NATIVE_EXECUTION_IN_PROGRESS','prepared_utc':datetime.now(timezone.utc).isoformat(),
    'manifest':str(manifest_path),'manifest_sha256':sha(manifest_path),'baseline_pointer_sha256':sha(B/'current-master.json'),
    'baseline_register':p['register'],'baseline_register_sha256':p['register_sha256'],
    'baseline_gallery':str(gallery),'baseline_gallery_sha256':sha(gallery),'source_gallery_table_counts':table_counts,
    'native_manifest_files':6205,'planned_renames':4784,'unchanged_names':1421,'containing_folders':387,
    'wall_images':6205-len(workshop),'retained_workshop_images':len(workshop),'retained_workshop_folders':7,
    'manifest_ids_in_existing_source_gallery':len(set(ids)&old_ids),
    'current_manifest_ids_not_in_retained_source_gallery':sorted(set(ids)-old_ids),
    'active_option_records_with_manifest_references':len(option_impacts),
    'selected_reference_links_requiring_filename_refresh':sum(r['filename_will_change'] for o in option_impacts for r in o['references']),
    'option_reference_impacts':option_impacts,
    'workshop_references_requiring_explicit_gallery_refresh':[{'file_id':f['id'],'folder_id':f['parent_id'],
        'old_path':f['path'],'proposed_path':f['new_path'],'content_hash_before':f['content_hash'],
        'bytes_before':f['size']} for f in workshop if f['changed']],
    'publication_gates':['Full owning-session native readback after all async and synchronous operations terminate',
        'Stable file IDs, native parent IDs, content hashes, bytes and extensions match the before manifest',
        'Use observed final paths and revisions, never intermediate or merely planned targets',
        'Update current navigation and explicit outside-wall gallery references; retain source capture history',
        'Coordinate app source/readback restart or source-only review rebase if catalogue binding changes'],
    'canonical_register_workbook_gallery_pointer_or_control_writes':0,'native_calls_or_writes':0,
    'app_runtime_or_review_writes':0,'source_identity_physical_or_listing_decisions':0}
(H/'prepared-impact.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['option_reference_impacts','workshop_references_requiring_explicit_gallery_refresh','publication_gates','source_gallery_table_counts']},indent=2))
