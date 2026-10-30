"""Attach derived cached-photo coverage without creating owner approvals or stock claims."""
import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'components/reviews/parallel-import-2026-10-19-batch41'
SOURCE = ROOT / 'components/parallel-reviews/brancusi-gold-finishes-2026-10-19/coverage-audit'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp'); temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); temp.replace(path)


def main():
    paths = {'user': ROOT / 'components/reviews/user_classifications.json', 'progress': ROOT / 'components/reviews/specification_review_progress.json',
        'walkthrough': ROOT / 'components/reviews/walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(path) for k, path in paths.items()}
    if (HERE / 'import-receipt.json').exists():
        assert all('BR-' + str(n) + '-GOLD-LEAF' in docs['progress']['current_component_photograph_gaps'] for n in [1, 2])
        print(json.dumps({'batch': 41, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    package_path = SOURCE / 'IMPORT_PACKAGE.json'; digest = 'dbf005633c9002a258bf677c9e22231a655dad8cb57037032b0d7aaa66c79dc7'
    assert sha(package_path) == digest
    package = read(package_path); frozen = []
    def freeze(path, expected):
        path = Path(path); assert sha(path) == expected
        dest = HERE / 'sources' / (expected + path.suffix); dest.parent.mkdir(exist_ok=True)
        if dest.exists(): assert sha(dest) == expected
        else: dest.write_bytes(path.read_bytes())
        frozen.append({'source': str(path), 'snapshot': rel(dest), 'sha256': expected, 'bytes': dest.stat().st_size})
        return rel(dest)
    freeze(package_path, digest); freeze(package['manifest']['path'], package['manifest']['sha256'])
    manifest = read(package['manifest']['path']); assert len(manifest['files']) == 18
    for item in manifest['files']: freeze(SOURCE / item['path'], item['sha256'])
    report, observations = read(package['report']['path']), read(package['file_observations']['path'])['files']
    assert report['file_count'] == len(observations) == 68 and report['folder_count'] == 6
    assert dict(Counter(x['role'] for x in observations)) == report['role_counts']
    live = read(HERE / 'current-reference-check.json'); freeze(HERE / 'current-reference-check.json', sha(HERE / 'current-reference-check.json'))
    groups = {x['group_ref']: x for x in live['groups']}
    assert set(groups) == {'G032', 'G033', 'G034', 'G035', 'G038', 'G039'}
    entries = {x['file_id']: (group, x) for group in groups.values() for x in group['listing']['entries']}
    assert len(entries) == 68 and len({x['file_id'] for x in observations}) == 68
    for group in groups.values(): assert not group['listing']['has_more'] and not group['listing']['cursor']
    assert len(groups['G039']['listing']['entries']) == 0 and len(groups['G035']['listing']['entries']) == 31
    for item in observations:
        group, entry = entries[item['file_id']]
        assert item['group_ref'] == group['group_ref'] and item['folder_id'] == group['folder']['id']
        assert item['name'] == entry['name'] and item['current_bytes'] == entry['file']['size'] and item['current_path_display'] == entry['path_display']
        assert entry['path_display'].rsplit('/', 1)[0] == group['folder']['path_display']
        assert sha(item['thumbnail_path']) == item['thumbnail_sha256'] and Path(item['thumbnail_path']).stat().st_size == item['thumbnail_bytes']
        assert item['original_content_hashed_now'] is False and not item.get('individual_component_decomposition_performed')
        assert not item.get('physical_manufacture_confirmed') and item.get('physical_stock_count') is None
        freeze(item['thumbnail_path'], item['thumbnail_sha256'])
    before = copy.deepcopy(docs); guards = {k: sha(path) for k, path in paths.items()}
    user, progress, cp, component, root = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component', 'root'])
    assert root['current_component_review'] == component and not cp['current_answer_recorded']
    protected = {str(path): sha(path) for path in [paths['user'], ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat(); coverage = {}; gaps = {}
    for n in [1, 2]:
        cid, vid = f'BC-BR-{n}', f'BR-{n}-GOLD-LEAF'; node = progress['reviews'][cid]['size_finish_variants'][vid]
        data = copy.deepcopy(report['per_component'][cid]); assert data['confirmed_name'] == node['canonical_name'] and data['kept_primary_file_id'] == node['primary_image_id']
        assert node['identity_confirmed'] and not node['proposals_approved'] and len(node['specification_proposals']) == 6
        text = ('Complete front/on-wall and unmeasured angled views available. G035 has31 room-detail presentations; the full folded silhouette is unconfirmed. '
                if n == 1 else 'Complete front/on-wall and unmeasured angled views available. G039 is empty; family room context exists. ')
        text += 'Gold pair/series pictures are family context only. No rear/fixing or calibrated profile found in the six audited Gold folders.'
        data.update({'component_id': cid, 'size_finish_variant_id': vid, 'reviewed_utc': now, 'source_scope': 'Six allocated Gold folders,68 cached thumbnails; not a whole-library absence claim.',
            'root_live_reference_check': rel(HERE / 'current-reference-check.json'), 'original_bytes_verified_now': False,
            'source_report_snapshot': next(x['snapshot'] for x in frozen if x['source'] == package['report']['path']),
            'source_folder_references': [{'group_ref': k, 'folder_id': g['folder']['id'], 'path_display': g['folder']['path_display'], 'files': len(g['listing']['entries'])} for k, g in groups.items()]})
        coverage[vid] = data
        node.update({'photo_coverage': data, 'photo_coverage_summary': text, 'photo_coverage_review': rel(HERE / 'component-coverage.json')})
        node['missing_photographs'] = list(dict.fromkeys(node.get('missing_photographs', []) + ['Full-component wide-room image; current detail/family context does not establish this coverage']))
        gaps[vid] = {'component_id': cid, 'size_finish_variant_id': vid, 'canonical_name': node['canonical_name'],
            'front': 'Complete front/on-wall depiction available; cached thumbnails reviewed.',
            'room': '31 room presentations show a rectangular detail; complete folded silhouette unconfirmed.' if n == 1 else 'Dedicated G039 In Situ folder is empty; family room context is available.',
            'series': 'Gold pair/group pictures exist in G032/G033; retained as family context without decomposition.',
            'evidence': '68 cached thumbnails across six complete current folder listings. Scene provenance unverified; not a whole-library absence claim.',
            'missing': 'Rear/fixing image, calibrated side/profile and a full-component wide-room image remain unestablished. Unmeasured angled views already exist.',
            'review_record': rel(HERE / 'component-coverage.json'), 'source_package_sha256': digest}
    progress.setdefault('component_photo_coverage_reviews', {}).update(coverage)
    progress.setdefault('current_component_photograph_gaps', {}).update(gaps)
    for item in observations:
        progress.setdefault('media_coverage_observations_by_file_id', {})[item['file_id']] = copy.deepcopy(item) | {'coverage_review': rel(HERE / 'file-observations.json'), 'derived_cached_thumbnail_observation': True}
    summary = {'batch': 41, 'recorded_utc': now, 'receipt': rel(HERE / 'import-receipt.json'), 'scope_kind': 'DERIVED_CACHED_PHOTO_COVERAGE',
        'new_owner_decisions': 0, 'new_finish_name_approvals': 0, 'new_full_specification_approvals': 0, 'new_registered_BC_component_ids': [],
        'reviewed_cached_images': 68, 'reviewed_current_folders': 6, 'new_scoped_photo_gap_rows': 2,
        'root_new_private_original_downloads': 0, 'remote_mutations': 0, 'workbook_export_pending': True}
    cp['parallel_import_queue'].append({'scope_kind': summary['scope_kind'], 'receipt': rel(package_path), 'receipt_sha256': digest,
        'approval_imported': False, 'evidence_imported': True, 'import_receipt': summary['receipt'], 'status': 'PHOTO_COVERAGE_EVIDENCE_APPLIED;NO_NEW_OWNER_OR_SPEC_APPROVAL'})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, component]: target['last_parallel_import'] = copy.deepcopy(summary)
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    component['next_work'][1] = 'Use the scoped Brancusi Gold photo gaps: both need rear/fixing and calibrated profile evidence; full-component wide-room coverage remains unestablished. Keep group pictures as family context.'
    for k, doc in docs.items():
        if k != 'user': doc['updated_utc'] = now
    root['current_component_review'] = copy.deepcopy(component)
    assert docs['user'] == before['user'] and progress['asset_assignment_overrides'] == before['progress']['asset_assignment_overrides']
    for n in [1, 2]:
        cid, vid = f'BC-BR-{n}', f'BR-{n}-GOLD-LEAF'
        assert progress['reviews'][cid]['size_finish_variants'][vid]['specification_proposals'] == before['progress']['reviews'][cid]['size_finish_variants'][vid]['specification_proposals']
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(Path(k)) == v for k, v in protected.items())
    write(HERE / 'before-import.json', before); write(HERE / 'component-coverage.json', coverage); write(HERE / 'file-observations.json', observations)
    write(HERE / 'source-manifest.json', {'files': frozen, 'source_package_sha256': digest, 'root_viewed_contact_sheets': read(SOURCE / 'CONTACT_SHEET_INDEX.json')})
    for k, path in paths.items():
        if k != 'user': write(path, docs[k])
    write(HERE / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'summary': summary, 'protected_sha256': protected, 'shared_after_sha256': {k: sha(path) for k, path in paths.items()}})
    print(json.dumps({'batch': 41, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'cached_images': 68, 'scoped_photo_gap_rows': 2, 'new_owner_or_specification_approvals': 0, 'frozen_references': len(frozen)}))


if __name__ == '__main__': main()
