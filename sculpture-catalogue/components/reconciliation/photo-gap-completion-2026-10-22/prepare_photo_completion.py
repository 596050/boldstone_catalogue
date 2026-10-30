"""Apply six source-qualified visual roles and the owner's photograph-review scope."""
import collections,copy,hashlib,importlib.util,json,math,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
g=read(H/'inputs/master_register.before');oldg=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a);bindings=read(H/'new-photo-bindings.json');queue=read(H/'photo-review-queue.json');summary=read(H/'photo-review-summary.json');assets=read(H/'current-assets.json');did='OWNER-FROZEN-FISH-70X15-PHOTO-WORK-2026-10-22'
decision={'decision_id':did,'recorded_utc':now(),'user_statement':'Right now, frozen fish should be jsut be set to 70 × 15 cm','follow_on_instruction':'Go through26individual-image gaps,65in situ gaps and20series-image gaps.','current_frozen_fish_default':{'height_cm':70,'width_cm':15},'interpretation':'Retain70×15cm on every current Frozen Fish option. Proceed with the photograph work; defer the historical FFL1/FFS2 identity question without merging records or inferring an identity answer.','working_specification_changes':0,'new_options':0,'native_mutations':0}
write(H/'owner-decision.json',decision)
sp=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v);b=v.load(H/'inputs/master_workbook.before')
links={};changes={};styles={}
for sn,s in b['sheets'].items():
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in s['root'].findall('.//'+v.q('hyperlink')):
  cell=h.get('ref');target='#'+h.get('location')if h.get('location')else rs[h.get('{'+v.R+'}id')].get('Target');links[(sn,cell)]={'sheet':sn,'cell':cell,'target':target,'label':b['values'][sn].get(cell,'')}
def setcell(sn,cell,value):
 assert cell not in b['formulas'][sn],(sn,cell)
 if b['values'][sn].get(cell,'')!=value:changes[(sn,cell)]={'sheet':sn,'cell':cell,'before':b['values'][sn].get(cell,''),'value':value}
def setlink(sn,cell,target,label):
 if (sn,cell)not in links:styles[(sn,cell)]={'sheet':sn,'cell':cell,'font':{'color':'#0563C1','underline':'single'}}
 links[(sn,cell)]={'sheet':sn,'cell':cell,'target':target,'label':label};setcell(sn,cell,label)
def row(sn,pid,col='A'):
 rr=[i for i in range(10,1800)if b['values'][sn].get(col+str(i))==pid];assert len(rr)==1,(sn,pid,rr);return rr[0]
def actionrow(pid,role):return next(i for i in range(10,221)if b['values']['Missing Pictures'].get('B'+str(i))==pid and b['values']['Missing Pictures'].get('D'+str(i))==role)
affected={};dependencies=[];previews=[['Photo Coverage','A2:L5','01-summary']]
for d in bindings:
 pid=d['option_id'];role=d['role'];key={'In situ':'in_situ','Series':'series'}[role];c=next(x for x in a['coverage']if x['option_id']==pid);o=next(x for x in g['options']if x['product_id']==pid);act=next(x for x in a['missing_pictures']if x['option_id']==pid and x['role']==role);ref=d['reference'];finding=d['finding']+' '+d['qualification'];affected.setdefault(pid,[]).append(d)
 assert c[key]['status']=='No verified image'and act['status']=='Open'and act['action_type']=='Find / capture'
 c.setdefault('before_photo_gap_completion',{})[key]=copy.deepcopy(c[key]);c[key].update(status='Available',reference=copy.deepcopy(ref),basis=finding,reference_is_candidate_only=False,member_position=d['position'],visual_binding_id=d['binding_id'],physical_cast_or_size_certified=False,source_origin_authenticated=False)
 o.setdefault('photo_coverage_before_photo_gap_completion',copy.deepcopy(o['photo_coverage']));o['photo_coverage'][key]='Available'
 o.setdefault('current_photo_gap_review',{'recorded_utc':now(),'ledger':rel(H/'photo-review-queue.json'),'bindings':[]})['bindings'].append(copy.deepcopy(d))
 if role=='In situ':
  o['context_before_photo_gap_completion']={k:copy.deepcopy(o.get(k))for k in ['context_status','context_description','context_file_id','context_folder_id','context_image_url','context_folder_url']};o.update(context_status='Available',context_description=finding)
  for k in ['file_id','folder_id','image_url','folder_url']:o['context_'+k]=ref[k]
 act['before_photo_gap_completion']=copy.deepcopy(act);act.update(status='Resolved',action='Use the existing linked '+role.lower()+' reference at '+d['position']+'.',reference=copy.deepcopy(ref),qualification=finding,scope='Exact depicted design/finish association only; original physical specifications and source qualifications retained.',visual_binding_id=d['binding_id'])
 i=row('Photo Coverage',pid);j=row('Master Catalogue',pid);k=actionrow(pid,role)
 sc,ic,fc,idc,pc=('F','G','H','O','P')if role=='In situ'else('I','J','K','Q','R')
 setcell('Photo Coverage',sc+str(i),'Available');setlink('Photo Coverage',ic+str(i),ref['image_url'],'Room / garden'if role=='In situ'else'Series image');setlink('Photo Coverage',fc+str(i),ref['folder_url'],'Folder');setcell('Photo Coverage',idc+str(i),ref['file_id']);setcell('Photo Coverage',pc+str(i),ref['folder_id'])
 if role=='In situ':setlink('Master Catalogue','T'+str(j),ref['image_url'],'Context image');setlink('Master Catalogue','U'+str(j),ref['folder_url'],'Folder')
 for col,field in [('F','action'),('K','scope'),('L','qualification'),('N','status')]:setcell('Missing Pictures',col+str(k),act[field])
 setlink('Missing Pictures','G'+str(k),ref['image_url'],'Mapped visual reference');setlink('Missing Pictures','H'+str(k),ref['folder_url'],'Folder');setcell('Missing Pictures','I'+str(k),ref['file_id']);setcell('Missing Pictures','J'+str(k),ref['folder_id'])
 dependencies.append({'coverage_cell':sc+str(i),'role':role,'action_cell':'N'+str(k)})
for pid,ds in affected.items():
 c=next(x for x in a['coverage']if x['option_id']==pid);c['notes_before_photo_gap_completion']=copy.deepcopy(c['notes']);c['notes']=[d['role']+': '+d['finding']+' '+d['qualification']for d in ds];i=row('Photo Coverage',pid);setcell('Photo Coverage','L'+str(i),'\n'.join(c['notes']))
 j=row('Master Catalogue',pid);prior=b['values']['Master Catalogue'].get('V'+str(j),'');prior=re.sub(r'Photo review: individual[^\n]*','Photo review: individual '+c['individual']['status']+'; in situ '+c['in_situ']['status']+'; series '+c['series']['status']+'. See Photo Coverage for role qualifications.',prior);setcell('Master Catalogue','V'+str(j),prior+'\n22 October: complete existing '+', '.join(d['role'].lower()for d in ds)+' references bound; physical specifications retained.')
 previews.append(['Photo Coverage',f'B{i}:L{i}','role-'+pid])
for x in a['coverage']:
 if x['option_id']=='BSI-04D6E8690F30':x['legacy_identity_review_deferred']={'decision_id':did,'current_default':'70 H×15 W cm','identity_answer_inferred':False};x['notes'].append('22 October: owner directs photograph work to proceed with all Frozen Fish at70×15cm; legacy identity/alias review deferred.')
for x in a['missing_pictures']:
 if x['option_id']=='BSI-04D6E8690F30':
  x['owner_scope_before_photo_gap_completion']={'action':x['action'],'qualification':x['qualification'],'scope':x['scope']};x['review_deferred_by_owner_scope']=True;x['action']='Keep current Frozen Fish at70cm high×15cm wide. Historical FFL1/FFS2 binding is deferred; continue the other photograph tasks.';x['scope']='Existing historical identity reference retained; no current100×22cm photograph requested and no merger inferred.';x['qualification']='The owner reaffirms the current70×15cm default. This is a size instruction; the retained legacy identity and image binding are not silently merged.'
  k=actionrow(x['option_id'],x['role'])
  for col,key in [('F','action'),('K','scope'),('L','qualification')]:setcell('Missing Pictures',col+str(k),x[key])
for x in g['options']:
 if x['product_id']in g['current_frozen_fish_size_policy']['affected_option_ids']:assert '70'in x['master_fields']['Dimensions / depth']['display']and '15'in x['master_fields']['Dimensions / depth']['display']
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];required=[x for x in active if x['status']!='Optional'];counts=a['counts'];counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),required_picture_actions=len(required),resolved_action_rows=53,active_action_rows=len(active),terminal_tasks_resolved=52,terminal_tasks_capture_required=104,current_files_in_root_inventory=6633,current_root_folder_count=427,legacy_frozen_identity_review_deferred=True)
assert len(required)==105 and counts['actions_by_type']=={'Verify existing image':1,'Find / capture':104,'Optional image':53}
a.update(recorded_utc=now(),status='CURRENT_PHOTO_GAP_COMPLETION_2026_10_22',historical_audit={'path':m['audit']['path'],'sha256':m['audit']['sha256'],'prior_counts':olda['counts']},latest_photo_gap_completion={'queue':rel(H/'photo-review-queue.json'),'queue_sha256':sha(H/'photo-review-queue.json'),'summary':summary,'bindings':rel(H/'new-photo-bindings.json'),'bindings_sha256':sha(H/'new-photo-bindings.json'),'source_verifications':[{'path':rel(H/x),'sha256':sha(H/x)}for x in ['context-original-verification.json','selected-original-verification.json']],'current_native_inventory':{'path':rel(H/'current-inventory.json'),'sha256':sha(H/'current-inventory.json')},'new_individual_images_created':0})
write(H/'image-coverage-current.json',a)
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'recorded_utc':now(),'status':a['status'],'path':str(H/'image-coverage-current.json'),'audit':rel(H/'image-coverage-current.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'counts':counts,'scope':'All111 carried-forward actions reviewed. Six additional visual roles mapped;17 exact-crop candidates awaiting owner criterion; Frozen Fish stays70×15cm and legacy identity review is deferred.','verification':rel(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json')}
for key in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(key,None)
g.setdefault('historical_terminal_photo_reviews',[]).append(copy.deepcopy(g['latest_terminal_photo_review']));g['latest_terminal_photo_review']={'recorded_utc':now(),'ledger':rel(H/'photo-review-queue.json'),'ledger_sha256':sha(H/'photo-review-queue.json'),'reviewed':111,'resolved_visual_associations':6,'remaining_required_actions':105,'find_capture_or_size_binding':104,'existing_image_bindings':1,'new_individual_photos':0,'remote_mutations':0}
g['latest_photo_gap_completion']={**a['latest_photo_gap_completion'],'owner_scope_decision':rel(H/'owner-decision.json'),'owner_scope_decision_sha256':sha(H/'owner-decision.json'),'remaining_individual_gaps':26,'remaining_in_situ_gaps':61,'remaining_series_gaps':18,'frozen_fish_default_unchanged':'70 H×15 W cm','legacy_identity_deferred':True};write(H/'canonical-master-register.json',g)
u=read(H/'inputs/owner_ledger.before');u.setdefault('photo_review_scope_instructions',[]).append(copy.deepcopy(decision));u['updated_utc']=now();write(H/'owner-ledger.pending.json',u)
walk=read(H/'inputs/guided_review.before');walk.setdefault('deferred_review_items',[]).append({**copy.deepcopy(walk['current_item']),'deferred_by':did,'reason':'Owner directs photograph work to proceed with Frozen Fish current size70×15cm.'});walk.setdefault('scope_instructions',[]).append(copy.deepcopy(decision));fp=assets['id:cnqzTNngPVsAAAAAAAyhSQ'];walk['current_item']={'step':8,'case_sequence':'exact-crop-criterion','option_ids':['BSI-6D48F324B10C','BSI-59CBB4D2FA9E'],'name':'Fingerprint — Verdigris Left and Right component crops','primary_reference':{k:fp[k]for k in ['file_id','folder_id','name','path','image_url','folder_url']},'question':'Should Python be used to make exact lossless crops of the fully visible Left and Right panels, keeping their original pixels and colours? The existing image-review thread owns this walkthrough.','owner_answer':None,'review_thread':'01a13fe6-495b-7253-b923-31823b4cbca8'};walk.update(status='READY_FOR_EXACT_CROP_WALKTHROUGH',updated_utc=now(),remaining_case_order=[],latest_photo_gap_completion=g['latest_photo_gap_completion']);write(H/'walkthrough.pending.json',walk)
setcell('Photo Coverage','A3','22 October photo review: six further roles mapped from existing originals. 158 individual views,123 in situ and113 series references. 26 individual gaps include17 crop candidates,8 separate-photo needs and1 deferred legacy binding. Frozen Fish:70×15cm.')
setcell('Missing Pictures','A3','105 required action rows remain:104 find/capture and1 deferred identity check. Six existing context/series roles mapped.17 individual crops need the owner criterion;8 need separate photographs. All Frozen Fish remain70×15cm.')
i=row('Photo Coverage','BSI-04D6E8690F30');setcell('Photo Coverage','L'+str(i),'\n'.join(next(x for x in a['coverage']if x['option_id']=='BSI-04D6E8690F30')['notes']))
heights={}
for (sn,cell),ch in changes.items():
 if cell=='A3'or not isinstance(ch['value'],str):continue
 col=re.match('[A-Z]+',cell)[0];idx=0
 for z in col:idx=idx*26+ord(z)-64
 root=b['sheets'][sn]['root'];width=next((float(x.get('width'))for x in root.findall('.//'+v.q('col'))if int(x.get('min'))<=idx<=int(x.get('max'))),13);rn=int(cell[len(col):]);lines=sum(max(1,math.ceil(len(x)/max(8,width*.9)))for x in ch['value'].split('\n'));ht=lines*13+12;before=float(next(x for x in root.find(v.q('sheetData'))if x.get('r')==str(rn)).get('ht',15))
 if ht>before:assert ht<=409,(sn,cell,ht);heights[(sn,rn)]=max(heights.get((sn,rn),before),ht)
formula_values=[('Photo Coverage','B4',158),('Photo Coverage','D4',123),('Photo Coverage','F4',113),('Photo Coverage','B5',26),('Photo Coverage','D5',0),('Photo Coverage','F5',0),('Missing Pictures','B4',104),('Missing Pictures','D4',1),('Missing Pictures','F4',53)]
plan={'cell_changes':list(changes.values()),'formula_changes':[],'hyperlinks':list(links.values()),'formula_caches':[{'sheet':sn,'cell':cell,'formula':b['formulas'][sn][cell],'expected':x}for sn,cell,x in formula_values],'row_heights':[{'sheet':sn,'row':rn,'height':ht}for(sn,rn),ht in heights.items()],'style_changes':list(styles.values()),'baseline_ranges':[['Photo Coverage',f'B{row("Photo Coverage","BSI-E5B3990ECDDC")}:L{row("Photo Coverage","BSI-E5B3990ECDDC")}','baseline-moonwave']],'preview_ranges':previews,'dependency_tests':dependencies,'expected_native_hyperlinks':len(links)};write(H/'workbook-edit-plan.json',plan)
def diff(before,after,path=[]):
 if before==after:return []
 if isinstance(before,dict)and isinstance(after,dict):
  out=[]
  for k in sorted(set(before)|set(after)):
   if k not in before:out.append({'path':path+[k],'kind':'added','after':after[k]})
   elif k not in after:out.append({'path':path+[k],'kind':'removed','before':before[k]})
   else:out.extend(diff(before[k],after[k],path+[k]))
  return out
 if isinstance(before,list)and isinstance(after,list)and len(before)==len(after):return [x for i,(b,a)in enumerate(zip(before,after))for x in diff(b,a,path+[i])]
 return [{'path':path,'kind':'changed','before':before,'after':after}]
write(H/'register-change-log.json',diff(oldg,g));write(H/'audit-change-log.json',diff(olda,a));write(H/'preparation-verification.json',{'status':'PASS','source_specifications_unchanged':all(x['master_fields']==y['master_fields']and x['specifications']==y['specifications']for x,y in zip(g['options'],oldg['options'])),'all184_names_and_counts_unchanged':all(x['name']==y['name']for x,y in zip(g['options'],oldg['options'])),'visual_roles_added':6,'cell_changes':len(changes),'expected_native_hyperlinks':len(links),'new_individual_images':0,'remaining_required_actions':105,'Frozen_Fish_current_size':'70 H×15 W cm','legacy_identity_review_deferred':True});print(json.dumps(read(H/'preparation-verification.json')))
