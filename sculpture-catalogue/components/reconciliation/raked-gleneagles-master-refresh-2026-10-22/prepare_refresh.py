"""Refresh accepted names and current native references, preserving source facts."""
import collections, copy, hashlib, importlib.util, json, math, posixpath, re, shutil
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from xml.etree import ElementTree as E

H=Path(__file__).resolve().parent; BASE=H.parents[2]; ROOT=BASE.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
addendum=ROOT/'reports/dropbox-gleneagles-component-review-2026-10-22/execution/current-state-addendum.json'
for key,p in [('glen_state_addendum',addendum),('native_image_verification',H/'native-image-verification.json')]:
 if key not in m:
  snap=H/'inputs'/(key+'.before');shutil.copy2(p,snap);m[key]={'path':str(p),'snapshot':str(snap),'sha256':sha(p)}
write(H/'input-manifest.json',m)
for x in m.values():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],x['path']
r=read(H/'inputs/raked_overlay.before');d=read(H/'inputs/glen_overlay.before');state=read(addendum)
assert sha(H/'inputs/raked_overlay.before')=='a2b1bd38df951ef88136bebc9d7b65bbe7febd18a94d6fd248909bf92869574e'
assert sha(H/'inputs/glen_overlay.before')=='63c6620632a3b93b69a2647b123dae0d6f82fb9fe2c63afaaf5616437edbf6e3'
assert d['owner_decision']['owner_response']=='do it' and d['owner_decision']['approved_specification_value_changes']==0
live=read(H/'independent-native-readbacks.json');glen_live=read(H/'gleneagles-current-native-readback.json')['listing']
proof=[]
for label,overlay,listing in [('Raked Spiral',r,live['raked']['listing']),('Gleneagles',d,glen_live)]:
 assert not listing['has_more']; byid={x['file_id']:x for x in listing['entries']}
 for x in overlay['objects']:
  y=byid[x['file_id']]
  assert y['name']==x['current_name'] and y['path']=='ns:202238505/'+x['current_path'] and y['object_type']==x['object_type'],x['file_id']
  if x['object_type']=='file':assert y['file']['size']==x['size']
 for x in overlay.get('created_folders',[]):assert byid[x['file_id']]['path']=='ns:202238505/'+x['path']
 proof.append({'family':label,'original_objects_preserved':len(overlay['objects']),'complete_native_descendants':len(listing['entries'])})
glen_byid={x['file_id']:x for x in glen_live['entries']}
old_docs={x['file_id'] for x in d['created_reference_documents']}
assert not old_docs.intersection(glen_byid)
assert len([x for x in glen_live['entries'] if x['object_type']=='file'])==13
images={x['id']:x for x in read(H/'native-image-verification.json')['sources']}
bindings=copy.deepcopy(state['current_component_bindings'])
for binding in bindings:
 fid=binding['current_component_view_file_id']; src=images[fid]
 assert sha(src['local_path'])==src['sha256']==binding['current_component_view_sha256']
 assert glen_byid[fid]['path']=='ns:202238505/'+binding['current_component_view_path']
 assert posixpath.dirname(glen_byid[fid]['path'])=='ns:202238505/'+binding['component_finish_folder_path']
 binding['coverage_projection']='Candidate complete PNG linked for source/derivation review; existing individual-photo classification retained.'
 binding['individual_photo_status']='Group only'
 binding['reference_document_id']='Unbound'
 binding['reference_document_url']=''
write(H/'independent-native-verification.json',{'status':'PASS','recorded_utc':now(),'families':proof,'new_component_folder_ids_verified':4,'new_png_ids_sizes_and_hashes_verified':4,'historical_reference_documents_not_current':sorted(old_docs),'physical_or_photographic_provenance_inferred':False,'root_native_writes':0})
maps=sorted(r['prefix_maps']+d['prefix_maps'],key=lambda x:len(x['old_path']),reverse=True)
def path_rewrite(p):
 for x in maps:
  old=x['old_path']
  if p.casefold()==old.casefold() or p.casefold().startswith(old.casefold()+'/'):return x['current_path']+p[len(old):]
 return p
def url_rewrite(s):
 if not isinstance(s,str) or not s.startswith('https://www.dropbox.com/'):return s
 p=urlsplit(s);decoded=unquote(p.path)
 for route in ['/home','/preview']:
  if decoded.startswith(route+'/'):
   old=decoded[len(route):];new=path_rewrite(old)
   if new!=old:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return s
def ref(s):
 if not isinstance(s,str):return s
 if s.startswith('https://www.dropbox.com/'):return url_rewrite(s)
 if s.startswith('ns:202238505//'):return 'ns:202238505/'+path_rewrite('/'+s.split('//',1)[1].lstrip('/'))
 if s.startswith('/BOLDSTONE MASTER/'):return path_rewrite(s)
 return s
def rebase(z):
 if isinstance(z,list):return [rebase(x) for x in z]
 if isinstance(z,dict):return {k:(copy.deepcopy(v) if k.startswith(('prior_','historical_')) or '_before_' in k else rebase(v)) for k,v in z.items()}
 return ref(z)
def project(z):
 for k in ['image_url','folder_url','context_image_url','context_folder_url','path']:
  if k in z:z[k]=ref(z[k])
g=read(H/'inputs/master_register.before');oldg=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a)
names={x['product_id']:x['new_option_name'] for x in bindings};components={x['component_id']:x['new_component_name'] for x in bindings}
name_map={x['name']:names[x['product_id']] for x in g['options'] if x['product_id'] in names}
name_map.update({x['name']:components[x['component_id']] for x in g['components'] if x['component_id'] in components})
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
 for x in g[layer]:project(x)
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:project(x.get('current_primary_reference',{}))
for x in g['arrangement_context_references']:
 project(x)
 for y in x.get('images',[]):project(y)
for x in g['options']:
 for key in ['current_candidate_binding_review','current_photo_task_review','current_photo_gap_review']:
  if key in x:x[key]=rebase(x[key])
 if x['product_id'] not in names:continue
 binding=next(b for b in bindings if b['product_id']==x['product_id']); old_name=x['name']
 x['name']=names[x['product_id']];x['retained_names']=list(dict.fromkeys(x['retained_names']+[old_name,x['name']]))
 for k in ['current_listing_reconciliation','current_listing_resolution']:
  if k in x:x[k]['name']=x['name']
 x['current_numbered_identity']={'source':m['glen_overlay'],'member_number':binding['component_number'],'front_view_position':binding['approved_position'],'source_group_file_id':binding['primary_group_reference_file_id'],'old_position_names_retained':True}
 x['component_folder_binding']=copy.deepcopy(binding)
 x['current_individual_asset_candidate']={'file_id':binding['current_component_view_file_id'],'folder_id':binding['component_finish_folder_id'],'image_url':binding['current_component_view_url'],'folder_url':binding['component_finish_folder_url'],'source_sha256':binding['current_component_view_sha256'],'state':'COMPLETE_VIEW_VISUALLY_MATCHED_CREATION_PROVENANCE_PENDING','verified_photo_coverage_changed':False}
for x in g['components']:
 if x['component_id'] not in components:continue
 binding=next(b for b in bindings if b['component_id']==x['component_id']);old_name=x['name']
 x['name']=components[x['component_id']];x['option_names']=[names[i] for i in x['option_ids']]
 x['retained_names']=list(dict.fromkeys(x['retained_names']+[old_name,x['name']]+x['option_names']))
 x['component_finish_folder_bindings']=[copy.deepcopy(binding)]
 x['current_numbered_identity']={'member_number':binding['component_number'],'front_view_position':binding['approved_position'],'owner_decision':d['owner_decision'],'source_group_file_id':binding['primary_group_reference_file_id']}
def labels(z):
 if isinstance(z,list):
  for x in z:labels(x)
 elif isinstance(z,dict):
  for k,v in z.items():
   if k in ['name','display_name','title','option_name','component_name'] and isinstance(v,str) and v in name_map:z[k]=name_map[v]
   elif k not in ['evidence_ref','master_ref','frozen_master','source_ref'] and not k.startswith(('prior_','historical_')):labels(v)
for k in ['source_media_configuration_coverage','source_platform_offer_coverage','current_listing_issues','current_listing_resolution','current_listing_resolution_details']:labels(g[k])
for x in a['coverage']:
 if x['option_id'] in names:
  x['name']=names[x['option_id']];x['current_individual_asset_candidate']=copy.deepcopy(next(o for o in g['options'] if o['product_id']==x['option_id'])['current_individual_asset_candidate'])
 for role in ['individual','in_situ','series']:
  if x[role].get('reference'):x[role]['reference']=rebase(x[role]['reference'])
 for k in ['candidate_binding_review','owner_guided_review']:
  if k in x:x[k]=rebase(x[k])
for x in a['missing_pictures']:
 if x['option_id'] in names:x['name']=names[x['option_id']]
 if x.get('reference'):x['reference']=rebase(x['reference'])
for x in a['identity_review']:
 if x.get('name') in name_map:x['name']=name_map[x['name']]
 for k in ['reference','comparison']:
  if x.get(k):x[k]=rebase(x[k])
a['recorded_utc']=now();a['current_folder_refresh']={'scope':'Raked Spiral and Gleneagles native paths; four approved Gleneagles display numbers and candidate PNG references. Existing role decisions and counts retained.','source_overlays':[m['raked_overlay'],m['glen_overlay']],'root_current_native_verification':rel(H/'independent-native-verification.json'),'new_photograph_coverage_claims':0}
assert a['counts']==olda['counts']
write(H/'image-coverage-current.json',a)
scope={'recorded_utc':now(),'owner_decision':copy.deepcopy(d['owner_decision']),'historical_execution_overlay':m['glen_overlay'],'current_state_addendum':m['glen_state_addendum'],'root_native_verification':rel(H/'independent-native-verification.json'),'component_finish_bindings':bindings,'source_fields_changed':0,'new_components_or_options':0,'individual_gaps_retained':4,'new_candidate_pngs':4,'reference_document_state':'Unbound in current family; historical document IDs and execution evidence retained.'}
g['latest_gleneagles_numbering']=scope
g['latest_raked_spiral_paths']={'recorded_utc':now(),'overlay':m['raked_overlay'],'summary':r['summary'],'prefix_maps':r['prefix_maps'],'root_native_verification':rel(H/'independent-native-verification.json'),'accepted_sculpture_names_changed':0,'specification_changes':0}
g['historical_image_coverage_audits'].append(copy.deepcopy(oldg['latest_image_coverage_audit']))
g['latest_image_coverage_audit']={**copy.deepcopy(oldg['latest_image_coverage_audit']),'recorded_utc':now(),'audit':rel(H/'image-coverage-current.json'),'audit_sha256':sha(H/'image-coverage-current.json'),'verification':rel(H/'saved-file-verification.json'),'visual_verification':rel(H/'visual-verification.json'),'current_folder_updates':['Raked Spiral','Gleneagles Vine and Tendril']}
for k in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g)
sp=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(sp);sp.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before')
changes={};links={};heights={}
def setcell(sn,cell,value):
 assert cell not in b['formulas'][sn],(sn,cell)
 before=b['values'][sn].get(cell,'')
 if before!=value:changes[(sn,cell)]={'sheet':sn,'cell':cell,'before':before,'value':value}
def row(sn,key):
 rs=[int(re.search(r'\d+',c)[0]) for c,v in b['values'][sn].items() if re.fullmatch(r'A\d+',c) and v==key];assert len(rs)==1,(sn,key);return rs[0]
for sn,s in b['sheets'].items():
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])} if rp in b['files'] else {}
 for h in s['root'].findall('.//'+n.q('hyperlink')):
  cell=h.get('ref');target='#'+h.get('location') if h.get('location') else rs[h.get('{'+n.R+'}id')].get('Target');links[(sn,cell)]={'sheet':sn,'cell':cell,'target':url_rewrite(target),'label':ref(b['values'][sn].get(cell,''))}
 for cell,value in b['values'][sn].items():
  value2=ref(value)
  if value2!=value:setcell(sn,cell,value2)
for sn,col in [('Master Catalogue','B'),('Specifications','B'),('Photo Coverage','B'),('Missing Pictures','C'),('Listing Reconciliation','B'),('Listing Issues','B'),('Listing Resolution','B'),('Draft Listings','B')]:
 for cell,value in b['values'][sn].items():
  if re.fullmatch(col+r'\d+',cell) and value in name_map:setcell(sn,cell,name_map[value])
for cid,name in components.items():
 rn=row('Components',cid);comp=next(x for x in g['components'] if x['component_id']==cid);setcell('Components','B'+str(rn),name);setcell('Components','K'+str(rn),'\n'.join(comp['retained_names']))
for sn,col in [('Sets and Context','D'),('Source Mapping','E'),('Listing Offer Links','P')]:
 for cell,value in b['values'][sn].items():
  if not re.fullmatch(col+r'\d+',cell) or not isinstance(value,str):continue
  new=value
  for old,newname in sorted(name_map.items(),key=lambda x:len(x[0]),reverse=True):new=new.replace(old+' [',newname+' [')
  if new!=value:setcell(sn,cell,new)
for key,link in links.items():
 if key in changes:link['label']=changes[key]['value']
for (sn,cell),change in changes.items():
 if not isinstance(change['value'],str) or cell=='A3':continue
 col=re.match('[A-Z]+',cell)[0];ci=0
 for char in col:ci=ci*26+ord(char)-64
 root=b['sheets'][sn]['root'];width=next((float(x.get('width')) for x in root.findall('.//'+n.q('col')) if int(x.get('min'))<=ci<=int(x.get('max'))),13)
 rn=int(cell[len(col):]);lines=sum(max(1,math.ceil(len(x)/max(8,width*.9))) for x in change['value'].split('\n'));height=lines*13+12;before=float(next(x for x in root.find(n.q('sheetData')) if x.get('r')==str(rn)).get('ht',15))
 if height>before:assert height<=409,(sn,cell,height);heights[(sn,rn)]=max(heights.get((sn,rn),before),height)
link=lambda label,target:{'label':label,'target':target}
original_objects={x['file_id']:x for x in d['objects']};rows=[]
for x in bindings:
 opt=next(o for o in g['options'] if o['product_id']==x['product_id']);image=original_objects[opt['file_id']];parent=original_objects[opt['folder_id']]
 assert image['current_parent_id']==opt['folder_id'] and opt['photo_coverage']['individual']=='Group only'
 rows.append([x['product_id'],x['new_option_name'],x['component_number'],x['approved_position'],link('Component folder',x['component_finish_folder_url']),link('Isolated PNG candidate',x['current_component_view_url']),link('Original group image',image['current_native_url']),link('Image containing folder',parent['current_native_url']),x['component_finish_folder_id'],x['current_component_view_file_id'],opt['file_id'],opt['folder_id'],'White','Group only',x['old_approved_option_name'],'Complete PNG matches the numbered motif and relief. Creation process is unconfirmed; qualified individual-photo gap remains open. Existing dimensions, mass, material, fixing, price and availability retain their source qualifications.'])
sheet={'title':'Gleneagles component folders and source images','note':'Front view: 1 top left, 2 top right, 3 bottom left, 4 bottom right. New PNGs are linked for source review; four qualified individual-photo gaps remain.','headers':['Option ID','Current sculpture / option','Number','Approved position','Component folder','New PNG candidate','Original group example','Containing image folder','Component folder ID','Candidate PNG file ID','Original group file ID','Original image folder ID','Finish','Individual photo status','Earlier positional name','Scope and next action'],'widths':[25,49,12,19,25,27,27,30,35,35,35,35,14,24,52,88],'rows':rows}
write(H/'workbook-data.json',{'sheets':{'Gleneagles Folders':sheet}})
old_targets={}
for sn,s in b['sheets'].items():
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])} if rp in b['files'] else {}
 for h in s['root'].findall('.//'+n.q('hyperlink')):old_targets[(sn,h.get('ref'))]='#'+h.get('location') if h.get('location') else rs[h.get('{'+n.R+'}id')].get('Target')
plan={'cell_changes':list(changes.values()),'hyperlinks':list(links.values()),'target_changes':[{'sheet':sn,'cell':cell,'before':old_targets[(sn,cell)],'after':v['target']} for (sn,cell),v in links.items() if old_targets[(sn,cell)]!=v['target']],'row_heights':[{'sheet':sn,'row':rn,'height':height} for (sn,rn),height in heights.items()],'style_changes':[],'old_sheet_count':len(b['sheets']),'new_sheet_count':1,'expected_native_hyperlinks':len(links)+16,'baseline_ranges':[['Components','B62:K65','baseline-glen-components'],['Master Catalogue','A97:D100','baseline-glen-options']],'preview_ranges':[['Components','A62:K65','01-numbered-components'],['Master Catalogue','A97:D100','02-numbered-options'],['Gleneagles Folders','A2:H4','03-folder-summary'],['Gleneagles Folders','A9:H13','04-current-folder-and-image-links'],['Gleneagles Folders','I9:P13','05-stable-IDs-and-qualification']]}
write(H/'workbook-edit-plan.json',plan)
def diff(old,new,path=[]):
 if old==new:return []
 if isinstance(old,dict) and isinstance(new,dict):
  out=[]
  for k in sorted(set(old)|set(new)):
   if k not in old:out.append({'path':path+[k],'kind':'added','after':new[k]})
   elif k not in new:out.append({'path':path+[k],'kind':'removed','before':old[k]})
   else:out.extend(diff(old[k],new[k],path+[k]))
  return out
 if isinstance(old,list) and isinstance(new,list) and len(old)==len(new):return [x for i,(p,q) in enumerate(zip(old,new)) for x in diff(p,q,path+[i])]
 return [{'path':path,'kind':'changed','before':old,'after':new}]
write(H/'register-change-log.json',diff(oldg,g));write(H/'audit-change-log.json',diff(olda,a))
assert len(g['options'])==184 and len(g['components'])==111
assert all(x['product_id']==y['product_id'] and x['canonical_component_id']==y['canonical_component_id'] and x['master_fields']==y['master_fields'] and x['specifications']==y['specifications'] and x['photo_coverage']==y['photo_coverage'] for x,y in zip(g['options'],oldg['options']))
assert g['original_review_specification_assertions']==oldg['original_review_specification_assertions']
write(H/'preparation-verification.json',{'status':'PASS','current_option_names':names,'component_names':components,'cell_changes':len(changes),'native_hyperlink_targets_updated':len(plan['target_changes']),'new_link_cells':16,'old_sheets':len(b['sheets']),'new_folder_sheet':1,'specification_changes':0,'new_options':0,'role_classification_changes':0,'qualified_individual_gaps_retained':26,'four_new_png_candidates_linked':4,'unavailable_reference_documents_not_linked':4})
print(json.dumps(read(H/'preparation-verification.json')))
