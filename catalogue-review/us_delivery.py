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


@lru_cache(maxsize=1)
def tariff():
    return json.loads((Path(__file__).parent/'tariffs/us-ups-2026.json').read_text())


def money(value):
    return float(Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def upper_weight(text):
    """Keep upper endpoints, including a later parenthesised weight range."""
    matches = re.findall(r'(\d+(?:\.\d+)?)(?:\s*[–−-]\s*(\d+(?:\.\d+)?))?\s*kg\b', str(text), re.I)
    if not matches:
        raise ValueError('A catalogue weight in kilograms is needed.')
    result = max(float(b or a) for a, b in matches)
    if not positive(result):
        raise ValueError('The catalogue weight must be positive.')
    return result


def upper_dimensions(text):
    # Same supported dimension syntax as costing, but use upper range endpoints
    # for shipping rather than the manufacturing midpoint.
    text = str(text)
    if re.search(r'\b(mm|inches|inch|in\.)\b', text, re.I) and 'cm' not in text:
        raise ValueError('Catalogue dimensions in centimetres are needed.')
    # A semicolon commonly separates face dimensions from depth. Keep it;
    # stop after the first complete triplet so later arrangement/framework
    # dimensions cannot replace the dimensions of the sold component.
    nums = [float(b or a) for a, b in re.findall(r'(\d+(?:\.\d+)?)(?:\s*[–−-]\s*(\d+(?:\.\d+)?))?', text)]
    if ('diameter' in text.lower() or 'square' in text.lower()) and len(nums) >= 2:
        nums = [nums[0], nums[0], nums[1]]
    if len(nums) < 3 or any(not positive(x) for x in nums[:3]):
        raise ValueError('Three catalogue dimensions are needed.')
    return sorted(nums[:3], reverse=True)


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
    values = fields or {f['key']:f['value'] for f in product['fields']+product.get('listing_fields',[])}
    basis = {'dimensions':values.get('Dimensions / depth',''),'weight':values.get('Weight','')}
    base = {'product_id':product['id'],'source':basis,
            'source_fingerprint':hashlib.sha256(json.dumps(basis,sort_keys=True).encode()).hexdigest(),
            'status':'available','currency':'GBP'}
    try:
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
    except (ValueError, TypeError, KeyError) as exc:
        return {**base,'status':'needs_measurements','message':str(exc),'quotes':[]}
