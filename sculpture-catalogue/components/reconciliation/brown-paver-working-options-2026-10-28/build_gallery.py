"""New source-only working references; no app review or Primary selection."""
from common import *
from copy import deepcopy
from html import escape as e
import shutil,sqlite3,hashlib,sys
new_options=read(H/'new-paver-options.json')
exclusions=read(H/'listing-use-exclusions.json')
dest=H/'gallery-projection';dest.mkdir(exist_ok=True);dbpath=dest/'complete-image-platform-register.sqlite'
html_only='--html-only' in sys.argv
assert not dbpath.exists() or html_only
if not html_only:shutil.copyfile(manifest['sources']['source_gallery']['snapshot'],dbpath)
db=sqlite3.connect(dbpath)
dump=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':'))
history_table='products_before_brown_paver_working_options_20261028'
if not html_only:
    db.execute('CREATE TABLE '+history_table+' AS SELECT * FROM products')
    for o in g['options']:db.execute('INSERT OR REPLACE INTO products VALUES(?,?,?,?)',(o['product_id'],o['name'],o['family'],dump(o)))
    added=[]
    for o in new_options:
        fid=o['file_id'];aid=hashlib.sha256(('OWNER-PAVER-WORKING-20261028|'+o['product_id']+'|'+fid).encode()).hexdigest()[:24]
        r={'association_id':aid,'product_id':o['product_id'],'file_id':fid,'intended_use':'selected_working_reference','association_status':'CURRENT_QUALIFIED_WORKING_APPEARANCE_REFERENCE','visual_role':'individual','image_url':o['image_url'],'folder_url':o['folder_url'],'folder_id':o['folder_id'],'evidence':[o['owner_addition_authority']],'qualification':'Accepted as the exact working appearance reference only. Listing, Advertising and Primary choices are unselected; physical finish, mould identity and measurements remain unverified.'}
        db.execute('INSERT INTO associations VALUES(?,?,?,?,?,?)',(aid,o['product_id'],fid,r['intended_use'],r['association_status'],dump(r)));added.append(aid)
    previous=db.execute("SELECT value_json FROM metadata WHERE key='current_navigation_publication'").fetchone()[0];db.execute('INSERT INTO metadata VALUES(?,?)',('navigation_before_brown_paver_additions_20261028',previous));nav=json.loads(previous);nav.update(register_sha256=sha(H/'canonical-master-register.json'),working_paver_additions_utc=manifest['recorded_utc'],active_options=187)
    db.execute("UPDATE metadata SET value_json=? WHERE key='current_navigation_publication'",(dump(nav),));db.execute('INSERT INTO metadata VALUES(?,?)',('brown_paver_working_option_admission_20261028',dump(g['latest_brown_paver_working_options'])));db.commit()
else:added=read(H/'association-additions.json')['added_association_ids']
assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
counts={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['products','images','associations','publication_current_images','publication_verified_deletions','publication_listing_use_exclusions','source_product_links']};db.close()
write(H/'association-additions.json',{'added_association_ids':added,'new_option_ids':[o['product_id'] for o in new_options],'reference_file_ids':[o['file_id'] for o in new_options],'automatic_listing_primary_or_advertising_choices':0,'old_associations_changed':0,'platform_source_links_added':0})
style = '<style>body{font:16px Arial;max-width:1150px;margin:32px auto;padding:0 20px;color:#243847}a{color:#17617d}article{border-top:1px solid #cbd4da;padding:18px 0}p{line-height:1.5}input{padding:10px;width:70%;font:inherit}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #dde3e7;padding:9px;vertical-align:top}.small{color:#51636e;font-size:14px}code{font-size:12px;overflow-wrap:anywhere}</style>'
script = '<script>document.querySelector("input").addEventListener("input",ev=>{let q=ev.target.value.toLowerCase();document.querySelectorAll("article").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script>'
def link(url, label):
    return '<a href="' + e(url, quote=True) + '">' + e(label) + '</a>' if url else e(label + ' unselected')
def page(title, content):
    return '<!doctype html><meta charset="utf-8"><title>' + e(title) + '</title>' + style + '<h1>' + e(title) + '</h1><p class="small">Two separate working Brown paver options added28October2026. Retained earlier image-use policy verified ' + e(manifest['retained_policy_cut_utc']) + '. Native image paths retain the separate ' + e(manifest['native_inventory_cut_utc']) + ' inventory cutoff. 187 active options; estimates and source qualifications remain.</p><p>' + link('index.html','Review home') + ' · ' + link('product-images.html','Individual options') + ' · ' + link('family-images.html','Image folders') + ' · ' + link('listing-use-exclusions.html','Listing exclusions') + '</p>' + content
articles = []
for o in sorted((x for x in g['options'] if x['product_id'] in active), key=lambda x:(x['family'],x['name'])):
    links = link(o.get('image_url'),'Working reference — Primary unselected' if o.get('catalogue_image_reference_only') else 'Primary picture') + ' · ' + link(o.get('folder_url'),'Containing folder')
    if o.get('context_image_url'): links += ' · ' + link(o['context_image_url'],'Context picture') + ' · ' + link(o['context_folder_url'],'Context folder')
    if o.get('current_series_reference'):
        s=o['current_series_reference']; links += ' · ' + link(s['image_url'],'Series picture') + ' · ' + link(s['folder_url'],'Series folder')
    fields = ''.join('<tr><td>' + e(k) + '</td><td>' + e(str(v.get('display',''))) + '<p class="small">' + e(str(v.get('state',''))) + ' | ' + e(str(v.get('basis',''))) + '</p></td></tr>' for k,v in o.get('master_fields',o['specifications']).items())
    exclusions_note = ('<p>Listing is excluded for ' + str(len(o['image_use_exclusions'])) + ' In situ image choices. Other purposes and context roles remain separately qualified.</p>') if o.get('image_use_exclusions') else ''
    role_label='Source reference; Primary unselected' if o.get('catalogue_image_reference_only') else 'Prior Primary/source reference'
    articles.append('<article id="' + o['product_id'] + '"><h2>' + e(o['name']) + '</h2><p>' + links + '</p><p class="small">' + e(o.get('context_description','')) + '</p>' + exclusions_note + '<table>' + fields + '</table><p><code>' + e(o['product_id']) + ' | '+role_label+' ' + e(o.get('file_id') or 'unbound') + '</code></p></article>')
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
for o in new_options:articles.append('<article><h2>'+e(o['name'])+'</h2><p>'+link(o['image_url'],'Working reference — Primary unselected')+' · '+link(o['folder_url'],'Containing folder')+'</p><p>No saved Listing, Advertising or Primary approval. No new capture is requested by default.</p></article>')
(dest/'index.html').write_text(page('Boldstone catalogue review','<p>187 active options;181 catalogue image references. Five earlier Primary/capture choices remain open, plus two new Brown working references with Primary unselected. Zero unheld series requests;30 context cases and one earlier series case stay held. Existing fields and12 new working proposals retain their evidence labels.</p><input aria-label="Filter requests" placeholder="Filter pending choices">' + ''.join(articles) + script))
write(dest/'sealed-handoff.json', {'status':'TWO_OWNER_WORKING_PAVER_ADDITIONS','register_sha256':sha(H/'canonical-master-register.json'),'database_sha256':sha(dbpath),'database':str(dbpath),'source_database':manifest['sources']['source_gallery'],'counts':counts,'source_history_table_map':{'products':history_table},'files':{p.name:sha(p) for p in dest.glob('*.html')},'source_images_associations_platform_tables_unchanged':True,'native_inventory_cut_utc':manifest['native_inventory_cut_utc'],'image_use_policy_cut_utc':manifest['retained_policy_cut_utc'],'native_app_or_platform_writes':0})
write(H/'gallery-preparation.json', {'status':'EXCLUSION_PROJECTION_PREPARED','database_sha256':sha(dbpath),'seal_sha256':sha(dest/'sealed-handoff.json'),'counts':counts})
print(json.dumps(counts))
