import json, hashlib, copy, collections
from pathlib import Path
from datetime import datetime, timezone

H=Path(__file__).resolve().parent; B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')

m=read(H/'input-manifest.json'); scope=read(H/'scope.json')
for k,x in m.items(): assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
assert read(H/'source-evidence-verification.json')['status']=='PASS'
old=read(H/'inputs/master_register.before'); g=copy.deepcopy(old)
a=read(H/'inputs/audit.before'); oldaudit=copy.deepcopy(a)
assets=read(H/'inputs/report_assets.before'); reviews=read(H/'inputs/report_reviews.before')
refs=read(H/'current-source-references.json'); original=read(H/'original-verification.json')['files']
opts={x['product_id']:x for x in g['options']}; cov={x['option_id']:x for x in a['coverage']}
packets={oid:read(m['approval_'+oid]['snapshot']) for oid in scope['target_option_ids']}
newaccepted=set(scope['individual_qualified_reference_option_ids']); insitu=set(scope['in_situ_option_ids'])
oldaccepted={x['product_id'] for x in g['options'] if x.get('owner_accepted_listing_references') and cov[x['product_id']]['individual']['status']!='Available'}
assert len(oldaccepted)==5 and not oldaccepted&newaccepted
details={x['product_id']:x for x in g['current_listing_resolution_details']['entries']}
summaries=[]

def pref(oid):
 d=packets[oid]
 return {'path':scope['approvals'][oid],'sha256':m['approval_'+oid]['sha256'],'decision_id':d['decision_id']}

def current_review(container,key,value):
 if key in container: container.setdefault('historical_owner_superseded_reviews',[]).append({'key':key,'before':copy.deepcopy(container[key]),'superseded_utc':now()})
 container[key]=copy.deepcopy(value)

for oid in scope['target_option_ids']:
 d=packets[oid]; o=opts[oid]; c=cov[oid]; pr=pref(oid)
 approved=[]
 for z in d['approved_reference_roles']:
  fid=z['source'].get('file_id',z['source'].get('id')); rr=copy.deepcopy(refs[fid])
  assert fid==rr['file_id']
  approved.append({**copy.deepcopy(z),'reference':rr})
 role='Individual' if oid in newaccepted else 'In situ'; rolekey='individual' if oid in newaccepted else 'in_situ'
 if oid=='BSI-B1DCB5B08396':
  basis='Owner accepts the whole MP4 / MP2 / MP4 White-and-Gold photograph as MP4’s listing reference. MP4 is the two OUTER panels; the CENTRE panel remains MP2. Technical Group only is retained. The separate-photo request is closed for this option only; no crop, additional option, verified gold leaf or physical cast is asserted.'
 elif oid in newaccepted:
  num=['BSI-725A77437026','BSI-D7C2FC84A86B','BSI-63B177B06578'].index(oid)+1
  pos=['LEFT','CENTRE','RIGHT'][num-1]
  approved[0]['target_member_position']='Complete corresponding numbered White panel; DESIGN ONLY'
  basis=f'Owner accepts the Lava Moon {num} WHITE image as DESIGN ONLY and the whole Sandstone three-panel group as FINISH reference ({pos} panel). White is not a verified standalone Sandstone photograph. Technical Group only is retained; the combined-reference review and separate-photo request are closed by this scoped exception. No crop or physical/provenance verification is asserted.'
 elif oid=='BSI-ADD5F3BEFCF5':
  basis='Owner identifies Cup Ring CRS2 as the RIGHT panel in the whole White garden-wall pair and accepts it as a qualified in situ reference. The LEFT-panel identity is governed by its separate Spiral approval. The archived individual primary is retained. Scene origin, actual cast, measurements and specifications remain unverified.'
 elif oid=='BSI-70BDE00F2855':
  basis='Owner identifies Spiral CRS1 as the LEFT panel in the whole White garden-wall pair and accepts it as a qualified in situ reference. Cup Ring is the RIGHT panel under its separate approval. The existing individual primary is retained. Scene origin, actual cast, measurements and specifications remain unverified.'
 else:
  basis='Owner accepts the Brancusi 1 garden depiction as a VARIATION within the existing Brancusi 1 / Meander Light identity. This is a qualified in situ variation reference, not a verified identical outline, cast or authenticated client installation. The observed additional wave lobes and different fold outline and earlier exclusion assessment remain in history; original primary 51QQ is retained. No new option is created.'
 ownertext=d.get('exact_owner_message') or d['owner_instruction']['text']
 r=copy.deepcopy(approved[-1 if oid in newaccepted and oid!='BSI-B1DCB5B08396' else 0]['reference'])
 if oid in newaccepted:
  c.setdefault('historical_individual_references',[]).append(copy.deepcopy(c['individual']))
  acceptance={'approval':pr,'technical_individual_status_retained':c['individual']['status'],'basis':basis,'references':approved,'separate_full_image_verified':False,'no_repeat_individual_capture_prompt':True,'physical_verification_added':False}
  o['owner_accepted_listing_references']=copy.deepcopy(acceptance); c['owner_accepted_listing_references']=copy.deepcopy(acceptance)
  o['owner_image_review_disposition']='OWNER_ACCEPTED_EXISTING_QUALIFIED_REFERENCE'
  c['individual'].update(basis=basis,owner_review_disposition='ACCEPTED_FOR_LISTING_REFERENCE_WITH_TECHNICAL_SOURCE_ROLE_RETAINED',owner_acceptance=pr,terminal_review_state='OWNER_ACCEPTED_QUALIFIED_LISTING_REFERENCE',owner_capture_criterion='Scoped owner exception: use the whole group or combined design/finish references; no repeat separate-photo prompt for this option.',cropped_image_accepted=False)
 else:
  c.setdefault('historical_in_situ_references',[]).append(copy.deepcopy(c['in_situ']))
  variation=oid=='BSI-923D5E50A898'
  c['in_situ']={'status':'Available','reference':r,'basis':basis,'owner_acceptance':pr,'member_position':approved[0].get('target_member_position','Owner-accepted variation'),'terminal_review_state':'OWNER_ACCEPTED_VARIATION_REFERENCE' if variation else 'OWNER_BOUND_IN_SITU_REFERENCE','reference_is_candidate_only':False,'physical_cast_or_size_certified':False,'scene_authenticity_verified':False,'owner_accepted_variation':variation,'exact_primary_outline_match_verified':False if variation else None}
  contextkeys=['context_status','context_description','context_file_id','context_folder_id','context_image_url','context_folder_url']
  o.setdefault('historical_owner_superseded_contexts',[]).append({k:copy.deepcopy(o.get(k)) for k in contextkeys})
  o.update(context_status='Available',context_description=basis,context_file_id=r['file_id'],context_folder_id=r['folder_id'],context_image_url=r['image_url'],context_folder_url=r['folder_url'])
  o['photo_coverage']['in_situ']='Available';o['owner_accepted_in_situ_reference']={'approval':pr,'references':approved,'basis':basis,'owner_accepted_variation':variation,'physical_verification_added':False}
 c.setdefault('historical_owner_superseded_notes',[]).append({'notes':copy.deepcopy(c['notes']),'approval':pr})
 c['notes']=[basis];c['owner_review']=d['decision_id']
 state={'state':'OWNER_ACCEPTED_QUALIFIED_LISTING_REFERENCE' if oid in newaccepted else c['in_situ']['terminal_review_state'],'finding':basis,'next_action':'Image-role review complete. Retain source qualifications and continue only with remaining independent context/physical checks.','source_reference':r,'approved_reference_roles':approved,'owner_approval':pr,'physical_or_platform_verification_added':False}
 current_review(c.setdefault('terminal_task_review',{}),rolekey,state)
 current_review(o.setdefault('current_photo_task_review',{}).setdefault('roles',{}),rolekey,state)
 if rolekey in c.get('candidate_binding_review',{}): current_review(c['candidate_binding_review'],rolekey,state)
 if rolekey in o.get('current_candidate_binding_review',{}).get('roles',{}): current_review(o['current_candidate_binding_review']['roles'],rolekey,state)
 actions=[x for x in a['missing_pictures'] if x['option_id']==oid and x['role']==role and x['status']=='Open'];assert len(actions)==1,(oid,role)
 x=actions[0];x.setdefault('historical_actions',[]).append(copy.deepcopy(x))
 x.update(status='Resolved',action='Owner accepts qualified listing references; separate-photo request closed for this option.' if oid in newaccepted else 'Owner accepts qualified in situ reference; photograph task closed for this option.',reference=r,qualification=basis,owner_response=ownertext,owner_decision_id=d['decision_id'],resolution_kind='OWNER_ACCEPTED_QUALIFIED_REFERENCE' if oid in newaccepted else 'OWNER_ACCEPTED_IN_SITU_VARIATION' if oid=='BSI-923D5E50A898' else 'OWNER_BOUND_IN_SITU_REFERENCE',technical_separate_photo_available=False if oid in newaccepted else c['individual']['status']=='Available',terminal_review_state=state['state'])
 for x in reviews:
  if x.get('option_id',x.get('product_id'))==oid and x.get('role')==role:
   x.setdefault('historical_owner_superseded_reviews',[]).append({k:copy.deepcopy(x.get(k)) for k in ['review_state','finding','next_action','source_reference']})
   x.update(review_state=state['state'],finding=basis,next_action=state['next_action'],owner_decision_id=d['decision_id'],source_reference=r,approved_reference_roles=approved)
 if oid in details:
  x=details[oid];x.setdefault('historical_media_review_states',[]).append({'remaining_evidence_gaps':copy.deepcopy(x['remaining_evidence_gaps']),'draft_media_condition':copy.deepcopy(x.get('draft_listing',{}).get('media_condition')),'before_sync_utc':now()})
  x['remaining_evidence_gaps']=[v for v in x['remaining_evidence_gaps'] if not v.startswith('Existing image-coverage limitation:')]+[basis]
  if x.get('draft_listing'):
   previous=x['draft_listing'].get('media_condition','')
   x['draft_listing']['media_condition']=(previous+'\nCurrent in situ reference: ' if oid in insitu else '')+basis+' Keep all existing physical and platform restrictions.'
  x['current_media_review_synchronization']={'recorded_utc':now(),'owner_approval':pr,'accepted_qualified_reference_exception':oid in newaccepted,'qualified_in_situ_reference_available':oid in insitu,'platform_and_physical_dispositions_unchanged':True}
 o['current_photo_approval_import']={'approval':pr,'role':role,'basis':basis,'approved_references':approved,'technical_individual_coverage_retained':c['individual']['status']}
 assert not any(z.get('decision_id')==d['decision_id'] for z in g['imported_owner_review_packets'])
 g['imported_owner_review_packets'].append({**pr,'imported_utc':now(),'no_physical_or_platform_verification_added':True})
 a.setdefault('imported_owner_image_decisions',[]).append({**pr,'option_id':oid,'role':role,'basis':basis})
 summaries.append({'option_id':oid,'name':o['name'],'role':role,'approval':pr,'basis':basis,'references':approved,'technical_individual_status':c['individual']['status']})

for x in original:
 assets[x['file_id']]={**assets.get(x['file_id'],{}),**copy.deepcopy(x),'thumb':x['local_original'],'original':x['local_original'],'current_original_content_rehashed':True,'native_reference_status':'VERIFIED_CURRENT_ID_AND_ACTUAL_PARENT'}
opened=[x for x in a['missing_pictures'] if x['status']=='Open'];active=[x for x in a['missing_pictures'] if x['status']!='Resolved'];ind=[x for x in opened if x['role']=='Individual'];cap=[x for x in ind if x['action_type']=='Find / capture']
counts=a['counts'];counts.update(individual_statuses=dict(collections.Counter(x['individual']['status']for x in a['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),resolved_action_rows=sum(x['status']=='Resolved'for x in a['missing_pictures']),required_picture_actions=len(opened),outstanding_individual_image_or_identity_actions=len(ind),separate_individual_photographs_required=len(cap),owner_accepted_group_or_combined_reference_exceptions=len(oldaccepted|newaccepted))
counts['terminal_task_count_scope']='Terminal-task and deep-review counters retain their dated 21 October audit scope; required_picture_actions and outstanding role counts are the current owner-approved queue.'
assert counts['individual_statuses']==oldaudit['counts']['individual_statuses']
assert len(opened)==80 and len(ind)==2 and len(cap)==1 and counts['in_situ_statuses']=={'Available':128,'No verified image':60}
assert counts['resolved_action_rows']==74 and counts['actions_by_type']=={'Verify existing image':1,'Find / capture':79,'Optional image':54}
assert {x['option_id']for x in ind}=={'BSI-C41824131174','BSI-04D6E8690F30'}
for x,y in zip(g['options'],old['options']):
 for k in ['product_id','name','canonical_key','canonical_component_id','specifications','master_fields','selling_details','file_id','folder_id','image_url','folder_url','current_listing_reconciliation','current_listing_resolution']:
  assert x.get(k)==y.get(k),(x['product_id'],k)
 if x['product_id'] not in scope['target_option_ids']:assert x==y,x['product_id']
assert g['original_review_specification_assertions']==old['original_review_specification_assertions']
for k in ['summary','components','aliases','source_sets','source_offer_edges','wall_sculpture_customisation_policy','current_frozen_fish_size_policy']:assert g[k]==old[k],k
result={'status':'SEVEN_SCOPED_OWNER_PHOTO_APPROVALS_IMPORTED','recorded_utc':now(),'scope':scope,'imported_approvals':summaries,'complete_individual_images_added':[],'new_owner_accepted_qualified_reference_exceptions':sorted(newaccepted),'owner_accepted_qualified_reference_exceptions':sorted(oldaccepted|newaccepted),'previously_approved_complete_individual_images':old['latest_approved_images_folder_refresh']['complete_individual_images_added'],'in_situ_roles_closed':sorted(insitu),'current_options':188,'working_component_identities':112,'working_field_groups':1128,'current_counts':copy.deepcopy(counts),'new_physical_verifications':0,'new_platform_writes':0,'native_mutations':0}
a.setdefault('historical_individual_capture_queue_counts',[]).append(copy.deepcopy(a['individual_capture_queue_counts']))
a['individual_capture_queue_counts'].update(individual_gaps=2,separate_photographs_required=1,legacy_identity_deferred=1,new_owner_accepted_individual_listing_images=0,technical_individual_gaps=11,scoped_accepted_group_or_combined_exceptions=9)
for policy in [g['current_individual_photo_capture_policy'],a['current_individual_photo_capture_policy']]:
 policy.setdefault('historical_current_requirements',[]).append(copy.deepcopy(policy.get('current_requirements')))
 policy['current_requirements']={'individual_gaps':2,'separate_individual_images_required':1,'deferred_identity':1,'technical_individual_gaps':11,'scoped_accepted_group_or_combined_exceptions':9,'new_complete_individual_images_this_import':0,'no_crops_created':True,'scoped_owner_exception_option_ids':sorted(oldaccepted|newaccepted),'scope':'Original no-crop decision retained; later explicit whole-group and design/finish approvals close only their named capture prompts.'}
g.setdefault('historical_draft_media_synchronizations',[]).append(copy.deepcopy(g['latest_draft_media_synchronization']))
g['latest_draft_media_synchronization']={'recorded_utc':now(),'option_ids':scope['target_option_ids'],'draft_detail_entries_updated':sum(x in details for x in scope['target_option_ids']),'complete_individual_images_added':0,'new_scoped_listing_reference_exceptions':4,'qualified_in_situ_bindings_added':3,'new_physical_verifications':0,'platform_writes':0,'scope':'Current media conditions synchronized with these seven scoped owner approvals; original individual primaries and physical/platform restrictions retained.'}
a['latest_queued_photo_approval_import']=copy.deepcopy(result);a['recorded_utc']=now();a['status']='CURRENT_SEVEN_QUEUED_PHOTO_APPROVALS_IMPORTED_2026_10_23';g['latest_queued_photo_approval_import']=copy.deepcopy(result)
g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']))
write(H/'image-coverage-current.json',a)
g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),audit_sha256=sha(H/'image-coverage-current.json'),counts=copy.deepcopy(counts),scope='188 current options. Seven scoped approvals imported: four group/design-finish listing-reference exceptions and three qualified in situ bindings. Eleven technical individual gaps remain distinct from two open individual/identity actions.',status=a['status'],verification=str((H/'saved-file-verification.json').relative_to(B)),visual_verification=str((H/'visual-verification.json').relative_to(B)))
for k in ['verification_sha256','visual_verification_sha256','independent_verification','independent_verification_sha256','native_binding_verification','native_binding_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g);write(H/'current-assets.json',assets);write(H/'photo-review-queue.json',reviews);write(H/'preparation-verification.json',result)
state=read(H/'inputs/guided_state.before');state.setdefault('historical_states',[]).append(copy.deepcopy({k:v for k,v in state.items()if k!='historical_states'}))
state.update(status='SEVEN_APPROVALS_IMPORTED_ACANTHUS_PHYSICAL_REVIEW_PENDING',current_phase='individual',current_position=0,current_option_id='BSI-C41824131174',queues={'individual':[x['option_id']for x in cap],'in_situ':[x['option_id']for x in opened if x['role']=='In situ'],'series':[x['option_id']for x in opened if x['role']=='Series']},deferred_identity_option_ids=['BSI-04D6E8690F30'],no_repeat_individual_prompt_option_ids=sorted(oldaccepted|newaccepted),working_specification_question='Actual Acanthus Sandstone dimensions/depth, weighed mass, recipe and fitted hardware already requested; no new answer inferred.')
write(H/'guided-owner-review-state.json',state)
pending=read(H/'inputs/pending_followups.before');importpaths=set(scope['approvals'].values());superseded=[];remaining=[]
for x in pending['entries']:
 if x['path'] in importpaths:continue
 if x['kind']=='owner-review-outcome' and x.get('product_id')=='BSI-725A77437026':superseded.append({**x,'status':'SUPERSEDED_BY_LATER_EXPLICIT_DESIGN_AND_FINISH_REFERENCE_APPROVAL','superseding_approval':pref('BSI-725A77437026')})
 else:remaining.append(x)
later=[B/'components/parallel-reviews/decowaves-terracotta-pair-in-situ-approval-2026-10-23/owner-image-approval.json',B.parent/'reports/dropbox-leaf-form-individual-split-2026-10-23/current-reference-overlay.json',B/'components/parallel-reviews/dune-ripple-two-copper-finishes-in-situ-approval-2026-10-23/owner-image-approval.json']
for path in later:
 if path.exists() and str(path)not in {x['path']for x in remaining}:
  d=read(path);remaining.append({'kind':'native-overlay'if 'overlay'in path.name else'owner-image-approval','path':str(path),'sha256':sha(path),'status':d.get('status'),'decision_id':d.get('decision_id'),'applied_to_current_frozen_release':False,'queue_only_no_coverage_change':True})
pending.update(recorded_utc=now(),frozen_current_scope=str(H/'scope.json'),entries=remaining,imported_in_this_release=[pref(x)for x in scope['target_option_ids']],superseded_review_outcomes=superseded)
write(H/'pending-followups.json',pending)
write(H/'visual-source-inspection.json',{'status':'PASS','all_seven_originals_viewed':True,'qualifications':['MP4 outer panels only; centre MP2 separate','White Lava files show corresponding numbered design only','Sandstone group left1 centre2 right3; whole original retained','Cup Ring right and Spiral left in same garden pair','Brancusi1 garden is accepted variation; prior relief differences preserved'],'pixels_edited':False,'source_files':[{'file_id':x['file_id'],'sha256':x['sha256']}for x in original]})
print(json.dumps({'status':result['status'],'approvals':len(summaries),'technical_individual_gaps':counts['technical_individual_reference_gaps'],'individual_actions':len(ind),'in_situ_gaps':60,'series_gaps':18,'required_actions':80,'queued_later_packets':len(remaining)}))
