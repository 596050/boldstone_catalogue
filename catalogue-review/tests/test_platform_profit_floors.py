import random
import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_pricing import price_floor, proceeds


class ProfitFloorTests(unittest.TestCase):
    def test_preserves_full_receipt_not_just_break_even(self):
        q = price_floor(100, '.25', discount='.5')
        self.assertGreaterEqual(q['net'], Decimal('100'))
        self.assertEqual(q['minimum_sale'], Decimal('133.40'))

    def test_fees_tax_and_discount_combine(self):
        q = price_floor(100, '.25', '.03', '.2', fixed=2, discount='.5')
        self.assertGreaterEqual(q['net'], Decimal('100'))
        self.assertGreater(q['asking'], Decimal('300'))

    def test_no_fees_still_preserves_rounding_reserve(self):
        q = price_floor('27.44', discount='.5')
        self.assertGreaterEqual(q['net'], Decimal('27.44'))

    def test_auction_whole_currency_reserve(self):
        q = price_floor(135, '.2', fee_tax='.2', discount='.6', rounding_reserve=1, places=0)
        self.assertGreaterEqual(proceeds(q['discounted_sale'], '.2', fee_tax='.2', rounding_reserve=1, places=0), 135)

    def test_trade_discount_after_markdown(self):
        effective = 1 - Decimal('.6') * Decimal('.88')
        self.assertEqual(effective, Decimal('.472'))
        q = price_floor(100, '.4', fee_tax='.2', discount=effective)
        self.assertGreaterEqual(q['net'], 100)

    def test_faire_promotions_are_additional_to_wholesale_margin(self):
        q = price_floor(100, '.25', '.03', '.2', discount='.2')
        retail_reference = q['asking'] * 2
        promoted_wholesale = retail_reference * Decimal('.5') * Decimal('.8')
        self.assertGreaterEqual(proceeds(promoted_wholesale, '.25', '.03', '.2'), 100)

    def test_invalid_inputs_do_not_produce_prices(self):
        for kwargs in [dict(target=0), dict(target=100, discount=1), dict(target=100, commission='.9', fee_tax='.2'),
                       dict(target='NaN'), dict(target=100, payout='-.01'),dict(target=100,fixed=-1)]:
            with self.assertRaises(ValueError):
                price_floor(**kwargs)

    def test_randomized_rounding_and_fee_boundaries(self):
        rng = random.Random(20261104)
        for _ in range(1000):
            target = Decimal(rng.randrange(1, 250000)) / 100
            commission = Decimal(rng.randrange(0, 51)) / 100
            payout = Decimal(rng.randrange(0, 6)) / 100
            tax = Decimal(rng.choice([0, 20])) / 100
            discount = Decimal(rng.randrange(0, 91)) / 100
            fixed = Decimal(rng.randrange(0, 1000)) / 100
            q = price_floor(target, commission, payout, tax, fixed, discount)
            self.assertGreaterEqual(q['net'], target)
            # Independently charge each percentage fee, rounded up to pennies.
            sale = q['discounted_sale']
            up = lambda x: x.quantize(Decimal('.01'), rounding='ROUND_CEILING')
            fees = up(sale*commission) + up(sale*payout) + up(fixed)
            actual = sale - fees - up(fees*tax)
            self.assertGreaterEqual(actual, target)


if __name__ == '__main__':
    unittest.main()
