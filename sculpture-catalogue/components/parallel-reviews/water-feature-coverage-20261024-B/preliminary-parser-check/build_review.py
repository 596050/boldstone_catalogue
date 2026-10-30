"""Read-only coverage review of saved within-root water-related inventories."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, parse_qs
import hashlib
import json

LANE = Path(__file__).resolve().parent
BASE = LANE.parents[3]
CAT = BASE / 'sculpture-catalogue'
ALLOWED = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
SOURCES = {
    'pointer': CAT / 'current-master.json',
    'structure': BASE / 'reports/dropbox-structure-technical-review-20261023T213001Z/current-structure-snapshot.json',
    'water_snapshot': BASE / 'reports/dropbox-wall-only-water-leaf-shellmoon-review-20261023T235909Z/native-source-snapshot.json',
    'recent_snapshot': BASE / 'reports/dropbox-wall-only-chiswick-echo-bone-review-20261024T183336Z/fresh-closing-native-listings-and-candidate-metadata.json',
    'recent_observations': BASE / 'reports/dropbox-wall-only-chiswick-echo-bone-review-20261024T183336Z/review-observations.json',
}

def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def objsha(v): return hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')
def display(path): return path.split('//', 1)[1] if path.startswith('ns:') else path
def path_from_url(url):
    z = urlsplit(url); p = unquote(z.path)
    for prefix in ['/home', '/preview']:
        if p.startswith(prefix + '/'):
            return p[len(prefix):] + ('/' + parse_qs(z.query)['preview'][0] if 'preview' in parse_qs(z.query) else '')
    raise ValueError(url)
def family(path): return display(path)[len(ALLOWED) + 1:].split('/')[0]
def folder_url(path): return 'https://www.dropbox.com/home' + quote(path, safe='/')
def image_url(path): return folder_url(path.rsplit('/', 1)[0]) + '?preview=' + quote(path.rsplit('/', 1)[1], safe='')

pointer = read(SOURCES['pointer'])
SOURCES['register'] = CAT / pointer['register']
SOURCES['native_map'] = CAT / pointer['current_native_reference_map']['path']
SOURCES['audit'] = SOURCES['register'].parent / 'image-coverage-current.json'
guards = {str(p): sha(p) for p in SOURCES.values()}
guards[str(CAT / pointer['workbook'])] = pointer['workbook_sha256']
for name in ['checkpoint.json', 'components/checkpoint.json', 'components/reviews/specification_review_progress.json']:
    guards[str(CAT / name)] = sha(CAT / name)
g = read(SOURCES['register']); audit = read(SOURCES['audit']); native = read(SOURCES['native_map'])
active = {x['product_id']: x for x in g['options'] if x['product_id'] in g['active_option_ids']}
assert len(active) == 188 and sha(SOURCES['register']) == pointer['register_sha256']
named_options = [o for o in active.values() if any(t in o['name'].lower() for t in ['water', 'fountain', 'basin'])]
families = {family(path_from_url(o['folder_url'])) for o in named_options}
families.add('Moonphases')
selected_families = {s.casefold() for s in families}
objects = {}; rejected_outside = 0

def add(entries, source, source_locator):
    global rejected_outside
    for i, entry in enumerate(entries):
        p = display(entry.get('display_path') or entry.get('path_display') or entry.get('path', ''))
        if not p.startswith(ALLOWED + '/'):
            rejected_outside += 1; continue
        if family(p).casefold() not in selected_families: continue
        fid = entry.get('file_id') or entry.get('id')
        if not fid: continue
        typ = entry.get('object_type') or entry.get('tag') or ('.tag' in entry and entry['.tag'])
        if typ not in ['file', 'folder']: continue
        previous = objects.get(fid, {})
        objects[fid] = {'id': fid, 'type': typ, 'path': p, 'name': entry.get('name', p.rsplit('/', 1)[1]),
                        'size': entry.get('size', entry.get('file', {}).get('size', previous.get('size'))),
                        'parent_id': entry.get('parent_id', previous.get('parent_id')),
                        'evidence': previous.get('evidence', []) + [{'path': str(source), 'locator': source_locator + '/' + str(i)}]}

structure = read(SOURCES['structure'])
for i, r in enumerate(structure['results']):
    add([r['family']], SOURCES['structure'], f'/results/{i}/family-as-array')
    for j, page in enumerate(r['pages']): add(page['entries'], SOURCES['structure'], f'/results/{i}/pages/{j}/entries')
water = read(SOURCES['water_snapshot'])
for i, r in enumerate(water['families']):
    for j, page in enumerate(r['pages']): add(page['entries'], SOURCES['water_snapshot'], f'/families/{i}/pages/{j}/entries')
recent = read(SOURCES['recent_snapshot'])
for i, r in enumerate(recent['listings']):
    add([r['folder']], SOURCES['recent_snapshot'], f'/listings/{i}/folder-as-array')
    add(r['result']['entries'], SOURCES['recent_snapshot'], f'/listings/{i}/result/entries')
# Canonical map incorporates completed later moves such as Battersea2. It is scoped,
# so it overlays saved full family listings rather than replacing them.
for fid, o in native['current_objects'].items():
    add([o], SOURCES['native_map'], '/current_objects/' + fid + '/object-as-array')
by_path = {o['path'].casefold(): o for o in objects.values()}
files_by_folder = defaultdict(list)
for o in objects.values():
    if o['type'] == 'file':
        parent = by_path.get(o['path'].rsplit('/', 1)[0].casefold())
        if parent:
            o['parent_id'] = parent['id']; files_by_folder[parent['id']].append(o)

role_bindings = defaultdict(list)
for row in audit['coverage']:
    for role in ['individual', 'in_situ', 'series']:
        value = row.get(role, {}); ref = value.get('reference') or {}
        if ref.get('folder_id'):
            role_bindings[ref['folder_id']].append({'option_id': row['option_id'], 'name': row['name'], 'role': role,
                'status': value.get('status'), 'file_id': ref.get('file_id'), 'image_url': ref.get('image_url'), 'folder_url': ref.get('folder_url')})
arrangements_by_folder = defaultdict(list)
for r in g['arrangement_context_references']:
    if r.get('folder_id'): arrangements_by_folder[r['folder_id']].append(r)
configs_by_folder = defaultdict(list)
for c in g['source_media_configuration_coverage']:
    for key in ['baseline_solo_folder_ids', 'baseline_context_folder_ids', 'baseline_series_folder_ids']:
        for fid in c.get(key, []):
            configs_by_folder[fid].append({'configuration_id': c['configuration_id'], 'association': key,
                'coverage_state': c['coverage_state'], 'existing_target_option_ids': c.get('exact_supported_target_ids', []),
                'qualification': c.get('exact_supported_target_basis', '')})

folders = []
for o in sorted(objects.values(), key=lambda o: o['path'].casefold()):
    if o['type'] != 'folder' or len(o['path'][len(ALLOWED) + 1:].split('/')) < 2: continue
    fam = family(o['path'])
    if fam.casefold() == 'moonphases' and 'water' not in o['name'].lower(): continue
    sources = sorted(files_by_folder[o['id']], key=lambda f: f['name'].casefold())
    direct = [x['product_id'] for x in active.values() if x.get('folder_id') == o['id']]
    roles = role_bindings[o['id']]; arrangements = arrangements_by_folder[o['id']]; configs = configs_by_folder[o['id']]
    selected_fids = [active[oid]['file_id'] for oid in direct] + [x['file_id'] for x in roles]
    chosen = next((s for fid in selected_fids for s in sources if s['id'] == fid), sources[0] if sources else None)
    status = ('Current product reference' if direct else 'Existing image-role reference' if roles else
              'Existing arrangement reference' if arrangements else 'Retained configuration evidence' if configs else
              'Family photographs; no direct option binding established by this audit')
    folders.append({'family': fam, 'folder_id': o['id'], 'folder_path': o['path'], 'folder_url': folder_url(o['path']),
        'saved_inventory_file_count': len(sources), 'status': status, 'direct_option_ids': direct, 'role_bindings': roles,
        'arrangement_refs': [r['reference_id'] for r in arrangements], 'configuration_evidence': configs,
        'representative_image': None if chosen is None else {'file_id': chosen['id'], 'path': chosen['path'],
            'image_url': image_url(chosen['path']), 'selection_basis': 'Existing selected reference' if chosen['id'] in selected_fids else 'First filename in saved folder inventory; navigation example only'},
        'source_evidence': o['evidence'], 'missing_product_inferred': False, 'new_option_created': False})

water_ids = {o['product_id'] for o in named_options}
review_options = []
for o in active.values():
    if not o.get('folder_url'): continue
    fam = family(path_from_url(o['folder_url']))
    if fam.casefold() not in selected_families or fam == 'Moonphases': continue
    disposition = o.get('current_listing_resolution', {})
    offers = []
    for e in g['source_offer_edges']:
        if any(o['canonical_design_id'] in m['canonical_component_targets'] for m in e['members']):
            offers.append({'offer_ref': e['offer_ref'], 'title': e['source_offer']['title'],
                'sku': e['source_offer'].get('sku'), 'historical_platform': e['source_offer'].get('platform'),
                'qualification': 'Retained component-level association; exact current finish, build and native product match not inferred.'})
    candidate = objects.get(o['file_id']); current_path = path_from_url(o['image_url'])
    review_options.append({'option_id': o['product_id'], 'name': o['name'], 'design_id': o['canonical_design_id'],
        'family': fam, 'water_or_basin_name_screen': o['product_id'] in water_ids,
        'scope_note': 'Water-related name or basin screen; functioning plumbing and water-ready build are not newly verified.' if o['product_id'] in water_ids else 'Existing companion sculpture option in the same family; not newly classified as a water feature.',
        'image_url': o['image_url'], 'folder_url': o['folder_url'], 'file_id': o['file_id'], 'folder_id': o['folder_id'],
        'primary_inventory_binding': {'present': candidate is not None, 'path_matches': bool(candidate and candidate['path'] == current_path),
            'parent_matches': bool(candidate and candidate['parent_id'] == o['folder_id'])},
        'master_fields': o['master_fields'], 'complete_option_sha256': objsha(o),
        'listing_resolution': {k: disposition.get(k) for k in ['current_source_resolution_disposition', 'source_supported_individual_record_present', 'conditional_native_tuple', 'next_action']},
        'component_related_source_offers': offers,
        'count_scope': 'Existing active catalogue option. No product, physical cast, mould, stock or live offer added.'})
review_options.sort(key=lambda x: (x['family'].casefold(), not x['water_or_basin_name_screen'], x['name']))
moonphase = next(r for r in g['arrangement_context_references'] if r['reference_id'] == 'REF-MOONPHASE-WATER-FEATURE-WHITE-01')
moonphase_members = [e for e in g['confirmed_arrangement_member_edges'] if e['reference_id'] == moonphase['reference_id']]
arrangement = {k: moonphase.get(k) for k in ['reference_id', 'name', 'image_url', 'folder_url', 'file_id', 'folder_id', 'component_identification', 'counted_as_working_product', 'individual_count_increment', 'owner_member_confirmation']}
arrangement['members'] = [{**e, 'individual_image_url': active[e['product_id']]['image_url'], 'individual_folder_url': active[e['product_id']]['folder_url']} for e in moonphase_members]
name_only_source = next(e for e in g['source_offer_edges'] if e['offer_ref'] == 'O017')
lexical_note = {'offer_ref': 'O017', 'title': name_only_source['source_offer']['title'],
    'note': 'The word Water in the historical Japanese Raked Water Path title is not sufficient to classify a functioning fountain. This source is retained separately from the named water/basin option screen.',
    'canonical_targets': sorted({t for m in name_only_source['members'] for t in m['canonical_component_targets']})}
result = {'schema': 'boldstone.saved-water-related-folder-product-coverage.v1', 'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'status': 'LOCAL_COVERAGE_REVIEW_COMPLETE_NO_NEW_IDENTITY_DECISIONS', 'source_guards': guards,
    'source_inventory_dates': {'structure': structure['captured_utc'], 'water': water['captured_utc'], 'recent_Chiswick_Bone': recent['recorded_utc'], 'canonical_pointer': pointer['recorded_utc']},
    'allowed_root': ALLOWED, 'families': sorted({r['family'] for r in folders}),
    'counts': {'screened_named_water_or_basin_options': len(named_options), 'existing_options_in_related_families': len(review_options),
        'reviewed_folder_records': len(folders), 'saved_inventory_files_in_reviewed_folders': sum(r['saved_inventory_file_count'] for r in folders),
        'confirmed_Moonphase_members': len(moonphase_members), 'new_options': 0, 'new_image_roles': 0, 'new_physical_verifications': 0,
        'native_calls': 0, 'native_writes': 0, 'platform_writes': 0, 'shared_writes': 0},
    'limitations': ['This is a saved-inventory coverage check, not a fresh whole-library enumeration.',
        'Folder examples are navigation references, not new primary-image or photo-role selections.',
        'Group membership does not establish a separate fountain product, panel quantities, plumbing, physical stock or a water-ready build.',
        'A folder without a direct primary binding is not proof of a missing sculpture.',
        'Current owner holds and the separate Chiswick015/Echo23 filing proposals remain unchanged.'],
    'folder_status_counts': dict(Counter(r['status'] for r in folders)), 'folders': folders, 'options': review_options,
    'Moonphase_arrangement': arrangement, 'name_only_source_note': lexical_note,
    'unmatched_folder_records': [r['folder_id'] for r in folders if not(r['direct_option_ids'] or r['role_bindings'] or r['arrangement_refs'] or r['configuration_evidence'])]}
save('coverage-review.json', result)

def a(url, label): return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'
style = '<style>body{font:16px/1.55 system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#18352d;background:#faf9f5}article{background:white;border:1px solid #d4ddd7;padding:22px;margin:20px 0;border-radius:9px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;text-align:left;vertical-align:top;padding:9px}a{color:#166b66}small{color:#53675e}.tag{font-weight:600}nav{padding:15px;background:#e7eee7}h2{margin-top:0}pre{white-space:pre-wrap}</style>'
parts = ['<!doctype html><meta charset="utf-8"><title>Water-related catalogue coverage</title>', style,
    '<h1>Water-related catalogue coverage</h1><p>Existing catalogue entries, saved Dropbox folders and arrangement links. No new products or photograph roles were created.</p>',
    f'<p>{len(named_options)} water/basin-named options; {len(review_options)} existing options including companion sculptures; {len(folders)} folder records. Saved inventory dates range from 23–24 October 2026; no fresh Dropbox read in this review.</p>',
    '<nav>' + a('#options', 'Individual entries') + ' · ' + a('#folders', 'Folder coverage') + ' · ' + a('#moonphases', 'Moonphases group') + ' · ' + a('#limits', 'Scope and remaining work') + '</nav>', '<h2 id="options">Individual entries</h2>']
terminal = []
for i, o in enumerate(review_options, 1):
    parts += [f'<article id="{o["option_id"]}"><h2>{i}. {escape(o["name"])}</h2><p>{a(o["image_url"], "Image")} · {a(o["folder_url"], "Containing folder")}</p><p>{escape(o["scope_note"])}</p><table><thead><tr><th>Specification</th><th>Accepted working detail</th></tr></thead><tbody>']
    for k, v in o['master_fields'].items():
        text = v.get('display', str(v)) if isinstance(v, dict) else str(v)
        parts.append(f'<tr><td>{escape(k)}</td><td>{escape(text)}</td></tr>')
    parts += ['</tbody></table>', f'<p>Platform disposition: {escape(o["listing_resolution"].get("current_source_resolution_disposition") or "Retained source review")}. Exact active account and physical configuration are not newly certified.</p>',
        '<p>Related historical source offers: ' + escape(', '.join(x['offer_ref'] + ' ' + x['title'] for x in o['component_related_source_offers']) or 'No retained component-level offer association') + '</p></article>']
    terminal += [f'{i}. {o["name"]}', 'Image: ' + o['image_url'], 'Folder: ' + o['folder_url'],
                 'Coverage: ' + json.dumps(o['primary_inventory_binding']), 'Platform: ' + str(o['listing_resolution'].get('current_source_resolution_disposition')), '']
parts.append('<h2 id="folders">Folder coverage</h2>')
for r in folders:
    ex = r['representative_image']; links = a(r['folder_url'], 'Containing folder') + (' · ' + a(ex['image_url'], 'Example image') if ex else '')
    names = [active[i]['name'] for i in r['direct_option_ids']]
    parts += [f'<article><h3>{escape(r["folder_path"].split(ALLOWED + "/")[1])}</h3><p>{links}</p><p>{escape(r["status"])}. {r["saved_inventory_file_count"]} files in the combined saved inventory.</p>',
        '<p>Direct current entries: ' + escape('; '.join(names) or 'None selected from this folder; this does not imply a missing product') + '</p>',
        f'<small>{len(r["role_bindings"])} existing photo-role links; {len(r["arrangement_refs"])} arrangement links; {len(r["configuration_evidence"])} retained configuration references.</small></article>']
parts += ['<article id="moonphases"><h2>Moonphases — White water-feature arrangement</h2><p>' + a(arrangement['image_url'], 'Group image') + ' · ' + a(arrangement['folder_url'], 'Containing folder') + '</p>',
    '<p>The owner-confirmed members are the existing White Moonphase 1–4 designs. The group adds no separate product; plumbing, positions, quantities and a water-ready build remain unconfirmed.</p><ul>']
for e in arrangement['members']: parts.append('<li>' + escape(e['product_name']) + ': ' + a(e['individual_image_url'], 'Individual image') + ' · ' + a(e['individual_folder_url'], 'Folder') + '</li>')
parts += ['</ul></article><article id="limits"><h2>Scope and remaining work</h2><ul>']
parts += ['<li>' + escape(x) + '</li>' for x in result['limitations']]
parts += ['</ul><p>' + escape(lexical_note['note']) + '</p><p>Working prices, estimates, made-to-order availability and 1–2 week lead times are retained as recorded. Existing platform holds remain in force.</p></article>']
with (LANE / 'review.html').open('x') as f: f.write('\n'.join(parts))
with (LANE / 'terminal-review.txt').open('x') as f: f.write('\n'.join(terminal))
save('input-manifest.json', {name: {'path': str(p), 'sha256': guards[str(p)]} for name, p in SOURCES.items()})
assert all(sha(p) == h for p, h in guards.items()), 'Read-only source changed during review'
print(json.dumps({'status': result['status'], 'counts': result['counts'], 'folder_status_counts': result['folder_status_counts'],
    'unmatched_folder_records': result['unmatched_folder_records'],
    'primary_binding_failures': [o['option_id'] for o in review_options if not all(o['primary_inventory_binding'].values())]}, indent=2))
