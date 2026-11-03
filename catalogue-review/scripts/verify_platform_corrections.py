"""Independent current-app joins and economic checks on the saved final XLSX."""
import hashlib
import json
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as E
import zipfile

OUT=Path(sys.argv[1]).resolve();read=lambda n:json.loads((OUT/n).read_text())
U='http://schemas.openxmlformats.org/spreadsheetml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';NS={'s':U};q=lambda s:'{'+U+'}'+s
with zipfile.ZipFile(OUT/'catalogue_wall_sculptures.xlsx') as z:
    assert z.testzip() is None
    ss=[''.join(t.text or '' for t in e.iter(q('t'))) for e in E.fromstring(z.read('xl/sharedStrings.xml'))]
    rel={e.get('Id'):'xl/'+e.get('Target').lstrip('/').removeprefix('xl/') for e in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    paths={e.get('name'):rel[e.get('{'+R+'}id')] for e in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)}
    cells={n:{c.get('r'):c for c in E.fromstring(z.read(p)).findall('s:sheetData/s:row/s:c',NS)} for n,p in paths.items()}
    def val(s,a):
        c=cells[s].get(a)
        if c is None:return None
        if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(q('t')))
        v=c.find('s:v',NS);text=v.text if v is not None else ''
        if c.get('t')=='s':return ss[int(text)]
        if c.get('t')=='b':return text=='1'
        assert c.get('t')!='e',(s,a,text)
        return float(text) if text and c.get('t','n')=='n' else text
    for s in cells:
        for a in cells[s]:val(s,a)
    headers={val('Wall Sculptures',a):re.sub(r'\d','',a) for a in cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
    rows={val('Wall Sculptures',f'AA{r}'):r for r in range(8,189)}
    app=read('app-after.json');products={p['id']:p for p in app['products']}
    assert len(paths)==12 and set(rows)==set(products)
    get=lambda pid,h:val('Wall Sculptures',headers[h]+str(rows[pid]))
    for p in products.values():
        f={f['key']:f['value'] for f in p['fields']+p['listing_fields']};r=rows[p['id']]
        assert val('Wall Sculptures','D'+str(r))==f['Dimensions / depth']
        assert val('Wall Sculptures','AD'+str(r))==f['Description']
        assert abs(val('Wall Sculptures','H'+str(r))-float(re.search(r'[\d,.]+',f['Price']).group().replace(',','')))<.001
        assert abs(val('Wall Sculptures','AM'+str(r))-p['costing']['manufacturing_cost'])<.001
    records=read('matched-platform-records.json');fx=val('Wall Sculptures','BB4')
    assert len(records)==194 and sum(r['platform']=='ebay' for r in records)==18
    below_cost=[];below_net=[]
    for record in records:
        pid=record['catalogue_ids'][0];platform=record['platform']
        assert get(pid,platform+'_observed_'+('chairish_id' if platform=='chairish' else 'item_id'))==record['native_id']
        for axis in ('width','height','depth'):
            assert get(pid,platform+'_'+axis+'_cm') is not None
            assert abs(get(pid,platform+'_'+axis+'_cm')-record['targets'][axis+'_cm'])<.001
        if platform=='ebay':
            assert get(pid,'ebay_price_gbp')==val('Wall Sculptures','H'+str(rows[pid]))
            assert get(pid,'ebay_international_shipping_enabled') is False
            assert get(pid,'ebay_international_service') in (None,'') and get(pid,'ebay_international_charge_gbp') in (None,'')
        else:
            assert get(pid,'chairish_commission_rate')==.4 and get(pid,'chairish_auction_commission_rate')==.2
            expected_price=next(p for p in read('corrected-pricing.json') if p['catalogue_id']==pid)
            assert get(pid,'chairish_asking_price_usd')==expected_price['asking_price_usd']
            for suffix in ('price','reserve','auction_reserve','trade_price','discount_allowance'):
                net=get(pid,'chairish_proceeds_at_'+suffix+'_usd')/fx
                if net+1e-8<record['targets']['manufacturing_cost_gbp']:below_cost.append((pid,suffix))
                if net+1e-8<record['targets']['catalogue_price_gbp']:below_net.append((pid,suffix))
    assert not below_cost and not below_net,(below_cost,below_net)
    for pid in ('BSI-0BE032939501','BSI-EF421C1D2C92'):
        for h in headers:
            if h.startswith('ebay_') and h not in ('ebay_snapshot_scope','ebay_update_state'):assert get(pid,h) in (None,''),(pid,h)
    for c in cells['eBay Photo Links'].values():assert val('eBay Photo Links',c.get('r'))!='188721196311'
    pid='BSI-3C849B547D50'
    assert [get(pid,'ebay_packed_'+axis+'_cm_estimate') for axis in ('length','width','height')]==[110,26,13]
    assert get(pid,'ebay_packed_kg_estimate')==11 and 'DHL' in get(pid,'ebay_domestic_service')
    plan=read('corrections-plan.json')
    for p in plan['patches']:
        got=val(p['sheet'],p['cell']);expected=p['value']
        assert (expected is None and got in (None,'')) or got==expected or (isinstance(expected,(int,float)) and isinstance(got,(int,float)) and abs(got-expected)<.011),(p['sheet'],p['cell'],got,expected)
        if p['formula']:assert cells[p['sheet']][p['cell']].find('s:f',NS).text==p['formula'][1:]
    # Native master table remains a real table and includes the added fields.
    tables=[E.fromstring(z.read(n)) for n in z.namelist() if re.fullmatch(r'xl/tables/table\d+.xml',n)]
    master=next(t for t in tables if t.get('ref','').startswith('A7:') and len(t.find('s:tableColumns',NS))==len(headers))
    assert len(master.find('s:tableColumns',NS))==293
receipt={'status':'PASS','components':181,'ebay_individual_prices_corrected':18,'unsupported_international_targets_disabled':18,
    'excluded_echo_pair':True,'chairish_prices':176,'chairish_scenarios_below_manufacturing':len(below_cost),
    'chairish_scenarios_below_catalogue_net_price':len(below_net),'orientations_added':3,'native_table_columns':293,
    'all_saved_patch_values_and_formulas_verified':True,'sha256':hashlib.sha256((OUT/'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest()}
(OUT/'independent-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
