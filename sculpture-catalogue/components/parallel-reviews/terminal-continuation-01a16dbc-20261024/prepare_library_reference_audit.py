"""Freeze current primary references and reuse matching, source-qualified reads."""
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
raw = (B / 'current-master.json').read_bytes()
p = json.loads(raw)
source = B / p['register']
assert sha(source) == p['register_sha256']
g = read(source)
active = set(g['active_option_ids'])
rows = [o for o in g['options'] if o['product_id'] in active]
assert len(rows) == 188
eligible, excluded = [], []
for option in rows:
    if option['family'] == 'Wall Circle':
        reason = 'OWNER_WALL_CIRCLE_HOLD_RETAINED; exact two deleted-reference histories remain in their separate sealed review'
    elif option['family'] == 'Moonwave':
        reason = 'DIRECTORY_SESSION_OWNS_PENDING_NINE_FILE_PROPOSAL'
    elif not option.get('file_id') or not option.get('folder_id'):
        reason = 'NO_SELECTED_FILE_OR_FOLDER_ID; existing Frozen Fish identity deferral retained'
    else:
        eligible.append(option)
        continue
    excluded.append({'option_id': option['product_id'], 'name': option['name'], 'family': option['family'], 'reason': reason})
now = datetime.now(timezone.utc)
lane = B / 'components/parallel-reviews' / ('library-primary-reference-audit-01a16dbc-' + now.strftime('%Y%m%dT%H%M%SZ'))
(lane / 'receipts').mkdir(parents=True, exist_ok=False)
known = {}
health = B / 'components/parallel-reviews/unpaired43-native-navigation-20261024T023834Z/metadata-receipts.json'
for record in read(health)['requests']:
    if record.get('status') == 'METADATA_RETURNED':
        kind = record['metadata_type']
        known[record['query']] = {'requested_id': record['query'], 'completed_utc': record['completed_utc'],
            'response': {'isError': False, 'structuredContent': {'metadata_type': kind, kind: record['metadata']}},
            'evidence_kind': 'REUSED_PRIOR_VERIFIED_NATIVE_METADATA', 'source': {'path': str(health), 'sha256': sha(health)}}
for prior, key in [(B / 'components/reconciliation/decowaves2-owner-design-group-master-2026-10-24/live-pair-metadata.json', 'observations'),
                   (B / 'components/parallel-reviews/ammonite-primary-navigation-01a16dbc-20261024T150549Z/metadata-receipts.json', 'observations')]:
    data = read(prior)
    for record in data[key]:
        if record['response'].get('isError'):
            continue
        known[record['requested_id']] = {**record, 'completed_utc': record.get('completed_utc', data['recorded_utc']),
            'evidence_kind': 'REUSED_PRIOR_VERIFIED_NATIVE_METADATA', 'source': {'path': str(prior), 'sha256': sha(prior)}}

def paths_match(option):
    if option['file_id'] not in known or option['folder_id'] not in known:
        return False
    file = known[option['file_id']]['response']['structuredContent'].get('file')
    folder = known[option['folder_id']]['response']['structuredContent'].get('folder')
    if not file or not folder or file['id'] != option['file_id'] or folder['id'] != option['folder_id']:
        return False
    image = urlsplit(option['image_url'])
    if image.path.startswith('/preview/'):
        expected = unquote(image.path.removeprefix('/preview'))
    elif image.path.startswith('/home/') and parse_qs(image.query).get('preview'):
        expected = unquote(image.path.removeprefix('/home')) + '/' + parse_qs(image.query)['preview'][0]
    else:
        return False
    return expected == file['path_display'] and str(Path(expected).parent) == folder['path_display'] and unquote(urlsplit(option['folder_url']).path.removeprefix('/home')) == folder['path_display']

reused_ids = {identifier for option in eligible if paths_match(option) for identifier in [option['file_id'], option['folder_id']]}
all_ids = list(dict.fromkeys(identifier for option in eligible for identifier in [option['file_id'], option['folder_id']]))
reuse = {identifier: known[identifier] for identifier in all_ids if identifier in reused_ids}
query_ids = [identifier for identifier in all_ids if identifier not in reuse]
families = defaultdict(list)
for option in eligible:
    families[option['family']].append(option)
plan = {'schema': 'boldstone.current-selected-reference-audit-plan.v1', 'created_utc': now.isoformat(),
        'source_register': str(source), 'source_register_sha256': p['register_sha256'],
        'source_pointer_observed_sha256': hashlib.sha256(raw).hexdigest(),
        'active_options': 188, 'eligible_options': eligible, 'excluded_options': excluded,
        'families': dict(families), 'all_query_ids': all_ids, 'reused_observations': reuse,
        'new_query_ids': query_ids, 'new_batches': [query_ids[i:i + 20] for i in range(0, len(query_ids), 20)],
        'scope': 'Current selected image and containing folder metadata only. Same-ID prior verified paths reused with original clocks. Other native work, Wall Circle holds, null/deferred references, image content/provenance, physical specifications and canonical writes are excluded.',
        'image_bytes_downloaded': 0, 'new_selections': 0, 'canonical_or_native_writes': 0}
(lane / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'directory': str(lane), 'plan_sha256': sha(lane / 'plan.json'), 'eligible_options': len(eligible),
                  'families': len(families), 'excluded_options': len(excluded), 'unique_metadata_ids': len(all_ids),
                  'reused_metadata_ids': len(reuse), 'new_metadata_ids': len(query_ids), 'batches': plan['new_batches']}))
