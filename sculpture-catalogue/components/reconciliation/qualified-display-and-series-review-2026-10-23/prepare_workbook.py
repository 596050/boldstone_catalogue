"""Prepare scoped values and native hyperlinks; workbook authoring is JavaScript."""
import collections,importlib.util,json,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
b=v.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');tasks=read(H/'review-plan.json');out=B/'outputs'/H.name;oldout=B/'outputs/nine-empty-folder-master-refresh-2026-10-23';changes={};links={};forms={};heights=[];target_rows=[]
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
def setcell(sn,c,value):
 assert c not in b['formulas'][sn]
 before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def rowof(sn,oid):return next((int(c[1:])for c,x in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and x==oid),None)
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
  if not protected(sn,c):u=u.replace(str(oldout),str(out))
  if not protected(sn,c)and u.startswith(str(out))and'/imported-approvals.html#'in u and any(z['option_id']==u.rsplit('#',1)[1]and z['in_situ']['status']=='Available'for z in a['coverage']):u=str(out/'current-context-references.html')+'#'+u.rsplit('#',1)[1]
  links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u}
for t in tasks:
 oid=t['option_id'];row=rowof('Master Catalogue',oid);r=str(row);c=next(x for x in a['coverage']if x['option_id']==oid);ref=c['in_situ']['reference'];basis=c['in_situ']['basis'];label=t['display_label'];proof=str(out/'imported-approvals.html')+'#'+oid
 assert row==g['options'].index(next(x for x in g['options']if x['product_id']==oid))+10
 setcell('Photo Coverage','F'+r,'Available');linkcell('Photo Coverage','G'+r,label,ref['image_url']);linkcell('Photo Coverage','H'+r,'Actual containing folder',ref['folder_url']);setcell('Photo Coverage','O'+r,ref['file_id']);setcell('Photo Coverage','P'+r,ref['folder_id']);setcell('Photo Coverage','L'+r,'Individual: '+c['individual']['status']+'. '+(c['individual'].get('basis','')if c['individual']['status']!='Available'else'Kept primary reference unchanged.')+'\nContext: '+basis+'\nSeries: '+c['series']['status']+'.');linkcell('Photo Coverage','U'+r,'Reviewed display reference and qualification',proof)
 linkcell('Master Catalogue','T'+r,label,ref['image_url']);linkcell('Master Catalogue','U'+r,'Actual containing folder',ref['folder_url']);setcell('Master Catalogue','V'+r,b['values']['Master Catalogue']['V'+r].split('\nPhoto review:')[0]+'\nPhoto review: individual '+c['individual']['status']+'; in situ Available; series '+c['series']['status']+'.\n'+basis)
 rr=rowof('Listing Resolution',oid)
 if rr:setcell('Listing Resolution','V'+str(rr),b['values']['Listing Resolution'].get('V'+str(rr),'')+'\n'+basis);heights.append({'sheet':'Listing Resolution','row':rr,'height':150})
 details=next((x for x in g['current_listing_resolution_details']['entries']if x['product_id']==oid),None);rr=rowof('Draft Listings',oid)
 if rr and details and details.get('draft_listing'):setcell('Draft Listings','N'+str(rr),'\n'.join(details['remaining_evidence_gaps']));setcell('Draft Listings','P'+str(rr),details['draft_listing']['media_condition'])
 ar=next(i for i,x in enumerate(a['missing_pictures'],10)if x['option_id']==oid and x['role']=='In situ');task=a['missing_pictures'][ar-10];sr=str(ar)
 assert b['values']['Missing Pictures']['B'+sr]==oid and b['values']['Missing Pictures']['N'+sr]=='Open'and task['status']=='Resolved'
 for col,value in {'F':task['action'],'I':ref['file_id'],'J':ref['folder_id'],'L':basis,'M':task['owner_response'],'N':'Resolved'}.items():setcell('Missing Pictures',col+sr,value)
 linkcell('Missing Pictures','G'+sr,label,ref['image_url']);linkcell('Missing Pictures','H'+sr,'Actual containing folder',ref['folder_url'])
 heights.extend([{'sheet':'Master Catalogue','row':row,'height':155},{'sheet':'Photo Coverage','row':row,'height':110},{'sheet':'Missing Pictures','row':ar,'height':140}]);target_rows.append({'option_id':oid,'row':row,'action_row':ar})
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):161,('Photo Coverage','F4'):116,('Missing Pictures','B4'):43,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
for(sn,c),value in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':value}
for sn,text in {'Master Catalogue':'187 active options and one retired history row across112 identities.18 qualified display references imported from14 whole stored images;36 active context cases and17 series cases reviewed. Nine completed empty-folder histories retained. Scene origin and physical specifications remain unverified.','Photo Coverage':'177 complete individual references;10 technical gaps include9 owner-accepted qualified exceptions and one deferred Frozen Fish identity. Current gaps:26 in situ and17 series.18 reviewer-verified display references imported under owner direction;8 held context cases remain unchanged. No installation authenticity or physical certification inferred.','Missing Pictures':'209 retained rows:44 required open actions,54 optional,108 resolved and3 retired. Current gaps:one deferred individual/identity entry,26 in situ and17 series.17 series reviews remain source-required. Sandstone remains retired.'}.items():setcell(sn,'A3',text)
outcomes=read(H/'review-outcomes.json');target_ids={x['option_id']for x in tasks}
for z in outcomes['in_situ']:
 oid=z['option_id']
 if oid in outcomes['held_ids']or oid in target_ids:continue
 rr=rowof('Master Catalogue',oid);r=str(rr);setcell('Photo Coverage','L'+r,b['values']['Photo Coverage']['L'+r]+'\nLatest bounded Master review: '+z['finding']);linkcell('Photo Coverage','U'+r,'Current source review — photograph still required',str(out/'context-review-walkthrough.html')+'#'+oid+'-in-situ')
for z in outcomes['series']:
 oid=z['option_id'];rr=rowof('Master Catalogue',oid);r=str(rr);assert b['values']['Photo Coverage']['M9']=='Individual file ID';setcell('Photo Coverage','L'+r,changes.get(('Photo Coverage','L'+r),{}).get('value',b['values']['Photo Coverage']['L'+r])+'\nLatest bounded Master series review: '+z['next_required_input'])
for i,x in enumerate(a['missing_pictures'],10):
 if x.get('latest_source_review'):setcell('Missing Pictures','L'+str(i),x['qualification'])
for key,x in list(changes.items()):
 if key[0]=='Photo Coverage'and key[1].startswith('L'):
  row=int(key[1][1:]);heights=[z for z in heights if not(z['sheet']=='Photo Coverage'and z['row']==row)];heights.append({'sheet':'Photo Coverage','row':row,'height':210})
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
groups=collections.defaultdict(list);blocks=[]
for x in changes.values():groups[(x['sheet'],re.match('[A-Z]+',x['cell'])[0])].append(x)
for(sn,col),xs in groups.items():
 run=[]
 for x in sorted(xs,key=lambda z:int(z['cell'][len(col):])):
  if run and int(x['cell'][len(col):])!=int(run[-1]['cell'][len(col):])+1:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[z['value']]for z in run]});run=[]
  run.append(x)
 if run:blocks.append({'sheet':sn,'range':run[0]['cell']+':'+run[-1]['cell'],'values':[[z['value']]for z in run]})
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks,'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':heights,'table_appends':[],'new_sheets':{},'target_rows':target_rows,'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','F'+str(target_rows[0]['row'])+':L'+str(target_rows[0]['row']),'baseline-leaf-growth']],'preview_ranges':[['Photo Coverage','A2:F5','01-current-summary']]+[['Photo Coverage','F'+str(z['row'])+':M'+str(z['row']),'0'+str(i+2)+'-display-reference']for i,z in enumerate([target_rows[j]for j in [0,1,8,13,16]])]+[['Missing Pictures','D'+str(target_rows[0]['action_row'])+':N'+str(target_rows[0]['action_row']),'07-rust-replacement-action']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'links':len(links),'targets':target_rows,'formula_text_changes':0}))
