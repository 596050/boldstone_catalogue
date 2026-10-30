"""Plan bounded current-navigation notes and link normalization."""
import importlib.util,json,posixpath,re
from pathlib import Path
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];norm=proj['case_only_replacements'];changes={};links={};nativechanges=[]
def protected(sn,c):return sn=='Fingerprint History' or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
def value(sn,c,v):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':v}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')];target=u if protected(sn,c)else norm.get(u,u.replace(OLD,str(OUT)));links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':target}
  if target!=u and u.startswith('https://www.dropbox.com/'):nativechanges.append({'sheet':sn,'cell':c,'before':u,'current':target})
 for c,v in w['values'][sn].items():
  if isinstance(v,str)and v in norm and not protected(sn,c):value(sn,c,norm[v])
text='188 active options;112 working component identities. Scoped Dropbox check:46 selected images and48 folders verified;2 Wall Circle primary references unresolved. Source-photo coverage retained. See navigation review.'
value('Master Catalogue','A3',text);links[('Master Catalogue','A3')]={'sheet':'Master Catalogue','cell':'A3','label':text,'target':str(OUT/'current-primary-navigation-health.html')}
value('Photo Coverage','A3','Source-photo coverage:177 complete individual views;10 accepted group references;11 technical gaps;0 capture requests. Separate native check:46/48 selected files and48/48 folders verified;2 Wall Circle references unresolved.22 context and1 Series request held; Frozen Fish identity deferred.')
note='24 Oct Dropbox check: primary unresolved; folder verified. Source image retained; no replacement. Identity hold retained.'
for row in [188,190]:
 assert w['values']['Master Catalogue']['A'+str(row)]in proj['option_ids']
 for sn,c in [('Master Catalogue','N'),('Photo Coverage','D')]:value(sn,c+str(row),'Saved image (unverified)')
 for sn,c in [('Master Catalogue','V'),('Photo Coverage','L')]:value(sn,c+str(row),w['values'][sn].get(c+str(row),'')+'\n'+note)
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
expected={('Master Catalogue','B4'):188,('Master Catalogue','D4'):112,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):23,('Missing Pictures','D4'):1,('Missing Pictures','F4'):70,('Draft Listings','B4'):101,('Draft Listings','D4'):3}
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':v}for(sn,c),v in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':28,'expected_formula_count':3407,'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'native_link_changes':nativechanges,
 'baseline_ranges':[['Master Catalogue','A2:Y5','baseline-catalogue-header'],['Photo Coverage','L188:L190','baseline-wall-circle-notes']],
 'preview_ranges':[['Master Catalogue','A2:Y5','01-current-catalogue-header'],['Photo Coverage','L188:L190','02-current-wall-circle-notes']],
 'supplemental_preview_ranges':[['Photo Coverage','A2:V5','03-source-photo-coverage-header'],['Master Catalogue','N188:O190','04-retained-saved-image-links']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'normalized_current_links':len(nativechanges)}))
