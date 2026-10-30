import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

OUT = Path(__file__).parent
ROOT = '/BOLDSTONE MASTER/Products/01 Wall Sculptures/Fingerprint'
baseline = json.loads((OUT / 'baseline-native.json').read_text())
assert not baseline['has_more']
by_id = {x['file_id']: x for x in baseline['entries']}
def fq(path):
    assert path.startswith('ns:202238505//')
    return '/' + path.split('//', 1)[1]

changes = [
    ('id:cnqzTNngPVsAAAAAAAyhQw', 'Fingerprint Concentric Pair Verdigris', 'VERDIGRIS_PAIR'),
    ('id:cnqzTNngPVsAAAAAAAyhIA', 'Fingerprint Concentric Pair White', 'WHITE_PAIR'),
    ('id:cnqzTNngPVsAAAAAAAykGg', 'Fingerprint Concentric Pair White In Situ', 'WHITE_PAIR_CONTEXT'),
    ('id:cnqzTNngPVsAAAAAAAyhOw', 'Fingerprint Verdigris Mixed Arrangements', 'MIXED_ARRANGEMENTS_NOT_INDIVIDUAL_COMPONENT_BOUND'),
    ('id:cnqzTNngPVsAAAAAAAyhIQ', 'Fingerprint Verdigris Room Views', 'MIXED_ROOM_VIEWS_NOT_INDIVIDUAL_COMPONENT_BOUND'),
]
folder_moves = []
for ident, name, role in changes:
    original = by_id[ident]
    assert original['object_type'] == 'folder'
    folder_moves.append({'source_id': ident, 'source_path': fq(original['path']),
        'destination_path': ROOT + '/Arrangements/' + name, 'role': role,
        'file_count': sum(x['object_type'] == 'file' and x['path'].rsplit('/', 1)[0] == original['path'] for x in baseline['entries'])})

members = [
    ('BC-FP-LEFT', 'Fingerprint Left Panel', {'Verdigris': 'BSI-6D48F324B10C', 'White': 'BSI-5A81C695D1AB'}),
    ('BC-FP-RIGHT', 'Fingerprint Right Panel', {'Verdigris': 'BSI-59CBB4D2FA9E', 'White': 'BSI-51CF74303593'}),
]
new_folders = [{'path': ROOT + '/Arrangements', 'role': 'PAIR_GROUP_AND_CONTEXT_IMAGES'}]
for component_id, name, finishes in members:
    new_folders.append({'path': ROOT + '/' + name, 'role': 'INDIVIDUAL_COMPONENT', 'component_id': component_id})
    for finish, product_id in finishes.items():
        new_folders.append({'path': ROOT + '/' + name + '/' + finish, 'role': 'COMPONENT_FINISH_REFERENCES', 'component_id': component_id, 'product_id': product_id, 'finish': finish})

def current_file_path(item):
    old = fq(item['path'])
    for move in folder_moves:
        if old.startswith(move['source_path'] + '/'):
            return move['destination_path'] + old[len(move['source_path']):]
    return old

def url(path, folder=False):
    return 'https://www.dropbox.com/' + ('home' if folder else 'preview') + quote(path, safe='/')

uploads = []
bindings = []
for component_id, component_name, finishes in members:
    for finish, product_id in finishes.items():
        selected = [m for m in folder_moves if m['role'] in (('WHITE_PAIR', 'WHITE_PAIR_CONTEXT') if finish == 'White' else ('VERDIGRIS_PAIR',))]
        files = [x for x in baseline['entries'] if x['object_type'] == 'file' and any(fq(x['path']).startswith(m['source_path'] + '/') for m in selected)]
        rows = []
        for f in files:
            path = current_file_path(f)
            kind = 'Pair in situ reference' if 'In Situ/' in path else 'Pair reference'
            if f['file_id'] == 'id:cnqzTNngPVsAAAAAAAyhHg':
                kind += '; shorter framing, exact dimensions and cast not established'
            rows.append('<tr><td><a href="' + html.escape(url(path), quote=True) + '">' + html.escape(f['name']) + '</a></td><td>' + html.escape(kind) + '</td></tr>')
        title = component_name + ' - ' + finish
        body = '<!doctype html>\n<html lang="en"><meta charset="utf-8"><title>' + html.escape(title) + '</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto;padding:0 20px;line-height:1.5}td,th{text-align:left;padding:10px;border-bottom:1px solid #ddd}table{border-collapse:collapse;width:100%}</style><h1>' + html.escape(title) + '</h1><p>This folder represents one existing catalogue component in this finish. The linked photographs show the pair; they are retained in Arrangements.</p><p><strong>Individual photograph: still needed.</strong> These reference links do not provide a standalone photograph of this panel.</p><p>Project composition 2 includes both concentric panels. Individual member numbers 1 and 2 have not been established; the existing approved Left Panel and Right Panel identities remain in use.</p><p><a href="' + html.escape(url(ROOT + '/Arrangements', True), quote=True) + '">Open Arrangements</a></p><table><thead><tr><th>Photograph</th><th>Reference role</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table><p>Existing catalogue identity: ' + html.escape(component_id) + '. Finish option: ' + html.escape(product_id) + '.</p><p>Native Dropbox links require the viewer\'s existing access. No new shared links were created.</p></html>\n'
        local = OUT / 'reference-files' / (component_id + '-' + finish + '.html')
        local.parent.mkdir(exist_ok=True)
        assert not local.exists()
        local.write_text(body)
        destination = ROOT + '/' + component_name + '/' + finish + '/Pair and Group References.html'
        uploads.append({'source_file': str(local), 'destination_path': destination, 'sha256': hashlib.sha256(local.read_bytes()).hexdigest(), 'size': local.stat().st_size})
        bindings.append({'component_id': component_id, 'product_id': product_id, 'finish': finish, 'component_folder_path': ROOT + '/' + component_name, 'finish_folder_path': destination.rsplit('/', 1)[0], 'reference_document_path': destination, 'pair_reference_file_ids': [f['file_id'] for f in files], 'individual_photo_status': 'Group only', 'individual_member_number': None, 'source_composition_number': '2'})

plan = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'status': 'AUTHORIZED_COMPONENT_SPLIT_PRE_MUTATION_PLAN',
    'authorization': 'Owner explicitly said continue with each component in its own folder/catalogue identity, finish references, and pair/group photographs kept separately under Arrangements.',
    'existing_identification_policy': 'Preserve BC-FP-LEFT/RIGHT and four existing option IDs; no new component numbers, identities, measured specifications, stock or mould claims.',
    'create_folders': new_folders, 'folder_moves': folder_moves, 'reference_file_uploads': uploads, 'component_finish_bindings': bindings,
    'autorename': False, 'delete_items': [], 'original_image_edits_or_copies': [],
    'expected': {'original_files': 75, 'original_folder_ids': 8, 'original_files_inside_moved_folders': sum(x['file_count'] for x in folder_moves), 'new_folders': len(new_folders), 'new_reference_documents': len(uploads), 'individual_photo_gaps_retained': 4},
    'rollback': 'Move the five existing folders back to their recorded source paths. New reference files and folders can be removed only after separate explicit deletion confirmation.',
    'shared_master_owner': '01a144ab-1a7c-7223-a403-73a4d53d70ff'}
target = OUT / 'split-plan.json'
assert not target.exists()
target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'path': str(target), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'expected': plan['expected']}))
