"""Apply the owner's scoped Catawiki decisions without changing other channels."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, sys

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column, column_index

w = Xlsx(OUT / 'previous-catalogue.xlsx')
sheet = 'Wall Sculptures'
headers = {w.value(sheet, a): column(column_index(a)) for a in w.cells[sheet] if re.fullmatch(r'[A-Z]+7', a)}
assert len(headers) == 962
review = json.loads((OUT.parent / 'product-review.json').read_text())
products = {p['product_id']: p for p in review['products']}
native = json.loads((OUT / 'canonical-lots.json').read_text())
lots = {p['product_id']: p for p in native['lots']}
saved = json.loads((OUT / 'native-draft-updates.json').read_text())
verified = {p['product_id']: p for p in saved}
known_reserves = {'BSI-2CA935C1A57A': 207, 'BSI-123AABD474C1': 899, 'BSI-A76B86DA7928': 440}
now = datetime.now(timezone.utc)
serial = lambda d: (d - datetime(1899, 12, 30, tzinfo=timezone.utc)).total_seconds() / 86400
patches = []

def put(name, row, value):
    assert name.startswith('catawiki_')
    a = headers[name] + str(row)
    before = w.value(sheet, a)
    formula = w.formula(sheet, a)
    if before != value:
        patches.append({'sheet': sheet, 'cell': a, 'field': name, 'before': before,
                        'value': value, 'formula': formula})

for row in range(8, 189):
    pid = w.value(sheet, headers['Product ID'] + str(row))
    if pid not in products:
        continue
    p = products[pid]
    desc = re.sub(r'^Availability: Made to order\n', '', p['draft']['Description'], flags=re.M)
    desc = re.sub(r'\n\nDimensions: [^\n]+\nWeight: [^\n]+\nQuantity: one individual sculpture or panel\.[\s\S]*$', '', desc)
    desc += ('\n\nCondition: new, as confirmed by the maker. Each sculpture is handmade. '
             'Photographs are reference examples of the design and finish; the supplied cast may vary from the images. '
             'Collection in Midford, Bath, and insured shipping are intended; shipping service and destination charges remain to be confirmed.')
    put('catawiki_description', row, desc)
    put('catawiki_condition', row, 'New (owner-confirmed)')
    put('catawiki_object_details_review', row,
        'Owner confirms new casts that vary from the catalogue images. Signature and production era/year are not specified. '
        'Do not copy Saatchi-only years or edition caps. Confirm and photograph the specific physical cast before final submission.')
    count = p['photo_candidate_count']
    put('catawiki_photo_candidate_urls', row, ';'.join(i['url'] for i in p['photo_candidates']))
    put('catawiki_photo_candidate_count', row, count)
    put('catawiki_photo_shortfall_to_five', row, max(0, 5 - count))
    put('catawiki_photo_review', row,
        'Listing and In situ selections are candidates, not accepted evidence. Owner says supplied casts vary from reference images. '
        'Catawiki requires original photos of the actual sale object; native editor asks for at least five suitable photos. '
        'Accurate AI visualisations must be labelled and can supplement, not replace, required originals. Policy updated 14 August 2026.')
    put('catawiki_price_basis', row,
        'Catalogue GBP selling price + GBP100; whole-EUR target remains unchanged. Owner accepts the eight modelled lower net-proceeds cases. '
        'Additional common minimum value requested, but amount and asking-value versus sale-floor interpretation await clarification. '
        'EUR200 asking-floor scenario is not applied. Shipping is separate; an estimate is not a guaranteed auction minimum.')
    if p['catawiki_target_price_eur'] < 200:
        reserve_review = 'Owner explicitly permits no-reserve auctions for the original 97 targets below EUR200. The estimate does not prevent a lower winning bid. Additional minimum-value clarification pending.'
    else:
        reserve_review = 'Reserve requires native entry and expert approval. Native UI requires reserve below the estimate; no 90-percent after-auction concession is authorised.'
    if pid in known_reserves:
        reserve_review += ' Saved native draft reserve proposal: EUR' + str(known_reserves[pid]) + '; not an accepted or live auction reserve.'
        put('catawiki_reserve_price_eur', row, known_reserves[pid])
    put('catawiki_reserve_review', row, reserve_review)
    put('catawiki_value_review', row,
        'Seller-proposed value, not independent appraisal. No extra price increases made for the accepted fee shortfalls. '
        'Common asking/sale floor awaits clarification; expert determines selection and valuation.')
    put('catawiki_shipping_review', row,
        'Owner requests both collection from Midford, Bath, and insured shipping. No verified Catawiki destination rates or shipping profile yet. '
        'Obtain packing and tracked carrier/freight quotes with sculpture loss/damage cover, including EU destinations. '
        'Do not adopt suggested EUR12.50 rates or treat blank rates as free shipping. Larger sculptures require freight assessment.')
    put('catawiki_exclusivity_status', row,
        'Reservation of the specific physical cast exclusively for Catawiki remains unconfirmed. Other channel product listings have not been withdrawn.')
    if pid in lots:
        lot = lots[pid]
        put('catawiki_native_lot_id', row, lot['id'])
        put('catawiki_native_edit_url', row, 'https://www.catawiki.com/en/v/lot/' + lot['id'] + '/edit')
        status = 'Draft observed; not submitted or live publication evidence.'
        if pid in verified:
            status += ' New condition, reference-image disclosure, dimensions and target price saved and independently read back in the native editor.'
        if pid == 'BSI-DF3FF43C94C9':
            status += ' Duplicate draft 108498490 held out; retain canonical 108498424.'
        put('catawiki_native_status', row, status)
        put('catawiki_native_observed_utc', row, serial(now))
    put('catawiki_prepared_utc', row, serial(now))

assert len(products) == 176 and len(lots) == 43 and native['observed_drafts'] == 44
assert len({p['cell'] for p in patches}) == len(patches)
assert all(len(str(p['value'])) <= 32767 for p in patches)
plan = {'created_utc': now.isoformat(), 'source_sha256': hashlib.sha256((OUT / 'previous-catalogue.xlsx').read_bytes()).hexdigest(),
        'scope': 'Catawiki-only owner decisions: new casts, reference-image variation, approved no-reserve policy for 97 existing targets, collection plus insured-shipping intent, updated native-draft bindings and photo-policy review. Prices, all other channels, signatures, production years and edition limits are unchanged. No final Catawiki submission.',
        'counts': {'component_records': 181, 'publication_products': 176, 'new_condition_records': 176,
                   'observed_native_drafts': 44, 'unique_native_products': 43, 'duplicate_drafts_held': 1,
                   'remaining_without_native_lot': 133, 'native_decision_updates_verified': len(verified),
                   'no_reserve_approved_original_targets': 97},
        'patches': patches,
        'previews': [{'name': 'condition', 'range': headers['catawiki_condition']+'7:'+headers['catawiki_era']+'10'},
                     {'name': 'native-status', 'range': headers['catawiki_native_lot_id']+'7:'+headers['catawiki_native_status']+'10'}]}
(OUT / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'patches': len(patches), 'counts': plan['counts']}, indent=2))
