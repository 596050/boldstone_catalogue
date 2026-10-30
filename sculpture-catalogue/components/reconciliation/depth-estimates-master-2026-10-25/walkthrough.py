"""Walk the14 working depth estimates with their exact references."""
import argparse
import hashlib
import json
from pathlib import Path
H=Path(__file__).resolve().parent
B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
args=argparse.ArgumentParser();args.add_argument('--row',type=int,default=1);args.add_argument('--all',action='store_true');args=args.parse_args()
p=read(B/'current-master.json')
assert p['register_sha256']==sha(H/'canonical-master-register.json')
assert sha(B/p['register'])==p['register_sha256'] and sha(B/p['workbook'])==p['workbook_sha256']
g=read(B/p['register']);options={o['product_id']:o for o in g['options']};packet=read(H/'depth-estimate-packet.json')
assert 1<=args.row<=14
for number,row in enumerate(packet['rows'],1):
    if not args.all and number!=args.row:continue
    o=options[row['product_id']];field=o['master_fields']['Dimensions / depth'];assert field==row['after']
    print(f"DEPTH {number}/14: {o['name']}\nEstimated body depth: {row['estimate']['nominal_cm']} cm; range {row['estimate']['range_cm'][0]}–{row['estimate']['range_cm'][1]} cm; not measured.")
    print('Current dimensions: '+field['display'])
    print('Image: '+o['image_url']+'\nContaining folder: '+o['folder_url'])
    print('Stable file ID: '+o['file_id']+'\nActual folder ID: '+o['folder_id']+'\n')
print('Depth is sculpture-body depth, excluding mounting stand-off and separate hardware. Actual measurement inputs remain blank.')
