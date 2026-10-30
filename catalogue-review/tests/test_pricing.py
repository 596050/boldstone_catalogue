"""Markup prices stay consistent across costs, specifications and listing exports."""
from copy import deepcopy
import csv
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from costing import DEFAULTS, default_inputs, pricing, priced_listing_value, product_cost, settings, validate_inputs, validate_settings
from exports import create_export
from projection import Projection
from server import Application, Handler
from specifications import specification_overview
from store import ReviewStore, Conflict


def product():
    rows = [('Name', 'Dune Ripple Verdigris'), ('Dimensions / depth', '35 x 20 x 6 cm'),
            ('Weight', '4 kg'), ('Material / finish', 'GFRC with verdigris'),
            ('Fixing', 'Keyhole'), ('Price', '£250 per individual panel')]
    return {'id': 'A', 'name': rows[0][1], 'family': 'Dune Ripple',
            'fields': [{'key': k, 'label': k, 'value': v, 'section': 'Listing copy' if k == 'Name' else 'Specifications',
                        'basis': 'Retained source', 'qualification': ''} for k, v in rows]}


class MarkupPricingTests(unittest.TestCase):
    def setUp(self):
        self.product = product()
        self.config = {**deepcopy(DEFAULTS), 'default_pricing_mode': 'markup'}

    def cost(self, inputs=None, reviews=None):
        rows = list(reviews or [])
        if inputs is not None:
            rows.append({'kind': 'cost', 'product_id': 'A', 'item_id': '', 'version': 1,
                         'data': {**default_inputs(self.product, []), **inputs}})
        return product_cost(self.product, rows, (self.config, 3))

    def test_one_hundred_percent_doubles_all_costs_including_labour(self):
        c = self.cost()
        self.assertEqual(c['total_cost'], 38.33)
        self.assertEqual(c['pricing']['marked_up_price'], 76.66)
        self.assertEqual(c['pricing']['listing_value'], '£76.66')
        self.assertEqual(c['pricing']['fixed_value'], '£250 per individual panel')

    def test_zero_fractional_and_large_markup_use_markup_not_margin(self):
        for pct, amount in [(0, 38.33), (12.5, 43.12), (200, 114.99), (10000, 3871.33)]:
            with self.subTest(pct=pct):
                self.assertEqual(self.cost({'markup_percent': pct})['pricing']['marked_up_price'], amount)

    def test_penny_rounding_is_half_up(self):
        self.assertEqual(pricing({'markup_percent': 50}, self.config, 1.01)['marked_up_price'], 1.52)
        self.assertEqual(pricing({}, self.config, 0)['marked_up_price'], 0)

    def test_shared_percentage_changes_inherited_prices_but_not_overrides(self):
        self.config['default_markup_percent'] = 150
        self.assertEqual(self.cost()['pricing']['marked_up_price'], 95.83)
        self.assertEqual(self.cost({'markup_percent': 100})['pricing']['marked_up_price'], 76.66)
        self.assertFalse(self.cost({'markup_percent': 0})['pricing']['uses_shared_markup'])
        self.assertTrue(self.cost({'markup_percent': None})['pricing']['uses_shared_markup'])

    def test_fixed_override_and_markup_override_ignore_shared_method(self):
        c = self.cost({'pricing_mode': 'fixed'})
        self.assertEqual(c['pricing']['listing_value'], '£250 per individual panel')
        self.config['default_pricing_mode'] = 'fixed'
        self.assertEqual(self.cost({'pricing_mode': 'markup'})['pricing']['listing_value'], '£76.66')

    def test_labour_and_material_changes_recalculate_price(self):
        c = self.cost({'labour_hours_override': 2})
        self.assertEqual(c['total_cost'], 60)
        self.assertEqual(c['pricing']['marked_up_price'], 120)
        self.config['materials']['gfrc']['rate'] = 8
        self.assertEqual(self.cost({'labour_hours_override': 2})['pricing']['marked_up_price'], 126)

    def test_fixed_review_survives_markup_and_switching_back(self):
        r = {'kind': 'field', 'product_id': 'A', 'item_id': 'Price',
             'data': {'decision': 'edit', 'value': '£350 per panel'}}
        original = deepcopy(self.product)
        self.assertEqual(self.cost(reviews=[r])['pricing']['listing_value'], '£76.66')
        self.assertEqual(self.cost({'pricing_mode': 'fixed'}, [r])['pricing']['listing_value'], '£350 per panel')
        self.assertEqual(self.product, original)

    def test_price_exclusion_is_not_reintroduced_by_markup(self):
        choice = {'decision': 'exclude'}
        c = self.cost(reviews=[{'kind': 'field', 'product_id': 'A', 'item_id': 'Price', 'data': choice}])
        self.assertTrue(c['pricing']['price_omitted'])
        self.assertIsNone(c['pricing']['listing_value'])
        self.assertIsNone(priced_listing_value(self.product['fields'][-1], choice, c))

    def test_missing_cost_inputs_withhold_markup_price_instead_of_old_fixed_price(self):
        self.product['fields'][1]['value'] = 'Unknown dimensions'
        c = self.cost()
        self.assertEqual(c['status'], 'needs_inputs')
        self.assertEqual(c['pricing']['listing_value'], '')
        self.assertEqual(priced_listing_value(self.product['fields'][-1], {}, c), '')

    def test_legacy_saved_rates_and_cost_inputs_load_without_mutation(self):
        config = deepcopy(DEFAULTS)
        config.pop('default_pricing_mode'); config.pop('default_markup_percent')
        config['labour_hourly'] = 31
        record = {'kind': 'cost_settings', 'product_id': '', 'item_id': '', 'version': 7, 'data': config}
        before = deepcopy(record)
        c, version = settings([record])
        self.assertEqual(c['default_markup_percent'], 100)
        self.assertEqual(c['default_pricing_mode'], 'fixed')
        self.assertEqual(c['labour_hourly'], 31)
        self.assertEqual(version, 7)
        self.assertEqual(record, before)

    def test_rejects_negative_nonfinite_boolean_string_and_excessive_markup(self):
        for bad in [-1, float('inf'), float('nan'), True, '100', 10001]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_inputs({**default_inputs(self.product, []), 'markup_percent': bad}, self.config)
            with self.subTest(shared=bad), self.assertRaises(ValueError):
                validate_settings({**self.config, 'default_markup_percent': bad})
        with self.assertRaises(ValueError):
            validate_inputs({**default_inputs(self.product, []), 'pricing_mode': 'margin'}, self.config)


class PricingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = Application.__new__(Application)
        self.app.store = ReviewStore(self.temp.name)
        self.app.catalogue = SimpleNamespace(products={'A': product()}, assets={}, edges={'A': {}},
                                            paths={}, source={'register_sha256': 'source'})
        self.app.catalogue.fields = lambda pid: {f['key']: f for f in self.app.catalogue.products[pid]['fields']}
        self.app.catalogue_lock = threading.RLock()
        self.app.token = 'isolated-pricing-test'
        self.app.refresh_source = lambda: None
        self.app.projection = lambda: Projection(self.app.catalogue, self.app.store.all())
        self.config = {**deepcopy(DEFAULTS), 'default_pricing_mode': 'markup'}
        self.app.save({'kind': 'cost_settings', 'version': 0, 'data': self.config})

    def save_cost(self, data, version=0, rates_version=1):
        return self.app.save({'kind': 'cost', 'product_id': 'A', 'item_id': '', 'version': version,
                              'settings_version': rates_version, 'data': data})

    def test_saved_settings_and_overrides_are_durable_and_conflict_checked(self):
        data = {**default_inputs(product(), []), 'pricing_mode': 'markup', 'markup_percent': 125}
        self.save_cost(data)
        reopened = ReviewStore(self.temp.name)
        self.assertEqual(reopened.get('cost', 'A')['data']['markup_percent'], 125)
        with self.assertRaises(Conflict): self.save_cost(data)
        with self.assertRaises(Conflict): self.save_cost(data, 1, 0)
        self.assertEqual(product_cost(product(), reopened.all())['pricing']['marked_up_price'], 86.24)

    def test_older_client_cost_save_does_not_reset_pricing_override(self):
        data = {**default_inputs(product(), []), 'pricing_mode': 'fixed', 'markup_percent': 50}
        self.save_cost(data)
        legacy = {k: v for k, v in data.items() if k not in ('pricing_mode', 'markup_percent')}
        result = self.save_cost({**legacy, 'other_cost': 10}, 1)
        self.assertEqual(result['data']['pricing_mode'], 'fixed')
        self.assertEqual(result['data']['markup_percent'], 50)

    def test_overview_and_csv_prices_match_and_keep_original_price_audit(self):
        result = specification_overview(self.app.catalogue, self.app.store.all())
        f = next(f for f in result['products'][0]['fields'] if f['key'] == 'Price')
        self.assertEqual(f['value'], '£76.66')
        self.assertEqual(f['source_value'], '£250 per individual panel')
        self.assertEqual(f['decision'], 'calculated')
        export = create_export(self.app.catalogue, self.app.store)
        def rows(name):
            with (Path(export['path']) / name).open(encoding='utf-8-sig') as stream:
                return list(csv.DictReader(stream))
        p = rows('all-product-decisions.csv')[0]
        self.assertEqual(p['Price'], f['value'])
        self.assertEqual(p['pricing_method'], 'markup')
        self.assertEqual(rows('manufacturing-costs.csv')[0]['listing_price'], f['value'])
        audit = next(r for r in rows('specification-decisions.csv') if r['field'] == 'Price')
        self.assertEqual(audit['original'], f['source_value'])
        self.assertEqual(audit['listing_value'], f['value'])

    def test_preview_uses_current_fixed_price_and_never_saves_inputs(self):
        self.app.save({'kind': 'field', 'product_id': 'A', 'item_id': 'Price', 'version': 0,
                       'data': {'decision': 'edit', 'value': '£350', 'certainty': 'source_claim'}})
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.app = self.app
        threading.Thread(target=server.serve_forever, daemon=True).start()
        before = self.app.store.all()
        try:
            body = {'product_id': 'A', 'settings_version': 1,
                    'data': {**default_inputs(product(), []), 'pricing_mode': 'fixed'}}
            url = f'http://127.0.0.1:{server.server_port}/api/costs/preview'
            request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
                'Content-Type': 'application/json', 'X-Review-Token': self.app.token})
            with urllib.request.urlopen(request) as response: result = json.load(response)
            self.assertEqual(result['pricing']['listing_value'], '£350')
            self.assertEqual(self.app.store.all(), before)
        finally:
            server.shutdown(); server.server_close()
