"""Independent before/after checks on metadata completion and preserved choices."""
from pathlib import Path
from collections import Counter
import json,sqlite3,hashlib,csv
OUT=Path(__file__).resolve().parent
before=json.loads((OUT/'before-catalogue-snapshot.json').read_text());after=json.loads((OUT/'catalogue-snapshot.json').read_text())
oldp={p['id']:p for p in before['products']};newp={p['id']:p for p in after['products']}
assert oldp.keys()==newp.keys() and len(newp)==181
for pid,p in newp.items():
    old=oldp[pid]
    for key in ('name','family','listing_decision','review_status','notes','costing'):
        assert old[key]==p[key],(pid,key)
    assert old['photos']==p['photos'],(pid,'Photo choices changed')
    oldfields={f['key']:f['value'] for f in old['fields']+old['listing_fields']}
    fields={f['key']:f['value'] for f in p['fields']+p['listing_fields']}
    assert all(v==fields[k] for k,v in oldfields.items() if k!='Description'),pid
    assert fields['Description'].startswith(oldfields['Description'])
    assert 'Delivery is quoted separately for each order.' in fields['Description']
oldi={(r['product_id'],r['image']['id']):r for r in before['images']};newi={(r['product_id'],r['image']['id']):r for r in after['images']}
assert oldi.keys()==newi.keys()
selected=set();selected_assoc=0;new_alt=set();alt_writes=0
for key,r in newi.items():
    old=oldi[key]
    assert r['metadata']==old['metadata'],(key,'Shared tags changed')
    for k in set(r['choice'])|set(old['choice']):
        if k not in ('alt','reviewed_content_hash'):assert r['choice'].get(k)==old['choice'].get(k),(key,k)
    if old['choice'].get('alt'):assert old['choice']['alt']==r['choice']['alt']
    elif r['choice'].get('alt'):new_alt.add(r['image']['id']);alt_writes+=1
    if old['image']['original'].get('dimensions'):assert old['image']['original']['dimensions']==r['image']['original']['dimensions'],key
    if 'listing' in r['choice'].get('uses',[]) and r['choice'].get('decision')!='exclude' and r['scope']=='Associated':
        assert r['choice'].get('alt','').strip(),key
        assert all(r['image']['original'].get('dimensions') or []),key
        assert len(r['image']['original']['dimensions'])==2,key
        assert r['image']['original']['dropbox_content_hash']==old['image']['original']['dropbox_content_hash'],key
        selected.add(r['image']['id']);selected_assoc+=1
report={'status':'PASS','components':len(newp),'unique_selected_photos':len(selected),'selected_associations':selected_assoc,
 'distinct_photos_with_alt_filled':len(new_alt),'alt_association_writes':alt_writes,
 'dimensions_completed':sum(not x['image']['original'].get('dimensions') for x in json.loads((OUT/'selected-images.json').read_text())),
 'selected_missing_alt':0,'selected_missing_original_dimensions':0,
 'all_product_decisions_names_prices_specifications_and_photo_choices_preserved':True,
 'existing_alt_text_preserved':True,'shared_image_tags_preserved':True,'all_181_descriptions_contain_delivery_policy':True}
(OUT/'app-preparation-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
