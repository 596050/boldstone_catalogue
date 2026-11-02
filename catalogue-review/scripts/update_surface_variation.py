"""Apply only the owner's handmade-finish disclosure, using field versions.

Fresh source snapshots and item receipts make interrupted runs resumable without
overwriting unrelated catalogue edits or changing accepted channel identities.
"""
import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from channel_content import (values, has_surface_effect, surface_variation_copy,
                             complete_description, description_html, SURFACE_VARIATION,
                             customisation_copy, CUSTOMISATION)
from companion_groups import companion_notes, apply_companion_note

BASE = 'http://127.0.0.1:8767'
AUTHORITY = ('Owner instruction 1 November 2026: all listings with surface effects '
             'must explain that the pattern varies and differs from the photographs '
             'because each piece is handmade.')


def fetch(path):
    with urlopen(BASE + path, timeout=120) as response:
        return json.load(response)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('output', type=Path)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--companions', action='store_true')
    ap.add_argument('--customisation', action='store_true')
    args = ap.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    def read(name): return json.loads((out / name).read_text())
    def write(name, data):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    if not (out / 'plan.json').exists():
        before = fetch('/api/specifications')
        write('app-before.json', before)
        notes = companion_notes(before) if args.companions else {}
        write('companion-notes.json', notes)
        products = []
        for p in before['products']:
            effect = has_surface_effect(p)
            field = next(f for f in p['listing_fields'] if f['key'] == 'Description')
            target = surface_variation_copy(field['value'], effect)
            if args.companions:
                target = apply_companion_note(target, notes.get(p['id']))
            if args.customisation:
                target = customisation_copy(target)
            if target != field['value']:
                products.append({'catalogue_id': p['id'], 'name': p['name'],
                                 'surface_effect': effect, 'before': field, 'value': target})
        authority = AUTHORITY + (' Owner also requested a line identifying companion pieces for sculptures that form pairs or groups.' if args.companions else '')
        authority += (' Owner also requested that every design can be customised and new commissions created with designer Sally Price.' if args.customisation else '')
        write('plan.json', {'authority': authority, 'companions': args.companions,
                           'customisation': args.customisation,
                           'created_utc': datetime.now(timezone.utc).isoformat(),
                           'source_hash': before['source_hash'], 'products': products})
    plan, before = read('plan.json'), read('app-before.json')
    notes = read('companion-notes.json') if (out / 'companion-notes.json').exists() else {}
    if not args.apply:
        print(json.dumps({'planned_description_updates': len(plan['products'])}))
        return
    boot = fetch('/api/bootstrap')
    assert boot['source']['register_sha256'] == plan['source_hash']
    current = {p['id']: p for p in fetch('/api/specifications')['products']}
    receipts = read('app-receipts.json') if (out / 'app-receipts.json').exists() else []
    for p in plan['products']:
        field = next(f for f in current[p['catalogue_id']]['listing_fields'] if f['key'] == 'Description')
        if field['value'] == p['value']:
            continue
        assert (field['value'], field['version']) == (p['before']['value'], p['before']['version']), ('Concurrent description edit', p['catalogue_id'])
        payload = {'kind': 'field', 'product_id': p['catalogue_id'], 'item_id': 'Description',
                   'version': field['version'], 'data': {
                       'decision': 'edit', 'value': p['value'], 'certainty': 'confirmed',
                       'evidence': plan['authority'],
                       'notes': 'Handmade surface-effect disclosure. Other specifications, price, photos and identity preserved.'}}
        req = Request(BASE + '/api/reviews', data=json.dumps(payload).encode(), method='POST',
                      headers={'Content-Type': 'application/json', 'Origin': BASE,
                               'X-Review-Token': boot['csrf_token']})
        with urlopen(req, timeout=120) as response:
            result = json.load(response)
        assert result['data']['value'] == p['value']
        receipts.append({'catalogue_id': p['catalogue_id'], 'before': field, 'after': result})
        write('app-receipts.json', receipts)
    after = fetch('/api/specifications')
    byid = {p['id']: p for p in after['products']}
    assert len(byid) == len(before['products']) == 181
    for old in before['products']:
        new = byid[old['id']]
        assert new['costing'] == old['costing'] and new['photos'] == old['photos']
        assert (new['name'], new['listing_decision']) == (old['name'], old['listing_decision'])
        for key, value in values(old).items():
            expected = surface_variation_copy(value, has_surface_effect(old)) if key == 'Description' else value
            if key == 'Description' and plan.get('companions'):
                expected = apply_companion_note(expected, notes.get(old['id']))
            if key == 'Description' and plan.get('customisation'):
                expected = customisation_copy(expected)
            assert values(new)[key] == expected, (old['id'], key)
        assert values(new)['Description'].count(SURFACE_VARIATION) == int(has_surface_effect(new))
        if plan.get('customisation'):
            assert values(new)['Description'].count(CUSTOMISATION) == 1
    write('app-after.json', after)
    prepared_path = out.parent / 'current-prepared-catalogue.json'
    prepared = json.loads(prepared_path.read_text())
    if not (out / 'prepared-before.json').exists():
        write('prepared-before.json', prepared)
    prior = copy.deepcopy(prepared)
    for record in prepared['records']:
        p = byid[record['catalogue_id']]
        assert record['surface_effect'] == has_surface_effect(p), ('Finish classification changed', p['id'])
        record['description_text'] = values(p)['Description']
        record['description_html'] = description_html(record['description_text'])
        record['channel_descriptions'] = {
            'ebay_simple_delivery': complete_description(p, record['sku'], 3, channel='ebay'),
            'ebay_custom_delivery': complete_description(p, record['sku'], 10, channel='ebay'),
            'tiktok_draft': complete_description(p, record['sku'], 10, channel='tiktok')}
    for old, new in zip(prior['records'], prepared['records']):
        assert all(old[k] == new[k] for k in old if k not in ('description_text', 'description_html', 'channel_descriptions'))
    prepared['surface_variation_update_utc'] = datetime.now(timezone.utc).isoformat()
    prepared_path.write_text(json.dumps(prepared, ensure_ascii=False, indent=2) + '\n')
    result = {'status': 'PASS_VERSION_CHECKED_APP_READBACK', 'products_checked': len(byid),
              'description_updates': len(plan['products']),
              'included_surface_effect_products': sum(r['surface_effect'] for r in prepared['records']),
              'companion_listings': len(notes),
              'customisation_products': len(byid) if plan.get('customisation') else 0,
              'source_hash': after['source_hash'], 'unrelated_values_preserved': True,
              'wording': SURFACE_VARIATION, 'verified_utc': datetime.now(timezone.utc).isoformat()}
    write('app-verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
