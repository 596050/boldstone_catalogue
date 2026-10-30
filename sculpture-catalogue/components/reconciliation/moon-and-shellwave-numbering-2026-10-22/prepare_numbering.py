"""Apply owner numbered identities and a verified in-place Dropbox path overlay."""
import collections, copy, hashlib, importlib.util, json, math, posixpath, re, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from xml.etree import ElementTree as E

H=Path(__file__).resolve().parent; BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
packet=BASE/'components/parallel-reviews/six-image-checks-2026-10-22-b/decisions/acanthus-pewter/OWNER_DECISION.json'
assert sha(packet)=='f2d84c648ed5abc07a154e5e19794a56285fe88e459e73f1876ba61fd16dff68'
if 'pewter_decision' not in m:
 shutil.copy2(packet,H/'inputs/pewter_decision.before')
 m['pewter_decision']={'path':str(packet),'snapshot':str(H/'inputs/pewter_decision.before'),'sha256':sha(packet)}
 write(H/'input-manifest.json',m)
for key,filename in [('native_overlay','dropbox-current-reference-overlay.json'),('native_verification','dropbox-verification.json'),('root_native_readback','root-independent-dropbox-readback.json')]:
 p=H/filename
 if key not in m:
  shutil.copy2(p,H/'inputs'/(key+'.before'));m[key]={'path':str(p),'snapshot':str(H/'inputs'/(key+'.before')),'sha256':sha(p)}
write(H/'input-manifest.json',m)
for x in m.values(): assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
assert read(m['native_overlay']['path'])['verification']['status']=='PASS'
pewter=read(packet)
for x in pewter['input_verifications']:assert sha(x['path'])==x['sha256'],x['path']
assert pewter['exact_owner_answer']=='Yes it is a Pewter sculpture' and pewter['case_sequence']==154 and not pewter['specification_changes'] and pewter['new_products']==0
spacket=BASE/'components/parallel-reviews/six-image-checks-2026-10-22-b/decisions/acanthus-sandstone/OWNER_DECISION.json'
assert sha(spacket)=='03cd4a2bd12b6982175bd4347ec777732fe80befabf3189e32060ec497c3d4e2'
if 'sandstone_decision' not in m:
 shutil.copy2(spacket,H/'inputs/sandstone_decision.before');m['sandstone_decision']={'path':str(spacket),'snapshot':str(H/'inputs/sandstone_decision.before'),'sha256':sha(spacket)};write(H/'input-manifest.json',m)
sandstone=read(spacket)
for x in sandstone['input_verifications']:assert sha(x['path'])==x['sha256'],x['path']
assert sandstone['case_sequence']==155 and sandstone['exact_owner_answer'].startswith('Yes - ') and not sandstone['specification_changes'] and sandstone['new_products']==0
rp=read(H/'rename-plan.json'); oldroot=rp['family']['old_path']; newroot=rp['family']['new_path']
maps=[(x['old_path'],x['current_final_path']) for x in rp['child_folder_renames']]+[(oldroot,newroot)]
maps.sort(key=lambda x:len(x[0]),reverse=True)
def path_rewrite(p):
 for old,new in maps:
  if p.casefold()==old.casefold() or p.casefold().startswith(old.casefold()+'/'):return new+p[len(old):]
 return p
def url_rewrite(u):
 if not isinstance(u,str) or not u.startswith('https://www.dropbox.com/'):return u
 p=urlsplit(u); decoded=unquote(p.path)
 for route in ['/home','/preview']:
  if decoded.startswith(route+'/'):
   old=decoded[len(route):]; new=path_rewrite(old)
   if old!=new:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return u
def ref_string(s):
 if not isinstance(s,str):return s
 if s.startswith('https://www.dropbox.com/'):return url_rewrite(s)
 if s.startswith('ns:202238505//'):return 'ns:202238505/'+path_rewrite('/'+s.split('//',1)[1].lstrip('/'))
 if s.startswith('/BOLDSTONE MASTER/'):return path_rewrite(s)
 return s
def rebase(z):
 if isinstance(z,dict):return {k:rebase(v) for k,v in z.items()}
 if isinstance(z,list):return [rebase(v) for v in z]
 return ref_string(z)
components={'BC-MSW-SPIRAL':'Moon and Shellwave 1','BC-MSW-MOON':'Moon and Shellwave 2'}
names={'BSI-6E9202BEAD51':'Moon and Shellwave 2 — Black and White','BSI-6FE9343F889E':'Moon and Shellwave 2 — White','BSI-B9E2B67965E2':'Moon and Shellwave 1 — White','BSI-D886F539DD3E':'Moon and Shellwave 1 — White Water Feature'}
g=read(H/'inputs/master_register.before'); oldg=copy.deepcopy(g)
a=read(H/'inputs/audit.before'); olda=copy.deepcopy(a)
name_map={x['name']:names[x['product_id']] for x in g['options'] if x['product_id'] in names}
name_map.update({'Half Moon':'Moon and Shellwave 2','Shellwave':'Moon and Shellwave 1'})
wf='BSI-D886F539DD3E'; moon='BSI-6FE9343F889E'; did='MOON-AND-SHELLWAVE-NUMBERED-COMPONENTS-2026-10-22'
decision={'decision_id':did,'recorded_utc':now(),'user_statement':rp['source_user_instruction'],'family':'Moon and Shellwave','component_mapping':copy.deepcopy(rp['component_mapping']),'option_names':names,'interpretation':'Spiral is member 1; curved moon is member 2. The upper outlet-bearing spiral in the current scene is member 1; the lower curved moon is member 2. Existing finish/build options remain distinct.','historical_code_warning':'Historical MSW2 identifies the spiral (new display number 1); MSW1/MSW3 identify the curved moon (new display number 2). Source codes and native platform IDs/SKUs are not renumbered.','specification_changes':0,'new_options':0,'new_components':0,'source_question_case':139,'native_rename_plan':rel(H/'rename-plan.json'),'native_rename_plan_sha256':sha(H/'rename-plan.json'),'same_physical_cast_or_measured_size_confirmed':False}
write(H/'owner-decision.json',decision)
# Project current references only. Original assertions, source titles and historical snapshots stay intact.
def project(node):
 for k in ['image_url','folder_url','context_image_url','context_folder_url','path']:
  if k in node:node[k]=ref_string(node[k])
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
 for x in g[layer]:project(x)
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:project(x.get('current_primary_reference',{}))
for x in g['arrangement_context_references']:
 project(x)
 for y in x.get('images',[]):project(y)
for x in g['components']:
 if x['component_id'] not in components:continue
 x['name']=components[x['component_id']];x['family']='Moon and Shellwave'
 x['option_names']=[names[i] for i in x['option_ids']]
 x['retained_names']=list(dict.fromkeys(x['retained_names']+[x['name']]+x['option_names']))
 x['current_numbered_identity']={'decision_id':did,'display_member_number':1 if x['component_id']=='BC-MSW-SPIRAL' else 2,'historical_source_codes_retained':True,'family_folder_id':rp['family']['folder_id']}
for x in g['options']:
 if x['product_id'] not in names:continue
 x['name']=names[x['product_id']];x['family']='Moon and Shellwave'
 x['retained_names']=list(dict.fromkeys(x['retained_names']+[x['name']]))
 for key in ['current_listing_reconciliation','current_listing_resolution']:
  if key in x:x[key]['name']=x['name'];x[key]['family']='Moon and Shellwave'
 x['current_numbered_identity']={'decision_id':did,'component_name':components[x['canonical_component_id']],'display_member_number':1 if x['canonical_component_id']=='BC-MSW-SPIRAL' else 2,'source_codes_retained':True}
 # Active review references use the new paths; prior_* and *_before_* snapshots retain old paths.
 for key in ['current_candidate_binding_review','current_photo_task_review']:
  if key in x:x[key]=rebase(x[key])
def current_labels(z):
 if isinstance(z,dict):
  for k,v in z.items():
   if k in ['name','display_name','title'] and isinstance(v,str) and v in name_map:z[k]=name_map[v]
   elif k=='family' and v=='Moon & Shellwave':z[k]='Moon and Shellwave'
   elif k not in ['evidence_ref','master_ref','frozen_master','source_ref']:current_labels(v)
 elif isinstance(z,list):
  for v in z:current_labels(v)
for key in ['source_media_configuration_coverage','source_platform_offer_coverage','current_listing_issues','current_listing_resolution','current_listing_resolution_details']:
 current_labels(g[key])
# Current coverage and task references get the path overlay without modifying their historical subrecords.
for x in a['coverage']:
 if x['option_id'] in names:x['name']=names[x['option_id']];x['family']='Moon and Shellwave'
 for role in ['individual','in_situ','series']:
  if x[role].get('reference'):x[role]['reference']=rebase(x[role]['reference'])
 for key in ['candidate_binding_review','owner_guided_review']:
  if key in x:x[key]=rebase(x[key])
for x in a['missing_pictures']:
 if x['option_id'] in names:x['name']=names[x['option_id']]
 if x.get('reference'):x['reference']=rebase(x['reference'])
for x in a['identity_review']:
 if x.get('name') in name_map:x['name']=name_map[x['name']]
 for key in ['reference','comparison']:
  if x.get(key):x[key]=rebase(x[key])
c=next(x for x in a['coverage'] if x['option_id']==wf)
finding='Owner names the upper outlet-bearing spiral Moon and Shellwave 1 and the lower curved moon Moon and Shellwave 2. This scene is a series/arrangement reference for the existing member-1 White Water Feature option. Individual dimensions, mass, price and hardware retain their existing qualifications; the whole assembly is not one component.'
c['before_owner_numbering']=copy.deepcopy(next(x for x in olda['coverage'] if x['option_id']==wf))
c['series'].update(status='Available',basis=finding,reference_is_candidate_only=False,member_position='UPPER outlet-bearing spiral: Moon and Shellwave 1; LOWER curved moon: Moon and Shellwave 2',deep_review_state='OWNER_NUMBERED_COMPONENT_ASSIGNMENT_CONFIRMED',owner_decision_id=did,physical_cast_or_size_certified=False)
c['individual']['basis']='The upper spiral is Moon and Shellwave 1 — White Water Feature. The available scene includes lower Moon and Shellwave 2; an isolated complete view of the upper adapted spiral is still required.'
c['notes']=[finding,'Member 1 still needs its own complete isolated photograph. Member 2 reuses the existing White option; no new option or lower-panel water adaptation is inferred.']
c['owner_numbering_decision']={'decision_id':did,'source':rel(H/'owner-decision.json'),'upper_component_id':'BC-MSW-SPIRAL','lower_component_id':'BC-MSW-MOON','new_options':0,'specification_changes':0}
o=next(x for x in g['options'] if x['product_id']==wf)
o['photo_coverage']['series']='Available';o['current_owner_photo_decision']={'decision_id':did,'role':'Series','status':'Available','member_position':'UPPER outlet-bearing spiral','lower_companion_component_id':'BC-MSW-MOON','finding':finding,'same_physical_cast_confirmed':False}
o['current_numbered_identity']['scene_position']='UPPER outlet-bearing spiral'
if 'current_candidate_binding_review' in o:
 o['candidate_review_before_owner_numbering']=copy.deepcopy(o['current_candidate_binding_review'])
 o['current_candidate_binding_review']['roles']['series'].update(state='OWNER_NUMBERED_COMPONENT_ASSIGNMENT_CONFIRMED',finding=finding,next_action='Series association resolved. Obtain the isolated full upper spiral photograph separately.',position='UPPER spiral1; LOWER curved moon2',owner_decision_id=did)
if 'candidate_binding_review' in c:
 c['candidate_review_before_owner_numbering']=copy.deepcopy(c['candidate_binding_review'])
 c['candidate_binding_review']['series'].update(state='OWNER_NUMBERED_COMPONENT_ASSIGNMENT_CONFIRMED',finding=finding,next_action='Series association resolved. Individual photograph remains required.',position='UPPER spiral1; LOWER curved moon2',owner_decision_id=did)
for x in a['missing_pictures']:
 if x['option_id']==wf and x['role']=='Series':
  x['before_owner_numbering']=copy.deepcopy(next(y for y in olda['missing_pictures'] if y['option_id']==wf and y['role']=='Series'))
  x.update(status='Resolved',action='Series scene mapped: upper Moon and Shellwave 1, lower Moon and Shellwave 2. The individual-image request remains open.',scope='Owner numbered component assignment; existing two components and four options retained. No measured specifications or extra water-feature option inferred.',qualification=finding,owner_response=rp['source_user_instruction'],owner_decision_id=did)
 if x['option_id']==wf and x['role']=='Individual':
  x.update(action='Find or photograph Moon and Shellwave 1 — White Water Feature alone, including the complete upper spiral and outlet.',qualification=c['individual']['basis'])
 if x['option_id']=='BSI-6E9202BEAD51' and x['role']=='Series':x['action']='Photograph Moon and Shellwave 2 — Black and White with its identified series companions, keeping its complete outline visible and recording the component position.'
lower=next(x for x in a['identity_review'] if x['case_id']=='SHELLWAVE-WATER-LOWER')
lower['before_owner_numbering']=copy.deepcopy(next(x for x in olda['identity_review'] if x['case_id']==lower['case_id']))
lower.update(name=names[moon],proposed_identity='Moon and Shellwave 2 — curved moon; existing White component option',state='Owner-confirmed existing component',check='Lower curved moon mapped to existing member 2. Retain individual specifications separately from the upper adapted spiral and the complete arrangement.',related_option_ids=[moon,wf],owner_decision=rp['source_user_instruction'],owner_decision_id=did,canonical_component_id='BC-MSW-MOON')
# Import the concurrent, sealed owner answer from the authorised image-review lane.
pp=pewter['option_id'];pd=pewter['decision_id'];pr=copy.deepcopy(pewter['group_reference'])
pcov=next(x for x in a['coverage'] if x['option_id']==pp)
assert pcov['individual']['status']=='Detail only' and pcov['series']['status']=='Verify existing image'
assert pcov['individual']['reference']['file_id']==pewter['detail_reference']['file_id']
pcov['before_owner_pewter_confirmation']=copy.deepcopy(pcov['series'])
pcov['series'].update(status='Available',basis=pewter['interpretation'],reference=pr,reference_is_candidate_only=False,member_position=pewter['confirmed_position'],deep_review_state='OWNER_FINISH_POSITION_CONFIRMED',owner_decision_id=pd,physical_cast_or_size_certified=False)
pcov['notes_before_owner_pewter_confirmation']=copy.deepcopy(pcov['notes'])
pcov['notes']=['Owner confirms Pewter at BACK RIGHT in the group. Primary remains detail only; a complete isolated individual photograph is still required.']
po=next(x for x in g['options'] if x['product_id']==pp)
po['photo_coverage']['series']='Available'
po['current_owner_photo_decision']={'decision_id':pd,'role':'Series','status':'Available','member_position':pewter['confirmed_position'],'finding':pewter['interpretation'],'source_packet':rel(packet),'source_packet_sha256':sha(packet),'same_physical_cast_confirmed':False}
if 'current_candidate_binding_review' in po:
 po['candidate_review_before_owner_pewter_confirmation']=copy.deepcopy(po['current_candidate_binding_review'])
 po['current_candidate_binding_review']['roles']['series'].update(state='OWNER_FINISH_POSITION_CONFIRMED',finding=pewter['interpretation'],next_action='Series association resolved. Complete isolated individual photograph remains required.',position=pewter['confirmed_position'],owner_decision_id=pd)
if 'candidate_binding_review' in pcov:
 pcov['candidate_review_before_owner_pewter_confirmation']=copy.deepcopy(pcov['candidate_binding_review'])
 pcov['candidate_binding_review']['series'].update(state='OWNER_FINISH_POSITION_CONFIRMED',finding=pewter['interpretation'],next_action='Series association resolved. Individual photograph remains required.',position=pewter['confirmed_position'],owner_decision_id=pd)
pa=next(x for x in a['missing_pictures'] if x['option_id']==pp and x['role']=='Series')
pa['before_owner_pewter_confirmation']=copy.deepcopy(pa)
pa.update(status='Resolved',action='Existing Pewter option mapped to the upright panel at BACK RIGHT of the workshop group. Its complete isolated individual photograph remains required.',qualification=pewter['interpretation'],scope='Owner-confirmed existing finish/position association; no new component, measured specification or platform match.',owner_response=pewter['exact_owner_answer'],owner_decision_id=pd,reference=pr)
ss=sandstone['option_id'];sd=sandstone['decision_id'];sr=copy.deepcopy(sandstone['group_reference'])
scov=next(x for x in a['coverage'] if x['option_id']==ss)
assert scov['individual']['status']=='Detail only' and scov['series']['status']=='Verify existing image' and scov['individual']['reference']['file_id']==sandstone['detail_reference']['file_id']
scov['before_owner_sandstone_confirmation']=copy.deepcopy(scov['series']);scov['notes_before_owner_sandstone_confirmation']=copy.deepcopy(scov['notes'])
scov['series'].update(status='Available',basis=sandstone['interpretation'],reference=sr,reference_is_candidate_only=False,member_position=sandstone['confirmed_position'],deep_review_state='OWNER_FINISH_POSITION_CONFIRMED',owner_decision_id=sd,physical_cast_or_size_certified=False)
scov['notes']=['Owner confirms Sandstone at BACK CENTRE in the group. Primary remains detail only; a complete isolated individual photograph is still required.']
so=next(x for x in g['options'] if x['product_id']==ss);so['photo_coverage']['series']='Available';so['current_owner_photo_decision']={'decision_id':sd,'role':'Series','status':'Available','member_position':sandstone['confirmed_position'],'finding':sandstone['interpretation'],'source_packet':rel(spacket),'source_packet_sha256':sha(spacket),'same_physical_cast_confirmed':False}
if 'current_candidate_binding_review' in so:
 so['candidate_review_before_owner_sandstone_confirmation']=copy.deepcopy(so['current_candidate_binding_review']);so['current_candidate_binding_review']['roles']['series'].update(state='OWNER_FINISH_POSITION_CONFIRMED',finding=sandstone['interpretation'],next_action='Series association resolved. Complete isolated individual photograph remains required.',position=sandstone['confirmed_position'],owner_decision_id=sd)
if 'candidate_binding_review' in scov:
 scov['candidate_review_before_owner_sandstone_confirmation']=copy.deepcopy(scov['candidate_binding_review']);scov['candidate_binding_review']['series'].update(state='OWNER_FINISH_POSITION_CONFIRMED',finding=sandstone['interpretation'],next_action='Series association resolved. Individual photograph remains required.',position=sandstone['confirmed_position'],owner_decision_id=sd)
sa=next(x for x in a['missing_pictures'] if x['option_id']==ss and x['role']=='Series');sa['before_owner_sandstone_confirmation']=copy.deepcopy(sa)
sa.update(status='Resolved',action='Existing Sandstone option mapped to the upright panel at BACK CENTRE of the workshop group. Its complete isolated individual photograph remains required.',qualification=sandstone['interpretation'],scope='Owner-confirmed existing finish/position association; no new component, measured specification or platform match.',owner_response=sandstone['exact_owner_answer'],owner_decision_id=sd,reference=sr)
active=[x for x in a['missing_pictures'] if x['status']!='Resolved'];required=[x for x in active if x['status']!='Optional'];counts=a['counts']
counts.update(series_statuses=dict(collections.Counter(x['series']['status'] for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role'] for x in active)),actions_by_type=dict(collections.Counter(x['action_type'] for x in active)),required_picture_actions=len(required),resolved_action_rows=sum(x['status']=='Resolved' for x in a['missing_pictures']),active_action_rows=len(active),terminal_tasks_resolved=46,terminal_tasks_binding_required=1,deep_candidate_checks_remaining=1,group_and_collection_positions_identity_unresolved=82,group_positions_linked_to_existing_components=8)
assert len(required)==111 and counts['actions_by_type']=={'Find / capture':110,'Verify existing image':1,'Optional image':53}
a.update(recorded_utc=now(),status='CURRENT_MOON_AND_SHELLWAVE_OWNER_NUMBERING',historical_audit={'path':m['audit']['path'],'sha256':m['audit']['sha256'],'prior_counts':olda['counts']},owner_numbered_component_review={'decision_id':did,'new_series_roles_resolved':1,'new_individual_photos':0,'specification_changes':0,'new_options':0,'dropbox_folder_renames':10},imported_owner_image_decisions=[{'path':rel(p),'sha256':sha(p),'decision_id':d['decision_id'],'series_roles_resolved':1} for p,d in [(packet,pewter),(spacket,sandstone)]])
write(H/'image-coverage-current.json',a)
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']))
g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'recorded_utc':now(),'status':a['status'],'audit':rel(H/'image-coverage-current.json'),'path':str(H/'image-coverage-current.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'counts':counts,'scope':'Owner numbered Moon and Shellwave components; source codes and all working/source specifications retained.','verification':rel(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json')}
for key in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(key,None)
g.setdefault('historical_terminal_photo_reviews',[]).append(copy.deepcopy(g['latest_terminal_photo_review']))
event={'recorded_utc':now(),'decision_id':did,'option_id':wf,'role':'Series','state':'OWNER_NUMBERED_COMPONENT_ASSIGNMENT_CONFIRMED','finding':finding,'reference':c['series']['reference']}
write(H/'owner-guided-events.json',[event]+[{'recorded_utc':now(),'decision_id':d['decision_id'],'option_id':d['option_id'],'role':'Series','state':'OWNER_FINISH_POSITION_CONFIRMED','finding':d['interpretation'],'reference':d['group_reference'],'packet_sha256':sha(p)} for p,d in [(packet,pewter),(spacket,sandstone)]])
g['latest_terminal_photo_review']={'recorded_utc':now(),'ledger':rel(H/'owner-guided-events.json'),'ledger_sha256':sha(H/'owner-guided-events.json'),'reviewed':3,'resolved_visual_associations':3,'remaining_required_actions':111,'find_capture_or_size_binding':110,'existing_image_bindings':1,'new_individual_photos':0,'native_folder_renames':10,'platform_mutations':0}
g['latest_owner_guided_design_review']={'decision':rel(H/'owner-decision.json'),'decision_sha256':sha(H/'owner-decision.json'),'option_id':wf,'owner_numbered_identity_confirmed':True,'new_options':0,'specification_changes':0}
g['latest_moon_and_shellwave_numbering']={'decision':rel(H/'owner-decision.json'),'decision_sha256':sha(H/'owner-decision.json'),'family':'Moon and Shellwave','family_folder_id':rp['family']['folder_id'],'current_family_path':newroot,'component_mapping':copy.deepcopy(rp['component_mapping']),'option_names':names,'native_rename_plan':rel(H/'rename-plan.json'),'historical_source_codes_preserved':True,'new_options':0,'specification_changes':0}
g['latest_moon_and_shellwave_numbering'].update(native_current_reference_overlay={'path':rel(H/'dropbox-current-reference-overlay.json'),'sha256':sha(H/'dropbox-current-reference-overlay.json')},native_verification={'path':rel(H/'dropbox-verification.json'),'sha256':sha(H/'dropbox-verification.json')},root_independent_native_readback={'path':rel(H/'root-independent-dropbox-readback.json'),'sha256':sha(H/'root-independent-dropbox-readback.json')})
g.setdefault('imported_owner_review_packets',[]).extend([{'path':rel(p),'sha256':sha(p),'decision_id':d['decision_id'],'option_id':d['option_id'],'role':'Series','member_position':d['confirmed_position'],'new_options':0,'specification_changes':0} for p,d in [(packet,pewter),(spacket,sandstone)]])
write(H/'canonical-master-register.json',g)
u=read(H/'inputs/owner_ledger.before');u.setdefault('catalogue_naming_corrections',[]).append(copy.deepcopy(decision));u.setdefault('image_design_identity_decisions',[]).extend([{**copy.deepcopy(decision),'option_id':wf,'native_file_id':c['series']['reference']['file_id'],'native_folder_id':c['series']['reference']['folder_id']},copy.deepcopy(pewter),copy.deepcopy(sandstone)]);u['updated_utc']=now();write(H/'owner-ledger.pending.json',u)
walk=read(H/'inputs/guided_review.before');walk['owner_answers'].append({**copy.deepcopy(walk['current_item']),'owner_answer':decision['user_statement'],'interpretation':decision['interpretation'],'decision_id':did,'recorded_utc':now(),'status':'ANSWER_RECORDED_AND_APPLIED'})
walk['owner_answers'].append({'step':5,'case_sequence':154,'option_id':pp,'name':pewter['approved_name'],'primary_reference':pewter['detail_reference'],'candidate_reference':pr,'question':pewter['exact_question'],'owner_answer':pewter['exact_owner_answer'],'interpretation':pewter['interpretation'],'decision_id':pd,'source_packet':rel(packet),'source_packet_sha256':sha(packet),'recorded_utc':pewter['recorded_utc'],'status':'ANSWER_RECORDED_AND_APPLIED'})
walk['owner_answers'].append({'step':6,'case_sequence':155,'option_id':ss,'name':sandstone['approved_name'],'primary_reference':sandstone['detail_reference'],'candidate_reference':sr,'question':sandstone['exact_question'],'owner_answer':sandstone['exact_owner_answer'],'interpretation':sandstone['interpretation'],'decision_id':sd,'source_packet':rel(spacket),'source_packet_sha256':sha(spacket),'recorded_utc':sandstone['recorded_utc'],'status':'ANSWER_RECORDED_AND_APPLIED'})
legacy=next(x for x in a['coverage'] if x['option_id']=='BSI-04D6E8690F30')
walk['current_item']={'step':7,'case_sequence':'legacy-FFL1','option_id':legacy['option_id'],'name':legacy['name'],'primary_reference':legacy['individual']['reference'],'candidate_reference':next(x for x in a['coverage'] if x['option_id']=='BSI-FE10273D3655')['individual']['reference'],'question':'Does legacy Frozen Fish Long (FFL1) refer to the same design as Frozen Fish Two (FFS2), formerly offered at another size, or a different design? Review owned by image/source lane B; do not duplicate the prompt.','owner_answer':None,'review_thread':'01a13fe6-495b-7253-b923-31823b4cbca8'}
walk.update(status='PENDING_REMAINING_IMAGE_REVIEW_IN_LANE_B',updated_utc=now(),master_changes_applied=6,remaining_case_order=[],latest_owner_numbering_decision=g['latest_moon_and_shellwave_numbering']);write(H/'walkthrough.pending.json',walk)
# Native workbook plan: narrow display labels, current reference paths, one role closure.
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);b=v.load(H/'inputs/master_workbook.before')
links={};changes={}
def setcell(sn,cell,value):
 assert cell not in b['formulas'][sn],(sn,cell)
 if b['values'][sn].get(cell,'')!=value:changes[(sn,cell)]={'sheet':sn,'cell':cell,'before':b['values'][sn].get(cell,''),'value':value}
def row(sn,key,col='A'):
 rr=[int(re.search(r'\d+',k)[0]) for k,val in b['values'][sn].items() if re.fullmatch(col+r'\d+',k) and val==key];assert len(rr)==1,(sn,key,rr);return rr[0]
for sn,s in b['sheets'].items():
 loc=s['part'];rr=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rr])} if rr in b['files'] else {}
 for h in s['root'].findall('.//'+v.q('hyperlink')):
  cell=h.get('ref');target='#'+h.get('location') if h.get('location') else rs[h.get('{'+v.R+'}id')].get('Target');links[(sn,cell)]={'sheet':sn,'cell':cell,'target':url_rewrite(target),'label':ref_string(b['values'][sn].get(cell,''))}
 for cell,value in b['values'][sn].items():
  new=ref_string(value)
  if new!=value:setcell(sn,cell,new)
for sn,col in [('Master Catalogue','B'),('Specifications','B'),('Photo Coverage','B'),('Missing Pictures','C'),('Listing Reconciliation','B'),('Listing Issues','B'),('Listing Resolution','B'),('Draft Listings','B')]:
 for cell,value in b['values'][sn].items():
  if re.fullmatch(col+r'\d+',cell) and value in name_map:setcell(sn,cell,name_map[value])
for pid,name in names.items():setcell('Master Catalogue','C'+str(row('Master Catalogue',pid)),'Moon and Shellwave')
for cid,name in components.items():
 i=row('Components',cid);setcell('Components','B'+str(i),name);setcell('Components','C'+str(i),'Moon and Shellwave');comp=next(x for x in g['components'] if x['component_id']==cid);setcell('Components','K'+str(i),'\n'.join(comp['retained_names']))
for sn,col in [('Sets and Context','D'),('Source Mapping','E'),('Listing Offer Links','P')]:
 for cell,value in b['values'][sn].items():
  if not re.fullmatch(col+r'\d+',cell) or not isinstance(value,str):continue
  new=value
  for old,name in sorted(name_map.items(),key=lambda x:len(x[0]),reverse=True):
   # Only current target labels with IDs; original offer/source titles remain unchanged.
   new=new.replace(old+' [',name+' [')
  if new!=value:setcell(sn,cell,new)
for cov in a['coverage']:
 if cov['option_id'] not in names:continue
 i=row('Photo Coverage',cov['option_id'])
 if cov['option_id']==wf:setcell('Photo Coverage','I'+str(i),'Available');setcell('Photo Coverage','L'+str(i),'\n'.join(cov['notes']))
 else:
  note=b['values']['Photo Coverage'].get('L'+str(i),'')
  if cov['option_id'] in [moon,'BSI-B9E2B67965E2']:
   note=note.replace('Half Moon','Moon and Shellwave 2').replace('Shellwave','Shellwave')
   # Keep legacy prose as context and append the unambiguous current assignment.
   note=b['values']['Photo Coverage'].get('L'+str(i),'')+'\nCurrent names: Moon and Shellwave 2 = curved moon; Moon and Shellwave 1 = spiral.'
   setcell('Photo Coverage','L'+str(i),note)
for x in a['missing_pictures']:
 if x['option_id'] not in names and not(x['option_id'] in [pp,ss] and x['role']=='Series'):continue
 i=next(i for i in range(10,221) if b['values']['Missing Pictures'].get('B'+str(i))==x['option_id'] and b['values']['Missing Pictures'].get('D'+str(i))==x['role'])
 for col,key in [('F','action'),('K','scope'),('L','qualification'),('M','owner_response'),('N','status')]:setcell('Missing Pictures',col+str(i),x.get(key,''))
i=row('Identity Review','SHELLWAVE-WATER-LOWER')
for col,key in [('B','name'),('D','proposed_identity'),('E','state'),('F','check'),('O','owner_decision')]:setcell('Identity Review',col+str(i),lower[key])
setcell('Identity Review','K'+str(i),'\n'.join(lower['related_option_ids']))
j=row('Master Catalogue',wf);prior=b['values']['Master Catalogue'].get('V'+str(j),'');prior=re.sub(r'Photo review: individual[^\n]*','Photo review: individual Group only; in situ Available; series Available. See Photo Coverage for role qualifications.',prior);setcell('Master Catalogue','V'+str(j),prior+'\nUpper spiral is Moon and Shellwave 1; lower curved companion is Moon and Shellwave 2. Individual photograph still needed.')
ppi=row('Photo Coverage',pp);setcell('Photo Coverage','I'+str(ppi),'Available');setcell('Photo Coverage','L'+str(ppi),'\n'.join(pcov['notes']))
ppj=row('Master Catalogue',pp);prior=b['values']['Master Catalogue'].get('V'+str(ppj),'');prior=re.sub(r'Photo review: individual[^\n]*','Photo review: individual Detail only; in situ No verified image; series Available. See Photo Coverage for role qualifications.',prior);setcell('Master Catalogue','V'+str(ppj),prior+'\nOwner confirms Pewter at BACK RIGHT in the workshop group; a full isolated photograph remains required.')
ssi=row('Photo Coverage',ss);setcell('Photo Coverage','I'+str(ssi),'Available');setcell('Photo Coverage','L'+str(ssi),'\n'.join(scov['notes']))
ssj=row('Master Catalogue',ss);prior=b['values']['Master Catalogue'].get('V'+str(ssj),'');prior=re.sub(r'Photo review: individual[^\n]*','Photo review: individual Detail only; in situ No verified image; series Available. See Photo Coverage for role qualifications.',prior);setcell('Master Catalogue','V'+str(ssj),prior+'\nOwner confirms Sandstone at BACK CENTRE in the workshop group; a full isolated photograph remains required.')
setcell('Photo Coverage','A3','22 October: Moon and Shellwave 1 = spiral; 2 = curved moon. Both Acanthus finish positions confirmed. 158 full individual, 119 qualified in situ and 111 series references. Current Frozen Fish: 70 × 15 cm; wall sculptures offer customisation.')
setcell('Missing Pictures','A3','111 required actions remain: 110 find/capture actions and 1 existing-image/identity check. Moon and Shellwave members and both Acanthus finish positions are assigned. Isolated-photo gaps remain recorded.')
for key,x in links.items():
 if key in changes:x['label']=changes[key]['value']
for rn in [row('Photo Coverage',wf),row('Photo Coverage',pp),row('Photo Coverage',ss)]:
 setcell('Photo Coverage','J'+str(rn),'Series image')
 links[('Photo Coverage','J'+str(rn))]['label']='Series image'
heights={}
for (sn,cell),ch in changes.items():
 if cell=='A3' or not isinstance(ch['value'],str):continue
 col=re.match('[A-Z]+',cell)[0];idx=0
 for z in col:idx=idx*26+ord(z)-64
 root=b['sheets'][sn]['root'];width=next((float(x.get('width')) for x in root.findall('.//'+v.q('col')) if int(x.get('min'))<=idx<=int(x.get('max'))),13);rn=int(cell[len(col):]);lines=sum(max(1,math.ceil(len(x)/max(8,width*.9))) for x in ch['value'].split('\n'));ht=lines*13+12;before=float(next(x for x in root.find(v.q('sheetData')) if x.get('r')==str(rn)).get('ht',15))
 if ht>before:assert ht<=409,(sn,cell,ht);heights[(sn,rn)]=max(heights.get((sn,rn),before),ht)
pc=row('Photo Coverage',wf);mp=next(i for i in range(10,221) if b['values']['Missing Pictures'].get('B'+str(i))==wf and b['values']['Missing Pictures'].get('D'+str(i))=='Series')
formula_values=[('Photo Coverage','B4',158),('Photo Coverage','D4',119),('Photo Coverage','F4',111),('Photo Coverage','B5',26),('Photo Coverage','D5',0),('Photo Coverage','F5',0),('Missing Pictures','B4',110),('Missing Pictures','D4',1),('Missing Pictures','F4',53)]
plan={'cell_changes':list(changes.values()),'formula_changes':[],'hyperlinks':list(links.values()),'formula_caches':[{'sheet':sn,'cell':cell,'formula':b['formulas'][sn][cell],'expected':x} for sn,cell,x in formula_values],'row_heights':[{'sheet':sn,'row':rn,'height':ht} for (sn,rn),ht in heights.items()],'style_changes':[],'baseline_ranges':[['Components','B71:K72','baseline-components'],['Photo Coverage','B113:L116','baseline-options']],'preview_ranges':[['Components','A71:K72','01-numbered-components'],['Master Catalogue','A113:D116','02-four-options'],['Photo Coverage','A2:L5','03-photo-summary'],['Photo Coverage','B116:L116','04-water-feature'],['Identity Review','B108:K108','05-lower-moon'],['Missing Pictures',f'C{mp}:N{mp}','06-resolved-series'],['Photo Coverage',f'B{ppi}:L{ppi}','07-pewter-group'],['Photo Coverage',f'B{ssi}:L{ssi}','08-sandstone-group']],'dependency_test':{'coverage_cell':'I'+str(pc),'coverage_total':'F4','coverage_verify':'F5','action_cell':'N'+str(mp),'available_before':111,'available_after':110,'verify_before':0,'verify_after':1,'actions_before':1,'actions_after':2}}
write(H/'workbook-edit-plan.json',plan)
def diff(before,after,path=[]):
 if before==after:return []
 if isinstance(before,dict) and isinstance(after,dict):
  out=[]
  for k in sorted(set(before)|set(after)):
   if k not in before:out.append({'path':path+[k],'kind':'added','after':after[k]})
   elif k not in after:out.append({'path':path+[k],'kind':'removed','before':before[k]})
   else:out.extend(diff(before[k],after[k],path+[k]))
  return out
 if isinstance(before,list) and isinstance(after,list) and len(before)==len(after):
  return [x for i,(b,a) in enumerate(zip(before,after)) for x in diff(b,a,path+[i])]
 return [{'path':path,'kind':'changed','before':before,'after':after}]
write(H/'register-change-log.json',diff(oldg,g));write(H/'audit-change-log.json',diff(olda,a))
write(H/'preparation-verification.json',{'status':'PASS','component_names':components,'option_names':names,'cell_changes':len(changes),'remaining_required_actions':111,'source_specifications_unchanged':all(x['master_fields']==y['master_fields'] and x['specifications']==y['specifications'] for x,y in zip(g['options'],oldg['options'])),'new_options':0,'new_components':0,'pewter_source_packet_sha256':sha(packet),'sandstone_source_packet_sha256':sha(spacket)})
print(json.dumps(read(H/'preparation-verification.json')))
