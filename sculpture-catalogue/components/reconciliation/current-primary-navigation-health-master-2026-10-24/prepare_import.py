"""Import a sealed, scoped navigation observation without changing photo coverage."""
import copy, hashlib, json, shutil
from pathlib import Path
from datetime import datetime, timezone
H=Path(__file__).resolve().parent; B=H.parents[2]; OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text()); sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not (H/'import-summary.json').exists()
p=read(B/'current-master.json'); OLD=(B/p['register']).parent
assert p['register_sha256']=='06acd3dc3abb1146d79845dc5c895ee164f0c87ab97800fbe4d0e04e5be88f96'
D=B/'components/parallel-reviews/unpaired43-native-navigation-20261024T023834Z'
assert sha(D/'sealed-handoff.json')=='09928cf3dbed6ddc3efea7164bf978508ca7e6a7633bb42baa209274220e214d'
seal=read(D/'sealed-handoff.json')
for f in seal['files']: assert sha(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes'],f['path']
proposal=read(D/'correction-proposal.json'); nav=read(D/'navigation-review.json')
assert len(nav['rows'])==48 and nav['counts']['primary_files_verified']==46 and nav['counts']['containing_folders_verified']==48
assert proposal['native_operations']==[] and len(proposal['unavailable_primary_annotations'])==2
OUT.mkdir(parents=True,exist_ok=True); (H/'inputs').mkdir(exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],
 'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json',
 'source_report_verification':OLD/'report-verification.json','navigation_seal':D/'sealed-handoff.json'}
for k,n in [('audit','image-coverage-current.json'),('native_map','current-native-reference-map.json'),('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json'),('photo_source','photo-source-review.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json')]:files[k]=OLD/n
oldout=Path(read(files['source_report_verification'])['output_directory'])
files.update(source_count_summary=oldout/'current-count-summary.json',source_photo_requests=oldout/'remaining-photograph-requests.json')
for i,x in enumerate(seal['files']): files['evidence_'+str(i)]=Path(x['path'])
m={}
for k,f in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(f,snap);m[k]={'path':str(f),'snapshot':str(snap),'sha256':sha(f)}
write(H/'input-manifest.json',m)
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);assets=read(m['report_assets']['snapshot']);native=read(m['native_map']['snapshot']);reviews=read(m['report_reviews']['snapshot']);photo=read(m['photo_source']['snapshot'])
before={k:copy.deepcopy(x)for k,x in [('register',g),('audit',a),('assets',assets),('native_map',native),('reviews',reviews),('photo_source',photo)]}
norm={x['before']:x['after']for x in proposal['case_only_url_replacements']}
fid='id:cnqzTNngPVsAAAAAAAt4Sw'; folder='id:cnqzTNngPVsAAAAAAAyiQg'
row=next(r for r in nav['rows']if r['file_id']==fid)
oldpath=row['expected_file_path'];newpath=row['native_file_metadata']['path_display']
assert oldpath.casefold()==newpath.casefold() and oldpath!=newpath and row['folder_id']==folder
norm.update({oldpath:newpath,'ns:202238505/'+oldpath:'ns:202238505/'+newpath,
 oldpath.rsplit('/',1)[0]:newpath.rsplit('/',1)[0], 'ns:202238505/'+oldpath.rsplit('/',1)[0]:'ns:202238505/'+newpath.rsplit('/',1)[0]})
def project(x):
 if isinstance(x,list):
  for z in x:project(z)
 elif isinstance(x,dict):
  if x.get('file_id')==fid:
   for k in ['image_url','folder_url','path','display_path','path_display','folder_path']:
    if x.get(k)in norm:x[k]=norm[x[k]]
  for k,v in list(x.items()):
   if any(s in k.lower()for s in ['historical','history','before','prior_','previous_','owner_policy','owner_photo_decision','source_receipt','imported_','original_']):continue
   if k in ['specifications','master_fields','selling_details','current_commercial_policy']:continue
   project(v)
for key in ['options','components','source_review_reconciliation','original_specification_current_references','arrangement_context_references','current_listing_resolution_details','current_existing_listing_copy_projections']:project(g[key])
for key in ['source_sets','source_offer_edges']:
 for z in g[key]:project(z.get('current_primary_reference',{}))
for key in ['coverage','missing_pictures','identity_review']:project(a[key])
project(reviews);project(photo['requests']);project(assets[fid]);project(native['current_objects'][fid])
health={'schema':'boldstone.current-primary-navigation-health.v1','recorded_utc':nav['recorded_utc'],
 'status':'SCOPED_METADATA_READBACK_WITH_TWO_UNRESOLVED_PRIMARIES','scope':'48 existing options related to the43 captured Squarespace sources without a documented historical Shopify pair. This is not a whole-library navigation audit.',
 'source_packet':{'path':str(D/'sealed-handoff.json'),'sha256':sha(D/'sealed-handoff.json')},'counts':nav['counts'],
 'source_photo_coverage_unchanged':True,'new_capture_requests':0,'new_image_selections':0,'native_mutations':0,'physical_verifications':0,
 'qualifications':['Metadata verification does not inspect image content or certify a physical sculpture.','Available in Photo Coverage describes retained source-photo content; current Dropbox navigation is checked separately.','The two unresolved IDs were not returned by ID or exact path and were absent from their checked direct parent listings. Deletion, account-wide absence and web-URL failure are not inferred.'],
 'rows':copy.deepcopy(nav['rows'])}
for r in health['rows']:
 r['current_image_url']=norm.get(r['image_url'],r['image_url']);r['current_folder_url']=norm.get(r['folder_url'],r['folder_url'])
write(H/'current-primary-navigation-health.json',health)
ref={'path':str(H/'current-primary-navigation-health.json'),'sha256':sha(H/'current-primary-navigation-health.json'),'checked_options':48,'primary_files_verified':46,'containing_folders_verified':48,'unresolved_primaries':2,'scope':health['scope'],'source_photo_coverage_unchanged':True}
g['current_primary_navigation_health']=copy.deepcopy(ref);a['current_primary_navigation_health']=copy.deepcopy(ref)
for item in proposal['unavailable_primary_annotations']:
 o=next(o for o in g['options']if o['product_id']==item['product_id']);c=next(c for c in a['coverage']if c['option_id']==item['product_id'])
 assert o['file_id']==item['file_id'] and o['folder_id']==item['folder_id'] and c['individual']['status']=='Available'
 ann={**copy.deepcopy(item),'recorded_utc':nav['recorded_utc'],'folder_verified':True,'saved_image_url':o['image_url'],'saved_folder_url':o['folder_url'],'source_evidence':copy.deepcopy(ref),'global_deletion_inferred':False,'web_url_openability_verified':False,'source_photo_content_status_retained':'Available'}
 o['current_primary_navigation']=copy.deepcopy(ann);c['individual']['current_native_navigation']=copy.deepcopy(ann)
 assets[o['file_id']]['current_primary_navigation']=copy.deepcopy(ann);native['current_objects'][o['file_id']]['current_primary_navigation']=copy.deepcopy(ann)
summary={'status':'CURRENT_PRIMARY_NAVIGATION_HEALTH_IMPORTED_WITH_TWO_UNRESOLVED_REFERENCES','recorded_utc':now(),'checked_options':48,'verified_primary_files':46,'verified_containing_folders':48,'case_only_link_normalizations':1,'unresolved_primary_references':2,'new_photograph_requests':0,'new_image_selections':0,'new_photo_role_bindings':0,'new_physical_verifications':0,'native_or_platform_writes':0,'current_options':188,'retained_options':189,'working_component_identities':112}
g['latest_current_primary_navigation_import']=summary
g['latest_active_photo_source_review']['path']=str(H/'photo-source-review.json');write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='SOURCE_PHOTO_COVERAGE_PRESERVED_CURRENT_PRIMARY_NAVIGATION_CHECKED_SEPARATELY')
for k,f in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/f).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for f,x in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-assets.json',assets),('current-native-reference-map.json',native),('photo-review-queue.json',reviews),('import-summary.json',summary)]:write(H/f,x)
for f in ['guided-owner-review-state.json','pending-followups.json','physical-source-audit.json','original-verification.json','guided_review.py','working-entry-owner-provenance-sidecar.json']:shutil.copy2(OLD/f,H/f)
changes=[]
def diff(x,y,path,group):
 if isinstance(x,dict)and isinstance(y,dict):
  for k in x.keys()|y.keys():
   if k not in x:changes.append({'group':group,'path':path+[k],'before_exists':False,'current':y[k]})
   elif k not in y:changes.append({'group':group,'path':path+[k],'before_exists':True,'before':x[k],'current_exists':False})
   else:diff(x[k],y[k],path+[k],group)
 elif isinstance(x,list)and isinstance(y,list)and len(x)==len(y):
  for i,(u,v)in enumerate(zip(x,y)):diff(u,v,path+[i],group)
 elif x!=y:changes.append({'group':group,'path':path,'before_exists':True,'before':x,'current':y})
for k,x in [('register',g),('audit',a),('assets',assets),('native_map',native),('reviews',reviews),('photo_source',photo)]:diff(before[k],x,[],k)
write(H/'authorized-current-field-changes.json',changes)
write(H/'source-evidence-verification.json',{'status':'PASS','packet_files_verified':len(seal['files']),'native_metadata_observation':ref,'no_current_web_link_test':True,'source_original_bytes_not_rehashed_this_metadata_only_pass':True})
write(H/'evidence-manifest.json',{str(D/'sealed-handoff.json'):{'sha256':sha(D/'sealed-handoff.json')},**{x['path']:{'sha256':x['sha256']}for x in seal['files']}})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'case_only_replacements':norm,'option_ids':[x['product_id']for x in proposal['unavailable_primary_annotations']]})
write(H/'WORK_STATE.json',{'status':'PREPARED_NOT_PUBLISHED','scope':summary})
if not(H/'node_modules').exists():(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps({**summary,'metadata_fields_changed':len(changes)}))
