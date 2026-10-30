"""Prepare minimal native changes with the Specifications sheet as value owner."""
import copy,importlib.util,json,math,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
from urllib.parse import quote,unquote,urlsplit,urlunsplit
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
def write(p,z):Path(p).write_text(json.dumps(z,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before')
g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');opts={x['product_id']:x for x in g['options']};imgs={x['product_id']:x for x in read(H/'image-updates.json')};overlays=[read(H/'inputs'/f'{x}_overlay.before')for x in ['moonspirals','echo','decowaves']];prefixes=sorted([p for o in overlays for p in o['prefix_maps']],key=lambda p:len(p['old_path']),reverse=True)
def path(s):
 for p in prefixes:
  if s==p['old_path']or s.startswith(p['old_path']+'/'):return p['current_path']+s[len(p['old_path']):]
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
changes={};links={};oldtargets={};caches={};heights={}
def setcell(sn,c,value):
 assert c not in b['formulas'][sn],(sn,c);before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def value(sn,c):return changes.get((sn,c),{}).get('value',b['values'][sn].get(c,''))
def linkcell(sn,c,url,label=None):
 assert(sn,c)in links,(sn,c)
 if label is not None:setcell(sn,c,label);links[(sn,c)]['label']=label
 links[(sn,c)]['target']=url
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rs={x.get('Id'):x for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for h in z['root'].findall('.//'+n.q('hyperlink')):
  c=h.get('ref');url='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target');oldtargets[(sn,c)]=url
  hist=sn=='Source Specifications'and re.fullmatch(r'[MN]\d+',c);links[(sn,c)]={'sheet':sn,'cell':c,'target':url if hist else ref(url),'label':b['values'][sn].get(c,'')}
 for c,v in b['values'][sn].items():
  if sn=='Source Specifications'and re.fullmatch(r'[MN]\d+',c):continue
  after=ref(v)
  if after!=v:setcell(sn,c,after)
for c,oid in b['values']['Specifications'].items():
 if not re.fullmatch(r'A\d+',c)or oid not in opts:continue
 rn=c[1:];field=b['values']['Specifications']['C'+rn]
 if field in ['Individual price','Availability']:
  f=opts[oid]['master_fields'][field]
  for col,key in [('D','display'),('E','state'),('F','basis')]:setcell('Specifications',col+rn,f[key])
  if oid!='BSI-46F6DB226213':setcell('Specifications','O'+rn,'')
 if oid in imgs:
  r=imgs[oid]['reference'];linkcell('Specifications','J'+rn,r['image_url'],'Owner-accepted standalone image');linkcell('Specifications','K'+rn,r['folder_url']);setcell('Specifications','L'+rn,r['file_id']);setcell('Specifications','M'+rn,r['folder_id'])
for c,oid in b['values']['Master Catalogue'].items():
 if not re.fullmatch(r'A\d+',c)or oid not in opts:continue
 rn=c[1:]
 for col,field in [('I','Individual price'),('J','Availability')]:
  expected=opts[oid]['master_fields'][field]['display']
  if b['values']['Master Catalogue'][col+rn]!=expected:caches[('Master Catalogue',col+rn)]={'sheet':'Master Catalogue','cell':col+rn,'formula':b['formulas']['Master Catalogue'][col+rn],'expected':expected}
 if oid in imgs:
  r=imgs[oid]['reference'];linkcell('Master Catalogue','N'+rn,r['image_url'],'Owner-accepted standalone image');linkcell('Master Catalogue','O'+rn,r['folder_url']);setcell('Master Catalogue','Q'+rn,r['file_id']);setcell('Master Catalogue','R'+rn,r['folder_id'])
for sn,imgcol,foldercol,filecol,parentcol in [('Draft Listings','I','J','K','L'),('Listing Resolution','R','S','T','U')]:
 for c,oid in b['values'][sn].items():
  if not re.fullmatch(r'A\d+',c)or oid not in imgs:continue
  rn=c[1:];r=imgs[oid]['reference'];linkcell(sn,imgcol+rn,r['image_url'],'Owner-accepted standalone image');linkcell(sn,foldercol+rn,r['folder_url']);setcell(sn,filecol+rn,r['file_id']);setcell(sn,parentcol+rn,r['folder_id'])
for c,oid in b['values']['Photo Coverage'].items():
 if not re.fullmatch(r'A\d+',c)or oid not in imgs:continue
 rn=c[1:];r=imgs[oid]['reference'];setcell('Photo Coverage','C'+rn,'Available');linkcell('Photo Coverage','D'+rn,r['image_url'],'Owner-accepted standalone image');linkcell('Photo Coverage','E'+rn,r['folder_url']);setcell('Photo Coverage','M'+rn,r['file_id']);setcell('Photo Coverage','N'+rn,r['folder_id'])
 setcell('Photo Coverage','L'+rn,'Complete standalone listing image accepted by owner. Photographic/generation provenance is unverified; in-situ and series requirements are unchanged.');setcell('Photo Coverage','U'+rn,'Use these as standalone listing images — owner,22 October2026.')
for c,oid in b['values']['Missing Pictures'].items():
 if not re.fullmatch(r'B\d+',c)or oid not in imgs:continue
 rn=c[1:]
 if b['values']['Missing Pictures']['D'+rn]!='Individual':continue
 t=next(x for x in a['missing_pictures']if x['option_id']==oid and x['role']=='Individual');r=t['reference']
 for col,key in [('F','action'),('I','file_id'),('J','folder_id'),('K','scope'),('L','qualification'),('M','owner_response'),('N','status')]:setcell('Missing Pictures',col+rn,r[key]if key in ['file_id','folder_id']else t[key])
 linkcell('Missing Pictures','G'+rn,r['image_url'],'Accepted standalone image');linkcell('Missing Pictures','H'+rn,r['folder_url'])
for c,oid in b['values']['Draft Listings'].items():
 if not re.fullmatch(r'A\d+',c)or oid not in opts:continue
 rn=c[1:];setcell('Draft Listings','H'+rn,'\n'.join(field+': '+f['display']for field,f in opts[oid]['master_fields'].items()))
 if oid in imgs:setcell('Draft Listings','P'+rn,'Use the owner-accepted complete standalone image, retaining unverified photographic/generation provenance. In-situ and series requirements remain separate. No platform match or publication is inferred.')
setcell('Photo Coverage','A3','186 current options. Three owner-accepted complete listing images close individual roles only; provenance remains unverified.19 individual gaps remain:18 separate images and1 deferred identity.61 in-situ and18 series gaps remain. No crops created.')
for c,v in [('B4',167),('B5',19)]:caches[('Photo Coverage',c)]={'sheet':'Photo Coverage','cell':c,'formula':b['formulas']['Photo Coverage'][c],'expected':v}
caches[('Missing Pictures','B4')]={'sheet':'Missing Pictures','cell':'B4','formula':b['formulas']['Missing Pictures']['B4'],'expected':97}
setcell('Moonphases and Dune','A2','Current approved folder reference updates')
setcell('Moonphases and Dune','A3','49 approved folder updates: Moonphases,Dune Ripple,Deco Palm/Spiral,Moonspirals,Echo Sound andDecowaves. Stable native IDs retained; folder changes do not create components or change specifications.')
folderrows=[];L=lambda label,url:{'label':label,'target':url}
for o in overlays:
 for p in o['prefix_maps']:
  children=[x for x in o['objects']if x['object_type']=='file'and x['current_parent_id']==p['file_id']and re.search(r'\.(jpe?g|png|webp)$',x['current_name'],re.I)];im=children[0]if children else None
  folderrows.append([Path(o['family']['path']).name,p['file_id'],p['old_name'],p['current_name'],L('Current folder',p['current_native_url']),L('Existing example photograph',im['current_native_url'])if im else'',im['file_id']if im else'',p['file_id'],p['old_path'],p['current_path'],p['direct_file_count'],p.get('kind','arrangement/context'),'Folder IDs and file basenames retained','No specification or image-role change from renaming'])
formchanges=[{'sheet':'Moonphases and Dune','cell':c,'formula':f,'expected':expected}for c,f,expected in [('B4','=COUNTA(B10:B58)',49),('D4','=COUNTIF(A10:A58,"Dune Ripple")',22),('F4','=COUNTIF(A10:A58,"Moonphases")',10)]]
selling=[];packet={x['product_id']:x for x in read(H/'inputs/commercial_packet.before')['entries']}
for x in g['options']:
 p=packet[x['product_id']];d=x['selling_details'];selling.append([x['product_id'],x['name'],x['master_fields']['Individual price']['display'],x['master_fields']['Availability']['display'],d['price_status'],d['sale_unit'],'1 week'if x['product_id']=='BSI-46F6DB226213'else'1–2 weeks',p['before_master_fields']['Individual price']['display'],p['before_master_fields']['Availability']['display'],p['after']['Individual price']['basis'],d.get('included_or_excluded_scope',''),L('Example / comparison image',x['image_url'])if x['image_url']else'No bound individual image',L('Containing folder',x['folder_url'])if x['folder_url']else'No bound folder',x['file_id'],x['folder_id'],'Deferred identity; not listing-ready'if d['identity_deferred']else'Working catalogue only; no native listing-readiness upgrade','Specific earlier owner policy retained'if p.get('retain_current_commercial_fields_exactly')else'Price is an authorized estimate; made-to-order and1–2-week policy is owner instructed; physical stock/capacity is unverified.'])
sheet={'title':'Current individual working prices and selling policies','note':'185 estimated prices/ranges and one specific owner-accepted price. Current values are linked to the master; source prices and qualifiers are preserved separately.','headers':['Option ID','Individual sculpture / option','Current working price','Current availability policy','Price status','Sale unit','Lead-time class','Earlier working price','Earlier availability','Price selection and source basis','Included / excluded scope','Example image','Containing folder','Dropbox file ID','Dropbox folder ID','Listing readiness scope','Policy qualification'],'widths':[25,54,75,96,29,35,24,90,100,105,90,27,27,35,35,76,100],'rows':selling}
write(H/'workbook-data.json',{'table_appends':[{'sheet':'Moonphases and Dune','old_last_row':44,'columns':14,'rows':folderrows}],'new_sheets':{'Selling Details':sheet}})
for(sn,c),x in changes.items():
 if(sn,c)in links:links[(sn,c)]['label']=x['value']
 if not isinstance(x['value'],str)or c=='A3':continue
 col=re.match('[A-Z]+',c)[0];ci=0
 for ch in col:ci=ci*26+ord(ch)-64
 rn=int(c[len(col):]);root=b['sheets'][sn]['root'];width=next((float(z.get('width'))for z in root.findall('.//'+n.q('col'))if int(z.get('min'))<=ci<=int(z.get('max'))),13);before=float(next(z for z in root.find(n.q('sheetData'))if z.get('r')==str(rn)).get('ht',15));height=sum(max(1,math.ceil(len(t)/max(8,width*.9)))for t in x['value'].split('\n'))*13+12
 if height>before:
  if height>409 and sn=='Draft Listings':height=409
  assert height<=409,(sn,c,height);heights[(sn,rn)]=max(heights.get((sn,rn),before),height)
# Dense blocks on the owning detail sheet avoid a recalc after each field.
blocks=[];covered=set()
for sn,start,end,r1,r2 in [('Specifications','D','F',10,1125),('Specifications','O','O',10,1125),('Draft Listings','H','H',10,111)]:
 cols=[n.column(j)for j in range(26)if start<=n.column(j)<=end and len(n.column(j))==len(start)]
 vals=[]
 for row in range(r1,r2+1):
  vals.append([value(sn,c+str(row))for c in cols]);covered|={(sn,c+str(row))for c in cols};assert all(c+str(row)not in b['formulas'][sn]for c in cols)
 blocks.append({'sheet':sn,'range':f'{start}{r1}:{end}{r2}','values':vals})
groups={}
for k,x in changes.items():
 if k not in covered:groups.setdefault((k[0],re.match('[A-Z]+',k[1])[0]),[]).append(x)
for(sn,col),items in groups.items():
 items.sort(key=lambda x:int(x['cell'][len(col):]));run=[]
 for x in items:
  if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[q['value']]for q in run]});run=[]
  run.append(x)
 if run:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[q['value']]for q in run]})
leafrow=next(int(c[1:])for c,v in b['values']['Photo Coverage'].items()if re.fullmatch(r'A\d+',c)and v=='BSI-B42C439049D7')
plan={'cell_changes':list(changes.values()),'value_blocks':blocks,'formula_changes':formchanges,'formula_cache_changes':list(caches.values()),'hyperlinks':list(links.values()),'target_changes':[{'sheet':sn,'cell':c,'before':oldtargets[(sn,c)],'after':v['target']}for(sn,c),v in links.items()if oldtargets[(sn,c)]!=v['target']],
 'row_heights':[{'sheet':sn,'row':r,'height':v}for(sn,r),v in heights.items()],'old_sheet_count':27,'new_sheet_count':1,'expected_formula_count':3356,'expected_native_links':len(links)+sum(isinstance(v,dict)for row in folderrows+selling for v in row),
 'baseline_ranges':[['Master Catalogue','H84:J85','baseline-fingerprint-selling-details'],['Photo Coverage',f'A{leafrow}:E{leafrow}','baseline-leaf-detail-only']],
 'preview_ranges':[['Master Catalogue','H84:J85','01-fingerprint-current-selling-details'],['Photo Coverage','A2:H5','02-current-image-counts'],['Photo Coverage',f'A{leafrow}:E{leafrow}','03-accepted-leaf-individual-image'],['Selling Details','A2:H4','04-selling-summary'],['Selling Details','A9:G11','05-linked-current-selling-values'],['Moonphases and Dune','A2:H4','06-fortynine-folder-summary'],['Moonphases and Dune','A45:F47','07-new-folder-links'],['Selling Details','L91:Q91','08-deferred-frozen-fish-no-binding']]}
write(H/'workbook-edit-plan.json',plan);print(json.dumps({'cell_changes':len(changes),'value_blocks':len(blocks),'native_targets_changed':len(plan['target_changes']),'new_folder_rows':14,'new_selling_rows':186,'formula_count':3356,'native_links':plan['expected_native_links']}))
