import collections,csv,hashlib,html,json
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs

P=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone');BASE=ROOT/'sculpture-catalogue'
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
def read(p):return json.loads(Path(p).read_text())
def write(n,x):(P/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def fq(s):return s.split('/',1)[1] if s.startswith('ns:') else s
def home(s):return 'https://www.dropbox.com/home'+quote(s,safe='/')
def image_path(s):
 u=urlsplit(s);assert u.scheme=='https' and u.netloc=='www.dropbox.com'
 if u.path.startswith('/preview/'):return unquote(u.path[len('/preview'):])
 assert u.path.startswith('/home/')
 return unquote(u.path[len('/home'):])+'/'+parse_qs(u.query)['preview'][0]
before=read(P/'fresh-complete-native-listings.json');closing=read(P/'fresh-closing-native-listings.json')
assert len(before['listings'])==len(closing['listings'])==1
b=before['listings'][0];a=closing['listings'][0]
assert not b['result']['has_more'] and not a['result']['has_more']
assert {e['file_id']:e for e in b['result']['entries']}=={e['file_id']:e for e in a['result']['entries']}
rows=read(P/'deco-dune-ripple-verified-originals-and-links.json');byid={r['id']:r for r in rows};byindex={r['review_index']:r for r in rows}
assert len(rows)==len(byid)==182 and sum(r['size'] for r in rows)==663492401
hashes={r['id']:r for r in read(P/'fresh-native-hash-metadata.json')}
for r in rows:
 assert r['content_hash']==r['dropbox_content_hash']==hashes[r['id']]['content_hash']
 assert Path(r['local_path']).stat().st_size==r['size']==hashes[r['id']]['size']
 assert r['folder_path'].startswith(SCOPE+'/') and r['folder_url']==home(r['folder_path'])
 assert image_path(r['image_url'])==r['path_display']
protected=read(P/'protected-catalogue-references-before.json');pointer=read(BASE/'current-master.json');regpath=BASE/pointer['register'];register=read(regpath);options={o['product_id']:o for o in register['options']}
selected={o[k] for o in protected['options'] for k in ['file_id','context_file_id'] if o.get(k)}
assert len(protected['options'])==4 and len(selected)==6
aliases=[]
for o in protected['options']:
 assert o==options[o['product_id']]
 for prefix in ['', 'context_']:
  if not o.get(prefix+'file_id'):continue
  r=byid[o[prefix+'file_id']]
  assert o[prefix+'folder_id']==r['folder_id'] and o[prefix+'folder_url']==r['folder_url']
  assert image_path(o[prefix+'image_url'])==r['path_display']
  if o[prefix+'image_url']!=r['image_url']:aliases.append({'product_id':o['product_id'],'role':prefix or 'primary','file_id':r['id'],'preserved_catalogue_url':o[prefix+'image_url'],'equivalent_review_url':r['image_url']})
meta=read(P/'fresh-protected-files-and-family-roots-metadata.json')['metadata'];selected_meta={x['file']['id']:x['file'] for x in meta if x['metadata_type']=='file'}
assert set(selected_meta)==selected
for fid,m in selected_meta.items():
 r=byid[fid];assert m['name']==r['name'] and m['size']==r['size'] and m['path_display']==r['path_display']
write('protected-catalogue-reference-closing-check.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'register_path':str(regpath),'register_sha256':sha(regpath),'four_full_option_records_unchanged':True,'six_selected_IDs_and_actual_containing_folders_verified':True,'equivalent_preview_and_home_URL_forms':aliases,'native_writes':0,'canonical_writes':0,'no_new_photo_or_specification_questions':True})

findings=[]
def finding(code,indices,observation,next_step,status='REVIEW_OBSERVATION_NO_MOVE_APPROVAL'):
 findings.append({'id':code,'status':status,'observation':observation,'next_step':next_step,'images':[{**{k:r[k] for k in ['review_index','id','name','folder_id','folder_path','folder_url','image_url','sha256']},'selected_catalogue_photo':r['id'] in selected} for r in (byindex[i] for i in indices)]})
finding('DDR-01',[5,16],'Wave White004.jpg shows two Wave-pattern panels beside moulds/workshop equipment.015.JPG shows two Wave panels arranged horizontally. Both are currently in the individual Deco Dune Ripple1 White folder. Neither is a Wave1-plus-Spiral2 pair.','Keep both originals in place for now.004 is a workshop-view filing candidate;015 is a repeated-component arrangement candidate. Do not create a new design number or label either photograph as the1-and2 arrangement.')
finding('DDR-02',[30,31],'Both Verdigris three-panel PNGs show Wave1–Spiral2–Wave1 against a plain wall with very close framing. They do not show a wider room or installation setting.','The current folder label In Situ is inconsistent with this framing. A later exact folder-rename plan could remove In Situ while retaining the three-panel arrangement label. No rename is approved or applied here.')
finding('DDR-03',[32,80],'Pair White001.png is a wide room-scene reference;049.JPG shows the complete Wave1 and Spiral2 pair beneath a framed picture.001.png remains the selected shared catalogue context.','Retain both pair identities and selected roles. They are context-filing candidates if an exact flat White In Situ folder plan is later approved. Scene origin and permanent installation are not established.')
finding('DDR-04',[94,95]+list(range(110,122)),'Fourteen White three-panel photographs include a wider wall or room setting:008–009.JPG and024–035.JPG. Some files were captured sideways; originals are preserved. The arrangement remains two Wave1 panels and one Spiral2 panel.','Candidates for a later In Situ filing plan under the same three-panel arrangement. A destination folder does not currently exist. No new folder or move is approved or applied.')
finding('DDR-05',[21,176],'Wave White020.JPG and Spiral White039.JPG show each individual panel with the surrounding wall and framed picture. Their current folders contain both product/detail and room-display photographs.','Keep the existing component identities. These are candidates for individual In Situ folders in a later exact plan; no folders are created here.')
finding('DDR-06',[80,176],'Full-size inspection confirms pair049.JPG has a Wave panel on the left and Spiral panel on the right. Individual Spiral039.JPG shows the Spiral panel alone. The two originals have different bytes.','Corrected an earlier thumbnail impression that049 showed the Spiral alone.049 stays in the pair folder; there is no proposed move into the Spiral-only folder.','FULL_SIZE_COMPONENT_CHECK_CORRECTED_RETAIN_CURRENT_FILING')
finding('DDR-07',[61],'Pair White030.JPG includes a wider outdoor setting, but both panels are cut off by the lower image edge.','Retain current filing as a borderline view. It is excluded from the clear room-view candidates; no automatic role change.')
finding('DDR-08',[1,2,3,29,30,31,33,87,89,137,138],'The existing family has two established components:1=Wave and2=Spiral. Separate White and Verdigris options and flat pair/three-panel folders already exist. Three-panel groups repeat Wave1 on both sides of Spiral2.','Retain the established numbering, existing finish labels and four option records. Rotation, lighting and repeated panels do not add component identities or physical stock claims.','RETAIN_CURRENT_COMPONENT_IDENTITIES_AND_FINISH_OPTIONS')
write('review-observations.json',findings)
observations={}
for f in findings:
 for r in f['images']:observations.setdefault(r['id'],[]).append(f['id'])
decisions=[{**{k:r[k] for k in ['family','review_index','id','name','folder_id','folder_path','folder_url','image_url']},'reviewed_visually':True,'native_action_applied':'NONE','selected_catalogue_photo':r['id'] in selected,'observation_ids':observations.get(r['id'],[])} for r in rows]
write('all-182-image-folder-links-and-review.json',decisions)
with (P/'all-182-image-folder-links.tsv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['review_index','id','name','folder_path','folder_url','image_url'],delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(decisions)
folders=[]
for x in sorted([e for e in b['result']['entries'] if e['object_type']=='folder'],key=lambda x:x['name']):
 rr=[r for r in rows if r['folder_id']==x['file_id']];assert rr
 folders.append({'folder_id':x['file_id'],'name':x['name'],'path':x['path'],'folder_url':home(fq(x['path'])),'files':len(rr),'bytes':sum(r['size'] for r in rr)})
assert len(folders)==8 and sum(x['files'] for x in folders)==182
write('current-flat-family-structure-and-folder-links.json',folders)
duplicates=collections.defaultdict(list)
for r in rows:duplicates[r['sha256']].append(r['id'])
write('exact-byte-duplicate-check.json',{'originals':182,'distinct_sha256_hashes':len(duplicates),'duplicate_groups':[x for x in duplicates.values() if len(x)>1],'no_deletions_or_visual_duplicate_inference':True})
assert len(duplicates)==182

from PIL import Image,ImageOps
focus=P/'focus';focus.mkdir(exist_ok=True)
for i in [5,16,30,31,80,176]:
 with Image.open(byindex[i]['local_path']) as im:
  im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((1200,1200));im.save(focus/(str(i).zfill(3)+'.jpg'),quality=93)
write('full-size-checks.json',{'actual_original_indices_viewed':[5,16,30,31,80,176],'correction':'Pair049.JPG (review80) shows both components and stays in the pair folder. Spiral039.JPG (review176) shows the individual Spiral. No mistaken individual move plan was created.','originals_unchanged':True})
style='<meta charset="utf-8"><style>body{font:16px system-ui;max-width:1300px;margin:30px auto;padding:0 20px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}article{border:1px solid #bbb;padding:12px}img{width:100%;height:310px;object-fit:contain;background:#eee}a{overflow-wrap:anywhere}td,th{padding:8px;border:1px solid #bbb}table{border-collapse:collapse}</style>'
e=html.escape
parts=[style,'<title>Deco Dune Ripple complete filing review</title><h1>Deco Dune Ripple:182 originals reviewed; no Dropbox changes</h1><p>All original bytes matched fresh native hashes. Eight flat folders and four full catalogue option records are unchanged.1=Wave;2=Spiral. This review records filing observations, not approved moves or physical stock counts.</p><p><a href="deco-dune-ripple-all-image-folder-links.html">All182 images and containing folders</a></p><table><tr><th>Current folder</th><th>Images</th></tr>']
for f in folders:parts.append('<tr><td><a href="'+e(f['folder_url'])+'">'+e(f['name'])+'</a></td><td>'+str(f['files'])+'</td></tr>')
parts.append('</table>')
for f in findings:
 parts+=['<h2>'+e(f['id'])+'</h2><p>'+e(f['observation'])+'</p><p>'+e(f['next_step'])+'</p><div class="grid">']
 for r in f['images']:
  i=r['review_index'];src=('focus/'+str(i).zfill(3)+'.jpg') if i in [5,16,30,31,80,176] else ('thumbnails/deco-dune-ripple/'+str(i).zfill(3)+'.jpg')
  parts.append('<article><a href="'+e(r['image_url'])+'"><img loading="lazy" src="'+src+'"></a><p><a href="'+e(r['image_url'])+'">'+e(r['name'])+'</a><br><a href="'+e(r['folder_url'])+'">Containing folder</a></p>'+('<strong>Selected catalogue reference — unchanged</strong>' if r['selected_catalogue_photo'] else '')+'</article>')
 parts.append('</div>')
(P/'review-findings-and-all-family-links.html').write_text(''.join(parts))
priorpath=ROOT/'reports/dropbox-wall-only-textured-rust-review-20261024T203841Z/combined-thirty-seven-family-current-image-folder-links.json';old=read(priorpath);merged={r['file_id']:r for r in old};overlap=[]
for r in rows:
 if r['id'] in merged:overlap.append({'file_id':r['id'],'prior_role':merged[r['id']]['role']})
 merged[r['id']]={'role':'source','family':r['family'],'file_id':r['id'],**{k:r[k] for k in ['name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash']}}
cumulative=sorted(merged.values(),key=lambda r:(r['family'],r['folder_path'],r['name']));write('combined-thirty-eight-family-current-image-folder-links.json',cumulative)
accounting={'prior_manifest':str(priorpath),'prior_manifest_sha256':sha(priorpath),'new_whole_families':1,'new_originals':182,'prior_overlap':overlap,'whole_source_families':len({r['family'] for r in cumulative if r['role']=='source'}),'whole_source_originals':sum(r['role']=='source' for r in cumulative),'comparison_only_originals':sum(r['role']!='source' for r in cumulative),'distinct_original_references':len(cumulative),'freshness_note':'Only Deco Dune Ripple was freshly inventoried and reviewed here. Earlier families retain dated captures and approved move overlays. This is not a fresh whole-library inventory.','not_a_unique_design_or_physical_stock_count':True}
assert accounting['whole_source_families']==38 and accounting['whole_source_originals']==2095 and accounting['comparison_only_originals']==8 and len(cumulative)==2103
write('cumulative-link-accounting.json',accounting)
summary={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'READ_ONLY_WHOLE_FAMILY_REVIEW_COMPLETE','native_scope':SCOPE,'originals':182,'original_bytes':663492401,'folders':8,'native_descendant_objects_unchanged':190,'fresh_http_original_downloads':sum(not r['reused_native_identical_local_bytes'] for r in rows),'actual_cached_originals_rehashed_against_fresh_native_hashes':sum(r['reused_native_identical_local_bytes'] for r in rows),'contact_boards_visually_reviewed':10,'actual_full_size_originals_visually_checked':6,'full_option_records_unchanged':4,'selected_IDs_and_actual_parent_pairs_verified':6,'native_metadata_objects_verified':7,'native_writes':0,'canonical_writes':0,'new_exact_move_proposals':0,'new_owner_photo_or_physical_specification_questions':0,'pair049_corrected_full_size_not_a_single_component':True,'pending_Rust12_Bone40_Chiswick015_not_approved_or_applied':True,'completed_Echo23_not_repeated':True,'cumulative_accounting':accounting}
assert summary['fresh_http_original_downloads']==64 and summary['actual_cached_originals_rehashed_against_fresh_native_hashes']==118
write('validation.json',summary)
excluded={'review-seal.json','coordination-followup.json'};paths=[x for x in P.rglob('*') if x.is_file() and x.name not in excluded and 'originals' not in x.relative_to(P).parts]
write('review-seal.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_READ_ONLY_REVIEW','receipt_count':len(paths),'files':[{'path':str(x.relative_to(P)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],'actual_original_bytes_bound_by':'deco-dune-ripple-verified-originals-and-links.json','excluded_mutable_followup':['coordination-followup.json'],'native_writes':0,'canonical_writes':0})
print(json.dumps(summary,indent=2));print('REVIEW_SEAL_SHA256',sha(P/'review-seal.json'));print('SEALED_RECEIPTS',len(paths))
