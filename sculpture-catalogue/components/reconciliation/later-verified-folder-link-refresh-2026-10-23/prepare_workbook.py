import collections,importlib.util,json,posixpath,re
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
b=v.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');nm=read(H/'current-native-reference-map.json');objects=nm['current_objects'];oldpaths=nm['old_path_to_id'];scope=read(H/'path-refresh-scope.json');scoped=set(scope['changed_ids']);missing=set(scope['unavailable_file_ids']);gone=set(scope['deleted_empty_family_ids']);out=B/'outputs'/H.name;oldout=B/'outputs/moon-shellwave-links-leaf-curve-context-2026-10-23';changes={};links={};forms={};available_context_ids={x['option_id']for x in a['coverage']if x['in_situ']['status']=='Available'}
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
def fidof(u):
 if not isinstance(u,str)or not u.startswith('https://www.dropbox.com/'):return None
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0];p+='/'+name if name else'';return oldpaths.get(p.casefold())
def currenturl(u):
 fid=fidof(u)
 if fid in missing or fid in gone:return None
 if fid not in scoped:return u
 x=objects[fid];return 'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
def setcell(sn,c,value):
 if c in b['formulas'][sn]:return
 before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def clearlink(sn,c,label):links.pop((sn,c),None);setcell(sn,c,label)
def rowof(sn,oid):return next((int(c[1:])for c,x in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and x==oid),None)
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
  if not protected(sn,c):u=currenturl(u)
  if u is None:setcell(sn,c,'Historical source — current reference unavailable');continue
  u=u.replace(str(oldout),str(out))
  if not protected(sn,c) and u.startswith(str(B/'outputs')) and '/imported-approvals.html#'in u and u.rsplit('#',1)[1]in available_context_ids:u=str(out/'current-context-references.html')+'#'+u.rsplit('#',1)[1]
  links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u}
 for c,x in b['values'][sn].items():
  if not protected(sn,c)and isinstance(x,str)and x.startswith('https://www.dropbox.com/'):
   u=currenturl(x)
   if u!=x:setcell(sn,c,u if u is not None else'Historical source — current reference unavailable')
oid='BSI-83F1AACE15E9';row=rowof('Master Catalogue',oid);r=str(row);c=next(x for x in a['coverage']if x['option_id']==oid);ref=c['individual']['reference'];basis=c['in_situ']['basis'];details=next((x for x in g['current_listing_resolution_details']['entries']if x['product_id']==oid),None)
setcell('Photo Coverage','F'+r,'No verified image');clearlink('Photo Coverage','G'+r,'Current source unresolved');clearlink('Photo Coverage','H'+r,'—');setcell('Photo Coverage','O'+r,'');setcell('Photo Coverage','P'+r,'');setcell('Photo Coverage','L'+r,basis);linkcell('Photo Coverage','U'+r,'Current source issue and history',str(out/'unavailable-native-references.html')+'#'+oid)
clearlink('Master Catalogue','T'+r,'Current source unresolved');clearlink('Master Catalogue','U'+r,'—');setcell('Master Catalogue','V'+r,b['values']['Master Catalogue']['V'+r].split('\nPhoto review:')[0]+'\nPhoto review: individual Available; in situ No verified image; series Optional / no fixed set.\n'+basis)
rr=rowof('Listing Resolution',oid)
if rr:setcell('Listing Resolution','V'+str(rr),b['values']['Listing Resolution'].get('V'+str(rr),'')+'\n'+basis)
rr=rowof('Draft Listings',oid)
if rr and details and details.get('draft_listing'):setcell('Draft Listings','N'+str(rr),'\n'.join(details['remaining_evidence_gaps']));setcell('Draft Listings','P'+str(rr),details['draft_listing']['media_condition'])
arow=next(i for i,x in enumerate(a['missing_pictures'],10)if x['option_id']==oid and x['role']=='In situ');assert arow==218 and all(b['values']['Missing Pictures'].get(col+str(arow),'')==''for col in 'ABCDEFGHIJKLMN');task=a['missing_pictures'][-1]
for col,value in {'A':task['priority'],'B':oid,'C':task['name'],'D':'In situ','E':task['action_type'],'F':task['action'],'I':ref['file_id'],'J':ref['folder_id'],'K':task['scope'],'L':task['qualification'],'M':'','N':'Open'}.items():setcell('Missing Pictures',col+str(arow),value)
linkcell('Missing Pictures','G'+str(arow),'Verified individual for identification',ref['image_url']);linkcell('Missing Pictures','H'+str(arow),'Actual containing folder',ref['folder_url'])
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):139,('Photo Coverage','F4'):116,('Missing Pictures','B4'):65,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
for(sn,c),value in expected.items():
 before=b['formulas'][sn][c];formula=before.replace('217','220')if sn=='Missing Pictures'and c in ['B4','D4','F4']else before
 forms[(sn,c)]={'sheet':sn,'cell':c,'before':before,'formula':formula,'expected':value}
for sn,text in {'Master Catalogue':'187 active individual options and one retired history row across112 component identities. Later verified folder paths updated by stable ID. Four former Rust context sources remain unresolved; one current in-situ request reopened. Leaf Curve approval retained.','Photo Coverage':'177 complete individual references;10 technical gaps include9 owner-accepted qualified exceptions and one deferred Frozen Fish identity. Current gaps:48 in situ and17 series. Four former Rust source IDs retained in history; the previously linked001 needs a current replacement. No new physical or image-role approval.','Missing Pictures':'209 retained rows:66 required open actions,54 optional,86 resolved and3 retired. Current gaps:one deferred individual/identity entry,48 in situ and17 series. Rust in-situ source request added in reserved row218. Sandstone remains retired.'}.items():setcell(sn,'A3',text)
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
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks,'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':'Master Catalogue','row':row,'height':155},{'sheet':'Photo Coverage','row':row,'height':100},{'sheet':'Missing Pictures','row':arow,'height':140}],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','F'+r+':L'+r,'baseline-rust-source'],['Missing Pictures','A218:N218','baseline-reserved-row']],'preview_ranges':[['Photo Coverage','A2:F5','01-current-summary'],['Photo Coverage','F'+r+':L'+r,'02-rust-source-status'],['Master Catalogue','T'+r+':V'+r,'03-rust-history-and-limits'],['Missing Pictures','D218:N218','04-reopened-rust-request']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'links':len(links),'rust_workbook_row':row,'new_action_row_in_existing_table':arow}))
