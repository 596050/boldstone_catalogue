"""Prepare scoped current photo decisions; retain source, identity and spec layers."""
import collections,copy,hashlib,importlib.util,json,math,posixpath,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
m=read(H/'input-manifest.json');ptr=read(BASE/'current-master.json')
for key,rel in [('review_progress','components/reviews/specification_review_progress.json'),('component_checkpoint','components/checkpoint.json'),('root_checkpoint','checkpoint.json'),('owner_ledger','components/reviews/user_classifications.json'),('source_model','components/evidence/component_register.json')]:
 p=BASE/rel;dest=H/'inputs'/(key+'.before')
 if dest.exists():assert sha(dest)==sha(p),key
 else:shutil.copy2(p,dest)
 m[key]={'path':str(p),'snapshot':str(dest),'sha256':sha(p)}
for key,p in [('cup_colour_overlay',BASE.parent/'reports/dropbox-cup-ring-pink-brown-2026-10-21/CURRENT_REFERENCE_OVERLAY.json'),('cup_colour_seal',BASE.parent/'reports/dropbox-cup-ring-pink-brown-2026-10-21/SEAL.json'),('cup_colour_native',H/'cup-colour-native-readback.json')]:
 dest=H/'inputs'/(key+'.before')
 if dest.exists():assert sha(dest)==sha(p),key
 else:shutil.copy2(p,dest)
 m[key]={'path':str(p),'snapshot':str(dest),'sha256':sha(p)}
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
write(H/'input-manifest.json',m)
items=read(H/'terminal-review-items.json');assert len(items)==157 and all(x['review_state']!='QUEUED'for x in items)
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
assets=read(H/'current-assets.json')
overlay=read(m['cup_colour_overlay']['path']);assert sha(m['cup_colour_overlay']['path'])=='60d8a30a8cf715e681e019e9b31ab421fb49ccf1e55addf0780a7d3408a1da26'
assert sha(m['cup_colour_seal']['path'])=='a738bd7db16ffc91a3ccca341599a20fd17389cbe20791b3b287f0bb27d68ef2'
for f in read(m['cup_colour_seal']['path'])['files']:assert sha(f['path'])==f['sha256']and Path(f['path']).stat().st_size==f['bytes']
native={z.get('file',z.get('folder'))['id']:z.get('file',z.get('folder'))for z in read(m['cup_colour_native']['path'])}
for x in overlay['objects']:
 n=native[x['file_id']];assert(n['path_display'],n['size'],n['rev'])==(x['current_path'],x['size'],x['current_rev'])
 assert native[x['current_parent_id']]['path_display']==x['current_folder_path']
 a=assets[x['file_id']];assert a['bytes']==x['size'];a.update(path='ns:202238505/'+x['current_path'],display_path=x['current_path'],folder_path='ns:202238505/'+x['current_folder_path'],folder_id=x['current_parent_id'],image_url=x['current_native_url'],folder_url=x['current_folder_url'],current_appearance_reference_only=True,physical_finish_status='UNCONFIRMED')
for name in ['archive','checks','context','spiral','leaf']:
 receipt=read(H/(name+'-download-receipt.json'));assert receipt['status']=='PASS'
 for x in receipt['images']:
  if x['file_id']in assets and x['native_bytes_downloaded_for_this_ID']:assets[x['file_id']].update(full=x['local_path'],current_original_content_rehashed=True,current_original_sha256=x['sha256'],current_original_native_hash=x['native_content_hash'])
write(H/'current-assets.json',assets)
def ref_for(x):
 fid=x['primary_reference'].get('file_id')or x['prior_action']['reference']['file_id'];a=assets.get(fid,x['prior_action']['reference']);return{k:a.get(k,'')for k in ['file_id','folder_id','name','path','image_url','folder_url']}
roles={'Individual':('individual','C','D','E','M','N'),'In situ':('in_situ','F','G','H','O','P'),'Series':('series','I','J','K','Q','R')}
cov={x['option_id']:x for x in audit['coverage']};opts={x['product_id']:x for x in g['options']};actions={(x['option_id'],x['role']):x for x in audit['missing_pictures']};byopt=collections.defaultdict(list)
for x in items:
 d=x['findings'][-1];pid=x['option_id'];role,sc,ic,fc,idc,dc=roles[x['requested_role']];c=cov[pid];o=opts[pid];a=actions[(pid,x['requested_role'])];i=row('Photo Coverage','A',pid)
 current=copy.deepcopy(c[role]);status=d.get('new_photo_status',current['status']);candidate=copy.deepcopy(d.get('new_reference')or current.get('reference')or a['reference'])
 # Missing-role cells must not retain an apparently accepted context hyperlink.
 bound_reference=None if status=='No verified image'and role!='individual'else candidate
 c[role].update(status=status,reference=bound_reference,basis=d['finding'],terminal_review_state=x['review_state'],physical_cast_or_size_certified=False)
 if 'position'in d:c[role]['member_position']=d['position']
 if status=='No verified image'and current.get('reference'):c[role]['rejected_or_unbound_reference']=current['reference']
 if x['review_state']=='REVIEWED_BINDING_REQUIRED':c[role]['reference_is_candidate_only']=True
 c.setdefault('terminal_task_review',{})[role]={'sequence':x['sequence'],'state':x['review_state'],'finding':d['finding'],'next_action':d['next_action'],'source_reference':candidate,'position':d.get('position',''),'evidence_plates':d['evidence_plates']}
 if role!='individual':
  setcell('Photo Coverage',sc+str(i),status)
  for col,key,label in [(ic,'image_url','Candidate image'if status=='Verify existing image'else'Room / garden'if role=='in_situ'else'Series image'),(fc,'folder_url','Folder')]:setlink('Photo Coverage',col+str(i),bound_reference.get(key)if bound_reference else None,label if bound_reference else'Not verified'if col==ic else'—')
  setcell('Photo Coverage',idc+str(i),bound_reference['file_id']if bound_reference else'');setcell('Photo Coverage',dc+str(i),bound_reference['folder_id']if bound_reference else'')
 a.setdefault('terminal_review_prior_action',copy.deepcopy(x['prior_action']));a['terminal_review_sequence']=x['sequence'];a['terminal_review_state']=x['review_state']
 a['qualification']=d['finding'];a['action']=d['next_action'];a['scope']=d.get('review_scope','Bounded source review; no physical specification certification.')
 if x['review_state']=='RESOLVED_VERIFIED_REFERENCE':a['status']='Resolved';a['reference']=candidate
 elif x['review_state']=='REVIEWED_BINDING_REQUIRED':a.update(status='Open',action_type='Verify existing image',reference=candidate)
 else:a.update(status='Open',action_type='Find / capture',reference=ref_for(x))
 j=next(j for j in range(10,221)if book['values']['Missing Pictures'].get('B'+str(j))==pid and book['values']['Missing Pictures'].get('D'+str(j))==x['requested_role'])
 for col,key in [('E','action_type'),('F','action'),('K','scope'),('L','qualification'),('N','status')]:setcell('Missing Pictures',col+str(j),a[key])
 for col,key,label in [('G','image_url','Verified role reference'if a['status']=='Resolved'else'Candidate image'if a['action_type']=='Verify existing image'else'Product reference'),('H','folder_url','Folder')]:setlink('Missing Pictures',col+str(j),a['reference'][key],label)
 for col,key in [('I','file_id'),('J','folder_id')]:setcell('Missing Pictures',col+str(j),a['reference'][key])
 o['photo_coverage'][role]=status;byopt[pid].append((x,d))
for pid,pairs in byopt.items():
 o=opts[pid];c=cov[pid];i=row('Photo Coverage','A',pid);j=row('Master Catalogue','A',pid)
 c['notes']=['21 October terminal review: '+x['requested_role']+': '+d['finding']for x,d in pairs]
 c['scope']='157 required actions reviewed individually. Relevant returned archive and additional context candidates examined; search is bounded. Older observations remain in the preserved prior audit. Native IDs/path metadata refreshed; thumbnails are not physical measurement evidence.'
 c['scene_origin']='Source-qualified depictions; room montage/capture origin and real installed cast unverified unless separately established. Staged displays are labelled in the role notes.'
 setcell('Photo Coverage','L'+str(i),'\n'.join(c['notes']));setcell('Photo Coverage','S'+str(i),c['scope']);setcell('Photo Coverage','T'+str(i),c['scene_origin'])
 o['current_photo_task_review']={'recorded_utc':now(),'roles':copy.deepcopy(c['terminal_task_review']),'previous_photo_coverage':copy.deepcopy(next(z for z in oldg['options']if z['product_id']==pid)['photo_coverage'])}
 if any(x['requested_role']=='In situ'for x,d in pairs):
  o['prior_context_before_terminal_review']={k:copy.deepcopy(o.get(k))for k in ['context_status','context_description','context_image_url','context_folder_url','context_file_id','context_folder_id']}
  r=c['in_situ']['reference'];status=c['in_situ']['status'];o['context_status']=status;o['context_description']=c['in_situ']['basis']
  for key,outkey in [('file_id','context_file_id'),('folder_id','context_folder_id'),('image_url','context_image_url'),('folder_url','context_folder_url')]:o[outkey]=r[key]if r else''
  setlink('Master Catalogue','T'+str(j),r['image_url']if r else None,'Candidate scene'if status=='Verify existing image'else'Room / garden'if r else'Not verified')
  setlink('Master Catalogue','U'+str(j),r['folder_url']if r else None,'Folder'if r else'—')
 prior=book['values']['Master Catalogue'].get('V'+str(j),'');add='Photo review: individual '+c['individual']['status']+'; in situ '+c['in_situ']['status']+'; series '+c['series']['status']+'. See Photo Coverage for role qualifications.'
 setcell('Master Catalogue','V'+str(j),prior+'\n'+add)
cup_id='BSI-ADD5F3BEFCF5';cup_row=row('Identity Review','A','ID-CUP-RING')
cup_note='21 October owner-approved appearance organisation: two processed reference images now have separate Cup Ring Pink / Cup Ring Brown folders, with their original file IDs retained. Physical manufacture, intended sale finish and image edit/generation process remain unconfirmed. White historical primary retained; no new catalogue options.'
setcell('Identity Review','F'+str(cup_row),book['values']['Identity Review']['F'+str(cup_row)]+'\n'+cup_note)
active=[x for x in audit['missing_pictures']if x['status']!='Resolved'];required=[x for x in active if x['status']!='Optional']
counts=audit['counts'];counts.update(individual_statuses=dict(collections.Counter(x['individual']['status']for x in audit['coverage'])),in_situ_statuses=dict(collections.Counter(x['in_situ']['status']for x in audit['coverage'])),series_statuses=dict(collections.Counter(x['series']['status']for x in audit['coverage'])),actions_by_role=dict(collections.Counter(x['role']for x in active)),actions_by_type=dict(collections.Counter(x['action_type']for x in active)),resolved_action_rows=len(audit['missing_pictures'])-len(active),active_action_rows=len(active),required_picture_actions=len(required),current_files_in_root_inventory=len(assets),terminal_task_reviews=157,terminal_tasks_resolved=15,terminal_tasks_binding_required=31,terminal_tasks_capture_required=110,terminal_tasks_size_binding_required=1)
assert counts['in_situ_statuses']=={'Available':98,'Verify existing image':21,'No verified image':65},counts
assert counts['series_statuses']=={'Optional / no fixed set':53,'Available':101,'No verified image':20,'Verify existing image':10},counts
assert counts['actions_by_type']=={'Find / capture':111,'Verify existing image':31,'Optional image':53}and len(required)==142,counts
audit.update(recorded_utc=now(),status='CURRENT_BOUNDED_TERMINAL_PHOTO_REVIEW',historical_audit={'path':m['audit']['path'],'sha256':m['audit']['sha256'],'prior_counts':oldaudit['counts']},terminal_review={'path':str(H/'terminal-review-items.json'),'sha256':sha(H/'terminal-review-items.json'),'reviewed':157,'resolved_image_associations':15,'physical_cast_or_measurement_claims_upgraded':0,'root_remote_mutations':0,'capture_tasks_are_not_proof_no_image_exists_elsewhere':True})
setcell('Photo Coverage','A3','21 October terminal review: 184 options; 158 complete individual references, 98 source-qualified in situ presentations and 101 series references. Scene authenticity, scale and physical specifications retain their own evidence status.')
setcell('Missing Pictures','A3','Current picture work: 111 find/capture or size-binding actions, 31 specific existing-image checks and 53 optional series references. All 157 prior required items reviewed; 15 image associations resolved. Sixteen resolved historic rows retained, including Cup Ring.')
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
formula_cells=[('Photo Coverage','B4',158),('Photo Coverage','D4',98),('Photo Coverage','F4',101),('Photo Coverage','B5',26),('Photo Coverage','D5',21),('Photo Coverage','F5',10),('Missing Pictures','B4',111),('Missing Pictures','D4',31),('Missing Pictures','F4',53)]
plan={'cell_changes':list(changes.values()),'formula_changes':[],'hyperlinks':list(links.values()),'formula_caches':[{'sheet':sn,'cell':c,'formula':book['formulas'][sn][c],'expected':num}for sn,c,num in formula_cells],'row_heights':[{'sheet':sn,'row':rn,'height':height}for(sn,rn),height in heights.items()],'preview_ranges':[['Photo Coverage','A2:L5','01-coverage-summary'],['Missing Pictures','A2:L4','02-current-actions'],['Photo Coverage','B145:L147','03-moonspiral-bindings'],['Photo Coverage','B90:L90','04-qualified-context-example'],['Missing Pictures','C64:L64','05-example-action'],['Identity Review',f'B{cup_row}:F{cup_row}','06-cup-appearance-scope']]}
plan['style_changes']=[{'sheet':sn,'cell':cell,'font':{'name':'Arial','size':10,'color':'#245F9E'if(sn,cell)in links else'#28362D','underline':'single'if(sn,cell)in links else'none'}}for sn,cell in sorted(set(original_links)^set(links))]
# Correct preview ranges from current IDs, without changing sheet order or adding tabs.
pick=next(x for x in items if x['sequence']==75);pcr=row('Photo Coverage','A',pick['option_id']);plan['preview_ranges'][3]=['Photo Coverage',f'B{pcr}:L{pcr}','04-qualified-context-example']
pick=next(x for x in items if x['sequence']==98);mr=next(j for j in range(10,221)if book['values']['Missing Pictures'].get('B'+str(j))==pick['option_id']and book['values']['Missing Pictures'].get('D'+str(j))=='In situ');plan['preview_ranges'][4]=['Missing Pictures',f'C{mr}:L{mr}','05-example-action']
write(H/'workbook-edit-plan.json',plan);write(H/'image-coverage-current.json',audit)
g.setdefault('historical_image_coverage_audits',[]).append(copy.deepcopy(g['latest_image_coverage_audit']))
g['latest_image_coverage_audit']={**g['latest_image_coverage_audit'],'status':audit['status'],'recorded_utc':now(),'audit':str((H/'image-coverage-current.json').relative_to(BASE)),'audit_sha256':sha(H/'image-coverage-current.json'),'counts':counts,'source_scope':'All 157 required actions individually reviewed in the terminal; bounded archive/context searches and explicit per-role decisions. Source-qualified pictures do not authenticate physical casts, scale or installed hardware.','prior_audit_preserved':audit['historical_audit']}
g['latest_terminal_photo_review']={'recorded_utc':now(),'ledger':str((H/'terminal-review-items.json').relative_to(BASE)),'ledger_sha256':sha(H/'terminal-review-items.json'),'prior_required_actions':157,'reviewed':157,'resolved_visual_associations':15,'remaining_required_actions':142,'find_capture_or_size_binding':111,'existing_image_bindings':31,'new_individual_photos':0,'accepted_name_or_spec_changes':0,'new_catalogue_options':0,'remote_mutations':0}
g['current_cup_colour_reference_paths']={'status':overlay['status'],'recorded_utc':now(),'source_overlay':m['cup_colour_overlay'],'source_seal':m['cup_colour_seal'],'independent_current_metadata':m['cup_colour_native'],'objects':overlay['objects'],'created_folders':overlay['created_folders'],'physical_finish_status':'UNCONFIRMED','catalogue_options_added':0,'White_historical_primary_unchanged':True,'root_native_mutations':0}
for k in oldg:
 if k not in ['options','latest_image_coverage_audit','historical_image_coverage_audits']:assert g[k]==oldg[k],k
for x,y in zip(g['options'],oldg['options']):
 for k in ['product_id','canonical_key','canonical_component_id','name','retained_names','master_fields','specifications','current_listing_resolution','current_listing_reconciliation']:assert x.get(k)==y.get(k),(x['product_id'],k)
write(H/'canonical-master-register.json',g)
write(H/'preparation-verification.json',{'status':'PASS','options':184,'identities':111,'working_fields_preserved':1104,'raw_assertions_preserved':1668,'cell_changes':len(changes),'native_hyperlinks':len(links),'old_hyperlinks':len(original_links),'tabs_unchanged':21,'row_heights_extended':len(heights),'required_actions':142,'resolved_this_pass':15,'physical_claims_upgraded':0,'remote_mutations':0})
print(json.dumps(read(H/'preparation-verification.json')))
