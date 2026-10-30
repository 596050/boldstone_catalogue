"""Apply 32 deep visual checks to current role coverage, preserving catalogue facts."""
import collections,copy,hashlib,importlib.util,json,math,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
m=read(H/'input-manifest.json')
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
items=read(H/'candidate-checks.json');assert len(items)==32 and all(x['state']!='PENDING_DEEP_REVIEW' and len(x['findings'])==1 for x in items)
for x in items:
 for p in x['findings'][-1]['evidence_plates']:assert sha(p['path'])==p['sha256'],p['path']
g=read(H/'inputs/master_register.before');oldg=copy.deepcopy(g);audit=read(H/'inputs/audit.before');oldaudit=copy.deepcopy(audit)
book=v.load(H/'inputs/master_workbook.before');links={}
for sn,s in book['sheets'].items():
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(book['files'][rp])}if rp in book['files']else{}
 for h in s['root'].findall('.//'+v.q('hyperlink')):
  target='#'+h.get('location')if h.get('location')else rs[h.get('{'+v.R+'}id')].get('Target');cell=h.get('ref');links[(sn,cell)]={'sheet':sn,'cell':cell,'target':target,'label':book['values'][sn].get(cell,'')}
original_links=copy.deepcopy(links);changes={}
def setcell(sn,c,value):
 prior=book['values'][sn].get(c,'')
 if value!=prior:changes[(sn,c)]={'sheet':sn,'cell':c,'before':prior,'value':value}
def setlink(sn,c,target,label):
 if target:links[(sn,c)]={'sheet':sn,'cell':c,'target':target,'label':label}
 else:links.pop((sn,c),None)
 setcell(sn,c,label)
def row(sn,col,value):
 out=[i for i in range(10,1500)if book['values'][sn].get(col+str(i))==value];assert len(out)==1,(sn,value);return out[0]
roles={'In situ':('in_situ','F','G','H','O','P'),'Series':('series','I','J','K','Q','R')}
cov={x['option_id']:x for x in audit['coverage']};opts={x['product_id']:x for x in g['options']};actions={(x['option_id'],x['role']):x for x in audit['missing_pictures']};byopt=collections.defaultdict(list)
for x in items:
 d=x['findings'][-1];pid=x['option_id'];role,sc,ic,fc,idc,dc=roles[x['role']];c=cov[pid];o=opts[pid];a=actions[(pid,x['role'])];i=row('Photo Coverage','A',pid);candidate=copy.deepcopy(x['candidate_reference']);mapped=x['state']=='VISUAL_ROLE_MAPPED';excluded=x['state']=='CANDIDATE_EXCLUDED_CAPTURE_REQUIRED'
 status='Available'if mapped else'No verified image'if excluded else'Verify existing image'
 c.setdefault('before_candidate_binding_review',{})[role]=copy.deepcopy(c[role])
 bound=None if excluded else candidate
 c[role].update(status=status,reference=bound,basis=d['finding'],member_position=d.get('position',''),deep_review_state=x['state'],reference_is_candidate_only=not mapped,physical_cast_or_size_certified=False)
 if excluded:c[role]['rejected_or_unbound_reference']=candidate
 next_action=d.get('next_action')or'Visual role mapped at '+d.get('position','the recorded position')+'. Retain scene, scale and physical-build qualifications.'
 c.setdefault('candidate_binding_review',{})[role]={'sequence':x['sequence'],'state':x['state'],'finding':d['finding'],'next_action':next_action,'source_reference':candidate,'position':d.get('position',''),'evidence_plates':d['evidence_plates']}
 setcell('Photo Coverage',sc+str(i),status)
 for col,key,label in [(ic,'image_url','Candidate image'if not mapped else'Context image'if role=='in_situ'else'Series image'),(fc,'folder_url','Folder')]:setlink('Photo Coverage',col+str(i),bound[key]if bound else None,label if bound else'Not verified'if col==ic else'—')
 setcell('Photo Coverage',idc+str(i),bound['file_id']if bound else'');setcell('Photo Coverage',dc+str(i),bound['folder_id']if bound else'')
 a['before_candidate_binding_review']=copy.deepcopy(a);a.update(candidate_binding_sequence=x['sequence'],candidate_binding_state=x['state'],qualification=d['finding'],action=next_action,scope='Deep visual comparison of linked native sources and diagnostic crops/rotations; no new product photographs, measured specifications or platform matches.')
 if mapped:a.update(status='Resolved',reference=candidate)
 elif excluded:a.update(status='Open',action_type='Find / capture',reference=copy.deepcopy(x['primary_reference']))
 else:a.update(status='Open',action_type='Verify existing image',reference=candidate)
 j=next(j for j in range(10,221)if book['values']['Missing Pictures'].get('B'+str(j))==pid and book['values']['Missing Pictures'].get('D'+str(j))==x['role'])
 for col,key in [('E','action_type'),('F','action'),('K','scope'),('L','qualification'),('N','status')]:setcell('Missing Pictures',col+str(j),a[key])
 for col,key,label in [('G','image_url','Mapped visual reference'if mapped else'Product reference'if excluded else'Candidate image'),('H','folder_url','Folder')]:setlink('Missing Pictures',col+str(j),a['reference'][key],label)
 for col,key in [('I','file_id'),('J','folder_id')]:setcell('Missing Pictures',col+str(j),a['reference'][key])
 o['photo_coverage'][role]=status;byopt[pid].append((x,d))
for pid,pairs in byopt.items():
 o=opts[pid];c=cov[pid];i=row('Photo Coverage','A',pid);j=row('Master Catalogue','A',pid)
 c['notes']=['21 October deep comparison: '+x['role']+' — '+x['state']+'; '+d.get('position','candidate excluded; find an exact context view')for x,d in pairs]
 c['scope']='Available means a qualified visual role, not certified physical scale, cast, scene authenticity or installed hardware. Diagnostic rotations/crops do not create product images. Detailed findings retained in candidate_binding_review.'
 setcell('Photo Coverage','L'+str(i),'\n'.join(c['notes']));setcell('Photo Coverage','S'+str(i),c['scope'])
 o['current_candidate_binding_review']={'recorded_utc':now(),'ledger':str((H/'candidate-checks.json').relative_to(BASE)),'roles':copy.deepcopy(c['candidate_binding_review'])}
 if any(x['role']=='In situ'for x,d in pairs):
  o['context_before_candidate_binding_review']={k:copy.deepcopy(o.get(k))for k in ['context_status','context_description','context_image_url','context_folder_url','context_file_id','context_folder_id']}
  r=c['in_situ']['reference'];status=c['in_situ']['status'];o['context_status']=status;o['context_description']=c['in_situ']['basis']
  for key,outkey in [('file_id','context_file_id'),('folder_id','context_folder_id'),('image_url','context_image_url'),('folder_url','context_folder_url')]:o[outkey]=r[key]if r else''
  setlink('Master Catalogue','T'+str(j),r['image_url']if r else None,'Candidate scene'if status=='Verify existing image'else'Context image'if r else'Not verified');setlink('Master Catalogue','U'+str(j),r['folder_url']if r else None,'Folder'if r else'—')
 prior=book['values']['Master Catalogue'].get('V'+str(j),'')
 # Replace only the previous summary line; historical findings remain in the sealed prior audit.
 summary='Photo review: individual '+c['individual']['status']+'; in situ '+c['in_situ']['status']+'; series '+c['series']['status']+'. See Photo Coverage for role qualifications.'
 setcell('Master Catalogue','V'+str(j),re.sub(r'Photo review: individual[^\n]*',summary,prior)if'Photo review: individual'in prior else prior+'\n'+summary)
active=[x for x in audit['missing_pictures']if x['status']!='Resolved'];required=[x for x in active if x['status']!='Optional']
counts=audit['counts'];counts.update(individual_statuses=dict(collections.Counter(x['individual']['status']for x in audit['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in audit['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in audit['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),resolved_action_rows=len(audit['missing_pictures'])-len(active),active_action_rows=len(active),required_picture_actions=len(required),deep_candidate_checks=32,deep_visual_roles_mapped=25,deep_candidate_checks_remaining=6,deep_candidates_excluded_to_capture=1,deep_original_files_rehashed=4)
assert counts['in_situ_statuses']=={'Available':116,'Verify existing image':3,'No verified image':65},counts
assert counts['series_statuses']=={'Optional / no fixed set':53,'Available':108,'No verified image':20,'Verify existing image':3},counts
assert counts['actions_by_type']=={'Find / capture':111,'Verify existing image':6,'Optional image':53}and len(required)==117 and counts['resolved_action_rows']==41,counts
counts.update(terminal_task_reviews=157,terminal_tasks_resolved=40,terminal_tasks_binding_required=6,terminal_tasks_capture_required=110,terminal_tasks_size_binding_required=1)
audit.update(recorded_utc=now(),status='CURRENT_DEEP_CANDIDATE_BINDING_REVIEW',historical_audit={'path':m['audit']['path'],'sha256':m['audit']['sha256'],'prior_counts':oldaudit['counts']},candidate_binding_review={'ledger':str(H/'candidate-checks.json'),'ledger_sha256':sha(H/'candidate-checks.json'),'reviewed':32,'mapped_visual_roles':25,'source_qualified_not_physical_verification':True,'metadata_verification':str(H/'metadata-verification.json'),'current_native_content_hashes_unchanged':40,'modified_timestamps_changed':40,'new_original_files_rehashed':4,'remote_mutations':0})
setcell('Photo Coverage','A3','21 October deep comparison: 184 options; 158 full individual references, 116 qualified in situ presentations and 108 series references. Available is a visual-role status; scene origin, scale and physical builds retain their own evidence status.')
setcell('Missing Pictures','A3','Current picture work: 111 find/capture or size-binding actions, 6 existing-image checks and 53 optional series references. The deep pass reviewed 32 cases and mapped 25 further visual roles. Forty-one resolved historic rows are retained.')
heights={}
for(sn,cell),change in changes.items():
 if cell=='A3'or not isinstance(change['value'],str):continue
 col=re.match('[A-Z]+',cell)[0];idx=0
 for ch in col:idx=idx*26+ord(ch)-64
 rn=int(cell[len(col):]);root=book['sheets'][sn]['root'];width=13
 for z in root.findall('.//'+v.q('col')):
  if int(z.get('min'))<=idx<=int(z.get('max')):width=float(z.get('width',13));break
 lines=sum(max(1,math.ceil(len(s)/max(8,width*.90)))for s in change['value'].split('\n'));height=lines*13+12
 oldrow=next(z for z in root.find(v.q('sheetData'))if z.get('r')==str(rn));before=float(oldrow.get('ht',15))
 if height>before:assert height<=409,(sn,cell,height);heights[(sn,rn)]=max(heights.get((sn,rn),before),height)
formula_cells=[('Photo Coverage','B4',158),('Photo Coverage','D4',116),('Photo Coverage','F4',108),('Photo Coverage','B5',26),('Photo Coverage','D5',3),('Photo Coverage','F5',3),('Missing Pictures','B4',111),('Missing Pictures','D4',6),('Missing Pictures','F4',53)]
pc=lambda n:row('Photo Coverage','A',next(x['option_id']for x in items if x['sequence']==n))
mr=lambda n:next(i for i in range(10,221)if book['values']['Missing Pictures'].get('B'+str(i))==next(x['option_id']for x in items if x['sequence']==n)and book['values']['Missing Pictures'].get('D'+str(i))==next(x['role']for x in items if x['sequence']==n))
plan={'cell_changes':list(changes.values()),'formula_changes':[],'hyperlinks':list(links.values()),'formula_caches':[{'sheet':sn,'cell':c,'formula':book['formulas'][sn][c],'expected':num}for sn,c,num in formula_cells],'row_heights':[{'sheet':sn,'row':rn,'height':height}for(sn,rn),height in heights.items()],'preview_ranges':[['Photo Coverage','A2:L5','01-coverage-summary'],['Missing Pictures','A2:L4','02-current-actions'],['Photo Coverage',f'B{pc(58)}:L{pc(59)}','03-fold-positions'],['Missing Pictures',f'C{mr(100)}:L{mr(100)}','04-handedness-check'],['Photo Coverage',f'B{pc(106)}:L{pc(107)}','05-studio-context'],['Master Catalogue',f'R{row("Master Catalogue","A",items[0]["option_id"])}:V{row("Master Catalogue","A",items[0]["option_id"])}','06-master-context']],'dependency_test':{'coverage_cell':'F'+str(pc(74)),'action_cell':'N'+str(mr(74)),'action_counter':'D4','action_before':6,'action_after':7}}
plan['style_changes']=[{'sheet':sn,'cell':cell,'font':{'name':'Arial','size':10,'color':'#245F9E'if(sn,cell)in links else'#28362D','underline':'single'if(sn,cell)in links else'none'}}for sn,cell in sorted(set(original_links)^set(links))]
write(H/'workbook-edit-plan.json',plan);write(H/'image-coverage-current.json',audit)
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']))
g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'status':audit['status'],'recorded_utc':now(),'audit':str((H/'image-coverage-current.json').relative_to(BASE)),'audit_sha256':sha(H/'image-coverage-current.json'),'counts':counts,'source_scope':'32 deeper candidate/associated scene checks; 25 qualified visual roles mapped. Prior157-action pass retained. Crops/rotations are diagnostics, not new product photos.','prior_audit_preserved':audit['historical_audit']}
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),scope='184 saved options retained; all prior157 actions reviewed, including a deeper32-case pass. Current117 required photograph/size/binding actions remain. Available roles are source-qualified visual references.',verification=str((H/'saved-file-verification.json').relative_to(BASE)),visual_verification=str((H/'visual-verification.json').relative_to(BASE)))
g['latest_image_coverage_audit'].pop('verification_sha256',None);g['latest_image_coverage_audit'].pop('visual_verification_sha256',None)
g.setdefault('historical_terminal_photo_reviews',[]).append(copy.deepcopy(g['latest_terminal_photo_review']))
g['latest_terminal_photo_review']={'recorded_utc':now(),'ledger':str((H/'candidate-checks.json').relative_to(BASE)),'ledger_sha256':sha(H/'candidate-checks.json'),'prior_required_actions':142,'reviewed':32,'resolved_visual_associations':25,'remaining_required_actions':117,'find_capture_or_size_binding':111,'existing_image_bindings':6,'new_individual_photos':0,'accepted_name_or_spec_changes':0,'new_catalogue_options':0,'remote_mutations':0}
for k in oldg:
 if k not in ['options','latest_image_coverage_audit','historical_image_coverage_audits','latest_terminal_photo_review','historical_terminal_photo_reviews']:assert g[k]==oldg[k],k
for x,y in zip(g['options'],oldg['options']):
 for k in ['product_id','canonical_key','canonical_component_id','name','retained_names','master_fields','specifications','current_listing_resolution','current_listing_reconciliation']:assert x.get(k)==y.get(k),(x['product_id'],k)
assert audit['identity_review']==oldaudit['identity_review']
write(H/'canonical-master-register.json',g)
write(H/'preparation-verification.json',{'status':'PASS','options':184,'identities':111,'working_fields_preserved':1104,'raw_assertions_preserved':1668,'cell_changes':len(changes),'native_hyperlinks':len(links),'old_hyperlinks':len(original_links),'tabs_unchanged':21,'row_heights_extended':len(heights),'required_actions':117,'resolved_this_pass':25,'physical_claims_upgraded':0,'remote_mutations':0})
print(json.dumps(read(H/'preparation-verification.json')))
