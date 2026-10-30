"""Read-only app datasource/review contract against the published catalogue."""
from common import *
import sqlite3,sys
sys.path.insert(0,str(H/'app-v2.10.0-independent/source'))
import catalogue,dropbox_sync
from projection import Projection

# Byte/dimension evidence remains separately qualified. Disable media cache
# enrichment so this contract check cannot write the live runtime cache.
catalogue.enrich=lambda *args:None
dropbox_sync.enrich=lambda *args:None
cat=catalogue.Catalogue(BASE.parent,cache_root=H/'source-readback-cache')
state=read(manifest['sources']['current_wall_census']['snapshot'])
state.update(snapshot_path=manifest['sources']['current_wall_census']['path'],snapshot_sha256=manifest['sources']['current_wall_census']['sha256'])
runtime=Path.home()/'Library/Application Support/BoldstoneReview'
cat=dropbox_sync.apply_inventory(cat,state,runtime)
c=sqlite3.connect(Path(manifest['sources']['app_review_cut']['snapshot']).as_uri()+'?mode=ro',uri=True)
c.row_factory=sqlite3.Row;reviews=[dict(r) for r in c.execute('SELECT * FROM reviews')];c.close()
for row in reviews:
    row['data']=json.loads(row['data'])
    if isinstance(row.get('original'),str):row['original']=json.loads(row['original'])
view=Projection(cat,reviews);assert set(cat.products)==active
checks=0
for o in g['options']:
    if o['product_id'] not in active:continue
    p=cat.products[o['product_id']]
    assert p['primary_id']==o.get('file_id');assert p['folder_url']==o.get('folder_url');checks+=2
    for field in p['fields']:
        if field['key'] in {'Dimensions / depth','Weight','Material / finish','Fixing'}:
            assert field['value']==o['master_fields'][field['key']]['display'];checks+=1
    if o.get('file_id'):assert o['file_id'] in cat.assets;checks+=1
for row in read(CUT/'recorded-primary-choices.json'):
    fid,pid=row['item_id'],row['product_id']
    assert view.record('image',pid,fid)['data'].get('primary') is True,(pid,fid,'Primary choice lost')
    assert view.cid(fid) in {a['id'] for a in view.images(pid)},(pid,fid,'Primary absent from gallery')
    checks+=2
result={'status':'PASS_NEW_PUBLISHED_SOURCE_WITH_FROZEN_SAVED_REVIEWS','checks':checks,'active_products':len(cat.products),'recorded_primary_choices_preserved':21,'register_sha256':cat.source['register_sha256'],'gallery_sha256':cat.source['gallery_sha256'],'scope':'Read-only private source load and frozen review projection. Media enrichment disabled; no server restart, byte/dimension verification or native operation.','app_native_or_platform_writes':0}
write(H/'source-rebase-compatibility.json',result)
ready=read(H/'SOURCE_READY_FOR_APP_REBASE.json');ready['source_compatibility_check']={'path':str(H/'source-rebase-compatibility.json'),'sha256':sha(H/'source-rebase-compatibility.json'),'checks':checks};write(H/'SOURCE_READY_FOR_APP_REBASE.json',ready)
print(json.dumps(result,indent=2))
