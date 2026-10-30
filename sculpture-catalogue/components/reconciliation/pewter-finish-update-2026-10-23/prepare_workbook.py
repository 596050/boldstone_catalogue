"""Extend the current master by two finish rows and scoped current references."""
import collections,importlib.util,json,math,posixpath,re
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());write=lambda p,z:Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
b=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');cross=read(H/'native-current-crosswalk.json');objects=cross['current_objects'];oldpaths=cross['old_path_to_id'];repair=read(H/'source-location-repairs.json');archive={x['file_id']:x['path']for x in repair['archived_originals']};familyurl=repair['current_family_url'];oldfolder=repair['last_known_parent_id'];changes={};forms={};links={};heights={}
new_boundary={'Master Catalogue':195,'Specifications':1125,'Photo Coverage':195,'Listing Resolution':195,'Draft Listings':111,'Selling Details':195,'Missing Pictures':214}
def setcell(sn,c,v):
 if c in b['formulas'][sn]:return
 before=b['values'][sn].get(c,'')
 if before!=v or int(re.search(r'\d+',c)[0])>new_boundary.get(sn,10**9):changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def formula(sn,c,f,expected):forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn].get(c,''),'formula':f,'expected':expected}
def linkcell(sn,c,label,target):
 assert target
 setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def row(sn,r,values):
 for j,v in enumerate(values):
  c=n.column(j)+str(r)
  if isinstance(v,dict):linkcell(sn,c,v['label'],v['target'])
  else:setcell(sn,c,v);links.pop((sn,c),None)
L=lambda target,label:{'label':label,'target':target}
def protected(sn,c):return sn=='Source Specifications'and re.fullmatch('[MN]\\d+',c)or sn=='Fingerprint History'or sn=='Moonphases and Dune'and re.fullmatch('I\\d+',c)
def urlref(u):
 if not isinstance(u,str)or not u.startswith('https://www.dropbox.com/'):return None
 z=urlsplit(u);p=unquote(z.path)
 for r in ['/home','/preview']:
  if p.startswith(r+'/'):
   p=p[len(r):];name=parse_qs(z.query).get('preview',[''])[0];return oldpaths.get((p+('/'+name if name else '')).casefold())
 return None
def current_url(u):
 fid=urlref(u)
 if fid in archive:return archive[fid]
 if fid==oldfolder:return familyurl
 o=objects.get(fid)
 if o:
  p=o['display_path'];z=urlsplit(u);preview=parse_qs(z.query).get('preview')
  if o['object_type']=='file':return 'https://www.dropbox.com/preview'+quote(p,safe='/')
  return 'https://www.dropbox.com/home'+quote(p,safe='/')
 return u
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rs[x.get('{'+n.R+'}id')].get('Target');fid=urlref(u);label=b['values'][sn].get(c,'')
  target=u if protected(sn,c)else current_url(u)
  if not protected(sn,c)and fid in archive:label='Archived original (Dropbox unavailable)';setcell(sn,c,label)
  if not protected(sn,c)and fid==oldfolder:label='Current family; source folder unavailable';setcell(sn,c,label)
  links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
 for c,v in b['values'][sn].items():
  if not protected(sn,c)and isinstance(v,str)and v.startswith('https://www.dropbox.com/')and current_url(v)!=v:setcell(sn,c,current_url(v))
# Current source parent IDs follow the actual file, including the moved old detail.
pairs={'Specifications':[('J','M')],'Components':[('F','I')],'Master Catalogue':[('N','R')],'Photo Coverage':[('D','N'),('G','P'),('J','R')],'Missing Pictures':[('G','J')],'Identity Review':[('G','J'),('L','P')],'Listing Reconciliation':[('M','P')],'Listing Offer Links':[('R','U')],'Listing Issues':[('J','M')],'Listing Resolution':[('R','U')],'Draft Listings':[('I','L')],'Selling Details':[('L','O')]}
for sn,cols in pairs.items():
 for c,v in b['values'][sn].items():
  for im,parent in cols:
   if re.fullmatch(im+r'\d+',c)and int(c[len(im):])>=10:
    oldlink=next((h for h in links.values()if h['sheet']==sn and h['cell']==c),None)
    if not oldlink:continue
    # IDs can be recovered from the original native link before path projection.
    urlid=urlref(oldlink['target'])
    if not urlid:
     for fid,obj in objects.items():
      if oldlink['target']=='https://www.dropbox.com/preview'+quote(obj['display_path'],safe='/'):urlid=fid;break
    if urlid in objects and objects[urlid]['object_type']=='file':setcell(sn,parent+c[len(im):],objects[urlid]['parent_id'])
ids={x['product_id']:i+10 for i,x in enumerate(g['options'])};specrows={x['product_id']:i*6+10 for i,x in enumerate(g['options'])};one='BSI-3635E3DC3434';sand='BSI-C41824131174';new=g['options'][-2:];covmap={x['option_id']:x for x in a['coverage']}
def image_ref(r,label='Image'):
 if not r:return''
 return L(r.get('archived_original')or r['image_url'],'Archived original (Dropbox unavailable)'if r.get('archived_original')else label)
def folder_ref(r):
 if not r:return''
 return L(r.get('current_family_navigation_url')or r['folder_url'],'Current family navigation'if r.get('archived_original')else'Containing folder')
for x in [next(z for z in g['options']if z['product_id']==one)]+new:
 oid=x['product_id'];r=ids[oid];d=specrows[oid];v=x['master_fields'];cr=covmap[oid];ip=cr['individual']['reference'];sr=cr['series'].get('reference');ins=cr['in_situ'].get('reference')
 if oid!=one:
  row('Master Catalogue',r,[oid,x['name'],x['family'],x['canonical_component_id'],*[v[f]['display']for f in v],6,'Six working fields recorded',x['identity_basis'],image_ref(ip,'Owner-added full Pewter image'),folder_ref(ip),L("#'Specifications'!D"+str(d),'Six working fields'),x['file_id'],x['folder_id'],'Custom orientation available','','','Working comparator estimates and policies; actual size, weight, material, fitted fixing and current exact platform offer unverified.','','New Pewter finish; exact Squarespace/Shopify variant unverified','\n'.join(x['source_scopes'])])
 else:
  linkcell('Master Catalogue','N'+str(r),'Owner-added full Pewter image',x['image_url']);linkcell('Master Catalogue','O'+str(r),'Containing folder',x['folder_url']);setcell('Master Catalogue','Q'+str(r),x['file_id']);setcell('Master Catalogue','R'+str(r),x['folder_id']);setcell('Master Catalogue','V'+str(r),'Owner explicitly accepted six qualified working fields for this One Leaf option only. Physical specifications remain unverified. Full individual image available; wider in situ context remains required. Workshop group retained as archived original; native source currently unavailable.')
 for j,f in enumerate(v):
  z=v[f];t=d+j;row('Specifications',t,[oid,x['name'],f,z['display'],z['state'],z['basis'],'\n'.join(z['source_scopes']),z.get('prior_display',''),1,image_ref(ip,'Full Pewter image'),folder_ref(ip),x['file_id'],x['folder_id'],'\n'.join(z.get('proposal_ids',[])),'',oid+'::'+f,1]);heights[('Specifications',t)]=max(132,min(390,18+13*max(math.ceil(len(z['state'])/65),math.ceil(len(z['basis'])/100),math.ceil(len(z['display'])/85))))
 if oid!=one:
  for j,f in enumerate(v):
   key=f'$A{r}&"::{f}"';formula('Master Catalogue',n.column(j+4)+str(r),f'=IF(COUNTIFS(\'Specifications\'!$P$10:$P$1137,{key},\'Specifications\'!$Q$10:$Q$1137,1)=1,INDEX(\'Specifications\'!$D$10:$D$1137,MATCH({key},\'Specifications\'!$P$10:$P$1137,0)),"Working detail missing, unaccepted or duplicated")',v[f]['display'])
  formula('Master Catalogue','K'+str(r),f"=COUNTIFS('Specifications'!$A$10:$A$1137,A{r},'Specifications'!$Q$10:$Q$1137,1)",6);formula('Master Catalogue','L'+str(r),f'=IF(K{r}=6,"Six working fields recorded","Working details incomplete")','Six working fields recorded')
 row('Photo Coverage',r,[oid,x['name'],cr['individual']['status'],image_ref(ip,'Owner-added full image'),folder_ref(ip),cr['in_situ']['status'],image_ref(ins,'In situ reference'),folder_ref(ins),cr['series']['status'],image_ref(sr,'Pair / series image'),folder_ref(sr),'Complete owner-added Pewter image; original pixels retained. Creation origin and actual physical cast unverified. '+('Prior workshop group source unavailable in current Dropbox; archived original and owner position binding retained.'if oid==one else cr['series']['basis']),ip['file_id'],ip['folder_id'],ins['file_id']if ins else'',ins['folder_id']if ins else'',sr['file_id']if sr else'',sr['folder_id']if sr else'',cr['scope'],cr['scene_origin'],cr.get('owner_review',''),'Family / series relevant'if cr['series_required']else'Optional / no fixed set'])
 heights[('Master Catalogue',r)]=192;heights[('Photo Coverage',r)]=180
 if oid==one:setcell('Selling Details','J'+str(r),v['Individual price']['basis'])
 if oid==one:
  for sn,ic,fc,fidc,pidc in [('Selling Details','L','M','N','O'),('Listing Resolution','R','S','T','U'),('Draft Listings','I','J','K','L')]:
   rr=next((int(c[1:])for c,value in b['values'][sn].items()if re.fullmatch(r'A\d+',c)and value==oid),None)
   if rr is not None:
    linkcell(sn,ic+str(rr),'Owner-added full Pewter image',x['image_url']);linkcell(sn,fc+str(rr),'Containing folder',x['folder_url']);setcell(sn,fidc+str(rr),x['file_id']);setcell(sn,pidc+str(rr),x['folder_id'])
 if oid!=one:
  review=next(z for z in g['current_listing_resolution_details']['entries']if z['product_id']==oid);draft=review['draft_listing'];nextaction=x['current_listing_resolution']['next_action']
  row('Listing Resolution',r,[oid,x['name'],'New current option; platform verification pending',0,0,0,'','','','','','',draft['proposed_sku'],'','','',nextaction,image_ref(ip,'Full Pewter image'),folder_ref(ip),x['file_id'],x['folder_id'],'New owner-added finish; exact current native variant and physical configuration unverified.','','No prior exact individual record asserted']);heights[('Listing Resolution',r)]=156
  dr=112+len([z for z in new if ids[z['product_id']]<r]);row('Draft Listings',dr,[oid,x['name'],'Individual option draft',draft['proposed_sku'],draft['proposed_product_group_id'],draft['proposed_variant_reference'],x['sale_unit'],L("#'Specifications'!D"+str(d),'Six working fields'),image_ref(ip,'Full Pewter image'),folder_ref(ip),x['file_id'],x['folder_id'],'New current option; platform verification pending','\n'.join(review['remaining_evidence_gaps']),draft['activation_condition'],draft['media_condition'],'Draft only; not created','']);heights[('Draft Listings',dr)]=168
  row('Selling Details',r,[oid,x['name'],v['Individual price']['display'],v['Availability']['display'],'estimate','per individual panel','1–2 weeks','','',v['Individual price']['basis'],'',image_ref(ip,'Full Pewter image'),folder_ref(ip),x['file_id'],x['folder_id'],'Working catalogue only; no native listing-readiness upgrade','Comparator price estimate; made-to-order1–2weeks is owner policy; stock/capacity unverified.']);heights[('Selling Details',r)]=168
  for c,ix in [('C',9),('D',10)]:formula('Selling Details',c+str(r),f"=VLOOKUP($A{r},'Master Catalogue'!$A$10:$Y$197,{ix},FALSE)",v['Individual price'if c=='C'else'Availability']['display'])
  formula('Selling Details','G'+str(r),f'=IF(ISNUMBER(SEARCH("1–2 weeks",D{r})),"1–2 weeks",IF(ISNUMBER(SEARCH("1 week",D{r})),"1 week","Check source policy"))','1–2 weeks')
# Note archived availability in the active Sandstone and series views.
for sn,keycol in [('Master Catalogue','A'),('Photo Coverage','A')]:
 r=ids[sand];col='V'if sn=='Master Catalogue'else'L';before=b['values'][sn].get(col+str(r),'');setcell(sn,col+str(r),before+'\nCurrent Dropbox lookup cannot resolve the historical Sandstone detail or workshop group. Archived originals and their historical IDs are retained. Folder link is current family navigation.');heights[(sn,r)]=max(180,heights.get((sn,r),0))
# Recreate current action values in their stable order; append only the three new tasks.
prior_actions=read(H/'inputs/audit.before')['missing_pictures']
for r,x in enumerate(a['missing_pictures'],10):
 if r<215 and x==prior_actions[r-10]:continue
 ref=x['reference'];row('Missing Pictures',r,[x['priority'],x['option_id'],x['name'],x['role'],x['action_type'],x['action'],image_ref(ref,'Available reference'),folder_ref(ref),ref['file_id'],ref['folder_id'],x['scope'],x['qualification'],x.get('owner_response',''),x['status']]);heights[('Missing Pictures',r)]=180 if x['option_id']==one else 132
# Extend every affected current option/field range while retaining source snapshots.
for sn,fs in b['formulas'].items():
 for c,f in fs.items():
  ff=re.sub(r'(:\$?[A-Z]+)\$?195\b',lambda m:m.group(1)+('$'if'$195'in m.group(0)else'')+'197',f)
  ff=re.sub(r'(:\$?[A-Z]+)\$?1125\b',lambda m:m.group(1)+('$'if'$1125'in m.group(0)else'')+'1137',ff)
  if sn=='Missing Pictures':ff=ff.replace(':E214',':E217').replace(':N214',':N217')
  if sn=='Draft Listings':ff=ff.replace(':C111',':C113')
  if ff!=f and(sn,c)not in forms:formula(sn,c,ff,b['values'][sn][c])
for r in range(1126,1138):formula('Specifications','Q'+str(r),f'=IF(AND(I{r}=1,COUNTBLANK(D{r})=0,COUNTIFS($P$10:$P$1137,P{r})=1),1,0)',1)
expected={('Master Catalogue','B4'):188,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):170,('Photo Coverage','F4'):116,('Photo Coverage','B5'):18,('Missing Pictures','B4'):98,('Missing Pictures','F4'):54,('Listing Resolution','D5'):104,('Draft Listings','B4'):101,('Selling Details','B4'):188,('Selling Details','D4'):187,('Selling Details','F4'):187}
for key,v in expected.items():
 if key in forms:forms[key]['expected']=v
 else:formula(*key,b['formulas'][key[0]][key[1]],v)
for i,c in enumerate(g['components'],10):
 if c['component_id']in ['BC-AC-TWO','BC-EG-1']:forms[('Components','D'+str(i))]['expected']=c['option_count']
for c in list(changes):
 if c in forms:changes.pop(c)
notes={'Master Catalogue':'188 current individual finish/size options across112 working component identities. One Leaf Pewter working details explicitly accepted with estimates retained. Two new Pewter finish options use separate comparator estimates.','Photo Coverage':'188 current options.170 complete individual references;18 individual/identity entries remain, comprising17 separate photograph requests and one deferred Frozen Fish identity.63 wider in situ gaps and18 series gaps. Archived Acanthus source-location repairs are tracked separately.','Missing Pictures':'208 current action rows:99 required actions,54 optional references and55 resolved actions. The new One Leaf Pewter full image closes one individual request. Two new Pewter finish options add wider in situ requests.','Listing Resolution':'188 current options. Two owner-added Pewter finish options await native verification; historical source inventories retain their dated scope.104 local draft/custom scopes, with no platform execution.','Draft Listings':'101 proposed individual-option drafts and3 custom/unlisted Wall Circle scopes. Two new Pewter finish proposals remain subject to current native inventory and physical/order checks. No platform listings created.','Selling Details':'188 current options:187 estimated prices/ranges plus the specific Moon Crater Phase4 Verdigris/Rust owner price. One Leaf Pewter estimate explicitly accepted. The two new Pewter finish estimates retain their own component comparisons.'}
for sn,text in notes.items():setcell(sn,'A3',text);heights[(sn,3)]=60
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
def blocks(items,kind):
 result=[];group=collections.defaultdict(list)
 for x in items:group[(x['sheet'],re.match('[A-Z]+',x['cell'])[0])].append(x)
 for(sn,col),rows in group.items():
  rows.sort(key=lambda x:int(x['cell'][len(col):]));runs=[]
  for x in rows:
   if runs and int(x['cell'][len(col):])!=int(runs[-1]['cell'][len(col):])+1:result.append({'sheet':sn,'range':runs[0]['cell']+':'+runs[-1]['cell'],kind:[[z['value'if kind=='values'else'formula']]for z in runs]});runs=[]
   runs.append(x)
  if runs:result.append({'sheet':sn,'range':runs[0]['cell']+':'+runs[-1]['cell'],kind:[[z['value'if kind=='values'else'formula']]for z in runs]})
 return result
appends=[{'sheet':sn,'old_last':last,'rows':rows,'columns':cols}for sn,last,rows,cols in [('Master Catalogue',195,2,25),('Specifications',1125,12,17),('Photo Coverage',195,2,22),('Listing Resolution',195,2,24),('Draft Listings',111,2,18),('Selling Details',195,2,17),('Missing Pictures',214,3,14)]]
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks(changes.values(),'values'),'formula_blocks':blocks(forms.values(),'formulas'),'hyperlinks':list(links.values()),'row_heights':[{'sheet':sn,'row':r,'height':v}for(sn,r),v in heights.items()],'table_appends':appends,'new_sheets':{},'baseline_ranges':[['Master Catalogue','A2:J4','baseline-summary'],['Specifications','C'+str(specrows[one])+':F'+str(specrows[one]+1),'baseline-one-leaf-working-specs']],'preview_ranges':[['Master Catalogue','A2:J4','01-current-summary'],['Master Catalogue','A196:D197','02-new-pewter-options'],['Specifications','C'+str(specrows[one])+':F'+str(specrows[one]+1),'03-one-leaf-qualified-acceptance'],['Photo Coverage','A196:L197','04-new-pewter-photo-roles'],['Selling Details','A196:G197','05-new-pewter-working-prices'],['Photo Coverage','A2:L5','06-current-photo-summary']],'summary_expected':[{'sheet':k[0],'cell':k[1],'value':v}for k,v in expected.items()],'one_leaf_master_row':ids[one],'one_leaf_spec_row':specrows[one],'expected_original_sheet_count':28,'expected_formula_count':sum(map(len,b['formulas'].values()))+34,'preserved_source_snapshot_sheet':'Listing Reconciliation'}
write(H/'workbook-edit-plan.json',plan)
print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'formula_changes':len(forms),'hyperlinks':len(links),'table_appends':len(appends),'expected_formula_count':plan['expected_formula_count']}))
