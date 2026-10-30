from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
from http.server import ThreadingHTTPServer
import json
import re
import threading
import urllib.request
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from specifications import specification_overview
from server import Handler


class SpecificationOverviewTests(unittest.TestCase):
    def setUp(self):
        def field(key, value, section='Specifications'):
            return {'key': key, 'label': key, 'value': value, 'section': section,
                    'basis': 'Retained evidence', 'qualification': 'Not measured'}
        self.cat = SimpleNamespace(source={'register_sha256': 'source1'}, products={
            'A': {'name': 'Panel — White', 'family': 'Panels', 'folder_url': 'https://www.dropbox.com/folder',
                  'fields': [field('Weight', '6 kg — source'), field('Depth', ''),
                             field('Name', 'Panel — White', 'Listing copy'), field('Description', '', 'Listing copy')]},
            'B': {'name': 'Panel Bronze', 'family': 'Panels', 'fields': [field('Weight', '7 kg')]}})

    def review(self, kind, pid, item, data):
        return {'kind': kind, 'product_id': pid, 'item_id': item, 'version': 2, 'data': data}

    def test_all_components_and_fields_including_blank_values_are_visible(self):
        result = specification_overview(self.cat, [])
        self.assertEqual(result['totals'], {'products': 2, 'fields': 3, 'missing': 1, 'omitted': 0})
        product = next(p for p in result['products'] if p['id'] == 'A')
        self.assertEqual(len(product['listing_fields']), 2)
        self.assertEqual(product['fields'][0]['value'], '6 kg - source')
        self.assertEqual(product['fields'][0]['source_value'], '6 kg — source')
        self.assertEqual(product['folder_url'], 'https://www.dropbox.com/folder')

    def test_saved_edits_omissions_and_product_exclusion_stay_separate(self):
        rows = [self.review('field', 'A', 'Weight', {'decision': 'edit', 'value': '8 kg', 'certainty': 'estimate'}),
                self.review('field', 'A', 'Depth', {'decision': 'exclude'}),
                self.review('field', 'A', 'Name', {'decision': 'edit', 'value': 'New — White'}),
                self.review('product', 'A', '', {'decision': 'exclude', 'notes': 'Keep for reference'})]
        result = specification_overview(self.cat, rows)
        product = next(p for p in result['products'] if p['id'] == 'A')
        self.assertEqual(product['name'], 'New - White')
        self.assertEqual(product['fields'][0]['value'], '8 kg')
        self.assertEqual(product['fields'][0]['certainty'], 'estimate')
        self.assertIsNone(product['fields'][1]['value'])
        self.assertEqual(product['listing_decision'], 'exclude')
        self.assertEqual(product['notes'], 'Keep for reference')
        self.assertEqual(result['totals']['products'], 2)
        self.assertEqual(result['totals']['missing'], 0)
        self.assertEqual(result['totals']['omitted'], 1)

    def test_pending_or_keep_uses_source_not_a_previous_edit(self):
        for decision in ['pending', 'keep']:
            rows = [self.review('field', 'A', 'Weight', {'decision': decision, 'value': '99 kg'})]
            product = next(p for p in specification_overview(self.cat, rows)['products'] if p['id'] == 'A')
            self.assertEqual(product['fields'][0]['value'], '6 kg - source')

    def test_retired_records_and_image_choices_do_not_add_components(self):
        rows = [self.review('field', 'RETIRED', 'Weight', {'decision': 'edit', 'value': '9 kg'}),
                self.review('image', 'A', 'photo', {'decision': 'reviewed', 'uses': ['listing']})]
        result = specification_overview(self.cat, rows)
        self.assertEqual({p['id'] for p in result['products']}, {'A', 'B'})
        self.assertTrue(all('images' not in p for p in result['products']))

    def test_overview_is_read_only_and_revision_changes_only_with_relevant_details(self):
        original = deepcopy(self.cat.products)
        rows = [self.review('field', 'A', 'Weight', {'decision': 'edit', 'value': '8 kg'})]
        previous_rows = deepcopy(rows)
        first = specification_overview(self.cat, rows)
        self.assertEqual(first['revision'], specification_overview(self.cat, rows)['revision'])
        rows.append(self.review('asset', '', 'photo', {'types': ['in_situ']}))
        self.assertEqual(first['revision'], specification_overview(self.cat, rows)['revision'])
        self.assertEqual(self.cat.products, original)
        self.assertEqual(rows[0], previous_rows[0])
        rows[0]['data']['value'] = '10 kg'
        self.assertNotEqual(first['revision'], specification_overview(self.cat, rows)['revision'])

    def test_family_display_edit_does_not_regroup_component_identity(self):
        self.cat.products['A']['fields'].append({'key': 'Family', 'label': 'Family', 'value': 'Panels',
                                               'section': 'Listing copy', 'basis': '', 'qualification': ''})
        rows = [self.review('field', 'A', 'Family', {'decision': 'edit', 'value': 'Another collection'})]
        product = next(p for p in specification_overview(self.cat, rows)['products'] if p['id'] == 'A')
        self.assertEqual(product['family'], 'Panels')
        self.assertEqual(next(f['value'] for f in product['listing_fields'] if f['key'] == 'Family'), 'Another collection')

    def test_overview_endpoint_and_every_page_script_are_served(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = SimpleNamespace(catalogue_lock=threading.RLock(), catalogue=self.cat,
                                     store=SimpleNamespace(all=lambda: []))
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:' + str(server.server_port)
        try:
            with urllib.request.urlopen(base + '/') as response:
                html = response.read().decode()
            for path in re.findall(r'<script src="([^"]+)"', html):
                with urllib.request.urlopen(base + path) as response:
                    self.assertIn('javascript', response.headers['Content-Type'])
                    self.assertTrue(response.read())
            with urllib.request.urlopen(base + '/api/specifications') as response:
                data = json.load(response)
            self.assertEqual(data['totals']['products'], 2)
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    unittest.main()
