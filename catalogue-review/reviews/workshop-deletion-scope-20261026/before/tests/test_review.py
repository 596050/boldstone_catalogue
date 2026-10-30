import base64
from contextlib import closing
import csv
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exports import create_export
from store import Conflict, ReviewStore, validate


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ReviewStore(self.root / 'state')
        self.image = self.root / 'source.png'
        self.image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
        fields = [{'key': 'Weight', 'label': 'Weight', 'value': '6 kg — estimate', 'basis': 'Working estimate', 'qualification': 'Not weighed', 'section': 'Specifications'},
                  {'key': 'Name', 'label': 'Name', 'value': 'Panel', 'basis': 'Name', 'qualification': '', 'section': 'Listing copy'}]
        asset = {'id': 'image', 'name': 'Panel photograph', 'source': 'Dropbox', 'url': 'https://www.dropbox.com/example', 'folder_url': '', 'role': 'individual', 'representation': 'cached source'}
        self.cat = SimpleNamespace(products={pid: {'name': pid, 'family': 'Panels', 'fields': fields} for pid in ('A', 'B')}, assets={'image': asset},
                                   edges={'A': {'image': {}}, 'B': {'image': {}}}, paths={'image': (self.image, 'cached source')}, source={'register_sha256': 'source1'})

    def tearDown(self):
        self.temp.cleanup()

    def save(self, kind, pid, item, value, version=0):
        return self.store.save(kind, pid, item, validate(kind, value), version, 'source1', {'source': 'original'})

    def test_durable_reload_and_conflict(self):
        self.save('product', 'A', '', {'decision': 'include'})
        other = ReviewStore(self.root / 'state')
        self.assertEqual(other.get('product', 'A')['data']['decision'], 'include')
        with self.assertRaises(Conflict):
            self.save('product', 'A', '', {'decision': 'exclude'})
        self.assertEqual(other.get('product', 'A')['data']['decision'], 'include')

    def test_original_and_audit_history_retained(self):
        self.save('field', 'A', 'Weight', {'decision': 'edit', 'value': '7 kg', 'certainty': 'estimate'})
        self.save('field', 'A', 'Weight', {'decision': 'keep'}, 1)
        r = self.store.get('field', 'A', 'Weight')
        self.assertEqual(r['original'], {'source': 'original'})
        self.assertEqual(len(self.store.history()), 2)

    def test_confirmation_requires_evidence(self):
        with self.assertRaises(ValueError):
            validate('field', {'decision': 'edit', 'value': '7 kg', 'certainty': 'confirmed'})
        validate('field', {'decision': 'edit', 'value': '7 kg', 'certainty': 'confirmed', 'evidence': 'Weighed on workshop scale'})

    def test_exclusion_is_per_product(self):
        self.save('image', 'A', 'image', {'decision': 'exclude', 'uses': ['listing'], 'primary': False})
        self.save('image', 'B', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.assertEqual(self.store.get('image', 'A', 'image')['data']['uses'], [])
        self.assertEqual(self.store.get('image', 'B', 'image')['data']['uses'], ['listing'])

    def test_primary_is_unique_and_versioned(self):
        self.save('image', 'A', 'one', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.save('image', 'A', 'two', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        self.assertFalse(self.store.get('image', 'A', 'one')['data']['primary'])
        self.assertEqual(self.store.get('image', 'A', 'one')['version'], 2)
        self.assertTrue(self.store.get('image', 'A', 'two')['data']['primary'])

    def test_export_separates_ads_and_excluded_products(self):
        before = self.image.read_bytes()
        self.save('product', 'A', '', {'decision': 'exclude'})
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising'], 'primary': False})
        self.save('asset', '', 'image', {'tags': ['autumn'], 'collection': 'Campaign', 'rights': 'owned'})
        result = create_export(self.cat, self.store, True)
        root = Path(result['path'])
        self.assertEqual(result['included'], 0)
        self.assertEqual(result['listing_ready'], 0)
        self.assertEqual(len(list((root / 'media/advertising').rglob('*.png'))), 1)
        self.assertFalse((root / 'media/listing').exists())
        self.assertEqual(self.image.read_bytes(), before)
        self.assertIn('autumn', (root / 'asset-tags.csv').read_text())
        with zipfile.ZipFile(root.with_suffix('.zip')) as z:
            self.assertIsNone(z.testzip())
        with closing(sqlite3.connect(root / 'review-backup.sqlite3')) as db:
            self.assertEqual(db.execute('select count(*) from reviews').fetchone()[0], 3)

    def test_listing_copy_is_separate_from_certainty_and_ready_gate(self):
        self.save('product', 'A', '', {'decision': 'include', 'status': 'reviewed'})
        self.save('field', 'A', 'Weight', {'decision': 'edit', 'value': '7 kg', 'certainty': 'estimate'})
        self.save('field', 'A', 'Name', {'decision': 'edit', 'value': '=Danger()', 'certainty': 'retain'})
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        result = create_export(self.cat, self.store)
        self.assertEqual(result['listing_ready'], 1)
        with (Path(result['path']) / 'listing-ready.csv').open(encoding='utf-8-sig') as f:
            row = list(csv.DictReader(f))[0]
        self.assertEqual(row['Weight'], '7 kg')
        self.assertEqual(row['name'], "'=Danger()")
        self.assertEqual(row['Weight qualification'], 'estimate; Not weighed')
        with (Path(result['path']) / 'specification-decisions.csv').open(encoding='utf-8-sig') as f:
            detail = next(r for r in csv.DictReader(f) if r['product_id'] == 'A' and r['field'] == 'Weight')
        self.assertEqual(detail['original'], '6 kg — estimate')
        self.assertEqual(detail['certainty'], 'estimate')
        self.assertEqual(detail['listing_value'], '7 kg')

    def test_listing_hyphens_do_not_change_source_or_evidence(self):
        self.save('field', 'A', 'Name', {'decision': 'edit', 'value': 'Panel — White', 'certainty': 'source_claim', 'evidence': 'Owner — named panel'})
        result = create_export(self.cat, self.store)
        with (Path(result['path']) / 'specification-decisions.csv').open(encoding='utf-8-sig') as f:
            detail = next(r for r in csv.DictReader(f) if r['product_id'] == 'A' and r['field'] == 'Name')
        self.assertEqual(detail['listing_value'], 'Panel - White')
        self.assertEqual(detail['evidence'], 'Owner — named panel')
        self.assertEqual(self.store.get('field', 'A', 'Name')['data']['value'], 'Panel — White')

    def test_restricted_asset_and_edit_request_prevent_ready_export(self):
        self.save('product', 'A', '', {'decision': 'include', 'status': 'reviewed'})
        self.save('field', 'A', 'Weight', {'decision': 'keep'})
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['listing', 'advertising'], 'primary': True, 'edit_notes': 'Crop label'})
        self.save('asset', '', 'image', {'rights': 'restricted'})
        result = create_export(self.cat, self.store, True)
        self.assertEqual(result['listing_ready'], 0)
        self.assertFalse((Path(result['path']) / 'media').exists())

    def test_preview_never_exported_as_original(self):
        self.cat.paths['image'] = (self.image, 'cached preview')
        self.save('image', 'A', 'image', {'decision': 'reviewed', 'uses': ['advertising']})
        result = create_export(self.cat, self.store, True)
        root = Path(result['path'])
        self.assertTrue((root / 'preview-references/advertising').exists())
        self.assertFalse((root / 'media').exists())

    def test_validation_rejects_invalid_or_excessive_input(self):
        for kind, value in [('image', {'order': -1}), ('image', {'uses': ['delete']}), ('asset', {'tags': ['x'*81]}), ('product', {'decision': 'publish'}), ('field', {'decision': 'edit', 'value': ''})]:
            with self.assertRaises(ValueError):
                validate(kind, value)


if __name__ == '__main__':
    unittest.main()
