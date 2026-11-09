"""Exports must agree with reviewed fields/photos and survive missing cache files."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import test_review
from component_photos import component_photos
from exports import create_export
from projection import Projection
from store import validate


class ExportConsistencyTests(unittest.TestCase):
    setUpBase = test_review.ReviewTests.setUp
    tearDown = test_review.ReviewTests.tearDown

    def setUp(self):
        self.setUpBase()
        self.cat.assets['image']['original'] = {'dropbox_content_hash': 'a' * 64}
        self.save('product', '', {'decision': 'include', 'status': 'reviewed'})
        self.save('field', 'Weight', {'decision': 'keep'})
        self.save('image', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})

    def save(self, kind, item, data, original=None):
        if original is None:
            if kind == 'field':
                original = next(f for f in self.cat.products['A']['fields'] if f['key'] == item)
            elif kind == 'image':
                original = {'asset': self.cat.assets[item], 'association': self.cat.edges['A'][item]}
            else:
                original = {}
        version = self.store.get(kind, 'A', item)['version']
        self.store.save(kind, 'A', item, validate(kind, data), version,
                        self.cat.source['register_sha256'], deepcopy(original))

    def export(self, media=False):
        result = create_export(self.cat, self.store, media)
        with (Path(result['path']) / 'all-product-decisions.csv').open(encoding='utf-8-sig') as stream:
            product = next(r for r in csv.DictReader(stream) if r['product_id'] == 'A')
        with (Path(result['path']) / 'image-decisions-and-tags.csv').open(encoding='utf-8-sig') as stream:
            images = [r for r in csv.DictReader(stream) if r['product_id'] == 'A']
        return result, product, images

    def test_unrelated_publication_and_image_rename_preserve_readiness(self):
        before = self.store.snapshot()
        self.cat.source['register_sha256'] = 'new-register'
        self.cat.assets['image']['name'] = 'panel__white__001.png'
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 1, product['review_blockers'])
        self.assertEqual(self.store.snapshot(), before)

    def test_changed_field_value_or_qualification_still_requires_review(self):
        self.cat.source['register_sha256'] = 'new-register'
        field = self.cat.products['A']['fields'][0]
        for key, value in [('value', '12 kg'), ('qualification', 'Different source claim'),
                           ('basis', 'Different material record')]:
            original = field[key]
            with self.subTest(key=key):
                field[key] = value
                result, product, _ = self.export()
                self.assertEqual(result['listing_ready'], 0)
                self.assertIn('Source changed since field review: Weight', product['review_blockers'])
            field[key] = original

    def test_legacy_field_without_snapshot_fails_closed_after_publication(self):
        with self.store.connect() as db:
            db.execute("UPDATE reviews SET original='{}' WHERE kind='field'")
        self.cat.source['register_sha256'] = 'new-register'
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 0)
        self.assertIn('Source changed since field review', product['review_blockers'])

    def test_changed_image_bytes_still_require_review(self):
        self.cat.source['register_sha256'] = 'new-register'
        self.cat.assets['image']['original']['dropbox_content_hash'] = 'b' * 64
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 0)
        self.assertIn('Source changed since image review', product['review_blockers'])

    def test_missing_image_identity_does_not_auto_approve_after_publication(self):
        self.cat.source['register_sha256'] = 'new-register'
        self.cat.assets['image']['original'] = {}
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 0)
        self.assertIn('Source changed since image review', product['review_blockers'])

    def test_latest_reviewed_bytes_override_first_review_image_snapshot(self):
        # The store deliberately retains the original first-review snapshot.
        # A later explicit review records the replacement's current hash.
        self.cat.assets['image']['original']['dropbox_content_hash'] = 'b' * 64
        self.save('image', 'image', {'decision': 'reviewed', 'uses': ['listing'], 'primary': True})
        with self.store.connect() as db:
            record = self.store.get('image', 'A', 'image')
            data = {**record['data'], 'reviewed_content_hash': 'b' * 64}
            db.execute("UPDATE reviews SET data=? WHERE kind='image'", (json.dumps(data),))
        self.cat.source['register_sha256'] = 'new-register'
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 1, product['review_blockers'])

    def test_two_primary_selections_are_not_listing_ready(self):
        self.cat.assets['other'] = {**deepcopy(self.cat.assets['image']), 'id': 'other', 'name': 'Other photo'}
        self.cat.edges['A']['other'] = {'tier': 'accepted'}
        self.save('image', 'other', {'decision': 'reviewed', 'uses': ['listing'], 'primary': False})
        # Historical imports can contain conflicting primaries. The live cards
        # flag this rather than choosing one, so the export must do the same.
        with self.store.connect() as db:
            data = {'decision': 'reviewed', 'uses': ['listing'], 'primary': True}
            db.execute("UPDATE reviews SET data=? WHERE kind='image' AND item_id='other'", (json.dumps(data),))
        self.assertEqual(component_photos(Projection(self.cat, self.store.all()), 'A')['primary_listing']['status'], 'needs_review')
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 0)
        self.assertIn('primary', product['review_blockers'].lower())

    def test_deleted_cached_file_does_not_abort_review_bundle(self):
        before = self.store.snapshot()
        self.image.unlink()
        result, _, images = self.export(media=True)
        self.assertTrue(Path(result['path']).with_suffix('.zip').is_file())
        self.assertEqual(images[0]['media_file'], '')
        self.assertIn('unavailable', images[0]['export_status'].lower())
        self.assertEqual(images[0]['source_url'], self.cat.assets['image']['url'])
        self.assertEqual(self.store.snapshot(), before)

    def test_edited_media_product_name_uses_listing_wording(self):
        self.save('field', 'Name', {'decision': 'edit', 'value': 'Panel — White', 'certainty': 'retain'})
        _, product, images = self.export()
        self.assertEqual(images[0]['product_name'], product['name'])
        self.assertEqual(images[0]['product_name'], 'Panel - White')

    def test_tied_photo_orders_match_the_component_carousel(self):
        for aid, name in [('id:a', 'Zebra photo'), ('id:z', 'Apple photo')]:
            self.cat.assets[aid] = {**deepcopy(self.cat.assets['image']), 'id': aid, 'name': name}
            self.cat.edges['A'][aid] = {'tier': 'accepted'}
            self.save('image', aid, {'decision': 'reviewed', 'uses': ['listing'], 'order': 0})
        expected = component_photos(Projection(self.cat, self.store.all()), 'A')['listing_ids']
        self.assertEqual(expected, ['image', 'id:z', 'id:a'])
        _, product, _ = self.export()
        self.assertEqual(json.loads(product['listing_image_ids']), expected)

    def test_sha256_identity_preserves_platform_original_review(self):
        self.cat.assets['image']['source'] = 'Shopify'
        self.cat.assets['image']['original'] = {'sha256': 'c' * 64}
        with self.store.connect() as db:
            original = {'asset': deepcopy(self.cat.assets['image'])}
            db.execute("UPDATE reviews SET original=? WHERE kind='image'", (json.dumps(original),))
        self.cat.source['register_sha256'] = 'new-register'
        self.assertEqual(self.export()[0]['listing_ready'], 1)
        self.cat.assets['image']['original']['sha256'] = 'd' * 64
        self.assertEqual(self.export()[0]['listing_ready'], 0)

    def test_unknown_alias_review_is_not_hidden_by_a_newer_current_review(self):
        self.cat.assets['alias'] = {**deepcopy(self.cat.assets['image']), 'id': 'alias'}
        self.cat.canonical_assets = {'alias': 'image'}
        self.cat.duplicate_members = {'image': ['image', 'alias']}
        choice = self.store.get('image', 'A', 'image')['data']
        with self.store.connect() as db:
            # Legacy import: same choices, but no proof of the originally
            # reviewed bytes. A newer canonical row must not conceal this.
            db.execute("INSERT INTO reviews SELECT kind,product_id,'alias',version,data,'older-source','{}',updated_at FROM reviews WHERE kind='image'")
        self.assertEqual(self.store.get('image', 'A', 'alias')['data'], choice)
        result, product, _ = self.export()
        self.assertEqual(result['listing_ready'], 0)
        self.assertIn('Source changed since image review', product['review_blockers'])

    def test_missing_cache_does_not_prevent_other_files_exporting(self):
        other = self.root / 'other.png'
        other.write_bytes(self.image.read_bytes())
        self.cat.assets['other'] = {**deepcopy(self.cat.assets['image']), 'id': 'other', 'name': 'Other photo'}
        self.cat.edges['A']['other'] = {'tier': 'accepted'}
        self.cat.paths['other'] = (other, 'cached source')
        self.save('image', 'other', {'decision': 'reviewed', 'uses': ['advertising']})
        self.image.unlink()
        result, _, images = self.export(media=True)
        rows = {r['asset_id']: r for r in images}
        self.assertEqual(rows['image']['media_file'], '')
        self.assertTrue((Path(result['path']) / rows['other']['media_file']).is_file())

    def test_output_write_failure_is_not_reported_as_successful_export(self):
        with patch('exports.shutil.copyfileobj', side_effect=OSError('No space left on output device')):
            with self.assertRaisesRegex(OSError, 'No space left'):
                self.export(media=True)
        self.assertEqual(list((self.store.root / 'exports').glob('*.zip')), [])

    def test_export_snapshot_does_not_mix_in_choices_saved_during_export(self):
        backup = self.store.backup
        def save_after_backup(path):
            backup(path)
            self.save('image', 'image', {'decision': 'exclude'})
        with patch.object(self.store, 'backup', side_effect=save_after_backup):
            result, _, images = self.export()
        self.assertEqual(result['listing_ready'], 1)
        self.assertEqual(images[0]['use'], 'listing')
        self.assertEqual(self.store.get('image', 'A', 'image')['data']['decision'], 'exclude')


if __name__ == '__main__':
    unittest.main()
