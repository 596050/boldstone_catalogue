"""Create a new immutable projection; never change the captured source database."""
from common import *
from copy import deepcopy
from html import escape as e
from urllib.parse import quote
from collections import Counter
import shutil, sqlite3, subprocess

dest=H/'gallery-projection';dest.mkdir(exist_ok=True)
dbpath=dest/'complete-image-platform-register.sqlite'
assert not dbpath.exists(), 'Do not overwrite an existing projection'
result=subprocess.run(['cp','-c',manifest['sources']['source_gallery']['snapshot'],str(dbpath)],capture_output=True)
if result.returncode:shutil.copyfile(manifest['sources']['source_gallery']['snapshot'],dbpath)
db=sqlite3.connect(dbpath)
history_suffix='before_latest_cleanup_20261027'
db.execute('CREATE TABLE publication_original_products_'+history_suffix+' AS SELECT * FROM products')
db.execute('ALTER TABLE publication_current_images RENAME TO publication_current_images_'+history_suffix)
db.execute('ALTER TABLE publication_verified_deletions RENAME TO publication_verified_deletions_'+history_suffix)
db.execute('CREATE TABLE publication_current_images(file_id TEXT PRIMARY KEY,record_json TEXT NOT NULL)')
db.execute('CREATE TABLE publication_verified_deletions(file_id TEXT PRIMARY KEY,record_json TEXT NOT NULL)')
deleted=read(CUT/'verified-deletion-tombstones.json')
dump=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
for o in g['options']:
    db.execute('INSERT OR REPLACE INTO products VALUES(?,?,?,?)',(o['product_id'],o['name'],o.get('family',''),dump(o)))
oldimages={fid:json.loads(raw) for fid,raw in db.execute('SELECT file_id,record_json FROM images')}
for fid,r in files.items():
    before=oldimages.get(fid)
    im=deepcopy(before) if before else {'file_id':fid,'is_image':True,'inventory_status':'New current native photograph; exact option identity requires separate review.','visual_role':'uncertain','visual_review_status':'Native metadata only','metadata':{},'saved_asset_metadata':{},'visual_role_evidence':{}}
    if before:
        im['native_navigation_history']=deepcopy(before.get('native_navigation_history',[]))+[{k:before.get(k) for k in ['name','folder_id','path','image_url','folder_url','inventory_status','current_native_evidence']}]
    im.update(name=r['name'],folder_id=r['folder_id'],path=r['path'],image_url=r['image_url'],folder_url=r['folder_url'],in_wall_sculpture_tree=r['scope']=='Wall Sculptures')
    im['current_native_evidence']={'status':'Current in immutable scoped census after verified deletion cut','publication_cut_utc':manifest['recorded_utc'],'file_id':fid,'folder_id':r['folder_id'],'content_hash':r.get('content_hash'),'bytes':r.get('bytes',r.get('size')),'native_scope':r['scope'],'original_bytes_rehashed_by_publisher':False}
    # Saved source byte hashes and cached renditions stay untouched. A new
    # native hash is navigation evidence, not local byte verification.
    db.execute('INSERT OR REPLACE INTO images VALUES(?,?,?,?,?,?)',(fid,r['folder_id'],r['path'],1,int(r['scope']=='Wall Sculptures'),dump(im)))
    db.execute('INSERT INTO publication_current_images VALUES(?,?)',(fid,dump(r)))
for fid,proof in deleted.items():
    db.execute('INSERT INTO publication_verified_deletions VALUES(?,?)',(fid,dump(proof)))
    if fid in oldimages and fid not in files:
        im=deepcopy(oldimages[fid]);im['publication_native_availability']={'status':'Verified absent following owner-approved app deletion','publication_cut_utc':manifest['recorded_utc'],'proof':proof}
        db.execute('UPDATE images SET record_json=? WHERE file_id=?',(dump(im),fid))
for fid in manifest.get('accepted_scoped_unavailable_ids',[]):
    if fid in oldimages and fid not in files:
        im=deepcopy(oldimages[fid]);im['publication_native_availability']={'status':'Native NOT_FOUND in complete scoped census; cause not inferred','publication_cut_utc':manifest['recorded_utc'],'qualification':manifest['scoped_unavailable_qualification']}
        db.execute('UPDATE images SET record_json=? WHERE file_id=?',(dump(im),fid))
previous=db.execute("SELECT value_json FROM metadata WHERE key='current_navigation_publication'").fetchone()[0]
db.execute('INSERT INTO metadata VALUES(?,?)',('navigation_publication_'+history_suffix,previous))
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('current_navigation_publication',dump({'cut':manifest['recorded_utc'],'register_sha256':sha(H/'canonical-master-register.json'),'files':len(files),'verified_deletion_tombstones':len(deleted),'source_database_sha256':manifest['sources']['source_gallery']['sha256']})))
db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
counts={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['products','images','associations','publication_original_products','publication_current_images','publication_verified_deletions']}
db.close()

style='<style>body{font:16px Arial,sans-serif;max-width:1150px;margin:32px auto;padding:0 20px;color:#243847}a{color:#17617d}article{border-top:1px solid #cbd4da;padding:18px 0}p{line-height:1.5}input{padding:10px;width:70%;font:inherit}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #dde3e7;padding:9px;vertical-align:top}.small{color:#51636e;font-size:14px}.links a{margin-right:20px}code{font-size:12px;overflow-wrap:anywhere}</style>'
script='<script>document.querySelector("input").addEventListener("input",ev=>{let q=ev.target.value.toLowerCase();document.querySelectorAll("article").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script>'
def link(url,label):return '<a href="'+e(url,quote=True)+'">'+e(label)+'</a>' if url else e(label+' unavailable')
def page(title,content):return '<!doctype html><meta charset="utf-8"><title>'+e(title)+'</title>'+style+'<h1>'+e(title)+'</h1><p class="small">Publication cut '+e(manifest['recorded_utc'])+'. 186 active options; photographs and saved source rows are not a sculpture count. Working estimates, source conflicts, variation and display qualifications remain.</p><p>'+link('index.html','Review home')+' · '+link('product-images.html','All individual options')+' · '+link('family-images.html','Current images and folders')+'</p>'+content
articles=[]
for o in sorted((o for o in g['options'] if o['product_id'] in active),key=lambda o:(o['family'],o['name'])):
    links=link(o.get('image_url'),'Primary picture')+' · '+link(o.get('folder_url'),'Containing folder')
    if o.get('context_image_url'):links+=' · '+link(o['context_image_url'],'Context picture')+' · '+link(o['context_folder_url'],'Context folder')
    s=o.get('current_series_reference')
    if s:links+=' · '+link(s['image_url'],'Series picture')+' · '+link(s['folder_url'],'Series folder')
    elif o.get('historical_series_reference'):links+=' · '+link(o['historical_series_reference']['folder_url'],'Series folder (image unavailable)')
    specs=''.join('<tr><td>'+e(k)+'</td><td>'+e(str(v.get('display','')))+'<div class="small">'+e(str(v.get('state','')))+' | '+e(str(v.get('basis','')))+'</div></td></tr>' for k,v in o.get('master_fields',o['specifications']).items())
    articles.append('<article id="'+o['product_id']+'"><h2>'+e(o['name'])+'</h2><p>'+links+'</p><p class="small">'+e(o.get('context_description',''))+'</p><p class="small">'+e(o.get('source_scope_notes',''))+'</p><table>'+specs+'</table><p><code>'+e(o['product_id'])+' | Primary '+e(o.get('file_id') or 'unbound')+' | Parent '+e(o.get('folder_id') or 'unbound')+'</code></p></article>')
(dest/'product-images.html').write_text(page('Individual sculptures and working specifications','<input aria-label="Filter sculptures" placeholder="Filter by sculpture, family or ID">'+''.join(articles)+script))
image_articles=[]
for r in overlay:
    image_articles.append('<article><p>'+link(r['image_url'],r['name'])+' · '+link(r['folder_url'],'Containing folder')+'</p><p class="small">'+e(r['path'])+'</p><code>'+e(r['file_id'])+' | '+e(r['folder_id'])+'</code></article>')
wallcount=sum(r['scope']=='Wall Sculptures' for r in overlay)
(dest/'family-images.html').write_text(page('Current scoped image and folder index',f'<p>{wallcount:,} Wall Sculptures files and {len(overlay)-wallcount:,} retained Workshop files. Exact component identities and sale units remain separate from folder naming.</p><input aria-label="Filter images" placeholder="Filter by filename, folder or stable ID">'+''.join(image_articles)+script))
changes=read(H/'register-preparation.json')
changed_cards=[]
for c in changes['primary_changes']:
    changed_cards.append('<article><h2>'+e(c['name'])+'</h2><p>'+link(c['image_url'],'Selected picture')+' · '+link(c['folder_url'],'Actual containing folder')+' · '+link('product-images.html#'+c['product_id'],'Specifications')+'</p><p class="small">Saved product-specific Primary choice. Group, design-reference and variation qualifications are retained; no specification inference.</p></article>')
for pid in changes['new_context_losses']:
    o=options[pid]
    changed_cards.append('<article><h2>'+e(o['name'])+'</h2><p>'+link(o.get('image_url'),'Current Primary')+' · '+link(o['folder_url'],'Containing folder')+' · '+link('product-images.html#'+pid,'Specifications')+'</p><p class="small">The previous shared context/series photograph is unavailable. Existing owner-hold and series-replacement qualifications remain. Historical file and folder IDs are retained.</p></article>')
unbound=[o for o in g['options'] if o['product_id'] in active and not o.get('file_id')]
unboundcards=''.join('<article><h2>'+e(o['name'])+'</h2><p>Current Primary unbound. '+link(o.get('folder_url'),'Containing folder')+'</p><p class="small">'+e(o.get('photo_coverage',{}).get('individual','Exact current Primary remains unbound; preserve existing identity scope.'))+'</p></article>' for o in unbound)
(dest/'index.html').write_text(page('Boldstone current catalogue review','<p>186 active options after the owner-confirmed Acanthus duplicate consolidation. Current image paths and saved Primary choices use the captured census and review cut. Physical and commercial details retain their earlier qualifications.</p><input aria-label="Filter changed references" placeholder="Filter changed references">'+''.join(changed_cards)+unboundcards+script))
write(dest/'sealed-handoff.json',{'status':'CURRENT_REGISTER_AND_NATIVE_NAVIGATION_PROJECTION','publication_cut_utc':manifest['recorded_utc'],'register_sha256':sha(H/'canonical-master-register.json'),'source_database':manifest['sources']['source_gallery'],'database':str(dbpath),'database_sha256':sha(dbpath),'counts':counts,'source_history_table_map':{'products':'publication_original_products_'+history_suffix,'publication_current_images':'publication_current_images_'+history_suffix,'publication_verified_deletions':'publication_verified_deletions_'+history_suffix},'files':{p.name:sha(p) for p in dest.glob('*.html')},'source_platform_associations_preserved':True,'physical_specification_changes':0,'native_writes':0})
write(H/'gallery-preparation.json',{'status':'GALLERY_AND_READERS_PREPARED','directory':str(dest),'seal_sha256':sha(dest/'sealed-handoff.json'),'database_sha256':sha(dbpath),'counts':counts})
print(json.dumps(counts))
