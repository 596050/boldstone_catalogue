"""Verify source identities, photo evidence, links and unchanged catalogue bytes."""
import hashlib
import json
import math
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse
from PIL import Image, ImageChops, ImageOps, ImageStat

H = Path(__file__).resolve().parent
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, d: Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
r, analysis = read(H / 'review.json'), read(H / 'photo-comparisons.json')
checks = []
def check(name, result): checks.append({'name': name, 'passed': bool(result)})
check('Five protected catalogue/navigation files unchanged', len(r['protected_files']) == 5 and all(sha(p) == s for p, s in r['protected_files'].items()))
check('Historical source evidence hashes unchanged', all(sha(p) == s for p, s in r['source_inputs'].items()))
assets = read(r['current_asset_map']['path'])
check('Explicit current asset map hash verified', sha(r['current_asset_map']['path']) == r['current_asset_map']['sha256'] == analysis['current_asset_map']['sha256'])
g = read(next(p for p in r['protected_files'] if p.endswith('canonical-master-register.json')))
options = {x['product_id']: x for x in g['options']}
edges = {x['offer_ref']: x for x in g['source_offer_edges']}
expected_tuples = {
    'O003': ('6a410d3d21dbe14148c0a367', '733a1644-4674-482e-ac5b-5e42e5f7fbe1', 'SQ1605793'),
    'O011': ('6a53ee70e5ed822c37e0b7bd', '99fc1ad0-d33d-4eba-81d8-9c7bcb096346', 'SQ4868573'),
    'O064': ('6aa018ab5e7636290fa6e74c', '118590fc-f3fa-4cf0-897c-4229cd349073', 'EBAY-188568590316'),
}
for c in r['cases']:
    ref, o = c['offer_ref'], options[c['option_id']]
    t = c['native_tuple']
    check(ref + ' exact product/variant/SKU retained', (t['product_id'], t['variant_id'], t['sku_raw']) == expected_tuples[ref])
    check(ref + ' raw offer, BOM and qualified fields unchanged', c['retained_source_offer'] == edges[ref]['source_offer'] and c['retained_BOM_members'] == edges[ref]['members'] and c['qualified_working_fields'] == o['master_fields'])
    check(ref + ' three source frames have exact current file/parent/URL mappings', len(c['source_photo_correspondences']) == 3 and all(all(x[k] == assets[x['file_id']][k] for k in ['file_id', 'folder_id', 'image_url', 'folder_url']) for x in c['source_photo_correspondences']))
    check(ref + ' selected reference retained', c['current_selected_reference'] == {k: o[k] for k in c['current_selected_reference']})
source_frames = [x for c in r['cases'] for x in c['source_photo_correspondences']]
check('Nine source cached renditions and their counterparts rehash', len(source_frames) == 9 and all(sha(x['source_cached_path']) == x['source_cached_sha256'] and sha(x['native_cached_path']) == x['native_cached_sha256'] for x in source_frames))
check('Eight unique viewed native images rehash', len(r['viewed_native_images']) == len({x['file_id'] for x in r['viewed_native_images']}) == 8 and all(sha(x['cached_path']) == x['cached_sha256'] for x in r['viewed_native_images']))
check('Unavailable temporary originals distinguished from current rendition bytes', all(not x['historical_source_original_present'] and not Path(x['historical_source_original_path']).is_file() and x['historical_source_original_sha256_not_reverified'] != x['source_cached_sha256'] for x in source_frames))

def rgb(path):
    with Image.open(path) as im: return ImageOps.exif_transpose(im).convert('RGB')
def rmse(a, b): return math.sqrt(sum(x*x for x in ImageStat.Stat(ImageChops.difference(a, b)).rms)/3)
recomputed = []
for x in source_frames:
    a, b = rgb(x['source_cached_path']), rgb(x['native_cached_path'])
    if x['offer_ref'] == 'O011':
        c = x['in_memory_crop_alignment']
        b = b.resize(tuple(c['native_analysis_dimensions']), Image.Resampling.LANCZOS).crop(tuple(c['crop_box_in_native_analysis_pixels']))
        value = rmse(a.resize((64,64), Image.Resampling.LANCZOS), b.resize((64,64), Image.Resampling.LANCZOS))
        expected = c['aligned_RGB_RMSE_0_255']
    else:
        value = rmse(a.resize((96,96), Image.Resampling.LANCZOS), b.resize((96,96), Image.Resampling.LANCZOS))
        expected = x['whole_frame_RGB_RMSE_96px']
    recomputed.append({'ref': x['offer_ref'], 'order': x['source_order'], 'RMSE': value, 'reported_RMSE': expected})
check('Nine recorded pixel comparisons independently recompute', all(abs(x['RMSE'] - x['reported_RMSE']) < 1e-9 for x in recomputed))
check('Verdigris fitted crop errors below 3.1; silver whole-frame errors below 1.7', all(x['RMSE'] < (3.1 if x['ref'] == 'O011' else 1.7) for x in recomputed))
byref = {x['offer_ref']: x for x in r['cases']}
check('Silver aliases share exactly the same three current photo IDs', [x['file_id'] for x in byref['O003']['source_photo_correspondences']] == [x['file_id'] for x in byref['O064']['source_photo_correspondences']] and byref['O003']['option_id'] == byref['O064']['option_id'])
check('Different captured prices, visibility and SKUs preserved', byref['O003']['retained_source_offer']['native_price'] == '350.00' and byref['O064']['retained_source_offer']['native_price'] == '80.33' and byref['O003']['retained_source_offer']['visible'] == 'Yes' and byref['O064']['retained_source_offer']['visible'] == 'No' and byref['O003']['native_tuple']['sku_raw'] != byref['O064']['native_tuple']['sku_raw'])
check('O064 public-collection absence remains limited to that capture', byref['O064']['historical_public_collection_evidence'] == {'native_product_id': '6aa018ab5e7636290fa6e74c', 'state': 'NOT_RETURNED_IN_THIS_CHECKED_PUBLIC_COLLECTION', 'hidden_draft_or_deletion_inferred': False})
check('No physical, byte-identity or native-configuration upgrade', all(not c[k] for c in r['cases'] for k in ['source_original_byte_identity_verified', 'exact_current_sale_configuration_verified', 'physical_specifications_verified', 'new_platform_pair', 'new_source_SKU_assignment', 'new_product']))

class PageLinks(HTMLParser):
    def __init__(self): super().__init__(); self.images=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='img': self.images.append(a['src'])
        if tag=='a': self.links.append(a['href'])
page=PageLinks();page.feed((H/'index.html').read_text())
check('Comparison page has all eighteen source/counterpart image panels', len(page.images)==18 and all(Path(unquote(urlparse(x).path)).is_file() for x in page.images))
check('Every source image, Dropbox image and containing folder is linked', all(all(x[k] in page.links for k in ['source_url','image_url','folder_url']) for x in source_frames))
proposal=read(H/'photo-binding-proposal.json')
check('Handoff contains evidence only and no action payload', not proposal['apply_automatically'] and proposal['native_actions']==[] and proposal['platform_actions']==[] and proposal['new_products']==proposal['specification_changes']==proposal['historical_source_rewrites']==0)
result={'status':'PASS' if all(x['passed'] for x in checks) else 'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),'checks':checks,'recomputed_photo_metrics':recomputed,'review_sha256':sha(H/'review.json')}
write(H/'verification.json',result)
assert result['status']=='PASS',result
files=['compare_cached_photos.py','build_review.py','verify_review.py','photo-comparisons.json','photo-binding-proposal.json','review.json','index.html','terminal-review.txt','verification.json']
write(H/'sealed-handoff.json',{'status':'SEALED_READ_ONLY_PHOTO_CROSSWALK','recorded_utc':result['recorded_utc'],'files':{str(H/f):sha(H/f) for f in files},'source_refs':['O011','O003','O064'],'summary':r['summary'],'canonical_writes':0})
print(json.dumps({'status':result['status'],'passed':result['checks_passed'],'total':result['checks_total'],'seal_sha256':sha(H/'sealed-handoff.json')}))
