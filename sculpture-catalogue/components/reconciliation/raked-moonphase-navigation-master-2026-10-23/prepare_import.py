"""Import two sealed native-navigation packets and one isolated owner-review batch."""
import copy,hashlib,importlib.util,json,posixpath,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(path):return '/'+path.split('//',1)[1].lstrip('/')if path.startswith('ns:')else path
def metadata(r):
 assert not r.get('isError');s=r.get('structuredContent',r);return s[s['metadata_type']]
def native_receipts(seal):return seal.get('native_receipts',seal.get('receipts',[]))
assert not(H/'import-summary.json').exists(),'Already prepared'
(H/'inputs').mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
p=read(B/'current-master.json');OLD=(B/p['register']).parent;oldout=(B/p['current_image_review_links']['all_links']).parent
review=B/'components/parallel-reviews/series-terminal-walkthrough-20261023T212756Z';raked=B.parent/'reports/dropbox-raked-moonphase-three-changes-2026-10-23';workshop=B.parent/'reports/dropbox-mixed-workshop-overview-relocation-2026-10-23'
files={'pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':OLD/'image-coverage-current.json','native_map':OLD/'current-native-reference-map.json','report_assets':OLD/'current-assets.json','report_reviews':OLD/'photo-review-queue.json','review_state':OLD/'guided-owner-review-state.json','pending':OLD/'pending-followups.json','review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','source_report_verification':OLD/'report-verification.json','source_count_summary':oldout/'current-count-summary.json','source_photo_requests':oldout/'remaining-photograph-requests.json','raked_overlay':raked/'current-reference-overlay.json','raked_seal':raked/'execution-seal.json','workshop_overlay':workshop/'current-reference-overlay.json','workshop_seal':workshop/'execution-seal.json','owner_batch':review/'sealed-owner-decisions-batch01.json','series_deferral':review/'dune-copper-owner-deferral.json','bronze_finish':review/'pewter-courtyard-right-panel-owner-bronze.json'}
if (H/'input-manifest.json').exists():
 assert '--resume-frozen-inputs'in sys.argv;m=read(H/'input-manifest.json')
 for key,item in m.items():assert sha(item['path'])==sha(item['snapshot'])==item['sha256'],key
else:
 m={}
 for key,path in files.items():
  snap=H/'inputs'/(key+'.before');shutil.copy2(path,snap);m[key]={'path':str(path),'snapshot':str(snap),'sha256':sha(path)}
 write(H/'input-manifest.json',m)
g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);assets=read(m['report_assets']['snapshot']);reviews=read(m['report_reviews']['snapshot']);state=read(m['review_state']['snapshot']);pending=read(m['pending']['snapshot']);old_native=copy.deepcopy(native)
overlays=[read(m[k]['snapshot'])for k in ['raked_overlay','workshop_overlay']];seals=[read(m[k]['snapshot'])for k in ['raked_seal','workshop_seal']]
for overlay,seal in zip(overlays,seals):
 assert overlay['status']=='COMPLETE_VERIFIED'and seal['status']in ['COMPLETE_VERIFIED','SEALED_COMPLETE_VERIFIED']and not overlay['deleted_folders']and not overlay['deleted_files']
 assert len(native_receipts(seal))==18 and len(seal['review_receipts'])==5
 for item in native_receipts(seal)+seal['review_receipts']:assert sha(item['path'])==item['sha256'],item['path']
objects={x['file_id']:x for overlay in overlays for x in overlay['objects']};changed={i:x for i,x in objects.items()if x['old_path']!=x['current_path']};assert len(changed)==70
assert sum(x['object_type']=='file'for x in changed.values())==66
assert sum(x['object_type']=='file'and x['old_parent_id']!=x['current_parent_id']for x in changed.values())==8
assert sum(x['object_type']=='folder'and x['old_path']is not None and x['old_parent_id']!=x['current_parent_id']for x in changed.values())==1
fresh={}
for item in read(H/'fresh-metadata.json')['records']:fresh[item['id']]=metadata(item['result'])
we=read(H/'fresh-workshop-evidence.json')
for item in we['metadata']:fresh[item['id']]=metadata(item['result'])
for ident,md in fresh.items():
 if ident in objects:
  obj=objects[ident];assert display(obj['current_path'])==md['path_display']and obj['current_name']==md['name']
  if obj['object_type']=='file':assert obj['size']==md['size']and obj['current_server_modified']==md['server_modified']and obj['current_client_modified']==md['client_modified']
fresh_lists=[]
for item in read(H/'fresh-family-listings.json')['records']:
 r=item['result'];assert not r.get('isError')and not r['structuredContent']['has_more'];entries=r['structuredContent']['entries'];fresh_lists.extend(entries)
family_root_ids={x['file_id']for x in overlays[0]['preserved_family_roots']}
expected={x['file_id']:x for x in overlays[0]['objects']if x['file_id']not in family_root_ids}
assert {x['file_id']for x in fresh_lists}==set(expected)and len(expected)==458
for item in fresh_lists:
 o=expected[item['file_id']];assert item['path']==o['current_path']and item['name']==o['current_name']
 if item['object_type']=='file':assert item['file']['size']==o['size']and item['client_modified']==o['current_client_modified']and item['modified_time']==o['current_server_modified']
wl={}
for item in we['lists']:
 r=item['result'];assert not r.get('isError')and not r['structuredContent']['has_more'];wl[item['path']]=r['structuredContent']['entries']
wp=overlays[1]['prefix_maps'][0];wfiles={i for i,x in changed.items()if x['object_type']=='file'and x['current_parent_id']==wp['file_id']}
assert len(wfiles)==3 and {x['file_id']for x in wl[wp['current_path']]}==wfiles
assert wp['file_id']in{x['file_id']for x in wl['/BOLDSTONE MASTER/Products/Workshop and Moulding']}
assert wp['file_id']not in{x['file_id']for x in wl['/BOLDSTONE MASTER/Products/01 Wall Sculptures/Deco Palm and Spiral']}
path_history=[];new_map_ids=[]
for ident,obj in changed.items():
 before=copy.deepcopy(native['current_objects'].get(ident))
 if before:assert before['path']==obj['old_path'],ident
 if before is None:new_map_ids.append(ident)
 current={**(before or{}),'file_id':ident,'object_type':obj['object_type'],'name':obj['current_name'],'path':obj['current_path'],'display_path':display(obj['current_path']),'parent_id':obj['current_parent_id'],'size':obj['size'],'current_navigation_source':'Sealed approved native move/rename; no catalogue identity inference'}
 if ident in fresh and 'rev'in fresh[ident]:current['rev']=fresh[ident]['rev']
 native['current_objects'][ident]=current
 for path in [obj['old_path'],obj['current_path']]:
  if path:native['old_path_to_id'][display(path).casefold()]=ident
 path_history.append({'file_id':ident,'before':before or{'path':obj['old_path'],'parent_id':obj['old_parent_id']},'current':current})
 if obj['object_type']=='file':
  asset=assets[ident];assert asset['path']==obj['old_path']and asset['folder_id']==obj['old_parent_id']and asset['bytes']==obj['size']
  asset.setdefault('historical_same_id_navigation',[]).append({'path':asset['path'],'folder_id':asset['folder_id'],'image_url':asset['image_url'],'folder_url':asset['folder_url']})
  asset.update(path=obj['current_path'],display_path=display(obj['current_path']),folder_id=obj['current_parent_id'],folder_path=obj['current_path'].rsplit('/',1)[0],image_url='https://www.dropbox.com/preview'+quote(display(obj['current_path']),safe='/'),folder_url='https://www.dropbox.com/home'+quote(display(obj['current_path'].rsplit('/',1)[0]),safe='/'),modified_time=obj['current_server_modified'])
post=read(raked/'complete-post-state.json');root=metadata(post['raked_root_metadata']);wall=metadata(post['wall_root_metadata']);assert root['path_display'].rsplit('/',1)[0]==wall['path_display']
native['current_objects'].setdefault(root['id'],{'file_id':root['id'],'object_type':'folder','name':root['name'],'path':'ns:202238505/'+root['path_display'],'display_path':root['path_display'],'parent_id':wall['id'],'size':0})
native['status']='CURRENT_MAP_WITH_RAKED_MOONPHASE_AND_WORKSHOP_NAVIGATION';native.setdefault('verified_path_change_history',[]).append({'overlays':[{'path':m[k]['path'],'sha256':m[k]['sha256']}for k in ['raked_overlay','workshop_overlay']],'objects':path_history,'new_native_folder_ids':['id:cnqzTNngPVsAAAAAAA6Vrg'],'existing_native_ids_newly_represented_in_scoped_map':new_map_ids,'all_source_bytes_rehashed':False})
def refresh_ref(ref,preserve_display_name=False):
 ident=ref.get('file_id')
 if ident in changed and changed[ident]['object_type']=='file':
  asset=assets[ident]
  for key in ['path','image_url','folder_url','folder_id','name']:
   if key in ref and not(key=='name'and preserve_display_name):ref[key]=asset[key]
  return True
 return False
current_refs=[]
for collection in ['source_sets','source_offer_edges']:
 for i,row in enumerate(g[collection]):
  if refresh_ref(row.get('current_primary_reference',{})):current_refs.append(collection+'/'+str(i)+'/current_primary_reference')
for i,row in enumerate(g['arrangement_context_references']):
 if refresh_ref(row,preserve_display_name=True):current_refs.append('arrangement_context_references/'+str(i))
 for j,ref in enumerate(row.get('images',[])):
  if refresh_ref(ref):current_refs.append('arrangement_context_references/'+str(i)+'/images/'+str(j))
for i,row in enumerate(a['identity_review']):
 for key in ['reference','comparison_reference']:
  if refresh_ref(row.get(key,{})):current_refs.append('identity_review/'+str(i)+'/'+key)
assert len(current_refs)==5,current_refs
assert not any(any(o.get(k)in changed for k in ['file_id','context_file_id','series_file_id'])for o in g['options'])
originals=read(OLD/'original-verification.json')
for seal in seals:
 for item in seal['verified_originals']:
  data=Path(item['local_path']).read_bytes();content=hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest()for i in range(0,len(data),4194304))).hexdigest()
  assert sha(item['local_path'])==item['sha256']and len(data)==item['size']and content==item.get('dropbox_content_hash',item.get('content_hash'))
  originals['files'].append({'file_id':item['file_id'],'local_original':item['local_path'],'sha256':item['sha256'],'bytes':len(data),'dropbox_content_hash':content})
assert len({x['file_id']for x in originals['files']})==len(originals['files'])==69
batch=read(m['owner_batch']['snapshot'])
for item in batch['receipts']:assert sha(item['path'])==item['sha256']
owner_events=read(H/'owner-event-verification.json')['events'];defer=read(m['series_deferral']['snapshot']);bronze=read(m['bronze_finish']['snapshot'])
assert any(defer['owner_text']in x['texts']for x in owner_events)and any(bronze['owner_text']in x['texts']for x in owner_events)
oid=defer['current_item']['option_id'];assert oid=='BSI-C3573D23A4B7'and oid in state['queues']['series']
defer_event={**defer,'source_receipt':m['series_deferral']['path'],'source_sha256':m['series_deferral']['sha256'],'verified_owner_event':next(x for x in owner_events if defer['owner_text']in x['texts']),'canonical_applied':True}
note='Owner held this Dune Ripple2 Copper Series request for now. The source gap and existing reference are retained; other Series requests remain active.'
o=next(x for x in g['options']if x['product_id']==oid);o['current_series_owner_deferral']=defer_event;c=next(x for x in a['coverage']if x['option_id']==oid);c['series']['owner_deferral']=defer_event;c['owner_review']=(c.get('owner_review','')+'\n'+note).strip()
for t in a['missing_pictures']:
 if t['option_id']==oid and t['role']=='Series':t['owner_deferral']=defer_event;t['owner_response']=(t.get('owner_response','')+'\n'+note).strip()
for t in reviews:
 if t['option_id']==oid and t['role']=='Series':t['owner_deferral']=defer_event;t['next_action']='Hold this Series prompt until the owner resumes.'
state['queues']['series'].remove(oid);state.setdefault('held_series_ids',[]).append(oid);state.setdefault('owner_held_series_reviews',[]).append(defer_event);state['missing_source_task']='16 active Series requests; Dune2Copper Series owner-held. All22 missing context prompts remain held.';state['updated_utc']=now()
pewter='BSI-3635E3DC3434';exclusion={**bronze,'source_receipt':m['bronze_finish']['path'],'source_sha256':m['bronze_finish']['sha256'],'verified_owner_event':next(x for x in owner_events if bronze['owner_text']in x['texts']),'canonical_applied':True,'solid_bronze_material_inferred':False}
next(x for x in g['options']if x['product_id']==pewter).setdefault('series_candidate_exclusions',[]).append(exclusion);next(x for x in a['coverage']if x['option_id']==pewter)['series'].setdefault('candidate_exclusions',[]).append(exclusion)
g.setdefault('imported_series_owner_review_packets',[]).append({'path':m['owner_batch']['path'],'sha256':m['owner_batch']['sha256'],'deferrals':[defer_event],'candidate_finish_exclusions':[exclusion],'image_roles_closed':0})
photo=read(OLD/'photo-source-review.json');match=[x for x in photo['requests']if x['option_id']==oid and x['role']=='Series'];assert len(match)==1;match[0]['review_state']='OWNER_HELD_SERIES_GAP_RETAINED';match[0]['owner_deferral']=defer_event;photo['requests']=[x for x in photo['requests']if x not in match];photo.setdefault('held_series_requests',[]).extend(match);next(x for x in photo['requests']if x['option_id']==pewter)['candidate_exclusions']=[exclusion];photo.update(status='16_SERIES_ACTIVE_ONE_SERIES_HELD_ALL22_CONTEXT_HELD',role_counts={'Display/context':0,'Series':16},held_series_cases=1)
ready=[x for x in pending['entries']if x.get('path')==m['raked_overlay']['path']];assert len(ready)==1;pending['entries']=[x for x in pending['entries']if x not in ready];pending.setdefault('imported_packet_history',[]).extend([{'path':m[k]['path'],'sha256':m[k]['sha256'],'applied_to_current_frozen_release':True,'navigation_only':True}for k in ['raked_overlay','workshop_overlay']]);pending['status']='COMPLETED_NAVIGATION_IMPORTED_PRIOR_OWNER_HELD_NATIVE_PACKET_RETAINED'
summary={'status':'SEALED_ARRANGEMENT_AND_WORKSHOP_NAVIGATION_IMPORTED','recorded_utc':now(),'overlays':[{'path':m[k]['path'],'sha256':m[k]['sha256']}for k in ['raked_overlay','workshop_overlay']],'changed_file_paths':66,'existing_folder_renames':3,'created_native_folders':1,'actual_file_parent_changes':8,'actual_folder_parent_changes':1,'existing_current_source_references_refreshed':current_refs,'individual_option_primary_changes':0,'new_catalogue_records':0,'physical_fields_changed':0,'photograph_role_bindings_changed':0,'active_context':0,'held_context':22,'active_series':16,'held_series':1,'native_or_platform_writes':0}
g['latest_arrangement_workshop_navigation_import']=summary;g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='NAVIGATION_REFRESH_AND_ONE_SERIES_HOLD_GAPS_RETAINED')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for name,value in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('pending-followups.json',pending),('import-summary.json',summary),('path-change-history.json',path_history),('photo-source-review.json',photo),('original-verification.json',originals),('series-owner-deferral-import.json',defer_event),('pewter-bronze-candidate-exclusion.json',exclusion)]:write(H/name,value)
for name in ['physical-source-audit.json','guided_review.py','author_workbook.mjs','verify_workbook.py']:shutil.copy2(OLD/name,H/name)
script=(H/'guided_review.py').read_text().replace("deferred=set(state.get('deferred_individual_ids',[]))","deferred=set(state.get('deferred_individual_ids',[]));held_series=set(state.get('held_series_ids',[]))").replace("or task['role']=='Individual'and task['option_id']in deferred:continue","or task['role']=='Individual'and task['option_id']in deferred or task['role']=='Series'and task['option_id']in held_series:continue");(H/'guided_review.py').write_text(script)
if not(H/'node_modules').exists():(H/'node_modules').symlink_to(Path('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules'),target_is_directory=True)
write(H/'source-evidence-verification.json',{'status':'PASS','sealed_native_receipts':sum(len(native_receipts(x))for x in seals),'sealed_review_receipts':sum(len(x['review_receipts'])for x in seals),'fresh_metadata_objects':len(fresh),'fresh_complete_family_listings':2,'fresh_direct_workshop_scope_lists':3,'new_affected_whole_originals_rehashed':66,'all_scope_originals_rehashed':False,'verified_owner_events':2,'new_physical_verifications':0,'native_or_platform_writes':0})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-metadata.json','fresh-family-listings.json','fresh-workshop-evidence.json','owner-event-verification.json','source-evidence-verification.json','path-change-history.json','original-verification.json','series-owner-deferral-import.json','pewter-bronze-candidate-exclusion.json','photo-source-review.json']})
write(H/'projection-index.json',{'changed_native_objects':changed,'changed_reference_paths':current_refs,'old_output':str(oldout),'new_output':str(OUT)})
print(json.dumps({'status':'PREPARED','changed_native_objects':70,'file_paths':66,'file_parent_changes':8,'folder_parent_changes':1,'current_reference_paths':len(current_refs),'option_primaries_changed':0,'active_series':16,'held_series':1,'context_holds':22}))
