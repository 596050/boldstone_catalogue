"""Owner-directed current size and customisation policy; preserve source evidence."""
import collections,copy,hashlib,importlib.util,json,math,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
s=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
book=v.load(H/'inputs/master_workbook.before');g=read(H/'inputs/master_register.before');oldg=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a);d=read(H/'owner-decision.json');DID=d['decision_id'];legacy='BSI-04D6E8690F30';white='BSI-FE10273D3655';opts={o['product_id']:o for o in g['options']};frozen=[o for o in g['options']if o['family']=='Frozen Fish'];assert len(frozen)==6
links={}
for sn,sh in book['sheets'].items():
 loc=sh['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(book['files'][rp])}if rp in book['files']else{}
 for h in sh['root'].findall('.//'+v.q('hyperlink')):
  c=h.get('ref');t='#'+h.get('location')if h.get('location')else rs[h.get('{'+v.R+'}id')].get('Target');links[(sn,c)]={'sheet':sn,'cell':c,'target':t,'label':book['values'][sn].get(c,'')}
original_links=copy.deepcopy(links);changes={};cache_overrides={}
def setcell(sn,c,value):
 assert c not in book['formulas'][sn],(sn,c)
 before=book['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def setlink(sn,c,target,label):
 if target:links[(sn,c)]={'sheet':sn,'cell':c,'target':target,'label':label}
 else:links.pop((sn,c),None)
 setcell(sn,c,label)
def rows(sn,pid,col='A'):return[i for i in range(10,1600)if book['values'][sn].get(col+str(i))==pid]
def onerow(sn,pid,col='A'):
 x=rows(sn,pid,col);assert len(x)==1,(sn,pid,x);return x[0]
policy={'policy_id':'WALL-SCULPTURE-CUSTOMISATION-2026-10-21','status':'OWNER_CONFIRMED_OFFER_POLICY','recorded_utc':now(),'source_decision':DID,'scope':'All current and future wall sculptures','available':True,'axes':['size','colour','texture','material','orientation'],'other_customisations_available':True,'customer_text':'All wall sculptures can be customised in size, colour, texture, material, orientation and other details. Specifications describe the current listed version; the chosen specification and quote are agreed for a custom order.','catalogue_count_effect':0,'creates_all_possible_SKUs':False,'automatically_transfers_base_weight_price_or_stock':False}
g['wall_sculpture_customisation_policy']=policy;g['current_frozen_fish_size_policy']={'decision_id':DID,'height_cm':70,'width_cm':15,'scope':'All current Frozen Fish records and finishes','depth':'Existing estimates/listing claims retained','custom_sizes_available':True,'former_100x22_claim_status':'Historical source configuration, superseded as current default','affected_option_ids':[o['product_id']for o in frozen]}
oldname=opts[legacy]['name'];newname='Frozen Fish Long (FFL1) — White, 70 × 15 cm';opts[legacy]['name']=newname
opts[legacy].setdefault('retained_names',[]).append(oldname)if oldname not in opts[legacy].get('retained_names',[])else None
for o in g['options']:
 o['customisation_policy_ref']=policy['policy_id'];o['offered_customisation_axes']=copy.deepcopy(policy['axes']);o['other_customisations_available']=True
 j=onerow('Master Catalogue',o['product_id']);old=book['values']['Master Catalogue'].get('S'+str(j),'')
 setcell('Master Catalogue','S'+str(j),'Custom orientation available.'+('\nRecorded choices: '+old if old else''))
for o in frozen:
 pid=o['product_id'];j=onerow('Master Catalogue',pid);before=copy.deepcopy(o['master_fields']['Dimensions / depth']);dep='7 cm — previous listing claim'if 'Terracotta'in o['name']or'Verdigris'in o['name']else'5–7 cm — retained estimate'
 value='70 H × 15 W cm — owner-confirmed current face size. Depth '+dep+'.'
 o.setdefault('master_field_history',[]).append({'field':'Dimensions / depth','before':before,'superseding_decision':DID})
 o['master_fields']['Dimensions / depth'].update(display=value,state='Owner-confirmed current face dimensions; depth retains its prior qualification; not independently measured',basis='Owner instruction, 21 October 2026: all current Frozen Fish are 70 cm high × 15 cm wide. Earlier source dimensions remain in historical evidence.',prior_display=before['display'],owner_decision_id=DID)
 o['current_standard_face_cm']={'height':70,'width':15};o['current_configuration_override']={'owner_decision_id':DID,'applies_to':'Current catalogue defaults; preserved native/source exports remain historical','physical_measurement_performed':False}
 for i in rows('Specifications',pid):
  setcell('Specifications','B'+str(i),o['name'])
  if book['values']['Specifications'].get('C'+str(i))=='Dimensions / depth':
   for col,key in [('D','display'),('E','state'),('F','basis')]:setcell('Specifications',col+str(i),o['master_fields']['Dimensions / depth'][key])
 cache_overrides[('Master Catalogue','E'+str(j))]=value
lo=opts[legacy];lo.update(unbound_size_option=False,unbound_identity=True,record_type='LEGACY_NAMED_WORKING_OPTION_IDENTITY_REVIEW',count_class='Legacy FFL1 identity unresolved; current face 70 × 15 cm',size_class='Current 70 × 15 cm; historical Long 100 × 22 cm superseded',distinct_current_design_or_variant_verified=False)
lo['prior_identity_basis_before_owner_size']=lo['identity_basis'];lo['identity_basis']='Legacy FFL1 design/alias relationship remains unbound. The owner sets every current Frozen Fish to 70 × 15 cm. Historical larger-size source associations are preserved as evidence, rather than a separate current default size.'
lo['current_legacy_identity_disposition']={'owner_decision_id':DID,'current_face_cm':{'height':70,'width':15},'same_as_FFS2_not_assumed':True,'separate_standard_100x22_not_current':True,'next_action':'Identify whether historical FFL1 is the same relief as FFS2 or a separate design at the current 70 × 15 cm size.'}
lo['readiness_note']='Current face size is 70 × 15 cm. Historical Long identity still needs comparison with FFS2; no separate current 100 × 22 cm default is asserted.'
lo['remaining_evidence_gaps']='Legacy FFL1 design identity/alias relationship remains unbound; confirm before separately listing this record.'
before=copy.deepcopy(lo['master_fields']['Weight']);lo.setdefault('master_field_history',[]).append({'field':'Weight','before':before,'superseding_decision':DID})
lo['master_fields']['Weight'].update(display='Approximately 4–6 kg — provisional comparison with 70 × 15 cm White Frozen Fish; exact legacy design and cast weight remain unverified.',state='Working estimate for the revised 70 × 15 cm face; not weighed',basis='Small White Frozen Fish 4–6 kg source range used provisionally. Former 8–10 kg/10 kg Long claims remain historical 100 × 22 cm evidence.',prior_display=before['display'])
for i in rows('Specifications',legacy):
 if book['values']['Specifications'].get('C'+str(i))=='Weight':
  for col,key in [('D','display'),('E','state'),('F','basis')]:setcell('Specifications',col+str(i),lo['master_fields']['Weight'][key])
j=onerow('Master Catalogue',legacy);cache_overrides[('Master Catalogue','F'+str(j))]=lo['master_fields']['Weight']['display']
setcell('Master Catalogue','D'+str(j),'Legacy FFL1 — design identity unbound')
setcell('Master Catalogue','M'+str(j),'Legacy FFL1 identity unresolved; current 70 × 15 cm default')
setcell('Master Catalogue','V'+str(j),lo['readiness_note']+' '+lo['remaining_evidence_gaps']+' Custom size, colour, texture, material and orientation are available under the catalogue policy.')
# Refresh current display labels; raw source tabs and all source assertion values stay intact.
current_sheets=['Master Catalogue','Specifications','References and Gaps','Photo Coverage','Missing Pictures','Identity Review','Listing Reconciliation','Listing Issues','Listing Resolution','Draft Listings']
for sn in current_sheets:
 for c,x in book['values'][sn].items():
  if x==oldname:setcell(sn,c,newname)
for i in rows('References and Gaps',legacy):
 setcell('References and Gaps','D'+str(i),lo['readiness_note']+' '+lo['remaining_evidence_gaps'])
cov={r['option_id']:r for r in a['coverage']};acts={(r['option_id'],r['role']):r for r in a['missing_pictures']}
cl=cov[legacy];cl['name']=newname;cl.setdefault('prior_owner_correction',{})[DID]=copy.deepcopy(olda['coverage'][next(i for i,r in enumerate(olda['coverage'])if r['option_id']==legacy)])
cl['individual'].update(status='Unbound identity',basis='Owner sets all current Frozen Fish to 70 × 15 cm. The remaining gap is whether legacy FFL1 is the same design as FFS2 or a separate relief; no new 100 × 22 cm photograph is requested.',exact_option=False)
cl['in_situ']['basis']='Resolve the legacy FFL1 design relationship before assigning/requiring a separate wider scene. Current face is 70 × 15 cm.'
cl['notes']=['Owner current size: 70 × 15 cm. Legacy FFL1 identity/alias still unbound; do not request a 100 × 22 cm photograph.']
lo['photo_coverage']['individual']='Unbound identity'
i=onerow('Photo Coverage',legacy);setcell('Photo Coverage','C'+str(i),'Unbound identity');setcell('Photo Coverage','L'+str(i),'\n'.join(cl['notes']))
for role in ['Individual','In situ','Series']:
 x=acts[(legacy,role)];x['name']=newname;x['before_owner_size_correction']=copy.deepcopy(x)
 if role=='Individual':x.update(action_type='Verify existing image',action='Confirm whether the legacy FFL1 record is an alias of FFS2 or a separate design at 70 × 15 cm. Use the linked White solo as a comparison, not an assumed FFL1 image.',qualification=cl['individual']['basis'])
 elif role=='In situ':x.update(action='Resolve legacy FFL1 identity first. Reuse existing context if it is FFS2; obtain a separate 70 × 15 cm scene only if a distinct design is confirmed.',qualification=cl['in_situ']['basis'])
 else:x['qualification']='Optional series context; the legacy design must be identified before assigning an exact member. Current face default is 70 × 15 cm.'
cw=cov[white];cw.setdefault('before_owner_size_correction',{})['in_situ']=copy.deepcopy(cw['in_situ'])
finding='Owner instruction assigns all current Frozen Fish the 70 H × 15 W cm face. Bind the White fin-panel garden source to the current FFS2 White option. This is an owner-defined catalogue configuration, not a measurement of the historic pictured cast.'
cw['in_situ'].update(status='Available',basis=finding,reference_is_candidate_only=False,owner_decision_id=DID,owner_confirmed_current_face_cm={'height':70,'width':15},physical_cast_or_size_certified=False)
cw['in_situ']['owner_resolved_prior_deep_review_state']=cw['in_situ'].get('deep_review_state');cw['in_situ']['deep_review_state']='OWNER_CURRENT_SIZE_CONFIRMED'
cw['notes']=['Owner current face size: 70 × 15 cm. Garden image mapped to the current FFS2 White configuration; historic cast not measured.']
wo=opts[white];wo['photo_coverage']['in_situ']='Available';wo['context_status']='Available';wo['context_description']=finding
wo['current_owner_photo_decision']={'decision_id':DID,'role':'In situ','status':'Available','finding':finding,'supersedes_size_binding_question':True}
for k,out in [('file_id','context_file_id'),('folder_id','context_folder_id'),('image_url','context_image_url'),('folder_url','context_folder_url')]:wo[out]=cw['in_situ']['reference'][k]
i=onerow('Photo Coverage',white);setcell('Photo Coverage','F'+str(i),'Available');setcell('Photo Coverage','L'+str(i),'\n'.join(cw['notes']));setlink('Photo Coverage','G'+str(i),cw['in_situ']['reference']['image_url'],'Context image')
j=onerow('Master Catalogue',white);setlink('Master Catalogue','T'+str(j),wo['context_image_url'],'Context image')
setcell('Master Catalogue','V'+str(j),'Owner-confirmed current Frozen Fish face: 70 × 15 cm. White garden image associated with this catalogue configuration. Depth, mass, formulation, installed hardware and historic pictured-cast measurement keep their prior qualifications.')
x=acts[(white,'In situ')];x['before_owner_size_correction']=copy.deepcopy(x);x.update(status='Resolved',action='Garden role mapped to current 70 × 15 cm FFS2 White under the owner instruction.',qualification=finding,owner_decision_id=DID)
for pid in [legacy,white]:
 for role in ['Individual','In situ','Series']:
  if(pid,role)not in acts:continue
  x=acts[(pid,role)];j=next(i for i in range(10,221)if book['values']['Missing Pictures'].get('B'+str(i))==pid and book['values']['Missing Pictures'].get('D'+str(i))==role)
  for col,key in [('C','name'),('E','action_type'),('F','action'),('L','qualification'),('N','status')]:setcell('Missing Pictures',col+str(j),x[key])
# Identity question is preserved with its new scope.
case=next(x for x in a['identity_review']if x['case_id']=='ID-FROZEN-FISH-LONG');case['before_owner_correction']=copy.deepcopy(case);case.update(name=newname,position='Legacy FFL1 design identity; current face 70 × 15 cm',proposed_identity='Compare historical FFL1 with existing FFS2; no extra default size',state='Current size resolved; design/alias relationship unbound',check=cl['individual']['basis'],owner_size_decision=DID)
i=onerow('Identity Review','ID-FROZEN-FISH-LONG')
for col,key in [('B','name'),('C','position'),('D','proposed_identity'),('E','state'),('F','check')]:setcell('Identity Review',col+str(i),case[key])
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];required=[x for x in active if x['status']!='Optional'];counts=a['counts']
counts.update(individual_statuses=dict(collections.Counter(x['individual']['status']for x in a['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),required_picture_actions=len(required),resolved_action_rows=42,active_action_rows=len(active),terminal_tasks_resolved=41,terminal_tasks_binding_required=6,terminal_tasks_capture_required=110,terminal_tasks_size_binding_required=0,owner_standardized_frozen_fish_records=6,legacy_frozen_identity_gaps=1)
assert len(required)==116 and counts['actions_by_type']=={'Find / capture':110,'Verify existing image':6,'Optional image':53},counts
a.update(recorded_utc=now(),status='CURRENT_OWNER_FROZEN_SIZE_AND_CUSTOMISATION_UPDATE',historical_audit={'path':m['audit']['path'],'sha256':m['audit']['sha256'],'prior_counts':olda['counts']},owner_configuration_update={'decision_id':DID,'decision_file':str(H/'owner-decision.json'),'frozen_fish_size_records':6,'new_visual_role_bindings':1,'other_customisation_policy_scope':'All wall sculptures'})
setcell('Photo Coverage','A3','Current owner instruction: all Frozen Fish default to 70 H × 15 W cm. 158 full individual references, 117 qualified in situ references and 108 series references; legacy FFL1 now has an identity gap. All wall sculptures offer customisation.')
setcell('Missing Pictures','A3','Current picture work: 110 find/capture actions, 6 existing-image/identity checks and 53 optional series references. 116 required actions remain. Legacy FFL1 needs identity comparison at 70 × 15 cm; a separate 100 × 22 cm image is no longer requested.')
setcell('Master Catalogue','A3',policy['customer_text']);setcell('Master Catalogue','A4','Working individual option records')
setcell('Master Catalogue','A6','184 working records comprise 176 options on 111 identified components, seven Wall Circle visual entries and one legacy FFL1 identity under review. All current Frozen Fish default to 70 × 15 cm. Custom requests do not add speculative options to this count.')
write(H/'wall-sculpture-customisation-policy.json',policy);write(H/'image-coverage-current.json',a)
g['summary']['documented_individual_size_options_exact_photo_unbound']=0;g['summary']['unresolved_legacy_frozen_fish_identity_records']=1
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'recorded_utc':now(),'status':a['status'],'audit':str((H/'image-coverage-current.json').relative_to(BASE)),'path':str(H/'image-coverage-current.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'counts':counts,'scope':'Owner current Frozen Fish face standardisation and all-wall-sculpture customisation. Former Long size gap reclassified as legacy identity, not merged.','verification':str((H/'saved-file-verification.json').relative_to(BASE)),'visual_verification':str((H/'visual-verification.json').relative_to(BASE))}
g['latest_image_coverage_audit'].pop('verification_sha256',None);g['latest_image_coverage_audit'].pop('visual_verification_sha256',None)
g.setdefault('historical_terminal_photo_reviews',[]).append(copy.deepcopy(g['latest_terminal_photo_review']))
event={'recorded_utc':now(),'decision_id':DID,'option_id':white,'role':'In situ','state':'OWNER_CURRENT_SIZE_RESOLVED','finding':finding,'reference':cw['in_situ']['reference']}
write(H/'owner-guided-events.json',[event]);g['latest_terminal_photo_review']={'recorded_utc':now(),'ledger':str((H/'owner-guided-events.json').relative_to(BASE)),'ledger_sha256':sha(H/'owner-guided-events.json'),'reviewed':1,'resolved_visual_associations':1,'remaining_required_actions':116,'find_capture_or_size_binding':110,'existing_image_bindings':6,'new_individual_photos':0,'remote_mutations':0}
g['latest_owner_configuration_update']={'decision':str((H/'owner-decision.json').relative_to(BASE)),'decision_sha256':sha(H/'owner-decision.json'),'customisation_policy':str((H/'wall-sculpture-customisation-policy.json').relative_to(BASE)),'frozen_option_ids':[o['product_id']for o in frozen],'all_184_options_customisable':True,'legacy_identity_not_merged':True}
write(H/'canonical-master-register.json',g)
u=read(H/'inputs/owner_ledger.before');u.setdefault('family_standard_size_decisions',[]).append({**d,'affected_option_ids':[o['product_id']for o in frozen]});u.setdefault('wall_sculpture_customisation_policy_decisions',[]).append({**policy,'user_statement':d['user_statement']});u['updated_utc']=now();write(H/'owner-ledger.pending.json',u)
walk=read(H/'inputs/guided_review.before');answer={**copy.deepcopy(walk['current_item']),'owner_answer':d['user_statement'],'decision_id':DID,'recorded_utc':now(),'status':'ANSWER_RECORDED_AND_APPLIED'};walk['owner_answers'].append(answer)
prior=read(BASE/'components/reconciliation/candidate-binding-deep-review-2026-10-21/candidate-checks.json');n=next(x for x in prior if x['sequence']==99)
walk['current_item']={'step':2,'case_sequence':99,'option_id':n['option_id'],'name':n['name'],'primary_reference':n['primary_reference'],'candidate_reference':n['candidate_reference'],'question':'Does the spiral panel second from the left in the Riyadh pool-wall photo show the same design as the workshop panel, possibly mirrored/rotated, or a separate design?','owner_answer':None}
walk.update(status='READY_FOR_NEXT_OWNER_CLASSIFICATION',updated_utc=now(),current_master_workbook=read(H/'inputs/master_pointer.before')['workbook'],master_changes_applied=1);walk['remaining_case_order']=[100,139,154,155];write(H/'walkthrough.pending.json',walk)
heights={}
for(sn,cell),ch in changes.items():
 if int(re.sub('[A-Z]','',cell))<9 or not isinstance(ch['value'],str):continue
 col=re.match('[A-Z]+',cell)[0];idx=0
 for z in col:idx=idx*26+ord(z)-64
 root=book['sheets'][sn]['root'];width=next((float(x.get('width'))for x in root.findall('.//'+v.q('col'))if int(x.get('min'))<=idx<=int(x.get('max'))),13);rn=int(cell[len(col):]);lines=sum(max(1,math.ceil(len(x)/max(8,width*.9)))for x in ch['value'].split('\n'));height=lines*13+12;before=float(next(x for x in root.find(v.q('sheetData'))if x.get('r')==str(rn)).get('ht',15))
 if height>before:assert height<=409,(sn,cell,height);heights[(sn,rn)]=max(heights.get((sn,rn),before),height)
cache_values=[('Photo Coverage','B4',158),('Photo Coverage','D4',117),('Photo Coverage','F4',108),('Photo Coverage','B5',26),('Photo Coverage','D5',2),('Photo Coverage','F5',3),('Missing Pictures','B4',110),('Missing Pictures','D4',6),('Missing Pictures','F4',53)]
for sn,c,val in cache_values:cache_overrides[(sn,c)]=val
plan={'cell_changes':list(changes.values()),'formula_changes':[],'hyperlinks':list(links.values()),'formula_caches':[{'sheet':sn,'cell':c,'formula':book['formulas'][sn][c],'expected':val}for(sn,c),val in cache_overrides.items()],'row_heights':[{'sheet':sn,'row':i,'height':ht}for(sn,i),ht in heights.items()],'style_changes':[],'preview_ranges':[['Master Catalogue','A2:H7','01-current-policy'],['Master Catalogue','B91:J96','02-frozen-current-specs'],['Master Catalogue','R91:V92','03-custom-orientation'],['Specifications','B496:F497','04-legacy-size-weight'],['Photo Coverage','B91:L96','05-frozen-image-status'],['Identity Review','B10:F10','06-legacy-identity']],'baseline_ranges':[['Master Catalogue','A2:H7','baseline-policy'],['Master Catalogue','B91:J96','baseline-frozen']]}
write(H/'workbook-edit-plan.json',plan)
write(H/'preparation-verification.json',{'status':'PASS','frozen_records_standardized':6,'customisable_option_records':184,'legacy_identity_not_merged':True,'source_assertions_unchanged':g['original_review_specification_assertions']==oldg['original_review_specification_assertions'],'required_picture_actions':116,'cell_changes':len(changes),'native_hyperlinks':len(links)})
print(json.dumps(read(H/'preparation-verification.json')))
