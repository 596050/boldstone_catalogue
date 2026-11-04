"""Reconcile captured platform inventories without creating or changing offers.

Native browser captures are the current inventory evidence. Historical receipts
provide stable ID bindings; public HTTP failures are never treated as absence.
"""
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review'))
from channel_content import values


def reconcile(out):
    read = lambda p: json.loads(p.read_text())
    write = lambda n, v: (out / n).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
    app = read(out / 'app-current.json')
    included = [p for p in app['products'] if p['listing_decision'] == 'include']
    assert len(included) == 178
    current = {values(p)['Seller SKU']: p for p in included}
    assert len(current) == len(included)
    previous = ROOT / 'outputs/catalogue-marketplace-publication-20261101'
    chairish = {r['sku']: r for r in read(previous / 'chairish-current/draft-receipts.json')}
    wescover = {r['sku']: r for r in read(previous / 'wescover-current/public-176-final-audit.json')['records']}
    assert len(chairish) == len(wescover) == 176
    assert set(chairish) == set(wescover) < set(current)

    draft_capture = (out / 'chairish-drafts-initial.txt').read_text()
    draft_skus = re.findall(r'SKU: ([^\n]+)', draft_capture)
    assert len(draft_skus) == len(set(draft_skus)) == 24
    captures = ['chairish-pending-loaded.txt', 'chairish-pending-page2.txt',
                'chairish-pending-page3.txt', 'chairish-pending-page4.txt']
    pending_paged = []
    for name in captures:
        pending_paged.extend(re.findall(r'SKU: ([^\n]+)', (out / name).read_text()))
    assert len(pending_paged) == 152
    pending = set(pending_paged)
    # Four rows crossed pagination boundaries. Check their exact, already-known
    # native IDs rather than creating replacements or calling them duplicates.
    direct = []
    for p in sorted(out.glob('chairish-record-*.txt')):
        text = p.read_text()
        native_id = p.stem.removeprefix('chairish-record-')
        sku = re.search(r'SKU \(Optional\), Value: ([^\n]+)', text)[1]
        assert chairish[sku]['id'] == native_id
        assert 'text Pending Review' in text
        pending.add(sku)
        direct.append({'sku': sku, 'native_id': native_id, 'capture': p.name})
    assert len(direct) == 4 and len(pending) == 152
    assert not pending & set(draft_skus)
    assert pending | set(draft_skus) == set(chairish)
    assert 'No current all listings.' in (out / 'chairish-active.txt').read_text()
    assert 'No current incomplete listings.' in (out / 'chairish-incomplete.txt').read_text()
    inactive = (out / 'chairish-inactive.txt').read_text()
    assert 'terracotta-top-accent-table-metal-legs' in inactive

    inventory_text = '\n'.join((out / name).read_text() for name in
                               ['wescover-items-first100.txt', 'wescover-items-bottom.txt'])
    assert 'of 178 items' in inventory_text
    headings = set(re.findall(r'heading (.+), Value: 3', inventory_text))
    assert len({r['title'] for r in wescover.values()}) == 176
    assert {r['title'] for r in wescover.values()} <= headings
    other = headings - {r['title'] for r in wescover.values()} - {
        'Creator Profile', 'Running a sale? Discount your whole catalog at once', 'Creator Video'}
    assert other == {'Terracotta Top Accent Table with Metal Legs', 'Two Frozen Decowaves Wall Sculpture'}
    public = read(out / 'wescover-public-readbacks.json')
    public_by_sku = {r['sku']: r for r in public}
    assert set(public_by_sku) == set(wescover)
    summary_public = read(out / 'wescover-summary.json')
    public_ok = {r['sku'] for r in public if r.get('status') == 'PUBLIC_PRODUCT_MATCHED'}
    assert len(public_ok) == summary_public['matched_current_products']
    assert all(r.get('http_status') in (200, 429) for r in public)

    saatchi_out = ROOT / 'outputs/saatchi-missing-reconciliation-20261104'
    missing_saatchi = {r['sku']: r for r in read(saatchi_out / 'missing-records.json')}
    live_saatchi = read(saatchi_out / 'live-portfolio-reconciled.json')
    assert len(missing_saatchi) == 80 and len(live_saatchi) == 98
    creation = read(out / 'new-saatchi-draft.json') if (out / 'new-saatchi-draft.json').exists() else None
    created = {}
    if creation:
        assert creation['status'] == 'DRAFT_PRIMARY_ONLY_NOT_PUBLISHED'
        assert creation['sku'] in missing_saatchi
        saved = (out / 'saatchi-save-checked.txt').read_text()
        assert '/art/'+creation['artwork_id']+'/overview' in saved
        assert creation['title']+' Visibility:  Draft' in saved
        created[creation['sku']] = creation
    additional = set(current) - set(wescover)
    assert additional == {'BOLD-D886F539DD3E', 'BOLD-65520F070145'}
    records = []
    for sku, p in current.items():
        blocked = ''
        if sku == 'BOLD-D886F539DD3E':
            blocked = 'Owner deferred photography; no listing photos selected. Preserve that instruction.'
        elif sku == 'BOLD-65520F070145':
            blocked = 'Catalogue sale unit still says native option alias unresolved; selected image is a pattern study. One selected photo only (Chairish requires two). Resolve identity before creating another offer.'
        records.append({'catalogue_id': p['id'], 'sku': sku, 'name': p['name'],
                        'retail_name': p['retail_name'],
                        'app_url': 'http://127.0.0.1:8767/#'+p['id'],
                        'chairish': {'state': 'Pending Review' if sku in pending else 'Draft' if sku in draft_skus else 'Not uploaded',
                                     'native_id': chairish.get(sku, {}).get('id'), 'url': chairish.get(sku, {}).get('url')},
                        'wescover': {'state': 'Public product verified' if sku in public_ok else 'Native inventory present; public HTTP check rate-limited' if sku in wescover else 'Not uploaded',
                                     'native_item_id': wescover.get(sku, {}).get('native_item_id'), 'url': wescover.get(sku, {}).get('url'),
                                     'current_native_binding_basis': 'Unique native inventory title against previous stable-ID manifest; 103 exact public SKU readbacks.' if sku in wescover else ''},
                        'saatchi': {'state': 'New draft saved; publication details required' if sku in created else missing_saatchi[sku]['status'] if sku in missing_saatchi else 'Published and for sale',
                                    'missing': sku in missing_saatchi and sku not in created,
                                    'native_id': created.get(sku, {}).get('artwork_id'),
                                    'url': created.get(sku, {}).get('url')},
                        'additional_blocker': blocked, 'native_creation_confirmed_this_run': sku in created})
    summary = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'app_revision': app['revision'],
               'included_components': 178, 'previous_publication_scope': 176,
               'chairish': {'exact_existing_sku_matches': 176, 'active': 0, 'pending_review': 152, 'drafts': 24,
                            'incomplete': 0, 'unrelated_hidden_table': 1, 'additional_not_uploaded': 2,
                            'pagination_boundary_rows_reconciled_by_existing_native_id': direct},
               'wescover': {'native_inventory_count': 178, 'matched_catalogue_titles': 176,
                            'other_existing_products': sorted(other), 'public_exact_checks_passed': len(public_ok),
                            'public_checks_rate_limited': 176-len(public_ok), 'additional_not_uploaded': 2,
                            'public_failure_is_not_absence': True},
               'saatchi': {'published_and_for_sale': 98, 'new_saved_drafts': len(created),
                           'still_absent_included_components': 80-len(created),
                           'not_published_included_components': 80,
                           'still_absent_from_previous_176_scope': 78-len(created)},
               'new_platform_records_created': len(created),
               'limits': ['Current inventory presence is not approval or a full current copy/price audit.',
                          'Saatchi native file selection succeeded through Downloads. New artwork year and edition facts remain unverified; the incomplete description form has not passed its save step.',
                          'Do not upscale or pad undersized photographs to evade upload requirements.']}
    write('reconciled-records.json', records)
    write('summary.json', summary)
    esc = lambda v: html.escape(str(v or ''))
    rows = []
    for r in records:
        def link(platform):
            t = r[platform]
            return '<a href="'+esc(t['url'])+'">'+esc(t['state'])+'</a>' if t.get('url') else esc(t['state'])
        rows.append('<tr><td><a href="'+esc(r['app_url'])+'">'+esc(r['retail_name'])+'</a><br><small>'+esc(r['sku'])+'</small></td><td>'+link('saatchi')+'</td><td>'+link('chairish')+'</td><td>'+link('wescover')+'</td><td>'+esc(r['additional_blocker'])+'</td></tr>')
    (out / 'platform-reconciliation.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><title>Wall sculpture platform reconciliation</title><style>body{font:16px system-ui;margin:32px;color:#253029}table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccd2ca;padding:10px;text-align:left;vertical-align:top}th{background:#edf0e8}a{color:#345a42}small{color:#59645c}input{padding:10px;width:400px}</style><h1>Wall sculpture platform reconciliation</h1><p>Checked '''+esc(summary['checked_utc'])+'''. Source: current app, 178 included components. '''+str(len(created))+''' new Saatchi draft saved. Existing offers were preserved.</p><ul><li>Saatchi: 98 published; '''+str(len(created))+''' new draft; '''+str(80-len(created))+''' included components remain absent.</li><li>Chairish: all previous 176 exact SKUs exist: 152 pending review, 24 drafts, none active.</li><li>Wescover: all previous 176 unique product titles exist in the native editor. 103 public products have fresh exact SKU checks; 73 public checks were rate-limited. An existing table and separate pair offer were preserved.</li><li>Two additional app records remain held: deferred water-feature photography and unresolved Yellow/Grey Circle alias.</li></ul><p>Inventory presence does not mean current copy/prices were fully audited or a platform approved a product. <a href="../saatchi-missing-reconciliation-20261104/missing-wall-sculptures.html">Initial Saatchi missing photos and prepared copy</a>. That earlier packet predates the new Wave and Moonshadow I draft, native ID 14388967. Its year and edition facts remain unverified; description form values are prepared but their persistence is not claimed.</p><input placeholder="Filter name, SKU or status" oninput="for(const r of document.querySelectorAll('tbody tr'))r.hidden=!r.innerText.toLowerCase().includes(this.value.toLowerCase())"><table><thead><tr><th>Catalogue component</th><th>Saatchi</th><th>Chairish</th><th>Wescover</th><th>Additional upload blocker</th></tr></thead><tbody>'''+''.join(rows)+'</tbody></table></html>')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    reconcile(Path(sys.argv[1]).resolve())
