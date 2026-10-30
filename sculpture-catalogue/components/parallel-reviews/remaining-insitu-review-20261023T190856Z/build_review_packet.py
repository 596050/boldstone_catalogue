import datetime
import hashlib
import html
import json
from pathlib import Path
from urllib.parse import quote

J = Path(__file__).parent
B = J.parents[2]
load = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
save = lambda name, data: (J / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
manifest = load(J / 'manifest.json')
reg_path = Path(manifest['baseline_register'])
assert sha(reg_path) == manifest['baseline_register_sha256']
reg = load(reg_path)
options = {x['product_id']: x for x in reg['options']}
coverage = {x['option_id']: x for x in load(reg_path.with_name('image-coverage-current.json'))['coverage']}
baseline = load(J / 'baseline-insitu-gaps.json')
plan = load(J / 'active-insitu-review-plan.json')
selected = load(J / 'selected-display-candidates.json')
checks = {x['id']: x for x in load(J / 'candidate-original-checks.json')['entries']}
rust = load(J / 'rust-current-original-evidence.json')
checks.update({x['id']: x for x in rust['entries']})
metadata = load(J / 'candidate-file-metadata.json')
metadata.update({x['file']['id']: x for x in rust['meta']})

# Reuse disjoint, complete current listings shared by the series reviewer.
family_listings = load(J / 'current-family-listings.json')['families']
a_dir = B / 'components/parallel-reviews/series-gap-review-20261023T190939Z'
a_lists = load(a_dir / 'current-family-listings.json')
for family in ['Acanthus', 'Frozen Fish', 'Moon Crater Phase', 'Moonphases', 'Egyptian Palm']:
    pages = a_lists['families'][family]
    if family == 'Frozen Fish':
        pages = [load(a_dir / 'frozen-fish-listing-retry.json')]
    assert pages and pages[-1]['has_more'] is False
    family_listings[family] = {'entries': [e for p in pages for e in p['entries']], 'has_more': False}
entries = {}
folders = {}
for family, data in family_listings.items():
    assert data['has_more'] is False
    for e in data['entries']:
        entries[e['file_id']] = e
        if e['object_type'] == 'folder':
            folders[e['path'].lower()] = e

a_authority = B / 'components/parallel-reviews/installation-review-coordination-20261023T192240Z/owner-instruction-event.jsonl'
ae = load(a_authority)
assert hashlib.sha256(a_authority.read_bytes().rstrip(b'\r\n')).hexdigest() == 'a81946b44a3c4ad7aad945f5c1b81a80a39893551e6f9296389068ad6b1f8822'
assert ae['payload']['item']['type'] == 'UserMessage'
authority = {
    'owner_task_instruction': {'path': str(J / 'owner-instruction-evidence.json'), 'sha256': sha(J / 'owner-instruction-evidence.json')},
    'later_owner_completion': {'path': str(a_authority), 'sha256': sha(a_authority), 'raw_without_newline_sha256': 'a81946b44a3c4ad7aad945f5c1b81a80a39893551e6f9296389068ad6b1f8822'},
    'exact_later_owner_text': ae['payload']['item']['content'][0]['text'],
    'interpretation': 'Complete the requested review using the recommended labelled-display working convention. This is reviewer selection under owner completion instructions, not a personal per-image Use image answer.',
    'pending_duplicate_policy_question': 'SUPERSEDED_BY_LATER_OWNER_COMPLETION_INSTRUCTION_AND_REVIEWER_SELECTION',
    'personal_owner_Use_image_answers_added': 0,
}
save('review-authority.json', authority)

specific = {
    'BSI-83F1AACE15E9': 'Whole room-display002 shows the full square panel above a wooden table with tea ware against a turquoise wall. The distinctive rust islands, turquoise mottling and gold flecks match retained primary005. Room-display004 independently shows the same panel above a cabinet. Creation origin and a real client/permanent installation are unverified. The four former unavailable source IDs remain unresolved history; this selects a current replacement without restoring or deleting anything.',
    'BSI-86E6AEA0EB98': 'Whole White triptych002 shows all three complete long Fish panels and surrounding brickwork. Use the already source-linked group as a qualified brick-wall display for the retained FFS1 member. No new component/position, measured size, physical cast or legacy FFL1 relationship is inferred.',
    'BSI-60CAC1435616': 'Whole White triptych002 shows all three complete long Fish panels and surrounding brickwork. Use the already source-linked group as a qualified brick-wall display for the retained FFS3 member. No new component/position, measured size, physical cast or legacy FFL1 relationship is inferred.',
    'BSI-8DE87C63B013': 'The retained Terracotta FFS2 source003 shows the full elongated relief with stone courses and mortar visible on every side. Qualified stone-wall display only; no wider garden, actual current dimensions, installation hardware or White/other-finish transfer is established.',
    'BSI-0D80125C0E35': 'The retained Verdigris FFS2 source008 shows the full elongated relief with stone courses and mortar visible on every side. Qualified stone-wall display only; no wider garden, actual current dimensions, installation hardware or White/other-finish transfer is established.',
    'BSI-FBD125528AEC': 'The retained complete White Moon Ring001 is shown against weathered timber planks with hinge/latch hardware and surrounding door visible. Qualified timber-door display; not a certified permanent fitting, measured cast or wider garden installation.',
    'BSI-1CDB2BAE6105': 'Whole Plant Form in-situ003 matches the existing White primary001 relief: three upright pointed lobes and the broad crossing lower form, with complete panel edges and surrounding brickwork visible. Qualified brick-wall display only. It supplies no fitted-hardware or wider-garden certification.',
    'BSI-9AF26B8CF780': 'The whole retained Rust and Blue Patina001 panel stands on a protective sheet beside a stair and hatstand. The full tall outline and blue vertical streak pattern are visible. Qualified indoor floor-standing/workroom display; it is not shown installed on a wall and no mounting or physical-size claim is added.',
    'BSI-177C94BD0EFF': 'The exact retained MCP2 Blue Splashes001 square and raised circular relief are wholly visible against textured stone courses. Qualified stone-wall display, preserving this specific blue/white/black pattern and phase identity. No wider-room/garden or physical measurement is certified.',
    'BSI-2E097B70CD7F': 'The exact retained MCP2 Verdigris and Rust003 square is wholly visible against textured stone courses. Its rust band and speckled turquoise circular face are retained. Qualified stone-wall display only; no transfer from other phases or plain Verdigris groups.',
    'BSI-BFEE06AB14A0': 'The exact retained MCP3 Verdigris and Rust001 square is wholly visible against textured stone courses. Its relief geometry and rust/turquoise surface are retained. Qualified stone-wall display only; no transfer from other phases or plain Verdigris groups.',
    'BSI-1AF0A83FAA37': 'The retained MCP4 Silver and Bronze004 image is an oblique view of the complete square, circular relief and side depth against a stone wall. Qualified side-view stone-wall display only. Existing finish nomenclature is retained; no measured depth, material or installation hardware is inferred.',
    'BSI-DF431D2D9F15': 'The exact retained Silver MP4 source001 shows the full curved panel with substantial surrounding stone courses. Qualified stone-wall display only; existing silver finish and MP4 identity are retained without transferring White family scenes or certifying a real installed cast.',
    'BSI-27B50C52ED10': 'Whole four-White-Moon-Craters040 shows the existing four-phase family as four complete square panels in one row on brickwork, with visible wall around the arrangement. Use as qualified group display for existing MCP1 White, consistent with retained four-phase series membership. No new member numbering, stock or physical cast/size claim is added.',
    'BSI-8035F91E2A67': 'Whole four-White-Moon-Craters040 shows the existing four-phase family as four complete square panels in one row on brickwork, with visible wall around the arrangement. Use as qualified group display for existing MCP2 White, consistent with retained four-phase series membership. No new member numbering, stock or physical cast/size claim is added.',
    'BSI-89699A0F5BA9': 'Whole four-White-Moon-Craters040 shows the existing four-phase family as four complete square panels in one row on brickwork, with visible wall around the arrangement. Use as qualified group display for existing MCP3 White, consistent with retained four-phase series membership. No new member numbering, stock or physical cast/size claim is added.',
    'BSI-DF3FF43C94C9': 'The retained pair002 shows two full horizontal White Sand Ripple panels on a broad rust-coloured display board. Fossil/Rough is the lower textured member; Smooth is above. Use the whole existing series view as qualified board display. No wider room, permanent installation or physical size is certified.',
    'BSI-0401496CA4E6': 'The retained pair002 shows two full horizontal White Sand Ripple panels on a broad rust-coloured display board. Smooth is the upper member; Fossil/Rough is below. Use the whole existing series view as qualified board display. Do not substitute the separate floor-to-ceiling blue architectural treatment or certify a physical size.',
}
decisions = []
binding_checks = []
for oid in ['BSI-DF3FF43C94C9', 'BSI-0401496CA4E6']:
    specific[oid] = specific[oid].replace('on a broad rust-coloured display board', 'against brown textured backing').replace('qualified board display', 'qualified pair display; backing material and mounting are unverified')
for n, item in enumerate(selected, 1):
    oid = item['option_id']; old = options[oid]; src = item['source']; fid = src['file_id']
    if oid in ['BSI-DF3FF43C94C9', 'BSI-0401496CA4E6']:
        item['proposed_label'] = 'Pair display — brown backing'
    e = entries[fid]; meta = metadata[fid]['file']; original = checks[fid]
    parent_path = e['path'].rsplit('/', 1)[0]
    parent = folders[parent_path.lower()]
    expected_parent = src.get('folder_id')
    if not expected_parent and item['prior_primary'].get('file_id') == fid:
        expected_parent = item['prior_primary'].get('folder_id')
    if expected_parent:
        assert parent['file_id'] == expected_parent
    assert meta['id'] == fid and meta['size'] == e['file']['size'] == original['size']
    display_path = meta['path_display']; display_parent = display_path.rsplit('/', 1)[0]
    # Dropbox resolves paths case-insensitively; the API preserves two casing
    # variants for Moon Ring WHite and Textured panels. Stable IDs are exact.
    assert e['path'].casefold().endswith(display_path.casefold())
    assert hashlib.sha256(Path(original['local_path']).read_bytes()).hexdigest() == original['sha256']
    ref = {'file_id': fid, 'folder_id': parent['file_id'], 'name': meta['name'], 'path': e['path'], 'path_display': display_path, 'rev': meta['rev'], 'size': meta['size'], 'content_hash': original['content_hash'], 'sha256': original['sha256'], 'dimensions': original['dimensions'], 'image_url': 'https://www.dropbox.com/home' + quote(display_parent, safe='/') + '?preview=' + quote(meta['name'], safe=''), 'folder_url': 'https://www.dropbox.com/home' + quote(display_parent, safe='/'), 'review_label': item['proposed_label'], 'native_reference_status': 'CURRENT_MASTER_FILE_AND_ACTUAL_PARENT_VERIFIED', 'whole_original_only': True, 'scene_authenticity_verified': False, 'physical_cast_or_size_certified': False}
    decisions.append({'decision_id': 'REVIEWER-REMAINING-DISPLAY-20261023-' + str(n).zfill(2), 'product_id': oid, 'name': item['name'], 'role': 'In situ', 'status_before': 'No verified image', 'status_after': 'Available', 'decision_kind': 'OWNER_AUTHORIZED_REVIEWER_SELECTION_QUALIFIED_DISPLAY_ONLY', 'explicit_owner_image_role_approval': False, 'reviewer_selected_reference': True, 'owner_directed_editorial_completion': True, 'personal_owner_Use_image_answer': None, 'reference': ref, 'basis': specific[oid], 'display_qualification': item['proposed_label'], 'source_qualified_visual_binding': True, 'scene_authenticity_verified': False, 'wider_room_or_garden_view_verified': False, 'physical_cast_or_size_certified': False, 'existing_individual_reference': coverage[oid]['individual']['reference'], 'individual_primary_file_id_to_preserve': old['file_id'], 'series_policy_to_preserve': coverage[oid]['series'], 'private_source_original_path': original['local_path'], 'pixels_edited': False, 'baseline_option_semantic_sha256': hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()})
    binding_checks.append({'product_id': oid, 'file_id': fid, 'parent_id': parent['file_id'], 'fresh_listing_membership': True, 'metadata_size_matches_original': True, 'original_sha256_matches': True, 'revision': meta['rev']})

residual_explanations = {
    'BSI-3635E3DC3434': 'The current exact Pewter folder has only the complete isolated panel and a finish detail; no group or contextual placement is supplied. Reuse A current listing and completed search rather than repeating unchanged searches.',
    'BSI-449C4421ABD0': 'The current complete Pewter image has an isolated plain-wall background. It does not show an identifiable wider setting or a physical display surface beyond the product backdrop.',
    'BSI-1774B82C6518': 'The current complete Pewter image has an isolated plain-wall background. No exact Pewter contextual placement is verified by the current family listing and A source review.',
    'BSI-B42C439049D7': 'The newer complete Gold Leaf Growth image replaces the old detail as primary, but remains an isolated product depiction on a plain background. The White red-board scene is not transferred to the Gold finish.',
    'BSI-46F6DB226213': 'Primary MCP4 Verdigris and Rust is an isolated product depiction. The reviewed triple-MCP4 room images show a different darker plain-Verdigris/rim treatment, not the retained rust-mottled surface.',
    'BSI-2418C8B43415': 'The close Gold Leaf panel view sits among foliage, with foliage crossing the lower edge and no wider placement/support established. Keep the primary; seek a more complete contextual presentation rather than promote this ambiguous close product view.',
    'BSI-718DFFB7EC5D': 'The current Bronze1 primary is now a complete standalone product image, not merely a detail. Its plain background and close Bronze pair do not show wider contextual placement. White installations cannot supply this exact Bronze role.',
    'BSI-54F871DCF4CA': 'The current Bronze2 primary is now a complete standalone product image, not merely a detail. Its plain background and close Bronze pair do not show wider contextual placement. White installations cannot supply this exact Bronze role.',
    'BSI-207102CFD25C': 'The whole Blue/Brown/Rust primary is an overhead worktable view surrounded mainly by protective fabric and tools. It does not establish a composed wall/room/garden display; retain the existing product reference.',
}
by_id = {x['product_id']: x for x in decisions}
held = set(plan['held_option_ids'])
outcomes = []
for x in baseline:
    oid = x['option_id']
    if oid in by_id:
        state = 'READY_FOR_QUALIFIED_DISPLAY_IMPORT'; finding = by_id[oid]['basis']; ref = by_id[oid]['reference']
    elif oid in held:
        state = 'OWNER_HOLD_OR_DEFERRED_IDENTITY_PRESERVED'; finding = x['prior_finding']; ref = x['primary']
    else:
        state = 'CURRENT_CONTEXT_SOURCE_STILL_REQUIRED'; finding = residual_explanations.get(oid, x['prior_finding']); ref = x['primary']
    outcomes.append({'option_id': oid, 'name': x['name'], 'role': 'In situ', 'review_state': state, 'finding': finding, 'reference': ref, 'prior_finding_preserved': x['prior_finding'], 'scope': 'Current relevant-family listings checked. Reused historical visual searches plus this bounded primary/context review; not a whole-Dropbox absence claim.'})
assert len(outcomes) == 44 and len(decisions) == 18 and len(held) == 8
preflight = {'status': 'PASS_CURRENT_FILES_ORIGINALS_AND_ACTUAL_PARENTS', 'recorded_utc': now, 'checks': binding_checks, 'unique_selected_files': 14, 'whole_original_sources_visually_reviewed': 14, 'family_listing_scopes': 18, 'fresh_family_file_count': len([x for x in entries.values() if x['object_type'] == 'file']), 'authority': authority, 'source_byte_evidence': [str(J / 'candidate-original-checks.json'), str(J / 'rust-current-original-evidence.json')], 'scope': 'All18 proposed roles use exact current Master IDs, actual containing parents and whole source bytes. No original source was edited.'}
save('source-preflight.json', preflight)
packet = {'schema': 'boldstone.reviewer-qualified-display-decisions.v1', 'recorded_utc': now, 'status': 'READY_FOR_INDEPENDENT_REVIEW_AND_ROOT_IMPORT', 'authority': {'path': str(J / 'review-authority.json'), 'sha256': sha(J / 'review-authority.json')}, 'source_preflight': {'path': str(J / 'source-preflight.json'), 'sha256': sha(J / 'source-preflight.json')}, 'decisions': decisions, 'baseline_register': {'path': str(reg_path), 'sha256': sha(reg_path), 'workbook_sha256': manifest['baseline_workbook_sha256']}, 'expected_scope_delta': {'qualified_in_situ_roles_closed': 18, 'in_situ_gaps_before': 44, 'in_situ_gaps_after': 26, 'series_gaps_unchanged': 17, 'current_options_unchanged': 187, 'required_picture_actions_after': 44, 'new_individual_roles': 0, 'new_series_roles': 0, 'personal_Use_image_answers_added': 0, 'physical_verifications_added': 0}, 'preserve': ['All existing individual primaries, specifications, selling details and series roles', 'All eight owner-held/deferred in-situ cases, retired Sandstone, unresolved old Rust source IDs and exact history'], 'scope_exclusions': ['Native file/folder mutations', 'Platform writes', 'Physical stock/size/hardware or authentic installed-scene certification'], 'canonical_or_workbook_writes_by_this_lane': 0, 'native_or_platform_writes': 0, 'review_outcomes': {'path': str(J / 'remaining-insitu-review-outcomes.json'), 'count': 44}, 'supplementary_rust_source': checks['id:cnqzTNngPVsAAAAAAAuQ-g']}
save('remaining-insitu-review-outcomes.json', outcomes)
save('reviewer-reference-decisions.json', packet)
cards = []
for x in outcomes:
    r = x['reference']; label = by_id.get(x['option_id'], {}).get('display_qualification', x['review_state'].replace('_', ' ').title())
    cards.append('<article><h2>' + html.escape(x['name']) + '</h2><p><strong>' + html.escape(label) + '</strong></p><p>' + html.escape(x['finding']) + '</p><p><a href="' + html.escape(r.get('image_url', ''), quote=True) + '">Photograph</a> · <a href="' + html.escape(r.get('folder_url', ''), quote=True) + '">Containing folder</a></p></article>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Remaining installation and display reviews</title><style>body{font:17px system-ui;max-width:1000px;margin:48px auto;padding:0 24px;background:#f7f5f0;color:#202b2a}article{background:white;border:1px solid #ddd;padding:20px;margin:18px 0}h2{font-size:21px}a{color:#17635e}</style><h1>Remaining installation and display reviews</h1><p>44 cases reviewed: 18 qualified display references prepared for import, 18 still need a contextual photograph, and eight remain held or deferred. These are working image-role decisions, not physical installation certification. Publication status must be read from the current master.</p>' + ''.join(cards) + '</html>'
(J / 'review-results.html').write_text(page)
print(json.dumps({'status': packet['status'], 'packet': str(J / 'reviewer-reference-decisions.json'), 'sha256': sha(J / 'reviewer-reference-decisions.json'), 'counts': packet['expected_scope_delta'], 'fresh_family_files': preflight['fresh_family_file_count']}, ensure_ascii=False))
