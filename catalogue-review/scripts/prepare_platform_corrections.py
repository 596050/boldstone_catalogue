"""Prepare bounded updates to the existing platform-enriched master workbook."""
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, ROUND_FLOOR
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as E
import zipfile

OUT = Path(sys.argv[1]).resolve()
read = lambda n: json.loads((OUT / n).read_text())
write = lambda n,v: (OUT / n).write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n')
U = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'s':U}; q=lambda s:'{'+U+'}'+s
def col(i):
    s=''
    while i:i,n=divmod(i-1,26);s=chr(65+n)+s
    return s
def index(s):
    n=0
    for c in re.sub(r'\d','',s):n=n*26+ord(c)-64
    return n
def load(z):
    ss=[''.join(t.text or '' for t in e.iter(q('t'))) for e in E.fromstring(z.read('xl/sharedStrings.xml'))]
    rel={e.get('Id'):'xl/'+e.get('Target').lstrip('/').removeprefix('xl/') for e in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    paths={e.get('name'):rel[e.get('{'+R+'}id')] for e in E.fromstring(z.read('xl/workbook.xml')).find('s:sheets',NS)}
    cells={n:{c.get('r'):c for c in E.fromstring(z.read(p)).findall('s:sheetData/s:row/s:c',NS)} for n,p in paths.items()}
    def val(n,a):
        c=cells[n].get(a)
        if c is None:return None
        if c.get('t')=='inlineStr':return ''.join(t.text or '' for t in c.iter(q('t')))
        v=c.find('s:v',NS);t=v.text if v is not None else ''
        if c.get('t')=='s':return ss[int(t)]
        if c.get('t')=='b':return t=='1'
        return float(t) if t and c.get('t','n')=='n' else t
    return paths,cells,val
with zipfile.ZipFile(OUT/'previous-catalogue.xlsx') as z: paths,cells,val=load(z)
app=read('app-after.json'); products={p['id']:p for p in app['products']}
f={p['id']:{k['key']:k for k in p['fields']+p['listing_fields']} for p in app['products']}
rows={val('Wall Sculptures',f'AA{r}'):r for r in range(8,189)}
assert set(rows)==set(products)
headers={val('Wall Sculptures',a):re.sub(r'\d','',a) for a in cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
assert len(headers)==263
records=read('matched-platform-records.json');issues=read('consistency-issues.json')
assert len(records)==194 and all(len(r['catalogue_ids'])==1 for r in records)
fx=Decimal(str(val('Wall Sculptures','BB4')))
D=lambda n:Decimal(str(n));ceil=lambda x:int(D(x).quantize(Decimal('1'),rounding=ROUND_CEILING))
round0=lambda x:int(D(x).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
floor=lambda x:int(D(x).quantize(Decimal('1'),rounding=ROUND_FLOOR))
money=lambda x:float(D(x).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
changes={};added=[]
def put(sheet,address,value,formula=None,fmt=None):
    before=val(sheet,address)
    c=cells[sheet].get(address);oldf=c.find('s:f',NS) if c is not None else None
    if before==value and (oldf.text if oldf is not None else None)==(formula[1:] if formula else None):return
    changes[(sheet,address)]={'sheet':sheet,'cell':address,'before':before,'value':value,'formula':formula,'format':fmt}
def column(header):
    if header not in headers:
        c=col(max(index(c) for c in headers.values())+1);headers[header]=c;added.append(header)
        put('Wall Sculptures',c+'7',header,fmt='header')
    return headers[header]
def target(pid,key,value,formula=None,fmt=None):
    put('Wall Sculptures',column(key)+str(rows[pid]),value,formula,fmt)
def ref(pid,key):return column(key)+str(rows[pid])

# Preserve all existing core values except the explicitly reviewed axis labels.
for change in read('orientation-changes.json'):
    pid=change['product_id'];r=rows[pid];key=change['key']
    put('Wall Sculptures',('D' if key=='Dimensions / depth' else 'AD')+str(r),change['value'])
    if key=='Description':put('Website Copy','B'+str(r),change['value'])
for a in cells['Specification Sources']:
    if not re.fullmatch(r'C\d+',a):continue
    r=int(a[1:]);pid=val('Specification Sources',a);key=val('Specification Sources','E'+str(r))
    if pid in f and any(c['product_id']==pid and c['key']==key for c in read('orientation-changes.json')):
        field=f[pid][key]
        for c,k in [('F','value'),('G','decision'),('H','certainty'),('L','evidence'),('M','notes'),('N','updated_at')]:
            v=field.get(k) or ''
            if k=='updated_at' and v:v=datetime.fromisoformat(v).isoformat(timespec='milliseconds').replace('+00:00','Z')
            put('Specification Sources',c+str(r),v)
for sheet in ('Wall Sculptures','Website Copy','Specification Sources'):
    put(sheet,'A4',f'App snapshot: {app["checked_at"]} (UTC). Platform source snapshots: 2 November 2026. Corrected platform targets: 3 November 2026. Live platform updates remain separate.')

# Editable pricing controls belong beside the existing FX and unit inputs.
controls=[('BG','Chairish discount allowance',.4,'0%'),('BH','Chairish sale commission',.4,'0%'),
          ('BI','Chairish auction commission',.2,'0%'),('BJ','Other seller fees per sale (USD)',0,'0.00'),
          ('BK','Chairish price basis','Preserve catalogue selling-price proceeds after up to 40% discount and commission. Shipping, duties and tax quotes remain separate.','text')]
for c,label,value,fmt in controls:
    put('Wall Sculptures',c+'3',label,fmt='header');put('Wall Sculptures',c+'4',value,fmt=fmt)
sources=read('reference-sources.json')
sources['chairish_commissions']='https://support.chairish.com/hc/en-us/articles/44165603442321-Chairish-Selling-Plans-Commission-Rate-Overview'
sources['chairish_auctions']='https://support.chairish.com/hc/en-us/articles/44166615383953-Chairish-Auctions'
write('reference-sources.json',sources)
put('Wall Sculptures','BL3','Chairish fee source',fmt='header');put('Wall Sculptures','BL4',sources['chairish_commissions'])

# Clear the excluded bundle's fields from both component rows. Keep each real component.
pair_pids=['BSI-0BE032939501','BSI-EF421C1D2C92']
for pid in pair_pids:
    for header,c in list(headers.items()):
        if header.startswith('ebay_') and val('Wall Sculptures',c+str(rows[pid])) not in ('',None):
            put('Wall Sculptures',c+str(rows[pid]),None)
    target(pid,'ebay_snapshot_scope','Excluded Echo pair offer; no individual eBay offer in supplied snapshot')
    target(pid,'ebay_update_state','Pair excluded by owner instruction. Individual catalogue component retained.')

pricing=[]
for record in records:
    platform=record['platform'];pid=record['catalogue_ids'][0];r=rows[pid];t=record['targets'];src=record['source']
    assert abs(float(val('Wall Sculptures','H'+str(r)))-t['catalogue_price_gbp'])<.001
    # Refresh exact cm and descriptions. Original observed snapshot cells stay intact.
    for key in ['width_cm','height_cm','depth_cm','dimensions_text','dimension_basis','description']:
        target(pid,platform+'_'+key,t[key])
    if platform=='ebay':
        target(pid,'ebay_price_gbp',t['catalogue_price_gbp'],'=H'+str(r),'0.00')
        target(pid,'ebay_international_shipping_enabled',False)
        target(pid,'ebay_international_service',None)
        target(pid,'ebay_international_charge_gbp',None)
        action='Disable international postage in the live offer. Re-enable only after a supported service and destination-specific charge are configured and checked at checkout.'
        target(pid,'ebay_international_shipping_action',action)
        target(pid,'ebay_international_shipping_review','UK only target. International service and rate are not verified; live eBay setting still requires application.')
        size=products[pid]['us_shipping']['packed_cm']
        for axis,n in zip(['length','width','height'],size):target(pid,'ebay_packed_'+axis+'_cm_estimate',n,fmt='0.00')
        target(pid,'ebay_packed_kg_estimate',products[pid]['us_shipping']['packed_kg'])
        target(pid,'ebay_package_size',src['Package size'])
        target(pid,'ebay_domestic_service',src['Domestic service'])
        if pid=='BSI-3C849B547D50':
            assert size==[110,26,13] and products[pid]['us_shipping']['packed_kg']==11
            target(pid,'ebay_package_size','Larger parcel: DHL collection eligibility 120 × 80 × 80 cm, up to 30 kg')
            target(pid,'ebay_domestic_service','DHL collection, subject to measured package and native service availability')
            target(pid,'ebay_domestic_shipping_review','Estimated package 110 × 26 × 13 cm, 11 kg. Fits published DHL collection limits, exceeds Royal Mail 61 cm limit. Measure and select an eligible carrier before live publication.')
        target(pid,'ebay_shipping_update_state','Catalogue targets corrected; physical packing and live service application outstanding')
    else:
        # Preserve the net catalogue price, not merely manufacturing break-even.
        # Whole-dollar minimums protect proceeds against platform rounding.
        net=ceil(D(t['catalogue_price_gbp'])*fx);fee=D(0);commission=D('.4');discount=D('.4');auction=D('.2')
        reserve=D(src['Reserve discount'] or 0);auction_disc=D(src['Auction reserve discount'] or 0);trade=D(src['Trade discount'] or 0)
        allowance=max(discount,reserve,auction_disc,trade)
        minimum=ceil((D(net)+fee)/(1-commission));asking=ceil(D(minimum)/(1-allowance))
        sale=round0(D(asking)*(1-reserve));auction_price=round0(D(asking)*(1-auction_disc))
        trade_price=round0(D(asking)*(1-trade));worst=round0(D(asking)*(1-allowance))
        proceeds=lambda v,rate:floor(D(v)*(1-rate)-fee)
        data={
          'net_target_usd':(net,'=ROUNDUP(H'+str(r)+'*$BB$4,0)','0'),
          'commission_rate':(.4,'=$BH$4','0%'),
          'auction_commission_rate':(.2,'=$BI$4','0%'),
          'other_fees_usd':(0,'=$BJ$4','0.00'),
          'discount_allowance':(float(allowance),'=MAX($BG$4,'+ref(pid,'chairish_observed_reserve_discount')+','+ref(pid,'chairish_observed_auction_reserve_discount')+','+ref(pid,'chairish_observed_trade_discount')+')','0%'),
          'minimum_sale_price_usd':(minimum,'=ROUNDUP(('+ref(pid,'chairish_net_target_usd')+'+'+ref(pid,'chairish_other_fees_usd')+')/(1-'+ref(pid,'chairish_commission_rate')+'),0)','0'),
          'asking_price_usd':(asking,'=ROUNDUP('+ref(pid,'chairish_minimum_sale_price_usd')+'/(1-'+ref(pid,'chairish_discount_allowance')+'),0)','0'),
          'reserve_price_usd':(sale,'=ROUND('+ref(pid,'chairish_asking_price_usd')+'*(1-'+ref(pid,'chairish_observed_reserve_discount')+'),0)','0'),
          'auction_reserve_usd':(auction_price,'=ROUND('+ref(pid,'chairish_asking_price_usd')+'*(1-'+ref(pid,'chairish_observed_auction_reserve_discount')+'),0)','0'),
          'trade_price_usd':(trade_price,'=ROUND('+ref(pid,'chairish_asking_price_usd')+'*(1-'+ref(pid,'chairish_observed_trade_discount')+'),0)','0'),
          'discounted_sale_usd':(worst,'=ROUND('+ref(pid,'chairish_asking_price_usd')+'*(1-'+ref(pid,'chairish_discount_allowance')+'),0)','0'),
        }
        for key,v in list(data.items()):target(pid,'chairish_'+key,v[0],v[1],v[2])
        for key,amount,rate,ratekey in [('price',asking,commission,'commission_rate'),('reserve',sale,commission,'commission_rate'),
              ('auction_reserve',auction_price,auction,'auction_commission_rate'),('trade_price',trade_price,commission,'commission_rate'),('discount_allowance',worst,commission,'commission_rate')]:
            pricekey={'price':'asking_price_usd','reserve':'reserve_price_usd','auction_reserve':'auction_reserve_usd','trade_price':'trade_price_usd','discount_allowance':'discounted_sale_usd'}[key]
            value=proceeds(amount,rate)
            target(pid,'chairish_proceeds_at_'+key+'_usd',value,'=ROUNDDOWN('+ref(pid,'chairish_'+pricekey)+'*(1-'+ref(pid,'chairish_'+ratekey)+')-'+ref(pid,'chairish_other_fees_usd')+',0)','0')
            assert D(value)>=D(t['catalogue_price_gbp'])*fx
        net_gbp=money(D(proceeds(worst,commission))/fx)
        target(pid,'chairish_net_after_discount_gbp',net_gbp,'=ROUND('+ref(pid,'chairish_proceeds_at_discount_allowance_usd')+'/$BB$4,2)','0.00')
        target(pid,'chairish_profit_after_discount_gbp',money(D(net_gbp)-D(t['manufacturing_cost_gbp'])),
               '=ROUND('+ref(pid,'chairish_net_after_discount_gbp')+'-AM'+str(r)+',2)','0.00')
        target(pid,'chairish_pricing_basis','Catalogue price is the seller net target. Asking price covers up to 40% discount and 40% standard commission. Auction proceeds use 20% commission. Whole-dollar rounding is conservative. Other-fee allowance is editable; shipping, import charges and taxes require separate quotes.')
        pricing.append({'catalogue_id':pid,'row':r,'catalogue_price_gbp':t['catalogue_price_gbp'],'manufacturing_cost_gbp':t['manufacturing_cost_gbp'],
            'asking_price_usd':asking,'reserve_price_usd':sale,'auction_reserve_usd':auction_price,'net_after_discount_gbp':net_gbp,
            'net_at_auction_usd':proceeds(auction_price,auction),'profit_after_discount_gbp':money(D(net_gbp)-D(t['manufacturing_cost_gbp']))})
    target(pid,platform+'_update_state','Corrected catalogue targets. Apply to existing native listing only; no live update is claimed.')

# Keep mismatched source values visible, but make the corrected targets/actions explicit.
for issue in issues:
    pid=issue['catalogue_ids'][0];platform=issue['platform'];field=issue['field']
    if platform=='ebay' and field=='Price (GBP)':
        issue['action']='Corrected ebay_price_gbp links to the catalogue price. Apply this price to the existing eBay item.';issue['severity']='Apply on platform'
    elif platform=='ebay' and field=='International postage':
        issue['catalogue_or_reference']='International shipping disabled in the corrected target'
        issue['action']='Apply ebay_international_shipping_enabled = FALSE. Service/rate fields are blank until an actual supported route is configured.';issue['severity']='Apply on platform'
    elif platform=='ebay' and field=='Selected parcel':
        issue['catalogue_or_reference']='110 × 26 × 13 cm, 11 kg estimated; DHL collection fits published size/weight limits'
        issue['action']='Package estimate and eligible-carrier target corrected. Verify measured packing and native carrier selection before publication.';issue['severity']='Packing check'
    elif platform=='chairish' and (field=='Price (USD)' or field.startswith('Proceeds at ')):
        price=next(p for p in pricing if p['catalogue_id']==pid)
        issue['catalogue_or_reference']=f'Corrected asking USD {price["asking_price_usd"]}; net after discount GBP {price["net_after_discount_gbp"]}'
        issue['action']='Chairish target prices now cover discount and commission while retaining the catalogue net price. Apply the corrected asking/reserve prices to the existing listing.';issue['severity']='Apply on platform'
review=[[i['platform'],i['native_id'],', '.join(i['catalogue_ids']),i['field'],str(i['observed']) if i['observed'] is not None else '',str(i['catalogue_or_reference']),i['action'],i['severity']] for i in issues]
for n in range(5,672):
    for j in range(8):put('Platform Review',col(j+1)+str(n),review[n-5][j] if n-5<len(review) else None)
put('Platform Review','A2','Catalogue targets corrected 3 November 2026. Original platform observations remain dated 2 November. Apply targets to existing listings; shipping still needs measured packing and destination quotes.')
for n,v in enumerate([['Chairish commission and auction rates',sources['chairish_commissions']],['Chairish pricing policy','40% discount allowance, 40% standard commission, 20% auction commission. Preserve catalogue selling-price proceeds, excluding shipping.'],['Echo pair excluded','Bundle 188721196311 removed from component platform fields and photo links. Both individual Echo components remain.']],17):
    for j,x in enumerate(v):put('Platform Review',col(j+10)+str(n),x)

photo_rows=[]
for n in range(5,195):
    row=[val('eBay Photo Links',col(j)+str(n)) for j in range(1,8)]
    if row[0] and str(row[0])!='188721196311':photo_rows.append(row)
for n in range(5,195):
    for j in range(7):put('eBay Photo Links',col(j+1)+str(n),photo_rows[n-5][j] if n-5<len(photo_rows) else None)
put('eBay Photo Links','A2','Photographs from 18 matched individual eBay offers only. Echo pair offer excluded from the component catalogue at owner request. Original supplied file retained in the audit history.')
write('corrected-pricing.json',pricing)
write('corrected-issues.json',issues)
plan={'patches':list(changes.values()),'added_master_columns':added,'last_master_column':max(index(c) for c in headers.values()),
      'headers':headers,'master_rows':rows,'review_rows':len(review),'photo_rows':len(photo_rows),
      'scope':'Correct eBay catalogue prices, disable unsupported international targets, fix Azure package/carrier target, exclude Echo bundle, gross up Chairish prices for discounts/fees, label three orientations. No live platform changes.'}
write('corrections-plan.json',plan)
print(json.dumps({'cells':len(changes),'new_columns':len(added),'chairish_prices':len(pricing),'ebay_offers':18,'orientations':3,'review_rows':len(review),'photos':len(photo_rows)}))
