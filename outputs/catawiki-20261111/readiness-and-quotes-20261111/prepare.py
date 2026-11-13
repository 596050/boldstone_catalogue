"""Prepare a complete, non-publishing Catawiki readiness and supplier RFQ audit."""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
import json, hashlib, sys, re, html, shutil

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = Path(__file__).parent
assert not (OUT / 'dropbox-receipt.json').exists(), 'This dated operation is complete. Use a new operation directory to refresh it without overwriting its source snapshot or receipts.'
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column, column_index

pointer_path = ROOT / 'sculpture-catalogue/current-master.json'
pointer = json.loads(pointer_path.read_text())
source = Path(pointer['current_app_review_workbook']['path'])
body = source.read_bytes()
assert hashlib.sha256(body).hexdigest() == pointer['current_app_review_workbook']['sha256']
(OUT / 'source-pointer-before.json').write_text(json.dumps(pointer, ensure_ascii=False, indent=2) + '\n')
shutil.copyfile(source, OUT / 'previous-catalogue.xlsx')
x = Xlsx(source)
sheet = 'Wall Sculptures'
headers = {x.value(sheet, a): column(column_index(a)) for a in x.cells[sheet] if re.fullmatch(r'[A-Z]+7', a)}
review = json.loads((OUT.parent / 'product-review.json').read_text())
assert review['source_sha256'] == hashlib.sha256(body).hexdigest()
native = json.loads((OUT.parent / 'owner-decisions-20261111/canonical-lots.json').read_text())
lots = {p['product_id']: p for p in native['lots']}
by_id = {p['product_id']: p for p in review['products']}
assert len(by_id) == 176 and len(lots) == 43
get = lambda field, row: x.value(sheet, headers[field] + str(row))
now = datetime.now(timezone.utc).isoformat()
original_no_reserve = {p['product_id'] for p in by_id.values() if p['catawiki_target_price_eur'] < 200}
assert len(original_no_reserve) == 97
first_batch = [
    'BSI-2CA935C1A57A', 'BSI-624D16148726', 'BSI-EFBAEB31C2B1',
    'BSI-923D5E50A898', 'BSI-F7ADC5AEE4E0', 'BSI-FE10273D3655',
    'BSI-8298E205204F', 'BSI-B1DCB5B08396', 'BSI-8C0D9152DF73',
    'BSI-3C849B547D50',
]
known_reserves = {'BSI-2CA935C1A57A': 207, 'BSI-123AABD474C1': 899, 'BSI-A76B86DA7928': 440}
products = []
groups = defaultdict(list)
for row in range(8, 189):
    pid = get('Product ID', row)
    if pid not in by_id:
        continue
    p = by_id[pid]
    dims = sorted([get(f'ebay_packed_{k}_cm_estimate', row) for k in ['length', 'width', 'height']], reverse=True)
    weight = get('ebay_packed_kg_estimate', row)
    assert all(isinstance(n, (float, int)) and n > 0 for n in dims + [weight])
    if weight <= 5 and dims[0] <= 60: profile = 'P1'
    elif weight <= 10 and dims[0] <= 70: profile = 'P2'
    elif weight <= 20 and dims[0] <= 100: profile = 'P3'
    elif weight <= 30 and dims[0] <= 120: profile = 'P4'
    elif weight <= 60 and dims[0] <= 150: profile = 'F1'
    else: profile = 'F2'
    photos = p['photo_candidates']
    known_small = [i for i in photos if i['width_px'] and i['height_px'] and max(i['width_px'], i['height_px']) < 2000]
    unknown_px = [i for i in photos if not i['width_px'] or not i['height_px']]
    lot = lots.get(pid)
    signature = get('catawiki_signature', row) or ''
    era = get('catawiki_era', row) or ''
    # Exact production years are deliberately left blank where unknown.
    assert not get('catawiki_creation_year', row)
    reserve = None if pid in original_no_reserve else known_reserves.get(pid, p['catawiki_target_price_eur'] - 1)
    rec = {
        'product_id': pid, 'sku': p['sku'], 'title': p['title'], 'family': p['family'],
        'website': p['website'], 'catalogue_row': row, 'dimensions': p['dimensions'], 'weight': p['weight'],
        'material_finish': p['material_finish'], 'retail_gbp': p['retail_gbp'],
        'catawiki_target_price_gbp': p['catawiki_target_price_gbp'],
        'catawiki_target_price_eur': p['catawiki_target_price_eur'],
        'reserve_price_eur_proposed': reserve,
        'reserve_status': 'No reserve: owner-authorised original group' if reserve is None else 'Seller proposal only; expert approval required',
        'existing_lot_id': lot['id'] if lot else '',
        'existing_edit_url': 'https://www.catawiki.com/en/v/lot/' + lot['id'] + '/edit' if lot else '',
        'native_action': 'Update existing draft' if lot else 'New lot required after qualification',
        'first_batch_candidate_rank': first_batch.index(pid) + 1 if pid in first_batch else None,
        'photo_candidate_count': len(photos),
        'selected_listing_photo_count': sum(bool(i['listing']) for i in photos),
        'selected_in_situ_photo_count': sum(bool(i['in_situ']) for i in photos),
        'selected_non_in_situ_candidates': sum(not i['in_situ'] for i in photos),
        'shortfall_to_five_candidates': max(0, 5 - len(photos)),
        'known_below_2000px_long_edge': len(known_small),
        'original_dimensions_unknown': len(unknown_px),
        'actual_cast_photographs': 'Not confirmed. Catalogue examples are not proof of the specific auction cast.',
        'signature': signature or 'Awaiting owner confirmation; unsigned is a factual declaration, not a workaround',
        'era': era or 'Awaiting owner confirmation: is the actual cast After 2000?',
        'exact_year': '',
        'planned_cast_label': pid + '-CW01',
        'cast_reservation_state': 'PLANNED ONLY: identify and label a physical cast before auction. No live auction or cross-channel stock hold asserted.',
        'shipping_profile': profile,
        'packed_length_cm_estimate': dims[0], 'packed_width_cm_estimate': dims[1],
        'packed_height_cm_estimate': dims[2], 'packed_weight_kg_estimate': weight,
        'shipping_quote_status': 'Specialist RFQ requested; no verified rates or fragile-gypsum breakage cover yet',
        'shipping_quote_gbp': None,
        'pickup': 'Intended: Court Essington, Midford, Bath BA2 7BX; enable collection alongside verified shipping where supported',
        'readiness': 'PREPARATION ONLY: actual-cast photos, signature/era, insurance/rates, physical cast reservation and final terms pending',
        'photos': photos,
    }
    assert rec['catawiki_target_price_gbp'] == round(rec['retail_gbp'] + 100, 2)
    assert rec['catawiki_target_price_eur'] >= 150
    assert reserve is None or 0 < reserve < rec['catawiki_target_price_eur']
    products.append(rec)
    groups[profile].append(rec)

profiles = []
for key in ['P1', 'P2', 'P3', 'P4', 'F1', 'F2']:
    g = groups[key]
    profiles.append({
        'profile': key, 'product_count': len(g),
        'max_length_cm_estimate': max(r['packed_length_cm_estimate'] for r in g),
        'max_width_cm_estimate': max(r['packed_width_cm_estimate'] for r in g),
        'max_height_cm_estimate': max(r['packed_height_cm_estimate'] for r in g),
        'max_weight_kg_estimate': max(r['packed_weight_kg_estimate'] for r in g),
        'max_declared_value_gbp_proposed': max(r['catawiki_target_price_gbp'] for r in g),
        'type': 'Specialist parcel packing assessment' if key.startswith('P') else 'Pallet/crate/freight assessment',
        'basis': 'Separate potential shipments. Profile maxima can come from different products; no single packed consignment or carrier acceptance is asserted.',
        'quote_status': 'RFQ requested; awaited',
        'product_ids': [r['product_id'] for r in g],
    })

counts = {'publication_products': len(products), 'existing_native_products': len(lots),
          'new_lots_required': sum(not p['existing_lot_id'] for p in products),
          'native_drafts_observed': native['observed_drafts'], 'duplicate_held': native['duplicate_lot_held'],
          'no_reserve_authorised': len(original_no_reserve), 'reserve_proposals': sum(p['reserve_price_eur_proposed'] is not None for p in products),
          'all_targets_above_150_eur': True,
          'fewer_than_five_candidates': sum(p['photo_candidate_count'] < 5 for p in products),
          'first_batch_candidates': len(first_batch), 'complete_lots_verified': 0,
          'shipping_profiles': len(profiles)}
assert counts['new_lots_required'] == 133 and counts['reserve_proposals'] == 79
assert counts['fewer_than_five_candidates'] == 52

policy = {
    'recorded_utc': now,
    'prices': 'Keep catalogue GBP retail + GBP100. Do not apply an additional EUR200 asking floor. Expert valuation remains independent.',
    'no_reserve_original_product_ids': sorted(original_no_reserve),
    'higher_value_reserves': '79 seller proposals below the proposed estimates, for expert approval only; not approved reserves or guaranteed proceeds.',
    'signature_and_era': 'Owner confirmation requested; no unsigned or era declaration inferred from a conditional question.',
    'exact_year': 'Leave blank where unknown; do not reuse estimated Saatchi-only years or edition caps.',
    'photos': 'Official current art guidance does not state a numeric pixel minimum. Working recommendation: originals with at least 2000px on long edge, sharp and accurately lit; this is not an official Catawiki acceptance threshold. Native account editor previously requested at least five photos. Actual sale cast originals required; labelled accurate visualisations may supplement.',
    'unsigned': 'Direct-from-artist acceptance must be expert-reviewed. General contemporary-art guidance excludes unsigned works without supporting evidence. Do not invent a signature or certificate.',
    'cast_reservations': 'Planned labels only until actual physical casts are identified. Reserve the actual object through the auction/payment/fulfilment cycle; other listings may remain only if supported by genuinely separate available stock.',
    'shipping': 'Collection plus insured shipping intended. Packing estimates are not measured consignments. No rates entered until quoted for the relevant zone with fragile gypsum damage cover.',
    'catawiki_submitted': False, 'terms_accepted': False,
}
write = lambda name, obj: (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
write('readiness.json', {'created_utc': now, 'source_sha256': hashlib.sha256(body).hexdigest(), 'counts': counts, 'policy': policy, 'profiles': profiles, 'products': products})
write('owner-decisions.json', policy)
rfq = [{k: p[k] for k in ['product_id','sku','title','dimensions','material_finish','shipping_profile','packed_length_cm_estimate','packed_width_cm_estimate','packed_height_cm_estimate','packed_weight_kg_estimate','catawiki_target_price_gbp']} for p in products]
write('supplier-rfq-products.json', {'warning': 'ESTIMATES ONLY. 176 separate potential shipments, not one consignment. No manufacturing costs, private platform data or customer addresses included.', 'products': rfq})

# A readable complete product list using existing public image URLs, without downloading photographs.
esc = lambda s: html.escape(str(s or ''), quote=True)
cards = []
for p in sorted(products, key=lambda p: (p['family'], p['title'])):
    images = ''.join(f'<a href="{esc(i["dropbox_url"])}" target="_blank" rel="noopener"><img loading="lazy" src="{esc(i["url"])}" alt="{esc(i["alt"] or i["name"])}"><span>{esc(i["name"])} · {int(i["width_px"])} × {int(i["height_px"])} px</span></a>' if i['width_px'] and i['height_px'] else f'<a href="{esc(i["dropbox_url"])}" target="_blank" rel="noopener"><img loading="lazy" src="{esc(i["url"])}" alt="{esc(i["alt"] or i["name"])}"><span>{esc(i["name"])} · original dimensions unknown</span></a>' for i in p['photos'])
    rank = f'Candidate batch #{p["first_batch_candidate_rank"]} · ' if p['first_batch_candidate_rank'] else ''
    native_link = f'<a href="{esc(p["existing_edit_url"])}">Edit draft {esc(p["existing_lot_id"])}</a>' if p['existing_lot_id'] else 'New lot required after qualification'
    cards.append(f'''<article data-search="{esc((p['title']+' '+p['family']+' '+p['sku']+' '+p['product_id']).lower())}" data-new="{int(not p['existing_lot_id'])}" data-gap="{int(p['photo_candidate_count']<5)}" data-first="{int(bool(p['first_batch_candidate_rank']))}" data-freight="{int(p['shipping_profile'].startswith('F'))}">
    <h2>{esc(p['title'])}</h2><p class="muted">{esc(p['family'])} · {esc(p['sku'])} · {esc(p['product_id'])}</p>
    <p><b>{esc(rank)}{native_link}</b> · <a href="{esc(p['website'])}">Website</a></p>
    <dl><dt>Proposed estimate</dt><dd>€{p['catawiki_target_price_eur']:.0f} / £{p['catawiki_target_price_gbp']:.2f} (catalogue + £100)</dd><dt>Reserve</dt><dd>{'No reserve: owner authorised' if p['reserve_price_eur_proposed'] is None else '€'+format(p['reserve_price_eur_proposed'],'.0f')+' proposed, awaiting expert approval'}</dd>
    <dt>Object</dt><dd>{esc(p['dimensions'])} · {esc(p['weight'])}</dd><dt>Shipping profile {p['shipping_profile']}</dt><dd>Estimated packed {p['packed_length_cm_estimate']:g} × {p['packed_width_cm_estimate']:g} × {p['packed_height_cm_estimate']:g} cm / {p['packed_weight_kg_estimate']:g} kg. Quote and breakage cover pending.</dd>
    <dt>Selected candidates</dt><dd>{p['photo_candidate_count']} total · {p['selected_listing_photo_count']} listing · {p['selected_in_situ_photo_count']} in situ · shortfall to five: {p['shortfall_to_five_candidates']}</dd>
    <dt>Image quality review</dt><dd>{p['known_below_2000px_long_edge']} below recommended 2000px long edge; {p['original_dimensions_unknown']} dimensions unknown. Neither is a verified platform rejection.</dd>
    <dt>Facts</dt><dd>{esc(p['signature'])}. {esc(p['era'])}. Exact year blank.</dd><dt>Cast reservation</dt><dd>Proposed label {esc(p['planned_cast_label'])}. Physical cast still needs identification; no stock hold asserted.</dd></dl>
    <p class="hold">Actual-cast photographs, attribution evidence if unsigned, shipping and physical reservation require completion before submission.</p>
    <details><summary>View all {p['photo_candidate_count']} selected image links</summary><div class="photos">{images or '<p>No selected photographs.</p>'}</div></details></article>''')
profile_rows = ''.join(f'<tr><td>{p["profile"]}</td><td>{p["product_count"]}</td><td>{p["max_length_cm_estimate"]:g} × {p["max_width_cm_estimate"]:g} × {p["max_height_cm_estimate"]:g} cm</td><td>{p["max_weight_kg_estimate"]:g} kg</td><td>£{p["max_declared_value_gbp_proposed"]:.2f}</td></tr>' for p in profiles)
page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>All 176 Catawiki products: preparation, photographs and shipping</title><style>
body{{font:16px/1.5 system-ui,sans-serif;background:#f3f4ee;color:#1e2922;margin:0}}main{{max-width:1120px;margin:auto;padding:30px}}h1{{font-size:34px;line-height:1.15}}h2{{font-size:22px;margin-bottom:4px}}article,.box{{background:white;border:1px solid #d7dfd4;border-radius:12px;margin:18px 0;padding:24px}}a{{color:#315c4c}}.muted{{color:#657167}}.hold{{background:#fff3d8;padding:12px;border-radius:6px}}dl{{display:grid;grid-template-columns:190px 1fr;gap:8px 18px}}dt{{font-weight:650}}dd{{margin:0}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #d7dfd4}}.filters{{position:sticky;top:0;padding:14px;background:#e6ecdf;z-index:2;border-radius:8px;display:flex;gap:12px;flex-wrap:wrap}}input,select{{font:inherit;padding:10px;border:1px solid #adbdac;border-radius:6px}}input{{flex:1;min-width:200px}}.photos{{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin-top:15px}}.photos img{{width:100%;height:180px;object-fit:contain;background:#eee}}.photos span{{display:block;font-size:12px;overflow-wrap:anywhere}}[hidden]{{display:none!important}}details summary{{cursor:pointer;font-weight:650}}@media(max-width:600px){{main{{padding:14px}}dl{{grid-template-columns:1fr}}dd{{margin-bottom:10px}}}}
</style><main><p class="muted">Boldstone · Catawiki preparation · {esc(now)}</p><h1>All 176 products requiring Catawiki completion</h1><p>43 products already have native drafts; 133 need new lots. One extra duplicate draft is held out. No complete lots or public submissions are verified. This list covers every publication product, including all 52 with fewer than five selected image candidates.</p>
<div class="box"><h2>Pricing and photographs</h2><p>Existing catalogue prices plus £100 are retained: 97 no-reserve proposals and 79 reserve proposals requiring expert approval. All seller-proposed estimates meet the €150 numeric threshold in Direct from the Artist; expert selection and valuation are still independent.</p><p>Catawiki's current art guidance specifies high-resolution photographs without a numeric pixel minimum. <b>2000px on the long edge is a practical recommendation, not an official minimum.</b> Native account editor previously asked for at least five photographs. The actual sale cast must be shown; catalogue examples or accurately labelled AI settings can supplement suitable originals.</p><p>Unsigned means the physical cast has no artist signature. Production era is the period when that cast was made, such as After 2000. Confirmation is pending; exact years remain blank. Unsigned contemporary works require supporting attribution evidence and expert acceptance.</p></div>
<div class="box"><h2>Shipping quote groups</h2><p>Specialist packing and insured-delivery quotes requested. These are estimated envelopes, not measured packages. The maxima within a group can come from different products. No usable destination tariff or fragile-gypsum breakage cover is yet confirmed.</p><table><tr><th>Profile</th><th>Products</th><th>Maximum estimated dimensions</th><th>Maximum weight</th><th>Proposed declared value</th></tr>{profile_rows}</table><p>Collection: Court Essington, Midford, Bath BA2 7BX. Insured shipping will be offered alongside collection where supported once destination rates and fragile-gypsum cover are verified.</p></div>
<div class="filters"><input id="search" placeholder="Search title, SKU, family or product ID"><select id="mode"><option value="all">All 176 products</option><option value="new">133 new lots required</option><option value="existing">43 existing drafts</option><option value="gap">52 fewer than five candidates</option><option value="first">10 first-batch candidates — not yet ready</option><option value="freight">15 freight/crate assessments</option></select><span id="count"></span></div>
{''.join(cards)}<div class="box"><h2>Source and status boundaries</h2><p>Source workbook SHA-256: {esc(hashlib.sha256(body).hexdigest())}. Existing draft bindings: {esc(native['observed_drafts'])} drafts / {len(lots)} unique products; duplicate 108498490 excluded, canonical 108498424 retained. These are the last verified native observations, not publication receipts.</p><p><a href="https://www.catawiki.com/en/help/specific-guidelines-art/direct-from-the-artist-submission-guidelines">Direct from the Artist guidelines</a> · <a href="https://www.catawiki.com/en/help/specific-guidelines-art/post-war-contemporary-art-prints-submission-guidelines">Contemporary art attribution rules</a> · <a href="https://www.catawiki.com/en/help/seller-terms/ai-image-policy">AI image policy</a> · <a href="https://www.catawiki.com/en/help/submitting-lots/how-to-submit-multiple-bulk-objects-at-once">Bulk submission</a></p></div></main><script>
const q=document.querySelector('#search'),m=document.querySelector('#mode'),cards=[...document.querySelectorAll('article')];function filter(){{let n=0;for(const c of cards){{const s=q.value.toLowerCase(),mval=m.value;let yes=c.dataset.search.includes(s)&&(mval==='all'||(mval==='existing'&&c.dataset.new==='0')||c.dataset[mval]==='1');c.hidden=!yes;n+=yes}}document.querySelector('#count').textContent=n+' products'}}q.addEventListener('input',filter);m.addEventListener('change',filter);filter();</script></html>'''
(OUT / 'all-products.html').write_text(page)
print(json.dumps({'status': 'PREPARED_NOT_SUBMITTED', 'counts': counts, 'profiles': [{k:v for k,v in p.items() if k!='product_ids'} for p in profiles]}, indent=2))
