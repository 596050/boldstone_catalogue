"""Import three approved same-ID paths and exact Wall Circle history observations."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
def namespace(p):return 'ns:202238505/'+display(p)
assert not(H/'import-summary.json').exists()
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=Path(read(OLD/'report-verification.json')['output_directory'])
assert sha(B/'current-master.json')=='1b1025e30e4e22ed362e48fec48e2266c895a086758bb5f6edcdb5d85ec82c1e'
assert p['register_sha256']=='8826312ebe27d675e7477925d849be3a3bc14d71cfdaa2f6b310c594b2a64ccf'
D=B.parent/'reports/dropbox-moonspirals-three-pair-moves-20261024T143451Z'
W=B/'components/parallel-reviews/wall-circle-reference-history-01a16dbc-20261024T143807Z'
assert sha(D/'execution-seal.json')=='e174f2fa0b0572d6461fb9d8b61a2e9ee2b14986cad75d836e99c1ed861cbd8d'
assert sha(D/'current-reference-overlay.json')=='943477bb3e9d2f3e2e703b65ef1e4da80cb1b45052c1d67488252aef00635a34'
assert sha(W/'sealed-findings.json')=='faf213e28f8f2aec5bfd9e96ca70f620710612ce334178404ec367c8135d66d3'
overlay=read(D/'current-reference-overlay.json');seal=read(D/'execution-seal.json');wseal=read(W/'sealed-findings.json');finding=read(W/'findings.json')
assert overlay['status']==seal['status']=='COMPLETE_VERIFIED'
assert not overlay['deleted_files']and not overlay['deleted_folders']and not overlay['created_folders']and not overlay['prefix_maps']
assert finding['source_register_sha256']==p['register_sha256']and finding['native_or_platform_writes']==0
(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','moonspirals_overlay':D/'current-reference-overlay.json','moonspirals_seal':D/'execution-seal.json','wall_circle_seal':W/'sealed-findings.json'}
for key,name in [('audit','image-coverage-current.json'),('native_map','current-native-reference-map.json'),('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json'),('review_state','guided-owner-review-state.json'),('pending','pending-followups.json'),('photo_source','photo-source-review.json'),('physical_audit','physical-source-audit.json'),('originals','original-verification.json'),('primary_health','current-primary-navigation-health.json'),('working_groups','working-design-group-projection.json')]:files[key]=OLD/name
for i,r in enumerate(seal['receipts']):
 assert sha(r['path'])==r['sha256']and Path(r['path']).stat().st_size==r['size'],r['path'];files['moonspirals_receipt_'+str(i)]=Path(r['path'])
for i,r in enumerate(wseal['files']):assert sha(r['path'])==r['sha256'];files['wall_circle_receipt_'+str(i)]=Path(r['path'])
m={}
for key,path in files.items():
 snap=H/'inputs'/(key+'.before');shutil.copy2(path,snap);m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
write(H/'input-manifest.json',m)
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);assets=read(m['report_assets']['snapshot']);health=read(m['primary_health']['snapshot'])
objects={o['file_id']:o for o in overlay['objects']};changed={i:o for i,o in objects.items()if o['old_path']!=o['current_path']}
expected_ids={'id:cnqzTNngPVsAAAAAAAucCw','id:cnqzTNngPVsAAAAAAAuR4Q','id:cnqzTNngPVsAAAAAAAuigw'}
assert set(changed)==expected_ids and len(objects)==157
assert all(o['object_type']=='file'and o['old_parent_id']=='id:cnqzTNngPVsAAAAAAAyi8Q'and o['current_parent_id']=='id:cnqzTNngPVsAAAAAAAyi8w'for o in changed.values())
assert overlay['summary']=={'files':148,'folders':9,'bytes':416784106,'moved_file_paths':3,'moved_actual_parents':3,'created_folders':0,'folder_renames':0,'all_original_bytes_preserved':True}
assert all(not v for v in overlay['catalogue_projection']['current_option_offer_coverage_moved_ID_occurrences'].values())
def blockhash(data):return hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()for i in range(0,len(data),4194304))).hexdigest()
verified=seal['verified_post_move_originals'];assert len(verified)==148
verified_ids=set();fresh=[]
for x in verified:
 ident=x.get('file_id',x.get('id'));assert ident not in verified_ids and ident in objects;verified_ids.add(ident)
 assert x['size']==objects[ident]['size']and x['sha256']==objects[ident]['sha256']and x['dropbox_content_hash']==objects[ident]['dropbox_content_hash']
 if ident in changed:
  path=x.get('path',x.get('local_path'));data=Path(path).read_bytes();assert sha(path)==x['sha256']and len(data)==x['size']and blockhash(data)==x['dropbox_content_hash'];fresh.append({'file_id':ident,'path':path,'sha256':x['sha256'],'bytes':len(data),'dropbox_content_hash':x['dropbox_content_hash']})
assert len(fresh)==3 and sum(objects[i]['size']for i in verified_ids)==416784106
history=[];map_unrepresented=[]
root=overlay['source_scope'];assert root=='/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moonspirals'
for ident,obj in objects.items():
 assert obj['current_path'].startswith(root+'/')and obj['old_name']==obj['current_name']and obj['old_client_modified']==obj['current_client_modified']
 before=copy.deepcopy(native['current_objects'].get(ident))
 if ident in changed:
  assert before and display(before['path'])==obj['old_path']and before['parent_id']==obj['old_parent_id']
  cur={**before,'path':namespace(obj['current_path']),'display_path':obj['current_path'],'parent_id':obj['current_parent_id'],'current_navigation_source':str(D/'current-reference-overlay.json')};native['current_objects'][ident]=cur
  history.append({'file_id':ident,'before':before,'current':copy.deepcopy(cur)})
 elif before:assert display(before['path'])==obj['current_path']and before.get('parent_id')==obj['current_parent_id'],ident
 else:map_unrepresented.append(ident)
 if ident in changed:
  for path in [obj['old_path'],obj['current_path']]:native['old_path_to_id'][path.casefold()]=ident
  asset=assets[ident];assert display(asset['path'])==obj['old_path']and asset['folder_id']==obj['old_parent_id']and asset['bytes']==obj['size']
  asset.setdefault('historical_same_id_navigation',[]).append({k:asset.get(k)for k in ['path','display_path','folder_path','folder_id','image_url','folder_url']})
  asset.update(path=namespace(obj['current_path']),display_path=obj['current_path'],folder_id=obj['current_parent_id'],folder_path=namespace(obj['current_path'].rsplit('/',1)[0]),image_url=obj['current_native_url'],folder_url='https://www.dropbox.com/home'+quote(obj['current_path'].rsplit('/',1)[0],safe='/'),modified_time=obj['current_server_modified'])
native['status']='CURRENT_MAP_WITH_THREE_APPROVED_MOONSPIRALS_PAIR_PATHS'
native.setdefault('verified_path_change_history',[]).append({'overlay':str(D/'current-reference-overlay.json'),'sha256':sha(D/'current-reference-overlay.json'),'objects':history,'created_native_folders':0,'native_family_originals_with_sealed_postmove_hash_readback':148,'fresh_moved_originals_rehashed_by_importer':3,'unchanged_original_rehashes_reported_by_native_lane':145,'all_library_source_bytes_rehashed':False,'existing_unrepresented_scoped_ids_not_added':map_unrepresented})
# Current option/coverage selections contain none of the three moved IDs.
def occurrences(x,path=''):
 found=[]
 if isinstance(x,dict):
  if x.get('file_id')in changed:found.append(path)
  for k,v in x.items():
   if any(s in k.lower()for s in ['history','historical','before','prior_','imported_']):continue
   found.extend(occurrences(v,path+'/'+k))
 elif isinstance(x,list):
  for i,v in enumerate(x):found.extend(occurrences(v,path+'/'+str(i)))
 return found
assert not occurrences(g['options'])and not occurrences(a['coverage'])
wall_rows={r['option_id']:r for r in finding['rows']};assert set(wall_rows)=={'BSI-D5A939264C82','BSI-65520F070145'}
wall_observations={}
for option in g['options']:
 if option['product_id']not in wall_rows:continue
 r=wall_rows[option['product_id']];assert option==r['canonical_option_guard']and option['file_id']==r['file_id']and option['folder_id']==r['folder_id']
 local=r['existing_local_original'];data=Path(local['path']).read_bytes();assert hashlib.sha256(data).hexdigest()==local['sha256']and len(data)==local['size']and blockhash(data)==local['dropbox_content_hash']==r['latest_available_revision']['content_hash']
 prior=copy.deepcopy(option['current_primary_navigation'])
 note='Exact stable-ID Dropbox revision history explicitly marks the saved primary deleted at '+r['server_deleted_utc']+'. A previously downloaded Master-source original matches the latest available revision size and content hash. Its local historical copy is retained; no restoration or replacement selection occurred. Deletion actor and reason are unknown. The Wall Circle owner hold remains.'
 obs={**prior,'status':'SAVED_PRIMARY_ID_MARKED_DELETED_IN_AVAILABLE_DROPBOX_HISTORY','evidence':note,'recorded_utc':finding['recorded_utc'],'previous_navigation_observation':prior,'deletion_observed_in_exact_id_history':True,'server_deleted_utc':r['server_deleted_utc'],'deletion_actor':None,'deletion_reason':None,'available_revision_count':r['available_revision_count'],'history_response_has_more':False,'latest_available_revision':r['latest_available_revision'],'existing_local_historical_original':local,'restored_to_dropbox':False,'replacement_selected':False,'current_primary_verified':False,'owner_hold_preserved':True,'source_evidence':{'path':str(W/'sealed-findings.json'),'sha256':sha(W/'sealed-findings.json')},'source_photo_content_status_retained':'Available','global_deletion_inferred':False}
 option['current_primary_navigation']=obs;wall_observations[option['product_id']]=obs
 cov=next(x for x in a['coverage']if x['option_id']==option['product_id']);assert cov['individual']['current_native_navigation']==prior;cov['individual']['current_native_navigation']=copy.deepcopy(obs)
 row=next(x for x in health['rows']if x['product_id']==option['product_id']);row['previous_navigation_observation']=copy.deepcopy(row);row.update(navigation_status=obs['status'],qualification=note,server_deleted_utc=r['server_deleted_utc'],deletion_observed_in_exact_id_history=True,latest_available_revision=r['latest_available_revision'],available_revision_count=r['available_revision_count'],existing_local_historical_original=local,restored_to_dropbox=False,replacement_selected=False,current_primary_verified=False)
health['status']='SCOPED_METADATA_AND_HISTORY_READBACK_WITH_TWO_SAVED_PRIMARIES_MARKED_DELETED';health['latest_history_recorded_utc']=finding['recorded_utc'];health['history_source_packet']={'path':str(W/'sealed-findings.json'),'sha256':sha(W/'sealed-findings.json')};health['counts']['saved_primary_ids_marked_deleted_in_available_history']=2;health['counts']['matching_local_historical_originals']=2
health['qualifications'][-1]='Two exact saved IDs have explicit server-deleted flags and clocks in available Dropbox revision history. Matching previously downloaded originals remain historical source evidence. No restore, replacement selection, actor attribution, account-wide absence or web-URL success is inferred.'
write(H/'current-primary-navigation-health.json',health);write(H/'wall-circle-history-observations.json',{'source':health['history_source_packet'],'rows':wall_observations,'selected_reference_ids_unchanged':True,'restorations':0,'replacement_selections':0})
g['current_primary_navigation_health']={**g['current_primary_navigation_health'],'path':str(H/'current-primary-navigation-health.json'),'sha256':sha(H/'current-primary-navigation-health.json'),'saved_primary_ids_marked_deleted_in_available_history':2,'matching_local_historical_originals':2}
a['current_primary_navigation_health']=copy.deepcopy(g['current_primary_navigation_health'])
summary={'status':'THREE_MOONSPIRALS_PAIR_PATHS_AND_TWO_WALL_CIRCLE_HISTORY_OBSERVATIONS_IMPORTED','recorded_utc':now(),'current_options':188,'retained_options':189,'retained_component_id_records':112,'working_design_groups':110,'changed_file_paths':3,'actual_file_parent_changes':3,'created_native_folders':0,'existing_folder_renames':0,'source_family_files':148,'source_family_bytes':416784106,'source_family_folders':9,'fresh_moved_originals_rehashed_by_importer':3,'unchanged_originals_rehashed_by_native_lane':145,'historical_wall_circle_originals_rehashed_by_importer':2,'saved_primary_ids_marked_deleted_in_available_history':2,'selected_primary_file_ids_changed':0,'new_image_selections':0,'photo_role_bindings_changed':0,'new_photo_bindings':0,'new_physical_verifications':0,'native_or_platform_writes_by_importer':0,'active_photo_requests':0,'held_context':22,'held_series':1,'deferred_identity':1,'required_picture_actions':24,'optional_series':70,'new_platform_matches':0}
g['latest_moonspirals_pair_native_navigation_import']=summary;g['latest_wall_circle_exact_history_observation']=health['history_source_packet']
g['latest_active_photo_source_review'].update(path=str(H/'photo-source-review.json'),sha256=sha(OLD/'photo-source-review.json'))
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='SAME_SOURCE_COVERAGE_WITH_CURRENT_NATIVE_HISTORY_QUALIFICATIONS')
for k,f in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/f).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
assert g['summary']==read(m['master_register']['snapshot'])['summary']and a['counts']==read(m['audit']['snapshot'])['counts']
for f,v in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('import-summary.json',summary),('path-change-history.json',history),('current-reference-fields-refreshed.json',[]),('source-evidence-verification.json',{'status':'PASS','sealed_native_receipts':len(seal['receipts']),'sealed_wall_circle_receipts':len(wseal['files']),'family_originals_with_sealed_metadata_and_hash_receipts':148,'family_bytes':416784106,'fresh_moved_originals_rehashed_by_importer':fresh,'historical_wall_circle_originals_rehashed_by_importer':2,'native_or_platform_writes_by_importer':0,'new_physical_verifications':0})]:write(H/f,v)
for f in ['photo-review-queue.json','guided-owner-review-state.json','pending-followups.json','photo-source-review.json','physical-source-audit.json','original-verification.json','guided_review.py','working-entry-owner-provenance-sidecar.json','working-design-group-projection.json','physical-checklist-label-alignment.json']:shutil.copy2(OLD/f,H/f)
write(H/'evidence-manifest.json',{str(x['path']):{'sha256':x['sha256']}for k,x in m.items()if k.startswith(('moonspirals_','wall_circle_'))})
write(H/'projection-index.json',{'old_output':str(oldout),'new_output':str(OUT),'option_ids':[],'changed_native_objects':changed,'current_reference_fields':[],'wall_circle_option_ids':list(wall_rows),'source_family_overlay':str(D/'current-reference-overlay.json')})
write(H/'WORK_STATE.json',{'status':'FROZEN_CANDIDATE_DATA','publisher_thread':'01a144ab-1a7c-7223-a403-73a4d53d70ff','scope':'3 approved same-ID paths;2 exact-ID server-deleted history observations; no source selections, identity groups, working fields or holds changed'})
(H/'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules',target_is_directory=True)
print(json.dumps(summary))
