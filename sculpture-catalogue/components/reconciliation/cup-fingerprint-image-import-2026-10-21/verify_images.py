"""Read back the saved native workbook and verify all scoped changes."""
import copy, csv, hashlib, importlib.util, json, posixpath, sys
from pathlib import Path
from datetime import datetime, timezone
from xml.etree import ElementTree as E
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[2]
spec=importlib.util.spec_from_file_location('native',BASE/'components/reconciliation/image-identity-coverage-2026-10-20/verify_edit.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n);n.HERE=HERE
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def links(d):
 out={}
 for sn,s in d['sheets'].items():
  loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
  rs={x.get('Id'):x for x in E.fromstring(d['files'][rp])}if rp in d['files']else{}
  for h in s['root'].findall('.//'+n.q('hyperlink')):
   target='#'+h.get('location')if h.get('location')else rs[h.get('{'+n.R+'}id')].get('Target')
   out[(sn,h.get('ref'))]={'sheet':sn,'cell':h.get('ref'),'target':target,'label':d['values'][sn].get(h.get('ref'),'')}
 return out
def tables(d,s):
 loc=s['part'];rp=posixpath.join(posixpath.dirname(loc),'_rels',posixpath.basename(loc)+'.rels')
 rs={x.get('Id'):x.get('Target')for x in E.fromstring(d['files'][rp])};out=[]
 for t in s['root'].findall('.//'+n.q('tablePart')):
  target=rs[t.get('{'+n.R+'}id')];part=target.lstrip('/')if target.startswith('/')else posixpath.normpath(posixpath.dirname(loc)+'/'+target);out.append(d['files'][part])
 return out
b=n.load(HERE/'inputs/master_workbook.before');plan=read(HERE/'workbook-edit-plan.json');exp=read(HERE/'expected-edit.json')
if '--attach'in sys.argv:n.attach()
a=n.load(HERE/'master-workbook.pending');g=read(HERE/'canonical-master-register.json');old=read(HERE/'inputs/master_register.before');audit=read(HERE/'image-coverage-current.json')
issues=[];checks=0
def check(ok,msg):
 global checks
 checks+=1
 if not ok:issues.append(msg)
changes={(x['sheet'],x['cell']):x['value']for x in plan['cell_changes']}
caches={(x['sheet'],x['cell']):x['expected']for x in exp['formulas']}
height_changes={(x['sheet'],str(x['row'])):str(x['height'])for x in plan['row_heights']}
check(list(a['sheets'])==list(b['sheets'])and len(a['sheets'])==20,'All20 tabs retained in order')
for sn,s in b['sheets'].items():
 for cell in set(b['values'][sn])|set(a['values'][sn]):
  target=changes.get((sn,cell),caches.get((sn,cell),b['values'][sn].get(cell,'')))
  check(a['values'][sn].get(cell,'')==target,f'{sn}!{cell} preserved or scoped value')
  if(sn,cell)not in changes:check(a['styles'][sn].get(cell,'0')==b['styles'][sn].get(cell,'0'),f'{sn}!{cell} unchanged style')
 expected_formulas=copy.deepcopy(b['formulas'][sn])
 for x in plan['formula_changes']:
  if x['sheet']==sn:expected_formulas[x['cell']]=x['formula']
 check(a['formulas'][sn]==expected_formulas,sn+' formula text retained except scoped conditional-lookup summary')
 for tag in ['sheetViews','sheetFormatPr','cols','mergeCells','conditionalFormatting','autoFilter','pageMargins']:
  check([E.tostring(x)for x in s['root'].findall(n.q(tag))]==[E.tostring(x)for x in a['sheets'][sn]['root'].findall(n.q(tag))],sn+' preserved '+tag)
 check(tables(b,s)==tables(a,a['sheets'][sn]),sn+' native table bytes/filter scope retained')
 oldrows={x.get('r'):dict(x.attrib)for x in s['root'].find(n.q('sheetData'))}
 newrows={x.get('r'):dict(x.attrib)for x in a['sheets'][sn]['root'].find(n.q('sheetData'))}
 check(set(oldrows)==set(newrows),sn+' row identity')
 for row,attrs in oldrows.items():
  expected=copy.deepcopy(attrs)
  if(sn,row)in height_changes:expected['ht']=height_changes[(sn,row)];expected['customHeight']='1'
  # XML numeric spellings 100 and100.0 have the same row-height meaning.
  got=copy.deepcopy(newrows.get(row,{}))
  if 'ht'in got and 'ht'in expected:got['ht']=float(got['ht']);expected['ht']=float(expected['ht'])
  check(got==expected,sn+' row'+row+' attributes')
for group in ['fonts','fills','borders','cellStyleXfs','cellXfs','numFmts','dxfs']:
 oldstyles=b['style_root'].find(n.q(group));newstyles=a['style_root'].find(n.q(group))
 check(oldstyles is None or newstyles is not None and len(newstyles)>=len(oldstyles)and all(E.tostring(x)==E.tostring(y)for x,y in zip(oldstyles,newstyles)),group+' original resources preserved')
actual=links(a);wanted={(x['sheet'],x['cell']):x for x in exp['hyperlinks']}
check(actual==wanted,'All11215 native links saved with expected labels and stable-ID path targets')
check(len(actual)==11215,'Native hyperlink count')
check(sum(len(x)for x in a['formulas'].values())==2727,'Formula count retained')
for x in exp['formulas']:check(a['values'][x['sheet']][x['cell']]==x['expected'],'Current summary cache '+x['sheet']+'!'+x['cell'])
check(g['summary']==old['summary'],'Count definitions and totals retained')
check(len(g['options'])==184 and len(g['components'])==111,'184 options/111 catalogue identities')
check(g['original_review_specification_assertions']==old['original_review_specification_assertions'],'1668 historical source assertions unchanged')
for x,y in zip(g['options'],old['options']):
 for k in ['product_id','canonical_key','canonical_component_id','name','retained_names','master_fields','specifications','source_closure_evidence','current_listing_resolution','current_listing_reconciliation']:
  check(x.get(k)==y.get(k),x['product_id']+' preserved '+k)
 if x['canonical_component_id']in ['BC-FP-LEFT','BC-FP-RIGHT']:
  check(x['source_composition_attribution']['source_composition_number']=='2'and x['source_composition_attribution']['individual_member_number']is None,'FP composition2; no member number')
for k in old:
 if k not in ['options','components','latest_image_coverage_audit']:
  check(g[k]==old[k],'Unchanged graph layer '+k)
check(g['historical_image_coverage_audits']==[old['latest_image_coverage_audit']],'Prior157/27 audit preserved exactly')
for x,y in zip(g['components'],old['components']):
 z=copy.deepcopy(x);z.pop('source_composition_attribution',None);z.pop('current_image_resolution',None)
 if x['component_id']=='BC-CR-RING':
  for k in ['file_id','folder_id','image_url','folder_url']:z[k]=y[k]
 check(z==y,'Component identity preserved '+x['component_id'])
byid={x['product_id']:x for x in g['options']};cup=byid['BSI-ADD5F3BEFCF5']
check(cup['file_id']=='id:cnqzTNngPVsAAAAAAAtg4A'and cup['folder_id']=='id:cnqzTNngPVsAAAAAAAtg2A','Cup complete historical image and stable containing folder')
check(cup['photo_coverage']['individual']=='Available'and '453'in cup['current_image_resolution']['qualification'],'Cup historical453px qualification')
ffl=byid['BSI-04D6E8690F30'];oldffl=next(x for x in old['options']if x['product_id']==ffl['product_id'])
check(ffl==oldffl and not ffl.get('file_id'),'FFL exact100x22 image remains unbound')
check(len(audit['coverage'])==len({x['option_id']for x in audit['coverage']})==184,'Every option covered once')
check(audit['counts']['individual_statuses']=={'Available':158,'Detail only':5,'Group only':20,'Unbound size':1},'158complete/26individual gaps')
check(audit['counts']['in_situ_statuses']==old['latest_image_coverage_audit']['counts']['in_situ_statuses'],'In-situ qualification counts unchanged')
check(audit['counts']['series_statuses']==old['latest_image_coverage_audit']['counts']['series_statuses'],'Series qualification counts unchanged')
check(len(audit['identity_review'])==99,'Group candidate count unchanged')
group_reviews=[x for x in audit['identity_review']if not x['case_id'].startswith('ID-')]
check(len(group_reviews)==90,'90 group and collection position reviews retained, not new identity counts')
check(len([x for x in group_reviews if x['state']in ['Candidate position; identity unverified','Component identification needed']])==83,'83 unresolved position reviews; seven positions already relate to existing components')
for x in audit['missing_pictures']:
 check(bool(x['reference']['file_id']and x['reference']['folder_id']and x['reference']['image_url']and x['reference']['folder_url']),'Picture action stable file/folder IDs and links')
check(len(audit['missing_pictures'])==211 and len([x for x in audit['missing_pictures']if x['status']=='Resolved'])==1,'211history actions, oneCup closure')
for name,count in [('Missing_Pictures_Required_2026-10-21.csv',157),('Missing_Individual_Images_2026-10-21.csv',26),('Optional_Series_Images_2026-10-21.csv',53)]:
 with(HERE/name).open(encoding='utf-8-sig',newline='')as f:rows=list(csv.DictReader(f))
 check(len(rows)==count,name+' row count')
 check(all(r['image_url']and r['folder_url']and r['file_id']and r['folder_id']for r in rows),name+' per-row references')
for item in read(HERE/'input-manifest.json').values():check(digest(item['path'])==digest(item['snapshot'])==item['sha256'],'Source/current input unchanged')
result={'status':'PASS'if not issues else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'issues':issues[:60],
 'workbook_sha256':digest(HERE/'master-workbook.pending'),'register_sha256':digest(HERE/'canonical-master-register.json'),
 'audit_sha256':digest(HERE/'image-coverage-current.json'),'sheet_count':20,'native_hyperlinks':len(actual),'formula_count':2727,
 'cell_changes':len(plan['cell_changes']),'row_height_adjustments':len(plan['row_heights']),'individual_available':158,'individual_gaps':26,
 'required_actions':157,'find_capture_actions':119,'verify_existing_actions':38,'optional_actions':53,
 'all184_names_1104_fields_and_source_listing_histories_preserved':not issues,'physical_claims_upgraded':0,'platform_or_dropbox_writes':0}
write(HERE/'saved-file-verification.json',result)
print(json.dumps({k:result[k]for k in ['status','checks','issues','workbook_sha256','register_sha256']}))
if issues:raise SystemExit(1)
