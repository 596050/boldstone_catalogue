"""Project verified paths, numbered display names and explicit working approvals."""
import copy,hashlib,importlib.util,json,math,posixpath,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,urlunsplit
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for key,filename in [('moonphases_native','moonphases-native-readback.json'),('dune_native','dune-ripple-native-readback.json'),('deco_native','deco-native-readback.json'),('native_family_metadata','native-family-metadata.json'),('owner_photo_policy','owner-photo-policy.json')]:
 p=H/filename;t=H/'inputs'/(key+'.before');shutil.copy2(p,t);m[key]={'path':str(p),'snapshot':str(t),'sha256':sha(p)}
write(H/'input-manifest.json',m)
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
overlays=[read(m[k]['snapshot'])for k in ['moonphases_overlay','dune_overlay','deco_overlay']]
native=[read(m[k]['snapshot'])for k in ['moonphases_native','dune_native','deco_native']]
objects={};prefixes=[];nativechecks=0
for o,live in zip(overlays,native):
 assert o['verification']['status']=='PASS'and not live['has_more']
 for receipt in o['receipts']:assert sha(receipt['path'])==receipt['sha256']
 byid={x['file_id']:x for x in live['entries']};assert set(byid)=={x['file_id']for x in o['objects']}
 parents={x['current_path'].casefold():x['file_id']for x in o['objects']if x['object_type']=='folder'};parents[o['family']['path'].casefold()]=o['family']['file_id']
 for x in o['objects']:
  y=byid[x['file_id']];assert y['path']=='ns:202238505/'+x['current_path']and y['name']==x['current_name']and y['object_type']==x['object_type']
  assert parents[posixpath.dirname(x['current_path']).casefold()]==x['current_parent_id']
  if x['current_parent_id']!=x['old_parent_id']:assert x['file_id']=='id:cnqzTNngPVsAAAAAAA53Pg'and x['object_type']=='folder'
  if x['object_type']=='file':assert y['file'].get('size',0)==x['size']and x['old_name']==x['current_name']
  objects[x['file_id']]=x;nativechecks+=1
 prefixes.extend(o['prefix_maps'])
prefixes.sort(key=lambda x:len(x['old_path']),reverse=True)
assert len(objects)==1435 and len(prefixes)==35
approval=read(H/'inputs/fp_approval.before');seal=read(H/'inputs/fp_approval_seal.before')
assert seal['sha256']==m['fp_approval']['sha256']and approval['physical_verification_added']is False and approval['value_changes']==approval['count_changes']==approval['image_binding_changes']==0
policy=read(H/'owner-photo-policy.json');assert policy['owner_answer']=='No'
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a)
names={x['product_id']:x['current_name']for x in overlays[1]['option_name_projection']}
cnames={x['component_id']:x['current_name']for x in overlays[1]['component_numbering']}
name_map={x['name']:names[x['product_id']]for x in g['options']if x['product_id']in names}
name_map.update({x['name']:cnames[x['component_id']]for x in g['components']if x['component_id']in cnames})
def path(s):
 for x in prefixes:
  if s==x['old_path']or s.startswith(x['old_path']+'/'):return x['current_path']+s[len(x['old_path']):]
 return s
def ref(s):
 if not isinstance(s,str):return s
 if s.startswith('ns:202238505//'):return'ns:202238505/'+path('/'+s.split('//',1)[1])
 if s.startswith('/BOLDSTONE MASTER/'):return path(s)
 if not s.startswith('https://www.dropbox.com/'):return s
 p=urlsplit(s);d=unquote(p.path)
 for route in ['/home','/preview']:
  if d.startswith(route+'/'):
   new=path(d[len(route):])
   if new!=d[len(route):]:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return s
def project(x):
 for k in ['image_url','folder_url','context_image_url','context_folder_url','path','ns_path','url']:
  if k in x:x[k]=ref(x[k])
 obj=objects.get(x.get('file_id'))
 if obj:
  if 'name'in x and x['name']==obj['old_name']:x['name']=obj['current_name']
  if x.get('folder_id'):assert x['folder_id']==obj['current_parent_id']
def rebase(x):
 if isinstance(x,list):return[rebase(v)for v in x]
 if isinstance(x,dict):
  z={k:copy.deepcopy(v)if k.startswith(('prior_','historical_'))or'_before_'in k or k in ['source_ref','evidence_ref','master_ref','frozen_master']else rebase(v)for k,v in x.items()}
  project(z);return z
 return ref(x)
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
 for x in g[layer]:project(x)
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:project(x.get('current_primary_reference',{}))
for x in g['arrangement_context_references']:
 project(x)
 for im in x.get('images',[]):project(im)
for x in g['options']:
 for k in ['current_candidate_binding_review','current_photo_task_review','current_photo_gap_review']:
  if k in x:x[k]=rebase(x[k])
 if x['product_id']in names:
  before=x['name'];x['name']=names[x['product_id']];x['retained_names']=list(dict.fromkeys(x['retained_names']+[before,x['name']]))
  x['current_numbered_identity']={'owner_instruction':overlays[1]['owner_authorization'],'overlay':m['dune_overlay'],'number':1 if x['canonical_component_id']=='BC-DR-WAVE1'else 2,'physical_design_or_specification_change':False}
  for k in ['current_listing_reconciliation','current_listing_resolution']:
   if k in x:x[k]['name']=x['name']
for x in g['components']:
 if x['component_id']in cnames:
  before=x['name'];x['name']=cnames[x['component_id']];x['option_names']=[names[z]for z in x['option_ids']]
  x['retained_names']=list(dict.fromkeys(x['retained_names']+[before,x['name']]+x['option_names']))
def labels(x):
 if isinstance(x,list):
  for y in x:labels(y)
 elif isinstance(x,dict):
  for k,v in x.items():
   if k in ['name','display_name','title','option_name','component_name']and isinstance(v,str)and v in name_map:x[k]=name_map[v]
   elif not k.startswith(('prior_','historical_'))and k not in ['source_ref','evidence_ref','master_ref','frozen_master']:labels(v)
for layer in ['source_media_configuration_coverage','source_platform_offer_coverage','current_listing_issues','current_listing_resolution','current_listing_resolution_details']:labels(g[layer])

# The acceptance changes provenance and review state, never the approved value.
apref={'decision_id':approval['decision_id'],'path':m['fp_approval']['path'],'sha256':m['fp_approval']['sha256'],'source_thread_id':approval['source_thread_id'],'physical_verification_added':False,'labels_preserved':True}
fpids={x['product_id']for x in approval['options']};byoption={x['product_id']:x for x in g['options']}
for p in approval['options']:
 x=byoption[p['product_id']];assert x['canonical_component_id']==p['component_id']
 x['explicit_owner_working_specification_confirmation']=copy.deepcopy(apref)
 for field,display in p['current_displays_approved_as_working'].items():
  f=x['master_fields'][field];s=x['specifications'][field];assert f['display']==s['display']==display and not f['physical_verification']and not s['physical_verification']
  f['historical_working_acceptance_state']=f['state'];f['state']=s['state']+'\nExplicit owner confirmation of labelled working specification,22 October2026; proposals, estimates, guesses and unknowns retained.'
  f['explicit_owner_confirmation']=copy.deepcopy(apref);f['source_references'].append({'owner_confirmation':copy.deepcopy(apref)})
  s['historical_acceptance_basis']=s['acceptance_basis'];s['acceptance_basis']='Explicit owner confirmation of the labelled working specification table on22 October2026; '+approval['decision_id'];s['explicit_owner_confirmation']=copy.deepcopy(apref)
for x in g['current_listing_resolution_details']['entries']:
 if x['product_id']in fpids:x['accepted_working_fields']=copy.deepcopy(byoption[x['product_id']]['master_fields']);x['explicit_owner_working_specification_confirmation']=copy.deepcopy(apref)
g['latest_fingerprint_working_specification_confirmation']={'status':approval['status'],'recorded_utc':now(),**apref,'current_option_ids':sorted(fpids),'field_groups':36,'display_changes':0,'exact_owner_table':approval['approved_rows']}
g['latest_fingerprint_product_finalization']['latest_explicit_working_confirmation']=copy.deepcopy(apref)

reviews=rebase(read(H/'inputs/report_reviews.before'));cropids={x['option_id']for x in reviews if x['role']=='Individual'and x['review_state']=='EXACT_CROP_CANDIDATE_PENDING_OWNER_CRITERION'};assert len(cropids)==13
capture='Take a separate full photograph of this exact individual component and finish, with the whole sculpture visible. Retain the group/detail original as context; do not create a crop or a reconstructed image.'
for x in reviews:
 if x['option_id']in names:x['name']=names[x['option_id']]
 if x['option_id']in cropids and x['role']=='Individual':
  x['historical_crop_review']={k:copy.deepcopy(x[k])for k in ['review_state','finding','next_action']if k in x}
  x.update(review_state='SEPARATE_PHOTOGRAPH_REQUIRED_OWNER_DECLINED_CROPS',finding='The owner declines exact-pixel crops. The existing group/detail image remains a comparison reference; the individual-image gap stays open.',next_action=capture,owner_photo_criterion=copy.deepcopy(policy))
for x in a['coverage']:
 if x['option_id']in names:x['name']=names[x['option_id']]
 for role in ['individual','in_situ','series']:
  if x[role].get('reference'):project(x[role]['reference'])
 if x['option_id']in cropids:
  x['individual']['historical_crop_assessment']=copy.deepcopy(x['individual'])
  x['individual'].update(owner_capture_criterion='Separate individual photograph required; owner declined exact crops.',cropped_image_accepted=False)
for layer in ['missing_pictures','identity_review']:
 for x in a[layer]:
  if x.get('option_id')in names:x['name']=names[x['option_id']]
  for k in ['reference','comparison']:
   if x.get(k):project(x[k])
  if layer=='missing_pictures'and x['option_id']in cropids and x['role']=='Individual':
   x['historical_crop_action']={k:copy.deepcopy(x[k])for k in ['action','scope','qualification']}
   x.update(action=capture,scope='Owner requires a separate individual photograph. Existing group/detail references remain context only.',qualification='Exact crops declined by owner; no new individual image created or gap closed.',owner_response='No — keep open until separate individual photographs are taken.')
for oid in cropids:byoption[oid]['current_owner_individual_photo_criterion']=copy.deepcopy(policy)
scope={'status':'CURRENT_FOLDERS_AND_DUNE_NUMBERING_VERIFIED','recorded_utc':now(),'overlays':[m['moonphases_overlay'],m['dune_overlay'],m['deco_overlay']],
 'folder_renames':35,'moonphases_folder_renames':10,'dune_ripple_folder_renames':22,'deco_palm_spiral_folder_renames':3,'stable_objects_verified':1435,
 'file_IDs_and_sizes_preserved':1370,'file_parent_IDs_unchanged':True,'approved_custom_folder_parent_change':'id:cnqzTNngPVsAAAAAAA53Pg','dune_component_numbering':copy.deepcopy(overlays[1]['component_numbering']),
 'current_option_display_names_changed':13,'new_components_or_options':0,'specification_display_changes':0,'image_role_changes':0,'root_Dropbox_or_platform_writes':0}
g['latest_moonphases_dune_ripple_refresh']=scope;g['current_individual_photo_capture_policy']=copy.deepcopy(policy)
a['recorded_utc']=now();a['latest_moonphases_dune_ripple_refresh']=copy.deepcopy(scope);a['current_individual_photo_capture_policy']=copy.deepcopy(policy)
a['individual_capture_queue_counts']={'individual_gaps':22,'separate_photographs_required':21,'legacy_identity_deferred':1,'approved_crop_actions':0,'historical_crop_candidates_declined':13}
write(H/'image-coverage-current.json',a)
g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']))
g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=rel(H/'image-coverage-current.json'),audit_sha256=sha(H/'image-coverage-current.json'),verification=rel(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),scope='Current186 options:22 individual gaps requiring21 separate photographs and1 deferred identity;61in situ and18series gaps. Owner declines crops; verified Moonphases/Dune/Deco folder changes and Dune1Waves/2Spiral labels do not change photograph roles.')
for k in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g);write(H/'photo-review-queue.json',reviews);write(H/'current-assets.json',rebase(read(H/'inputs/report_assets.before')))
write(H/'independent-native-verification.json',{'status':'PASS','objects_verified':nativechecks,'stable_file_IDs':1370,'folder_renames':35,'file_sizes_and_file_parent_IDs_unchanged':True,'approved_folder_parent_changes':1,'root_native_writes':0})
assert g['summary']==old['summary']and a['counts']==olda['counts']and g['original_review_specification_assertions']==old['original_review_specification_assertions']
for x,y in zip(g['options'],old['options']):
 assert x['product_id']==y['product_id']and x['canonical_component_id']==y['canonical_component_id']and x['photo_coverage']==y['photo_coverage']
 for field in x['master_fields']:assert x['master_fields'][field]['display']==y['master_fields'][field]['display']and x['master_fields'][field]['physical_verification']==y['master_fields'][field]['physical_verification']

s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');changes={};links={};heights={}
def setcell(sn,c,value):
 before=b['values'][sn].get(c,'');assert c not in b['formulas'][sn]
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  c=h.get('ref');url='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');hist=sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)
  links[(sn,c)]={'sheet':sn,'cell':c,'target':url if hist else ref(url),'label':b['values'][sn].get(c,'')}
 for c,value in b['values'][sn].items():
  if sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c):continue
  new=ref(value)
  if new!=value:setcell(sn,c,new)
for sn,col in [('Master Catalogue','B'),('Specifications','B'),('Photo Coverage','B'),('Missing Pictures','C'),('Listing Reconciliation','B'),('Listing Issues','B'),('Listing Resolution','B'),('Draft Listings','B')]:
 for c,value in b['values'][sn].items():
  if re.fullmatch(col+r'\d+',c)and value in name_map:setcell(sn,c,name_map[value])
for cid,name in cnames.items():
 rn=next(re.search(r'\d+',c)[0]for c,v in b['values']['Components'].items()if re.fullmatch(r'A\d+',c)and v==cid);comp=next(x for x in g['components']if x['component_id']==cid)
 setcell('Components','B'+rn,name);setcell('Components','K'+rn,'\n'.join(comp['retained_names']))
for sn,col in [('Sets and Context','D'),('Source Mapping','E'),('Listing Offer Links','P')]:
 for c,value in b['values'][sn].items():
  if not re.fullmatch(col+r'\d+',c)or not isinstance(value,str):continue
  new=value
  for before,after in sorted(name_map.items(),key=lambda x:len(x[0]),reverse=True):new=new.replace(before+' [',after+' [')
  if new!=value:setcell(sn,c,new)
for c,oid in b['values']['Specifications'].items():
 if re.fullmatch(r'A\d+',c)and oid in fpids:
  rn=re.search(r'\d+',c)[0];field=b['values']['Specifications']['C'+rn];setcell('Specifications','E'+rn,byoption[oid]['master_fields'][field]['state'])
for c,oid in b['values']['Missing Pictures'].items():
 if re.fullmatch(r'B\d+',c)and oid in cropids:
  rn=re.search(r'\d+',c)[0]
  if b['values']['Missing Pictures']['D'+rn]!='Individual':continue
  task=next(x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='Individual')
  for col,key in [('F','action'),('K','scope'),('L','qualification'),('M','owner_response')]:setcell('Missing Pictures',col+rn,task[key])
setcell('Photo Coverage','A3','186 current options. Owner declines crops for13 group/detail candidates:22 individual gaps remain (21 separate photographs plus1 deferred identity),61in situ and18series gaps. Current folder links include Moonphases,Dune Ripple1Waves/2Spiral and approved Deco Palm/Spiral changes.')
for k,x in links.items():
 if k in changes:x['label']=changes[k]['value']
for(sn,c),x in changes.items():
 if not isinstance(x['value'],str)or c=='A3':continue
 col=re.match('[A-Z]+',c)[0];ci=0
 for ch in col:ci=ci*26+ord(ch)-64
 rn=int(c[len(col):]);root=b['sheets'][sn]['root'];width=next((float(z.get('width'))for z in root.findall('.//'+n.q('col'))if int(z.get('min'))<=ci<=int(z.get('max'))),13)
 height=sum(max(1,math.ceil(len(t)/max(8,width*.9)))for t in x['value'].split('\n'))*13+12
 previous=float(next(z for z in root.find(n.q('sheetData'))if z.get('r')==str(rn)).get('ht',15))
 if height>previous:assert height<=409;heights[(sn,rn)]=max(heights.get((sn,rn),previous),height)
L=lambda label,target:{'label':label,'target':target};rows=[]
for o in overlays:
 for p in o['prefix_maps']:
  children=[x for x in o['objects']if x['object_type']=='file'and x['current_parent_id']==p['file_id']and re.search(r'\.(jpe?g|png|webp)$',x['current_name'],re.I)]
  im=children[0]if children else None
  rows.append([Path(o['family']['path']).name,p['file_id'],p['old_name'],p['current_name'],L('Current folder',p['current_native_url']),L('Existing example photograph',im['current_native_url'])if im else'',im['file_id']if im else'',p['file_id'],p['old_path'],p['current_path'],p['direct_file_count'],p.get('kind','arrangement/context'),'Folder IDs and file basenames retained','No specification or image-role change'])
sheet={'title':'Moonphases,Dune Ripple and Deco current folder references','note':'35 owner-approved folder renames verified by stable IDs. Dune Ripple1=Waves;2=Spiral.186 options/112 working component identities retained.','headers':['Family','Folder ID','Earlier folder name','Current folder name','Current folder','Example photograph','Example file ID','Photo parent folder ID','Earlier path','Current path','Direct files','Folder kind','Identity guard','Specification and image scope'],'widths':[25,35,67,71,28,29,35,35,105,105,15,25,55,58],'rows':rows}
write(H/'workbook-data.json',{'sheets':{'Moonphases and Dune':sheet}})
oldtargets={k:x['target']for k,x in links.items()}
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  k=(sn,h.get('ref'));oldtargets[k]='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target')
# Batch consecutive writes within a column; every cell is declared and no owning
# formula is overwritten by an enclosing rectangle.
blocks=[];groups={}
for (sn,c),x in changes.items():groups.setdefault((sn,re.match('[A-Z]+',c)[0]),[]).append(x)
for (sn,col),items in groups.items():
 items.sort(key=lambda x:int(x['cell'][len(col):]));run=[]
 for x in items:
  if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:
   blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[q['value']]for q in run]});run=[]
  run.append(x)
 if run:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[q['value']]for q in run]})
plan={'cell_changes':list(changes.values()),'value_blocks':blocks,'hyperlinks':list(links.values()),'target_changes':[{'sheet':sn,'cell':c,'before':oldtargets[(sn,c)],'after':x['target']}for(sn,c),x in links.items()if x['target']!=oldtargets[(sn,c)]],
 'row_heights':[{'sheet':sn,'row':rn,'height':v}for(sn,rn),v in heights.items()],'old_sheet_count':26,'new_sheet_count':1,'new_native_links':sum(isinstance(v,dict)for row in rows for v in row)+1,
 'baseline_ranges':[['Master Catalogue','A57:D60','baseline-dune-labels'],['Specifications','A454:F455','baseline-fp-acceptance']],
 'preview_ranges':[['Master Catalogue','A57:D60','01-current-dune-labels'],['Components','A34:D35','02-current-dune-components'],['Specifications','A454:F455','03-owner-confirmed-working-state'],['Moonphases and Dune','A2:H4','04-verified-folder-counts'],['Moonphases and Dune','A9:F11','05-current-folder-links'],['Missing Pictures','B14:F16','06-separate-photograph-criterion'],['Photo Coverage','A2:H5','07-current-gaps']]}
write(H/'workbook-edit-plan.json',plan)
def diff(x,y,p=[]):
 if x==y:return[]
 if isinstance(x,dict)and isinstance(y,dict):
  z=[]
  for k in sorted(set(x)|set(y)):
   if k not in x:z.append({'path':p+[k],'kind':'added','after':y[k]})
   elif k not in y:z.append({'path':p+[k],'kind':'removed','before':x[k]})
   else:z+=diff(x[k],y[k],p+[k])
  return z
 if isinstance(x,list)and isinstance(y,list)and len(x)==len(y):return[z for i,(v,w)in enumerate(zip(x,y))for z in diff(v,w,p+[i])]
 return[{'path':p,'kind':'changed','before':x,'after':y}]
write(H/'register-change-log.json',diff(old,g));write(H/'audit-change-log.json',diff(olda,a))
write(H/'preparation-verification.json',{'status':'PASS','native_objects_verified':1435,'file_IDs_and_sizes_preserved':1370,'folder_renames':35,'dune_option_names_updated':13,'dune_component_names_updated':2,'specification_display_changes':0,'explicit_FP_working_approvals':36,'physical_verification_added':0,'new_options':0,'individual_gaps':22,'separate_photos_required':21,'crop_actions_approved':0,'changed_cells':len(changes),'changed_link_targets':len(plan['target_changes']),'new_native_links':plan['new_native_links'],'value_blocks':len(blocks)})
print(json.dumps(read(H/'preparation-verification.json')))
