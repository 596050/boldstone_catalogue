"""Transparent US planning estimates; never used as an automatic checkout rate.

Source dimensions remain separate from measured packaging. Tariffs are public
UPS business list rates, not a live booking or a guarantee of artwork coverage.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import math
import re
from measurement_text import dimensions as catalogue_dimensions, NUMBER


class TariffUnavailable(ValueError):
    """The saved rate data cannot support a planning estimate."""


@lru_cache(maxsize=1)
def tariff():
    path = Path(__file__).parent / 'tariffs/us-ups-2026.json'
    try:
        saved = json.loads(path.read_text())
        # Check all fields used by the calculator before caching a snapshot.
        for key in ('carrier', 'service', 'origin_postcode', 'verified_at', 'rate_basis', 'sources'):
            saved[key]
        if not isinstance(saved['sources'], (dict, list)) or not saved['destinations'] or not saved['rates']:
            raise ValueError('Incomplete saved rate table')
        destinations = [d['id'] for d in saved['destinations']]
        previous = 0
        for band in saved['rates']:
            if not positive(band['max_kg']) or band['max_kg'] <= previous:
                raise ValueError('Unordered rate bands')
            previous = band['max_kg']
            for destination in destinations:
                if not positive(band[destination + '_gbp']):
                    raise ValueError('Invalid transport rate')
        for fuel in saved['fuel_history']:
            date.fromisoformat(fuel['effective_date'])
            if type(fuel['percent']) not in (int, float) or not math.isfinite(fuel['percent']) or fuel['percent'] < 0:
                raise ValueError('Invalid fuel rate')
        surcharges = saved['surcharges']
        for key in ('surge_start', 'surge_end'):
            date.fromisoformat(surcharges[key])
        for key in ('residential_gbp', 'additional_handling_gbp', 'large_package_gbp',
                    'demand_large_gbp', 'demand_handling_gbp', 'surge_per_kg_gbp',
                    'us_processing_gbp', 'future_collection_gbp'):
            value = surcharges[key]
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid surcharge')
        return saved
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise TariffUnavailable(
            f'US shipping rates are unavailable. Restore the verified saved tariff at {path} '
            'before calculating an estimate.') from exc


def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def upper_weight(text):
    """Keep upper endpoints, including a later parenthesised weight range."""
    matches = re.findall(r'(?<![\w.])(' + NUMBER + r')(?:\s*[–−-]\s*(' + NUMBER + r'))?\s*kg\b', str(text), re.I)
    if not matches:
        raise ValueError('A catalogue weight in kilograms is needed.')
    endpoints = [float(x) for a, b in matches for x in (a, b or a)]
    if not all(positive(x) for x in endpoints):
        raise ValueError('The catalogue weight must be positive.')
    return max(endpoints)


def upper_dimensions(text):
    return sorted(catalogue_dimensions(text, upper=True)[:3], reverse=True)


def parcel_estimate(dimensions, weight, destination, today=None):
    today = today or datetime.now(timezone.utc).date()
    if len(dimensions) != 3 or not all(positive(x) for x in dimensions) or not positive(weight):
        raise ValueError('Use positive finite packed dimensions and weight.')
    t = tariff()
    dest = next((d for d in t['destinations'] if d['id'] == destination), None)
    if not dest:
        raise ValueError('Unknown example destination.')
    dims = sorted([math.ceil(x) for x in dimensions], reverse=True)
    length, width, depth = dims
    girth = length + 2 * (width + depth)
    dimensional = math.ceil((length*width*depth/5000)*2)/2
    actual = math.ceil(weight*2)/2
    large = girth > 300
    billable = max(actual, dimensional, 40 if large else 0)
    common = {'carrier':t['carrier'], 'service':t['service'], 'currency':'GBP',
              'destination':dest.copy(), 'origin_postcode':t['origin_postcode'],
              'packed_cm':dims, 'packed_kg':weight, 'dimensional_kg':dimensional,
              'billable_kg':billable, 'length_plus_girth_cm':girth,
              'as_of':today.isoformat(), 'tariff_verified_at':t['verified_at'],
              'rate_basis':t['rate_basis'], 'sources':t['sources'].copy(),
              'requires_booking_quote':True, 'checkout_rate':False,
              'exclusions':['Packaging materials or a crate', 'Artwork-specific insurance/compensation',
                            'Import duties, taxes and customs brokerage', 'VAT where applicable',
                            'Remote-area or address-specific charges', 'Paper commercial invoice surcharge; assumes paperless documents'],
              'assumptions':['One corrugated-cardboard parcel', 'Residential destination',
                             'Future-day online collection', 'No negotiated account discount']}
    if weight > 70 or length > 274 or girth > 400:
        return {**common,'status':'freight_quote_required',
                'message':'The estimated package exceeds UPS parcel limits. Obtain an artwork/crate freight quote; no parcel charge is assigned.'}
    band = next((r for r in t['rates'] if billable <= r['max_kg']), None)
    if band is None:
        return {**common,'status':'carrier_quote_required','message':'Billable weight is outside this saved parcel table.'}
    fuels = [f for f in t['fuel_history'] if date.fromisoformat(f['effective_date']) <= today]
    if not fuels:
        return {**common,'status':'rate_unavailable','message':'No verified fuel rate covers this estimate date.'}
    fuel = max(fuels, key=lambda f:f['effective_date'])
    valid_until = date.fromisoformat(fuel['effective_date']) + timedelta(days=6)
    s = t['surcharges']
    peak = date.fromisoformat(s['surge_start']) <= today <= date.fromisoformat(s['surge_end'])
    handling = not large and (length > 100 or width > 76 or weight > 25)
    charges = {
        'transport_gbp':band[destination+'_gbp'],
        'residential_gbp':s['residential_gbp'],
        'additional_handling_gbp':s['additional_handling_gbp'] if handling else 0,
        'large_package_gbp':s['large_package_gbp'] if large else 0,
        'demand_gbp':s['demand_large_gbp'] if large and peak else s['demand_handling_gbp'] if handling and peak else 0,
        'surge_gbp':money(billable*s['surge_per_kg_gbp']) if peak else 0,
    }
    fuel_base = sum(Decimal(str(v)) for v in charges.values())
    charges['fuel_gbp'] = money(fuel_base*Decimal(str(fuel['percent']))/100)
    charges['us_processing_gbp'] = s['us_processing_gbp']
    charges['collection_gbp'] = s['future_collection_gbp']
    total = money(sum(Decimal(str(v)) for v in charges.values()))
    return {**common,'status':'planning_estimate','charges':charges,'estimate_gbp':total,
            'table_band_kg':band['max_kg'],'fuel_percent':fuel['percent'],
            'fuel_effective_date':fuel['effective_date'],'valid_until':valid_until.isoformat(),
            'stale':today > valid_until,
            'message':'Indicative carrier list-rate budget. Requote the measured package and actual delivery address before charging a customer.'}


def product_estimate(product, fields=None, measured=None, today=None):
    values = fields if fields is not None else {f['key']:f['value'] for f in product['fields']+product.get('listing_fields',[])}
    basis = {'dimensions':values.get('Dimensions / depth',''),'weight':values.get('Weight','')}
    base = {'product_id':product['id'],'source':basis,
            'source_fingerprint':hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest(),
            'status':'available','currency':'GBP'}
    try:
        if measured and (not isinstance(measured, dict) or
                         not all(positive(measured.get(k)) for k in ('length_cm','width_cm','depth_cm','weight_kg'))):
            raise ValueError('Saved package measurements are incomplete or invalid; correct them before estimating delivery.')
        estimated = not (measured and all(positive(measured.get(k)) for k in ('length_cm','width_cm','depth_cm','weight_kg')))
        upper, art_dims, allowance = None, None, None
        if not estimated:
            dims = [measured[k] for k in ('length_cm','width_cm','depth_cm')]
            weight = measured['weight_kg']
        else:
            upper = upper_weight(basis['weight'])
            art_dims = upper_dimensions(basis['dimensions'])
            allowance = money(max(1, upper*.1))
            dims = [math.ceil(n+10) for n in art_dims]
            weight = money(upper+allowance)
        return {**base,'package_estimated':estimated,'artwork_upper_kg':upper,
                'packing_allowance_kg':allowance if estimated else None,
                'artwork_upper_cm':art_dims,'packed_cm':sorted(dims,reverse=True),'packed_kg':weight,
                'packing_basis':('Catalogue upper weight plus max(10%, 1 kg); provisional 5 cm protection on each side. Box dimensions are estimates, not measured packaging.' if estimated else 'Saved packed measurements from the delivery checker.'),
                'quotes':[parcel_estimate(dims,weight,d['id'],today=today) for d in tariff()['destinations']]}
    except TariffUnavailable as exc:
        return {**base,'status':'rate_unavailable','message':str(exc),'quotes':[]}
    except (ValueError, TypeError, KeyError) as exc:
        return {**base,'status':'needs_measurements','message':str(exc),'quotes':[]}
