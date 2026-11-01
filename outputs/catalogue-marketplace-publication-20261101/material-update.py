"""Version-checked owner material/copy update; no price or image mutations."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, copy, html, json, re, urllib.request

OUT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'
SOURCE = OUT.parent / 'tiktok-ebay-upload-20261101/catalogue-snapshot-material-before.json'
MATERIAL = 'Made from a gypsum-based material.'
EFFECT = 'A decorative surface effect is applied to create the finish shown.'

def read(p):
    return json.loads(p.read_text())

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=120) as response:
        return json.load(response)

def fields(p):
    return {f['key']: f for f in p['fields'] + p['listing_fields']}

def plain_copy(text, effect):
    text = re.sub(r'(?m)^(?:Material|Surface effect):.*\n?', '', text).strip()
    points = 'Material: ' + MATERIAL + '\n'
    if effect:
        points += 'Surface effect: ' + EFFECT + '\n'
    if 'Dimensions:' in text:
        text = text.replace('Dimensions:', points + 'Dimensions:', 1)
    else:
        text += '\n\n' + points.rstrip()
    assert text.count(MATERIAL) == 1
    assert text.count(EFFECT) == int(effect)
    assert not re.search(r'GFRC|Jesmonite|Royal Mail|Tracked 48', text, re.I)
    return text

def html_copy(text, effect):
    text = re.sub(r'<li>\s*<strong>(?:Material|Surface effect):</strong>.*?</li>', '', text, flags=re.I|re.S)
    points = '<li><strong>Material:</strong> ' + MATERIAL + '</li>'
    if effect:
        points += '<li><strong>Surface effect:</strong> ' + EFFECT + '</li>'
    if '<ul>' in text:
        text = text.replace('<ul>', '<ul>' + points, 1)
    else:
        text += '<ul>' + points + '</ul>'
    assert text.count(MATERIAL) == 1 and text.count(EFFECT) == int(effect)
    assert not re.search(r'GFRC|Jesmonite|Royal Mail|Tracked 48', text, re.I)
    return text

def prepare():
    before = read(SOURCE)
    catalogue = read(OUT.parent / 'marketplace-completion-20261101/tiktok-prepared-catalogue.json')
    products = {p['id']: p for p in before['products']}
    plan = {'created_utc': datetime.now(timezone.utc).isoformat(), 'source_cutoff': before['event_cutoff'],
            'authority': 'Owner instruction 1 November 2026: gypsum-based material point and applied surface-effect point on all wall-sculpture platforms; no duplicates.',
            'products': []}
    for p in before['products']:
        fs = fields(p)
        finish_ids = [x['id'] for x in p['costing']['inputs']['finishes']]
        effect = any(x != 'white' for x in finish_ids)
        old_material = fs['Material / finish']['value']
        assert old_material.startswith('GFRC') or old_material.startswith('Gypsum-based material')
        new_material = re.sub(r'^GFRC', 'Gypsum-based material', old_material)
        new_material = re.sub(r'(?<!imitation )gold[- ]leaf', 'imitation gold leaf', new_material, flags=re.I)
        target = {'Material / finish': new_material, 'Description': plain_copy(fs['Description']['value'], effect)}
        plan['products'].append({'catalogue_id': p['id'], 'name': p['name'], 'included': p['listing_decision'] == 'include',
            'surface_effect': effect, 'finish_ids': finish_ids,
            'changes': [{'field': key, 'before': fs[key], 'after_value': value} for key, value in target.items()]})
    byid = {p['catalogue_id']: p for p in plan['products']}
    for r in catalogue['records']:
        r['description_html'] = html_copy(r['description_html'], byid[r['catalogue_id']]['surface_effect'])
        r['material'] = 'Gypsum-based material'
        r['surface_effect'] = byid[r['catalogue_id']]['surface_effect']
        r['description_text'] = next(x['after_value'] for x in byid[r['catalogue_id']]['changes'] if x['field'] == 'Description')
    catalogue['material_policy_utc'] = plan['created_utc']
    (OUT / 'material-update-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    (OUT / 'current-prepared-catalogue.json').write_text(json.dumps(catalogue, ensure_ascii=False, indent=2))
    return before, plan

def apply(before, plan):
    boot = get('/api/bootstrap')
    assert boot['source']['register_sha256'] == before['source']['register_sha256']
    live = {p['id']: p for p in get('/api/specifications')['products']}
    receipt_path = OUT / 'material-app-receipts.json'
    receipts = read(receipt_path) if receipt_path.exists() else []
    for n, p in enumerate(plan['products'], 1):
        pid = p['catalogue_id']
        fs = fields(live[pid])
        for change in p['changes']:
            key, value = change['field'], change['after_value']
            current = fs[key]
            if current['value'] == value:
                continue
            assert current['value'] == change['before']['value'] and current['version'] == change['before']['version'], ('Concurrent edit', pid, key)
            data = {'decision':'edit','value':value,'certainty':'confirmed',
                'evidence':plan['authority'],
                'notes':'Owner-specified offered material and public wording. Existing finish retained. Manufacturing scenario, labour, prices, dimensions, images and identity unchanged by this copy update.'}
            request = urllib.request.Request(BASE + '/api/reviews', data=json.dumps({'kind':'field','product_id':pid,'item_id':key,'version':current['version'],'data':data}).encode(),
                headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE}, method='POST')
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.load(response)
            assert result['data']['value'] == value
            receipts.append({'catalogue_id':pid,'field':key,'before':current,'after':result})
            receipt_path.write_text(json.dumps(receipts, ensure_ascii=False, indent=2))
        if n % 30 == 0:
            print(json.dumps({'saved':n,'total':len(plan['products'])}), flush=True)
    after = {p['id']:p for p in get('/api/specifications')['products']}
    for p in plan['products']:
        fs = fields(after[p['catalogue_id']])
        for change in p['changes']:
            assert fs[change['field']]['value'] == change['after_value']
    for old in before['products']:
        new = after[old['id']]
        assert new['costing'] == old['costing'], ('Cost changed',old['id'])
        assert new['name'] == old['name'] and new['listing_decision'] == old['listing_decision']
        for key, f in fields(old).items():
            if key not in ('Material / finish','Description'):
                assert fields(new)[key]['value'] == f['value'], (old['id'],key)
    result = {'status':'PASS_VERSION_CHECKED_APP_READBACK','products':len(plan['products']),
        'included':sum(p['included'] for p in plan['products']),
        'with_surface_effect':sum(p['surface_effect'] for p in plan['products']),
        'included_with_surface_effect':sum(p['included'] and p['surface_effect'] for p in plan['products']),
        'costs_prices_and_other_fields_unchanged':True,'completed_utc':datetime.now(timezone.utc).isoformat()}
    (OUT / 'material-app-verification.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    before, plan=prepare()
    print(json.dumps({'planned':len(plan['products']),'surface_effects':sum(p['surface_effect'] for p in plan['products'])}),flush=True)
    if args.apply:
        apply(before,plan)
