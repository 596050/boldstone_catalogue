"""Local item-by-item display of six unchanged qualified option records."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
LANE = HERE / 'case-normalization-handoff-20261024T165515Z'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
esc = lambda value: html.escape(str(value), quote=True)
pointer_path = BASE / 'current-master.json'
pointer = read(pointer_path)
register_path = BASE / pointer['register']
assert sha(register_path) == pointer['register_sha256']
register = read(register_path)
options = {r['product_id']: r for r in register['options']}
seal = read(LANE / 'sealed-handoff.json')
for frozen in seal['files']:
    assert sha(frozen['path']) == frozen['sha256']
packet = read(LANE / 'handoff.json')
rows, cards = [], []
for number, frozen in enumerate(packet['rows'], 1):
    option = options[frozen['option_id']]
    assert option['file_id'] == frozen['expected_file_id']
    assert option['folder_id'] == frozen['expected_folder_id']
    assert option['master_fields'] == frozen['current_option']['master_fields']
    assert option['source_scopes'] == frozen['current_option']['source_scopes']
    fields = option['master_fields']
    assert len(fields) == 6
    published = all(option[k] == frozen['proposed'][k] for k in ('image_url', 'folder_url'))
    if not published:
        assert all(option[k] == frozen['before'][k] for k in ('image_url', 'folder_url'))
    row = {'option_id': option['product_id'], 'name': option['name'],
        'file_id': option['file_id'], 'folder_id': option['folder_id'],
        'observed_image_url': frozen['proposed']['image_url'], 'observed_folder_url': frozen['proposed']['folder_url'],
        'saved_catalogue_image_url': option['image_url'], 'saved_catalogue_folder_url': option['folder_url'],
        'navigation_status': 'PUBLISHED' if published else 'QUEUED_NOT_APPLIED',
        'original_metadata_observations': frozen['metadata_observations'],
        'source_scopes': option['source_scopes'], 'six_qualified_fields': fields,
        'physical_specifications_verified': option['physical_specifications_verified']}
    rows.append(row)
    field_cards = []
    for name, value in fields.items():
        field_cards.append('<section><h3>' + esc(name) + '</h3><p class="display">' + esc(value['display']) +
            '</p><p class="state">' + esc(value.get('state', '')) + '</p><p><strong>Basis:</strong> ' +
            esc(value.get('basis', '')) + '</p><details><summary>Full retained field object and source references</summary><pre>' +
            esc(json.dumps(value, indent=2, ensure_ascii=False)) + '</pre></details></section>')
    cards.append('<article id="' + esc(option['product_id']) + '"><h2>' + str(number) + '. ' + esc(option['name']) +
        '</h2><p><a href="' + esc(row['observed_image_url']) + '">Image at observed path</a> · <a href="' +
        esc(row['observed_folder_url']) + '">Containing folder</a> · <a href="' + esc(str(LANE / 'index.html') + '#' + option['product_id']) +
        '">Exact URL correction</a></p><p>Navigation status: ' + esc(row['navigation_status']) +
        '. Selected file <code>' + esc(option['file_id']) + '</code>; folder <code>' + esc(option['folder_id']) +
        '</code>.</p><p>Retained source scopes: ' + esc(json.dumps(row['source_scopes'], ensure_ascii=False)) + '</p>' +
        ''.join(field_cards) + '</article>')
    print(json.dumps({'item': number, 'name': row['name'], 'navigation_status': row['navigation_status'],
        'image': row['observed_image_url'], 'folder': row['observed_folder_url'],
        'retained_qualified_fields': len(fields),
        'recorded_physical_field_verifications': sum(v.get('physical_verification') == 1 for v in fields.values())}, ensure_ascii=False))

assert read(pointer_path) == pointer, 'Pointer changed while reading; rerun'
data = {'status': 'PASS_SIX_OPTIONS_THIRTY_SIX_QUALIFIED_FIELDS_UNCHANGED',
    'recorded_utc': datetime.now(timezone.utc).isoformat(), 'pointer_sha256': sha(pointer_path),
    'register': str(register_path), 'register_sha256': sha(register_path),
    'original_handoff': str(LANE / 'sealed-handoff.json'), 'original_handoff_sha256': sha(LANE / 'sealed-handoff.json'),
    'options': rows, 'new_live_reads': 0, 'new_physical_verifications': 0,
    'native_or_canonical_writes': 0, 'source_objects_changed': 0}
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Six option specification walkthrough</title><style>body{font:16px/1.5 system-ui;max-width:1050px;margin:36px auto;padding:0 20px;color:#222}a{color:#15549b}article{border-top:2px solid #bbb;margin:36px 0;padding-top:12px}section{border-top:1px solid #ddd;margin:20px 0}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}.display{font-weight:600}.state{color:#555}pre{font-size:13px}</style></head><body><h1>Six option specification walkthrough</h1><p>Each option retains all six complete field objects and their original source qualifications. The URL-capitalization work changes navigation only. No new measurements, materials, weights, fixing verification, stock or live-offer observations are recorded here.</p><p>The image and folder links use prior exact-ID metadata observations; no live reads were made for this display. Historical owner wording in the retained objects is source evidence, not a new question.</p><p><a href="case-specifications.json">Structured record</a></p>' + ''.join(cards) + '</body></html>'
(HERE / 'case-specifications.json').write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
(HERE / 'case-specifications.html').write_text(page)
print(json.dumps({'report': str(HERE / 'case-specifications.html'), 'status': data['status'],
    'options': len(rows), 'qualified_fields': sum(len(r['six_qualified_fields']) for r in rows)}))
