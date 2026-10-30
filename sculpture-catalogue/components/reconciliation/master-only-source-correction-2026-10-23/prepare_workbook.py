import collections,importlib.util,json,posixpath,re
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
b=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');olda=read(H/'inputs/audit.before')
out=B/'outputs/master-only-source-correction-2026-10-23';oldout=B/'outputs/in-situ-folder-refresh-and-context-review-2026-10-23';family='https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/01%20Wall%20Sculptures/Acanthus'
badfiles={'id:cnqzTNngPVsAAAAAAA6LRw','id:cnqzTNngPVsAAAAAAA6LRQ'};badparent='id:cnqzTNngPVsAAAAAAA6LRA'
changes={};links={};forms={};heights={}
def setcell(sn,c,v):
 if c in b['formulas'][sn]:return
 before=b['values'][sn].get(c,'')
 if before!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def unlink(sn,c,label):links.pop((sn,c),None);setcell(sn,c,label)
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def rowof(sn,oid):return next((int(c[1:])for c,v in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and v==oid),None)
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+n.R+'}id')]
  if 'BOLDSTONE_BACKUP'in unquote(u).upper():
   if '/home/'in u:linkcell(sn,c,'Master family navigation',family)
   else:setcell(sn,c,'No verified Master image')
  else:
   # Current navigational views follow this release; sealed historical workbook tabs retain their original local links.
   if sn not in ['Fingerprint History','Moonphases and Dune']and str(oldout)in u:u=u.replace(str(oldout),str(out))
   links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u}
 for c,v in b['values'][sn].items():
  if v in badfiles:setcell(sn,c,'Unbound')
  elif v==badparent:setcell(sn,c,'')
  elif isinstance(v,str)and 'BOLDSTONE_BACKUP'in unquote(v).upper():setcell(sn,c,'No verified Master image')
cov={x['option_id']:x for x in a['coverage']};detail={x['product_id']:x for x in g['current_listing_resolution_details']['entries']}
note=read(H/'source-scope-correction.json')['scope_note']
for oid in ['BSI-3635E3DC3434','BSI-C41824131174']:
 row=rowof('Master Catalogue',oid);r=str(row);c=cov[oid]
 setcell('Photo Coverage','I'+r,'No verified image');unlink('Photo Coverage','J'+r,'No verified Master series image');linkcell('Photo Coverage','K'+r,'Master family navigation',family);setcell('Photo Coverage','Q'+r,'Unbound');setcell('Photo Coverage','R'+r,'')
 setcell('Photo Coverage','L'+r,note);linkcell('Photo Coverage','U'+r,'Master-only source correction',str(out/'source-scope-correction.html')+'#'+oid)
 setcell('Master Catalogue','V'+r,note+'\nPhoto review: individual '+c['individual']['status']+'; in situ '+c['in_situ']['status']+'; series '+c['series']['status']+'.')
 for sn in ['Listing Resolution','Draft Listings']:
  rr=rowof(sn,oid)
  if rr is not None:
   if sn=='Listing Resolution':setcell(sn,'V'+str(rr),b['values'][sn].get('V'+str(rr),'')+'\n'+note)
   elif oid in detail and detail[oid].get('draft_listing'):
    setcell(sn,'N'+str(rr),'\n'.join(detail[oid]['remaining_evidence_gaps']));setcell(sn,'P'+str(rr),detail[oid]['draft_listing']['media_condition'])
 if oid=='BSI-C41824131174':
  setcell('Photo Coverage','C'+r,'No verified image');unlink('Photo Coverage','D'+r,'No verified Master image');linkcell('Photo Coverage','E'+r,'Master family navigation',family);setcell('Photo Coverage','M'+r,'Unbound');setcell('Photo Coverage','N'+r,'')
  unlink('Master Catalogue','N'+r,'No verified Master image');linkcell('Master Catalogue','O'+r,'Master family navigation',family);setcell('Master Catalogue','Q'+r,'Unbound');setcell('Master Catalogue','R'+r,'')
for i,(x,y)in enumerate(zip(a['missing_pictures'],olda['missing_pictures']),10):
 if x==y:continue
 if x['option_id']not in ['BSI-3635E3DC3434','BSI-C41824131174']:continue
 if x['role'] not in ['Individual','In situ','Series']:continue
 vals={'E':x['action_type'],'F':x['action'],'K':x['scope'],'L':x['qualification'],'M':x.get('owner_response',''),'N':x['status']}
 for c,v in vals.items():setcell('Missing Pictures',c+str(i),v)
 if x['reference']['file_id']=='Unbound':
  unlink('Missing Pictures','G'+str(i),'No verified Master image');linkcell('Missing Pictures','H'+str(i),'Master family navigation',family);setcell('Missing Pictures','I'+str(i),'Unbound');setcell('Missing Pictures','J'+str(i),'')
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):11,('Photo Coverage','D4'):135,('Photo Coverage','F4'):116,('Missing Pictures','B4'):72,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186}
for(sn,c),v in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':v}
notes={'Master Catalogue':'188 individual options across112 working component identities. Current sculpture image evidence is restricted to BOLDSTONE MASTER. Sandstone needs a current Master image; Sandstone and Pewter series-photo gaps reopened. Accepted specifications and earlier qualified approvals retained.','Photo Coverage':'Current Master sources only:177 complete individual images;11 technical gaps including9 accepted group/combined exceptions and2 open individual/identity actions. Current gaps:53 in situ and18 series. Sandstone has no verified current Master image.','Missing Pictures':'208 retained action rows:73 required open actions,54 optional and81 resolved. Sandstone needs a current Master individual image; Frozen Fish legacy identity remains deferred. Context gaps:53 in situ and18 series.'}
for sn,v in notes.items():setcell(sn,'A3',v)
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
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks,'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'baseline_ranges':[['Photo Coverage','A2:F5','baseline-photo-summary'],['Photo Coverage','C15:L16','baseline-acanthus-sources']],'preview_ranges':[['Photo Coverage','A2:F5','01-current-photo-summary'],['Photo Coverage','C15:L16','02-acanthus-master-only'],['Master Catalogue','N16:V16','03-sandstone-source-scope'],['Missing Pictures','A2:N4','04-current-actions']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'status':'PLAN_READY','edited_cells':len(changes),'native_links':len(links),'formulas_changed':0}))
