"""Build the local photo checklist and its linked audits from the same Dropbox scan."""

import html
import json
from collections import Counter
from datetime import datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from audit_in_situ import (
    BASE, DETAIL, HIGH, ROLES, SITU, folder, in_situ_audit, load_tree, pathkey,
    role_name, write_json,
)


def report_data(tree, sit, creations):
    situ_by_id = {r['component_id']: r for r in sit['components']}
    rows = []
    targets = []
    used_ids = set()
    for e in tree.components:
        comp = tree.record(e)
        sr = situ_by_id[comp['id']]
        row = {
            'component_id': comp['id'], 'name': comp['name'], 'family': sr['family'],
            'component_path': comp['path'], 'component_url': comp['url'],
            'folders': {}, 'coverage': {}, 'missing_roles': [], 'related_folders': [],
        }
        for role in ROLES:
            if role == SITU:
                dedicated, shared = sr['dedicated'], sr['shared']
            else:
                dedicated, shared = tree.coverage(e, role)
            used_ids.update(f['id'] for f in dedicated + shared)
            count = sum(f['image_count'] for f in dedicated)
            group_count = sum(f['image_count'] for f in shared)
            covered = bool(count or (role == SITU and group_count))
            row['coverage'][role] = {
                'dedicated': dedicated, 'shared': shared, 'dedicated_image_count': count,
                'shared_image_count': group_count, 'covered': covered,
            }
            if not covered:
                row['missing_roles'].append(role)
            if role == SITU:
                continue
            # The filing view describes the actual role folder inside the component. Sibling
            # Detail collections can supply photographs even when that subfolder is empty.
            inside = [f for f in dedicated if f['match'] in ('named_subfolder', 'component_subfolder')]
            if inside:
                target = dict(inside[0])
                target['created_at'] = creations.get(target['id'])
            else:
                target = {'name': role, 'id': None, 'path': None, 'url': None,
                          'child_count': 0, 'file_count': 0, 'image_count': 0,
                          'empty': False, 'created_at': None}
            target.update(role=role, folder_missing=not inside, created=bool(target['created_at']))
            row['folders'][role] = target
            targets.append(target)
        target_ids = {f['id'] for f in row['folders'].values()}
        related = {sub['file_id']: tree.record(sub) for sub in tree.children[pathkey(e)]
                   if folder(sub) and sub['file_id'] not in target_ids}
        for role in (HIGH, DETAIL):
            for f in row['coverage'][role]['dedicated']:
                if f['id'] not in target_ids:
                    related[f['id']] = f
        row['related_folders'] = list(related.values())
        rows.append(row)

    empty_rows = [r for r in rows if any(f['empty'] for f in r['folders'].values())]
    filing_rows = [r for r in rows if any(not f['image_count'] for f in r['folders'].values())]
    missing = Counter(role for r in rows for role in r['missing_roles'])
    unassigned = {}
    for candidates in (*tree.family_role_folders.values(), *tree.group_folders.values()):
        for f in candidates:
            if f['file_id'] not in used_ids and tree.image_counts[pathkey(f)]:
                unassigned[f['file_id']] = dict(tree.record(f), role=role_name(f['name']))
    review = [dict(tree.record(e), family=tree.family[e['file_id']],
                   subfolders=[f['name'] for f in tree.children[pathkey(e)] if folder(f)])
              for e in tree.review]
    summary = {
        'checked_at': tree.snapshot['checked_at'], 'started_at': tree.snapshot['started_at'],
        'component_finish_folders': len(rows), 'families': len({r['family'] for r in rows}),
        'components_with_any_gap': sum(bool(r['missing_roles']) for r in rows),
        'components_missing_all_three': sum(len(r['missing_roles']) == 3 for r in rows),
        'components_with_all_three': sum(not r['missing_roles'] for r in rows),
        'missing_by_role': {role: missing[role] for role in ROLES},
        'group_detail_only': sum(not r['coverage'][DETAIL]['covered'] and
                                 bool(r['coverage'][DETAIL]['shared_image_count']) for r in rows),
        'required_folders': len(targets), 'existing_role_subfolders': sum(bool(f['id']) for f in targets),
        'empty_high_resolution': sum(f['role'] == HIGH and f['empty'] for f in targets),
        'empty_in_detail': sum(f['role'] == DETAIL and f['empty'] for f in targets),
        'empty_folders': sum(f['empty'] for f in targets),
        'component_finish_folders_with_empty_folders': len(empty_rows),
        'components_with_unfilled_role_subfolders': len(filing_rows),
        'populated_folders': sum(bool(f['id']) and not f['empty'] for f in targets),
        'recursive_pages_after': tree.snapshot['pages'], 'final_listing_complete': True,
        'listed_folders': sum(folder(e) for e in tree.by_id.values()),
        'listed_files': sum(not folder(e) for e in tree.by_id.values()),
        'scope_review_folders': len(review),
        'in_situ': sit['summary'],
    }
    audit = {
        'summary': summary, 'root': tree.snapshot['root']['folder']['path_display'],
        'components': rows, 'scope_review': review,
        'unassigned_photo_folders': sorted(unassigned.values(), key=lambda f: f['path'].casefold()),
    }
    return audit, {'summary': summary, 'components': empty_rows}


def esc(value):
    return html.escape(str(value), quote=True)


def link(url, label, title=''):
    tooltip = f' title="{esc(title)}"' if title else ''
    return f'<a href="{esc(url)}"{tooltip} target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def images(count):
    return f'{count} image' + ('' if count == 1 else 's')


def folder_evidence(f):
    label = link(f['url'], f['name'], f['path'])
    contents = images(f['image_count']) if f['image_count'] else ('Empty folder' if f['empty'] else 'No image files')
    origin = ''
    if f.get('match') == 'renamed_component_sibling':
        origin = ' · filed under the former component name'
    return f'<li>{label}<br><small>{contents}{origin}</small></li>'


def role_cell(row, role):
    info = row['coverage'][role]
    fs, groups = info['dedicated'], info['shared']
    count, group_count = info['dedicated_image_count'], info['shared_image_count']
    if count:
        label = images(count)
    elif role == SITU and group_count:
        label = 'Shared only · ' + images(group_count)
    elif fs:
        label = 'No individual images' if group_count else 'No images'
    else:
        label = 'No matching folder'
    css = 'present' if info['covered'] else 'missing'
    summary_label = esc(label)
    if not count and group_count and role == DETAIL:
        css += ' group-detail'
        summary_label = (f'<span class="individual-label">{esc(label)}</span>'
                         f'<span class="group-label">Shared only · {images(group_count)}</span>')
    elif not count and group_count and role == SITU:
        css += ' group-situ'
    populated = [f for f in fs if f['image_count']]
    simple = len(fs) == 1 and not groups and fs[0]['match'] in ('named_subfolder', 'named_sibling')
    if simple:
        body = link(fs[0]['url'], label, fs[0]['path'])
    elif fs or groups:
        body = '<details><summary>' + summary_label + '</summary><ul>'
        body += ''.join(folder_evidence(f) for f in fs)
        if groups:
            body += '<li><small>Named group folders</small><ul>' + ''.join(folder_evidence(f) for f in groups) + '</ul></li>'
        body += '</ul></details>'
    else:
        body = esc(label)
    note = ''
    if role in (HIGH, DETAIL) and count and not row['folders'][role]['image_count']:
        note = 'Filed beside the component'
    elif any(f['match'] == 'renamed_component_sibling' for f in populated):
        note = 'Folder uses the former name'
    elif any(f['match'] == 'component_subfolder' for f in populated):
        note = 'Folder uses a different name'
    elif role == DETAIL and not count and group_count:
        note = f'{images(group_count)} in named group folders'
    elif not count and not group_count and fs:
        note = 'Empty folder' if all(f['empty'] for f in fs) else 'Folder has other items'
    notes = f'<small class="cell-note">{esc(note)}</small>' if note else ''
    return f'<td><div class="{css}">{body}</div>{notes}</td>'


KEYS = {HIGH: 'high', DETAIL: 'detail', SITU: 'situ'}


def render_row(r):
    gaps = ' '.join(KEYS[x] for x in r['missing_roles'])
    filing = any(not f['image_count'] for f in r['folders'].values())
    component = link(r['component_url'], r['name'], r['component_path'])
    return (f'<tr data-id="{esc(r["component_id"])}" data-search="{esc((r["family"] + " " + r["name"]).casefold())}" '
            f'data-gaps="{gaps}" data-filing="{int(filing)}" '
            f'data-situ-dedicated="{int(bool(r["coverage"][SITU]["dedicated_image_count"]))}" '
            f'data-group-detail="{int(bool(r["coverage"][DETAIL]["shared_image_count"]))}">'
            f'<th scope="row">{component}<small class="family">{esc(r["family"])}</small></th>'
            + ''.join(role_cell(r, role) for role in (DETAIL, HIGH, SITU)) + '</tr>')


STYLE = """
:root{color-scheme:light;--ink:#24352a;--leaf:#255d43;--muted:#536258;--line:#d6ded4;--paper:#fcfbf8}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
main{max-width:1280px;margin:auto;padding:32px 28px 54px}h1,h2,p{margin:0 0 12px}h1{font:500 clamp(29px,4vw,44px)/1.12 Georgia,serif}
h2{font:500 24px Georgia,serif;margin-top:28px}a{color:var(--leaf);text-underline-offset:3px}small,.muted{color:var(--muted)}
.totals{display:flex;flex-wrap:wrap;gap:12px 28px;margin:24px 0;padding:16px 0;border-block:1px solid var(--line)}
.totals a{color:inherit;text-decoration:none}.totals a:hover{text-decoration:underline}.totals b{display:block;font-size:25px}
.controls{display:flex;align-items:end;gap:12px 20px;flex-wrap:wrap;margin:20px 0 8px}
.controls label.field{display:grid;gap:4px;font-size:14px;font-weight:600}
input[type=search],select{font:inherit;padding:8px 10px;border:1px solid #9aa99d;border-radius:5px;background:white;color:var(--ink);max-width:100%}
.check{font-size:14px}.row-count{margin:10px 0;font-size:14px}.tablewrap{overflow:auto}table{width:100%;min-width:680px;border-collapse:collapse;background:white;font-size:14px}
th,td{padding:12px 14px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
thead th{background:#e7ede6}tbody th{width:33%;font-weight:600}td{width:22%}.family,.cell-note{display:block;margin-top:3px;font-weight:400}
summary{cursor:pointer}td summary{text-decoration:underline dotted;text-underline-offset:3px}td ul{padding-left:18px;max-width:29em;overflow-wrap:anywhere}td li{margin:6px 0}
.missing,.missing>a{font-weight:600;color:#88481d}.present,.present>a{color:var(--leaf)}
.group-label,.count-group-detail .individual-label{display:none}.count-group-detail .group-label{display:inline}
.count-group-detail .group-detail{color:var(--leaf);font-weight:400}.dedicated-situ .group-situ{color:#88481d;font-weight:600}
details.extra{margin:16px 0;padding:10px 14px;border:1px solid var(--line);border-radius:5px}details.extra summary{font-weight:600}
.method{max-width:1050px;margin-top:20px;font-size:14px}.foot{margin-top:24px;font-size:13px}
[hidden]{display:none!important}@media(max-width:650px){main{padding:22px 14px}.controls{align-items:start}.totals{gap:10px 24px}input[type=search]{width:100%}}
"""

SCRIPT = """
const find = document.getElementById('search'), view = document.getElementById('view');
const strict = document.getElementById('dedicatedOnly'), groupDetail = document.getElementById('groupDetail');
const rows = [...document.querySelectorAll('#photoFolders tbody tr')];
function update() {
  let n = 0;
  document.body.classList.toggle('dedicated-situ',strict.checked);
  document.body.classList.toggle('count-group-detail',groupDetail.checked);
  const query = find.value.trim().toLowerCase();
  for (const row of rows) {
    const gaps = new Set(row.dataset.gaps.split(' ').filter(Boolean));
    if (strict.checked && row.dataset.situDedicated === '0') gaps.add('situ');
    if (groupDetail.checked && row.dataset.groupDetail === '1') gaps.delete('detail');
    const match = {any:gaps.size>0, every:gaps.size===3, complete:gaps.size===0,
      all:true, filing:row.dataset.filing==='1'}[view.value] ?? gaps.has(view.value);
    row.hidden = !(match && row.dataset.search.includes(query));
    if (!row.hidden) n++;
  }
  document.getElementById('count').textContent = n + (n === 1 ? ' component shown' : ' components shown');
  document.getElementById('none').hidden = n !== 0;
}
const routes = {'missing-in-situ':'situ', 'empty-photo-folders':'filing',
  'missing-in-detail':'detail','missing-high-resolution':'high','missing-all-three':'every',
  'all-complete':'complete','photo-gaps':'any','all-components':'all'};
function fromHash() {
  const selected = routes[location.hash.slice(1)];
  if (selected) view.value = selected;
  update();
}
find.addEventListener('input',update);
for (const el of [view,strict,groupDetail]) el.addEventListener('change',update);
for (const a of document.querySelectorAll('.totals a, [data-filter-link]')) a.addEventListener('click',() => {
  view.value=routes[a.hash.slice(1)]; find.value=''; strict.checked=false; groupDetail.checked=false; update();
});
window.addEventListener('hashchange',fromHash);
fromHash();
"""


def render(audit):
    s, rows = audit['summary'], audit['components']
    checked = datetime.fromisoformat(s['checked_at'].replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/London'))
    date_text = checked.strftime('%-d %B %Y at %H:%M %Z')
    root_url = 'https://www.dropbox.com/home' + quote(audit['root'], safe='/')
    parts = [f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Boldstone — Sculpture photo folder checklist</title><style>{STYLE}</style></head><body><main>
<h1>Sculpture photo folder checklist</h1><p class="muted">Dropbox checked {esc(date_text)} · {s["component_finish_folders"]} component and finish folders in {s["families"]} families · {link(root_url, "01 Wall Sculptures")}</p>
<p><strong>{s["components_with_any_gap"]} components are missing at least one image type.</strong> {s["components_with_all_three"]} have all three.</p><nav class="totals" aria-label="Filter by photo coverage">''']
    for anchor, count, label in (
        ('missing-in-detail', s['missing_by_role'][DETAIL], 'Missing individual In Detail'),
        ('missing-high-resolution', s['missing_by_role'][HIGH], 'Missing High Resolution'),
        ('missing-in-situ', s['missing_by_role'][SITU], 'Missing In Situ'),
        ('missing-all-three', s['components_missing_all_three'], 'Missing all three'),
        ('all-complete', s['components_with_all_three'], 'Have all three'),
    ):
        parts.append(f'<a id="{anchor}" href="#{anchor}"><b>{count}</b>{label}</a>')
    parts.append('''</nav><section id="photo-gaps" aria-label="Component checklist"><div id="empty-photo-folders" class="controls">
<label class="field">Find a component or family<input id="search" type="search" placeholder="Name or family"></label>
<label class="field">Show<select id="view">
<option value="any">Missing any image type</option><option value="every">Missing all three</option>
<option value="detail">Missing In Detail</option><option value="high">Missing High Resolution</option>
<option value="situ">Missing In Situ</option><option value="filing">High Resolution or In Detail subfolder needs filing</option>
<option value="complete">Have all three</option><option value="all">All components</option></select></label>
<label class="check"><input type="checkbox" id="dedicatedOnly"> Require dedicated In Situ</label>
<label class="check"><input type="checkbox" id="groupDetail"> Count named group detail photos</label></div>
<p id="count" class="row-count" role="status"></p><div class="tablewrap"><table id="photoFolders"><thead><tr>
<th scope="col">Component and finish</th><th scope="col">In Detail</th><th scope="col">High Resolution</th><th scope="col">In Situ</th>
</tr></thead><tbody>''')
    parts.extend(render_row(r) for r in rows)
    parts.append(f'''</tbody></table></div><p id="none" hidden>No components match these filters.</p></section>
<p class="method">Counts use image files in labelled Dropbox folders, including their subfolders. An individually named <em>Details</em> folder beside a component counts towards its coverage. {s["group_detail_only"]} components have detail photos only in named group folders. The group detail checkbox includes those photos.</p>
<p class="method">{s["in_situ"]["with_dedicated_images"]} components have dedicated In Situ images and {s["in_situ"]["with_shared_images_only"]} have them only in a group folder naming the component and finish. The High Resolution label follows the folder designation. Pixel dimensions and photo content were not inspected.</p>
<p class="method"><a href="#empty-photo-folders" data-filter-link>Check component subfolders for filing</a> · {s["empty_in_detail"]} In Detail and {s["empty_high_resolution"]} High Resolution subfolders are empty. The component and image-count links open their current Dropbox folders.</p>''')
    if audit['scope_review']:
        parts.append('<details class="extra"><summary>Component folders to confirm (' + str(len(audit['scope_review'])) + ')</summary><ul>')
        for f in audit['scope_review']:
            label = link(f['url'], f['name'])
            parts.append(f'<li>{label} · {images(f["image_count"])} under {esc(f["family"])}. Its status as a component and finish is unconfirmed. Subfolders include {esc(", ".join(f["subfolders"]) or "none")}.</li>')
        parts.append('</ul></details>')
    if audit['unassigned_photo_folders']:
        parts.append('<details class="extra"><summary>Photo folders without a confirmed component and finish (' + str(len(audit['unassigned_photo_folders'])) + ')</summary><ul>')
        for f in audit['unassigned_photo_folders']:
            parts.append(f'<li>{link(f["url"], f["name"], f["path"])} · {images(f["image_count"])}</li>')
        parts.append('</ul></details>')
    parts.append('<p class="foot"><a href="folder-audit.json">Full component audit</a> · <a href="in-situ-audit.json">In Situ folder links</a> · <a href="empty-folder-links.json">Empty subfolders</a></p></main><script>' + SCRIPT + '</script></body></html>')
    return '\n'.join(parts)


def build(base=BASE):
    tree = load_tree(base)
    creations = {}
    receipts = base / 'creation-receipts.jsonl'
    if receipts.exists():
        for line in receipts.read_text().splitlines():
            r = json.loads(line)
            if r.get('status') == 'created':
                creations[r['response']['folder']['file_id']] = r['completed_at']
    sit = in_situ_audit(tree)
    audit, empty = report_data(tree, sit, creations)
    page = render(audit)
    write_json(base / 'in-situ-audit.json', sit)
    write_json(base / 'folder-audit.json', audit)
    write_json(base / 'empty-folder-links.json', empty)
    write_json(base / 'verification.json', audit['summary'])
    (base / 'empty-folder-list.html').write_text(page)
    return audit


if __name__ == '__main__':
    print(json.dumps(build()['summary'], indent=2))
