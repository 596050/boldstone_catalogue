import json
from capture_public_inventory import OUT, digest, fetch, locator, normalized, now, save

def main():
    frozen_path = OUT / 'FRESH_PUBLIC_INVENTORY.json'
    before = digest(frozen_path)
    inventory = json.loads(frozen_path.read_text())
    known = {p['native_product_id']: p for p in inventory['products']}
    probes, new = [], {}
    for offset in [200, 198]:
        url = 'https://boldstonesculpture.com/buy?offset=' + str(offset) + '&format=json'
        data, receipt = fetch(url, 'boundary-offset-' + str(offset))
        probe = {'requested_numeric_offset':offset,'receipt':receipt,'url_parameter_semantics':'Server supplies numeric offsets in ordinary public URLs; its exact indexing/hidden-record semantics are not documented in the captured response. No opaque cursor was modified.'}
        if receipt.get('status') == 200 and isinstance(data, dict):
            products = [normalized(item,receipt,'/items/' + str(index)) for index,item in enumerate(data.get('items',[]))]
            ids = [p['native_product_id'] for p in products]
            probe.update(returned_product_count=len(products),returned_native_product_ids=ids,collection_claimed_item_count=(data.get('collection') or {}).get('itemCount'),pagination=data.get('pagination'),returned_native_product_records=[{'native_product_id':p['native_product_id'],'title':p['title'],'source_locator':p['source_locator']} for p in products],overlap_with_frozen_native_ids=[i for i in ids if i in known],new_native_product_ids=[i for i in ids if i not in known],overlapping_native_records_identical_to_frozen={p['native_product_id']:p['native_record']==known[p['native_product_id']]['native_record'] for p in products if p['native_product_id'] in known})
            for product in products:
                if product['native_product_id'] not in known:
                    new.setdefault(product['native_product_id'],product)
        else:
            probe['limit'] = 'Successful native JSON object not returned; no product absence conclusion.'
        probes.append(probe)
    assert digest(frozen_path) == before
    result={'schema':'boldstone.squarespace-numeric-boundary-supplement.v1','created_utc':now(),'base_inventory_path':str(frozen_path),'base_inventory_sha256':before,'authorization':'Coordinator requested bounded offset200 and optional198 check after observing200returned/nextoffset202/itemCount208.','base_inventory_unchanged':True,'probes':probes,'new_native_product_count':len(new),'new_native_variant_count':sum(len(p['variants']) for p in new.values()),'products':list(new.values()),'base_plus_supplement_unique_native_product_count':len(known|new),'limit':'These two public numeric boundary observations do not establish authenticated account, hidden/draft inventory, universal public inventory completeness or physical stock. Base inventory remains frozen.'}
    save('BOUNDARY_INVENTORY_SUPPLEMENT.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['products','probes']},indent=2))
    for p in probes:
        print(json.dumps({k:v for k,v in p.items() if k not in ['receipt','returned_native_product_records']},indent=2))

if __name__ == '__main__':
    main()
