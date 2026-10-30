from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone
import json, hashlib, csv, io, html, unicodedata

base=Path("/Users/tprice/Documents/boldstone/reports/dropbox-mixed-workshop-overview-relocation-2026-10-23")
review=Path('/Users/tprice/Documents/boldstone/reports/dropbox-structure-technical-review-20261023T213001Z')
load=lambda p:json.loads(p.read_text())
now=datetime.now(timezone.utc).isoformat()
def write(name,obj):
    with (base/name).open('x') as f: json.dump(obj,f,indent=2); f.write('\n')
def canon(path):
    if path.startswith('ns:'): path='/'+path.split('//',1)[1]
    return unicodedata.normalize('NFC',path).lower()
def human(path):
    return '/'+path.split('//',1)[1] if path.startswith('ns:') else path
def home(path):
    return 'https://www.dropbox.com/home'+'/'.join(quote(x,safe='') for x in human(path).split('/'))
def parent(path): return canon(path).rsplit('/',1)[0]
def totals(entries):
    return dict(files=sum(x['object_type']=='file' for x in entries),folders=sum(x['object_type']=='folder' for x in entries),bytes=sum(x.get('file',{}).get('size',0) for x in entries))
before=load(base/'before-scoped-listings.json'); after=load(base/'after-scoped-listings.json')
bm=load(base/'before-folder-metadata.json'); am=load(base/'after-file-and-folder-metadata.json')
approval=load(base/'approved-action.json')
proposal=load(review/'proposed-workshop-overview-move.json')
old=approval['approved_action']['source_path']; new=approval['approved_action']['destination_path']; sourceid=approval['approved_action']['source_id']
assert hashlib.sha256((review/'proposed-workshop-overview-move.json').read_bytes()).hexdigest()==approval['proposal_sha256']
assert hashlib.sha256((review/'review-seal.json').read_bytes()).hexdigest()=='358aca22a18686c3b83bd4416278d66a00667baad4ca2d0264e4b58bcec13c64'
for side in [before,after]:
    for data in side.values():
        assert data['complete'] and data['pages'][-1]['has_more']==False
        assert len(data['entries'])==sum(len(p['entries']) for p in data['pages'])
b={x['file_id']:x for k in ['deco','workshop'] for x in before[k]['entries']}
a={x['file_id']:x for k in ['deco','workshop'] for x in after[k]['entries']}
assert set(b)==set(a) and len(a)==858
expected={x['file_id'] for x in proposal['files']}
assert len(expected)==3
assert {x['file_id'] for x in before['source']['entries']}==expected=={x['file_id'] for x in after['source']['entries']}
def parent_map(entries,meta):
    out={canon(meta[k]['folder']['path_display']):meta[k]['folder']['id'] for k in ['deco','workshop']}
    out.update({canon(x['path']):x['file_id'] for x in entries.values() if x['object_type']=='folder'})
    return out
bp=parent_map(b,bm); ap=parent_map(a,am)
objects=[]; changed_files=[]; changed_folders=[]; file_parent_changes=[]; folder_parent_changes=[]; file_server_changes=[]; folder_server_changes=[]
for ident,x in b.items():
    y=a[ident]
    assert x['object_type']==y['object_type']
    isfile=x['object_type']=='file'
    assert (x.get('file',{}).get('size',0)==y.get('file',{}).get('size',0))
    assert x.get('client_modified')==y.get('client_modified')
    if ident==sourceid:
        assert x['name']==old.rsplit('/',1)[1] and y['name']==new.rsplit('/',1)[1]
    else: assert x['name']==y['name']
    changed=canon(x['path'])!=canon(y['path'])
    if changed:
        (changed_files if isfile else changed_folders).append(ident)
        if isfile:
            assert ident in expected and parent(x['path'])==canon(old) and parent(y['path'])==canon(new)
        else: assert ident==sourceid and canon(x['path'])==canon(old) and canon(y['path'])==canon(new)
    oldparent=bp[parent(x['path'])]; currentparent=ap[parent(y['path'])]
    if oldparent!=currentparent: (file_parent_changes if isfile else folder_parent_changes).append(ident)
    if x.get('modified_time')!=y.get('modified_time'):
        (file_server_changes if isfile else folder_server_changes).append(ident)
        assert ident in expected or ident==sourceid
    objects.append(dict(file_id=ident,object_type=x['object_type'],old_name=x['name'],current_name=y['name'],old_path=x['path'],current_path=y['path'],old_parent_id=oldparent,current_parent_id=currentparent,size=y.get('file',{}).get('size',0),old_client_modified=x.get('client_modified'),current_client_modified=y.get('client_modified'),old_server_modified=x.get('modified_time'),current_server_modified=y.get('modified_time'),current_native_url=home(human(y['path']).rsplit('/',1)[0])+'?preview='+quote(y['name'],safe='') if isfile else home(y['path'])))
assert set(changed_files)==expected and changed_folders==[sourceid]
assert not file_parent_changes and folder_parent_changes==[sourceid]
assert set(file_server_changes)==expected
assert not any(canon(x['path'])==canon(old) for x in a.values())
assert am['source']['folder']['id']==sourceid and am['source']['folder']['path_display']==new and am['source']['folder']['folder_size']==221916
assert load(base/'old-source-path-not-found.json')['isError']
assert '[NOT_FOUND]' in json.dumps(load(base/'old-source-path-not-found.json'))
assert totals(before['deco']['entries'])==dict(files=632,folders=19,bytes=5313364905)
assert totals(after['deco']['entries'])==dict(files=629,folders=18,bytes=5313142989)
assert totals(before['workshop']['entries'])==dict(files=201,folders=6,bytes=1644947403)
assert totals(after['workshop']['entries'])==dict(files=204,folders=7,bytes=1645169319)
assert sum(x.get('file',{}).get('size',0) for x in b.values())==sum(x.get('file',{}).get('size',0) for x in a.values())==6958312308
reviewed={x['file_id']:x for x in load(review/'technical-original-download-receipts.json') if x['file_id'] in expected}
hashes={x['id']:x for x in load(base/'after-content-hashes.json')['entries']}
assert set(hashes)==set(reviewed)==expected
verified=[]
for ident,r in reviewed.items():
    data=Path(r['local_path']).read_bytes()
    sha=hashlib.sha256(data).hexdigest()
    dropbox=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()
    assert len(data)==r['size']==hashes[ident]['size']==a[ident]['file']['size']
    assert sha==r['sha256'] and dropbox==r['content_hash']==r['verified_content_hash']==hashes[ident]['content_hash']
    assert canon(hashes[ident]['path_display'])==canon(a[ident]['path'])
    m=am[ident]['file']
    assert m['id']==ident and m['name']==a[ident]['name'] and m['size']==len(data) and canon(m['path_display'])==canon(a[ident]['path']) and m['client_modified']==b[ident]['client_modified']
    verified.append(dict(file_id=ident,name=r['name'],size=len(data),local_path=r['local_path'],sha256=sha,dropbox_content_hash=dropbox,current_path=m['path_display'],folder_id=sourceid,folder_url=home(new),image_url=home(new)+'?preview='+quote(r['name'],safe=''),status='MATCH_VERIFIED'))
verified.sort(key=lambda r:r['name'])
validation=dict(schema='boldstone.dropbox-workshop-relocation-validation.v1',status='COMPLETE_VERIFIED',verified_utc=now,folder_moves=1,folder_renames=1,new_folders=0,deleted_folders=0,new_images=0,deleted_images=0,before={k:totals(before[k]['entries']) for k in ['deco','workshop']},after={k:totals(after[k]['entries']) for k in ['deco','workshop']},scoped_descendant_ids_preserved=858,scoped_ids_including_two_roots_preserved=860,files_preserved=833,total_file_bytes_preserved=6958312308,affected_images=3,affected_bytes=221916,file_path_changes=3,folder_path_changes=1,actual_file_parent_changes=0,actual_folder_parent_changes=1,original_file_names_sizes_client_timestamps_preserved=True,unrelated_file_server_timestamps_unchanged=True,file_server_timestamp_changes=3,folder_server_timestamp_changes=len(folder_server_changes),affected_original_content_hashes_verified=3,all_833_files_rehashed=False,unaffected_files_checked_by_complete_metadata_comparison=830,old_path_not_found=True,other_folder_structure_preserved=True,shared_master_writes=0,new_dropbox_notes_indexes_shortcuts_or_copies=0)
write('original-content-verification.json',verified)
write('validation.json',validation)
links=[dict(file_id=r['file_id'],name=r['name'],size=r['size'],folder_id=sourceid,folder_path=new,folder_url=r['folder_url'],image_url=r['image_url']) for r in verified]
write('current-image-links.json',links)
with (base/'terminal-current-image-links.tsv').open('x',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(links[0]),delimiter='\t'); w.writeheader();w.writerows(links)
with (base/'current-image-and-folder-links.html').open('x') as f:
    f.write('<!doctype html><meta charset="utf-8"><title>Workshop overview relocation</title><h1>Verified workshop folder</h1><p><a href="'+html.escape(home(new),quote=True)+'">'+html.escape(new)+'</a></p><ul>')
    for r in links:f.write('<li><a href="'+html.escape(r['image_url'],quote=True)+'">'+html.escape(r['name'])+'</a> - '+str(r['size'])+' bytes</li>')
    f.write('</ul><p>Three originals verified. Filenames and file IDs preserved.</p>')
rootid='01a144ab-1a7c-7223-a403-73a4d53d70ff'
overlay=dict(schema='boldstone.dropbox-current-reference-overlay.v1',status='COMPLETE_VERIFIED',recorded_utc=now,source_scope='BOLDSTONE MASTER only',owner_authorization=approval['owner_approval'],preserved_scope_roots=[dict(file_id=bm[k]['folder']['id'],name=bm[k]['folder']['name'],path=bm[k]['folder']['path_display'],before=totals(before[k]['entries']),after=totals(after[k]['entries'])) for k in ['deco','workshop']],prefix_maps=[dict(file_id=sourceid,old_name=old.rsplit('/',1)[1],current_name=new.rsplit('/',1)[1],old_path=old,current_path=new,old_parent_id=bm['deco']['folder']['id'],current_parent_id=bm['workshop']['folder']['id'],direct_file_count=3,descendant_file_count=3,status='success',current_native_url=home(new))],specific_file_maps=[],specific_file_maps_override_prefix_maps=True,prefix_map_application='Use current same-ID native objects as authority. Apply this single folder parent and name change and descendant path refresh. Each image retains its original folder ID. This replaces the prior unapproved workshop-overview proposal only.',created_folders=[],deleted_folders=[],deleted_files=[],objects=objects,summary=validation,verification=validation,catalogue_projection=['Refresh navigation paths and native image/folder links by stable ID for this completed move only.','Folder parent changes from Deco Palm and Spiral to the existing Workshop and Moulding root; image parent IDs and names stay unchanged.','Existing photographs are workshop context. Do not infer new designs, finishes, physical specifications, stock, primary-image assignments or missing-context closure.','Keep the global owner hold on missing In Situ/display context photographs unchanged.','Keep both pending Egyptian Palm and Raked Spiral identification questions pending.','Root remains sole shared catalogue/master writer.'],current_folders=[dict(folder_id=sourceid,images=3,folder_path=new,folder_url=home(new),sample_image_url=links[0]['image_url'])],receipts=str(base),review_receipts=str(review),review_proposal_sha256=approval['proposal_sha256'],review_seal_sha256='358aca22a18686c3b83bd4416278d66a00667baad4ca2d0264e4b58bcec13c64',rollback=dict(ordered_steps=[dict(action='move',source_id=sourceid,destination_path=old,autorename=False)],note='Move the same folder back to its former Deco Palm and Spiral path, restoring its original name. No individual files need renaming or copying.'),master_write_owner=rootid,master_writes_by_this_lane=0)
write('current-reference-overlay.json',overlay)
write('receipt.json',dict(schema='boldstone.dropbox-native-change-receipt.v1',status='COMPLETE_VERIFIED',recorded_utc=now,action='move_and_rename_same_folder',source_id=sourceid,old_path=old,current_path=new,verified_images=3,verified_bytes=221916,overlay='current-reference-overlay.json',validation='validation.json',shared_master_status='HANDOFF_PENDING_NOT_WRITTEN_BY_THIS_LANE',claim_status='ACTIVE_UNTIL_HANDOFF_DELIVERED'))
sealed=[]
for p in sorted(base.iterdir()):
    if p.is_file(): sealed.append(dict(path=str(p),size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
review_receipts=[]
for n in ['proposed-workshop-overview-move.json','review-seal.json','technical-original-download-receipts.json','technical-folder-metadata.json','technical-review-decisions.json']:
    p=review/n;review_receipts.append(dict(path=str(p),size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
seal=dict(schema='boldstone.dropbox-native-execution-seal.v1',status='SEALED_COMPLETE_VERIFIED',created_utc=now,receipts=sealed,review_receipts=review_receipts,verified_originals=verified,excluded_future_files=['handoff-and-release.json'],source_proposal_sha256=approval['proposal_sha256'])
write('execution-seal.json',seal)
print(json.dumps(validation,indent=2))
print('OVERLAY_SHA256',hashlib.sha256((base/'current-reference-overlay.json').read_bytes()).hexdigest())
print('SEAL_SHA256',hashlib.sha256((base/'execution-seal.json').read_bytes()).hexdigest())
print('SEALED_RECEIPTS',len(sealed),'REVIEW_RECEIPTS',len(review_receipts))
print('FOLDER',home(new))
for i,r in enumerate(links,1):print('IMAGE',i,r['image_url'])

