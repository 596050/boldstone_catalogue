"""Walk through each of the38 exported Shopify wall products in the terminal."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'catalogue-terminal-walkthrough-20261024'))
from navigation_projection import frozen_binding,native_reference

H = Path(__file__).resolve().parent
arg = argparse.ArgumentParser()
arg.add_argument('--product', type=int, default=1)
arg.add_argument('--image', help='Exact review image ID, e.g. S051')
arg.add_argument('--specifications', action='store_true')
args = arg.parse_args()
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
seal = read(H / 'sealed-handoff.json')
assert all(sha(p) == digest for p, digest in seal['files'].items())
packet = read(H / 'shopify-wall-gallery-visual-review.json')
pointer=read(H.parents[1]/'sculpture-catalogue/current-master.json')
assert sha(H.parents[1] / 'sculpture-catalogue/current-master.json') == packet['baseline_pointer_sha256'] or frozen_binding(pointer,'pointer',packet['baseline_pointer_sha256']), 'Rebind navigation after a master data edit.'
products = list(dict.fromkeys(r['handle'] for r in packet['records']))
if args.image:
    rows = [r for r in packet['records'] if r['review_id'] == args.image]
    if not rows:
        raise SystemExit('Image ID absent from this117-image review.')
else:
    if not 1 <= args.product <= len(products):
        raise SystemExit('Product numbers are1 through38.')
    rows = [r for r in packet['records'] if r['handle'] == products[args.product-1]]
print(f"PRODUCT {products.index(rows[0]['handle'])+1}/38: {rows[0]['title']}")
print('Handle: ' + rows[0]['handle'])
print('Raw SKU: ' + (', '.join(rows[0]['exported_skus']) or '(blank)'))
print('Platform source pair: ' + (', '.join(rows[0]['matched_squarespace_offer_refs']) or 'No nonempty-SKU pair in the local export'))
for r in rows:
    chosen = r['native_photo_correspondence'] or r['native_scene_or_design_candidate']
    n = native_reference(pointer,chosen['native_reference']['file_id'])
    print(f"\n{r['review_id']} | image {r['gallery_order']} | {r['source_visual_role']}")
    print('Correspondence: ' + r['native_correspondence_disposition'])
    print('Image: ' + n['image_url'])
    print('Containing folder: ' + n['folder_url'])
    print('Stable file ID: ' + n['file_id'])
    print('Actual parent ID: ' + n['folder_id'])
    print('Qualification: ' + r['source_role_and_uncertainty_note'])
    print('Local Shopify CSV row: ' + str(r['exported_gallery_row']['source_row']['logical_row_including_header']))
if args.specifications:
    cross = read(packet['crosswalk']['path'])
    assert sha(packet['crosswalk']['path']) == packet['crosswalk']['sha256']
    refs = rows[0]['matched_squarespace_offer_refs']
    options = {}
    for source in cross['squarespace_source_records']:
        if source['offer_ref'] in refs:
            for o in source['related_current_individual_options']:
                options[o['product_id']] = o
    for o in options.values():
        print('\nCURRENT EXISTING OPTION: ' + o['name'] + ' / ' + o['product_id'])
        fields = o.get('full_qualified_working_fields') or o.get('master_fields') or {}
        if not fields:
            raise AssertionError('Expected full qualified field objects in the R5 option projection')
        for name, field in fields.items():
            print(name + ': ' + field['display'])
            print('  Evidence state: ' + field['state'])
print('\nReview: ' + str(H / 'index.html') + '#' + rows[0]['handle'])
print('Product gallery membership does not certify variant-specific image, physical specifications, price, availability or stock.')
