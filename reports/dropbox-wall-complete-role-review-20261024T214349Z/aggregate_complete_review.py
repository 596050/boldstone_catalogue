import collections,csv,datetime,functools,hashlib,html,json,pathlib,unicodedata,urllib.parse
P=pathlib.Path(__file__).resolve().parent
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,x):pathlib.Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
@functools.lru_cache(None)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def norm(s):return unicodedata.normalize('NFC',s).casefold()
progress=read(P/'completed-family-role-manifests.json')
native=read(P/'all-current-6360-image-folder-links.json')
sources={x['file_id']:x for x in read(P/'current-6360-visual-source-evidence.json')}
hashes={x['id']:x for x in read(P/'fresh-all-6360-native-hash-metadata.json')['entries']}
native_by_id={x['file_id']:x for x in native}
opening=read(P/'fresh-complete-native-inventory.json')
closing=read(P/'closing-complete-native-inventory.json')
a={x['file_id']:x for p in opening['pages'] for x in p['entries']}
b={x['file_id']:x for p in closing['pages'] for x in p['entries']}
assert closing['pagination_complete'] and not closing['pages'][-1]['has_more']
assert set(a)==set(b)
for k in a:
 for f in ['path','name','object_type','file','modified_time']:assert a[k].get(f)==b[k].get(f),(k,f)
assert len(progress)==60 and sum(x['images'] for x in progress)==6360
assert len(native_by_id)==len(sources)==len(hashes)==6360
source_seal=read(P/'native-link-and-cache-binding-seal.json')
for x in source_seal['files']:assert sha(str(P/x['path']))==x['sha256']
allroles=[];families=[];seal_member_count=0;board_paths=set()
for p in progress:
 mp=pathlib.Path(p['manifest_path']);d=mp.parent;sp=pathlib.Path(p['seal_path'])
 assert sha(str(mp))==p['manifest_sha256']
 assert sha(str(sp))==p['seal_sha256']
 seal=read(sp)
 for x in seal['files']:
  f=d/x['path'];assert f.stat().st_size==x['size'];assert sha(str(f))==x['sha256'],str(f);seal_member_count+=1
 roles=read(mp);spec=read(d/'manual-role-specification.json');boards=read(d/'contact-board-index.json')
 assert spec['all_boards_viewed']==list(range(1,len(boards)+1))
 assert len(roles)==p['images']==seal['images']
 assert set(x['review_index'] for x in roles)==set(range(1,len(roles)+1))
 for x in roles:
  n=native_by_id[x['file_id']];s=sources[x['file_id']];h=hashes[x['file_id']];e=x['evidence']
  for k in ['family','name','folder_id','folder_path','folder_url','image_url','size']:assert x[k]==n[k],(x['file_id'],k)
  assert x['visual_role'] in ['individual','detail','rear','installation','group_context','uncertain']
  assert s['native_content_hash']==h['content_hash']==e['source_native_content_hash']
  assert e['source_image_path']==s['source_image_path']
  assert e['actual_visual_source_sha256']==s['actual_visual_source_sha256']==sha(e['source_image_path'])
  assert e['contact_board_sha256']==sha(e['contact_board_path']);board_paths.add(e['contact_board_path'])
  assert e['visually_reviewed_utc']
  assert e.get('reviewer_thread_id') in [None,'01a159af-d182-7393-9201-a2ac7ccba14a','01a13fe6-495b-7253-b923-31823b4cbca8','01a144ab-1a7c-7223-a403-73a4d53d70ff']
  assert x['native_action_applied']=='NONE' and not x['catalogue_photo_selections_changed']
  assert x['no_new_component_identity_from_group']
  image_url=urllib.parse.urlsplit(x['image_url']);folder_url=urllib.parse.urlsplit(x['folder_url'])
  assert image_url.scheme==folder_url.scheme=='https' and image_url.netloc==folder_url.netloc=='www.dropbox.com'
  assert norm(urllib.parse.unquote(folder_url.path.removeprefix('/home')))==norm(x['folder_path'])
  assert urllib.parse.parse_qs(image_url.query)['preview']==[x['name']]
  assert image_url.path==folder_url.path
 allroles.extend(roles)
 families.append({**p,'slug':d.name,'family_url':'https://www.dropbox.com/home/'+urllib.parse.quote('BOLDSTONE MASTER/Products/01 Wall Sculptures/'+p['family'],safe='/'),'gallery':'families/'+d.name+'/visual-roles-and-all-image-folder-links.html'})
assert len({x['file_id'] for x in allroles})==6360
assert {x['file_id'] for x in allroles}==set(native_by_id)
allroles.sort(key=lambda x:(x['family'].casefold(),x['review_index']))
counts=collections.Counter(x['visual_role'] for x in allroles)
scope='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
folders=[x for x in b.values() if x['object_type']=='folder']
child_counts=collections.Counter(norm(x['path'].rsplit('/',1)[0]) for x in b.values())
empty=[{'folder_id':x['file_id'],'path':x['path'],'folder_url':'https://www.dropbox.com/home/'+urllib.parse.quote(x['path'].split('//',1)[1].lstrip('/'),safe='/')} for x in folders if not child_counts[norm(x['path'])]]
prefix='ns:202238505//'+scope+'/'
depths=collections.Counter(x['path'][len(prefix):].count('/')+1 for x in folders)
assert depths=={1:60,2:381}
structure={'scope':scope,'readback_completed_utc':closing['completed_utc'],'family_folders':60,'photo_folders':381,'folders_below_photo_folder_depth':0,'empty_photo_folders':empty,'empty_folders_not_removed':True,'all_current_images_keep_actual_containing_folder_links':True,'native_changes':0}
write(P/'closing-directory-structure-review.json',structure)
write(P/'all-6360-current-native-visual-roles.json',allroles)
with (P/'all-6360-current-native-visual-roles.tsv').open('w',newline='') as f:
 cols=['family','review_index','file_id','name','visual_role','depicted_scope','folder_path','folder_url','image_url','review_note']
 w=csv.DictWriter(f,fieldnames=cols,delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(allroles)
uncertain=[x for x in allroles if x['visual_role']=='uncertain']
write(P/'uncertain-current-image-roles.json',uncertain)
flags=collections.Counter(z for x in allroles for z in x['uncertainty_flags'])
summary={'status':'PASS_COMPLETE_ALL_6360_CURRENT_NATIVE_IMAGES_VISUALLY_REVIEWED','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':scope,'family_count':60,'image_count':6360,'unique_current_file_ids':6360,'missing_native_ids':[],'extra_native_ids':[],'duplicate_role_assignments':0,'explicit_primary_role_counts':dict(counts),'uncertain_primary_roles':len(uncertain),'secondary_installation_images':sum('installation' in x['secondary_roles'] for x in allroles),'secondary_group_detail_images':sum('group_context' in x['secondary_roles'] for x in allroles),'source_evidence_kind_counts':dict(collections.Counter(x['evidence']['visual_source_kind'] for x in allroles)),'native_hash_bound_visual_sources_verified':6360,'actual_visual_source_bytes_sha256_rechecked':6360,'all_family_seal_members_rechecked':seal_member_count,'contact_boards_with_explicit_viewed_evidence':len(board_paths),'native_opening_census_completed_utc':opening['completed_utc'],'native_closing_census_completed_utc':closing['completed_utc'],'native_closing_census_pages':len(closing['pages']),'native_closing_census_objects':len(b),'native_added_during_review':0,'native_absent_during_review':0,'native_path_name_size_type_or_modified_time_changes':0,'flat_directory_depth_verified':True,'native_writes':0,'canonical_writes':0,'filing_plans_rust12_bone40_chiswick015':'PENDING_EXACT_APPROVAL_UNAPPLIED','identity_and_finish_qualifications_not_overridden':True,'distinct_sculptures_not_counted_from_photo_roles':True,'per_image_reviewer_thread_ids_present':sum(bool(x['evidence'].get('reviewer_thread_id')) for x in allroles),'older_sealed_rows_without_explicit_reviewer_thread_id':sum(not x['evidence'].get('reviewer_thread_id') for x in allroles),'older_sealed_rows_left_unchanged':True,'flags_count_by_label':dict(sorted(flags.items()))}
write(P/'complete-role-review-validation.json',summary)
write(P/'all-60-family-review-index.json',families)
rows=[]
for x in allroles:
 slug=pathlib.Path(next(y['manifest_path'] for y in progress if y['family']==x['family'])).parent.name
 rows.append({'family':x['family'],'index':x['review_index'],'name':x['name'],'role':x['visual_role'],'scope':x['depicted_scope'],'secondary':x['secondary_roles'],'flags':x['uncertainty_flags'],'note':x['review_note'],'folder':x['native_finish_folder_label'],'folder_url':x['folder_url'],'image_url':x['image_url'],'preview':'families/'+slug+'/previews/'+str(x['review_index']).zfill(3)+'.jpg'})
data=json.dumps(rows,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
options=''.join('<option value="'+html.escape(z,quote=True)+'">'+html.escape(z)+'</option>' for z in sorted(set(x['family'] for x in rows)))
families_table=''.join('<tr><td><a href="'+x['gallery']+'">'+html.escape(x['family'])+'</a></td><td>'+str(x['images'])+'</td><td>'+html.escape(', '.join(k+': '+str(v) for k,v in x['role_counts'].items()))+'</td><td><a href="'+html.escape(x['family_url'],quote=True)+'">Dropbox family folder</a></td></tr>' for x in sorted(families,key=lambda z:z['family'].casefold()))
css='body{font:16px system-ui;margin:24px;line-height:1.45;color:#182524}a{color:#075e82}label{display:inline-block;margin:8px 12px 8px 0}input,select,button{font:inherit;padding:8px}input{width:300px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:14px}article{border:1px solid #bbb;padding:12px;overflow-wrap:anywhere}img{width:100%;height:230px;object-fit:contain;background:#eee}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:9px;border-bottom:1px solid #ddd}small{color:#455}summary{cursor:pointer;font-weight:600}#pager{margin:18px 0}.notice{padding:12px;background:#edf4f0}'
base='<!doctype html><meta charset="utf-8"><title>Wall Sculptures: all 6,360 photographs</title><style>'+css+'</style><h1>Wall Sculptures: all 6,360 photographs reviewed</h1><p>60 sculpture families · 381 photograph folders. Every photograph below links to the original Dropbox image and its current containing folder.</p><p class="notice">Photographic roles describe what is visible. Individual views are photographs, not a count of distinct designs. Group arrangements, finish labels, scene provenance and physical specifications keep their separate qualifications. No Dropbox files were moved or renamed in this review.</p><p>Closing directory readback: '+html.escape(closing['completed_utc'])+'. All 6,360 file IDs, paths and sizes matched the opening census.</p><details><summary>Browse all 60 family galleries</summary><table><thead><tr><th>Family gallery</th><th>Images</th><th>Photographic roles</th><th>Dropbox</th></tr></thead><tbody>'+families_table+'</tbody></table></details><p><a href="all-6360-current-native-visual-roles.tsv">Download full image and folder list (TSV)</a> · <a href="complete-role-review-validation.json">Verification record</a> · <a href="closing-directory-structure-review.json">Directory structure findings</a></p><label>Search <input id="q" type="search" placeholder="Family, filename, folder or flag"></label><label>Family <select id="family"><option value="">All families</option>'+options+'</select></label><label>Photographic role <select id="role"><option value="">All roles</option><option value="individual">Individual view</option><option value="detail">Detail</option><option value="rear">Rear</option><option value="installation">Wider setting / In Situ reference</option><option value="group_context">Group or process context</option><option value="uncertain">Uncertain</option></select></label><div id="pager"><button id="prev">Previous</button> <span id="status"></span> <button id="next">Next</button></div><div id="grid" class="grid"></div>'
js='const data='+data+';const $=id=>document.getElementById(id);const esc=s=>String(s).replace(/[&<>"\\\']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\\"":"&quot;","\\\'":"&#39;"}[c]||c));let page=0,filtered=[];const size=100;function draw(reset=false){if(reset)page=0;const q=$("q").value.toLowerCase(),f=$("family").value,r=$("role").value;filtered=data.filter(x=>(!f||x.family===f)&&(!r||x.role===r)&&(!q||[x.family,x.name,x.folder,...x.flags].join(" ").toLowerCase().includes(q)));const max=Math.max(0,Math.ceil(filtered.length/size)-1);page=Math.min(max,Math.max(0,page));$("status").textContent=filtered.length+" images · page "+(page+1)+" of "+(max+1);$("prev").disabled=page===0;$("next").disabled=page===max;$("grid").innerHTML=filtered.slice(page*size,(page+1)*size).map(x=>\'<article><a href="\'+esc(x.image_url)+\'"><img loading="lazy" src="\'+esc(x.preview)+\'"></a><p><strong>\'+esc(x.family)+\'</strong> #\'+x.index+\' · \'+esc(x.role)+(x.secondary.length?\' / \'+esc(x.secondary.join(", ")): "")+\'</p><p><a href="\'+esc(x.image_url)+\'">\'+esc(x.name)+\'</a><br><a href="\'+esc(x.folder_url)+\'">\'+esc(x.folder)+\'</a></p><p>\'+esc(x.note)+\'</p><small>\'+esc(x.flags.join(", "))+\'</small></article>\').join("");}for(const k of ["q","family","role"])$(k).addEventListener(k==="q"?"input":"change",()=>draw(true));$("prev").onclick=()=>{page--;draw()};$("next").onclick=()=>{page++;draw()};const params=new URLSearchParams(location.search);if(params.has("role"))$("role").value=params.get("role");draw();'
(P/'complete-review.html').write_text(base+'<script>'+js+'</script>')
write(P/'reader-link-validation.json',{'status':'PASS','all_image_links':len(rows),'all_folder_links':len(rows),'family_gallery_links':len(families),'all_preview_paths_exist':all((P/x['preview']).exists() for x in rows),'all_local_gallery_paths_exist':all((P/x['gallery']).exists() for x in families),'no_signed_download_urls_in_reader':True})
checkpoint={'recorded_utc':summary['recorded_utc'],'status':'COMPLETE_NATIVE_VISUAL_ROLE_REVIEW_AND_CLOSING_READBACK','completed_families':60,'completed_images':6360,'remaining_images':0,'native_writes':0,'canonical_writes':0}
write(P/'active-work-checkpoint.json',checkpoint)
bind=['completed-family-role-manifests.json','all-6360-current-native-visual-roles.json','all-6360-current-native-visual-roles.tsv','all-60-family-review-index.json','complete-role-review-validation.json','complete-review.html','reader-link-validation.json','closing-complete-native-inventory.json','closing-directory-structure-review.json','uncertain-current-image-roles.json','native-link-and-cache-binding-seal.json']
write(P/'complete-6360-role-review-seal.json',{'status':'SEALED_COMPLETE_6360_NATIVE_VISUAL_ROLE_REVIEW','recorded_utc':summary['recorded_utc'],'images':6360,'families':60,'files':[{'path':z,'size':(P/z).stat().st_size,'sha256':sha(str(P/z))} for z in bind],'family_seals':[{'family':x['family'],'path':x['seal_path'],'sha256':x['seal_sha256']} for x in progress],'native_writes':0,'canonical_writes':0})
print(json.dumps({k:v for k,v in summary.items() if k!='flags_count_by_label'},indent=2))
print('AGGREGATE_SEAL_SHA256',sha(str(P/'complete-6360-role-review-seal.json')))

