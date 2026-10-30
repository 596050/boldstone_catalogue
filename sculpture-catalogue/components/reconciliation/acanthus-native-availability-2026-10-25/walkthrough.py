"""Display current specifications without treating deleted references as available."""
from pathlib import Path
import argparse
import hashlib
import json
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
arg=argparse.ArgumentParser();arg.add_argument('--option',type=int);arg.add_argument('--deleted',action='store_true')
arg.add_argument('--row',type=int,default=1);arg.add_argument('--all',action='store_true');arg.add_argument('--depth-row',type=int);arg.add_argument('--coral',action='store_true');a=arg.parse_args()
p=read(B/'current-master.json');g=read(B/p['register']);assert sha(B/p['register'])==p['register_sha256']
overlay=read(H/'availability-overlay.json');assert p['register_sha256']==overlay['baseline_register_sha256']
deleted={r['file_id']:r for r in overlay['rows']};options={o['product_id']:o for o in g['options']}
MASTER=B/'components/reconciliation/matched-listing-master-2026-10-25'
def links(o):
    ref=o if o.get('file_id')else o['owner_confirmed_design_reference'];fid=ref['file_id']
    if fid in deleted:print('Source image: unavailable — owner-confirmed native deletion; historical ID retained. No replacement selected by this reconciliation.')
    else:print('Image: '+ref['image_url']+'\nScope: retained source reference; this is not a new primary approval.')
    print('Containing folder: '+ref['folder_url']+'\nStable source file ID: '+fid+'\nActual folder ID: '+ref['folder_id'])
def fields(o):
    for k,v in o['master_fields'].items():print(k+': '+v['display']+'\nEvidence: '+v['state'])
if a.deleted:
    for r in overlay['rows']:print(r['name']+'\nStatus: deleted; native absence verified\nStable file ID: '+r['file_id']+'\nContaining folder: '+r['folder_url']+'\n')
elif a.option:
    plan=read(g['current_listing_treatment_plan']['register']);assert 1<=a.option<=188
    row=plan['options'][a.option-1];o=options[row['product_id']];assert row['accepted_working_fields']==o['master_fields']
    print('OPTION '+str(a.option)+'/188: '+o['name']+' / '+o['product_id']);links(o)
    print('Listing treatment: '+row['listing_treatment']+'\nReason: '+row['reason']);fields(o)
elif a.coral:
    o=options['BSI-0C2CB099DDEB'];print(o['name']);links(o);fields(o)
elif a.depth_row:
    assert 1<=a.depth_row<=14;row=read(MASTER/'depth-estimate-packet.json')['rows'][a.depth_row-1];o=options[row['product_id']]
    assert o['master_fields']['Dimensions / depth']['depth_estimate']==row['after']['depth_estimate'];print(o['name']);links(o);print(o['master_fields']['Dimensions / depth']['display'])
else:
    rows=read(MASTER/'specification-completion-packet.json')['changes'];assert 1<=a.row<=30
    for number,row in enumerate(rows,1):
        if not a.all and number!=a.row:continue
        o=options[row['product_id']];assert o['master_fields'][row['field']]==row['after']
        print('PROPOSAL '+str(number)+'/30: '+o['name']+' / '+row['field']);links(o);print(row['after']['display']+'\nEvidence: '+row['after']['state'])
print('Native-file availability applies only to the five confirmed deletions through event345. Working fields, platform evidence, owner holds and all source identities remain unchanged.')
