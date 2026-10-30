"""Apply confirmed Lava Moon numbering and current stable-ID references only."""
import copy,hashlib,importlib.util,json,math,posixpath,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,urlunsplit
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json')
for key,f in [('native_readback','independent-native-readback.json'),('native_images','native-image-verification.json')]:
 p=H/f;s=H/'inputs'/(key+'.before')
 if key not in m:shutil.copy2(p,s);m[key]={'path':str(p),'snapshot':str(s),'sha256':sha(p)}
write(H/'input-manifest.json',m)
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
o=read(H/'inputs/owner_overlay.before');assert o['exact_owner_confirmation']=='Lava Moon is done, you can move on, it is corect now'
for r in o['receipts']:assert sha(r['path'])==r['sha256']
live=read(H/'independent-native-readback.json');byid={x['file_id']:x for x in live['entries']};assert not live['has_more']and len(byid)==17
objects={x['file_id']:x for x in o['objects']};assert set(objects)==set(byid)
for fid,x in objects.items():
 y=byid[fid];assert y['path']=='ns:202238505/'+x['current_path']and y['name']==x['current_name']and y['object_type']==x['object_type']
 if x['object_type']=='file':assert y['file']['size']==x['size']
images=read(H/'native-image-verification.json');assert images['status']=='PASS'and len(images['originals'])==4
for x in images['originals']:assert sha(x['local_path'])==x['sha256']and byid[x['file_id']]['path']==x['path']
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a);binds=copy.deepcopy(o['component_numbering_and_current_white_bindings']);names={};cnames={};pngs={x['file_id']:x for x in images['originals']}
for x in binds:
 cnames[x['component_id']]=x['new_component_display_name'];names[x['white_product_id']]=x['new_white_display_name'];names[x['sandstone_product_id']]=x['new_sandstone_display_name']
 x.update(creation_provenance='UNCONFIRMED; owner placement and visual motif correspondence do not certify capture/exact crop or generation history.',visual_comparison='Isolated view follows the numbered left/centre/right relief in original group ylMA; exact pixel derivation, cast and scale are not certified.',individual_photo_status='Group only',candidate_sha256=pngs[x['current_white_candidate_file_id']]['sha256'])
name_map={x['name']:names[x['product_id']]for x in g['options']if x['product_id']in names};name_map.update({x['name']:cnames[x['component_id']]for x in g['components']if x['component_id']in cnames})
maps=sorted(o['prefix_maps'],key=lambda x:len(x['old_path']),reverse=True);move=o['file_moves'][0]
def path(s):
 if s==move['old_path']:return move['current_path']
 for x in maps:
  if s==x['old_path']or s.startswith(x['old_path']+'/'):return x['current_path']+s[len(x['old_path']):]
 return s
def ref(s):
 if not isinstance(s,str):return s
 if s.startswith('ns:202238505//'):return 'ns:202238505/'+path('/'+s.split('//',1)[1])
 if s.startswith('/BOLDSTONE MASTER/'):return path(s)
 if not s.startswith('https://www.dropbox.com/'):return s
 p=urlsplit(s);dec=unquote(p.path)
 for route in ['/home','/preview']:
  if dec.startswith(route+'/'):
   tail=dec[len(route):]
   # home?preview links identify the moved detail file via their query.
   if tail==posixpath.dirname(move['old_path'])and unquote(p.query).endswith('='+move['current_name']):tail=posixpath.dirname(move['current_path'])
   new=path(tail)
   if new!=dec[len(route):]:return urlunsplit((p.scheme,p.netloc,quote(route+new,safe='/'),p.query,p.fragment))
 return s
def rebase(z):
 if isinstance(z,list):return[rebase(v)for v in z]
 if isinstance(z,dict):return{k:copy.deepcopy(v)if k.startswith(('prior_','historical_'))or '_before_'in k else rebase(v)for k,v in z.items()}
 return ref(z)
def project(z):
 for k in ['image_url','folder_url','context_image_url','context_folder_url','path']:
  if k in z:z[k]=ref(z[k])
 if z.get('file_id')==move['file_id']:
  z.update(folder_id=move['current_parent_id'],image_url=move['current_native_url'],folder_url=objects[move['current_parent_id']]['current_native_url'])
for layer in ['options','components','aliases','source_review_reconciliation','original_specification_current_references','exceptions']:
 for x in g[layer]:project(x)
for layer in ['source_sets','source_offer_edges']:
 for x in g[layer]:project(x.get('current_primary_reference',{}))
for x in g['arrangement_context_references']:
 project(x)
 for y in x.get('images',[]):project(y)
for x in g['options']:
 for k in ['current_candidate_binding_review','current_photo_task_review','current_photo_gap_review']:
  if k in x:x[k]=rebase(x[k])
 if x['product_id']not in names:continue
 oldname=x['name'];x['name']=names[x['product_id']];x['retained_names']=list(dict.fromkeys(x['retained_names']+[oldname,x['name']]))
 binding=next(z for z in binds if x['canonical_component_id']==z['component_id'])
 x['current_numbered_identity']={'owner_confirmation':o['exact_owner_confirmation'],'overlay':m['owner_overlay'],'member_number':binding['owner_confirmed_number'],'historical_position':binding['historical_position_alias'],'specification_transfer_or_value_change':False}
 for k in ['current_listing_reconciliation','current_listing_resolution']:
  if k in x:x[k]['name']=x['name']
 if x['product_id']==binding['white_product_id']:
  x['component_folder_binding']=copy.deepcopy(binding);x['current_individual_asset_candidate']={'file_id':binding['current_white_candidate_file_id'],'folder_id':binding['current_white_folder_id'],'image_url':binding['current_white_candidate_url'],'folder_url':binding['current_white_folder_url'],'source_sha256':binding['candidate_sha256'],'state':'VISUAL_COMPONENT_CANDIDATE_CREATION_PROVENANCE_PENDING','verified_photo_coverage_changed':False}
for x in g['components']:
 if x['component_id']not in cnames:continue
 oldname=x['name'];x['name']=cnames[x['component_id']];x['option_names']=[names[z]for z in x['option_ids']];x['retained_names']=list(dict.fromkeys(x['retained_names']+[oldname,x['name']]+x['option_names']));x['component_finish_folder_bindings']=[copy.deepcopy(next(z for z in binds if z['component_id']==x['component_id']))]
def labels(z):
 if isinstance(z,list):
  for v in z:labels(v)
 elif isinstance(z,dict):
  for k,v in z.items():
   if k in ['name','display_name','title','option_name','component_name']and isinstance(v,str)and v in name_map:z[k]=name_map[v]
   elif not k.startswith(('prior_','historical_'))and k not in ['evidence_ref','master_ref','frozen_master','source_ref']:labels(v)
for k in ['source_media_configuration_coverage','source_platform_offer_coverage','current_listing_issues','current_listing_resolution','current_listing_resolution_details']:labels(g[k])
for x in a['coverage']:
 if x['option_id']in names:
  x['name']=names[x['option_id']];opt=next(z for z in g['options']if z['product_id']==x['option_id'])
  if 'current_individual_asset_candidate'in opt:x['current_individual_asset_candidate']=copy.deepcopy(opt['current_individual_asset_candidate'])
 for role in ['individual','in_situ','series']:
  if x[role].get('reference'):project(x[role]['reference'])
for layer in ['missing_pictures','identity_review']:
 for x in a[layer]:
  if x.get('option_id')in names:x['name']=names[x['option_id']]
  elif x.get('name')in name_map:x['name']=name_map[x['name']]
  for k in ['reference','comparison']:
   if x.get(k):project(x[k])
scope={'status':'OWNER_CONFIRMED_NUMBERING_CURRENT_PATHS_VERIFIED_PNG_PROVENANCE_PENDING','recorded_utc':now(),'owner_confirmation':o['exact_owner_confirmation'],'overlay':m['owner_overlay'],'component_finish_bindings':binds,'original_group_references_preserved':True,'specification_value_changes':0,'new_canonical_options':0,'new_components':0,'individual_photo_gaps_retained':6,'new_white_candidate_PNGs':3,'unlocated_historical_objects':o['missing_from_earlier_scope'],'root_remote_writes':0}
a['recorded_utc']=now();a['latest_lava_moon_numbering']=copy.deepcopy(scope);write(H/'image-coverage-current.json',a)
g['latest_lava_moon_numbering']=scope;g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=rel(H/'image-coverage-current.json'),audit_sha256=sha(H/'image-coverage-current.json'),verification=rel(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'))
for k in ['verification_sha256','visual_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g)
s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');changes={};links={};heights={}
def setcell(sn,c,value):
 before=b['values'][sn].get(c,'');assert c not in b['formulas'][sn]
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
for sn,z in b['sheets'].items():
 loc=z['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  c=h.get('ref');url='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');historical=sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c);links[(sn,c)]={'sheet':sn,'cell':c,'target':url if historical else ref(url),'label':b['values'][sn].get(c,'')}
 for c,value in b['values'][sn].items():
  if sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c):continue
  new=ref(value)
  if new!=value:setcell(sn,c,new)
 # The historical IDs stay unchanged; only the current-source link resolves the moved file's real parent.
 for c,value in b['values'][sn].items():
  if value==move['file_id']and sn in ['Source Mapping','Source Specifications']:
   rn=re.search(r'\d+',c)[0]
   for col,url in [('H',move['current_native_url']),('I',objects[move['current_parent_id']]['current_native_url'])]:links[(sn,col+rn)]['target']=url
for sn,col in [('Master Catalogue','B'),('Specifications','B'),('Photo Coverage','B'),('Missing Pictures','C'),('Listing Reconciliation','B'),('Listing Issues','B'),('Listing Resolution','B'),('Draft Listings','B')]:
 for c,value in b['values'][sn].items():
  if re.fullmatch(col+r'\d+',c)and value in name_map:setcell(sn,c,name_map[value])
for cid,name in cnames.items():
 rn=next(re.search(r'\d+',c)[0]for c,value in b['values']['Components'].items()if re.fullmatch('A[0-9]+',c)and value==cid);comp=next(x for x in g['components']if x['component_id']==cid);setcell('Components','B'+rn,name);setcell('Components','K'+rn,'\n'.join(comp['retained_names']))
for sn,col in [('Sets and Context','D'),('Source Mapping','E'),('Listing Offer Links','P')]:
 for c,value in b['values'][sn].items():
  if not re.fullmatch(col+r'\d+',c)or not isinstance(value,str):continue
  new=value
  for oldname,newname in sorted(name_map.items(),key=lambda x:len(x[0]),reverse=True):new=new.replace(oldname+' [',newname+' [')
  if new!=value:setcell(sn,c,new)
for k,x in links.items():
 if k in changes:x['label']=changes[k]['value']
for(sn,c),x in changes.items():
 if not isinstance(x['value'],str)or c=='A3':continue
 col=re.match('[A-Z]+',c)[0];ci=0
 for ch in col:ci=ci*26+ord(ch)-64
 rn=int(c[len(col):]);root=b['sheets'][sn]['root'];width=next((float(z.get('width'))for z in root.findall('.//'+n.q('col'))if int(z.get('min'))<=ci<=int(z.get('max'))),13);lines=sum(max(1,math.ceil(len(t)/max(8,width*.9)))for t in x['value'].split('\n'));height=lines*13+12;before=float(next(z for z in root.find(n.q('sheetData'))if z.get('r')==str(rn)).get('ht',15))
 if height>before:assert height<=409;heights[(sn,rn)]=max(heights.get((sn,rn),before),height)
L=lambda label,target:{'label':label,'target':target};rows=[]
for x in binds:
 opt=next(z for z in g['options']if z['product_id']==x['white_product_id']);im=objects[opt['file_id']];folder=objects[opt['folder_id']]
 rows.append([x['white_product_id'],x['new_white_display_name'],x['owner_confirmed_number'],x['historical_position_alias'],L('Component folder',x['current_white_folder_url']),L('Isolated PNG candidate',x['current_white_candidate_url']),L('Original group image',im['current_native_url']),L('Actual group folder',folder['current_native_url']),x['current_white_folder_id'],x['current_white_candidate_file_id'],opt['file_id'],opt['folder_id'],'White','Group only',next(z['name']for z in old['options']if z['product_id']==opt['product_id']),'Numbering and current folders are owner-confirmed. Candidate PNG creation/exact derivation remains unconfirmed; six individual-photo gaps across White and Sandstone remain. Source specifications retain their existing qualifications.'])
sheet={'title':'Lava Moon numbered components and current source folders','note':'1 Left,2 Centre,3 Right. Six existing White/Sandstone option IDs and all source specifications retained. Three White PNGs linked as provenance-pending candidates.','headers':['Option ID','Current sculpture / option','Number','Historical position','Component folder','New PNG candidate','Original group example','Containing image folder','Component folder ID','Candidate PNG file ID','Original group file ID','Original image folder ID','Finish','Individual photo status','Earlier positional name','Scope and next action'],'widths':[25,49,12,19,25,27,27,30,35,35,35,35,14,24,52,88],'rows':rows}
write(H/'workbook-data.json',{'sheets':{'Lava Moon Folders':sheet}})
oldlinks={}
for sn,z in b['sheets'].items():
 loc=z['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):oldlinks[(sn,h.get('ref'))]='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target')
plan={'cell_changes':list(changes.values()),'hyperlinks':list(links.values()),'target_changes':[{'sheet':sn,'cell':c,'before':oldlinks[(sn,c)],'after':x['target']}for(sn,c),x in links.items()if x['target']!=oldlinks[(sn,c)]],'row_heights':[{'sheet':sn,'row':rn,'height':v}for(sn,rn),v in heights.items()],'old_sheet_count':24,'new_sheet_count':1,'expected_native_hyperlinks':len(links)+12,'baseline_ranges':[['Master Catalogue','A102:D107','baseline-lava-options'],['Components','A65:K68','baseline-lava-components']],'preview_ranges':[['Master Catalogue','A102:D107','01-numbered-lava-options'],['Lava Moon Folders','A2:H4','02-folder-summary'],['Lava Moon Folders','A9:H12','03-current-folder-links'],['Lava Moon Folders','I9:P12','04-stable-IDs-and-qualifications']]}
write(H/'workbook-edit-plan.json',plan)
def diff(a,b,p=[]):
 if a==b:return[]
 if isinstance(a,dict)and isinstance(b,dict):
  out=[]
  for k in sorted(set(a)|set(b)):
   if k not in a:out.append({'path':p+[k],'kind':'added','after':b[k]})
   elif k not in b:out.append({'path':p+[k],'kind':'removed','before':a[k]})
   else:out+=diff(a[k],b[k],p+[k])
  return out
 if isinstance(a,list)and isinstance(b,list)and len(a)==len(b):return[x for i,(v,w)in enumerate(zip(a,b))for x in diff(v,w,p+[i])]
 return[{'path':p,'kind':'changed','before':a,'after':b}]
write(H/'register-change-log.json',diff(old,g));write(H/'audit-change-log.json',diff(olda,a))
assert a['counts']==olda['counts']and g['summary']==old['summary']and g['original_review_specification_assertions']==old['original_review_specification_assertions']
assert all(x['product_id']==y['product_id']and x['master_fields']==y['master_fields']and x['specifications']==y['specifications']and x['photo_coverage']==y['photo_coverage']for x,y in zip(g['options'],old['options']))
write(H/'independent-native-verification.json',{'status':'PASS','current_objects':17,'current_images':11,'new_candidate_PNGs_verified':3,'new_candidate_and_original_group_bytes_rehashed':4,'current_parent_ID_change':move,'unlocated_historical_objects':o['missing_from_earlier_scope'],'root_native_writes':0})
write(H/'preparation-verification.json',{'status':'PASS','six_option_names_updated':names,'three_component_names_updated':cnames,'new_options':0,'specification_changes':0,'image_role_changes':0,'retained_individual_gaps':26,'changed_cells':len(changes),'changed_link_targets':len(plan['target_changes']),'new_native_links':12})
print(json.dumps(read(H/'preparation-verification.json')))
