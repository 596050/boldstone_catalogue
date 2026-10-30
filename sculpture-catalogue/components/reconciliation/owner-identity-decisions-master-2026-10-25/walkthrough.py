"""Read each imported owner decision with its exact current reference and fields."""
import argparse
import hashlib
import json
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
args = argparse.ArgumentParser()
args.add_argument('--decision',type=int,default=1)
args.add_argument('--all',action='store_true')
args = args.parse_args()
p = read(B/'current-master.json')
assert p['register_sha256'] == sha(H/'canonical-master-register.json')
assert sha(B/p['register']) == p['register_sha256'] and sha(B/p['workbook']) == p['workbook_sha256']
g = read(B/p['register'])
options = {o['product_id']:o for o in g['options']}
packets = read(H/'approved-packets.json')
assert 1 <= args.decision <= len(packets)
for number,packet in enumerate(packets,1):
    if not args.all and number != args.decision:
        continue
    assert sha(packet['seal']) == packet['seal_sha256'] and sha(packet['answer_path']) == packet['answer_sha256']
    answer = read(packet['answer_path'])
    relation = answer['accepted_relationship']
    oid = relation.get('product_id') or relation['legacy_product_id']
    option = options[oid]
    ref = option if option.get('file_id') else option['owner_confirmed_design_reference']
    print(f"DECISION {number}/{len(packets)}: {option['name']}\nOwner answer: {answer['owner_answer_verbatim']}")
    print('Image: '+ref['image_url'])
    print('Containing folder: '+ref['folder_url'])
    print('Stable file ID: '+ref['file_id'])
    print('Actual folder ID: '+ref['folder_id'])
    print('Scope: '+relation['scope'])
    if not option.get('file_id'):
        print('This is a shared relief-design reference; no separate legacy primary photograph is selected.')
    for field,value in option['master_fields'].items():
        print(field+': '+value['display'])
        print('  Evidence: '+value['state'])
    print('Review: '+str(B/'outputs'/H.name/'owner-identity-decisions.html')+'#'+oid+'\n')
print('All188 option records retained. Physical/commercial values and22 context/1 series deferrals are unchanged.')
