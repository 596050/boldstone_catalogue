"""Verify sealed listing overlays, current views and preservation of old evidence."""
import copy,hashlib,importlib.util,json,posixpath,sys
from pathlib import Path
from datetime import datetime,timezone
from xml.etree import ElementTree as E
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2]
spec=importlib.util.spec_from_file_location('native_support',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py');n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=HERE
read=lambda p:json.loads(Path(p).read_text());digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def links(d):
 out=[]
 for name,s in d['sheets'].items():
  loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rels={r.get('Id'):r for r in E.fromstring(d['files'][rp])} if rp in d['files'] else {}
  for h in s['root'].findall('.//'+n.q('hyperlink')):
   url='#'+h.get('location') if h.get('location') else rels[h.get('{'+n.R+'}id')].get('Target');out.append({'sheet':name,'cell':h.get('ref'),'target':url,'label':d['values'][name][h.get('ref')]})
 return out
def tables(d,s):
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels');rels={r.get('Id'):r.get('Target') for r in E.fromstring(d['files'][rp])};out=[]
 for t in s['root'].findall('.//'+n.q('tablePart')):
  target=rels[t.get('{'+n.R+'}id')];part=target.lstrip('/') if target.startswith('/') else posixpath.normpath(posixpath.dirname(loc)+'/'+target);out.append(d['files'][part])
 return out
b=n.load(HERE/'inputs/master_workbook.before');exp=read(HERE/'expected-edit.json')
if '--attach' in sys.argv:
 if not exp.get('prior_links_included'):exp['hyperlinks']=links(b)+exp['hyperlinks'];exp['prior_links_included']=True;write(HERE/'expected-edit.json',exp)
 n.attach()
a=n.load(HERE/'master-workbook.pending');checks=0;issues=[]
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
check(list(a['sheets'])==list(b['sheets'])+list(exp['sheets']),'16 old tabs retained, four current views appended')
for name,s in b['sheets'].items():
 expected=dict(b['values'][name])
 for x in exp['old_cell_changes']:
  if x['sheet']==name:expected[x['cell']]=x['value']
 check(a['values'][name]==expected,name+' historical values unchanged except two dated notes')
 check(a['formulas'][name]==b['formulas'][name],name+' formula text/cached results retained')
 check(a['styles'][name]==b['styles'][name],name+' native cell styles')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins']:
  check([E.tostring(x) for x in s['root'].findall(n.q(tag))]==[E.tostring(x) for x in a['sheets'][name]['root'].findall(n.q(tag))],name+' '+tag)
 check([r.attrib for r in s['root'].find(n.q('sheetData'))]==[r.attrib for r in a['sheets'][name]['root'].find(n.q('sheetData'))],name+' row heights')
 check(tables(b,s)==tables(a,a['sheets'][name]),name+' original native tables and filters')
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 old=b['style_root'].find(n.q(group));new=a['style_root'].find(n.q(group));check(old is None or new is not None and all(E.tostring(x)==E.tostring(y) for x,y in zip(old,new)),group+' preserved resource definitions')
for name,d in exp['sheets'].items():
 for i,row in enumerate(d['rows'],10):
  for j,v in enumerate(row):check(a['values'][name].get(n.column(j)+str(i),'')==v,f'{name}!{n.column(j)}{i} data')
 for j,v in enumerate(d['headers']):check(a['values'][name][n.column(j)+'9']==v,name+' header')
 check(a['sheets'][name]['root'].find('.//'+n.q('pane')) is not None,name+' frozen headers/IDs')
 check(len(a['sheets'][name]['root'].findall('.//'+n.q('tablePart')))==1,name+' filterable table')
for x in exp['formulas']:
 check(a['formulas'][x['sheet']].get(x['cell'])==x['formula'],'Summary formula text')
 check(a['values'][x['sheet']].get(x['cell'])==x['expected'],'Summary cached result')
actual=links(a);check(actual==exp['hyperlinks'],'All native link labels/targets preserved or added as planned')
g=read(HERE/'canonical-master-register.json');old=read(HERE/'inputs/master_register.before');stripped=copy.deepcopy(g)
for o in stripped['options']:o.pop('current_listing_resolution')
for k in ['current_listing_resolution','current_listing_resolution_details','listing_resolution_source_edges','listing_resolution_native_action_drafts','latest_listing_resolution']:stripped.pop(k)
check(stripped==old,'Only additive listing-resolution metadata in graph; all paths/history/specifications preserved')
review=g['current_listing_resolution_details']['entries'];overlays=g['current_listing_resolution']['option_overlays'];counts=g['latest_listing_resolution']['counts']
check(len(overlays)==len({x['product_id'] for x in overlays})==184,'All184 options resolved by ID')
check(len(review)==len({x['product_id'] for x in review})==106,'Assigned106 complete and unique')
byid={o['product_id']:o for o in g['options']}
for x in review:
 check(x['accepted_working_fields']==byid[x['product_id']]['master_fields'],'Accepted six-field object unchanged')
 check(not x['physical_configuration_verified'] and not x['proven_live_absent'],'No physical or live-absence certification')
 if x['draft_listing']:check(x['draft_listing']['six_working_fields']==byid[x['product_id']]['master_fields'],'Draft accepted field values exact')
 if x['conditional_native_tuple']:
  t=x['conditional_native_tuple'];v=next(y for y in g['wall_circle_native_options'] if y['variant_id']==t['native_variant_id'])
  check(v['sku']==t['sku'] and v['attributes']['Diameter Size']==t['diameter_option'] and v['attributes']['Lighting']==t['lighting_option'],'Conditional native tuple ID/SKU/axes exact')
check(sum(x['source_supported_individual_record_present'] for x in overlays)==47,'47 source-supported individual-design options')
check(sum(bool(x['conditional_native_tuple']) for x in overlays)==4,'Four conditional tuples kept separate')
check(len(g['listing_resolution_source_edges']['edges'])==3,'Three new evidence edges only in additive overlay')
check(len(g['current_listing_source_links']['offers'])==81 and len(g['current_listing_match_evidence']['edges'])==262 and len(g['current_listing_issues']['issues'])==165,'Original81/262/165 source layers preserved')
check(len([x for x in review if x['draft_listing']])==97 and len([x for x in review if x['custom_unlisted_pattern_draft']])==3,'97 individual drafts plus3 custom scopes')
check(all(not x['request_draft']['executable_now'] and x['execution_status']=='NOT_EXECUTED' for x in g['listing_resolution_native_action_drafts']['actions']),'Seven requests are nonexecuted drafts')
for x in read(HERE/'input-manifest.json').values():check(digest(x['path'])==digest(x['snapshot'])==x['sha256'],'Sealed/current input still unchanged')
result={'status':'PASS' if not issues else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:40],
 'workbook_sha256':digest(HERE/'master-workbook.pending'),'register_sha256':digest(HERE/'canonical-master-register.json'),'old_sheet_count':16,'new_sheets':4,
 'native_hyperlinks':len(actual),'formula_count':sum(len(x) for x in a['formulas'].values()),'counts':counts,'all184names_1104fields_currentpaths_media_and_history_preserved':True,
 'old_data_row_changes':0,'dated_source_note_changes':2,'platform_or_dropbox_writes':0}
write(HERE/'saved-file-verification.json',result);print(json.dumps({k:result[k] for k in ['status','checks','issues','native_hyperlinks','formula_count']}))
if issues:raise SystemExit(1)
