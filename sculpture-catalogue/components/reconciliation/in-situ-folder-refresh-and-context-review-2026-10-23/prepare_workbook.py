import json,importlib.util,posixpath,re,collections
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/audit.before');current=read(H/'current-native-reference-map.json');objects=current['current_objects'];oldpaths=current['old_path_to_id'];replacements=current['byte_identical_backup_replacements'];changes={};links={};forms={};heights={};out=B/'outputs/in-situ-folder-refresh-and-context-review-2026-10-23'
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
def urlpath(u):
 if not isinstance(u,str)or not u.startswith('https://www.dropbox.com/'):return None
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0];return p+('/'+name if name else '')
def urlid(u):return oldpaths.get((urlpath(u)or'').casefold())
def newurl(u):
 fid=replacements.get(urlid(u),urlid(u))
 if fid not in objects:return u
 x=objects[fid]
 if(urlpath(u)or'').casefold()==x['display_path'].casefold():return u
 return'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
def setcell(sn,c,v):
 if c in b['formulas'][sn]:return
 before=b['values'][sn].get(c,'')
 if before!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def rowof(sn,oid):return next((int(c[1:])for c,v in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and v==oid),None)
def imageurl(x):return'https://www.dropbox.com/preview'+quote(x['display_path'],safe='/')
def folderurl(x):return'https://www.dropbox.com/home'+quote(posixpath.dirname(x['display_path']),safe='/')
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+n.R+'}id')];links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u if protected(sn,c)else newurl(u)}
 for c,v in b['values'][sn].items():
  if not protected(sn,c)and isinstance(v,str)and v.startswith('https://www.dropbox.com/')and newurl(v)!=v:setcell(sn,c,newurl(v))
pairs={'Specifications':[('J','K','L','M')],'Components':[('F','G','H','I')],'Master Catalogue':[('N','O','Q','R')],'Photo Coverage':[('D','E','M','N'),('G','H','O','P'),('J','K','Q','R')],'Missing Pictures':[('G','H','I','J')],'Identity Review':[('G','H','I','J'),('L','M','O','P')],'Listing Reconciliation':[('M','N','O','P')],'Listing Offer Links':[('R','S','T','U')],'Listing Issues':[('J','K','L','M')],'Listing Resolution':[('R','S','T','U')],'Draft Listings':[('I','J','K','L')],'Selling Details':[('L','M','N','O')]}
for sn,groups in pairs.items():
 for im,folder,fc,pc in groups:
  for cell,sourceid in b['values'][sn].items():
   if not re.fullmatch(fc+'[0-9]+',cell)or int(cell[len(fc):])<10:continue
   fid=replacements.get(sourceid,sourceid)
   if fid not in objects or objects[fid]['object_type']!='file':continue
   r=cell[len(fc):];x=objects[fid];setcell(sn,fc+r,fid);setcell(sn,pc+r,x['parent_id'])
   for col,target,label in [(im,imageurl(x),'Byte-identical backup reference'if sourceid in replacements else b['values'][sn].get(im+r,'Image')),(folder,folderurl(x),'Backup containing folder'if sourceid in replacements else b['values'][sn].get(folder+r,'Containing folder'))]:
    key=(sn,col+r);previous=links.get(key,{}).get('target');target=previous if previous and(urlpath(previous)or'').casefold()==(urlpath(target)or'').casefold()else target
    if sourceid in replacements or previous!=target:linkcell(sn,col+r,label,target)
for cell,sourceid in b['values']['Source Specifications'].items():
 if not re.fullmatch('J[0-9]+',cell):continue
 fid=replacements.get(sourceid,sourceid)
 if fid in objects and objects[fid]['object_type']=='file':
  rr=cell[1:];x=objects[fid]
  for col,target in [('H',imageurl(x)),('I',folderurl(x))]:
   before=links.get(('Source Specifications',col+rr),{}).get('target')
   if(urlpath(before)or'').casefold()!=(urlpath(target)or'').casefold():linkcell('Source Specifications',col+rr,b['values']['Source Specifications'].get(col+rr,'Current reference'),target)
cov={x['option_id']:x for x in a['coverage']};detail={x['product_id']:x for x in g['current_listing_resolution_details']['entries']};bindings=read(H/'preparation-verification.json')['imported_approvals']
for item in bindings:
 oid=item['option_id'];row=rowof('Master Catalogue',oid);c=cov[oid];r=c['in_situ'if item['role']=='In situ'else'series']['reference'];basis=item['basis'];note=b['values']['Master Catalogue']['V'+str(row)].split('\nPhoto review:')[0]
 setcell('Master Catalogue','V'+str(row),note+'\nPhoto review: individual '+c['individual']['status']+'; in situ '+c['in_situ']['status']+'; series '+c['series']['status']+'.\n'+basis);heights[('Master Catalogue',row)]=210
 if item['role']=='In situ':
  setcell('Photo Coverage','F'+str(row),'Available');linkcell('Photo Coverage','G'+str(row),'Owner-accepted in situ reference',r['image_url']);linkcell('Photo Coverage','H'+str(row),'Containing folder',r['folder_url']);setcell('Photo Coverage','O'+str(row),r['file_id']);setcell('Photo Coverage','P'+str(row),r['folder_id']);linkcell('Master Catalogue','T'+str(row),'Owner-accepted in situ reference',r['image_url']);linkcell('Master Catalogue','U'+str(row),'Containing folder',r['folder_url'])
 else:
  setcell('Photo Coverage','I'+str(row),'Available');linkcell('Photo Coverage','J'+str(row),'Matched Bronze series pair',r['image_url']);linkcell('Photo Coverage','K'+str(row),'Containing folder',r['folder_url']);setcell('Photo Coverage','Q'+str(row),r['file_id']);setcell('Photo Coverage','R'+str(row),r['folder_id'])
 setcell('Photo Coverage','L'+str(row),basis);linkcell('Photo Coverage','U'+str(row),'Context binding and evidence',str(out/'imported-approvals.html')+'#'+oid);heights[('Photo Coverage',row)]=210
 for sn,cols in [('Draft Listings',{'N':'\n'.join(detail[oid]['remaining_evidence_gaps']),'P':detail[oid]['draft_listing']['media_condition']}if oid in detail and detail[oid].get('draft_listing')else{}),('Listing Resolution',{'V':b['values']['Listing Resolution'].get('V'+str(row),'')+'\nCurrent media: '+basis})]:
  rr=rowof(sn,oid)
  if rr is not None:
   for col,value in cols.items():setcell(sn,col+str(rr),value)
   heights[(sn,rr)]=240
for i,(x,y)in enumerate(zip(a['missing_pictures'],old['missing_pictures']),10):
 if x==y:continue
 r=x['reference'];vals=[x['priority'],x['option_id'],x['name'],x['role'],x['action_type'],x['action'],b['values']['Missing Pictures'].get('G'+str(i),'Reference'),'Containing folder',r['file_id'],r['folder_id'],x['scope'],x['qualification'],x.get('owner_response',''),x['status']]
 for j,v in enumerate(vals):setcell('Missing Pictures',n.column(j)+str(i),v)
 linkcell('Missing Pictures','G'+str(i),'Current qualified reference',r['image_url']);linkcell('Missing Pictures','H'+str(i),'Containing folder',r['folder_url'])
 if x['status']=='Resolved'and y['status']=='Open':heights[('Missing Pictures',i)]=210
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):11,('Photo Coverage','D4'):135,('Photo Coverage','F4'):118,('Missing Pictures','B4'):70,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54}
for(sn,c),v in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':v}
notes={'Master Catalogue':'188 individual options across112 working component identities. Current links/actual parents refreshed, seven in situ bindings and two Bronze series bindings added. Acanthus backup lineage is explicit; physical/platform qualifications retained.','Photo Coverage':'177 complete individual images;11 technical gaps, including9 accepted group/combined exceptions and2 open individual/identity actions. Current context gaps:53 in situ and16 series. Seven in situ approvals and two Bronze series associations imported.','Missing Pictures':'208 retained action rows:71 required open actions,54 optional and83 resolved. Acanthus Sandstone separate photograph and Frozen Fish legacy identity remain open. Context gaps:53 in situ and16 series.','Lava Moon Folders':'White1LEFT/2CENTRE/3RIGHT in each repeated pool-room triptych: owner accepts the whole scene for all three White panels. Corresponding White PNGs remain design-only references for Sandstone; Sandstone group remains finish evidence. Creation origin and physical provenance remain unverified.'}
for sn,text in notes.items():setcell(sn,'A3',text);heights[(sn,3)]=66
ar=rowof('Master Catalogue','BSI-C41824131174');setcell('Master Catalogue','V'+str(ar),'Historical Sandstone detail source ID no longer resolves in current lookup. A byte-identical backup copy with its own live ID/actual parent is now linked; original IDs retained in source history. Detail-only coverage remains. Workshop group BACK-CENTRE candidate awaits owner listing-reference choice; no standalone Sandstone image verified.');heights[('Master Catalogue',ar)]=210
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
lav=rowof('Photo Coverage','BSI-7357A558C9E8');sp=rowof('Photo Coverage','BSI-718DFFB7EC5D');lf=rowof('Master Catalogue','BSI-87908C8439B3')
# Group adjacent edited cells into column blocks while keeping the source workbook intact.
def blocks():
 groups=collections.defaultdict(list);result=[]
 for x in changes.values():groups[(x['sheet'],re.match('[A-Z]+',x['cell'])[0])].append(x)
 for(sn,col),xs in groups.items():
  run=[]
  for x in sorted(xs,key=lambda z:int(z['cell'][len(col):])):
   if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:result.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[v['value']]for v in run]});run=[]
   run.append(x)
  if run:result.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[v['value']]for v in run]})
 return result
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks(),'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':sn,'row':r,'height':v}for(sn,r),v in heights.items()],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'baseline_ranges':[['Photo Coverage','A2:F5','baseline-photo-summary'],['Photo Coverage','F'+str(lav)+':L'+str(lav),'baseline-lava-context']],'preview_ranges':[['Photo Coverage','A2:F5','01-current-photo-summary'],['Photo Coverage','F'+str(lav)+':L'+str(lav),'02-lava-pool-context'],['Photo Coverage','I'+str(sp)+':L'+str(sp),'03-bronze-series'],['Master Catalogue','N'+str(ar)+':V'+str(ar),'04-acanthus-backup-lineage'],['Missing Pictures','A2:N4','05-current-actions']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'links':len(links),'value_blocks':len(plan['value_blocks']),'in_situ_available':135,'series_available':118,'required_find_capture':70}))
