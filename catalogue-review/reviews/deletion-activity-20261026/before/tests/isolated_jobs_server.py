"""Disposable browser QA. Every native call is an in-memory fake, never Dropbox."""
from pathlib import Path
from types import SimpleNamespace as NS
from http.server import ThreadingHTTPServer
import json
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

fixture=BackgroundJobTests();fixture.setUp();fixture.organisation_fixture()
fixture.client=fixture.native
cat=fixture.cat
for pid,p in cat.products.items():
    p.update(primary_id=TARGET,sale_unit='Isolated test sculpture - no Dropbox changes',image_url='',
             fields=[{'key':'Name','label':'Name','value':p['name'],'section':'Listing copy','basis':'QA fixture','qualification':''}])
cat.families={'Ammonite':list(cat.products)}
cat.source['dedupe']={};cat.fields=lambda pid:{f['key']:f for f in cat.products[pid]['fields']}
cat.assets[TARGET].update(local_preview=True,representation='Isolated test image',inventory_status='QA_ONLY')
for a in cat.assets.values():a.setdefault('family','Ammonite')
cat.preview_paths={}
app=Application.__new__(Application)
app.catalogue=cat;app.store=fixture.store;app.catalogue_lock=threading.RLock();app.token='isolated-test-token-not-a-dropbox-credential'
app.export_lock=threading.Lock();app.original_lock=threading.Lock();app.deletions=fixture.manager
app.sync=NS(request=lambda:{'enabled':False},snapshot=lambda:{'enabled':False,'state':'disabled','generation':0})
app.similarity=Similarity(app.store.root)
original=fixture.manager.runner
def slow_native(request):
    if request['action']=='execute':time.sleep(8)
    return original(request)
app.deletions.runner=slow_native
app.jobs=BackgroundJobs(app,runner=fixture.jobs.runner)
server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);server.app=app;server.daemon_threads=True
app.jobs.start()
print(json.dumps({'url':'http://127.0.0.1:8768/#L1','data_dir':str(app.store.root),'native':'in-memory fake only'}),flush=True)
try:server.serve_forever()
finally:app.jobs.stop();server.server_close();fixture.tearDown()
