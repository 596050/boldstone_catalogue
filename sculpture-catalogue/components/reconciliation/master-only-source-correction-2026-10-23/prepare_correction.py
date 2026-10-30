"""Apply the owner's Master-only source restriction without changing identities or specifications."""
import collections,copy,hashlib,json,posixpath,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote
H=Path(__file__).resolve().parent; B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json'); O=Path(m['register']['path']).parent
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
g=read(m['register']['snapshot']); old=copy.deepcopy(g); a=read(m['audit']['snapshot']); olda=copy.deepcopy(a)
family='https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Acanthus'
familyid='id:cnqzTNngPVsAAAAAAAt_GA'; sand='BSI-C41824131174'; pewter='BSI-3635E3DC3434'
badfiles={'id:cnqzTNngPVsAAAAAAA6LRw','id:cnqzTNngPVsAAAAAAA6LRQ','id:cnqzTNngPVsAAAAAAAudqw','id:cnqzTNngPVsAAAAAAAuV6Q'}
badparents={'id:cnqzTNngPVsAAAAAAA6LRA','id:cnqzTNngPVsAAAAAAA6Vng','id:cnqzTNngPVsAAAAAAAyh4Q'}
now=datetime.now(timezone.utc).isoformat()
policy={'status':'OWNER_REQUIRED_BOLDSTONE_MASTER_ONLY','recorded_utc':now,'owner_text':'why are you going into back photo, focus exclusively on the boldstone master','permitted_root':'/BOLDSTONE MASTER','backup_searches_and_current_references_permitted':False,'historical_audit_retained':True,'source_scope_is_not_identity_or_physical_specification_change':True,'live_evidence':str(H/'live-master-evidence.json')}
live=read(H/'live-master-evidence.json'); ls=live['listing'];assert not ls['has_more'] and not ls['cursor']
assert len(ls['entries'])==95 and sum(x['object_type']=='file'for x in ls['entries'])==79
assert not any(x['file_id']in badfiles for x in ls['entries'])
liveobjects={x['file_id']:x for x in ls['entries']}
paths={x['path'].casefold():x['file_id']for x in ls['entries']if x['object_type']=='folder'}
paths['ns:202238505//BOLDSTONE MASTER/Products/01 Wall Sculptures/Acanthus'.casefold()]=familyid
immutable={'specifications','master_fields','selling_details','original_review_specification_assertions','source_only_assertions_not_applied_to_options','input_manifest','master_input_manifest','source_ref','master_ref','evidence_ref'}
def historic(k):return k.startswith(('historical_','prior_','before_','candidate_review_before_'))
def outside(s):return isinstance(s,str)and 'BOLDSTONE_BACKUP'in unquote(s).upper()
def clean(z):
 if isinstance(z,list):return[clean(v)for v in z]
 if not isinstance(z,dict):return '' if outside(z) else z
 out={k:copy.deepcopy(v)if k in immutable or historic(k)else clean(v)for k,v in z.items()if k!='backup_source_lineage'}
 fid=z.get('file_id')
 if fid in badfiles:
  out.update(file_id='Unbound',folder_id='',image_url='',folder_url='',current_family_navigation_url=family,current_family_folder_id=familyid,native_reference_status='NO_VERIFIED_CURRENT_BOLDSTONE_MASTER_IMAGE',current_source_scope='/BOLDSTONE MASTER')
  for k in ['path','archived_original','original','thumb','backup_copy_sha256','historical_original_file_id','historical_original_lookup_status']:
   out.pop(k,None)
  if 'product_id'not in z:out['name']='Current Master photograph required'
 elif fid in liveobjects:
  x=liveobjects[fid];dp='/'+x['path'].split('//',1)[1];parent=paths.get(posixpath.dirname(x['path']).casefold())
  if x['object_type']=='file':
   assert parent,('Current actual parent missing',fid,x['path'])
   for k,v in [('folder_id',parent),('image_url','https://www.dropbox.com/preview'+quote(dp,safe='/')),('folder_url','https://www.dropbox.com/home'+quote(posixpath.dirname(dp),safe='/')),('path',x['path'])]:
    if k in out:out[k]=v
 return out
for k in list(g):
 if k not in immutable and not historic(k):g[k]=clean(g[k])
for k in ['coverage','missing_pictures','identity_review','primary_reference_changes','context_reference_changes']:a[k]=clean(a[k])
opts={x['product_id']:x for x in g['options']}; cov={x['option_id']:x for x in a['coverage']}
def missing_ref():return {'file_id':'Unbound','folder_id':'','name':'Current Master photograph required','image_url':'','folder_url':'','current_family_navigation_url':family,'current_family_folder_id':familyid,'native_reference_status':'NO_VERIFIED_CURRENT_BOLDSTONE_MASTER_IMAGE','physical_cast_or_size_certified':False}
note='Current image evidence is restricted to BOLDSTONE MASTER by owner instruction. The complete current Acanthus listing does not contain the former Sandstone detail or workshop group. Find or take the exact photograph in Master; historical owner-confirmed identity remains recorded.'
for oid in [sand,pewter]:
 c=cov[oid]; c.setdefault('historical_source_scope_corrections',[]).append({'date':now,'series_before':copy.deepcopy(next(x for x in olda['coverage']if x['option_id']==oid)['series'])})
 c['series'].update(status='No verified image',reference=missing_ref(),basis=note,terminal_review_state='MASTER_IMAGE_REQUIRED',reference_is_candidate_only=False,current_source_scope='/BOLDSTONE MASTER')
 c.setdefault('notes',[]).append(note);opts[oid]['photo_coverage']['series']='No verified image'
 role={'state':'MASTER_IMAGE_REQUIRED','finding':note,'next_action':'Find or take a current Master series image.','source_reference':missing_ref()}
 c.setdefault('terminal_task_review',{})['series']=copy.deepcopy(role)
 opts[oid].setdefault('current_photo_task_review',{}).setdefault('roles',{})['series']=copy.deepcopy(role)
 opts[oid]['current_source_scope_policy']=copy.deepcopy(policy)
c=cov[sand]; c['individual'].update(status='No verified image',reference=missing_ref(),basis=note,terminal_review_state='MASTER_IMAGE_REQUIRED')
opts[sand].update(file_id='Unbound',folder_id='',image_url='',folder_url='',current_family_navigation_url=family,current_family_folder_id=familyid,native_reference_status='NO_VERIFIED_CURRENT_BOLDSTONE_MASTER_IMAGE',current_link_basis=note)
opts[sand]['photo_coverage']['individual']='No verified image'
reopened=[]
for x in a['missing_pictures']:
 if x['option_id']in [sand,pewter]and x['role']=='Series':
  x.setdefault('historical_actions',[]).append(copy.deepcopy(next(y for y in olda['missing_pictures']if y['option_id']==x['option_id']and y['role']=='Series')))
  x.update(status='Open',action_type='Find / capture',action='Find or take a series photograph in BOLDSTONE MASTER showing this finish.',reference=missing_ref(),qualification=note,resolution_kind='REOPENED_CURRENT_MASTER_SOURCE_REQUIRED')
  reopened.append({'option_id':x['option_id'],'role':'Series'})
 if x['option_id']==sand and x['role']in ['Individual','In situ']:
  x.update(reference=missing_ref(),qualification=note)
  if x['role']=='Individual':x['action']='Find or take a complete individual Sandstone photograph in BOLDSTONE MASTER.'
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']in [sand,pewter]:
  x.setdefault('remaining_evidence_gaps',[]).append(note)
  if x.get('draft_listing'):x['draft_listing']['media_condition']+='\n'+note
reviews=clean(read(m['reviews']['snapshot']))
for x in reviews:
 if x.get('option_id')in [sand,pewter]and x.get('role')=='Series' or x.get('option_id')==sand and x.get('role')=='Individual':x.update(review_state='MASTER_IMAGE_REQUIRED',finding=note,next_action='Find or take the exact image in BOLDSTONE MASTER.',source_reference=missing_ref())
state=clean(read(m['state']['snapshot']));state.update(status='MASTER_ONLY_ACANTHUS_IMAGE_REQUIRED',source_scope_policy=policy,pending_question='Find or take the current Sandstone photograph in BOLDSTONE MASTER; the former fallback-image choice is superseded.',superseded_pending_question={'status':'SUPERSEDED_BY_OWNER_MASTER_ONLY_SCOPE','owner_choice_required':False})
state['queues']['series']=[x['option_id']for x in a['missing_pictures']if x['role']=='Series'and x['status']=='Open']
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];opened=[x for x in active if x['status']=='Open'];counts=a['counts']
counts.update(individual_statuses=dict(collections.Counter(x['individual']['status']for x in a['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=len(opened),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']),archived_source_files_currently_not_found=2)
assert counts['required_picture_actions']==73 and counts['series_statuses']['No verified image']==18 and counts['resolved_action_rows']==81 and counts['actions_by_type']['Find / capture']==72
g['summary']['individual_options_with_dropbox_reference']=186
result={'status':'MASTER_ONLY_CURRENT_REFERENCES_CORRECTED','recorded_utc':now,'policy':policy,'affected_option_ids':[sand,pewter],'series_actions_reopened':reopened,'historical_owner_identity_confirmations_preserved':True,'specifications_or_commercial_values_changed':0,'native_or_platform_mutations':0,'current_counts':counts,'scope_note':note}
g.setdefault('historical_context_folder_refreshes',[]).append(copy.deepcopy(old['latest_context_folder_refresh']))
g['latest_master_only_source_correction']=result;g['current_dropbox_source_policy']=policy
g['latest_context_folder_refresh']=result
a.update(recorded_utc=now,status='CURRENT_MASTER_ONLY_SOURCE_CORRECTION',current_dropbox_source_policy=policy,latest_master_only_source_correction=result)
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']))
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=copy.deepcopy(counts),recorded_utc=now,status=a['status'],scope='BOLDSTONE MASTER only; Sandstone current image unavailable and two series gaps reopened. All earlier qualified approvals retained.')
g['latest_image_coverage_audit'].pop('audit_sha256',None)
for o,p in zip(g['options'],old['options']):
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details']:assert o[k]==p[k],(o['product_id'],k)
assert g['original_review_specification_assertions']==old['original_review_specification_assertions']
native=read(m['native_map']['snapshot']);native['current_objects']={k:v for k,v in native['current_objects'].items()if not outside(v.get('display_path',''))}
native['old_path_to_id']={k:v for k,v in native['old_path_to_id'].items()if not outside(k)and v not in badfiles}
native['byte_identical_backup_replacements']={};native['current_source_policy']=policy
assets={k:clean(v)for k,v in read(m['assets']['snapshot']).items()if k not in badfiles and not any(outside(v.get(f,''))for f in ['path','image_url','folder_url'])}
priorprep=read(O/'preparation-verification.json');priorprep.pop('byte_identical_backup_reference_replacements',None);priorprep.update(current_counts=counts,source_scope_correction=result)
ledger=clean(read(O/'context-review-ledger.json'))
for x in ledger['tasks']:
 if x['option_id']in [sand,pewter]and x['role']=='Series':x.update(status_after='Open',outcome='MASTER_IMAGE_REQUIRED',current_finding=note,current_reference=missing_ref())
for f,x in [('canonical-master-register.json',g),('image-coverage-current.json',a),('current-assets.json',assets),('photo-review-queue.json',reviews),('guided-owner-review-state.json',state),('pending-followups.json',read(m['pending']['snapshot'])),('current-native-reference-map.json',native),('preparation-verification.json',priorprep),('source-scope-correction.json',result),('context-review-ledger.json',ledger)]:write(H/f,x)
shutil.copy2(O/'scope.json',H/'scope.json')
write(H/'source-evidence-verification.json',{'status':'PASS','permitted_root':'/BOLDSTONE MASTER','checked_descendants':95,'files':79,'folders':16,'pagination_exhausted':True,'out_of_scope_originals_not_used':True})
write(H/'original-verification.json',{'files':[],'scope':'No source pixels downloaded or modified for this correction.'})
write(H/'evidence-manifest.json',{str(H/'live-master-evidence.json'):{'sha256':sha(H/'live-master-evidence.json')}})
print(json.dumps({'status':result['status'],'required_actions':73,'in_situ_gaps':53,'series_gaps':18,'current_individual_reference_options':186,'specification_changes':0}))
