"""Apply one owner-confirmed context design match and advance the walkthrough."""
import collections,copy,hashlib,importlib.util,json,math,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
b=v.load(H/'inputs/master_workbook.before');g=read(H/'inputs/master_register.before');oldg=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a);d=read(H/'owner-decision.json');pid=d['question_context']['option_id'];did=d['decision_id']
links={}
for sn,s in b['sheets'].items():
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in s['root'].findall('.//'+v.q('hyperlink')):
  c=h.get('ref');target='#'+h.get('location')if h.get('location')else rs[h.get('{'+v.R+'}id')].get('Target');links[(sn,c)]={'sheet':sn,'cell':c,'target':target,'label':b['values'][sn].get(c,'')}
changes={}
def setcell(sn,c,x):
 assert c not in b['formulas'][sn]
 if b['values'][sn].get(c,'')!=x:changes[(sn,c)]={'sheet':sn,'cell':c,'before':b['values'][sn].get(c,''),'value':x}
def setlink(sn,c,target,label):links[(sn,c)]={'sheet':sn,'cell':c,'target':target,'label':label};setcell(sn,c,label)
def row(sn,pid,col='A'):
 r=[i for i in range(10,1500)if b['values'][sn].get(col+str(i))==pid];assert len(r)==1,(sn,pid);return r[0]
c=next(x for x in a['coverage']if x['option_id']==pid);o=next(x for x in g['options']if x['product_id']==pid);action=next(x for x in a['missing_pictures']if x['option_id']==pid and x['role']=='In situ')
ref=copy.deepcopy(d['question_context']['candidate_reference']);primary=d['question_context']['primary_reference'];native={x['id']:x for x in read(H/'native-readback.json')}
for r in [ref,primary]:assert r['path']=='ns:202238505/'+native[r['file_id']]['path_display'],r
assert native[ref['folder_id']]['path_display']==posixpath.dirname(native[ref['file_id']]['path_display'])
finding='Owner confirms the spiral SECOND FROM LEFT in the Riyadh pool-wall photograph is the same design as the workshop Shellmoon panel. Bind it as an in situ design reference. Mirroring or rotation may explain the presentation; the exact transformation and physical cast are not confirmed. Existing component dimensions, weight and other specifications retain their qualifications.'
c.setdefault('before_owner_design_confirmation',{})[did]=copy.deepcopy(c['in_situ'])
c['in_situ'].update(status='Available',basis=finding,reference=ref,reference_is_candidate_only=False,member_position='SECOND FROM LEFT on the pool wall',deep_review_state='OWNER_SAME_DESIGN_CONFIRMED',owner_decision_id=did,same_design_owner_confirmed=True,exact_transform_confirmed=False,physical_cast_or_size_certified=False)
c['notes']=['22 October owner review: same Shellmoon design confirmed; pool-wall position SECOND FROM LEFT. Exact mirrored/rotated transform unspecified.']
c['owner_guided_review']={'decision_id':did,'source_decision':rel(H/'owner-decision.json'),'source_reference':ref,'comparison_reference':primary,'member_position':'SECOND FROM LEFT','specification_changes':0}
o.setdefault('context_before_owner_design_confirmation',{})[did]={k:copy.deepcopy(o.get(k))for k in ['context_status','context_description','context_image_url','context_folder_url','context_file_id','context_folder_id']}
o['photo_coverage']['in_situ']='Available';o['context_status']='Available';o['context_description']=finding
for key,out in [('file_id','context_file_id'),('folder_id','context_folder_id'),('image_url','context_image_url'),('folder_url','context_folder_url')]:o[out]=ref[key]
o['current_owner_photo_decision']={'decision_id':did,'role':'In situ','status':'Available','same_design_confirmed':True,'member_position':'SECOND FROM LEFT','exact_transform_confirmed':False,'same_physical_cast_confirmed':False,'finding':finding}
action['before_owner_design_confirmation']=copy.deepcopy(action);action.update(status='Resolved',action='Pool-wall context mapped to Riyadh — Shellmoon Panel, SECOND FROM LEFT, following owner confirmation.',qualification=finding,scope='Owner-confirmed design association only; no new component, variant SKU, physical cast or specification claim.',owner_decision_id=did,reference=ref)
i=row('Photo Coverage',pid);j=row('Master Catalogue',pid);k=next(i for i in range(10,221)if b['values']['Missing Pictures'].get('B'+str(i))==pid and b['values']['Missing Pictures'].get('D'+str(i))=='In situ')
setcell('Photo Coverage','F'+str(i),'Available');setlink('Photo Coverage','G'+str(i),ref['image_url'],'Context image');setcell('Photo Coverage','L'+str(i),'\n'.join(c['notes']))
setlink('Master Catalogue','T'+str(j),ref['image_url'],'Context image')
prior=b['values']['Master Catalogue'].get('V'+str(j),'');prior=re.sub(r'Photo review: individual[^\n]*','Photo review: individual '+c['individual']['status']+'; in situ Available; series '+c['series']['status']+'. See Photo Coverage for role qualifications.',prior)
setcell('Master Catalogue','V'+str(j),prior+'\nOwner confirms the same Shellmoon design at pool-wall position SECOND FROM LEFT; exact mirroring/rotation is unspecified.')
for col,key in [('F','action'),('K','scope'),('L','qualification'),('N','status')]:setcell('Missing Pictures',col+str(k),action[key])
setlink('Missing Pictures','G'+str(k),ref['image_url'],'Mapped visual reference')
active=[x for x in a['missing_pictures']if x['status']!='Resolved'];required=[x for x in active if x['status']!='Optional'];counts=a['counts']
counts.update(in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in a['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),required_picture_actions=len(required),resolved_action_rows=43,active_action_rows=len(active),terminal_tasks_resolved=42,terminal_tasks_binding_required=5)
assert len(required)==115 and counts['actions_by_type']=={'Find / capture':110,'Verify existing image':5,'Optional image':53}
a.update(recorded_utc=now(),status='CURRENT_OWNER_GUIDED_SHELLMOON_DESIGN_MATCH',historical_audit={'path':m['audit']['path'],'sha256':m['audit']['sha256'],'prior_counts':olda['counts']},owner_guided_design_review={'decision_id':did,'option_id':pid,'new_context_roles_resolved':1,'member_position':'SECOND FROM LEFT','same_design_confirmed':True,'physical_cast_confirmed':False,'remote_mutations':0})
setcell('Photo Coverage','A3','22 October owner review: Riyadh Shellmoon is the SECOND FROM LEFT pool-wall spiral. 158 full individual references, 118 qualified in situ references and 108 series references. Current Frozen Fish default to 70 × 15 cm; all wall sculptures offer customisation.')
setcell('Missing Pictures','A3','115 required actions remain: 110 find/capture actions and 5 existing-image/identity checks. The owner-confirmed Riyadh Shellmoon pool-wall design match is resolved. Optional series references and earlier resolved actions remain recorded.')
write(H/'image-coverage-current.json',a)
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'recorded_utc':now(),'status':a['status'],'audit':rel(H/'image-coverage-current.json'),'path':str(H/'image-coverage-current.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'counts':counts,'scope':'One owner-confirmed design-level context match; 184 records and all existing specifications retained.','verification':rel(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json')}
g['latest_image_coverage_audit'].pop('verification_sha256',None);g['latest_image_coverage_audit'].pop('visual_verification_sha256',None)
g.setdefault('historical_terminal_photo_reviews',[]).append(copy.deepcopy(g['latest_terminal_photo_review']))
event={'recorded_utc':now(),'decision_id':did,'option_id':pid,'role':'In situ','state':'OWNER_SAME_DESIGN_CONFIRMED','finding':finding,'reference':ref,'primary_reference':primary}
write(H/'owner-guided-events.json',[event]);g['latest_terminal_photo_review']={'recorded_utc':now(),'ledger':rel(H/'owner-guided-events.json'),'ledger_sha256':sha(H/'owner-guided-events.json'),'reviewed':1,'resolved_visual_associations':1,'remaining_required_actions':115,'find_capture_or_size_binding':110,'existing_image_bindings':5,'new_individual_photos':0,'remote_mutations':0}
g.setdefault('owner_confirmed_context_design_bindings',[]).append({'decision_id':did,'option_id':pid,'component_id':o['canonical_component_id'],'file_id':ref['file_id'],'folder_id':ref['folder_id'],'position':'SECOND FROM LEFT','same_design_confirmed':True,'exact_transform_confirmed':False})
g['latest_owner_guided_design_review']={'decision':rel(H/'owner-decision.json'),'decision_sha256':sha(H/'owner-decision.json'),'option_id':pid,'same_design_confirmed':True,'member_position':'SECOND FROM LEFT','new_options':0,'specification_changes':0}
write(H/'canonical-master-register.json',g)
u=read(H/'inputs/owner_ledger.before');u.setdefault('image_design_identity_decisions',[]).append({**d,'option_id':pid,'component_id':o['canonical_component_id'],'native_file_id':ref['file_id'],'native_folder_id':ref['folder_id']});u['updated_utc']=now();write(H/'owner-ledger.pending.json',u)
walk=read(H/'inputs/guided_review.before');walk['owner_answers'].append({**copy.deepcopy(walk['current_item']),'owner_answer':d['user_statement'],'interpretation':d['interpretation'],'decision_id':did,'recorded_utc':now(),'status':'ANSWER_RECORDED_AND_APPLIED'})
nextcase=next(x for x in read(BASE/'components/reconciliation/candidate-binding-deep-review-2026-10-21/candidate-checks.json')if x['sequence']==100)
assert nextcase['primary_reference']['path']=='ns:202238505/'+native[nextcase['primary_reference']['file_id']]['path_display']
walk['current_item']={'step':3,'case_sequence':100,'option_id':nextcase['option_id'],'name':nextcase['name'],'primary_reference':nextcase['primary_reference'],'candidate_reference':nextcase['candidate_reference'],'question':'Is the plain curved panel FOURTH FROM LEFT in the pool photograph the same design as the workshop Plain Moon panel, allowing for a mirrored/rotated presentation?','owner_answer':None}
walk.update(status='READY_FOR_NEXT_OWNER_CLASSIFICATION',updated_utc=now(),master_changes_applied=2,remaining_case_order=[139,154,155]);write(H/'walkthrough.pending.json',walk)
heights={}
for(sn,cell),ch in changes.items():
 if cell=='A3'or not isinstance(ch['value'],str):continue
 col=re.match('[A-Z]+',cell)[0];idx=0
 for z in col:idx=idx*26+ord(z)-64
 root=b['sheets'][sn]['root'];width=next((float(x.get('width'))for x in root.findall('.//'+v.q('col'))if int(x.get('min'))<=idx<=int(x.get('max'))),13);rn=int(cell[len(col):]);lines=sum(max(1,math.ceil(len(x)/max(8,width*.9)))for x in ch['value'].split('\n'));ht=lines*13+12;before=float(next(x for x in root.find(v.q('sheetData'))if x.get('r')==str(rn)).get('ht',15))
 if ht>before:assert ht<=409,(sn,cell,ht);heights[(sn,rn)]=max(heights.get((sn,rn),before),ht)
formula_values=[('Photo Coverage','B4',158),('Photo Coverage','D4',118),('Photo Coverage','F4',108),('Photo Coverage','B5',26),('Photo Coverage','D5',1),('Photo Coverage','F5',3),('Missing Pictures','B4',110),('Missing Pictures','D4',5),('Missing Pictures','F4',53)]
plan={'cell_changes':list(changes.values()),'formula_changes':[],'hyperlinks':list(links.values()),'formula_caches':[{'sheet':sn,'cell':cell,'formula':b['formulas'][sn][cell],'expected':x}for sn,cell,x in formula_values],'row_heights':[{'sheet':sn,'row':rn,'height':ht}for(sn,rn),ht in heights.items()],'style_changes':[],'baseline_ranges':[['Photo Coverage',f'B{i}:L{i}','baseline-shellmoon']],'preview_ranges':[['Photo Coverage','A2:L5','01-summary'],['Photo Coverage',f'B{i}:L{i}','02-shellmoon'],['Missing Pictures',f'C{k}:N{k}','03-resolved-action'],['Master Catalogue',f'R{j}:V{j}','04-master-context']],'dependency_test':{'coverage_cell':'F'+str(i),'action_cell':'N'+str(k),'available_before':118,'available_after':117,'verify_before':1,'verify_after':2,'actions_before':5,'actions_after':6}}
write(H/'workbook-edit-plan.json',plan);write(H/'preparation-verification.json',{'status':'PASS','same_design_confirmed':True,'position':'SECOND FROM LEFT','cell_changes':len(changes),'remaining_required_actions':115,'source_specifications_unchanged':all(x['master_fields']==y['master_fields']and x['specifications']==y['specifications']for x,y in zip(g['options'],oldg['options'])),'identity_review_unchanged':a['identity_review']==olda['identity_review'],'new_options':0})
print(json.dumps(read(H/'preparation-verification.json')))
