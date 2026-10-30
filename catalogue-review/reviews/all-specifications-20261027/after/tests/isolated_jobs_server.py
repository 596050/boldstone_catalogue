"""Disposable browser QA. Every native call is an in-memory fake, never Dropbox."""
from pathlib import Path
from types import SimpleNamespace as NS
from http.server import ThreadingHTTPServer
import json
import argparse
import sys
import threading
import time
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from test_background_jobs import BackgroundJobTests
from test_deletions import TARGET
from server import Application,Handler
from background_jobs import BackgroundJobs
from similarity import Similarity
from media import TYPES

parser=argparse.ArgumentParser()
parser.add_argument('--seed-busy-delete',action='store_true')
parser.add_argument('--seed-rename-rejection',action='store_true')
parser.add_argument('--slow-review-saves',action='store_true')
args=parser.parse_args()
fixture=BackgroundJobTests();fixture.setUp();fixture.organisation_fixture()
fixture.client=fixture.native
cat=fixture.cat
for pid,p in cat.products.items():
    p.update(primary_id=TARGET,sale_unit='Isolated test sculpture - no Dropbox changes',image_url='',
             fields=[{'key':'Name','label':'Name','value':p['name'],'section':'Listing copy','basis':'QA fixture','qualification':''},
                     {'key':'Depth','label':'Depth','value':'3 cm','section':'Specifications','basis':'QA fixture','qualification':''}])
cat.families={'Ammonite':list(cat.products)}
cat.source['dedupe']={};cat.fields=lambda pid:{f['key']:f for f in cat.products[pid]['fields']}
cat.assets[TARGET].update(local_preview=True,representation='Isolated test image',inventory_status='QA_ONLY')
for a in cat.assets.values():a.setdefault('family','Ammonite')
cat.preview_paths={}
app=Application.__new__(Application)
app.catalogue=cat;app.store=fixture.store;app.catalogue_lock=threading.RLock();app.token='isolated-test-token-not-a-dropbox-credential'
app.export_lock=threading.Lock();app.original_lock=threading.Lock();app.deletions=fixture.manager
if args.slow_review_saves:
    original_save=app.save
    def slow_save(body):
        time.sleep(4)
        return original_save(body)
    app.save=slow_save
app.sync=NS(request=lambda:{'enabled':False},snapshot=lambda:{'enabled':False,'state':'disabled','generation':0})
app.similarity=Similarity(app.store.root)
original=fixture.manager.runner
def slow_native(request):
    if request['action']=='execute':time.sleep(8)
    return original(request)
app.deletions.runner=slow_native
app.jobs=BackgroundJobs(app,runner=fixture.jobs.runner)
if args.seed_busy_delete:
    review=app.deletions.prepare({'asset_id':TARGET,'reason':'unwanted'})
    app.jobs.enqueue_deletion({'operation_id':review['operation_id'],'confirm_file_id':TARGET,'confirmed':True})
    (app.store.root/'native-writer-reservation.json').write_text(json.dumps({'active':True,'label':'Isolated browser QA','reason':'Fake jobs held for mixed-selection testing.'}))
if args.seed_rename_rejection:
    from test_rename_deletions import rename_fixture
    review=app.deletions.prepare({'asset_id':TARGET,'reason':'unwanted'})
    app.jobs.enqueue_deletion({'operation_id':review['operation_id'],'confirm_file_id':TARGET,'confirmed':True})
    rename_fixture(app.store.root,fixture.client)
    pointer=app.store.root/'filename-readback.json';raw=pointer.read_bytes();pointer.unlink()
    app.deletions.runner=original;app.jobs.step();app.deletions.runner=slow_native
    pointer.write_bytes(raw)
    cat.assets[TARGET]['name']=fixture.client.files[TARGET].name
server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);server.app=app;server.daemon_threads=True
app.jobs.start()
print(json.dumps({'url':'http://127.0.0.1:8768/#L1','data_dir':str(app.store.root),'native':'in-memory fake only'}),flush=True)
try:server.serve_forever()
finally:app.jobs.stop();server.server_close();fixture.tearDown()
