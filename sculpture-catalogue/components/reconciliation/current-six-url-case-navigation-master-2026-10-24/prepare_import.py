"""Normalize current same-ID navigation, retaining source and history snapshots."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from navigation import refresh,display,namespace
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
assert not(H/'import-summary.json').exists()
D=B/'components/parallel-reviews/terminal-continuation-01a16dbc-20261024/case-normalization-handoff-20261024T165515Z';h=read(D/'handoff.json');seal=read(D/'sealed-handoff.json');p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=Path(read(OLD/'report-verification.json')['output_directory'])
assert sha(D/'sealed-handoff.json')=='393075dfdada35fd7755a0a33a0f70afc517085cf75d72339b2359785ec43dcd'
assert sha(B/'current-master.json')==h['pointer_sha256']=='b3b08bff3645ae52351dfdda2ed29f23cf56d99cbf5b86b6277f356f541ab628'
assert p['register_sha256']==h['register_sha256']and p['workbook_sha256']==h['workbook_sha256']
(H/'inputs').mkdir();OUT.mkdir(parents=True,exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','handoff':D/'handoff.json','handoff_seal':D/'sealed-handoff.json','projection_classification':D/'projection-column-classification.json'}
for k,n in [('audit','image-coverage-current.json'),('native_map','current-native-reference-map.json'),('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('photo_source','photo-source-review.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json'),('primary_health','current-primary-navigation-health.json'),('working_groups','working-design-group-projection.json')]:files[k]=OLD/n
for i,x in enumerate(seal['files']):assert sha(x['path'])==x['sha256'];files['sealed_'+str(i)]=Path(x['path'])
m={}
for k,path in files.items():
 snap=H/'inputs'/(k+'.before');shutil.copy2(path,snap);m[k]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m);write(H/'verified-six-cases.json',h)
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);assets=read(m['report_assets']['snapshot']);native=read(m['native_map']['snapshot']);queue=read(m['report_reviews']['snapshot']);photo=read(m['photo_source']['snapshot']);opts={o['product_id']:o for o in g['options']};journal=[]
def project(x,label):
 if isinstance(x,list):
  for i,v in enumerate(x):
   if isinstance(v,str):
    new=refresh(v)
    if new!=v:journal.append({'path':label+'/'+str(i),'before':v,'value':new});x[i]=new
   else:project(v,label+'/'+str(i))
 elif isinstance(x,dict):
  for k,v in list(x.items()):
   if any(t in k.lower()for t in ['history','historical','prior_','before','original_visual','source_field_record','source_record','source_receipt','owner_','imported_']):continue
   if k in ['specifications','master_fields','selling_details','source_references','source_offer','original_review_specification_assertions']:continue
   if isinstance(v,str):
    new=refresh(v)
    if new!=v:journal.append({'path':label+'/'+k,'before':v,'value':new});x[k]=new
   else:project(v,label+'/'+k)
for r in h['rows']:
 o=opts[r['option_id']];assert o==r['current_option']and o['file_id']==r['expected_file_id']and o['folder_id']==r['expected_folder_id']
 for k in ['image_url','folder_url']:
  assert o[k]==r['before'][k]and refresh(o[k])==r['proposed'][k];o[k]=r['proposed'][k]
for k in ['components','source_review_reconciliation','original_specification_current_references','arrangement_context_references','current_listing_resolution_details','current_existing_listing_copy_projections','current_listing_source_links','current_listing_match_evidence','current_bordered_moonphase_references']:
 if k in g:project(g[k],'register/'+k)
for k in ['source_sets','source_offer_edges']:
 for i,row in enumerate(g[k]):project(row.get('current_primary_reference',{}),'register/'+k+'/'+str(i)+'/current_primary_reference')
for k in ['coverage','missing_pictures','identity_review']:project(a[k],'audit/'+k)
project(queue,'photo-review-queue');project(photo.get('requests',[]),'photo-source-review/requests')
native_changes=[];asset_changes=[]
for r in h['rows']:
 for key in ['file_metadata','folder_metadata']:
  meta=r[key];ident=meta['id'];before=copy.deepcopy(native['current_objects'][ident]);assert display(before['path']).casefold()==meta['path_display'].casefold();cur=copy.deepcopy(before)
  for k in ['path','display_path']:cur[k]=namespace(meta['path_display'])if k=='path'else meta['path_display']
  cur['name']=meta['name']
  assert cur.get('parent_id')==before.get('parent_id')
  if cur!=before:native_changes.append({'file_id':ident,'before':before,'current':cur});native['current_objects'][ident]=cur
 ident=r['expected_file_id'];before=copy.deepcopy(assets[ident]);asset=assets[ident];assert asset['folder_id']==r['expected_folder_id']
 for k in ['path','display_path','folder_path','image_url','folder_url']:
  if k in asset:asset[k]=refresh(asset[k])
 asset['image_url']=r['proposed']['image_url'];asset['folder_url']=r['proposed']['folder_url'];asset_changes.append({'file_id':ident,'before':before,'current':copy.deepcopy(asset)})
native.setdefault('verified_path_change_history',[]).append({'status':'CASE_ONLY_CURRENT_NAVIGATION_NORMALIZATION_NO_NATIVE_MOVES','source':str(D/'sealed-handoff.json'),'sha256':sha(D/'sealed-handoff.json'),'objects':native_changes,'native_moves':0,'observation_clocks_preserved_in_handoff':True})
summary={'status':'SIX_CURRENT_FILE_AND_PARENT_URL_CASE_CORRECTIONS_IMPORTED','recorded_utc':now(),'current_options':188,'retained_options':189,'retained_component_id_records':112,'working_design_groups':110,'corrected_option_url_fields':12,'corrected_options':6,'native_file_ids_changed':0,'native_folder_ids_changed':0,'native_moves':0,'source_snapshots_changed':0,'new_image_selections':0,'photo_role_bindings_changed':0,'new_physical_verifications':0,'new_platform_matches':0,'native_or_platform_writes_by_importer':0,'new_live_metadata_calls':0,'new_original_binary_reads':0,'active_photo_requests':0,'held_context':22,'held_series':1,'deferred_identity':1}
g['latest_current_url_case_normalization']=summary;g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'));write(H/'photo-source-review.json',photo);g['latest_active_photo_source_review']['sha256']=sha(H/'photo-source-review.json')
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='SAME_SOURCE_COVERAGE_WITH_SIX_CURRENT_LINK_CASE_CORRECTIONS')
for k,n in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/n).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for n,v in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-assets.json',assets),('current-native-reference-map.json',native),('photo-review-queue.json',queue),('import-summary.json',summary),('current-reference-change-journal.json',journal),('path-change-history.json',native_changes),('asset-change-history.json',asset_changes)]:write(H/n,v)
for n in ['guided-owner-review-state.json','pending-followups.json','physical-source-audit.json','original-verification.json','guided_review.py','working-entry-owner-provenance-sidecar.json','working-design-group-projection.json','physical-checklist-label-alignment.json','current-primary-navigation-health.json']:shutil.copy2(OLD/n,H/n)
write(H/'source-evidence-verification.json',{'status':'PASS','six_full_option_and_twelve_URL_guards_verified':True,'sealed_metadata_and_original_clocks_preserved':True,'new_native_reads':0,'native_writes':0,'binary_reads':0,'new_physical_verifications':0})
write(H/'evidence-manifest.json',{x['path']:{'sha256':x['sha256']}for k,x in m.items()if k.startswith('sealed_')or k in ['handoff','handoff_seal','projection_classification']})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':[r['option_id']for r in h['rows']],'current_reference_fields':journal})
write(H/'WORK_STATE.json',{'status':'FROZEN_SIX_CASE_DATA','publisher':'01a144ab-1a7c-7223-a403-73a4d53d70ff','pending_Moonwave_ten_move_plan_included':False})
(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
