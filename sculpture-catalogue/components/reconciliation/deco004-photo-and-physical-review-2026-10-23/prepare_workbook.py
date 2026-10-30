"""Plan current file004 links and actual parent cells; preserve the old002/003 folder."""
import importlib.util,json,posixpath,re
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);b=v.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');native=read(H/'current-native-reference-map.json');history=read(H/'path-change-history.json');r=history['reference'];fid=r['file_id'];out=B/'outputs'/H.name;oldout=Path(read(H/'inputs/source_report_verification.before')['output_directory']);changes={};links={};forms={}
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
def currenturl(u):
 if not u.startswith('https://www.dropbox.com/'):return u
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 ident=native['old_path_to_id'].get(p.casefold())
 if ident==fid:return r['image_url']
 if ident in {'id:cnqzTNngPVsAAAAAAAyh5w','id:cnqzTNngPVsAAAAAAAyh6w','id:cnqzTNngPVsAAAAAAAyh6g'}:
  obj=native['current_objects'][ident]
  return 'https://www.dropbox.com/'+('home'if obj['object_type']=='folder'else'preview')+quote(obj['display_path'],safe='/')
 return u
def setcell(sn,c,value):
 assert c not in b['formulas'][sn];before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def link(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
  if not protected(sn,c):u=currenturl(u).replace(str(oldout),str(out))
  links[(sn,c)]={'sheet':sn,'cell':c,'label':b['values'][sn].get(c,''),'target':u}
 for c,x in b['values'][sn].items():
  if not protected(sn,c)and isinstance(x,str)and x.startswith('https://www.dropbox.com/'):
   u=currenturl(x)
   if u!=x:setcell(sn,c,u)
for i,c in enumerate(a['coverage'],10):
 if c['option_id']not in history['affected_option_ids']:continue
 assert c['in_situ']['reference']['file_id']==fid
 for sn,col in [('Master Catalogue','U'),('Photo Coverage','H')]:link(sn,col+str(i),b['values'][sn][col+str(i)],r['folder_url'])
 setcell('Photo Coverage','P'+str(i),r['folder_id'])
for i,x in enumerate(a['missing_pictures'],10):
 if x['reference'].get('file_id')==fid:link('Missing Pictures','H'+str(i),b['values']['Missing Pictures']['H'+str(i)],r['folder_url']);setcell('Missing Pictures','J'+str(i),r['folder_id'])
notes=read(H/'owner-context-deferral-imports.json');note=notes[0]
setcell('Photo Coverage','U19','Owner held context review: '+note['owner_text']+'. Gap remains open; resume only on owner request.')
setcell('Missing Pictures','M42','Owner held on 23 October 2026: '+note['owner_text']+'. Context photograph remains unverified.')
setcell('Photo Coverage','U196','Owner held context review: '+notes[1]['owner_text']+'. Gap remains open; resume only on owner request.')
setcell('Missing Pictures','M215','Owner held on 23 October 2026: '+notes[1]['owner_text']+'. Context photograph remains unverified.')
link('Master Catalogue','A3','187 active options;112 working component identities. Deco004 actual parent and scene navigation refreshed by stable IDs.002/003 identity holds retained.187 physical source records reviewed; estimates preserved.',str(out/'deco004-changes.html'))
link('Specifications','A3','187 options and748 physical field groups reviewed. Accepted estimates and source qualifications retained; no new measured or inspected physical evidence supplied. Open the evidence checklist for each option.',str(out/'physical-evidence-review.html'))
link('Photo Coverage','A3','177 complete individual,165 context and116 series references. Remaining:12 active context,17 series,10 held context and one deferred Frozen Fish identity. Deco004 actual parent updated; existing image decisions retained.',str(out/'photograph-review-walkthrough.html'))
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):165,('Photo Coverage','F4'):116,('Missing Pictures','B4'):39,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
for(sn,c),value in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':value}
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
p={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','F44:K46','baseline-deco-context-links'],['Specifications','A1:L3','baseline-specification-review']],'preview_ranges':[['Photo Coverage','F44:K46','01-deco-context-links'],['Photo Coverage','O44:R46','02-deco-file-parent-ids'],['Specifications','A1:L3','03-physical-source-review-header'],['Photo Coverage','A2:F5','04-unchanged-coverage-counts']]}
write(H/'workbook-edit-plan.json',p);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':p['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'native_hyperlinks':len(links),'changed_parent_id_cells':6,'formula_text_changes':0}))
