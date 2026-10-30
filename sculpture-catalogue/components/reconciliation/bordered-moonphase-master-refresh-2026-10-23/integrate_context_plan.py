"""Extend the scoped Artifact edit plan for the two qualified context bindings."""
import importlib.util,json,re
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('n',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);b=n.load(H/'inputs/master_workbook.before');p=read(H/'workbook-edit-plan.json');a=read(H/'image-coverage-current.json');g=read(H/'canonical-master-register.json');out=B/'outputs'/H.name;changes={(x['sheet'],x['cell']):x for x in p['cell_changes']};links={(x['sheet'],x['cell']):x for x in p['hyperlinks']};rows=[]
def setcell(sn,c,value):
 assert c not in b['formulas'][sn];before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def link(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
def row(sn,oid):return next((int(c[1:])for c,x in b['values'][sn].items()if re.fullmatch('A[0-9]+',c)and x==oid),None)
for oid in ['BSI-65A93033A200','BSI-4515726BBC18','BSI-2418C8B43415','BSI-207102CFD25C']:
 c=next(x for x in a['coverage']if x['option_id']==oid);z=c['in_situ'];r=z['reference'];rr=row('Master Catalogue',oid);basis=z['basis'];ar=next(i for i,x in enumerate(a['missing_pictures'],10)if x['option_id']==oid and x['role']=='In situ');task=a['missing_pictures'][ar-10]
 setcell('Photo Coverage','F'+str(rr),'Available');link('Photo Coverage','G'+str(rr),z['display_qualification'],r['image_url']);link('Photo Coverage','H'+str(rr),'Containing folder',r['folder_url']);setcell('Photo Coverage','O'+str(rr),r['file_id']);setcell('Photo Coverage','P'+str(rr),r['folder_id']);setcell('Photo Coverage','T'+str(rr),z['display_qualification']+'; creation origin and authentic installation unverified.');link('Photo Coverage','U'+str(rr),'Current qualified display reference',str(out/'imported-approvals.html')+'#'+oid)
 note=basis+('\nAdditional original008 is in Moonphase1’s individual folder; selected001 primary retained.'if rr==134 else'')
 if rr==134:link('Photo Coverage','L134',note,str(out/'bordered-moonphase-changes.html')+'#'+oid)
 else:setcell('Photo Coverage','L'+str(rr),note)
 link('Master Catalogue','T'+str(rr),z['display_qualification'],r['image_url']);link('Master Catalogue','U'+str(rr),'Containing folder',r['folder_url']);setcell('Master Catalogue','V'+str(rr),b['values']['Master Catalogue']['V'+str(rr)].split('\nPhoto review:')[0]+'\nPhoto review: individual Available; in situ Available; series Available.\n'+basis)
 for col,value in {'F':task['action'],'I':r['file_id'],'J':r['folder_id'],'L':basis,'M':task['owner_response'],'N':'Resolved'}.items():setcell('Missing Pictures',col+str(ar),value)
 link('Missing Pictures','G'+str(ar),z['display_qualification'],r['image_url']);link('Missing Pictures','H'+str(ar),'Containing folder',r['folder_url'])
 for sn,col in [('Listing Resolution','V'),('Draft Listings','N'),('Draft Listings','P')]:
  rowid=row(sn,oid)
  if rowid:setcell(sn,col+str(rowid),b['values'][sn].get(col+str(rowid),'')+'\n'+basis)
 rows.append({'option_id':oid,'row':rr,'action_row':ar})
for x in p['summary_expected']:
 if (x['sheet'],x['cell'])==('Photo Coverage','D4'):x['value']=165
 if (x['sheet'],x['cell'])==('Missing Pictures','B4'):x['value']=39
for x in p['formula_changes']:
 if(x['sheet'],x['cell'])==('Photo Coverage','D4'):x['expected']=165
 if(x['sheet'],x['cell'])==('Missing Pictures','B4'):x['expected']=39
link('Master Catalogue','A3','187 active individual options and one retired history row across112 component identities. Bordered Moonphase paths refreshed by stable ID; original008 is an additional Moonphase1 reference. Four qualified display references added: two bordered panels, one workshop/tabletop and one garden-ground scene. Primary images and working specifications are retained.',str(out/'bordered-moonphase-changes.html'))
setcell('Photo Coverage','A3','177 complete individual references;10 technical gaps include9 owner-accepted qualified exceptions and one deferred Frozen Fish identity. Current gaps:22 in situ, including8 held cases, and17 series. Four qualified displays added: two bordered Moonphase brick-wall panels, a workshop/tabletop panel and a garden-ground panel; origin and physical details remain unverified.')
setcell('Missing Pictures','A3','209 retained rows:40 required open actions,54 optional,112 resolved and3 retired. Current gaps:one deferred individual/identity entry,22 in situ and17 series. Eight in-situ cases remain held;14 are active source requests. Sandstone One Leaf remains retired.')
for k,x in changes.items():
 if k in links:links[k]['label']=x['value']
p.update(cell_changes=list(changes.values()),hyperlinks=list(links.values()),value_blocks=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],target_rows=rows,row_heights=[{'sheet':sn,'row':z['row']if sn!='Missing Pictures'else z['action_row'],'height':140 if sn!='Master Catalogue'else 155}for z in rows for sn in ['Photo Coverage','Master Catalogue','Missing Pictures']],preview_ranges=[['Photo Coverage','F134:L134','01-moonphase-one-display-and-series'],['Photo Coverage','F137:L137','02-moonphase-two-display-and-series'],['Photo Coverage','A2:F5','03-current-coverage-summary'],['Missing Pictures','D'+str(rows[0]['action_row'])+':N'+str(rows[0]['action_row']),'04-resolved-moonphase-context-action']])
p['preview_ranges'] += [['Photo Coverage','F'+str(z['row'])+':L'+str(z['row']),'05-'+z['option_id']]for z in rows[2:]]
write(H/'workbook-edit-plan.json',p);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':p['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'native_hyperlinks':len(links),'context_rows':rows,'formula_text_changes':0}))
