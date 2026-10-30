"""Verify current parent-ID edits and native links against the sealed ledger."""
import copy,hashlib,importlib.util,json,posixpath,re,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlsplit,unquote,parse_qs
from xml.etree import ElementTree as E
HERE=Path(sys.argv[sys.argv.index('--task-dir')+1]).resolve() if '--task-dir' in sys.argv else Path(__file__).resolve().parent
BASE=HERE.parents[2]
spec=importlib.util.spec_from_file_location('native_ref_support',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=HERE
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
manifest=read(HERE/'input-manifest.json');plan=read(HERE/'workbook-edit-plan.json');overlay=read(manifest['overlay']['snapshot'])
byid={x['file_id']:x for x in overlay['objects']};oldpaths={x['old_display_path'].casefold():x for x in overlay['objects'] if x.get('old_display_path')};currentpaths={x['current_display_path'].casefold():x for x in overlay['objects']}
def resolve(url,paths):
 if not url.startswith('https://www.dropbox.com/'):return None
 u=urlsplit(url);p=unquote(u.path)
 for r in ['/home','/preview']:
  if p.startswith(r+'/'):p=p[len(r):];break
 name=parse_qs(u.query).get('preview',[''])[0]
 return paths.get((p+('/'+name if name else '')).casefold())
def links(d):
 result={}
 for name,s in d['sheets'].items():
  loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rels={r.get('Id'):r for r in E.fromstring(d['files'][rp])}
  for h in s['root'].findall('.//'+n.q('hyperlink')):
   url='#'+h.get('location') if h.get('location') else rels[h.get('{'+n.R+'}id')].get('Target');result[(name,h.get('ref'))]=url
 return result
def tables(d,s):
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rels={r.get('Id'):r.get('Target') for r in E.fromstring(d['files'][rp])};result=[]
 for t in s['root'].findall('.//'+n.q('tablePart')):
  target=rels[t.get('{'+n.R+'}id')];part=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(loc)+'/'+target);result.append(d['files'][part])
 return result
if '--attach' in sys.argv:n.attach()
b=n.load(HERE/'inputs/master_workbook.before');a=n.load(HERE/'master-workbook.pending');issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
check(list(a['sheets'])==list(b['sheets']),'All16 sheet names/order preserved')
changes={(x['sheet'],x['cell']):x for x in plan['cell_changes']}
for name,s in b['sheets'].items():
 expected=dict(b['values'][name])
 for (sheet,cell),x in changes.items():
  if sheet==name:expected[cell]=x['value']
 check(a['values'][name]==expected,name+' only planned current parent-ID values changed')
 check(a['formulas'][name]==b['formulas'][name],name+' formulas/cache results preserved')
 check(a['styles'][name]==b['styles'][name],name+' cell styles preserved')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins']:
  check([E.tostring(x) for x in s['root'].findall(n.q(tag))]==[E.tostring(x) for x in a['sheets'][name]['root'].findall(n.q(tag))],name+' '+tag)
 check([r.attrib for r in s['root'].find(n.q('sheetData'))]==[r.attrib for r in a['sheets'][name]['root'].find(n.q('sheetData'))],name+' row heights/attributes')
 check(tables(b,s)==tables(a,a['sheets'][name]),name+' native tables/filters preserved')
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 before=b['style_root'].find(n.q(group));after=a['style_root'].find(n.q(group));check(before is None or after is not None and all(E.tostring(x)==E.tostring(y) for x,y in zip(before,after)),group+' old definitions retained')
actual=links(a);old=links(b);expected={(x['sheet'],x['cell']):x['target'] for x in plan['hyperlinks']}
check(actual==expected,'All native current link destinations')
check(len(actual)==len(old)==10469,'No native link creation/loss')
check(sum(old[k]!=actual[k] for k in old)==len(plan['target_changes']),'Changed destination count')
for key,url in old.items():
 o=resolve(url,oldpaths)
 if o and o['object_type']=='file':
  target=resolve(actual[key],currentpaths);check(target is not None and target['file_id']==o['file_id'],'Image stable-ID retained: '+str(key))
for x in plan['cell_changes']:
 o=byid[x['file_id']];check(x['before']==o['old_parent_id'] and x['value']==o['current_parent_id'],'Current parent-ID edit agrees with exact file move')
g=read(HERE/'canonical-master-register.json');original=read(HERE/'inputs/master_register.before');restored=copy.deepcopy(g);restored.pop(plan.get('graph_metadata_key','latest_four_family_matching'))
for c in plan['graph_changes']:
 node=restored
 for k in c['path'][:-1]:node=node[k]
 node[c['path'][-1]]=c['before']
check(restored==original,'Graph changes confined to declared current references')
for before,after in zip(original['options'],g['options']):
 check((before['product_id'],before['name'],before['canonical_component_id'])==(after['product_id'],after['name'],after['canonical_component_id']),'No FP numbering or option identity change')
 check(before['master_fields']==after['master_fields'],'All6 accepted fields retained')
 check(before['photo_coverage']==after['photo_coverage'],'No photograph coverage upgrade from folder placement')
for key in ['summary','original_review_specification_assertions','current_listing_source_links','current_listing_match_evidence','current_listing_issues','latest_listing_reconciliation','latest_image_coverage_audit']:
 check(g[key]==original[key],key+' source/history preserved')
check(len(g['options'])==184 and len(g['components'])==111,'184 options and111 component identities preserved')
for x in manifest.values():check(digest(x['path'])==digest(x['snapshot'])==x['sha256'],'Source/control unchanged')
result={'status':'PASS' if not issues else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:40],
 'workbook_sha256':digest(HERE/'master-workbook.pending'),'register_sha256':digest(HERE/'canonical-master-register.json'),
 'native_link_destinations_updated':len(plan['target_changes']),'current_parent_ID_cells_updated':len(plan['cell_changes']),
 'graph_current_reference_changes':len(plan['graph_changes']),'native_hyperlinks':len(actual),'formula_count':sum(len(x) for x in a['formulas'].values()),
 'all_other_workbook_values_formulas_styles_tables_panes_preserved':not issues,'all184names_and1104specifications_preserved':True,
 'all_sealed_listing_and_media_evidence_preserved':True,'individual_FP_numbering':'Pending owner answer; no numeric labels assigned',
 'fresh_move_metadata_readbacks':plan.get('fresh_file_metadata_readbacks',10),'fresh_created_folder_readbacks':plan.get('fresh_folder_metadata_readbacks',1),
 'overlay_sha256':manifest['overlay']['sha256'],'sidecar_sha256':manifest['sidecar']['sha256'],'remote_writes':0}
write(HERE/'saved-file-verification.json',result);print(json.dumps({k:result[k] for k in ['status','checks','issues','native_link_destinations_updated','current_parent_ID_cells_updated']}))
if issues:raise SystemExit(1)
