"""Add one direct current finish-name Keep without changing the four-design crosswalk."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from import_source_followups_24_25 import canonical_messages

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch50'
SOURCE = ROOT / 'components/parallel-reviews/moonphase-four-silver-2026-10-19/owner-name-keep'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))
def write(path, value):
    path = Path(path); path.parent.mkdir(exist_ok=True, parents=True); temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)

paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json', 'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
docs = {k: read(v) for k, v in paths.items()}; design, variant = 'MOONPHASE-CURRENT-4', 'MOONPHASE-CURRENT-4:SILVER'
if (HERE / 'import-receipt.json').exists():
    assert docs['progress']['catalogue_alias_reviews'][variant]['identity_confirmed']
    print(json.dumps({'batch': 50, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); raise SystemExit
before, guards = copy.deepcopy(docs), {k: sha(v) for k, v in paths.items()}
package_path = SOURCE / 'IMPORT_PACKAGE.json'; digest = '80e484869fd3947a6166622571b5a76f462b73e2b5c31b584128993acaca64c5'
assert sha(package_path) == digest
package = read(package_path); frozen = []
def freeze(path, expected):
    path = Path(path); assert sha(path) == expected
    dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(exist_ok=True); dest.write_bytes(path.read_bytes()); frozen.append({'source': str(path), 'snapshot': rel(dest), 'sha256': expected, 'bytes': dest.stat().st_size})
    return rel(dest)
freeze(package_path, digest); freeze(package['manifest']['path'], package['manifest']['sha256'])
for name, expected in read(package['manifest']['path'])['files'].items(): freeze(SOURCE / name, expected)
decision = read(package['decision']['path']); review = read(SOURCE / 'REVIEW_BEFORE_KEEP.json')
parent_manifest = read(SOURCE / 'SOURCE_MANIFEST_BEFORE_KEEP.json')['files']
for name in ['PUBLIC_LISTING.html', 'PUBLIC_LISTING_READ.json', 'RECONCILIATION.json']: freeze(SOURCE.parent / name, parent_manifest[name])
evidence = [decision['preceding_assistant_card_evidence'], decision['authoritative_user_evidence']]
messages = canonical_messages([x | {'transcript': x['transcript_path']} for x in evidence], package['source_owner_session'])
assert [x['line'] for x in messages] == [27039, 27046] and messages[-1]['text'] == 'Keep “Moonphase Four — Silver (MP4)”'
assert '__001.jpg' in messages[0]['text']
heads = read(HERE / 'current-reference-check.json')['metadata']; head = next(x['file'] for x in heads if x.get('file')); folder = next(x['folder'] for x in heads if x.get('folder'))
assert all(head[k] == review['primary_image'][k] for k in ['id', 'name', 'rev', 'size', 'path_display']) and folder['id'] == review['primary_folder']['id']
image = review['image_evidence']; content = Path(image['path']).read_bytes(); assert len(content) == head['size'] and hashlib.sha256(content).hexdigest() == image['sha256']
blocks = b''.join(hashlib.sha256(content[i:i+4194304]).digest() for i in range(0, len(content), 4194304)); assert hashlib.sha256(blocks).hexdigest() == image['dropbox_content_hash']
original_snapshot = freeze(image['path'], image['sha256']); freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
u, p, cp, c = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
assert docs['root']['current_component_review'] == c and 'G243' in p['catalogue_design_aliases'][design]['reviewed_individual_groups'] and variant not in p['catalogue_alias_reviews']
assert cp['current_question_id'] == 'MCP4-VERDIGRIS-RUST-WEIGHT-01' and not cp['current_answer_recorded']
now = datetime.now(timezone.utc).isoformat(); approval = rel(HERE / 'identity-approval.json')
decision.update({'catalogue_variant_key': variant, 'identity_confirmed': True, 'name_approved': True, 'approval_record': approval, 'imported_utc': now, 'shared_master_import_performed': True, 'verified_authoritative_user': messages[-1]})
u['catalogue_finish_alias_decisions'].append(decision)
u['catalogue_alias_confirmation_counts']['Moonphases']['catalogue_finish_construction_aliases'] = len(u['catalogue_finish_alias_decisions'])
proposals = [{'proposal_id': x['id'], 'field': x['field'], 'display': x['display'], 'status': 'PUBLIC_LISTING_CLAIM;OWNER_UNAPPROVED;ACTUAL_SPECIMEN_APPLICABILITY_TO_CHECK', 'owner_approved': False, 'basis': 'Retrieved public listing at ' + x['source_checked_utc'] + '. ' + x['source_url'] + ' . Owner kept finish name only; no physical measurement, current stock or catalogue-price approval.'} for x in review['specification_review_items']]
ref = {'file_id': head['id'], 'folder_id': folder['id'], 'file_path': head['path_display'], 'folder_path': folder['path_display'], 'file_revision': head['rev'], 'file_bytes': head['size'], 'image_url': review['links']['image'], 'folder_url': review['links']['folder']}
scope = 'Owner kept Moonphase Four — Silver (MP4) for selected source001 under existing corrected public design Four. Historical BC-MP-1/BC-MP-5 and maker-code lineage retained; old public-numbering question is superseded. All six listing claims remain unapproved; no White/border weight transfer, manufacture, mould/stock count or scene authenticity inferred. Exact Shopify counterpart remains unconfirmed.'
node = {'catalogue_design_key': design, 'catalogue_variant_key': variant, 'canonical_name': decision['canonical_name'], 'identity_confirmed': True, 'identity_decision_display': 'Owner kept this Silver finish name', 'identity_approval': approval, 'proposals_approved': False, 'physical_specs_verified': False, 'existing_platform_match_confirmed': False, 'historical_component_ids': review['historical_component_ids'], 'historical_physical_maker_code_unresolved': True, 'current_dropbox_reference': ref, 'primary_image_id': head['id'], 'primary_folder_id': folder['id'], 'specification_proposals': proposals, 'scope': scope, 'source_offer_refs': ['O070'], 'platform_mapping': review['platform_mapping'], 'review_record': rel(HERE / 'finish-review.json'), 'root_verified_cached_original': {'snapshot': original_snapshot, 'sha256': image['sha256'], 'baseline_dropbox_content_hash': image['dropbox_content_hash'], 'new_original_download': False}, 'photo_coverage': {'on_wall': True, 'wider_room': False, 'rear': False, 'series_arrangement': False, 'contextual_images_available': True, 'context_image_type': 'Single panel on stone wall; no wider-room or rear/fixing view established in the30-source G243 packet', 'contextual_file_ids': [head['id']], 'installation_provenance': 'UNCONFIRMED', 'review_scope': 'Peer inspected30 cached previews; root inspected/rehashed cached source001 and checked current IDs/rev/size/parent. No new original-byte retrieval or whole-library absence claim.', 'physical_stock_count_inferred': False}}
p['catalogue_alias_reviews'][variant] = node
p['asset_assignment_overrides'][head['id']] = p['asset_assignment_overrides'].get(head['id'], {}) | {'file_id': head['id'], 'folder_id': folder['id'], 'canonical_design_key': design, 'canonical_catalogue_variant_key': variant, 'owner_name_approval': approval, 'assignment_status': 'OWNER_KEPT_EXACT_SOURCE001_MOONPHASE_FOUR_SILVER;SIX_LISTING_CLAIMS_UNAPPROVED'}
p['catalogue_group_overrides']['G243'] = p['catalogue_group_overrides'].get('G243', {}) | {'current_family': 'Moonphases', 'current_name': folder['name'], 'current_folder_id': folder['id'], 'current_folder_path': folder['path_display'], 'file_count': 30, 'component_ids': ['BC-MP-1', 'BC-MP-5'], 'role': 'Current Moonphase Four Silver references; historical source IDs retained', 'catalogue_finish_alias_record': approval, 'assignment_status': 'Owner kept source001 as Moonphase Four — Silver (MP4), current design MOONPHASE-CURRENT-4. Historical BC-MP-1/5 retained. Other views do not establish additional physical sculptures; six specifications and scene provenance unverified.'}
cp['pending_specification_reviews'].append({'component_id': design, 'size_finish_variant_id': variant, 'canonical_name': node['canonical_name'], 'identity_approved': True, 'specifications_approved': False, 'pending_fields': [x['field'] for x in proposals], 'review_record': node['review_record'], 'identity_approval': approval, 'image_link': ref['image_url'], 'folder_link': ref['folder_url']})
summary = {'batch': 50, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'CURRENT_DESIGN_FINISH_NAME_ONLY', 'catalogue_design_key': design, 'catalogue_variant_key': variant, 'new_current_finish_alias_name_keeps': 1, 'new_full_specification_approvals': 0, 'new_registered_BC_component_ids': [], 'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': digest, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'SILVER_FINISH_NAME_KEPT;SIX_LISTING_CLAIMS_UNAPPROVED'})
c['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
for target, key in [(p, 'latest_parallel_import'), (cp, 'last_parallel_import'), (c, 'last_parallel_import')]: target[key] = copy.deepcopy(summary)
for doc in docs.values(): doc['updated_utc'] = now
docs['root']['current_component_review'] = copy.deepcopy(c)
assert p['reviews'] == before['progress']['reviews'] and p['catalogue_design_aliases'] == before['progress']['catalogue_design_aliases']
assert all(p['catalogue_alias_reviews'][k] == v for k, v in before['progress']['catalogue_alias_reviews'].items())
assert u['identity_confirmation_counts'] == before['user']['identity_confirmation_counts'] and u['specification_approval_counts'] == before['user']['specification_approval_counts']
assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_')) and all(sha(paths[k]) == v for k, v in guards.items())
write(HERE / 'before-import.json', before); write(HERE / 'identity-approval.json', decision); write(HERE / 'finish-review.json', node); write(HERE / 'source-manifest.json', {'files': frozen, 'verified_messages': messages})
for k, path in paths.items(): write(path, docs[k])
write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'shared_after_sha256': {k: sha(v) for k, v in paths.items()}})
print(json.dumps({'batch': 50, 'status': 'APPLIED', 'current_finish_aliases': len(p['catalogue_alias_reviews']), 'new_specification_approvals': 0, 'root_weight_question_preserved': True}))
