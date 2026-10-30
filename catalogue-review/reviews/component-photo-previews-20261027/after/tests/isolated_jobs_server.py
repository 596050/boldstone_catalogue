"""Disposable browser QA. Every native call is an in-memory fake, never Dropbox."""
from pathlib import Path
from types import SimpleNamespace as NS
from http.server import ThreadingHTTPServer
import json
import argparse
import sys
import threading
import time
from copy import deepcopy
sys.path[:0]=[str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1])]
from test_background_jobs import BackgroundJobTests
from test_deletions import TARGET
from server import Application,Handler
from background_jobs import BackgroundJobs
from similarity import Similarity
from media import TYPES
from deletion_reviews import DeletionReviews
from deletions import NativeUnavailable

parser=argparse.ArgumentParser()
parser.add_argument('--seed-busy-delete',action='store_true')
parser.add_argument('--seed-rename-rejection',action='store_true')
parser.add_argument('--slow-review-saves',action='store_true')
parser.add_argument('--large-deletion-review',action='store_true')
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
app.refresh_source=lambda:False
app.sync=NS(request=lambda:{'enabled':False},snapshot=lambda:{'enabled':False,'state':'disabled','generation':0})
app.similarity=Similarity(app.store.root)
original=fixture.manager.runner
read_attempts={}
if args.large_deletion_review:
    for index in range(181):
        fid='id:bulk'+str(index)
        asset={**deepcopy(cat.assets[TARGET]),'id':fid,'name':f'dune-ripple-test-{index:03d}.jpg'}
        cat.assets[fid]=asset;cat.paths[fid]=cat.paths[TARGET]
        native=deepcopy(fixture.client.files[TARGET]);native.id=fid;native.name=asset['name']
        native.path_display=native.path_display.rsplit('/',1)[0]+'/'+native.name;native.path_lower=native.path_display.lower()
        fixture.client.files[fid]=native
        for edges in cat.edges.values():edges[fid]={'uses':[],'qualifications':[],'tier':'accepted'}
def slow_native(request):
    if request['action']=='execute':time.sleep(.015 if args.large_deletion_review else 8)
    if args.large_deletion_review and request['action']=='inspect':
        fid=request['binding']['id'];read_attempts[fid]=read_attempts.get(fid,0)+1;time.sleep(.05)
        if fid=='id:bulk52' and read_attempts[fid]<=3:raise NativeUnavailable('Isolated temporary Dropbox read failure',True)
    return original(request)
app.deletions.runner=slow_native
app.jobs=BackgroundJobs(app,runner=fixture.jobs.runner)
app.deletion_reviews=DeletionReviews(app)
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
app.deletion_reviews.start()
print(json.dumps({'url':'http://127.0.0.1:8768/#L1','data_dir':str(app.store.root),'native':'in-memory fake only'}),flush=True)
try:server.serve_forever()
finally:app.jobs.stop();app.deletion_reviews.stop();server.server_close();fixture.tearDown()
