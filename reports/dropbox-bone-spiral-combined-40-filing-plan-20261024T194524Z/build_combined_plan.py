import csv
import hashlib
import html
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote

P=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
PREVIOUS=ROOT/'reports/dropbox-bone-spiral-38-detail-filing-plan-20261024T193923Z'
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Bone Spiral'
def read(p):return json.loads(Path(p).read_text())
def write(n,d):(P/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fq(p):return p.split('/',1)[1] if p.startswith('ns:') else p
def home(p):return 'https://www.dropbox.com/home'+quote(p,safe='/')
def hashes(data):return hashlib.sha256(data).hexdigest(),hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()

oldseal=read(PREVIOUS/'plan-seal.json')
for r in oldseal['files']:
    f=PREVIOUS/r['path'];assert f.stat().st_size==r['size'] and sha(f)==r['sha256']
oldproposal=read(PREVIOUS/'exact-38-move-proposal.json')
assert sha(PREVIOUS/'exact-38-move-proposal.json')=='75dda359d42d62328e5d52f60e36cefc24cea2c13120335496417da987712348'
first=read(P/'fresh-workshop-native-listing-metadata-and-hashes.json')
last=read(P/'fresh-combined-close-view-guards-and-closing-listing.json')
prior=read(PREVIOUS/'fresh-closing-native-listing.json')['listing']
assert not first['listing']['has_more'] and not last['closing_listing']['has_more']
identity=lambda x:{r['file_id']:r for r in x['entries']}
entries=identity(last['closing_listing']);assert entries==identity(first['listing'])==identity(prior)
files={k:v for k,v in entries.items() if v['object_type']=='file'};folders={k:v for k,v in entries.items() if v['object_type']=='folder'}
assert len(files)==153 and len(folders)==5 and sum(v['file']['size'] for v in files.values())==491362397
root=first['metadata'][-1]['folder'];assert root['path_display']==SCOPE
source_id='id:cnqzTNngPVsAAAAAAA53DA';white_id='id:cnqzTNngPVsAAAAAAA53Cw'
source=fq(folders[source_id]['path']);white=fq(folders[white_id]['path']);workshop=SCOPE+'/Bone Spiral 2 White Workshop Views'
assert source==SCOPE+'/Bone Spiral 2 White In Situ'
assert white==SCOPE+'/Bone Spiral 2 White'
assert not any(fq(v['path']).lower()==workshop.lower() for v in entries.values())
counts=Counter(fq(v['path']).rsplit('/',1)[0] for v in files.values());assert counts[source]==67 and counts[white]==1
metadata={v.get('file',v.get('folder',{})).get('id'):v for v in first['metadata']+last['close_view_and_destination_metadata']}
assert metadata[white_id]['folder']['path_display']==white
hashmeta={r['id']:r for r in first['hash_metadata']+last['close_view_hash_metadata']}
workshop_rows=read(P/'two-workshop-originals-from-whole-family-review.json')
assert len(workshop_rows)==2
prior_rows={r['id']:r for r in read(PREVIOUS/'selected-38-originals-from-whole-family-review.json')}
allrows={**prior_rows,**{r['id']:r for r in workshop_rows}};assert len(allrows)==len(hashmeta)==40
verified=[]
for fid,r in allrows.items():
    data=Path(r['local_path']).read_bytes();sh,dh=hashes(data);n=hashmeta[fid]
    assert sh==r['sha256'] and dh==r['dropbox_content_hash']==n['content_hash'] and len(data)==r['size']==n['size']
    assert metadata[fid]['metadata_type']=='file' and metadata[fid]['file']['path_display']==fq(files[fid]['path'])==source+'/'+r['name']
    assert metadata[fid]['file']['name']==r['name'] and metadata[fid]['file']['size']==r['size']
    verified.append({'file_id':fid,'local_path':r['local_path'],'size':len(data),'sha256':sh,'dropbox_content_hash':dh,'fresh_native_content_hash_match':True,'new_binary_download':False})
write('all-40-actual-original-current-hash-readback.json',verified)

pointer_path=ROOT/'sculpture-catalogue/current-master.json';pointer=read(pointer_path);regpath=ROOT/'sculpture-catalogue'/pointer['register'];reg=read(regpath)
options=[o for o in reg['options'] if o.get('family')=='Bone Spiral'];assert options==read(PREVIOUS/'protected-selected-options-current.json')['options']
protected={o[k] for o in options for k in ['file_id','context_file_id']};assert not protected.intersection(allrows)
write('protected-selected-options-current.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'pointer_sha256':sha(pointer_path),'register_sha256':sha(regpath),'options':options,'full_selected_option_records_unchanged':2,'selected_file_ids_in_move_set':[],'current_asset_reference_map':pointer['current_asset_reference_map'],'current_native_reference_map':pointer['current_native_reference_map']})
workshop_moves=[]
for r in workshop_rows:
    target=workshop+'/'+r['name'];assert not any(fq(v['path']).lower()==target.lower() for v in entries.values())
    workshop_moves.append({'file_id':r['id'],'original_name':r['name'],'short_name':r['name'].split('__')[-1],
        'source_folder_id':source_id,'source_folder_path':source,'source_folder_url':home(source),'source_image_url':home(source)+'?preview='+quote(r['name'],safe=''),
        'destination_folder_id':None,'destination_folder_path':workshop,'destination_folder_url':home(workshop),'destination_path':target,'expected_image_url':home(workshop)+'?preview='+quote(r['name'],safe=''),
        'size':r['size'],'sha256':r['sha256'],'dropbox_content_hash':r['dropbox_content_hash'],'preview':'previews/'+r['id'].split(':')[1]+'.jpg',
        'selected_primary_or_context':False,'destination_collision':False,'reason':'The component 2 panel is shown lying on a cluttered workbench; classify as workshop reference.',
        'undo_destination_path':source+'/'+r['name']})
allmoves=[{**r,'filing_group':'Close product/detail views'} for r in oldproposal['moves']]+[{**r,'filing_group':'Workshop views'} for r in workshop_moves]
assert len(allmoves)==len({r['file_id'] for r in allmoves})==40
for r in allmoves:
    assert r['source_folder_id']==source_id and r['source_folder_path']==source
    assert not any(fq(v['path']).lower()==r['destination_path'].lower() for v in entries.values())
newfolder={'path':workshop,'proposed_folder_url':home(workshop),'parent_folder_id':root['id'],'parent_path':SCOPE,'exists_now':False,'expected_files_after':2}
proposal={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'COMBINED_40_MOVE_PLAN_PREPARED_NOT_APPLIED_OWNER_CONFIRMATION_PENDING','scope':SCOPE,
    'operation':'create one folder, then move 40 existing originals','folders_to_create':[newfolder],'moves':allmoves,
    'includes_previously_pending_38_photo_plan_once':{'path':str(PREVIOUS/'exact-38-move-proposal.json'),'sha256':sha(PREVIOUS/'exact-38-move-proposal.json')},
    'new_workshop_originals':2,'workshop_originals_total_bytes':sum(r['size'] for r in workshop_rows),
    'expected_counts':{'Bone_Spiral_2_White_In_Situ_before':67,'Bone_Spiral_2_White_In_Situ_after':27,'Bone_Spiral_2_White_before':1,'Bone_Spiral_2_White_after':39,'new_Bone_Spiral_2_White_Workshop_Views':2,'family_originals_before':153,'family_originals_after':153,'family_folders_before':5,'family_folders_after':6,'family_bytes_before':491362397,'family_bytes_after':491362397},
    'all_original_names_formats_IDs_and_bytes_preserved':True,'selected_catalogue_primary_context_roles_unchanged':True,'native_writes':0,'canonical_writes':0,
    'no_other_photographs_or_families_included':True,'Chiswick_015_remains_separate_pending_item':True,'Echo_23_already_completed_no_repeat':True,
    'new_workshop_folder_kept_flat_inside_Wall_Sculptures':True,
    'requires_fresh_prewrite_guards_and_exact_owner_approval':True,
    'undo_after_application':'Move these same 40 IDs back into the original In Situ folder with their original filenames. Removing the newly empty workshop folder would require separate deletion approval.'}
write('combined-exact-40-move-proposal.json',proposal)
write('workshop-two-only-details.json',{'status':'REVIEWED_NOT_APPLIED_INCLUDED_IN_COMBINED_40_PROPOSAL','folders_to_create':[newfolder],'moves':workshop_moves,'standalone_expected_source_67_to_65_if_only_two_approved':True,'after_all_40_source_count':27,'not_an_approval_for_either_set':True})
with (P/'all-40-proposed-image-source-destination-links.tsv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['filing_group','short_name','file_id','source_image_url','source_folder_url','destination_folder_url'],delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(allmoves)
e=html.escape
page=['<!doctype html><html><head><meta charset="utf-8"><title>Bone Spiral 2 — combined 40-photo filing proposal</title><style>body{font:16px system-ui;max-width:1350px;margin:30px auto;padding:0 20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:18px}article{border:1px solid #ccc;padding:12px}img{width:100%;height:260px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:9px;text-align:left}</style></head><body><h1>Bone Spiral 2: one combined 40-photo proposal</h1><p><strong>Not applied. Owner confirmation pending.</strong> This combines the previously reviewed38 close views with two workshop photographs. It includes the38 once. Keep component2, the White label, original filenames and formats.</p><table><tr><th>Folder</th><th>Current</th><th>Expected after all40 moves</th></tr><tr><td><a href="'+e(home(source))+'">Bone Spiral 2 White In Situ</a></td><td>67</td><td>27</td></tr><tr><td><a href="'+e(home(white))+'">Bone Spiral 2 White</a></td><td>1</td><td>39</td></tr><tr><td>Bone Spiral 2 White Workshop Views — new, directly under Bone Spiral</td><td>Does not exist</td><td>2</td></tr></table><p>All153 originals /491,362,397bytes retained. Five folders become six. Selected catalogue primary/context images and the other three folders remain unchanged. No Dropbox notes or indexes are proposed.</p>']
for group in ['Workshop views','Close product/detail views']:
    rr=[r for r in allmoves if r['filing_group']==group];page.append('<h2>'+e(group)+' — '+str(len(rr))+'</h2><div class="grid">')
    for r in rr:page.append('<article><a href="'+e(r['source_image_url'])+'"><img loading="lazy" src="'+e(r['preview'])+'"></a><p><strong>'+e(r['short_name'])+'</strong></p><p>'+e(r['reason'])+'</p><p><a href="'+e(r['source_image_url'])+'">Current image</a><br><a href="'+e(r['source_folder_url'])+'">Current containing folder</a><br>'+('<a href="'+e(r['destination_folder_url'])+'">Existing destination folder</a>' if group!='Workshop views' else 'Proposed destination, not created: '+e(workshop))+'</p><small>'+e(r['original_name'])+'</small></article>')
    page.append('</div>')
page.append('</body></html>');(P/'review-combined-40-proposed-moves.html').write_text(''.join(page))
validation={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_COMBINED_EXACT_PLAN_COMPLETE','unchanged_native_descendants':158,'family_originals':153,'family_folders':5,'family_bytes':491362397,
    'current_actual_originals_rehashed_against_fresh_native_hashes':40,'new_binary_downloads':0,'exact_source_file_metadata_checked':40,'new_destination_absent':True,'destination_collisions':0,
    'selected_catalogue_ids_in_move_set':0,'full_selected_option_records_unchanged':2,'native_writes':0,'canonical_writes':0,'proposal_sha256':sha(P/'combined-exact-40-move-proposal.json'),'expected_counts':proposal['expected_counts'],
    'prior_38_plan_seal_sha256':sha(PREVIOUS/'plan-seal.json'),'prior_38_contact_boards_viewed':5,'two_full_workshop_originals_viewed':2}
write('validation.json',validation)
excluded={'plan-seal.json','coordination-followup.json'};paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded]
write('plan-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_COMBINED_40_PROPOSAL_NO_MUTATIONS','receipt_count':len(paths),'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],'excluded_mutable_followup':['coordination-followup.json']})
print(json.dumps(validation,indent=2));print('PLAN_SEAL_SHA256',sha(P/'plan-seal.json'));print('REVIEW',P/'review-combined-40-proposed-moves.html')
