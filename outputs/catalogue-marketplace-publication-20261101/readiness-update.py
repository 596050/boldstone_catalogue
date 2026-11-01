"""Apply the owner's scoped three-working-day dispatch confirmation with CAS."""
import csv, json, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8767'

def get(path):
    with urllib.request.urlopen(BASE+path,timeout=120) as response:
        return json.load(response)

def fields(product):
    return {f['key']:f for f in product['fields']+product['listing_fields']}
AUTHORITY = ('Owner confirmation 1 November 2026: "They are ready within 3 days", '
             'answering the dispatch question for the 156 sapr_2972 imported offers '
             'using Simple Delivery; Folded Fan - White excluded from this question.')

def copy_update(text, html=False):
    if html:
        text, n1 = re.subn(r'(<strong>Availability:</strong>\s*)Made to order', r'\1Ready to dispatch', text)
        text, n2 = re.subn(r'<strong>Production lead time:</strong>\s*1[–-]2 weeks',
                          '<strong>Dispatch time:</strong> Within 3 working days', text)
    else:
        text, n1 = re.subn(r'(?m)^Availability: Made to order$', 'Availability: Ready to dispatch', text)
        text, n2 = re.subn(r'(?m)^Production lead time: 1[–-]2 weeks$', 'Dispatch time: Within 3 working days', text)
    assert (n1, n2) == (1, 1), (n1, n2, text)
    return text

def main():
    rows = list(csv.reader((OUT/'ebay-sapr-157-missing-wall-sculpture-drafts.csv').open()))
    sku_col = rows[4].index('Custom label (SKU)')
    skus = {r[sku_col] for r in rows[5:]} - {'FF-1-70.50'}
    assert len(skus) == 156
    prepared_path = OUT/'current-prepared-catalogue.json'
    prepared = json.loads(prepared_path.read_text())
    records = [r for r in prepared['records'] if r['sku'] in skus]
    assert len(records) == 156
    ids = {r['catalogue_id'] for r in records}
    planpath = OUT/'readiness-update-plan.json'
    if planpath.exists():
        plan = json.loads(planpath.read_text())
        before = json.loads((OUT/'readiness-app-before.json').read_text())
    else:
        before = get('/api/specifications')
        (OUT/'readiness-app-before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2))
        plan = {'authority':AUTHORITY,'created_utc':datetime.now(timezone.utc).isoformat(),'products':[]}
        for p in before['products']:
            if p['id'] not in ids: continue
            ff = fields(p)
            assert ff['Availability']['value'] == 'Made to order'
            target = {'Availability':'Ready to dispatch','Lead time':'Within 3 working days',
                      'Description':copy_update(ff['Description']['value'])}
            plan['products'].append({'catalogue_id':p['id'],'name':p['name'],
                'changes':[{'field':k,'before':ff[k],'value':v} for k,v in target.items()]})
        assert len(plan['products']) == 156
        planpath.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    boot = get('/api/bootstrap')
    assert boot['source']['register_sha256'] == before['source_hash']
    current = {p['id']:p for p in get('/api/specifications')['products']}
    receipt_path=OUT/'readiness-app-receipts.json'
    receipts=json.loads(receipt_path.read_text()) if receipt_path.exists() else []
    for n,p in enumerate(plan['products'],1):
        ff=fields(current[p['catalogue_id']])
        for c in p['changes']:
            f=ff[c['field']]
            if f['value']==c['value']: continue
            assert (f['value'],f['version'])==(c['before']['value'],c['before']['version']),('Concurrent change',p['catalogue_id'],c['field'])
            data={'kind':'field','product_id':p['catalogue_id'],'item_id':c['field'],'version':f['version'],
                  'data':{'decision':'edit','value':c['value'],'certainty':'confirmed','evidence':AUTHORITY,
                          'notes':'Owner-confirmed dispatch readiness. Production, packing and carrier transit are separate.'}}
            req=urllib.request.Request(BASE+'/api/reviews',data=json.dumps(data).encode(),method='POST',
                headers={'Content-Type':'application/json','X-Review-Token':boot['csrf_token'],'Origin':BASE})
            with urllib.request.urlopen(req,timeout=120) as r: saved=json.load(r)
            assert saved['data']['value']==c['value']
            receipts.append({'catalogue_id':p['catalogue_id'],'field':c['field'],'before':f,'after':saved})
            receipt_path.write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
        if n%20==0: print(json.dumps({'saved_products':n,'total':156}),flush=True)
    after=get('/api/specifications'); after_byid={p['id']:p for p in after['products']}
    for p in plan['products']:
        for c in p['changes']: assert fields(after_byid[p['catalogue_id']])[c['field']]['value']==c['value']
    for old in before['products']:
        new=after_byid[old['id']]
        assert new['costing']==old['costing']
        assert new['photos']==old['photos'] and new['listing_decision']==old['listing_decision']
        for key,f in fields(old).items():
            if old['id'] in ids and key in {'Availability','Lead time','Description'}: continue
            assert fields(new)[key]['value']==f['value'],(old['id'],key)
    if not prepared.get('readiness_policy_utc'):
        (OUT/'prepared-before-readiness.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2))
        for r in records:
            r['description_html']=copy_update(r['description_html'],html=True)
            r['description_text']=copy_update(r['description_text'])
            r['handling_working_days_required']=3
            r['availability']='Ready to dispatch'
            r['readiness_authority']=AUTHORITY
        prepared['readiness_policy_utc']=datetime.now(timezone.utc).isoformat()
        prepared_path.write_text(json.dumps(prepared,ensure_ascii=False,indent=2))
    (OUT/'readiness-app-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2))
    result={'status':'PASS_VERSION_CHECKED_READBACK','products':156,'fields':468,
            'costs_images_other_fields_unchanged':True,'authority':AUTHORITY,'completed_utc':datetime.now(timezone.utc).isoformat()}
    (OUT/'readiness-verification.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)

if __name__=='__main__': main()
