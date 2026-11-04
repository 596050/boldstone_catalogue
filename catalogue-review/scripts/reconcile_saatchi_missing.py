"""Reconcile captured Saatchi portfolio rows to the current catalogue.

Read-only against the app, source workbook and native-ID receipts. Writes a
local reconciliation packet; does not create or publish any artwork.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'catalogue-review'), str(ROOT / 'catalogue-review/scripts')]
from channel_content import values, finish_retail_name
from import_saatchi_snapshot import Xlsx, artwork_records, column
from prepare_saatchi_catalogue import native_artwork_bindings


def reconcile(out):
    read = lambda path: json.loads(path.read_text())
    write = lambda name, data: (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    app = read(out / 'app-current.json')
    baseline = read(ROOT / 'outputs/catalogue-data-audit-20261104/app.json')
    assert app['revision'] == baseline['revision'] and app['source_hash'] == baseline['source_hash']
    assert app['products'] == baseline['products'], 'Refresh image evidence after catalogue changes'
    olddir = ROOT / 'outputs/catalogue-marketplace-publication-20261101/saatchi-current'
    old = {r['catalogue_id']: r for r in read(olddir / 'prepared-catalogue.json')['records']}
    # These captures predate the 4 November creation. Keep their 98-artwork
    # reconciliation reproducible; the later cross-platform report overlays
    # newly verified creations from their own receipt.
    frozen_receipts = ROOT / 'outputs/multichannel-missing-20261104/saatchi-primary-receipts-before.json'
    bindings = native_artwork_bindings(frozen_receipts if frozen_receipts.exists() else olddir / 'primary-draft-receipts.json')
    _, source = artwork_records(Xlsx('/Users/tprice/Downloads/Saatchi_Art_artworks_2026-11-03.xlsx'))
    assert len(source) == len(bindings) == 98
    source_by_id = {r['Artwork ID']: r for r in source}
    assert set(bindings.values()) == set(source_by_id)

    captures = [out / 'portfolio-ax-3.txt', out / 'portfolio-ax-4.txt'] + sorted(out.glob('page-*.txt'))
    live = {}
    for capture in captures:
        text = capture.read_text()
        matches = list(re.finditer(r'\n\s*\d+ text (.+)\n\s*\d+ text Sculpture\n', text))
        for i, match in enumerate(matches):
            body = text[match.start():matches[i+1].start() if i+1 < len(matches) else len(text)]
            price = re.search(r'\d+ text \$([^\n]+)', body)
            row = live.setdefault(match[1], {'title': match[1], 'captures': [], 'published': False, 'for_sale': False})
            row['captures'].append(capture.name)
            # Virtualised boundary rows can omit their final fields. Merge
            # their complete overlapping readback instead of overwriting it.
            row['published'] |= bool(re.search(r'\d+ text Published\n', body))
            row['for_sale'] |= bool(re.search(r'\d+ text For Sale\n', body))
            if price:
                row['price_usd'] = float(price[1].replace(',', ''))
    assert len(live) == 98
    matched = []
    for title, row in live.items():
        candidates = [r for r in source if r['Title'].replace(' Finish', '') == title.replace(' Finish', '')]
        assert len(candidates) == 1, title
        src = candidates[0]
        assert row['published'] and row['for_sale'], title
        assert row['price_usd'] == src['Artwork price (US$)'], title
        matched.append({**row, 'artwork_id_binding': src['Artwork ID'], 'studio_url': src['Studio page'],
                        'binding_basis': 'Supplied native-ID inventory; live unique title, price and visibility reconciliation. IDs not freshly extracted.'})
    assert len({r['artwork_id_binding'] for r in matched}) == 98

    workbook = Xlsx(ROOT / 'outputs/catalogue-completeness-20261103/catalogue_wall_sculptures.xlsx')
    headers = {workbook.value('Wall Sculptures', column(c)+'7'): column(c) for c in range(1, 431)}
    rows = {workbook.value('Wall Sculptures', 'AA'+str(r)): r for r in range(8, 189)}
    fields = [h for h in headers if h.startswith('saatchi_') and not h.startswith('saatchi_observed_')]
    alternatives = read(out / 'alternatives-to-review.json')
    visual = {
        'BOLD-449C4421ABD0': 'Only a cropped surface detail at the required size; no complete individual view.',
        'BOLD-624D16148726': 'Larger photographs show both panels. Individual-component primary needs an unambiguous complete view.',
        'BOLD-EFBAEB31C2B1': 'Larger photographs show both panels. Individual-component primary needs an unambiguous complete view.',
        'BOLD-9278986A1A89': 'The larger selected photograph shows two panels; confirm image identity and provide a complete individual view.',
        'BOLD-7CDE8362BB51': 'The larger selected photograph shows two panels; confirm image identity and provide a complete individual view.',
        'SQ2233720': 'Larger photograph crops the sculpture edges; suitable as a detail, not the complete primary view.',
        'BOLD-A57A49000891': 'Reviewed full individual sculpture photograph; acceptable dimensions. Alternative preserves the app primary.',
    }
    missing = []
    exclusions = []
    for p in app['products']:
        f = values(p)
        sku = f['Seller SKU']
        assert sku == workbook.value('Wall Sculptures', 'AQ'+str(rows[p['id']])), sku
        if p['listing_decision'] != 'include':
            exclusions.append({'id': p['id'], 'name': p['name'], 'decision': p['listing_decision']})
            continue
        if sku in bindings:
            continue
        listing = {r['id']: r for r in p['photos']['listing']['images']}
        checks = []
        for photo in old.get(p['id'], {}).get('photos', []):
            if photo['id'] not in listing:
                continue
            current = listing[photo['id']]
            current_hash = current.get('original', {}).get('dropbox_content_hash')
            assert current_hash and current_hash == photo['content_hash'], photo['id']
            checks.append({'photo_id': photo['id'], 'url': photo['url'], 'content_hash': current_hash,
                           'withheld_reasons': current['withheld_reasons'], **photo['header_check']})
        good = [r for r in checks if r['status'] == 'PASS_IMAGE_HEADER_CHECK' and not r['withheld_reasons']]
        status = 'Needs a qualifying full-view primary'
        reason = 'Selected listing photographs do not meet the native 1500W × 1200H minimum.'
        if good:
            assert sku in visual
            status = 'Photo review needed'
            reason = visual[sku]
        if sku == 'BOLD-A57A49000891':
            status = 'Image ready; upload not saved'
        if not listing:
            status = 'Photography deferred by owner'
            reason = p.get('notes') or 'No listing photograph selected.'
        elif p['id'] not in old:
            status = 'Separate catalogue inclusion review'
            reason = 'Included app component outside the previous 176-product publication scope. Its selected image has no prior Saatchi preflight.'
        target = {h: workbook.value('Wall Sculptures', headers[h]+str(rows[p['id']])) for h in fields}
        assert target['saatchi_catalogue_sku'] == sku
        assert target['saatchi_catalogue_price_gbp'] == p['costing']['pricing']['marked_up_price']
        assert len(target['saatchi_description']) <= 1000
        missing.append({'id': p['id'], 'sku': sku, 'name': p['name'], 'title': finish_retail_name(p),
                        'family': p['family'], 'app_url': 'http://127.0.0.1:8767/#'+p['id'], 'folder_url': p['folder_url'],
                        'previous_176_publication_scope': p['id'] in old, 'status': status, 'reason': reason,
                        'selected_listing_count': len(listing), 'photo_checks': checks, 'qualifying_photo_count': len(good),
                        'current_catalogue_targets': target, 'native_artwork_id': None, 'saved_or_published_this_run': False,
                        'creation_year': None, 'edition_status': None, 'physical_stock_count': None})
    assert len(missing) == 80 and sum(r['previous_176_publication_scope'] for r in missing) == 78
    assert len({r['id'] for r in missing}) == len({r['sku'] for r in missing}) == 80
    assert not set(r['sku'] for r in missing) & set(bindings)
    summary = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'app_revision': app['revision'],
               'app_included': 178, 'excluded': len(exclusions), 'live_portfolio_count': 98,
               'live_published_and_for_sale_count': 98, 'missing_included_components': 80,
               'missing_from_previous_176_product_scope': 78, 'additional_included_records': 2,
               'missing_records_with_pixel_qualifying_listing_photos': sum(r['qualifying_photo_count'] > 0 for r in missing),
               'visually_usable_full_view_alternatives': 1, 'native_creations_confirmed': 0,
               'status_counts': dict(Counter(r['status'] for r in missing)),
               'native_upload_rule': 'Live uploader: JPEG/PNG, at least 1500W × 1200H pixels, less than 50 MB.',
               'blocking_tool_issue': 'Browser filechooser could not initialise; native Go to Folder selection resets without confirming the chosen file.',
               'publication_requirements': 'Actual year, original/edition and stock facts remain unverified for new artworks; do not copy them from unrelated existing works. Crate weights/dimensions remain estimates.'}
    write('live-portfolio-reconciled.json', matched)
    write('missing-records.json', missing)
    write('summary.json', summary)
    write('exclusions.json', exclusions)
    esc = lambda s: html.escape(str(s or ''))
    body = []
    for r in missing:
        photos = ''.join('<li><a href="'+esc(c['url'])+'">'+esc(c['photo_id'])+'</a>: '+esc(c.get('width'))+' × '+esc(c.get('height'))+' px; '+esc(c['status'])+'</li>' for c in r['photo_checks'])
        target = r['current_catalogue_targets']
        body.append('<tr><td><a href="'+esc(r['app_url'])+'">'+esc(r['title'])+'</a><br><small>'+esc(r['sku'])+'</small></td><td>'+esc(r['status'])+'<br>'+esc(r['reason'])+'</td><td>£'+format(target['saatchi_catalogue_price_gbp'],'.2f')+' catalogue<br>$'+format(target['saatchi_asking_price_usd'],'.0f')+' Saatchi target</td><td><a href="'+esc(r['folder_url'])+'">Dropbox folder</a><details><summary>'+str(r['selected_listing_count'])+' selected listing photos; inspect evidence</summary><ul>'+photos+'</ul></details><details><summary>Prepared description and specifications</summary><p class="copy">'+esc(target['saatchi_description'])+'</p><p>'+esc(target['saatchi_dimensions_text'])+'; '+esc(target['saatchi_weight_text'])+'</p></details></td></tr>')
    doc = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Saatchi missing wall sculptures</title><style>body{font:16px system-ui;margin:32px;color:#253029}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd2ca;padding:12px;text-align:left;vertical-align:top}th{background:#edf0e8}small{color:#59645c}a{color:#345a42}.copy{white-space:pre-wrap}details{margin:10px 0}input{padding:10px;width:480px;max-width:90%}</style><h1>Saatchi missing wall sculptures</h1><p>Checked '+esc(summary['checked_utc'])+'. Live portfolio: 98 published artworks for sale, reconciled by unique title and price against the existing native-ID inventory. 80 included app components are absent: 78 from the previous 176-product publication scope, plus two other included records.</p><p>No new artwork has been saved or published in this run. One full-view alternative is ready for upload. The other records need a suitable primary, image review or their existing catalogue hold resolved. No artwork images are downloaded by this report.</p><p>New artwork year, edition/stock facts and final crate measurements require their own evidence. Prepared USD prices include the workbook commission/discount allowances and exclude shipping.</p><input placeholder="Filter by name, SKU or status" oninput="for(const r of document.querySelectorAll(\'tbody tr\'))r.hidden=!r.innerText.toLowerCase().includes(this.value.toLowerCase())"><table><thead><tr><th>Sculpture</th><th>Next action</th><th>Prices</th><th>Source and prepared copy</th></tr></thead><tbody>'+''.join(body)+'</tbody></table></html>'
    (out/'missing-wall-sculptures.html').write_text(doc)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    reconcile(Path(sys.argv[1]).resolve())
