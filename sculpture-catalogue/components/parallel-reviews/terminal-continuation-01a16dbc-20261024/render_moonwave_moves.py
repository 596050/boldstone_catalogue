"""Present each sealed, owner-approved move; perform no native operations."""
import hashlib
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[3] / 'reports/dropbox-moonwave-ten-approved-moves-20261024T182423Z'
read = lambda path: json.loads(Path(path).read_text())
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
esc = lambda value: html.escape(str(value), quote=True)
seal = read(SOURCE / 'execution-seal.json')
assert seal['status'] == 'COMPLETE_VERIFIED'
for source in seal['receipts']:
    assert sha(source['path']) == source['sha256']
validation = read(SOURCE / 'validation.json')
overlay = read(SOURCE / 'current-reference-overlay.json')
current = read(SOURCE / 'all-current-moonwave-image-folder-links.json')
assert len(current) == len({row['file_id'] for row in current}) == 99
by_id = {row['file_id']: row for row in current}
moves = sorted(overlay['specific_file_maps'], key=lambda row: (
    0 if Path(row['new_path']).parent.name.endswith('In Situ') else 1,
    int(Path(row['new_path']).name.rsplit('__', 1)[-1].split('.')[0])))
assert len(moves) == validation['owner_approved_moves_completed'] == 10
rows, cards = [], []
for number, move in enumerate(moves, 1):
    native = by_id[move['file_id']]
    before, after = Path(move['old_path']), Path(move['new_path'])
    assert before.name == after.name == native['name']
    assert str(after.parent) == native['folder_path']
    assert move['new_parent_id'] == native['folder_id']
    for field in ['sha256', 'size', 'dropbox_content_hash']:
        assert move[field] == native[field]
    row = {'item': number, 'file_id': move['file_id'], 'name': native['name'],
        'old_folder': str(before.parent), 'old_parent_id': move['old_parent_id'],
        'current_folder': native['folder_path'], 'current_parent_id': native['folder_id'],
        'image_url': native['image_url'], 'folder_url': native['folder_url'],
        'sealed_original_sha256': native['sha256'], 'sealed_original_size': native['size'],
        'sealed_dropbox_content_hash': native['dropbox_content_hash']}
    rows.append(row)
    cards.append('<article id="item-' + str(number) + '"><h2>' + str(number) + '. ' + esc(native['name']) +
        '</h2><p><a href="' + esc(row['image_url']) + '">Current image</a> · <a href="' + esc(row['folder_url']) +
        '">Current containing folder</a></p><p><strong>From:</strong> ' + esc(row['old_folder']) +
        '<br><strong>To:</strong> ' + esc(row['current_folder']) + '</p><p>Same file ID: <code>' + esc(row['file_id']) +
        '</code><br>Filename and original bytes preserved in the directory session verification.</p><details><summary>Sealed original-byte evidence</summary><pre>' +
        esc(json.dumps(row, indent=2, ensure_ascii=False)) + '</pre></details></article>')
    print(json.dumps({'item': number, 'file': native['name'], 'from': before.parent.name,
        'to': after.parent.name, 'image': row['image_url'], 'folder': row['folder_url']}, ensure_ascii=False))
record = {'status': 'PASS_TEN_SEALED_MOVE_REFERENCES_MATCH_CURRENT99',
    'execution_seal': str(SOURCE / 'execution-seal.json'), 'execution_seal_sha256': sha(SOURCE / 'execution-seal.json'),
    'directory_verification_utc': validation['verified_utc'], 'rows': rows,
    'current_family_counts': {'White': 84, 'InSitu': 15, 'original_files': 99},
    'new_live_reads': 0, 'new_binary_downloads_or_rehashes': 0, 'native_or_canonical_writes': 0}
(HERE / 'moonwave-ten-moves.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
page = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Ten approved Moonwave moves</title><style>body{font:16px/1.5 system-ui;max-width:1080px;margin:36px auto;padding:0 20px}a{color:#15549b}article{border-top:1px solid #ccc;margin:26px 0;padding-top:12px}p,pre{overflow-wrap:anywhere}pre{white-space:pre-wrap;font-size:13px}</style></head><body><h1>Ten approved Moonwave moves</h1><p>The directory session executed and verified this exact owner-approved set. Six wider brick-wall photographs moved to In Situ; four close views moved to White. All99 originals remain, with84 in White and15 in In Situ. Primary033, context005, the three borderline photographs and four room photographs stayed in place.</p><p>This page reads sealed records only. It performs no new live reads, downloads, original-file rehashes or native operations.</p><p><a href="moonwave-ten-moves.json">Structured move list</a> · <a href="' + esc(str(SOURCE / 'all-current-moonwave-image-folder-links.html')) + '">All99 current images and folders</a></p>' + ''.join(cards) + '</body></html>'
(HERE / 'moonwave-ten-moves.html').write_text(page)
print(json.dumps({'status': record['status'], 'report': str(HERE / 'moonwave-ten-moves.html'), 'items': 10}))
