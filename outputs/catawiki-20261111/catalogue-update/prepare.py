"""Plan additive Catawiki fields and linked GBP-plus-100 price formulas."""
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, ROUND_UP
import json,sys,hashlib,xml.etree.ElementTree as E

ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,column,column_index

w=Xlsx(OUT/'previous-catalogue.xlsx');s='Wall Sculptures'
existing={w.value(s,a):column_index(a) for a in w.cells[s] if a.endswith('7') and a[:-1].isalpha()}
assert len(existing)==905 and not any(h.startswith('catawiki_') for h in existing)
review=json.loads((OUT.parent/'product-review.json').read_text());reviewed={r['product_id']:r for r in review['products']}
fxroot=E.fromstring((OUT.parent/'ecb-daily.xml').read_bytes())
fx_date=next(n.attrib['time'] for n in fxroot.iter() if 'time' in n.attrib)
fx=Decimal(next(n.attrib['rate'] for n in fxroot.iter() if n.attrib.get('currency')=='GBP'))
now=datetime.now(timezone.utc).isoformat()
excel_date=lambda d:(d-datetime(1899,12,30,tzinfo=timezone.utc)).total_seconds()/86400
fields=[
 'catawiki_price_uplift_gbp','catawiki_target_price_gbp','catawiki_target_price_eur',
 'catawiki_price_basis','catawiki_gbp_per_eur_reference','catawiki_fx_reference_date',
 'catawiki_fx_reference_source','catawiki_seller_commission_rate','catawiki_fee_vat_allowance_rate',
 'catawiki_fx_settlement_allowance_rate','catawiki_fixed_seller_fee_eur',
 'catawiki_estimated_seller_fees_eur','catawiki_estimated_net_proceeds_gbp',
 'catawiki_net_vs_catalogue_price_gbp','catawiki_profit_protection_review',
 'catawiki_reserve_price_eur','catawiki_reserve_review','catawiki_value_review',
 'catawiki_reference_number','catawiki_seller_sku','catawiki_publication_scope',
 'catawiki_title','catawiki_description','catawiki_object_type','catawiki_auction_type',
 'catawiki_language','catawiki_artist','catawiki_brand','catawiki_material','catawiki_finish',
 'catawiki_height_cm','catawiki_width_cm','catawiki_depth_cm','catawiki_weight_text',
 'catawiki_quantity_per_lot','catawiki_photo_candidate_urls','catawiki_photo_candidate_count',
 'catawiki_photo_shortfall_to_five','catawiki_photo_review','catawiki_signature',
 'catawiki_condition','catawiki_creation_year','catawiki_era','catawiki_edition',
 'catawiki_object_details_review','catawiki_shipping_profile_id','catawiki_shipping_uk_eur',
 'catawiki_shipping_europe_eur','catawiki_shipping_rest_of_world_eur','catawiki_shipping_review',
 'catawiki_exclusivity_status','catawiki_terms_status','catawiki_native_lot_id',
 'catawiki_native_edit_url','catawiki_native_status','catawiki_native_observed_utc',
 'catawiki_prepared_utc']
col={h:906+i for i,h in enumerate(fields)}
patches=[]
def put(h,row,value,style='text',formula=None):
 a=column(col[h])+str(row)
 assert w.value(s,a) is None and w.formula(s,a) is None
 p={'sheet':s,'cell':a,'before':None,'value':value,'style':style,'field':h}
 if formula:p['formula']=formula
 patches.append(p)
def f(h,row):return column(col[h])+str(row)
def inp(h):return '$'+column(col[h])+'$4'
def old(h,row):return column(existing[h])+str(row)
money=lambda n:float(Decimal(n).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
up=lambda n:float(Decimal(n).quantize(Decimal('.01'),rounding=ROUND_UP))

for h in fields:put(h,7,h,'header')
assumptions={
 'catawiki_gbp_per_eur_reference':(float(fx),'ratio'),
 'catawiki_fx_reference_date':(fx_date,'text'),
 'catawiki_fx_reference_source':('https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml','text'),
 'catawiki_seller_commission_rate':(.125,'percentage'),
 'catawiki_fee_vat_allowance_rate':(.2,'percentage'),
 'catawiki_fx_settlement_allowance_rate':(.03,'percentage')}
for h,(v,style) in assumptions.items():put(h,3,h,'header');put(h,4,v,style)
records=[]
for row in range(8,189):
 v=lambda h:w.value(s,old(h,row))
 pid=v('Product ID');r=reviewed.get(pid);included=bool(r)
 base=Decimal(str(v('Price (GBP)')));target=base+Decimal(100)
 eur=int((target/fx).to_integral_value(rounding=ROUND_UP))
 fixed=1 if eur<150 else 2 if eur<300 else 3 if eur<500 else 5 if eur<1000 else 10
 fees=Decimal(str(up((Decimal(eur)*Decimal('.125')+fixed)*Decimal('1.2'))))
 net=Decimal(str(money((Decimal(eur)-fees)*fx*Decimal('.97'))))
 gap=money(net-base)
 calc={
 'catawiki_price_uplift_gbp':(100,None,'gbp'),
 'catawiki_target_price_gbp':(money(target),f'=ROUND({old("Price (GBP)",row)}+{f("catawiki_price_uplift_gbp",row)},2)','gbp'),
 'catawiki_target_price_eur':(eur,f'=ROUNDUP({f("catawiki_target_price_gbp",row)}/{f("catawiki_gbp_per_eur_reference",row)},0)','eur'),
 'catawiki_fixed_seller_fee_eur':(fixed,f'=IF({f("catawiki_target_price_eur",row)}<150,1,IF({f("catawiki_target_price_eur",row)}<300,2,IF({f("catawiki_target_price_eur",row)}<500,3,IF({f("catawiki_target_price_eur",row)}<1000,5,10))))','eur'),
 'catawiki_estimated_seller_fees_eur':(float(fees),f'=ROUNDUP(({f("catawiki_target_price_eur",row)}*{f("catawiki_seller_commission_rate",row)}+{f("catawiki_fixed_seller_fee_eur",row)})*(1+{f("catawiki_fee_vat_allowance_rate",row)}),2)','eur'),
 'catawiki_estimated_net_proceeds_gbp':(float(net),f'=ROUND(({f("catawiki_target_price_eur",row)}-{f("catawiki_estimated_seller_fees_eur",row)})*{f("catawiki_gbp_per_eur_reference",row)}*(1-{f("catawiki_fx_settlement_allowance_rate",row)}),2)','gbp'),
 'catawiki_net_vs_catalogue_price_gbp':(gap,f'=ROUND({f("catawiki_estimated_net_proceeds_gbp",row)}-{old("Price (GBP)",row)},2)','gbp'),
 'catawiki_profit_protection_review':('Meets catalogue proceeds in planning model' if gap>=0 else 'Below catalogue proceeds in planning model',f'=IF({f("catawiki_net_vs_catalogue_price_gbp",row)}>=0,"Meets catalogue proceeds in planning model","Below catalogue proceeds in planning model")','text')}
 for h,(value,formula,style) in calc.items():put(h,row,value,style,formula)
 for h,(value,style) in assumptions.items():put(h,row,value,style,'='+inp(h))
 photo_count=len(r['photo_candidates']) if r else 0
 put('catawiki_photo_shortfall_to_five',row,max(0,5-photo_count),'integer',f'=MAX(0,5-{f("catawiki_photo_candidate_count",row)})')
 data={
 'catawiki_price_basis':'Catalogue GBP selling price + GBP100. EUR target rounded up to a whole euro. Catawiki-only proposal; not a saved native price or expert valuation. Packing and postage separate.',
 'catawiki_reserve_price_eur':'',
 'catawiki_reserve_review':'Expert approval pending. No reserve entered; normally requires expected value of at least EUR200.',
 'catawiki_value_review':'Seller target meets numeric EUR100 threshold; expert must confirm market value. Uplift alone does not establish eligibility.',
 'catawiki_reference_number':pid,'catawiki_seller_sku':v('SKU'),
 'catawiki_publication_scope':'Included publication product' if included else 'Outside current 176-product publication scope',
 'catawiki_title':v('Retail / website name'),'catawiki_description':r['draft']['Description'] if r else v('Customer-facing description'),
 'catawiki_object_type':'Relief','catawiki_auction_type':'Post-War & Contemporary Galleries',
 'catawiki_language':'English','catawiki_artist':'Sally Price','catawiki_brand':'Boldstone',
 'catawiki_material':'Gypsum-based material (Plaster category)','catawiki_finish':v('Internal material / finish'),
 'catawiki_height_cm':v('ebay_height_cm'),'catawiki_width_cm':v('ebay_width_cm'),'catawiki_depth_cm':v('ebay_depth_cm'),
 'catawiki_weight_text':v('Weight'),'catawiki_quantity_per_lot':1,
 'catawiki_photo_candidate_urls':';'.join(p['url'] for p in r['photo_candidates']) if r else '',
 'catawiki_photo_candidate_count':photo_count,
 'catawiki_photo_review':'Selected non-In situ candidates only. Review actual sale-item photographs, neutral background, back/fixings and details; at least five suitable photos. No AI room mock-ups.',
 'catawiki_signature':'','catawiki_condition':'','catawiki_creation_year':'','catawiki_era':'','catawiki_edition':'',
 'catawiki_object_details_review':'Verify signature, physical condition and actual cast date/era before submission. Saatchi-only edition limits and years do not apply.',
 'catawiki_shipping_profile_id':'','catawiki_shipping_uk_eur':'','catawiki_shipping_europe_eur':'','catawiki_shipping_rest_of_world_eur':'',
 'catawiki_shipping_review':'No shipping profile configured in bulk uploader at readback. Confirm actual packing, eligible carrier, destination charges and platform dispatch deadline.',
 'catawiki_exclusivity_status':'Owner decision pending; reserve the submitted physical cast exclusively for Catawiki.',
 'catawiki_terms_status':'Not accepted by this workflow; final upload requires action-time confirmation.',
 'catawiki_native_lot_id':r['existing_lot_id'] or '' if r else '',
 'catawiki_native_edit_url':f'https://www.catawiki.com/en/v/lot/{r["existing_lot_id"]}/edit' if r and r['existing_lot_id'] else '',
 'catawiki_native_status':'Draft observed; update in place' if r and r['existing_lot_id'] else 'No submission observed in dated readback' if included else 'Outside publication scope',
 'catawiki_native_observed_utc':excel_date(datetime.fromtimestamp((OUT.parent/'submissions.txt').stat().st_mtime,timezone.utc)) if included else '',
 'catawiki_prepared_utc':excel_date(datetime.fromisoformat(now))}
 for h,value in data.items():
  formula=None
  if h in ['catawiki_reference_number','catawiki_seller_sku','catawiki_title','catawiki_finish','catawiki_weight_text']:
   ref={'catawiki_reference_number':'Product ID','catawiki_seller_sku':'SKU','catawiki_title':'Retail / website name','catawiki_finish':'Internal material / finish','catawiki_weight_text':'Weight'}[h]
   formula='='+old(ref,row)
  style='utc' if h in ['catawiki_native_observed_utc','catawiki_prepared_utc'] and isinstance(value,(float,int)) else 'integer' if h in ['catawiki_photo_candidate_count','catawiki_quantity_per_lot'] else 'decimal' if h in ['catawiki_height_cm','catawiki_width_cm','catawiki_depth_cm'] else 'text'
  put(h,row,value,style,formula)
 records.append({'row':row,'id':pid,'title':v('Retail / website name'),'base_price_gbp':float(base),'catawiki_target_gbp':money(target),'catawiki_target_eur':eur,'estimated_net_gbp':float(net),'net_vs_catalogue_gbp':gap,'included':included})
assert len(records)==181 and sum(r['included'] for r in records)==176
assert len({p['cell'] for p in patches})==len(patches)
assert all(r['catawiki_target_gbp']==money(Decimal(str(r['base_price_gbp']))+100) for r in records)
plan={'created_utc':now,'scope':'Add prefixed Catawiki fields to all 181 component records. Catawiki GBP target equals catalogue GBP selling price plus GBP100, with linked EUR targets and planning fee/net calculations. Preserve core prices, costs, labour, all other platforms and 12 sheets. No Catawiki submission or terms acceptance.',
 'source_sha256':hashlib.sha256((OUT/'previous-catalogue.xlsx').read_bytes()).hexdigest(),
 'new_headers':fields,'first_added_column':906,'last_added_column':905+len(fields),'patches':patches,
 'assumptions':assumptions,'records':records,'counts':{'component_records':181,'publication_products':176,'added_columns':len(fields),'new_formula_cells':sum(bool(p.get('formula')) for p in patches),'below_catalogue_proceeds_at_target':sum(r['net_vs_catalogue_gbp']<0 for r in records)},
 'pricing_interpretation':'GBP100 addition, not 100 percent. Optional clarification asked; no alternate response received during preparation.',
 'previews':[{'name':'prices','range':column(col['catawiki_price_uplift_gbp'])+'7:'+column(col['catawiki_target_price_eur'])+'13'},
             {'name':'net-proceeds','range':column(col['catawiki_fixed_seller_fee_eur'])+'7:'+column(col['catawiki_profit_protection_review'])+'12'},
             {'name':'identity-status','range':column(col['catawiki_native_lot_id'])+'7:'+column(col['catawiki_prepared_utc'])+'12'}]}
(OUT/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'counts':plan['counts'],'first_column':column(906),'last_column':column(plan['last_added_column']),'sample':records[:4]},ensure_ascii=False,indent=2))
