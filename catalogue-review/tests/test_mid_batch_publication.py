"""Source publication between native operations, without live Dropbox calls."""
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import patch
import json
import threading
import unittest
import test_deletions
from catalogue import digest
from source_refresh import refresh_source


class MidBatchPublicationTests(unittest.TestCase):
    setUp = test_deletions.DeletionBatchTests.setUp
    tearDown = test_deletions.DeletionBatchTests.tearDown
    plans = test_deletions.DeletionBatchTests.plans
    batch = test_deletions.DeletionBatchTests.batch
    confirmation = test_deletions.DeletionBatchTests.confirmation

    def execute_with_publication(self, change_use=False):
        batch = self.batch(self.plans([test_deletions.TARGET, test_deletions.KEEPER, self.third]))
        app = NS(catalogue=self.cat, store=self.store, catalogue_lock=threading.RLock(),
                 sync=NS(base=self.cat, inventory_state=None), deletions=self.manager)
        successor = deepcopy(self.cat)
        if change_use:
            successor.edges['A'].pop(test_deletions.KEEPER)
        self.manager.refresh_source = lambda: refresh_source(app)
        real = self.manager.runner
        published = []

        def native(request):
            result = real(request)
            if request['action'] == 'execute' and request['binding']['id'] == test_deletions.TARGET:
                base = self.root / 'sculpture-catalogue'
                register = base / 'new.json'
                register.write_text('{"publication":2}')
                successor.source.update(register=str(register), register_sha256=digest(register))
                (base/'current-master.json').write_text(json.dumps({'register': register.name,
                    'register_sha256': digest(register), 'current_published_gallery_projection': {'path': 'index.html'}}))
                published.append(True)
            return result

        self.manager.runner = native
        with patch('source_refresh.Catalogue', return_value=successor), patch('source_refresh.apply_filename_overlay'):
            result = self.manager.execute_batch(self.confirmation(batch))
        self.assertEqual(published, [True])
        self.assertIs(self.manager.cat, successor)
        return result

    def test_independent_files_survive_a_publication_after_first_delete(self):
        result = self.execute_with_publication()
        self.assertEqual([r['state'] for r in result['results']], ['deleted']*3)
        self.assertEqual(self.client.calls, [(test_deletions.TARGET, 'a1'), (test_deletions.KEEPER, 'a1'), (self.third, 'a1')])
        self.assertTrue(all(r['verified_absent'] for r in result['results']))

    def test_changed_association_rejects_only_its_own_file_after_publication(self):
        result = self.execute_with_publication(change_use=True)
        self.assertEqual([r['state'] for r in result['results']], ['deleted', 'rejected', 'deleted'])
        self.assertEqual(self.client.calls, [(test_deletions.TARGET, 'a1'), (self.third, 'a1')])
        self.assertNotIn(test_deletions.KEEPER, self.client.gone)
