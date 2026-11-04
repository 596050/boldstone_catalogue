"""Complete supported catalogue targets without inventing platform observations.

Read-only preparation and independent native-XLSX verification. The companion
artifact-tool script authors the changes; publishing is a separate guarded step.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'catalogue-review'), str(ROOT/'catalogue-review/scripts')]
from import_saatchi_snapshot import Xlsx, column, column_index, NS
from channel_content import values, complete_description, chairish_description, saatchi_description, marketplace_title, appearance, has_surface_effect, product_type
from prepare_chairish_catalogue import chairish_dimensions
from delivery import quote, SEED

D = lambda n: Decimal(str(n))
ceil = lambda n: int(D(n).to_integral_value(rounding=ROUND_CEILING))
floor = lambda n: int(D(n).to_integral_value(rounding=ROUND_FLOOR))
round0 = lambda n: int(D(n).quantize(D(1), rounding=ROUND_HALF_UP))
money = lambda n: float(D(n).quantize(D('.01'), rounding=ROUND_HALF_UP))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def prepare(out):
    read = lambda n: json.loads((out/n).read_text())
    write = lambda n, v: (out/n).write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n')
    x = Xlsx(out/'previous-catalogue.xlsx'); app = read('app-after.json'); snap = read('catalogue-snapshot.json')
    products = {p['id']:p for p in app['products']}; projected = {p['id']:p for p in snap['products']}
    rows = {x.value('Wall Sculptures',f'AA{r}'):r for r in range(8,189)}
    assert set(rows) == set(products) == set(projected) and len(rows)==181
    for pid,p in products.items():
        assert values(p)==values(projected[pid]) and p['costing']==projected[pid]['costing']
        assert p['listing_decision']==projected[pid]['listing_decision']
    headers={x.value('Wall Sculptures',a):re.sub(r'\d','',a) for a in x.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7',a)}
    assert len(headers)==378
    original_headers=dict(headers); changes={}; added=[]; issues=[]; filled=Counter(); changed=Counter()
    def put(sheet,cell,value,formula=None,fmt=None):
        before=x.value(sheet,cell); bf=x.formula(sheet,cell)
        if before==value and bf==(formula[1:] if formula else None) and not fmt:return
        changes[sheet,cell]={'sheet':sheet,'cell':cell,'before':before,'value':value,'formula':formula,'format':fmt}
        if before in (None,'') and value not in (None,''):filled[sheet]+=1
        else:changed[sheet]+=1
    def target(pid,h,v,formula=None,fmt=None):
        if h not in headers:
            headers[h]=column(len(headers)+1);added.append(h)
            put('Wall Sculptures',headers[h]+'7',h,fmt='header')
        if fmt is None and isinstance(v,(float,int)) and not isinstance(v,bool):
            fmt='0.00' if any(z in h for z in ('_gbp','_usd','_cm','_in','_kg','_lb')) else '0'
        put('Wall Sculptures',headers[h]+str(rows[pid]),v,formula,fmt)
    def ref(pid,h):
        if h not in headers:
            headers[h]=column(len(headers)+1);added.append(h)
            put('Wall Sculptures',headers[h]+'7',h,fmt='header')
        return headers[h]+str(rows[pid])
    def old(pid,h):return x.value('Wall Sculptures',original_headers[h]+str(rows[pid])) if h in original_headers else None
    def issue(pid,field,observed,target,action,severity='Apply on platform',platform='catalogue'):
        issues.append([platform,pid,products[pid]['name'],field,observed,target,action,severity])
    fx=D(x.value('Wall Sculptures','BB4'))
    reviews={r['catalogue_id']:r for r in json.loads((ROOT/'channel-update-playbook/chairish-orientation-review.json').read_text())['records']}
    images={r['image']['id']:r['image'] for r in snap['images']}
    bykey={(r['product_id'],r['image']['id']):r for r in snap['images']}
    # Verify the existing complete image register against current identities,
    # classifications and metadata. No image is downloaded or duplicated.
    image_differences=[]
    for n,record in enumerate(snap['images'],8):
        a,c,m=record['image'],record['choice'],record['metadata'];pid=record['product_id']
        assert (x.value('Images','C'+str(n)) or '',x.value('Images','AD'+str(n)))==(pid,a['id'])
        active=record['scope']=='Associated' and not a.get('excluded')
        types=a.get('effective_types',m.get('types',a.get('types',[])));uses=a.get('selected_uses',[])
        checks={'E':a['name'],'H':'Yes' if active and a.get('primary_eligible') else 'No',
                'I':'Yes' if active and 'listing' in uses else 'No','J':'Yes' if 'advertising' in uses else 'No',
                'L':'Yes' if 'in_situ' in types else 'No','N':'; '.join(uses),'O':c.get('decision','pending'),
                'Y':c.get('alt',''),'Z':c.get('caption',''),'AE':a.get('provenance',{}).get('path',''),
                'AF':a.get('provenance',{}).get('revision','')}
        for co,v in checks.items():
            if (x.value('Images',co+str(n)) or '')!=v:image_differences.append([n,co])
    assert not image_differences,'Image register changed; refresh its rows and hyperlinks explicitly'
    assert len(snap['images'])==8698
    sku_corrections=[]; prepared=[]; deferred=[]
    controls=[('BM','Saatchi commission',.4,'0%'),('BN','Saatchi promotion / trade discount allowance',.2,'0%'),
              ('BO','Saatchi fee and discount source','https://support.saatchiart.com/hc/en-us/articles/14567306007323-Promotional-Discounts-and-Commission-Split',None)]
    for co,label,v,fmt in controls:
        assert x.value('Wall Sculptures',co+'3') in (None,'')
        put('Wall Sculptures',co+'3',label,fmt='header');put('Wall Sculptures',co+'4',v,fmt=fmt)
    for pid,p in products.items():
        f=values(p);r=rows[pid];cost=p['costing'];price=money(cost['pricing']['marked_up_price']);photos=projected[pid]['photos'];ship=p['us_shipping']
        assert money(x.value('Wall Sculptures','H'+str(r)))==price
        assert money(x.value('Wall Sculptures','AM'+str(r)))==cost['manufacturing_cost']
        assert x.value('Wall Sculptures','AL'+str(r))==cost['labour_cost']==0
        assert x.value('Wall Sculptures','Y'+str(r))==p['listing_decision']
        assert x.value('Upload Plan','C'+str(r))==pid
        if x.value('Wall Sculptures','AQ'+str(r))!=f['Seller SKU']:
            sku_corrections.append({'id':pid,'before':x.value('Wall Sculptures','AQ'+str(r)),'after':f['Seller SKU']})
            issue(pid,'Seller SKU',old(pid,'SKU'),f['Seller SKU'],'Export corrected to app Seller SKU. Preserve native platform SKU as an alias and reconcile the existing item before updating; never create a duplicate.','Fixed locally')
            put('Wall Sculptures','AQ'+str(r),f['Seller SKU'],fmt='@');put('Upload Plan','D'+str(r),f['Seller SKU'],fmt='@')
        # Dimensions keep exact catalogue centimetres. Reviewed photographs only
        # assign existing face dimensions; they are not fresh measurements.
        dim=chairish_dimensions(f['Dimensions / depth']);cm=dict(dim['values_cm']);basis=dim['basis']
        if dim['missing_axes'] and pid in reviews:
            rev=reviews[pid];assert rev['dimensions']==f['Dimensions / depth']
            pair=re.search(r'(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)',dim['source'])
            assert pair and sorted(map(float,pair.groups()))==sorted(rev['face_cm'].values())
            cm.update(rev['face_cm']);basis+=' Existing photo-reviewed face orientation retained.'
        missing_axes=[axis for axis in ('width','height','depth') if axis not in cm]
        if missing_axes:
            issue(pid,'Dimension orientation',f['Dimensions / depth'],', '.join(missing_axes),
                  'Axis remains unassigned. Do not guess which rectangular side is width or height.','Needs information')
        base=complete_description(p,f['Seller SKU'],dispatch_days=10)
        record={'description_text':base,'sku':f['Seller SKU'],'surface_effect':has_surface_effect(p),'product_type':product_type(p),'colour':appearance(p)}
        sd=saatchi_description(record)
        assert len(sd)<=1000
        # Current photo lists are purpose-derived; related candidates are never
        # turned into listing images merely to fill a blank.
        photo_ids=list(dict.fromkeys(([photos['primary_id']] if photos.get('primary_id') else [])+photos['listing_ids']+photos['in_situ_ids']))
        primary_url=images.get(photos.get('primary_id'),{}).get('url')
        gallery_urls=[images[aid]['url'] for aid in photo_ids]
        snapshots={platform:bool(old(pid,platform+'_observed_'+key)) for platform,key in [('chairish','chairish_id'),('ebay','item_id'),('saatchi','artwork_id')]}
        common={'brand':'Boldstone','catalogue_title':marketplace_title(p),'catalogue_price_gbp':price,'catalogue_price_usd':ceil(D(price)*fx),
            'manufacturing_cost_gbp':cost['manufacturing_cost'],'material_description':'Made from a gypsum-based material.',
            'finish_description':f['Material / finish'],'quantity_of_components':1,'dimensions_text':f['Dimensions / depth'],
            'dimension_basis':basis,'weight_text':f['Weight'],'fx_date':x.value('Wall Sculptures','BC4'),'usd_per_gbp_reference':float(fx),
            'packed_cm_estimate':' × '.join(map(str,ship['packed_cm']))+' cm','packed_kg_estimate':ship['packed_kg'],
            'packing_basis':ship['packing_basis'],'us_quote_basis':'App UPS list-rate planning budgets, as of '+ship['quotes'][0]['as_of']+'. Measured packing, destination quote, cover and import charges still required.'}
        for ax in ('width','height','depth'):
            common[ax+'_cm']=cm.get(ax)
            common[ax+'_in']=money(D(cm[ax])/D('2.54')) if ax in cm else None
        for q in ship['quotes']:common['us_'+q['destination']['id']+'_estimate_gbp']=q.get('estimate_gbp')
        for platform in ('chairish','ebay'):
            for k,v in common.items():
                # Keep the established platform field schema; common keys exist.
                assert platform+'_'+k in headers,(platform,k)
                formula='=H'+str(r) if k=='catalogue_price_gbp' else '=AM'+str(r) if k=='manufacturing_cost_gbp' else '=$BB$4' if k=='usd_per_gbp_reference' else '=ROUNDUP(H'+str(r)+'*$BB$4,0)' if k=='catalogue_price_usd' else None
                target(pid,platform+'_'+k,v,formula)
            target(pid,platform+'_update_state','Catalogue-derived targets refreshed. '+('Update matched native item only.' if snapshots[platform] else 'No matched item in supplied snapshot; reconcile native account before creation.')+' No live update is claimed.')
            target(pid,platform+'_sale_unit_scope','One individually described component; other photographed pieces excluded')
        target(pid,'chairish_description',chairish_description(record,10))
        target(pid,'chairish_shipping_review','No verified destination-specific inclusive shipping quote. Do not use the planning estimate as a checkout rate.')
        target(pid,'ebay_description',complete_description(p,f['Seller SKU'],3 if snapshots['ebay'] else 10,'ebay'))
        target(pid,'ebay_catalogue_title',marketplace_title(p,80))
        target(pid,'ebay_sale_unit',f['Sale unit'])
        target(pid,'ebay_price_gbp',price,'=H'+str(r),'0.00')
        target(pid,'ebay_international_shipping_enabled',False)
        for h in ('ebay_international_service','ebay_international_charge_gbp'):target(pid,h,None)
        target(pid,'ebay_international_shipping_action','Keep international shipping disabled until a supported service and actual destination-specific charge are configured. No live setting change is claimed.')
        target(pid,'ebay_international_shipping_review','UK-only prepared target; international service/rate unverified.')
        for ax,v in zip(('length','width','height'),ship['packed_cm']):target(pid,'ebay_packed_'+ax+'_cm_estimate',v)
        rm=quote(dict(zip(('length_cm','width_cm','depth_cm'),ship['packed_cm']))|{'weight_kg':ship['packed_kg'],'packaging_gbp':0,'collection':False,'destination':'uk'},SEED)
        target(pid,'ebay_royal_mail_tier',rm['tier']['label'] if rm['status']=='calculated' else 'Separate courier quote required')
        target(pid,'ebay_royal_mail_tracked48_online_gbp',rm['postage_pence']/100 if rm['status']=='calculated' else None)
        if not snapshots['ebay']:
            target(pid,'ebay_package_size','Estimated '+common['packed_cm_estimate']+' / '+str(ship['packed_kg'])+' kg; measure before selecting service')
            target(pid,'ebay_domestic_service','Carrier/service not selected; obtain eligible measured-package quote')
        target(pid,'ebay_domestic_shipping_review',('Estimate fits '+rm['tier']['label']+'. ' if rm['status']=='calculated' else 'Estimate exceeds Royal Mail parcel limits. ')+ 'Confirm measured packing, eligible carrier and full buyer charge; platform label prices may differ from retail tariffs.')
        target(pid,'ebay_shipping_update_state','Planning data only. No native service or checkout rate verified.')
        # All components receive the same editable, seller-net-preserving Chairish
        # price mechanism. Empty observed discounts remain empty observations.
        reserve=D(old(pid,'chairish_observed_reserve_discount') or 0) if snapshots['chairish'] else D('.2')
        auction_disc=D(old(pid,'chairish_observed_auction_reserve_discount') or 0) if snapshots['chairish'] else D('.4')
        trade=D(old(pid,'chairish_observed_trade_discount') or 0) if snapshots['chairish'] else D('.12')
        for key,v in [('reserve_discount_target',reserve),('auction_discount_target',auction_disc),('trade_discount_target',trade)]:
            target(pid,'chairish_'+key,float(v),fmt='0%')
        net=ceil(D(price)*fx);allow=max(D('.4'),reserve,auction_disc,trade);minimum=ceil(D(net)/D('.6'));asking=ceil(D(minimum)/(1-allow))
        cv={'net_target_usd':(net,f'=ROUNDUP(H{r}*$BB$4,0)'), 'other_fees_usd':(0,'=$BJ$4'),
            'commission_rate':(.4,'=$BH$4'),'auction_commission_rate':(.2,'=$BI$4'),
            'discount_allowance':(float(allow),'=MAX($BG$4,'+','.join(ref(pid,'chairish_'+k) for k in ['reserve_discount_target','auction_discount_target','trade_discount_target'])+')'),
            'minimum_sale_price_usd':(minimum,'=ROUNDUP(('+ref(pid,'chairish_net_target_usd')+'+'+ref(pid,'chairish_other_fees_usd')+')/(1-'+ref(pid,'chairish_commission_rate')+'),0)'),
            'asking_price_usd':(asking,'=ROUNDUP('+ref(pid,'chairish_minimum_sale_price_usd')+'/(1-'+ref(pid,'chairish_discount_allowance')+'),0)')}
        for k,(v,formula) in cv.items():target(pid,'chairish_'+k,v,formula,'0%' if 'rate' in k or k=='discount_allowance' else '0')
        prices={'reserve':round0(D(asking)*(1-reserve)),'auction_reserve':round0(D(asking)*(1-auction_disc)),
                'trade':round0(D(asking)*(1-trade)),'discounted_sale':round0(D(asking)*(1-allow))}
        for key,dk in [('reserve','reserve_discount_target'),('auction_reserve','auction_discount_target'),('trade','trade_discount_target'),('discounted_sale','discount_allowance')]:
            pk={'reserve':'reserve_price_usd','auction_reserve':'auction_reserve_usd','trade':'trade_price_usd','discounted_sale':'discounted_sale_usd'}[key]
            target(pid,'chairish_'+pk,prices[key],'=ROUND('+ref(pid,'chairish_asking_price_usd')+'*(1-'+ref(pid,'chairish_'+dk)+'),0)','0')
        for key,v,rate,pk in [('price',asking,D('.4'),'asking_price_usd'),('reserve',prices['reserve'],D('.4'),'reserve_price_usd'),('auction_reserve',prices['auction_reserve'],D('.2'),'auction_reserve_usd'),('trade_price',prices['trade'],D('.4'),'trade_price_usd'),('discount_allowance',prices['discounted_sale'],D('.4'),'discounted_sale_usd')]:
            rk='auction_commission_rate' if key=='auction_reserve' else 'commission_rate'
            target(pid,'chairish_proceeds_at_'+key+'_usd',floor(D(v)*(1-rate)),'=ROUNDDOWN('+ref(pid,'chairish_'+pk)+'*(1-'+ref(pid,'chairish_'+rk)+')-'+ref(pid,'chairish_other_fees_usd')+',0)','0')
        chnet=money(D(floor(D(prices['discounted_sale'])*D('.6')))/fx)
        target(pid,'chairish_net_after_discount_gbp',chnet,'=ROUND('+ref(pid,'chairish_proceeds_at_discount_allowance_usd')+'/$BB$4,2)')
        target(pid,'chairish_profit_after_discount_gbp',money(D(chnet)-D(cost['manufacturing_cost'])),'=ROUND('+ref(pid,'chairish_net_after_discount_gbp')+'-AM'+str(r)+',2)')
        target(pid,'chairish_pricing_basis','Preserves catalogue selling-price net proceeds after 40% standard commission and up to 40% discount. Auction commission 20%. Unobserved reserve/trade/auction targets use editable 20%/12%/40% defaults. Shipping, taxes and packing separate; verify seller plan before application.')
        # Saatchi target schema is deliberately separate from saatchi_observed_*.
        sdct={'catalogue_sku':f['Seller SKU'],'catalogue_title':marketplace_title(p),'catalogue_price_gbp':price,
            'description':sd,'description_characters':len(sd),'category':'Sculpture','medium':'Relief',
            'material_description':'Gypsum-based material','colour':appearance(p),'product_type':product_type(p),
            'quantity_of_components':1,'sale_unit':f['Sale unit'],'dimensions_text':f['Dimensions / depth'],'dimension_basis':basis,
            'weight_text':f['Weight'],'fixings':f['Fixing'],'suitable_for_outdoor_use':True,'dispatch_working_days':3,
            'surface_effect_applied':has_surface_effect(p),'surface_effect_variation':'Each piece is handmade. The surface-effect pattern will vary and will differ from the photographs.' if has_surface_effect(p) else 'Not applicable: no added colour/effect selected',
            'primary_image_url':primary_url,'listing_image_urls':'\n'.join(images[aid]['url'] for aid in photos['listing_ids']),
            'in_situ_image_urls':'\n'.join(images[aid]['url'] for aid in photos['in_situ_ids']),
            'selected_gallery_count':len(photo_ids),'packed_cm_estimate':common['packed_cm_estimate'],'packed_kg_estimate':ship['packed_kg'],
            'packing_basis':ship['packing_basis'],'shipping_basis':'Platform-arranged destination shipping, separate from artwork price. App parcel estimates do not certify Saatchi packaging/crate eligibility or checkout charges.',
            'unverified_information':'Actual creation year, original/edition status, produced/available/sold quantities, signature, measured final packing and platform eligibility are not established by the app. Keep observed snapshot claims separate.',
            'update_state':'Prepared catalogue targets; '+('update existing matched artwork only.' if snapshots['saatchi'] else 'no artwork ID in supplied snapshot; reconcile before creation.')+' No live update is claimed.',
            'inclusion_decision':p['listing_decision'],'price_basis':'Seller-net target after 40% commission and 20% promotion/trade allowance. Editable controls BM4/BN4. Artwork-only USD, shipping/tax separate. Verify native price limits before application.'}
        for ax in ('width','height','depth'):
            sdct[ax+'_cm']=cm.get(ax);sdct[ax+'_in']=money(D(cm[ax])/D('2.54')) if ax in cm else None
        for k,v in sdct.items():target(pid,'saatchi_'+k,v)
        snet=ceil(D(price)*fx);smin=ceil(D(snet)/D('.6'));sask=ceil(D(smin)/D('.8'));disc=round0(D(sask)*D('.8'));proceeds=floor(D(disc)*D('.6'));sgbp=money(D(proceeds)/fx)
        sv={'net_target_usd':(snet,f'=ROUNDUP(H{r}*$BB$4,0)'), 'commission_rate':(.4,'=$BM$4'), 'discount_allowance':(.2,'=$BN$4'),
            'minimum_sale_price_usd':(smin,'=ROUNDUP('+ref(pid,'saatchi_net_target_usd')+'/(1-'+ref(pid,'saatchi_commission_rate')+'),0)'),
            'asking_price_usd':(sask,'=ROUNDUP('+ref(pid,'saatchi_minimum_sale_price_usd')+'/(1-'+ref(pid,'saatchi_discount_allowance')+'),0)'),
            'discounted_sale_usd':(disc,'=ROUND('+ref(pid,'saatchi_asking_price_usd')+'*(1-'+ref(pid,'saatchi_discount_allowance')+'),0)'),
            'proceeds_after_discount_usd':(proceeds,'=ROUNDDOWN('+ref(pid,'saatchi_discounted_sale_usd')+'*(1-'+ref(pid,'saatchi_commission_rate')+'),0)'),
            'net_after_discount_gbp':(sgbp,'=ROUND('+ref(pid,'saatchi_proceeds_after_discount_usd')+'/$BB$4,2)'),
            'profit_after_discount_gbp':(money(D(sgbp)-D(cost['manufacturing_cost'])),'=ROUND('+ref(pid,'saatchi_net_after_discount_gbp')+'-AM'+str(r)+',2)')}
        for k,(v,formula) in sv.items():target(pid,'saatchi_'+k,v,formula,'0%' if k in ('commission_rate','discount_allowance') else '0.00' if k.endswith('gbp') else '0')
        if snapshots['saatchi']:
            observed_net=D(old(pid,'saatchi_observed_your_60_share_usd'))/fx
            if observed_net<D(price):issue(pid,'Net proceeds',money(observed_net),price,'Prepared asking price covers commission and promotion allowance. Apply to the existing artwork after native eligibility checks.',platform='saatchi')
            observed_dims={ax:old(pid,'saatchi_observed_'+ax+'_cm') for ax in ('width','height','depth')}
            if any(ax in cm and abs(D(v)-D(cm[ax]))>D('.1') for ax,v in observed_dims.items()):
                issue(pid,'Dimension axes',str(observed_dims),str(cm),'Use exact catalogue cm targets; do not round-trip rounded inches.',platform='saatchi')
            if has_surface_effect(p) and not re.search(r'\bfinish\b',old(pid,'saatchi_observed_title'),re.I):
                issue(pid,'Finish title',old(pid,'saatchi_observed_title'),sdct['catalogue_title'],'Prepared title clarifies the applied finish.',platform='saatchi')
            if len(photos['in_situ_ids'])+len(photos['listing_ids']) > 0 and int(old(pid,'saatchi_observed_additional_images_count'))+1<len(photo_ids):
                issue(pid,'Selected photo coverage',int(old(pid,'saatchi_observed_additional_images_count'))+1,len(photo_ids),'Compare selected current image IDs with native gallery and channel photo rules. No candidate images automatically selected.',platform='saatchi')
        elif p['listing_decision']=='include':
            issue(pid,'Snapshot coverage','No Saatchi artwork row','Prepared current targets','Reconcile the native account before creating anything. Absence from this supplied export is not proof it is unlisted.','Native check','saatchi')
        publication=[]
        if p['listing_decision']=='exclude':publication.append('Excluded by current app decision: do not publish')
        if photos['primary_listing']['status']!='set':publication.append('Primary photograph not set')
        if missing_axes:publication.append('Dimension axes unassigned')
        # Owner deferred the first water-feature photographs; preserve that.
        if pid=='BSI-D886F539DD3E':deferred.append(pid)
        target(pid,'catalogue_preparation_state','; '.join(publication) if publication else 'Catalogue target fields complete; live platform verification separate')
        checked=datetime.fromisoformat(snap['created_utc']).astimezone(timezone.utc).replace(tzinfo=None)
        serial=(checked-datetime(1899,12,30)).total_seconds()/86400
        target(pid,'catalogue_data_checked_utc',serial,fmt='yyyy-mm-dd hh:mm')
        target(pid,'catalogue_platform_coverage','; '.join(pl+(': supplied snapshot matched' if present else ': not in supplied snapshot') for pl,present in snapshots.items()))
        target(pid,'catalogue_noninferable_fields','Platform IDs absent from snapshots; actual production year, edition, stock/sales counts, verified final shipping charge, barcode/exemption and condition/provenance require evidence. Not applicable optional fields may remain blank.')
        prepared.append({'id':pid,'row':r,'sku':f['Seller SKU'],'decision':p['listing_decision'],'missing_axes':missing_axes,
            'cm':cm,'price_gbp':price,'manufacturing_gbp':cost['manufacturing_cost'],'saatchi_asking_usd':sask,
            'saatchi_net_gbp':sgbp,'chairish_asking_usd':asking,'chairish_net_gbp':chnet,'photo_count':len(photo_ids),
            'snapshots':snapshots})
    # Refresh current app UPS budgets, retaining blank charges for freight-only
    # items. A missing quote must never become zero/free shipping.
    for n in range(5,367):
        pid=x.value('US Delivery Estimates','A'+str(n));p=products[pid];ship=p['us_shipping']
        q=next(q for q in ship['quotes'] if q['destination']['name']==x.value('US Delivery Estimates','C'+str(n)))
        vals={'B':p['retail_name'],'E':q['status'],'F':ship['packed_kg'],'G':ship['packed_cm'][0],'H':ship['packed_cm'][1],
            'I':ship['packed_cm'][2],'J':q.get('dimensional_kg'),'K':q.get('billable_kg'),'U':q.get('estimate_gbp'),
            'V':q.get('fuel_percent'),'W':q['as_of'],'X':q.get('valid_until'),'Y':ship['packing_basis'],
            'Z':q['message'],'AA':'; '.join(q['exclusions']),'AB':q['sources']['rates'],'AC':q['sources']['fuel']}
        for co,k in zip(['L','M','N','O','P','Q','R','S','T'],['transport_gbp','residential_gbp','additional_handling_gbp','large_package_gbp','demand_gbp','surge_gbp','fuel_gbp','us_processing_gbp','collection_gbp']):vals[co]=q.get('charges',{}).get(k)
        for co,v in vals.items():put('US Delivery Estimates',co+str(n),v)
    put('US Delivery Estimates','A2','Current app UPS planning estimates. Carrier list tariffs and fuel allowance refreshed from app; final measured package, address and all-in quote still required.')
    # Keep every dated source observation intact. Put this fresh audit beside
    # the previous review, avoiding claims that native updates have occurred.
    counts=Counter((i[0],i[3]) for i in issues)
    for pid in products:
        for pl in ('chairish','ebay'):
            target(pid,pl+'_issue_count',int(old(pid,pl+'_issue_count') or 0)+sum(i[1]==pid and i[0]==pl for i in issues))
    ah=['Platform / scope','Catalogue ID','Sculpture','Issue','Observed / prior','Current target','Required action','Status']
    for i,h in enumerate(ah,14):put('Platform Review',column(i)+'4',h,fmt='header')
    assert len(issues)<=667
    for n,record in enumerate(issues,5):
        for i,v in enumerate(record,14):put('Platform Review',column(i)+str(n),v)
    put('Platform Review','N2','Fresh data audit: '+snap['created_utc']+'. Prepared targets are not proof of live publication. Earlier platform review and source snapshots remain preserved.')
    put('Wall Sculptures','A4','Current app snapshot '+snap['created_utc']+'. Missing supported platform targets completed; supplied native observations remain dated snapshots. No live listing writes.')
    put('Wall Sculptures','A5',f'181 components | 178 included, 3 excluded | 8,698 image association/reference rows verified | labour zero; manufacturing excludes labour | Current targets for Chairish, eBay and Saatchi.')
    filled=Counter(q['sheet'] for q in changes.values() if q['before'] in (None,'') and q['value'] not in (None,''))
    changed=Counter(q['sheet'] for q in changes.values() if not (q['before'] in (None,'') and q['value'] not in (None,'')))
    audit={'checked_utc':snap['created_utc'],'components':181,'included':sum(p['listing_decision']=='include' for p in products.values()),
        'excluded':sum(p['listing_decision']=='exclude' for p in products.values()),'core_fields':sum(len(p['fields'])+len(p['listing_fields']) for p in products.values()),
        'core_missing':sum(not f['value'] for p in products.values() for f in p['fields']+p['listing_fields']),
        'snapshot_coverage':{pl:sum(r['snapshots'][pl] for r in prepared) for pl in ['chairish','ebay','saatchi']},
        'sku_corrections':sku_corrections,'current_image_register_rows_verified':8698,'unique_images':3467,
        'saatchi_net_below_catalogue_before_correction':counts['saatchi','Net proceeds'],
        'saatchi_dimension_mismatches':counts['saatchi','Dimension axes'],'saatchi_titles_missing_finish':counts['saatchi','Finish title'],
        'saatchi_selected_photo_shortfalls':counts['saatchi','Selected photo coverage'],
        'unassigned_orientations':[r['id'] for r in prepared if r['missing_axes']],
        'shipping_estimates_updated':362,'freight_components':sum(any(q['status']=='freight_quote_required' for q in p['us_shipping']['quotes']) for p in products.values()),
        'included_without_primary':sum(p['listing_decision']=='include' and p['photos']['primary_listing']['status']!='set' for p in products.values()),
        'included_with_fewer_than_two_in_situ':sum(p['listing_decision']=='include' and p['photos']['in_situ']['count']<2 for p in products.values()),
        'deferred_photography':deferred,'filled_cells_by_sheet':dict(filled),'updated_cells_by_sheet':dict(changed),'audit_rows':len(issues)}
    plan={'scope':'Complete supported catalogue-derived platform target fields for all 181 components, preserve dated observations, reconcile current app SKU, refresh 362 US planning estimates, and record a current data audit. Labour zero and app selling prices unchanged. No native platform listing changes.',
          'patches':list(changes.values()),'headers':headers,'added_master_columns':added,'first_master_column':379,'last_master_column':len(headers),
          'master_rows':rows,'audit':audit,'audit_rows':len(issues),'audit_first_row':4,'audit_last_row':4+len(issues),
          'column_format_updates':[{'sheet':'Platform Review','first':14,'last':14,'width':18},
            {'sheet':'Platform Review','first':15,'last':15,'width':23},{'sheet':'Platform Review','first':16,'last':16,'width':34},
            {'sheet':'Platform Review','first':17,'last':19,'width':30},{'sheet':'Platform Review','first':20,'last':20,'width':90},
            {'sheet':'Platform Review','first':21,'last':21,'width':24}],
          'row_format_updates':[]}
    write('completeness-plan.json',plan);write('data-audit.json',audit);write('data-issues.json',issues);write('prepared-targets.json',prepared)
    print(json.dumps(audit,ensure_ascii=False));print('patches',len(changes),'new_columns',len(added))

def verify(out):
    read=lambda n:json.loads((out/n).read_text())
    p=read('completeness-plan.json');old=Xlsx(out/'previous-catalogue.xlsx');x=Xlsx(out/'catalogue_wall_sculptures.xlsx'); app=read('app-after.json')
    by={p['id']:p for p in app['products']};changes={(q['sheet'],q['cell']):q for q in p['patches']}
    assert old.paths==x.paths
    unchanged=0;observations=0;formulas=0
    for s,cells in old.cells.items():
        for a,c in cells.items():
            if (s,a) not in changes:
                assert ET.tostring(c)==ET.tostring(x.cells[s][a]),(s,a,'Unexpected original-cell change')
                unchanged+=1
    for q in p['patches']:
        got=x.value(q['sheet'],q['cell']);v=q['value']
        assert got==v or got in (None,'') and v in (None,'') or isinstance(got,(int,float)) and isinstance(v,(int,float)) and abs(got-v)<1e-7,(q['sheet'],q['cell'],got,v)
        assert x.formula(q['sheet'],q['cell'])==(q['formula'][1:] if q['formula'] else None)
    h=p['headers'];assert len(h)==len(set(k.casefold() for k in h))
    v=lambda pid,k:x.value('Wall Sculptures',h[k]+str(p['master_rows'][pid]))
    for header in h:
        if '_observed_' in header:
            for pid in by:
                assert v(pid,header)==old.value('Wall Sculptures',h[header]+str(p['master_rows'][pid]));observations+=1
    fx=D(x.value('Wall Sculptures','BB4'))
    for t in read('prepared-targets.json'):
        pid=t['id'];r=t['row'];q=by[pid]
        assert x.value('Wall Sculptures','AQ'+str(r))==values(q)['Seller SKU']
        assert x.value('Upload Plan','D'+str(r))==values(q)['Seller SKU']
        assert x.value('Wall Sculptures','AL'+str(r))==0
        assert x.value('Wall Sculptures','H'+str(r))==t['price_gbp']
        assert x.value('Wall Sculptures','AM'+str(r))==t['manufacturing_gbp']
        assert x.value('Wall Sculptures','Y'+str(r))==t['decision']
        for pl in ['ebay','chairish','saatchi']:
            for k in ['catalogue_title','catalogue_price_gbp','description','dimensions_text','weight_text','material_description','quantity_of_components','packed_cm_estimate','packed_kg_estimate','update_state']:
                assert v(pid,pl+'_'+k) not in (None,''),(pid,pl,k)
            assert v(pid,pl+'_quantity_of_components')==1
            for ax,cm in t['cm'].items():assert v(pid,pl+'_'+ax+'_cm')==cm
        assert v(pid,'ebay_price_gbp')==t['price_gbp'] and v(pid,'ebay_international_shipping_enabled') is False
        assert v(pid,'ebay_international_charge_gbp') in (None,'')
        assert len(v(pid,'saatchi_description'))==v(pid,'saatchi_description_characters')<=1000
        for pl in ['saatchi','chairish']:
            assert D(v(pid,pl+'_net_after_discount_gbp'))>=D(t['price_gbp'])
            assert v(pid,pl+'_asking_price_usd')==t[pl+'_asking_usd']
        # Independent price arithmetic, not assertions that merely mirror cell
        # formulas. Test the actual stored drivers with conservative rounding.
        ask=D(v(pid,'saatchi_asking_price_usd'));discount=D(v(pid,'saatchi_discount_allowance'));comm=D(v(pid,'saatchi_commission_rate'))
        sale=round0(ask*(1-discount));proceeds=floor(D(sale)*(1-comm))
        assert v(pid,'saatchi_proceeds_after_discount_usd')==proceeds
        assert money(D(proceeds)/fx)==v(pid,'saatchi_net_after_discount_gbp')
        if t['decision']=='exclude':assert 'Excluded' in v(pid,'catalogue_preparation_state')
    for s,cells in x.cells.items():
        for a,c in cells.items():
            x.value(s,a) # Reject every Excel error cell, including untouched ones.
            formulas+=bool(x.formula(s,a))
    result={'status':'PASS','sha256':sha(out/'catalogue_wall_sculptures.xlsx'),'components':181,
        'all_core_values_and_prices_preserved':True,'platform_target_sets':543,'native_observed_cells_preserved':observations,
        'unchanged_native_cells_verified':unchanged,'changed_or_added_cells_verified':len(changes),'formulas':formulas,
        'unknown_native_data_not_invented':True,'labour_zero_and_excluded_decisions_preserved':True}
    (out/'independent-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['prepare','verify']);ap.add_argument('output',type=Path);a=ap.parse_args()
    (prepare if a.action=='prepare' else verify)(a.output.resolve())
