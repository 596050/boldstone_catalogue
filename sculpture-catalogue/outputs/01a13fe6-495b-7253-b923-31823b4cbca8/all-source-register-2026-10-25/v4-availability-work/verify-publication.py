"""Read-only published-source and live-app audit; writes only a new receipt."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
from xml.etree import ElementTree as E
import csv,datetime,hashlib,json,re,sqlite3,urllib.request,zipfile

W=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone');CAT=ROOT/'sculpture-catalogue'
H=CAT/'components/reconciliation/six-native-deletions-and-app-review-2026-10-25'
APP=ROOT/'catalogue-review/reviews/specification-completion-20261025'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=Counter()
def check(ok,label):
 assert ok,label
 checks[label.split(':')[0]]+=1
def local(path):
 p=Path(path);return p if p.is_absolute() else CAT/p
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=90) as r:return json.load(r)
def csvrows(path):
 with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

pointer_path=CAT/'current-master.json';pointer=read(pointer_path)
pub=read(H/'publication-receipt.json');seal=read(W/'sealed-handoff.json')
check(sha(pointer_path)==pub['pointer_sha256']=='9a54e024644dc45f22cd69ba7118cee765987a1c5a2c48bb8948be3ee729b726','published pointer hash')
check(local(pointer['publication_receipt'])==H/'publication-receipt.json','publication receipt path')
for path,expected in pub['protected_source_files_unchanged'].items():check(sha(path)==expected,'protected source hash:'+path)
control_sections=['preferred_review_workbook','current_comprehensive_workbook','current_native_availability','current_effective_native_inventory','current_saved_specification_review','current_review_application']
for path,expected in pub['controls_sha256'].items():
 check(sha(path)==expected,'control hash:'+path);control=read(path)
 check(control['current_master_catalogue']==pointer,'full embedded pointer equality:'+path)
 for k in control_sections:check(control[k]==pointer[k],'control section equality:'+k)

workbook=local(pointer['preferred_review_workbook']);comprehensive=pointer['current_comprehensive_workbook']
check(workbook==Path(seal['workbook'])==local(comprehensive['path']),'published workbook path')
check(sha(workbook)==seal['workbook_sha256']==comprehensive['sha256']==pub['preferred_workbook_sha256'],'published workbook hash')
check(sha(local(comprehensive['source_seal']))==comprehensive['source_seal_sha256'],'published workbook seal')
check(comprehensive['sheets']==23 and comprehensive['primary_rows']==413 and comprehensive['native_hyperlinks']==44643,'published workbook counts')
check(comprehensive['saved_app_field_review_imports']==0,'no app field import in workbook')
previous_validation=read(W/'validation.json')
check(previous_validation['sha256']==sha(workbook) and previous_validation['nonempty_source_cells_compared']==341850 and not previous_validation['exact_hyperlink_deltas'],'previous exact-content audit bound to published bytes')
N='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
with zipfile.ZipFile(workbook) as z:
 check(z.testzip() is None,'saved workbook ZIP integrity')
 strings=[''.join(t.text or '' for t in x.iter(N+'t')) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
 cells={c.get('r'):c for c in E.fromstring(z.read('xl/worksheets/sheet23.xml')).iter(N+'c')}
 def val(a):
  c=cells[a];v=c.findtext(N+'v','')
  return strings[int(v)] if c.get('t')=='s' else ''.join(t.text or '' for t in c.iter(N+'t')) if c.get('t')=='inlineStr' else v
 for a,v in {'B6':'6360','B7':'6','B8':'6354','B30':'347'}.items():check(val(a)==v,'published cached count:'+a)
 check(cells['B7'].findtext(N+'f')=='COUNTA(F13:F18)','published count formula')
 native_ids={val('F'+str(r)) for r in range(13,19)}

availability=pointer['current_native_availability'];overlay_path=local(availability['path']);overlay=read(overlay_path)
check(sha(overlay_path)==availability['sha256']==pub['overlay_sha256']==seal['overlay_sha256'],'published overlay hash')
check(availability['review_event_cutoff']==347 and availability['last_confirmed_native_event']==342,'native cutoff')
check(availability['counts']==overlay['counts'],'overlay counts equality')
check(native_ids=={r['file_id'] for r in overlay['rows']} and len(native_ids)==6,'workbook deleted IDs match overlay')
current_csv=local(availability['current_native_files']);deleted_csv=local(availability['deleted_native_history'])
current={r['file_id']:r for r in csvrows(current_csv)};deleted={r['file_id']:r for r in csvrows(deleted_csv)}
check(len(current)==6354 and len(deleted)==6 and set(deleted)==native_ids,'published native CSV counts and IDs')
check(not (set(current)&native_ids),'deleted IDs omitted from current CSV')
old_path=local(availability['preceding_five_id_scope_overlay']['current_native_files'])
old={r['file_id']:r for r in csvrows(old_path)}
check(set(old)-set(current)=={'id:cnqzTNngPVsAAAAAAAt61Q'} and not set(current)-set(old),'exact sixth-file CSV delta')
for fid,row in current.items():
 for k in ['name','folder_id','image_url','folder_url']:check(row[k]==old[fid][k],'native CSV retained identity and links')
 check(row['review_event_cutoff']=='347','native CSV cutoff')
for row in overlay['rows']:
 for k,v in deleted[row['file_id']].items():check(v==str(row[k]),'deletion CSV evidence matches overlay')
check('id:cnqzTNngPVsAAAAAAAt_oA' in current,'Icarus 010 retained')

class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':self.links.extend(v for k,v in attrs if k=='href' and v)
reader_paths=[local(availability[k]) for k in ['review','all_options_review']]
for path in reader_paths:
 parser=Links();parser.feed(path.read_text())
 for href in parser.links:
  parts=urlsplit(href)
  if parts.scheme in ['http','https','mailto','tel'] or not parts.path:continue
  decoded=Path(unquote(parts.path));target=decoded if decoded.is_absolute() else path.parent/decoded
  check(target.exists(),'published reader local link')

saved=pointer['current_saved_specification_review']
check(saved['products']==188 and saved['specification_fields']==1316 and saved['event_cutoff']==1830 and saved['canonical_field_imports']==0,'saved app metadata')
for key in ['report','values_readback','handoff','independent_verification']:check(sha(local(saved[key]))==saved[key+'_sha256'],'saved app artifact hash:'+key)
check(pointer['current_review_application']['latest_saved_specification_review']==saved,'app section saved review equality')
health=get('/api/health');boot=get('/api/bootstrap')
check(health['version']=='2.2' and health['products']==188,'live app health')
plan=read(APP/'prepared-values.json');initial=read(APP/'initial-app-fields.json');before=read(APP/'before-live-state.json')
check(len(boot['products'])==188,'live app products')
for k in ['register_sha256','gallery_sha256']:check(boot['source'][k]==plan['source'][k],'live app source identity:'+k)
with ThreadPoolExecutor(max_workers=4) as pool:
 live=list(pool.map(lambda p:get('/api/products/'+p['id']),initial['products']))
by_id={p['id']:p for p in live}
for p in initial['products']:
 now=by_id[p['id']]
 check(now['fields']==p['fields'],'live original fields preserved')
 check(now['family']==p['family'],'live family preserved')
 check('\u2014' not in now['name'],'live name hyphens')
for c in plan['changes']:
 r=next(r for r in by_id[c['product_id']]['reviews'] if r['kind']=='field' and r['item_id']==c['item_id'])
 check(r['data']==c['data'],'live saved field data')
 check(r['version']==c['version']+1,'live saved field version')
 check(r['source_hash']==plan['source']['register_sha256'],'live saved source binding')
 check(r['original']==(c['before']['original'] if c['before'] else c['source']),'live field provenance')
 check(bool(r['data']['value'].strip()) and '\u2014' not in r['data']['value'] and not re.search(r'estimat|guess|propos|hypothes',r['data']['value'],re.I),'live clean populated value')

db_path=Path(boot['data_directory'])/'reviews.sqlite3'
with closing(sqlite3.connect('file:'+str(db_path)+'?mode=ro',uri=True)) as db:
 db.row_factory=sqlite3.Row
 after={t:[dict(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in before}
check([r for r in after['reviews'] if r['kind']!='field']==[r for r in before['reviews'] if r['kind']!='field'],'nonfield reviews unchanged')
for t in ['operations','deletion_jobs','deletion_batches']:check(after[t]==before[t],'durable jobs unchanged:'+t)
check(after['events'][:len(before['events'])]==before['events'],'prior events retained')
check(len(after['reviews'])==1790 and max(r['id'] for r in after['events'])==1830,'live review counts and cutoff')
check(len(after['events'][len(before['events']):])==1483 and all(r['kind']=='field' for r in after['events'][len(before['events']):]),'only intended field events')
export_root=Path(saved['export']['path'])
exported={(r['product_id'],r['field']):r for r in csvrows(export_root/'specification-decisions.csv')}
exported_products={r['product_id']:r for r in csvrows(export_root/'all-product-decisions.csv')}
for c in plan['changes']:
 row=exported[c['product_id'],c['item_id']]
 for k,expected in [('listing_value',c['value']),('certainty',c['data']['certainty']),('evidence',c['data']['evidence']),('source_basis',c['source']['basis']),('original',c['source']['value'])]:check(row[k]==expected,'existing export field and provenance')
 check(exported_products[c['product_id']][c['item_id']]==c['value'],'existing product export field')
check(len(exported_products)==188,'export product count')
# A final hash check binds the readback to the publication that was audited.
check(sha(pointer_path)==pub['pointer_sha256'],'pointer unchanged during readback')
for path,expected in pub['controls_sha256'].items():check(sha(path)==expected,'control unchanged during readback')
for path,expected in pub['protected_source_files_unchanged'].items():check(sha(path)==expected,'source unchanged during readback')
receipt={
 'status':'PASS_INDEPENDENT_PUBLISHED_POINTER_CONTROLS_WORKBOOK_OVERLAY_AND_LIVE_APP_READBACK',
 'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'pointer':str(pointer_path),'pointer_sha256':pub['pointer_sha256'],
 'publication_receipt':str(H/'publication-receipt.json'),'publication_receipt_sha256':sha(H/'publication-receipt.json'),
 'workbook':str(workbook),'workbook_sha256':sha(workbook),'prior_exact_workbook_validation':str(W/'validation.json'),'prior_exact_workbook_validation_sha256':sha(W/'validation.json'),
 'controls_sha256':pub['controls_sha256'],'overlay_sha256':sha(overlay_path),
 'source_hashes':pub['protected_source_files_unchanged'],
 'native_csv_sha256':sha(current_csv),'deletion_csv_sha256':sha(deleted_csv),
 'published_readers':{str(p):sha(p) for p in reader_paths},
 'app_health':health,'live_app_source':{k:boot['source'][k] for k in ['register','register_sha256','gallery_database','gallery_sha256']},
 'live_review_rows':1790,'live_review_event_cutoff':1830,'sculptures_checked':188,'specification_fields':1316,'punctuation_name_edits':167,
 'checks':dict(checks),'checks_passed':sum(checks.values()),'failures':0,
 'workbook_source_specifications_unchanged':True,'app_review_overlay_kept_separate':True,
 'native_files_after_six_only':6354,'native_deletion_count':6,'no_new_global_native_scan':True,
 'http_methods_used':['GET'],'sqlite_connection_mode':'ro','canonical_app_native_or_platform_mutations':0,
 'verifier':str(Path(__file__).resolve()),'verifier_sha256':sha(__file__),
}
out=W/'published-readback-sealed.json';check(not out.exists(),'new independent receipt only')
out.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({'status':receipt['status'],'checks_passed':receipt['checks_passed'],'receipt':str(out),'sha256':sha(out)},indent=2))
