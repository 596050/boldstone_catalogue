"""Packed-parcel limits, tariff failures and isolated HTTP/persistence checks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import csv
import itertools
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delivery import SEED, Tariffs, parse_page, quote, validate_package, validate_tariff
from exports import create_export
from projection import Projection
from server import Application, Handler
from store import Conflict, ReviewStore


def package(**overrides):
    return {'length_cm': 45, 'width_cm': 35, 'depth_cm': 16, 'weight_kg': 2,
            'packaging_gbp': 0, 'collection': False, 'destination': 'uk', **overrides}


# Contract fixture: the published service table has both counter and online
# prices, and signature columns. It is not a saved live fetch (HTTP 403 locally).
PAGE = '''<html><script>Compensation cover up to £999</script>
<table><tr><th></th><th></th><th colspan="2">Tracked 48</th><th colspan="2">Tracked 48 with Signature</th></tr>
<tr><th>Size</th><th>Weight up to and including</th><th>Price</th><th>Online Price</th><th>Price</th><th>Online Price</th></tr>
<tr><td>Large Letter (Online purchase)</td><td>1kg</td><td></td><td>£2.90</td><td></td><td>£4.90</td></tr>
<tr><td>Small parcel</td><td>2kg</td><td>£4.70</td><td>£3.75</td><td>£6.30</td><td>£5.35</td></tr>
<tr><td rowspan="3">Medium parcel</td><td>2kg</td><td>£7.60</td><td>£5.70</td><td>£9.20</td><td>£7.30</td></tr>
<tr><td>10kg</td><td>£9.60</td><td>£7.55</td><td>£11.20</td><td>£9.15</td></tr>
<tr><td>20kg</td><td>£14.30</td><td>£12.25</td><td>£15.90</td><td>£13.85</td></tr></table>
<p>Prices include VAT</p><p>Collection for a small fee - just 50p per item</p><p>Compensation cover up to £75</p>
<h3>Small Parcel</h3><p>Max 2kg |</p><p>Max L 45cm x W 35cm x D 16cm</p>
<h3>Medium parcel</h3><p>Max 20kg |</p><p>Max L 61cm x W 46cm x D 46cm</p></html>'''


class QuoteTests(unittest.TestCase):
    def result(self, **kwargs):
        return quote(package(**kwargs), SEED)

    def test_size_and_weight_boundaries_are_inclusive(self):
        self.assertEqual(self.result()['tier']['id'], 'small_2')
        for kg, tier, pence in [(2, 'medium_2', 570), (2.000001, 'medium_10', 755),
                                (10, 'medium_10', 755), (10.001, 'medium_20', 1225), (20, 'medium_20', 1225)]:
            result = self.result(length_cm=61, width_cm=46, depth_cm=46, weight_kg=kg)
            self.assertEqual((result['tier']['id'], result['total_pence']), (tier, pence))
        self.assertEqual(self.result(weight_kg=20.00001)['status'], 'separate_quote')

    def test_all_box_orientations_are_equivalent(self):
        for dims in itertools.permutations([45, 35, 16]):
            self.assertEqual(self.result(**dict(zip(('length_cm', 'width_cm', 'depth_cm'), dims)))['tier']['id'], 'small_2')

    def test_small_box_over_two_kg_uses_medium_weight_band(self):
        self.assertEqual(self.result(weight_kg=2.001)['tier']['id'], 'medium_10')

    def test_small_box_just_over_each_size_moves_to_medium(self):
        for key, value in [('length_cm', 45.001), ('width_cm', 35.001), ('depth_cm', 16.001)]:
            self.assertEqual(self.result(**{key: value})['tier']['id'], 'medium_2')

    def test_oversize_and_international_never_return_a_charge(self):
        for changes in [dict(length_cm=61.001), dict(width_cm=46.001, depth_cm=46.001),
                        dict(weight_kg=25), dict(destination='international')]:
            result = self.result(**changes)
            self.assertEqual(result['status'], 'separate_quote')
            self.assertNotIn('total_pence', result)

    def test_money_uses_pennies_and_packaging_half_up(self):
        result = self.result(collection=True, packaging_gbp=1.005)
        self.assertEqual(result['packaging_pence'], 101)
        self.assertEqual(result['total_pence'], 526)
        self.assertEqual(result['postage_pence'], 375)

    def test_missing_unknown_and_nonfinite_inputs_are_rejected(self):
        for key in ('length_cm', 'width_cm', 'depth_cm', 'weight_kg'):
            for bad in (0, -1, True, None, '', '2', float('nan'), float('inf')):
                with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                    self.result(**{key: bad})
        for changes in [dict(packaging_gbp=-1), dict(collection='yes'), dict(destination='any'), dict(url='https://example.com')]:
            with self.assertRaises(ValueError):
                self.result(**changes)
        with self.assertRaises(ValueError): validate_package({})

    def test_quotes_do_not_mutate_inputs_or_tariff(self):
        data, tariff = package(), deepcopy(SEED)
        quote(data, tariff)
        self.assertEqual(data, package()); self.assertEqual(tariff, SEED)


class TariffTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(); self.addCleanup(self.root.cleanup)
        self.now = datetime(2026, 10, 30, 19, tzinfo=timezone.utc)
        self.calls = 0
        def fetch():
            self.calls += 1
            return PAGE
        self.manager = Tariffs(self.root.name, fetch=fetch, now=lambda: self.now)

    def test_parser_selects_online_prices_not_counter_or_signature(self):
        result = parse_page(PAGE, self.now.isoformat())
        self.assertEqual([x['pence'] for x in result['tiers']], [375, 570, 755, 1225])
        self.assertEqual(result['collection_pence'], 50)
        self.assertEqual(result['compensation_gbp'], 75)
        self.assertEqual(result['tiers'][0]['max_cm'], [45, 35, 16])

    def test_success_is_atomic_and_reloadable(self):
        self.manager.fetch = lambda: PAGE.replace('£3.75', '£3.85')
        result = self.manager.refresh()
        self.assertEqual(result['last_attempt']['status'], 'ok')
        self.assertEqual(result['tariff']['tiers'][0]['pence'], 385)
        again = Tariffs(self.root.name, now=lambda: self.now)
        self.assertEqual(again.snapshot(), result)

    def test_http_403_preserves_last_verified_rates_and_date(self):
        self.manager.refresh()
        before = self.manager.snapshot()['tariff']
        self.now += timedelta(days=1)
        def fail(): raise urllib.error.HTTPError('https://www.royalmail.com', 403, 'Forbidden', {}, None)
        self.manager.fetch = fail
        result = self.manager.refresh()
        self.assertEqual(result['tariff'], before)
        self.assertTrue(result['needs_confirmation'])
        self.assertIn('403', result['last_attempt']['message'])
        self.assertEqual(Tariffs(self.root.name, now=lambda: self.now).snapshot()['tariff'], before)

    def test_incomplete_or_changed_pages_cannot_replace_verified_rates(self):
        for html in [PAGE.replace('£12.25', ''), PAGE.replace('Max L 45cm', ''),
                     PAGE.replace('just 50p per item', 'Free collection'),
                     PAGE.replace('Online Price', 'Price'), PAGE.replace('£3.75', '£0.00'),
                     PAGE.replace('Prices include VAT', ''), '<html>Sign in</html>', PAGE + PAGE]:
            self.manager.fetch = lambda: html
            result = self.manager.refresh(force=True)
            self.assertEqual(result['tariff'], SEED)
            self.assertEqual(result['last_attempt']['status'], 'failed')
            self.now += timedelta(minutes=2)

    def test_timeout_keeps_rates_and_allows_a_later_retry(self):
        self.manager.fetch = lambda: (_ for _ in ()).throw(TimeoutError())
        self.assertTrue(self.manager.refresh()['needs_confirmation'])
        self.now += timedelta(minutes=2)
        self.manager.fetch = lambda: PAGE
        self.assertFalse(self.manager.refresh(force=True)['needs_confirmation'])

    def test_automatic_daily_cooldown_and_manual_minute_cooldown(self):
        self.manager.snapshot(); self.assertEqual(self.calls, 0)
        self.manager.refresh(); self.assertEqual(self.calls, 1)
        self.now += timedelta(seconds=30)
        self.manager.refresh(force=True); self.assertEqual(self.calls, 1)
        self.now += timedelta(seconds=31)
        self.manager.refresh(); self.assertEqual(self.calls, 1)
        self.manager.refresh(force=True); self.assertEqual(self.calls, 2)
        self.now += timedelta(days=1)
        self.manager.refresh(); self.assertEqual(self.calls, 3)

    def test_stale_seed_is_identified_without_network(self):
        self.now += timedelta(days=2)
        self.assertTrue(self.manager.snapshot()['stale'])
        self.assertTrue(self.manager.snapshot()['needs_confirmation'])
        self.assertEqual(self.calls, 0)

    def test_concurrent_refreshes_share_one_fetch_without_blocking_quotes(self):
        started, finish = threading.Event(), threading.Event()
        def fetch():
            self.calls += 1; started.set(); finish.wait(3); return PAGE
        self.manager.fetch = fetch
        worker = threading.Thread(target=self.manager.refresh); worker.start()
        try:
            self.assertTrue(started.wait(1))
            self.assertTrue(self.manager.refresh(force=True)['refreshing'])
            self.assertEqual(quote(package(), self.manager.snapshot()['tariff'])['total_pence'], 375)
            self.assertEqual(self.calls, 1)
        finally:
            finish.set(); worker.join(3)
        self.assertFalse(self.manager.snapshot()['refreshing'])

    def test_failed_disk_write_keeps_previous_tariff(self):
        self.manager.fetch = lambda: PAGE.replace('£3.75', '£3.85')
        with patch.object(self.manager, '_persist', side_effect=OSError('full')):
            result = self.manager.refresh()
        self.assertEqual(result['tariff'], SEED)
        self.assertIn('Could not save', result['last_attempt']['message'])

    def test_corrupt_cache_falls_back_with_visible_warning(self):
        self.manager.path.write_text('{bad')
        manager = Tariffs(self.root.name, now=lambda: self.now)
        self.assertEqual(manager.snapshot()['tariff'], SEED)
        self.assertTrue(manager.snapshot()['needs_confirmation'])

    def test_mutating_a_status_result_cannot_change_shared_rates(self):
        snapshot = self.manager.snapshot(); snapshot['tariff']['tiers'][0]['pence'] = 1
        self.assertEqual(self.manager.snapshot()['tariff']['tiers'][0]['pence'], 375)


class DeliveryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory(); self.addCleanup(self.root.cleanup)
        self.app = Application.__new__(Application)
        self.app.store = ReviewStore(self.root.name)
        p = {'id': 'A', 'name': 'Test sculpture', 'family': 'Test', 'fields': []}
        self.app.catalogue = SimpleNamespace(products={'A': p}, assets={}, edges={'A': {}}, paths={}, source={'register_sha256': 'source'})
        self.app.catalogue.fields = lambda pid: {}
        self.app.catalogue_lock = threading.RLock(); self.app.token = 'isolated-test-token'
        self.app.refresh_source = lambda: None
        self.app.tariffs = Tariffs(self.root.name, fetch=lambda: PAGE)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler); self.server.app = self.app
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True); self.worker.start()
        self.addCleanup(self.server.server_close); self.addCleanup(self.server.shutdown)

    def request(self, path, data=None, token=True):
        headers = {'Content-Type': 'application/json'}
        if token: headers['X-Review-Token'] = self.app.token
        req = urllib.request.Request(f'http://127.0.0.1:{self.server.server_port}'+path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=3) as response: return json.load(response)

    def test_quote_is_read_only_and_does_not_book_or_save(self):
        before = self.app.store.snapshot()
        self.assertEqual(self.request('/api/delivery/quote', {'data': package()})['total_pence'], 375)
        self.assertEqual(self.app.store.snapshot(), before)

    def test_package_save_reopen_conflict_and_export(self):
        body = {'kind': 'delivery', 'product_id': 'A', 'version': 0, 'data': package(packaging_gbp=2)}
        record = self.request('/api/reviews', body)
        self.assertEqual(record['version'], 1)
        result = self.request('/api/delivery?product_id=A')
        self.assertEqual(result['package']['data'], body['data'])
        self.assertEqual(ReviewStore(self.root.name).get('delivery', 'A')['data'], body['data'])
        with self.assertRaises(urllib.error.HTTPError) as exc: self.request('/api/reviews', body)
        self.assertEqual(exc.exception.code, 409)
        export = create_export(self.app.catalogue, self.app.store)
        with (Path(export['path'])/'delivery-packages.csv').open(encoding='utf-8-sig') as stream: rows = list(csv.DictReader(stream))
        self.assertEqual(rows[0]['product_id'], 'A'); self.assertEqual(rows[0]['weight_kg'], '2')

    def test_unknown_product_and_invalid_packages_are_rejected(self):
        for path, body, status in [('/api/delivery?product_id=B', None, 404),
                                   ('/api/reviews', {'kind': 'delivery', 'product_id': 'B', 'version': 0, 'data': package()}, 400),
                                   ('/api/delivery/quote', {'data': package(weight_kg=0)}, 400)]:
            with self.assertRaises(urllib.error.HTTPError) as exc: self.request(path, body)
            self.assertEqual(exc.exception.code, status)

    def test_refresh_requires_local_csrf_token(self):
        with self.assertRaises(urllib.error.HTTPError) as exc: self.request('/api/delivery/refresh', {}, token=False)
        self.assertEqual(exc.exception.code, 403)

    def test_slow_remote_refresh_does_not_hold_catalogue_lock(self):
        started, finish = threading.Event(), threading.Event()
        def fetch(): started.set(); finish.wait(3); return PAGE
        self.app.tariffs.fetch = fetch
        self.app.refresh_source = lambda: (_ for _ in ()).throw(AssertionError('Unneeded catalogue refresh'))
        worker = threading.Thread(target=lambda: self.request('/api/delivery/refresh', {})); worker.start()
        try:
            self.assertTrue(started.wait(1))
            acquired = self.app.catalogue_lock.acquire(timeout=.2)
            self.assertTrue(acquired)
            if acquired: self.app.catalogue_lock.release()
            self.assertEqual(self.request('/api/health')['status'], 'ok')
            self.assertEqual(self.request('/api/delivery/quote', {'data': package()})['total_pence'], 375)
        finally:
            finish.set(); worker.join(3)


if __name__ == '__main__':
    unittest.main()
