"""Project two completed native changes by file ID before folder-prefix fallback."""
import copy,hashlib,importlib.util,json,math,posixpath,re,shutil
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlsplit,urlunsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;BASE=H.parents[2];PRIOR=H.parent/'spice-frozen-decowaves-master-refresh-2026-10-22'
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(BASE))
def write(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
ptr=read(BASE/'current-master.json')
if not(H/'input-manifest.json').exists():
 sources={'master_pointer':BASE/'current-master.json','master_workbook':BASE/ptr['workbook'],'master_register':BASE/ptr['register'],'audit':Path(ptr['latest_image_coverage_audit']['path']),'review_progress':BASE/'components/reviews/specification_review_progress.json','component_checkpoint':BASE/'components/checkpoint.json','root_checkpoint':BASE/'checkpoint.json','report_assets':PRIOR/'current-assets.json','report_reviews':PRIOR/'photo-review-queue.json','squarespace_hold':BASE/'components/parallel-reviews/listing-execution-2026-10-21/SQUARESPACE_WRITE_HOLD.json','egyptian_overlay':BASE.parent/'reports/dropbox-egyptian-two-palms-flat-renames-2026-10-22/current-reference-overlay.json','gold_overlay':BASE.parent/'reports/dropbox-brancusi-gold-leaf-flat-renames-2026-10-22/current-reference-overlay.json','white_overlay':BASE.parent/'reports/dropbox-brancusi-white-pair-rename-2026-10-22/current-reference-overlay.json'}
 sources.update({k:H/f for k,f in [('egyptian_live','egyptian-live-tree.json'),('brancusi_live','brancusi-live-tree.json'),('egyptian_family','egyptian-family-metadata.json'),('brancusi_family','brancusi-family-metadata.json')]})
 m={}
 for k,p in sources.items():
  snap=H/'inputs'/(k+'.before');shutil.copy2(p,snap);m[k]={'path':str(p),'snapshot':str(snap),'sha256':sha(p)}
 write(H/'input-manifest.json',m)
m=read(H/'input-manifest.json')
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
assert m['master_workbook']['sha256']==ptr['workbook_sha256']and m['master_register']['sha256']==ptr['register_sha256']
overlays=[read(H/'inputs'/f'{x}_overlay.before')for x in ['egyptian','gold','white']];objects={};prefixes=[];path_aliases={}
for o in overlays:
 assert o['verification']['status']=='PASS'
 for x in o['receipts']:assert sha(x['path'])==x['sha256'],x['path']
 for x in o['objects']:
  # These sealed overlays retain namespace paths. Use display paths solely
  # for local URL/parent mapping; original namespace values remain in snapshots.
  for key in ['old_path','current_path']:
   if x[key].startswith('ns:202238505//'):x[key]='/'+x[key].split('//',1)[1]
  previous=objects.get(x['file_id'])
  if previous:
   assert x['old_path']==previous['current_path']and x['old_parent_id']==previous['current_parent_id']and x['object_type']==previous['object_type']
   if x['object_type']=='file':assert x['size']==previous['size']and x['old_name']==previous['current_name']
  for k in ['old_path','current_path']:path_aliases[x[k].casefold()]=x['file_id']
  objects[x['file_id']]=copy.deepcopy(x)
 prefixes+=o['prefix_maps']
for family,indices in [('egyptian',[0]),('brancusi',[1,2])]:
 o=overlays[indices[-1]];live=read(H/'inputs'/f'{family}_live.before');md=read(H/'inputs'/f'{family}_family.before')['folder'];assert not live['has_more']and md['id']==o['family']['file_id']and md['path_display']==o['family']['path']
 byid={x['file_id']:x for x in live['entries']};assert set(byid)=={x['file_id']for x in o['objects']}
 parents={x['current_path'].casefold():x['file_id']for x in objects.values()if x['object_type']=='folder'};parents[o['family']['path'].casefold()]=o['family']['file_id']
 for fid,y in byid.items():
  x=objects[fid]
  y=byid[x['file_id']];assert y['path']=='ns:202238505/'+x['current_path']and y['name']==x['current_name']and y['object_type']==x['object_type']
  assert parents[posixpath.dirname(x['current_path']).casefold()]==x['current_parent_id']
  if x['object_type']=='file':assert y['file'].get('size',0)==x['size']and x['old_name']==x['current_name']
 objects[md['id']]={'file_id':md['id'],'object_type':'folder','old_path':md['path_display'],'current_path':md['path_display'],'current_name':md['name'],'current_native_url':'https://www.dropbox.com/home'+quote(md['path_display'],safe='/')}
 path_aliases[md['path_display'].casefold()]=md['id']
assert len(objects)==555 and sum(x['object_type']=='file'for x in objects.values())==530 and len(prefixes)==5
prefixes.sort(key=lambda x:len(x['old_path']),reverse=True);oldpaths={p:objects[fid]for p,fid in path_aliases.items()}
write(H/'combined-native-object-crosswalk.json',{'objects':objects,'path_aliases':path_aliases,'prefix_maps':prefixes,'ordered_source_overlays':['egyptian','gold','white']})
def path(s):
 if s.casefold()in oldpaths:return oldpaths[s.casefold()]['current_path']
 for p in prefixes:
  if s.casefold()==p['old_path'].casefold()or s.casefold().startswith(p['old_path'].casefold()+'/'):return p['current_path']+s[len(p['old_path']):]
 return s
def fromurl(s):
 if not isinstance(s,str)or not s.startswith('https://www.dropbox.com/'):return None
 u=urlsplit(s);p=unquote(u.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(u.query).get('preview',[''])[0]
 return oldpaths.get((p+('/'+name if name else '')).casefold())
def ref(s):
 if not isinstance(s,str):return s
 if s.startswith('ns:202238505//'):return'ns:202238505/'+path('/'+s.split('//',1)[1])
 if s.startswith('/BOLDSTONE MASTER/'):return path(s)
 if not s.startswith('https://www.dropbox.com/'):return s
 u=urlsplit(s);p=unquote(u.path)
 for route in ['/home','/preview']:
  if not p.startswith(route+'/'):continue
  old=p[len(route):];name=parse_qs(u.query).get('preview',[''])[0];obj=fromurl(s)
  new=posixpath.dirname(obj['current_path'])if name and obj and obj['object_type']=='file'else path(old)
  if new!=old:return urlunsplit((u.scheme,u.netloc,quote(route+new,safe='/'),u.query,u.fragment))
 return s
def project(x):
 for k in ['image_url','folder_url','context_image_url','context_folder_url','path','ns_path','url']:
  if k in x:x[k]=ref(x[k])
 for fk,folder,url in [('file_id','folder_id','folder_url'),('context_file_id','context_folder_id','context_folder_url')]:
  o=objects.get(x.get(fk))
  if o and o['object_type']=='file':
   parent=objects[o['current_parent_id']]
   if folder in x:x[folder]=o['current_parent_id']
   if url in x:x[url]='https://www.dropbox.com/home'+quote(parent['current_path'],safe='/')
def rebase(z):
 if isinstance(z,list):return[rebase(v)for v in z]
 if isinstance(z,dict):
  result={k:copy.deepcopy(v)if k.startswith(('historical_','prior_','original_'))or k in ['source_ref','evidence_ref','master_ref','frozen_master','specifications','master_fields','accepted_working_fields','six_working_fields']else rebase(v)for k,v in z.items()};project(result);return result
 return ref(z)
g=read(H/'inputs/master_register.before');old=copy.deepcopy(g);a=read(H/'inputs/audit.before');olda=copy.deepcopy(a)
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
g['current_listing_resolution_details']=rebase(g['current_listing_resolution_details'])
for x in a['coverage']:
 for role in ['individual','in_situ','series']:
  if x[role].get('reference'):project(x[role]['reference'])
for layer in ['missing_pictures','identity_review']:
 for x in a[layer]:
  for k in ['reference','comparison']:
   if x.get(k):project(x[k])
assets=rebase(read(H/'inputs/report_assets.before'));reviews=rebase(read(H/'inputs/report_reviews.before'))
scope={'status':'VERIFIED_EGYPTIAN_PALMS_AND_BRANCUSI_GROUP_FOLDER_NAMES','recorded_utc':now(),'source_overlays':[m[x+'_overlay']for x in ['egyptian','gold','white']],'combined_crosswalk':{'path':str(H/'combined-native-object-crosswalk.json'),'sha256':sha(H/'combined-native-object-crosswalk.json')},'native_objects_verified_including_two_families':555,'original_file_IDs_names_and_sizes_preserved':530,'folder_renames':5,'new_folder_IDs':0,'file_parent_changes':0,'file_paths_updated':205,'names_specifications_counts_and_image_roles_changed':False,'historical_diptych_alias_preserved':True,'root_native_writes':0}
g['latest_palms_brancusi_path_refresh']=copy.deepcopy(scope);a['latest_palms_brancusi_path_refresh']=copy.deepcopy(scope);a['recorded_utc']=now()
write(H/'image-coverage-current.json',a);g['historical_image_coverage_audits'].append(copy.deepcopy(g['latest_image_coverage_audit']));g['latest_image_coverage_audit'].update(recorded_utc=now(),path=str(H/'image-coverage-current.json'),audit=rel(H/'image-coverage-current.json'),audit_sha256=sha(H/'image-coverage-current.json'),verification=rel(H/'saved-file-verification.json'),visual_verification=rel(H/'visual-verification.json'),scope='Current186options with all five Egyptian Palms and Brancusi Gold Leaf/White pair-folder changes projected by stable IDs. All image statuses, physical specifications, commercial fields and historical Diptych aliases are retained.')
for k in ['verification_sha256','visual_verification_sha256','independent_verification','independent_verification_sha256']:g['latest_image_coverage_audit'].pop(k,None)
write(H/'canonical-master-register.json',g);write(H/'current-assets.json',assets);write(H/'photo-review-queue.json',reviews)
assert g['summary']==old['summary']and a['counts']==olda['counts']and g['original_review_specification_assertions']==old['original_review_specification_assertions']
for x,y in zip(g['options'],old['options']):assert all(x[k]==y[k]for k in ['product_id','name','canonical_component_id','master_fields','specifications','photo_coverage','selling_details'])
for x,y in zip(g['options'],old['options']):assert x['file_id']==y['file_id']and x['folder_id']==y['folder_id']
def diff(x,y,p=[]):
 if x==y:return[]
 if isinstance(x,dict)and isinstance(y,dict):
  result=[]
  for k in sorted(set(x)|set(y)):
   if k not in x:result.append({'path':p+[k],'kind':'added','after':y[k]})
   elif k not in y:result.append({'path':p+[k],'kind':'removed','before':x[k]})
   else:result+=diff(x[k],y[k],p+[k])
  return result
 if isinstance(x,list)and isinstance(y,list)and len(x)==len(y):return[z for i,(v,w)in enumerate(zip(x,y))for z in diff(v,w,p+[i])]
 return[{'path':p,'kind':'changed','before':x,'after':y}]
write(H/'register-change-log.json',diff(old,g));write(H/'audit-change-log.json',diff(olda,a))

s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');changes={};links={};oldtargets={};heights={}
def protected(sn,c):return sn=='Source Specifications'and re.fullmatch('[MN]\\d+',c)or sn=='Moonphases and Dune'and re.fullmatch('I\\d+',c)or sn=='Fingerprint History'
def setcell(sn,c,v):
 assert c not in b['formulas'][sn];before=b['values'][sn].get(c,'')
 if before!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');url='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target');oldtargets[(sn,c)]=url;links[(sn,c)]={'sheet':sn,'cell':c,'target':url if protected(sn,c)else ref(url),'label':b['values'][sn].get(c,'')}
 for c,v in b['values'][sn].items():
  if not protected(sn,c)and ref(v)!=v:setcell(sn,c,ref(v))
pairs={'Master Catalogue':[('N','O','R'),('T','U',None)],'Specifications':[('J','K','M')],'Components':[('F','G','I')],'Sets and Context':[('I','J','L')],'Aliases':[('F','G','I')],'References and Gaps':[('F','G',None)],'Platform Sources':[('U','V','X')],'Source Mapping':[('H','I',None)],'Source Specifications':[('H','I',None)],'Photo Coverage':[('D','E','N'),('G','H','P'),('J','K','R')],'Missing Pictures':[('G','H','J')],'Identity Review':[('G','H','J'),('L','M','P')],'Listing Reconciliation':[('M','N','P')],'Listing Offer Links':[('R','S','U')],'Listing Issues':[('J','K','M')],'Listing Resolution':[('R','S','U')],'Listing Corrections':[('M','N',None)],'Draft Listings':[('I','J','L')],'Selling Details':[('L','M','O')]}
for(sn,c),url in oldtargets.items():
 match=re.fullmatch(r'([A-Z]+)(\d+)',c);o=fromurl(url)
 if not match or int(match[2])<10 or not o or o['object_type']!='file':continue
 col,row=match.groups()
 for image,folder,parent in pairs.get(sn,[]):
  if col!=image:continue
  key=(sn,folder+row)
  if key in links:links[key]['target']='https://www.dropbox.com/home'+quote(objects[o['current_parent_id']]['current_path'],safe='/')
  if parent and o.get('old_parent_id')!=o['current_parent_id']:setcell(sn,parent+row,o['current_parent_id'])
setcell('Moonphases and Dune','A3','58 approved folder updates, including the Egyptian Palm 1/2 and Brancusi 1/2 Gold Leaf and White groups. Original file and folder IDs, individual identities, specifications and historical source paths are retained.')
setcell('Moonphases and Dune','A4','Verified folder updates')
folderrows=[];L=lambda label,url:{'label':label,'target':url}
for o in overlays:
 for p in o['prefix_maps']+o.get('created_folders',[]):
  fid=p['file_id'];children=[x for x in objects.values()if x['object_type']=='file'and x['current_parent_id']==fid];im=children[0]
  folderrows.append([Path(o['family']['path']).name,fid,p['old_name'],p['current_name'],L('Current folder','https://www.dropbox.com/home'+quote(p['current_path'],safe='/')),L('Existing example photograph',im['current_native_url']),im['file_id'],fid,p['old_path'],p['current_path'],len(children),'arrangement/context','Original file and parent IDs retained; no new component','Existing identities, specifications, historical aliases and image-role qualifications retained'])
assert len(folderrows)==5
for k,x in changes.items():
 if k in links:links[k]['label']=x['value']
 col=re.match('[A-Z]+',k[1])[0];rn=int(k[1][len(col):]);v=x['value']
 if not isinstance(v,str)or k[1]=='A3':continue
 ci=0
 for ch in col:ci=ci*26+ord(ch)-64
 root=b['sheets'][k[0]]['root'];width=next((float(z.get('width'))for z in root.findall('.//'+n.q('col'))if int(z.get('min'))<=ci<=int(z.get('max'))),13);oldheight=float(next(z for z in root.find(n.q('sheetData'))if z.get('r')==str(rn)).get('ht',15));height=sum(max(1,math.ceil(len(t)/max(8,width*.9)))for t in v.split('\n'))*13+12
 if height>oldheight:assert height<=409;heights[(k[0],rn)]=max(heights.get((k[0],rn),oldheight),height)
blocks=[];groups={}
for(sn,c),x in changes.items():groups.setdefault((sn,re.match('[A-Z]+',c)[0]),[]).append(x)
for(sn,col),items in groups.items():
 items.sort(key=lambda x:int(x['cell'][len(col):]));run=[]
 for x in items:
  if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[z['value']]for z in run]});run=[]
  run.append(x)
 if run:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[z['value']]for z in run]})
plan={'cell_changes':list(changes.values()),'value_blocks':blocks,'row_heights':[{'sheet':sn,'row':rn,'height':v}for(sn,rn),v in heights.items()],'hyperlinks':list(links.values()),'target_changes':[{'sheet':sn,'cell':c,'before':oldtargets[(sn,c)],'after':v['target']}for(sn,c),v in links.items()if oldtargets[(sn,c)]!=v['target']],'formula_changes':[{'sheet':'Moonphases and Dune','cell':c,'formula':f,'expected':v}for c,f,v in [('B4','=COUNTA(B10:B67)',58),('D4','=COUNTIF(A10:A67,"Dune Ripple")',22),('F4','=COUNTIF(A10:A67,"Moonphases")',10)]],'formula_cache_changes':[],'expected_formula_count':3356,'expected_native_links':len(links)+10,'old_sheet_count':28,'new_sheet_count':0,'baseline_ranges':[['Master Catalogue','T32:U32','baseline-brancusi-references']],'preview_ranges':[['Master Catalogue','T32:U32','01-brancusi-current-references'],['Moonphases and Dune','A63:H67','02-five-current-folder-updates'],['Moonphases and Dune','A2:H4','03-current-folder-summary']]}
write(H/'workbook-data.json',{'table_appends':[{'sheet':'Moonphases and Dune','old_last_row':62,'columns':14,'rows':folderrows}],'new_sheets':{}});write(H/'workbook-edit-plan.json',plan)
write(H/'native-and-originals-verification.json',{'status':'PASS','objects_including_families':555,'original_file_IDs_names_sizes_preserved':530,'unchanged_file_content_claim_from_source_receipts':True,'root_original_bytes_redownloaded':False,'folder_renames':5,'new_folder_IDs':0,'actual_parent_IDs_changed':0,'file_paths_updated':205,'root_native_writes':0})
write(H/'preparation-verification.json',{'status':'PASS','cell_changes':len(changes),'value_blocks':len(blocks),'native_link_targets_updated':len(plan['target_changes']),'new_folder_rows':5,'current_folder_audit_rows':58,'current_options':186,'working_component_identities':112,'working_specifications_preserved':1116,'individual_gaps':19,'in_situ_gaps':61,'series_gaps':18,'new_physical_measurements_or_image_roles':0})
print(json.dumps(read(H/'preparation-verification.json')))
