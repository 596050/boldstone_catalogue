"""Build an item-level channel checklist from exact accepted manifests and receipts."""
from collections import Counter
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    load = lambda name: json.loads((root / name).read_text())
    records = load('saatchi-current/prepared-catalogue.json')['records']
    status = load('current-publication-status.json')
    wes_submitted = status['wescover'].get('latest_description_submission', {}).get('status') == 'NATIVE_SUBMISSION_RECEIVED'
    copy_root = root / 'catalogue-copy-disclosures'
    def copy_receipts(name):
        path = copy_root / name
        return {r['sku']: r for r in json.loads(path.read_text())} if path.exists() else {}
    copy_checks = {
        'in6192': copy_receipts('ebay-in6192-description-readbacks.json'),
        'wescover': copy_receipts('wescover-copy-receipts.json'),
        'chairish': copy_receipts('chairish-copy-receipts.json'),
        'marketplace': copy_receipts('marketplace-copy-receipts.json'),
        'saatchi': copy_receipts('saatchi-copy-receipts.json'),
        'tiktok': copy_receipts('tiktok-copy-receipts.json'),
    }
    sapr_active_copy = copy_receipts('ebay-sapr_2972_pre_submit-description-readbacks.json')
    sapr_draft_copy = copy_receipts('ebay-sapr_2972_drafts-description-readbacks.json')
    draft_specifics = copy_receipts('ebay-sapr-specifics-receipts.json')
    chair_colours = copy_receipts('chairish-colour-receipts.json')
    chair_fulfilment = copy_receipts('chairish-fulfilment-receipts.json')
    specifics_path = root / 'ebay-existing-specifics-staged-readbacks.json'
    specifics = {r['sku']: r for r in json.loads(specifics_path.read_text())} if specifics_path.exists() else {}
    assert not (set(sapr_active_copy) & set(sapr_draft_copy)), 'An offer cannot be both active and draft'
    wes = {r['sku']: r for r in load('wescover-current/public-176-final-audit.json')['records']}
    chair = {r['sku']: r for r in load('chairish-current/draft-receipts.json')}
    chair_plan = {r['sku']: r for r in load('chairish-current/prepared-native-drafts.json')['records']}
    galleries = {r['sku']: r for r in load('saatchi-current/gallery-completion-receipts.json')}
    gallery_plan = {r['sku']: r for r in load('saatchi-current/prepared-galleries.json')['records']}
    pending_saves = {r['sku'] for r in status['saatchi']['gallery_progress']['in_flight']
                     if r['phase'] == 'SAVE_REQUESTED'}
    in_drafts = {r['cells'][4]: r['link'] for r in load('ebay-in6192-draft-readback.json')
                 if len(r.get('cells', [])) > 4 and r.get('link')}
    live = {}
    for batch in status['ebay']['sapr_2972']['published_batches']:
        manifest = load(batch['manifest'])
        batch_rows = manifest['rows'] if isinstance(manifest, dict) else manifest
        assert len(batch_rows) == batch['count']
        for row in batch_rows:
            if row['sku'] in live:
                raise ValueError('Duplicate new publication SKU: ' + row['sku'])
            live[row['sku']] = dict(state='New listing published',
                dispatch_days=batch['handling_working_days'], evidence=batch['receipt'])
    for row in status['ebay']['sapr_2972']['published_receipts']:
        if row['sku'] in live:
            raise ValueError('Single publication also occurs in a batch')
        live[row['sku']] = dict(state='New listing published', url=row['url'],
            dispatch_days=row['handling_working_days'], evidence=row['proof'])
    assert len(live) == 91
    old = {}
    old_rows = load('ebay-existing20-revision-plan.json')
    for row in old_rows:
        assert 'Simple Delivery allows dispatch times of up to 3 working days.' in row['row']['text']
        match = row['match']
        if match['scope'] == 'individual':
            assert len(match['catalogue_ids']) == 1
            old[match['catalogue_ids'][0]] = dict(state='Existing listing revised',
                url=match['ebay_url'], dispatch_days=3,
                evidence='ebay-existing20-revised-live.txt')
    assert len(old) == 19
    oversized = {r['sku']: r for r in load('ebay-sapr-oversized-exceptions.json')}
    rows = []
    for record in records:
        sku = record['sku']
        assert sku in wes and sku in chair and sku in in_drafts
        sapr = live.get(sku) or old.get(record['catalogue_id'])
        if sapr is None:
            sapr = dict(state='Draft: shipping decision required', dispatch_days=None,
                reason='No suitable oversized option in native form' if sku in oversized else 'Freight/manual shipping required')
        if sku in sapr_active_copy:
            sapr.update(latest_description='Staged and reopened; final terms acceptance pending, not submitted',
                latest_description_at=sapr_active_copy[sku]['at'])
        elif sku in sapr_draft_copy:
            sapr.update(latest_description='Saved and reopened; draft only',
                latest_description_at=sapr_draft_copy[sku]['at'])
        if sku in specifics:
            sapr['specification_corrections'] = (
                f"{len(specifics[sku]['changes'])} field corrections saved and reopened; final submission pending")
        if sku in draft_specifics:
            receipt = draft_specifics[sku]
            assert receipt['status'] == 'DRAFT_SAVED_AND_REOPENED'
            assert sku not in live and record['catalogue_id'] not in old
            sapr['specification_corrections'] = (
                'Artist, height and width saved and reopened in the draft'
                if len(receipt['fields']) == 3 else
                'Artist saved and reopened; height/width orientation still needs confirmation')
            sapr['url'] = receipt['url']
        c = chair[sku]
        chair_issues = [
            'Programme eligibility, origin, production capacity/stock, inclusive US shipping and discounts'
            if sku in chair_fulfilment else
            'Programme eligibility, actual production year/origin, stock, inclusive US shipping and discounts']
        if sku not in chair_colours:
            chair_issues.append('Verify dominant colour')
        if c.get('structured_dimension_axes_pending'):
            chair_issues.append('Confirm width/height orientation')
        if c.get('needs_second_photo'):
            chair_issues.append('Second qualifying selected photograph')
        if c.get('primary_reference_requires_review'):
            chair_issues.append('Qualifying product primary photograph')
        native_id = record.get('native_artwork_id')
        saatchi = dict(state='Published existing artwork' if sku == 'SQ0717348' else
            'Draft: production details incomplete' if native_id else 'No draft: qualifying primary needed',
            artwork_id=native_id, url=f'https://www.saatchiart.com/en-gb/studio/art/{native_id}/overview' if native_id else None,
            gallery_saved=sku in galleries, gallery_count=galleries.get(sku, {}).get('photos'),
            gallery_target=gallery_plan.get(sku, {}).get('expected_photo_count'),
            gallery_save_unconfirmed=sku in pending_saves,
            overflow=len(gallery_plan.get(sku, {}).get('gallery_overflow', [])),
            dispatch_days=3, dispatch_basis='Saved' if sku == 'SQ0717348' else 'Planned policy')
        if sku == 'SQ0717348':
            saatchi.update(gallery_saved=True, gallery_count=3, gallery_target=3)
        rows.append(dict(sku=sku, title=record['title'], catalogue_id=record['catalogue_id'],
            app_url='http://127.0.0.1:8767/#' + record['catalogue_id'], sapr_2972=sapr,
            in6192=dict(state='Saved draft only', url=in_drafts[sku], dispatch_days=10 if sku == 'FF-1-70.50' else 3),
            wescover=dict(state='Customer-facing page verified', url=wes[sku]['url'], dispatch_days=10),
            chairish=dict(state='Saved draft; not submitted', url=c['url'],
                dispatch_days=chair_plan[sku]['dispatch_working_days'], dispatch_basis='Saved description dispatch',
                dimensions_verified=c.get('structured_dimensions_verified', False),
                outstanding=chair_issues, overflow=len(c.get('over_limit_photo_ids', [])),
                undersized=len(c.get('below_minimum_photo_ids', []))), saatchi=saatchi))
        rows[-1]['marketplace'] = dict(state='Existing listing; latest copy pending')
        if sku in chair_colours:
            colour = chair_colours[sku]
            assert colour['status'] == 'SAVED_REOPENED_DRAFT_ONLY'
            rows[-1]['chairish']['dominant_colour'] = colour['colour']
            rows[-1]['chairish']['dominant_colour_verified_at'] = colour['at']
        if sku in chair_fulfilment:
            receipt = chair_fulfilment[sku]
            assert receipt['status'] == 'SAVED_REOPENED_DRAFT_ONLY'
            rows[-1]['chairish'].update(production_setting='Made to order; native lead time 14 days',
                production_setting_verified_at=receipt['at'], dispatch_days=10)
        rows[-1]['tiktok'] = dict(state='Current native description not yet verified')
        for channel, receipts in copy_checks.items():
            receipt = receipts.get(sku)
            entry = rows[-1][channel]
            entry['latest_description'] = 'Saved and reopened' if receipt else 'Not yet verified'
            entry['latest_description_at'] = receipt.get('at') if receipt else None
            if channel == 'wescover' and receipt:
                entry['latest_description'] += ('; submitted for review, public update pending' if wes_submitted else
                                               '; global submission pending')
            if channel == 'saatchi' and receipt:
                entry['latest_description'] += '; published artwork record, public description section not rendered in this browser'
            if channel == 'marketplace' and receipt:
                entry.update(state='Existing listing updated and reopened', url=receipt['url'])
            if channel == 'tiktok' and receipt:
                labels = {
                    'SAVED_REOPENED_LIVE': 'Live revision saved and reopened',
                    'DRAFT_SAVED_REOPENED': 'Saved draft reopened; product not activated',
                    'SUBMITTED_FOR_REVIEW': 'Revision submitted; approval and readback pending',
                    'ALREADY_PRESENT_REOPENED': 'Existing wording reopened and verified',
                }
                entry.update(state=labels[receipt['status']], url=receipt.get('edit_url'),
                    latest_description=labels[receipt['status']],
                    latest_description_at=receipt.get('verified_at', receipt['at']),
                    product_id=receipt['product_id'])
    assert len(rows) == 176 and len({r['sku'] for r in rows}) == 176
    counts = dict(sapr=dict(Counter(r['sapr_2972']['state'] for r in rows)),
        wescover_pages=len(wes), in6192_drafts=len(rows), chairish_drafts=len(chair),
        saatchi=dict(Counter(r['saatchi']['state'] for r in rows)),
        saatchi_draft_galleries_saved=len(galleries),
        latest_descriptions={channel: len(receipts) for channel, receipts in copy_checks.items()})
    counts['sapr_latest_descriptions'] = dict(active_offers_staged=len(sapr_active_copy),
        remaining_drafts_saved=len(sapr_draft_copy))
    counts['tiktok_description_states'] = dict(Counter(r['tiktok']['state'] for r in rows))
    counts['sapr_specification_corrections'] = dict(offers_staged=len(specifics),
        fields=sum(len(r['changes']) for r in specifics.values()),
        publication='NOT_SUBMITTED')
    counts['sapr_draft_specifics'] = dict(drafts_saved_and_reopened=len(draft_specifics),
        fields_verified=sum(len(r['fields']) for r in draft_specifics.values()),
        publication='DRAFT_ONLY')
    counts['chairish_dimensions'] = dict(
        complete=sum(r['chairish']['dimensions_verified'] for r in rows),
        orientation_pending=sum(bool(r.get('structured_dimension_axes_pending')) for r in chair.values()))
    counts['chairish_colours'] = dict(saved_and_reopened=len(chair_colours),
        remaining_to_review=len(chair)-len(chair_colours), publication='DRAFT_ONLY')
    counts['chairish_made_to_order'] = dict(saved_and_reopened=len(chair_fulfilment),
        publication='DRAFT_ONLY')
    gallery_note = (
        f"Saatchi: {len(galleries)} of {len(gallery_plan)} prepared draft galleries saved and verified. "
        + (f"{len(pending_saves)} gallery saves remain unconfirmed. " if pending_saves else
           'No unconfirmed gallery saves. ')
        + 'Artwork production details and publication remain separate requirements.')
    data = dict(generated_utc=datetime.now(timezone.utc).isoformat(), counts=counts,
        basis='Saved channel receipts; see timestamps and scope in current-publication-status.json.',
        limitations=['Wescover customer-facing checks used a creator-authenticated browser.',
            'Accepted drafts and submitted records are not automatically public listings.',
            'Existing eBay Echo pair is preserved separately and does not substitute for the individual products.',
            gallery_note,
            'Latest description checks cover customisation with Sally Price, applicable handmade finish variation and named companion pieces.',
            'Latest copy saved in a draft or creator form is distinct from public publication. '
            + ('All 176 Wescover description updates were submitted; public review remains pending.' if wes_submitted else
               'Wescover changes still need global submission.')],
        records=rows)
    reconciliation_path = copy_root / 'included-record-reconciliation.json'
    if reconciliation_path.exists():
        data['catalogue_reconciliation'] = json.loads(reconciliation_path.read_text())
        data['limitations'].append(
            'This table covers the 176 prepared channel records. The app has 178 included records; '
            'Moon and Shellwave I Water Feature has owner-deferred photography. The Yellow and Grey '
            'Wall Circle has only a historical primary reference absent from the current Dropbox inventory; '
            'its original could not be fetched. Its existing website record must be reused if restored.')
    (root / 'per-item-channel-checklist.json').write_text(json.dumps(data, indent=2) + '\n')
    esc = lambda value: html.escape(str(value))
    def cell(channel):
        label = esc(channel['state'])
        if channel.get('url'):
            label = f'<a href="{esc(channel["url"])}" target="_blank" rel="noopener">{label}</a>'
        if channel.get('dispatch_days'):
            prefix = channel.get('dispatch_basis', 'Saved dispatch')
            label += f'<small>{prefix}: {channel["dispatch_days"]} working days</small>'
        if channel.get('reason'):
            label += '<small>' + esc(channel['reason']) + '</small>'
        if channel.get('latest_description'):
            label += '<small>Latest description: ' + esc(channel['latest_description']) + '</small>'
        if channel.get('specification_corrections'):
            label += '<small>' + esc(channel['specification_corrections']) + '</small>'
        if channel.get('dominant_colour'):
            label += '<small>Dominant colour saved and reopened: ' + esc(channel['dominant_colour']) + '</small>'
        if channel.get('production_setting'):
            label += '<small>' + esc(channel['production_setting']) + ' — saved and reopened</small>'
        return label
    table_rows = []
    for r in rows:
        s = r['saatchi']
        gallery = (f'{s["gallery_count"]} saved photo' + ('s' if s['gallery_count'] != 1 else '')) if s['gallery_saved'] else (
            f'Save unconfirmed ({s["gallery_target"]} photos staged)' if s['gallery_save_unconfirmed'] else
            f'Gallery pending ({s["gallery_target"]} planned)' if s['gallery_target'] else 'Qualifying primary needed')
        table_rows.append('<tr><td><a href="' + esc(r['app_url']) + '">' + esc(r['title']) + '</a><small>' + esc(r['sku']) + '</small></td>'
            + '<td>' + cell(r['sapr_2972']) + '</td><td>' + cell(r['in6192']) + '</td><td>' + cell(r['wescover']) + '</td>'
            + '<td>' + cell(r['chairish']) + '<small>' + '; '.join(map(esc, r['chairish']['outstanding'])) + '</small></td>'
            + '<td>' + cell(s) + '<small>' + esc(gallery) + (f'; {s["overflow"]} photos exceed platform cap' if s['overflow'] else '') + '</small></td>'
            + '<td>' + cell(r['marketplace']) + '</td><td>' + cell(r['tiktok']) + '</td></tr>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boldstone — per-item channel checklist</title><style>body{font:16px/1.5 system-ui;margin:2rem;color:#25332d;background:#f8f7f3}h1{font-family:Georgia;font-size:2rem}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;vertical-align:top;padding:.75rem;border:1px solid #ddd}th{position:sticky;top:0;background:#e8eee6}small{display:block;color:#5a625d;margin-top:.3rem}a{color:#315d42}input{font:inherit;padding:.6rem;width:min(30rem,90%);margin:1rem 0}.scroll{overflow:auto}li{margin:.3rem 0}</style>
<h1>Wall sculptures — channel checklist</h1><p>176 prepared channel records. Dispatch: three working days where required, ten elsewhere. Transit is additional.</p>'''
    page += '<p>Generated ' + esc(data['generated_utc']) + '. <a href="current-publication-status.json">Detailed evidence and timestamps</a></p>'
    page += '<p><strong>eBay sapr_2972:</strong> 91 new published + 19 existing individual listings revised; 66 shipping exceptions remain drafts. <strong>in6192:</strong> 176 saved drafts. <strong>Wescover:</strong> 176 customer-facing pages checked. <strong>Chairish:</strong> 176 unsubmitted drafts. <strong>Saatchi:</strong> 1 published, 97 incomplete drafts, 78 without a draft.</p>'
    page += '<ul>' + ''.join('<li>' + esc(x) + '</li>' for x in data['limitations']) + '</ul>'
    if data.get('catalogue_reconciliation'):
        page += '<p><a href="catalogue-copy-disclosures/included-record-reconciliation.json">App inclusion and missing-record reconciliation</a></p>'
    page += '<label>Find a sculpture or outstanding task<br><input id="search" type="search" placeholder="Name, SKU, shipping, primary…"></label><p id="count">176 records</p><div class="scroll"><table><thead><tr><th>Sculpture</th><th>eBay sapr_2972</th><th>eBay in6192</th><th>Wescover</th><th>Chairish</th><th>Saatchi Art</th><th>Facebook Marketplace</th><th>TikTok</th></tr></thead><tbody>'
    page += ''.join(table_rows) + '''</tbody></table></div><script>const input=document.querySelector('#search'),rows=[...document.querySelectorAll('tbody tr')];input.addEventListener('input',()=>{const q=input.value.toLowerCase();let n=0;for(const row of rows){row.hidden=!row.textContent.toLowerCase().includes(q);if(!row.hidden)n++}document.querySelector('#count').textContent=n+' of '+rows.length+' records'});</script></html>'''
    (root / 'per-item-channel-checklist.html').write_text(page)
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
