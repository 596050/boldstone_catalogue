"""Owner-authorized channel completeness and dispatch update, using field CAS."""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
sys.path.insert(0,str(ROOT/'catalogue-review'))
from channel_content import (values, appearance, product_type, marketplace_title,
    complete_description, description_html, validate, DISPATCH_EXCEPTIONS)
BASE='http://127.0.0.1:8767'
AUTHORITY=('Owner instruction 1 November 2026: fill evidence-supported channel information; '
           '"Keep three working days where required; 10 elsewhere". '
           'Gypsum-based material and applied surface-effect wording previously authorized. '
           'No new physical measurements, stock counts, GTINs or certification claims.')
def get(path):
    with urllib.request.urlopen(BASE+path,timeout=120) as r:return json.load(r)
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2))
def main(apply=False):
    prepared=json.loads((OUT/'current-prepared-catalogue.json').read_text())
    records={r['catalogue_id']:r for r in prepared['records']}
    planfile=OUT/'channel-requirements-plan.json'
    if planfile.exists():
        plan=json.loads(planfile.read_text());before=json.loads((OUT/'channel-requirements-before.json').read_text())
    else:
        before=get('/api/specifications');dump('channel-requirements-before.json',before)
        plan={'authority':AUTHORITY,'created_utc':datetime.now(timezone.utc).isoformat(),'products':[]}
        for p in before['products']:
            f={x['key']:x for x in p['fields']+p['listing_fields']}
            r=records.get(p['id'],{})
            sku=r.get('sku') or 'BOLD-'+p['id'].removeprefix('BSI-')
            text=complete_description(p,sku,10)
            errors=validate(p,{**r,'sku':sku,'description_text':text})
            assert not errors,(p['id'],errors)
            gaps=('GTIN/EAN or channel-approved exemption not verified; legal manufacturer/contact and '
                  'country of manufacture not verified for channel compliance; physical available stock '
                  'must be entered separately from quantity per sale. Artwork date/edition/provenance '
                  'and category-specific attributes require truthful evidence where requested. '
                  'Amazon/Tesco onboarding and category template acceptance are not verified. '
                  'TikTok extended handling or two-working-day readiness remains unresolved.')
            if 'alias unresolved' in f['Sale unit']['value']:
                gaps+=' Retained source flags an unresolved native Wall Circle alias; match by stable catalogue ID/SKU.'
            target={'Lead time':'Within 10 working days; platform-required exceptions recorded separately',
                    'Description':text,'Brand':'Boldstone','Product type':product_type(p),
                    'Model / catalogue reference':p['id'],'Seller SKU':sku,
                    'Colour / appearance':appearance(p),'Quantity per sale':'1 individual sculpture or panel',
                    'Marketplace title':marketplace_title(p),'Dispatch exceptions':DISPATCH_EXCEPTIONS,
                    'Product identifier status':'Seller SKU is not a GTIN/EAN. No verified barcode recorded; obtain an approved exemption where applicable.',
                    'Channel information gaps':gaps}
            plan['products'].append({'catalogue_id':p['id'],'name':p['name'],
                'changes':[{'field':k,'before':f[k],'value':v} for k,v in target.items() if f[k]['value']!=v]})
        assert len(plan['products'])==181
        dump('channel-requirements-plan.json',plan)
    if not apply:
        print(json.dumps({'planned_products':len(plan['products']),'planned_fields':sum(len(p['changes']) for p in plan['products'])}));return
    boot=get('/api/bootstrap');assert boot['source']['register_sha256']==before['source_hash']
    current={p['id']:p for p in get('/api/specifications')['products']}
    receiptfile=OUT/'channel-requirements-receipts.json'
    receipts=json.loads(receiptfile.read_text()) if receiptfile.exists() else []
    for n,p in enumerate(plan['products'],1):
        ff={f['key']:f for f in current[p['catalogue_id']]['fields']+current[p['catalogue_id']]['listing_fields']}
        for c in p['changes']:
            f=ff[c['field']]
            if f['value']==c['value']:continue
            assert (f['value'],f['version'])==(c['before']['value'],c['before']['version']),('Concurrent change',p['catalogue_id'],c['field'])
            payload={'kind':'field','product_id':p['catalogue_id'],'item_id':c['field'],'version':f['version'],
                     'data':{'decision':'edit','value':c['value'],'certainty':'source_claim','evidence':AUTHORITY,
                             'notes':'Derived from current catalogue and owner policy; account approval and physical stock are separate.'}}
            req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps(payload).encode(),method='POST',
                headers={'Content-Type':'application/json','Origin':BASE,'X-Review-Token':boot['csrf_token']})
            with urllib.request.urlopen(req,timeout=120) as response:saved=json.load(response)
            assert saved['data']['value']==c['value']
            receipts.append({'catalogue_id':p['catalogue_id'],'field':c['field'],'before':f,'after':saved})
            dump('channel-requirements-receipts.json',receipts)
        if n%30==0:print(json.dumps({'saved_products':n,'total':181}),flush=True)
    after=get('/api/specifications');byid={p['id']:p for p in after['products']}
    for p in plan['products']:
        for c in p['changes']:assert values(byid[p['catalogue_id']])[c['field']]==c['value']
    changed={c['field'] for p in plan['products'] for c in p['changes']}
    for p in before['products']:
        new=byid[p['id']]
        assert p['costing']==new['costing'] and p['photos']==new['photos'] and p['listing_decision']==new['listing_decision']
        for k,v in values(p).items():
            if k not in changed:assert values(new)[k]==v,(p['id'],k)
    if not (OUT/'prepared-before-channel-requirements.json').exists():dump('prepared-before-channel-requirements.json',prepared)
    for r in prepared['records']:
        p=byid[r['catalogue_id']];f=values(p)
        r.update(description_text=f['Description'],description_html=description_html(f['Description']),
                 marketplace_title=f['Marketplace title'],ebay_title=marketplace_title(p,80),
                 brand='Boldstone',product_type=f['Product type'],colour=f['Colour / appearance'],quantity_per_sale=1,
                 handling_working_days_default=10,dispatch_exceptions=f['Dispatch exceptions'],
                 channel_information_gaps=f['Channel information gaps'],us_shipping=p['us_shipping'])
        r.pop('handling_working_days_required',None)
        r['channel_descriptions']={'ebay_simple_delivery':complete_description(p,r['sku'],3,channel='ebay'),
                                   'ebay_custom_delivery':complete_description(p,r['sku'],10,channel='ebay'),
                                   'tiktok_draft':complete_description(p,r['sku'],10,channel='tiktok')}
    prepared['channel_requirements_utc']=datetime.now(timezone.utc).isoformat()
    dump('current-prepared-catalogue.json',prepared);dump('channel-requirements-after.json',after)
    result={'status':'PASS_VERSION_CHECKED_READBACK','products':181,'included_products':len(prepared['records']),
            'fields':len(receipts),'costs_images_inclusion_unchanged':True,'dispatch_default_working_days':10,
            'exceptions':'3 where required; TikTok 2-day readiness unresolved',
            'completed_utc':datetime.now(timezone.utc).isoformat()}
    dump('channel-requirements-verification.json',result);print(json.dumps(result))
if __name__=='__main__':main('--apply' in sys.argv)
