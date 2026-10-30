import json,csv,hashlib,datetime,collections,re,html,shutil
from pathlib import Path
from html.parser import HTMLParser

OUT=Path(__file__).parent
BASE=OUT.parent
MASTER=BASE/'inputs/master-register.json'
CSV=Path('/Users/tprice/Documents/boldstone/SquareSpace product upload/products_Jul-15_09-37-26AM.csv')
NATIVE=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue/evidence/native_records.json')
PRODUCT_FIELDS=['Product ID [Non Editable]','Product Type [Non Editable]','Product Page','Product URL','Title','Description','Categories','Tags','Visible','Hosted Image URLs']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
class Text(HTMLParser):
 def __init__(self):super().__init__();self.words=[]
 def handle_starttag(self,t,a):
  if t in ['p','li','br','div']:self.words.append('\n')
 def handle_endtag(self,t):
  if t in ['p','li','div']:self.words.append('\n')
 def handle_data(self,d):self.words.append(d)
def plain(s):
 p=Text();p.feed(s or '');return '\n'.join(re.sub(r'\s+',' ',x).strip() for x in ''.join(p.words).split('\n') if x.strip())
def evidence(path,pointer=None,**kw):return {'path':str(path),'sha256':sha(path),**({'json_pointer':pointer} if pointer else {}),**kw}

def main():
 assert sha(MASTER)=='30ff291d6b6fe0aad3a2bc39e121de4ef838c09afceb5f7ab11c78ea7fa71e2c'
 master=json.load(open(MASTER));native_all=json.load(open(NATIVE));native=[(i,x) for i,x in enumerate(native_all) if x['platform']=='Squarespace']
 rawdir=OUT/'raw-cached';rawdir.mkdir(exist_ok=True)
 rawcsv=rawdir/CSV.name
 if not rawcsv.exists():shutil.copyfile(CSV,rawcsv)
 assert sha(rawcsv)==sha(CSV)
 sources={'saved_native_csv':evidence(CSV,export_timestamp='Not encoded; filename has July15 but year and actual export time not asserted',preserved_raw_copy=str(rawcsv)),
  'cached_wall_native_rows':evidence(NATIVE,scope='223 Squarespace rows only; no Shopify normalization performed'),
  'frozen_master':evidence(MASTER,scope='184 catalogue options; platform source context only, not new184 matching')}
 products={}
 def get(pid):return products.setdefault(pid,{'platform':'Squarespace','native_product_id':pid,'observations':[]})
 def cv(v,pid,loc):
  return {'native_product_id':pid,'native_variant_id':v.get('Variant ID [Non Editable]'),'sku':v.get('SKU'),
   'option_attributes':{v[f'Option Name {i}']:v.get(f'Option Value {i}') for i in range(1,7) if v.get(f'Option Name {i}')},
   'option_values_in_source_order':[{'name':v.get(f'Option Name {i}'),'value':v.get(f'Option Value {i}')} for i in range(1,7) if v.get(f'Option Name {i}') or v.get(f'Option Value {i}')],
   'price':{'source_amount':v.get('Price'),'sale_amount':v.get('Sale Price'),'on_sale_raw':v.get('On Sale'),'currency':None,'currency_state':'UNENCODED_IN_NATIVE_CSV; NO_INHERITANCE_FROM_PUBLIC_OTHER_VERSION'},
   'stock_setting':{'raw':v.get('Stock'),'physical_stock_verified':False},'raw_dimensions_and_weight':{k:v.get(k) for k in ['Weight','Length','Width','Height']},
   'dimensions_weight_units':'NOT_ENCODED_IN_CSV; NOT_CONVERTED','source_locator':loc}
 groups={};parent=None
 with rawcsv.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f)
  for i,v in enumerate(reader):
   if v['Product ID [Non Editable]']:
    parent={k:v.get(k,'') for k in PRODUCT_FIELDS};pid=parent['Product ID [Non Editable]']
    groups[pid]={'source_kind':'SAVED_NATIVE_CSV','source_state':'CACHED_SOURCE_ONLY','source_export_time':None,'native_product_id':pid,
     'title':parent['Title'],'description_html':parent['Description'],'description_text':plain(parent['Description']),
     'url':'https://boldstonesculpture.com/'+parent['Product Page']+'/p/'+parent['Product URL'],'product_type':parent['Product Type [Non Editable]'],
     'visibility_raw':parent['Visible'],'categories_raw':parent['Categories'],'tags_raw':parent['Tags'],'hosted_image_urls':parent['Hosted Image URLs'].split(),
     'product_row_locator':{'path':str(rawcsv),'csv_record_1_based':i+1,'header_inclusive_logical_row':i+2},'variants':[]}
   assert parent is not None
   loc={'path':str(rawcsv),'csv_record_1_based':i+1,'header_inclusive_logical_row':i+2,'parent_context_inherited_for_blank_product_cells':not bool(v['Product ID [Non Editable]'])}
   groups[pid]['variants'].append(cv(v,pid,loc))
 for pid,x in groups.items():get(pid)['observations'].append(x)
 ng={}
 for i,n in native:
  v=n['values'];pid=n['parent_id']
  if pid not in ng:
   ng[pid]={'source_kind':'CACHED_WALL_NATIVE_EXTRACT','source_state':'CACHED_SOURCE_ONLY','native_product_id':pid,'title':v.get('Title'),
    'description_html':v.get('Description'),'description_text':plain(v.get('Description')),'url':'https://boldstonesculpture.com/'+v.get('Product Page','buy')+'/p/'+v.get('Product URL',''),
    'visibility_raw':v.get('Visible'),'categories_raw':v.get('Categories'),'tags_raw':v.get('Tags'),'hosted_image_urls':v.get('Hosted Image URLs','').split(),'variants':[],
    'source_locator':{'path':str(NATIVE),'json_pointer':f'/{i}'}}
  ng[pid]['variants'].append(cv(v,pid,{'path':str(NATIVE),'json_pointer':f'/{i}','source_sheet':n['source_sheet'],'source_row':n['source_row'],'native_csv_record':n['native_csv_record']}))
 for pid,x in ng.items():get(pid)['observations'].append(x)
 pages=json.load(open(OUT/'PUBLIC_PAGINATION.json'));catnames={};public_items={}
 def public_obs(item,path,pointer,receipt,kind):
  pid=item['id'];sc=item.get('structuredContent') or {};variants=item.get('variants') if isinstance(item.get('variants'),list) else sc.get('variants',[])
  vs=[]
  for i,v in enumerate(variants):
   vs.append({'native_product_id':pid,'native_variant_id':v.get('id'),'sku':v.get('sku'),'option_attributes':v.get('attributes',{}),'option_values_in_source_order':v.get('optionValues',[]),
    'price':{'price_money':v.get('priceMoney'),'sale_price_money':v.get('salePriceMoney'),'native_price_integer':v.get('price'),'native_sale_price_integer':v.get('salePrice'),'on_sale':v.get('onSale')},
    'stock_setting':{'unlimited':v.get('unlimited'),'qty_in_stock_raw':v.get('qtyInStock'),'physical_stock_verified':False},
    'raw_dimensions_and_weight':{k:v.get(k) for k in ['len','width','height','weight']},'dimensions_weight_units':'NATIVE_NUMBERS_WITHOUT_UNIT_ASSERTION; NOT_CONVERTED',
    'native_image_ids':v.get('imageIds',[]),'native_images':v.get('images',[]),'source_locator':{'path':path,'json_pointer':pointer+'/variants/'+str(i)}})
  description_field='body' if item.get('body') else 'excerpt'
  return {'source_kind':kind,'source_state':'FRESH_PUBLIC_OBSERVED','native_product_id':pid,'observed_utc':receipt.get('response_utc'),
   'title':item.get('title'),'description_html':item.get(description_field),'description_text':plain(item.get(description_field)),'description_source_field':description_field,
   'url':'https://boldstonesculpture.com'+item.get('fullUrl',''),
   'workflow_state_raw':item.get('workflowState'),'collection_id':item.get('collectionId'),'updated_on_native':item.get('updatedOn'),'publish_on_native':item.get('publishOn'),
   'category_ids':item.get('categoryIds',[]),'category_names':[catnames.get(x,x) for x in item.get('categoryIds',[])],'tags':item.get('tags',[]),
   'product_type_raw':item.get('productType'),'product_level_price_money_raw':item.get('priceMoney'),'variant_option_ordering':item.get('variantOptionOrdering',[]),
   'primary_asset_url':item.get('assetUrl'),'native_media_items':item.get('items',[]),'variants':vs,
   'source_locator':{'path':path,'json_pointer':pointer,'body_sha256':receipt['sha256']},'receipt_url':receipt['url']}
 for pg in pages['pages']:
  x=json.load(open(pg['body_path']));receipt=json.load(open(pg['receipt_path']))
  def cats(z):
   for q in z:
    catnames[q['id']]=q.get('displayName');cats(q.get('children',[]))
  cats(x.get('nestedCategories',{}).get('categories',[]))
  for i,item in enumerate(x.get('items',[])):
   pid=item['id'];public_items[pid]=item
   get(pid)['observations'].append(public_obs(item,pg['body_path'],f'/items/{i}',receipt,'FRESH_PUBLIC_COLLECTION_JSON'))
 direct=json.load(open(OUT/'DIRECT_PRODUCT_CHECKS.json'))
 for q in direct['checks']:
  prod=get(q['expected_product_id']);prod.setdefault('public_detail_checks',[]).append(q)
  if q.get('http_status')==200 and q.get('response_product_id'):
   x=json.load(open(q['body_path']));r=json.load(open(q['receipt_path']));pid=x['item']['id']
   get(pid)['observations'].append(public_obs(x['item'],q['body_path'],'/item',r,'FRESH_PUBLIC_PRODUCT_JSON'))
 prior=collections.defaultdict(list)
 for i,x in enumerate(master.get('source_platform_offer_coverage',[])):
  if x.get('squarespace_id'):prior[x['squarespace_id']].append({'source_offer_ref':x['offer_ref'],'source_sale_scope':x.get('source_sale_scope'),'native_parts_source_claim':x.get('native_parts'),
   'source_cautions':x.get('source_cautions'),'body_description_inherited_to_members':False,'evidence_state':'PRIOR_CATALOGUE_SOURCE_INTERPRETATION_NOT_A_NEW_PRODUCT_MATCH',
   'source_locator':{'path':str(MASTER),'json_pointer':f'/source_platform_offer_coverage/{i}'}})
 for pid,p in products.items():
  observations=p['observations'];fresh=[o for o in observations if o['source_state']=='FRESH_PUBLIC_OBSERVED'];preferred=(fresh or observations)[-1]
  p.update(title=preferred['title'],url=preferred['url'],description_text=preferred['description_text'],variants=preferred['variants'],
   normalized_variant_source=preferred['source_kind'],preferred_source_locator=preferred['source_locator'] if 'source_locator' in preferred else preferred['product_row_locator'],
   public_collection_observed=pid in public_items,fresh_public_product_observed=bool(fresh),inventory_state='FRESH_PUBLIC_OBSERVED' if fresh else 'CACHED_ONLY_NOT_RETURNED_IN_CHECKED_PUBLIC_COLLECTION',
   cached_wall_extract_member=pid in ng,cached_native_csv_member=pid in groups,prior_catalogue_offer_scopes=prior[pid],
   native_sellable_unit={'classification':'UNRESOLVED_PENDING_DESCRIPTION_REVIEW','quantity_per_offered_unit':None,'basis':'No panel count inferred from photographs or from a title alone','cart_quantity_and_physical_stock_are_separate':True})
  changes=[]
  if fresh:
   freshmap={v['native_variant_id']:v for v in preferred['variants']}
   for old in [o for o in observations if o['source_state']=='CACHED_SOURCE_ONLY']:
    oldmap={v['native_variant_id']:v for v in old['variants']}
    differences=[]
    for vid in set(oldmap)&set(freshmap):
     a,b=oldmap[vid],freshmap[vid]
     changed={k:{'cached':a[k],'fresh':b[k]} for k in ['sku','option_attributes'] if a[k]!=b[k]}
     oldprice=a['price']['source_amount'];newprice=(b['price'].get('price_money') or {}).get('value')
     if newprice is not None and oldprice!=newprice:changed['price_amount']={'cached':oldprice,'fresh':newprice,'currency_note':'Cached CSV currency unencoded; fresh priceMoney currency retained'}
     if changed:differences.append({'native_variant_id':vid,'fields':changed})
    changes.append({'cached_source_kind':old['source_kind'],'added_native_variant_ids':sorted(set(freshmap)-set(oldmap)),'not_currently_returned_native_variant_ids':sorted(set(oldmap)-set(freshmap)),'same_id_field_differences':differences,
     'identity_relation':'Exact native IDs only; no design/184-option match implied'})
  p['cached_to_public_changes']=changes
 def sku_collisions(which):
  buckets=collections.defaultdict(list)
  for p in products.values():
   if which=='fresh' and not p['fresh_public_product_observed']:continue
   if which=='cached' and p['fresh_public_product_observed']:continue
   for v in p['variants']:
    if v.get('sku'):buckets[v['sku']].append({'native_product_id':p['native_product_id'],'native_variant_id':v['native_variant_id'],'title':p['title'],'option_attributes':v['option_attributes'],'source_state':p['inventory_state']})
  return [{'sku':k,'records':v,'treatment':'SKU_COLLISION; NOT_AUTOMATIC_SAME_PRODUCT_OR_DELETION_CANDIDATE'} for k,v in buckets.items() if len({(x['native_product_id'],x['native_variant_id']) for x in v})>1]
 records=sorted(products.values(),key=lambda p:p['native_product_id'])
 result={'schema':'boldstone.squarespace-source-inventory.v1','status':'PRELIMINARY_NATIVE_IDS_RECOVERED; SALE_UNIT_REVIEW_PENDING','prepared_utc':now(),
  'bound_master_sha256':sha(MASTER),'scope':'Squarespace source inventory only; no184-option matching or shared import','source_manifest':sources,
  'counts':{'all_observed_product_ids_union':len(records),'fresh_public_collection_product_ids':len(public_items),'fresh_public_collection_variant_rows':sum(len(x.get('variants',[])) for x in public_items.values()),
   'cached_full_csv_product_ids':len(groups),'cached_full_csv_variant_rows':sum(len(x['variants']) for x in groups.values()),'cached_wall_extract_product_ids':len(ng),'cached_wall_extract_variant_rows':len(native),
   'source_only_product_ids':sum(not p['fresh_public_product_observed'] for p in records),'normalized_preferred_variant_rows_including_source_only':sum(len(p['variants']) for p in records)},
  'public_pagination':pages,'direct_product_check_receipt':str(OUT/'DIRECT_PRODUCT_CHECKS.json'),'products':records,
  'duplicate_sku_candidates':sku_collisions('fresh')+sku_collisions('cached'),'product_duplicate_candidates':[],
  'completeness_and_freshness_limits':['Fresh public collection follows the returned nextPageUrl chain;203 products were returned while collection.itemCount reports208. The discrepancy remains explicit.',
   'Anonymous public reads do not enumerate authenticated drafts, hidden inventory or all account products. Source-only or404 records are not certified deletions.',
   'The saved native CSV has342 variant rows and174 populated product headers. Blank continuation product cells inherit only the preceding explicit parent context; raw CSV is preserved byte for byte.',
   'Raw weight/dimension units and CSV currency are not guessed. Unlimited stock settings do not establish physical inventory or availability.',
   'Exact native product identity, native variant/configuration identity and184 catalogue option identity are separate. No title-only exact match or cross-platform duplicate inference is made.'],
  'remote_writes':0,'shared_master_writes':0,'shopify_reads_performed':False,'dropbox_calls_performed':False,'live_sandbox_tests_run':False}
 dump(OUT/'SQUARESPACE_SOURCE_INVENTORY.json',result)
 dump(OUT/'SOURCE_COUNTS_EARLY.json',{'status':result['status'],'counts':result['counts'],'schema':result['schema'],'path':str(OUT/'SQUARESPACE_SOURCE_INVENTORY.json'),'sha256':sha(OUT/'SQUARESPACE_SOURCE_INVENTORY.json')})
 print(json.dumps(result['counts'],indent=2))

if __name__=='__main__':main()
