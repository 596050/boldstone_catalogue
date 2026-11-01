"""Boundary and provenance checks for indicative US shipping, without API calls."""
import itertools
import sys
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from us_delivery import upper_dimensions, upper_weight, parcel_estimate, product_estimate

class USDeliveryTests(unittest.TestCase):
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
        self.assertAlmostEqual(reference['estimate_gbp'],264.58)
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

if __name__=='__main__':unittest.main()
