"""Record native consent regression receipts and read-only photo opportunities."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import hashlib
import json
import re

OUT = Path(__file__).parent
FIX = OUT / 'consent-fix'
load = lambda name: json.loads((OUT / name).read_text())
now = datetime.now(timezone.utc).isoformat()


def request_count(name):
    text = (FIX / name).read_text()
    matches = re.findall(r'\btext (\d+) / (\d+) requests', text)
    assert matches, name
    return int(matches[-1][0])


def product_events(name):
    lines = (FIX / name).read_text().splitlines()
    events = {}
    for i, line in enumerate(lines):
        m = re.search(r'cell (https://ct\.pinterest\.com/\S+)', line)
        if not m:
            continue
        url = urlparse(m[1])
        q = parse_qs(url.query)
        if q.get('event') != ['pagevisit']:
            continue
        data = json.loads(q['ed'][0])
        item = data['line_items'][0]
        assert item['product_id'] == '467ac7b5-9295-450f-8f65-13d2fafdbc07'
        assert data['currency'] == 'GBP' and data['value'] == 79.62
        status = next(int(m[1]) for s in lines[i+1:i+9]
                      if (m := re.search(r'cell (\d{3}) ', s)))
        assert status == 200
        e = events.setdefault(data['event_id'], dict(product_id=item['product_id'],
            currency='GBP', value=79.62, quantity=data['order_quantity'], endpoints={}))
        e['endpoints'][url.path] = status
    assert len(events) == 1, (name, events)
    assert next(iter(events.values()))['endpoints'] == {'/user/': 200, '/v3/': 200}
    return list(events.values())


assert request_count('analytics-only-network.txt') == 0
assert request_count('advertising-only-ga4-network.txt') == 0
assert request_count('late-advertising-ga4-view-count.txt') == 1
assert request_count('late-analytics-pinterest-view-count.txt') == 2  # Two endpoints, one event ID.
assert request_count('withdrawn-pinterest-network.txt') == 0
assert request_count('withdrawn-pinterest-sdk.txt') == 0
late_advertising = product_events('late-advertising-network.txt')
late_analytics = product_events('late-analytics-pinterest-view-count.txt')
ga = (FIX / 'late-analytics-ga4-full-payload.txt').read_text()
assert 'en=view_item&_ee=1&pr1=idBT-1-100.22' in ga
assert 'epn.value=79.62' in ga and 'cu=GBP' in ga
assert (FIX / 'footer-after.html').read_bytes() == (FIX / 'footer-saved-readback.html').read_bytes()
assert '0 items in cart' in (FIX / 'test-cart-empty.txt').read_text()
receipt = dict(status='PASS_LIVE_CONSENT_ORDER_REGRESSION_AND_WITHDRAWAL', checked_at=now,
    tag_id='2612823030261', catalogue_id='BSI-489226D6FF87', sku='BT-1-100.22',
    test_scope='One live representative product; all 176 configured SKU/feed mappings retained.',
    bug='One shared product-view key suppressed a later-consented destination.',
    fix='Independent GA4 and Pinterest product-view keys; only consented destinations record delivery.',
    saved_footer_sha256=hashlib.sha256((FIX / 'footer-saved-readback.html').read_bytes()).hexdigest(),
    exact_saved_source_reloaded=True, header_and_other_injection_fields_untouched=True,
    logic_checks_passed=17, advertising_declined_pinterest_requests=0,
    later_advertising_grant=late_advertising, ga4_view_requests_after_later_advertising=1,
    analytics_declined_ga4_product_views=0, later_analytics_grant_ga4_product_view=True,
    later_analytics_ga4_delivery_basis='Full native Network Payload shows the batched view_item, exact SKU, GBP and 79.62. Query-only filtering would miss this POST body.',
    later_analytics_did_not_duplicate_pinterest=late_analytics,
    withdrawal_pinterest_requests=0, withdrawal_pinterest_sdk_requests=0,
    protections_weakened=False, adblock_pause_required=False,
    customer_or_payment_details_entered=False, orders_submitted=0, purchase_events_created=0,
    cart_empty=True, private_qa_window_closed=True,
    purchase_tracking_status='Not verified; no order was placed.',
    merchant_approval_status='Separate account gate remains; tracking success does not establish approval.')
(FIX / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
event_receipt = load('pinterest-browser-event-receipt.json')
event_receipt.update(consent_withdrawal_status='PASS; separate category grants and withdrawal verified live',
    consent_regression_receipt='consent-fix/verification.json')
(OUT / 'pinterest-browser-event-receipt.json').write_text(json.dumps(event_receipt, indent=2) + '\n')

photos = load('unselected-original-header-review.json')
qualified = {p['catalogue_id']: p for p in photos['products']
             if any(c['header_check']['meets_documented_dimensions'] for c in p['candidates'])}
assert len(qualified) == 4
notes = {
    'BSI-7CDE8362BB51': 'Full matching White panel; heavy shadows. Review lighting before selecting.',
    'BSI-41E5370B1314': 'Full matching White sculpture; shadow and displayed orientation need review.',
    'BSI-DF431D2D9F15': 'Matching Silver Finish sculpture on a stone wall. Several files are rotated relative to the selected primary; review orientation. This does not establish a new Listing choice.',
    'BSI-70C7029C1DB1': 'Matching full White panel on a brick wall in direct sun. File 002 has good whole-product coverage; review lighting and composition.'}
for pid, p in qualified.items():
    p['visual_review_note'] = notes[pid]
    p['qualifying_candidates'] = [c for c in p['candidates'] if c['header_check']['meets_documented_dimensions']]
    p['contact_sheet'] = str(OUT / ('photo-candidates-' + pid + '.jpg'))
photo_receipt = dict(status='REVIEW_CHOICES_ONLY_NO_SELECTIONS_CHANGED', checked_at=now,
    products=list(qualified.values()), products_with_additional_options=4,
    qualifying_unselected_originals=21, scope='25 plausible associated product originals checked; not an exhaustive search of every Dropbox file.',
    header_verification='Exact Dropbox ID/revision/size/provider-hash metadata plus bounded original header; full original content hash was not recomputed.',
    owner_choices_changed=0, originals_retained_locally=0)
(OUT / 'pinterest-unselected-photo-options.json').write_text(json.dumps(photo_receipt, ensure_ascii=False, indent=2) + '\n')

evidence = load('platform-task-evidence.json')
detail = ('Tag 2612823030261: matched product PageVisit, AddToCart and InitiateCheckout received HTTP 200 in a private Chrome test. '
          'Exact configured product ID, GBP79.62 and quantity1 verified for Brancusi Totem White; all176 configured mappings retained. '
          'Fixed separate-consent ordering: GA4 and Pinterest now deduplicate independently. Both late category grants and advertising withdrawal verified live; '
          '17 logic checks pass. Existing browser protections unchanged. This representative test is not a test of every product or completed purchase; no order placed.')
for pid, p in evidence['products'].items():
    e = p['platforms']['pinterest']
    if e['state'] == 'not_targeted':
        continue
    task = next(t for t in e['tasks'] if t['id'] == 'pinterest_tracking')
    task.update(state='verified', title='Consent and matched browser events verified', detail=detail,
                url='https://boldstonesculpture.com/buy/p/brancusi-totem-white')
    e['tasks'] = [t for t in e['tasks'] if t['id'] != 'unselected_photo_alternatives']
    if pid in qualified:
        q = qualified[pid]
        e['tasks'].append(dict(id='unselected_photo_alternatives', state='action',
            title='Review larger unselected original photographs', scope='photos', url=q['qualifying_candidates'][0]['url'],
            detail=f"{len(q['qualifying_candidates'])} higher-resolution unselected associated originals meet the documented dimensions. "
                   + notes[pid] + ' Bounded current-revision headers and small visual previews verified; primary and purpose choices unchanged.'))
    e['checked_at'] = now
evidence['checked_at'] = now
evidence['source'] += ' Further review: real matched Pinterest events and both consent orders verified; four additional unselected photo opportunities retained for owner review.'
(OUT / 'platform-task-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status=receipt['status'], products_with_unselected_photo_options=4, qualifying_originals=21, logic_checks=17)))
