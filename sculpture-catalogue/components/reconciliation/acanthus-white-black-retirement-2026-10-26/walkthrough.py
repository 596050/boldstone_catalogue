"""Read one current sculpture at a time, preserving review ownership and holds."""
from pathlib import Path
import argparse,json
H=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--id');parser.add_argument('--family');parser.add_argument('--number',type=int,default=1)
a=parser.parse_args();g=json.loads((H/'canonical-master-register.json').read_text())
m=json.loads((H/'current-native-overlay.json').read_text())['current_objects']
options=[o for o in g['options'] if o['product_id'] in g['active_option_ids']]
if a.family:options=[o for o in options if o['family'].casefold()==a.family.casefold()]
if a.id:options=[o for o in options if o['product_id']==a.id]
assert options,'No active sculpture in this selection'
o=options[0] if a.id else options[a.number-1]
print(o['name']+' | '+o['product_id'])
print('Component: '+o['canonical_component_id'])
ref=o if o.get('file_id') else o.get('owner_confirmed_design_reference',{})
image=m.get(ref.get('file_id'),{});folder=m.get(image.get('folder_id') or ref.get('folder_id'),{})
print('Image: '+image.get('image_url','Recorded image currently absent'))
print('Containing folder: '+folder.get('folder_url','Recorded folder currently absent'))
print('Stable file: '+str(ref.get('file_id'))+' | stable folder: '+str(folder.get('id')))
for k,v in o['master_fields'].items():print('\n'+k+': '+v['display']+'\nEvidence: '+v['state'])
print('\nPhoto coverage: '+json.dumps(o['photo_coverage'],ensure_ascii=False))
if o['product_id'] in g['current_global_context_owner_hold']['all_held_option_ids']:
    print('In situ owner hold remains in force; do not repeat the missing-photo request.')
print('No identity, physical specification, platform or image-use decision is inferred by this readback.')
