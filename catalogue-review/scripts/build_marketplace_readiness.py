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
    wes = {r['sku']: r for r in load('wescover-current/public-176-final-audit.json')['records']}
    chair = {r['sku']: r for r in load('chairish-current/draft-receipts.json')}
    galleries = {r['sku']: r for r in load('saatchi-current/gallery-completion-receipts.json')}
    gallery_plan = {r['sku']: r for r in load('saatchi-current/prepared-galleries.json')['records']}
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
        c = chair[sku]
        chair_issues = ['Programme eligibility, production facts, stock, inclusive US shipping and discounts']
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
            overflow=len(gallery_plan.get(sku, {}).get('gallery_overflow', [])),
            dispatch_days=3)
        if sku == 'SQ0717348':
            saatchi.update(gallery_saved=True, gallery_count=3, gallery_target=3)
        rows.append(dict(sku=sku, title=record['title'], catalogue_id=record['catalogue_id'],
            app_url='http://127.0.0.1:8767/#' + record['catalogue_id'], sapr_2972=sapr,
            in6192=dict(state='Saved draft only', url=in_drafts[sku], dispatch_days=10 if sku == 'FF-1-70.50' else 3),
            wescover=dict(state='Customer-facing page verified', url=wes[sku]['url'], dispatch_days=10),
            chairish=dict(state='Saved draft; not submitted', url=c['url'], dispatch_days=3,
                outstanding=chair_issues, overflow=len(c.get('over_limit_photo_ids', [])),
                undersized=len(c.get('below_minimum_photo_ids', []))), saatchi=saatchi))
    assert len(rows) == 176 and len({r['sku'] for r in rows}) == 176
    counts = dict(sapr=dict(Counter(r['sapr_2972']['state'] for r in rows)),
        wescover_pages=len(wes), in6192_drafts=len(rows), chairish_drafts=len(chair),
        saatchi=dict(Counter(r['saatchi']['state'] for r in rows)),
        saatchi_draft_galleries_saved=len(galleries))
    data = dict(generated_utc=datetime.now(timezone.utc).isoformat(), counts=counts,
        basis='Saved channel receipts; see timestamps and scope in current-publication-status.json.',
        limitations=['Wescover customer-facing checks used a creator-authenticated browser.',
            'Accepted drafts and submitted records are not automatically public listings.',
            'Existing eBay Echo pair is preserved separately and does not substitute for the individual products.',
            'Saatchi local-storage write errors currently prevent completing the two pending saves and remaining galleries.'],
        records=rows)
    (root / 'per-item-channel-checklist.json').write_text(json.dumps(data, indent=2) + '\n')
    esc = lambda value: html.escape(str(value))
    def cell(channel):
        label = esc(channel['state'])
        if channel.get('url'):
            label = f'<a href="{esc(channel["url"])}" target="_blank" rel="noopener">{label}</a>'
        if channel.get('dispatch_days'):
            label += f'<small>{channel["dispatch_days"]} working days</small>'
        if channel.get('reason'):
            label += '<small>' + esc(channel['reason']) + '</small>'
        return label
    table_rows = []
    for r in rows:
        s = r['saatchi']
        gallery = f'{s["gallery_count"]} saved photos' if s['gallery_saved'] else (
            f'Gallery pending ({s["gallery_target"]} planned)' if s['gallery_target'] else 'Qualifying primary needed')
        table_rows.append('<tr><td><a href="' + esc(r['app_url']) + '">' + esc(r['title']) + '</a><small>' + esc(r['sku']) + '</small></td>'
            + '<td>' + cell(r['sapr_2972']) + '</td><td>' + cell(r['in6192']) + '</td><td>' + cell(r['wescover']) + '</td>'
            + '<td>' + cell(r['chairish']) + '<small>' + '; '.join(map(esc, r['chairish']['outstanding'])) + '</small></td>'
            + '<td>' + cell(s) + '<small>' + esc(gallery) + (f'; {s["overflow"]} photos exceed platform cap' if s['overflow'] else '') + '</small></td></tr>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boldstone — per-item channel checklist</title><style>body{font:16px/1.5 system-ui;margin:2rem;color:#25332d;background:#f8f7f3}h1{font-family:Georgia;font-size:2rem}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;vertical-align:top;padding:.75rem;border:1px solid #ddd}th{position:sticky;top:0;background:#e8eee6}small{display:block;color:#5a625d;margin-top:.3rem}a{color:#315d42}input{font:inherit;padding:.6rem;width:min(30rem,90%);margin:1rem 0}.scroll{overflow:auto}li{margin:.3rem 0}</style>
<h1>Wall sculptures — channel checklist</h1><p>176 included catalogue records. Dispatch: three working days where required, ten elsewhere. Transit is additional.</p>'''
    page += '<p>Generated ' + esc(data['generated_utc']) + '. <a href="current-publication-status.json">Detailed evidence and timestamps</a></p>'
    page += '<p><strong>eBay sapr_2972:</strong> 91 new published + 19 existing individual listings revised; 66 shipping exceptions remain drafts. <strong>in6192:</strong> 176 saved drafts. <strong>Wescover:</strong> 176 customer-facing pages checked. <strong>Chairish:</strong> 176 unsubmitted drafts. <strong>Saatchi:</strong> 1 published, 97 incomplete drafts, 78 without a draft.</p>'
    page += '<ul>' + ''.join('<li>' + esc(x) + '</li>' for x in data['limitations']) + '</ul>'
    page += '<label>Find a sculpture or outstanding task<br><input id="search" type="search" placeholder="Name, SKU, shipping, primary…"></label><p id="count">176 records</p><div class="scroll"><table><thead><tr><th>Sculpture</th><th>eBay sapr_2972</th><th>eBay in6192</th><th>Wescover</th><th>Chairish</th><th>Saatchi Art</th></tr></thead><tbody>'
    page += ''.join(table_rows) + '''</tbody></table></div><script>const input=document.querySelector('#search'),rows=[...document.querySelectorAll('tbody tr')];input.addEventListener('input',()=>{const q=input.value.toLowerCase();let n=0;for(const row of rows){row.hidden=!row.textContent.toLowerCase().includes(q);if(!row.hidden)n++}document.querySelector('#count').textContent=n+' of '+rows.length+' records'});</script></html>'''
    (root / 'per-item-channel-checklist.html').write_text(page)
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
