from pathlib import Path
import json,sys,time
from http.server import ThreadingHTTPServer
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'work'))
from server import Application,Handler
import dropbox_sync
from media import enrich
from projection import Projection
app=Application(Path('/Users/tprice/Documents/boldstone'),BASE/'qa-state',auto_sync=False)
runtime=Path('/Users/tprice/Library/Application Support/BoldstoneReview')
# Read current inventory/cache; keep metadata cache writes in the isolated QA state.
dropbox_sync.enrich=lambda cat,_:enrich(cat,BASE/'qa-state')
cat=dropbox_sync.apply_inventory(app.catalogue,dropbox_sync.read_inventory(runtime/'dropbox-sync/inventory.json'),runtime)
app.catalogue=cat;app.deletions.cat=cat
app.deletions.runner=lambda _: (_ for _ in ()).throw(ValueError('Native deletion disabled in the isolated audit server.'))
app.original=lambda _: (_ for _ in ()).throw(ValueError('Native original downloads disabled in the isolated audit server.'))
original_save=app.save
app.save=lambda body:(time.sleep(0.4),original_save(body))[1]
view=app.projection()
counts=[]
for pid,p in cat.products.items():
    removed=view.removed[pid]
    if removed:
        counts.append({'id':pid,'name':p['name'],'removed':len(removed),'removed_listing':sum('listing' in view.decision('image',pid,aid).get('uses',[]) for aid in removed),'retained':len(view.edges[pid])})
(BASE/'baseline-count-audit.json').write_text(json.dumps(counts,indent=2))
server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);server.daemon_threads=True;server.app=app
print(json.dumps({'qa_ready':True,'products':len(cat.products),'counts_affected':counts}),flush=True)
server.serve_forever()
