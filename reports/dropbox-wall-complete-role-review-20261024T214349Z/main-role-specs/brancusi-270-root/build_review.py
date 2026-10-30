"""Read-only Brancusi270 role handoff to the directory session's serial recorder."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
from urllib.parse import quote

H = Path(__file__).resolve().parent
BASE = H.parents[1]
FAMILY = BASE / 'families/brancusi'
ROOT = BASE.parents[1]
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
write = lambda p, v: Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n')
def span(first, last):
    return list(range(first, last+1))

# Every range below was observed in the labelled270-image/fourteen-page boards.
roles = {
    'individual': [3, 7, 8, 11] + span(46, 63) + span(66, 81) + [233, 238, 240, 241] + span(244, 251) + span(254, 269),
    'detail': [4, 5, 6, 9, 10, 12, 13, 14, 64, 65] + span(82, 89) + [104, 118] + span(153, 161) + span(172, 181) + span(211, 216) + [221, 230, 231, 232, 234, 235, 242, 243, 252, 253],
    'rear': [],
    'installation': span(15, 45) + span(90, 92),
    'group_context': [1, 2] + span(93, 103) + span(105, 117) + span(119, 152) + span(162, 171) + span(182, 210) + span(217, 220) + span(222, 229) + [236, 237, 239, 270],
    'uncertain': [],
}
group_details = [4, 10, 104, 118] + span(153, 161) + span(172, 181) + span(211, 216) + [221]
secondary_installation = [101, 102] + span(128, 131) + [270]
partial_companions = [1, 2, 4, 10, 228, 229, 236, 237, 239]
cross_number_resemblance = [61, 66, 67, 82, 83, 242, 243, 244, 245, 257, 258]
spec = {
    'family': 'Brancusi', 'reviewer_thread_id': '01a144ab-1a7c-7223-a403-73a4d53d70ff',
    'all_boards_viewed': span(1, 14),
    'component_finish_qualification': 'Retain the existing Brancusi1 and Brancusi2 labels and separate White/Gold Leaf finish records. This pass classifies each visible photograph only. Similar details, color casts, rotations, derived room settings and group placements do not establish new component identities, design equivalences, exact physical finishes, cast quantities or individual platform variants.',
    'visual_roles': {k: sorted(v) for k, v in roles.items()},
    'group_detail_indices': sorted(group_details),
    'secondary_installation_indices': sorted(secondary_installation),
    'single_depicted_scope_indices': sorted(set(roles['installation']) | (set(roles['detail']) - set(group_details))),
    'flags': [
        {'indices': sorted(partial_companions), 'flag': 'PARTIAL_COMPANION_VISIBLE_IN_COMPONENT_FOLDER_NO_ISOLATED_SINGLE_SCOPE'},
        {'indices': sorted(group_details), 'flag': 'CROPPED_MULTI_PANEL_DETAIL_RETAINS_GROUP_SCOPE'},
        {'indices': span(15, 45) + [101, 102, 270], 'flag': 'ROOM_OR_DISPLAY_REFERENCE_CREATION_ORIGIN_UNVERIFIED'},
        {'indices': span(46, 89) + span(103, 227) + span(242, 269), 'flag': 'SIMILAR_FRAME_CROP_LIGHTING_ORIENTATION_VERSIONS_RETAINED'},
        {'indices': cross_number_resemblance, 'flag': 'SIMILAR_WHITE_VIEWS_ACROSS_NUMBER_FOLDERS_NO_IDENTITY_PROMOTION'},
        {'indices': [72, 73, 74] + span(217, 227), 'flag': 'FRONT_VIEW_OR_VISIBLE_SUSPENSION_DOES_NOT_VERIFY_FITTED_FIXING'},
        {'indices': [270], 'flag': 'MULTI_PANEL_GARDEN_SCENE_IN_NUMBER2_CONTEXT_FOLDER_NOT_ISOLATED_NUMBER2_VIEW'},
    ],
    'notes': [
        {'indices': sorted(partial_companions), 'note': 'A complete or dominant panel is accompanied by part of the other panel; keep a group/cropped-group role even though the native containing folder names one component.'},
        {'indices': span(15, 45), 'note': 'Gold Leaf room/display references. Similar styled scenes and variable apparent scale are retained; the pass does not certify image-production method, actual installation, measured dimensions or White-finish applicability.'},
        {'indices': [101, 102], 'note': 'Gold Leaf pair in a styled room; primary role remains group/context with a secondary installation/display role.'},
        {'indices': span(128, 131), 'note': 'White pair on a wide outdoor brick-wall/garden display; primary group scope is retained.'},
        {'indices': cross_number_resemblance, 'note': 'White close/horizontal views resemble photographs in both existing numbered folders. Compared pairs have different native content hashes; no exact duplicate, new equivalence, folder change or number reassignment is claimed by this role review.'},
        {'indices': [270], 'note': 'Four panel placements in a garden pavilion are visible in this frame. Preserve group/display qualification; the Number2 folder label alone does not make this a separate individual photograph or certify physical stock.'},
    ],
}

checks = []
def check(name, v):
    checks.append({'check': name, 'pass': bool(v)})
    assert v, name

rows = read(FAMILY / 'indexed-current-images-and-links.json')
boards = read(FAMILY / 'contact-board-index.json')
native = read(BASE / 'complete-current-native-object-map.json')
evidence = {r['file_id']: r for r in read(BASE / 'current-6360-visual-source-evidence.json')}
assigned = [i for indices in spec['visual_roles'].values() for i in indices]
check('Each270 current image has exactly one explicit primary role', len(assigned) == len(set(assigned)) == len(rows) == 270 and set(assigned) == {r['review_index'] for r in rows})
check('All fourteen indexed boards viewed', set(spec['all_boards_viewed']) == {b['page'] for b in boards} and len(boards) == 14)
check('All group details retain a detail primary role', set(group_details) <= set(roles['detail']))
check('Secondary installation keeps group primary role', set(secondary_installation) <= set(roles['group_context']))
role_for = {i: role for role, indices in roles.items() for i in indices}
board_evidence = [{'page': b['page'], 'path': b['path'], 'sha256': sha(b['path']), 'indices': b['indices']} for b in boards]
observations = []
for row in rows:
    i = row['review_index']
    e = evidence[row['file_id']]
    n = native[row['file_id']]
    check('Exact current file and actual parent ' + str(i), row['file_id'] == n['file_id'] and row['folder_id'] == n['parent_id'] and row['image_url'] == n['image_url'] and row['folder_url'] == n['folder_url'])
    check('Hash-bound visual frame unchanged ' + str(i), sha(e['source_image_path']) == e['actual_visual_source_sha256'] and e == row['visual_source'])
    board = next(b for b in board_evidence if i in b['indices'])
    observations.append({'review_index': i, 'file_id': row['file_id'], 'name': row['name'],
        'folder_id': row['folder_id'], 'folder_url': row['folder_url'], 'image_url': row['image_url'],
        'visual_role': role_for[i], 'group_detail': i in group_details, 'secondary_installation': i in secondary_installation,
        'native_finish_folder_label': row['folder_path'].rsplit('/', 1)[-1],
        'source': e, 'board': board,
        'flags': [v['flag'] for v in spec['flags'] if i in v['indices']],
        'notes': [v['note'] for v in spec['notes'] if i in v['indices']],
        'component_identity_reassigned': False, 'physical_specification_verified': False,
        'native_action_applied': 'NONE', 'canonical_binding_applied': False})
write(H / 'manual-role-specification.json', spec)
write(H / 'explicit-270-observations.json', observations)
esc = html.escape
parts = ['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Brancusi270 role review</title><style>body{font:17px/1.5 system-ui;margin:2rem auto;padding:0 1rem;max-width:1300px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}article{border:1px solid #bbb;border-radius:8px;padding:1rem;overflow-wrap:anywhere}img{width:100%;height:250px;object-fit:contain;background:#eee}.meta{font-size:13px}</style><h1>Brancusi: all270 current images reviewed</h1><p>Image-role review of the fourteen labelled contact sheets. These are image counts, not sculpture, mould or stock counts. Existing Brancusi1/2 and White/Gold Leaf labels remain separate and qualified. No Dropbox, master or platform changes.</p><p>' + esc(str(dict(Counter(role_for.values())))) + '</p><div class="grid">']
for r in observations:
    local = quote(os.path.relpath(r['source']['source_image_path'], H), safe='/')
    parts += ['<article id="image-' + str(r['review_index']) + '"><h2>#' + str(r['review_index']) + ' · ' + esc(r['visual_role']) + '</h2><a href="' + local + '"><img loading="lazy" src="' + local + '" alt="Current hash-bound Brancusi review frame"></a><p><a href="' + esc(r['image_url'], quote=True) + '">Dropbox image</a> · <a href="' + esc(r['folder_url'], quote=True) + '">Actual containing folder</a></p><p>' + esc(r['name']) + '</p><p>' + esc(' '.join(r['notes'])) + '</p><p class="meta">' + esc(r['file_id']) + '<br>' + esc(r['folder_id']) + '<br>' + esc(', '.join(r['flags'])) + '</p></article>']
parts.append('</div><p>Room/display origin, actual dimensions, weight, material composition, fitted fixing, physical stock and per-panel sale configuration are not newly verified by this review.</p>')
(H / 'index.html').write_text('\n'.join(parts) + '\n')
pointer = ROOT / 'sculpture-catalogue/current-master.json'
check('Canonical baseline still64e', sha(pointer) == '64e22f7c3aaca874817b11b497294c4b40b17564b717ce7c05e41ffbc44f22b7')
summary = {'status': 'PASS', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks,
    'images': len(rows), 'boards_viewed': 14, 'role_counts': dict(Counter(role_for.values())),
    'group_detail_count': len(group_details), 'secondary_group_installation_count': len(secondary_installation),
    'rear_views_seen': 0, 'new_component_identities': 0, 'new_physical_specifications': 0,
    'native_or_platform_writes': 0, 'canonical_writes': 0,
    'reviewer_thread_id': spec['reviewer_thread_id'],
    'directory_serial_recorder_required': True,
    'protected_canonical_pointer_sha256': sha(pointer),
    'family_index': {'path': str(FAMILY / 'indexed-current-images-and-links.json'), 'sha256': sha(FAMILY / 'indexed-current-images-and-links.json')},
    'native_map': {'path': str(BASE / 'complete-current-native-object-map.json'), 'sha256': sha(BASE / 'complete-current-native-object-map.json')},
    'native_visual_evidence': {'path': str(BASE / 'current-6360-visual-source-evidence.json'), 'sha256': sha(BASE / 'current-6360-visual-source-evidence.json')},
    'boards': board_evidence}
write(H / 'verification.json', summary)
files = [H / 'build_review.py', H / 'manual-role-specification.json', H / 'explicit-270-observations.json', H / 'index.html', H / 'verification.json', FAMILY / 'indexed-current-images-and-links.json', FAMILY / 'contact-board-index.json']
files += [Path(b['path']) for b in board_evidence]
write(H / 'sealed-handoff.json', {'status': 'SEALED_ROOT_BRANCUSI270_EXPLICIT_ROLE_SPECIFICATION',
    'recorded_utc': summary['recorded_utc'], 'family': 'Brancusi', 'images': len(rows),
    'files': {str(p): sha(p) for p in files}, 'role_counts': summary['role_counts'],
    'native_writes': 0, 'canonical_writes': 0})
print(json.dumps({'status': 'PASS', 'checks': len(checks), 'roles': summary['role_counts'],
    'group_details': len(group_details), 'secondary_installation': len(secondary_installation),
    'seal_sha256': sha(H / 'sealed-handoff.json')}, indent=2))
