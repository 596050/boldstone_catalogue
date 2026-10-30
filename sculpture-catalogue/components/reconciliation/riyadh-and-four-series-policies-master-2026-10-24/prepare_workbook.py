"""Plan exact current links and four optional photograph requirements."""
import importlib.util,json,posixpath
from pathlib import Path
from urllib.parse import urlsplit,unquote,parse_qs,quote
from xml.etree import ElementTree as E
H=Path(__file__).resolve().parent;B=H.parents[2];OUT=B/'outputs'/H.name
read=lambda p:json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
s=importlib.util.spec_from_file_location('native',B/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(s);s.loader.exec_module(n)
w=n.load(H/'inputs/master_workbook.before');g=read(H/'canonical-master-register.json');a=read(H/'image-coverage-current.json');proj=read(H/'projection-index.json');OLD=proj['old_output']
objects=proj['changed_native_objects'];paths={o['old_path'].casefold():i for i,o in objects.items()if o['old_path']}
def refresh(u):
 if not u.startswith('https://www.dropbox.com/'):return u.replace(OLD,str(OUT))
 z=urlsplit(u);p=unquote(z.path)
 for route in ['/home','/preview']:
  if p.startswith(route+'/'):p=p[len(route):];break
 name=parse_qs(z.query).get('preview',[''])[0]
 if name:p+='/'+name
 ident=paths.get(p.casefold())
 if not ident:return u
 o=objects[ident];return 'https://www.dropbox.com/'+('home'if o['object_type']=='folder'else'preview')+quote(o['current_path'],safe='/')
def protected(sn,c):return sn=='Fingerprint History'or sn=='Source Specifications'and c.rstrip('0123456789')in ['M','N']or sn=='Moonphases and Dune'and c.rstrip('0123456789')=='I'
changes={};links={};heights=[];targets=[];nativechanges=[]
def value(sn,c,v):
 assert c not in w['formulas'][sn]
 if w['values'][sn].get(c,'')!=v:changes[(sn,c)]={'sheet':sn,'cell':c,'before':w['values'][sn].get(c,''),'value':v}
for sn,z in w['sheets'].items():
 rp=posixpath.join(posixpath.dirname(z['part']),'_rels',posixpath.basename(z['part'])+'.rels');rels={x.get('Id'):x.get('Target')for x in E.fromstring(w['files'][rp])}
 for x in z['root'].findall('.//'+n.q('hyperlink')):
  c=x.get('ref');u='#'+x.get('location')if x.get('location')else rels[x.get('{'+n.R+'}id')];new=u if protected(sn,c)else refresh(u)
  links[(sn,c)]={'sheet':sn,'cell':c,'label':w['values'][sn].get(c,''),'target':new}
  if new!=u and u.startswith('https://www.dropbox.com/'):nativechanges.append({'sheet':sn,'cell':c,'before':u,'current':new})
 for c,v in w['values'][sn].items():
  if isinstance(v,str)and v.startswith('https://www.dropbox.com/')and not protected(sn,c):value(sn,c,refresh(v))
for oid in proj['option_ids']:
 row=next(i for i,o in enumerate(g['options'],10)if o['product_id']==oid);c=next(x for x in a['coverage']if x['option_id']==oid)
 tr=next(i for i,t in enumerate(a['missing_pictures'],10)if t['option_id']==oid and t['role']=='Series');t=a['missing_pictures'][tr-10]
 targets.append({'option_id':oid,'row':row,'action_row':tr})
 for col,v in [('I',c['series']['status']),('U',c['owner_review']),('V','Optional group/series photograph — owner policy'),('L',c['series']['basis']+'\nEarlier role notes: '+w['values']['Photo Coverage']['L'+str(row)])]:value('Photo Coverage',col+str(row),v)
 value('Master Catalogue','V'+str(row),c['series']['basis']+'\nEarlier evidence notes: '+w['values']['Master Catalogue']['V'+str(row)])
 for col,k in [('E','action_type'),('F','action'),('L','qualification'),('M','owner_response'),('N','status')]:value('Missing Pictures',col+str(tr),t[k])
 for sn,rr in [('Photo Coverage',row),('Master Catalogue',row),('Missing Pictures',tr)]:heights.append({'sheet':sn,'row':rr,'height':210})
headers={
 'Master Catalogue':'188 active options;189 retained records;112 working component identities. Riyadh current folders and links refreshed by stable IDs. Four exact group/series photograph requirements are now optional. Existing identities, specifications and companion associations retained.',
 'Photo Coverage':'177 complete individual,166 qualified context and117 qualified Series references.9 required Series gaps:8 active and one held.62 Series optional;22 missing context requests held. One individual water-build photograph and one deferred Frozen Fish identity remain.',
 'Missing Pictures':'33 diagnostic requirements:22 held context,9 Series (8 active and one held), one individual water-build photograph and one deferred Frozen Fish identity. Four requirements made optional by owner policy. No additional photograph or physical specification verified.'}
for sn,text in headers.items():value(sn,'A3',text);links[(sn,'A3')]={'sheet':sn,'cell':'A3','label':text,'target':str(OUT/('navigation-and-owner-decisions.html'if sn=='Master Catalogue'else'remaining-photograph-requests.html'))}
for key,x in changes.items():
 if key in links:links[key]['label']=x['value']
expected={('Master Catalogue','B4'):188,('Master Catalogue','F4'):188,('Master Catalogue','H4'):187,('Photo Coverage','B4'):177,('Photo Coverage','D4'):166,('Photo Coverage','F4'):117,('Photo Coverage','B5'):11,('Missing Pictures','B4'):32,('Missing Pictures','D4'):1,('Missing Pictures','F4'):62}
riyadh=next(i for i,o in enumerate(g['options'],10)if o['product_id']=='BSI-B9DA00108196')
plan={'cell_changes':list(changes.values()),'formula_changes':[{'sheet':sn,'cell':c,'before':w['formulas'][sn][c],'formula':w['formulas'][sn][c],'expected':v}for(sn,c),v in expected.items()],
 'value_blocks':[{'sheet':x['sheet'],'range':x['cell'],'values':[[x['value']]]}for x in changes.values()],'formula_blocks':[],
 'hyperlinks':list(links.values()),'row_heights':heights,'table_appends':[],'new_sheets':{},'target_rows':[],
 'optional_action_row':targets[0]['action_row'],'expected_original_sheet_count':28,'expected_formula_count':3407,
 'summary_expected':[{'sheet':sn,'cell':c,'value':v}for(sn,c),v in expected.items()],'policy_targets':targets,'native_link_changes':nativechanges,
 'baseline_ranges':[['Photo Coverage','I'+str(targets[0]['row'])+':L'+str(targets[0]['row']),'baseline-series-policy'],['Photo Coverage','F'+str(riyadh)+':H'+str(riyadh),'baseline-riyadh-context']],
 'preview_ranges':[['Photo Coverage','I'+str(x['row'])+':L'+str(x['row']),'0'+str(i+1)+'-series-policy']for i,x in enumerate(targets)]+[['Photo Coverage','F'+str(riyadh)+':H'+str(riyadh),'05-riyadh-context']],
 'supplemental_preview_ranges':[['Missing Pictures','A2:F5','06-current-action-totals'],['Missing Pictures','L'+str(targets[2]['action_row'])+':N'+str(targets[2]['action_row']),'07-leaf-form-owner-scope']]}
write(H/'workbook-edit-plan.json',plan);write(H/'expected-edit.json',{'sheets':{},'hyperlinks':plan['hyperlinks'],'formulas':[]})
print(json.dumps({'status':'PLAN_READY','cell_changes':len(changes),'native_hyperlinks_refreshed':len(nativechanges),'native_hyperlinks':len(links),'targets':targets}))
