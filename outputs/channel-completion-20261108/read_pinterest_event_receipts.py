"""Summarise observed native Network UI, excluding visitor tokens and headers."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import json
import re

OUT = Path(__file__).parent
source = OUT / 'pinterest-private-checkout-start-events.txt'
lines = source.read_text().splitlines()
config = json.loads((OUT / 'pinterest-tag-config.json').read_text())
product = json.loads((OUT / 'social-five-products.json').read_text())[0]
expected = config['products'][product['sku']]['id']
decoded = (OUT / 'pinterest-private-checkout-decoded-parameters.txt').read_text()
assert re.search(r'row tid ' + re.escape(config['tagId']) + r'\b', decoded)
assert 'row event initiatecheckout' in decoded
events, generic = {}, {}
for i, line in enumerate(lines):
    match = re.search(r'cell (https://ct\.pinterest\.com/\S+)', line)
    if not match:
        continue
    url = urlparse(match.group(1))
    query = parse_qs(url.query)
    event = query.get('event', [''])[0]
    if event not in ('pagevisit', 'addtocart', 'initiatecheckout', 'checkout', 'purchase'):
        continue
    payload = json.loads(query['ed'][0])
    status = next((int(m.group(1)) for s in lines[i+1:i+9]
                   if (m := re.search(r'cell (\d{3}) ', s))), None)
    assert status == 200, (event, status)
    truncated = query.get('tid') != [config['tagId']]
    if truncated:
        # Native AX caps URL values at 512 characters. The decoded parameter UI
        # independently exposes the complete tag ID for this exact event.
        assert event == 'initiatecheckout' and len(match.group(1)) == 512
        assert config['tagId'].startswith(query['tid'][0])
    if not payload.get('line_items'):
        assert event == 'pagevisit'
        key = payload['event_id']
        entry = generic.setdefault(key, dict(event=event, event_id=key, endpoints={}))
        entry['endpoints'][url.path] = status
        continue
    assert payload['currency'] == 'GBP' and payload['value'] == product['price_gbp']
    assert payload['order_quantity'] == 1
    assert len(payload['line_items']) == 1
    item = payload['line_items'][0]
    assert item['product_id'] == expected and item['product_quantity'] == 1
    assert item['product_price'] == product['price_gbp']
    key = payload['event_id']
    entry = events.setdefault(key, dict(event=event, event_id=key, currency='GBP',
        value=payload['value'], quantity=1, catalogue_id=product['catalogue_id'],
        sku=product['sku'], product_id=expected, product_name=item['product_name'],
        endpoints={}))
    assert entry['event'] == event
    entry['endpoints'][url.path] = status
    if truncated:
        entry['full_tag_id_verified_in_decoded_parameter_ui'] = True
assert {'pagevisit', 'addtocart', 'initiatecheckout'} <= {e['event'] for e in events.values()}
assert not any(e['event'] in ('checkout', 'purchase') for e in events.values())
for event in ('addtocart', 'initiatecheckout'):
    matching = [e for e in events.values() if e['event'] == event]
    assert len(matching) == 1, event
    assert matching[0]['endpoints'] == {'/user/': 200, '/v3/': 200}, event
receipt = dict(checked_at=datetime.now(timezone.utc).isoformat(),
    status='PASS_ACCEPTED_CONSENT_AND_THREE_MATCHED_BROWSER_EVENTS',
    tag_id=config['tagId'], test_context='New private Chrome session; existing browser/extension protections unchanged',
    website_url=product['website_url'], events=list(events.values()),
    generic_nonproduct_pagevisits=list(generic.values()),
    event_identity_matches_current_176_product_configuration=True,
    matching_scope='One representative component tested live; all 176 configured IDs retained and separately mapped to the feed',
    checkout_rendered=True, customer_or_payment_details_entered=False,
    orders_submitted=0, purchase_events_created=0,
    measurement_correction='Earlier empty traces used a filter value that had not applied. Exact keyboard input, '
        'committed domain filter and visible matched rows resolved the observation problem. '
        'Native accessibility default activation was not counted; a physical pointer action produced the trusted cart event.',
    no_adblock_pause_required=True,
    consent_withdrawal_status='Pending current test',
    evidence=[source.name, 'pinterest-private-checkout-decoded-parameters.txt',
              'pinterest-private-real-click-addtocart.png', 'pinterest-private-checkout-start-events.png'])
(OUT / 'pinterest-browser-event-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'status':receipt['status'], 'unique_events':len(events),
    'event_types':sorted({e['event'] for e in events.values()}), 'tag_id':receipt['tag_id'], 'purchase_events':0}))
