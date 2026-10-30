"""Project nine owner-removed empty folders while preserving image/option evidence."""
import copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);native=read(m['native_map']['snapshot']);a=read(m['audit']['snapshot']);pending=read(m['pending']['snapshot']);meta=read(H/'fresh-native-evidence.json');lists=read(H/'fresh-parent-lists.json');deleted=[];packets=[]
for k in ['three_overlay','six_overlay']:
 z=read(m[k]['snapshot']);assert z['status']=='COMPLETE_VERIFIED'and z['deleted_files']==[];assert z['summary']['deleted_files']==0 and z['summary']['unexpected_missing_ids']==0 and z['summary']['actual_containing_folder_id_changes']==0
 for x in z['deleted_folders']:assert x['deleted_while_empty']and x['preserve_historical_source_alias'];deleted.append(copy.deepcopy(x))
 packets.append({'path':m[k]['path'],'sha256':m[k]['sha256'],'deleted_empty_folders':len(z['deleted_folders']),'files_deleted':0,'verification':copy.deepcopy(z['summary'])})
ids={x['file_id']for x in deleted};assert len(ids)==9;parents={x['old_parent_id']for x in deleted};assert len(parents)==6
entries=[]
for family in lists['records']:
 assert family['complete']and len(family['pages'])==1
 for page in family['pages']:assert not page['isError']and page['structuredContent']['has_more']is False;entries+=page['structuredContent']['entries']
assert len(entries)==87 and not ids.intersection(x['file_id']for x in entries)
parent_metadata={}
for x in meta['records']:
 if x['id']in parents:
  assert not x['result']['isError'];f=x['result']['structuredContent']['folder'];assert f['id']==x['id']and f['path_display'].startswith('/BOLDSTONE MASTER/');parent_metadata[x['id']]=f
assert set(parent_metadata)==parents
authority={'authority_type':'OWNER_DIRECTED_LOCAL_FOLDER_MAP_REFRESH','source_event':m['owner_event'],'source_event_evidence':m['owner_evidence'],'owner_message':read(m['owner_event']['snapshot'])['payload']['item']['content'][0]['text'],'native_mutations_performed_here':0,'image_role_or_specification_changes_authorized_in_this_import':False}
write(H/'owner-folder-refresh-authority.json',authority)
removed_current=0
for x in deleted:
 fid=x['file_id'];prior=native['current_objects'].pop(fid,None);removed_current+=prior is not None
 hist={**x,'status':'OWNER_REMOVED_WHILE_EMPTY','native_record_before_local_refresh':prior,'actual_surviving_family':parent_metadata[x['old_parent_id']],'owner_authorized_local_refresh':True,'preserve_historical_alias':True,'active_tree_position':False}
 native['owner_removed_empty_family_history'][fid]=hist;native['old_path_to_id'][x['path_display'].casefold()]=fid
assert removed_current==5 and not ids.intersection(native['current_objects'])
summary={'status':'NINE_EMPTY_FOLDER_HISTORY_ENTRIES_IMPORTED','recorded_utc':now(),'owner_authority':str(H/'owner-folder-refresh-authority.json'),'owner_authority_sha256':sha(H/'owner-folder-refresh-authority.json'),'native_packets':packets,'removed_empty_folder_ids':sorted(ids),'empty_folders_recorded':9,'formerly_current_map_entries_removed':5,'historical_empty_folder_records_added':9,'fresh_surviving_family_parents_verified':6,'fresh_direct_children_checked':87,'completed_parent_list_pages':6,'individual_options_changed':0,'image_coverage_records_changed':0,'photograph_actions_closed':0,'new_physical_verifications':0,'native_or_platform_writes':0,'current_counts':copy.deepcopy(a['counts'])}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(g['latest_context_folder_refresh']));g['latest_context_folder_refresh']=summary;g['latest_empty_folder_history_import']=summary;g['current_removed_empty_folder_history']={'path':str(H/'removed-empty-folder-history.json'),'current_import_ids':sorted(ids),'preserve_historical_source_component_dispositions':True,'no_option_or_photo_identity_change':True}
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),recorded_utc=now(),status='COVERAGE_UNCHANGED_BY_EMPTY_FOLDER_REFRESH',scope='Nine already-removed empty folder IDs recorded as history. All image role decisions, outstanding requests and technical distinctions remain unchanged.')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);native['status']='CURRENT_MAP_WITH_NINE_OWNER_REMOVED_EMPTY_FOLDER_TOMBSTONES';pending.setdefault('imported_packet_history',[])
remaining=[]
for z in pending['entries']:
 if z.get('path')==m['three_overlay']['path']:pending['imported_packet_history'].append({**z,'applied_to_current_frozen_release':True,'imported_utc':now(),'local_history_import':str(H/'removed-empty-folder-history.json')})
 else:remaining.append(z)
pending['imported_packet_history'].append({'path':m['six_overlay']['path'],'sha256':m['six_overlay']['sha256'],'status':'COMPLETE_VERIFIED_IMPORTED_LOCAL_HISTORY','applied_to_current_frozen_release':True,'imported_utc':now()});pending['entries']=remaining;assert len(remaining)==1 and remaining[0]['status']=='PARTIAL_OWNER_HOLD'
for k in ['options','components','source_component_dispositions','original_review_specification_assertions','current_source_unavailable_references','latest_four_qualified_display_import','latest_owner_leaf_curve_context_import','latest_verified_native_folder_import']:assert g[k]==old[k],k
for name,key in [('image-coverage-current.json','audit'),('current-assets.json','report_assets'),('photo-review-queue.json','report_reviews'),('guided-owner-review-state.json','review_state')]:shutil.copy2(m[key]['snapshot'],H/name)
write(H/'canonical-master-register.json',g);write(H/'current-native-reference-map.json',native);write(H/'pending-followups.json',pending);write(H/'removed-empty-folder-history.json',{'status':summary['status'],'recorded_utc':now(),'folders':deleted,'summary':summary,'surviving_parent_metadata':parent_metadata});write(H/'import-summary.json',summary)
write(H/'source-evidence-verification.json',{'status':'PASS','native_removal_packets_verified':2,'empty_folder_ids':9,'complete_fresh_parent_lists':6,'direct_children_checked':87,'removed_ids_absent_from_current_parent_lists':True,'stable_parent_metadata_verified':6,'fresh_removed_id_metadata_results':'INVALID_ARGUMENT; not used alone as deletion proof. Terminal native deletion receipts and complete current parent lists are authoritative.','new_native_or_platform_mutations':0})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-native-evidence.json','fresh-parent-lists.json','owner-folder-refresh-authority.json','source-evidence-verification.json']})
print(json.dumps({'status':summary['status'],'empty_folders':9,'current_map_entries_removed':5,'options_changed':0,'coverage_sha256_unchanged':sha(H/'image-coverage-current.json')==m['audit']['sha256'],'pending_entries':len(remaining)}))
