"""Conservative unit-price floors that preserve a catalogue net receipt.

Rates are explicit planning inputs. No native platform setting is changed here.
Packing, shipping and product sales taxes are outside the unit-price calculation.
"""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


def decimal(value):
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError('A finite pricing input is required')
    return number


def rounded(value, places=2, up=True):
    return decimal(value).quantize(Decimal(10) ** -places,
                                  rounding=ROUND_CEILING if up else ROUND_FLOOR)


def retention(commission=0, payout=0, fee_tax=0):
    c, p, t = map(decimal, (commission, payout, fee_tax))
    if min(c, p, t) < 0 or t > 1 or c + p >= 1:
        raise ValueError('Invalid fee rate')
    result = 1 - (c + p) * (1 + t)
    if result <= 0:
        raise ValueError('Fees consume all proceeds')
    return result


def proceeds(sale, commission=0, payout=0, fee_tax=0, fixed=0,
             rounding_reserve='.05', places=2):
    s, f, reserve = map(decimal, (sale, fixed, rounding_reserve))
    if min(s, f, reserve) < 0:
        raise ValueError('Negative sale, fee or rounding reserve')
    return rounded(s * retention(commission, payout, fee_tax)
                   - f * (1 + decimal(fee_tax)) - reserve, places, up=False)


def price_floor(target, commission=0, payout=0, fee_tax=0, fixed=0,
                discount=0, rounding_reserve='.05', places=2):
    target, discount, fixed, reserve = map(decimal, (target, discount, fixed, rounding_reserve))
    if target <= 0 or not 0 <= discount < 1 or min(fixed, reserve) < 0:
        raise ValueError('Invalid target, discount or fee input')
    sale = rounded((target + fixed * (1 + decimal(fee_tax)) + reserve)
                   / retention(commission, payout, fee_tax), places)
    asking = rounded(sale / (1 - discount), places)
    discounted = rounded(asking * (1 - discount), places, up=False)
    net = proceeds(discounted, commission, payout, fee_tax, fixed, reserve, places)
    if net < target:
        raise ArithmeticError('Price floor failed to preserve the target')
    return dict(minimum_sale=sale, asking=asking, discounted_sale=discounted, net=net)
