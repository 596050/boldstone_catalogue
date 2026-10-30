"""One qualified owner-context binding; current paths by native file ID only."""
import collections, copy, hashlib, json, posixpath, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit, parse_qs

H=Path(__file__).resolve().parent; B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,z): Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json'); p=read(m['pointer']['snapshot']); O=Path(m['master_register']['path']).parent
extra={**{k:O/f for k,f in [('native_map','current-native-reference-map.json'),('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json')]},
 'pending':B/p['queued_followup_packets']['path'],
 'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json',
 'owner_context':B/'components/parallel-reviews/fountain-palm-egyptian-bronze-verdigris-context-refresh-2026-10-23/owner-context-review.json',
 'overlay':B/'components/parallel-reviews/fountain-palm-egyptian-bronze-verdigris-context-refresh-2026-10-23/current-path-overlay.json'}
for key,path in extra.items():
 if key not in m:
  snapshot=H/'inputs'/(key+'.before');shutil.copy2(path,snapshot);m[key]={'path':str(path),'snapshot':str(snapshot),'sha256':sha(path)}
write(H/'input-manifest.json',m)
for k,x in m.items(): assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
assert m['owner_context']['sha256']=='64a227d881ce38e1e31f30f5fc65d20b66179f9f07dc9e279230960349c63bb0'
assert m['overlay']['sha256']=='b75ac82cef48d0d8ef592df22051fda64bd95580842fd4251c3e42eb978accda'
old=read(m['master_register']['snapshot']);g=copy.deepcopy(old);a=read(m['audit']['snapshot']);native=read(m['native_map']['snapshot']);objects=native['current_objects'];oldpaths=native['old_path_to_id']
d=read(m['overlay']['snapshot']);approval=read(m['owner_context']['snapshot']);fresh=read(H/'fresh-fountain-evidence.json');folder=fresh['folder']['folder'];listing=fresh['listing'];moved={x['file_id']:x for x in d['files']if x['parent_changed']}
assert len(d['files'])==83 and len(moved)==14 and not listing['has_more']and not listing['cursor']
assert folder['id']=='id:cnqzTNngPVsAAAAAAA6Vqw'; actual={x['file_id']:x for x in listing['entries']};assert set(actual)==set(moved)
for fid,x in moved.items():
 assert actual[fid]['path']==x['namespace_path']and actual[fid]['file']['size']==x['size']
 assert posixpath.dirname(x['path_display'])==folder['path_display']and x['folder_id']==folder['id']
 previous=objects.get(fid,{})
 if previous.get('display_path'):oldpaths[previous['display_path'].casefold()]=fid
 objects[fid]={**previous,'file_id':fid,'object_type':'file','display_path':x['path_display'],'path':x['namespace_path'],'name':x['name'],'parent_id':folder['id'],'size':x['size']}
 oldpaths[x['path_display'].casefold()]=fid
objects[folder['id']]={**objects.get(folder['id'],{}),'file_id':folder['id'],'object_type':'folder','display_path':folder['path_display'],'path':'ns:202238505/'+folder['path_display'],'name':folder['name'],'parent_id':objects['id:cnqzTNngPVsAAAAAAAyiew'].get('parent_id'),'size':0};oldpaths[folder['path_display'].casefold()]=folder['id']
def currenturl(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return s
 u=urlsplit(s);path=unquote(u.path)
 for route in ['/home','/preview']:
  if path.startswith(route+'/'):path=path[len(route):];break
 name=parse_qs(u.query).get('preview',[''])[0];path+=('/'+name if name else'');fid=oldpaths.get(path.casefold())
 if fid not in moved or path.casefold()==moved[fid]['path_display'].casefold():return s
 return 'https://www.dropbox.com/preview'+quote(moved[fid]['path_display'],safe='/')
immutable={'specifications','master_fields','selling_details','original_visual_record','original_review_specification_assertions','source_only_assertions_not_applied_to_options','input_manifest','master_input_manifest','source_ref','master_ref','evidence_ref'}
def project(z):
 if isinstance(z,list):return[project(x)for x in z]
 if not isinstance(z,dict):return currenturl(z)
 out={k:copy.deepcopy(x)if k in immutable or k.startswith(('historical_','prior_','before_','candidate_review_before_'))else project(x)for k,x in z.items()};fid=out.get('file_id')
 if fid in moved:
  x=moved[fid]
  for k,v in [('folder_id',x['folder_id']),('path',x['namespace_path']),('image_url',x['image_url']),('folder_url',x['folder_url'])]:
   if k in out:out[k]=v
 return out
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions','arrangement_context_references','current_listing_resolution_details','current_listing_source_links','current_listing_match_evidence','current_listing_issues']:g[layer]=project(g[layer])
for layer in ['coverage','missing_pictures','identity_review']:a[layer]=project(a[layer])
reviews=project(read(m['report_reviews']['snapshot']));assets=project(read(m['report_assets']['snapshot']));event=approval['owner_source']
raw=next(line.rstrip('\n')for line in Path(event['transcript_path']).open()if hashlib.sha256(line.rstrip('\n').encode()).hexdigest()==event['event_sha256']);assert json.loads(raw)['timestamp']==event['timestamp']
assert event['exact_text']=="I've added in situ"
originals=read(H/'original-verification.json')
for r in approval['targets'][0]['references']:
 key='preferred'if r['file_id'].endswith('sPzg')else'alternate';md=fresh[key]['file'];source=r['current_original_check'];assert md['id']==r['file_id']and md['rev']==r['rev']and md['size']==source['bytes']and md['path_display']==r['path_display']and sha(source['path'])==source['sha256']
 assets[r['file_id']]={**assets.get(r['file_id'],{}),**r,'path':moved[r['file_id']]['namespace_path'],'thumb':source['path'],'original':source['path'],'sha256':source['sha256'],'current_original_content_rehashed':True,'pixels_edited':False}
 if not any(x.get('file_id',x.get('id'))==r['file_id']for x in originals['files']):originals['files'].append({'file_id':r['file_id'],'local_original':source['path'],'sha256':source['sha256'],'pixels_edited':False})
primary=fresh['primary']['file'];assert primary['id']=='id:cnqzTNngPVsAAAAAAAylDg'and primary['path_display']==approval['individual_primary_unchanged']['source_metadata']['path_display']and primary['rev']==approval['individual_primary_unchanged']['source_metadata']['rev']
for x in originals['files']:x.setdefault('file_id',x.get('id'))
write(H/'original-verification.json',originals)
oid='BSI-70ECBB049292';o=next(x for x in g['options']if x['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid);assert c['in_situ']['status']=='No verified image'and o['file_id']==primary['id']
base=approval['targets'][0]['references'][0];r={k:base[k]for k in ['file_id','folder_id','name','image_url','folder_url']};r.update(path=moved[r['file_id']]['namespace_path'],native_reference_status='CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED',source_qualified_visual_binding=True,physical_cast_or_size_certified=False,scene_authenticity_verified=False)
basis='Owner designated the new In Situ folder after reporting "I\'ve added in situ". The kept Bronze and Verdigris panel is fully visible on a yellow display board indoors, with staircase and furnishings visible. Use082 as a qualified owner-designated display-context reference;003 remains an alternate outdoor workshop-support view. This closes the catalogue context task only: no permanent or authenticated client installation, measured dimensions, weight, maker composition or fitted fixing is certified. Solo views do not resolve its series-image task. The individual product image001 remains unchanged.'
c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(c['in_situ']));c['in_situ']={'status':'Available','reference':r,'basis':basis,'owner_context_designation':{'decision_id':approval['decision_id'],'path':m['owner_context']['path'],'sha256':m['owner_context']['sha256']},'explicit_owner_image_role_approval':False,'source_qualified_visual_binding':True,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False,'display_context_only':True};c.setdefault('notes',[]).append(basis)
o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k))for k in ['context_status','context_file_id','context_folder_id','context_image_url','context_folder_url','context_description']});o.update(context_status='Available',context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'],context_description=basis);o['photo_coverage']['in_situ']='Available';o['current_owner_designated_display_context']={'decision_id':approval['decision_id'],'reference':r,'qualification':basis}
state={'state':'OWNER_DESIGNATED_QUALIFIED_DISPLAY_CONTEXT','finding':basis,'next_action':'Keep the display-context qualification; series task remains open.','source_reference':r,'display_context_only':True}
c['terminal_task_review']['in_situ']=copy.deepcopy(state);o.setdefault('current_photo_task_review',{}).setdefault('roles',{})['in_situ']=copy.deepcopy(state)
actions=[x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='In situ'and x['status']=='Open'];assert len(actions)==1
x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Resolved',action='Use owner-designated indoor display082 as qualified context.',reference=r,qualification=basis,owner_response=event['exact_text'],resolution_kind=state['state'])
for x in reviews:
 if x.get('option_id')==oid and x.get('role')=='In situ':x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],source_reference=r)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']==oid:
  x.setdefault('remaining_evidence_gaps',[]).append(basis)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+basis
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];counts=a['counts'];counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']))
assert(counts['required_picture_actions'],counts['in_situ_statuses']['No verified image'],counts['series_statuses']['No verified image'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'])==(71,51,18,70,83)
item={'option_id':oid,'name':o['name'],'role':'In situ — qualified owner-designated display context','basis':basis,'references':[{'role':'In situ — display context','reference':r}],'approval':{'path':m['owner_context']['path'],'sha256':m['owner_context']['sha256'],'decision_id':approval['decision_id'],'scope':'OWNER_CONTEXT_DESIGNATION_AND_COORDINATOR_VISUAL_ASSESSMENT'},'technical_individual_status':c['individual']['status']}
result={'status':'FOUNTAIN_OWNER_DISPLAY_CONTEXT_IMPORTED','recorded_utc':now(),'overlays_imported':[{'path':m['overlay']['path'],'sha256':m['overlay']['sha256']}],'current_counts':counts,'imported_context_confirmation':item,'qualified_in_situ_roles_closed':1,'explicit_owner_image_role_approvals_added':0,'image_actual_parent_paths_refreshed':14,'stable_file_ids_retained':83,'physical_or_commercial_values_changed':0,'native_or_platform_mutations':0}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(g['latest_context_folder_refresh']));g['latest_context_folder_refresh']=result;g['latest_qualified_display_context_import']=result;g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=copy.deepcopy(counts),recorded_utc=now(),status=result['status'],scope='BOLDSTONE MASTER only;14 Fountain Palm actual parents refreshed and one owner-designated display context bound with provenance limits.')
for key,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][key]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(key+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);g['latest_draft_media_synchronization']={'status':'CURRENT_FOUNTAIN_DISPLAY_CONTEXT_MEDIA_CONDITIONS','option_ids':[oid],'physical_or_platform_claims_changed':False}
a.update(recorded_utc=now(),status=result['status'],latest_context_folder_refresh=result)
g.setdefault('imported_owner_review_packets',[]).append({**item['approval']})
pdfs={x['file_id']:x for x in originals['files']if x.get('pages')};spec_review={'status':'SOURCE_CONFLICTS_RETAINED_NO_PHYSICAL_UPGRADE','recorded_utc':now(),'family':'Acanthus','sources':[{'file_id':fid,'path':x['path'],'sha256':x['sha256'],'page':2,'square_panel_face_cm':[30,30],'listed_weight_kg':5.5 if fid.endswith('uuFg')else 6.5,'scope':'Illustrated White Acanthus square-panel source claim; not specific to Sandstone or Pewter.'}for fid,x in pdfs.items()],'conclusion':'Brochure versions conflict on square-panel weight. Keep existing option-specific working values and owner statements; do not transfer the White source weights to Sandstone/Pewter. No exact missing Sandstone or Pewter series photograph appears on the reviewed page2 images.','rear_observation':{'file_id':'id:cnqzTNngPVsAAAAAAAygEw','name':'acanthus__acanthus-two-leaves-bronze__006.jpg','visible_fixing':'One recessed metal keyhole-style hanger visible on the photographed rear.','limits':'Front/back cast identity and load rating unverified; does not verify other options or material composition.'},'physical_values_changed':0,'physical_verifications_added':0}
g.setdefault('current_specification_evidence_reviews',[]).append(spec_review);write(H/'specification-evidence-review.json',spec_review)
for x,y in zip(g['options'],old['options']):
 for key in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','physical_specifications_verified']:assert x[key]==y[key],(x['product_id'],key)
assert g['summary']==old['summary']and g['original_review_specification_assertions']==old['original_review_specification_assertions']
previous=read(O/'preparation-verification.json');prep={k:previous[k]for k in ['owner_accepted_qualified_reference_exceptions','previously_approved_complete_individual_images']};prep.update(status=result['status'],recorded_utc=now(),imported_approvals=[item],current_counts=counts,earlier_qualified_reference_sets_retained=True)
ledger=project(read(O/'context-review-ledger.json'))
for x in ledger['tasks']:
 if x['option_id']==oid and x['role']=='In situ':x.update(status_after='Resolved',outcome=state['state'],current_finding=basis,current_reference=r)
rs=read(m['review_state']['snapshot']);rs['queues']['in_situ']=[x for x in rs['queues']['in_situ']if x!=oid];rs.setdefault('completed_owner_reviews',[]).append({'option_id':oid,'qualified_display_context':True,'source_file_id':r['file_id'],'explicit_exact_image_role_approval':False,'physical_verification':False})
pending=read(m['pending']['snapshot'])
for name,z in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-native-reference-map.json',native),('current-assets.json',assets),('photo-review-queue.json',reviews),('preparation-verification.json',prep),('context-review-ledger.json',ledger),('pending-followups.json',pending),('guided-owner-review-state.json',rs),('context-import-summary.json',result)]:write(H/name,z)
write(H/'scope.json',{'overlays':{},'owner_context':m['owner_context']['path'],'source_root':'/BOLDSTONE MASTER'})
write(H/'source-evidence-verification.json',{'status':'PASS','fresh_moved_file_ids_checked':14,'all_scope_file_ids_retained':83,'owner_context_event_sha256':event['event_sha256'],'fresh_file_id_revision_size_parent_verified':True,'display_context_only':True,'series_gap_unchanged':True,'physical_or_commercial_values_changed':0})
write(H/'evidence-manifest.json',{str(H/name):{'sha256':sha(H/name)}for name in ['fresh-fountain-evidence.json','specification-evidence-review.json']})
print(json.dumps({'status':result['status'],'in_situ_gaps':51,'series_gaps':18,'required_actions':71,'paths_refreshed':14}))
