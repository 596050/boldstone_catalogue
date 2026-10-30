import collections,copy,hashlib,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,parse_qs
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');O=Path(m['master_register']['path']).parent
for key,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],key
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);olda=copy.deepcopy(a);native=read(m['native_map']['snapshot']);objects=native['current_objects'];oldpaths=native['old_path_to_id'];overlays={k:read(m[k]['snapshot'])for k in ['barbados','sally']};fresh=read(H/'fresh-folder-evidence.json')
display=lambda p:'/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
verified_receipts=0
for i,(key,d)in enumerate(overlays.items()):
 assert d['status']=='COMPLETE_VERIFIED'and d['summary']['all_original_ids_retained']and d['summary']['actual_file_parent_id_changes']==0
 for receipt in d['receipts']:assert sha(receipt['path'])==receipt['sha256'];verified_receipts+=1
 f=fresh[str(i)];md=f['metadata']['folder'];listing=f['listing'];assert not listing['has_more']and not listing['cursor']
 folder=d['prefix_maps'][0];assert md['id']==folder['file_id']and md['path_display']==folder['current_path']
 d['objects']=[x for x in d['objects']if x['file_id']==md['id']or x.get('current_parent_id')==md['id']]
 expected={x['file_id']:x for x in d['objects']if x['object_type']=='file'};actual={x['file_id']:x for x in listing['entries']};assert set(expected)==set(actual)
 for fid,x in expected.items():assert x['size']==actual[fid]['file']['size']and x['current_path']==actual[fid]['path']
 for x in d['objects']:
  dp=display(x['current_path']);assert dp.startswith('/BOLDSTONE MASTER/');objects[x['file_id']]={**objects.get(x['file_id'],{}),'file_id':x['file_id'],'object_type':x['object_type'],'display_path':dp,'path':x['current_path'],'name':x['current_name'],'parent_id':x['current_parent_id'],'size':x['size']}
  for p in [x['old_path'],x['current_path']]:oldpaths[display(p).casefold()]=x['file_id']
def urlpath(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return None
 u=urlsplit(s);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(u.query).get('preview',[''])[0];return p+('/'+name if name else '')
scoped_ids={x['file_id']for d in overlays.values()for x in d['objects']}
def currenturl(s):
 p=urlpath(s)
 if not p:return s
 fid=oldpaths.get(p.casefold())
 if fid not in objects or fid not in scoped_ids:return s
 x=objects[fid]
 if p.casefold()==x['display_path'].casefold():return s
 return'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
immutable={'specifications','master_fields','selling_details','original_visual_record','original_review_specification_assertions','source_only_assertions_not_applied_to_options','input_manifest','master_input_manifest','source_ref','master_ref','evidence_ref'}
def project(z):
 if isinstance(z,list):return[project(x)for x in z]
 if not isinstance(z,dict):return currenturl(z)
 out={k:copy.deepcopy(x)if k in immutable or k.startswith(('historical_','prior_','before_','candidate_review_before_'))else project(x)for k,x in z.items()}
 fid=out.get('file_id')
 if fid in objects and objects[fid]['object_type']=='file':
  x=objects[fid]
  if any(fid in {i['file_id']for i in d['objects']}for d in overlays.values()):
   for k,v in [('folder_id',x['parent_id']),('path',x['path']),('image_url','https://www.dropbox.com/preview'+quote(x['display_path'],safe='/')),('folder_url','https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'))]:
    if k in out:out[k]=v
 return out
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references','current_listing_resolution_details','current_listing_source_links','current_listing_match_evidence','current_listing_issues']:g[layer]=project(g[layer])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
reviews=project(read(m['report_reviews']['snapshot']));assets=project(read(m['report_assets']['snapshot']))
approval=read(m['owner_component']['snapshot']);correction=read(m['owner_role_correction']['snapshot']);target=approval['target'];oid=target['product_id'];assert oid=='BSI-E0FAA8F7CB6D'and approval['decision']['identity_confirmation_only']and not approval['decision']['separate_image_role_approval_inferred']
event=approval['owner_source'];raw=next(line.rstrip('\n')for line in Path(event['transcript_path']).open()if hashlib.sha256(line.rstrip('\n').encode()).hexdigest()==event['event_sha256']);assert json.loads(raw)['timestamp']==event['timestamp']
fm=read(H/'fresh-garden-metadata.json');file=fm['2']['file'];folder=fm['3']['folder'];assert file['id']==target['scene_file_id']and folder['id']==target['folder_id']and file['rev']==target['source_metadata']['rev']and posixpath.dirname(file['path_display'])==folder['path_display']
source=target['source_check'];assert Path(source['path']).stat().st_size==source['bytes']==file['size']and sha(source['path'])==source['sha256']
r={'file_id':file['id'],'folder_id':folder['id'],'name':file['name'],'path':'ns:202238505/'+file['path_display'],'image_url':'https://www.dropbox.com/preview'+quote(file['path_display'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(folder['path_display'],safe='/'),'native_reference_status':'CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED','source_qualified_visual_binding':True,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False}
basis='Owner confirms Egyptian Palm Three — White (Three Leaves) as the SECOND panel from the LEFT in this four-panel garden-wall scene. The visible planting and wall setting support a qualified in situ association. The owner reply confirms component identity only; no explicit image-role approval, authenticated client installation, creation origin, measured size, weight, material or fitted fixing is inferred. The original primary image remains a product photograph and is explicitly excluded from the in situ role. Other three panel identities are unchanged.'
opts={x['product_id']:x for x in g['options']};cov={x['option_id']:x for x in a['coverage']};o=opts[oid];c=cov[oid];assert o['file_id']=='id:cnqzTNngPVsAAAAAAAykzQ'and c['in_situ']['status']=='No verified image'
c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(c['in_situ']));c['in_situ']={'status':'Available','reference':r,'basis':basis,'member_position':target['position'],'owner_component_identity_confirmation':{'decision_id':approval['decision_id'],'path':m['owner_component']['path'],'sha256':m['owner_component']['sha256']},'explicit_owner_image_role_approval':False,'source_qualified_visual_binding':True,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False};c.setdefault('notes',[]).append(basis)
o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']});o.update(context_status='Available',context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'],context_description=basis);o['photo_coverage']['in_situ']='Available';o['current_garden_component_confirmation']={'decision_id':approval['decision_id'],'scope':'COMPONENT_IDENTITY_ONLY','reference':r,'position':target['position'],'qualified_role_assessment':basis};o['primary_image_role_correction']={'packet':m['owner_role_correction']['path'],'sha256':m['owner_role_correction']['sha256'],'primary_file_id':o['file_id'],'in_situ':False}
state={'state':'OWNER_CONFIRMED_COMPONENT_QUALIFIED_GARDEN_CONTEXT','finding':basis,'next_action':'Keep the qualified garden association and its provenance limits.','source_reference':r,'owner_component_confirmation_only':True}
c.setdefault('terminal_task_review',{})['in_situ']=copy.deepcopy(state);o.setdefault('current_photo_task_review',{}).setdefault('roles',{})['in_situ']=copy.deepcopy(state)
actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='In situ'and x['status']=='Open'];assert len(actions)==1
x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action='Use the qualified garden-scene association: Egyptian Palm Three is second from left.',reference=r,qualification=basis,owner_response='Yes — component identity only.',resolution_kind=state['state'])
for x in reviews:
 if x.get('option_id')==oid and x.get('role')=='In situ':x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=r)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==oid:
  x.setdefault('remaining_evidence_gaps',[]).append(basis)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+basis
assets[r['file_id']]={**assets.get(r['file_id'],{}),**r,'thumb':source['path'],'original':source['path'],'sha256':source['sha256'],'current_original_content_rehashed':True,'pixels_edited':False}
for k,v in [(file['id'],file),(folder['id'],folder)]:objects[k]={'file_id':k,'object_type':'file'if k==file['id']else'folder','display_path':v['path_display'],'path':'ns:202238505/'+v['path_display'],'name':v['name'],'parent_id':folder['id']if k==file['id']else objects.get(k,{}).get('parent_id'),'size':v.get('size',0)}
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];counts=a['counts'];counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']))
assert counts['required_picture_actions']==72 and counts['in_situ_statuses']['No verified image']==52 and counts['series_statuses']['No verified image']==18 and counts['actions_by_type']['Find / capture']==71
item={'option_id':oid,'name':o['name'],'role':'In situ','basis':basis,'references':[{'role':'In situ','reference':r,'target_member_position':target['position']}],'approval':{'path':m['owner_component']['path'],'sha256':m['owner_component']['sha256'],'decision_id':approval['decision_id'],'scope':'COMPONENT_IDENTITY_ONLY'},'technical_individual_status':c['individual']['status']}
result={'status':'QUEUED_WORKSHOP_LINKS_AND_GARDEN_COMPONENT_IMPORTED','recorded_utc':now(),'overlays_imported':[{k:v for k,v in m[key].items()if k in ['path','sha256']}for key in overlays],'current_counts':counts,'imported_component_confirmation':item,'qualified_in_situ_roles_closed':1,'explicit_owner_image_role_approvals_added':0,'workshop_image_paths_refreshed':13,'same_ids_and_actual_parents_preserved':True,'physical_or_commercial_values_changed':0,'native_or_platform_mutations':0}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(g['latest_context_folder_refresh']));g['latest_context_folder_refresh']=result;g['latest_queued_master_import']=result;g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=copy.deepcopy(counts),recorded_utc=now(),status='CURRENT_WORKSHOP_AND_GARDEN_COMPONENT_IMPORT',scope='BOLDSTONE MASTER only; two workshop folder names refreshed and Egyptian Palm3 garden context qualified through owner-confirmed component identity.')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);g['latest_draft_media_synchronization']={'status':'CURRENT_GARDEN_REFERENCE_MEDIA_CONDITIONS','option_ids':[oid],'physical_or_platform_claims_changed':False}
a.update(recorded_utc=now(),status='CURRENT_WORKSHOP_AND_GARDEN_COMPONENT_IMPORT',latest_context_folder_refresh=result,latest_queued_master_import=result)
g.setdefault('imported_owner_review_packets',[]).append({'path':m['owner_component']['path'],'sha256':m['owner_component']['sha256'],'decision_id':approval['decision_id'],'scope':'COMPONENT_IDENTITY_ONLY_WITH_QUALIFIED_VISUAL_CONTEXT_ASSESSMENT'})
for x,y in zip(g['options'],old['options']):
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details']:assert x[k]==y[k],(x['product_id'],k)
assert g['summary']==old['summary']and g['original_review_specification_assertions']==old['original_review_specification_assertions']
previous_prep=read(O/'preparation-verification.json');prep={k:previous_prep[k]for k in ['owner_accepted_qualified_reference_exceptions','previously_approved_complete_individual_images']};prep.update(status=result['status'],recorded_utc=now(),scope={'overlays':{k:m[k]['path']for k in overlays},'component_confirmation':m['owner_component']['path'],'source_root':'/BOLDSTONE MASTER'},imported_approvals=[item],current_counts=counts,latest_queued_master_import=result,earlier_qualified_reference_sets_retained=True)
ledger=project(read(O/'context-review-ledger.json'))
for x in ledger['tasks']:
 if x['option_id']==oid and x['role']=='In situ':x.update(status_after='Resolved',outcome=state['state'],current_finding=basis,current_reference=r)
pending=read(m['pending']['snapshot']);imported={m[k]['path']for k in overlays};pending['entries']=[x for x in pending['entries']if x['path']not in imported];pending.setdefault('imported_in_this_release',[]).extend(result['overlays_imported']);pending['current_imported_component_confirmation']={'path':m['owner_component']['path'],'sha256':m['owner_component']['sha256'],'scope':'COMPONENT_IDENTITY_ONLY'}
rs=read(m['review_state']['snapshot']);rs['queues']['in_situ']=[x for x in rs['queues']['in_situ']if x!=oid];rs.setdefault('completed_owner_reviews',[]).append({'option_id':oid,'component_position':'Second from left in garden scene','qualified_in_situ_association':True,'explicit_image_role_approval':False,'physical_verification':False})
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('preparation-verification.json',prep),('context-review-ledger.json',ledger),('pending-followups.json',pending),('guided-owner-review-state.json',rs),('queued-import-summary.json',result)]:write(H/name,z)
write(H/'scope.json',{'overlays':{k:m[k]['path']for k in overlays},'component_confirmation':m['owner_component']['path'],'source_root':'/BOLDSTONE MASTER'})
write(H/'original-verification.json',{'files':[{'file_id':file['id'],'local_original':source['path'],'sha256':source['sha256']}],'pixels_edited':False})
write(H/'source-evidence-verification.json',{'status':'PASS','sealed_overlay_receipts_checked':verified_receipts,'fresh_workshop_file_ids_checked':13,'owner_component_event_sha256':event['event_sha256'],'fresh_garden_id_revision_size_parent_verified':True,'component_identity_only':True,'explicit_image_role_approval_inferred':False})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-folder-evidence.json','fresh-garden-metadata.json']})
print(json.dumps({'status':result['status'],'in_situ_gaps':52,'series_gaps':18,'required_actions':72,'folder_paths_refreshed':13,'explicit_image_role_approvals_added':0}))
