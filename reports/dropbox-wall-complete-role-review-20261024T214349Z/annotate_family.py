import collections,csv,datetime,hashlib,html,json,pathlib,sys
P=pathlib.Path(__file__).resolve().parent
def read(p):return json.loads(pathlib.Path(p).read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def write(p,x):pathlib.Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def run(slug):
 d=P/'families'/slug;spec=read(d/'manual-role-specification.json');rows=read(d/'indexed-current-images-and-links.json');boards=read(d/'contact-board-index.json');roles={}
 for role,indices in spec['visual_roles'].items():
  assert role in ['individual','detail','rear','installation','group_context','uncertain']
  for i in indices:assert i not in roles;roles[i]=role
 assert set(roles)=={r['review_index'] for r in rows}
 sources={r['file_id']:r for r in read(P/'current-6360-visual-source-evidence.json')};annotations=[];now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 focus={r['file_id']:r for r in read(d/'focus-check-originals.json')} if (d/'focus-check-originals.json').exists() else {}
 for r in rows:
  i=r['review_index'];role=roles[i];secondary=[]
  if i in spec.get('secondary_installation_indices',[]):secondary.append('installation')
  if role=='detail' and i in spec.get('group_detail_indices',[]):secondary.append('group_context')
  board=next(b for b in boards if i in b['indices']);scope='multiple' if role=='group_context' or i in spec.get('group_detail_indices',[]) else 'single' if role=='individual' else 'uncertain'
  if i in spec.get('single_depicted_scope_indices',[]):scope='single'
  if i in spec.get('uncertain_depicted_scope_indices',[]):scope='uncertain'
  flags=[x['flag'] for x in spec.get('flags',[]) if i in x['indices']]
  note=' '.join(x['note'] for x in spec.get('notes',[]) if i in x['indices'])
  source=sources[r['file_id']]
  annotations.append({**{k:r[k] for k in ['family','review_index','file_id','name','folder_id','folder_path','folder_url','image_url','size']},'visual_role':role,'secondary_roles':secondary,'depicted_scope':scope,'native_finish_folder_label':r['folder_path'].split('/')[-1],'component_finish_qualification':spec['component_finish_qualification'],'uncertainty_flags':flags,'review_note':note,'evidence':{'contact_board_path':board['path'],'contact_board_sha256':sha(board['path']),'source_image_path':source['source_image_path'],'actual_visual_source_sha256':source['actual_visual_source_sha256'],'source_native_content_hash':source['native_content_hash'],'visual_source_kind':source['visual_source_kind'],'actual_original_bytes_rehashed_current':source['original_bytes_rehashed_current'],'visually_reviewed_utc':spec.get('per_image_reviewed_utc',{}).get(str(i),now)},'installation_origin_or_permanence_verified':False,'catalogue_photo_selections_changed':False,'native_action_applied':'NONE','no_new_component_identity_from_group':True})
 for r in annotations:
  r['evidence']['reviewer_thread_id']=spec.get('reviewer_thread_id','01a159af-d182-7393-9201-a2ac7ccba14a')
  if r['file_id'] in focus:r['evidence']['additional_full_original_check']=focus[r['file_id']]
 write(d/'family-visual-roles.json',annotations)
 with (d/'family-visual-roles.tsv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['family','review_index','file_id','name','visual_role','depicted_scope','folder_id','folder_url','image_url','review_note'],delimiter='\t',extrasaction='ignore');w.writeheader();w.writerows(annotations)
 counts=collections.Counter(r['visual_role'] for r in annotations);summary={'family':spec['family'],'images':len(rows),'explicit_role_counts':counts,'all_current_family_images_visually_reviewed_and_annotated':True,'all_boards_viewed':spec['all_boards_viewed'],'native_metadata_and_source_hashes_current':True,'native_writes':0,'canonical_writes':0,'product_option_association_graph_not_created':True,'no_new_owner_identity_or_photo_requests':True,'specification':spec}
 write(d/'role-review-validation.json',summary)
 parts=['<!doctype html><meta charset="utf-8"><title>'+html.escape(spec['family'])+' visual roles</title><style>body{font:16px system-ui;margin:24px;line-height:1.45}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}article{border:1px solid #bbb;padding:10px;overflow-wrap:anywhere}img{width:100%;height:260px;object-fit:contain;background:#eee}</style><h1>'+html.escape(spec['family'])+': '+str(len(rows))+' current images classified</h1><p>No native moves or catalogue changes. Installation labels describe visible setting references; actual scene origin, permanent installation and physical finish verification are separate.</p><p>'+html.escape(str(dict(counts)))+'</p><div class="grid">']
 for r in annotations:
  parts.append('<article><a href="'+html.escape(r['image_url'],quote=True)+'"><img loading="lazy" src="previews/'+str(r['review_index']).zfill(3)+'.jpg"></a><p>#'+str(r['review_index'])+' <strong>'+r['visual_role']+'</strong>'+(' / '+', '.join(r['secondary_roles']) if r['secondary_roles'] else '')+'</p><p><a href="'+html.escape(r['image_url'],quote=True)+'">'+html.escape(r['name'])+'</a><br><a href="'+html.escape(r['folder_url'],quote=True)+'">'+html.escape(r['native_finish_folder_label'])+'</a></p><p>'+html.escape(r['review_note'])+'</p><small>'+html.escape(', '.join(r['uncertainty_flags']))+'</small></article>')
 parts.append('</div>');(d/'visual-roles-and-all-image-folder-links.html').write_text(''.join(parts))
 paths=[p for p in d.rglob('*') if p.is_file() and p.name!='family-role-seal.json'];seal={'recorded_utc':now,'family':spec['family'],'images':len(rows),'status':'SEALED_COMPLETE_CURRENT_FAMILY_VISUAL_ROLE_REVIEW','files':[{'path':str(x.relative_to(d)),'size':x.stat().st_size,'sha256':sha(x)} for x in sorted(paths)],'native_writes':0,'canonical_writes':0};write(d/'family-role-seal.json',seal)
 progresspath=P/'completed-family-role-manifests.json';progress=read(progresspath) if progresspath.exists() else [];progress=[r for r in progress if r['family']!=spec['family']];progress.append({'family':spec['family'],'images':len(rows),'manifest_path':str(d/'family-visual-roles.json'),'manifest_sha256':sha(d/'family-visual-roles.json'),'seal_path':str(d/'family-role-seal.json'),'seal_sha256':sha(d/'family-role-seal.json'),'role_counts':counts});write(progresspath,progress)
 print(json.dumps({'family':spec['family'],'images':len(rows),'roles':counts,'manifest_sha256':sha(d/'family-visual-roles.json'),'seal_sha256':sha(d/'family-role-seal.json'),'all_6360_role_annotations_completed_so_far':sum(x['images'] for x in progress)},indent=2),flush=True)
if __name__=='__main__':run(sys.argv[1])
