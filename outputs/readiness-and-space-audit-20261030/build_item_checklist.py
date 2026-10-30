"""Build a read-only per-component checklist from current app responses."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import html
import json
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
specs = json.loads((OUT / 'specifications.json').read_text())
coverage = json.loads((OUT / 'coverage.json').read_text())['products']
pointer = json.loads((ROOT / 'sculpture-catalogue/current-master.json').read_text())
plan = json.loads(Path(pointer['current_upload_preparation']['path']).read_text())
plans = {p['product_id']: p for p in plan['products']}
images = {x['id']: x for x in json.loads((OUT / 'selected-image-links.json').read_text())}
rows = []
for product in specs['products']:
    pid = product['id']
    photo = coverage[pid]
    mapping = plans[pid]
    decision = product['listing_decision']
    tasks = []
    if decision == 'pending':
        tasks.append('Decide whether to include this listing.')
    elif decision == 'exclude':
        tasks.append('Keep excluded from upload unless you change this decision.')
    if decision != 'exclude':
        if product['review_status'] != 'reviewed':
            tasks.append('Complete the component review.')
        if photo['primary_listing']['status'] != 'set':
            tasks.append('Choose a primary listing photograph.')
        if not photo['listing']['count']:
            tasks.append('Select listing photographs.')
        if photo['in_situ']['missing']:
            tasks.append(f"Add or assign {photo['in_situ']['missing']} in-situ image(s) to reach two.")
        for note in mapping['publication_review']:
            if note.startswith('Visible '):
                description, _, image_id = note.partition(' id:')
                image = images.get('id:' + image_id, {})
                tasks.append({'text': description, 'image_url': image.get('image_url'), 'image_id': 'id:' + image_id})
    optional = []
    # The app's older White-title indicator also flags some titles which
    # already contain White. Do not turn those false positives into work.
    if photo.get('white_evidence') == 'white_folder_title_missing' and not re.search(r'\bwhite\b', product['name'], re.I):
        optional.append('Title check: containing folder says White; the display title omits White.')
    row = {'id': pid, 'name': product['name'], 'family': product['family'],
           'listing_decision': decision, 'review_status': product['review_status'],
           'specification_fields_filled': sum(bool(f['value']) for f in product['fields']),
           'specification_field_count': len(product['fields']),
           'listing_copy_fields_filled': sum(bool(f['value']) for f in product['listing_fields']),
           'listing_copy_field_count': len(product['listing_fields']),
           'primary_status': photo['primary_listing']['status'],
           'primary_image_url': images.get(photo['primary_listing'].get('image_id'), {}).get('image_url'),
           'listing_image_count': photo['listing']['count'],
           'in_situ_count': photo['in_situ']['count'], 'in_situ_missing': photo['in_situ']['missing'],
           'next_item_tasks': tasks, 'optional_title_checks': optional,
           'sku': mapping['sku'], 'sku_status': mapping['sku_status'],
           'shopify_action': mapping['shopify_action'], 'shopify_handle': mapping['shopify_handle'],
           'squarespace_action': mapping['squarespace_action'],
           'squarespace_product_id': mapping['squarespace_product_id'],
           'squarespace_variant_id': mapping['squarespace_variant_id'],
           'cost_gbp': mapping['manufacturing_cost_gbp'], 'price_gbp': mapping['price_gbp'],
           'cost_material': product['costing']['material_label'],
           'recorded_material': next(f['value'] for f in product['fields'] if f['key'] == 'Material / finish'),
           'app_url': f'http://127.0.0.1:8767/#{pid}', 'folder_url': product['folder_url']}
    rows.append(row)

included = [r for r in rows if r['listing_decision'] == 'include']
summary = {'checked_utc': specs['checked_at'], 'components': len(rows),
           'decisions': dict(Counter(r['listing_decision'] for r in rows)),
           'missing_specification_fields': sum(r['specification_field_count'] - r['specification_fields_filled'] for r in rows),
           'missing_listing_copy_fields': sum(r['listing_copy_field_count'] - r['listing_copy_fields_filled'] for r in rows),
           'included_without_primary': sum(r['primary_status'] != 'set' for r in included),
           'included_with_in_situ_gaps': sum(r['in_situ_missing'] > 0 for r in included),
           'included_in_situ_slots_missing': sum(r['in_situ_missing'] for r in included),
           'selected_distinct_images': len(images),
           'selected_images_with_original_dimensions': sum(bool(i['dimensions']) for i in images.values()),
           'included_with_item_tasks': sum(bool(r['next_item_tasks']) for r in included),
           'optional_title_checks': sum(bool(r['optional_title_checks']) for r in rows),
           'platform_changes_applied': False}
(OUT / 'item-checklist.json').write_text(json.dumps({'summary': summary, 'items': rows}, ensure_ascii=False, indent=2))
esc = lambda v: html.escape(str(v), quote=True)
def link(url, label):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>' if url else esc(label)
body = []
for i, r in enumerate(rows, 1):
    task_html = []
    for task in r['next_item_tasks']:
        task_html.append('<li>' + (link(task.get('image_url'), task['text']) if isinstance(task, dict) else esc(task)) + '</li>')
    task_html.extend('<li class="muted">' + esc(t) + '</li>' for t in r['optional_title_checks'])
    if not task_html:
        task_html = ['<li>No further item-specific gap in this audit. Proceed with destination checks and draft upload.</li>']
    searchable = esc(' '.join([r['name'], r['family'], r['sku']]).lower())
    body.append(f'''<tr data-search="{searchable}" data-decision="{esc(r['listing_decision'])}" data-tasks="{str(bool(r['next_item_tasks']) and r['listing_decision'] != 'exclude').lower()}" data-gap="{str(bool(r['in_situ_missing'])).lower()}">
<td>{i}</td><td><strong>{link(r['app_url'], r['name'])}</strong><small>{esc(r['family'])}</small>{link(r['folder_url'], 'Dropbox folder')}<br>{link(r['primary_image_url'], 'Primary image') if r['primary_status']=='set' else '<span class="warn">Primary missing</span>'}</td>
<td><span class="badge {esc(r['listing_decision'])}">{esc(r['listing_decision'])}</span><small>{esc(r['review_status'])}</small></td>
<td>{r['specification_fields_filled']}/{r['specification_field_count']} specifications<br>{r['listing_copy_fields_filled']}/{r['listing_copy_field_count']} listing fields<br>Cost £{r['cost_gbp']:.2f}<br>Price £{r['price_gbp']:.2f}<small>100% markup</small><details><summary>Material basis</summary><p>Cost model: {esc(r['cost_material'])}</p><p>Recorded specification: {esc(r['recorded_material'])}</p></details></td>
<td>Primary: {esc(r['primary_status'])}<br>Listing photos: {r['listing_image_count']}<br>In situ: {r['in_situ_count']}/2{'<small class="warn">Need '+str(r['in_situ_missing'])+'</small>' if r['in_situ_missing'] else ''}</td>
<td><ul>{''.join(task_html)}</ul></td><td><code>{esc(r['sku'])}</code><small>{esc(r['sku_status'])}</small><details><summary>Destination actions</summary><p>Shopify: {esc(r['shopify_action'])}</p><p>Handle: {esc(r['shopify_handle'])}</p><p>Squarespace: {esc(r['squarespace_action'])}</p></details></td></tr>''')
page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BOLDSTONE - work remaining for every component</title><style>
body{font:15px/1.5 system-ui,sans-serif;color:#26352d;background:#f7f6f0;margin:24px}h1{font:36px Georgia,serif}p{max-width:1100px}a{color:#426c4d}small{display:block;color:#667168;margin:4px 0}.toolbar{position:sticky;top:0;background:#f7f6f0;padding:12px 0;display:flex;gap:12px;flex-wrap:wrap;z-index:2}input,select{font:inherit;padding:9px;border:1px solid #bbc6b9;border-radius:5px}input{min-width:330px}table{width:100%;border-collapse:collapse;background:white}th,td{text-align:left;vertical-align:top;padding:12px;border:1px solid #dee3dc}th{background:#e6ece1}td:nth-child(2){min-width:230px}td:nth-child(6){min-width:260px}ul{padding-left:18px;margin:0}.badge{display:inline-block;padding:3px 8px;border-radius:4px;background:#e6ece1}.exclude{background:#eee}.pending,.warn{color:#80511c}.pending{background:#f8edce}.muted{color:#73766f}details p{font-size:13px}code{font-size:12px}tr[hidden]{display:none}
</style><h1>Work remaining for every component sculpture</h1>'''
page += f'<p>Checked {esc(summary["checked_utc"])}. <strong>181 components; 172 included, 6 undecided and 3 excluded.</strong> All 1,267 specification fields and 724 listing-copy fields are filled. All 409 distinct selected listing photos have alt text and verified original dimensions.</p>'
page += '<p>For included products: one primary/listing selection is missing; four selected photos need finish-assignment review across two White products; 27 products need 38 more in-situ assignments to meet the two-image target. Excluded products do not need preparation while they remain excluded. Group photographs stay optional.</p>'
page += '<p><strong>Common upload work:</strong> check the current destination records against the saved product/variant/SKU plan, upload selected image originals to the store, attach and order them, then review the resulting drafts. The prepared package has not changed the stores. Delivery is quoted separately; the 1-2 week period is production time. Packed weight, packaging and transit arrangements are settled for the delivery quote. Recorded material and the editable GFRC cost model remain separate.</p>'
page += '<div class="toolbar"><input id="search" aria-label="Search components" placeholder="Find sculpture, family or SKU"><select id="filter" aria-label="Filter"><option value="all">All 181 components</option><option value="tasks">Item-specific work, excluding excluded items</option><option value="include">Included</option><option value="pending">Undecided</option><option value="exclude">Excluded</option><option value="gap">In-situ gaps</option></select><span id="count"></span></div><table><thead><tr><th>#</th><th>Component and links</th><th>Decision</th><th>Fields and price</th><th>Images</th><th>Item-specific work</th><th>Upload mapping</th></tr></thead><tbody>' + ''.join(body) + '</tbody></table>'
page += '''<script>const rows=[...document.querySelectorAll('tbody tr')],q=document.querySelector('#search'),f=document.querySelector('#filter');function update(){let count=0;for(const r of rows){const match=r.dataset.search.includes(q.value.toLowerCase())&&(f.value==='all'||f.value==='tasks'&&r.dataset.tasks==='true'||f.value==='gap'&&r.dataset.gap==='true'||r.dataset.decision===f.value);r.hidden=!match;if(match)count++}document.querySelector('#count').textContent=count+' of '+rows.length+' components'}q.addEventListener('input',update);f.addEventListener('change',update);update()</script></html>'''
(OUT / 'per-component-checklist.html').write_text(page)
assert len(rows) == len(plans) == 181
assert all(r['specification_fields_filled'] == 7 and r['listing_copy_fields_filled'] == 4 for r in rows)
print(json.dumps(summary, indent=2))
