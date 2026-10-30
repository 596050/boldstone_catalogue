"""Working component visibility from explicitly named group folders.

This is folder organisation, never listing approval or manufactured identity.
Only a complete, unambiguous parse of known variant folder names is accepted.
Size/finish distinctions remain in the anchors; manual removals win later.
"""
from collections import defaultdict
from functools import lru_cache
from urllib.parse import unquote, urlparse
import re


def folder_name(url):
    return unquote(urlparse(url or '').path).rstrip('/').split('/')[-1]


def normal(value):
    return re.sub(r'\s+', ' ', value.replace('&', ' and ').casefold()).strip()


def strip_role(name):
    previous = None
    while name != previous:
        previous = name
        name = re.sub(r'\s+(in situ|details?|together|group|series|rear|workshop)$', '', name)
    return name


def match_group(label, anchors):
    label = strip_role(normal(label))
    # An established individual/variant folder takes precedence over parsing
    # words such as "Acanthus and Moon" as separate sculptures.
    if label in anchors:
        return []
    if ' and ' not in label:
        return []
    solutions = set()
    # The final named variant carries the finish: "... 1 and ... 2 White".
    # Other members may omit this exact suffix. Numbers may never be omitted.
    suffixes = {''}
    for name in anchors:
        if label.endswith(' and ' + name):
            words = name.split()
            for count in range(1, min(4, len(words) - 1) + 1):
                tail = ' '.join(words[-count:])
                if not re.search(r'\d', tail) and ' and ' not in tail:
                    suffixes.add(' ' + tail)
    for suffix in suffixes:
        aliases = defaultdict(set)
        for name, pids in anchors.items():
            if suffix and not name.endswith(suffix):
                continue
            aliases[name].update(pids)
            if suffix:
                aliases[name[:-len(suffix)]].update(pids)

        @lru_cache(None)
        def parse(text):
            found = []
            for alias, pids in aliases.items():
                # Ambiguous anchors never establish a default membership.
                if len(pids) != 1:
                    continue
                pid = next(iter(pids))
                if text == alias and alias in anchors:
                    found.append((pid,))
                elif text.startswith(alias + ' and '):
                    for rest in parse(text[len(alias) + 5:]):
                        if pid not in rest:
                            found.append((pid, *rest))
                if len(found) > 100:
                    return ()
            return tuple(found)

        for members in parse(label):
            if len(members) > 1:
                solutions.add(tuple(sorted(members)))
    return list(next(iter(solutions))) if len(solutions) == 1 else []


def group_defaults(cat):
    anchors = defaultdict(lambda: defaultdict(set))
    for pid, product in cat.products.items():
        name = strip_role(normal(folder_name(product.get('folder_url'))))
        if name:
            anchors[product.get('family', '')][name].add(pid)
    folders = {}
    result = {}
    for aid, asset in cat.assets.items():
        if asset.get('source') != 'Dropbox' or asset.get('source_unavailable'):
            continue
        # The current containing-folder URL is authoritative over old role labels.
        label = folder_name(asset.get('folder_url'))
        family = asset.get('family', '')
        key = (family, label)
        if key not in folders:
            folders[key] = match_group(label, anchors.get(family, {}))
        if folders[key]:
            result[aid] = folders[key]
    return result


def shown(view, pid, aid):
    edge = view.edges.get(pid, {}).get(aid)
    choice = view.decision('image', pid, aid)
    return bool(edge and (edge.get('tier') != 'related' or
                (choice.get('decision') != 'exclude' and 'listing' in choice.get('uses', []))))


def payload(view, aid):
    if aid not in view.cat.assets or view.cid(aid) != aid or aid in view.deleted:
        raise ValueError('This image is no longer available. Refresh the gallery.')
    asset = view.asset(aid)
    rows = []
    for pid, product in view.cat.products.items():
        edit = view.decision('field', pid, 'Name')
        name = edit.get('value') if edit.get('decision') == 'edit' else product['name']
        record = view.record('image', pid, aid)
        choice = record['data']
        assignment = view.record('assignment', pid, aid)
        rows.append({'product_id': pid, 'name': name, 'family': product['family'],
                     'shown': shown(view, pid, aid), 'default': pid in asset['default_component_ids'],
                     'removed': aid in view.removed.get(pid, {}), 'excluded': choice.get('decision') == 'exclude',
                     'listing': choice.get('decision') == 'reviewed' and 'listing' in choice.get('uses', []),
                     'advertising': choice.get('decision') == 'reviewed' and 'advertising' in choice.get('uses', []),
                     'image_version': record['version'], 'assignment_version': assignment['version'],
                     'image_member_versions': record.get('member_versions', {x: 0 for x in view.member_ids(aid)}),
                     'assignment_member_versions': assignment.get('member_versions', {x: 0 for x in view.member_ids(aid)})})
    return {'image': asset, 'rows': rows,
            'content_hash': asset.get('original', {}).get('dropbox_content_hash') or asset.get('original', {}).get('sha256')}
