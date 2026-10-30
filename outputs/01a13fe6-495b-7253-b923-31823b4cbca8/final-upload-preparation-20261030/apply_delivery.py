"""Add quoted-delivery wording while preserving current descriptions and owner decisions."""
from pathlib import Path
import json,sys,urllib.request,urllib.error
OUT=Path(__file__).resolve().parent;BASE='http://127.0.0.1:8767'
def get(p):return json.load(urllib.request.urlopen(BASE+p,timeout=90))
boot=get('/api/bootstrap');token=boot['csrf_token'];results=[]
wording='Delivery is quoted separately for each order. The 1-2 week lead time covers production; dispatch and transit arrangements are agreed with the delivery quote.'
for p in boot['products']:
    for key in ['Description','Name']:
        for attempt in range(3):
            live=get('/api/products/'+p['id'])
            field=next(f for f in live['fields'] if f['key']==key)
            record=next((r for r in live['reviews'] if r['kind']=='field' and r['item_id']==key),{'version':0,'data':{}})
            d=dict(record['data']);value=d.get('value') if d.get('decision')=='edit' else field['value']
            if d.get('decision')=='exclude':break
            if key=='Description':
                if wording in (value or ''):break
                assert value, 'Do not replace an empty description with delivery text'
                d.update(decision='edit',value=value.rstrip()+' '+wording)
                d['notes']=(d.get('notes','')+' Delivery quote policy added during upload preparation, 2026-10-30; no carrier, rate or transit time invented.').strip()
            else:
                if record.get('source_hash')==boot['source']['register_sha256'] or record.get('original')==field or not record['version']:break
                if value!=live['name']:raise RuntimeError('Changed name needs independent review: '+p['id'])
                d['notes']=(d.get('notes','')+' Rechecked the current component title against the current catalogue during upload preparation, 2026-10-30.').strip()
            body={'kind':'field','product_id':p['id'],'item_id':key,'version':record['version'],'data':d}
            if '--apply' not in sys.argv:break
            req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':BASE,'X-Review-Token':token})
            try:r=json.load(urllib.request.urlopen(req,timeout=90))
            except urllib.error.HTTPError as error:
                if error.code==409 and attempt<2:continue
                raise RuntimeError(error.read().decode()) from error
            assert r['data']==d
            result={'product_id':p['id'],'field':key,'version':r['version']};results.append(result)
            with (OUT/'delivery-write-receipts.jsonl').open('a') as f:f.write(json.dumps(result)+'\n')
            break
        else:raise RuntimeError('Concurrent edits repeatedly changed the description')
    print(json.dumps({'product_id':p['id'],'writes':len(results)}),flush=True)
(OUT/'delivery-policy.json').write_text(json.dumps({'production_lead_time':'1-2 weeks','requires_shipping':True,
    'delivery_charge_policy':'Quote separately per order','delivery_charge_gbp':None,'carrier':None,
    'transit_time':'Agreed with delivery quote','delivery_included_in_price':False,
    'packed_weight_and_package_dimensions':'To be established for the dispatch quote; product dimensions are not package dimensions',
    'wording':wording,'writes':results},indent=2))
