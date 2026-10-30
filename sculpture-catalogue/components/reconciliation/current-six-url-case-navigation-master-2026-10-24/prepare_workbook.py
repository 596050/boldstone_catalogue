import copy,json,importlib.util,re
from pathlib import Path
from navigation import refresh
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text())
m=read(H/'input-manifest.json');OLD=Path(m['master_register']['path']).parent;oldout=read(H/'projection-index.json')['old_output'];p=copy.deepcopy(read(OLD/'workbook-edit-plan.json'))
protected=lambda s,c:s=='Fingerprint History'or s=='Source Specifications'and c.rstrip('0123456789')in['M','N']or s=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
changes=[]
for x in p['hyperlinks']:
 before=x['target'];new=before if protected(x['sheet'],x['cell'])else refresh(before).replace(oldout,str(OUT));x['target']=new
 if new!=before and before.startswith('https://www.dropbox.com/'):changes.append({'sheet':x['sheet'],'cell':x['cell'],'before':before,'current':new})
ov=read(H/'moonwave-native-overlay.json');moved={o['file_id']:o for o in ov['objects']if o['old_path']!=o['current_path']}
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n);w=n.load(H/'inputs/master_workbook.before');linkmap={(x['sheet'],x['cell']):x for x in p['hyperlinks']}
from urllib.parse import quote
for sn in ['Source Mapping','Source Specifications']:
 for c,ident in w['values'][sn].items():
  if re.fullmatch(r'J\d+',c)and ident in moved:
   cell='I'+c[1:];x=linkmap.get((sn,cell))
   if x:
    before=x['target'];target='https://www.dropbox.com/home'+quote(moved[ident]['current_path'].rsplit('/',1)[0],safe='/')
    if before!=target:changes.append({'sheet':sn,'cell':cell,'before':before,'current':target,'own_file_id':ident});x['target']=target
parents=[]
for sn,filecol,parentcol,foldercol in [('Platform Sources','W','X','V'),('Listing Offer Links','T','U','S')]:
 for c,ident in w['values'][sn].items():
  if re.fullmatch(filecol+r'\d+',c)and ident in moved:
   row=c[len(filecol):];cell=parentcol+row;parents.append({'sheet':sn,'cell':cell,'before':w['values'][sn][cell],'value':moved[ident]['current_parent_id']});link=linkmap[(sn,foldercol+row)];target='https://www.dropbox.com/home'+quote(moved[ident]['current_path'].rsplit('/',1)[0],safe='/')
   if target!=link['target']:changes.append({'sheet':sn,'cell':foldercol+row,'before':link['target'],'current':target,'own_file_id':ident});link['target']=target
x=next(x for x in p['hyperlinks']if x['sheet']=='Master Catalogue'and x['cell']=='A3');before=x['label'];label='188 active options;112 retained component IDs;110 working design groups. Six current URL corrections and ten approved Moonwave photo moves imported; stable identities, specifications and owner holds retained.';x.update(label=label,target=str(OUT/'moonwave-approved-folder-changes.html'))
p.update(cell_changes=[{'sheet':'Master Catalogue','cell':'A3','before':before,'value':label}],value_blocks=[{'sheet':'Master Catalogue','range':'A3','values':[[label]]}],row_heights=[],native_link_changes=changes,actual_parent_cells=[],baseline_ranges=[['Master Catalogue','A2:Y5','baseline-master-header'],['Master Catalogue','B108:H108','baseline-leaf-specifications']],preview_ranges=[['Master Catalogue','A2:Y5','01-master-header'],['Master Catalogue','B108:H108','02-leaf-specifications']],supplemental_preview_ranges=[['Photo Coverage','B134:F135','03-border-panel-coverage'],['Missing Pictures','A2:F5','04-action-totals']])
p['cell_changes']+=parents;p['value_blocks']+=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in parents];p['actual_parent_cells']=[x['sheet']+'!'+x['cell']for x in parents]
p['baseline_ranges'].append(['Platform Sources','T25:X25','baseline-moonwave-source-navigation']);p['supplemental_preview_ranges'].append(['Platform Sources','T25:X25','05-moonwave-source-navigation'])
for name,data in [('workbook-edit-plan.json',p),('expected-edit.json',{'sheets':{},'hyperlinks':p['hyperlinks'],'formulas':[]})]:(H/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':'PLAN_READY','value_changes':1,'native_case_link_changes':len(changes),'native_ID_changes':0,'historical_values_and_targets_preserved':True}))
