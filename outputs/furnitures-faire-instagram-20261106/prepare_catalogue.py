"""Record observed channel prices and verified native publication receipts."""
import json,re,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx,column,column_index
read=lambda p:json.loads(p.read_text())
save=lambda n,v:(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
now=datetime.now(timezone.utc).isoformat();sheet='Wall Sculptures'
x=Xlsx(OUT/'previous-catalogue.xlsx')
headers={x.value(sheet,a):re.sub(r'\d','',a) for a in x.cells[sheet] if re.fullmatch('[A-Z]+7',a)}
rows={x.value(sheet,'AA'+str(n)):n for n in range(8,189)}
faire=read(OUT/'faire-observed-prices.json');native={r['catalogue_id']:r for r in faire['records']}
furniture=read(OUT/'furnitures-upload-plan.json');fby={r['catalogue_id']:r for r in furniture['records']}
bindings={r['catalogue_id']:r for r in read(OUT/'furnitures-native-bindings.json')}
receipts={r['catalogue_id']:r for r in read(OUT/'furnitures-field-receipts.json') if r['status']=='VERIFIED_SAVED'}
assert set(receipts)<=set(fby)==set(bindings)==set(native)
core=read(OUT/'furnitures-native-reconciliation.json')
assert core['status']=='PASS_176_NATIVE_ACTIVE_IDENTITIES_PRICES_STOCK_PRIMARY' and core['count']==176
core_by={r['catalogue_id']:r for r in core['records']}
posts=read(OUT/'instagram-five-posts.json');assert len(posts)==5 and all(p['status']=='PUBLISHED_VERIFIED' and p['product_tag_saved'] and p['permalink'] for p in posts)
added=[
 'faire_native_product_name','faire_native_wholesale_gbp','faire_native_retail_gbp',
 'faire_native_retail_to_wholesale_ratio','faire_native_margin_valid','faire_native_shop_status',
 'faire_native_editor_status','faire_native_checked_utc','faire_onboarding_min_retail_multiple',
 'faire_onboarding_max_retail_multiple','faire_onboarding_wholesale_parity_requirement',
 'faire_native_versus_app_retail_gbp','faire_native_versus_protected_wholesale_gbp',
 'faire_native_versus_recorded_brandboom_wholesale_gbp','faire_native_price_source',
 'furnitures_sku','furnitures_native_product_id','furnitures_product_url','furnitures_edit_url',
 'furnitures_native_price_gbp','furnitures_commission_rate','furnitures_price_basis',
 'furnitures_category','furnitures_material','furnitures_dimensions','furnitures_colour',
 'furnitures_material_target','furnitures_dimensions_target','furnitures_colour_target','furnitures_specification_fields_status',
 'furnitures_stock','furnitures_image_count','furnitures_image_urls','furnitures_image_ids',
 'furnitures_native_status','furnitures_delivery_policy_observed','furnitures_payout_status_observed',
 'furnitures_checked_utc']
assert not set(added)&set(headers)
first=max(map(column_index,headers.values()))+1
headers|={h:column(first+i) for i,h in enumerate(added)}
values={}
for pid,n in rows.items():
 if pid not in native:
  values[pid]={'faire_native_shop_status':'Not imported: outside the approved 176-product publication scope.',
  'furnitures_native_status':'Not listed: excluded or held outside the approved 176-product publication scope.',
   'furnitures_checked_utc':'Checked UTC: '+now}
  continue
 r=native[pid];f=fby[pid];b=bindings[pid];receipt=receipts.get(pid);c=core_by[pid]
 assert c['price_gbp']==f['price_gbp'] and c['native_id']==b['native_id']
 if receipt:assert receipt['price_gbp']==f['price_gbp'] and receipt['image_count']==len(f['image_urls'])
 app_retail=float(x.value(sheet,'H'+str(n)))
 target=float(x.value(sheet,'QV'+str(n)))
 brandboom=float(x.value(sheet,headers['brandboom_wholesale_gbp']+str(n)))
 values[pid]={
  'faire_native_product_name':r['name'],
  'faire_native_wholesale_gbp':r['wholesale_gbp'],'faire_native_retail_gbp':r['retail_gbp'],
  'faire_native_retail_to_wholesale_ratio':r['retail_to_wholesale'],'faire_native_margin_valid':'Yes: retail is between 1.25 and 10 times wholesale',
  'faire_native_shop_status':'Inactive; catalogue under Faire review. Product preview is not publication approval.',
  'faire_native_editor_status':'Locked during catalogue review; supplied bulk editor URL redirects to review homepage.',
  'faire_native_checked_utc':'Checked UTC: '+r['checked_utc'],
  'faire_onboarding_min_retail_multiple':1.25,'faire_onboarding_max_retail_multiple':10,
  'faire_onboarding_wholesale_parity_requirement':'Faire onboarding email, 6 November 2026: wholesale prices must match other wholesale channels.',
  'faire_native_versus_app_retail_gbp':round(r['retail_gbp']-app_retail,2),
  'faire_native_versus_protected_wholesale_gbp':round(r['wholesale_gbp']-target,2),
  'faire_native_versus_recorded_brandboom_wholesale_gbp':round(r['wholesale_gbp']-brandboom,2),
  'faire_native_price_source':'https://www.faire.com/brand/b_dddpsekzv4 ; native preview showing 176 of 176 products. Requirements: Brand Onboarding email received 6 November 2026.',
  'faire_pricing_action':'6 November: observed native prices recorded separately. Margin valid, shop inactive/review locked. Retail exceeds app retail; wholesale is below protected model and recorded Brandboom wholesale. Reconcile channel parity and genuine retail before approval; protected model preserved.',
  'furnitures_sku':f['sku'],'furnitures_native_product_id':b['native_id'],
  'furnitures_product_url':b['public_url'],'furnitures_edit_url':b['edit_url'],
  'furnitures_native_price_gbp':f['price_gbp'],'furnitures_commission_rate':f['commission_rate'],
  'furnitures_price_basis':f['price_basis'],'furnitures_category':f['category'],
  'furnitures_material_target':f['material'],'furnitures_dimensions_target':f['dimensions'],'furnitures_colour_target':f['colour'],
  'furnitures_specification_fields_status':'Saved and read back in native editor' if receipt else 'Pending separate native fields. Details are present in the imported product description. Browser focus changed during the completion pass.',
  'furnitures_stock':1,'furnitures_image_count':len(f['image_urls']),
  'furnitures_image_urls':'\n'.join(f['image_urls']),'furnitures_image_ids':'\n'.join(f['image_ids']),
  'furnitures_native_status':'Active. Native identity, price, stock indicator and primary image independently reconciled. '+('Separate specifications, description and all gallery URLs saved and read back.' if receipt else 'Bulk import confirms image links. Separate specification-field completion and individual full-gallery readback pending.'),
  'furnitures_delivery_policy_observed':'Checkout test for GBP38 Acanthus Bloom showed GBP49 UK delivery. Site advertises free UK delivery over GBP500. No seller delivery controls exposed. No payment or test order placed.',
  'furnitures_payout_status_observed':'Seller dashboard says Stripe payouts arrive in the next release and orders are recorded meanwhile. Payout readiness is not verified.',
  'furnitures_checked_utc':'Checked UTC: '+(receipt['utc'] if receipt else core['checked_utc'])}
 if receipt:values[pid].update(furnitures_material=f['material'],furnitures_dimensions=f['dimensions'],furnitures_colour=f['colour'])
for p in posts:
 values[p['catalogue_id']].update(instagram_post_url=p['permalink'],instagram_native_post_id=p['native_id'],
  instagram_product_tag_sku=p['sku'],instagram_published_status='Published and independently observed in native Published content; exact design/finish tag saved; full caption tail observed.',
  instagram_checked_utc='Checked UTC: '+p['verified_utc'])
patches=[]
for h in added:patches.append(dict(sheet=sheet,cell=headers[h]+'7',before=None,value=h))
for pid,d in values.items():
 n=rows[pid]
 for h,v in d.items():
  cell=headers[h]+str(n);before=x.value(sheet,cell)
  if before!=v:patches.append(dict(sheet=sheet,cell=cell,before=before,value=v))
numeric=[h for h in added if h.endswith('_gbp') or h in ['faire_native_retail_to_wholesale_ratio','faire_onboarding_min_retail_multiple','faire_onboarding_max_retail_multiple','furnitures_commission_rate','furnitures_stock','furnitures_image_count']]
plan=dict(scope='Record 176 observed Faire prices, current review lock and pricing differences; add 176 verified active Furnitures records with prices, selected image links and platform limitations; record five published Instagram posts. Existing app retail prices, profit-protection models, costs, labour, specifications and all other channel observations are preserved except the current Faire action note and five Instagram receipt fields.',
 first_added_column=first,last_column=first+len(added)-1,added_headers=added,headers=headers,numeric_headers=numeric,
 patches=patches,preview_range=headers['faire_native_product_name']+'7:'+headers['faire_native_retail_gbp']+'10')
plan['furnitures_separate_specification_fields_verified']=len(receipts)
plan['furnitures_separate_specification_fields_pending']=176-len(receipts)
save('catalogue-plan.json',plan);save('plan.json',plan)
save('channel-records.json',values)
print(json.dumps(dict(products=len(values),fields=len(added),patches=len(patches),instagram_posts=len(posts))))
save('furnitures-pending-fields.json',[dict(**bindings[pid],material=fby[pid]['material'],dimensions=fby[pid]['dimensions'],colour=fby[pid]['colour']) for pid in fby if pid not in receipts])
