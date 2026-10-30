import hashlib,json,re,sqlite3,html
from collections import defaultdict,Counter
from datetime import datetime,timezone
from html.parser import HTMLParser
from pathlib import Path

project=Path(__file__).resolve().parents[1]
ev=project/'evidence'
source=json.loads((ev/'catalogue_source_tables_2026-10-15.json').read_text())
inventory=json.loads((ev/'wall_inventory_2026-10-16.json').read_text())
reviews=json.loads((ev/'image_review_curated_review.json').read_text())
batch=json.loads((project/'reviews'/'batch01.json').read_text())
media=json.loads((ev/'batch01_media.json').read_text())
batch02=json.loads((project/'reviews'/'batch02.json').read_text())
batch02_groups={r['leaf_id']:r for r in batch02['groups']}
batch02_roles={r['file_id']:r['role'] for r in batch02['asset_roles']}
additional_media=json.loads((ev/'additional_source_receipts.json').read_text())
entries=inventory['entries'];root=inventory['root_path']+'/'
assert inventory['complete'] and len({r['file_id'] for r in entries})==len(entries)
def rel(r):return r['path'][len(root):]
def key(prefix,value):return prefix+hashlib.sha256(value.encode()).hexdigest()[:12].upper()
def split_ids(value):return [x.strip() for x in (value or '').split(';') if x.strip()]
folders=[r for r in entries if r['object_type']=='folder']
files=[r for r in entries if r['object_type']=='file']
family_folders=sorted([r for r in folders if '/' not in rel(r)],key=lambda r:r['name'].casefold())
leaves=sorted([r for r in folders if rel(r).count('/')==1],key=lambda r:rel(r).casefold())
by_path={r['path'].casefold():r for r in entries};by_id={r['file_id']:r for r in entries}
family_by_name={r['name'].casefold():r for r in family_folders}
group_id={r['file_id']:key('BSG-',r['file_id']) for r in leaves}
group_by_path={r['path'].casefold():r for r in leaves}
files_by_group=defaultdict(list)
for r in files:
    parent=group_by_path.get(r['path'].rsplit('/',1)[0].casefold())
    assert parent,('Asset has no unique current leaf',r['file_id'],r['path'])
    files_by_group[parent['file_id']].append(r)
assert len(family_folders)==63 and len(leaves)==347 and len(files)==6656

plans={r['target_relative'].casefold():r for r in source['DB Groups']}
routes={r['id']:r for r in source['DB Source Mappings']}
family_source={r['Family'].casefold():r for r in source['DB Families']}

sscols=list(source['SS Wall Products'][0]);sscols=sscols[sscols.index('Product ID [Non Editable]'):]
shcols=list(source['SH Wall Products'][0]);shcols=shcols[shcols.index('Handle'):shcols.index('Status')+1]
oldcols=list(source['SH Older Wall'][0]);oldcols=oldcols[oldcols.index('Handle'):oldcols.index('Status')+1]
offers=[];offer_by_key={};native=[]
def offer(p,platform,source_sheet,source_row,record_key,sku,title,product_id='',handle='',related_sq=''):
    item=dict(offer_key=record_key,platform=platform,title=title,sku=sku,product_id=product_id,handle=handle,source_sheet=source_sheet,source_row=source_row,related_sq=related_sq,raw=p)
    offers.append(item);offer_by_key[record_key]=item
for p in source['SS Wall Products']:
    offer(p,'Squarespace','SS Wall Products',p['_row'],'SQ:'+p['Product ID [Non Editable]'],p['SKU'],p['Title'],p['Product ID [Non Editable]'])
for p in source['SH Wall Products']:
    offer(p,'Shopify main','SH Wall Products',p['_row'],'SH:'+p['Handle'],p['Variant SKU'],p['Title'],handle=p['Handle'],related_sq=p['Squarespace product ID'])
for sheet,prefix,platform in [('SH Older Wall','SH-OLDER:','Shopify older'),('SH Seed Wall','SH-SEED:','Shopify seed')]:
    for p in source[sheet]:offer(p,platform,sheet,p['_row'],prefix+p['Handle'],p['Variant SKU'],p['Title'],handle=p['Handle'],related_sq=p['Matched/candidate Squarespace ID'])
for p in source['SS Wall Variants']:
    native.append(dict(row_key='SQROW:'+p['CSV data record'],platform='Squarespace',offer_key='SQ:'+p['Resolved parent product ID'],source_sheet='SS Wall Variants',source_row=p['_row'],native_csv_record=p['CSV data record'],parent_id=p['Resolved parent product ID'],variant_id=p['Variant ID [Non Editable]'],values={k:p[k] for k in sscols}))
for p in source['SH Source Rows']:
    native.append(dict(row_key='SHROW:'+p['CSV record'],platform='Shopify main',offer_key='SH:'+p['Handle'],source_sheet='SH Source Rows',source_row=p['_row'],native_csv_record=p['CSV record'],parent_id=p['Handle'],variant_id='',values={k:p[k] for k in shcols}))
for sheet,prefix,platform in [('SH Older Wall','SH-OLDER:','Shopify older'),('SH Seed Wall','SH-SEED:','Shopify seed')]:
    for p in source[sheet]:native.append(dict(row_key=prefix+p['Subset record'],platform=platform,offer_key=prefix+p['Handle'],source_sheet=sheet,source_row=p['_row'],native_csv_record=p['Subset record'],parent_id=p['Handle'],variant_id='',values={k:p[k] for k in oldcols}))

links=[]
def link(offerkey,family,basis,scope,leaf_id='',asset_id='',detail='',accepted=False):
    f=family_by_name.get(family.casefold());assert f,('Unknown family',family)
    links.append(dict(link_id=key('LINK-',f'{offerkey}|{f["file_id"]}|{leaf_id}|{asset_id}|{basis}'),offer_key=offerkey,family=f['name'],family_id=f['file_id'],group_id=group_id.get(leaf_id,''),leaf_id=leaf_id,asset_id=asset_id,basis=basis,scope=scope,accepted_image=accepted,image_correspondence=accepted,detail=detail))
for r in source['Matched Overview']:
    offerkey='SQ:'+r['Squarespace product ID']
    for family in split_ids(r['Dropbox family / families']):
        link(offerkey,family,'PRESERVED FAMILY LINK','Historical family only; individual member and finish not certified',detail=r['Evidence / cautions'])
for r in reviews:
    offerkey='SH:frozen-fish' if r['source_sheet']=='Unmatched Shopify' else 'SQ:'+r['pid']
    src=r.get('source');asset=by_id.get(src['id']) if src else None
    assert not src or asset,('Previously accepted source is outside current census',r['pid'])
    leaf=group_by_path[asset['path'].rsplit('/',1)[0].casefold()] if asset else None
    link(offerkey,r['family'],r['state'].upper(),'Source image only; measure and offer-scope questions remain' if src else 'Existing family hypothesis; exact member unresolved',leaf['file_id'] if leaf else '',src['id'] if src else '',r['notes'],r['state'] in ['Confirmed image link','Historical draft image link'])
extra_review_file=ev/'established_image_decisions.json'
extra_reviews=json.loads(extra_review_file.read_text()) if extra_review_file.exists() else []
for r in extra_reviews:
    asset=by_id[r['asset_id']];leaf=group_by_path[asset['path'].rsplit('/',1)[0].casefold()]
    link('SQ:'+r['pid'],rel(asset).split('/')[0],r['basis'],r['scope'],leaf['file_id'],asset['file_id'],r['detail'],r['accepted_image'])
    links[-1]['image_correspondence']=r.get('image_correspondence',r['accepted_image'])
# Batch 02 joins reviewed design/finish groups to the exact native offer. It does
# not extend those specifications to other finishes or mixed workshop photographs.
for sculpture in batch02['sculptures']:
    for offerkey in sculpture['offer_keys']:
        for leaf_id in sculpture['leaf_ids']:
            if any(l['offer_key']==offerkey and l['leaf_id']==leaf_id and l['accepted_image'] for l in links):continue
            asset=files_by_group[leaf_id][0]
            link(offerkey,'Acanthus','REVIEWED DESIGN AND FINISH CORRESPONDENCE','Specific pictured design / finish; source dimensions and material are claims, not physical measurements',leaf_id,asset['file_id'],'Batch 02: all 76 family files viewed. '+sculpture['title']+' / '+sculpture['finish'],True)
            links[-1]['image_correspondence']=False
# The supplied exact-SKU crosswalk links Shopify to the same native Squarespace offer history.
# It does not upgrade the historical family evidence into per-member physical verification.
for o in offers:
    if o['platform']=='Shopify main' and o['related_sq']:
        for r in [x for x in links if x['offer_key']=='SQ:'+o['related_sq']]:
            link(o['offer_key'],r['family'],'EXACT SKU CROSSWALK / '+r['basis'],r['scope'],r['leaf_id'],r['asset_id'],r['detail'],r['accepted_image'])
    elif o['platform'] in ['Shopify older','Shopify seed'] and o['related_sq']:
        for r in [x for x in links if x['offer_key']=='SQ:'+o['related_sq']]:link(o['offer_key'],r['family'],'HISTORICAL LINEAGE CANDIDATE','Older/seed version; do not overwrite later facts',detail=o['raw'].get('Lineage state',''))
unique_links={}
for row in links:
    if row['link_id'] in unique_links:assert unique_links[row['link_id']]==row,'Conflicting relationship key'
    else:unique_links[row['link_id']]=row
links=list(unique_links.values())

class Plain(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_endtag(self,tag):
        if tag in ['p','li','div','h1','h2','h3']:self.parts.append('\n')
def plain(value):
    p=Plain();p.feed(value or '');return '\n'.join(re.sub(r'\s+',' ',x).strip() for x in ''.join(p.parts).splitlines() if x.strip())
categories=[('Dimensions',r'\b(?:cm|mm|metre|centimet|dimension|length|width|height|diameter|depth)\b|\d\s*[×x]\s*\d'),('Weight',r'\b(?:kg|kilogram|weight|grams)\b'),('Material',r'\b(?:jesmonite|gypsum|cement|plaster|marble|resin|composite|steel|stone|sand|material)\b'),('Finish',r'\b(?:finish|verdigris|rust|gold|silver|bronze|copper|white|colour|color|patina|surface effect|terracotta|ral)\b'),('Mounting',r'\b(?:hang|hanging|fixing|cleat|mount|mounting|framework|recessed)\b'),('Suitability',r'\b(?:interior|outdoor|indoor|exterior|garden|suitable|courtyard)\b'),('Production',r'\b(?:weeks|lead time|made to order|cast to order|england|bath|production)\b'),('Options',r'\b(?:custom|different sizes|surface effects|companion|option|led|lighting)\b'),('Composition',r'\b(?:part|parts|two|three|four|five|pair|set|diptych|triptych|component)\b')]
facts=[]
def fact(o,field,value,unit,scope,status,locator):
    facts.append(dict(fact_id=key('SPEC-',f'{o["offer_key"]}|{field}|{value}|{locator}'),offer_key=o['offer_key'],platform=o['platform'],title=o['title'],sku=o['sku'],field=field,value=value,unit=unit,scope=scope,status=status,source_sheet=o['source_sheet'],source_row=o['source_row'],locator=locator))
for o in offers:
    p=o['raw'];body=p.get('Description',p.get('Body (HTML)',''))
    for index,line in enumerate(plain(body).splitlines(),1):
        # Sentence-level claims remain source statements, not automatically accepted design specifications.
        for n,sentence in enumerate(re.split(r'(?<=[.!?])\s+(?=[A-Z])',line),1):
            tags=[name for name,pattern in categories if re.search(pattern,sentence,re.I)]
            if tags:fact(o,' / '.join(tags),sentence,'As explicitly written in text','This native offer; individual Dropbox applicability requires the recorded link scope','SOURCE CLAIM',f'{o["source_sheet"]}!row{o["source_row"]}/{"Description" if o["platform"]=="Squarespace" else "Body (HTML)"}/paragraph{index}/sentence{n}')
    if o['platform']=='Squarespace':
        fields=[('Price','Currency unencoded'),('Sale Price','Currency unencoded'),('On Sale',''),('Stock',''),('Weight','Unit unencoded'),('Length','Unit unencoded'),('Width','Unit unencoded'),('Height','Unit unencoded'),('Visible','')]
    else:fields=[('Variant Price','Currency unencoded'),('Variant Compare At Price','Currency unencoded'),('Variant Grams','g'),('Variant Weight Unit','Export display unit'),('Variant Inventory Qty','units, if populated'),('Variant Inventory Policy',''),('Variant Inventory Tracker',''),('Published',''),('Status',''),('Cost per item','Currency unencoded')]
    for field,unit in fields:
        if p.get(field,'')!='':fact(o,field,p[field],unit,'Native exported field; zero or Unlimited does not establish a physical quantity or readiness','RAW SOURCE',f'{o["source_sheet"]}!row{o["source_row"]}/{field}')
for r in source['Historical Products']:
    o=offer_by_key.get('SH:'+r['Shopify handle'])
    if o:
        for field in ['Parts','Each component (cm)','Overall (cm)','Export weight (kg)','Finish stated in export','Custom options stated']:
            if r.get(field,'')!='':fact(o,'Prior extraction: '+field,r[field],'cm' if '(cm)' in field else 'kg' if '(kg)' in field else '', 'Preserved historical interpretation; verify against native description before adoption','HISTORICAL EXTRACTION',f'Historical Products!row{r["_row"]}/{field}')
first=offer_by_key['SQ:'+batch['squarespace_product_id']]
for spec in batch['specifications']:fact(first,'Batch 01: '+spec['field'],spec['value'],spec['unit'],spec['scope'],spec['status'],'reviews/batch01.json/specifications')
for sculpture in batch02['sculptures']:
    for offerkey in sculpture['offer_keys']:
        o=offer_by_key[offerkey]
        for field,unit in [('dimensions_cm','cm; source order'),('weight_kg','kg; approximate source claim'),('material',''),('fixing','')]:
            if sculpture[field]:fact(o,'Batch 02: '+field,sculpture[field],unit,'Specific reviewed design and finish '+sculpture['sculpture_id'],'SOURCE STATED; LIVE BODY AGREES; NOT PHYSICALLY MEASURED','reviews/batch02.json/sculptures/'+sculpture['sculpture_id'])
        fact(o,'Batch 02: Public price',sculpture['public_price'],sculpture['public_price_currency'],'Public native offer observed '+sculpture['public_observed'],'PUBLIC PAGE VERIFIED',sculpture['public_url'])

# All native non-empty values are preserved exactly. Long strings are split into ordered,
# losslessly reassemblable chunks for a readable Excel source table; the full schemas,
# including empty native fields, are retained in native_records.json.
numeric_fields={'Price','Sale Price','Weight','Length','Width','Height','Variant Grams','Variant Price','Variant Compare At Price','Variant Inventory Qty','Cost per item','Image Position'}
native_fields=[]
for r in native:
    for field,value in r['values'].items():
        if value=='':continue
        chunks=[value[i:i+850] for i in range(0,len(value),850)]
        for part,chunk in enumerate(chunks,1):
            numeric=float(value) if field in numeric_fields and re.fullmatch(r'-?\d+(?:\.\d+)?',value) and len(chunks)==1 else None
            unit='g' if field=='Variant Grams' else 'Unencoded; do not assume cm/kg' if r['platform']=='Squarespace' and field in ['Weight','Length','Width','Height'] else 'Unencoded currency' if 'Price' in field or field=='Cost per item' else ''
            native_fields.append(dict(row_key=r['row_key'],offer_key=r['offer_key'],platform=r['platform'],source_sheet=r['source_sheet'],source_row=r['source_row'],field=field,part=part,parts=len(chunks),raw_value=chunk,numeric_value=numeric,unit=unit))

by_family_link=defaultdict(list);by_group_link=defaultdict(list)
for l in links:
    by_family_link[l['family_id']].append(l)
    if l['leaf_id']:by_group_link[l['leaf_id']].append(l)
groups=[]
for leaf in leaves:
    relative=rel(leaf);fam=relative.split('/')[0];ff=family_by_name[fam.casefold()]
    route=routes.get(leaf['file_id']);planned=plans.get(relative.casefold()) or (plans.get(route['target_relative'].casefold()) if route else None)
    assert planned,('Unmapped current leaf',relative)
    refs=by_group_link[leaf['file_id']];accepted=[l for l in refs if l['accepted_image']]
    label=leaf['name'];kind='Context / in-situ media' if label.endswith(' In Situ') else 'Unclassified / mixed reference' if re.search(r'Unclassified|Mixed Sculptures|Sculptures With Sally',label,re.I) else 'Member / finish / arrangement label'
    related=[l for l in by_family_link[ff['file_id']] if l['offer_key'] not in {x['offer_key'] for x in refs}]
    reviewed02=batch02_groups.get(leaf['file_id'])
    design_id=batch['design_id'] if fam=='Abstract Cave Paintings' else reviewed02['design_id'] if reviewed02 else ''
    media_state='ALL 13 FAMILY FILES VIEWED' if fam=='Abstract Cave Paintings' else 'HAS SCOPED IMAGE LINK; FULL GROUP REVIEW PENDING' if accepted else 'IMAGE REVIEW PENDING'
    issues=[]
    if planned['review']=='True':issues.append('Preserved plan: provisional identity/storage classification')
    if planned['target_relative'].casefold()!=relative.casefold():issues.append('Current group label differs from preserved plan; stable folder ID retained')
    if kind=='Unclassified / mixed reference':issues.append('Do not treat this media collection as one sculpture')
    if fam=='Abstract Cave Paintings':issues+=batch['open_questions']
    if reviewed02:issues+=reviewed02['issues']
    groups.append(dict(group_id=group_id[leaf['file_id']],family=fam,group_name=label,kind=reviewed02['kind'] if reviewed02 else kind,design_id=design_id,sculpture_id=reviewed02['sculpture_id'] if reviewed02 else 'BSC-0001-V01' if fam=='Abstract Cave Paintings' else '',leaf_id=leaf['file_id'],family_id=ff['file_id'],path=leaf['path'],assets=len(files_by_group[leaf['file_id']]),confirmed_offers=sorted({l['offer_key'] for l in accepted}),candidate_offers=sorted({l['offer_key'] for l in refs if not l['accepted_image']}),family_reference_offers=sorted({l['offer_key'] for l in related}),media_state=reviewed02['media_state'] if reviewed02 else media_state,spec_state=reviewed02['spec_state'] if reviewed02 else 'SOURCE CLAIMS EXTRACTED; MATERIAL / WEIGHT / FIXING OPEN' if fam=='Abstract Cave Paintings' else 'OFFER SPECIFICATIONS AVAILABLE; APPLICABILITY REQUIRES REVIEW' if accepted else 'NO VERIFIED MEMBER SPECIFICATION ASSIGNMENT',plan_target=planned['target_relative'],plan_review=planned['review']=='True',issues='; '.join(issues),next_action=reviewed02['next_action'] if reviewed02 else 'Resolve the four Batch 01 questions' if fam=='Abstract Cave Paintings' else 'Review full group images, component identity, finishes and related offers; then adopt only applicable source facts'))

asset_rows=[]
old_ids={r['Dropbox file ID'] for r in source['DB Asset Records']}
prior_image_media=[r['source'] for r in reviews if r.get('source') and r['source'].get('current_download_verified')]
media_by_id={r['id']:r for r in prior_image_media+media+additional_media if r.get('hash_verified') or r.get('current_download_verified')}
scoped_review_ids={r['asset_id'] for r in extra_reviews}|{r['id'] for r in prior_image_media}
for r in sorted(files,key=lambda r:r['path'].casefold()):
    leaf=group_by_path[r['path'].rsplit('/',1)[0].casefold()];g=next(x for x in groups if x['leaf_id']==leaf['file_id'])
    review='NOT INDIVIDUALLY REVIEWED'
    if g['family']=='Abstract Cave Paintings':
        review='CONTEXT IMAGE; INSTALLATION PROVENANCE OPEN' if 'In Situ' in leaf['name'] else 'FULL / DETAIL / STUDIO REFERENCE VIEWED; NO SCALE MEASUREMENT'
    if r['file_id'] in batch02_roles:review=batch02_roles[r['file_id']]
    if review=='NOT INDIVIDUALLY REVIEWED' and r['file_id'] in scoped_review_ids:review='VIEWED FOR SPECIFIC NATIVE GALLERY COMPARISON; FULL GROUP REVIEW PENDING'
    asset_rows.append(dict(file_id=r['file_id'],group_id=g['group_id'],family=g['family'],group_name=g['group_name'],name=r['name'],path=r['path'],bytes=r.get('file',{}).get('size'),modified=r.get('modified_time',''),client_modified=r.get('client_modified',''),original_register=r['file_id'] in old_ids,review=review,binary_verified=r['file_id'] in media_by_id))

family_rows=[]
for index,f in enumerate(family_folders,1):
    gg=[g for g in groups if g['family_id']==f['file_id']];ll=by_family_link[f['file_id']]
    family_rows.append(dict(batch_id=f'CAT-FAM-{index:03d}',family=f['name'],family_id=f['file_id'],groups=len(gg),assets=sum(g['assets'] for g in gg),groups_with_image_links=sum(bool(g['confirmed_offers']) for g in gg),linked_offers=len({l['offer_key'] for l in ll}),provisional_groups=sum(g['plan_review'] for g in gg),review_state=batch['review_state'] if f['name']=='Abstract Cave Paintings' else batch02['review_state'] if f['name']=='Acanthus' else 'QUEUED',next_action='Resolve the four Batch 01 questions' if f['name']=='Abstract Cave Paintings' else 'Resolve six Batch 02 identity / source questions' if f['name']=='Acanthus' else 'Review member identity and applicable source specifications'))

issues=[]
for r in source['Product Issues']:
    issues.append(dict(issue_id=r['Issue ID'],scope=r['Scope'],priority=r['Priority'],description=r['Observed evidence'],action=r['Required decision / action'],status=r['Status'],offer_keys='; '.join('SQ:'+x for x in split_ids(r['Affected Squarespace product IDs'])),source=r['Source']))
for i,q in enumerate(batch['open_questions'],1):issues.append(dict(issue_id=f'B01-{i:02d}',scope='Icarus / Abstract Cave Paintings 1',priority='Review',description=q,action=q,status='OPEN',offer_keys=first['offer_key'],source='reviews/batch01.json'))
for i,q in enumerate(batch02['open_questions'],1):issues.append(dict(issue_id=f'B02-{i:02d}',scope='Acanthus',priority='Review',description=q,action=q,status='OPEN',offer_keys='; '.join(s['offer_keys'][0] for s in batch02['sculptures'] if s['offer_keys']),source='reviews/batch02.json'))
for i,r in enumerate([r for r in extra_reviews if r.get('caution')],1):issues.append(dict(issue_id=f'GALLERY-{i:02d}',scope=r['title'],priority='Review',description=r['detail'],action='Review gallery purpose, pictured composition and sale quantity before applying product specifications to every depicted member.',status='OPEN',offer_keys='SQ:'+r['pid'],source='established_image_decisions.json'))
issues.append(dict(issue_id='PLAN-LABEL-001',scope='Dune Ripple Spiral Copper and Partial Verdigris',priority='Review',description='Preserved plan calls this Waves Copper and Partial Verdigris. Current stable-ID folder label says Spiral Copper and Partial Verdigris.',action='Retain current name and exact stable ID; confirm member geometry during this family review.',status='OPEN',offer_keys='',source='Current inventory versus DB Groups plan'))

icarus_groups=[g for g in groups if g['family']=='Abstract Cave Paintings']
designs=[dict(design_id=batch['design_id'],title=batch['design_title'],description=batch['scope'])]+batch02['designs']
reviewed_sculptures=[dict(sculpture_id='BSC-0001-V01',design_id='BSC-0001',title=batch['design_title'],finish='Bath Stone AC730 as stated; white RAL 9010 framework',leaf_ids=[g['leaf_id'] for g in icarus_groups],group_ids=[g['group_id'] for g in icarus_groups],files=13,offer_keys=[first['offer_key']],dimensions_cm='Panel 200 × 100 × 5; framework 186 × 86 × 6.5',weight_kg='Approximately 60',material='Bath Stone Jesmonite AC730; gypsum / cementitious material-class conflict CAT-007',fixing='Stainless-steel French cleat; white RAL 9010 framework; optional concealed LED',native_price='3500.00',price_unit='Unencoded export currency',public_price=3500,public_price_currency='GBP',public_observed='2026-10-16',public_url='https://boldstonesculpture.com/buy/p/icarus-wall-sculpture',source_scope='Native offer and public page agree; material conflict and physical claim questions remain',shopify_state=batch['shopify_state'],unresolved='; '.join(batch['open_questions']),review_state='SOURCE SPECIFICATIONS MAPPED; MATERIAL / FIXING / PROVENANCE OPEN')]+batch02['sculptures']
counts=dict(families=len(family_rows),groups=len(groups),assets=len(asset_rows),native_offers=len(offers),ss_offers=sum(o['platform']=='Squarespace' for o in offers),shopify_main_offers=sum(o['platform']=='Shopify main' for o in offers),older_and_seed_offers=sum(o['platform'] in ['Shopify older','Shopify seed'] for o in offers),native_rows=len(native),native_fields_nonempty=sum(1 for r in native for v in r['values'].values() if v!=''),native_field_parts=len(native_fields),specification_claims=len(facts),relationship_rows=len(links),groups_with_confirmed_image_links=sum(bool(g['confirmed_offers']) for g in groups),groups_without_confirmed_image_links=sum(not g['confirmed_offers'] for g in groups),families_reviewed_with_open_questions=2,reviewed_designs=len(designs),reviewed_sculpture_finish_records=len(reviewed_sculptures),physical_specifications_fully_verified=0,first_batch_files_viewed=13,fully_reviewed_family_files=89,individually_viewed_assets=sum(r['review']!='NOT INDIVIDUALLY REVIEWED' for r in asset_rows),source_ids_not_in_current_snapshot=len(old_ids-set(by_id)))
model=dict(created_utc=datetime.now(timezone.utc).isoformat(),inventory_time=inventory['finished_utc'],scope=inventory['root_path'],counts=counts,families=family_rows,groups=groups,designs=designs,reviewed_sculptures=reviewed_sculptures,offers=offers,links=links,facts=facts,native_fields=native_fields,assets=asset_rows,issues=issues,batch01=batch,batch02=batch02,source_register=source['Source Register'],reference_notes=source['Historical Descriptions'])
(ev/'native_records.json').write_text(json.dumps(native,ensure_ascii=False))
(ev/'catalogue_model.json').write_text(json.dumps(model,ensure_ascii=False))

# A small resumable relational store lives outside synchronized workspace folders.
state=Path('/Users/tprice/Library/Application Support/BoldstoneCatalogue');state.mkdir(parents=True,exist_ok=True)
db=state/'catalogue.sqlite3';con=sqlite3.connect(db)
for name,rows in [('families',family_rows),('groups',groups),('offers',offers),('links',links),('facts',facts),('native_rows',native),('assets',asset_rows),('issues',issues),('designs',designs),('reviewed_sculptures',reviewed_sculptures)]:
    con.execute(f'CREATE TABLE IF NOT EXISTS {name} (record_key TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    con.execute(f'DELETE FROM {name}')
    for row in rows:
        rid=next((row[k] for k in ['group_id','offer_key','link_id','fact_id','row_key','file_id','issue_id','family_id'] if k in row and row[k]),None)
        if name=='links':rid=row['link_id']
        if name=='facts':rid=row['fact_id']
        if name=='assets':rid=row['file_id']
        if name=='native_rows':rid=row['row_key']
        if name=='designs':rid=row['design_id']
        if name=='reviewed_sculptures':rid=row['sculpture_id']
        con.execute(f'INSERT OR REPLACE INTO {name} VALUES (?,?)',(rid,json.dumps(row,ensure_ascii=False)))
con.commit();con.close()
checkpoint=json.loads((project/'checkpoint.json').read_text())
checkpoint.update(phase='Full current wall inventory mapped; first two family media reviews and native specification mapping recorded, with explicit open questions',counts=counts,next_batch='CAT-FAM-003: Ammonite',state_database=str(db),model='evidence/catalogue_model.json',native_records='evidence/native_records.json')
(project/'checkpoint.json').write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2))
with (project/'review_journal.jsonl').open('a') as f:f.write(json.dumps(dict(time=model['created_utc'],event='BATCH01_02_AND_ESTABLISHED_IMAGE_REVIEW',counts=counts))+'\n')
print(json.dumps(counts))
