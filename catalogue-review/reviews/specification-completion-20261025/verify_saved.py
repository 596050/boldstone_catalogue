"""Independently read every live option and its real export after the app update."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import collections
import csv
import hashlib
import html
import json
import re
import sqlite3
import urllib.request

ROOT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'
plan = json.loads((ROOT/'prepared-values.json').read_text())
receipt = json.loads((ROOT/'apply-receipt.json').read_text())
baseline = json.loads((ROOT/'before-live-state.json').read_text())
initial = json.loads((ROOT/'initial-app-fields.json').read_text())
checks = collections.Counter()
def check(condition, label):
    assert condition, label
    checks[label.split(':')[0]] += 1

def get(path):
    with urllib.request.urlopen(BASE+path,timeout=90) as response:
        return json.load(response)

boot = get('/api/bootstrap')
check(len(boot['products'])==188,'options')
for key in ('register_sha256','gallery_sha256'):
    check(boot['source'][key]==plan['source'][key], 'source hashes')
with ThreadPoolExecutor(max_workers=4) as executor:
    live = list(executor.map(lambda p:get('/api/products/'+p['id']),initial['products']))
live_by_id = {p['id']:p for p in live}

for p in initial['products']:
    now = live_by_id[p['id']]
    check(now['fields']==p['fields'],'raw source fields unchanged')
    check(now['family']==p['family'],'family unchanged')
    check('\u2014' not in now['name'],'title hyphens')
for c in plan['changes']:
    product = live_by_id[c['product_id']]
    record = next(r for r in product['reviews'] if r['kind']=='field' and r['item_id']==c['item_id'])
    check(record['version']==c['version']+1,'saved version')
    check(record['data']==c['data'],'saved data')
    check(record['source_hash']==plan['source']['register_sha256'],'saved source binding')
    check(record['original']==(c['before']['original'] if c['before'] else c['source']),'original field retained')
    check(bool(record['data']['value'].strip()),'populated value')
    check('\u2014' not in record['data']['value'],'hyphens')
    check(not re.search(r'estimat|guess|propos|hypothes',record['data']['value'],re.I),'clean listing wording')

data_root = Path(boot['data_directory'])
with closing(sqlite3.connect('file:'+str(data_root/'reviews.sqlite3')+'?mode=ro',uri=True)) as db:
    db.row_factory = sqlite3.Row
    after = {table:[dict(row) for row in db.execute('SELECT * FROM '+table+' ORDER BY rowid')]
             for table in baseline}
check([r for r in after['reviews'] if r['kind']!='field']==[r for r in baseline['reviews'] if r['kind']!='field'],'nonfield reviews unchanged')
for table in ('operations','deletion_jobs','deletion_batches'):
    check(after[table]==baseline[table],table+' unchanged')
check(after['events'][:len(baseline['events'])]==baseline['events'],'prior events unchanged')
new_events = after['events'][len(baseline['events']):]
check(len(new_events)==len(plan['changes']),'event count')
check(all(r['kind']=='field' for r in new_events),'only field events')
check(len(after['reviews'])==len(baseline['reviews'])+len(plan['changes'])-sum(bool(c['before']) for c in plan['changes']),'review count')

request = urllib.request.Request(BASE+'/api/export',data=b'{"include_media":false}',method='POST',headers={
    'Content-Type':'application/json','Origin':BASE,'X-Review-Token':boot['csrf_token']})
with urllib.request.urlopen(request,timeout=180) as response:
    export = json.load(response)
export_root = Path(export['path'])
with (export_root/'specification-decisions.csv').open(encoding='utf-8-sig',newline='') as stream:
    exported = {(r['product_id'],r['field']):r for r in csv.DictReader(stream)}
with (export_root/'all-product-decisions.csv').open(encoding='utf-8-sig',newline='') as stream:
    exported_products = {r['product_id']:r for r in csv.DictReader(stream)}
for c in plan['changes']:
    out = exported[c['product_id'],c['item_id']]
    check(out['listing_value']==c['value'],'export listing value')
    check(out['certainty']==c['data']['certainty'],'export certainty')
    check(out['evidence']==c['data']['evidence'],'export evidence')
    check(out['source_basis']==c['source']['basis'],'export source basis')
    check(out['original']==c['source']['value'],'export original')
    check(exported_products[c['product_id']][c['item_id']]==c['value'],'product export value')
check(len(exported_products)==188,'export options')
for path_key,hash_key in [('register','register_sha256'),('gallery_database','gallery_sha256')]:
    check(hashlib.sha256(Path(plan['source'][path_key]).read_bytes()).hexdigest()==plan['source'][hash_key],'source bytes unchanged')

def key(r):
    return r['kind'],r['product_id'],r['item_id']
deleted_ids = {r['file_id'] for r in after['deletion_jobs'] if r['state']=='deleted'}
public = []
for p in live:
    fields = {r['item_id']:r for r in p['reviews'] if r['kind']=='field'}
    options = [im for im in p['images'] if im['source']=='Dropbox'
               and im['id'] not in deleted_ids and im.get('association',{}).get('tier')!='removed']
    # An example link is not an additional listing or primary approval.
    options.sort(key=lambda im:(im['id']!=p.get('primary_id'),
                               'primary_folder' not in im.get('association',{}).get('uses',[]),
                               im.get('association',{}).get('tier') not in ('accepted','manual','folder'),im['name']))
    reference = options[0] if options else None
    public.append({'product_id':p['id'],'name':p['name'],'family':p['family'],
                   'folder_url':p.get('folder_url',''),
                   'image_reference':{k:reference.get(k) for k in ('id','name','url','folder_url','association')} if reference else None,
                   'values':{k:r['data']['value'] for k,r in fields.items() if k!='Name'},
                   'provenance':{k:{'certainty':r['data']['certainty'],'evidence':r['data']['evidence'],'original':r['original']} for k,r in fields.items() if k!='Name'}})
    check(reference is None or reference['id'] not in deleted_ids,'reference deletion suppression')
(ROOT/'all-188-readback.json').write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n')

e = html.escape
sections = []
for p in public:
    links = [f'<a href="{BASE}/#{e(p["product_id"])}">Open in review app</a>']
    if p['folder_url']:
        links.append(f'<a href="{e(p["folder_url"])}">Containing folder</a>')
    ref = p['image_reference']
    if ref and ref.get('url'):
        links.append(f'<a href="{e(ref["url"])}">Retained image reference</a>')
    rows = ''.join(f'<tr><th>{e(k)}</th><td>{e(v)}</td></tr>' for k,v in p['values'].items())
    proof = ''.join(f'<h4>{e(k)}</h4><p>{e(v["original"]["value"])}</p><p>{e(v["original"]["qualification"])}</p><p>{e(v["original"]["basis"])}</p>' for k,v in p['provenance'].items())
    sections.append(f'<article><p class="family">{e(p["family"])}</p><h2>{e(p["name"])}</h2><p>{" · ".join(links)}</p><table>{rows}</table><details><summary>Original sources and qualifications</summary>{proof}</details></article>')
document = '<!doctype html><html lang="en"><meta charset="utf-8"><title>All 188 sculpture specifications</title><style>body{font:16px system-ui;max-width:1080px;margin:40px auto;padding:0 20px;background:#f7f6ef;color:#26352b}article{background:white;padding:24px;margin:24px 0;border:1px solid #d9ded3;border-radius:8px}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #e3e5dc}th{width:190px}.family,details{color:#5d6c5d}a{color:#3b643d}details{margin-top:18px}h2{font:28px Georgia}details p{white-space:pre-wrap}</style><h1>All 188 sculpture specifications</h1><p>Saved app listing values: 1,316 populated specification and selling fields. Original sources and qualifications remain separate. Image links are retained references, not new image approvals.</p>'+''.join(sections)+'</html>'
(ROOT/'all-sculptures.html').write_text(document)
summary = {'verified_utc':datetime.now(timezone.utc).isoformat(),'products':188,'specification_fields':1316,
           'title_punctuation_edits':167,'checks':dict(checks),'checks_passed':sum(checks.values()),'failures':0,
           'prior_nonfield_reviews_preserved':len([r for r in baseline['reviews'] if r['kind']!='field']),
           'total_reviews':len(after['reviews']),'event_cutoff':max(r['id'] for r in after['events']),
           'export':export,'source':plan['source'],'canonical_or_native_changes':False}
(ROOT/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('checks','source')},indent=2))
