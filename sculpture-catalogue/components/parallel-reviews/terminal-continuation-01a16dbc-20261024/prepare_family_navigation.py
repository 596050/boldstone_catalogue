"""Freeze a bounded family of current catalogue references for read-only auditing."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--family', required=True)
args = parser.parse_args()
raw = (B / 'current-master.json').read_bytes()
p = json.loads(raw)
source = B / p['register']
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(source) == p['register_sha256']
g = json.loads(source.read_text())
components = {x['component_id']: x for x in g['components']}
active = set(g['active_option_ids'])
rows = [o for o in g['options'] if o['product_id'] in active and components.get(o['canonical_component_id'], {}).get('family') == args.family]
assert 1 <= len(rows) <= 25, 'Use a bounded subset for larger families'
assert all(o['file_id'] and o['folder_id'] for o in rows)
now = datetime.now(timezone.utc)
slug = ''.join(c.lower() if c.isalnum() else '-' for c in args.family).strip('-')
lane = B / 'components/parallel-reviews' / (slug + '-primary-navigation-01a16dbc-' + now.strftime('%Y%m%dT%H%M%SZ'))
lane.mkdir(exist_ok=False)
scope = {'schema': 'boldstone.bounded-family-reference-audit-scope.v1', 'recorded_utc': now.isoformat(),
         'family': args.family, 'source_register': str(source), 'source_register_sha256': p['register_sha256'],
         'observed_pointer_sha256': hashlib.sha256(raw).hexdigest(), 'options': rows,
         'query_ids': list(dict.fromkeys(i for row in rows for i in [row['file_id'], row['folder_id']])),
         'allowed': 'Read exact selected stable file IDs and their existing folder IDs. Record current navigation only.',
         'new_image_selection': False, 'new_physical_or_identity_decision': False,
         'owner_holds_released': False, 'canonical_or_native_writes': 0}
(lane / 'scope.json').write_text(json.dumps(scope, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'directory': str(lane), 'scope_sha256': sha(lane / 'scope.json'),
                  'query_ids': scope['query_ids'], 'options': len(rows), 'source_register_sha256': p['register_sha256']}))
