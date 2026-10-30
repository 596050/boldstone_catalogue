"""Produce an append-only, reviewable join of current images and LOCAL platforms.

The source-to-product relationship remains separate from photo correspondence.
No entire gallery is silently assigned to a finish or sale variant.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sqlite3

H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent
inputs={}
def load(p):
    p=Path(p);blob=p.read_bytes();inputs[str(p)]=hashlib.sha256(blob).hexdigest();return json.loads(blob)
def write(p,d):Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify_seal(p):
    p=Path(p)
    seal=load(p)
    for file,digest in seal.get('files',{}).items():
        path=Path(file) if Path(file).is_absolute() else p.parent/file
        actual=sha(path)
        expected=digest if isinstance(digest,str) else digest['sha256']
        assert actual==expected,(file,expected,actual)
    return seal
run=Path(load(H/'current-work.json')['run'])
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
out=H/'integrations'/stamp;out.mkdir(parents=True,exist_ok=False)
source_db=sqlite3.connect(run/'image-register.sqlite')
db=sqlite3.connect(out/'complete-image-platform-register.sqlite')
source_db.backup(db);source_db.close()
images={x['file_id']:x for x in load(run/'images.json')}
associations=load(run/'associations.json')
source_gallery=load(run/'source-evidence/source-rendition-review-register.json')
decisions=load(H/'source-visual-decisions.json')
followups=load(H/'source-visual-followups.json') if (H/'source-visual-followups.json').exists() else {}
crop_followups=load(H/'bounded-crop-comparison-review.json') if (H/'bounded-crop-comparison-review.json').exists() else {}
multi_version={}
if (H/'multiple-correspondence-qa/sealed-handoff.json').exists():
    verify_seal(H/'multiple-correspondence-qa/sealed-handoff.json')
    multi_version={r['gallery_entry_id']:r for r in load(H/'multiple-correspondence-qa/review.json')['records']}
root=ROOT/'reports/local-platform-crosswalk-corrected-20261024-root'
verify_seal(root/'sealed-handoff.json')
platform=load(root/'local-platform-crosswalk.json')
assert inputs[str(root/'local-platform-crosswalk.json')]=='ef7158d87d6402d1e57b8f209da3ca6421104887da9c8a1e3ea9413b72bce578'
for file,receipt in platform['source_manifest'].items():assert sha(file)==receipt['sha256'],file
assert len(platform['local_shopify_records'])==136
assert sum(len(x['variants']) for x in platform['local_shopify_records'])==160
assert len(platform['squarespace_source_records'])==80
assert sum(len(x['local_squarespace_gallery_record']['ordered_gallery']) for x in platform['squarespace_source_records'])==445

# The owner-selected LOCAL Shopify export is the authority for these records.
# Keep each reviewed media occurrence intact, including crop/scene qualifications.
shopify_dir=ROOT/'reports/shopify-wall-gallery-review-20261024-root'
verify_seal(shopify_dir/'sealed-handoff.json')
shopify_review=load(shopify_dir/'shopify-wall-gallery-visual-review.json')
shopify_records=shopify_review['records']
assert len(shopify_records)==117 and len({r['review_id'] for r in shopify_records})==117
shopify_products={r['handle']:r for r in platform['local_shopify_records']}
shopify_by_sq=defaultdict(list)
shopify_integrity_checks=0
for row in shopify_records:
    assert row['exported_gallery_row'] in shopify_products[row['handle']]['full_product_gallery']
    assert row['exported_gallery_row']['variant_image_raw']==''
    assert row['variant_specific_assignment_certified'] is False
    assert row['canonical_binding_applied'] is False
    shopify_integrity_checks+=4
    for evidence in [row['source_download'],row['evidence_board'],row.get('focused_evidence_board')]:
        if evidence:
            assert sha(evidence['path'])==evidence['sha256'];shopify_integrity_checks+=1
    for key in ['native_photo_correspondence','native_scene_or_design_candidate']:
        candidate=row.get(key)
        if not candidate:continue
        fid=candidate['file_id'];native=candidate['native_reference'];visual=candidate['visual_source']
        assert fid in images and images[fid]['folder_id']==native['folder_id']
        assert images[fid]['image_url']==native['image_url']
        assert images[fid]['folder_url']==native['folder_url']
        assert sha(visual['source_image_path'])==visual['actual_visual_source_sha256']
        shopify_integrity_checks+=4
    for sq in row['squarespace_photo_correspondences']:
        assert sha(sq['selected_rendition']['path'])==sq['selected_rendition']['sha256']
        shopify_by_sq[sq['gallery_entry_id']].append((row,sq));shopify_integrity_checks+=1
assert sum(bool(r['native_photo_correspondence']) for r in shopify_records)==114
assert {r['review_id'] for r in shopify_records if not r['native_photo_correspondence']}=={'S016','S021','S022'}

# Consume only sealed, explicitly reviewed per-file roles. Source folder labels
# remain qualified scope evidence, not proof of product/finish identity.
directory=ROOT/'reports/dropbox-wall-complete-role-review-20261024T214349Z'
role_index=load(directory/'completed-family-role-manifests.json')
roles={}
for entry in role_index:
    assert sha(entry['manifest_path'])==entry['manifest_sha256']
    assert sha(entry['seal_path'])==entry['seal_sha256']
    for role in load(entry['manifest_path']):
        fid=role['file_id'];assert fid in images and images[fid]['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'
        assert role['folder_id']==images[fid]['folder_id']
        assert fid not in roles
        roles[fid]={**role,'review_manifest':entry['manifest_path'],'review_manifest_sha256':entry['manifest_sha256']}
supplementary_roles={}
supplementary_path=H/'supplementary-selected-reference-roles.json'
if supplementary_path.exists():
    for role in load(supplementary_path):
        fid=role['file_id'];assert fid not in roles
        assert images[fid]['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED_OUTSIDE_WALL_SCOPE'
        assert images[fid]['folder_id']==role['folder_id']
        assert sha(role['evidence']['source_image_path'])==role['evidence']['actual_visual_source_sha256']
        supplementary_roles[fid]=role
for fid,image in images.items():
    evidence=roles.get(fid) or supplementary_roles.get(fid)
    image['visual_role_evidence']=evidence
    image['visual_role']=(evidence or {}).get('visual_role')
    image['visual_review_status']='EXPLICIT_PER_FILE_VISUAL_ROLE_REVIEW' if evidence else 'PER_FILE_VISUAL_ROLE_NOT_YET_INTEGRATED'
    if not image['inventory_status'].startswith('CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED'):
        image['historical_image_url']=image.get('image_url');image['historical_folder_url']=image.get('folder_url')
        image['image_url']=None;image['folder_url']=None
    db.execute('UPDATE images SET folder_id=?,path=?,record_json=? WHERE file_id=?',(image.get('folder_id'),image.get('path'),json.dumps(image,ensure_ascii=False),fid))

wall_dir=B/'components/parallel-reviews/held-identities-resumption-01a16dbc-20261024/wall-source-gallery-roles'
verify_seal(wall_dir/'sealed-handoff.json')
wall=load(wall_dir/'gallery-roles.json')
wall_roles={x['source_image_url']:x for x in wall['frames']}
assert len(wall_roles)==24
wall_photo_dir=B/'components/parallel-reviews/wall-circle-exact-source-photo-review-01a16dbc-20261024'
verify_seal(wall_photo_dir/'sealed-integration-handoff.json')
verify_seal(wall_photo_dir/'sealed-handoff.json')
wall_photos=load(wall_photo_dir/'source-picture-links.json')
assert len(wall_photos['links'])==38 and wall_photos['source_frames']==20
wall_photo_by_url=defaultdict(list)
for edge in wall_photos['links']:
    assert edge['source_picture_match_supported'] is True
    assert edge['grade']=='SAME_FULL_FRAME_IMAGE_RENDITION'
    assert edge['physical_or_exact_variant_identity_claimed'] is False
    fid=edge['current_file_id'];assert images[fid]['folder_id']==edge['current_folder_id']
    assert images[fid]['image_url']==edge['image_url'] and images[fid]['folder_url']==edge['folder_url']
    wall_photo_by_url[edge['source_image_url']].append(edge)
matches=[]
def prior_supported_bindings(evidence):
    """Retain explicit sealed photo findings, never convert a score to a match."""
    r=evidence['recorded_review'];found=[]
    def add(fid,basis):
        if fid and fid in images:found.append((fid,basis))
    if r.get('same_photograph_supported') is True or r.get('photo_level_correspondence_supported') is True:
        add(r.get('file_id') or r.get('current_image',{}).get('file_id'),'EXPLICIT_PRIOR_PHOTO_CORRESPONDENCE')
    if r.get('same_photograph_correspondence_supported') is True:
        add(r.get('current_reference',{}).get('file_id'),'EXPLICIT_PRIOR_PHOTO_CORRESPONDENCE')
    for candidate in r.get('matched_current_images',[]):
        if candidate.get('same_image_composition_supported') is True or candidate.get('same_photograph_supported') is True:
            add(candidate.get('current_image',{}).get('file_id'),'EXPLICIT_PRIOR_COMPOSITION_CORRESPONDENCE')
    if r.get('status')=='SAME_PHOTOGRAPH_CORRESPONDENCE_SAVED_RENDITIONS':
        for candidate in r.get('current_candidates',[]):
            if candidate.get('source_and_target_visually_reviewed') is True:
                add(candidate.get('current_reference',{}).get('file_id'),'EXPLICIT_PRIOR_SAVED_RENDITION_CORRESPONDENCE')
    # These are manually written, sealed findings, not numerical thresholds.
    if r.get('visual_result','').startswith('Whole-frame photo correspondence supported'):
        add(r.get('selected_file_id') or r.get('target_file_id'),'EXPLICIT_PRIOR_WHOLE_FRAME_PHOTO_FINDING')
    if 'show the same photograph' in r.get('visual_assessment',''):
        add(r.get('file_id'),'EXPLICIT_PRIOR_VISUAL_PHOTO_FINDING')
    return found

def append_match(row,fid,evidence,status):
    assert fid in images
    match={'gallery_entry_id':row['gallery_entry_id'],'offer_ref':row['offer_ref'],'source_url':row['source_url'],
        'file_id':fid,'visual_role':row['visual_role'],'image_url':images[fid]['image_url'],'folder_url':images[fid]['folder_url'],
        'native_status':images[fid]['inventory_status'],'status':status,'evidence':evidence,
        'source_to_option_assignment_automatically_created':False}
    matches.append(match)

for row in source_gallery:
    key=f"{row['offer_ref']}:{row['gallery_order']:02d}"
    decision=decisions.get(key)
    if row['offer_ref']=='O001':
        role=wall_roles[row['source_url']]
        row['visual_role']=role['primary_visual_role'];row['role_status']='EXPLICIT_VISUAL_ROLE_REVIEW'
        row['visual_review_status']='EXPLICIT_VISUAL_REVIEW_WITH_PROVENANCE_QUALIFICATIONS'
        row['current_role_evidence']={'path':str(wall_dir/'gallery-roles.json'),'sha256':inputs[str(wall_dir/'gallery-roles.json')],'record':role}
        for edge in wall_photo_by_url.get(row['source_url'],[]):
            assert edge['source_gallery_order_1based']==row['gallery_order']
            append_match(row,edge['current_file_id'],{'path':str(wall_photo_dir/'source-picture-links.json'),'sha256':inputs[str(wall_photo_dir/'source-picture-links.json')],'record':edge},edge['grade'])
    elif decision:
        assert decision['gallery_entry_id']==row['gallery_entry_id']
        assert sha(decision['source_path'])==decision['source_sha256']
        assert sha(decision['candidate_path'])==decision['candidate_sha256']
        row['visual_role']=decision['source_visual_role'];row['role_status']='EXPLICIT_VISUAL_ROLE_REVIEW'
        row['visual_review_status']='EXPLICIT_VISUAL_REVIEW_WITH_QUALIFIED_CORRESPONDENCE'
        row['current_role_evidence']=decision
        if decision['matched_candidate_file_id']:
            fid=decision['matched_candidate_file_id'];assert fid in images
            append_match(row,fid,decision,'VISUALLY_SUPPORTED_PHOTO_CORRESPONDENCE_WITH_RETAINED_QUALIFICATIONS')
    for evidence in row['prior_visual_evidence']:
        assert sha(evidence['path'])==evidence['sha256']
        for fid,basis in prior_supported_bindings(evidence):append_match(row,fid,evidence,basis)
    for followup in followups.get(key,[]):
        assert followup['gallery_entry_id']==row['gallery_entry_id']
        row.setdefault('followup_evidence',[]).append(followup)
        if followup.get('same_photo_correspondence_supported') is True:
            append_match(row,followup['file_id'],followup,'FOLLOWUP_VISUALLY_SUPPORTED_PHOTO_CORRESPONDENCE')
    if key in crop_followups:
        comparison=crop_followups[key]
        assert comparison['gallery_entry_id']==row['gallery_entry_id']
        assert sha(comparison['board'])==comparison['board_sha256']
        row['bounded_crop_comparison_review']=comparison
    for shop,sq in shopify_by_sq.get(row['gallery_entry_id'],[]):
        assert sq['source_url']==row['source_url']
        evidence={'review_path':str(shopify_dir/'shopify-wall-gallery-visual-review.json'),
            'review_sha256':inputs[str(shopify_dir/'shopify-wall-gallery-visual-review.json')],
            'shopify_review_id':shop['review_id'],'handle':shop['handle'],
            'native_correspondence_disposition':shop['native_correspondence_disposition'],
            'source_role_and_uncertainty_note':shop['source_role_and_uncertainty_note'],
            'squarespace_same_frame_evidence':sq,'exact_byte_or_pixel_identity_claimed':False,
            'variant_specific_assignment_certified':False}
        row.setdefault('local_shopify_gallery_evidence',[]).append(evidence)
        if shop.get('native_photo_correspondence'):
            append_match(row,shop['native_photo_correspondence']['file_id'],evidence,
                'LOCAL_SHOPIFY_SAME_SOURCE_FRAME__'+shop['native_correspondence_disposition'])
    row['supported_photo_file_ids']=sorted({m['file_id'] for m in matches if m['gallery_entry_id']==row['gallery_entry_id']})
    if row['gallery_entry_id'] in multi_version:
        versions=multi_version[row['gallery_entry_id']]
        assert set(row['supported_photo_file_ids'])=={r['file_id'] for r in versions['candidates']}
        row['multiple_current_version_review']=versions
    row['photo_correspondence_status']='SUPPORTED_WITH_RETAINED_QUALIFICATIONS' if row['supported_photo_file_ids'] else 'EXACT_CURRENT_PHOTO_CORRESPONDENCE_NOT_ESTABLISHED'
    db.execute('UPDATE source_gallery SET record_json=? WHERE gallery_entry_id=?',(json.dumps(row,ensure_ascii=False),row['gallery_entry_id']))

db.executescript('''
CREATE TABLE local_shopify_products(handle TEXT PRIMARY KEY, disposition TEXT, record_json TEXT NOT NULL);
CREATE TABLE local_shopify_variants(variant_key TEXT PRIMARY KEY, handle TEXT, record_json TEXT NOT NULL);
CREATE TABLE local_shopify_media(handle TEXT, row_ordinal INTEGER, record_json TEXT NOT NULL);
CREATE TABLE source_product_links(offer_ref TEXT, product_id TEXT, relationship TEXT, record_json TEXT NOT NULL);
CREATE TABLE source_photo_correspondences(gallery_entry_id TEXT, file_id TEXT, visual_role TEXT, record_json TEXT NOT NULL);
CREATE TABLE per_image_visual_roles(file_id TEXT PRIMARY KEY, visual_role TEXT, record_json TEXT NOT NULL);
CREATE TABLE local_squarespace_records(offer_ref TEXT PRIMARY KEY, native_product_id TEXT, record_json TEXT NOT NULL);
CREATE TABLE local_source_offers(offer_ref TEXT PRIMARY KEY, platform TEXT, record_json TEXT NOT NULL);
CREATE TABLE local_shopify_gallery_reviews(review_id TEXT PRIMARY KEY, handle TEXT, visual_role TEXT, record_json TEXT NOT NULL);
''')
for row in platform['local_shopify_records']:
    db.execute('INSERT INTO local_shopify_products VALUES(?,?,?)',(row['handle'],row['disposition'],json.dumps(row,ensure_ascii=False)))
    for variant in row['variants']:
        db.execute('INSERT INTO local_shopify_variants VALUES(?,?,?)',(variant['variant_key'],row['handle'],json.dumps(variant,ensure_ascii=False)))
    for i,media in enumerate(row['full_product_gallery']):
        db.execute('INSERT INTO local_shopify_media VALUES(?,?,?)',(row['handle'],i,json.dumps(media,ensure_ascii=False)))
for row in platform['squarespace_source_records']:
    native=row['local_squarespace_gallery_record']['native_product_id']
    db.execute('INSERT INTO local_squarespace_records VALUES(?,?,?)',(row['offer_ref'],native,json.dumps(row,ensure_ascii=False)))
    db.execute('INSERT INTO local_source_offers VALUES(?,?,?)',(row['offer_ref'],'Squarespace',json.dumps(row,ensure_ascii=False)))
    for option in row['related_current_individual_options']:
        db.execute('INSERT INTO source_product_links VALUES(?,?,?,?)',(row['offer_ref'],option['product_id'],option['relationship'],json.dumps(option,ensure_ascii=False)))
for row in platform['unpaired_shopify_wall_records']:
    ref=row['retained_source_offer']['offer_ref']
    db.execute('INSERT INTO local_source_offers VALUES(?,?,?)',(ref,'Shopify',json.dumps(row,ensure_ascii=False)))
    for option in row['related_current_individual_options']:
        db.execute('INSERT INTO source_product_links VALUES(?,?,?,?)',(ref,option['product_id'],option['relationship'],json.dumps(option,ensure_ascii=False)))
for row in shopify_records:
    db.execute('INSERT INTO local_shopify_gallery_reviews VALUES(?,?,?,?)',(row['review_id'],row['handle'],row['source_visual_role'],json.dumps(row,ensure_ascii=False)))
for row in matches:db.execute('INSERT INTO source_photo_correspondences VALUES(?,?,?,?)',(row['gallery_entry_id'],row['file_id'],row['visual_role'],json.dumps(row,ensure_ascii=False)))
for fid,row in roles.items():db.execute('INSERT INTO per_image_visual_roles VALUES(?,?,?)',(fid,row['visual_role'],json.dumps(row,ensure_ascii=False)))

per_product=defaultdict(dict)
for row in associations:
    fid=row['file_id'];image=images.get(fid,{})
    row['visual_role']=image.get('visual_role');row['visual_role_status']=image.get('visual_review_status','NO_CURRENT_FILE')
    row['image_url']=image.get('image_url');row['folder_url']=image.get('folder_url')
    row['current_native_status']=image.get('inventory_status','NOT_IN_CURRENT_MAP')
    db.execute('UPDATE associations SET record_json=? WHERE association_id=?',(json.dumps(row,ensure_ascii=False),row['association_id']))
    grouped=per_product[row['product_id']].setdefault(fid,{'file_id':fid,'name':image.get('name'),
        'visual_role':image.get('visual_role'),'visual_review_status':row['visual_role_status'],
        'image_url':row['image_url'],'folder_url':row['folder_url'],'native_status':row['current_native_status'],
        'association_statuses':[],'evidence':[]})
    if row['association_status'] not in grouped['association_statuses']:grouped['association_statuses'].append(row['association_status'])
    grouped['evidence'].append({'association_id':row['association_id'],'intended_use':row['intended_use'],'source_evidence':row['evidence']})

summary={'status':'REVIEW_INTEGRATION_COMPLETE_IDENTITY_AND_CANONICAL_RELEASE_PENDING' if len(roles)==6360 else 'IN_PROGRESS_FULL_OBJECTIVE_RETAINED','recorded_utc':datetime.now(timezone.utc).isoformat(),
    'baseline_pointer_sha256':load(run/'summary.json')['baseline_pointer_sha256'],
    'catalogue_options':db.execute('SELECT COUNT(*) FROM products').fetchone()[0],
    'current_wall_files':sum(x['inventory_status']=='CURRENT_NATIVE_FILE_AND_ACTUAL_PARENT_VERIFIED' for x in images.values()),
    'reviewed_current_file_roles':len(roles),'reviewed_families':len(role_index),
    'supplementary_selected_master_document_reference_roles':len(supplementary_roles),
    'gallery_entries':len(source_gallery),'source_entries_with_explicit_roles':sum(x.get('role_status')=='EXPLICIT_VISUAL_ROLE_REVIEW' for x in source_gallery),
    'retained_and_new_photo_evidence_edges':len(matches),'source_entries_with_retained_prior_visual_evidence':sum(bool(x['prior_visual_evidence']) for x in source_gallery),
    'local_shopify_products':136,'local_shopify_variants':160,'local_shopify_media_rows':db.execute('SELECT COUNT(*) FROM local_shopify_media').fetchone()[0],
    'local_source_pair_counts':platform['counts'],
    'local_shopify_full_gallery_review_counts':shopify_review['counts'],
    'local_shopify_gallery_import_integrity_checks_passed':shopify_integrity_checks,
    'local_shopify_gallery_review_complete':True,
    'wall_circle_supported_source_frames':20,'wall_circle_supported_source_picture_links':38,
    'full_gallery_membership_established':True,'complete_full_gallery_visual_review':all(x.get('role_status')=='EXPLICIT_VISUAL_ROLE_REVIEW' for x in source_gallery),
    'source_entries_with_supported_photo_correspondence':sum(bool(x.get('supported_photo_file_ids')) for x in source_gallery),
    'source_entries_without_supported_photo_correspondence':[{'offer_ref':x['offer_ref'],'gallery_order':x['gallery_order']} for x in source_gallery if not x.get('supported_photo_file_ids')],
    'every_current_file_visually_classified':len(roles)==6360,'held_identity_answers_complete':False,
    'canonical_or_platform_writes':0,
    'next_work':(['Import remaining directory role packets.'] if len(roles)<6360 else [])+['Incorporate pending exact owner identity decisions through their existing review owner.','Incorporate the main session canonical navigation and selected-reference replacement release after independent readback.','Retain unresolved exact-photo comparisons until additional supporting evidence is available; completed visual reviews are not missing photographs.'],
    'scope_notes':['Shopify authority is the owner-requested local export; no live Shopify access required or claimed.',
        'Missing numeric Shopify IDs and variant-image fields are not invented.',
        'Folder candidates remain labelled. Group pictures remain context. Separate source/gallery/option relationships are not collapsed.',
        'Historical unavailable file links are retained as evidence, not emitted as verified current image links.']}
db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('integration_summary',json.dumps(summary,ensure_ascii=False)))
db.commit();assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()
write(out/'summary.json',summary);write(out/'input-manifest.json',inputs)
write(out/'per-product-image-lists.json',{pid:list(rows.values()) for pid,rows in per_product.items()})
write(out/'source-gallery-review.json',source_gallery);write(out/'source-photo-correspondences.json',matches)
write(out/'local-shopify-gallery-review.json',shopify_review)
write(out/'local-shopify-gallery-import-readback.json',{'status':'PASS_INDEPENDENT_HASH_AND_NATIVE_PARENT_IMPORT_CHECKS','checks_passed':shopify_integrity_checks,'reviewed_occurrences':117,'qualified_native_photo_correspondences':114,'exact_photo_unresolved_review_ids':['S016','S021','S022'],'new_variant_image_assignments':0,'visual_review_origin':'Main session; B verifies integrity, native references and preservation of proof grades.'})
write(out/'current-file-visual-roles.json',list(roles.values()))
e=lambda x:html.escape(str(x),quote=True)
page='<!doctype html><meta charset="utf-8"><title>Local records and image review</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;line-height:1.5}td,th{padding:8px;border-bottom:1px solid #ddd;text-align:left}table{border-collapse:collapse}</style><h1>Local records and image review — in progress</h1><p>The Shopify source is the local export. Product/variant records, source gallery photographs and current Dropbox images remain separately qualified.</p><table>'
for label,key in [('Catalogue options','catalogue_options'),('Current Dropbox wall images','current_wall_files'),('Images with explicit visual roles','reviewed_current_file_roles'),('Full source gallery entries','gallery_entries'),('Source images with explicit visual roles','source_entries_with_explicit_roles'),('Local Shopify products','local_shopify_products'),('Local Shopify variant rows','local_shopify_variants')]:page+=f'<tr><th>{e(label)}</th><td>{summary[key]}</td></tr>'
page+='</table><p><a href="product-images.html">Browse all 188 product image lists</a> · <a href="'+e(root/'index.html')+'">Local Shopify and Squarespace matching report</a> · <a href="'+e(shopify_dir/'index.html')+'">All 117 Shopify gallery images</a> · <a href="source-gallery-review.json">Full Squarespace gallery review register</a></p><p>Remaining reviews and identity decisions are listed in <a href="summary.json">the progress record</a>. This is a preparation snapshot; no canonical or platform records were changed.</p>'
(out/'index.html').write_text(page)
write(H/'current-integration.json',{'run':str(out),'summary':str(out/'summary.json'),'reader':str(out/'index.html'),'database':str(out/'complete-image-platform-register.sqlite')})
print(json.dumps({'output':str(out),'summary':summary},indent=2))
