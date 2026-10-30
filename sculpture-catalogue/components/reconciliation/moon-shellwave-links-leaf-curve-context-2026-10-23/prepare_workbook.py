import collections,importlib.util,json,posixpath,re
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
b=v.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');olda=read(H/'inputs/audit.before');nm=read(H/'current-native-reference-map.json');objects=nm['current_objects'];oldpaths=nm['old_path_to_id'];out=B/'outputs/moon-shellwave-links-leaf-curve-context-2026-10-23';oldout=B/'outputs/four-queued-links-and-strata-owner-context-2026-10-23';changes={};links={};forms={}
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
scoped_ids=set(read(H/'path-refresh-scope.json')['changed_ids'])
def currenturl(u):
 if not isinstance(u,str)or not u.startswith('https://www.dropbox.com/'):return u
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0];p+='/'+name if name else'';fid=oldpaths.get(p.casefold())
 if fid not in objects or fid not in scoped_ids:return u
 x=objects[fid]
 if p.casefold()==x['display_path'].casefold():return u
 return'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
def setcell(sn,c,value):
 if c in b['formulas'][sn]:return
 before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def rowof(sn,oid):return next((int(c[1:])for c,x in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and x==oid),None)
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
  if not protected(sn,c):u=currenturl(u).replace(str(oldout),str(out))
  links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u}
 for c,x in b['values'][sn].items():
  if not protected(sn,c)and isinstance(x,str)and x.startswith('https://www.dropbox.com/')and currenturl(x)!=x:setcell(sn,c,currenturl(x))
oid='BSI-CF0CC1EB8F96';row=rowof('Master Catalogue',oid);r=str(row);c=next(x for x in a['coverage']if x['option_id']==oid);ref=c['in_situ']['reference'];basis=c['in_situ']['basis'];details=next(x for x in g['current_listing_resolution_details']['entries']if x['product_id']==oid)
setcell('Photo Coverage','F'+r,'Available');linkcell('Photo Coverage','G'+r,'Owner-accepted outdoor display',ref['image_url']);linkcell('Photo Coverage','H'+r,'Actual containing folder',ref['folder_url']);setcell('Photo Coverage','O'+r,ref['file_id']);setcell('Photo Coverage','P'+r,ref['folder_id']);setcell('Photo Coverage','L'+r,basis);linkcell('Photo Coverage','U'+r,'Owner outdoor-display approval',str(out/'imported-approvals.html')+'#'+oid)
linkcell('Master Catalogue','T'+r,'Owner-accepted outdoor display',ref['image_url']);linkcell('Master Catalogue','U'+r,'Actual containing folder',ref['folder_url']);setcell('Master Catalogue','V'+r,b['values']['Master Catalogue']['V'+r].split('\nPhoto review:')[0]+'\nPhoto review: individual Available; in situ Available; series Optional / no fixed set.\n'+basis)
rr=rowof('Listing Resolution',oid)
if rr:setcell('Listing Resolution','V'+str(rr),b['values']['Listing Resolution'].get('V'+str(rr),'')+'\n'+basis)
rr=rowof('Draft Listings',oid)
if rr and details.get('draft_listing'):setcell('Draft Listings','N'+str(rr),'\n'.join(details['remaining_evidence_gaps']));setcell('Draft Listings','P'+str(rr),details['draft_listing']['media_condition'])
for i,(x,y)in enumerate(zip(a['missing_pictures'],olda['missing_pictures']),10):
 if x['option_id']!=oid or x['role']!='In situ':continue
 for col,value in {'E':x['action_type'],'F':x['action'],'I':ref['file_id'],'J':ref['folder_id'],'K':x['scope'],'L':x['qualification'],'M':x['owner_response'],'N':x['status']}.items():setcell('Missing Pictures',col+str(i),value)
 linkcell('Missing Pictures','G'+str(i),'Owner-accepted outdoor display',ref['image_url']);linkcell('Missing Pictures','H'+str(i),'Actual containing folder',ref['folder_url'])
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):140,('Photo Coverage','F4'):116,('Missing Pictures','B4'):64,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
for(sn,c),value in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':value}
for sn,text in {'Master Catalogue':'187 active individual options and one retired history row across112 component identities. Moon/Shellwave/workshop links match the live stable-ID readback. Leaf Curve White and Gold Leaf001 is an owner-accepted outdoor-display reference.','Photo Coverage':'177 complete individual references;10 technical gaps include9 owner-accepted qualified exceptions and one deferred Frozen Fish identity. Current gaps:47 in situ and17 series. Leaf Curve001 is outdoor display. Permanent/client installation and physical specifications remain unverified. Sandstone remains retired.','Missing Pictures':'208 retained rows:65 required open actions,54 optional,86 resolved and3 retired. Current gaps:one deferred individual/identity entry,47 in situ and17 series. Sandstone has no active tasks.'}.items():setcell(sn,'A3',text)
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
groups=collections.defaultdict(list);blocks=[]
for x in changes.values():groups[(x['sheet'],re.match('[A-Z]+',x['cell'])[0])].append(x)
for(sn,col),xs in groups.items():
 run=[]
 for x in sorted(xs,key=lambda z:int(z['cell'][len(col):])):
  if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[v['value']]for v in run]});run=[]
  run.append(x)
 if run:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[v['value']]for v in run]})
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks,'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':'Master Catalogue','row':row,'height':110},{'sheet':'Listing Resolution','row':row,'height':110}],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','A2:F5','baseline-summary'],['Photo Coverage','F'+r+':L'+r,'baseline-leaf-curve']],'preview_ranges':[['Photo Coverage','A2:F5','01-photo-summary'],['Photo Coverage','F'+r+':L'+r,'02-leaf-curve-outdoor-display'],['Master Catalogue','T'+r+':V'+r,'03-leaf-curve-source-limits'],['Missing Pictures','A2:N4','04-current-actions']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'links':len(links),'leaf_curve_workbook_row':row}))
