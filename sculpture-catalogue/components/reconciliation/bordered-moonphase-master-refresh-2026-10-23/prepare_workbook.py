"""Refresh current scoped native links and expose additional008 in the existing views."""
import importlib.util,json,posixpath,re
from pathlib import Path
from urllib.parse import quote,unquote,urlsplit,parse_qs
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('v',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
b=v.load(H/'inputs/master_workbook.before');native=read(H/'current-native-reference-map.json');scoped=set(read(H/'import-summary.json')['changed_stable_ids']);oldout=Path(read(H/'inputs/source_report_verification.before')['output_directory']);out=B/'outputs'/H.name;changes={};links={};forms={}
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and re.fullmatch('[MN][0-9]+',c)or sn=='Moonphases and Dune'and re.fullmatch('I[0-9]+',c)
def currenturl(u):
 if not u.startswith('https://www.dropbox.com/'):return u
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 fid=native['old_path_to_id'].get(p.casefold())
 if fid not in scoped:return u
 x=native['current_objects'][fid];return 'https://www.dropbox.com/'+('preview'if x['object_type']=='file'else'home')+quote(x['display_path'],safe='/')
def setcell(sn,c,value):
 assert c not in b['formulas'][sn];before=b['values'][sn].get(c,'')
 if before!=value:changes[(sn,c)]={'sheet':sn,'cell':c,'before':before,'value':value}
def linkcell(sn,c,label,target):setcell(sn,c,label);links[(sn,c)]={'sheet':sn,'cell':c,'label':label,'target':target}
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
linkcell('Master Catalogue','A3','187 active individual options and one retired history row across112 component identities. Bordered Moonphase pair-folder links updated by stable ID. Original008 is an additional Moonphase1 reference in its actual containing folder. Selected primary images, specifications and photograph-role decisions are retained.',str(out/'bordered-moonphase-changes.html'))
linkcell('Photo Coverage','L134',b['values']['Photo Coverage']['L134']+'\nAdditional bordered Moonphase1 original008 is mapped to its actual individual folder. Selected001 primary retained. Open the linked folder review.',str(out/'bordered-moonphase-changes.html')+'#BSI-65A93033A200')
expected={('Photo Coverage','B4'):177,('Photo Coverage','B5'):10,('Photo Coverage','D4'):161,('Photo Coverage','F4'):116,('Missing Pictures','B4'):43,('Missing Pictures','D4'):1,('Missing Pictures','F4'):54,('Master Catalogue','H4'):186,('Master Catalogue','B4'):187,('Master Catalogue','F4'):187}
for(sn,c),value in expected.items():forms[(sn,c)]={'sheet':sn,'cell':c,'before':b['formulas'][sn][c],'formula':b['formulas'][sn][c],'expected':value}
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
oldlinks={}
for sn,z in b['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rr={x.get('Id'):x.get('Target')for x in E.fromstring(b['files'][rp])}if rp in b['files']else{}
 for x in z['root'].findall('.//'+v.q('hyperlink')):oldlinks[(sn,x.get('ref'))]='#'+x.get('location')if x.get('location')else rr[x.get('{'+v.R+'}id')]
native_changes=[{'sheet':sn,'cell':c,'before':oldlinks.get((sn,c)),'after':x['target']}for(sn,c),x in links.items()if x['target']!=oldlinks.get((sn,c))and x['target'].startswith('https://www.dropbox.com/')]
plan={'cell_changes':list(changes.values()),'formula_changes':list(forms.values()),'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],'hyperlinks':list(links.values()),'row_heights':[{'sheet':'Photo Coverage','row':134,'height':140}],'table_appends':[],'new_sheets':{},'target_rows':[],'expected_original_sheet_count':len(b['sheets']),'expected_formula_count':sum(map(len,b['formulas'].values())),'summary_expected':[{'sheet':sn,'cell':c,'value':value}for(sn,c),value in expected.items()],'baseline_ranges':[['Photo Coverage','I134:L134','baseline-bordered-series']],'preview_ranges':[['Photo Coverage','I134:L134','01-bordered-series-and-additional-reference'],['Master Catalogue','A1:H5','02-current-catalogue-summary']],'dropbox_link_changes':native_changes}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]});print(json.dumps({'status':'PLAN_READY','cells_changed':len(changes),'current_dropbox_destinations_refreshed':len(native_changes),'native_hyperlinks':len(links),'formula_text_changes':0}))
