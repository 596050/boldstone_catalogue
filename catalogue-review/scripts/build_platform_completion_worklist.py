"""Reconcile publication evidence without changing any external listings."""
from __future__ import annotations

import collections
import copy
import datetime as dt
import html
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'outputs/platform-live-completion-20261104'


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    scope = read(OUT / 'scope.json')
    source = read(OUT / 'app-source.json')
    with urlopen('http://127.0.0.1:8767/api/specifications', timeout=30) as response:
        latest = json.load(response)
    assert latest['revision'] == source['revision'] == scope['app_revision'], 'App source changed; reconcile again.'
    skus = set(scope['publication_skus'])
    assert len(skus) == 176
    products = {p['id']: p for p in source['products']}
    prior = {r['sku']: r for r in read(ROOT / 'outputs/multichannel-missing-20261104/reconciled-records.json') if r['sku'] in skus}
    chair = {r['sku']: r for r in read(ROOT / 'outputs/platform-rollout-20261104/chairish-price-updates.json')['records']}
    chair_verification = read(ROOT / 'outputs/platform-rollout-20261104/chairish-verification.json')
    drafts = {r['sku']: r for r in read(OUT / 'chairish-draft-worklist.json')}
    wes = read(OUT / 'wescover-public-verification.json')
    wes_rows = {r['sku']: r for r in wes['records']}
    packet = {r['sku']: r for r in read(ROOT / 'outputs/catalogue-saatchi-art-scope-20261104/publication-packet.json')['records']}
    photos = read(OUT / 'saatchi-original-summary.json')['products']
    headers = {r['photo_id']: r for r in read(OUT / 'saatchi-original-headers.json')}
    assert set(prior) == set(chair) == set(wes_rows) == set(packet) == skus
    assert wes['status'] == 'PASS' and all(r['public'] and r['identity_matches'] and r['price'] > 0 for r in wes_rows.values())
    assert len({r['native_id'] for r in chair.values()}) == 176
    assert len({r['native_item_id'] for r in wes_rows.values()}) == 176

    groups = {'BOLD-624D16148726', 'BOLD-EFBAEB31C2B1', 'BOLD-9278986A1A89', 'BOLD-7CDE8362BB51'}
    details = {'BOLD-449C4421ABD0', 'SQ2233720', 'BOLD-C0F5BF012CFC'}
    rows = []
    counts = collections.Counter()
    for sku in sorted(skus):
        old = prior[sku]
        product = products[old['catalogue_id']]
        c = copy.deepcopy(chair[sku])
        c['price_verified_at'] = chair_verification['verified_at']
        if sku in drafts:
            d = drafts[sku]
            # Do not perpetuate the stale PRICE_NOT_YET_UPDATED preparation label.
            d['native_status'] = c['native_status']
            d['price_verified_at'] = c['price_verified_at']
            c['state'] = 'Draft'
            c['saved_photo_count_historical'] = d['saved_photos_at_last_gallery_audit']
            c['gallery_count_needs_native_refresh'] = True
            c['next_action'] = ('ADD_GENUINE_SECOND_SELECTED_PHOTO_AND_VALIDATE_EXISTING_DRAFT'
                                if d['needs_second_photo'] else 'VALIDATE_AND_SUBMIT_EXISTING_DRAFT')
        else:
            assert 'PENDING_REVIEW' in c['native_status']
            c['state'] = 'Pending Review'
            c['next_action'] = 'AWAIT_CHAIRISH_REVIEW_AND_INSPECT_ANY_NATIVE_ACCOUNT_ISSUES'
        counts['chairish_' + c['state']] += 1
        counts[c['next_action']] += 1

        s = copy.deepcopy(old['saatchi'])
        s['native_id'] = packet[sku]['native_id']
        s['url'] = f"https://www.saatchiart.com/en-gb/studio/art/{s['native_id']}/overview" if s['native_id'] else None
        s['status_basis'] = 'Earlier native inventory reconciliation; no publication changes in this pass.'
        s['selected_originals'] = []
        if sku not in photos:
            if sku == 'BOLD-A57A49000891':
                s['state'] = 'Draft'
                s['next_action'] = 'COMPLETE_AND_PUBLISH_EXISTING_DRAFT_14388967'
            else:
                assert s['native_id'] and old['saatchi']['state'] == 'Published and for sale'
                s['state'] = 'Published and for sale'
                s['next_action'] = 'RETAIN_EXISTING_ARTWORK_ID'
        else:
            assert not s['native_id'], 'Never create another artwork when an existing ID is known.'
            s['state'] = 'Not uploaded'
            finding = photos[sku]
            s['selected_originals'] = [headers[p] for p in finding['photos']]
            if sku in groups:
                s['next_action'] = 'NATIVE_REVIEW_SELECTED_PAIR_PHOTO_WITH_EXPLICIT_SINGLE_PANEL_OFFER'
                s['photo_review'] = 'Photo shows both complete panels. Size passes; validate accurate individual-offer presentation. Group photographs are not asserted to be prohibited.'
            elif sku in details:
                s['next_action'] = 'NEEDS_QUALIFYING_FULL_VIEW_SELECTED_PHOTO'
                s['photo_review'] = 'Larger selected candidate is a cropped detail, not a full view of the product.'
            elif finding['portrait_candidates_for_native_test']:
                s['next_action'] = 'TEST_UNALTERED_PORTRAIT_ORIGINAL_IN_NATIVE_UPLOADER'
                s['photo_review'] = 'Full-view portrait is 1200 by 1600. Published guidance and native uploader orientation differ; native acceptance remains unverified.'
            else:
                assert not finding['originals_meeting_landscape_gate']
                s['next_action'] = 'NEEDS_HIGHER_RESOLUTION_SELECTED_ORIGINAL'
                s['photo_review'] = 'All selected Dropbox originals are below both checked orientation gates; no upscaling or padding performed.'
        counts['saatchi_' + s['state']] += 1
        counts[s['next_action']] += 1
        rows.append({
            'sku': sku, 'catalogue_id': product['id'], 'title': product['retail_name'],
            'app_url': f"http://127.0.0.1:8767/#{product['id']}", 'folder_url': product['folder_url'],
            'chairish': c, 'saatchi': s, 'wescover': copy.deepcopy(wes_rows[sku]),
        })

    assert counts['chairish_Pending Review'] == 152 and counts['chairish_Draft'] == 24
    assert counts['saatchi_Published and for sale'] == 98 and counts['saatchi_Draft'] == 1 and counts['saatchi_Not uploaded'] == 77
    assert counts['NEEDS_HIGHER_RESOLUTION_SELECTED_ORIGINAL'] == 69
    assert counts['NEEDS_QUALIFYING_FULL_VIEW_SELECTED_PHOTO'] == 3
    assert counts['NATIVE_REVIEW_SELECTED_PAIR_PHOTO_WITH_EXPLICIT_SINGLE_PANEL_OFFER'] == 4
    assert counts['TEST_UNALTERED_PORTRAIT_ORIGINAL_IN_NATIVE_UPLOADER'] == 1
    assert counts['ADD_GENUINE_SECOND_SELECTED_PHOTO_AND_VALIDATE_EXISTING_DRAFT'] == 7
    assert len([r for r in rows if r['saatchi']['native_id']]) == 99

    report = {
        'prepared_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'app_revision': source['revision'],
        'products': 176, 'new_native_publications_this_pass': 0,
        'wescover_public_verified_at': wes['completed_at'],
        'chairish_status_verified_at': chair_verification['verified_at'],
        'counts': dict(counts), 'records': rows,
        'browser_blocker': 'Browser form control failed or was interrupted before any publication edit. No additional submission or publication is claimed.',
        'photo_scope': 'Only current app-selected Listing originals; 127 distinct originals checked using bounded headers. No files, tags, primary selections or platform listings changed.',
        'publication_guards': [
            'Reconcile existing IDs before every create. Preserve the 99 Saatchi and 176 Chairish/Wescover bindings.',
            'Refresh historical gallery counts and native validation before Chairish submission.',
            'Limited Edition 50 and estimated year values are Saatchi-only prepared catalogue fields, not proof of native publication or numbered availability.',
            'Do not enable prints, invent stock/edition numbers, or upscale/pad photos to pass upload limits.',
        ],
    }
    write('chairish-draft-worklist.json', list(drafts.values()))
    write('completion-worklist.json', report)
    labels = {
        'AWAIT_CHAIRISH_REVIEW_AND_INSPECT_ANY_NATIVE_ACCOUNT_ISSUES': 'Await platform review; inspect account issues',
        'VALIDATE_AND_SUBMIT_EXISTING_DRAFT': 'Validate and submit existing draft',
        'ADD_GENUINE_SECOND_SELECTED_PHOTO_AND_VALIDATE_EXISTING_DRAFT': 'Second genuine selected photo needed; validate draft',
        'RETAIN_EXISTING_ARTWORK_ID': 'Retain existing published artwork',
        'COMPLETE_AND_PUBLISH_EXISTING_DRAFT_14388967': 'Complete existing draft 14388967 and publish',
        'NATIVE_REVIEW_SELECTED_PAIR_PHOTO_WITH_EXPLICIT_SINGLE_PANEL_OFFER': 'Review selected pair photo; clearly sell one identified panel',
        'NEEDS_QUALIFYING_FULL_VIEW_SELECTED_PHOTO': 'Qualifying full-view selected photo needed',
        'TEST_UNALTERED_PORTRAIT_ORIGINAL_IN_NATIVE_UPLOADER': 'Test full-view portrait in native uploader',
        'NEEDS_HIGHER_RESOLUTION_SELECTED_ORIGINAL': 'Higher-resolution selected original needed',
    }
    esc = html.escape
    def link(url, text):
        return f'<a href="{esc(url, quote=True)}" target="_blank" rel="noopener">{esc(text)}</a>' if url else esc(text)
    table = []
    for r in rows:
        c, s, w = r['chairish'], r['saatchi'], r['wescover']
        needs = c['state'] == 'Draft' or s['state'] != 'Published and for sale'
        table.append(f'''<tr data-needs="{int(needs)}"><td>{link(r['app_url'], r['title'])}<small>{esc(r['sku'])}</small>{link(r['folder_url'], 'Dropbox folder')}</td>
<td>{link(c['url'], c['state'])}<small>{esc(labels[c['next_action']])}</small><small>Price verified {esc(c['price_verified_at'][:16])} UTC</small></td>
<td>{link(s['url'], s['state'])}<small>{esc(labels[s['next_action']])}</small><small>{esc(s.get('photo_review', ''))}</small></td>
<td>{link(w['url'], 'Public product verified')}<small>SKU matched · positive price · InStock offer</small><small>{esc(w['checked_at'][:16])} UTC</small></td></tr>''')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Wall sculpture publication worklist</title>
<style>body{font:16px/1.5 system-ui;margin:32px;color:#24312a;background:#fafaf7}h1{font:36px Georgia;margin-bottom:10px}.summary{display:flex;gap:20px;flex-wrap:wrap}.summary div{padding:20px;background:#edf1e8;border-radius:8px}input,button{font:inherit;padding:9px;margin:15px 8px 15px 0}table{border-collapse:collapse;width:100%;background:white}th,td{text-align:left;vertical-align:top;padding:14px;border-bottom:1px solid #ddd}th{position:sticky;top:0;background:#e8eee2}small{display:block;color:#566058;margin-top:6px}a{color:#31593e}tr[hidden]{display:none}.note{max-width:1100px}</style>
<h1>Wall sculpture publication worklist</h1><p>Evidence reconciled 4 November 2026. 176 publication products; existing identities preserved.</p>
<div class="summary"><div><b>Wescover: 176 public</b><br>Fresh public SKU and available-offer verification</div><div><b>Chairish: 152 pending, 24 draft</b><br>Earlier native readback; no new submissions this pass</div><div><b>Saatchi: 98 published, 1 draft, 77 missing</b><br>Earlier inventory; no new publications this pass</div></div>
<p class="note">Browser form control failed or was interrupted before edits completed. Seventeen Chairish drafts have at least two saved photos in the historical gallery audit; seven have only one. These counts still need native refresh and final form validation. Pending Review is not Active.</p>
<p class="note">Saatchi originals: 69 products need higher-resolution selected originals; three larger candidates are cropped details; four have complete pair photographs needing accurate single-panel presentation and native review; one full-view portrait needs an orientation acceptance test. The existing Wave and Moonshadow I draft should be completed using its existing ID. No original was upscaled, padded or altered, and no extra images were tagged for Listing.</p>
<p class="note">Wescover checks establish public product identity, a positive USD price and an available offer. They do not certify checkout, every description, price alignment or the complete gallery. Saatchi and Chairish states are dated earlier native evidence, not fresh publication claims.</p>
<input id="search" type="search" placeholder="Find title or SKU" aria-label="Find title or SKU"><label><input id="needs" type="checkbox"> Show unfinished products only</label><p id="count"></p>
<table><thead><tr><th>Product / source</th><th>Chairish</th><th>Saatchi Art</th><th>Wescover</th></tr></thead><tbody>''' + ''.join(table) + '''</tbody></table>
<p>Machine-readable evidence: <a href="completion-worklist.json">completion-worklist.json</a> · <a href="wescover-public-verification.json">Wescover verification</a> · <a href="saatchi-original-summary.json">Saatchi original-photo audit</a></p>
<script>const rows=[...document.querySelectorAll('tbody tr')],search=document.querySelector('#search'),needs=document.querySelector('#needs');function filter(){let n=0;for(const row of rows){row.hidden=!(row.textContent.toLowerCase().includes(search.value.toLowerCase())&&(!needs.checked||row.dataset.needs==='1'));if(!row.hidden)n++}document.querySelector('#count').textContent=n+' of 176 products shown'}search.addEventListener('input',filter);needs.addEventListener('change',filter);filter();</script></html>'''
    (OUT / 'publication-worklist.html').write_text(page)
    print(json.dumps({'products': len(rows), 'native_publications': 0, 'counts': dict(counts)}, indent=2))


if __name__ == '__main__':
    main()
