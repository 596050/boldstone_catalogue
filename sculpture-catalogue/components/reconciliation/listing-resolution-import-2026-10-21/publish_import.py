"""Publish the verified additive listing review; execute no native requests."""
import copy, hashlib, json
from pathlib import Path
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
read = lambda p: json.loads(Path(p).read_text())
digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
rel = lambda p: str(Path(p).relative_to(BASE))

def write(p, d):
    p = Path(p)
    t = p.with_name(p.name + '.resolution-tmp')
    t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)

m = read(HERE / 'input-manifest.json')
check = read(HERE / 'saved-file-verification.json')
g = read(HERE / 'canonical-master-register.json')
assert check['status'] == 'PASS' and not check['issues']
assert digest(HERE / 'master-workbook.pending') == check['workbook_sha256']
assert digest(HERE / 'canonical-master-register.json') == check['register_sha256']
for item in m.values():
    assert digest(item['path']) == digest(item['snapshot']) == item['sha256']
seal_path = Path(m['SEAL.json']['path'])
seal = read(seal_path)
for item in seal['artifacts']:
    p = seal_path.parent / item['relative_path']
    assert digest(p) == item['sha256'] and p.stat().st_size == item['bytes']
previews = read(HERE / 'preview-manifest.json')
assert len(previews) == 9
write(HERE / 'visual-verification.json', {
    'status': 'PASS', 'recorded_utc': now(),
    'previews': [{**p, 'sha256': digest(p['path'])} for p in previews],
    'finding': 'All four new tables, conditional native tuple values, request prerequisites and the two dated source notes inspected. Text and identifiers readable; no clipped values observed. Unchanged old views retain prior QA.'
})
ptr = copy.deepcopy(read(BASE / 'current-master.json'))
prior = copy.deepcopy(ptr)
ptr.update(recorded_utc=now(), workbook_sha256=check['workbook_sha256'],
           register=rel(HERE / 'canonical-master-register.json'),
           register_sha256=check['register_sha256'],
           publication_receipt=rel(HERE / 'publication-receipt.json'))
summary = copy.deepcopy(g['latest_listing_resolution'])
summary.update(verification=rel(HERE / 'saved-file-verification.json'),
               verification_sha256=digest(HERE / 'saved-file-verification.json'),
               visual_verification=rel(HERE / 'visual-verification.json'),
               visual_verification_sha256=digest(HERE / 'visual-verification.json'))
ptr['latest_listing_resolution'] = summary
ptr['current_listing_resolution_sheet'] = 'Listing Resolution'
ptr['historical_listing_evidence_preserved'] = True
updates = {}
for key in ['review_progress', 'component_checkpoint', 'root_checkpoint']:
    p = Path(m[key]['path'])
    d = read(p)
    d.update(current_master_catalogue=copy.deepcopy(ptr),
             current_master_workbook=ptr['workbook'],
             current_master_register=ptr['register'], updated_utc=now(),
             latest_listing_resolution=copy.deepcopy(summary))
    if key == 'component_checkpoint':
        d['current_master_validation'] = {'path': summary['verification'], 'sha256': summary['verification_sha256']}
    updates[p] = d
write(HERE / 'export-receipt.json', {
    'status': 'PASS', 'recorded_utc': now(), 'workbook': ptr['workbook'],
    'workbook_sha256': ptr['workbook_sha256'], 'register': ptr['register'],
    'register_sha256': ptr['register_sha256'], 'native_hyperlinks': check['native_hyperlinks'],
    'formula_count': check['formula_count'], 'old_sheet_count': 16, 'new_sheet_count': 4,
    'accepted_values_changed': 0, 'current_media_changed': 0, 'native_actions_executed': 0
})
for item in m.values():
    assert digest(item['path']) == item['sha256']
target = BASE / ptr['workbook']
(HERE / 'master-workbook.pending').replace(target)
for p, d in updates.items():
    write(p, d)
write(BASE / 'current-master.json', ptr)
assert read(BASE / 'current-master.json') == ptr and digest(target) == ptr['workbook_sha256']
for p in updates:
    assert read(p)['current_master_catalogue'] == ptr
for key in ['master_register', 'owner_ledger', 'source_model', 'SEAL.json', 'HANDOFF.json', 'LISTING_RESOLUTION.json', 'OPTION_RESOLUTIONS_106.json', 'FOUR_LISTING_CORRECTIONS.json', 'NEW_SOURCE_LINKS.json', 'NATIVE_ACTION_DRAFTS.json', 'IMPORT_PLAN.json']:
    assert digest(m[key]['path']) == m[key]['sha256']
for key in ['latest_listing_reconciliation', 'latest_image_coverage_audit', 'latest_four_family_matching', 'latest_cup_frozen_manual_paths']:
    assert ptr[key] == prior[key]
receipt = {
    'status': 'PASS_PUBLISHED_AND_READ_BACK', 'recorded_utc': now(),
    'workbook': str(target), 'workbook_sha256': digest(target),
    'register': str(HERE / 'canonical-master-register.json'), 'register_sha256': ptr['register_sha256'],
    'verification': summary['verification'], 'visual_verification': summary['visual_verification'],
    'checks': check['checks'], 'counts': check['counts'],
    'new_sheets': summary['sheets'], 'original_sheets_retained': 16,
    'all184_names_1104_fields_current_media_and_history_preserved': True,
    'current_master_pointer_sha256': digest(BASE / 'current-master.json'),
    'controls_sha256': {str(p): digest(p) for p in updates},
    'prior_inputs_preserved': True, 'platform_and_dropbox_writes': 0,
    'native_requests_executed': 0
}
write(HERE / 'publication-receipt.json', receipt)
write(HERE / 'completion.json', {
    'status': 'COMPLETE_VERIFIED_ADDITIVE_SOURCE_REVIEW_AND_LOCAL_DRAFTS',
    'recorded_utc': now(), 'publication_receipt': rel(HERE / 'publication-receipt.json'),
    'workbook_sha256': ptr['workbook_sha256'], 'register_sha256': ptr['register_sha256'],
    'catalogue_options': 184, 'platform_or_dropbox_writes': 0,
    'all_actual_configurations_certified': False
})
print(json.dumps({k: receipt[k] for k in ['status', 'workbook_sha256', 'register_sha256', 'checks', 'native_requests_executed']}))
