"""Bad catalogue prose must not silently become a different sculpture's size."""
from copy import deepcopy
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from costing import DEFAULTS, calculate, dimensions, product_cost
from us_delivery import upper_dimensions, upper_weight


class MeasurementTextTests(unittest.TestCase):
    def test_sale_quantity_and_later_shape_do_not_change_panel_dimensions(self):
        text = 'Set of 2 panels: 35 x 20 x 6 cm; arrangement 70 cm square'
        self.assertEqual(dimensions(text), (35, 20, 6, 1))
        self.assertEqual(upper_dimensions(text), [35, 20, 6])

    def test_later_diameter_does_not_turn_a_rectangular_panel_into_a_circle(self):
        self.assertEqual(dimensions('35 x 20 x 6 cm; rear fixing 2 cm diameter'), (35, 20, 6, 1))
        self.assertEqual(upper_dimensions('35 x 20 x 6 cm; rear fixing 2 cm diameter'), [35, 20, 6])

    def test_small_decimals_and_reversed_ranges_use_their_full_values(self):
        self.assertEqual(dimensions('35 x 20 x .5 cm'), (35, 20, .5, 1))
        self.assertEqual(upper_dimensions('60–45 cm square; 18–10 cm deep'), [60, 60, 18])
        self.assertEqual(upper_weight('5–3 kg'), 5)
        self.assertEqual(upper_weight('.5 kg'), .5)

    def test_negative_and_unsupported_units_need_correction(self):
        for text in ('-35 x 20 x 6 cm', '35 x 20 x -6 cm', '35 x 20 x 6 mm',
                     '35 x 20 x 6 inches', '35 cm x 20 cm x 6 mm'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                dimensions(text)
        for text in ('-5 kg', '0 kg', '5–-3 kg'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                upper_weight(text)

    def test_shapes_and_labels_keep_individual_scope(self):
        self.assertEqual(dimensions('Set of 2: 50 cm diameter x 2.5 cm deep')[:3], (50, 50, 2.5))
        self.assertEqual(dimensions('6 cm deep × 40 cm wide × 45 cm high'), (40, 45, 6, 1))

    def test_compact_ascii_multiplication_keeps_all_three_quantities(self):
        for text in ('35x20x6cm', '35 x20 x6 cm', '35cmx20cmx6cm', '35X20X.5cm'):
            with self.subTest(text=text):
                depth = .5 if '.5' in text else 6
                self.assertEqual(dimensions(text), (35, 20, depth, 1))

    def test_dimension_labels_before_a_later_chain_are_not_discarded(self):
        for text in ('6 cm deep; 40 cm wide x 45 cm high',
                     'Set of 2 panels: 6 cm deep; 40 cm wide x 45 cm high',
                     'Depth: 6 cm; width: 40 cm; height: 45 cm',
                     '6 cm deep; 40 cm wide x 45 cm long'):
            with self.subTest(text=text):
                self.assertEqual(dimensions(text), (40, 45, 6, 1))
                self.assertEqual(upper_dimensions(text), [45, 40, 6])

    def test_prefix_shape_labels_preserve_circle_and_square_measurements(self):
        self.assertEqual(dimensions('Diameter: 50 cm; depth: 2.5 cm'), (50, 50, 2.5, math.pi / 4))
        self.assertEqual(dimensions('Square 30 cm; depth 5 cm'), (30, 30, 5, 1))
        self.assertEqual(upper_dimensions('Diameter: 50 cm; depth: 2.5 cm'), [50, 50, 2.5])

    def test_high_relief_sale_count_does_not_become_a_dimension_label(self):
        self.assertEqual(dimensions('Set of 2 high relief panels: 35x20x6 cm'), (35, 20, 6, 1))
        self.assertEqual(dimensions('Set of 2 square panels: 35x20x6 cm'), (35, 20, 6, 1))

    def test_spelled_out_units_are_never_silently_treated_as_centimetres(self):
        for text in ('350x200x60 millimetres', '350x200x60 millimeters',
                     '35x20x6 feet', '35x20x6 foot', '35x20x6 ft'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                dimensions(text)
        self.assertEqual(dimensions('35x20x6 centimetres'), (35, 20, 6, 1))

    def test_wrong_units_withhold_cost_instead_of_pricing_a_larger_object(self):
        product = {'id': 'A', 'name': 'Panel', 'family': 'Panels',
                   'fields': [{'key': 'Dimensions / depth', 'value': '350 x 200 x 60 mm'}]}
        self.assertEqual(product_cost(product, [])['status'], 'needs_inputs')

    def test_valid_extreme_input_bounds_do_not_crash_decimal_rounding(self):
        config = deepcopy(DEFAULTS)
        for key in ('reference_width_cm', 'reference_height_cm', 'reference_depth_cm'):
            config[key] = .01
        config['materials']['gfrc']['rate'] = 1000000
        inputs = {'width_cm': 10000, 'height_cm': 10000, 'depth_cm': 10000,
                  'shape_factor': 100, 'casting_factor': 100, 'material': 'gfrc',
                  'finishes': [{'id': 'white', 'coverage': 1}], 'fixing_count': 0,
                  'labour_hours_override': 0, 'other_cost': 0, 'notes': ''}
        self.assertTrue(math.isfinite(calculate(inputs, config)['total_cost']))
