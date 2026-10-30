"""Compose four sealed path overlays and one independently owner-directed role."""
import collections,copy,hashlib,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');O=Path(m['master_register']['path']).parent
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
for key,digest in [('four_preflight','4bb976e0be5fe94bced783ca3e7935b77074d1744d4171962417fa00392fc9e8'),('four_final_map','79dc84466fe6cd37c83a5bb527555afa45e012471a4e27a6e75bea8363816d64'),('four_owner_directive','fe1da9f1a6ac0133ba7c0edf0c49925f320730498bb4f673c6927dceb9aac151'),('strata_owner','5329eaa6e300ef564dc18f47162ac40604e32f595db9273a1c50833a9e0e0e87')]:assert m[key]['sha256']==digest,key
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);objects=native['current_objects'];oldpaths=native['old_path_to_id'];fresh=read(H/'fresh-native-evidence.json');listings={x['name']:x['data']for x in fresh['results']if x['kind']=='listing'};metadata={x['name']:x['data']for x in fresh['results']if x['kind']=='metadata'}
pre=read(m['four_preflight']['snapshot']);final=read(m['four_final_map']['snapshot'])['objects'];directive=read(m['four_owner_directive']['snapshot']);approval=read(m['strata_owner']['snapshot']);expected_sizes={x['file_id']:x.get('size',0)for i in range(4)for x in read(m['overlay'+str(i)]['snapshot'])['objects']if x['object_type']=='file'}
def eventcheck(e,key):
 raw=next(line.rstrip('\n')for line in Path(e['transcript_path']).open()if hashlib.sha256(line.rstrip('\n').encode()).hexdigest()==e[key]);assert json.loads(raw)['timestamp']==e['timestamp'];return e[key]
owner_event=eventcheck(directive['owner_source'],'raw_event_sha256');strata_event=eventcheck(approval['source_owner_event'],'event_sha256')
def dp(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
actual={x['file_id']:x for name in ['moon','workshop','barbados']for x in listings[name]['entries']}
assert all(not x['has_more']and not x['cursor']for x in listings.values())and len(actual)==424
assert set(actual)=={x['file_id']for x in final}
paths={x['path']:x['file_id']for x in actual.values()if x['object_type']=='folder'}
for fid in ['id:cnqzTNngPVsAAAAAAArqbw','id:cnqzTNngPVsAAAAAAA6Vpw','id:cnqzTNngPVsAAAAAAAydFQ']:
 folder=metadata[fid]['folder'];paths['ns:202238505/'+folder['path_display']]=fid
for x in final:
 nowobj=actual[x['file_id']];assert nowobj['object_type']==x['object_type']and nowobj['path']==x['current_path']and paths.get(posixpath.dirname(nowobj['path']))==x['current_parent_id']
 if x['object_type']=='file':assert nowobj['file'].get('size',0)==expected_sizes[x['file_id']]
receipts=set();prefixes=[];changed_ids=set();transition_ids=[]
for receipt in pre['linked_receipt_checks']:assert receipt['match']and sha(receipt['path'])==receipt['declared_sha256'];receipts.add(receipt['path'])
for i in range(4):
 d=read(m['overlay'+str(i)]['snapshot']);assert d['status']=='COMPLETE_VERIFIED';prefixes.extend(d['prefix_maps'])
 for r in d['receipts']:assert sha(r['path'])==r['sha256'];receipts.add(r['path'])
 for x in d['objects']:
  fid=x['file_id'];current=dp(x['current_path']);before=dp(x['old_path'])
  if before!=current:changed_ids.add(fid);transition_ids.append(fid)
  if fid in objects and objects[fid].get('display_path'):oldpaths[objects[fid]['display_path'].casefold()]=fid
  for path in [before,current]:oldpaths[path.casefold()]=fid
  objects[fid]={**objects.get(fid,{}),'file_id':fid,'object_type':x['object_type'],'display_path':current,'path':x['current_path'],'name':x['current_name'],'parent_id':x['current_parent_id'],'size':x.get('size',0)}
for x in final:assert objects[x['file_id']]['path']==x['current_path']and objects[x['file_id']]['parent_id']==x['current_parent_id']
role=approval['approved_reference_roles'][0];r=copy.deepcopy(role['reference']);source=role['source'];sf=metadata[r['file_id']]['file'];folder=metadata[r['folder_id']]['folder'];primary=metadata['id:cnqzTNngPVsAAAAAAAueFw']['file']
assert sf['rev']==r['rev']and sf['size']==source['size']==Path(source['local_path']).stat().st_size and sf['path_display']==r['path_display']and posixpath.dirname(sf['path_display'])==folder['path_display']and sha(source['local_path'])==source['sha256']
assert listings['strata']['entries'][0]['file_id']==r['file_id']and len(listings['strata']['entries'])==1
old_strata=objects.get(r['file_id'],{});oldpaths[old_strata.get('display_path',dp(approval['owner_native_move_verified']['previous_path'])).casefold()]=r['file_id'];oldpaths[r['path_display'].casefold()]=r['file_id'];objects[r['file_id']]={**old_strata,'file_id':r['file_id'],'object_type':'file','display_path':r['path_display'],'path':r['path'],'name':r['name'],'parent_id':r['folder_id'],'size':r['size']};objects[r['folder_id']]={'file_id':r['folder_id'],'object_type':'folder','display_path':folder['path_display'],'path':'ns:202238505/'+folder['path_display'],'name':folder['name'],'parent_id':objects['id:cnqzTNngPVsAAAAAAAyjGQ']['parent_id'],'size':0};oldpaths[folder['path_display'].casefold()]=r['folder_id'];changed_ids.update([r['file_id'],r['folder_id']])
def currenturl(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return s
 u=urlsplit(s);path=unquote(u.path)
 for route in ['/home','/preview']:
  if path.startswith(route+'/'):path=path[len(route):];break
 name=parse_qs(u.query).get('preview',[''])[0];path+=('/'+name if name else'');fid=oldpaths.get(path.casefold())
 if fid not in changed_ids or path.casefold()==objects[fid]['display_path'].casefold():return s
 x=objects[fid];return'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
immutable={'specifications','master_fields','selling_details','original_visual_record','original_review_specification_assertions','source_only_assertions_not_applied_to_options','input_manifest','master_input_manifest','source_ref','master_ref','evidence_ref','catalogue_retirement'}
def project(z):
 if isinstance(z,list):return[project(x)for x in z]
 if not isinstance(z,dict):return currenturl(z)
 out={k:copy.deepcopy(x)if k in immutable or k.startswith(('historical_','prior_','before_','candidate_review_before_'))else project(x)for k,x in z.items()};fid=out.get('file_id')
 if fid in changed_ids and objects[fid]['object_type']=='file':
  x=objects[fid]
  for k,val in [('folder_id',x['parent_id']),('path',x['path']),('image_url','https://www.dropbox.com/preview'+quote(x['display_path'],safe='/')),('folder_url','https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'))]:
   if k in out:out[k]=val
 return out
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references','current_listing_resolution_details','current_listing_source_links','current_listing_match_evidence','current_listing_issues']:g[layer]=project(g[layer])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
assets=project(read(m['report_assets']['snapshot']));reviews=project(read(m['report_reviews']['snapshot']));oid='BSI-7B6291B7C7F9';o=next(x for x in g['options']if x['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid);assert o['file_id']==primary['id']=='id:cnqzTNngPVsAAAAAAAueFw'and c['in_situ']['status']=='No verified image'and c['series']['status']=='Optional / no fixed set'
basis='Owner directs Strata White in situ to the current single-file Strata White In Situ folder. Image003 shows the complete kept White grid relief on an old brick wall, with surrounding brickwork. Use the whole original as an owner-designated wall-setting reference. A wider room or garden, authenticated client/permanent installation, physical cast, measured dimensions, material or fitted fixing is not verified. Individual001 and optional series disposition are unchanged.'
c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(c['in_situ']));c['in_situ']={'status':'Available','reference':r,'basis':basis,'explicit_owner_image_role_approval':True,'owner_image_role_approval':{'decision_id':approval['decision_id'],'path':m['strata_owner']['path'],'sha256':m['strata_owner']['sha256']},'source_qualified_visual_binding':True,'wall_setting_only':True,'wider_room_or_garden_view_verified':False,'scene_authenticity_verified':False,'physical_cast_or_size_certified':False};c.setdefault('notes',[]).append(basis)
o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']});o.update(context_status='Available',context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'],context_description=basis);o['photo_coverage']['in_situ']='Available';o['current_owner_directed_wall_setting']={'decision_id':approval['decision_id'],'reference':r,'qualification':basis}
state={'state':'OWNER_DESIGNATED_STRATA_WALL_SETTING','finding':basis,'next_action':'Keep the wall-setting qualification and whole original.','source_reference':r};c.setdefault('terminal_task_review',{})['in_situ']=copy.deepcopy(state);o.setdefault('current_photo_task_review',{}).setdefault('roles',{})['in_situ']=copy.deepcopy(state)
actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='In situ'and x['status']=='Open'];assert len(actions)==1;x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action='Use owner-designated complete Strata White003 wall-setting image.',reference=r,qualification=basis,owner_response='This for strata white in situ: [owner-supplied exact single-file folder]',resolution_kind=state['state'])
for x in reviews:
 if x.get('option_id')==oid and x.get('role')=='In situ':x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=r)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==oid:
  x.setdefault('remaining_evidence_gaps',[]).append(basis)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+basis
assets[r['file_id']]={**assets.get(r['file_id'],{}),**r,'thumb':source['local_path'],'original':source['local_path'],'sha256':source['sha256'],'current_original_content_rehashed':True,'pixels_edited':False}
active=[x for x in a['missing_pictures']if x['status']in ['Open','Optional']];counts=a['counts'];current=[x for x in a['coverage']if x.get('active_catalogue_option',True)];counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in current)),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']))
assert(counts['required_picture_actions'],counts['in_situ_statuses']['No verified image'],counts['series_statuses']['No verified image'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'],counts['retired_action_rows'])==(66,48,17,65,85,3)
item={'option_id':oid,'name':o['name'],'role':'In situ — owner-designated wall setting','basis':basis,'references':[{'role':'In situ — wall setting','reference':r}],'approval':{'path':m['strata_owner']['path'],'sha256':m['strata_owner']['sha256'],'decision_id':approval['decision_id'],'scope':'OWNER_DIRECTED_EXACT_SINGLE_FILE_CONTEXT_FOLDER'},'technical_individual_status':c['individual']['status']}
summary={'status':'FOUR_VERIFIED_NATIVE_OVERLAYS_AND_STRATA_WALL_SETTING_IMPORTED','recorded_utc':now(),'overlays_imported':[{k:v for k,v in m['overlay'+str(i)].items()if k in ['path','sha256']}for i in range(4)],'native_objects_freshly_verified':424,'native_files_metadata_verified':404,'prefix_maps_imported':8,'same_id_path_transitions':len(transition_ids),'changed_native_ids':len(changed_ids),'source_receipts_checked':len(receipts),'qualified_in_situ_roles_closed':1,'new_identity_or_specification_approvals':0,'new_native_or_platform_mutations':0,'current_counts':counts,'imported_context':item}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(g['latest_context_folder_refresh']));g['latest_context_folder_refresh']=summary;g['latest_four_links_and_strata_import']=summary;g['latest_draft_media_synchronization']={'status':'CURRENT_STRATA_WALL_SETTING_MEDIA_CONDITIONS','option_ids':[oid],'physical_or_platform_claims_changed':False};g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=counts,recorded_utc=now(),status=summary['status'],scope='Four sealed local path overlays and one owner-directed Strata wall-setting role; retirement, identities and specifications preserved.')
for k,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);g.setdefault('imported_owner_review_packets',[]).append(item['approval']);a.update(recorded_utc=now(),status=summary['status'],latest_context_folder_refresh=summary)
for x,y in zip(g['options'],old['options']):
 for key in ['product_id','name','canonical_component_id','specifications','master_fields','selling_details','counted_as_individual_option']:assert x[key]==y[key],(x['product_id'],key)
assert g['summary']==old['summary']and g['original_review_specification_assertions']==old['original_review_specification_assertions']
prep=read(O/'preparation-verification.json');prep.update(status=summary['status'],imported_approvals=[item],current_counts=counts)
ledger=project(read(O/'context-review-ledger.json'))
for x in ledger['tasks']:
 if x['option_id']==oid and x['role']=='In situ':x.update(status_after='Resolved',outcome=state['state'],current_finding=basis,current_reference=r)
rs=read(m['review_state']['snapshot']);rs['queues']['in_situ']=[x for x in rs['queues']['in_situ']if x!=oid];rs.setdefault('completed_owner_reviews',[]).append({'option_id':oid,'qualified_wall_setting':True,'file_id':r['file_id'],'physical_verification':False})
pending=read(m['pending']['snapshot']);imported={m['overlay'+str(i)]['path']for i in range(4)};pending['entries']=[x for x in pending['entries']if x['path']not in imported];pending.setdefault('imported_in_this_release',[]).extend(summary['overlays_imported'])
later=B.parent/'reports/dropbox-moon-crater-four-panel-arrangement-renames-2026-10-23/current-reference-overlay.json';assert sha(later)=='72b72da2313f2be9f2d4aa290f7d27cfb0618e23394f70ce2d59a4b4605d6f47'
if not any(x['path']==str(later)for x in pending['entries']):pending['entries'].append({'kind':'COMPLETED_NATIVE_PATH_REFRESH','path':str(later),'sha256':sha(later),'status':'COMPLETE_VERIFIED','applied_to_current_frozen_release':False,'queue_only_no_coverage_change':True,'compose_after':'dropbox-moon-crater-phase-pair-renames-2026-10-23'})
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('context-review-ledger.json',ledger),('guided-owner-review-state.json',rs),('preparation-verification.json',prep),('pending-followups.json',pending),('import-summary.json',summary)]:write(H/name,z)
for name in ['retired-option-history.json','retired-photo-review-entries.json','owner-retirement-instruction.json','specification-evidence-review.json']:shutil.copy2(O/name,H/name)
originals=read(O/'original-verification.json');originals['files'].append({'file_id':r['file_id'],'local_original':source['local_path'],'sha256':source['sha256'],'pixels_edited':False});write(H/'original-verification.json',originals)
write(H/'scope.json',{'overlays':{str(i):m['overlay'+str(i)]['path']for i in range(4)},'source_root':'/BOLDSTONE MASTER','strata_owner':m['strata_owner']['path']});write(H/'path-refresh-scope.json',{'changed_ids':sorted(changed_ids),'prefix_maps':prefixes,'strata_actual_parent_change':approval['owner_native_move_verified']})
write(H/'source-evidence-verification.json',{'status':'PASS','fresh_native_objects':424,'fresh_metadata_files':404,'all_fresh_lists_complete':True,'source_receipts_checked':len(receipts),'owner_directive_event_sha256':owner_event,'strata_owner_event_sha256':strata_event,'strata_original_sha256':source['sha256'],'wall_setting_only':True,'retirement_preserved':True,'new_native_or_platform_mutations':0})
write(H/'evidence-manifest.json',{str(H/'fresh-native-evidence.json'):{'sha256':sha(H/'fresh-native-evidence.json')},str(H/'path-refresh-scope.json'):{'sha256':sha(H/'path-refresh-scope.json')}})
print(json.dumps({'status':summary['status'],'active_options':187,'in_situ_gaps':48,'series_gaps':17,'required_actions':66,'fresh_objects':424,'changed_ids':len(changed_ids)}))
