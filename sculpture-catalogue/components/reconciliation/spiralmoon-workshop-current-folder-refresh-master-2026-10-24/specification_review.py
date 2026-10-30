"""Show one current sculpture and its six working details. No writes or prompts."""
import argparse,hashlib,json
from pathlib import Path
H=Path(__file__).resolve().parent;B=H.parents[2]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--option',default='BSI-3635E3DC3434');p.add_argument('--list',action='store_true');p.add_argument('--basis',action='store_true');args=p.parse_args()
pointer=json.loads((B/'current-master.json').read_text());source=B/pointer['register'];raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==pointer['register_sha256'];g=json.loads(raw);active=set(g['active_option_ids']);options=[o for o in g['options']if o['product_id']in active]
if args.list:
 for i,o in enumerate(options,1):print(f"{i:03d}. {o['product_id']}  {o['name']}")
 raise SystemExit
o=next((o for o in options if o['product_id']==args.option),None)
if o is None:raise SystemExit('No active option with this exact stable ID')
print(f"{options.index(o)+1} / {len(options)}: {o['name']}\nOption: {o['product_id']}\nComponent: {o['canonical_component_id']}")
print(f"Image: {o.get('image_url')or'No exact selected image'}\nContaining folder: {o.get('folder_url')or'Unbound'}\nFile ID: {o.get('file_id')or'Unbound'}\nFolder ID: {o.get('folder_id')or'Unbound'}")
for field,value in o['master_fields'].items():
 print('\n'+field+': '+value['display'])
 if args.basis:print('Basis: '+value['basis']+'\nState: '+value['state'])
print('\nPhysical verification: '+('Recorded for this option'if o['physical_specifications_verified']else'No new measurements or maker inspection recorded; accepted working values retain their qualifications.'))
print('Photo requests remain subject to the existing owner holds and deferrals. This reader does not change them.')
