import csv
import hashlib
import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

P = Path(__file__).resolve().parent
ROOT = Path('/Users/tprice/Documents/boldstone')
SCOPE = '/BOLDSTONE MASTER/Products/01 Wall Sculptures'
FAMILIES = [('Chiswick Moon', 'chiswick-moon'), ('Echo Sound', 'echo-sound'), ('Bone Spiral', 'bone-spiral')]

def read(path):
    return json.loads(Path(path).read_text())

def write(name, value):
    (P / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def home(path):
    return 'https://www.dropbox.com/home' + quote(path, safe='/')

def fq(path):
    return path.split('/', 1)[1] if path.startswith('ns:') else path

before = read(P / 'fresh-complete-native-listings.json')
closing = read(P / 'fresh-closing-native-listings-and-candidate-metadata.json')
for b, a in zip(before['listings'], closing['listings']):
    assert b['name'] == a['name'] and not b['result']['has_more'] and not a['result']['has_more']
    assert {x['file_id']: x for x in b['result']['entries']} == {x['file_id']: x for x in a['result']['entries']}

rows = []
by_family = {}
for family, slug in FAMILIES:
    rr = read(P / (slug + '-verified-originals-and-links.json'))
    by_family[family] = {x['review_index']: x for x in rr}
    for r in rr:
        assert r['sha256'] and r['dropbox_content_hash'] == r['content_hash']
        assert r['folder_path'].startswith(SCOPE + '/')
        assert r['folder_url'] == home(r['folder_path'])
        assert r['image_url'] == home(r['folder_path']) + '?preview=' + quote(r['name'], safe='')
        assert Path(r['local_path']).stat().st_size == r['size']
        rows.append(r)
assert len(rows) == len({r['id'] for r in rows}) == 353
assert sum(x['size'] for x in rows) == 1677148965

catalogue_before = read(P / 'protected-catalogue-references-before.json')
pointer = read(ROOT / 'sculpture-catalogue/current-master.json')
register_path = ROOT / 'sculpture-catalogue' / pointer['register']
register = read(register_path)
options = {x['product_id']: x for x in register['options']}
for option in catalogue_before['options']:
    assert options[option['product_id']] == option, option['product_id']
selected = {o[k] for o in catalogue_before['options'] for k in ('file_id', 'context_file_id') if o.get(k)}
write('protected-catalogue-reference-closing-check.json', {
    'recorded_utc': datetime.now(timezone.utc).isoformat(),
    'register': str(register_path), 'register_sha256': sha(register_path),
    'selected_options_checked': len(catalogue_before['options']),
    'all_eight_full_option_records_unchanged': True,
    'canonical_writes_by_this_review': 0,
    'other_sessions_may_publish_disjoint_navigation_changes': True,
})

candidate = by_family['Chiswick Moon'][16]
assert candidate['id'] == 'id:cnqzTNngPVsAAAAAAAufgw'
destination = by_family['Chiswick Moon'][1]
native_file, native_source, native_destination = closing['candidate_metadata']
assert native_file['metadata_type'] == 'file'
assert native_source['metadata_type'] == native_destination['metadata_type'] == 'folder'
assert native_file['file']['id'] == candidate['id']
assert native_file['file']['path_display'] == candidate['path_display']
assert native_file['file']['size'] == candidate['size']
assert native_source['folder']['id'] == candidate['folder_id']
assert native_destination['folder']['id'] == destination['folder_id']
assert candidate['id'] not in selected
target = destination['folder_path'] + '/' + candidate['name']
all_native = [x for z in closing['listings'] for x in z['result']['entries']]
assert not any(fq(x['path']).lower() == target.lower() for x in all_native)

def occurrences(value, identity, path=''):
    found = []
    if isinstance(value, dict):
        for k, v in value.items():
            found.extend(occurrences(v, identity, path + '/' + str(k)))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found.extend(occurrences(v, identity, path + '/' + str(i)))
    elif value == identity:
        found.append(path)
    return found

proposal = {
    'status': 'PROPOSED_NOT_APPLIED_AWAITING_EXACT_OWNER_CONFIRMATION',
    'operation': 'move', 'folders_to_create': [], 'native_writes': 0,
    'reason': 'Close framing of the panel; the surrounding water-feature installation is not shown. Retain this original as a product photograph.',
    'file_id': candidate['id'], 'original_name': candidate['name'],
    'size': candidate['size'], 'sha256': candidate['sha256'],
    'dropbox_content_hash': candidate['dropbox_content_hash'],
    'source_folder_id': candidate['folder_id'], 'source_folder_path': candidate['folder_path'],
    'source_folder_url': candidate['folder_url'], 'source_image_url': candidate['image_url'],
    'destination_folder_id': destination['folder_id'], 'destination_folder_path': destination['folder_path'],
    'destination_folder_url': destination['folder_url'], 'destination_path': target,
    'expected_current_image_url': destination['folder_url'] + '?preview=' + quote(candidate['name'], safe=''),
    'expected_counts': {'source_before': 15, 'source_after': 14, 'destination_before': 1, 'destination_after': 2, 'family_before': 20, 'family_after': 20},
    'destination_collision': False,
    'selected_primary_or_context': False,
    'current_register_exact_file_id_occurrences': occurrences(register, candidate['id']),
    'preserve': ['original filename', 'format', 'file identity', 'original bytes', 'all four selected Chiswick primary/context references', 'water-feature folders within Wall Sculptures'],
    'undo_after_application': 'Move the same file ID back to its original source folder, retaining the original filename.',
    'requires_fresh_live_guards_if_owner_approves_later': True,
}
write('proposed-chiswick-close-framing-move.json', proposal)

findings = []
def finding(code, family, indices, observation, next_step):
    rr = [by_family[family][i] for i in indices]
    findings.append({'id': code, 'family': family, 'status': 'OBSERVATION_ONLY_NO_NATIVE_CHANGE',
        'observation': observation, 'next_step': next_step, 'images': [
            {k: r[k] for k in ('review_index', 'id', 'name', 'folder_id', 'folder_path', 'folder_url', 'image_url', 'sha256')}
            for r in rr]})

finding('CHISWICK-01', 'Chiswick Moon', [16], proposal['reason'], 'Exact one-file move prepared separately; owner confirmation pending.')
finding('ECHO-01', 'Echo Sound', [46, 146, 147], 'Three dark brown/green/gold-looking pair photographs are filed under White. The photographs alone do not verify their finish name.', 'Hold these three files in place; compare their source evidence before proposing a finish destination.')
finding('ECHO-02', 'Echo Sound', [154, 155, 156, 157, 160, 163], 'Six tightly framed pair views in In Situ are candidates for the product folder under the owner close-framing convention.', 'Prepare a separate exact filing plan after the Chiswick item; no moves included in the current one-file proposal.')
finding('ECHO-03', 'Echo Sound', [53, 54, 55, 56, 57, 58, 84, 86, 101, 102, 109, 110, 111, 123, 129, 130, 131], 'Wider brick-wall pair views remain in the product folder. These are candidates for In Situ; this is a review set, not an approved move set.', 'Review these exact images against the close-framing boundary before a separate proposal. Intermediate framings remain unchanged.')
finding('BONE-01', 'Bone Spiral', [99, 100], 'Two component 2 panels photographed on a cluttered workbench are filed in component 2 In Situ.', 'Prepare a flat Bone Spiral 2 White Workshop Views destination proposal; no new folder or move is authorized by this observation.')
finding('BONE-02', 'Bone Spiral', list(range(107,124)) + list(range(130,151)), 'Thirty-eight detail crops of component 2 are filed in In Situ; no wider setting is visible.', 'Prepare an exact move plan to existing Bone Spiral 2 White, preserving filenames and component 2 identity.')
finding('BONE-03', 'Bone Spiral', [30, 42, 43, 44, 45, 46, 48], 'Seven photographs in the pair product folder frame only the narrow component 1 surface.', 'Check these crop references against the existing component 1 identity before proposing individual filing.')
finding('BONE-04', 'Bone Spiral', [101, 102, 105, 106], 'Four close photographs show two repeated component 2 panels, rather than two distinct component designs.', 'Retain repeated component identity; do not invent a new design number from the panel count.')
write('review-observations.json', findings)

observations_by_id = {}
for finding_row in findings:
    for r in finding_row['images']:
        observations_by_id.setdefault(r['id'], []).append(finding_row['id'])
decisions = []
for r in rows:
    decisions.append({**{k:r[k] for k in ('family','review_index','id','name','folder_id','folder_path','folder_url','image_url')},
        'reviewed_visually': True, 'native_action': 'NONE',
        'observation_ids': observations_by_id.get(r['id'], []),
        'disposition': 'EXACT_MOVE_PROPOSED_NOT_APPLIED' if r['id']==candidate['id'] else 'OBSERVATION_PENDING_SEPARATE_PLAN' if r['id'] in observations_by_id else 'RETAIN_CURRENT_FILING_NO_EXACT_CHANGE_PROPOSED'})
write('all-353-image-folder-links-and-review.json', decisions)
with (P/'all-353-image-folder-links.tsv').open('w', newline='') as f:
    out = csv.DictWriter(f, fieldnames=['family','review_index','id','name','folder_path','folder_url','image_url','disposition'], delimiter='\t', extrasaction='ignore')
    out.writeheader(); out.writerows(decisions)

style = '<meta charset="utf-8"><style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;line-height:1.5}table{border-collapse:collapse;width:100%}td,th{padding:8px;border:1px solid #ccc;text-align:left}img{max-width:100%;max-height:360px}article{padding:16px 0;border-bottom:1px solid #bbb}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}a{overflow-wrap:anywhere}</style>'
e = html.escape
def card(r, family):
    slug = next(s for f,s in FAMILIES if f == family)
    return '<article><img loading="lazy" src="thumbnails/'+slug+'/'+str(r['review_index']).zfill(3)+'.jpg"><p><a href="'+e(r['image_url'])+'">'+e(r['name'])+'</a><br><a href="'+e(r['folder_url'])+'">Containing folder</a></p></article>'
parts = [style, '<title>Chiswick, Echo Sound and Bone Spiral filing review</title><h1>353 original images reviewed</h1><p>Read-only review. No Dropbox changes applied. The exact Chiswick one-file proposal is separate from the later review observations below.</p>']
for family,slug in FAMILIES:
    parts.append('<p><a href="'+slug+'-all-image-folder-links.html">All '+str(len(by_family[family]))+' '+e(family)+' images and containing folders</a></p>')
parts.append('<p><a href="proposed-chiswick-close-framing-move.html">First exact proposed move: Chiswick 015.jpg</a></p>')
for f in findings:
    parts += ['<h2>'+e(f['id']+' — '+f['family'])+'</h2><p>'+e(f['observation'])+'</p><p>'+e(f['next_step'])+'</p><div class="grid">']
    parts += [card(r, f['family']) for r in f['images']]
    parts.append('</div>')
(P/'review-findings-and-all-family-links.html').write_text(''.join(parts))
single = [style, '<title>Chiswick Moon 015 exact move proposal</title><h1>Proposed move: 015.jpg</h1><p>Not applied. No folder creation. Move the original close-framed image from Water Feature White In Situ into the existing Water Feature White folder.</p>', card(candidate, 'Chiswick Moon'), '<p>Destination: <a href="'+e(destination['folder_url'])+'">Chiswick Moon Water Feature White</a></p><p>Expected counts: In Situ 15 → 14; product folder 1 → 2; family total stays 20. The original filename and bytes stay unchanged. Selected primary and context photographs stay unchanged.</p>']
(P/'proposed-chiswick-close-framing-move.html').write_text(''.join(single))

old_path = ROOT/'reports/dropbox-moonwave-ten-approved-moves-20261024T182423Z/combined-thirty-family-current-image-folder-links.json'
old = read(old_path)
merged = {r['file_id']:r for r in old}
overlaps = []
for r in rows:
    if r['id'] in merged:
        overlaps.append({'file_id':r['id'], 'prior_role':merged[r['id']]['role'], 'family':r['family']})
    merged[r['id']] = {'role':'source', 'family':r['family'], 'file_id':r['id'], **{k:r[k] for k in ('name','size','folder_id','folder_path','folder_url','image_url','sha256','dropbox_content_hash')}}
cumulative = sorted(merged.values(), key=lambda x:(x['family'],x['folder_path'],x['name']))
write('combined-thirty-three-family-current-image-folder-links.json', cumulative)
accounting = {'prior_manifest':str(old_path),'prior_manifest_sha256':sha(old_path),
    'new_whole_families':3,'new_originals':353,'prior_overlap':overlaps,
    'whole_source_families':len({r['family'] for r in cumulative if r['role']=='source'}),
    'whole_source_originals':sum(r['role']=='source' for r in cumulative),
    'comparison_only_originals':sum(r['role']!='source' for r in cumulative),
    'distinct_original_references':len(cumulative),
    'freshness_note':'Only Chiswick Moon, Echo Sound and Bone Spiral were freshly relisted in this review. Earlier family paths retain their dated receipts and approved move overlays; this is not a fresh whole-library inventory.',
    'not_a_physical_stock_or_unique_design_count':True}
write('cumulative-link-accounting.json', accounting)

summary = {'recorded_utc':datetime.now(timezone.utc).isoformat(), 'status':'READ_ONLY_COMPLETE_EXACT_CHISWICK_PROPOSAL_PENDING_OWNER',
    'scope':SCOPE,'native_writes':0,'canonical_writes':0,
    'originals':len(rows),'original_bytes':sum(r['size'] for r in rows),
    'fresh_http_original_downloads':sum(not r['reused_native_identical_local_bytes'] for r in rows),
    'actual_existing_originals_rehashed_against_fresh_native_content_hash':sum(r['reused_native_identical_local_bytes'] for r in rows),
    'native_objects_unchanged':len(all_native),'complete_contact_boards_viewed':18,
    'full_option_records_unchanged':8,
    'families':{f:{'files':len(rr),'bytes':sum(r['size'] for r in rr.values()),'folders':len({r['folder_id'] for r in rr.values()})} for f,rr in by_family.items()},
    'proposal_file':'proposed-chiswick-close-framing-move.json','proposal_sha256':sha(P/'proposed-chiswick-close-framing-move.json'),
    'other_findings_are_observations_not_approved_moves':True,'all_existing_owner_holds_preserved':True,
    'moonwave_native_execution_completed_prior_turn':True,'moonwave_combined_canonical_import_owned_by_main_and_B':True,
    'cumulative_accounting':accounting}
write('validation.json', summary)
print(json.dumps(summary, indent=2))

# Seal review receipts and previews, retaining large originals through their individual hashes above.
excluded = {'review-seal.json','coordination-followup.json'}
paths = [q for q in P.rglob('*') if q.is_file() and q.name not in excluded and 'originals' not in q.relative_to(P).parts]
seal = {'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'SEALED_READ_ONLY_REVIEW',
    'receipt_count':len(paths),'files':[{'path':str(q.relative_to(P)),'size':q.stat().st_size,'sha256':sha(q)} for q in sorted(paths)],
    'large_originals_bound_by':'*-verified-originals-and-links.json',
    'excluded_mutable_followup':['coordination-followup.json'], 'native_writes':0}
write('review-seal.json', seal)
print('SEAL_SHA256', sha(P/'review-seal.json'))
print('PROPOSAL_SHA256', sha(P/'proposed-chiswick-close-framing-move.json'))
