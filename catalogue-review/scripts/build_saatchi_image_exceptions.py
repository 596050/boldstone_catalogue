"""Render original-image exceptions alongside subsequently verified draft alternatives."""
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sys


def main():
    root = Path(sys.argv[1]).resolve()
    load = lambda name: json.loads((root / name).read_text())
    audit = load('primary-original-final-audit.json')
    alternatives = {r['sku']: r for r in load('listing-alternative-selection.json')}
    records = {r['sku']: r for r in load('prepared-catalogue.json')['records']}
    receipts = {r['sku']: r for r in load('primary-draft-receipts.json')}
    resolved = 0
    esc = lambda s: html.escape(str(s))
    cards = []
    for row in audit['rows']:
        sku = row['sku']
        record = records[sku]
        primary = next(p for p in record['photos'] if p['id'] == row['photo_id'])
        selected = alternatives.get(sku)
        assert row['verified'] and row['content_hash_matches_catalogue']
        if selected:
            native_id = str(selected['artwork_id'])
            assert native_id == str(record['native_artwork_id'])
            assert native_id == str(receipts[sku]['artwork_id'])
            resolved += 1
            status = ('A qualifying selected listing alternative is saved in Saatchi draft '
                      f'{native_id}. The app primary is unchanged. This is not publication approval.')
        else:
            assert not record.get('native_artwork_id')
            count = len(row['qualifying_selected_alternatives'])
            status = (f'{count} other selected photos meet the size check; none is an approved '
                      'replacement primary. A suitable product photograph is still needed.')
        dimensions = ' × '.join(str(x) for x in row['original_dimensions'])
        card = '<article><h2>' + esc(row['title']) + '</h2><p>' + esc(sku) + '</p>'
        card += '<img loading="lazy" src="' + esc(primary['url']) + '" alt="Current catalogue primary for ' + esc(row['title']) + '">'
        card += '<p>Catalogue primary: ' + dimensions + ' px; verified original below Saatchi’s minimum.</p><p>' + esc(status) + '</p>'
        if selected:
            card += '<img loading="lazy" src="' + esc(selected['photo']['url']) + '" alt="Saved Saatchi listing alternative for ' + esc(row['title']) + '">'
            card += '<p><a href="' + esc(selected['native_url']) + '">Open existing Saatchi draft</a></p>'
        card += '<p><a href="http://127.0.0.1:8767/#' + esc(row['catalogue_id']) + '">Open catalogue record</a></p></article>'
        cards.append(card)
    assert len(cards) == 97 and resolved == 19
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Saatchi primary-image exceptions</title><style>body{font:16px/1.5 system-ui;margin:32px;background:#f6f5ef;color:#25312c}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{padding:16px;background:white;border:1px solid #ddd;border-radius:8px}img{width:100%;height:230px;object-fit:contain}h2{font-size:18px}a{color:#315c45}</style>
<h1>Saatchi primary-image exceptions</h1><p>97 catalogue primaries fail the native image minimum: <strong>19 have saved Saatchi alternatives; 78 still need a suitable primary.</strong> App primary choices remain unchanged.</p>
<p>Native threshold used: 1500 px wide and 1200 px high. Original identities and hashes were verified; no larger version of these same files was found. Images below load from existing website URLs.</p>'''
    page += '<p>Updated ' + esc(datetime.now(timezone.utc).isoformat()) + ' · <a href="../per-item-channel-checklist.html">All 176 channel records</a></p><main>'
    page += ''.join(cards) + '</main></html>'
    (root / 'primary-image-exceptions.html').write_text(page)
    print(json.dumps({'originals_below_minimum': len(cards), 'saved_alternative_drafts': resolved,
                      'remaining_primary_needed': len(cards) - resolved}))


if __name__ == '__main__':
    main()
