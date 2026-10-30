"""Reconcile current component decisions with immutable local platform exports."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,hashlib,html,json,re
ROOT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def clean(x):return str(x or '').replace('\u2014','-').replace('\u2013','-')
def slug(x):return re.sub('[^a-z0-9]+','-',clean(x).lower()).strip('-')
def group_title(ps):
    if len(ps)==1:return ps[0]['name']
    names=[p['name'] for p in ps]
    if all('Ammonite' in n and 'Left Panel' in n for n in names):return 'Ammonite Left Panel'
    if all('Ammonite' in n and 'Right Panel' in n for n in names):return 'Ammonite Right Panel'
    prefix=names[0]
    for name in names[1:]:
        while prefix and not name.startswith(prefix):prefix=prefix[:-1]
    return prefix.rstrip(' -/,') or ps[0]['family']
def write_csv(name,rows,keys=None):
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=keys or list(dict.fromkeys(k for row in rows for k in row)),extrasaction='raise');writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
snapshot=read(OUT/'catalogue-snapshot.json')
old_path=ROOT/'sculpture-catalogue/components/reconciliation/acanthus-white-black-retirement-2026-10-26/listing-treatment-register.json'
cross_path=ROOT/'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json'
ss_path=ROOT/'products_Oct-15_04-49-54PM.csv'
sh_path=Path('/Users/tprice/Downloads/products_export_1 (1).csv')
old=read(old_path);cross=read(cross_path)
offers={r['offer_ref']:r for r in cross['squarespace_source_records']}
old_by_id={r['product_id']:r for r in old['options']}
source_receipts=[]
for path in [old_path,cross_path,ss_path,sh_path]:
    body=path.read_bytes();source_receipts.append({'path':str(path),'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
assert source_receipts[-1]['sha256']=='bfa0412dbbc6461060023e71d739ce73a4c76918730de165e2472e5436500118'
ss={};parent=None
for number,row in enumerate(csv.DictReader(ss_path.open(encoding='utf-8-sig',newline='')),2):
    if row['Product ID [Non Editable]']:parent=row['Product ID [Non Editable]']
    row={**row,'Product ID [Non Editable]':parent,'source_csv_row':number}
    key=(parent,row['Variant ID [Non Editable]']);assert key not in ss;ss[key]=row
sh=defaultdict(list);title=None;handle=None;options={}
for number,row in enumerate(csv.DictReader(sh_path.open(encoding='utf-8-sig',newline='')),2):
    if row['Handle']!=handle:handle=row['Handle'];options={};title=row['Title']
    for i in range(1,4):
        if row[f'Option{i} Name']:options[i]=row[f'Option{i} Name']
    if not (row['Variant SKU'] or row['Option1 Value']):continue
    row={**row,'Title':row['Title'] or title,'source_csv_row':number}
    for i in range(1,4):row[f'Option{i} Name']=row[f'Option{i} Name'] or options.get(i,'')
    if row['Variant SKU'].strip():sh[row['Variant SKU'].strip()].append(row)

visual_flags={104:'Visible brown finish: check assignment to White.',106:'Visible pink finish: check assignment to White.',
    107:'Visible sand-coloured finish: check assignment to White.',108:'Visible brown finish: check assignment to White.'}
selected=read(OUT/'selected-images.json')
flag_by_id={x['image']['id']:visual_flags[x['number']] for x in selected if x['number'] in visual_flags}
products=[];exact_claims={};sku_claims={}
for p in snapshot['products']:
    pid=p['id'];o=old_by_id.get(pid,{})
    fields={f['key']:clean(f['value']) for f in p['fields']+p['listing_fields']}
    refs=list(o.get('selected_source_offer_refs',[]));square_product=o.get('selected_squarespace_product_id','')
    square_variant=o.get('selected_squarespace_variant_id','');existing_sku=o.get('selected_existing_source_sku','')
    evidence='Retained component treatment checked against exact local export identifiers.'
    # Current selected front/detail images and local O007 gallery show the same
    # circular crater relief and rust/verdigris finish. The source also states
    # 25 x 25 x 6 cm, agreeing with the current accepted component specification.
    if pid=='BSI-EBD43DF0704F':
        refs=['O007'];native=offers['O007']['squarespace_native_tuple']
        square_product=native['native_product_id'];square_variant=native['native_variant_id'];existing_sku=native['sku_raw']
        evidence='Visual design/finish reconciliation on 2026-10-30: source-o007-0.image and source-o007-1.image compared with selected photographs 264-266; 25 x 25 x 6 cm agrees. This identifies the product design, not an identical physical cast.'
    native=None
    if square_variant:
        native=ss[(square_product,square_variant)]
        assert native['SKU']==existing_sku
        assert (square_product,square_variant) not in exact_claims
        exact_claims[(square_product,square_variant)]=pid
    sku=existing_sku or o.get('proposed_listing_sku') or 'BOLD-'+pid.removeprefix('BSI-')
    assert sku and sku not in sku_claims,(pid,sku);sku_claims[sku]=pid
    shopify_matches=sh.get(existing_sku,[]) if existing_sku else []
    assert len(shopify_matches)<=1,(pid,'Ambiguous SKU in local Shopify export')
    matched=shopify_matches[0] if shopify_matches else None
    group=o.get('proposed_product_group_key') or 'NEW:'+pid+':SCULPTURE'
    if pid=='BSI-EBD43DF0704F':group='EXISTING:'+square_product
    parent_square=square_product or o.get('suggested_existing_parent_product_id','')
    if not parent_square and group.startswith('EXISTING:'):parent_square=group.split(':',1)[1]
    sq_action='Update exact existing variant' if native else ('Add variant to existing product' if parent_square else 'Create product or variant')
    p_options=[{'name':native.get(f'Option Name {i}'),'value':native.get(f'Option Value {i}')} for i in range(1,7) if native and native.get(f'Option Value {i}')]
    sh_options=[{'name':matched[f'Option{i} Name'],'value':matched[f'Option{i} Value']} for i in range(1,4) if matched and matched[f'Option{i} Value']]
    row={'product_id':pid,'name':clean(p['name']),'family':clean(p['family']), 'component_id':p['component_id'],
        'listing_decision':p['listing_decision'],'review_status':p['review_status'],
        'sku':sku,'sku_status':'Existing exact source SKU' if existing_sku else 'Proposed new unique SKU',
        'group_key':group,'squarespace_action':sq_action,'squarespace_product_id':parent_square,
        'squarespace_variant_id':square_variant,'squarespace_options':p_options,
        'squarespace_csv_row':native['source_csv_row'] if native else None,
        'source_offer_refs':refs,'related_offer_refs':o.get('related_source_offer_refs',[]),
        'shopify_handle':matched['Handle'] if matched else '',
        'shopify_numeric_product_id':None,'shopify_numeric_variant_id':None,
        'shopify_options':sh_options,'shopify_existing_options':sh_options,'shopify_csv_row':matched['source_csv_row'] if matched else None,
        'binding_evidence':evidence,'local_sources_only':True,'live_platform_presence_verified':False,
        'specifications':fields,'price_gbp':p['costing']['pricing']['marked_up_price'],
        'markup_percent':p['costing']['pricing']['markup_percent'],'manufacturing_cost_gbp':p['costing']['total_cost'],
        'production_material':p['costing']['material_label'],'cost_excludes_delivery':True,
        'requires_shipping':True,'delivery_charge_policy':'Quote separately per order','delivery_charge_gbp':None,
        'delivery_included_in_price':False,'production_lead_time':'1-2 weeks',
        'transit_time':'Agreed with delivery quote','packed_weight_kg':None,'package_dimensions_cm':None,
        'listing_photo_ids':p['photos']['listing_ids'],'primary_photo_id':p['photos']['primary_id'],
        'in_situ_photo_ids':p['photos']['in_situ_ids'],'app_url':p['app_url'],'folder_url':p['folder_url'],
        'publication_review':[]}
    if p['listing_decision']!='include':row['publication_review'].append('Owner listing decision: '+p['listing_decision'])
    if p['review_status']!='reviewed':row['publication_review'].append('Component review is not complete')
    if not p['photos']['primary_id']:row['publication_review'].append('Choose primary listing photograph')
    if not p['photos']['listing_ids']:row['publication_review'].append('Choose listing photographs')
    for aid in p['photos']['listing_ids']:
        if aid in flag_by_id:row['publication_review'].append(flag_by_id[aid]+' '+aid)
    if p['family']=='Frozen Fish':
        draft=next(x for x in cross['local_shopify_records'] if x['handle']=='frozen-fish')
        assert len(draft['variants'])==1 and draft['variants'][0]['sku_raw']==''
        row.update(group_key='SHOPIFY:frozen-fish',shopify_handle='frozen-fish',shopify_parent_only=True,
            shopify_parent_source_row=draft['variants'][0]['source_row']['logical_row_including_header'],
            binding_evidence=evidence+' Owner consolidated Frozen Fish into White, Terracotta and Verdigris. Reuse the existing blank-SKU Frozen Fish family draft as parent; its placeholder is not an exact purchasable variant match.')
    products.append(row)

groups=defaultdict(list)
for p in products:groups[p['group_key']].append(p)
for group,ps in groups.items():
    existing={p['shopify_handle'] for p in ps if p['shopify_handle']}
    assert len(existing)<=1,(group,existing)
    handle=next(iter(existing)) if existing else 'boldstone-'+slug(group.removeprefix('NEW:').removeprefix('EXISTING:').removesuffix(':SCULPTURE'))
    for p in ps:
        p['shopify_parent_title']=group_title(ps)
        if p.get('shopify_parent_only'):
            p['shopify_action']='Configure three finish variants in existing family draft; reconcile blank-SKU placeholder'
            p['shopify_options']=[{'name':'Finish','value':p['name'].split(' - ',1)[1]}]
        elif p['shopify_handle']:
            p['shopify_action']='Update exact existing variant'
        elif existing:
            p['shopify_action']='Append variant through platform API; preserve existing option identity'
            p['shopify_options']=[{'name':'Component / finish','value':p['name']}]
        else:
            p['shopify_action']='Create draft product' if len(ps)==1 else 'Create variant in new draft product'
            p['shopify_options']=[{'name':'Title','value':'Default Title'}] if len(ps)==1 else [{'name':'Component / finish','value':p['name']}]
        if existing and len(ps)>1 and not p.get('shopify_parent_only'):
            p['shopify_options']=[{'name':'Component / finish','value':p['name']}]
            p['shopify_option_migration']='Configure one shared Component / finish option through the API. Resolve existing variants by their saved old option tuple and preserve native variant IDs during renaming; append new variants afterwards. Do not perform this option migration with CSV.'
        p['shopify_handle']=handle
    assert len({tuple((o['name'],o['value']) for o in p['shopify_options']) for p in ps})==len(ps)
    assert len({tuple(o['name'] for o in p['shopify_options']) for p in ps})==1

retired=[{'product_id':o['product_id'],'name':clean(o['name']),'action':'Do not recreate; absent from current app after merge/retirement',
          'old_sku':o.get('proposed_listing_sku','')} for o in old['options'] if o['product_id'] not in {p['product_id'] for p in products}]
media=[]
for p in products:
    by_id={r['image']['id']:r for r in snapshot['images'] if r['product_id']==p['product_id']}
    ordered=sorted(p['listing_photo_ids'],key=lambda aid:(aid!=p['primary_photo_id'],by_id[aid]['choice'].get('order',0),aid))
    for position,aid in enumerate(ordered,1):
        r=by_id[aid];a=r['image'];original=a['original'];dims=original.get('dimensions') or [None,None]
        media.append({'product_id':p['product_id'],'sku':p['sku'],'shopify_handle':p['shopify_handle'],
          'position':position,'primary':aid==p['primary_photo_id'],'listing_decision':p['listing_decision'],
          'image_id':aid,'name':a['name'],'source':'Dropbox','source_url':a['url'],'folder_url':a['folder_url'],
          'content_hash':original.get('dropbox_content_hash'),'bytes':original.get('bytes'),
          'original_width':dims[0],'original_height':dims[1],'alt':r['choice'].get('alt',''),
          'types':a.get('effective_types',r['metadata'].get('types',a.get('types',[]))),
          'purposes':r['choice'].get('uses',[]),'rights':r['metadata'].get('rights','unknown'),
          'edit_requested':r['choice'].get('edit_notes',''),'publication_review':flag_by_id.get(aid,''),
          'upload_method':'Fetch original by stable Dropbox ID, verify content hash, then upload to destination media storage',
          'public_import_url':''})
counts={'components':len(products),'groups':len(groups),'listing_decisions':dict(Counter(p['listing_decision'] for p in products)),
        'squarespace_exact_variants':len(exact_claims),'shopify_actions':dict(Counter(p['shopify_action'] for p in products)),
        'squarespace_actions':dict(Counter(p['squarespace_action'] for p in products)),
        'unique_skus':len(sku_claims),'retired_components_omitted':len(retired),'selected_image_associations':len(media),
        'distinct_selected_photos':len({r['image_id'] for r in media}),
        'selected_photos_missing_alt':len({r['image_id'] for r in media if not r['alt'].strip()}),
        'selected_photos_missing_dimensions':len({r['image_id'] for r in media if not r['original_width'] or not r['original_height']}),
        'components_with_publication_review':sum(bool(p['publication_review']) for p in products)}
payload={'created_utc':snapshot['created_utc'],'status':'PREPARED_LOCAL_UPLOAD_PLAN_NO_PLATFORM_WRITES',
    'source_receipts':source_receipts,'counts':counts,'products':products,'retired':retired,
    'delivery_policy':read(OUT/'delivery-policy.json') if (OUT/'delivery-policy.json').exists() else {'charge':'Quote separately per order'},
    'media_upload_pending':'Private Dropbox browse links are references, not public platform-import image URLs.',
    'platform_recheck':'Local source exports have no current admin guarantee. Resolve handles/IDs again before applying; no Shopify numeric IDs were invented.'}
(OUT/'upload-plan.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
flat=[]
for p in products:
    flat.append({k:v for k,v in p.items() if k not in ('specifications','listing_photo_ids','in_situ_photo_ids')}|p['specifications'])
write_csv('all-components-upload-register.csv',flat)
write_csv('selected-image-upload-manifest.csv',media)
write_csv('retired-components-not-for-upload.csv',retired)

# Native Shopify draft CSV for new local handles only. Media is supplied in the
# separate authenticated upload manifest, never as a login-gated Image Src.
headers=['Handle','Title','Body (HTML)','Vendor','Type','Tags','Published','Option1 Name','Option1 Value',
         'Variant SKU','Variant Price','Variant Requires Shipping','Variant Inventory Policy','Variant Fulfillment Service',
         'Cost per item','Status']
drafts=[];updates=[]
for group,ps in groups.items():
    applicable=[p for p in ps if p['listing_decision']=='include']
    if not applicable:continue
    new=all('new draft' in p['shopify_action'] or p['shopify_action']=='Create draft product' for p in ps)
    if new:
        title=group_title(ps)
        body=''.join('<h3>'+html.escape(p['name'])+'</h3><p>'+html.escape(p['specifications']['Description'])+'</p>' for p in applicable)
        for i,p in enumerate(applicable):
            row=dict.fromkeys(headers,'');row.update({'Handle':p['shopify_handle'],'Title':title if i==0 else '',
                'Body (HTML)':body if i==0 else '', 'Vendor':'Boldstone' if i==0 else '', 'Type':'Wall Sculpture' if i==0 else '',
                'Tags':p['family']+', made to order, delivery quote' if i==0 else '', 'Published':'FALSE' if i==0 else '',
                'Option1 Name':p['shopify_options'][0]['name'],'Option1 Value':p['shopify_options'][0]['value'],
                'Variant SKU':p['sku'],'Variant Price':f"{p['price_gbp']:.2f}",'Variant Requires Shipping':'TRUE',
                'Variant Inventory Policy':'continue','Variant Fulfillment Service':'manual',
                'Cost per item':f"{p['manufacturing_cost_gbp']:.2f}",'Status':'draft' if i==0 else ''})
            drafts.append(row)
    for p in applicable:
        if p['shopify_action']=='Update exact existing variant':
            row={'Handle':p['shopify_handle'],'Title':sh[p['sku']][0]['Title'],'Option1 Name':'','Option1 Value':'','Option2 Name':'',
                 'Option2 Value':'','Option3 Name':'','Option3 Value':'','Variant SKU':p['sku'],'Variant Price':f"{p['price_gbp']:.2f}",
                 'Cost per item':f"{p['manufacturing_cost_gbp']:.2f}"}
            for i,o in enumerate(p['shopify_existing_options'],1):row[f'Option{i} Name']=o['name'];row[f'Option{i} Value']=o['value']
            updates.append(row)
write_csv('shopify-new-products-draft.csv',drafts,headers)
write_csv('shopify-existing-variant-price-updates.csv',updates)
assert len(products)==181 and len(sku_claims)==181
assert len({p['shopify_handle'] for p in products})==len(groups)
(OUT/'upload-preparation-checks.json').write_text(json.dumps({'status':'PASS','counts':counts,'native_new_draft_rows':len(drafts),
  'existing_price_update_rows':len(updates),'no_duplicate_skus':True,'no_duplicate_native_variant_targets':True,
  'retired_components_not_reintroduced':True,'native_numeric_ids_not_invented':True,
  'public_image_urls_not_invented':True,'shipping_costs_not_added_to_markup_price':True},indent=2))
print(json.dumps(counts,indent=2))
