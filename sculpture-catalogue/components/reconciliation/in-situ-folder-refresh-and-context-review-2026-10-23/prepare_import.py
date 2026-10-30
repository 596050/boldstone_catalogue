import json,hashlib,copy,collections,posixpath
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def display(p):return '/'+p.split('//',1)[1].lstrip('/')if p.startswith('ns:')else p
m=read(H/'input-manifest.json');scope=read(H/'scope.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
old=read(H/'inputs/master_register.before');g=copy.deepcopy(old);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a);assets=read(H/'inputs/report_assets.before');reviews=read(H/'inputs/report_reviews.before');cross=read(H/'native-current-crosswalk.json');objects=copy.deepcopy(cross['current_objects']);oldpaths=copy.deepcopy(cross['old_path_to_id']);lists=read(H/'context-current-listings.json');roots=read(H/'current-root-folders.json')['entries'];rootids={display(x['path']).casefold():x['file_id']for x in roots}
# Current paths are refreshed by stable ID; folder names do not establish new identities or image roles.
for l in lists.values():
 root=display(l['path']);fid=rootids[root.casefold()];paths={display(x['path']).casefold():x['file_id']for x in l['entries']if x['object_type']=='folder'};paths[root.casefold()]=fid
 objects[fid]={'file_id':fid,'object_type':'folder','display_path':root,'path':'ns:202238505/'+root,'name':posixpath.basename(root),'parent_id':None,'size':0}
 for x in l['entries']:
  dp=display(x['path']);objects[x['file_id']]={'file_id':x['file_id'],'object_type':x['object_type'],'display_path':dp,'path':x['path'],'name':x['name'],'parent_id':paths[posixpath.dirname(dp).casefold()],'size':x.get('file',{}).get('size',0)}
# Explicitly record byte-identical backup IDs when historical originals no longer resolve.
replacements={'id:cnqzTNngPVsAAAAAAAudqw':'id:cnqzTNngPVsAAAAAAA6LRw','id:cnqzTNngPVsAAAAAAAuV6Q':'id:cnqzTNngPVsAAAAAAA6LRQ'}
acfiles={x['file_id']:x for x in read(H/'acanthus-download-verification.json')['files']};oldhashes={'id:cnqzTNngPVsAAAAAAAudqw':'15b6aaa850d7bff1446e5b9e3942a926916dc40a072d1df0b3102ff10e66f580','id:cnqzTNngPVsAAAAAAAuV6Q':'987b7a303e4e4dadb0cf5386c9e465a59ff2299179dc4406840e77ddd268d3b6'}
md={**read(H/'source-metadata-current.json'),**read(H/'acanthus-candidate-metadata.json'),**read(H/'new-scene-metadata.json')}
for id,d in md.items():
 kind=d.get('metadata_type');v=d.get(kind,{})
 if kind not in ['file','folder']:continue
 dp=v['path_display'];parent=None
 if kind=='file':
  parent=next((z['file_id']for z in objects.values()if z['object_type']=='folder'and z['display_path'].casefold()==posixpath.dirname(dp).casefold()),None)
  if not parent:parent=next((k for k,d2 in md.items()if d2.get('metadata_type')=='folder'and d2['folder']['path_display'].casefold()==posixpath.dirname(dp).casefold()),None)
 objects[id]={'file_id':id,'object_type':kind,'display_path':dp,'path':'ns:202238505/'+dp,'name':v['name'],'parent_id':parent,'size':v.get('size',0),'rev':v.get('rev')}
for oldid,newid in replacements.items():assert acfiles[newid]['sha256']==oldhashes[oldid]and objects[newid]['parent_id']=='id:cnqzTNngPVsAAAAAAA6LRA'
# Compose later verified path observations so an in-flight workshop move cannot leave stale links.
latepaths={'workshop':B.parent/'reports/dropbox-workshop-material-separation-2026-10-23/current-reference-overlay.json','dune':B/'components/parallel-reviews/dune-ripple-owner-split-recheck-20261023120434Z/current-path-overlay.json'}
workshop=read(latepaths['workshop']);assert workshop['status']=='COMPLETE_VERIFIED'
for z in workshop['receipts']:assert sha(z['path'])==z['sha256']
for x in workshop['objects']:
 dp=display(x['current_path']);objects[x['file_id']]={'file_id':x['file_id'],'object_type':x['object_type'],'display_path':dp,'path':x['current_path'],'name':x['current_name'],'parent_id':x['current_parent_id'],'size':x['size']}
 for key in ['old_path','current_path']:
  if x.get(key):oldpaths[display(x[key]).casefold()]=x['file_id']
dunesummary=read(latepaths['dune'].with_name('recheck-summary.json'))
for z in dunesummary['artifacts']:assert sha(z['path'])==z['sha256']
for x in read(latepaths['dune'])['objects']:
 dp=x['display_path_derived_from_verified_namespace'];objects[x['id']]={**objects.get(x['id'],{}),'file_id':x['id'],'object_type':x['object_type'],'display_path':dp,'path':x['namespace_path'],'name':x['name'],'parent_id':x['parent_folder_id']};oldpaths[dp.casefold()]=x['id']
latepaths['wall-circle']=H/'wall-circle-final-native-readback.json'
wall=read(latepaths['wall-circle'])
for fid,x in wall.items():
 dp=x['path_display'];parent=next((z['file_id']for z in objects.values()if z['object_type']=='folder'and z['display_path']==posixpath.dirname(dp)),None)
 if x['metadata_type']=='file':parent=next(k for k,z in wall.items()if z['metadata_type']=='folder'and z['path_display']==posixpath.dirname(dp))
 objects[fid]={**objects.get(fid,{}),'file_id':fid,'object_type':x['metadata_type'],'display_path':dp,'path':'ns:202238505/'+dp,'name':x['name'],'parent_id':parent,'size':x.get('size',0)};oldpaths[dp.casefold()]=fid
def register_paths(z):
 if isinstance(z,list):
  for v in z:register_paths(v)
 elif isinstance(z,dict):
  if z.get('file_id')and isinstance(z.get('path'),str):oldpaths[display(z['path']).casefold()]=z['file_id']
  for v in z.values():register_paths(v)
register_paths(old['options']);register_paths(olda['coverage']);register_paths(assets)
def ref(fid):
 original_id=fid;fid=replacements.get(fid,fid);x=objects[fid];assert x['object_type']=='file'and x['parent_id'];r={'file_id':fid,'folder_id':x['parent_id'],'name':x['name'],'path':x['path'],'image_url':'https://www.dropbox.com/preview'+quote(x['display_path'],safe='/'),'folder_url':'https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/'),'native_reference_status':'VERIFIED_CURRENT_FILE_ID_AND_ACTUAL_PARENT','physical_cast_or_size_certified':False}
 if original_id!=fid:r.update(historical_original_file_id=original_id,historical_original_lookup_status='CURRENT_LOOKUP_FAILED_AND_NOT_IN_COMPLETE_PRODUCT_FAMILY_LIST',backup_copy_sha256=oldhashes[original_id],native_reference_status='BYTE_IDENTICAL_BACKUP_COPY_WITH_DISTINCT_LIVE_ID')
 return r
def urlid(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return None
 u=urlsplit(s);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):
   p=p[len(route):];name=parse_qs(u.query).get('preview',[''])[0];return oldpaths.get((p+('/'+name if name else '')).casefold())
 return None
def currenturl(s):
 id=urlid(s)
 if id in replacements:id=replacements[id]
 if id not in objects:return s
 x=objects[id]
 u=urlsplit(s);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(u.query).get('preview',[''])[0];p+=('/'+name if name else '')
 if p.casefold()==x['display_path'].casefold():return s
 return 'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
def project(z):
 if isinstance(z,list):return[project(x)for x in z]
 if not isinstance(z,dict):return currenturl(z)
 out={k:copy.deepcopy(v)if k.startswith(('historical_','prior_','original_','before_'))or k in ['specifications','master_fields','accepted_working_fields','six_working_fields','evidence_ref','master_ref','source_ref']else project(v)for k,v in z.items()}
 for fk,pk,ik,uk in [('file_id','folder_id','image_url','folder_url'),('context_file_id','context_folder_id','context_image_url','context_folder_url')]:
  fid=out.get(fk)
  if fid in objects or fid in replacements:
   if fid in objects and objects[fid]['object_type']!='file':continue
   r=ref(fid)
   if fid in replacements:out.setdefault('historical_native_source_identities',[]).append({fk:fid,pk:out.get(pk),'reason':'Use byte-identical backup copy; original native lookup unavailable'});out[fk]=r['file_id'];out['backup_source_lineage']=r
   for k,v in [(pk,r['folder_id']),(ik,r['image_url']),(uk,r['folder_url'])]:
    if k in out:
     target_id=urlid(out[k])if k in [ik,uk]and isinstance(out[k],str)else None
     required_id=r['folder_id']if k==uk else r['file_id']
     out[k]=currenturl(out[k])if target_id==required_id else v
   if 'path'in out:out['path']=r['path']
   if fid in replacements:out['native_reference_status']=r['native_reference_status']
 return out
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references','current_listing_resolution_details','current_listing_source_links','current_listing_match_evidence','current_listing_issues']:
 if layer in g:g[layer]=project(g[layer])
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:
  if 'current_primary_reference'in x:x['current_primary_reference']=project(x['current_primary_reference'])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
reviews=project(reviews);assets=project(assets);opts={x['product_id']:x for x in g['options']};cov={x['option_id']:x for x in a['coverage']};summaries=[]
def close(oid,role,r,basis,approval=None,position=''):
 o=opts[oid];c=cov[oid];rk='in_situ'if role=='In situ'else'series';c.setdefault('historical_'+rk+'_references',[]).append(copy.deepcopy(c[rk]));c[rk]={'status':'Available','reference':r,'basis':basis,'member_position':position,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False,'source_qualified_visual_binding':True,'owner_acceptance':approval}
 c['notes'].append(basis)
 if role=='In situ':
  o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']});o.update(context_status='Available',context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'],context_description=basis)
 o['photo_coverage'][rk]='Available';o.setdefault('current_context_reference_updates',[]).append({'role':role,'reference':r,'basis':basis,'approval':approval})
 state={'state':'OWNER_ACCEPTED_CLOSE_WALL_IN_SITU'if approval else'SOURCE_QUALIFIED_SERIES_MEMBERS_MAPPED','finding':basis,'next_action':'Role association complete. Retain source/provenance limits and remaining separate photo roles.','source_reference':r,'owner_approval':approval}
 for d in [c.setdefault('terminal_task_review',{}),o.setdefault('current_photo_task_review',{}).setdefault('roles',{})]:
  if rk in d:d.setdefault('historical_owner_superseded_reviews',[]).append({'key':rk,'before':copy.deepcopy(d[rk])})
  d[rk]=copy.deepcopy(state)
 actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']==role and x['status']=='Open'];assert len(actions)==1
 x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action='Use the qualified owner-accepted close-wall in situ reference.'if approval else'Both Bronze components mapped in the new complete pair reference.',reference=r,qualification=basis,owner_response=approval.get('owner_text','')if approval else'',resolution_kind=state['state'])
 for x in reviews:
  if x.get('option_id')==oid and x.get('role')==role:x.setdefault('historical_owner_superseded_reviews',[]).append({k:copy.deepcopy(x.get(k))for k in ['review_state','finding','next_action','source_reference']});x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=r)
 summaries.append({'option_id':oid,'name':o['name'],'role':role,'basis':basis,'references':[{'role':role,'reference':r,'target_member_position':position}],'approval':approval,'technical_individual_status':c['individual']['status']})
for key,p in scope['approvals'].items():
 d=read(p);pr={'path':p,'sha256':sha(p),'decision_id':d['decision_id'],'owner_text':d.get('exact_owner_message',d.get('source_owner_event',{}).get('text',''))}
 for z in d['approved_reference_roles']:
  oid=z['product_id'];r=ref(z['source']['id']);position=z.get('target_member_position','')
  basis='Owner accepts this complete close-wall view as the in situ reference for this exact finish. '+('Decowaves 1 is LEFT; Decowaves 2 is RIGHT in the whole Terracotta pair. 'if key=='decowaves'else'The Copper and Copper/Partial Verdigris finishes each retain their own image; their series gaps stay open. ')+'This is a close product-on-wall view; a wider authenticated installation, physical size, material and fitted hardware are not verified.'
  close(oid,'In situ',r,basis,pr,position)
 g.setdefault('imported_owner_review_packets',[]).append({k:v for k,v in pr.items()if k!='owner_text'}|{'imported_utc':now(),'no_physical_or_platform_verification_added':True})
# The newly added Bronze pair matches the kept individual reliefs; map series only, not wider in situ.
white=read(H/'lava-white-pool-owner-approval.json');pr={'path':str(H/'lava-white-pool-owner-approval.json'),'sha256':sha(H/'lava-white-pool-owner-approval.json'),'decision_id':white['decision_id'],'owner_text':white['exact_owner_message']}
for x in white['targets']:
 basis='Owner explicitly accepts the new pool-room scene as the in situ reference for all three White panels. In each repeated triptych, Lava Moon 1 is LEFT, 2 is CENTRE and 3 is RIGHT. Whole scene retained; repeated arrangements do not create extra options. Creation origin, real installation, physical cast, size and material remain unverified.'
 close(x['product_id'],'In situ',ref(white['source_file_id']),basis,pr,x['member_position'])
g['imported_owner_review_packets'].append({k:v for k,v in pr.items()if k!='owner_text'}|{'imported_utc':now(),'no_physical_or_platform_verification_added':True})
newpair=ref('id:cnqzTNngPVsAAAAAAA6VkA')
for oid,pos in [('BSI-718DFFB7EC5D','LEFT'),('BSI-54F871DCF4CA','RIGHT')]:
 basis='New complete Bronze pair shows Spiralfish Wave & Tide 1 LEFT and 2 RIGHT. The raised pointed ridges, large outer spiral, small inner coil and incised flowing marks match the kept corresponding individual references. Whole original retained as a source-qualified SERIES depiction. Creation origin, real cast, size and installation authenticity remain unverified; this close pair does not close the separate in situ task.'
 close(oid,'Series',newpair,basis,None,pos)
# Keep current draft media conditions aligned with role changes; retain all native/physical restrictions.
for x in g['current_listing_resolution_details']['entries']:
 changes=[z for z in summaries if z['option_id']==x['product_id']]
 if changes:
  x.setdefault('historical_media_review_states',[]).append({'remaining_evidence_gaps':copy.deepcopy(x['remaining_evidence_gaps']),'draft_media_condition':x.get('draft_listing',{}).get('media_condition')});text=' '.join(z['basis']for z in changes);x['remaining_evidence_gaps'].append(text)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\nCurrent context update: '+text
for f in ['original-verification.json','acanthus-download-verification.json','new-scene-download-verification.json']:
 for x in read(H/f)['files']:
  rr=ref(x['file_id']);assets[x['file_id']]={**assets.get(x['file_id'],{}),**rr,'thumb':x['local_original'],'original':x['local_original'],'sha256':x['sha256'],'current_original_content_rehashed':True,'pixels_edited':False}
opened=[x for x in a['missing_pictures']if x['status']=='Open'];active=[x for x in a['missing_pictures']if x['status']!='Resolved'];ind=[x for x in opened if x['role']=='Individual'];cap=[x for x in ind if x['action_type']=='Find / capture'];counts=a['counts'];counts.update(individual_statuses=dict(collections.Counter(x['individual']['status']for x in a['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=len(opened),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']))
assert len(opened)==71 and len(ind)==2 and len(cap)==1 and counts['in_situ_statuses']['No verified image']==53 and counts['series_statuses']['No verified image']==16
for o,y in zip(g['options'],old['options']):
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details']:assert o[k]==y[k],(o['product_id'],k)
assert g['original_review_specification_assertions']==old['original_review_specification_assertions']and g['summary']==old['summary']
result={'status':'SEVEN_OWNER_IN_SITU_BINDINGS_FIVE_FOLDER_OVERLAYS_AND_TWO_SERIES_BINDINGS_IMPORTED','recorded_utc':now(),'scope':scope,'imported_approvals':summaries,'owner_in_situ_roles_closed':7,'new_series_roles_closed':2,'complete_individual_images_added':[],'owner_accepted_qualified_reference_exceptions':old['latest_queued_photo_approval_import']['owner_accepted_qualified_reference_exceptions'],'previously_approved_complete_individual_images':old['latest_queued_photo_approval_import']['previously_approved_complete_individual_images'],'current_counts':counts,'native_overlays_verified':5,'actual_parent_overrides':39,'byte_identical_backup_reference_replacements':replacements,'new_physical_verifications':0,'new_platform_writes':0,'native_mutations':0}
result['additional_current_path_readbacks']={k:{'path':str(p),'sha256':sha(p)}for k,p in latepaths.items()}
g.setdefault('historical_draft_media_synchronizations',[]).append(copy.deepcopy(g['latest_draft_media_synchronization']))
g['latest_draft_media_synchronization']={'recorded_utc':now(),'option_ids':[z['option_id']for z in summaries],'qualified_in_situ_bindings_added':7,'qualified_series_bindings_added':2,'complete_individual_images_added':0,'new_physical_verifications':0,'platform_writes':0,'scope':'Current media conditions retain all existing platform and physical restrictions; only accepted context roles and current reference paths changed.'}
# Current source paths and live backup IDs are explicit; historical source assertions retain original IDs.
write(H/'current-native-reference-map.json',{'status':'PASS','current_objects':objects,'old_path_to_id':oldpaths,'byte_identical_backup_replacements':replacements,'backup_original_sha256':oldhashes})
a['latest_context_folder_refresh']=copy.deepcopy(result);a['recorded_utc']=now();a['status']='CURRENT_CONTEXT_FOLDER_REFRESH_2026_10_23';g['latest_context_folder_refresh']=copy.deepcopy(result);g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']));write(H/'image-coverage-current.json',a);g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),audit_sha256=sha(H/'image-coverage-current.json'),counts=counts,status=a['status'],scope='188 options. Seven owner-accepted in situ bindings, five completed native folder overlays and two source-qualified Bronze series bindings. Acanthus complete Sandstone image remains pending.',verification=str((H/'saved-file-verification.json').relative_to(B)),visual_verification=str((H/'visual-verification.json').relative_to(B)))
for k in ['verification_sha256','visual_verification_sha256','native_binding_verification','native_binding_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g);write(H/'current-assets.json',assets);write(H/'photo-review-queue.json',reviews);write(H/'preparation-verification.json',result)
state=read(H/'inputs/guided_state.before');state.update(status='CONTEXT_IMPORT_PREPARED_ACANTHUS_OWNER_IMAGE_CHOICE_PENDING',queues={'individual':[x['option_id']for x in cap],'in_situ':[x['option_id']for x in opened if x['role']=='In situ'],'series':[x['option_id']for x in opened if x['role']=='Series']});write(H/'guided-owner-review-state.json',state)
pending=read(H/'inputs/pending_followups.before');applied=set(scope['approvals'].values())|set(scope['overlays'].values());pending['entries']=[x for x in pending['entries']if x['path']not in applied];pending['recorded_utc']=now();pending['frozen_current_scope']=str(H/'scope.json');pending['imported_in_this_release']=[{'path':p,'sha256':sha(p)}for p in applied]
for name in ['dropbox-barbados-workshop-folder-rename-2026-10-23','dropbox-sally-workshop-folder-rename-2026-10-23']:
 p=B.parent/'reports'/name/'current-reference-overlay.json'
 if p.exists():d=read(p);pending['entries'].append({'kind':'native-overlay','path':str(p),'sha256':sha(p),'status':d['status'],'applied_to_current_frozen_release':False,'queue_only_no_coverage_change':True})
write(H/'pending-followups.json',pending)
print(json.dumps({'status':result['status'],'required_actions':71,'in_situ_gaps':53,'series_gaps':16,'options':188,'source_paths_in_current_map':len(objects),'queued_native_overlays':len(pending['entries'])}))
