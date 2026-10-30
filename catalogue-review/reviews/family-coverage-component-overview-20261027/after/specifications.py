"""Read-only overview of the same listing values used by the review export."""
from datetime import datetime, timezone
import hashlib
import json

from presentation import listing_value


def specification_overview(catalogue, reviews):
    lookup = {(r['kind'], r['product_id'], r['item_id']): r for r in reviews
              if r['kind'] in ('field', 'product') and r['product_id'] in catalogue.products}
    products = []
    for pid, product in catalogue.products.items():
        fields = []
        for field in product['fields']:
            record = lookup.get(('field', pid, field['key']), {})
            choice = record.get('data', {})
            fields.append({**field, 'source_value': field['value'], 'value': listing_value(field, choice),
                           'decision': choice.get('decision', 'pending'), 'version': record.get('version', 0),
                           'certainty': choice.get('certainty', 'retain'), 'evidence': choice.get('evidence', ''),
                           'notes': choice.get('notes', ''), 'updated_at': record.get('updated_at', '')})
        specs = [f for f in fields if f['section'] != 'Listing copy']
        name = next((f['value'] for f in fields if f['key'] == 'Name'), None) or product['name']
        review = lookup.get(('product', pid, ''), {}).get('data', {})
        products.append({'id': pid, 'component_id': product.get('component_id', ''),
                         'name': name.replace('\u2014', '-'), 'original_name': product['name'],
                         'family': product['family'], 'folder_url': product.get('folder_url', ''),
                         'fields': specs, 'listing_fields': [f for f in fields if f['section'] == 'Listing copy'],
                         'listing_decision': review.get('decision', 'pending'),
                         'review_status': review.get('status', 'unreviewed'), 'notes': review.get('notes', ''),
                         'missing_count': sum(f['value'] is not None and not str(f['value']).strip() for f in specs),
                         'omitted_count': sum(f['value'] is None for f in specs)})
    products.sort(key=lambda p: (p['family'].casefold(), p['name'].casefold(), p['id']))
    for number, product in enumerate(products, 1):
        product['number'] = number
    result = {'products': products, 'families': sorted({p['family'] for p in products}),
              'source_hash': catalogue.source['register_sha256'],
              'totals': {'products': len(products), 'fields': sum(len(p['fields']) for p in products),
                         'missing': sum(p['missing_count'] for p in products),
                         'omitted': sum(p['omitted_count'] for p in products)}}
    result['revision'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    return result
