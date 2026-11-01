"""Read-only overview of the same listing values used by the review export."""
from datetime import datetime, timezone
import hashlib
import json

from presentation import listing_value
from costing import product_cost, priced_listing_value, settings as cost_settings
from us_delivery import product_estimate as us_shipping_estimate


def specification_overview(catalogue, reviews, photos=None):
    lookup = {(r['kind'], r['product_id'], r['item_id']): r for r in reviews
              if r['kind'] in ('field', 'product') and r['product_id'] in catalogue.products}
    products = []
    rates = cost_settings(reviews)
    for pid, product in catalogue.products.items():
        cost = product_cost({**product, 'id': pid}, reviews, rates)
        fields = []
        for field in product['fields']:
            record = lookup.get(('field', pid, field['key']), {})
            choice = record.get('data', {})
            fields.append({**field, 'source_value': field['value'], 'value': priced_listing_value(field, choice, cost),
                           'decision': choice.get('decision', 'pending'), 'version': record.get('version', 0),
                           'certainty': choice.get('certainty', 'retain'), 'evidence': choice.get('evidence', ''),
                           'notes': choice.get('notes', ''), 'updated_at': record.get('updated_at', '')})
            if field['key'] == 'Price' and choice.get('decision') != 'exclude' and cost['pricing']['mode'] == 'markup':
                fields[-1].update(decision='calculated', certainty='estimate',
                                  evidence=f"Manufacturing cost plus separate labour, with {cost['pricing']['markup_percent']}% markup; shared rates revision {cost['settings_version']}.")
        specs = [f for f in fields if f['section'] != 'Listing copy']
        name = next((f['value'] for f in fields if f['key'] == 'Name'), None) or product['name']
        retail_name = next((f['value'] for f in fields if f['key'] == 'Retail name'), None) or ''
        review = lookup.get(('product', pid, ''), {}).get('data', {})
        products.append({'id': pid, 'component_id': product.get('component_id', ''),
                         'name': name.replace('\u2014', '-'), 'original_name': product['name'],
                         'retail_name': retail_name.replace('\u2014', '-'),
                         'family': product['family'], 'folder_url': product.get('folder_url', ''),
                         'costing': cost,
                         'fields': specs, 'listing_fields': [f for f in fields if f['section'] == 'Listing copy'],
                         'listing_decision': review.get('decision', 'pending'),
                         'review_status': review.get('status', 'unreviewed'), 'notes': review.get('notes', ''),
                         'missing_count': sum(f['value'] is not None and not str(f['value']).strip() for f in specs),
                         'omitted_count': sum(f['value'] is None for f in specs)})
    products.sort(key=lambda p: (p['family'].casefold(), p['name'].casefold(), p['id']))
    for number, product in enumerate(products, 1):
        product['number'] = number
        packed = next((r.get('data', {}) for r in reviews
                       if r['kind'] == 'delivery' and r['product_id'] == product['id']), {})
        product['us_shipping'] = us_shipping_estimate(product, measured=packed)
        if photos is not None:
            product['photos'] = photos[product['id']]
    result = {'products': products, 'families': sorted({p['family'] for p in products}),
              'source_hash': catalogue.source['register_sha256'],
              'totals': {'products': len(products), 'fields': sum(len(p['fields']) for p in products),
                         'missing': sum(p['missing_count'] for p in products),
                         'omitted': sum(p['omitted_count'] for p in products)}}
    result['revision'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    return result
