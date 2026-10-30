import csv
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

P = Path(__file__).resolve().parent
ROOT = Path('/Users/tprice/Documents/boldstone')
PREVIOUS = ROOT/'reports/dropbox-wall-only-chiswick-echo-bone-review-20261024T183336Z'
SCOPE = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(name, value):
    (P/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def fq(path):
    return path.split('/',1)[1] if path.startswith('ns:') else path

def home(path):
    return 'https://www.dropbox.com/home'+quote(path,safe='/')

fresh=read(P/'fresh-native-listing-metadata-and-hashes.json')
closing=read(P/'fresh-closing-native-listing.json')
selected=read(P/'selected-originals-from-prior-whole-family-review.json')
checks=read(P/'actual-existing-original-hash-readback.json')
prior=read(PREVIOUS/'fresh-complete-native-listings.json')
old_echo=next(x['result'] for x in prior['listings'] if x['name']=='Echo Sound')
assert not old_echo['has_more'] and not fresh['native_listing']['has_more'] and not closing['listing']['has_more']
ident=lambda listing:{x['file_id']:x for x in listing['entries']}
assert ident(old_echo)==ident(fresh['native_listing'])==ident(closing['listing'])
entries=ident(closing['listing'])
files={k:v for k,v in entries.items() if v['object_type']=='file'}
folders={k:v for k,v in entries.items() if v['object_type']=='folder'}
assert len(files)==180 and len(folders)==9
assert len(selected)==len({x['id'] for x in selected})==len(checks)==23
assert all(c['fresh_native_hash_match'] and not c['new_binary_download'] for c in checks)

white='id:cnqzTNngPVsAAAAAAAyicA'
insitu='id:cnqzTNngPVsAAAAAAAykBg'
assert folders[white]['name']=='Echo Sound 1 and Echo Sound 2 White'
assert folders[insitu]['name']=='Echo Sound 1 and Echo Sound 2 White In Situ'
metadata={x.get('file',x.get('folder',{})).get('id'):x for x in fresh['metadata']}
for fid in [white,insitu]:
    assert metadata[fid]['metadata_type']=='folder'
    assert metadata[fid]['folder']['path_display']==fq(folders[fid]['path'])
pointer=read(ROOT/'sculpture-catalogue/current-master.json')
regpath=ROOT/'sculpture-catalogue'/pointer['register']
register=read(regpath)
options=[x for x in register['options'] if x.get('family')=='Echo Sound']
assert len(options)==4
old_options={x['product_id']:x for x in read(PREVIOUS/'protected-catalogue-references-before.json')['options'] if x.get('family')=='Echo Sound'}
for option in options:
    assert option==old_options[option['product_id']]
    for prefix in ['', 'context_']:
        entry=files[option[prefix+'file_id']]
        parent=fq(entry['path']).rsplit('/',1)[0]
        assert option[prefix+'folder_url']==home(parent)
        assert option[prefix+'image_url']==home(parent)+'?preview='+quote(entry['name'],safe='')
        assert option[prefix+'folder_id'] in folders
protected={x[k] for x in options for k in ['file_id','context_file_id']}
assert not protected.intersection(x['id'] for x in selected)
write('protected-selected-options-current.json',{
    'recorded_utc':datetime.now(timezone.utc).isoformat(),
    'register_path':str(regpath),'register_sha256':sha(regpath),
    'options':options,'full_option_records_unchanged_from_prior_review':True,
    'all_selected_image_and_containing_folder_urls_match_fresh_native_identity':True,
    'selected_file_ids_in_move_set':[],
})

def find_ids(obj, identities, path=''):
    found=[]
    if isinstance(obj,dict):
        for k,v in obj.items():found+=find_ids(v,identities,path+'/'+str(k))
    elif isinstance(obj,list):
        for i,v in enumerate(obj):found+=find_ids(v,identities,path+'/'+str(i))
    elif isinstance(obj,str) and obj in identities:
        found.append({'json_pointer':path,'file_id':obj})
    return found

moves=[]
for r in selected:
    dest_id=white if r['proposal_group']=='ECHO-02' else insitu
    src_id=insitu if dest_id==white else white
    assert r['folder_id']==src_id
    native=files[r['id']]
    assert native['name']==r['name'] and native['path']==r['path']
    assert metadata[r['id']]['metadata_type']=='file'
    assert metadata[r['id']]['file']['path_display']==r['path_display']
    target=fq(folders[dest_id]['path'])+'/'+r['name']
    assert not any(fq(x['path']).lower()==target.lower() for x in entries.values())
    moves.append({
        'file_id':r['id'],'original_name':r['name'],'size':r['size'],
        'short_name':r['name'].split('__')[-1],
        'sha256':r['sha256'],'dropbox_content_hash':r['dropbox_content_hash'],
        'source_folder_id':src_id,'source_folder_path':r['folder_path'],
        'source_image_url':r['image_url'],'source_folder_url':r['folder_url'],
        'destination_folder_id':dest_id,'destination_folder_path':fq(folders[dest_id]['path']),
        'destination_path':target,'destination_folder_url':home(fq(folders[dest_id]['path'])),
        'expected_image_url':home(fq(folders[dest_id]['path']))+'?preview='+quote(r['name'],safe=''),
        'direction':'In Situ to White' if dest_id==white else 'White to In Situ',
        'reason':'Close framing of the panels; retain as product photograph.' if dest_id==white else 'Wider brick-wall view shows surrounding wall; classify as In Situ under owner convention.',
        'source_review_index':r['review_index'],'selected_primary_or_context':False,
        'destination_collision':False,
        'preview':'previews/'+r['id'].split(':',1)[1]+'.jpg',
        'undo_destination_path':r['path_display'],
    })
assert sum(m['destination_folder_id']==insitu for m in moves)==17
assert sum(m['destination_folder_id']==white for m in moves)==6
folder_counts={fid:sum(fq(x['path']).rsplit('/',1)[0]==fq(f['path']) for x in files.values()) for fid,f in folders.items()}
assert folder_counts[white]==104 and folder_counts[insitu]==14
proposal={
    'recorded_utc':datetime.now(timezone.utc).isoformat(),
    'status':'EXACT_PLAN_PREPARED_NOT_APPLIED_OWNER_CONFIRMATION_PENDING',
    'scope':SCOPE,'family':'Echo Sound','operation':'move',
    'native_writes':0,'canonical_writes':0,'folders_to_create':[],
    'basis':'Owner: brick-wall photographs should count as In Situ but not including close framing. Exact selection reviewed here; not a blanket library-wide automatic rule.',
    'moves':moves,
    'expected_counts':{'pair_white_before':104,'pair_white_after':93,'pair_in_situ_before':14,'pair_in_situ_after':25,'family_files_before':180,'family_files_after':180,'family_folders_before':9,'family_folders_after':9,'family_bytes_before':sum(x.get('file',{}).get('size',0) for x in files.values()),'family_bytes_after':sum(x.get('file',{}).get('size',0) for x in files.values())},
    'all_23_filenames_formats_ids_and_bytes_preserved':True,
    'selected_four_options_and_their_primary_context_roles_unchanged':True,
    'current_register_exact_moved_file_id_occurrences':find_ids(register,{x['file_id'] for x in moves}),
    'preserve_all_captured_source_evidence_and_own_file_navigation_on_later_catalogue_import':True,
    'unresolved_dark_finish_images_not_moved':['echo-sound__echo-sounds-1-and-2-white__001.jpg','echo-sound__echo-sounds-1-and-2-white__101.jpg','echo-sound__echo-sounds-1-and-2-white__102.jpg'],
    'no_other_images_included_in_this_plan':True,
    'chiswick_015_separate_proposal_still_pending':True,
    'requires_new_native_guards_and_session_overlap_check_after_later_owner_approval':True,
    'undo_after_application':'Move the same 23 IDs back to each recorded original containing folder, retaining original filenames.',
}
write('exact-23-move-proposal.json',proposal)
with (P/'all-23-proposed-image-source-destination-links.tsv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['direction','short_name','file_id','source_image_url','source_folder_url','destination_folder_url','expected_image_url'],delimiter='\t',extrasaction='ignore');writer.writeheader();writer.writerows(moves)
e=html.escape
parts=['<!doctype html><html><head><meta charset="utf-8"><title>Echo Sound — exact 23-image filing proposal</title><style>body{font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:20px}article{border:1px solid #ccc;padding:14px}img{width:100%;height:270px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:9px;text-align:left}</style></head><body><h1>Echo Sound: exact 23-image filing proposal</h1><p><strong>Not applied. Owner confirmation pending.</strong> Move 17 wider wall views into the existing pair In Situ folder and six close views back into the existing pair White folder. No folder creation. Original filenames, formats and bytes remain unchanged.</p><table><tr><th>Existing folder</th><th>Before</th><th>Expected after</th></tr>']
for fid,after in [(white,93),(insitu,25)]:parts.append('<tr><td><a href="'+e(home(fq(folders[fid]['path'])))+'">'+e(folders[fid]['name'])+'</a></td><td>'+str(folder_counts[fid])+'</td><td>'+str(after)+'</td></tr>')
parts.append('</table><p>All 180 images in the family remain preserved. The selected catalogue primary/context photographs and individual component folders are unchanged.</p>')
for direction in ['White to In Situ','In Situ to White']:
    group=[x for x in moves if x['direction']==direction]
    parts.append('<h2>'+e(direction)+' — '+str(len(group))+' images</h2><div class="grid">')
    for x in group:
        parts.append('<article><a href="'+e(x['source_image_url'])+'"><img loading="lazy" src="'+e(x['preview'])+'"></a><p><strong>'+e(x['short_name'])+'</strong><br>'+e(x['reason'])+'</p><p><a href="'+e(x['source_image_url'])+'">Open current image in Dropbox</a><br><a href="'+e(x['source_folder_url'])+'">Current containing folder</a><br><a href="'+e(x['destination_folder_url'])+'">Proposed existing destination folder</a></p><small>'+e(x['original_name'])+'</small></article>')
    parts.append('</div>')
parts.append('<p>Three dark-finish images remain in place: 001.jpg, 101.jpg and 102.jpg under the pair White folder. Their finish is unresolved. This proposal excludes all other photographs and the separate pending Chiswick item.</p></body></html>')
(P/'review-all-23-proposed-moves.html').write_text(''.join(parts))

validation={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_EXACT_PLAN_COMPLETE',
    'native_objects_unchanged_since_prior_whole_family_review':189,
    'family_files':180,'family_folders':9,'actual_existing_originals_rehashed':23,
    'fresh_native_hash_matches':23,'new_binary_downloads':0,
    'metadata_identity_checks':25,'contact_boards_visually_reviewed':3,
    'full_selected_option_records_unchanged':4,
    'selected_photo_file_ids_in_move_set':0,'destination_collisions':0,
    'native_writes':0,'canonical_writes':0,
    'proposal_sha256':sha(P/'exact-23-move-proposal.json'),
    'expected_counts':proposal['expected_counts'],
    'canonical_occurrence_count':len(proposal['current_register_exact_moved_file_id_occurrences']),
    'prior_whole_family_review_seal_sha256':sha(PREVIOUS/'review-seal.json')}
write('validation.json',validation)
excluded={'plan-seal.json','coordination-followup.json'}
paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded]
write('plan-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_EXACT_PROPOSAL_NO_MUTATIONS',
    'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],
    'receipt_count':len(paths),'excluded_mutable_followup':['coordination-followup.json'],
    'actual_original_bytes_bound_in':'actual-existing-original-hash-readback.json'})
print(json.dumps(validation,indent=2))
print('PLAN_SEAL_SHA256',sha(P/'plan-seal.json'))
print('REVIEW_PAGE',P/'review-all-23-proposed-moves.html')
