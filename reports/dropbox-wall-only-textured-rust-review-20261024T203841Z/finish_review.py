import csv,hashlib,html,json,re
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs

P=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
BASE=ROOT/'sculpture-catalogue'
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
FAMILIES=[('Textured Panels','textured-panels'),('Wall Panel Rust and Verdigris','wall-panel-rust-and-verdigris')]
def read(p):return json.loads(Path(p).read_text())
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fq(s):return re.sub(r'^ns:\d+/','',s)
def home(s):return 'https://www.dropbox.com/home'+quote(s,safe='/')
def image_identity(s):
 u=urlsplit(s);assert u.scheme=='https' and u.netloc=='www.dropbox.com'
 if u.path.startswith('/preview/'):return unquote(u.path[len('/preview'):])
 assert u.path.startswith('/home/')
 return unquote(u.path[len('/home'):])+'/'+parse_qs(u.query)['preview'][0]
before=read(P/'fresh-complete-native-listings.json');after=read(P/'fresh-closing-native-listings.json')
for b,a in zip(before['listings'],after['listings']):
 assert b['name']==a['name'] and not b['result']['has_more'] and not a['result']['has_more']
 assert {e['file_id']:e for e in b['result']['entries']}=={e['file_id']:e for e in a['result']['entries']}
rows=[];byfamily={}
for family,slug in FAMILIES:
 rr=read(P/(slug+'-verified-originals-and-links.json'));rows+=rr;byfamily[family]={r['review_index']:r for r in rr}
assert len(rows)==len({r['id'] for r in rows})==160 and sum(r['size'] for r in rows)==1201621594
nativehash={r['id']:r for r in read(P/'fresh-native-hash-metadata.json')}
for r in rows:
 assert r['content_hash']==r['dropbox_content_hash']==nativehash[r['id']]['content_hash']
 assert Path(r['local_path']).stat().st_size==r['size']==nativehash[r['id']]['size']
 assert r['folder_path'].startswith(SCOPE+'/') and r['folder_url']==home(r['folder_path'])
 assert r['image_url']==home(r['folder_path'])+'?preview='+quote(r['name'],safe='')
byid={r['id']:r for r in rows};protected=read(P/'protected-catalogue-references-before.json')
pointer=read(BASE/'current-master.json');regpath=BASE/pointer['register'];reg=read(regpath);options={o['product_id']:o for o in reg['options']}
selected_ids={o[k] for o in protected['options'] for k in ['file_id','context_file_id'] if o.get(k)}
aliases=[]
for o in protected['options']:
 assert options[o['product_id']]==o
 for prefix in ['', 'context_']:
  if not o.get(prefix+'file_id'):continue
  r=byid[o[prefix+'file_id']]
  assert o[prefix+'folder_id']==r['folder_id'] and o[prefix+'folder_url']==r['folder_url']
  assert image_identity(o[prefix+'image_url'])==r['path_display']
  if o[prefix+'image_url']!=r['image_url']:aliases.append({'product_id':o['product_id'],'role':prefix or 'primary','file_id':r['id'],'preserved_catalogue_url':o[prefix+'image_url'],'equivalent_review_url':r['image_url']})
metadata=read(P/'fresh-protected-files-and-family-roots-metadata.json')['metadata']
selected_metadata={m['file']['id']:m['file'] for m in metadata if m['metadata_type']=='file'}
assert set(selected_metadata)==selected_ids and len(selected_ids)==4
for fid,m in selected_metadata.items():
 r=byid[fid];assert m['name']==r['name'] and m['path_display']==r['path_display'] and m['size']==r['size']
write('protected-catalogue-reference-closing-check.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'register':str(regpath),'register_sha256':sha(regpath),'three_full_option_records_unchanged':True,'four_selected_file_ID_and_actual_parent_pairs_verified':True,'equivalent_preview_and_home_URL_forms':aliases,'native_writes':0,'canonical_writes':0})

findings=[]
def finding(code,family,indices,observation,next_step,status):
 rr=[byfamily[family][i] for i in indices]
 findings.append({'id':code,'family':family,'status':status,'observation':observation,'next_step':next_step,'images':[{**{k:r[k] for k in ['review_index','id','name','folder_id','folder_path','folder_url','image_url','sha256']},'selected_catalogue_photo':r['id'] in selected_ids} for r in rr]})
rust='Wall Panel Rust and Verdigris';textured='Textured Panels'
candidate_indices=[8,9,10,12,13,14,15,16,17,25,26,28]
finding('RUST-01',rust,candidate_indices,'Eleven close surface/detail crops (007–009.jpg,011–016.jpeg,024–025.jpeg) and one rear view (027.jpeg) are filed in In Situ.','Exact twelve-file move proposed into the existing product folder. Product5→17; In Situ23→11. No new folders or filename changes. Not approved or applied.','EXACT_PROPOSED_MOVE_PENDING_OWNER_CONFIRMATION')
finding('RUST-02',rust,[6,7],'Room-display002.jpg and004.jpg show the panel with surrounding furniture.002.jpg remains the selected catalogue context.','Retain current folder and selected roles. Scene origin and real installation are not established by this filing review.','RETAIN_CURRENT_FILING')
finding('RUST-03',rust,[11,18,19,20,21,22,23,24,27],'Nine full-panel brick-wall views have varying amounts of surrounding wall:010.jpeg,017–023.jpeg,026.jpeg. Some are closely framed.','Retain current filing while the exact close-framing boundary is unresolved. These nine are excluded from the twelve proposed moves.','BORDERLINE_RETAIN_CURRENT_FILING')
finding('TEXTURED-01',textured,[1,8],'Tall Rust and Blue Patina001.jpg and008.jpg show the full panel standing in an interior display/setup.001.jpg is both selected primary and context.','Keep selected references and current filing; do not infer a permanent installation. Any later folder move needs an exact plan and approval.','REVIEW_OBSERVATION_NO_MOVE_APPROVAL')
finding('TEXTURED-02',textured,[131,132],'Wide Blue Brown and Rust108.jpg and109.jpg show the panel laid on a table with the surrounding room and other stored panels.','Keep these setup views in place pending a filing decision; no Workshop Views or In Situ folder is created.','REVIEW_OBSERVATION_NO_MOVE_APPROVAL')
finding('TEXTURED-03',textured,[26,27,28,30,31,68,69,70,71],'The Wide panel appears in both portrait and landscape views, with lighting/exposure differences across its detail photographs. The Tall and Wide panels already have separate named folders.','Retain existing identities and finish labels. Do not create extra components or finishes from orientation or lighting.','RETAIN_CURRENT_IDENTITY')
write('review-observations.json',findings)
obs={}
for f in findings:
 for r in f['images']:obs.setdefault(r['id'],[]).append(f['id'])
decisions=[{**{k:r[k] for k in ['family','review_index','id','name','folder_id','folder_path','folder_url','image_url']},'reviewed_visually':True,'native_action_applied':'NONE','observation_ids':obs.get(r['id'],[]),'selected_catalogue_photo':r['id'] in selected_ids} for r in rows]
write('all-160-image-folder-links-and-review.json',decisions)
with (P/'all-160-image-folder-links.tsv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['family','review_index','id','name','folder_path','folder_url','image_url'],delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(decisions)

rust_native=next(x for x in before['listings'] if x['name']==rust)
folders={e['name']:e for e in rust_native['result']['entries'] if e['object_type']=='folder'}
src=folders[rust+' In Situ'];dst=folders[rust]
candidates=[byfamily[rust][i] for i in candidate_indices];assert len(candidates)==12 and not(selected_ids & {r['id'] for r in candidates})
proposed_metadata=read(P/'fresh-twelve-candidates-and-two-folder-metadata.json')['metadata']
meta={m[m['metadata_type']]['id']:m[m['metadata_type']] for m in proposed_metadata}
moves=[]
for r in candidates:
 m=meta[r['id']];assert m['path_display']==r['path_display'] and m['size']==r['size'] and r['folder_id']==src['file_id']
 target=dst['path']+'/'+r['name'];assert not any(e['path'].casefold()==target.casefold() for e in rust_native['result']['entries'])
 moves.append({'file_id':r['id'],'name':r['name'],'source_path':r['path'],'source_folder_id':src['file_id'],'source_folder_url':r['folder_url'],'current_image_url':r['image_url'],'destination_path':target,'destination_folder_id':dst['file_id'],'destination_folder_url':home(fq(dst['path'])),'proposed_image_url':home(fq(dst['path']))+'?preview='+quote(r['name'],safe=''),'size':r['size'],'sha256':r['sha256'],'dropbox_content_hash':r['content_hash'],'current_rev':m['rev'],'reason':'Rear view without an installation setting' if r['review_index']==28 else 'Close surface/detail framing without a wider setting'})
proposal={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'PROPOSED_NOT_APPROVED_NOT_APPLIED','native_scope':SCOPE,'operation':'MOVE','create_folders':False,'rename_files':False,'files':moves,'expected_counts':{'product_before':5,'product_after':17,'in_situ_before':23,'in_situ_after':11,'family_originals_preserved':28,'family_bytes_preserved':22649200,'family_folders_preserved':2},'selected_primary_and_context_unchanged':True,'native_writes':0,'canonical_writes':0,'approval_required_for_this_exact_plan':True,'other_pending_plans_not_included':['Bone Spiral combined40','Chiswick015'],'reversion_if_later_applied':[{'file_id':m['file_id'],'restore_path':m['source_path']} for m in moves]}
write('proposed-exact-twelve-rust-moves.json',proposal)
style='<meta charset="utf-8"><style>body{font:16px system-ui;max-width:1250px;margin:30px auto;padding:0 20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:16px}article{border:1px solid #bbb;padding:12px}img{width:100%;height:240px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}</style>'
e=html.escape
parts=[style,'<title>Textured Panels and Rust/Verdigris complete filing review</title><h1>160 originals reviewed; no Dropbox changes</h1><p>132 Textured Panels images and28 Wall Panel Rust and Verdigris images. Every actual original matched a fresh native content hash. Three full catalogue option records and four distinct selected image IDs are unchanged. Observations and a twelve-file proposal follow.</p>']
for family,slug in FAMILIES:parts.append('<p><a href="'+slug+'-all-image-folder-links.html">All '+str(len(byfamily[family]))+' '+e(family)+' images and containing folders</a></p>')
for f in findings:
 slug=next(s for n,s in FAMILIES if n==f['family']);parts+=['<h2>'+e(f['id'])+'</h2><p>'+e(f['observation'])+'</p><p>'+e(f['next_step'])+'</p><div class="grid">']
 for r in f['images']:parts.append('<article><a href="'+e(r['image_url'])+'"><img loading="lazy" src="thumbnails/'+slug+'/'+str(r['review_index']).zfill(3)+'.jpg"></a><p><a href="'+e(r['image_url'])+'">'+e(r['name'])+'</a><br><a href="'+e(r['folder_url'])+'">Containing folder</a></p>'+('<strong>Selected catalogue reference — unchanged</strong>' if r['selected_catalogue_photo'] else '')+'</article>')
 parts.append('</div>')
(P/'review-findings-and-all-family-links.html').write_text(''.join(parts))
parts=[style,'<title>Twelve proposed Rust and Verdigris moves</title><h1>Twelve proposed moves — not applied</h1><p>Move11 close surface/detail photographs and one rear view from In Situ to the existing product folder. Product5→17; In Situ23→11; all28 original files and filenames preserved. No new folders. Selected primary005.jpeg and context002.jpg remain unchanged.</p><div class="grid">']
for r,m in zip(candidates,moves):parts.append('<article><a href="'+e(m['current_image_url'])+'"><img src="thumbnails/wall-panel-rust-and-verdigris/'+str(r['review_index']).zfill(3)+'.jpg"></a><p><a href="'+e(m['current_image_url'])+'">'+e(m['name'])+'</a></p><p>'+e(m['reason'])+'</p><p>From: <a href="'+e(m['source_folder_url'])+'">In Situ</a><br>To: <a href="'+e(m['destination_folder_url'])+'">Existing product folder</a></p></article>')
parts.append('</div>');(P/'review-exact-twelve-proposed-rust-moves.html').write_text(''.join(parts))

priorpath=ROOT/'reports/dropbox-wall-only-leaf-growth-fountain-palm-review-20261024T201625Z/combined-thirty-five-family-current-image-folder-links.json';old=read(priorpath);merged={r['file_id']:r for r in old};overlap=[]
for r in rows:
 if r['id'] in merged:overlap.append({'file_id':r['id'],'prior_role':merged[r['id']]['role']})
 merged[r['id']]={'role':'source','family':r['family'],'file_id':r['id'],**{k:r[k] for k in ['name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash']}}
cumulative=sorted(merged.values(),key=lambda r:(r['family'],r['folder_path'],r['name']));write('combined-thirty-seven-family-current-image-folder-links.json',cumulative)
accounting={'prior_manifest':str(priorpath),'prior_manifest_sha256':sha(priorpath),'new_whole_families':2,'new_originals':160,'prior_overlap':overlap,'whole_source_families':len({r['family'] for r in cumulative if r['role']=='source'}),'whole_source_originals':sum(r['role']=='source' for r in cumulative),'comparison_only_originals':sum(r['role']!='source' for r in cumulative),'distinct_original_references':len(cumulative),'freshness_note':'Only Textured Panels and Wall Panel Rust and Verdigris were freshly inventoried and reviewed here. Earlier family references retain dated captures and approved move overlays. This is not a fresh whole-library inventory.','not_unique_design_or_physical_stock_count':True}
assert accounting['whole_source_families']==37 and accounting['whole_source_originals']==1913 and accounting['comparison_only_originals']==8 and len(cumulative)==1921
write('cumulative-link-accounting.json',accounting)
summary={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_REVIEW_COMPLETE_EXACT_TWELVE_FILE_PROPOSAL_PENDING','native_scope':SCOPE,'native_writes':0,'canonical_writes':0,'originals':160,'original_bytes':1201621594,'fresh_http_original_downloads':sum(not r['reused_native_identical_local_bytes'] for r in rows),'actual_existing_originals_rehashed_against_fresh_native_hashes':sum(r['reused_native_identical_local_bytes'] for r in rows),'unchanged_native_descendant_objects':164,'contact_boards_visually_reviewed':9,'full_option_records_unchanged':3,'selected_file_IDs_and_actual_parents_verified':4,'selected_and_family_root_metadata_objects':6,'candidate_and_folder_metadata_objects':14,'proposal_file_sha256':sha(P/'proposed-exact-twelve-rust-moves.json'),'proposed_moves_applied':0,'families':{f:{'files':len(rr),'bytes':sum(r['size'] for r in rr.values()),'folders':len({r['folder_id'] for r in rr.values()})} for f,rr in byfamily.items()},'historical_rust_four_source_ID_discrepancy_held_no_restoration':True,'no_new_missing_photo_or_physical_specification_questions':True,'Bone40_and_Chiswick015_remain_pending_unapplied':True,'Echo23_complete_not_repeated':True,'cumulative_accounting':accounting}
assert summary['fresh_http_original_downloads']==27 and summary['actual_existing_originals_rehashed_against_fresh_native_hashes']==133
write('validation.json',summary)
excluded={'review-seal.json','coordination-followup.json'}
paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded and 'originals' not in x.relative_to(P).parts]
write('review-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_READ_ONLY_REVIEW_AND_UNAPPROVED_EXACT_PROPOSAL','receipt_count':len(paths),'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],'original_bytes_bound_by':['textured-panels-verified-originals-and-links.json','wall-panel-rust-and-verdigris-verified-originals-and-links.json'],'excluded_mutable_followup':['coordination-followup.json'],'native_writes':0,'canonical_writes':0})
print(json.dumps(summary,indent=2));print('REVIEW_SEAL_SHA256',sha(P/'review-seal.json'));print('SEALED_RECEIPTS',len(paths))
