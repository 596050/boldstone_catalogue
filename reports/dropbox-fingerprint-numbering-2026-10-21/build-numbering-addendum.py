import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone')
OUT = ROOT / 'reports/dropbox-fingerprint-numbering-2026-10-21'
CACHE = Path('/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
native = read(OUT / 'native-source-readback.json')
downloads = read(OUT / 'source-download-receipt.json')
for source in downloads['sources']:
    assert sha(source['local_path']) == source['sha256']
    assert native['current_primary_pdf_metadata'][source['id']]['file']['size'] == source['size']

rx = re.compile(r'(?i)\bfinger[ _-]*print(?:s)?\b|\bfp[ _-]?[12]\b')
texts = []
for p in sorted((CACHE / 'documents').glob('*.txt')):
    content = p.read_text(errors='replace')
    texts.append({'path': str(p), 'sha256': sha(p), 'numbered_fingerprint_text_match': bool(rx.search(content))})
manufacturing_rows = read(CACHE / 'Manufacturing_Sheet_Extract.json')
manufacturing_labels = read(CACHE / 'Manufacturing_Labelled_References.json')
manufacturing = {
    'row_extract': str(CACHE / 'Manufacturing_Sheet_Extract.json'),
    'row_extract_sha256': sha(CACHE / 'Manufacturing_Sheet_Extract.json'),
    'rows': len(manufacturing_rows),
    'numbering_text_matches': [x for x in manufacturing_rows if rx.search(json.dumps(x, ensure_ascii=False))],
    'labelled_reference_count': len(manufacturing_labels),
    'labelled_reference_matches': [x for x in manufacturing_labels if rx.search(json.dumps(x, ensure_ascii=False))],
    'source_revision_and_size_match_captured_document': True,
    'source_live_metadata': native['current_pair_and_legacy_group_metadata']['id:cnqzTNngPVsAAAAAAAuDJA'],
    'scope': 'Reviewed extracted cell/label text; no fresh visual classification of all 98 manufacturing pictures.'
}
lineage_path = Path('/Users/tprice/BoldstoneMigration/path-realignment-20261016/OLD-AND-NEW-NAMES.csv')
lineage = [x for x in csv.DictReader(lineage_path.open()) if '/Fingerprint/' in x['current_path']]
assert len(lineage) == 75

ledger_path = ROOT / 'sculpture-catalogue/components/reviews/user_classifications.json'
ledger = read(ledger_path)
decisions = [x for x in ledger['size_finish_variant_decisions'] if str(x.get('component_id', '')).startswith('BC-FP-')]
transcript_path = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl')
needed = {x['authoritative_user_evidence']['line'] for x in decisions}
actual = {}
with transcript_path.open() as f:
    for n, line in enumerate(f, 1):
        if n == 1:
            session = json.loads(line)
            assert session['type'] == 'session_meta'
            assert session['payload']['id'] == '01a13fbf-1cbc-7511-8416-cf339051083e'
        if n in needed:
            event = json.loads(line)
            assert event['type'] == 'response_item' and event['payload']['role'] == 'user'
            actual[n] = ''.join(c.get('text', '') for c in event['payload']['content'] if c.get('type') == 'input_text')
        if n >= max(needed):
            break
owner_evidence = []
for x in decisions:
    line = x['authoritative_user_evidence']['line']
    assert actual[line] == x['user_statement']
    owner_evidence.append({'component_id': x['component_id'], 'canonical_name': x['canonical_name'], 'user_statement': actual[line], 'session_id': session['payload']['id'], 'transcript_path': str(transcript_path), 'line': line, 'approval_record': x['approval_record']})

pointer = read(ROOT / 'sculpture-catalogue/current-master.json')
metadata = native['current_pair_and_legacy_group_metadata']
def native_url(fid):
    from urllib.parse import quote
    return 'https://www.dropbox.com/preview' + quote(metadata[fid]['file']['path_display'], safe='/')

report = {
    'schema': 'BOLDSTONE_FINGERPRINT_NUMBERING_SOURCE_ADDENDUM_V1',
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'SOURCE_COMPOSITION_NUMBERS_ESTABLISHED;INDIVIDUAL_MEMBER_NUMBERS_NOT_ESTABLISHED',
    'scope': 'Read-only investigation; no Dropbox, catalogue, ledger or specification writes. Additive local evidence only.',
    'current_master_at_audit': {k: pointer.get(k) for k in ['register', 'register_sha256', 'workbook', 'workbook_sha256']},
    'findings': [
        {'number': '1', 'number_scope': 'Whole proposed paired composition / design-reference group', 'appearance': 'Rough, offset/concentric relief pair', 'source': 'norwich-echo-fingerprint.pdf', 'page': 1, 'location': 'top-left composition labelled 1', 'matched_primary_file_id': 'id:cnqzTNngPVsAAAAAAAyhPw', 'match_basis': 'Direct visual match of both relief geometries. PDF removes the brick/background margins; no identical-byte or same-cast claim.', 'current_image_url': native_url('id:cnqzTNngPVsAAAAAAAyhPw')},
        {'number': '2', 'number_scope': 'Whole proposed paired composition / design-reference group', 'appearance': 'Established standard concentric pair', 'source': 'norwich-echo-fingerprint.pdf', 'page': 1, 'location': 'top-right composition labelled 2', 'matched_primary_file_id': 'id:cnqzTNngPVsAAAAAAAyhSQ', 'match_basis': 'Direct visual match of the established two-panel concentric composition. Both current historical Left/Right component records occur within this one numbered composition.', 'current_image_url': native_url('id:cnqzTNngPVsAAAAAAAyhSQ')}
    ],
    'corroboration': [
        {'source': 'norwich-series-1-2.pdf', 'page': 1, 'finding': 'Labels 1 and 2 each apply to a complete four-panel array of the respective rough and standard concentric pattern.'},
        {'source': 'norwich-series-3-4.pdf', 'page': 1, 'finding': 'Labels 1 and 2 apply to four-panel arrays; 1.1 and 2.1 apply to three-panel arrays. These are whole-composition labels, not individual member codes.'},
        {'source': 'all-context-pages.jpg', 'finding': 'All 15 remaining PDF pages rendered and inspected as contact-sheet context views; no individual Fingerprint 1/2 member labels found.'}
    ],
    'source_heading_guard': 'The sheets explicitly describe pattern inspiration suggestions. The numbers are source proposal/composition labels, not independently certified manufacturer mould codes, physical cast identities, exact dimensions or current stock.',
    'component_crosswalk': [
        {'component_id': 'BC-FP-LEFT', 'historical_position': 'Left member of the standard pair', 'supported_source_composition_number': '2', 'individual_member_number': None},
        {'component_id': 'BC-FP-RIGHT', 'historical_position': 'Right member of the standard pair', 'supported_source_composition_number': '2', 'individual_member_number': None}
    ],
    'white_finish_guard': {'file_id': 'id:cnqzTNngPVsAAAAAAAyk7Q', 'current_image_url': native_url('id:cnqzTNngPVsAAAAAAAyk7Q'), 'basis': 'Matching standard concentric geometry and historical Fingerprint 2 White filename. The numbered project witness is Verdigris; no independently labelled White manufacturing/member code was found.'},
    'historical_lineage': {'path': str(lineage_path), 'sha256': sha(lineage_path), 'rows': lineage, 'old_group_1_file_count': sum('fingerprint-1-verdigris__' in x['current_path'] for x in lineage), 'scope': 'Historic 1 and 2 labels apply to media groups containing paired and multi-panel images; they do not prove Left=1 / Right=2.'},
    'owner_statements_verified': owner_evidence,
    'current_numbered_name_instruction': {'text': 'Keep 1 and 2 designations and matching instead of Left and Right otherwse match them and continue', 'source': 'Active owner chat, preceding Step07', 'finding': 'Preference for numeric names; no individual member-to-number mapping specified.'},
    'negative_checks': {'captured_document_texts': texts, 'manufacturing': manufacturing, 'website_archive': {'parent_id': native['source_website_archive_parent']['folder']['id'], 'entries': len(native['source_website_archive_inventory']['entries']), 'pagination_exhausted': not native['source_website_archive_inventory']['has_more'], 'fingerprint_labelled_filenames': [x['name'] for x in native['source_website_archive_inventory']['entries'] if re.search('finger|print', x['name'], re.I)], 'scope': 'Filename inventory only, not a fresh visual review of all website-export images.'}},
    'search_limitation': 'Native title/content searches missed the current primary project PDFs. Direct enumeration of the known Norwich project parent found all three. Negative search results are not proof of source absence.',
    'step07_qualification': {'sealed_overlay': 'reports/dropbox-wall-structure-2026-10-20/step-07-matching-current-overlay.json', 'sealed_overlay_sha256': '697684bb695cf140b165f202bda42fe55747172a492ab4425945e1305231669c', 'finding': 'The new 1 and 2 pair-folder wording in Step07 was an unordered individual-member convention. The source shows that 1 and 2 already label distinct whole compositions. The three standard-pair folders contain composition 2 references, so their wording now needs an owner-visible correction/convention decision. Do not rewrite sealed Step07 history.', 'source_qualified_folder_correction_candidates_not_applied': [{'file_id': 'id:cnqzTNngPVsAAAAAAAyhQw', 'current_name': 'Fingerprint 1 and 2 Verdigris', 'source_consistent_candidate': 'Fingerprint 2 Verdigris'}, {'file_id': 'id:cnqzTNngPVsAAAAAAAyhIA', 'current_name': 'Fingerprint 1 and 2 White', 'source_consistent_candidate': 'Fingerprint 2 White'}, {'file_id': 'id:cnqzTNngPVsAAAAAAAykGg', 'current_name': 'Fingerprint 1 and 2 White In Situ', 'source_consistent_candidate': 'Fingerprint 2 White In Situ'}]},
    'minimal_owner_decision_if_needed': 'Keep Fingerprint 1 for the rough-pattern whole design and Fingerprint 2 for the concentric whole design, matching the project sheets, with individual member labels decided separately?',
    'superseded_question': 'Which side of the standard concentric pair is Fingerprint 1? This is not answerable from these project labels: the whole standard pair is source composition 2.',
    'retained_limits': ['No new individual product IDs or physical counts.', 'No specification transfer between rough composition 1 and standard composition 2.', 'No authenticated client installation inferred from project inspiration scenes.', 'No per-panel numbering convention invented.'],
    'sources': downloads['sources'],
    'input_evidence': {'native_source_readback_sha256': sha(OUT / 'native-source-readback.json'), 'download_receipt_sha256': sha(OUT / 'source-download-receipt.json'), 'owner_ledger_sha256': sha(ledger_path)},
    'Dropbox_mutations': 0,
    'shared_master_writes': 0,
    'new_shared_links': 0
}
dest = OUT / 'numbering-source-addendum.json'
dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'path': str(dest), 'sha256': sha(dest), 'source_pdfs': len(downloads['sources']), 'source_pages_reviewed': 18, 'verified_owner_identity_statements': len(owner_evidence), 'historical_Fingerprint_files': len(lineage), 'captured_document_texts_checked': len(texts), 'new_Dropbox_or_master_writes': 0}))
