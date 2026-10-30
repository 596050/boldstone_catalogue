import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--item',type=int,required=True,choices=range(1,7));a=p.parse_args();g=json.loads((H/'canonical-master-register.json').read_text());rows=json.loads((H/'verified-six-cases.json').read_text())['rows'];r=rows[a.item-1];o=next(x for x in g['options']if x['product_id']==r['option_id']);print('ITEM',a.item,o['name']);print('Image:',o['image_url']);print('Containing folder:',o['folder_url']);print('Stable file ID:',o['file_id']);print('Stable parent ID:',o['folder_id'])
for k,v in o['master_fields'].items():print(k+': '+v['display']+' | '+v.get('state',''))
print('Current physical verification:',o['physical_specifications_verified']);print('Publication:', 'Published'if(H/'publication-receipt.json').exists()else'Candidate; saved checks in progress')
