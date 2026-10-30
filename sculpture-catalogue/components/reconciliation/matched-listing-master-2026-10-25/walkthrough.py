"""Step through the current labelled proposals and all188 listing treatments."""
import argparse
import hashlib
import json
from pathlib import Path

H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parser=argparse.ArgumentParser();parser.add_argument('--row',type=int,default=1);parser.add_argument('--all',action='store_true');parser.add_argument('--option',type=int);parser.add_argument('--depth-row',type=int);parser.add_argument('--coral',action='store_true');args=parser.parse_args()
p=read(B/'current-master.json');assert p['register_sha256']==sha(H/'canonical-master-register.json')
assert sha(B/p['register'])==p['register_sha256']and sha(B/p['workbook'])==p['workbook_sha256']
g=read(B/p['register']);options={o['product_id']:o for o in g['options']}
def links(o):
    ref=o if o.get('file_id')else o['owner_confirmed_design_reference']
    print('Image: '+ref['image_url']+'\nContaining folder: '+ref['folder_url'])
    print('Stable file ID: '+ref['file_id']+'\nActual folder ID: '+ref['folder_id'])
def fields(o):
    for name,value in o['master_fields'].items():print(name+': '+value['display']+'\nEvidence: '+value['state'])
if args.option:
    plan=read(g['current_listing_treatment_plan']['register']);assert 1<=args.option<=188
    row=plan['options'][args.option-1];o=options[row['product_id']];assert row['accepted_working_fields']==o['master_fields']
    print('OPTION '+str(args.option)+'/188: '+o['name']+' / '+o['product_id']);links(o)
    print('Listing treatment: '+row['listing_treatment']+'\nReason: '+row['reason'])
    print('Selected source SKU: '+(row['selected_existing_source_sku']or'(no exact selected SKU)'))
    print('Proposed listing SKU: '+(row['proposed_listing_sku']or'(none; retain current qualification)'))
    print('Local Shopify handle: '+(row['selected_local_shopify_handle']or'(no exact selected handle)'));fields(o)
    print('Local listing plan only; native execution is not performed.');raise SystemExit(0)
if args.coral:
    o=options['BSI-0C2CB099DDEB'];print(o['name']);links(o);fields(o);raise SystemExit(0)
if args.depth_row:
    assert 1<=args.depth_row<=14
    row=read(H/'depth-estimate-packet.json')['rows'][args.depth_row-1];o=options[row['product_id']]
    assert o['master_fields']['Dimensions / depth']['depth_estimate']==row['after']['depth_estimate']
    print('DEPTH '+str(args.depth_row)+'/14: '+o['name']);links(o)
    print(o['master_fields']['Dimensions / depth']['display']);raise SystemExit(0)
rows=read(H/'specification-completion-packet.json')['changes'];assert 1<=args.row<=30
for number,row in enumerate(rows,1):
    if not args.all and number!=args.row:continue
    o=options[row['product_id']];assert o['master_fields'][row['field']]==row['after']
    print('PROPOSAL '+str(number)+'/30: '+o['name']+' / '+row['field']);links(o)
    print(row['after']['display']+'\nEvidence: '+row['after']['state']+'\nBasis: '+row['after']['basis']+'\n')
print('Proposals remain estimates or hypotheses. No new physical measurement, exact native match or stock verification is inferred.')
