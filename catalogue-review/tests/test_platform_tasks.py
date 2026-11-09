from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace, MethodType
from http.server import ThreadingHTTPServer
import json
import sys
import threading
import unittest
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_tasks import PlatformTasks, PLATFORMS, SCHEMA, fingerprints, validate_snapshot
from server import Application, Handler
from projection import Projection


class PlatformTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.tasks = PlatformTasks(self.root)
        self.now = datetime(2026, 11, 8, 18, tzinfo=timezone.utc)
        self.product = {'id': 'A', 'name': 'Panel', 'listing_decision': 'include',
                        'fields': [{'key': 'Price', 'value': '40.00'}],
                        'listing_fields': [{'key': 'Retail name', 'value': 'Panel - Copper Finish'}]}
        self.photos = {'primary_listing': {'image_id': 'id:one'}, 'primary_content_hash': 'old',
                       'listing': {'image_ids': ['id:one', 'id:two']}, 'in_situ': {'image_ids': ['id:two']}}

    def tearDown(self):
        self.tmp.cleanup()

    def snapshot(self, state='verified', tasks=None):
        return {'schema': SCHEMA, 'checked_at': self.now.isoformat(), 'products': {'A': {
            'fingerprints': fingerprints(self.product, self.photos),
            'platforms': {'pinterest': {'state': state, 'checked_at': self.now.isoformat(),
                                       'summary': 'Dated native observation', 'tasks': tasks or []}}}}}

    def write(self, data):
        p=self.root/'incoming.json';p.write_text(json.dumps(data));p.replace(self.tasks.path)

    def test_missing_audit_does_not_invent_platform_success(self):
        result=self.tasks.product(self.product, self.photos, self.now)
        self.assertEqual(len(result['platforms']), len(PLATFORMS))
        self.assertTrue(all(p['state']=='unknown' and p['open_count'] for p in result['platforms']))

    def test_new_or_unbound_component_is_unknown_not_excluded(self):
        self.write(self.snapshot())
        self.product['id']='NEW'
        result=self.tasks.product(self.product,self.photos,self.now)
        self.assertTrue(all(p['state']=='unknown' for p in result['platforms']))

    def test_photo_changes_remove_obsolete_image_diagnosis_but_retain_account_blocker(self):
        tasks=[dict(id='image_size',state='action',title='Review primary resolution',detail='Old photo is too small',scope='photos'),
               dict(id='merchant_approval',state='waiting',title='Merchant approval',detail='Await platform review',scope='account')]
        self.write(self.snapshot('action',tasks))
        self.photos['primary_listing']['image_id']='id:replacement'
        result=self.tasks.product(self.product,self.photos,self.now)
        p=next(p for p in result['platforms'] if p['id']=='pinterest')
        self.assertEqual(p['state'],'action')
        self.assertEqual({t['id'] for t in p['tasks']},{'merchant_approval','catalogue_changed'})
        self.assertNotIn('Old photo is too small',json.dumps(p))

    def test_changed_bytes_invalidate_even_with_stable_dropbox_id(self):
        self.write(self.snapshot())
        self.photos['primary_content_hash']='new-content'
        result=self.tasks.product(self.product,self.photos,self.now)
        self.assertTrue(result['catalogue_changed_since_check'])
        p=next(p for p in result['platforms'] if p['id']=='pinterest')
        self.assertEqual(p['state'],'action')

    def test_field_edit_does_not_erase_still_valid_photo_problem(self):
        problem=dict(id='image_size',state='action',title='Review photo',detail='2048 x 1360',scope='photos')
        self.write(self.snapshot('action',[problem]))
        self.product['fields'][0]['value']='42.00'
        p=next(p for p in self.tasks.product(self.product,self.photos,self.now)['platforms'] if p['id']=='pinterest')
        self.assertEqual({t['id'] for t in p['tasks']},{'image_size','catalogue_changed'})

    def test_replaced_snapshot_reloads_and_corruption_cannot_leave_green_status(self):
        self.write(self.snapshot())
        p=lambda:next(p for p in self.tasks.product(self.product,self.photos,self.now)['platforms'] if p['id']=='pinterest')
        self.assertEqual(p()['state'],'verified')
        self.write(self.snapshot('waiting',[dict(id='review',state='waiting',title='Pending',detail='Native review pending')]))
        self.assertEqual(p()['state'],'waiting')
        self.tasks.path.write_text('{broken')
        self.assertEqual(p()['state'],'unknown')
        self.assertIn('could not be read',self.tasks.source_error)

    def test_old_observation_and_changed_inclusion_require_recheck(self):
        self.write(self.snapshot())
        p=next(p for p in self.tasks.product(self.product,self.photos,self.now+timedelta(days=8))['platforms'] if p['id']=='pinterest')
        self.assertEqual(p['state'],'action');self.assertIn('audit_stale',{t['id'] for t in p['tasks']})
        self.write(self.snapshot('not_targeted'))
        self.product['listing_decision']='exclude'
        p=next(p for p in self.tasks.product(self.product,self.photos,self.now)['platforms'] if p['id']=='pinterest')
        self.assertEqual(p['state'],'action');self.assertIn('inclusion_changed',{t['id'] for t in p['tasks']})

    def test_validation_rejects_undated_success_missing_fingerprints_and_duplicate_task_ids(self):
        for change in ['date','fingerprint','duplicate']:
            data=self.snapshot()
            if change=='date':data['products']['A']['platforms']['pinterest']['checked_at']=''
            elif change=='fingerprint':data['products']['A']['fingerprints']={}
            else:data['products']['A']['platforms']['pinterest']['tasks']=[dict(id='x',state='action',title='x',detail='x')]*2
            with self.subTest(change=change),self.assertRaises(ValueError):validate_snapshot(data)

    def test_status_projection_is_read_only(self):
        data=self.snapshot();before=deepcopy((data,self.product,self.photos))
        self.write(data)
        self.tasks.product(self.product,self.photos,self.now)
        self.assertEqual((data,self.product,self.photos),before)

    def test_http_endpoint_and_component_specifications_share_platform_evidence(self):
        field=lambda key,value,section='Specifications':dict(key=key,label=key,value=value,section=section,basis='',qualification='')
        cat=SimpleNamespace(source={'register_sha256':'source'},products={'A':dict(id='A',name='Panel',family='Panels',fields=[field('Retail name','Panel','Listing copy'),field('Weight','2 kg')])},assets={},edges={'A':{}})
        app=SimpleNamespace(catalogue=cat,catalogue_lock=threading.RLock(),store=SimpleNamespace(all=lambda:[]),
                            platform_tasks=self.tasks,projection=lambda:Projection(cat,[]))
        app.platform_status=MethodType(Application.platform_status,app)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.app=app
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base+'/api/platform-tasks?product_id=A') as r:first=json.load(r)
            with urllib.request.urlopen(base+'/api/specifications') as r:spec=json.load(r)
            self.assertEqual(first['products']['A']['revision'],spec['products'][0]['platform_tasks']['revision'])
            with urllib.request.urlopen(base+'/platform-tasks.js') as r:self.assertIn('javascript',r.headers['Content-Type'])
        finally:server.shutdown();server.server_close();worker.join()


if __name__=='__main__':unittest.main()
