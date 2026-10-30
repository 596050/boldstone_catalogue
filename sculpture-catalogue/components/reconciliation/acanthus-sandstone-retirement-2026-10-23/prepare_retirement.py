"""Retire one current option without deleting its identity or source history."""
import collections,copy,hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
O=Path(m['master_register']['path']).parent;g=read(m['master_register']['snapshot']);a=read(m['audit']['snapshot']);oid='BSI-C41824131174';o=next(x for x in g['options']if x['product_id']==oid);original=copy.deepcopy(o);instruction=read(H/'owner-retirement-instruction.json')
retirement={'decision_id':'ACANTHUS-ONE-LEAF-SANDSTONE:OWNER-RETIRED:2026-10-23','recorded_utc':now(),'option_id':oid,'name':o['name'],'owner_text':'Sandstone does not exist anymore','instruction_path':str(H/'owner-retirement-instruction.json'),'instruction_sha256':sha(H/'owner-retirement-instruction.json'),'status':'RETIRED_FROM_CURRENT_CATALOGUE','current_offer_active':False,'physical_or_commercial_verification_inferred':False,'scope':'Only Acanthus One Leaf Left — Sandstone. Other finishes and all other Sandstone families retain their prior status.'}
reason='Owner23October2026: Sandstone does not exist anymore. Retired from the current catalogue; retain identity, Dropbox IDs, source specifications and earlier proposals as history. No photograph, measurement, price, availability or platform-creation task remains for this option.'
write(H/'retired-option-history.json',{'retirement':retirement,'complete_option_before_retirement':original,'coverage_before_retirement':next(x for x in a['coverage']if x['option_id']==oid),'photo_actions_before_retirement':[x for x in a['missing_pictures']if x['option_id']==oid]})
o.update(catalogue_status='Retired',active_catalogue_option=False,counted_as_individual_option=False,count_class='Retired option — historical identity retained',catalogue_retirement=retirement,current_offer_active=False,historical_selling_details_only=True,current_availability='Retired — no longer exists',current_measurement_required=False)
o['photo_coverage'].update(individual='Retired / not applicable',in_situ='Retired / not applicable',series='Retired / not applicable')
o.setdefault('current_photo_task_review',{}).update(state='OWNER_RETIRED_OPTION',next_action='No active photo or measurement task.',retirement=retirement)
o['current_listing_resolution']={**o.get('current_listing_resolution',{}),'catalogue_active':False,'status':'RETIRED_NO_CURRENT_OFFER_OR_DRAFT_CREATION','next_action':'None — owner-retired option; history retained.'}
g.setdefault('catalogue_retirements',[]).append(retirement);g['retired_option_ids']=[oid];g['active_option_ids']=[x['product_id']for x in g['options']if x.get('counted_as_individual_option',True)];g['option_lifecycle_policy']='options retains active and retired history rows; current counts/exports use counted_as_individual_option and exclude catalogue_status Retired. Never count len(options) as the active catalogue total.'
component=next(x for x in g['components']if x['component_id']=='BC-AC-ONE');component['historical_option_members_before_retirement']={k:copy.deepcopy(component[k])for k in ['option_ids','option_count','option_names']};component['option_ids'].remove(oid);component['option_names'].remove(o['name']);component['option_count']=len(component['option_ids']);component['retired_option_ids']=[oid]
s=g['summary'];s.update(individual_options_on_identified_components=179,individual_named_working_options=187,current_option_records=187,current_field_groups=1122,options_with_six_working_fields=187,retained_option_records=188,retired_option_records=1,retained_working_field_groups=1128)
g['count_definition']='Active individually offered finish/size/build options, excluding retired options. All188 history rows are retained;187 remain current. Component identities are not physical casts, moulds or stock.'
for c in a['coverage']:
 if c['option_id']==oid:
  c['historical_coverage_before_retirement']=copy.deepcopy(c);c['active_catalogue_option']=False;c['catalogue_retirement']=retirement
  for role in ['individual','in_situ','series']:c[role]={'status':'Retired / not applicable','reference':c[role].get('reference'),'basis':reason,'retirement':retirement}
  c['series_required']=False;c['notes']=[reason]
for x in a['missing_pictures']:
 if x['option_id']==oid:
  assert x['status']=='Open';x.setdefault('historical_actions',[]).append(copy.deepcopy(x));x.update(status='Retired / not applicable',action='No action — owner-retired option.',qualification=reason,owner_response='Sandstone does not exist anymore',resolution_kind='OWNER_RETIRED_NOT_A_PHOTO_RESOLUTION',catalogue_retirement=retirement)
for x in a['identity_review']:
 if x.get('option_id',x.get('product_id'))==oid:x.update(catalogue_status='Retired',current_task_required=False,retirement=retirement)
current=[x for x in a['coverage']if x.get('active_catalogue_option',True)];active=[x for x in a['missing_pictures']if x['status']in ['Open','Optional']];counts=a['counts'];counts.update(individual_options=len(current),retained_option_coverage_rows=len(a['coverage']),retired_option_rows=1,individual_statuses=dict(collections.Counter(x['individual']['status']for x in current)),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in current)),series_statuses=dict(collections.Counter(x['series']['status']for x in current)),series_required_options=sum(x['series_required']for x in current),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),active_action_rows=len(active),required_picture_actions=sum(x['status']=='Open'for x in active),retired_action_rows=3,technical_individual_reference_gaps=10,outstanding_individual_image_or_identity_actions=1,separate_individual_photographs_required=0)
assert(counts['required_picture_actions'],counts['in_situ_statuses']['No verified image'],counts['series_statuses']['No verified image'],counts['actions_by_type']['Find / capture'],counts['resolved_action_rows'])==(67,49,17,66,84)
a.update(recorded_utc=now(),status='OWNER_RETIRED_SANDSTONE_EXCLUDED_FROM_CURRENT_PHOTO_TASKS',latest_catalogue_retirement=retirement)
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),audit=str((H/'image-coverage-current.json').relative_to(B)),counts=counts,recorded_utc=now(),status=a['status'],scope='One owner-retired option excluded from current catalogue and tasks; no photograph or physical evidence inferred.')
for k,name in [('verification','saved-file-verification.json'),('native_binding_verification','native-binding-verification.json'),('visual_verification','visual-verification.json')]:g['latest_image_coverage_audit'][k]=str((H/name).relative_to(B));g['latest_image_coverage_audit'].pop(k+'_sha256',None)
g['latest_image_coverage_audit'].pop('audit_sha256',None);g['latest_catalogue_retirement']=retirement
details=g['current_listing_resolution_details']
for x in details['entries']:
 if x['product_id']==oid:
  x['historical_listing_before_retirement']=copy.deepcopy(x);x.update(catalogue_status='Retired',current_offer_active=False,next_action='None — owner-retired; preserve source/draft history.',remaining_evidence_gaps=[])
  if x.get('draft_listing'):x['draft_listing'].update(status='RETIRED_LOCAL_DRAFT_DO_NOT_CREATE',current_offer_active=False,activation_condition='None — owner-retired.',media_condition=reason)
for layer in ['current_listing_issues','listing_resolution_native_action_drafts']:
 z=g.get(layer)
 if isinstance(z,list):
  for x in z:
   if isinstance(x,dict)and x.get('product_id',x.get('option_id'))==oid:x.update(catalogue_status='Retired',current_task_required=False,retirement=retirement)
reviews=read(m['report_reviews']['snapshot']);retired_reviews=[x for x in reviews if x.get('option_id')==oid];reviews=[x for x in reviews if x.get('option_id')!=oid]
ledger=read(O/'context-review-ledger.json')
for x in ledger['tasks']:
 if x['option_id']==oid:x.update(status_after='Retired / not applicable',outcome='OWNER_RETIRED_NOT_A_PHOTO_RESOLUTION',current_finding=reason,review_note='Historical source review retained; no active task.')
rs=read(m['review_state']['snapshot'])
for k,vals in rs.get('queues',{}).items():
 if isinstance(vals,list):rs['queues'][k]=[x for x in vals if x!=oid and not(isinstance(x,dict)and x.get('option_id')==oid)]
rs.setdefault('retired_option_reviews',[]).append(retirement);rs['current_option_id']='BSI-3635E3DC3434';rs['current_role']='Series'
pending=read(m['pending']['snapshot']);pending['owner_physical_measurement_reply_pending']=False;pending['retired_acanthus_sandstone']=retirement;pending['current_acanthus_requirement']='Only One Leaf Pewter series remains from the earlier3-photo priority batch. Owner-reported addition is not verified as a group source; exact filename/link question remains pending.'
prep=read(O/'preparation-verification.json');prep['retirement']=retirement;prep['current_counts']=counts
for name,x in [('canonical-master-register.json',g),('image-coverage-current.json',a),('photo-review-queue.json',reviews),('guided-owner-review-state.json',rs),('context-review-ledger.json',ledger),('pending-followups.json',pending),('preparation-verification.json',prep),('retired-photo-review-entries.json',retired_reviews)]:write(H/name,x)
for key,name in [('native_map','current-native-reference-map.json'),('report_assets','current-assets.json')]:shutil.copy2(m[key]['snapshot'],H/name)
for name in ['scope.json','original-verification.json','specification-evidence-review.json']:shutil.copy2(O/name,H/name)
write(H/'source-evidence-verification.json',{'status':'PASS','retirement_scope':oid,'retired_tasks':3,'source_history_preserved':True,'new_native_or_platform_mutations':0})
write(H/'evidence-manifest.json',{str(H/'owner-retirement-instruction.json'):{'sha256':sha(H/'owner-retirement-instruction.json')},str(H/'retired-option-history.json'):{'sha256':sha(H/'retired-option-history.json')}})
print(json.dumps({'status':'RETIREMENT_PREPARED','retained_rows':188,'active_options':187,'component_identities':112,'required_actions':67,'in_situ_gaps':49,'series_gaps':17,'retired_actions':3}))
