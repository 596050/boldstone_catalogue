"""Disposable browser QA. Every native call is an in-memory fake, never Dropbox."""
from pathlib import Path
from types import SimpleNamespace as NS
from http.server import ThreadingHTTPServer
import json
import argparse
import sys
import threading
import time
import sqlite3
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
parser.add_argument('--seed-uncertain-deletion',action='store_true')
parser.add_argument('--seed-review-cooldown',action='store_true')
parser.add_argument('--review-confirmation-retry',action='store_true')
parser.add_argument('--slow-history-checks',action='store_true')
parser.add_argument('--slow-component-reads',action='store_true')
parser.add_argument('--seed-pending-image-uses',action='store_true')
parser.add_argument('--gallery-layout',action='store_true')
parser.add_argument('--component-controls',action='store_true')
parser.add_argument('--worker-recovery',action='store_true')
parser.add_argument('--review-batch-recovery',action='store_true')
parser.add_argument('--image-editor-context',action='store_true')
parser.add_argument('--slow-original-download',action='store_true')
parser.add_argument('--organisation-recovery',action='store_true')
parser.add_argument('--overview-save-recovery',action='store_true')
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
if args.slow_original_download:
    def fake_original(body):
        aid=body.get('asset_id')
        if aid not in cat.assets:raise ValueError('Unknown isolated image')
        (app.store.root/'original-fetch-started').write_text(aid)
        time.sleep(4)
        cat.assets[aid]['original'].update(dimensions=[1,1],locally_verified=True,dimension_basis='Isolated fixture verification')
        return {'asset':app.projection().asset(aid)}
    app.original=fake_original
if args.image_editor_context:
    # Replace only fake metadata while the browser retains an older snapshot.
    # This flag never reads credentials or makes Dropbox calls.
    fixture_hash=app.store.root/'fixture-image-content-hash'
    fixture_hash.write_text(cat.assets[TARGET]['original']['dropbox_content_hash'])
    def refresh_fixture_content():
        value=fixture_hash.read_text().strip()
        if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('Invalid isolated fixture hash')
        cat.assets[TARGET]['original']['dropbox_content_hash']=value
        return False
    app.refresh_source=refresh_fixture_content
app.sync=NS(request=lambda:{'enabled':False},snapshot=lambda:{'enabled':False,'state':'disabled','generation':0})
app.similarity=Similarity(app.store.root)
original=fixture.manager.runner
read_attempts={}
if args.large_deletion_review or args.gallery_layout:
    for index in range(181 if args.large_deletion_review else 18):
        fid='id:bulk'+str(index)
        asset={**deepcopy(cat.assets[TARGET]),'id':fid,'name':f'dune-ripple-test-{index:03d}.jpg'}
        cat.assets[fid]=asset;cat.paths[fid]=cat.paths[TARGET]
        native=deepcopy(fixture.client.files[TARGET]);native.id=fid;native.name=asset['name']
        native.path_display=native.path_display.rsplit('/',1)[0]+'/'+native.name;native.path_lower=native.path_display.lower()
        asset['provenance']={'path':native.path_display}
        fixture.client.files[fid]=native
        for edges in cat.edges.values():edges[fid]={'uses':[],'qualifications':[],'tier':'accepted'}
def slow_native(request):
    if request['action']=='execute':time.sleep(.015 if args.large_deletion_review else 8)
    if args.slow_history_checks and request['action']=='check':time.sleep(4)
    if args.large_deletion_review and request['action']=='inspect':
        fid=request['binding']['id'];read_attempts[fid]=read_attempts.get(fid,0)+1;time.sleep(.05)
        if fid=='id:bulk52' and read_attempts[fid]<=3:raise NativeUnavailable('Isolated temporary Dropbox read failure',True)
    if args.review_confirmation_retry and request['action']=='inspect' and request['binding']['id']=='id:keeper':
        fid=request['binding']['id'];read_attempts[fid]=read_attempts.get(fid,0)+1
        if read_attempts[fid]<=3:
            raise NativeUnavailable('Isolated temporary read failure; no Dropbox connection.',True,0,
                                    {'error_code':'ReadTimeout','http_status':503,'request_id':'isolated-read-123'})
    return original(request)
app.deletions.runner=slow_native
app.jobs=BackgroundJobs(app,runner=fixture.jobs.runner)
app.deletion_reviews=DeletionReviews(app)
if args.organisation_recovery:
    # Start with a real planner failure; component corrections exercise the
    # durable outbox against the in-memory fake, never Dropbox credentials.
    cat.edges = {pid: {} for pid in cat.products}
    app.store.save('asset','',TARGET,{'types':['in_situ']},0,cat.source['register_sha256'],{})
    app.jobs.step()
if args.review_confirmation_retry:
    review=app.deletion_reviews.start_review({'request_id':'isolated-confirmation-retry',
            'entries':[{'asset_id':fid,'reason':'unwanted'} for fid in (TARGET,'id:keeper')]})
    app.deletion_reviews.inspect_one(review['id'],0)
    for _ in range(3):
        app.deletion_reviews.inspect_one(review['id'],1)
        row=app.deletion_reviews.row(review['id'])
        row['payload']['entries'][1]['next_attempt_at']=0;app.deletion_reviews.write(row)
if args.review_batch_recovery:
    # Two saved checks share an unconfirmed read receipt before either is
    # batched. The second review must still reach its own confirmation screen.
    for ident, ids in [('isolated-first-overlap', [TARGET]),
                       ('isolated-second-overlap', [TARGET, 'id:keeper'])]:
        app.deletion_reviews.start_review({'request_id': ident,
            'entries': [{'asset_id': fid, 'reason': 'unwanted'} for fid in ids]})
        for index in range(len(ids)):app.deletion_reviews.inspect_one(ident,index)
    app.deletion_reviews.plan('isolated-first-overlap')
if args.worker_recovery:
    # Only this disposable fixture reads these flags. No production fault API.
    (app.store.root/'worker-outage').touch()
    normal_step=app.jobs.step
    def fail_worker_until_flag_removed():
        if (app.store.root/'worker-outage').exists():raise sqlite3.OperationalError('Isolated test disk I/O error')
        return normal_step()
    app.jobs.step=fail_worker_until_flag_removed
    def fake_sync_status():
        if (app.store.root/'sync-outage').exists():raise sqlite3.OperationalError('Isolated status unavailable')
        return {'enabled':True,'state':'ready','generation':0,'last_checked':'2026-10-28T17:00:00Z'}
    app.sync=NS(request=fake_sync_status,snapshot=fake_sync_status)
if args.component_controls:
    for p in cat.products.values():
        p['fields'] += [{'key':key,'label':key,'value':value,'section':'Specifications','basis':'QA fixture','qualification':''}
            for key,value in [('Dimensions','40 × 40 cm'),('Weight','Approximately 6 kg'),('Material','Plaster/gypsum composite'),
                ('Fixing','Keyhole or French cleat'),('Price','£225 per panel'),('Availability','Made to order'),('Lead time','1-2 weeks')]]
    for aid,choice in [(TARGET,{'decision':'reviewed','uses':['listing'],'primary':True}),('id:bulk0',{'decision':'reviewed','uses':['listing','advertising']})]:
        app.store.save('image','L1',aid,choice,0,cat.source['register_sha256'],{})
    with app.store.connect() as db:
        app.jobs.insert(db,'isolated-finished','organise',{'asset_id':TARGET,'label':'Completed test move'})
        app.jobs.insert(db,'isolated-problem','organise',{'asset_id':TARGET,'label':'Unresolved test anchor'})
    app.jobs.mark('isolated-finished','completed',{})
    app.jobs.mark('isolated-problem','needs_review',{'message':'These component folder names are shared or ambiguous. Resolve their individual folder anchors first.'})
if args.seed_pending_image_uses:
    app.store.save('image','L1',TARGET,{'decision':'pending','uses':['listing','advertising','social'],
                    'notes':'Isolated draft - these uses have not been approved'},0,cat.source['register_sha256'],{})
if args.slow_component_reads:
    import server as server_module
    original_components=server_module.component_payload
    def slow_components(view,aid):
        time.sleep(4)
        return original_components(view,aid)
    server_module.component_payload=slow_components
if args.seed_review_cooldown:
    review=app.deletion_reviews.start_review({'request_id':'isolated-wait-review-123456',
            'entries':[{'asset_id':fid,'reason':'unwanted'} for fid in (TARGET,'id:keeper','id:third')]})
    app.deletion_reviews.inspect_one(review['id'],0)
    def limited(request):
        raise NativeUnavailable('Isolated Dropbox wait; no network request was made.',True,275)
    app.deletions.runner=limited
    app.deletion_reviews.inspect_one(review['id'],1)
    app.deletions.runner=slow_native
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
if args.overview_save_recovery:
    # First mutation succeeds but its preview read fails. The second commits
    # before returning an error. Recovery must only read, never replay a toggle.
    import server as server_module
    normal_components=server_module.save_components
    normal_overview=server_module.component_overview
    fault={'mutations':0,'reads':0,'preview_failures':0,'response_failures':0,'fail_next_read':False}
    def record_overview_fault():
        (app.store.root/'overview-fault.json').write_text(json.dumps(fault))
    def component_save_with_response_failure(application,body):
        result=normal_components(application,body)
        fault['mutations']+=1
        if fault['mutations']==1:fault['fail_next_read']=True
        if fault['mutations']==2:
            fault['response_failures']+=1;record_overview_fault()
            raise RuntimeError('Isolated response failure after committed save')
        record_overview_fault();return result
    def overview_with_read_failure(view,pid):
        fault['reads']+=1
        if fault['fail_next_read']:
            fault['fail_next_read']=False;fault['preview_failures']+=1;record_overview_fault()
            raise RuntimeError('Isolated preview read failure')
        record_overview_fault();return normal_overview(view,pid)
    server_module.save_components=component_save_with_response_failure
    server_module.component_overview=overview_with_read_failure
    record_overview_fault()
if args.seed_uncertain_deletion:
    review=app.deletions.prepare({'asset_id':TARGET,'reason':'unwanted'})
    app.jobs.enqueue_deletion({'operation_id':review['operation_id'],'confirm_file_id':TARGET,'confirmed':True})
    def unknown(request):
        if request['action']=='execute':raise TimeoutError('Isolated lost response; no Dropbox access')
        return original(request)
    app.deletions.runner=unknown;app.jobs.step();app.deletions.runner=slow_native
server=ThreadingHTTPServer(('127.0.0.1',8768),Handler);server.app=app;server.daemon_threads=True
app.jobs.start()
app.deletion_reviews.start()
print(json.dumps({'url':'http://127.0.0.1:8768/#L1','data_dir':str(app.store.root),'native':'in-memory fake only'}),flush=True)
try:server.serve_forever()
finally:app.jobs.stop();app.deletion_reviews.stop();server.server_close();fixture.tearDown()
