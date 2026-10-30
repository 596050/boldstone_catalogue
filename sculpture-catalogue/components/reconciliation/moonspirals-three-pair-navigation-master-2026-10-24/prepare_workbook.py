"""Plan exact same-file navigation edits, preserving historical source columns."""
import importlib.util,json,posixpath,re
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs,quote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name;read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');proj=read(H/'projection-index.json');OLD=proj['old_output'];objects=proj['changed_native_objects'];paths={o['old_path'].casefold():o for o in objects.values()if o['old_path']};changes={};links={};nativechanges=[]
def refresh(u):
 if not u.startswith('https://www.dropbox.com/'):return u.replace(OLD,str(OUT))
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 o=paths.get(p.casefold());return u if not o else 'https://www.dropbox.com/preview'+quote(o['current_path'],safe='/')
def protected(sn,c):return sn=='Fingerprint History' or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
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
# Explicit image/folder and file/parent pairs. Source Mapping and Source Specifications IDs are historical.
pairs={'Master Catalogue':[('Q','R','N','O')],'Specifications':[('L','M','J','K')],'Components':[('H','I','F','G')],'Photo Coverage':[('M','N','D','E'),('O','P','G','H'),('Q','R','J','K')],'Listing Reconciliation':[('O','P','M','N')],'Listing Resolution':[('T','U','R','S')],'Selling Details':[('N','O','L','M')],'Draft Listings':[('K','L','I','J')],'Source Mapping':[('J',None,'H','I')],'Source Specifications':[('J',None,'H','I')]}
parent_cells=[]
for sn,groups in pairs.items():
 for filecol,parentcol,imagecol,foldercol in groups:
  for c,ident in w['values'][sn].items():
   if re.fullmatch(filecol+r'\d+',c)and ident in objects:
    o=objects[ident];row=re.sub('[A-Z]','',c);folder='https://www.dropbox.com/home'+quote(o['current_path'].rsplit('/',1)[0],safe='/')
    if parentcol:value(sn,parentcol+row,o['current_parent_id']);parent_cells.append(sn+'!'+parentcol+row)
    key=(sn,foldercol+row)
    if key in links:
     before=links[key]['target'];links[key]['target']=folder
     if before!=folder:nativechanges.append({'sheet':sn,'cell':key[1],'before':before,'current':folder,'basis':'Actual containing folder of this exact same-ID file'})
    if str(w['values'][sn].get(foldercol+row,'')).startswith('https://www.dropbox.com/'):value(sn,foldercol+row,folder)
text='188 active options;112 retained component IDs;110 working design groups. Three approved Moonspiral pair photo links refreshed. Two saved Wall Circle primaries are marked deleted in Dropbox history; matching local historical originals retained.'
value('Master Catalogue','A3',text);links[('Master Catalogue','A3')]={'sheet':'Master Catalogue','cell':'A3','label':text,'target':str(OUT/'moonspirals-pair-folder-changes.html')}
# Label only current links to the two historical primaries. Raw source columns remain intact.
wall=read(H/'wall-circle-history-observations.json')['rows'];by_url={x['saved_image_url']:x for x in wall.values()}
for key,x in links.items():
 if x['target']in by_url and not protected(*key)and x['label']=='Saved image (unverified)':value(*key,'Historical image (deleted)')
for sn,idcol,notecol in [('Master Catalogue','A','V'),('Photo Coverage','A','L')]:
 for c,ident in w['values'][sn].items():
  if re.fullmatch(idcol+r'\d+',c)and ident in wall:
   cell=notecol+re.sub('[A-Z]','',c);r=wall[ident]
   note='24 Oct exact-ID history: saved primary marked deleted '+r['server_deleted_utc']+'. Matching local historical original verified. No replacement or restore; owner hold retained.'
   prior=w['values'][sn].get(cell,'').replace('24 Oct Dropbox check: primary unresolved; folder verified. Source image retained; no replacement. Identity hold retained.','').rstrip()
   value(sn,cell,prior+'\n'+note)
for k,x in changes.items():
 if k in links:links[k]['label']=x['value']
expected={('Master Catalogue','B4'):188,('Master Catalogue','D4'):112,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):23,('Missing Pictures','D4'):1,('Missing Pictures','F4'):70,('Draft Listings','B4'):101,('Draft Listings','D4'):3}
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':v}for(sn,c),v in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':28,'expected_formula_count':3407,'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'native_link_changes':nativechanges,'actual_parent_cells':parent_cells,'baseline_ranges':[['Master Catalogue','A2:Y5','baseline-current-catalogue-header'],['Photo Coverage','L188:L190','baseline-wall-circle-notes']],'preview_ranges':[['Master Catalogue','A2:Y5','01-current-catalogue-header'],['Photo Coverage','L188:L190','02-wall-circle-notes']],'supplemental_preview_ranges':[['Missing Pictures','A2:F5','03-preserved-action-totals'],['Photo Coverage','C188:F190','04-wall-circle-labels']]}
plan['row_heights']=[{'sheet':sn,'row':r,'height':100}for sn in ['Master Catalogue','Photo Coverage']for r in [188,190]]
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'native_links':len(nativechanges),'actual_parent_cells':parent_cells}))
