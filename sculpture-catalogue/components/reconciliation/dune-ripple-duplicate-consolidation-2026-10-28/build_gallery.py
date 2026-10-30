"""Preserve the full source gallery and add the exact current exclusion layer."""
from common import *
from copy import deepcopy
from html import escape as e
import shutil, sqlite3

dest = H / 'gallery-projection'
dest.mkdir(exist_ok=True)
dbpath = dest / 'complete-image-platform-register.sqlite'
assert not dbpath.exists()
shutil.copyfile(manifest['sources']['source_gallery']['snapshot'], dbpath)
db = sqlite3.connect(dbpath)
dump = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':'))
history = 'products_before_dune_ripple_alias_20261028'
db.execute('CREATE TABLE ' + history + ' AS SELECT * FROM products')
for o in g['options']:
    db.execute('UPDATE products SET name=?,family=?,record_json=? WHERE product_id=?', (o['name'], o['family'], dump(o), o['product_id']))
KEEP='BSI-9299D69FEF08';DUP='BSI-4536FDCA0DA9'
exclusions=read(H/'listing-use-exclusions.json')
added=[]
for raw in db.execute('SELECT * FROM associations WHERE product_id=?',(DUP,)).fetchall():
    aid,pid,fid,use,status,record_json=raw
    if fid not in {'id:cnqzTNngPVsAAAAAAAyegw','id:cnqzTNngPVsAAAAAAAykxw'} or status not in {'CURRENT_ACCEPTED_REFERENCE','CURRENT_QUALIFIED_CONTEXT_REFERENCE'}:continue
    r=json.loads(record_json);newid=__import__('hashlib').sha256(('DUNE-MERGE-20261028|'+KEEP+'|'+aid).encode()).hexdigest()[:24]
    r.update(association_id=newid,product_id=KEEP,merged_from_option_id=DUP,merged_from_association_id=aid,owner_merge_decision=read(H/'merge-decision.json'),scope='Original accepted-reference qualification retained by exact owner alias merge. Context hold and current series selection stay separate; other folder candidates are not approved.')
    nav=files[fid];r.update(image_url=nav['image_url'],folder_url=nav['folder_url'],folder_id=nav['folder_id'])
    db.execute('INSERT INTO associations VALUES(?,?,?,?,?,?)',(newid,KEEP,fid,use,status,dump(r)));added.append(newid)
assert len(added)==2
platform=[]
for offer,pid,relationship,record_json in db.execute('SELECT * FROM source_product_links WHERE product_id=?',(DUP,)).fetchall():
    r=json.loads(record_json);r.update(product_id=KEEP,merged_from_option_id=DUP,owner_merge_decision_id=read(H/'merge-decision.json')['decision_id'],merged_source_qualification='Original source and field claims retained as evidence. Keeper working specifications and exact native configuration limits are unchanged.')
    db.execute('INSERT INTO source_product_links VALUES(?,?,?,?)',(offer,KEEP,relationship,dump(r)));platform.append(offer)
assert 'O009' in platform
write(H/'association-union.json',{'added_association_ids':added,'qualified_platform_offer_links':platform,'accepted_reference_ids':['id:cnqzTNngPVsAAAAAAAyegw','id:cnqzTNngPVsAAAAAAAykxw'],'old_all_image_ids_subset_of_keeper':True,'current_image_id_union':60,'other_candidates_promoted':0,'source_rows_deleted':0})
previous = db.execute("SELECT value_json FROM metadata WHERE key='current_navigation_publication'").fetchone()[0]
db.execute('INSERT INTO metadata VALUES(?,?)', ('navigation_before_dune_ripple_alias_20261028', previous))
nav = json.loads(previous)
nav.update(register_sha256=sha(H/'canonical-master-register.json'), native_inventory_cut_utc=manifest['native_inventory_cut_utc'], image_use_policy_cut_utc=manifest['retained_policy_cut_utc'], image_use_exclusions=91)
db.execute("UPDATE metadata SET value_json=? WHERE key='current_navigation_publication'", (dump(nav),))
db.execute('INSERT INTO metadata VALUES(?,?)', ('dune_ripple_owner_duplicate_merge_20261028', dump(read(H/'merge-decision.json'))))
db.commit()
assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
counts = {t: db.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0] for t in ['products','images','associations','publication_current_images','publication_verified_deletions','publication_listing_use_exclusions','source_product_links']}
db.close()

style = '<style>body{font:16px Arial;max-width:1150px;margin:32px auto;padding:0 20px;color:#243847}a{color:#17617d}article{border-top:1px solid #cbd4da;padding:18px 0}p{line-height:1.5}input{padding:10px;width:70%;font:inherit}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #dde3e7;padding:9px;vertical-align:top}.small{color:#51636e;font-size:14px}code{font-size:12px;overflow-wrap:anywhere}</style>'
script = '<script>document.querySelector("input").addEventListener("input",ev=>{let q=ev.target.value.toLowerCase();document.querySelectorAll("article").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script>'
def link(url, label):
    return '<a href="' + e(url, quote=True) + '">' + e(label) + '</a>' if url else e(label + ' unselected')
def page(title, content):
    return '<!doctype html><meta charset="utf-8"><title>' + e(title) + '</title>' + style + '<h1>' + e(title) + '</h1><p class="small">Owner duplicate merge: 28 October 2026. Retained earlier image-use policy verified ' + e(manifest['retained_policy_cut_utc']) + '. Native image paths retain the separate ' + e(manifest['native_inventory_cut_utc']) + ' inventory cutoff. 185 active options; estimates and source qualifications remain.</p><p>' + link('index.html','Review home') + ' · ' + link('product-images.html','Individual options') + ' · ' + link('family-images.html','Image folders') + ' · ' + link('listing-use-exclusions.html','Listing exclusions') + '</p>' + content
articles = []
for o in sorted((x for x in g['options'] if x['product_id'] in active), key=lambda x:(x['family'],x['name'])):
    links = link(o.get('image_url'),'Primary picture') + ' · ' + link(o.get('folder_url'),'Containing folder')
    if o.get('context_image_url'): links += ' · ' + link(o['context_image_url'],'Context picture') + ' · ' + link(o['context_folder_url'],'Context folder')
    if o.get('current_series_reference'):
        s=o['current_series_reference']; links += ' · ' + link(s['image_url'],'Series picture') + ' · ' + link(s['folder_url'],'Series folder')
    fields = ''.join('<tr><td>' + e(k) + '</td><td>' + e(str(v.get('display',''))) + '<p class="small">' + e(str(v.get('state',''))) + ' | ' + e(str(v.get('basis',''))) + '</p></td></tr>' for k,v in o.get('master_fields',o['specifications']).items())
    exclusions_note = ('<p>Listing is excluded for ' + str(len(o['image_use_exclusions'])) + ' In situ image choices. Other purposes and context roles remain separately qualified.</p>') if o.get('image_use_exclusions') else ''
    articles.append('<article id="' + o['product_id'] + '"><h2>' + e(o['name']) + '</h2><p>' + links + '</p><p class="small">' + e(o.get('context_description','')) + '</p>' + exclusions_note + '<table>' + fields + '</table><p><code>' + e(o['product_id']) + ' | Primary ' + e(o.get('file_id') or 'unbound') + '</code></p></article>')
(dest/'product-images.html').write_text(page('Individual sculptures and working specifications','<input aria-label="Filter sculptures" placeholder="Filter by sculpture or ID">' + ''.join(articles) + script))
articles = ['<article><p>' + link(r['image_url'],r['name']) + ' · ' + link(r['folder_url'],'Containing folder') + '</p><p class="small">' + e(r['path']) + '</p><code>' + e(r['file_id']) + ' | ' + e(r['folder_id']) + '</code></article>' for r in overlay]
(dest/'family-images.html').write_text(page('Retained native image and folder index','<p>5,237 files from the declared 19:03 UTC native cut. This is a dated navigation index, not a newer native census or a count of sculptures.</p><input aria-label="Filter images" placeholder="Filter by filename, folder or ID">' + ''.join(articles) + script))
articles = []
for x in exclusions:
    articles.append('<article><h2>' + e(x['name']) + '</h2><p>Listing removed; remaining purposes: ' + e(', '.join(x['remaining_uses']) or 'none') + '. Primary cleared: ' + str(x['primary_cleared']) + '.</p><p>' + link(x['image_url'],'Excluded Listing image') + ' · ' + link(x['folder_url'],'Containing folder') + '</p><p class="small">' + e(x['scope']) + '</p><code>' + e(x['product_id']) + ' | ' + e(x['file_id']) + ' | review ' + str(x['review_version']) + '</code></article>')
(dest/'listing-use-exclusions.html').write_text(page('In situ images excluded from Listing','<p>91 component/image choices across 68 images and 30 active options. Four Primary choices cleared; no replacement guessed.</p><input aria-label="Filter exclusions" placeholder="Filter by sculpture or stable ID">' + ''.join(articles) + script))
articles = []
for o in g['options']:
    if o['product_id'] not in active or not o.get('historical_primary_reference') or o.get('file_id'): continue
    history=o['historical_primary_reference']
    description = 'The original remains retained, but its In situ tag excludes it from Listing.' if history.get('reason')=='in_situ_listing_exclusion' else 'The previous Primary is unavailable; its historical stable ID is retained.'
    articles.append('<article><h2>' + e(o['name']) + '</h2><p>Replacement Primary remains unselected. ' + description + '</p><p>' + link(o['folder_url'],'Containing folder') + '</p></article>')
(dest/'index.html').write_text(page('Boldstone catalogue review','<p>185 active options; 179 selected Primary references. Five Primary choices are open, zero unheld series requests, 28 context cases and one prior series case on hold. All physical/commercial fields retain their previous evidence.</p><input aria-label="Filter requests" placeholder="Filter pending choices">' + ''.join(articles) + script))
write(dest/'sealed-handoff.json', {'status':'EXACT_OWNER_DUNE_RIPPLE_DUPLICATE_PROJECTION','register_sha256':sha(H/'canonical-master-register.json'),'database_sha256':sha(dbpath),'database':str(dbpath),'source_database':manifest['sources']['source_gallery'],'counts':counts,'source_history_table_map':{'products':history},'files':{p.name:sha(p) for p in dest.glob('*.html')},'source_images_associations_platform_tables_unchanged':True,'native_inventory_cut_utc':manifest['native_inventory_cut_utc'],'image_use_policy_cut_utc':manifest['retained_policy_cut_utc'],'native_app_or_platform_writes':0})
write(H/'gallery-preparation.json', {'status':'EXCLUSION_PROJECTION_PREPARED','database_sha256':sha(dbpath),'seal_sha256':sha(dest/'sealed-handoff.json'),'counts':counts})
print(json.dumps(counts))
