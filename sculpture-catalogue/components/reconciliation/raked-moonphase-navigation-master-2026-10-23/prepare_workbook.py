"""Plan same-ID navigation links, one Series hold, and current summary cells."""
import hashlib,importlib.util,json,posixpath
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs,quote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('reader',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);w=v.load(H/'inputs/master_workbook.before');projection=read(H/'projection-index.json');objects=projection['changed_native_objects'];g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');OUT=B/'outputs'/H.name;OLD=projection['old_output'];changes={};links={}
def display(path):return '/'+path.split('//',1)[1].lstrip('/')if path.startswith('ns:')else path
paths={display(o['old_path']).casefold():i for i,o in objects.items()if o['old_path']}
def refresh(u):
 if not u.startswith('https://www.dropbox.com/'):return u.replace(OLD,str(OUT))
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 ident=paths.get(p.casefold())
 if not ident:return u
 obj=objects[ident];return 'https://www.dropbox.com/'+('home'if obj['object_type']=='folder'else'preview')+quote(display(obj['current_path']),safe='/')
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
def setcell(sn,c,value):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':value}
def link(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
native_link_changes=[]
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')];target=u if protected(sn,c)else refresh(u)
  links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':target}
  if target!=u and u.startswith('https://www.dropbox.com/'):native_link_changes.append({'sheet':sn,'cell':c,'before':u,'current':target})
 for c,text in w['values'][sn].items():
  if not protected(sn,c)and isinstance(text,str)and text.startswith('https://www.dropbox.com/'):
   updated=refresh(text)
   if updated!=text:setcell(sn,c,updated)
# Current folder metadata rows change only where the exact stable folder ID appears.
for c,text in w['values']['Moonphases and Dune'].items():
 if c.startswith('B')and text in objects:
  row=c[1:];obj=objects[text];setcell('Moonphases and Dune','D'+row,obj['current_name']);setcell('Moonphases and Dune','J'+row,obj['current_path'])
oid='BSI-C3573D23A4B7';row=next(i for i,o in enumerate(g['options'],10)if o['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid);setcell('Photo Coverage','U'+str(row),c['owner_review'])
for i,t in enumerate(a['missing_pictures'],10):
 if t['option_id']==oid and t['role']=='Series':setcell('Missing Pictures','M'+str(i),t['owner_response']);actionrow=i
prow=next(i for i,o in enumerate(g['options'],10)if o['product_id']=='BSI-3635E3DC3434');pc=next(x for x in a['coverage']if x['option_id']=='BSI-3635E3DC3434');setcell('Photo Coverage','U'+str(prow),pc['owner_review'])
for pi,pt in enumerate(a['missing_pictures'],10):
 if pt['option_id']=='BSI-3635E3DC3434'and pt['role']=='Series':setcell('Missing Pictures','M'+str(pi),pt['owner_response'])
link('Master Catalogue','A3','187 active options;112 working component identities. Raked Spiral, Moonphase and Workshop Views navigation refreshed by stable IDs.22 missing context roles and Dune2Copper Series are owner-held;16 Series requests remain active.',str(OUT/'navigation-and-owner-decisions.html'))
link('Photo Coverage','A3','177 complete individual,165 context and116 series references.22 missing context roles are held;0 context prompts.17 Series gaps remain:16 active and Dune2Copper held. Frozen Fish legacy identity stays deferred.',str(OUT/'remaining-photograph-requests.html'))
link('Missing Pictures','A3','40 diagnostic gaps retained:22 held context,17 Series (16 active and one held), and one deferred individual identity. Native navigation changes do not establish new sculpture identities or photograph matches.',str(OUT/'index.html'))
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):165,('Photo Coverage','F4'):116,('Missing Pictures','B4'):39,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':value}for(sn,c),value in expected.items()],'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':len(w['sheets']),'expected_formula_count':sum(map(len,w['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Sets and Context','H12:L12','baseline-raked-source-links'],['Photo Coverage','U'+str(row)+':V'+str(row),'baseline-dune-series-review']],'preview_ranges':[['Sets and Context','H12:L12','01-raked-source-links'],['Photo Coverage','U'+str(row)+':V'+str(row),'02-dune-series-owner-hold'],['Missing Pictures','L'+str(actionrow)+':N'+str(actionrow),'03-held-series-action'],['Master Catalogue','A1:Y3','04-navigation-refresh-summary']],'native_link_changes':native_link_changes,'dune_option_row':row,'dune_action_row':actionrow}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
builder=(H/'author_workbook.mjs').read_text().replace('GLOBAL_CONTEXT_OWNER_HOLD_MASTER_EXPORTED','RAKED_MOONPHASE_WORKSHOP_NAVIGATION_MASTER_EXPORTED');(H/'author_workbook.mjs').write_text(builder)
print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'same_ID_native_hyperlinks_refreshed':len(native_link_changes),'native_hyperlinks':len(links),'new_primary_bindings':0}))
