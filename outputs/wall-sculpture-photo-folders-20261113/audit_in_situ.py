import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent
snapshot = json.loads((BASE / 'inventory-in-situ.json').read_text())
plan = json.loads((BASE / 'folder-plan.json').read_text())
assert snapshot['has_more'] is False
entries = snapshot['entries']
by_id = {e['file_id']: e for e in entries}
by_path = {e['path'].casefold(): e for e in entries}
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif', '.tif', '.tiff', '.bmp', '.gif', '.avif'}


def normal(text):
    return ' '.join(unicodedata.normalize('NFC', text).casefold().replace('&', ' and ').split())


FINISHES = sorted(map(normal, [
    'White and Gold Leaf', 'White and Gold', 'Pale Blue and White',
    'Marbled Green and White', 'Marbled Black and White', 'Blue and White Marbled',
    'Copper and Partial Verdigris', 'Blue Wash Verdigris', 'Silver and Bronze',
    'Verdigris and Rust', 'Bronze Verdigris', 'Blue Splashes', 'Drip Rust',
    'Textured Gold Leaf', 'Gold Leaf', 'Verdigris Rust', 'Black and White',
    'Terracotta', 'White', 'Cream', 'Beige', 'Rust', 'Gold', 'Brown', 'Pewter',
    'Verdigris', 'Copper', 'Silver', 'Bronze',
]), key=len, reverse=True)


def identity_finish(component):
    name = normal(component['name'])
    for finish in FINISHES:
        if name.endswith(' ' + finish):
            return name[:-len(finish)].strip(), finish
    return name, ''


def aliases(component):
    stem, finish = identity_finish(component)
    result = [stem]
    if normal(component['family']) == 'deco palm and spiral':
        match = re.search(r'(palm|spiral) [12]$', stem)
        if match:
            result.append(match.group())
    return result


families = {}
for component in plan['components']:
    families.setdefault(normal(component['family']), []).append(component)


def group_matches(folder, component):
    body = re.sub(r'\bin situ\b.*$', '', normal(folder['name'])).strip()
    stem, wanted_finish = identity_finish(component)
    family_aliases = sorted({a for c in families[normal(component['family'])] for a in aliases(c)}, key=len, reverse=True)
    all_stems = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(a) for a in family_aliases) + r')(?!\w)')
    for alias in aliases(component):
        for match in re.finditer(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', body):
            tail = all_stems.sub(' ', body[match.end():])
            tail = re.sub(r'^(?:\s|\band\b)+', '', tail)
            if not wanted_finish:
                if not tail or tail.startswith('and '):
                    return True
                continue
            # A finish after a sequence of named members applies to those members.
            for finish in FINISHES:
                if tail == finish or tail.startswith(finish + ' '):
                    if finish == wanted_finish:
                        return True
                    break
    return False


def image_count(folder):
    prefix = folder['path'].casefold() + '/'
    return sum(e['object_type'] == 'file' and e['path'].casefold().startswith(prefix)
               and Path(e['name']).suffix.casefold() in IMAGE_EXTENSIONS for e in entries)


def record(folder):
    path = folder.get('path_display') or '/' + folder['path'].split('//', 1)[1]
    return {'name': folder['name'], 'id': folder['file_id'], 'path': path,
            'url': 'https://www.dropbox.com/home' + quote(path, safe='/'),
            'image_count': image_count(folder)}


rows = []
in_situ_folders = [e for e in entries if e['object_type'] in {'folder', 'mount'} and re.search(r'\bin situ\b', e['name'], re.I)]
for component in plan['components']:
    current = by_id[component['file_id']]
    dedicated = [by_path[path.casefold()] for path in (
        current['path'] + ' In Situ', current['path'] + '/' + current['name'] + ' In Situ'
    ) if path.casefold() in by_path and by_path[path.casefold()]['object_type'] in {'folder', 'mount'}]
    dedicated_ids = {e['file_id'] for e in dedicated}
    family_parent = current['path'].rsplit('/', 1)[0].casefold()
    shared = [e for e in in_situ_folders if e['file_id'] not in dedicated_ids
              and e['path'].rsplit('/', 1)[0].casefold() == family_parent
              and group_matches(e, component)]
    dedicated_images = sum(image_count(e) for e in dedicated)
    shared_images = sum(image_count(e) for e in shared)
    status = ('dedicated' if dedicated_images else 'shared_only' if shared_images else 'missing')
    rows.append({
        'name': current['name'], 'family': component['family'], 'component_id': current['file_id'],
        'component_url': record(current)['url'], 'status': status,
        'dedicated': [record(e) for e in dedicated], 'shared': [record(e) for e in shared],
        'dedicated_image_count': dedicated_images, 'shared_image_count': shared_images,
        'dedicated_folder_missing': not dedicated,
        'dedicated_folder_without_images': bool(dedicated) and not dedicated_images,
    })

summary = {
    'checked_at': snapshot['checked_at'], 'checked_components': len(rows),
    'with_dedicated_images': sum(r['status'] == 'dedicated' for r in rows),
    'with_shared_images_only': sum(r['status'] == 'shared_only' for r in rows),
    'without_matching_in_situ_images': sum(r['status'] == 'missing' for r in rows),
    'without_populated_dedicated_folder': sum(not r['dedicated_image_count'] for r in rows),
    'dedicated_folder_absent': sum(r['dedicated_folder_missing'] for r in rows),
    'dedicated_folder_without_images': sum(r['dedicated_folder_without_images'] for r in rows),
    'method': 'Dropbox folder names and image-file presence; shared folders require an explicitly named component and matching finish. Photo content was not visually re-reviewed.',
}
output = {'summary': summary, 'components': rows}
(BASE / 'in-situ-audit.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps(summary, indent=2))
print(json.dumps({'shared_only': [{'name': r['name'], 'folders': [f['name'] for f in r['shared'] if f['image_count']]} for r in rows if r['status'] == 'shared_only'],
                  'missing': [r['name'] for r in rows if r['status'] == 'missing']}, indent=2))
