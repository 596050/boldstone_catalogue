"""Read the coordinated catalogue queue; write only this session's link report."""
import argparse
import contextlib
import hashlib
import html
import io
import json
import runpy
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
ROOT = B.parent
SOURCE = ROOT / 'reports/catalogue-terminal-walkthrough-20261024/walkthrough.py'
PENDING = B / 'components/reconciliation/decowaves2-owner-design-group-master-2026-10-24'
PAIR = ['BSI-FE830AE502C3', 'BSI-837E9B0B3B36']
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
esc = lambda x: html.escape(str(x), quote=True)
parser = argparse.ArgumentParser()
parser.add_argument('--item', type=int)
parser.add_argument('--write-report', action='store_true')
args = parser.parse_args()
source_sha = sha(SOURCE)
old_argv = sys.argv
try:
    sys.argv = [str(SOURCE), '--item', '1']
    with contextlib.redirect_stdout(io.StringIO()):
        state = runpy.run_path(str(SOURCE), run_name='__main__')
finally:
    sys.argv = old_argv
assert sha(SOURCE) == source_sha, 'Shared walkthrough changed during read'
p, g = state['pointer'], state['g']
assert read(B / 'current-master.json') == p, 'Current pointer changed during read; run again'
assert sha(B / p['register']) == p['register_sha256']
assert sha(B / p['workbook']) == p['workbook_sha256']
items = state['items']
published = bool(p.get('latest_decowaves2_owner_design_equivalence_import'))
groups = p['current_working_design_group_projection']['grouped_working_design_identity_count']
for item in items:
    item['evidence_scope'] = 'Published catalogue and retained verification records. No new binary review or physical verification in this read.'
    if item['title'].startswith('Decowaves1'):
        item['details']['Owner approval'] = 'The exact number1 design pair was confirmed separately. The number2 question also has its own recorded answer.'
        item['details']['Working groups after confirmed equivalence'] = groups
for oid in PAIR:
    if any(x['option_id'] == oid and x['title'].startswith('Decowaves2') for x in items):
        continue
    option = next(o for o in g['options'] if o['product_id'] == oid)
    items.append({'title': 'Decowaves2 owner-confirmed design relationship',
                  'status': 'Published and verified' if published else 'Exact owner answer recovered; candidate verified; main session owns publication',
                  'option_id': oid, 'name': option['name'], 'image': option['image_url'],
                  'containing_folder': option['folder_url'], 'file_id': option['file_id'], 'folder_id': option['folder_id'],
                  'details': {'Owner answer': 'Two repeated wYes messages to the same presented pair; recorded as one affirmative design relationship.',
                              'Candidate design groups': 110, 'Retained component IDs': 112, 'Active sale options': 188,
                              'Scope': 'Design relationship only. Separate finish specifications, prices, stock evidence and existing Terracotta photo scope retained.'},
                  'review': str(B / 'outputs' / PENDING.name / 'decowaves2-owner-design-equivalence.html'),
                  'evidence_scope': 'Four stable-ID metadata reads confirmed the two files and their containing folders after the offline tests. No image bytes downloaded or changed.'})
history_lane = B / 'components/parallel-reviews/wall-circle-reference-history-01a16dbc-20261024T143807Z'
history_seal = read(history_lane / 'sealed-findings.json')
assert history_seal['status'] == 'SEALED_VERIFIED_READ_ONLY_FINDINGS'
for frozen in history_seal['files']:
    assert sha(frozen['path']) == frozen['sha256']
history_findings = read(history_lane / 'findings.json')
for observation in history_findings['rows']:
    option = next(o for o in g['options'] if o['product_id'] == observation['option_id'])
    assert option['file_id'] == observation['file_id'] and option['folder_id'] == observation['folder_id']
    assert option['master_fields'] == observation['canonical_option_guard']['master_fields']
    for item in items:
        if item['option_id'] != observation['option_id']:
            continue
        item['status'] = 'Saved image ID marked deleted in Dropbox history; exact local original readable'
        item['image'] = observation['existing_local_original']['path']
        item['image_kind'] = 'Existing local original, hash verified'
        item['review'] = str(history_lane / 'review.html') + '#' + observation['option_id']
        item['details'] = {'Server deletion recorded in UTC': observation['server_deleted_utc'],
                           'Available revision entries': observation['available_revision_count'],
                           'Exact local original': observation['existing_local_original'],
                           'Current folder files, unselected': observation['current_folder_files'],
                           'Scope': 'Same historical selected image bytes remain accessible locally. No remote restoration, alternate selection, identity decision or owner-hold release.'}
        item['evidence_scope'] = 'Fresh available-history response for the exact stable ID, verified current folder and complete direct-child listing. Existing local original fully decoded; SHA-256, Dropbox hash and size checked. Deletion actor and reason remain unknown.'
move_base = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Moonspirals'
from urllib.parse import quote
source_folder = 'https://www.dropbox.com/home' + quote(move_base + '/Moonspiral 2 White In Situ', safe='/')
target_folder = 'https://www.dropbox.com/home' + quote(move_base + '/Moonspiral 1 and Moonspiral 2 White In Situ', safe='/')
items.append({'title': 'Moonspirals three-file proposal', 'status': 'Proposal remains unapplied in the directory session',
              'option_id': '', 'name': 'Three photographs containing Moonspiral 1 and Moonspiral 2',
              'image': source_folder + '?preview=moonspirals__moonspiral-2-white-in-situ__012.JPG',
              'containing_folder': source_folder, 'file_id': '', 'folder_id': '',
              'details': {'Photographs': ['moonspirals__moonspiral-2-white-in-situ__012.JPG', 'moonspirals__moonspiral-2-white-in-situ__013.JPG', 'moonspirals__moonspiral-2-white-in-situ__014.JPG'],
                          'Proposed destination': target_folder,
                          'Scope': 'Recorded proposal from the directory session; no movement or approval inferred from this continuation.'},
              'review': str(ROOT / 'reports/dropbox-wall-only-moonspirals-moonwave-seaweed-review-20261024T015730Z/review-three-proposed-moonspirals-pair-moves.html'),
              'evidence_scope': 'Read existing proposal; no new Dropbox content action.'})
moon_lane = ROOT / 'reports/dropbox-moonspirals-three-pair-moves-20261024T143451Z'
moon_seal = read(moon_lane / 'execution-seal.json')
assert moon_seal['status'] == 'COMPLETE_VERIFIED'
for frozen in moon_seal['receipts']:
    assert sha(frozen['path']) == frozen['sha256']
moon_validation = read(moon_lane / 'validation.json')
moon_overlay = read(moon_lane / 'current-reference-overlay.json')
moon_publication = B / 'components/reconciliation/moonspirals-three-pair-navigation-master-2026-10-24/publication-receipt.json'
moon_import_published = moon_publication.exists() and read(moon_publication)['status'] == 'PASS_PUBLISHED_AND_READ_BACK'
assert moon_validation['approved_moves_completed'] == len(moon_overlay['specific_file_maps']) == 3
assert moon_validation['all148_original_ID_name_format_size_client_time_and_bytes_preserved']
for item in items:
    if item['title'] != 'Moonspirals three-file proposal':
        continue
    moved = sorted(moon_overlay['specific_file_maps'], key=lambda x: x['new_path'])
    current_folder = 'https://www.dropbox.com/home' + quote(str(Path(moved[0]['new_path']).parent), safe='/')
    item.update(title='Moonspirals three approved pair photographs',
                status='Native moves and catalogue import published and verified' if moon_import_published else 'Native moves completed and verified by the directory session; catalogue import owned by the main session',
                image=current_folder + '?preview=' + quote(Path(moved[0]['new_path']).name, safe=''),
                containing_folder=current_folder,
                review=str(moon_lane / 'all-current-moonspirals-image-folder-links.html'),
                details={'Approved moves completed': 3, 'Source folder files after moves': moon_validation['source_after'],
                         'Destination folder files after moves': moon_validation['destination_after'],
                         'Family originals retained and byte verified': moon_validation['family_originals'],
                         'Current moved references': [{'file_id': x['file_id'], 'image_url': current_folder + '?preview=' + quote(Path(x['new_path']).name, safe='')} for x in moved],
                         'Scope': 'Completed work from the directory session. This reader performed no native actions.'},
                evidence_scope='Terminal per-entry receipts, complete current family readback and exact execution seal verified. Source22 to19 and destination28 to31;148 originals retained.')
sample = next(o for o in g['options'] if o['product_id'] == 'BSI-3635E3DC3434')
missing = p['current_missing_picture_lists']
items.append({'title': 'Owner holds and remaining physical evidence', 'status': 'Owner holds retained; actual physical details remain optional pending input',
              'option_id': sample['product_id'], 'name': 'Acanthus physical question and retained photo holds',
              'image': sample['image_url'], 'containing_folder': sample['folder_url'],
              'file_id': sample['file_id'], 'folder_id': sample['folder_id'],
              'details': {'Paused context cases': missing['owner_held_in_situ_cases'], 'Paused Series cases': missing['owner_held_series_cases'],
                          'Deferred individual identity cases': 1, 'Active photograph requests': 0,
                          'Physical checklist': '188 options and752 physical field groups; no new measurements supplied in this continuation.',
                          'Question owner': 'This session only: Acanthus One Leaf Left Pewter actual measurements, weight, material or fitted fixing.',
                          'Held context list': str(B / missing['held_in_situ_cases_csv']),
                          'Held Series list': str(B / missing['held_series_cases_csv'])},
              'review': str(B / p['current_specification_verification']['review']),
              'evidence_scope': 'Accepted working estimates remain estimates. No missing-context prompts were restarted.'})
case_lane = H / 'case-normalization-handoff-20261024T165515Z'
case_seal = read(case_lane / 'sealed-handoff.json')
assert case_seal['status'] == 'PASS_GUARDED_TWELVE_URL_FIELDS_ONLY'
for frozen in case_seal['files']:
    assert sha(frozen['path']) == frozen['sha256']
case_packet = read(case_lane / 'handoff.json')
case_option_ids = {change['option_id'] for change in case_packet['rows']}
items = [item for item in items if item['option_id'] not in case_option_ids]
case_status = []
for change in case_packet['rows']:
    option = next(o for o in g['options'] if o['product_id'] == change['option_id'])
    assert option['file_id'] == change['expected_file_id']
    assert option['folder_id'] == change['expected_folder_id']
    applied = all(option[key] == change['proposed'][key] for key in ['image_url', 'folder_url'])
    if not applied:
        assert all(option[key] == change['before'][key] for key in ['image_url', 'folder_url'])
    status = 'Published in current catalogue' if applied else 'Guarded correction queued by the main publisher; not applied'
    case_status.append({'option_id': option['product_id'], 'status': status})
    items.append({'title': 'URL capitalization: ' + option['name'], 'status': status,
                  'option_id': option['product_id'], 'name': option['name'],
                  'image': change['proposed']['image_url'], 'image_kind': 'Image at observed path',
                  'containing_folder': change['proposed']['folder_url'],
                  'file_id': option['file_id'], 'folder_id': option['folder_id'],
                  'details': {'Saved catalogue URLs': {key: option[key] for key in ['image_url', 'folder_url']},
                              'Original metadata observation times': [e['recorded_utc'] for e in change['metadata_observations']],
                              'Scope': 'Capitalization in two existing URLs. Same selected IDs and immediate parent; URL route and query filename retained. No native rename or image-role change.',
                              'Publisher': case_packet['publisher_thread']},
                  'review': str(case_lane / 'index.html') + '#' + option['product_id'],
                  'evidence_scope': 'Uses sealed earlier native metadata with its original clocks. This report refresh performs local reads only; no new live metadata, image download or physical verification.'})
moonwave_plan_lane = ROOT / 'reports/dropbox-moonwave-wide-only-revised-plan-20261024T165319Z'
moonwave_plan = read(moonwave_plan_lane / 'proposed-ten-moonwave-brick-wall-moves.json')
assert moonwave_plan['status'] == 'PROPOSED_NOT_APPLIED'
assert moonwave_plan['owner_criterion_is_not_exact_move_approval']
moonwave = next(o for o in g['options'] if o['family'] == 'Moonwave')
items.append({'title': 'Moonwave revised brick-wall filing review',
              'status': 'Ten-move plan prepared by the directory session; execution not established by this reader',
              'option_id': moonwave['product_id'], 'name': moonwave['name'],
              'image': moonwave['image_url'], 'containing_folder': moonwave['folder_url'],
              'file_id': moonwave['file_id'], 'folder_id': moonwave['folder_id'],
              'details': {'Owner criterion': moonwave_plan['owner_criterion_verbatim'],
                          'Earlier nine-photo plan': 'Withdrawn; do not apply or use its proposed counts.',
                          'Replacement plan': 'Ten proposed moves. The directory session owns its existing approval question and execution.',
                          'Current image and context selections': 'Primary033 and context005 retained; no new role or specification decision.'},
              'review': str(moonwave_plan_lane / 'review-ten-proposed-brick-wall-moves.html'),
              'evidence_scope': 'Existing directory-session review and immutable proposal read locally. This reader neither approves nor executes native moves.'})
moonwave_execution_lane = ROOT / 'reports/dropbox-moonwave-ten-approved-moves-20261024T182423Z'
moonwave_done = (moonwave_execution_lane / 'execution-seal.json').exists()
moonwave_imported = False
if moonwave_done:
    moonwave_execution_seal = read(moonwave_execution_lane / 'execution-seal.json')
    assert moonwave_execution_seal['status'] == 'COMPLETE_VERIFIED'
    for frozen in moonwave_execution_seal['receipts']:
        assert sha(frozen['path']) == frozen['sha256']
    moonwave_validation = read(moonwave_execution_lane / 'validation.json')
    moonwave_overlay = read(moonwave_execution_lane / 'current-reference-overlay.json')
    assert moonwave_validation['owner_approved_moves_completed'] == len(moonwave_overlay['specific_file_maps']) == 10
    assert moonwave_validation['all99_original_ID_name_format_size_client_time_and_bytes_preserved']
    assert moonwave_validation['selected_primary033_and_context005_IDs_paths_parents_unchanged']
    own_file = next(m for m in moonwave_overlay['specific_file_maps'] if m['file_id'] == 'id:cnqzTNngPVsAAAAAAArp1g')
    own_folder_url = 'https://www.dropbox.com/home' + quote(str(Path(own_file['new_path']).parent), safe='/')
    offer_reference = next(edge['current_primary_reference'] for edge in g['source_offer_edges']
                           if edge.get('current_primary_reference', {}).get('file_id') == own_file['file_id'])
    moonwave_imported = (offer_reference['file_id'] == own_file['file_id'] and
                         offer_reference['folder_id'] == own_file['new_parent_id'] and
                         offer_reference['folder_url'] == own_folder_url)
    for item in items:
        if item['title'] != 'Moonwave revised brick-wall filing review':
            continue
        item.update(title='Moonwave ten approved file moves',
                    status='Native execution verified; current source-offer navigation imported' if moonwave_imported else 'Native execution verified; catalogue import pending with main publisher',
                    review=str(moonwave_execution_lane / 'all-current-moonwave-image-folder-links.html'),
                    details={'Approved file moves': 10, 'White folder files after verified execution': moonwave_validation['White_after'],
                             'In Situ folder files after verified execution': moonwave_validation['InSitu_after'],
                             'Original files retained and byte verified by the directory session': moonwave_validation['family_originals'],
                             'Earlier nine-photo plan': 'Remains withdrawn. The separately approved ten-file plan was executed.',
                             'Selected image roles': 'Primary033 and context005 IDs, paths and parents remain unchanged.',
                             'Verification time UTC': moonwave_validation['verified_utc']},
                    evidence_scope='All26 receipt-file checksums in the directory execution seal verified locally. Its recorded validation covers10 freshly downloaded moved originals and89 unchanged originals rehashed against fresh native hashes. This reader made no new native calls.')
app_demo = read(H / 'application-link-demo.json')
for frozen in app_demo['files']:
    assert sha(frozen['path']) == frozen['sha256']
app_html = next(frozen['path'] for frozen in app_demo['files'] if frozen['kind'] == 'html')
app_sample = case_packet['rows'][0]
items.append({'title': 'Read-only application report navigation',
              'status': 'Implemented;85 fake-adapter tests and lint passed',
              'option_id': app_sample['option_id'], 'name': 'Recorded six-option metadata example',
              'image': app_sample['proposed']['image_url'], 'containing_folder': app_sample['proposed']['folder_url'],
              'file_id': app_sample['expected_file_id'], 'folder_id': app_sample['expected_folder_id'],
              'details': {'Application change': 'HTML batch reports now show observed file and containing-folder links. Target/keeper pairs and folder descendants stay separate. Successful binary checks use the independent post-read metadata.',
                          'Verification': '85 offline tests passed in8.17s; lint passed.453 preserved-package checksums and350 fixed batches with11490 rows verified offline.',
                          'Recorded example': 'Six rows derived from sealed prior metadata; no new fixed-batch attempt or active database used.',
                          'Full qualified specification walkthrough': str(H / 'case-specifications.html')},
              'review': app_html,
              'evidence_scope': 'Local rendering and fake-adapter validation only. No new Dropbox read, binary download, shared link, database write or native mutation in the example.'})
dune_lane = B / 'components/parallel-reviews/o002-o004-source-photo-review-01a16dbc-20261024'
dune_seal = read(dune_lane / 'sealed-handoff.json')
assert dune_seal['status'] == 'SEALED_READ_ONLY_REVIEW'
for filename, expected in dune_seal['files'].items():
    assert sha(dune_lane / filename) == expected
dune_review = read(dune_lane / 'review.json')
for case in dune_review['cases']:
    option = next(o for o in g['options'] if o['product_id'] == case['option_id'])
    option_sha = hashlib.sha256(json.dumps(option, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    assert option_sha == case['whole_option_sha256'], 'Dune option changed since sealed source review'
    if any(x['option_id'] == case['option_id'] and str(dune_lane) in x.get('review', '') for x in items):
        continue
    items.append({'title': 'Dune Ripple saved source comparison: ' + case['offer_ref'],
                  'status': 'Completed locally;73 integrity and source checks passed',
                  'option_id': case['option_id'], 'name': case['name'],
                  'image': case['image_url'], 'containing_folder': case['folder_url'],
                  'file_id': case['file_id'], 'folder_id': case['folder_id'],
                  'details': {'Finding': case['finding'],
                              'Saved source gallery frames': len(case['saved_public_gallery']),
                              'Complete qualified working fields retained': len(case['working_fields']),
                              'Source product/variant/SKU': [case[k] for k in ['native_product_id', 'native_variant_id', 'sku']],
                              'Source boundaries': case['scope_notes']},
                  'review': str(dune_lane / 'index.html') + '#' + case['offer_ref'],
                  'evidence_scope': 'Saved gallery photos and two selected originals rehashed and decoded locally. Photo correspondence does not verify cast measurements, composition, stock or fitted hardware. No new downloads, native/platform writes or owner questions.'})
for number, item in enumerate(items, 1):
    if args.item is not None and args.item != number:
        continue
    print(f"ITEM {number}: {item['title']}\n{item['status']}\n{item['name']}\nImage: {item['image']}\nFolder: {item['containing_folder']}\nReview: {item['review']}")
assert args.item is None or 1 <= args.item <= len(items), 'Unknown item'
snapshot = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'published_pointer': str(B / 'current-master.json'),
            'register_sha256': p['register_sha256'], 'workbook_sha256': p['workbook_sha256'],
            'shared_walkthrough_source_sha256': source_sha, 'active_options': p['current_option_count'],
            'retained_component_ids': 112, 'published_working_design_groups': groups, 'number2_published': published,
            'items': items, 'offline_validation': {'application_fake_tests_passed': 85, 'application_fake_tests_seconds': 8.17, 'preserved_handover_tests_passed_previously': 18, 'preserved_checksums': 453, 'fixed_batches': 350, 'fixed_batch_rows': 11490},
            'live_validation': {'prior_decowaves2_pair': {'metadata_reads': 4, 'files': 2, 'folders': 2, 'binary_downloads': 0},
                                'prior_wall_circle_observation': history_findings['live_reads'], 'live_sandbox_tested': False},
            'dropbox_content_writes': 0, 'platform_writes': 0, 'shared_publication_owner': '01a144ab-1a7c-7223-a403-73a4d53d70ff'}
snapshot['current_refresh_live_reads'] = 0
snapshot['dune_source_review'] = {'path': str(dune_lane / 'sealed-handoff.json'),
    'sha256': sha(dune_lane / 'sealed-handoff.json'), 'existing_options': 2,
    'full_qualified_working_fields': 12, 'source_csv_fields': 18,
    'checks_passed': 73, 'new_native_or_platform_bindings': 0}
snapshot['case_normalization_followup'] = {'items': case_status, 'sealed_handoff': str(case_lane / 'sealed-handoff.json'),
    'sha256': sha(case_lane / 'sealed-handoff.json'), 'publisher_queue': str(ROOT / 'reports/catalogue-terminal-walkthrough-20261024/queued-native-case-corrections.json')}
snapshot['wall_circle_history_findings'] = {'path': str(history_lane / 'sealed-findings.json'), 'sha256': sha(history_lane / 'sealed-findings.json'), 'locally_readable_exact_originals': 2}
snapshot['native_moves_observed_from_directory_session'] = {'scope': 'Moonspirals only; Moonwave execution is recorded separately', 'count': 3, 'execution_seal': str(moon_lane / 'execution-seal.json'), 'sha256': sha(moon_lane / 'execution-seal.json')}
if moonwave_done:
    snapshot['verified_moonwave_execution'] = {'moves': 10, 'execution_seal': str(moonwave_execution_lane / 'execution-seal.json'),
        'sha256': sha(moonwave_execution_lane / 'execution-seal.json'), 'source_offer_navigation_imported': moonwave_imported,
        'White_after': moonwave_validation['White_after'], 'InSitu_after': moonwave_validation['InSitu_after'],
        'family_originals': 99, 'verified_utc': moonwave_validation['verified_utc']}
withdrawal = pointer_withdrawal = p.get('latest_moonwave_proposal_withdrawal')
if withdrawal:
    assert withdrawal['native_moves_applied'] == 0
    snapshot['current_moonwave_followup'] = {'withdrawn_prior_nine_photo_proposal': {key: withdrawal[key] for key in ['status', 'owner_source_timestamp_utc', 'native_moves_applied', 'replacement_review_owner_thread', 'current_role_selections_and_specs_changed']},
        'replacement_ten_file_execution': snapshot.get('verified_moonwave_execution', {'status': 'Execution not established by this reader'})}
if args.write_report:
    cards = []
    for number, item in enumerate(items, 1):
        rows = ''.join('<tr><th>' + esc(k) + '</th><td>' + esc(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) + '</td></tr>' for k, v in item['details'].items())
        image_label = item.get('image_kind', 'Saved image reference — unresolved' if item['option_id'] in ['BSI-D5A939264C82', 'BSI-65520F070145'] else 'Image')
        cards.append('<article id="item-' + str(number) + '"><h2>' + str(number) + '. ' + esc(item['title']) + '</h2><p class="status">' + esc(item['status']) + '</p><p>' + esc(item['name']) + '</p><p><a href="' + esc(item['image']) + '">' + image_label + '</a> · <a href="' + esc(item['containing_folder']) + '">Containing folder</a> · <a href="' + esc(item['review']) + '">Detailed evidence</a></p><table>' + rows + '</table><p class="scope">' + esc(item['evidence_scope']) + '</p></article>')
    title = 'Terminal catalogue continuation'
    intro = f"{p['current_option_count']} active sale options,112 retained component IDs and{groups} published working design groups. "
    intro += 'Number2 is published.' if published else 'The number2 answer is recovered and verified; its candidate is awaiting publication by the main session.'
    moonwave_note = '<p>Moonwave: the earlier nine-photo filing proposal remains withdrawn. The directory session prepared a separate ten-move review using the owner criterion that brick-wall photographs count as In Situ except close framing. It owns that review and its existing approval question; this reader records no move execution.</p>' if withdrawal else ''
    if moonwave_done:
        moonwave_note = '<p>Moonwave: the separately approved ten-file plan was executed and byte verified by the directory session. Current verified folder counts are84 White and15 In Situ; all99 originals remain. The earlier nine-photo proposal stays withdrawn. ' + ('The current source-offer navigation is imported.' if moonwave_imported else 'The main session owns the pending catalogue import.') + '</p>'
    validation_note = '<p>This refresh reads local artifacts only. Current application validation:85 fake-adapter tests passed in8.17s and lint passed. The offline handover verifier checked453 files and350 fixed batches with11490 rows. Earlier18 preserved-handover tests, scoped Wall Circle history/folder observations and local-original integrity checks, and the Decowaves2 metadata check remain separate. These are not new live checks in this report refresh. The sealed selected-reference audit retains254 fresh metadata observations and92 reused observations with their original clocks. Live sandbox integration was not tested.</p>'
    text = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>' + title + '</title><style>body{font:17px/1.5 Arial,sans-serif;max-width:1080px;margin:40px auto;padding:0 24px;color:#222}h1{font-size:30px}h2{font-size:22px}a{color:#15549b}article{padding:24px 0;border-top:1px solid #ccc}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #ddd;padding:9px;overflow-wrap:anywhere}th{width:30%}.status{font-weight:bold}.scope{color:#555;font-size:15px}</style></head><body><h1>' + title + '</h1><p>' + esc(intro) + '</p>' + moonwave_note + '<p>Reviewed on ' + esc(snapshot['recorded_utc']) + '. Image and folder links are kept with every item. All existing photograph holds remain. The catalogue is not a physical stock count.</p>' + validation_note + ''.join(cards) + '</body></html>'
    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []
        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self.links.append(dict(attrs).get('href', ''))
    parsed = Links()
    parsed.feed(text)
    for url in parsed.links:
        if not url.startswith('https:'):
            assert Path(url.split('#')[0]).is_file(), 'Missing local review ' + url
    (H / 'index.html').write_text(text)
    (H / 'walkthrough-state.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(H / 'index.html'), 'items': len(items), 'number2_published': published, 'published_design_groups': groups, 'local_link_checks': 'PASS'}))
