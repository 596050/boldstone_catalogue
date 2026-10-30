"""Plan two obsolete folder links and current history navigation only."""
import collections,importlib.util,json,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
from urllib.parse import quote
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
b=v.load(H/'inputs/master_workbook.before');out=B/'outputs'/H.name;oldout=B/'outputs/four-qualified-display-references-2026-10-23';changes={};links={};forms={}
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
def setcell(sn,c,value):
 assert c not in b['formulas'][sn];before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
  if not protected(sn,c):u=u.replace(str(oldout),str(out))
  links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u}
history=read(H/'removed-empty-folder-history.json');removed={x['file_id']:x for x in history['folders']};sn='Moonphases and Dune'
for row,fid in [(36,'id:cnqzTNngPVsAAAAAAAyj-Q'),(39,'id:cnqzTNngPVsAAAAAAAyj-g')]:
 r=str(row);x=removed[fid];assert b['values'][sn]['B'+r]==fid and b['values'][sn]['G'+r]==''and b['values'][sn]['K'+r]==0
 parent=history['surviving_parent_metadata'][x['old_parent_id']];setcell(sn,'D'+r,x['name']+' — removed while empty');linkcell(sn,'E'+r,'Surviving family folder','https://www.dropbox.com/home'+quote(parent['path_display'],safe='/'));setcell(sn,'H'+r,'');setcell(sn,'J'+r,'Removed empty folder; original paths and ID retained as history')
linkcell(sn,'A3','58 earlier folder rename records retained. Nine completed empty-folder removals are now recorded in the linked history. The two Dune Ripple White In Situ rows retain their old IDs and paths and navigate to the surviving family folder. No photograph was deleted.',str(out/'completed-changes.html'))
linkcell('Master Catalogue','A3','187 active individual options and one retired history row across112 component identities. Nine completed empty-folder removals recorded; stable IDs and historical aliases retained. Photograph coverage, qualified display references and physical specifications are unchanged. Open folder history for all nine entries.',str(out/'completed-changes.html'))
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):143,('Photo Coverage','F4'):116,('Missing Pictures','B4'):61,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
for(sn,c),value in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':value}
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
blocks=[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()]
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':blocks,'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':'Moonphases and Dune','row':r,'height':95}for r in [36,39]],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'baseline_ranges':[['Moonphases and Dune','B36:K36','baseline-removed-empty-folder']],'preview_ranges':[['Moonphases and Dune','B36:K36','01-dune-spiral-empty-history'],['Moonphases and Dune','B39:K39','02-dune-waves-empty-history'],['Photo Coverage','A2:F5','03-unchanged-image-summary']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'native_hyperlinks':len(links),'formula_text_changes':0}))
