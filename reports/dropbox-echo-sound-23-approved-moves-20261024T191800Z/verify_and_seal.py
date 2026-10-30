import csv
import hashlib
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

P=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Echo Sound'
def read(path):return json.loads(Path(path).read_text())
def write(name,data):(P/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fq(path):return path.split('/',1)[1] if path.startswith('ns:') else path
def home(path):return 'https://www.dropbox.com/home'+quote(path,safe='/')
def hashes(data):return hashlib.sha256(data).hexdigest(),hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()

before=read(P/'fresh-native-before-and-approved-proposal.json')
after=read(P/'fresh-native-after-and-metadata.json')
proposal=before['proposal'];moves={r['file_id']:r for r in proposal['moves']}
terminal=read(P/'move-status-2.json')
assert terminal['status']=='completed' and terminal['result_type']=='move'
results=terminal['move_result']['entries'];assert len(results)==23
for result in results:
    move=proposal['moves'][result['entry_index']]
    assert result['entry_status']=='success'
    obj=result['object'];assert obj['file_id']==move['file_id']
    assert obj.get('path_display')==move['destination_path'] or fq(obj['path'])==move['destination_path']
assert not before['listing']['has_more'] and not after['listing']['has_more']
b={r['file_id']:r for r in before['listing']['entries']}
a={r['file_id']:r for r in after['listing']['entries']}
assert set(b)==set(a) and len(a)==189
folders={k:v for k,v in a.items() if v['object_type']=='folder'}
files={k:v for k,v in a.items() if v['object_type']=='file'}
assert len(folders)==9 and len(files)==180
root=after['metadata'][-1]['folder'];root_id=root['id']
assert root['name']=='Echo Sound' and root['path_display']==SCOPE
oldfolders={fq(x['path']):x['file_id'] for x in b.values() if x['object_type']=='folder'}
newfolders={fq(x['path']):x['file_id'] for x in folders.values()}
oldfolders[SCOPE]=newfolders[SCOPE]=root_id
for fid,record in a.items():
    old=b[fid]
    assert record['name']==old['name'] and record['object_type']==old['object_type']
    assert record.get('client_modified')==old.get('client_modified')
    assert fq(record['path']).startswith(SCOPE+'/')
    if record['object_type']=='file':
        assert record['file']==old['file']
        if fid in moves:assert fq(record['path'])==moves[fid]['destination_path']
        else:assert record==old
    else:assert record['path']==old['path']
changed={fid for fid in a if a[fid]['path']!=b[fid]['path']}
assert changed==set(moves)
counts=Counter(fq(r['path']).rsplit('/',1)[0] for r in files.values())
assert counts[SCOPE+'/Echo Sound 1 and Echo Sound 2 White']==93
assert counts[SCOPE+'/Echo Sound 1 and Echo Sound 2 White In Situ']==25
assert sum(x['file'].get('size',0) for x in files.values())==1092139502

pre={x['file_id']:x for x in read(P/'all-180-original-prewrite-hashes.json')}
fresh={x['id']:x for x in read(P/'twenty-three-fresh-postmove-originals.json')}
hashmeta={x['id']:x for x in read(P/'fresh-postmove-native-hash-metadata.json')}
assert set(fresh)==set(moves) and all('sha256' in x for x in fresh.values())
assert set(pre)==set(hashmeta)==set(files)
verified=[]
for fid,native in sorted(files.items(),key=lambda x:x[1]['path']):
    reference=fresh[fid] if fid in fresh else pre[fid]
    data=Path(reference['local_path']).read_bytes();sh,dh=hashes(data)
    assert len(data)==pre[fid]['size']==hashmeta[fid]['size']==native['file']['size']
    assert sh==pre[fid]['sha256'] and dh==pre[fid]['dropbox_content_hash']==hashmeta[fid]['content_hash']
    assert hashmeta[fid]['name']==native['name'] and hashmeta[fid]['path']==native['path']
    parent=fq(native['path']).rsplit('/',1)[0];parent_id=newfolders[parent]
    verified.append({'file_id':fid,'name':native['name'],'size':len(data),'sha256':sh,'dropbox_content_hash':dh,'local_path':reference['local_path'],
        'verification_method':'FRESH_POSTMOVE_HTTP_ORIGINAL_DOWNLOAD' if fid in fresh else 'PRIOR_ORIGINAL_ACTUAL_BYTES_REHASHED_AGAINST_FRESH_NATIVE_HASH',
        'folder_id':parent_id,'folder_path':parent,'folder_url':home(parent),'image_url':home(parent)+'?preview='+quote(native['name'],safe=''),
        'path':fq(native['path']),'moved_this_batch':fid in moves})
write('verified-current-180-originals.json',verified)
links=[{k:r[k] for k in ['file_id','name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash','moved_this_batch']} for r in verified]
write('all-current-echo-sound-image-folder-links.json',links)
with (P/'all-current-echo-sound-image-folder-links.tsv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(links[0]),delimiter='\t');writer.writeheader();writer.writerows(links)

protected=read(P/'protected-catalogue-references-before.json')
pointer=read(ROOT/'sculpture-catalogue/current-master.json')
register_path=ROOT/'sculpture-catalogue'/pointer['register'];register=read(register_path)
options={o['product_id']:o for o in register['options']}
for o in protected['options']:
    assert options[o['product_id']]==o
    for prefix in ['', 'context_']:
        r=next(x for x in verified if x['file_id']==o[prefix+'file_id'])
        assert o[prefix+'folder_id']==r['folder_id'] and o[prefix+'folder_url']==r['folder_url'] and o[prefix+'image_url']==r['image_url']
assert all(o[k] not in moves for o in protected['options'] for k in ['file_id','context_file_id'])
write('protected-selected-references-after.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'register_path':str(register_path),'register_sha256':sha(register_path),'full_echo_option_records_unchanged':4,'selected_current_image_and_folder_pairs_all_verified':True,'options':protected['options']})

pre_meta={x.get('file',x.get('folder',{})).get('id'):x for x in before['metadata']}
post_meta={x.get('file',x.get('folder',{})).get('id'):x for x in after['metadata']}
specific=[]
for fid in sorted(moves):
    m=moves[fid];old=pre_meta[fid]['file'];new=post_meta[fid]['file']
    assert old['name']==new['name']==m['original_name'] and old['size']==new['size']==m['size']
    assert old['client_modified']==new['client_modified']
    assert new['path_display']==m['destination_path']
    specific.append({'file_id':fid,'old_path':old['path_display'],'new_path':new['path_display'],'old_parent_id':m['source_folder_id'],'new_parent_id':m['destination_folder_id'],
        'old_rev':old['rev'],'new_rev':new['rev'],'sha256':pre[fid]['sha256'],'dropbox_content_hash':pre[fid]['dropbox_content_hash'],'size':old['size']})
write('exact-23-old-new-file-parent-mappings.json',specific)
objects=[]
byid={x['file_id']:x for x in verified}
for fid,r in sorted(a.items(),key=lambda x:x[1]['path']):
    old=b[fid];oldpath=fq(old['path']);newpath=fq(r['path']);kind=r['object_type']
    parent=oldfolders[oldpath.rsplit('/',1)[0]];newparent=newfolders[newpath.rsplit('/',1)[0]]
    obj={'file_id':fid,'object_type':kind,'old_name':old['name'],'current_name':r['name'],'old_path':oldpath,'current_path':newpath,'current_ns_path':r['path'],
        'old_parent_id':parent,'current_parent_id':newparent,'size':r.get('file',{}).get('size',0),'old_client_modified':old.get('client_modified'),'current_client_modified':r.get('client_modified'),
        'old_server_modified':old.get('modified_time'),'current_server_modified':r.get('modified_time'),'current_native_url':byid[fid]['image_url'] if kind=='file' else home(newpath),'status':'success'}
    if kind=='file':obj.update(sha256=byid[fid]['sha256'],dropbox_content_hash=byid[fid]['dropbox_content_hash'],pre_move_sha256_identical=True,original_verification_method=byid[fid]['verification_method'])
    objects.append(obj)
write('complete-current-native-object-map.json',{'preserved_scope_roots':[root],'objects':objects})
validation={'schema':'boldstone.echo23.native-filing-verification.v1','status':'COMPLETE_VERIFIED','verified_utc':datetime.now(timezone.utc).isoformat(),
    'owner_approved_moves_completed':23,'forward_White_to_InSitu':17,'reverse_InSitu_to_White':6,'family_originals':180,'family_bytes':1092139502,'family_folders':9,
    'White_before':104,'White_after':93,'InSitu_before':14,'InSitu_after':25,
    'all_180_original_ID_name_format_size_client_time_and_bytes_preserved':True,
    'only_23_approved_file_paths_and_parent_IDs_changed':True,
    'fresh_postmove_original_downloads':23,'unchanged_157_actual_originals_rehashed_against_fresh_native_hashes':157,
    'selected_four_options_primary_context_ID_path_parent_role_unchanged':True,
    'created_folders':0,'renamed_folders':0,'deleted_files':0,'deleted_folders':0,'canonical_writes_by_this_lane':0,
    'dark_finish_001_101_102_remain_unmoved':True,'Chiswick_015_and_Bone_no_mutations_by_this_lane':True}
write('validation.json',validation)
overlay={'schema':'boldstone.current-native-reference-overlay.v1','status':'COMPLETE_VERIFIED','recorded_utc':datetime.now(timezone.utc).isoformat(),'source_scope':SCOPE,
    'owner_authorization':'Exact owner Do it approval; response_item source pointer, clock and line hash in owner-approval-source-evidence.json',
    'preserved_scope_roots':[root],'prefix_maps':[],'specific_file_maps':specific,'specific_file_maps_override_prefix_maps':True,
    'created_folders':[],'deleted_files':[],'deleted_folders':[],'objects':objects,
    'summary':{'files':180,'folders':9,'bytes':1092139502,'moved_file_paths':23,'moved_actual_parents':23,'created_folders':0,'folder_renames':0,'all_original_bytes_preserved':True},
    'verification':validation,'current_folders':[{'folder_id':fid,'folder_path':fq(f['path']),'folder_url':home(fq(f['path'])),'files':counts[fq(f['path'])]} for fid,f in sorted(folders.items(),key=lambda x:x[1]['path'])],
    'catalogue_projection':{'selected_individual_primary_and_context_unchanged':True,'current_moved_ID_occurrences':proposal['current_register_exact_moved_file_id_occurrences'],
        'no_captured_source_BOM_role_spec_or_commercial_changes_authorized':True,'current_native_objects_for_navigation_only':True},
    'review_proposal_sha256':before['proposal_sha256'],'master_writes_by_this_lane':0}
write('current-reference-overlay.json',overlay)

oldpath=ROOT/'reports/dropbox-wall-only-chiswick-echo-bone-review-20261024T183336Z/combined-thirty-three-family-current-image-folder-links.json'
cumulative=read(oldpath);prior_ids={x['file_id'] for x in cumulative}
assert set(files).issubset(prior_ids)
for i,r in enumerate(cumulative):
    if r['file_id'] in byid:
        v=byid[r['file_id']]
        cumulative[i]={'role':'source','family':'Echo Sound',**{k:v[k] for k in ['file_id','name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash']}}
assert len(cumulative)==len({x['file_id'] for x in cumulative})==1445
write('combined-thirty-three-family-current-image-folder-links.json',cumulative)
write('cumulative-link-accounting.json',{'prior_manifest':str(oldpath),'prior_manifest_sha256':sha(oldpath),'whole_source_families':33,'whole_source_originals':1437,'comparison_only_originals':8,'distinct_original_references':1445,'current_echo_links_refreshed':180,'freshness_note':'Only Echo Sound freshly verified here; earlier family captures retain dated receipts and approved move overlays. This is not a fresh whole-library inventory.','not_a_physical_stock_or_unique_design_count':True})

e=html.escape
style='<meta charset="utf-8"><style>body{font:16px system-ui;max-width:1400px;margin:30px auto;padding:0 20px;line-height:1.5}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccc;text-align:left}a{overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}article{border:1px solid #ccc;padding:12px}img{width:100%;height:260px;object-fit:contain;background:#eee}</style>'
page=[style,'<title>Echo Sound — all 180 current image and folder links</title><h1>Echo Sound — 180 preserved originals</h1><p>Completed: 17 wider White photographs moved into In Situ; six close views moved back into White. Pair White: 93; pair In Situ: 25. No folder creation or renaming.</p><p><a href="moved-23-current-image-folder-links.html">View the 23 moved photographs and current folders</a></p><table><tr><th>Current containing folder</th><th>Original image</th><th>Moved this batch</th></tr>']
for r in verified:page.append('<tr><td><a href="'+e(r['folder_url'])+'">'+e(r['folder_path'].split('/')[-1])+'</a></td><td><a href="'+e(r['image_url'])+'">'+e(r['name'])+'</a></td><td>'+('Yes' if r['moved_this_batch'] else '')+'</td></tr>')
page.append('</table>');(P/'all-current-echo-sound-image-folder-links.html').write_text(''.join(page))
page=[style,'<title>Echo Sound — 23 completed moves</title><h1>23 Echo Sound moves completed and verified</h1><p>Original filenames and bytes preserved. Current image and containing-folder links below.</p><div class="grid">']
for move in proposal['moves']:
    fid=move['file_id'];r=byid[fid];local=Path(fresh[fid]['local_path']).relative_to(P)
    page.append('<article><a href="'+e(r['image_url'])+'"><img loading="lazy" src="'+quote(str(local),safe='/')+'"></a><p><strong>'+e(move['direction'])+' — '+e(move['short_name'])+'</strong></p><p><a href="'+e(r['image_url'])+'">Current image</a><br><a href="'+e(r['folder_url'])+'">Current containing folder</a></p><small>'+e(r['name'])+'</small></article>')
page.append('</div>');(P/'moved-23-current-image-folder-links.html').write_text(''.join(page))
write('catalogue-publication-followup.json',{'status':'NATIVE_COMPLETE_CANONICAL_IMPORT_PENDING_MAIN','native_overlay':'current-reference-overlay.json','native_overlay_sha256':sha(P/'current-reference-overlay.json'),'sole_canonical_writer_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','no_canonical_writes_by_this_lane':True})
text=['Echo Sound:23 owner-approved moves COMPLETE_VERIFIED.','White104->93;InSitu14->25;180 originals/1,092,139,502 bytes/9 folders preserved.','23 fresh postmove downloads+157 actual unchanged originals rehashed against fresh native hashes.','All current images and containing folders:']
for r in verified:
    if r['moved_this_batch']:text.extend([r['name'],r['image_url'],r['folder_url']])
(P/'terminal-final-counts-and-moved-image-links.txt').write_text('\n'.join(text)+'\n')
excluded={'execution-seal.json','batch-coordination.json','catalogue-publication-followup.json'}
receipt_paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded and 'verified-postmove-originals' not in x.relative_to(P).parts]
write('execution-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'NATIVE_EXECUTION_COMPLETE_VERIFIED','receipt_count':len(receipt_paths),'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(receipt_paths)],'large_originals_bound_by':'verified-current-180-originals.json and twenty-three-fresh-postmove-originals.json','excluded_mutable_followup':['batch-coordination.json','catalogue-publication-followup.json']})
print(json.dumps(validation,indent=2))
print('OVERLAY_SHA256',sha(P/'current-reference-overlay.json'))
print('EXECUTION_SEAL_SHA256',sha(P/'execution-seal.json'))
print('SEALED_RECEIPTS',len(receipt_paths))
