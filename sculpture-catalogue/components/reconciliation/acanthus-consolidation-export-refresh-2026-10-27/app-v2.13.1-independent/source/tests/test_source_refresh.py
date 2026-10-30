from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch, Mock
import json
import sys
import threading
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_live_review
from catalogue import digest
from source_refresh import refresh_source
from live_review import check_sources, SourceConflict
from dropbox_sync import DropboxSync


class SourceRefreshTests(unittest.TestCase):
    tearDown=test_live_review.LiveReviewTests.tearDown

    def setUp(self):
        test_live_review.LiveReviewTests.setUp(self)
        self.app=NS(catalogue=self.cat,store=self.store,catalogue_lock=threading.RLock(),
                    sync=NS(base=self.cat,inventory_state=None),deletions=NS(cat=self.cat),
                    jobs=NS(overlay_locations=Mock()))
        self.new=deepcopy(self.cat)

    def publish(self):
        base=self.root/'sculpture-catalogue';register=base/'new.json';register.write_text('{"snapshot":2}')
        self.new.source.update(register=str(register),register_sha256=digest(register))
        (base/'current-master.json').write_text(json.dumps({'register':register.name,'register_sha256':digest(register),
            'current_published_gallery_projection':{'path':'index.html'}}))

    def test_unchanged_pointer_does_not_rebuild(self):
        with patch('source_refresh.Catalogue') as factory:
            self.assertFalse(refresh_source(self.app));factory.assert_not_called()

    def test_publisher_update_replaces_catalogue_and_next_scan_base_together(self):
        self.publish()
        self.store.save('product','A','',{'decision':'include'},0,self.cat.source['register_sha256'],{})
        before=self.store.all()
        with patch('source_refresh.Catalogue',return_value=self.new),patch('source_refresh.apply_filename_overlay'):
            self.assertTrue(refresh_source(self.app))
        self.assertIs(self.app.catalogue,self.new);self.assertIs(self.app.sync.base,self.new)
        self.assertIs(self.app.deletions.cat,self.new);check_sources(self.app.catalogue)
        self.assertEqual(self.store.all(),before)

    def test_invalid_new_publication_retains_old_catalogue_and_base(self):
        self.publish();self.new.source['register_sha256']='wrong'
        with patch('source_refresh.Catalogue',return_value=self.new),patch('source_refresh.apply_filename_overlay'):
            with self.assertRaises(SourceConflict):refresh_source(self.app)
        self.assertIs(self.app.catalogue,self.cat);self.assertIs(self.app.sync.base,self.cat)

    def test_inventory_and_verified_locations_survive_publication(self):
        self.publish();state={'checked_utc':'now'};self.app.sync.inventory_state=state
        overlay=deepcopy(self.new)
        with patch('source_refresh.Catalogue',return_value=self.new),patch('source_refresh.apply_inventory',return_value=overlay) as apply,patch('source_refresh.apply_filename_overlay'):
            refresh_source(self.app)
        apply.assert_called_once_with(self.new,state,self.store.root)
        self.assertIs(self.app.catalogue,overlay);self.assertIs(self.app.sync.base,self.new)
        self.app.jobs.overlay_locations.assert_called_once_with(overlay,'now')

    def test_concurrent_refreshes_load_once_and_ignore_older_scan(self):
        self.publish()
        with patch('source_refresh.Catalogue',return_value=self.new) as factory,patch('source_refresh.apply_filename_overlay'):
            with ThreadPoolExecutor(max_workers=3) as pool:
                self.assertEqual(sum(pool.map(lambda _:refresh_source(self.app),range(3))),1)
            factory.assert_called_once()
        sync=DropboxSync.__new__(DropboxSync);sync.app=self.app;sync.status={'generation':5};sync.base=self.new
        with patch('dropbox_sync.apply_inventory') as apply:
            sync.install({'generation':4});apply.assert_not_called()

    def test_inventory_build_uses_current_base_under_catalogue_lock(self):
        sync=DropboxSync.__new__(DropboxSync);sync.app=self.app;sync.status={'generation':0};sync.base=self.new
        state={'generation':1,'checked_utc':'now','new_image_count':0,'pending_previews':0,'image_count':0}
        def build(base,*args):
            self.assertTrue(self.app.catalogue_lock._is_owned());self.assertIs(base,self.new);return base
        with patch('dropbox_sync.apply_inventory',side_effect=build),patch('filename_overlay.apply_filename_overlay'):
            sync.install(state)
        self.assertIs(sync.inventory_state,state);self.assertIs(self.app.catalogue,self.new)

import test_deletions
from store import Conflict

class DeletionSourceRefreshTests(unittest.TestCase):
    setUp=test_deletions.DeletionJobTests.setUp
    tearDown=test_deletions.DeletionJobTests.tearDown
    plan=test_deletions.DeletionJobTests.plan
    confirm=test_deletions.DeletionJobTests.confirm

    def refreshed(self,changed_use=False):
        app=NS(catalogue=self.cat,store=self.store,catalogue_lock=threading.RLock(),
               sync=NS(base=self.cat,inventory_state=None),deletions=self.manager)
        new=deepcopy(self.cat)
        base=self.root/'sculpture-catalogue';register=base/'new.json';register.write_text('{"snapshot":2}')
        new.source.update(register=str(register),register_sha256=digest(register))
        (base/'current-master.json').write_text(json.dumps({'register':register.name,'register_sha256':digest(register),
            'current_published_gallery_projection':{'path':'index.html'}}))
        if changed_use:new.products['A']['name']='Different product use'
        self.manager.refresh_source=lambda:refresh_source(app)
        return app,new

    def test_checked_deletion_survives_unrelated_publication_without_retargeting(self):
        plan=self.plan();app,new=self.refreshed()
        with patch('source_refresh.Catalogue',return_value=new),patch('source_refresh.apply_filename_overlay'):
            result=self.manager.execute(self.confirm(plan))
        self.assertEqual(result['state'],'deleted')
        self.assertEqual(self.client.calls,[(test_deletions.TARGET,'a1')])
        self.assertIs(self.manager.cat,new)

    def test_publication_changing_reviewed_uses_still_prevents_deletion(self):
        plan=self.plan();app,new=self.refreshed(changed_use=True)
        with patch('source_refresh.Catalogue',return_value=new),patch('source_refresh.apply_filename_overlay'):
            with self.assertRaises(Conflict):self.manager.execute(self.confirm(plan))
        self.assertEqual(self.client.calls,[])
