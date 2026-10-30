"""Compose six existing native-change packets; reopen one unavailable current source."""
import collections,copy,hashlib,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');O=Path(m['master_register']['path']).parent
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
directive=read(m['owner_directive']['snapshot']);event=directive['source_owner_event'];raw=Path(event['raw_event_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==event['raw_event_sha256'];ev=json.loads(raw);assert ev['timestamp']==event['timestamp'] and ev['payload']['role']=='user' and ev['payload']['content'][0]['text']==event['text']
for line in Path(event['transcript_path']).open('rb'):
 if hashlib.sha256(line).hexdigest()==event['raw_event_sha256']:break
else:raise AssertionError('Exact owner directive not found in original transcript')
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);objects=native['current_objects'];oldpaths=native['old_path_to_id'];e=read(H/'fresh-native-evidence.json');root=read(H/'wall-root-metadata.json')['folder'];assert root['id']=='id:cnqzTNngPVsAAAAAAArpsA'
assert all(not z['has_more'] and not z.get('cursor')for z in e['listings'].values())
actual={x['file_id']:x for name in ['moon-crater','rust-panel','egyptian','panel-curves']for x in e['listings'][name]['entries']}
for fid in ['id:cnqzTNngPVsAAAAAAAydCg','id:cnqzTNngPVsAAAAAAAyddg','id:cnqzTNngPVsAAAAAAArp2w','id:cnqzTNngPVsAAAAAAAydRQ']:
 x=e['metadata'][fid]['data']['folder'];actual[fid]={'file_id':fid,'name':x['name'],'path':'ns:202238505/'+x['path_display'],'object_type':'folder'}
parents={x['path']:x['file_id']for x in actual.values()if x['object_type']=='folder'};parents['ns:202238505/'+root['path_display']]=root['id']
expected={};prefixes=[];packets=[];deleted=[]
for i in range(6):
 d=read(m['overlay'+str(i)]['snapshot']);assert d['status']=='COMPLETE_VERIFIED' and m['overlay'+str(i)]['sha256']==directive['six_writer_identified_ready_native_packets'][i]['sha256'];packets.append({'path':m['overlay'+str(i)]['path'],'sha256':m['overlay'+str(i)]['sha256']});prefixes.extend(d.get('prefix_maps',[]));deleted.extend(d.get('deleted_folders',[]))
 for x in d.get('objects',[]):expected[x['file_id']]=x
missing=set(expected)-set(actual);assert missing=={'id:cnqzTNngPVsAAAAAAAuRpA','id:cnqzTNngPVsAAAAAAAuRcw','id:cnqzTNngPVsAAAAAAAuRWQ','id:cnqzTNngPVsAAAAAAAuRdg'}
assert len(actual)==536 and len(expected)==539
checks=0;changed=set();unavailable=[]
for fid,x in expected.items():
 if fid in missing:
  assert e['metadata'][fid]['isError'] and e['metadata'][fid]['data']['error_code']=='INVALID_ARGUMENT';unavailable.append({'file_id':fid,'historical_native_object':copy.deepcopy(objects.get(fid)),'sealed_native_object':x,'current_lookup_status':'Not returned in the checked current Master folder; stable-ID metadata lookup fails','metadata_error':'INVALID_ARGUMENT','global_deletion_inferred':False});continue
 y=actual[fid];assert y['object_type']==x['object_type'] and y['path']==x['current_path'] and y['name']==x['current_name'];checks+=3
 parent=parents[posixpath.dirname(y['path'])];assert parent==x['current_parent_id'];checks+=1
 if y['object_type']=='file':assert y['file'].get('size',0)==x.get('size',0);checks+=1
 before=objects.get(fid,{});display='/'+y['path'].split('//',1)[1].lstrip('/')
 if before.get('display_path')!=display:changed.add(fid)
 for p in [before.get('display_path'),'/'+x['old_path'].split('//',1)[1].lstrip('/'),display]:
  if p:oldpaths[p.casefold()]=fid
 objects[fid]={**before,'file_id':fid,'object_type':y['object_type'],'display_path':display,'path':y['path'],'name':y['name'],'parent_id':parent,'size':y.get('file',{}).get('size',0),'native_reference_status':'CURRENT_MASTER_STABLE_ID_AND_ACTUAL_PARENT_VERIFIED'}
for x in unavailable:
 prior=objects.pop(x['file_id'],None)
 native.setdefault('unresolved_historical_objects',{})[x['file_id']]={'historical_native_object':prior,'sealed_native_object':x['sealed_native_object'],'native_reference_status':'CURRENT_LOOKUP_UNRESOLVED_HISTORICAL_ID_RETAINED','current_source_verification':x['current_lookup_status'],'current_native_path_verified':False}
assert len(deleted)==1 and deleted[0]['file_id']=='id:cnqzTNngPVsAAAAAAAyeeQ' and deleted[0]['deleted_while_empty']
gone=deleted[0]['file_id'];assert gone not in {x['file_id']for x in e['listings']['wall-root']['entries']};assert gone not in objects
native.setdefault('owner_removed_empty_family_history',{})[gone]=deleted[0]
photo=e['metadata']['id:cnqzTNngPVsAAAAAAAt8mA']['data']['file'];assert photo['size']==805275 and photo['rev']=='65e82b5be3fd00c0dea29' and '/Workshop and Moulding/Sally With Sculptures Workshop Views/'in photo['path_display']
def native_id(url):
 if not isinstance(url,str)or not url.startswith('https://www.dropbox.com/'):return None
 u=urlsplit(url);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(u.query).get('preview',[''])[0];p+='/'+name if name else'';return oldpaths.get(p.casefold())
def currenturl(url):
 fid=native_id(url)
 if fid in missing or fid==gone:return ''
 if fid not in changed:return url
 x=objects[fid];return 'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
immutable={'specifications','master_fields','selling_details','original_visual_record','original_review_specification_assertions','source_only_assertions_not_applied_to_options','input_manifest','master_input_manifest','source_ref','master_ref','evidence_ref','catalogue_retirement'}
def project(z):
 if isinstance(z,list):return[project(x)for x in z]
 if not isinstance(z,dict):return currenturl(z)if isinstance(z,str)else z
 out={k:copy.deepcopy(v)if k in immutable or k.startswith(('historical_','prior_','before_','candidate_review_before_'))else project(v)for k,v in z.items()};fid=out.get('file_id')
 if fid in changed and objects[fid]['object_type']=='file':
  x=objects[fid]
  for k,v in [('folder_id',x['parent_id']),('path',x['path']),('image_url',currenturl('https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'))),('folder_url','https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'))]:
   if k in out:out[k]=v
 if fid in missing:out['native_reference_status']='CURRENT_LOOKUP_UNRESOLVED_HISTORICAL_ID_RETAINED';out['current_native_path_verified']=False
 return out
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references','current_listing_resolution_details','current_listing_source_links','current_listing_match_evidence','current_listing_issues']:g[layer]=project(g[layer])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
assets=project(read(m['report_assets']['snapshot']));reviews=project(read(m['report_reviews']['snapshot']));oid='BSI-83F1AACE15E9';o=next(x for x in g['options']if x['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid);oldc=next(x for x in read(m['audit']['snapshot'])['coverage']if x['option_id']==oid)
assert oldc['in_situ']['status']=='Available' and oldc['in_situ']['reference']['file_id']=='id:cnqzTNngPVsAAAAAAAuRcw';primary=copy.deepcopy(c['individual']['reference']);assert primary['file_id']=='id:cnqzTNngPVsAAAAAAAyf6Q' and primary['file_id']in actual
basis='The previously linked Rust and Verdigris Panel in-situ001 (id:cnqzTNngPVsAAAAAAAuRcw) is not returned in the checked current BOLDSTONE MASTER folder and its stable-ID metadata lookup fails with INVALID_ARGUMENT. Three other former in-situ sources are also unavailable in that folder. This does not establish global deletion. Preserve their source IDs and prior associations as history; find or approve a current replacement. The individual005 reference remains verified.'
c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(oldc['in_situ']));c['in_situ']={'status':'No verified image','reference':primary,'basis':basis,'previous_source_currently_unresolved':True,'previous_file_id':'id:cnqzTNngPVsAAAAAAAuRcw'};c.setdefault('notes',[]).append(basis)
beforeo=next(x for x in old['options']if x['product_id']==oid);o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(beforeo.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']});o.update(context_status='No verified image',context_file_id='',context_folder_id='',context_image_url='',context_folder_url='',context_description=basis);o['photo_coverage']['in_situ']='No verified image';o['current_source_unavailable_review']={'historical_file_id':'id:cnqzTNngPVsAAAAAAAuRcw','qualification':basis,'native_mutations':0}
state={'state':'CURRENT_SOURCE_UNRESOLVED_FIND_REPLACEMENT','finding':basis,'next_action':'Find or review a current in-situ replacement; use individual005 for identification.','source_reference':primary};c.setdefault('terminal_task_review',{})['in_situ']=state;o.setdefault('current_photo_task_review',{}).setdefault('roles',{})['in_situ']=copy.deepcopy(state)
tasks=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='In situ'];assert not tasks
a['missing_pictures'].append({'priority':2,'option_id':oid,'name':o['name'],'role':'In situ','action_type':'Find / capture','action':state['next_action'],'reference':primary,'scope':'Current BOLDSTONE MASTER sources only. Retain the prior source and its IDs as history.','qualification':basis,'owner_response':'','status':'Open','resolution_kind':state['state'],'historical_previously_available_reference':copy.deepcopy(oldc['in_situ'])})
for x in reviews:
 if x.get('option_id')==oid and x.get('role')=='In situ':x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=primary)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==oid:
  x.setdefault('remaining_evidence_gaps',[]).append(basis)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+basis
active=[x for x in a['missing_pictures']if x['status']in ['Open','Optional']];counts=a['counts'];current=[x for x in a['coverage']if x.get('active_catalogue_option',True)];counts.update(action_rows=len(a['missing_pictures']),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in current)),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']));assert(counts['required_picture_actions'],counts['in_situ_statuses']['No verified image'],counts['series_statuses']['No verified image'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'])==(66,48,17,65,86)
summary={'status':'LATER_NATIVE_LINKS_REFRESHED_ONE_CURRENT_SOURCE_REOPENED','recorded_utc':now(),'overlays_imported':packets,'owner_directive':m['owner_directive'],'native_objects_currently_verified':536,'native_objects_from_packets_verified':535,'unresolved_historical_source_ids':sorted(missing),'verified_file_paths_refreshed':sum(objects[fid]['object_type']=='file'for fid in changed),'verified_folder_paths_refreshed':sum(objects[fid]['object_type']=='folder'for fid in changed),'current_counts':counts,'new_image_role_approvals':0,'reopened_in_situ_roles':1,'new_native_or_platform_mutations':0,'removed_empty_family_id':gone,'removed_family_already_absent_from_current_map':True}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(g['latest_context_folder_refresh']));g['latest_context_folder_refresh']=summary;g['latest_verified_native_folder_import']=summary;g['current_source_unavailable_references']=unavailable;g['latest_draft_media_synchronization']={'status':'VERIFIED_NATIVE_LINKS_AND_RUST_SOURCE_GAP','option_ids':[oid],'physical_or_platform_claims_changed':False};g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=counts,recorded_utc=now(),status=summary['status'],scope='Six existing native-change packets; four historical Rust sources unresolved and one in-situ action reopened. Prior Leaf Curve approval and all physical/commercial working fields retained.')
for k,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);g.setdefault('imported_local_path_directives',[]).append({k:m['owner_directive'][k]for k in ['path','sha256']});a.update(recorded_utc=now(),status=summary['status'],latest_context_folder_refresh=summary)
for x,y in zip(g['options'],old['options']):
 for k in ['product_id','name','canonical_component_id','specifications','master_fields','selling_details','counted_as_individual_option']:assert x[k]==y[k],(x['product_id'],k)
assert g['summary']==old['summary'] and g['latest_owner_leaf_curve_context_import']==old['latest_owner_leaf_curve_context_import']
prep=read(H/'preparation-verification.json');prep.update(status=summary['status'],imported_approvals=[],current_counts=counts)
ledger=project(read(H/'context-review-ledger.json'))
for x in ledger['tasks']:
 if x['option_id']==oid and x['role']=='In situ':x.update(status_after='Open',outcome=state['state'],current_finding=basis,current_reference=primary)
rs=read(m['review_state']['snapshot']);rs['queues']['in_situ'].append(oid)if oid not in rs['queues']['in_situ']else None
pending=read(m['pending']['snapshot']);ready={x['path']for x in packets};pending['entries']=[x for x in pending['entries']if x['path']not in ready];pending.setdefault('imported_in_this_release',[]).extend(packets);pending['frozen_current_scope']='Six later native-change packets; Rust31 current objects verified,4 former image IDs unresolved, one prior context role reopened. Existing holds retained.'
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('context-review-ledger.json',ledger),('guided-owner-review-state.json',rs),('preparation-verification.json',prep),('pending-followups.json',pending),('import-summary.json',summary),('unavailable-native-references.json',unavailable)]:write(H/name,z)
write(H/'path-refresh-scope.json',{'changed_ids':sorted(changed),'prefix_maps':prefixes,'unavailable_file_ids':sorted(missing),'deleted_empty_family_ids':[gone],'rust_gap_option_id':oid})
write(H/'scope.json',{'overlays':{str(i):m['overlay'+str(i)]['path']for i in range(6)},'source_root':'/BOLDSTONE MASTER','owner_directive':m['owner_directive']['path']})
write(H/'source-evidence-verification.json',{'status':'PASS_WITH_EXPLICIT_SOURCE_GAP','checks':checks,'native_objects_currently_verified':536,'native_packet_objects_verified':535,'all_lists_complete':True,'unresolved_historical_source_ids':sorted(missing),'owner_directive_sha256':m['owner_directive']['sha256'],'new_native_or_platform_mutations':0,'new_image_role_approvals':0})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-native-evidence.json','wall-root-metadata.json','path-refresh-scope.json']})
print(json.dumps({k:summary[k]for k in ['status','native_objects_currently_verified','verified_file_paths_refreshed','verified_folder_paths_refreshed','unresolved_historical_source_ids']}))
