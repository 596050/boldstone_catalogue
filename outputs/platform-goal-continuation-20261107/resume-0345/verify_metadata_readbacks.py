"""Independently parse saved native fields, rather than trusting receipt values."""
import hashlib
import json
import math
import re
import argparse
from datetime import datetime,timezone
from pathlib import Path

OUT=Path(__file__).parent
parser=argparse.ArgumentParser()
parser.add_argument('--include-first-fourteen',action='store_true')
args=parser.parse_args()
queue=(json.loads((OUT/'full-gallery-reconciliation.json').read_text())['records'] if args.include_first_fourteen
       else json.loads((OUT/'ebay-full-metadata-queue.json').read_text()))
targets={r['native_draft_id']:r for r in queue}
receipts=json.loads((OUT.parent/'resume-0220/ebay-metadata-receipts.json').read_text())
if args.include_first_fourteen:
    initial=OUT.parent/'resume-0041'
    by_hash={}
    for path in initial.glob('*.txt'):
        by_hash.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(),[]).append(path)
    verified=json.loads((initial/'ebay-independent-readback-verification.json').read_text())
    assert verified['drafts']==14
    for record in verified['records']:
        matches=by_hash.get(record['evidence_sha256'],[])
        assert matches,('Original verified readback missing',record['sku'])
        receipts.append(dict(sku=record['sku'],native_draft_id=record['native_draft_id'],evidence=str(matches[0])))
assert len(receipts)==len({r['native_draft_id'] for r in receipts})

def field(text,label):
    matches=re.findall(r'^\s*\d+ text field \(settable\) '+re.escape(label)+r', Value: ([^\n]*)$',text,re.M)
    assert len(matches)==1,('Missing or ambiguous native field',label,matches)
    return matches[0]

def dimension(text,label):
    lines=text.splitlines()
    positions=[i for i,l in enumerate(lines) if re.search(r'\d+ button '+re.escape(label)+r'$',l)]
    assert len(positions)==1,('Missing dimension label',label)
    value=next(l for l in lines[positions[0]+1:] if re.match(r'\s*\d+ button ',l))
    match=re.search(r'button (\d+(?:\.\d+)?) cm$',value)
    assert match,('Unreadable native dimension',label,value)
    return float(match[1])

def copy_key(text):
    return sorted(line.strip().removeprefix('Custom design: ') for line in text.splitlines() if line.strip())

records=[]
for receipt in receipts:
    p=targets[receipt['native_draft_id']]
    text=Path(receipt['evidence']).read_text()
    assert 'draftId='+p['native_draft_id'] in text
    assert field(text,'Custom label (SKU)')==p['sku']
    assert field(text,'Item title')==p['title']
    raw_price=field(text,'Item price')
    price=float(raw_price)
    assert math.isfinite(price) and price>0 and abs(price-p['price_gbp'])<0.001
    h,w,d=[dimension(text,label) for label in ['Item Height','Item Width','Item Length']]
    assert [h,w,d]==[p['height_cm'],p['width_cm'],p['depth_cm']]
    descriptions=re.findall(r'^\s*\d+ text entry area \(settable\) Description, Value: (.*?)(?=\n\s*\d+ [A-Za-z]|\Z)',text,re.M|re.S)
    assert len(descriptions)==1,('Description not uniquely readable',p['sku'])
    assert copy_key(descriptions[0])==copy_key(p['description']),('Description differs',p['sku'])
    assert 'Within 3 working days.' in descriptions[0]
    assert 'Made from a gypsum-based material.' in descriptions[0]
    assert 'Sally Price' in descriptions[0]
    assert re.search(r'button Gypsum-based material$',text,re.M)
    assert re.search(r'button New Item condition$',text,re.M)
    photos=int(re.search(r'text (\d+) out of 25 photos or videos uploaded',text)[1])
    assert photos==len(p['desired_gallery_ids']),('Full-source photo count mismatch',p['sku'],photos,len(p['desired_gallery_ids']))
    records.append(dict(sku=p['sku'],native_draft_id=p['native_draft_id'],price_gbp=price,
                        dimensions_hwd_cm=[h,w,d],photos=photos,
                        evidence_sha256=hashlib.sha256(text.encode()).hexdigest(),
                        status='PASS_NATIVE_SAVED_FIELDS_AND_FULL_SOURCE_PHOTO_COUNT'))
result=dict(status='PASS',checked_utc=datetime.now(timezone.utc).isoformat(),verified_existing_drafts=len(records),
            records=records,scope='Direct parsing of saved native AX readbacks: exact SKU/title, finite price, H/W/depth, full description content, material, condition and complete-source photo count.',
            delivery_cleared=False,publication_implied=False,new_listings_created=0)
filename='all65-metadata-independent-verification.json' if args.include_first_fourteen else 'metadata-independent-verification.json'
(OUT/filename).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))
