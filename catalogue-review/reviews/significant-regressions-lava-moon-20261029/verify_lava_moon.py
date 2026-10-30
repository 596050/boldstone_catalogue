"""Independently validate retirement, source preservation and effective images."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib, json, sqlite3, sys
H=Path(__file__).resolve().parent; PROJECT=H.parents[2]; APP=PROJECT/'catalogue-review'
sys.path.insert(0,str(APP))
from catalogue import Catalogue
from dropbox_sync import apply_inventory, read_inventory
from filename_overlay import apply_filename_overlay
from media import MediaCache
from projection import Projection
from store import ReviewStore
from component_photos import component_photos
OUT=PROJECT/'sculpture-catalogue/components/reconciliation/lava-moon-three-white-products-2026-10-29'
RUNTIME=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=read(OUT/'inputs/canonical-master-register.json');new=read(OUT/'canonical-master-register.json')
d=read(OUT/'owner-decision.json'); white=set(d['active_option_ids']); retired=set(d['retired_option_ids'])
a={o['product_id']:o for o in old['options']}; b={o['product_id']:o for o in new['options']}
assert len(new['active_option_ids'])==181 and len(b)==191 and len(new['retired_option_ids'])==10
assert set(old['active_option_ids'])-set(new['active_option_ids'])==retired
assert {p for p in new['active_option_ids'] if b[p]['family']=='Lava Moon'}==white
for pid in a:
    for k in ('specifications','master_fields','selling_details'): assert a[pid].get(k)==b[pid].get(k),(pid,k)
    if pid not in retired: assert a[pid]==b[pid],pid
newdb=OUT/'gallery-projection/complete-image-platform-register.sqlite'
with closing(sqlite3.connect(OUT/'inputs/complete-image-platform-register.sqlite')) as src, closing(sqlite3.connect(newdb)) as dst:
    assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    for t, in src.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        if t not in ('products','metadata'):
            assert list(src.execute('SELECT * FROM "'+t+'" ORDER BY rowid'))==list(dst.execute('SELECT * FROM "'+t+'" ORDER BY rowid')),t
with closing(sqlite3.connect('file:'+str(RUNTIME/'reviews.sqlite3')+'?mode=ro',uri=True)) as db:
    db.row_factory=sqlite3.Row
    reviews=[ReviewStore.unpack(r) for r in db.execute('SELECT * FROM reviews ORDER BY updated_at')]
MediaCache.flush=lambda self:None
inventory=read_inventory(RUNTIME/'dropbox-sync/inventory.json')
previous=apply_inventory(Catalogue(PROJECT,RUNTIME),inventory,RUNTIME)
read_text=Path.read_text
def proposed(path,*args,**kwargs):
    if path.resolve()==PROJECT/'sculpture-catalogue/current-master.json':return read_text(OUT/'next-current-master.json')
    return read_text(path,*args,**kwargs)
with patch.object(Path,'read_text',proposed):
    staged=apply_inventory(Catalogue(PROJECT,RUNTIME),inventory,RUNTIME)
apply_filename_overlay(previous,RUNTIME);apply_filename_overlay(staged,RUNTIME)
assert set(previous.assets)==set(staged.assets)
for aid in previous.assets:
    assert {k:v for k,v in previous.assets[aid].items() if k!='product_ids'}=={k:v for k,v in staged.assets[aid].items() if k!='product_ids'},aid
oldview=Projection(previous,reviews);view=Projection(staged,reviews)
context={aid for aid,a in staged.assets.items() if a.get('folder_id')==d['family_library_only_folder_id'] and not a.get('source_unavailable')}
assert len(context)==4,context
library_ids={a['id'] for a in view.library()}
assert context<=library_ids
assert not any(context & edges.keys() for edges in view.edges.values()), 'Context photos gained product associations'
checks={}
for pid in staged.products:
    assert staged.products[pid]==previous.products[pid],pid
    if pid not in white:
        assert view.edges[pid]==oldview.edges[pid],pid
        continue
    before=component_photos(oldview,pid);after=component_photos(view,pid)
    for key in ('primary_id','listing_ids','in_situ_ids'):
        assert before[key]==after[key],(pid,key,before[key],after[key])
    assert after['primary_id'] and len(after['in_situ_ids'])==3
    assert len(after['images'])==4 and not after['related_images']
    checks[pid]={'name':staged.products[pid]['name'],'associated_images':len(after['images']),
        'primary_id':after['primary_id'],'listing_count':len(after['listing_ids']),'in_situ_count':len(after['in_situ_ids'])}
receipt={'status':'PASS_THREE_WHITE_PRODUCTS_PRESERVATION','checked_utc':datetime.now(timezone.utc).isoformat(),
    'register_sha256':sha(OUT/'canonical-master-register.json'),'gallery_sha256':sha(newdb),
    'active_options':181,'retained_options':191,'retired_options':10,'context_only_images':sorted(context),
    'listings':checks,'source_specifications_preserved':191,'native_assets_preserved':len(staged.assets),
    'all_source_associations_preserved':True,'unrelated_products_preserved':178,'native_writes':0}
(OUT/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
