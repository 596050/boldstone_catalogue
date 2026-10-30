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
PREVIOUS=ROOT/'reports/dropbox-wall-only-chiswick-echo-bone-review-20261024T183336Z'
FAMILY='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Bone Spiral'
SOURCE='id:cnqzTNngPVsAAAAAAA53DA'
DEST='id:cnqzTNngPVsAAAAAAA53Cw'
def read(path):return json.loads(Path(path).read_text())
def write(name,data):(P/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fq(path):return path.split('/',1)[1] if path.startswith('ns:') else path
def home(path):return 'https://www.dropbox.com/home'+quote(path,safe='/')

fresh=read(P/'fresh-native-listing-metadata-and-hashes.json')
closing=read(P/'fresh-closing-native-listing.json')
old=next(x['result'] for x in read(PREVIOUS/'fresh-complete-native-listings.json')['listings'] if x['name']=='Bone Spiral')
assert not fresh['listing']['has_more'] and not closing['listing']['has_more'] and not old['has_more']
identity=lambda x:{r['file_id']:r for r in x['entries']}
assert identity(fresh['listing'])==identity(closing['listing'])==identity(old)
entries=identity(closing['listing']);files={k:r for k,r in entries.items() if r['object_type']=='file'};folders={k:r for k,r in entries.items() if r['object_type']=='folder'}
assert len(files)==153 and len(folders)==5 and sum(r['file']['size'] for r in files.values())==491362397
assert folders[SOURCE]['name']=='Bone Spiral 2 White In Situ' and folders[DEST]['name']=='Bone Spiral 2 White'
metadata={x.get('file',x.get('folder',{})).get('id'):x for x in fresh['metadata']}
for fid in [SOURCE,DEST]:
    assert metadata[fid]['metadata_type']=='folder' and metadata[fid]['folder']['path_display']==fq(folders[fid]['path'])
root=fresh['metadata'][-1];assert root['metadata_type']=='folder' and root['folder']['path_display']==FAMILY
source=fq(folders[SOURCE]['path']);dest=fq(folders[DEST]['path'])
counts=Counter(fq(r['path']).rsplit('/',1)[0] for r in files.values());assert counts[source]==67 and counts[dest]==1
selected=read(P/'selected-38-originals-from-whole-family-review.json');assert len(selected)==38
hashes={r['id']:r for r in fresh['hash_metadata']}
actual={r['file_id']:r for r in read(P/'all-153-actual-original-hash-readback.json')}
assert set(actual)==set(hashes)==set(files)
for fid,r in actual.items():
    assert r['fresh_native_hash_match'] and not r['new_binary_download'] and r['dropbox_content_hash']==hashes[fid]['content_hash'] and r['size']==hashes[fid]['size']==files[fid]['file']['size']

pointerpath=ROOT/'sculpture-catalogue/current-master.json';pointer=read(pointerpath)
regpath=ROOT/'sculpture-catalogue'/pointer['register'];register=read(regpath)
options=[o for o in register['options'] if o.get('family')=='Bone Spiral'];assert len(options)==2
prior_options=[o for o in read(PREVIOUS/'protected-catalogue-references-before.json')['options'] if o.get('family')=='Bone Spiral']
assert options==prior_options
selected_ids={o[k] for o in options for k in ['file_id','context_file_id']}
assert not selected_ids.intersection(r['id'] for r in selected)
for o in options:
    for prefix in ['', 'context_']:
        n=files[o[prefix+'file_id']];parent=fq(n['path']).rsplit('/',1)[0]
        assert o[prefix+'folder_url']==home(parent) and o[prefix+'image_url']==home(parent)+'?preview='+quote(n['name'],safe='')
        assert o[prefix+'folder_id'] in folders
write('protected-selected-options-current.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'pointer_sha256':sha(pointerpath),'register_path':str(regpath),'register_sha256':sha(regpath),'options':options,'full_option_records_unchanged':True,'selected_primary_context_current_identity_and_urls_verified':True,'selected_file_ids_in_move_set':[],'current_asset_reference_map':pointer['current_asset_reference_map'],'current_native_reference_map':pointer['current_native_reference_map']})

def find_ids(obj,ids,path=''):
    found=[]
    if isinstance(obj,dict):
        for k,v in obj.items():found+=find_ids(v,ids,path+'/'+str(k))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):found+=find_ids(v,ids,path+'/'+str(i))
    elif isinstance(obj,str) and obj in ids:found.append({'json_pointer':path,'file_id':obj})
    return found

moves=[]
for r in selected:
    fid=r['id'];n=files[fid];m=metadata[fid]
    assert m['metadata_type']=='file' and m['file']['name']==n['name']==r['name']
    assert m['file']['size']==n['file']['size']==r['size']
    assert m['file']['path_display']==fq(n['path'])==source+'/'+r['name']
    target=dest+'/'+r['name'];assert not any(fq(x['path']).lower()==target.lower() for x in entries.values())
    moves.append({'file_id':fid,'original_name':r['name'],'short_name':r['name'].split('__')[-1],
        'source_folder_id':SOURCE,'source_folder_path':source,'source_folder_url':home(source),'source_image_url':home(source)+'?preview='+quote(r['name'],safe=''),
        'destination_folder_id':DEST,'destination_folder_path':dest,'destination_folder_url':home(dest),'destination_path':target,'expected_image_url':home(dest)+'?preview='+quote(r['name'],safe=''),
        'size':r['size'],'sha256':actual[fid]['sha256'],'dropbox_content_hash':actual[fid]['dropbox_content_hash'],
        'preview':'previews/'+fid.split(':')[1]+'.jpg','selected_primary_or_context':False,'destination_collision':False,
        'reason':'Close product/detail framing of the existing component 2; no wider installation setting shown.',
        'undo_destination_path':fq(n['path'])})
proposal={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'EXACT_PLAN_PREPARED_NOT_APPLIED_OWNER_CONFIRMATION_PENDING','scope':FAMILY,
    'operation':'move','folders_to_create':[],'native_writes':0,'canonical_writes':0,
    'reason':'File close product and detail photographs in the existing component product folder, retaining wider setting photographs under In Situ.',
    'preserve_component_number':2,'preserve_finish_label':'White','moves':moves,
    'expected_counts':{'Bone_Spiral_2_White_In_Situ_before':67,'Bone_Spiral_2_White_In_Situ_after':29,'Bone_Spiral_2_White_before':1,'Bone_Spiral_2_White_after':39,'family_originals_before':153,'family_originals_after':153,'family_folders_before':5,'family_folders_after':5,'family_bytes_before':491362397,'family_bytes_after':491362397},
    'current_register_exact_moved_file_id_occurrences':find_ids(register,{r['file_id'] for r in moves}),
    'all_original_filenames_formats_ids_bytes_and_selected_catalogue_photo_roles_preserved':True,
    'other_families_and_workshop_pair_arrangement_photographs_excluded':True,
    'separate_Bone_workshop_2_and_Chiswick_015_items_remain_unapplied':True,
    'Echo_23_already_complete_no_repeat_mutation':True,
    'requires_fresh_live_guards_and_overlap_check_after_later_exact_owner_approval':True,
    'undo_after_application':'Move the same 38 file IDs back to the recorded original In Situ folder, retaining original filenames.'}
write('exact-38-move-proposal.json',proposal)
with (P/'all-38-proposed-image-source-destination-links.tsv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['short_name','file_id','source_image_url','source_folder_url','destination_folder_url','expected_image_url'],delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(moves)
e=html.escape
parts=['<!doctype html><html><head><meta charset="utf-8"><title>Bone Spiral 2 — exact 38-photo filing proposal</title><style>body{font:16px system-ui;max-width:1350px;margin:30px auto;padding:0 20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px}article{border:1px solid #ccc;padding:12px}img{width:100%;height:260px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}td,th{border:1px solid #ccc;padding:9px}table{border-collapse:collapse}</style></head><body><h1>Bone Spiral 2: 38 close-view moves proposed</h1><p><strong>Not applied. Exact owner confirmation pending.</strong> Move the close product/detail photographs below into the existing component 2 White folder. The sculpture number, White finish label and original filenames stay unchanged. No folder creation.</p><table><tr><th>Existing folder</th><th>Before</th><th>Expected after</th></tr><tr><td><a href="'+e(home(source))+'">Bone Spiral 2 White In Situ</a></td><td>67</td><td>29</td></tr><tr><td><a href="'+e(home(dest))+'">Bone Spiral 2 White</a></td><td>1</td><td>39</td></tr></table><p>All153 family originals remain preserved, along with the selected catalogue primary/context photographs and the other three family folders. Workshop and pair/group filing are separate pending items.</p><div class="grid">']
for r in moves:parts.append('<article><a href="'+e(r['source_image_url'])+'"><img loading="lazy" src="'+e(r['preview'])+'"></a><p><strong>'+e(r['short_name'])+'</strong></p><p><a href="'+e(r['source_image_url'])+'">Current image in Dropbox</a><br><a href="'+e(r['source_folder_url'])+'">Current containing folder</a><br><a href="'+e(r['destination_folder_url'])+'">Proposed existing destination</a></p><small>'+e(r['original_name'])+'</small></article>')
parts.append('</div></body></html>');(P/'review-all-38-proposed-moves.html').write_text(''.join(parts))
validation={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_EXACT_PLAN_COMPLETE','family_originals':153,'family_folders':5,'family_bytes':491362397,'unchanged_native_descendant_objects':158,
    'actual_existing_originals_rehashed_against_fresh_native_hashes':153,'new_binary_downloads':0,'fresh_metadata_objects':44,'contact_boards_visually_reviewed':5,
    'exact_proposed_moves':38,'destination_collisions':0,'selected_catalogue_file_ids_in_move_set':0,'full_selected_option_records_unchanged':2,'native_writes':0,'canonical_writes':0,
    'proposal_sha256':sha(P/'exact-38-move-proposal.json'),'expected_counts':proposal['expected_counts'],'current_register_exact_moved_ID_occurrences':len(proposal['current_register_exact_moved_file_id_occurrences']),
    'prior_whole_family_review_seal_sha256':sha(PREVIOUS/'review-seal.json')}
write('validation.json',validation)
excluded={'plan-seal.json','coordination-followup.json'};paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded]
write('plan-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_EXACT_PROPOSAL_NO_MUTATIONS','receipt_count':len(paths),'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],'excluded_mutable_followup':['coordination-followup.json'],'actual_original_bytes_bound_by':'all-153-actual-original-hash-readback.json'})
print(json.dumps(validation,indent=2));print('PLAN_SEAL_SHA256',sha(P/'plan-seal.json'));print('REVIEW',P/'review-all-38-proposed-moves.html')
