"""Add one reviewed genuine source photo to two exact existing components."""
from pathlib import Path
from urllib.request import urlopen,Request
from urllib.parse import urlencode
from datetime import datetime,timezone
import json,sys

OUT=Path(__file__).parent;BASE='http://127.0.0.1:8767'
get=lambda path:json.load(urlopen(BASE+path,timeout=120))
save=lambda name,data:(OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
mode=sys.argv[1] if len(sys.argv)>1 else 'ammonite'
assert mode in ['ammonite','moon-fish','lunar-phase-iv']
proof=json.loads((OUT/(mode+'-reviewed-original.json')).read_text())
aid=proof['image_id']
pids={'ammonite':['BSI-DA27DD604F0B','BSI-C3858B1FE67E'],'moon-fish':['BSI-992BA62AA818','BSI-8AC0376F7DEF'],'lunar-phase-iv':['BSI-818D745F1357']}[mode]
label={'ammonite':'Ammonite Grande','moon-fish':'Moon Fish Wave','lunar-phase-iv':'Lunar Phase'}[mode]
before=get('/api/specifications');save('app-before-'+mode+'-selection.json',before)
before_products={p['id']:p for p in before['products']}
bootstrap=get('/api/bootstrap');token=bootstrap['csrf_token']
intents=[];receipts=[]
for pid,side in zip(pids,['left-hand','right-hand']):
    components=get('/api/image-components?'+urlencode(dict(id=aid,primary=1)))
    assert components['image']['original']['dropbox_content_hash']==proof['content_hash']
    assert 'in_situ' not in components['image']['types']
    assert pid in components['image']['component_ids']
    row=next(r for r in components['rows'] if r['product_id']==pid)
    assert row['shown'] and not row['excluded'] and not row['primary']
    if row['listing']:
        receipts.append(dict(product_id=pid,image_id=aid,status='ALREADY_SELECTED_CURRENT_READBACK',checked_utc=datetime.now(timezone.utc).isoformat()));continue
    # These exact unreviewed image records have no text/other choices to overwrite.
    assert row['image_version']==0 and row['image_member_versions']=={aid:0}
    old=before_products[pid]
    body=dict(kind='image',product_id=pid,item_id=aid,version=0,expected_content_hash=proof['content_hash'],data=dict(decision='reviewed',uses=['listing'],primary=False,order=old['photos']['listing']['count']+1,alt=f'{label} White pair showing the {side} panel and its separately sold companion.',caption=f'Only the {side} panel is supplied by this listing. The companion panel is sold separately.',notes=f'Genuine complete original reviewed on 6 November 2026 for the owner-requested Saatchi completion. Both panels fully visible. Original {proof["width"]} × {proof["height"]} pixels; bytes verified against current Dropbox metadata and content hash. Existing primary and shared image type retained.'))
    intents.append(dict(product_id=pid,image_id=aid,request=body,status='SUBMITTING',utc=datetime.now(timezone.utc).isoformat()));save(mode+'-photo-selection-intents.json',intents)
    req=Request(BASE+'/api/reviews',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':BASE,'X-Review-Token':token},method='POST')
    with urlopen(req,timeout=120) as r:result=json.load(r)
    assert result['kind']=='image' and result['product_id']==pid and result['item_id']==aid and 'listing' in result['data']['uses'] and not result['data']['primary']
    intents[-1]['status']='RESPONSE_RECEIVED';save(mode+'-photo-selection-intents.json',intents)
    receipts.append(dict(product_id=pid,image_id=aid,status='SAVED',response=result,utc=datetime.now(timezone.utc).isoformat()));save(mode+'-photo-selection-receipts.json',receipts)
after=get('/api/specifications');save('app-after-'+mode+'-selection.json',after)
by={p['id']:p for p in after['products']}
for pid,p in before_products.items():
    q=by[pid]
    assert q['fields']==p['fields'] and q['listing_fields']==p['listing_fields'] and q['costing']==p['costing'] and q['listing_decision']==p['listing_decision']
    assert q['photos']['primary_listing']==p['photos']['primary_listing']
    old_ids={i['id'] for i in p['photos']['listing']['images']};new_ids={i['id'] for i in q['photos']['listing']['images']}
    assert new_ids==old_ids|({aid} if pid in pids else set()),pid
    assert q['photos']['in_situ']['count']==p['photos']['in_situ']['count']
check=get('/api/image-components?'+urlencode(dict(id=aid,primary=1)))
assert check['image']['types']==components['image']['types']
for pid in pids:
    r=next(r for r in check['rows'] if r['product_id']==pid);assert r['listing'] and r['shown'] and not r['primary']
save(mode+'-photo-selection-verification.json',dict(status='PASS_ADDITIONAL_LISTING_SELECTIONS',selections_added=len(pids),product_ids=pids,image_id=aid,all_primaries_preserved=True,all_other_listing_selections_preserved=True,all_costs_fields_decisions_preserved=True,shared_image_types_preserved=True,source_revision_after=after['revision'],checked_utc=datetime.now(timezone.utc).isoformat()))
for i in intents:i['status']='SAVED_AND_INDEPENDENTLY_READ_BACK'
save(mode+'-photo-selection-intents.json',intents)
print(f'PASS: {len(pids)} genuine Listing selections saved; primaries, types and unrelated catalogue data preserved')
