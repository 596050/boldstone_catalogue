"""Import a sealed read-only listing packet into a new current graph projection."""
import copy
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[2]
PACKET=BASE/'components/parallel-reviews/listing-reconciliation-2026-10-20'
read=lambda p:json.loads(Path(p).read_text())
digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
seal=read(PACKET/'SEAL.json')
assert seal['status']=='SEALED_VERIFIED_READY_FOR_COORDINATOR_IMPORT'
assert digest(PACKET/'SEAL.json')=='add3decb6feee8526b6d7e229cd9e423a4e8327257525195e6fb8bab818e03ea'
for r in list(seal['outputs'].values())+[seal['input_manifest'],seal['source_manifest'],seal['independent_validation']]:
    assert digest(r['path'])==r['sha256'] and Path(r['path']).stat().st_size==r['bytes']
assert read(seal['independent_validation']['path'])['status']=='PASS'
assert read(PACKET/'VALIDATION.json')['status']=='PASS'
pointer=read(BASE/'current-master.json');book=BASE/pointer['workbook'];graph=BASE/pointer['register']
assert digest(book)==pointer['workbook_sha256']==seal['input_workbook_sha256']
assert digest(graph)==pointer['register_sha256']==seal['input_master_sha256']
assert not (HERE/'input-manifest.json').exists(),'Prepared input set already exists'
(HERE/'inputs').mkdir(parents=True,exist_ok=True)
manifest={}
for key,source in {'master_pointer':BASE/'current-master.json','master_workbook':book,'master_register':graph,
 'review_progress':BASE/'components/reviews/specification_review_progress.json','component_checkpoint':BASE/'components/checkpoint.json',
 'root_checkpoint':BASE/'checkpoint.json','owner_ledger':BASE/'components/reviews/user_classifications.json',
 'source_model':BASE/'components/evidence/component_register.json','packet_seal':PACKET/'SEAL.json'}.items():
    snap=HERE/'inputs'/(key+'.before');snap.write_bytes(source.read_bytes());manifest[key]={'path':str(source),'snapshot':str(snap),'sha256':digest(source)}
for key in ['LISTING_RECONCILIATION.json','NATIVE_SOURCE_LINKS.json','LISTING_ISSUES.json','MATCH_EVIDENCE.json','RECONCILIATION_COUNTS.json','REVIEW_HANDOFF.json','SET_ONLY_AND_MULTIPART_OFFERS.json']:
    source=PACKET/key;snap=HERE/'inputs'/key;snap.write_bytes(source.read_bytes());manifest[key]={'path':str(source),'snapshot':str(snap),'sha256':digest(source)}
write(HERE/'input-manifest.json',manifest)
g=read(graph);before=copy.deepcopy(g);data=read(PACKET/'LISTING_RECONCILIATION.json');links=read(PACKET/'NATIVE_SOURCE_LINKS.json');issues=read(PACKET/'LISTING_ISSUES.json');edges=read(PACKET/'MATCH_EVIDENCE.json');counts=read(PACKET/'RECONCILIATION_COUNTS.json')
assert len(data['options'])==184 and len(links['offers'])==81 and len(edges['edges'])==262
for o,x in zip(g['options'],data['options']):
    assert (o['product_id'],o['name'])==(x['product_id'],x['name'])
    assert {k:v['display'] for k,v in o['master_fields'].items()}==x['working_specifications']
    assert o.get('file_id')==x['primary_image_file_id'] and o['photo_coverage']==x['photo_coverage']
    o['current_listing_reconciliation']={k:copy.deepcopy(v) for k,v in x.items() if k not in ['working_specifications','photo_coverage','primary_image_url','primary_folder_url','primary_image_file_id','primary_folder_id']}
g['current_listing_source_links']=links
g['current_listing_match_evidence']=edges
g['current_listing_issues']=issues
summary={'status':'SEALED_SOURCE_RECONCILIATION_IMPORTED; CURRENT_PLATFORM_VERIFICATION_PENDING','recorded_utc':datetime.now(timezone.utc).isoformat(),
 'packet':str(PACKET),'packet_seal_sha256':digest(PACKET/'SEAL.json'),'payload_sha256':digest(PACKET/'LISTING_RECONCILIATION.json'),
 'counts':counts,'scope_and_limits':data['scope_and_limits'],'independent_validation':seal['independent_validation'],
 'sheets':['Listing Reconciliation','Listing Offer Links','Listing Issues'],'source_record_links_do_not_assert_live_exact_configuration':True,'remote_writes':0}
g['latest_listing_reconciliation']=summary
assert g['summary']==before['summary'] and g['components']==before['components']
assert g['original_review_specification_assertions']==before['original_review_specification_assertions']
assert all(x['master_fields']==y['master_fields'] for x,y in zip(g['options'],before['options']))
write(HERE/'canonical-master-register.json',g)

states={
 'EXISTING_INDIVIDUAL_DESIGN_WITH_CONFIGURATION_CONFLICT':'Existing design; configuration conflict',
 'GALLERY_OR_DRAFT_CONTEXT_SALE_UNIT_UNRESOLVED':'Gallery / draft context only',
 'INDIVIDUAL_LISTING_CANDIDATE_SCOPE_UNRESOLVED':'Individual listing candidate; scope unresolved',
 'INDIVIDUAL_SOURCE_RECORD_LINKED':'Individual source record linked',
 'NO_SUPPORTED_INDIVIDUAL_ASSOCIATION_IN_CHECKED_SOURCES':'No individual association in checked sources',
 'RELATED_FAMILY_ONLY_NO_INDIVIDUAL_MATCH':'Related family only',
 'SET_OR_ARRANGEMENT_ASSOCIATION_ONLY':'Set / arrangement only',
 'WALL_CIRCLE_FAMILY_ONLY_EXACT_VARIANT_UNRESOLVED':'Wall Circle family; exact variant unresolved'}
human=lambda s:states.get(s,str(s).replace('_',' ').capitalize())
unique=lambda s:list(dict.fromkeys(x for x in s if x not in [None,'']))
joined=lambda s:'\n'.join(str(x) for x in unique(s))
link=lambda url,label:({'target':url,'label':label} if url else '')
offers={x['offer_ref']:x for x in links['offers']}
opt={x['product_id']:x for x in g['options']}
current={x['offer_ref']:x.get('current_primary_reference',{}) for x in g['source_offer_edges']}
offer_rows={x['offer_ref']:i for i,x in enumerate(links['offers'],10)}
rows=[]
for x in data['options']:
    ss=x['platforms']['Squarespace'];sh=x['platforms']['Shopify'];sv=ss['supported_individual_native_variants'];hv=sh['supported_individual_native_variants']
    ssraw=[v['native_variant'] for v in sv];shraw=[v['native_variant'] for v in hv]
    rs=unique(ss['related_offer_refs']+sh['related_offer_refs'])
    first=next((r for r in rs if r in offer_rows),None)
    rows.append([x['product_id'],x['name'],human(x['overall_disposition']),human(ss['disposition']),joined(v.get('native_product_id') for v in ssraw),
     joined(v.get('native_variant_id') for v in ssraw),joined(v.get('sku_raw') for v in ssraw),human(sh['disposition']),joined(v.get('handle') for v in shraw),
     joined(' / '.join(p['name']+': '+p['value'] for p in v.get('option_tuple',[])) for v in shraw),joined(v.get('sku_raw') for v in shraw),
     x['next_action'],link(x['primary_image_url'],'Sculpture image' if x['primary_image_file_id'] else 'Related source only'),link(x['primary_folder_url'],'Dropbox folder'),
     x['primary_image_file_id'] or 'Unbound',x['primary_folder_id'] or 'Unbound',joined(rs),joined(x['selected_evidence_edge_ids']),
     'Source-qualified. Exact current option / configuration not verified.',
     'Historical native export. Numeric product/variant IDs and current live state unavailable.',
     link("#'Listing Offer Links'!A"+str(offer_rows[first]),'Related source records') if first else '',
     '',x['match_grade']])

offer_view=[]
for x in links['offers']:
    ss=x['Squarespace'];sh=x['Shopify'];sv=ss.get('variants',[]);hv=sh.get('variants',[]);r=current[x['offer_ref']]
    target_ids=unique(pid for ids in x['linked_option_ids_by_relationship'].values() for pid in ids)
    unit=ss.get('native_sellable_unit',{})
    offer_view.append([x['offer_ref'],x['source_title'],x['source_sku'],ss.get('native_product_id',''),
      joined(v.get('native_variant_id') for v in sv) if len(sv)<=4 else f'{len(sv)} native variants; see Wall Circle Sources',len(sv),
      ss.get('presence_state',''),link(ss.get('url'),'Squarespace listing'),sh.get('handle',''),
      joined(' / '.join(p['name']+': '+p['value'] for p in v.get('option_tuple',[])) for v in hv),joined(v.get('sku_raw') for v in hv),
      sh.get('presence_state',''),human(unit.get('classification','UNRESOLVED')),unit.get('quantity_per_offered_unit_source_claim') or '',
      x.get('native_parts_raw',''),joined(opt[p]['name']+' ['+p+']' for p in target_ids if p in opt),
      'Source relationship only. A set, family or BOM association does not assign a standalone component SKU.',
      link(r.get('image_url'),'Source image'),link(r.get('folder_url'),'Dropbox folder'),r.get('file_id') or x['source_image_file_id'],r.get('folder_id') or x['source_image_folder_id'],
      'Not exported. Retain handle and option tuple; do not invent numeric Shopify IDs.',
      link("#'Wall Circle Sources'!A9",'18 patterns / 144 variants') if len(sv)>4 else ''])

issue_view=[]
for x in issues['issues']:
    pids=x.get('product_ids',[]);ofs=x.get('offer_refs',[])
    if not ofs:
        ofs=unique(e.rsplit('::',1)[-1] for e in x.get('evidence_edge_ids',[]) if '::' in e)
    related=[offers[r] for r in ofs if r in offers]
    r=next((opt[p] for p in pids if p in opt),None)
    if r:im={'image_url':r.get('image_url'),'folder_url':r.get('folder_url'),'file_id':r.get('file_id'),'folder_id':r.get('folder_id')}
    else:im=next((current[f] for f in ofs if f in current),{})
    native=x.get('native_collision_evidence',{}).get('records',x.get('native_records',[]))
    source_url=x.get('url') or next((o['Squarespace'].get('url') for o in related if o['Squarespace'].get('url')),None)
    issue_view.append([x['issue_id'],x.get('name') or x.get('title') or joined(opt[p]['name'] for p in pids if p in opt) or x.get('handle',''),human(x['issue_type']),
      x['next_action'],joined(pids),joined(ofs),joined([x.get('native_product_id')]+[n.get('native_product_id') for n in native]+[o['Squarespace'].get('native_product_id') for o in related]),
      joined([x.get('handle')]+[o['Shopify'].get('handle') for o in related]),
      joined([x.get('native_collision_evidence',{}).get('sku'),x.get('historical_sku_raw')]+x.get('selected_export_skus_raw',[])+[o['source_sku'] for o in related]),
      link(im.get('image_url'),'Sculpture / source image'),link(im.get('folder_url'),'Dropbox folder'),im.get('file_id') or 'Unbound',im.get('folder_id') or 'Unbound',
      'Source discrepancy or incomplete association; no live absence, duplicate active offer, new sculpture or physical-stock claim.', '', 'Open',link(source_url,'Source listing'),
      joined(n.get('native_variant_id') for n in native)])
defs={
 'Listing Reconciliation':{'title':'Individual option listing reconciliation','note':'All184 options assessed. Individual source-record links retain configuration limits. A missing snapshot association does not prove a live listing is absent.',
  'headers':['Option ID','Individual sculpture / option','Overall result','Squarespace result','SS individual product IDs','SS individual variant IDs','SS individual SKUs','Shopify result','Shopify individual handles','Shopify individual option tuples','Shopify individual SKUs','Next action','Sculpture reference','Containing folder','Dropbox file ID','Dropbox folder ID','Related source offers','Selected evidence edges','Exact configuration scope','Shopify access scope','Related source records','Owner review notes','Match grade'],
  'rows':rows,'widths':[25,58,64,64,36,52,30,64,58,65,30,118,24,20,40,40,40,67,85,92,27,95,81],'editable':['V']},
 'Listing Offer Links':{'title':'Native source offers and sale units','note':'81 source offers. Current public Squarespace records are separated from historical Shopify export records. Set descriptions and BOM positions do not create individual component SKUs.',
  'headers':['Offer reference','Source product','Source SKU','Squarespace product ID','Squarespace variant IDs','SS variant count','Squarespace source presence','Squarespace page','Shopify handle','Shopify option tuples','Shopify source SKUs','Shopify source presence','Description sale-unit classification','Description piece-count claim','Earlier part-count claim','Related catalogue options','Relationship limits','Source image','Containing folder','Dropbox file ID','Dropbox folder ID','Shopify numeric-ID scope','Wall Circle variant detail'],
  'rows':offer_view,'widths':[21,75,30,36,65,18,72,24,58,65,30,92,75,23,23,110,95,23,20,40,40,94,31],'editable':[]},
 'Listing Issues':{'title':'Listing issues and unresolved associations','note':'Review source conflicts, set-only associations, possible overlaps and missing record associations here. Source non-matches are not verified live absence. Resolve only after checking the exact product, variant and sale unit.',
  'headers':['Issue ID','Sculpture / source product','Issue type','Required action','Related option IDs','Related source offers','Squarespace product IDs','Shopify handles','Source SKUs','Image reference','Containing folder','Dropbox file ID','Dropbox folder ID','Evidence scope','Owner response / exact record','Action status','Source page','Native collision variant IDs'],
  'rows':issue_view,'widths':[48,65,91,128,45,32,60,62,45,24,20,40,40,122,100,22,24,65],'editable':['O','P']}}
for d in defs.values():assert len(d['headers'])==len(d['widths']) and all(len(r)==len(d['headers']) for r in d['rows'])
write(HERE/'workbook-data.json',{'sheets':defs,'counts':counts,'issue_counts':issues['counts_by_type'],'scope_and_limits':data['scope_and_limits']})
write(HERE/'preparation-verification.json',{'status':'PASS','packet_hashes_verified':len(seal['outputs'])+3,'current_names_and_options':184,'current_working_displays_exact':1104,'photo_coverage_preserved':184,
 'scoped_edges':262,'source_offers':81,'new_sheet_rows':{n:len(d['rows']) for n,d in defs.items()},'sealed_payload_sha256':digest(PACKET/'LISTING_RECONCILIATION.json')})
print(json.dumps({'status':'PREPARED','options':184,'offers':81,'issues':len(issue_view),'all1104_current_displays_preserved':True}))
