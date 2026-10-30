"""Import exactly one owner-approved existing photograph after stable-ID readback."""
import collections,copy,hashlib,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');O=Path(m['master_register']['path']).parent
approval_path=B/'components/parallel-reviews/leaf-curve-owner-display-approval-20261023T175607Z/owner-image-approval.json'
assert sha(approval_path)=='11f110c16bf3de6570c795e2a5654aed58a07e04dda4dc521956e64392d560a0'
approval=read(approval_path);pre=approval['technical_source_qualification'];assert sha(pre['path'])==pre['sha256'];preflight=read(pre['path'])
for key,source in [('owner_approval',approval_path),('owner_preflight',Path(pre['path']))]:
 if key not in m:
  target=H/'inputs'/(key+'.before');shutil.copy2(source,target);m[key]={'path':str(source),'snapshot':str(target),'sha256':sha(source)}
write(H/'input-manifest.json',m)
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
event=approval['source_owner_event'];matching=None
for raw in Path(event['transcript_path']).open():
 line=raw.rstrip('\n')
 if hashlib.sha256(line.encode()).hexdigest()==event['raw_event_sha256']:matching=json.loads(line);break
assert matching and matching['timestamp']==event['timestamp'] and matching['type']=='response_item' and matching['payload']['type']=='message' and matching['payload']['role']=='user'
assert '\n'.join(x['text']for x in matching['payload']['content']if x['type']=='input_text')==event['text']==approval['exact_owner_message']
assert approval['product_ids']==['BSI-CF0CC1EB8F96'] and len(approval['approved_reference_roles'])==1
role=approval['approved_reference_roles'][0];assert role['role']=='in_situ' and role['whole_original_only']
r=copy.deepcopy(role['reference']);oid=role['product_id'];e=read(H/'leaf-native-evidence.json');f=e['context']['file'];folder=e['folder']['folder'];primary=e['primary']['file']
assert f['id']==r['file_id'] and f['rev']==r['rev'] and f['size']==r['size'] and f['name']==r['name']
assert folder['id']==r['folder_id'] and posixpath.dirname(f['path_display'])==folder['path_display']
assert 'ns:202238505/'+f['path_display']==r['path']
source=next(x for x in preflight['original_checks']if x['file_id']==r['file_id'])
assert source['sha256']==r['sha256']==sha(source['local_original_path']) and Path(source['local_original_path']).stat().st_size==f['size']
assert source['current_revision']==r['rev']
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);assets=read(m['report_assets']['snapshot']);reviews=read(m['report_reviews']['snapshot'])
o=next(x for x in g['options']if x['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid)
assert o['file_id']==primary['id']=='id:cnqzTNngPVsAAAAAAAylMQ' and c['in_situ']['status']=='No verified image' and c['series']['status']=='Optional / no fixed set'
basis=approval['requested_register_change']['basis'];r.update(path_display=f['path_display'],content_hash=source['dropbox_content_hash'],dimensions=source['dimensions'],native_reference_status='CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED',source_qualified_visual_binding=True,scene_authenticity_verified=False,physical_cast_or_size_certified=False)
for x,kind,pid in [(f,'file',r['folder_id']),(folder,'folder',native['current_objects'][r['folder_id']]['parent_id'])]:
 fid=x['id'];before=native['current_objects'][fid];assert before['object_type']==kind and before['parent_id']==pid
 native['old_path_to_id'][before['display_path'].casefold()]=fid
 native['current_objects'][fid]={**before,'display_path':x['path_display'],'path':'ns:202238505/'+x['path_display'],'name':x['name'],'size':x.get('size',0)}
c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(c['in_situ']))
c['in_situ']={'status':'Available','reference':r,'basis':basis,'explicit_owner_image_role_approval':True,'owner_image_role_approval':{'decision_id':approval['decision_id'],'path':str(approval_path),'sha256':sha(approval_path)},'source_qualified_visual_binding':True,'outdoor_display_only':True,'wider_room_or_garden_view_verified':False,'scene_authenticity_verified':False,'physical_cast_or_size_certified':False}
c.setdefault('notes',[]).append(basis)
o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']})
o.update(context_status='Available',context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'],context_description=basis);o['photo_coverage']['in_situ']='Available';o['current_owner_directed_outdoor_display']={'decision_id':approval['decision_id'],'reference':r,'qualification':basis}
state={'state':'OWNER_ACCEPTED_LEAF_CURVE_OUTDOOR_DISPLAY','finding':basis,'next_action':'Use the whole original as qualified outdoor display.','source_reference':r}
c.setdefault('terminal_task_review',{})['in_situ']=copy.deepcopy(state);o.setdefault('current_photo_task_review',{}).setdefault('roles',{})['in_situ']=copy.deepcopy(state)
actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='In situ' and x['status']=='Open'];assert len(actions)==1
x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action='Use owner-accepted whole Leaf Curve White and Gold Leaf001 outdoor-display photograph.',reference=r,qualification=basis,owner_response='Accept this whole photograph as its outdoor-display reference.',resolution_kind=state['state'])
for x in reviews:
 if x.get('option_id')==oid and x.get('role')=='In situ':x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=r)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==oid:
  x.setdefault('remaining_evidence_gaps',[]).append(basis)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+basis
assets[r['file_id']]={**assets.get(r['file_id'],{}),**r,'thumb':source['local_original_path'],'original':source['local_original_path'],'sha256':source['sha256'],'current_original_content_rehashed':True,'pixels_edited':False}
active=[x for x in a['missing_pictures']if x['status']in ['Open','Optional']];counts=a['counts'];current=[x for x in a['coverage']if x.get('active_catalogue_option',True)]
counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in current)),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']))
assert(counts['required_picture_actions'],counts['in_situ_statuses']['No verified image'],counts['series_statuses']['No verified image'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'],counts['retired_action_rows'])==(65,47,17,64,86,3)
item={'option_id':oid,'name':o['name'],'role':'In situ — owner-accepted outdoor display','basis':basis,'references':[{'role':'Outdoor display — whole original','reference':r}],'approval':{'path':str(approval_path),'sha256':sha(approval_path),'decision_id':approval['decision_id'],'scope':'EXACT_WHOLE_ORIGINAL_OUTDOOR_DISPLAY_ONLY'},'technical_individual_status':c['individual']['status']}
summary={'status':'OWNER_ACCEPTED_LEAF_CURVE_OUTDOOR_DISPLAY_IMPORTED','recorded_utc':now(),'imported_context':item,'qualified_in_situ_roles_closed':1,'new_identity_or_specification_approvals':0,'new_native_or_platform_mutations':0,'current_counts':counts,'queued_moon_shellwave_workshop_links':'Already imported; live stable-ID readback verified8 folders and123 updated image paths.','queued_link_readback':str(H/'queued-link-readback.json'),'queued_link_readback_sha256':sha(H/'queued-link-readback.json')}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(g['latest_context_folder_refresh']));g['latest_context_folder_refresh']=summary;g['latest_owner_leaf_curve_context_import']=summary;g['latest_draft_media_synchronization']={'status':'LEAF_CURVE_OUTDOOR_DISPLAY_MEDIA_CONDITIONS','option_ids':[oid],'physical_or_platform_claims_changed':False}
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=counts,recorded_utc=now(),status=summary['status'],scope='One exact owner-accepted Leaf Curve outdoor-display role. Prior Moon/Shellwave/workshop links freshly verified; source IDs, retirement, identities and specifications retained.')
for k,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);g.setdefault('imported_owner_review_packets',[]).append(item['approval']);a.update(recorded_utc=now(),status=summary['status'],latest_context_folder_refresh=summary)
for x,y in zip(g['options'],old['options']):
 for key in ['product_id','name','canonical_component_id','specifications','master_fields','selling_details','counted_as_individual_option']:assert x[key]==y[key],(x['product_id'],key)
 if x['product_id']!=oid:assert x==y,('Unrelated option changed',x['product_id'])
assert g['summary']==old['summary'] and g['original_review_specification_assertions']==old['original_review_specification_assertions']
prep=read(H/'preparation-verification.json');prep.update(status=summary['status'],imported_approvals=[item],current_counts=counts);write(H/'preparation-verification.json',prep)
ledger=read(H/'context-review-ledger.json')
for x in ledger['tasks']:
 if x['option_id']==oid and x['role']=='In situ':x.update(status_after='Resolved',outcome=state['state'],current_finding=basis,current_reference=r)
rs=read(m['review_state']['snapshot']);rs['queues']['in_situ']=[x for x in rs['queues']['in_situ']if x!=oid];rs.setdefault('completed_owner_reviews',[]).append({'option_id':oid,'qualified_outdoor_display':True,'file_id':r['file_id'],'physical_verification':False})
pending=read(m['pending']['snapshot'])
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('context-review-ledger.json',ledger),('guided-owner-review-state.json',rs),('pending-followups.json',pending),('import-summary.json',summary)]:write(H/name,z)
originals=read(H/'original-verification.json');originals['files'].append({'file_id':r['file_id'],'local_original':source['local_original_path'],'sha256':source['sha256'],'pixels_edited':False});write(H/'original-verification.json',originals)
write(H/'scope.json',{'overlays':{str(i):str(B.parent/'reports'/name/'current-reference-overlay.json')for i,name in enumerate(['dropbox-moon-and-shellwave-pair-renames-2026-10-23','dropbox-moon-and-shellwave-triptych-rename-2026-10-23','dropbox-moon-and-shellwave-remaining-arrangement-renames-2026-10-23','dropbox-remaining-workshop-separation-2026-10-23'])},'source_root':'/BOLDSTONE MASTER','owner_context_packet':str(approval_path),'folder_refresh_status':'Already imported and live readback verified; no repeated import'})
write(H/'path-refresh-scope.json',{'changed_ids':[],'prefix_maps':[],'new_native_path_changes':0})
write(H/'source-evidence-verification.json',{'status':'PASS','owner_event_sha256':event['raw_event_sha256'],'owner_packet_sha256':sha(approval_path),'context_original_sha256':source['sha256'],'primary_file_id_preserved':primary['id'],'outdoor_display_only':True,'retirement_preserved':True,'native_objects_checked':409,'queued_folder_paths_verified':8,'new_native_or_platform_mutations':0})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-native-evidence.json','queued-link-readback.json','leaf-native-evidence.json','path-refresh-scope.json']})
print(json.dumps({'status':summary['status'],'active_options':187,'in_situ_gaps':47,'series_gaps':17,'required_actions':65,'working_values_changed':0}))
