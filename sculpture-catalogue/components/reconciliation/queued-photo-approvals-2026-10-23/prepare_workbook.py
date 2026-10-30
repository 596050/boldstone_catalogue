import json, importlib.util, posixpath, re
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
b=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');old=read(H/'inputs/audit.before');scope=read(H/'scope.json');targets=set(scope['target_option_ids']);changes={};links={};forms={};heights={};out=B/'outputs/queued-photo-approvals-2026-10-23'
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target') for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+n.q('hyperlink')):links[(sn,x.get('ref'))]={'sheet':sn,'cell':x.get('ref'),'label':b['values'][sn].get(x.get('ref'),''),'target':'#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')]}
def setcell(sn,c,v):
 assert c not in b['formulas'][sn]
 before=b['values'][sn].get(c,'')
 if before!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':v}
def linkcell(sn,c,label,target):
 setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def rowof(sn,oid):return next((int(c[1:])for c,v in b['values'][sn].items()if re.fullmatch(r'A\d+',c)and v==oid),None)
cov={x['option_id']:x for x in a['coverage']};details={x['product_id']:x for x in g['current_listing_resolution_details']['entries']}
for o in g['options']:
 oid=o['product_id']
 if oid not in targets:continue
 r=rowof('Master Catalogue',oid);c=cov[oid];approval=o['current_photo_approval_import'];basis=approval['basis'];note=b['values']['Master Catalogue']['V'+str(r)].split('\nPhoto review:')[0]
 status='Photo review: individual '+c['individual']['status']+'; in situ '+c['in_situ']['status']+'; series '+c['series']['status']+'.'
 setcell('Master Catalogue','V'+str(r),note+'\n'+status+'\n'+basis);heights[('Master Catalogue',r)]=230
 setcell('Photo Coverage','L'+str(r),basis);linkcell('Photo Coverage','U'+str(r),'Imported owner approval and image roles',str(out/'imported-approvals.html')+'#'+oid);heights[('Photo Coverage',r)]=225
 if oid in scope['in_situ_option_ids']:
  rr=c['in_situ']['reference'];setcell('Photo Coverage','F'+str(r),'Available');linkcell('Photo Coverage','G'+str(r),'Owner-accepted variation'if oid=='BSI-923D5E50A898'else'Owner-bound in situ image',rr['image_url']);linkcell('Photo Coverage','H'+str(r),'Containing folder',rr['folder_url']);setcell('Photo Coverage','O'+str(r),rr['file_id']);setcell('Photo Coverage','P'+str(r),rr['folder_id']);linkcell('Master Catalogue','T'+str(r),'Owner-accepted variation'if oid=='BSI-923D5E50A898'else'Owner-bound in situ image',rr['image_url']);linkcell('Master Catalogue','U'+str(r),'Containing folder',rr['folder_url'])
 # Keep primary individual image columns and source-scoped execution conditions intact.
 for sn,cols in [('Draft Listings',{'N':'\n'.join(details[oid]['remaining_evidence_gaps']),'P':details[oid]['draft_listing']['media_condition']}if oid in details and details[oid].get('draft_listing')else{}),('Listing Resolution',{'V':b['values']['Listing Resolution'].get('V'+str(r),'')+'\nCurrent media: '+basis})]:
  rr=rowof(sn,oid)
  if rr is not None:
   for col,value in cols.items():setcell(sn,col+str(rr),value)
   heights[(sn,rr)]=240
for i,(x,y)in enumerate(zip(a['missing_pictures'],old['missing_pictures']),10):
 if x==y:continue
 assert x['option_id']in targets and x['status']=='Resolved'
 ref=x['reference'];values=[x['priority'],x['option_id'],x['name'],x['role'],x['action_type'],x['action'],'Owner-accepted reference','Containing folder',ref['file_id'],ref['folder_id'],x['scope'],x['qualification'],x['owner_response'],x['status']]
 for j,v in enumerate(values):setcell('Missing Pictures',n.column(j)+str(i),v)
 linkcell('Missing Pictures','G'+str(i),'Owner-accepted reference',ref['image_url']);linkcell('Missing Pictures','H'+str(i),'Containing folder',ref['folder_url']);heights[('Missing Pictures',i)]=240
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):11,('Photo Coverage','D4'):128,('Photo Coverage','F4'):116,('Missing Pictures','B4'):79,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54}
for (sn,c),v in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':v}
notes={'Master Catalogue':'188 current individual options across 112 working component identities. Seven newer owner approvals imported with group, design/finish and variation qualifications. Physical specifications and platform matches retain their evidence status.','Photo Coverage':'177 complete individual images. Eleven technical individual/identity gaps remain: nine accepted group/combined references and two open entries (one separate photograph and one deferred Frozen Fish identity).60 in situ and18 series gaps remain.','Missing Pictures':'208 retained action rows:80 open required actions,54 optional and74 resolved. This import resolves four scoped group/design-finish listing-reference reviews and three in situ bindings. Technical individual photograph types remain unchanged.','Lava Moon Folders':'Three White PNGs remain approved complete individual listing images. They are now also approved as DESIGN ONLY for the corresponding Sandstone options; the whole Sandstone group supplies FINISH references (left1 centre2 right3). No standalone Sandstone photograph or new physical verification is asserted.'}
for sn,text in notes.items():setcell(sn,'A3',text);heights[(sn,3)]=66
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
br=rowof('Photo Coverage','BSI-923D5E50A898');mp=rowof('Photo Coverage','BSI-B1DCB5B08396');lav=rowof('Draft Listings','BSI-725A77437026')
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':sn,'row':r,'height':v}for(sn,r),v in heights.items()],'table_appends':[],'new_sheets':{},'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'baseline_ranges':[['Photo Coverage','A2:F5','baseline-photo-summary'],['Photo Coverage','F'+str(br)+':L'+str(br),'baseline-brancusi-context']],'preview_ranges':[['Photo Coverage','A2:F5','01-current-photo-summary'],['Photo Coverage','F'+str(br)+':L'+str(br),'02-brancusi-variation'],['Photo Coverage','L'+str(mp)+':L'+str(mp),'03-mp4-whole-group'],['Draft Listings','N'+str(lav)+':P'+str(lav),'04-lava-design-finish'],['Missing Pictures','A2:N4','05-current-actions']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'status':'PLAN_READY','changed_cells':len(changes),'links':len(links),'summary_caches':plan['summary_expected'],'formulas_preserved':plan['expected_formula_count']}))
