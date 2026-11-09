"""Prepare the current Pinterest bridge and canonical shopping funnel; no live writes."""
import argparse
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('config', type=Path, help='Public tagId and exact SKU-to-product-ID/path mapping JSON')
parser.add_argument('output', type=Path)
args = parser.parse_args()
config = json.loads(args.config.read_text())
assert str(config['tagId']).isdigit() and len(str(config['tagId'])) == 13
assert len(config['products']) == 176
ids = [v['id'] for v in config['products'].values()]
assert len(set(ids)) == 176
assert all(v['path'].startswith('/buy/p/') for v in config['products'].values())
here = Path(__file__).parent
tag = (here / 'pinterest_tag.js').read_text().replace('__BOLDSTONE_PINTEREST_CONFIG__', json.dumps(config, separators=(',', ':')))
funnel = (here / 'shopping_funnel.js').read_text()
assert 'lastViews.ga4' in funnel and 'lastViews.pinterest' in funnel
args.output.mkdir(parents=True, exist_ok=True)
files = {'pinterest-tag-header.html': '<script>\n' + tag + '\n</script>\n',
         'shopping-funnel-footer.html': '<script id="boldstone-ga4-shopping-funnel">\n' + funnel.rstrip() + '\n</script>'}
for name, body in files.items():
    path = args.output / name
    assert not path.exists(), f'Reconcile existing prepared artifact before overwriting: {path}'
    path.write_text(body)
(args.output / 'tracking-build.json').write_text(json.dumps({
    'status': 'PREPARED_ONLY', 'products': 176, 'live_writes': 0,
    'sha256': {n: hashlib.sha256(b.encode()).hexdigest() for n, b in files.items()}
}, indent=2) + '\n')
print('Prepared 176-product tracking configuration; no website settings changed.')
