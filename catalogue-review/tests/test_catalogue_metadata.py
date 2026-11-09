"""Regression coverage for retained workshop rows from the published gallery."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalogue import Catalogue


class RetainedMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / 'project'
        self.base = self.project / 'sculpture-catalogue'
        self.base.mkdir(parents=True)
        self.full = self.project / 'original.png'
        self.thumb = self.project / 'thumb.png'
        raw = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
        self.full.write_bytes(raw)
        self.thumb.write_bytes(raw + b'preview')
        self.native_hash = hashlib.sha256(hashlib.sha256(raw).digest()).hexdigest()
        folder = 'https://www.dropbox.com/home/BOLDSTONE%20MASTER/Products/Workshop%20and%20Moulding/Workshop'
        self.row = {'name': 'workshop.png', 'family': 'Barbados Wave', 'image_url': None, 'folder_url': None,
                    'inventory_status': 'SAVED_REFERENCE_OUTSIDE_CURRENT_WALL_INVENTORY_SCOPE',
                    'visual_role': None, 'metadata': {'full': str(self.full), 'thumb': str(self.thumb),
                        'bytes': len(raw), 'source_content_hash': self.native_hash,
                        'image_url': folder.replace('/home/', '/preview/') + '/workshop.png', 'folder_url': folder}}
        register = self.base / 'register.json'
        register.write_text(json.dumps({'components': [], 'active_option_ids': []}))
        (self.base / 'current-master.json').write_text(json.dumps({'register': 'register.json',
            'register_sha256': hashlib.sha256(register.read_bytes()).hexdigest(),
            'current_published_gallery_projection': {'path': 'gallery/index.html'}}))
        gallery = self.base / 'gallery'
        gallery.mkdir()
        self.database = gallery / 'complete-image-platform-register.sqlite'
        with sqlite3.connect(self.database) as db:
            db.executescript('''
                CREATE TABLE products(product_id,name,family,record_json);
                CREATE TABLE images(file_id,folder_id,path,is_image,in_wall,record_json);
                CREATE TABLE associations(id,product_id,file_id,use,status,record_json);
                CREATE TABLE source_product_links(offer_ref,product_id);
                CREATE TABLE source_gallery(record_json);
                CREATE TABLE local_source_offers(record_json);
                CREATE TABLE local_shopify_gallery_reviews(record_json);
                CREATE TABLE local_shopify_media(handle,ordinal,record_json);
            ''')

    def tearDown(self):
        self.temp.cleanup()

    def load(self, row=None):
        row = deepcopy(row or self.row)
        with sqlite3.connect(self.database) as db:
            db.execute('DELETE FROM images')
            db.execute('INSERT INTO images VALUES(?,?,?,?,?,?)', ('id:photo', 'id:folder',
                'ns:202238505//BOLDSTONE MASTER/Products/Workshop and Moulding/Workshop/workshop.png',
                1, 0, json.dumps(row)))
        return Catalogue(self.project, self.root / 'app-state')

    def test_nested_original_links_size_and_scope_are_recovered(self):
        cat = self.load()
        asset = cat.assets['id:photo']
        self.assertTrue(asset['local_preview'])
        self.assertEqual(cat.paths['id:photo'][0], self.full)
        self.assertEqual(cat.preview_paths['id:photo'], self.thumb)
        self.assertEqual(asset['url'], self.row['metadata']['image_url'])
        self.assertEqual(asset['folder_url'], self.row['metadata']['folder_url'])
        self.assertEqual(asset['original']['bytes'], self.full.stat().st_size)
        self.assertEqual(asset['original']['dimensions'], [1, 1])
        self.assertTrue(asset['original']['locally_verified'])
        self.assertEqual(asset['inventory_status'], self.row['inventory_status'])
        self.assertFalse(asset.get('live_synced'))
        self.assertEqual(asset['types'], [])
        self.assertFalse(cat.edges)

    def test_master_fields_do_not_require_a_second_specifications_record(self):
        register = self.base / 'register.json'
        register.write_text(json.dumps({'components': [], 'active_option_ids': ['A']}))
        pointer_path = self.base / 'current-master.json'
        pointer = json.loads(pointer_path.read_text())
        pointer['register_sha256'] = hashlib.sha256(register.read_bytes()).hexdigest()
        pointer_path.write_text(json.dumps(pointer))
        with sqlite3.connect(self.database) as db:
            db.execute('INSERT INTO products VALUES(?,?,?,?)', ('A', 'Panel', 'Panels', json.dumps({
                'master_fields': {'Weight': {'display': '6 kg'}}, 'selling_details': {}})))
        self.assertEqual(self.load().fields('A')['Weight']['value'], '6 kg')

    def test_gallery_path_with_uri_characters_still_loads_read_only(self):
        old = self.database.parent
        renamed = old.with_name('gallery #1? saved')
        old.rename(renamed)
        self.database = renamed / self.database.name
        pointer_path = self.base / 'current-master.json'
        pointer = json.loads(pointer_path.read_text())
        pointer['current_published_gallery_projection']['path'] = renamed.name + '/index.html'
        pointer_path.write_text(json.dumps(pointer))
        self.assertIn('id:photo', self.load().assets)

    def test_explicit_private_cache_outside_project_can_supply_original_and_preview(self):
        cache = self.root / 'app-state'
        cache.mkdir()
        full = cache / 'retained.png'
        thumb = cache / 'retained-thumb.png'
        full.write_bytes(self.full.read_bytes())
        thumb.write_bytes(self.thumb.read_bytes())
        row = deepcopy(self.row)
        row['metadata'].update(full=str(full), thumb=str(thumb))
        cat = self.load(row)
        self.assertEqual(cat.paths['id:photo'][0], full)
        self.assertEqual(cat.preview_paths['id:photo'], thumb)

    def test_thumbnail_recovers_preview_without_claiming_original_dimensions(self):
        self.full.unlink()
        cat = self.load()
        asset = cat.assets['id:photo']
        self.assertEqual(cat.paths['id:photo'], (self.thumb, 'cached preview'))
        self.assertEqual(asset['original']['bytes'], self.row['metadata']['bytes'])
        self.assertIsNone(asset['original']['dimensions'])
        self.assertFalse(asset['original']['locally_verified'])

    def test_current_thumbnail_and_links_take_precedence_over_old_full_cache(self):
        row = deepcopy(self.row)
        current = self.project / 'current-preview.png'
        current.write_bytes(self.thumb.read_bytes())
        row.update(image_url='https://www.dropbox.com/preview/current.png',
                   folder_url='https://www.dropbox.com/home/current', saved_asset_metadata={'thumb': str(current)})
        row['metadata']['size'] = 1234
        cat = self.load(row)
        asset = cat.assets['id:photo']
        self.assertEqual(cat.paths['id:photo'], (current, 'cached preview'))
        self.assertEqual(cat.preview_paths['id:photo'], current)
        self.assertEqual(asset['url'], row['image_url'])
        self.assertEqual(asset['folder_url'], row['folder_url'])
        self.assertEqual(asset['original']['bytes'], 1234)

    def test_historical_links_survive_when_no_cache_is_available(self):
        self.full.unlink()
        self.thumb.unlink()
        row = deepcopy(self.row)
        row['historical_image_url'] = row['metadata'].pop('image_url')
        row['historical_folder_url'] = row['metadata'].pop('folder_url')
        cat = self.load(row)
        self.assertFalse(cat.assets['id:photo']['local_preview'])
        self.assertEqual(cat.assets['id:photo']['url'], row['historical_image_url'])
        self.assertEqual(cat.assets['id:photo']['folder_url'], row['historical_folder_url'])

    def test_fallback_cache_obeys_existing_path_boundary(self):
        outside = self.root / 'outside.png'
        outside.write_bytes(self.full.read_bytes())
        row = deepcopy(self.row)
        row['metadata'].update(full=str(outside), thumb=str(outside))
        cat = self.load(row)
        self.assertFalse(cat.assets['id:photo']['local_preview'])
        self.assertNotIn('id:photo', cat.paths)
        self.assertNotIn('id:photo', cat.preview_paths)


if __name__ == '__main__':
    unittest.main()
