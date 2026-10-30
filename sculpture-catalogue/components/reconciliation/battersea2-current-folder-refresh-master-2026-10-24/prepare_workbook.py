"""Plan current native hyperlinks and the selected context's actual parent ID."""
import importlib.util,json,posixpath
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs,quote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];objects=proj['changed_native_objects'];paths={o['old_path'].casefold():o for o in objects.values()if o['old_path']};changes={};links={};nativechanges=[]
def refresh(u):
 if not u.startswith('https://www.dropbox.com/'):return u.replace(OLD,str(OUT))
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 o=paths.get(p.casefold())
 return u if not o else 'https://www.dropbox.com/'+('home'if o['object_type']=='folder'else'preview')+quote(o['current_path'],safe='/')
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
def value(sn,c,v):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':v}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')];target=u if protected(sn,c)else refresh(u);links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':target}
  if target!=u and u.startswith('https://www.dropbox.com/'):nativechanges.append({'sheet':sn,'cell':c,'before':u,'current':target})
 for c,v in w['values'][sn].items():
  if isinstance(v,str)and v.startswith('https://www.dropbox.com/')and not protected(sn,c):value(sn,c,refresh(v))
row=next(i for i,o in enumerate(g['options'],10)if o['product_id']=='BSI-1B70A9FB1B26');o=g['options'][row-10]
assert w['values']['Photo Coverage']['O'+str(row)]==o['context_file_id']=='id:cnqzTNngPVsAAAAAAAud0g';value('Photo Coverage','P'+str(row),o['context_folder_id'])
for sn,col in [('Master Catalogue','U'),('Photo Coverage','H')]:
 key=(sn,col+str(row));before=links[key]['target'];links[key]['target']=o['context_folder_url']
 if before!=o['context_folder_url']:nativechanges.append({'sheet':sn,'cell':key[1],'before':before,'current':o['context_folder_url'],'basis':'Actual parent of selected context file; product folder itself remains unchanged'})
headers={
 'Master Catalogue':'188 active options;189 retained records;112 working component identities. Battersea Shellmoon2 current context links and actual containing folder refreshed by stable IDs. Existing photo selections, specifications and owner photo policies retained.',
 'Photo Coverage':'177 complete individual,166 qualified context and117 qualified Series references. Battersea2 context004 retains its selected role with new actual parent6VsA.70 Series photographs optional;one Series and22 context requests held. One individual water-build image and one deferred Frozen Fish identity remain.',
 'Missing Pictures':'25 diagnostic requirements retained:22 held context,one held Series, one individual water-build photograph and one deferred Frozen Fish identity. Battersea2 folder filing adds no new photographs, identities or physical verifications.'}
for sn,text in headers.items():value(sn,'A3',text);links[(sn,'A3')]={'sheet':sn,'cell':'A3','label':text,'target':str(OUT/('battersea-folder-changes.html'if sn=='Master Catalogue'else'remaining-photograph-requests.html'))}
for k,x in changes.items():
 if k in links:links[k]['label']=x['value']
expected={('Master Catalogue','B4'):188,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):24,('Missing Pictures','D4'):1,('Missing Pictures','F4'):70}
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':v}for(sn,c),v in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':28,'expected_formula_count':3407,'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'native_link_changes':nativechanges,
 'baseline_ranges':[['Photo Coverage','M'+str(row)+':P'+str(row),'baseline-context-identifiers']],
 'preview_ranges':[['Photo Coverage','M'+str(row)+':P'+str(row),'01-context-identifiers'],['Photo Coverage','F'+str(row)+':H'+str(row),'02-context-navigation']],
 'supplemental_preview_ranges':[['Missing Pictures','A2:F5','03-unchanged-action-totals']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'native_links':len(nativechanges),'actual_parent_cell':'Photo Coverage!P'+str(row)}))
