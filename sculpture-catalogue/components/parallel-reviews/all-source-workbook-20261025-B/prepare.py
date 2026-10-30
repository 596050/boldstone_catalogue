"""Prepare complete, qualified source inventories for one standalone workbook."""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict, Counter
import csv, hashlib, html, json, re, sqlite3

W = Path(__file__).resolve().parent
B = W.parents[2]
ROOT = B.parent
OUT = B / 'outputs/01a13fe6-495b-7253-b923-31823b4cbca8/all-source-register-2026-10-25'
OUT.mkdir(parents=True, exist_ok=True)
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
def join(xs):
    values = [json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else str(x) for x in xs if x is not None and x != '']
    return '\n'.join(dict.fromkeys(values))
def num(v):
    if v is None or v == '': return None
    try: return float(v)
    except (ValueError, TypeError): return None
def plain(v):
    return html.unescape(re.sub('<[^>]+>', ' ', str(v or ''))).strip()
def col(n):
    s = ''; n += 1
    while n: n, k = divmod(n-1, 26); s = chr(65+k) + s
    return s

pointer_path = B / 'current-master.json'; pointer = read(pointer_path)
regpath = B / pointer['register']; reg = read(regpath)
assert sha(regpath) == pointer['register_sha256']
planpath = Path(pointer['current_listing_treatment_plan']['register']); plan = read(planpath)
assert sha(planpath) == pointer['current_listing_treatment_plan']['register_sha256']
galleryseal = B / pointer['current_published_gallery_projection']['path']; G = galleryseal.parent
assert sha(galleryseal) == pointer['current_published_gallery_projection']['sha256']
dbpath = G / 'complete-image-platform-register.sqlite'
c = sqlite3.connect('file:' + str(dbpath) + '?mode=ro', uri=True)
def records(t): return [json.loads(x[0]) for x in c.execute('SELECT record_json FROM ' + t)]
images = records('images'); image_map = {x['file_id']: x for x in images}
associations = records('associations')
ss80 = records('local_squarespace_records'); ss_by_id = {x['squarespace_native_tuple']['native_product_id']: x for x in ss80}
sh136 = records('local_shopify_products'); sh_map = {x['handle']: x for x in sh136}
sh160 = records('local_shopify_variants'); shmedia = records('local_shopify_media')
ss445 = records('source_gallery'); source260 = records('source_product_links')
prior_source_edges = list(c.execute('SELECT product_id,offer_ref,relationship FROM source_product_links'))
crosspath = ROOT / 'reports/local-platform-crosswalk-corrected-20261024-root/local-platform-crosswalk.json'
cross = read(crosspath)
sspath = Path(ss80[0]['local_squarespace_gallery_record']['csv_path'])
assert sha(sspath) == ss80[0]['local_squarespace_gallery_record']['csv_sha256']
shpath = Path(cross['source_authority']['primary_shopify_export']['path'])
assert sha(shpath) == cross['source_authority']['primary_shopify_export']['sha256']
def csvrows(p):
    with p.open(encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f); return list(r.fieldnames), list(r)
ssheaders, ssraw = csvrows(sspath); shheaders, shraw = csvrows(shpath)
N = ROOT / 'reports/dropbox-wall-complete-role-review-20261024T214349Z'
nativepath = N / 'complete-current-native-object-map.json'; native = read(nativepath)
folders = [x for x in native.values() if x['object_type'] == 'folder']
assert len(folders) == 442 and len(images) == 6690
auditpath = B / 'components/parallel-reviews/matched-listing-finalization-20261025-B/all-source-association-audit.json'
audit = read(auditpath)['entries']
active_ids = set(reg['active_option_ids'])
products = {x['product_id']: x for x in reg['options'] if x['product_id'] in active_ids}
treatments = {x['product_id']: x for x in plan['options']}
assert len(products) == len(treatments) == 188 and set(products) == set(treatments)

inputs = [pointer_path, regpath, planpath, galleryseal, dbpath, sspath, shpath, crosspath, nativepath, auditpath,
          G / 'current-images-without-option-scope.json', G / 'family-image-reader-index.json',
          N / 'exact-byte-duplicate-groups-current.json']
manifest = [{'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size} for p in inputs]
write(W / 'input-manifest.json', {'captured_utc': datetime.now(timezone.utc).isoformat(), 'inputs': manifest})

# Expand Squarespace continuation rows only in normalized views; raw rows stay intact.
ssproducts = {}; ssvariants = []; parent = None
for ordinal, raw in enumerate(ssraw, 2):
    if raw['Product ID [Non Editable]']:
        parent = raw['Product ID [Non Editable]']
        assert parent not in ssproducts
        ssproducts[parent] = {'id': parent, 'raw': raw, 'row': ordinal, 'variants': [], 'images': []}
    assert parent
    variant = {'product_id': parent, 'variant_id': raw['Variant ID [Non Editable]'], 'raw': raw, 'row': ordinal}
    ssproducts[parent]['variants'].append(variant); ssvariants.append(variant)
    for url in raw['Hosted Image URLs'].split():
        if url not in ssproducts[parent]['images']: ssproducts[parent]['images'].append(url)
assert len(ssproducts) == 208 and len(ssvariants) == 376 and len({v['variant_id'] for v in ssvariants}) == 376
assert set(ss_by_id).issubset(ssproducts) and len(ss_by_id) == 80
assert len(sh136) == 136 and len(sh160) == 160 and len(shraw) == 416
shsku = defaultdict(list); sssku = defaultdict(list)
for x in sh160:
    if x['sku_raw']: shsku[x['sku_raw']].append(x)
for x in ssvariants:
    if x['raw']['SKU']: sssku[x['raw']['SKU']].append(x)
pair_rows = []
for sku in sorted(set(shsku) & set(sssku)):
    status = 'Exact raw SKU pair' if len(shsku[sku]) == len(sssku[sku]) == 1 else 'Ambiguous repeated raw SKU'
    for s in sssku[sku]:
        for h in shsku[sku]:
            pair_rows.append([sku, status, s['product_id'], s['variant_id'], ssproducts[s['product_id']]['raw']['Title'], h['handle'], h['variant_key'], sh_map[h['handle']]['product']['title'],
                              'Source-row equality only; design, finish, quantity and current stock are not newly confirmed.', s['row'], h['source_row']['logical_row_including_header']])

selected_ss = defaultdict(list); selected_sh = defaultdict(list); related_ss = defaultdict(set); related_sh = defaultdict(set)
for pid, t in treatments.items():
    if t['selected_squarespace_product_id']: selected_ss[t['selected_squarespace_product_id']].append(pid)
    if t['selected_local_shopify_handle']: selected_sh[t['selected_local_shopify_handle']].append(pid)
    for offer in t['related_source_offer_refs']:
        r = next((x for x in ss80 if x['offer_ref'] == offer), None)
        if r:
            sid = r['squarespace_native_tuple']['native_product_id']; related_ss[sid].add(pid)
            h = (r.get('shopify_local_product') or {}).get('handle')
            if h: related_sh[h].add(pid)
for h, obj in sh_map.items():
    for offer in obj['matched_squarespace_offer_refs']:
        r = next((x for x in ss80 if x['offer_ref'] == offer), None)
        if r: related_sh[h].update(related_ss[r['squarespace_native_tuple']['native_product_id']])
    if obj['product'].get('in_preserved_wall_subset') and not obj['matched_squarespace_offer_refs']:
        for pid, t in treatments.items():
            if 'SH-DRAFT' in t['related_source_offer_refs']: related_sh[h].add(pid)
names = lambda ids: join(products[i]['name'] for i in sorted(set(ids)) if i in products)
selected_refs = defaultdict(list)
for pid, t in treatments.items():
    if t['selected_image'].get('file_id'): selected_refs[t['selected_image']['file_id']].append(pid)
by_file = defaultdict(list); pairs = defaultdict(list)
for a in associations: by_file[a['file_id']].append(a); pairs[(a['product_id'], a['file_id'])].append(a)
assert len(pairs) == 10847
unscoped = read(G / 'current-images-without-option-scope.json'); unscoped_ids = {x['file_id'] for x in unscoped}
assert len(unscoped_ids) == 625
source_image_ids = defaultdict(list)
for g in ss445:
    for fid in g.get('supported_photo_file_ids', []): source_image_ids[fid].append(g['offer_ref'])

tabs = []
def tab(name, title, columns, rows, note='', source=None, links=None, widths=None):
    obj = {'name': name, 'title': title, 'columns': columns, 'rows': rows, 'note': note,
           'source': str(source) if source else '', 'links': links or {}, 'widths': widths or {}, 'formulas': {}}
    tabs.append(obj); return obj
def idslink(sheet, key, label=None): return {'sheet': sheet, 'key': key, 'label': label or str(key)}
def url(u, label='Open'): return {'url': u, 'label': label} if u else None
def addlink(t, ri, ci, value):
    if value: t['links'][str(ri)+','+str(ci)] = value

overview = tab('Overview', 'BOLDSTONE | Consolidated sources', ['Inventory / result', 'Records', 'Scope'], [],
               'Saved source snapshots consolidated on 25 October 2026. Inventory completeness and confirmed sculpture identity are separate statuses.')
human_treatment = {
 'REUSE_EXISTING_INDIVIDUAL_RECORD':'Matched existing individual',
 'UPDATE_EXISTING_INDIVIDUAL_RECORD_COPY':'Matched; copy update proposed',
 'REUSE_RECORDED_PATTERN_VARIANT_WORKING_MAPPING':'Provisional pattern match',
 'CREATE_INDIVIDUAL_PRODUCT_IN_LOCAL_PLAN':'New individual listing proposed',
 'CREATE_INDIVIDUAL_PRODUCT_LINKED_TO_ARRANGEMENT':'New individual linked to arrangement',
 'CREATE_SEPARATE_WATER_FEATURE_PRODUCT':'New water-feature listing proposed',
 'ADD_DISTINCT_FINISH_OR_BUILD_VARIANT':'Additional variant proposed',
 'ADD_NAMED_PATTERN_VARIANT':'Additional named pattern proposed',
 'RETAIN_LEGACY_REFERENCE_NO_DUPLICATE_CREATION':'Duplicate avoidance; retain history',
 'RETAIN_EXISTING_CANDIDATE_PENDING_EXACT_BINDING':'Unmatched exact listing'}
prows = []
for pid, t in sorted(treatments.items(), key=lambda x:x[1]['name'].casefold()):
    p = products[pid]; mf = p['master_fields']; selling = p.get('selling_details', {}); im = t['selected_image']
    prows.append([pid, p['name'], human_treatment[t['listing_treatment']], p.get('family'), p.get('canonical_component_id'), t['working_design_group_id'],
                  mf['Dimensions / depth']['display'], mf['Weight']['display'], mf['Material / finish']['display'], mf['Fixing']['display'],
                  selling.get('estimated_price'), selling.get('estimated_price_upper'), mf['Individual price']['display'], mf['Availability']['display'],
                  selling.get('lead_time_min_weeks'), selling.get('lead_time_max_weeks'), join(t['selected_source_offer_refs']), t['selected_squarespace_product_id'],
                  t['selected_squarespace_variant_id'], t['selected_local_shopify_handle'], t['selected_existing_source_sku'], t['proposed_listing_sku'],
                  t['variant_label'], t['proposed_product_group_key'], t['reason'], im.get('file_id'), im.get('role'), 'Image' if im.get('image_url') else '',
                  'Folder' if im.get('folder_url') else '', join(t['confirmed_arrangement_ids']), join(t['retained_names']),
                  'Working estimates and source qualifications retained; physical details are not newly verified.'])
pt = tab('Products', 'Consolidated sculpture options', ['Product ID','Product / option','Listing status','Family','Component ID','Working design group','Dimensions / depth','Weight','Material / finish','Fixing choices','Working price GBP','Upper price GBP','Price qualification','Availability','Lead time min weeks','Lead time max weeks','Selected offer refs','Squarespace product ID','Squarespace variant ID','Shopify handle','Existing SKU','Proposed SKU','Variant label','Proposed product group','Reason / next action','Selected Dropbox file ID','Image role','Image','Folder','Arrangement IDs','Retained names','Specification qualification'], prows,
         '188 active options. New listings and provisional matches are proposals; no shop import was performed.', regpath, widths={1:42,2:30,6:65,7:54,8:66,9:55,12:62,13:62,24:75})
for i, row in enumerate(prows):
    t=treatments[row[0]]; addlink(pt,i,17,idslink('Squarespace',row[17]) if row[17] else None);addlink(pt,i,19,idslink('Shopify',row[19]) if row[19] else None)
    addlink(pt,i,25,idslink('Dropbox files',row[25]) if row[25] else None)
    addlink(pt,i,27,url(t['selected_image'].get('image_url'),'Image'));addlink(pt,i,28,url(t['selected_image'].get('folder_url'),'Folder'))

specrows=[]
for p in reg['options']:
    for field, v in p['master_fields'].items():
        specrows.append([p['product_id']+' | '+field,p['product_id'],p['name'],'Active' if p['product_id'] in active_ids else 'Retired history',field,v['display'],v.get('state'),v.get('basis'),v.get('working_recorded'),v.get('physical_verification'),join(v.get('source_scopes',[])),join(v.get('source_references',[])),json.dumps(v.get('completion_proposal',{}),ensure_ascii=False),v.get('prior_display','')])
st=tab('Specifications','Working specifications and retained history',['Field key','Product ID','Product / option','Lifecycle','Specification','Working value','Qualification','Basis / evidence','Working recorded','Physical verification','Source scopes','Source references','Completion proposal details','Previous value'],specrows,
       'All 1,134 retained field groups: 1,128 active and six for the retired option. Original qualification and basis text are retained.',regpath,widths={2:42,5:84,6:70,7:110,13:70})
for i,r in enumerate(specrows):
    if r[1] in products:addlink(st,i,1,idslink('Products',r[1]))

componentrows=[]
for x in reg['components']:
    componentrows.append([x['component_id'],x['name'],x.get('family'),x['record_type'],join(x['option_ids']),join(x['option_names']),x['option_count'],join(x.get('source_component_ids',[])),join(x.get('retained_names',[])),x.get('scope_note'),'Image' if x.get('image_url') else '', 'Folder' if x.get('folder_url') else '',x.get('physical_mould_count'),x.get('physical_stock_quantity')])
ct=tab('Components','Retained component identities',['Component ID','Component name','Family','Record type','Option IDs','Option names','Retained option count','Source component IDs','Retained names','Scope note','Image','Folder','Physical mould count','Physical stock quantity'],componentrows,
       '112 retained component IDs project to 110 working design groups after approved equivalences. These are not counts of casts, moulds or stock.',regpath,widths={1:52,5:75,8:65,9:95})
for i,x in enumerate(reg['components']):addlink(ct,i,10,url(x.get('image_url'),'Image'));addlink(ct,i,11,url(x.get('folder_url'),'Folder'))

offerrows=[]
for edge in reg['source_offer_edges']:
    o=edge['source_offer']
    offerrows.append([edge['offer_ref'],o.get('title'),o.get('platform'),o.get('sq_id'),o.get('sh_handle'),o.get('sku'),o.get('sale_unit_state'),o.get('native_parts'),o.get('proposed_bom_pieces'),num(o.get('native_price')),o.get('native_currency'),o.get('stock'),o.get('source_each_cm'),o.get('source_overall_cm'),o.get('source_set_weight_kg'),o.get('raw_weight'),o.get('raw_length'),o.get('raw_width'),o.get('raw_height'),o.get('raw_units'),o.get('native_description'),o.get('cautions'),o.get('source_url'),json.dumps(edge.get('members',[]),ensure_ascii=False),'Retained source offer; values are not reassigned to individual members.'])
ot=tab('Reviewed offers','Retained source offers and sale-unit claims',['Offer ref','Source title','Platform','Squarespace product ID','Shopify handle','Source SKU','Sale-unit state','Source part count','Proposed part count','Source price','Currency qualification','Source stock setting','Each dimensions claim','Overall dimensions claim','Set weight claim','Raw weight','Raw length','Raw width','Raw height','Units qualification','Retained description','Source cautions','Source listing','Member claims','Qualification'],offerrows,
       '81 retained offers: 80 Squarespace records and one Shopify draft. Historical source claims remain separate from the current working product fields.',regpath,widths={1:52,6:65,20:110,21:105,23:115,24:100})
for i,r in enumerate(offerrows):
    addlink(ot,i,3,idslink('Squarespace',r[3]) if r[3] in ssproducts else None)
    addlink(ot,i,4,idslink('Shopify',r[4]) if r[4] in sh_map else None)
    addlink(ot,i,22,url(r[22],'Source listing'))

reviewrows=[]
for pid,t in treatments.items():
    if t['listing_treatment'] in ['REUSE_RECORDED_PATTERN_VARIANT_WORKING_MAPPING','RETAIN_LEGACY_REFERENCE_NO_DUPLICATE_CREATION','RETAIN_EXISTING_CANDIDATE_PENDING_EXACT_BINDING']:
        reviewrows.append(['PRODUCT:'+pid,'Catalogue',pid,t['name'],human_treatment[t['listing_treatment']],t['reason'],'Products',pid])

ssrows=[]; ssvrows=[]; allgallery=[]
gallery_lookup={(x['native_product_id'],x['source_url']):x for x in ss445}
ssstatuses={}
for sid, sp in ssproducts.items():
    raw=sp['raw']; existing=ss_by_id.get(sid); sel=selected_ss[sid]; related=related_ss[sid]
    if sel:
        status='Provisional pattern match' if all(treatments[x]['listing_treatment']=='REUSE_RECORDED_PATTERN_VARIANT_WORKING_MAPPING' for x in sel) else 'Matched individual record'
    elif existing and related:status='Related family / arrangement only'
    elif existing:status='Unmatched in reviewed sculpture scope'
    else:status='Outside reviewed sculpture scope'
    ssstatuses[sid]=status
    counterparts=sorted({h['handle'] for v in sp['variants'] for h in shsku.get(v['raw']['SKU'],[]) if v['raw']['SKU']})
    ssrows.append([sid,raw['Title'],status,existing['offer_ref'] if existing else '',len(sp['variants']),join(v['raw']['SKU'] for v in sp['variants']),join(sel),names(sel),join(sorted(related)),names(related),join(counterparts),'Raw SKU counterpart' if counterparts else 'No raw SKU counterpart',raw['Product Page'],raw['Product URL'],raw['Categories'],raw['Tags'],raw['Visible'],len(sp['images']), 'Image' if sp['images'] else '',sp['row'],plain(raw['Description']), 'Physical-product export snapshot; no live availability or physical identity claim.'])
    if not sel:
        reviewrows.append(['SS:'+sid,'Squarespace',sid,raw['Title'],status,'Retained source record. '+('Existing component associations remain qualified.' if related else 'No individual catalogue assignment established.'),'Squarespace',sid])
    for idx,u in enumerate(sp['images'],1):
        old=gallery_lookup.get((sid,u),{})
        allgallery.append(['SS:'+sid+':'+str(idx),'Squarespace',sid,raw['Title'],idx,'Image',old.get('visual_role','Not visually reviewed in catalogue lane'),old.get('photo_correspondence_status','Unreviewed outside retained source gallery'),join(old.get('supported_photo_file_ids',[])),False,u,sp['row'],'Gallery membership does not assign this image to an exact variant.'])
    for v in sp['variants']:
        r=v['raw']; matched=[pid for pid,t in treatments.items() if t['selected_squarespace_variant_id']==v['variant_id']]
        options=join(r['Option Name '+str(i)]+' = '+r['Option Value '+str(i)] for i in range(1,7) if r['Option Value '+str(i)])
        ssvrows.append([v['variant_id'],sid,raw['Title'],r['SKU'],options,num(r['Price']),num(r['Sale Price']),r['On Sale'],r['Stock'],num(r['Weight']),num(r['Length']),num(r['Width']),num(r['Height']),'Raw export units / currency not encoded',join(matched),ssstatuses[sid],join(h['variant_key'] for h in shsku.get(r['SKU'],[]) if r['SKU']),v['row'],'Product fields inherited from the preceding explicit product header only. Variant values remain separate.'])
sst=tab('Squarespace','All Squarespace products in the Physical export',['Squarespace product ID','Source title','Catalogue association','Reviewed offer ref','Variant count','Source SKUs','Selected catalogue IDs','Selected catalogue options','Related catalogue IDs','Related options','Shopify SKU counterparts','Cross-platform status','Product page','Product slug','Categories','Tags','Source visibility','Image count','First image','Raw export row','Source description','Source qualification'],ssrows,
        '208 product headers; 80 belong to the previous sculpture review and 128 are additional source products. Export captured 24 October 2026.',sspath,widths={1:47,2:36,7:55,9:55,20:100})
for i,r in enumerate(ssrows):addlink(sst,i,18,url(ssproducts[r[0]]['images'][0] if ssproducts[r[0]]['images'] else '', 'Image'));addlink(sst,i,19,idslink('Squarespace raw',str(r[19]),str(r[19])))
svt=tab('Squarespace variants','All Squarespace export variants',['Variant ID','Product ID','Source title','SKU','Option tuple','Source price','Source sale price','On sale','Source stock setting','Raw weight','Raw length','Raw width','Raw height','Units / currency qualification','Selected catalogue IDs','Catalogue scope','Shopify variant counterparts','Raw export row','Continuation handling'],ssvrows,
        '376 native variant IDs, including all 144 Wall Circle combinations. Export prices and sizes are not overwritten by working estimates.',sspath,widths={2:42,4:85,13:45,18:85})
for i,r in enumerate(ssvrows):addlink(svt,i,1,idslink('Squarespace',r[1]));addlink(svt,i,17,idslink('Squarespace raw',str(r[17]),str(r[17])))

shrows=[]; shvrows=[]; shstatuses={}
for h, obj in sh_map.items():
    r=obj['product']; sel=selected_sh[h]; related=related_sh[h]
    if sel:status='Matched individual record'
    elif r['in_preserved_wall_subset'] and related:status='Related family / arrangement only'
    elif r['in_preserved_wall_subset']:status='Unmatched wall-sculpture draft'
    else:status='Outside reviewed sculpture scope'
    shstatuses[h]=status
    counterpart=sorted({s['product_id'] for v in obj['variants'] for s in sssku.get(v['sku_raw'],[]) if v['sku_raw']})
    medias=obj['full_product_gallery']
    shrows.append([h,r['title'],status,len(obj['variants']),join(v['sku_raw'] for v in obj['variants']),join(sel),names(sel),join(sorted(related)),names(related),join(counterpart),'Raw SKU counterpart' if counterpart else 'No raw SKU counterpart',r['type_raw'],r['product_category'],r['vendor_raw'],r['status_raw'],r['published_raw'],len(medias),'Image' if medias else '',r['source_header_row']['logical_row_including_header'],plain(r['body_html']),r['relative_product_path'],'Historical export corroborated by 30 August 2024 workbook; numeric Shopify IDs are not exported.'])
    if not sel:reviewrows.append(['SH:'+h,'Shopify',h,r['title'],status,'Retained source record. No new individual identity inferred from its title, SKU or gallery.','Shopify',h])
for v in sh160:
    h=v['handle'];srow=v['source_row']['logical_row_including_header'];sids=[s['variant_id'] for s in sssku.get(v['sku_raw'],[]) if v['sku_raw']]
    shvrows.append([v['variant_key'],h,sh_map[h]['product']['title'],v['sku_raw'],join(str(o['name'])+' = '+str(o['value']) for o in v['option_tuple']),num(v['price_raw']),num(v['compare_at_price_raw']),v['currency_state'],num(v['grams_raw']),v['exported_weight_unit_raw'],v['weight_scope'],v['inventory_tracker_raw'],v['inventory_policy_raw'],v['inventory_quantity'],v['inventory_quantity_state'],v['variant_image_raw'],join(sids),join(selected_sh[h]),shstatuses[h],srow,v['id_state'],v['product_status_raw']])
for idx,r in enumerate(shmedia):
    h=r['handle'];srow=r['source_row']['logical_row_including_header']
    allgallery.append(['SH:'+h+':'+str(srow),'Shopify',h,sh_map[h]['product']['title'],num(r['image_position_raw']),'Image' if r['image_src'] else '', 'See retained gallery review; no new role approval','Source gallery occurrence', '',bool(r['variant_image_raw']),r['image_src'],srow,'Explicit Variant Image field is blank in this export; product gallery is not a variant image assignment.'])
sht=tab('Shopify','All Shopify products in the local export',['Shopify handle','Source title','Catalogue association','Variant count','Source SKUs','Selected catalogue IDs','Selected catalogue options','Related catalogue IDs','Related options','Squarespace SKU counterparts','Cross-platform status','Source product type','Source category','Source vendor','Source status','Published flag','Gallery rows','First image','Raw export row','Source description','Relative product path','Source qualification'],shrows,
        '136 products, including 38 in the previous wall-sculpture subset and 98 other products. Historical prices and stock settings stay separate.',shpath,widths={0:48,1:43,2:36,6:55,8:55,19:100,21:85})
for i,r in enumerate(shrows):
    media=sh_map[r[0]]['full_product_gallery'];addlink(sht,i,17,url(media[0].get('image_src') if media else '', 'Image'));addlink(sht,i,18,idslink('Shopify raw',str(r[18]),str(r[18])))
shvt=tab('Shopify variants','All Shopify variant rows',['Local variant key','Shopify handle','Source title','Raw SKU','Option tuple','Source price','Compare-at price','Currency state','Source grams','Exported weight unit','Weight qualification','Inventory tracker','Inventory policy','Inventory quantity','Inventory quantity state','Explicit variant image','Squarespace variant counterparts','Selected catalogue IDs','Catalogue scope','Raw export row','Numeric ID state','Source product status'],shvrows,
         '160 variant rows. Local row keys are identifiers for these export rows, not native Shopify numeric IDs.',shpath,widths={0:55,1:43,2:42,4:68,10:75,16:50})
for i,r in enumerate(shvrows):addlink(shvt,i,1,idslink('Shopify',r[1]));addlink(shvt,i,19,idslink('Shopify raw',str(r[19]),str(r[19])))

dtrows=[]
for im in sorted(images,key=lambda x:(x.get('family') or '',x.get('path') or '')):
    fid=im['file_id'];scope=im['inventory_status'];role=im.get('visual_role') or 'Not reviewed';edges=by_file[fid];pids=sorted({x['product_id'] for x in edges});sel=selected_refs[fid]
    if scope!='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED':status='Historical / supplementary reference'
    elif sel:status='Matched selected reference'
    elif role in ['group_context','detail','rear','installation']:status='Context only'
    elif not pids:status='Unmatched image'
    else:status='Related candidate; exact role qualified'
    mapping='No product-option association' if fid in unscoped_ids else 'Recorded association' if pids else 'No current product-option association'
    md=im.get('metadata') or {};vr=im.get('visual_role_evidence') or {}
    dtrows.append([fid,im['name'],status,im.get('family'),role,mapping,scope,join(sel),names(sel),join(pids),names(pids),join(source_image_ids[fid]),im.get('folder_id'),'Image' if im.get('image_url') else '', 'Folder' if im.get('folder_url') else '',im.get('path'),md.get('size',(im.get('saved_asset_metadata') or {}).get('bytes')),md.get('modified_time'),md.get('client_modified'),md.get('content_hash') or (im.get('current_native_evidence') or {}).get('content_hash',''),vr.get('component_finish_qualification',vr.get('review_note','')),join(vr.get('uncertainty_flags',[]))])
    if fid in unscoped_ids:reviewrows.append(['DB:'+fid,'Dropbox',fid,im['name'],status+'; no product association',vr.get('review_note') or 'Retained in family inventory. Not automatically an extra sculpture or a deletion candidate.','Dropbox files',fid])
dt=tab('Dropbox files','All indexed Dropbox files and retained references',['Dropbox file ID','Filename','Record status','Family','Visual role','Product association','Inventory state','Selected by product IDs','Selected products','Related product IDs','Related products','Source-gallery offer refs','Actual parent folder ID','Image','Folder','Recorded path','Bytes','Server modified UTC text','Client modified UTC text','Content hash if available','Visual qualification','Uncertainty flags'],dtrows,
       '6,360 current Wall Sculptures files plus 330 retained supplementary/historical references. All 625 files without an option association are retained.',dbpath,widths={1:58,2:35,5:34,6:55,8:50,10:65,15:100,20:110})
for i,r in enumerate(dtrows):
    im=image_map[r[0]];addlink(dt,i,13,url(im.get('image_url'),'Image'));addlink(dt,i,14,url(im.get('folder_url'),'Folder'))

folderrows=[]
for f in sorted(folders,key=lambda x:x.get('path','')):
    fid=f['file_id'];members=[x for x in images if x.get('folder_id')==fid and x['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED']
    pids=sorted({a['product_id'] for x in members for a in by_file[x['file_id']]})
    folderrows.append([fid,f['name'],f.get('family',''),f.get('parent_id'),len(members),sum(x['file_id'] in unscoped_ids for x in members),join(pids),names(pids),'Folder',f.get('path'),f.get('modified_time'),'Current folder in 24 October 2026 scoped snapshot; folder membership does not prove an exact product.'])
ft=tab('Dropbox folders','All current scoped Dropbox folders',['Folder ID','Folder name','Family','Parent ID','Direct current files','Files without option association','Related product IDs','Related products','Folder','Recorded path','Server modified UTC text','Qualification'],folderrows,
       '442 folders including the Wall Sculptures root. Complete saved scope; no new search outside BOLDSTONE MASTER.',nativepath,widths={1:65,7:70,9:115,11:100})
fm={x['file_id']:x for x in folders}
for i,r in enumerate(folderrows):addlink(ft,i,8,url(fm[r[0]].get('folder_url'),'Folder'))

imgrows=[]
for (pid,fid), edges in sorted(pairs.items()):
    im=image_map.get(fid,{})
    imgrows.append([pid+' | '+fid,pid,products[pid]['name'],fid,im.get('name',''),im.get('visual_role',''),join(a['association_status'] for a in edges),join(a['intended_use'] for a in edges),join(a['association_id'] for a in edges),len(edges),im.get('inventory_status','NOT_IN_CURRENT_MAP'),'Retained qualified association; not an exact selling-variant or physical-specimen certificate.'])
it=tab('Image associations','Every product-image association',['Product / file key','Product ID','Product / option','Dropbox file ID','Filename','Visual role','Recorded statuses','Intended uses','Source association IDs','Evidence edge count','Inventory state','Qualification'],imgrows,
       '10,847 distinct product-file pairs retaining all 19,494 association IDs and their statuses. Use the file ID link for image and folder access.',dbpath,widths={0:55,2:43,4:60,6:65,7:65,8:75,11:90})
for i,r in enumerate(imgrows):addlink(it,i,1,idslink('Products',r[1]));addlink(it,i,3,idslink('Dropbox files',r[3]) if r[3] in image_map else None)

alinks=[]
for a in audit:
    alinks.append([a['product_id']+' | '+a['offer_ref'],a['product_id'],a['name'],a['offer_ref'],a.get('source_id',''),a.get('source_sku',''),bool(a.get('selected_for_individual_listing')),a.get('retained_relationship'),a.get('recorded_sale_unit_state'),a.get('design_scope'),a.get('finish_scope'),a.get('size_comparison'),a.get('build_scope'),a.get('local_review_result'),json.dumps(a.get('retained_source_qualifications',[]),ensure_ascii=False)])
latest_source_keys={(r[1],r[3]) for r in alinks}
offers_by_ref={x['offer_ref']:x['source_offer'] for x in reg['source_offer_edges']}
history_source_edges=[]
for pid,offer,relationship in sorted(prior_source_edges):
    if (pid,offer) in latest_source_keys:continue
    o=offers_by_ref[offer]
    history_source_edges.append((pid,offer))
    alinks.append([pid+' | '+offer,pid,products[pid]['name'],offer,o.get('sq_id',''),o.get('sku',''),False,
                   'Historical component context; not selected in current individual plan',o.get('sale_unit_state'),
                   'Earlier component-level association only','Finish applicability remains qualified',
                   'Size applicability remains qualified','Build applicability remains qualified',
                   'Retained from the earlier source-link table; absent from the latest individual matching audit. No exact match is reinstated.',relationship])
assert len(history_source_edges)==6
at=tab('Catalogue source links','All retained catalogue-to-source associations',['Association key','Product ID','Product / option','Offer ref','Source product ID','Source SKU','Selected in individual plan','Retained relationship','Source sale unit','Design evidence','Finish evidence','Size comparison','Build evidence','Review result','Source qualifications'],alinks,
       '262 latest reviewed source edges plus six older component links retained as history. Family, arrangement and source-image relationships remain distinct from selected individual records.',auditpath,widths={2:46,7:75,8:55,9:65,13:90,14:95})
for i,r in enumerate(alinks):addlink(at,i,1,idslink('Products',r[1]));addlink(at,i,4,idslink('Squarespace',r[4]) if r[4] in ssproducts else None)
pairtab=tab('Platform SKU pairs','Full-export raw-SKU crosswalk',['Raw SKU','Pairing status','Squarespace product ID','Squarespace variant ID','Squarespace title','Shopify handle','Shopify local variant key','Shopify title','Match qualification','Squarespace raw row','Shopify raw row'],pair_rows,
            'Uses exact non-empty raw SKU values across the complete exports. SKU equality is source-row evidence and does not approve design, finish, size or quantity.',crosspath,widths={4:52,7:52,8:100})
for i,r in enumerate(pair_rows):addlink(pairtab,i,2,idslink('Squarespace',r[2]));addlink(pairtab,i,5,idslink('Shopify',r[5]))
galt=tab('Platform images','All exported product-gallery occurrences',['Gallery occurrence ID','Platform','Source product key','Source title','Gallery position','Image','Visual role review','Photo correspondence status','Supported Dropbox file IDs','Explicit variant image present','Exported image URL','Raw export row','Qualification'],allgallery,
        'Includes all gallery URLs in the 208-product Squarespace export and all 416 Shopify media-row occurrences. Source-gallery membership is not exact variant assignment.',None,widths={2:48,3:48,6:50,7:66,8:58,10:110,12:110})
for i,r in enumerate(allgallery):addlink(galt,i,5,url(r[10],'Image'));addlink(galt,i,2,idslink('Squarespace' if r[1]=='Squarespace' else 'Shopify',r[2]))

arows=[]
for a in reg['aliases']:
    arows.append([a['alias_id'],a['source'],join(a['targets']),a['relationship'],a.get('reason',''),a.get('evidence',''),a.get('individual_count_increment',0),'Recorded alias relationship; not a new physical-stock count.'])
for p in reg['options']:
    if p['product_id'] not in active_ids:arows.append(['RETIRED:'+p['product_id'],p['name'],p['product_id'],'Retired catalogue option',json.dumps(p.get('lifecycle',p.get('retirement',{})),ensure_ascii=False),'Retained canonical history',0,'Excluded from active188; original fields retained in Specifications.'])
arows.append(['FFL1-DUPLICATE-AVOIDANCE','Frozen Fish FFL1 White','BSI-04D6E8690F30','Duplicate avoidance; same relief design','Retain legacy row without creating a second indistinguishable White SKU. Prices and source specifications are not merged.','Owner confirmed same relief design as FFS2',0,'Same design does not certify the same physical cast.'])
tab('Aliases and history','Aliases, retired options and duplicate avoidance',['Record ID','Alias / historical name','Targets','Relationship','Reason','Evidence','Individual count increment','Qualification'],arows,
    'Aliases are retained relationships. The current native content-hash duplicate report contains no exact-byte duplicate groups; nothing is deleted.',regpath,widths={1:55,2:52,3:50,4:110,5:60,7:100})
arrrows=[]
for x in reg['source_sets']:
    o=x['source_offer'];arrrows.append([x['offer_ref'],'Source set / proposed composition',o['title'],o.get('sale_unit_state'),o.get('native_parts'),o.get('proposed_bom_pieces'),join(m.get('source_component_id') for m in x.get('members',[])),json.dumps(x.get('members',[]),ensure_ascii=False),o.get('source_url',''),o.get('cautions',''),'No individual price or weight allocation inferred from a set.'])
for x in reg['arrangement_context_references']:
    arrrows.append([x['reference_id'],'Arrangement / context',x['name'],x.get('sale_unit_status'),None,None,join(x.get('confirmed_member_option_ids',[])),json.dumps(x.get('specifications',[]),ensure_ascii=False),x.get('image_url',''),x.get('notes',''),x.get('component_identification','')])
art=tab('Sets and context','Retained source sets and context groups',['Reference ID','Reference type','Name','Sale-unit state','Source part count','Proposed part count','Member IDs','Member details / source claims','Source / image','Notes','Qualification'],arrrows,
        '28 source sets/proposed compositions and 27 arrangement/context references. Groups remain context unless membership is separately confirmed.',regpath,widths={2:52,3:65,7:110,9:90,10:90})
for i,r in enumerate(arrrows):
    if r[8].startswith('https://'):addlink(art,i,8,url(r[8],'Open reference'))

rt=tab('Unmatched and qualified','Records without an exact individual assignment',['Review key','Source','Source ID','Name / filename','Status','Reason / retained qualification','Inventory sheet','Inventory record'],reviewrows,
       'Source-record coverage, not a count of missing sculptures. Includes context photos, outside-review platform products and exact-match exceptions.',None,widths={0:55,2:48,3:62,4:53,5:110})
for i,r in enumerate(reviewrows):addlink(rt,i,7,idslink(r[6],r[7],'Open source record'))

# The original export cells are retained, including blanks on continuation rows.
rawss=tab('Squarespace raw','Original Squarespace Physical export',['CSV record']+ssheaders,[[str(i)]+[r[k] for k in ssheaders] for i,r in enumerate(ssraw,2)],
          'Original cells preserved as exported text. Blank product IDs on continuation rows remain blank here. Use normalized tabs for inherited product fields.',sspath)
rawsh=tab('Shopify raw','Original Shopify export',['CSV record']+shheaders,[[str(i)]+[r[k] for k in shheaders] for i,r in enumerate(shraw,2)],
          'Original 416 rows and 95 export columns preserved. Prices and stock settings describe the historical export, not live inventory.',shpath)

# Put sources after the reader views; retain one authoritative instance of each source inventory.
order=['Overview','Products','Unmatched and qualified','Specifications','Components','Catalogue source links','Reviewed offers','Platform SKU pairs','Aliases and history','Sets and context','Squarespace','Squarespace variants','Shopify','Shopify variants','Dropbox files','Dropbox folders','Image associations','Platform images','Squarespace raw','Shopify raw']
tabs.sort(key=lambda t:order.index(t['name']))
byname={t['name']:t for t in tabs}
counts={'active_options':188,'retained_specification_fields':len(specrows),'squarespace_products':208,'squarespace_variants':376,'reviewed_squarespace_products':80,'additional_squarespace_products':128,'shopify_products':136,'shopify_variants':160,'shopify_export_rows':416,'shopify_wall_subset':38,'additional_shopify_products':98,'current_wall_files':6360,'retained_supplementary_files':330,'current_folders_including_root':442,'all_file_records':6690,'files_without_option_association':625,'individual_views_without_option_association':73,'image_pairs':len(imgrows),'association_evidence_edges':len(associations),'catalogue_source_links':len(alinks),'full_export_SKU_pairs':len(pair_rows),'platform_image_occurrences':len(allgallery),'review_rows':len(reviewrows)}
overview_specs=[
 ('Active sculpture options','Products','Complete working fields; estimates remain labelled.'),
 ('Squarespace products','Squarespace','208 Physical-export products;80 previously reviewed,128 additional.'),
 ('Squarespace variants','Squarespace variants','All376 variants, including144 Wall Circle options.'),
 ('Shopify products','Shopify','All136 products;38 wall-sculpture subset and98 other products.'),
 ('Shopify variants','Shopify variants','All160 variant rows; numeric Shopify IDs absent from export.'),
 ('Dropbox file records','Dropbox files','6,360 current scoped files and330 retained supplementary/history references.'),
 ('Current Dropbox folders','Dropbox folders','442 folders including the Wall Sculptures root.'),
 ('Product-image pairs','Image associations','10,847 pairs retaining19,494 evidence-edge IDs.'),
 ('Catalogue source associations','Catalogue source links','262 latest reviewed associations and six older component links retained as history.'),
 ('Full-export raw SKU pairs','Platform SKU pairs','Source-row matches only; not new individual identity approvals.'),
 ('Records without exact individual assignment','Unmatched and qualified','Mixed sources and context. This is not a missing-sculpture count.')]
for label,sheet,note in overview_specs:
    ri=len(overview['rows']);overview['rows'].append([label,None,note]);overview['formulas'][f'B{ri+7}']=f"=COUNTA('{sheet}'!A7:A{len(byname[sheet]['rows'])+6})"
    addlink(overview,ri,0,{'sheet':sheet,'cell':'A1','label':label})
overview['rows'] += [
 ['Current Dropbox files without option links',None,'625 images, including73 individual views. Context images are retained.'],
 ['Current individual views without option links',None,'Review for existing products, duplicate views or additional pieces.'],
 ['Existing individual listing treatments',None,'47 source-supported reuse/copy updates.'],
 ['Provisional Wall Circle pattern treatments',None,'Four mappings remain qualified.'],
 ['Native-listing exceptions',None,'FFL1 duplicate avoidance and MCP1 exact binding.']]
overview['formulas'].update({
 'B18':f'=COUNTIFS(\'Dropbox files\'!F7:F6696,"No product-option association")',
 'B19':f'=COUNTIFS(\'Dropbox files\'!F7:F6696,"No product-option association",\'Dropbox files\'!E7:E6696,"individual")',
 'B20':'=COUNTIFS(Products!C7:C194,"Matched existing individual")+COUNTIFS(Products!C7:C194,"Matched; copy update proposed")',
 'B21':'=COUNTIFS(Products!C7:C194,"Provisional pattern match")',
 'B22':'=COUNTIFS(Products!C7:C194,"Duplicate avoidance; retain history")+COUNTIFS(Products!C7:C194,"Unmatched exact listing")'})
for i,sheet in [(11,'Dropbox files'),(12,'Dropbox files'),(13,'Products'),(14,'Products'),(15,'Products')]:addlink(overview,i,0,{'sheet':sheet,'cell':'A1','label':overview['rows'][i][0]})
overview['widths']={0:61,1:15,2:100}

guidance=[
 ['Scope','Dropbox is the saved BOLDSTONE MASTER / Products / 01 Wall Sculptures snapshot, plus retained references. It is not a fresh whole-account census.'],
 ['Squarespace source','Full Physical-product export captured24 October2026:208products/376variants. Digital/service products or later account changes are not established by this file.'],
 ['Shopify source','All136products/160variants from the local export; dataset corroborated by a workbook named30.08.2024. Copy modification time is not an export date.'],
 ['Matched individual record','Existing local source was selected for an individual product. Source claim, physical verification and current live variant are separate states.'],
 ['Provisional pattern match','Working Wall Circle pattern association; exact cast/photo/current-account binding remains qualified.'],
 ['Related family / arrangement only','Source is associated with the component family or arrangement. The source sale quantity, finish, build and specimen are not promoted to exact individual facts. Six links absent from the latest audit are retained as historical context only.'],
 ['Context only','Group, detail, rear or installation image. A context-only image can be useful without representing an additional sellable sculpture.'],
 ['Unmatched image','No existing product-option edge for an individual or uncertain image. Image count is not a count of missing sculptures.'],
 ['Outside reviewed sculpture scope','Source product is preserved in this workbook but was not part of the reviewed188-option register. No new sculpture identity is inferred.'],
 ['Duplicate / alias policy','Explicit design aliases and FFL1 duplicate avoidance are retained. No new duplicate claim follows from a similar name or photo. Current content-hash report contains zero exact-byte groups.'],
 ['Specifications and prices','Working values remain qualified. Raw source claims, source prices, stock settings and set quantities are preserved separately. New material and face values remain proposals/estimates.'],
 ['Images and hyperlinks','Click Image or Folder in Products / Dropbox files, or follow an internal source-record link. Historical links are retained with their recorded availability state.'],
 ['Raw exports','Original fields are stored intact in Squarespace raw and Shopify raw, including HTML and continuation blanks. Expand the formula bar to read long raw text.'],
 ['What this workbook completes','Consolidation of all the saved source records listed here. It does not certify every depicted sculpture is identified, and it performs no shop import.'],
 ['Photography deferrals','22 installation and one series-image gap remain held under the owner instructions. No photograph requirement is reopened.']]
for row in manifest:guidance.append(['Source: '+Path(row['path']).name,row['path']+'\nSHA256 '+row['sha256']])
guide=tab('Guide and sources','Definitions, source clocks and provenance',['Topic','Definition / source'],guidance,
          'Filtering statuses never removes a source record. Stable IDs and export row numbers are retained for tracing.',None,widths={0:50,1:145})

# Readable spacing for authored summary/guide prose; original source text is untouched.
for t in [overview,guide]:
    for row in t['rows']:
        for j,v in enumerate(row):
            if isinstance(v,str) and not v.startswith('/'):
                v=re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', v)
                v=re.sub(r'(?<=\d)(?=[A-Za-z])', ' ', v)
                v=re.sub(r';(?=[A-Za-z\d])', '; ',v)
                v=re.sub(r',(?=[A-Za-z])', ', ',v)
                v=v.replace('FFL 1','FFL1').replace('MCP 1','MCP1')
                row[j]=v

# Resolve stable-key internal hyperlinks after all inventories have been built.
keyrows={t['name']:{str(r[0]):i+7 for i,r in enumerate(t['rows'])} for t in tabs}
for t in tabs:
    for ij,link in t['links'].items():
        if 'sheet' in link:
            cell=link.get('cell') or 'A'+str(keyrows[link['sheet']][str(link['key'])])
            link['target']="#'"+link['sheet'].replace("'","''")+"'!"+cell
        else:link['target']=link['url']
        i,j=map(int,ij.split(','));t['rows'][i][j]=link['label']

long=[]
for t in tabs:
    for i,row in enumerate(t['rows']):
        assert len(row)==len(t['columns']),(t['name'],i,len(row),len(t['columns']))
        for j,v in enumerate(row):
            if isinstance(v,str) and len(v)>32767:long.append((t['name'],i,j,len(v)))
assert not long,('Excel cell length limit',long)
assert {r[0] for r in prows}==active_ids
assert len(specrows)==1134 and len(alinks)==268
assert sum(r[6]=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED' for r in dtrows)==6360
assert sum(r[5]=='No product-option association' for r in dtrows)==625
assert sum(r[5]=='No product-option association' and r[4]=='individual' for r in dtrows)==73
assert sum(r[9] for r in imgrows)==19494
for row in manifest:assert sha(Path(row['path']))==row['sha256'],row['path']
book={'title':'Boldstone consolidated product and source register','as_of_utc':datetime.now(timezone.utc).isoformat(),'output':str(OUT/'Boldstone_All_Sources_Consolidated_2026-10-25.xlsx'),'tabs':tabs,'counts':counts}
write(W/'workbook-data.json',book)
write(W/'preparation-validation.json',{'status':'PASS_COMPLETE_SOURCE_PREPARATION','counts':counts,'squarespace_raw_rows':376,'shopify_raw_rows':416,'complete_raw_source_columns_preserved':True,'source_manifest_unchanged':True,'new_identity_approvals':0,'canonical_or_platform_writes':0,'sheet_rows':{t['name']:len(t['rows']) for t in tabs}})
planfile=read(W/'WORK_PLAN.json');planfile['steps'][0]['status']='complete';planfile['steps'][1]['status']='complete';planfile['steps'][2]['status']='in_progress';write(W/'WORK_PLAN.json',planfile)
print(json.dumps({'counts':counts,'tabs':{t['name']:len(t['rows']) for t in tabs},'data_bytes':(W/'workbook-data.json').stat().st_size},indent=2))
