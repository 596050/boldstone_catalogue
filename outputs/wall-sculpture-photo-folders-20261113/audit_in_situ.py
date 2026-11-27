"""Read component and photography folders from a completed Wall Sculptures listing."""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent
HIGH, DETAIL, SITU = 'High Resolution', 'In Detail', 'In Situ'
ROLES = (HIGH, DETAIL, SITU)
IMAGE_EXTENSIONS = set(
    '.jpg .jpeg .jfif .png .webp .heic .heif .avif .tif .tiff .bmp .gif '
    '.dng .cr2 .cr3 .nef .arw .orf .raf .rw2'.split()
)
ROLE_NAMES = {
    HIGH: re.compile(r'\b(?:high resolution|high res|hi res)\b'),
    DETAIL: re.compile(r'\b(?:in )?details?\b'),
    SITU: re.compile(r'\bin situ\b'),
}
CONTEXT = re.compile(
    r'\b(?:arrangements?|workshop|making|scene|generated series|together|views?|backview|'
    r'packaging|videos?|unclassified|panel backs|pair)\b'
)
FINISHES = sorted((
    'White and Gold Leaf', 'White and Gold', 'Pale Blue and White', 'Marbled Green and White',
    'Marbled Black and White', 'Blue and White Marbled', 'Copper and Partial Verdigris',
    'Blue Wash Verdigris', 'Silver and Bronze', 'Verdigris and Rust', 'Bronze Verdigris',
    'Blue Splashes', 'Drip Rust', 'Textured Gold Leaf', 'Gold Leaf', 'Verdigris Rust',
    'Black and White', 'Rust and Blue Patina', 'Blue Brown and Rust', 'Terracotta',
    'White', 'Cream', 'Beige', 'Rust', 'Gold', 'Brown', 'Pink', 'Pewter', 'Verdigris',
    'Copper', 'Silver', 'Bronze', 'Sandstone',
), key=len, reverse=True)
FINISHES = tuple(f.casefold() for f in FINISHES)


def normal(text):
    text = unicodedata.normalize('NFC', text).casefold().replace('&', ' and ')
    return ' '.join(re.sub(r'[-_‐‑–—]', ' ', text).split())


def identity_finish(name):
    name = normal(name)
    for finish in FINISHES:
        if name.endswith(' ' + finish):
            return name[:-len(finish)].strip(), finish
    return name, ''


def role_name(name):
    value = normal(name)
    for role, pattern in ROLE_NAMES.items():
        if pattern.search(value):
            return role
    return None


def folder(entry):
    return entry['object_type'] in {'folder', 'mount'}


def parent(entry):
    return entry['path'].rsplit('/', 1)[0].casefold()


def pathkey(entry):
    return entry['path'].casefold()


def component_kind(entry, family_name, children):
    """Use live family-level names and children, including components with absent role folders."""
    name = normal(entry['name'])
    if role_name(name) or CONTEXT.search(name):
        return 'context'
    stem, finish = identity_finish(name)
    # "And" also occurs inside a design name, a finish, and the Wall Circle pattern names.
    pattern_study = name.endswith('pattern studies')
    single_design = stem.replace('acanthus and moon', ' ').replace(normal(family_name), ' ')
    if not pattern_study and name != normal(family_name) and 'and' in single_design.split():
        return 'arrangement'
    if finish or pattern_study or any(folder(child) and role_name(child['name']) for child in children):
        return 'component'
    return 'review'


class Inventory:
    def __init__(self, snapshot, original):
        if snapshot['has_more'] is not False or snapshot.get('cursor'):
            raise ValueError('The Dropbox listing is incomplete.')
        self.snapshot = snapshot
        root = snapshot['root']['folder']
        entries = snapshot['entries']
        self.by_path = {pathkey(e): e for e in entries}
        self.by_id = {e['file_id']: e for e in entries}
        if not entries or len(self.by_id) != len(entries) or len(self.by_path) != len(entries):
            raise ValueError('Expected a nonempty listing with unique Dropbox IDs and paths.')
        namespace = entries[0]['path'].split('//', 1)[0]
        self.root_key = (namespace + '/' + root['path_lower']).casefold()
        self.children = defaultdict(list)
        self.image_counts = Counter()
        self.display = {self.root_key: root['path_display']}
        self.components = []
        self.review = []
        self.family = {}
        self.family_role_folders = defaultdict(list)
        self.group_folders = defaultdict(list)
        self.old_by_id = {e['file_id']: e for e in original['entries'] if folder(e)}
        self.old_by_path = {pathkey(e): e for e in self.old_by_id.values()}
        for e in sorted(entries, key=lambda e: (e['path'].count('/'), e['path'].casefold())):
            pk = parent(e)
            if pk not in self.display or (pk != self.root_key and not folder(self.by_path[pk])):
                raise ValueError('Missing folder for ' + e['path'])
            self.children[pk].append(e)
            if folder(e):
                self.display[pathkey(e)] = e.get('path_display') or self.display[pk] + '/' + e['name']
            elif Path(e['name']).suffix.casefold() in IMAGE_EXTENSIONS and e.get('file', {}).get('size', 0):
                while pk != self.root_key:
                    self.image_counts[pk] += 1
                    pk = parent(self.by_path[pk])
        for fam in self.children[self.root_key]:
            if not folder(fam) or fam['name'].startswith('_') or normal(fam['name']) == 'collection together':
                continue
            for e in self.children[pathkey(fam)]:
                if not folder(e):
                    continue
                self.family[e['file_id']] = fam['name']
                kind = component_kind(e, fam['name'], self.children[pathkey(e)])
                if kind == 'component':
                    self.components.append(e)
                elif kind == 'review':
                    self.review.append(e)
                role = role_name(e['name'])
                if role:
                    self.family_role_folders[(pathkey(fam), role)].append(e)
                if kind == 'arrangement' or (role and ' and ' in normal(e['name'])):
                    if role:
                        self.group_folders[role].append(e)
                    for sub in self.children[pathkey(e)]:
                        if folder(sub) and (subrole := role_name(sub['name'])):
                            self.group_folders[subrole].append(sub)

        def natural(text):
            return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', normal(text))]
        self.components.sort(key=lambda e: (natural(self.family[e['file_id']]), natural(e['name'])))
        self.names = {(parent(e), normal(e['name'])) for e in self.components}
        self.group_members = self.match_group_folders()

    def match_group_folders(self):
        """Read named members and their following finish, including a finish shared by a list."""
        stems = defaultdict(list)
        for e in self.components:
            stem, finish = identity_finish(e['name'])
            if finish:
                stems[stem].append((e, finish))
        full_names = {stem: stem for stem in stems}
        # The Deco Palm and Spiral family also uses "Palm 1" and "Spiral 2" in group labels.
        deco_names = full_names.copy()
        for stem in stems:
            if stem.startswith('deco palm and spiral '):
                deco_names[stem.removeprefix('deco palm and spiral ')] = stem

        def matcher(names):
            alternatives = '|'.join(re.escape(s) for s in sorted(names, key=len, reverse=True))
            return re.compile(r'(?<!\w)(?:' + alternatives + r')(?!\w)')
        full_pattern = matcher(full_names)
        deco_pattern = matcher(deco_names)
        members = defaultdict(list)
        for role, folders in self.group_folders.items():
            for f in folders:
                # For a generically named role subfolder the arrangement parent identifies the members.
                p = self.by_path[parent(f)]
                family_level = parent(p) == self.root_key
                body = ROLE_NAMES[role].split(normal(f['name']), maxsplit=1)[0].strip()
                if not body and not family_level:
                    body = normal(p['name'])
                family = p if family_level else self.by_path[parent(p)]
                names, pattern = (deco_names, deco_pattern) if normal(family['name']) == 'deco palm and spiral' else (full_names, full_pattern)
                matches = list(pattern.finditer(body))
                if len(matches) < 2:
                    continue
                # Clear the pending members at each explicit finish or unrecognised qualifier.
                pending = []
                for i, match in enumerate(matches):
                    pending.append(names[match.group()])
                    end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
                    tail = body[match.end():end].strip()
                    if tail in ('', 'and'):
                        continue
                    finish = next((fini for fini in FINISHES if tail == fini or tail.startswith(fini + ' ')), None)
                    for stem in pending:
                        for e, wanted in stems[stem]:
                            key = (e['file_id'], role)
                            if wanted == finish and f not in members[key]:
                                members[key].append(f)
                    pending = []
        return members

    def record(self, e, match=None):
        path = self.display[pathkey(e)]
        children = self.children[pathkey(e)]
        result = {
            'id': e['file_id'], 'name': e['name'], 'path': path,
            'url': 'https://www.dropbox.com/home' + quote(path, safe='/'),
            'image_count': self.image_counts[pathkey(e)], 'child_count': len(children),
            'file_count': sum(c['object_type'] == 'file' for c in children),
            'empty': not children,
        }
        if match:
            result['match'] = match
        return result

    def previous_sibling(self, component, role):
        # Both Dropbox IDs must still exist side by side, and the old label cannot belong
        # to another current component. This covers the Islington water feature rename.
        old = self.old_by_id.get(component['file_id'])
        if not old or normal(old['name']) == normal(component['name']) or (parent(component), normal(old['name'])) in self.names:
            return None
        old_peer = self.old_by_path.get(pathkey(old) + ' ' + role.casefold())
        live = self.by_id.get(old_peer['file_id']) if old_peer else None
        if live and folder(live) and parent(live) == parent(component) and normal(live['name']) == normal(old_peer['name']):
            return live
        return None

    def coverage(self, component, role):
        name = normal(component['name'])
        exact = name + ' ' + role.casefold()
        found = []
        for sub in self.children[pathkey(component)]:
            if folder(sub) and role_name(sub['name']) == role:
                how = 'named_subfolder' if normal(sub['name']) == exact else 'component_subfolder'
                found.append(self.record(sub, how))
        for peer in self.family_role_folders[(parent(component), role)]:
            left, right = ROLE_NAMES[role].split(normal(peer['name']), maxsplit=1)
            if left.strip() == name and not right.strip():
                found.append(self.record(peer, 'named_sibling'))
        if previous := self.previous_sibling(component, role):
            found.append(self.record(previous, 'renamed_component_sibling'))
        order = ['named_subfolder', 'component_subfolder', 'named_sibling', 'renamed_component_sibling']
        found.sort(key=lambda f: (order.index(f['match']), normal(f['name'])))
        shared = [self.record(f, 'named_group') for f in self.group_members.get((component['file_id'], role), [])]
        shared.sort(key=lambda f: f['path'].casefold())
        return found, shared


def in_situ_audit(tree):
    rows = []
    for e in tree.components:
        dedicated, shared = tree.coverage(e, SITU)
        dc = sum(f['image_count'] for f in dedicated)
        sc = sum(f['image_count'] for f in shared)
        rows.append({
            'name': e['name'], 'family': tree.family[e['file_id']], 'component_id': e['file_id'],
            'component_url': tree.record(e)['url'], 'dedicated': dedicated, 'shared': shared,
            'dedicated_image_count': dc, 'shared_image_count': sc,
            'status': 'dedicated' if dc else 'shared_only' if sc else 'missing',
            'dedicated_folder_missing': not dedicated,
            'dedicated_folder_without_images': bool(dedicated) and not dc,
        })
    status = Counter(r['status'] for r in rows)
    return {'summary': {
        'checked_at': tree.snapshot['checked_at'], 'checked_components': len(rows),
        'with_dedicated_images': status['dedicated'], 'with_shared_images_only': status['shared_only'],
        'without_matching_in_situ_images': status['missing'],
        'without_populated_dedicated_folder': len(rows) - status['dedicated'],
        'dedicated_folder_absent': sum(r['dedicated_folder_missing'] for r in rows),
        'dedicated_folder_without_images': sum(r['dedicated_folder_without_images'] for r in rows),
        'method': 'Images in dedicated folders and group folders that name the component and its finish.',
    }, 'components': rows}


def load_tree(base=BASE):
    return Inventory(json.loads((base / 'inventory-in-situ.json').read_text()),
                     json.loads((base / 'inventory-before.json').read_text()))


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    audit = in_situ_audit(load_tree())
    write_json(BASE / 'in-situ-audit.json', audit)
    print(json.dumps(audit['summary'], indent=2))
