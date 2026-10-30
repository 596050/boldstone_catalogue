"""Read back the bounded review against source evidence and the protected register."""
import hashlib
import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

H = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
r = read(H / 'review.json')
manifest = read(H / 'input-manifest.json')
screen = read(H / 'cached-candidate-screen.json')
checks = []
def check(name, condition):
    checks.append({'name': name, 'passed': bool(condition)})

check('Register, workbook and audit retain frozen hashes', all(sha(p) == expected for p, expected in r['baseline_protected_files'].items()))
check('Historical input files retain captured hashes', all(sha(p) == expected for p, expected in r['source_inputs'].items()))
all_images = manifest['source_renditions'] + manifest['viewed_Dropbox_cached_images']
check('All sixteen visually reviewed image files rehash correctly', len(all_images) == 16 and all(sha(x['path']) == x['sha256'] and Path(x['path']).stat().st_size == x['bytes'] for x in all_images))
check('Bounded screen covers exactly 178 unique saved MASTER candidates', len(screen['candidates']) == len({x['file_id'] for x in screen['candidates']}) == 178 and all('/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moon Crater Phase/' in x['native_path'] for x in screen['candidates']))
check('Screen inputs retain their cached bytes', all(sha(x['cached_path']) == x['cached_sha256'] for x in screen['candidates']))
check('Each of six ranking rows covers the same candidate IDs', len(screen['scores']) == 6 and all({x['file_id'] for x in row['ranked_candidates']} == {x['file_id'] for x in screen['candidates']} for row in screen['scores']))
g = read(next(p for p in r['baseline_protected_files'] if p.endswith('canonical-master-register.json')))
opts = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
expected = {'O006': ('BSI-46F6DB226213', 'BC-MCP-4', 'SQ2233720'), 'O007': ('BSI-EBD43DF0704F', 'BC-MCP-1', 'SQ6715979')}
for case in r['cases']:
    ref = case['offer_ref']; oid, design, sku = expected[ref]; o = opts[oid]
    check(ref + ' preserves raw offer, BOM and working fields exactly', case['retained_source_offer'] == edges[ref]['source_offer'] and case['retained_BOM_members'] == edges[ref]['members'] and case['master_fields'] == o['master_fields'])
    check(ref + ' binds existing option, design, source tuple and current links', case['option_id'] == oid and case['design_id'] == design and case['native_tuple']['sku_raw'] == sku and case['current_reference'] == {k: o[k] for k in case['current_reference']})
    check(ref + ' distinguishes three viewed frames from eight media records', case['source_frames_visually_reviewed'] == 3 and case['remaining_native_gallery_frames_not_visually_reviewed'] == 5 and len(case['native_gallery_metadata']) == 8 and all(any(m['assetUrl'] == x['source_image_url'] and m['id'] == x['native_media_id'] for m in case['native_gallery_metadata']) for x in case['images'] if 'source_image_url' in x))
    check(ref + ' leaves original and variant image binding unresolved', not case['exact_source_original_file_bound'] and not case['exact_photo_equivalence_certified'] and case['native_variant_raw']['imageIds'] == [] and case['native_variant_raw']['images'] == [] and all(case['retained_source_offer'][k] == '' for k in ['image_file_id', 'image_folder_id', 'image_path']))
check('Only O006 supports appearance association; O007 remains qualified', {x['offer_ref']: x['appearance_association_supported'] for x in r['cases']} == {'O006': True, 'O007': False})
check('No original match, new product, platform pair or physical verification claimed', all(not case[k] for case in r['cases'] for k in ['exact_current_size_build_or_physical_cast_verified', 'physical_specifications_verified', 'new_platform_pair', 'new_variant_SKU_assignment', 'new_product', 'new_photo_role']))

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.srcs = []; self.hrefs = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'img': self.srcs.append(a['src'])
        if tag == 'a': self.hrefs.append(a['href'])
parser = Links(); parser.feed((H / 'index.html').read_text())
check('HTML presents all sixteen cached image files with existing local targets', len(parser.srcs) == 16 and all(urlparse(x).scheme == 'file' and Path(unquote(urlparse(x).path)).is_file() for x in parser.srcs))
check('HTML contains every viewed Dropbox image and containing-folder link', all(x['image_url'] in parser.hrefs and x['folder_url'] in parser.hrefs for x in manifest['viewed_Dropbox_cached_images']))
check('Review declares no native, platform or canonical writes', all(r[k] == 0 for k in ['native_calls', 'native_writes', 'platform_writes', 'shared_canonical_writes']))
result = {'status': 'PASS' if all(c['passed'] for c in checks) else 'FAIL', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'passed': sum(c['passed'] for c in checks), 'total': len(checks), 'checks': checks, 'review_sha256': sha(H / 'review.json')}
write(H / 'verification.json', result)
assert result['status'] == 'PASS', result
files = ['build_review.py', 'verify_review.py', 'review.json', 'cached-candidate-screen.json', 'input-manifest.json', 'index.html', 'terminal-review.txt', 'verification.json']
write(H / 'sealed-handoff.json', {'status': 'SEALED_READ_ONLY_SOURCE_PHOTO_REVIEW', 'recorded_utc': result['recorded_utc'], 'files': {str(H / f): sha(H / f) for f in files}, 'source_refs': ['O006', 'O007'], 'outcome': r['outcome'], 'canonical_changes': 0})
print(json.dumps({'status': result['status'], 'passed': result['passed'], 'total': result['total'], 'seal_sha256': sha(H / 'sealed-handoff.json')}))
