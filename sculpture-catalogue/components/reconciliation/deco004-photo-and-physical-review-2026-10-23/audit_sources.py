"""Bound current photo deltas and audit four physical field groups for every active option."""
import collections,copy,csv,hashlib,json,re
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');assets=read(H/'current-assets.json');native=read(H/'current-native-reference-map.json');before_native=read(m['native_map']['snapshot']);brief=read(m['source_photo_requests']['snapshot']);inventory=read(H/'fresh-family-inventory.json');assert len(inventory['records'])==17 and all(x['complete']for x in inventory['records'])
root='/BOLDSTONE MASTER/Products/01 Wall Sculptures/';allfiles={};folders={};families={};deltas=[]
for scope in inventory['records']:
 entries=[x for p in scope['pages']for x in p['structuredContent']['entries']];files=[x for x in entries if x['object_type']=='file'];families[scope['display_path']]={'scope':scope['display_path'],'files':len(files),'folders':sum(x['object_type']=='folder'for x in entries),'file_ids':{x['file_id']for x in files}}
 for x in entries:
  (allfiles if x['object_type']=='file'else folders)[x['file_id']]=x
 for x in files:
  prior=before_native['current_objects'].get(x['file_id'])or assets.get(x['file_id']);size=prior.get('size',prior.get('bytes'))if prior else None;path=prior.get('path')if prior else None
  if prior and(path.casefold()!=x['path'].casefold()or(size is not None and size!=x['file'].get('size',0))):deltas.append({'file_id':x['file_id'],'path':x['path'],'prior_path':path,'prior_size':size,'current_size':x['file'].get('size',0)})
photo=[];cm={x['option_id']:x for x in a['coverage']}
for x in brief['requests']:
 r=x['existing_individual_reference'];f=allfiles.get(r['file_id']);assert f is not None,x['option_id'];actual_parent=f['path'].rsplit('/',1)[0];parent=folders.get(r['folder_id']);assert parent is not None and parent['path'].casefold()==actual_parent.casefold(),x['option_id'];family=root+('/'+f['path'].split('//',1)[1].lstrip('/'))[len(root):].split('/')[0]
 for role in x['missing_roles']:
  rolekey='in_situ'if role.lower()=='display/context'else'series';assert cm[x['option_id']][rolekey]['status']=='No verified image'
  photo.append({'option_id':x['option_id'],'name':x['name'],'role':role,'review_state':'REVIEWED_CURRENT_SOURCE_STILL_REQUIRED','checked_utc':now(),'family':family,'current_family_file_count':families[family]['files'],'current_source_id_found':True,'actual_primary_parent_verified':True,'existing_individual_reference':copy.deepcopy(r),'required_photograph':x['requested_photograph'],'qualification':x['qualification'],'retained_series_review_finding':x.get('retained_series_review_finding'),'new_qualified_source':None,'new_personal_image_approval':False,'scope':'Current complete relevant-family metadata membership; prior whole-original visual findings retained. No global image absence or all-file-byte equivalence claim.'})
assert len(photo)==31 and collections.Counter(x['role']for x in photo)=={'Display/context':14,'Series':17}
source_refs={}
def inspect_refs(t):
 if isinstance(t,dict):
  if isinstance(t.get('path'),str)and t['path'].startswith('/Users/')and isinstance(t.get('sha256'),str):
   key=(t['path'],t['sha256']);snapshot=t.get('snapshot');paths=[snapshot,t['path']]if snapshot else[t['path']];found=[p for p in paths if p and Path(p).is_file()];matches=[p for p in found if sha(p)==t['sha256']];source_refs[key]={'path':t['path'],'expected_sha256':t['sha256'],'snapshot':snapshot,'matched_bytes_at':matches,'status':'HASH_VERIFIED_RECORDED_SOURCE'if matches else'RECORDED_SOURCE_DIGEST_NOT_VERIFIED_IN_AVAILABLE_PATHS'}
  for v in t.values():inspect_refs(v)
 elif isinstance(t,list):
  for v in t:inspect_refs(v)
fields=['Dimensions / depth','Weight','Material / finish','Fixing'];physical=[];by_option=[]
checks={'Dimensions / depth':'Measure the individual panel width, height and maximum projection in cm. Identify the exact finish/size and whether backing or framework is included.','Weight':'Weigh the bare individual panel in kg. State whether fitted backing/hardware is included; separate packaging and any arrangement/system weight.','Material / finish':'Record maker-confirmed substrate, binder/composite, reinforcement and surface/coating details for this exact option or identifiable batch. A finish photograph does not establish composition.','Fixing':'Inspect the exact panel rear. Record fitted fixing type and count, attachment/positions and a paired rear-photo reference. Offered keyhole/French-cleat choices do not establish fitted hardware.'}
for o in g['options']:
 if not o.get('counted_as_individual_option',True):continue
 rows=[]
 for field in fields:
  working=o['master_fields'][field];spec=o['specifications'][field];assert working['physical_verification']==0
  display=working['display'];text=(display+' '+working['basis']).lower();owner_reported=bool(re.search(r'owner[- ](?:stated|confirmed)|\bowner:',display,re.I));qualified_owner_estimate=bool(working.get('explicit_owner_confirmation'))and not owner_reported
  if field=='Fixing'and not owner_reported:status='FITTED_FIXING_NOT_INSPECTED; OFFERED_CHOICES_OR_WORKING_ESTIMATE_RETAINED'
  elif owner_reported:status='OWNER_REPORTED_DETAIL; OBJECT_MEASUREMENT_OR_INSPECTION_NOT_DOCUMENTED'
  elif qualified_owner_estimate:status='OWNER_ACCEPTED_QUALIFIED_ESTIMATE; NOT_PHYSICALLY_VERIFIED'
  elif re.search(r'estimat|hypothes|guess|infer|analogy|comparator',text):status='QUALIFIED_ESTIMATE_OR_COMPARATOR; NOT_PHYSICALLY_VERIFIED'
  else:status='RECORDED_SOURCE_OR_WORKING_DETAIL; OBJECT_VERIFICATION_STILL_REQUIRED'
  inspect_refs(working.get('source_references',[]));ref=cm[o['product_id']]['individual'].get('reference')or{k:o.get(k,'')for k in ['file_id','folder_id','image_url','folder_url']}
  z={'option_id':o['product_id'],'name':o['name'],'component_id':o['canonical_component_id'],'field':field,'current_working_detail':display,'recorded_state':working['state'],'recorded_basis':working['basis'],'verification_outcome':status,'physically_verified':False,'new_measurement_or_hardware_evidence':False,'source_assertions':copy.deepcopy(spec.get('assertions',[])),'source_assertions_count':len(spec.get('assertions',[])),'working_source_references':copy.deepcopy(working.get('source_references',[])),'requires_object_specific_evidence':checks[field],'image_reference':copy.deepcopy(ref),'source_scope_limit':'Recorded source/owner/estimate review only; no direct physical access. Accepted working values remain unchanged.'};physical.append(z);rows.append(z)
  assert working['display']==o['master_fields'][field]['display']
 by_option.append({'option_id':o['product_id'],'name':o['name'],'image_reference':copy.deepcopy(ref),'physical_fields':rows,'complete_physical_verification':False})
assert len(by_option)==187 and len(physical)==748
input_source=B/'outputs/bordered-moonphase-master-refresh-2026-10-23/Physical_Verification_Input_187_Options.csv';input_rows=list(csv.DictReader(input_source.open(encoding='utf-8-sig')));measure_cols=['actual_width_cm','actual_height_cm','actual_maximum_depth_cm','bare_panel_measured_weight_kg','maker_material_recipe','fitted_fixing_type','fitted_fixing_count'];entered=[x for x in input_rows if any(x[k]for k in measure_cols)];assert not entered,'Owner-entered physical data requires review before an unchanged-value publication'
summary={'status':'ALL_187_ACTIVE_OPTIONS_PHYSICAL_SOURCE_AUDITED_MEASUREMENTS_STILL_REQUIRED','recorded_utc':now(),'active_options_reviewed':187,'physical_field_groups_reviewed':748,'source_assertions_reviewed':sum(x['source_assertions_count']for x in physical),'verification_outcomes':dict(collections.Counter(x['verification_outcome']for x in physical)),'recorded_source_references_checked':len(source_refs),'recorded_source_reference_statuses':dict(collections.Counter(x['status']for x in source_refs.values())),'physical_input_rows_checked':len(input_rows),'rows_with_entered_measurements':len(entered),'new_physical_verifications':0,'accepted_working_fields_changed':0,'ledger':str(H/'physical-source-audit.json'),'input_checklist':str(input_source),'physical_access_available':False}
write(H/'physical-source-audit.json',{'summary':summary,'options':by_option,'field_rows':physical,'recorded_source_reference_validation':list(source_refs.values())});write(H/'photo-source-review.json',{'status':'ALL_31_ACTIVE_PHOTOGRAPH_ROLES_REVIEWED_CURRENT_SOURCE_STILL_REQUIRED','recorded_utc':now(),'scope_families':17,'scope_files':len(allfiles),'scope_folders':len(folders),'metadata_deltas_against_known_canonical_or_asset_records':deltas,'all_original_file_bytes_rehashed':False,'role_counts':{'Display/context':14,'Series':17},'requests':photo,'per_family_summary':[{k:v for k,v in x.items()if k!='file_ids'}for x in families.values()]})
g['latest_physical_source_audit']=summary;g['latest_active_photo_source_review']={'path':str(H/'photo-source-review.json'),'sha256':sha(H/'photo-source-review.json'),'active_context_roles':14,'active_series_roles':17,'new_qualified_roles':0,'source_scope':'BOLDSTONE MASTER only'};write(H/'canonical-master-register.json',g)
asset=assets['id:cnqzTNngPVsAAAAAAAyluQ'];f=next(x['result']['structuredContent']['file']for x in read(H/'fresh-native-evidence.json')['records']if x['id']==asset['file_id']);asset.update(current_native_revision=f['rev'],current_metadata_server_modified=f['server_modified'],modified_time=f['server_modified']);write(H/'current-assets.json',assets)
e=read(H/'evidence-manifest.json')
for name in ['fresh-wall-sculpture-root.json','physical-source-audit.json','photo-source-review.json']:e[str(H/name)]={'sha256':sha(H/name)}
write(H/'evidence-manifest.json',e);print(json.dumps({'photo_roles_reviewed':31,'families':17,'files':len(allfiles),'known_metadata_deltas':len(deltas),'physical_options_audited':187,'physical_field_groups':748,'new_physical_verifications':0,'source_reference_statuses':summary['recorded_source_reference_statuses']}))
