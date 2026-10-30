"""Import scoped follow-ups against exact source images; never promote estimates."""
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REV = ROOT / 'components/reviews'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
rel = lambda p: str(Path(p).relative_to(ROOT))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def canonical_messages(evidence, session):
    targets = {x['line']: x for x in evidence}
    found, preceding = [], None
    with Path(evidence[0]['transcript']).open('rb') as stream:
        for number, raw in enumerate(stream, 1):
            if number > max(targets): break
            item = json.loads(raw); payload = item.get('payload', {})
            if number == 1: assert payload['id'] == session
            if item.get('type') != 'response_item' or payload.get('type') != 'message': continue
            text = '\n'.join(c.get('text', '') for c in payload.get('content', []) if c.get('type') in ['input_text', 'output_text', 'text'])
            actual = {'transcript': evidence[0]['transcript'], 'line': number, 'timestamp': item['timestamp'],
                      'role': payload['role'], 'text': text, 'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                      'raw_line_sha256': hashlib.sha256(raw).hexdigest(),
                      'source_raw_line_digest_includes_line_ending': True}
            if number in targets:
                expected = targets[number]
                assert all(actual[k] == expected[k] for k in ['line', 'timestamp', 'role', 'text'])
                assert actual['text_sha256'] == expected.get('text_sha256', expected.get('text_sha256_utf8'))
                if expected.get('raw_line_sha256'):
                    without_ending = hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest()
                    assert expected['raw_line_sha256'] in [actual['raw_line_sha256'], without_ending]
                    actual['provided_raw_line_digest_includes_line_ending'] = expected['raw_line_sha256'] == actual['raw_line_sha256']
                if payload['role'] == 'user': actual['immediately_preceding_assistant'] = preceding
                found.append(actual)
            if payload['role'] == 'assistant' and payload.get('phase') == 'final_answer' and text.strip(): preceding = actual
    assert len(found) == len(targets)
    return found


def apply_followup(batch):
    here = REV / f'parallel-import-2026-10-19-batch{batch}'
    is_soundwave = batch == 24
    four_panel = batch == 29
    three_panel = batch == 33
    four_panel_row = batch == 39
    asymmetric = batch == 44
    looped = batch == 47
    folder = ROOT / ('components/parallel-reviews/soundwave-2026-10-19/owner-name-keep' if is_soundwave else
                     'components/parallel-reviews/fingerprint-unresolved-groups-2026-10-19/' + ('looped-ridge-verdigris-name-import-20261019' if looped else 'asymmetric-spiral-verdigris-name-import-20261019' if asymmetric else 'four-panel-row-verdigris-name-import-20261019' if four_panel_row else 'three-panel-verdigris-name-import-20261019' if three_panel else 'four-panel-verdigris-name-import-20261019' if four_panel else 'double-curl-verdigris-name-import-20261019'))
    package_path = folder / 'IMPORT_PACKAGE.json'
    digest = 'be6ce431e1c2bbda58f9eb04fa923ad3ab0dc5338c31b7877fc6d9995abd06b0' if is_soundwave else '6bcd62c706bd7b45f893761f9ab2922194ef54ce78c98fc9620b34c68ca20e15'
    key = 'SOUNDWAVE-WHITE-G310003' if is_soundwave else 'FINGERPRINT-DOUBLE-CURL-VERDIGRIS-G158013'
    if four_panel:
        digest = '587f7c0b5720afe34bccf14371fde2d0b71772099bca42f6007523deab047bf3'
        key = 'FINGERPRINT-FOUR-PANEL-VERDIGRIS-G158026'
    if three_panel:
        digest = '242504ae0d5e7090846dbd8760d4a03ea240ad33a7875121a23f87f23cdc5677'
        key = 'FINGERPRINT-THREE-PANEL-VERDIGRIS-G160006'
    if four_panel_row:
        digest = '46fa90eb43fa599d475e625d5e04acc0c9430ad042a669a978c6ec3b9bb78ec1'
        key = 'FINGERPRINT-FOUR-PANEL-ROW-VERDIGRIS-G160005'
    if asymmetric:
        digest = '69f557f75283c1192ec4b9bff201279a5e49adc951072a9fb20238b56f1891a9'
        key = 'FINGERPRINT-ASYMMETRIC-SPIRAL-VERDIGRIS-G160003'
    if looped:
        digest = '5ddb07c2786c8118d3edc7fae65bcf42fe5246a0bfd0724ec1f9289b2a48d21a'
        key = 'FINGERPRINT-LOOPED-RIDGE-VERDIGRIS-G158032'
    paths = {'user': REV / 'user_classifications.json', 'progress': REV / 'specification_review_progress.json',
             'walkthrough': REV / 'walkthrough_checkpoint.json', 'component': ROOT / 'components/checkpoint.json', 'root': ROOT / 'checkpoint.json'}
    docs = {k: read(v) for k, v in paths.items()}
    if (here / 'import-receipt.json').exists():
        receipt = read(here / 'import-receipt.json')
        assert sum(d['decision_id'] == receipt['decision_id'] for d in docs['user']['source_design_name_decisions']) == 1
        assert docs['progress']['source_design_reviews'][key]['identity_confirmed'] is True
        print(json.dumps({'batch': batch, 'status': 'ALREADY_IMPORTED_IDEMPOTENT_NO_WRITE'})); return
    assert sha(package_path) == digest
    package = read(package_path); files = []; frozen = {}

    def freeze(path, expected):
        path = Path(path)
        if str(path) in frozen: assert frozen[str(path)]['sha256'] == expected; return
        assert sha(path) == expected
        dest = here / 'sources' / (expected + path.suffix)
        dest.parent.mkdir(exist_ok=True)
        if dest.exists(): assert sha(dest) == expected
        else: dest.write_bytes(path.read_bytes())
        entry = {'source': str(path), 'snapshot': rel(dest), 'sha256': expected, 'bytes': dest.stat().st_size}
        files.append(entry); frozen[str(path)] = entry

    freeze(package_path, digest)
    if is_soundwave:
        freeze(package['manifest']['path'], package['manifest']['sha256'])
        for item in read(package['manifest']['path'])['files']: freeze(item['path'], item['sha256'])
        decision = read(package['decision']['path'])
        for name in ['face_dimension_decision', 'face_dimension_shared_import']:
            item = decision[name]; freeze(item['path'], item['sha256'])
        evidence = [read(package[field]['path']) for field in ['full_specification_card', 'prior_name_question', 'preceding_acknowledgement', 'owner_evidence']]
    else:
        seal = folder / 'SEALED_PACKAGE_MANIFEST.json'
        assert sha(seal) == ('3c344cb9f699781a1b719e28105c0af989a1b27099ddf95fc666613bca027894' if looped else 'cedc3062a9c7a422fc105ceb1abbce5829163b96a02b4cdd0ff96b7bd59e5135' if asymmetric else '367c75353d451ccaa62c941dcba2263453d3911ef759026e319bead27b2b1016' if four_panel_row else '0ae956a62b60e3c278dceac606ba5a1f259aee9a0ce32612b71f4f98917a7264' if three_panel else '2dc2ba89b96d5f9f4e693b68c3c693526486be1ccbc31733478631c2949a06fd' if four_panel else '5977e1293a0f1b95dbe93e16aab0d9a62baea3882632d900d59d050ef4326592')
        freeze(seal, sha(seal))
        for item in read(seal)['files']: freeze(item['path'], item['sha256'])
        manifest = read(package['frozen_sources']['path'])
        assert len(manifest['files']) == (39 if looped else 35 if asymmetric else 28 if four_panel_row else 27 if three_panel else 26)
        for item in manifest['files']: freeze(item['frozen_path'], item['sha256'])
        item = package['owner_name_approvals'][0]['decision']; freeze(item['path'], item['sha256'])
        decision = read(item['path'])
        item = package['exact_owner_transcript']; freeze(item['path'], item['sha256'])
        evidence = read(item['path'])['messages']
        assert package['owner_production_confirmations'] == [] and package['manufacture_decision_must_not_be_replayed']
    verified = canonical_messages(evidence, package['source_owner_session'])
    name = 'Soundwave — White' if is_soundwave else 'Fingerprint — Double Curl Panels (Verdigris)'
    if four_panel: name = 'Fingerprint — Four Panel Arrangement (Verdigris)'
    if three_panel: name = 'Fingerprint — Three Panel Arrangement (Verdigris)'
    if four_panel_row: name = 'Fingerprint — Four Panel Row (Verdigris)'
    if asymmetric: name = 'Fingerprint — Asymmetric Spiral Panels (Verdigris)'
    if looped: name = 'Fingerprint — Looped Ridge Panels (Verdigris)'
    if is_soundwave:
        assert verified[-1]['line'] == 25411 and verified[-1]['text'] == 'Have you got the specifications? Keep “Soundwave — White”'
        assert verified[-1]['immediately_preceding_assistant']['line'] == 25404
        assert '__003.png' in next(x['text'] for x in verified if x['line'] == 25362)
        assert decision['name_approved'] is True
    else:
        assert verified[-1]['line'] == (17211 if looped else 17010 if asymmetric else 16883 if four_panel_row else 16750 if three_panel else 16605 if four_panel else 16455) and verified[-1]['text'] == 'Keep “' + name + '”'
        assert verified[-1]['immediately_preceding_assistant']['line'] == (17204 if looped else 17003 if asymmetric else 16843 if four_panel_row else 16732 if three_panel else 16587 if four_panel else 16425) and ('__032.png' if looped else '__003.png' if asymmetric else '__005.png' if four_panel_row else '__006.png' if three_panel else '__026.png' if four_panel else '__013.png') in verified[0]['text']
    assert decision['owner_estimates_accepted'] is False
    before, guards = copy.deepcopy(docs), {k: sha(v) for k, v in paths.items()}
    user, progress, cp, component = (docs[k] for k in ['user', 'progress', 'walkthrough', 'component'])
    assert docs['root']['current_component_review'] == component
    node = progress['source_design_reviews'][key]
    assert not node['identity_confirmed']
    if is_soundwave: assert node['owner_stated_face_dimensions_cm_in_stated_order'] == [80, 60]
    else:
        assert node['owner_stated_design_physically_made'] is True
        assert len([x for x in user['design_production_confirmation_decisions'] if x.get('source_design_key') == key]) == 1
    heads = read(here / 'current-reference-check.json')['metadata']
    head = next(x['file'] for x in heads if x.get('file')); parent = next(x['folder'] for x in heads if x.get('folder'))
    assert head['id'] == node['source_asset_id']
    assert parent['id'] == node['source_folder_id']
    if is_soundwave: assert head['id'] == decision['primary_file_id'] and parent['id'] == decision['folder_id']
    else: assert head['id'] == decision['reference_image']['id'] and parent['id'] == decision['reference_folder']['id']
    assert head['rev'] == node['source_file_revision'] and head['size'] == node['source_file_bytes']
    assert head['path_display'] == node['source_path_display'] and head['path_display'].rsplit('/', 1)[0] == parent['path_display']
    protected = {str(p): sha(p) for p in [ROOT / 'components/evidence/component_register.json', ROOT / cp['register_workbook'],
        ROOT / cp['current_review_record'], ROOT.parent / 'Boldstone_Wall_Sculptures_Matched_All_Fields_2026-10-15.xlsx']}
    now = datetime.now(timezone.utc).isoformat()
    decision.update({'source_design_key': key, 'authoritative_user_evidence': verified[-1],
                     'verified_original_question': next(x for x in verified if x['line'] == 25362) if is_soundwave else verified[0],
                     'approval_record': rel(here / 'source-name-decision.json'), 'imported_utc': now})
    user.setdefault('source_design_name_decisions', []).append(decision)
    node.update({'record_kind': 'INDIVIDUAL_WHOLE_SOURCE_OWNER_NAMED' if is_soundwave else 'OWNER_NAMED_GROUP_SOURCE;MEMBER_IDENTIFICATION_DEFERRED_BY_OWNER', 'canonical_source_name': name,
                 'canonical_name': name, 'identity_confirmed': True,
                 'owner_name_approval': decision['approval_record'], 'active_owner_question': None,
                 'source_name_question_answered': True, 'latest_followup_import': rel(here / 'import-receipt.json')})
    if not is_soundwave: node['catalogue_name_explicitly_approved'] = True
    assert node['specifications'] == before['progress']['source_design_reviews'][key]['specifications']
    progress['asset_assignment_overrides'][head['id']]['assignment_status'] = 'OWNER_NAMED_WHOLE_SOURCE;OWNER_FACE_SIZE_ONLY;OTHER_SPECIFICATIONS_PENDING' if is_soundwave else 'OWNER_NAMED_GROUP_REFERENCE;SIX_SPECIFICATION_ESTIMATES_UNAPPROVED'
    progress['asset_assignment_overrides'][head['id']]['latest_name_review_record'] = decision['approval_record']
    summary = {'batch': batch, 'recorded_utc': now, 'receipt': rel(here / 'import-receipt.json'), 'source_design_key': key,
        'new_source_name_approvals': 1, 'new_registered_BC_component_ids': [], 'new_full_specification_approvals': 0,
        'owner_estimates_accepted': False, 'face_size_preserved_cm': [80, 60] if is_soundwave else None, 'workbook_export_pending': True,
        'root_new_private_original_downloads': 0, 'remote_mutations': 0}
    cp['parallel_import_queue'].append({'scope_kind': 'EXISTING_WHOLE_SOURCE_NAME_ONLY' if is_soundwave else 'EXISTING_GROUP_SOURCE_NAME_ONLY;NO_PRODUCTION_REPLAY', 'receipt': rel(package_path),
        'receipt_sha256': digest, 'approval_imported': True, 'import_receipt': summary['receipt'], 'status': 'APPLIED_EXACT_OWNER_SCOPE;ACTUAL_SPECIFICATIONS_INCOMPLETE'})
    component['parallel_import_queue'] = copy.deepcopy(cp['parallel_import_queue'])
    for target in [cp, component]: target['last_parallel_import'] = copy.deepcopy(summary); target['updated_utc'] = now
    for field in ['next_serialized_parallel_import', 'completed_serialized_parallel_import']:
        cp[field] = {'status': 'APPLIED_AND_VERIFIED', 'receipt': summary['receipt'], 'completed_utc': now}
    progress['latest_parallel_import'] = copy.deepcopy(summary)
    user['updated_utc'] = progress['updated_utc'] = now
    docs['root']['current_component_review'] = copy.deepcopy(component); docs['root']['updated_utc'] = now
    assert progress['reviews'] == before['progress']['reviews']
    assert all(cp[k] == v for k, v in before['walkthrough'].items() if k.startswith('current_'))
    assert cp['deferred_reviews'] == before['walkthrough']['deferred_reviews']
    assert all(sha(paths[k]) == v for k, v in guards.items()) and all(sha(k) == v for k, v in protected.items())
    write(here / 'before-import.json', before)
    write(here / 'source-name-decision.json', decision)
    write(here / 'source-design-review.json', node)
    write(here / 'source-manifest.json', {'source_package_sha256': digest, 'files': files, 'verified_messages': verified})
    for k, path in paths.items(): write(path, docs[k])
    write(here / 'import-receipt.json', {'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'source_design_key': key,
        'decision_id': decision['decision_id'], 'summary': summary, 'protected_sha256': protected,
        'shared_after_sha256': {k: sha(v) for k, v in paths.items()}})
    print(json.dumps({'batch': batch, 'status': 'APPLIED;INDEPENDENT_READBACK_REQUIRED', 'frozen_references': len(files)}))


if __name__ == '__main__':
    assert sys.argv[1:] in [['24'], ['26'], ['29'], ['33'], ['39'], ['44'], ['47']]
    apply_followup(int(sys.argv[1]))
