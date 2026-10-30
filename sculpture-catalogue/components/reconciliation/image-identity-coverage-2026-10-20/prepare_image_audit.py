"""Prepare a current-ID image audit and source-bound visual comparison plates."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, parse_qs
from datetime import datetime, timezone
from PIL import Image, ImageOps, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
read = lambda p: json.loads(Path(p).read_text())
write = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ptr = read(BASE / 'current-master.json')
    graphpath = BASE / ptr['register']
    graph = read(graphpath)
    modelpath = BASE / 'components/evidence/component_register.json'
    model = read(modelpath)
    progresspath = BASE / 'components/reviews/specification_review_progress.json'
    progress = read(progresspath)
    assert sha(BASE / ptr['workbook']) == ptr['workbook_sha256']
    assert sha(graphpath) == ptr['register_sha256']
    pages = sorted(HERE.glob('inventory-page-*.json'))
    assert pages and not read(pages[-1])['has_more']
    entries = [x for p in pages for x in read(p)['entries']]
    assert len(entries) == len({x['file_id'] for x in entries})
    path_overlay = BASE.parent / 'reports/dropbox-wall-structure-2026-10-20/step-05-chelsea-moon-ripple-current-overlay.json'
    applied_overlay = None
    if path_overlay.exists():
        assert sha(path_overlay) == 'aa6e04c96d93820ee0d83aa889d3c98d7305963fd396a251255d6d066d01e156'
        overlay = read(path_overlay)
        assert overlay['status'] == 'PASS_CONSOLIDATED_CURRENT_PATH_OVERLAY' and all(overlay['verification'].values())
        for receipt in overlay['receipts']: assert sha(receipt['path']) == receipt['sha256']
        retired = {x['old_folder_id'] for x in overlay['folder_id_replacements']}
        by_id = {x['file_id']: x for x in entries if x['file_id'] not in retired}
        for current in overlay['current_objects']:
            e = dict(by_id.get(current['file_id'], {}))
            e.update(file_id=current['file_id'], name=current['name'], object_type=current['object_type'], path=current['path'])
            if current['object_type'] == 'file': e['file'] = {'size': current['size']}
            else: e['folder'] = {}
            by_id[e['file_id']] = e
        entries = list(by_id.values())
        applied_overlay = {'path': str(path_overlay), 'sha256': sha(path_overlay), 'current_ids': 30, 'retired_folder_replacements': overlay['folder_id_replacements']}
    folders = {x['path'].casefold(): x for x in entries if x['object_type'] == 'folder'}
    old_assets = {x['id']: x for x in model['assets']}
    assets = {}
    for e in entries:
        if e['object_type'] != 'file': continue
        old = old_assets.get(e['file_id'], {})
        folder = folders[e['path'].rsplit('/', 1)[0].casefold()]
        display = '/' + e['path'].split('//', 1)[1]
        family = display.split('/01 Wall Sculptures/', 1)[1].split('/')[0]
        original = old.get('full', '')
        thumb = old.get('thumb', '')
        assets[e['file_id']] = {'file_id': e['file_id'], 'folder_id': folder['file_id'],
            'name': e['name'], 'path': e['path'], 'display_path': display,
            'folder_path': folder['path'], 'family': family, 'bytes': e.get('file', {}).get('size'),
            'modified_time': e.get('modified_time'), 'client_modified': e.get('client_modified'),
            'image_url': 'https://www.dropbox.com/home' + quote(display.rsplit('/', 1)[0], safe='/') + '?preview=' + quote(e['name'], safe=''),
            'folder_url': 'https://www.dropbox.com/home' + quote(display.rsplit('/', 1)[0], safe='/'),
            'full': original if original and Path(original).exists() else '',
            'thumb': thumb if thumb and Path(thumb).exists() else '',
            'source_content_hash': old.get('content_hash'), 'source_bytes': old.get('bytes'),
            'cached_source_id_size_consistent': bool(old and old.get('bytes') == e.get('file', {}).get('size')),
            'current_original_content_rehashed': False}
    local = HERE / 'cache'
    if local.exists():
        for meta in local.glob('*.metadata.json'):
            d = read(meta)
            if d['id'] in assets:
                assets[d['id']]['full'] = d['local_path']
                assets[d['id']]['current_original_content_rehashed'] = d['dropbox_content_hash_verified']
    path_ids = {x['display_path'].casefold(): i for i, x in assets.items()}
    path_ids.update({('/' + x['path'].split('//', 1)[1]).casefold(): x['id'] for x in model['assets'] if x['id'] in assets})
    def from_url(url):
        if not url: return ''
        u = urlsplit(url)
        p = unquote(u.path)
        p = p[len('/home'):] if p.startswith('/home/') else p[len('/preview'):] if p.startswith('/preview/') else p
        if 'preview' in parse_qs(u.query): p += '/' + parse_qs(u.query)['preview'][0]
        return path_ids.get(p.casefold(), '')
    queue = []
    for i, x in enumerate(graph['options'], 1):
        if x.get('file_id'): queue.append({'label': f'P{i:03d}', 'category': 'primary', 'name': x['name'], 'product_id': x['product_id'], 'file_id': x['file_id']})
        context = from_url(x.get('context_image_url'))
        if context: queue.append({'label': f'C{i:03d}', 'category': 'context', 'name': x['name'], 'product_id': x['product_id'], 'file_id': context})
    for i, x in enumerate(graph['arrangement_context_references'], 1):
        if x.get('file_id') in assets: queue.append({'label': f'G{i:02d}', 'category': 'group', 'name': x['name'], 'reference_id': x['reference_id'], 'file_id': x['file_id']})
    for family, label in [('Frozen Fish', 'F'), ('Cup Ring and Spiral', 'U'), ('Wall Circle', 'W')]:
        selected = sorted((x for x in assets.values() if x['family'] == family), key=lambda x: x['path'])
        for i, a in enumerate(selected, 1): queue.append({'label': f'{label}{i:03d}', 'category': family, 'name': a['name'], 'file_id': a['file_id']})
    new = sorted((x for x in assets.values() if x['file_id'] not in old_assets), key=lambda x: x['path'])
    for i, a in enumerate(new, 1): queue.append({'label': f'N{i:02d}', 'category': 'new', 'name': a['name'], 'file_id': a['file_id']})
    inputs = HERE / 'inputs'
    inputs.mkdir(exist_ok=True)
    manifest = {}
    for label, source in [('master_pointer', BASE / 'current-master.json'), ('master_register', graphpath), ('master_workbook', BASE / ptr['workbook']), ('source_model', modelpath), ('review_progress', progresspath), ('owner_ledger', BASE / 'components/reviews/user_classifications.json')]:
        dest = inputs / (label + '.before')
        if not dest.exists(): dest.write_bytes(source.read_bytes())
        assert sha(source) == sha(dest), 'Source changed during preparation: ' + label
        manifest[label] = {'path': str(source), 'snapshot': str(dest), 'sha256': sha(source)}
    write(HERE / 'input-manifest.json', manifest)
    write(HERE / 'live-inventory.json', {'status': 'COMPLETE', 'recorded_utc': datetime.now(timezone.utc).isoformat(), 'pages': len(pages), 'entries': entries, 'counts': dict(Counter(x['object_type'] for x in entries)), 'completed_path_overlay': applied_overlay})
    write(HERE / 'asset-index.json', assets)
    write(HERE / 'visual-queue.json', queue)
    write(HERE / 'inventory-delta.json', {'new_file_ids': list(set(assets) - set(old_assets)), 'source_ids_not_in_current_scope': list(set(old_assets) - set(assets)), 'unchanged_size_ids': sum(x['cached_source_id_size_consistent'] for x in assets.values()), 'primary_references_current': sum(bool(x.get('file_id') in assets) for x in graph['options']), 'context_urls_resolved': sum(x['category'] == 'context' for x in queue), 'old_size_mismatch_ids': [i for i, x in assets.items() if i in old_assets and not x['cached_source_id_size_consistent']]})
    out = HERE / 'contact-sheets'
    out.mkdir(exist_ok=True)
    fontpath = '/System/Library/Fonts/Supplemental/Arial.ttf'
    font = ImageFont.truetype(fontpath, 16)
    small = ImageFont.truetype(fontpath, 13)
    heading = ImageFont.truetype(fontpath, 22)
    preview_manifest = []
    for category in dict.fromkeys(x['category'] for x in queue):
        rows = [x for x in queue if x['category'] == category]
        for start in range(0, len(rows), 20):
            chunk = rows[start:start+20]
            plate = Image.new('RGB', (1440, 1360), '#f3f5f2')
            draw = ImageDraw.Draw(plate)
            draw.text((20, 12), f'{category} | source-bound visual review | page {start//20+1}', font=heading, fill='#25382c')
            for j, x in enumerate(chunk):
                a = assets[x['file_id']]
                left, top = (j % 4) * 360 + 8, (j // 4) * 260 + 48
                imagepath = a['full'] or a['thumb']
                if imagepath:
                    try:
                        with Image.open(imagepath) as im:
                            im = ImageOps.exif_transpose(im).convert('RGB')
                            im.thumbnail((344, 203))
                            plate.paste(im, (left + (344-im.width)//2, top))
                    except Exception as ex: draw.text((left, top+50), str(ex)[:35], font=small, fill='red')
                else: draw.text((left, top+50), 'CURRENT FILE NOT CACHED', font=font, fill='red')
                title = x['label'] + ' ' + x['name']
                lines = [title[k:k+46] for k in range(0, min(len(title), 138), 46)]
                for line, text in enumerate(lines): draw.text((left, top+205+line*16), text, font=small, fill='#16281d')
            dest = out / (category.lower().replace(' ', '-') + f'-{start//20+1:02d}.jpg')
            plate.save(dest, quality=90)
            preview_manifest.append({'category': category, 'path': str(dest), 'labels': [x['label'] for x in chunk], 'count': len(chunk)})
    write(HERE / 'contact-manifest.json', preview_manifest)
    print(json.dumps({'files': len(assets), 'queued_views': len(queue), 'unique_queued_file_ids': len({x['file_id'] for x in queue}), 'contact_sheets': len(preview_manifest), 'categories': dict(Counter(x['category'] for x in queue)), 'uncached_new_files': sum(not assets[x['file_id']]['full'] and not assets[x['file_id']]['thumb'] for x in queue)}))


if __name__ == '__main__': main()
