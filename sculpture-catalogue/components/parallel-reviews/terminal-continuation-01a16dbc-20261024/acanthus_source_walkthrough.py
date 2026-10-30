"""Read every current Acanthus finish option without extending owner decisions."""
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
raw = (B / 'current-master.json').read_bytes()
p = json.loads(raw)
source = B / p['register']
assert sha(source) == p['register_sha256']
g = read(source)
components = {x['component_id']: x for x in g['components']}
active = set(g['active_option_ids'])
rows = [x for x in g['options'] if x['product_id'] in active and components.get(x['canonical_component_id'], {}).get('family') == 'Acanthus']
fields = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability']
assert len(rows) == 10 and len({x['product_id'] for x in rows}) == 10
assert all(set(x['master_fields']) == set(fields) for x in rows)
assert all(x['file_id'] and x['folder_id'] and x['image_url'] and x['folder_url'] for x in rows)
one = next(x for x in rows if x['product_id'] == 'BSI-3635E3DC3434')
two = next(x for x in rows if x['product_id'] == 'BSI-449C4421ABD0')
assert one['master_fields'] != two['master_fields']
assert '4 kg' in one['master_fields']['Weight']['display'] and '5 kg' in two['master_fields']['Weight']['display']
cards = []
for index, option in enumerate(rows, 1):
    print(f"ACANTHUS {index}: {option['name']}\nImage: {option['image_url']}\nFolder: {option['folder_url']}")
    for name in fields:
        print(name + ': ' + option['master_fields'][name]['display'].split('\n')[0])
    body = []
    for name in fields:
        field = option['master_fields'][name]
        # Historical quoted prompts stay within the expandable source object.
        # The visible value is its existing first line, not a new owner question.
        display = field['display'].split('\n')[0]
        detail = json.dumps(field, ensure_ascii=False, indent=2)
        body.append('<tr><th>' + esc(name) + '</th><td>' + esc(display) + '<details><summary>Recorded source and qualification</summary><pre>' + esc(detail) + '</pre></details></td></tr>')
    cards.append('<article id="' + esc(option['product_id']) + '"><h2>' + str(index) + '. ' + esc(option['name']) + '</h2><p><a href="' + esc(option['image_url']) + '">Catalogue image reference</a> · <a href="' + esc(option['folder_url']) + '">Containing folder</a></p><table>' + ''.join(body) + '</table><p><small>' + esc(option['product_id']) + ' · ' + esc(option['canonical_component_id']) + '<br>' + esc(option['file_id']) + ' · ' + esc(option['folder_id']) + '</small></p></article>')
physical = [option['master_fields'][name] for option in rows for name in fields[:4]]
verified = sum(bool(x.get('physical_verification')) for x in physical)
snapshot = {'schema': 'boldstone.acanthus-current-field-walkthrough.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
            'source_register': str(source), 'source_register_sha256': p['register_sha256'],
            'source_pointer_observed_sha256': hashlib.sha256(raw).hexdigest(), 'active_finish_options': len(rows),
            'component_id_records': len({x['canonical_component_id'] for x in rows}), 'working_field_objects': len(rows) * 6,
            'physical_field_groups': len(physical), 'recorded_physical_verifications': verified,
            'new_physical_verifications': 0, 'new_owner_confirmations': 0, 'new_live_metadata_checks': 0,
            'options': rows, 'source_or_shared_master_writes': 0,
            'scope': 'Existing published option objects and their qualified fields only. Native listing claims, owner estimates, actual measurements and selected-photo roles are separate. The pending One Leaf Pewter actual-details question is not answered by this report.'}
assert verified == 0
text = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Acanthus option walkthrough</title><style>body{font:17px/1.5 Arial,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px;color:#222}h1{font-size:30px}h2{font-size:23px}article{border-top:1px solid #ccc;margin-top:30px;padding-top:15px}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:10px}th{width:24%}a{color:#15549b}details{font-size:14px;margin:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere}small{overflow-wrap:anywhere}</style></head><body><h1>Acanthus finish options and working specifications</h1><p>All10 active Acanthus finish options, with60 retained working field objects and40 physical field groups. No physical verification is recorded for those40 groups. Existing listing claims, accepted estimates and source qualifications remain visible. No new owner decision or native image check was made.</p><p>One Leaf Pewter retains approximately4kg as its working estimate. Two Leaves Pewter retains approximately5kg. The One Leaf answer is not transferred to Two Leaves or another finish. Image and folder links below are the published catalogue references.</p>' + ''.join(cards) + '</body></html>'
(H / 'acanthus-options.html').write_text(text)
(H / 'acanthus-options.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
assert sha(source) == p['register_sha256']
print(json.dumps({'status': 'READ_ONLY_WALKTHROUGH_COMPLETE', 'options': len(rows), 'working_fields': len(rows) * 6, 'physical_fields': len(physical), 'new_confirmations': 0, 'report': str(H / 'acanthus-options.html')}))
