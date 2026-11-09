"""Boundary and provenance checks for indicative US shipping, without API calls."""
import itertools
import json
import sys
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from us_delivery import upper_dimensions, upper_weight, parcel_estimate, product_estimate, tariff, TariffUnavailable


# Synthetic calculation contract, deliberately independent of private carrier
# snapshots. These values are test inputs, not published or bookable rates.
SAMPLE_TARIFF = {
    'carrier': 'Test carrier', 'service': 'Test parcel', 'origin_postcode': 'TEST',
    'verified_at': '2026-11-01', 'rate_basis': 'Synthetic test fixture',
    'sources': {'calculator': 'https://example.com/calculator',
                'rates': 'https://example.com/rates', 'fuel': 'https://example.com/fuel'},
    'destinations': [{'id': 'new_york', 'name': 'Test destination', 'postcode': 'TEST'}],
    'rates': [{'max_kg': 70, 'new_york_gbp': 100}],
    'fuel_history': [{'effective_date': '2026-10-26', 'percent': 54.5},
                     {'effective_date': '2026-11-02', 'percent': 55.5}],
    'surcharges': {'surge_start': '2026-10-01', 'surge_end': '2026-12-31',
                   'residential_gbp': 5, 'additional_handling_gbp': 12.10,
                   'large_package_gbp': 56.55, 'demand_large_gbp': 5,
                   'demand_handling_gbp': 5, 'surge_per_kg_gbp': .1,
                   'us_processing_gbp': 2, 'future_collection_gbp': 3},
}

class USDeliveryTests(unittest.TestCase):
    def setUp(self):
        mock = patch('us_delivery.tariff', return_value=deepcopy(SAMPLE_TARIFF))
        mock.start()
        self.addCleanup(mock.stop)

    def test_depth_after_semicolon_and_ranges(self):
        self.assertEqual(upper_dimensions('100 × 22 cm; approximately 6 cm panel depth'), [100,22,6])
        self.assertEqual(upper_dimensions('25 × 25 cm; approximately 5–7 cm deep'), [25,25,7])
        self.assertEqual(upper_dimensions('45–60 cm square; 10–18 cm overall height'), [60,60,18])
        self.assertEqual(upper_dimensions('50 cm diameter × 2.5 cm deep'), [50,50,2.5])
        self.assertEqual(upper_dimensions('Panel 200 × 100 × 5 cm; framework 186 × 86 × 6.5 cm; 15 mm'), [200,100,5])
        self.assertEqual(upper_weight('Approximately 4 kg (range 3–5 kg)'), 5)

    def test_weight_and_carrier_limits(self):
        q=lambda d,w:parcel_estimate(d,w,'new_york',date(2026,11,1))
        self.assertEqual(q([70,40,20],70)['status'],'planning_estimate')
        self.assertEqual(q([70,40,20],70.01)['status'],'freight_quote_required')
        self.assertNotIn('estimate_gbp',q([275,20,10],10))
        self.assertNotIn('estimate_gbp',q([200,70,40],10))
        self.assertEqual(q([101,50,20],10)['charges']['additional_handling_gbp'],12.10)
        large=q([150,60,20],10)
        self.assertEqual(large['charges']['additional_handling_gbp'],0)
        self.assertEqual(large['charges']['large_package_gbp'],56.55)
        self.assertGreaterEqual(large['billable_kg'],40)

    def test_dimensions_round_up_and_orientation_is_irrelevant(self):
        q=lambda d:parcel_estimate(d,9,'new_york',date(2026,11,1))
        reference=q([60,40,16])
        self.assertEqual(reference['billable_kg'],9)
        self.assertAlmostEqual(reference['estimate_gbp'],168.62)
        for d in itertools.permutations([60,40,16]):self.assertEqual(q(d),reference)
        self.assertEqual(q([60.01,40,16])['packed_cm'],[61,40,16])
        self.assertFalse(reference['checkout_rate'])
        self.assertTrue(reference['requires_booking_quote'])

    def test_invalid_inputs_and_unknown_destination(self):
        for bad in [0,-1,True,float('inf'),float('nan')]:
            with self.assertRaises(ValueError):parcel_estimate([60,40,16],bad,'new_york')
        with self.assertRaises(ValueError):parcel_estimate([60,40,16],9,'unknown')

    def test_fuel_date_and_staleness(self):
        q=lambda day:parcel_estimate([60,40,16],9,'new_york',day)
        self.assertEqual(q(date(2026,11,1))['fuel_percent'],54.5)
        self.assertEqual(q(date(2026,11,2))['fuel_percent'],55.5)
        self.assertTrue(q(date(2026,11,9))['stale'])
        self.assertFalse(q(date(2026,11,8))['stale'])

    def test_measured_package_wins_even_when_artwork_specs_missing(self):
        p={'id':'example','fields':[]}
        self.assertEqual(product_estimate(p)['status'],'needs_measurements')
        q=product_estimate(p,measured={'length_cm':60,'width_cm':40,'depth_cm':16,'weight_kg':9})
        self.assertEqual(q['status'],'available');self.assertFalse(q['package_estimated'])
        self.assertIsNone(q['packing_allowance_kg'])

    def test_explicit_empty_fields_do_not_restore_unreviewed_source_measurements(self):
        product = {'id': 'A', 'fields': [{'key': 'Weight', 'value': '6 kg'},
                   {'key': 'Dimensions / depth', 'value': '50 x 30 x 6 cm'}]}
        self.assertEqual(product_estimate(product, fields={})['status'], 'needs_measurements')

    def test_invalid_saved_package_is_not_replaced_with_an_artwork_estimate(self):
        product = {'id': 'A', 'fields': [{'key': 'Weight', 'value': '6 kg'},
                   {'key': 'Dimensions / depth', 'value': '50 x 30 x 6 cm'}]}
        for measured in ({'weight_kg': -1}, ['old package'],
                         {'length_cm': 60, 'width_cm': 40, 'depth_cm': 16, 'weight_kg': 0}):
            with self.subTest(measured=measured):
                result = product_estimate(product, measured=measured)
                self.assertEqual(result['status'], 'needs_measurements')
                self.assertEqual(result['quotes'], [])


class UnavailableTariffTests(unittest.TestCase):
    def setUp(self):
        tariff.cache_clear()
        self.addCleanup(tariff.cache_clear)

    def test_missing_tariff_keeps_specifications_available_without_an_estimate(self):
        with patch('us_delivery.Path.read_text', side_effect=FileNotFoundError('missing')):
            result = product_estimate({'id': 'A', 'fields': []}, measured={
                'length_cm': 60, 'width_cm': 40, 'depth_cm': 16, 'weight_kg': 9})
        self.assertEqual(result['status'], 'rate_unavailable')
        self.assertEqual(result['quotes'], [])
        self.assertIn('Restore the verified saved tariff', result['message'])

    def test_malformed_or_incomplete_tariff_is_not_cached_as_a_working_rate(self):
        for raw in ('broken', '{}', '[]', '{"rates": null}'):
            with self.subTest(raw=raw), patch('us_delivery.Path.read_text', return_value=raw):
                with self.assertRaises(TariffUnavailable):
                    tariff()
        with patch('us_delivery.Path.read_text', return_value=json.dumps(SAMPLE_TARIFF)):
            self.assertEqual(tariff()['carrier'], 'Test carrier')

    def test_unordered_bands_and_negative_surcharges_are_unavailable(self):
        for mutate in (lambda t: t['rates'].append({'max_kg': 1, 'new_york_gbp': 10}),
                       lambda t: t['surcharges'].update(residential_gbp=-1)):
            data = deepcopy(SAMPLE_TARIFF)
            mutate(data)
            with patch('us_delivery.Path.read_text', return_value=json.dumps(data)):
                with self.assertRaises(TariffUnavailable):
                    tariff()

if __name__=='__main__':unittest.main()
