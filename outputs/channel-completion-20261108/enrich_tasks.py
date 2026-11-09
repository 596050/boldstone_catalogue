"""Add exact original-photo and native export readbacks to existing dated tasks."""
from pathlib import Path
import json

OUT = Path(__file__).parent
load = lambda n: json.loads((OUT / n).read_text())
evidence = load('platform-task-evidence.json')
review = load('pinterest-original-resolution-review.json')
bb = load('brandboom-native-restore-verification.json')
fix = load('brandboom-duplicate-photo-fix.json')
assert review['summary']['checked'] == 96 and not review['summary']['failures']
assert review['summary']['known_original_below_dimensions'] == 96
assert bb['status'] == 'PASS_ALL_176_NATIVE_PRODUCT_FIELDS'

for product in review['products']:
    entry = evidence['products'][product['catalogue_id']]['platforms']['pinterest']
    target = next(t for t in entry['tasks'] if t['id'] == 'primary_image_size')
    image = product['primary']
    width, height = image['original']['dimensions']
    candidates = [a for a in product['higher_resolution_listing_candidates']
                  if a['hosted_check']['meets_documented_dimensions']]
    detail = (f'Exact primary original is {width} × {height} px. '
              'Pinterest documents width >=1,000 and height >=1,500 pixels. ')
    detail += (f'{len(candidates)} genuinely larger already-selected Listing photograph(s) '
               'also meet the dimensions at their existing public URLs. Review those alternatives; '
               'the current primary choice is unchanged.' if candidates else
               'No qualifying alternative was found among the currently selected Listing photographs. '
               'Review unselected originals or obtain a suitable new photograph; do not upscale as a substitute for detail.')
    target['detail'] = detail + ' This size check is separate from the account-level merchant rejection; Pinterest has not identified individual failing products.'
    target['url'] = image['url']
    entry['tasks'] = [t for t in entry['tasks'] if t['id'] != 'selected_photo_alternatives']
    if candidates:
        details = []
        for a in candidates:
            dims = ' × '.join(map(str, a['original']['dimensions']))
            hosted = ' × '.join(map(str, a['hosted_check']['dimensions']))
            details.append(f"{a['name']}: original {dims} px; hosted {hosted} px; {a['id']}")
        entry['tasks'].append(dict(id='selected_photo_alternatives', state='verified',
            title='Larger selected Listing photos are available',
            detail='Original identities/hashes verified, hosted dimensions checked: ' + '; '.join(details)
                   + '. These are review choices, not new primary selections.',
            scope='photos', url=candidates[0]['url']))
    entry['checked_at'] = review['summary']['checked_at']

for pid, product in evidence['products'].items():
    entry = product['platforms']['brandboom']
    if entry['state'] == 'not_targeted':
        continue
    restore = next(t for t in entry['tasks'] if t['id'] == 'restore_catalogue')
    restore['detail'] = ('176 existing products and SKUs restored, zero added. Native all-product export '
        'independently matched every SKU and 13 saved fields: 2,288 comparisons, zero differences. '
        'All 176 are active in the editor. This export has no image columns; it does not prove every gallery or public Marketplace visibility.')
    entry['tasks'] = [t for t in entry['tasks'] if t['id'] != 'duplicate_photo_corrected']
    if pid == fix['catalogue_id']:
        entry['tasks'].append(dict(id='duplicate_photo_corrected', state='verified',
            title='Extra duplicate photo association removed',
            detail='The extra byte-identical native media 34736843 was moved to the recoverable Media Bin; '
                   '34706371 was retained. Saved once, browser reloaded, product reopened: all expected '
                   '17 photo IDs verified, primary 34706366 and £109.25 wholesale unchanged. '
                   'Distinct owner-selected Dropbox records with identical rendered pixels were retained.',
            scope='photos', url='https://manage.brandboom.com/products/s/111089'))
        entry['checked_at'] = fix['checked_at']
    else:
        entry['checked_at'] = bb['checked_at']

evidence['checked_at'] = fix['checked_at']
evidence['source'] = evidence['source'].split(' Follow-up:')[0] + ' Follow-up: all 96 original primary dimensions confirmed; 28 have qualifying selected/hosted alternatives. Brandboom native fields verified for all 176; one exact duplicate photo association corrected and reopened.'
assert sum(any(t['id'] == 'primary_image_size' for t in p['platforms']['pinterest']['tasks']) for p in evidence['products'].values()) == 96
assert sum(any(t['id'] == 'selected_photo_alternatives' for t in p['platforms']['pinterest']['tasks']) for p in evidence['products'].values()) == 28
(OUT / 'platform-task-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'products': len(evidence['products']), 'primary_resolution_tasks': 96,
                  'products_with_verified_alternatives': 28, 'brandboom_duplicate_fixes': 1}))
