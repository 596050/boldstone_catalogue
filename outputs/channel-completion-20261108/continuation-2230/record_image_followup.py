"""Reconcile dated native image evidence with unchanged current catalogue facts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from collections import defaultdict
import copy,hashlib,json,urllib.request

OUT=Path(__file__).parent;PACKET=OUT.parent;GALLERY=PACKET/'brandboom-gallery-audit'
load=lambda p:json.loads(Path(p).read_text())
now=lambda:datetime.now(timezone.utc).isoformat()
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=120) as response:return json.load(response)
spec=get('/api/specifications');coverage=get('/api/coverage')
base=load(PACKET/'catalogue-google-dates/app-specifications.json')
facts=lambda data:{p['id']:{key:p[key] for key in ['fields','listing_fields','costing','photos','listing_decision']} for p in data['products']}
assert facts(spec)==facts(base),'App facts changed; reconcile before binding dated external checks'
plan=load(PACKET/'brandboom-restore-plan.json');expected_photos=load(PACKET/'current-selected-photo-metadata.json')
for record in plan['records']:
    photo=coverage['products'][record['catalogue_id']]
    ids=list(dict.fromkeys([photo['primary_listing']['image_id']]+photo['listing']['image_ids']+photo['in_situ']['image_ids']))
    assert ids==record['image_ids'],record['catalogue_id']
def check_originals(record):
    detail=get('/api/products/'+record['catalogue_id']);images={row['id']:row for row in detail['images']}
    for photo in record['image_ids']:
        assert images[photo]['original'].get('dropbox_content_hash')==expected_photos[photo]['original'].get('dropbox_content_hash'),photo
    return len(record['image_ids'])
with ThreadPoolExecutor(max_workers=4) as pool:original_placements=sum(pool.map(check_originals,plan['records']))
assert original_placements==1437

comparisons={record['sku']:load(GALLERY/(record['sku']+'-comparison.json')) for record in plan['records']}
assert len(comparisons)==176 and all(r['native_count']==r['expected_count'] and r['primary_assignment_matches'] for r in comparisons.values())
assert sum(r['native_count'] for r in comparisons.values())==1437
assert {r['sku'] for r in comparisons.values() if r['worst_mean_absolute_pixel_difference']>6}=={'SQ5572436'}
repairs={row['sku']:load(GALLERY/'repairs'/(row['sku']+'-receipt.json')) for row in load(GALLERY/'repair-intent.json')['duplicate_associations']}
assert len(repairs)==14 and all(r['status']=='SAVED_AND_INDEPENDENTLY_REOPENED_EXACT_NATIVE_IDS' for r in repairs.values())
assert load(GALLERY/'removed-media-reference-audit.json')['other_product_references']==[]
verification={'status':'PASS_ALL_176_RENDERED_GALLERIES_WITH_EXACT_SAVED_REPAIR_READBACK',
    'checked_at':now(),'products':176,'selected_photo_placements':1437,'current_selected_original_content_hashes_unchanged':True,
    'gallery_count_mismatches':0,'primary_assignment_mismatches':0,'repaired_products':14,
    'excess_associations_removed_this_followup':14,'sideways_associations_replaced':3,'upright_renditions_added':3,
    'removed_associations_total':17,'removed_media_retained_in_native_media_bin':True,
    'removed_media_referenced_by_other_products':0,'prices_titles_and_app_choices_preserved':True,
    'rendered_comparison_qualification':'Small public provider renditions, source identities and native media IDs. Not a claim of identical original bytes or public Marketplace publication.',
    'manual_visual_review':{'SQ5572436':'All eight viewed photographs show the same compositions and rust/verdigris patterns as the selected sources. Larger raw RGB differences in two details reflect provider encodings; no colour edit was made.',
                          '14_extra_photo_pairs':'All fourteen native extra/retained/reference pairs visually reviewed before recoverable association removal.',
                          '3_upright_replacements':'Existing provider renditions match the selected sources, EXIF orientation is 1, and rendered checks pass after native upload/save/reload.'}}
(GALLERY/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
(OUT/'app-specifications-after-images.json').write_text(json.dumps(spec,ensure_ascii=False)+'\n')
(OUT/'app-coverage-after-images.json').write_text(json.dumps(coverage,ensure_ascii=False)+'\n')

google=load(OUT/'google-rendition-after-verification.json');assert google['status']=='PASS_NATIVE_COMBINED_OFFER_READBACK'
google_at=google['checked_at'];approval=(OUT/'google-rendition-approval-status.txt').read_text()
assert all(text in approval for text in ['325 Approved','0 Limited','0 Not approved','0 Under review'])
google['native_approval_checked_at']=datetime.fromtimestamp((OUT/'google-rendition-approval-status.txt').stat().st_mtime,timezone.utc).isoformat()
google['native_approval_counts']={'approved':325,'limited':0,'not_approved':0,'under_review':0}
(OUT/'google-rendition-after-verification.json').write_text(json.dumps(google,indent=2)+'\n')
ms=load(OUT/'microsoft-rendition-refresh-intent.json')
response_path=OUT/'microsoft-rendition-refresh-response.txt'
ms['acknowledgement_recorded_at']=ms.pop('acknowledged_at',now())
ms['request_action_interval_utc']={'earliest':ms['prepared_at'],'latest':datetime.fromtimestamp(response_path.stat().st_mtime,timezone.utc).isoformat()}
assert 'Import scheduled' in response_path.read_text()
(OUT/'microsoft-rendition-refresh-intent.json').write_text(json.dumps(ms,indent=2)+'\n')
import csv
issues=defaultdict(list)
for row in csv.DictReader((OUT/'microsoft-rejection-report.csv').open(encoding='utf-8-sig')):issues[row['Item Id']].append(row)
sizes=load(OUT/'merchant-compatible-supplement-plan.json')
oversized=defaultdict(list)
for row in sizes['rendition_changes']:
    for use in row['uses']:oversized[use['offer_id']].append({'role':use['role'],'old_url':row['old_url'],'replacement':row['replacement']})
evidence_path=PACKET/'platform-task-evidence.json'
backup=OUT/'platform-task-evidence-before-images.json'
if not backup.exists():backup.write_bytes(evidence_path.read_bytes())
evidence=load(backup);master=load(PACKET/'master-platform-values.json')
def task(key,state,title,detail,scope='external',url=''):
    return dict(id=key,state=state,title=title,detail=detail,scope=scope,url=url)
per_product={}
for record in plan['records']:
    pid=record['catalogue_id'];offer=master[pid]['pinterest_id'];entries=evidence['products'][pid]['platforms']
    expected=next(row for row in sizes['rows'] if row['id']==offer)
    bb_inventory=load(GALLERY/(record['sku']+'.json'))
    bb=entries['brandboom'];bb['checked_at']=bb_inventory['checked_at']
    bb['summary']='176 existing editor products restored; every selected gallery and primary checked. Public Marketplace publication remains separate.'
    bb['tasks']=[t for t in bb['tasks'] if t['id'] not in ['gallery_selected_photos','gallery_repair_readback']]
    bb['tasks'].append(task('gallery_selected_photos','verified','Saved gallery and primary verified',
        f"{record['image_count']} selected Listing/In situ placements match the saved native gallery; current selected primary is first. All 176 galleries total 1,437 placements. Source Dropbox identities/content hashes remain unchanged. Rendered comparisons do not establish public Marketplace visibility.",
        'photos','https://manage.brandboom.com/products/s/111089'))
    if record['sku'] in repairs:
        repair=repairs[record['sku']]
        detail=('Replaced both sideways copies with one upright rendition of the same selected photo.' if repair.get('new_upright_media_id') else 'Removed the one reviewed excess duplicate association.')
        bb['tasks'].append(task('gallery_repair_readback','verified','Gallery repair saved and reopened',detail+' Exact remaining native IDs, count, primary, title and wholesale price verified after full page reload. Old media remains in the native Media Bin; no Dropbox original was deleted.','photos'))
    gm=entries['google_merchant'];gm['state']='verified';gm['checked_at']=google_at
    gm['summary']='Current combined Google offer matches the catalogue; native account still shows all 325 approved.'
    gm['tasks']=[task('product_approval','verified','Google offer approved','Account 5664655454: 325 approved, zero limited/not approved/under review at the dated check. Eligibility is not proof of display or sales.'),
        task('native_feed_refresh','verified','Current combined offer independently verified','All 176 offers matched 11 saved fields (1,936 comparisons). No price changes or new offers; 149 other offers retained their protected fields.','fields'),
        task('image_size_compatibility','verified','Same-photo feed renditions fit Microsoft size cap',f"This offer had {len(oversized[offer])} oversized feed image URL(s). The existing Google supplement now uses qualified same-asset renditions where required. Across the feed, 217 URLs are below 1.5 MB. Photo paths, order, selected primary and website images are unchanged. Microsoft's refreshed native result is separate and pending.",'photos')]
    raw_messages=list(dict.fromkeys(row['Error Message'] for row in issues[offer]))
    if any('Disallowed Supplements' in message for message in raw_messages):
        status='Rejected: Microsoft health-product policy flag on this wall sculpture';state='action'
    elif any('miscellaneous internal error' in message for message in raw_messages):
        status='Rejected image fetch; corrected Google source queued for Microsoft refresh';state='waiting'
    elif any('Adult -' in message for message in raw_messages):
        status='Pending manual review: Microsoft adult-content flag on this abstract wall sculpture';state='waiting'
    else:status='Pending image crawling';state='waiting'
    mm=entries['microsoft_merchant'];mm.update(state=state,checked_at=ms['request_action_interval_utc']['latest'],
        summary=status+'. The new import is acknowledged; processing/publication not yet verified.')
    mm['tasks']=[task('image_size_compatibility','verified','Upstream feed images checked',f"All 1,252 distinct current feed URLs were checked without storing originals. This offer had {len(oversized[offer])} oversized URL(s), now replaced upstream by qualified renditions of the same photos. No claim that Microsoft has processed the new URLs yet.",'photos'),
        task('feed_refresh','waiting','Await the acknowledged Google reimport','Store 50112622, existing feed 1830968, Google account 5664655454. One refresh requested after the independent Google export passed. Native response: Import scheduled; product data updates when it finishes. No second feed or duplicate products created.'),
        task('product_review',state,'Resolve native Microsoft policy flag' if state=='action' else 'Await refreshed Microsoft product result',
            status+'. Last completed import: 325 total, 0 published, 308 pending, 17 rejected; 16 rejected offers are wall sculptures and one is an unrelated card. Raw per-offer messages retained in the catalogue. No product data changed to evade a classifier.','external')]
    per_product[pid]={'sku':record['sku'],'offer_id':offer,'brandboom_inventory':bb_inventory,'brandboom_repair':repairs.get(record['sku']),
        'google_offer':expected,'microsoft_status':status,'microsoft_raw_issue_messages':raw_messages,
        'oversized_feed_image_count':len(oversized[offer]),'primary_rendition_changed':any(x['role']=='primary' for x in oversized[offer])}
evidence['checked_at']=now();evidence['source']+=' Image follow-up: 176 Brandboom galleries and 14 repairs checked; 217 same-photo feed size corrections independently read back in Google. Microsoft refreshed processing is not inferred.'
evidence_path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
(OUT/'image-followup-per-product.json').write_text(json.dumps(per_product,ensure_ascii=False,indent=2)+'\n')
(OUT/'image-followup-evidence-verification.json').write_text(json.dumps({'status':'PASS_SOURCE_FACTS_COMPLETE_PHOTO_HASHES_AND_DATED_NATIVE_EVIDENCE','checked_at':now(),'component_records':181,'publication_records':176,'distinct_selected_source_images':len(expected_photos),'source_placements_checked':original_placements,'app_facts_changed':False,'new_google_products':0,'price_changes':0,'pinterest_appeals_used':0,'gtins_assigned':0,'public_pinterest_feed_changed':False},indent=2)+'\n')
print(json.dumps({'source_facts_unchanged':True,'selected_original_placements_hash_checked':1437,'brandboom_galleries':176,'saved_repairs':14,'google_native_offer_comparisons':1936,'microsoft_refresh_acknowledged_not_processed':True,'evidence_products':len(evidence['products'])}))
