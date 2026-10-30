from pathlib import Path
import json, hashlib, datetime, sys

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
SOURCE=PROJECT/'sculpture-catalogue'
DRAFT=SOURCE/'components/reconciliation/fingerprint-numbered-master-refresh-2026-10-22'
published='--published' in sys.argv
def read(p): return json.loads(p.read_text())
pointer=read(SOURCE/'current-master.json') if published else None
target=SOURCE/pointer['register'] if published else DRAFT/'canonical-master-register.json'
before=read(HERE/'catalogue-before-register.json')
after=read(target)
overlay=read(HERE/'catalogue-placement-overlay.json')
old={r['product_id']:r for r in before['options']}
new={r['product_id']:r for r in after['options']}
assert set(old)==set(new), 'Canonical IDs changed without factual reconciliation'
fp={id for id,r in old.items() if (r.get('canonical_design_id') or '').startswith('BC-FP-')}
assert len(fp)==4
unrelated_changes=[id for id in old if id not in fp and old[id]!=new[id]]
assert not unrelated_changes, unrelated_changes
assert all(old[id]['specifications']==new[id]['specifications'] for id in old), 'Specifications changed'
assert before['original_review_specification_assertions']==after['original_review_specification_assertions'], 'Historical assertions changed'
assert [(c['component_id'],c['name']) for c in before['components']]==[(c['component_id'],c['name']) for c in after['components']]
latest=after['latest_fingerprint_numbered_reconciliation']
inventory=latest['numbered_folder_finish_inventory']
assert len(inventory)==6
assert {(c['number'],c['finish']) for c in inventory}=={(c['number'],c['finish']) for c in overlay['components']}
for c in inventory:
    source=next(x for x in overlay['components'] if (x['number'],x['finish'])==(c['number'],c['finish']))
    assert c['component_folder']==source['individual_folder']
    assert c['original_individual_photo']==source['numbering_reference_photo']
    assert c['original_image_folder']==source['original_reference_folder']
    assert c['original_photo_sha256']==source['numbering_reference_sha256']
    assert c['context_photo_ids']==source['uploaded_context_photo_ids']
    assert c['isolated_png_candidates']==source['isolated_image_candidates']
    assert c['canonical_count_effect']==0 and c['canonical_option_id'] is None
photos=latest['uploaded_photo_relationships']
assert photos==overlay['photos'], 'Photo identity, path, hash or member map changed'
crosswalk=latest['legacy_candidate_crosswalk']
assert len(crosswalk)==4
assert all(not x['same_design_or_revision_confirmed'] and not x['specification_transfer_confirmed'] and not x['finish_transfer_confirmed'] for x in crosswalk)
assert latest['new_canonical_components_or_options']==0
assert latest['legacy_specification_transfers']==0
proof={'status':'PASS','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'target_register':str(target),'register_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    'published':published,'canonical_options_preserved':len(new),'identified_components_preserved':len(after['components']),
    'unrelated_options_identical':len(new)-len(fp),'all_specification_field_groups_unchanged':sum(len(r['specifications']) for r in new.values()),
    'original_review_assertions_unchanged':len(after['original_review_specification_assertions']),
    'six_current_numbered_finish_records_match_native_evidence':True,'all_26_photo_records_match_native_evidence':True,
    'legacy_identity_decision_pending':True,'legacy_specification_or_finish_transfers':0}
if published:
    assert proof['register_sha256']==pointer['register_sha256']
    wb=SOURCE/pointer['workbook']; proof['workbook_sha256']=hashlib.sha256(wb.read_bytes()).hexdigest()
    assert proof['workbook_sha256']==pointer['workbook_sha256']
    proof['workbook']=str(wb)
    proof['publication_receipt']=str(SOURCE/pointer['publication_receipt'])
name='independent-published-register-verification.json' if published else 'independent-prepared-register-verification.json'
(HERE/name).write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
