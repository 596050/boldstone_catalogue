"""Recover the answered number 2 question without altering historical inputs."""
import copy
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
B = H.parents[2]
OUT = B / 'outputs' / H.name
THREAD = '01a16dbc-036d-7003-8ebd-34cb76b5b667'
SOURCE_THREAD = '01a13fbf-1cbc-7511-8416-cf339051083e'
PAIR = ['BSI-FE830AE502C3', 'BSI-837E9B0B3B36']
COMPONENTS = ['BC-DECO-2', 'BC-FDW-2']
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()

def write(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

if (H / 'import-summary.json').exists():
    assert not (H / 'WORK_STATE.json').exists(), 'Preparation already finalized'
    manifest = read(H / 'input-manifest.json')
    for frozen in manifest.values():
        assert sha(frozen['path']) == sha(frozen['snapshot']) == frozen['sha256']
    before = read(manifest['master_register']['snapshot'])
    g = read(H / 'canonical-master-register.json')
    summary = read(H / 'import-summary.json')
    question_path = Path(manifest['prepared_question']['path'])
    oldout = Path(read(manifest['source_report_verification']['snapshot'])['output_directory'])
    OLD = Path(manifest['master_register']['path']).parent
else:
    p = read(B / 'current-master.json')
    assert p['register_sha256'] == '164211ed960d363e3e249142096997821ff80c63404a5ee8db6254959f9a42e5'
    assert sha(B / p['register']) == p['register_sha256']
    assert sha(B / p['workbook']) == p['workbook_sha256']
    OLD = (B / p['register']).parent
    question_path = B / 'components/parallel-reviews/decowaves2-finish-design-question-20261024T040607Z/prepared-question.json'
    question = read(question_path)
    assert [r['product_id'] for r in question['records']] == PAIR
    transcript = Path('/Users/tprice/.codex/sessions/2026/10/15/rollout-2026-10-15T14-27-31-01a13fbf-1cbc-7511-8416-cf339051083e.jsonl')
    records = []
    with transcript.open('rb') as f:
        metadata = json.loads(f.readline())
        assert metadata['type'] == 'session_meta' and metadata['payload']['id'] == SOURCE_THREAD
        assert metadata['payload']['cwd'] == '/Users/tprice/Documents/boldstone/application'
        start = max(0, transcript.stat().st_size - 1500000)
        f.seek(start)
        if start:
            f.readline()
        while True:
            offset = f.tell()
            raw = f.readline()
            if not raw:
                break
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            pl = obj.get('payload', {})
            if obj.get('type') != 'response_item' or pl.get('type') != 'message':
                continue
            text = ''.join(x.get('text', '') for x in pl.get('content', []) if isinstance(x, dict))
            kind = None
            if pl.get('role') == 'assistant' and 'Are these also the same sculpture design in different finishes?' in text:
                assert all(r['image_url'] in text and r['folder_url'] in text for r in question['records'])
                kind = 'presented_number2_question'
                records = []
            elif records and pl.get('role') == 'user':
                assert text.strip() == 'wYes', 'Unexpected answer; do not infer approval'
                kind = 'owner_affirmative'
            elif records and text.strip() and pl.get('role') == 'assistant' and pl.get('phase') == 'final_answer':
                raise AssertionError('Intervening final question after the recovered comparison')
            if kind:
                records.append({'kind': kind, 'timestamp': obj['timestamp'], 'byte_offset': offset,
                                'byte_length': len(raw), 'raw_line_sha256': hashlib.sha256(raw).hexdigest(),
                                'text_verbatim': text, 'source_record': obj})
    assert len(records) == 3 and records[0]['kind'] == 'presented_number2_question'
    assert all(r['text_verbatim'] == 'wYes' for r in records[1:])
    assert records[0]['timestamp'] < records[1]['timestamp'] < records[2]['timestamp']
    write(H / 'transcript-evidence.json', {'source_path': str(transcript), 'source_thread_id': SOURCE_THREAD,
          'source_cwd': metadata['payload']['cwd'], 'records': records,
          'interpretation': 'Both repeated wYes messages are treated as Yes to the immediately preceding exact number 2 comparison. The original spelling is retained. The duplicate adds no second edge.'})
    OUT.mkdir(parents=True, exist_ok=False)
    (H / 'inputs').mkdir()
    files = {'pointer': B / 'current-master.json', 'master_workbook': B / p['workbook'],
             'master_register': B / p['register'], 'review_progress': B / 'components/reviews/specification_review_progress.json',
             'component_checkpoint': B / 'components/checkpoint.json', 'root_checkpoint': B / 'checkpoint.json',
             'source_report_verification': OLD / 'report-verification.json', 'prepared_question': question_path}
    copies = {'audit': 'image-coverage-current.json', 'native_map': 'current-native-reference-map.json',
              'report_assets': 'current-assets.json', 'report_reviews': 'photo-review-queue.json',
              'photo_source': 'photo-source-review.json', 'review_state': 'guided-owner-review-state.json',
              'pending': 'pending-followups.json', 'physical_audit': 'physical-source-audit.json',
              'originals': 'original-verification.json'}
    files.update({k: OLD / name for k, name in copies.items()})
    oldout = Path(read(files['source_report_verification'])['output_directory'])
    files.update(source_count_summary=oldout / 'current-count-summary.json',
                 source_photo_requests=oldout / 'remaining-photograph-requests.json')
    manifest = {}
    for key, source in files.items():
        snap = H / 'inputs' / (key + '.before')
        shutil.copy2(source, snap)
        manifest[key] = {'path': str(source), 'snapshot': str(snap), 'sha256': sha(source)}
    write(H / 'input-manifest.json', manifest)
    g = read(manifest['master_register']['snapshot'])
    before = copy.deepcopy(g)
    pair = [next(o for o in g['options'] if o['product_id'] == oid) for oid in PAIR]
    for o, ref in zip(pair, question['records']):
        assert all(o[k] == v for k, v in ref.items())
    edge = {'edge_id': 'OWNER-20261024:DECOWAVES2-WHITE-VERDIGRIS-SAME-DESIGN',
            'relationship': 'OWNER_CONFIRMED_SAME_DESIGN_DIFFERENT_FINISHES',
            'component_ids': COMPONENTS, 'retained_component_ids': COMPONENTS,
            'owner_confirmed_option_ids': PAIR, 'owner_answer_timestamp': records[1]['timestamp'],
            'owner_answer_verbatim': 'wYes', 'normalized_answer': 'Yes',
            'duplicate_answer_timestamp': records[2]['timestamp'],
            'source': 'Two repeated owner wYes answers to the exact presented number 2 comparison',
            'no_physical_mould_cast_or_specification_transfer': True,
            'source_evidence': {'path': str(H / 'transcript-evidence.json'), 'sha256': sha(H / 'transcript-evidence.json')},
            'exact_pair_references': [{k: o[k] for k in ['product_id', 'name', 'canonical_design_id', 'canonical_component_id', 'file_id', 'folder_id', 'image_url', 'folder_url']} for o in pair],
            'number2_confirmed': True, 'terracotta_owner_photo_approval': False}
    assert len(g['current_owner_design_equivalence_edges']) == 1
    assert edge['edge_id'] not in {x['edge_id'] for x in g['current_owner_design_equivalence_edges']}
    g['current_owner_design_equivalence_edges'].append(edge)
    mapping = copy.deepcopy(g['current_working_design_group_projection']['component_id_to_working_group'])
    assert mapping['BC-FDW-1'] == 'BC-DECO-1' and mapping['BC-FDW-2'] == 'BC-FDW-2'
    mapping['BC-FDW-2'] = 'BC-DECO-2'
    groups = []
    for group_id in dict.fromkeys(mapping.values()):
        members = [cid for cid, gid in mapping.items() if gid == group_id]
        prior = next(x for x in before['current_working_design_group_projection']['groups'] if x['working_design_group_id'] == group_id)
        group = copy.deepcopy(prior)
        if group_id == 'BC-DECO-2':
            group.update(retained_component_ids=members,
                         active_option_ids=[o['product_id'] for o in g['options'] if o.get('canonical_component_id') in members and o['product_id'] in g['active_option_ids']],
                         owner_directly_confirmed_option_ids=PAIR,
                         grouping_basis='Owner-confirmed number 2 Verdigris/White pair. Existing Terracotta membership retained without new photograph approval.')
        groups.append(group)
    assert len(groups) == 110 and sum(len(x['retained_component_ids']) for x in groups) == 112
    projection = copy.deepcopy(before['current_working_design_group_projection'])
    projection.pop('one_equivalence_group', None)
    projection.update(grouped_working_design_identity_count=110, direct_owner_relationships=2,
                      equivalence_groups=[['BC-DECO-1', 'BC-FDW-1'], COMPONENTS],
                      all_other_components_remain_singletons=True, groups=groups, component_id_to_working_group=mapping)
    g['current_working_design_group_projection'] = projection
    for o in pair:
        assert 'current_owner_design_equivalence' not in o
        o['current_owner_design_equivalence'] = {'edge_id': edge['edge_id'], 'working_design_group_id': 'BC-DECO-2',
             'same_design_as_option_id': next(x for x in PAIR if x != o['product_id']), 'source_evidence': edge['source_evidence'],
             'scope': 'Same relief design in different finishes; this option retains its own fields, sources, IDs and individual sale scope.'}
    for component in g['components']:
        if component['component_id'] in COMPONENTS:
            component['scope_note'] = 'Retained component ID in working design group BC-DECO-2. Owner confirmed Decowaves 2 Verdigris and Frozen Decowaves 2 White share the relief design. Finish options and specifications remain separate. Existing Terracotta membership is not a new photograph approval.'
            component['current_owner_design_group'] = {'working_design_group_id': 'BC-DECO-2', 'edge_id': edge['edge_id'],
                 'retained_component_id': component['component_id'], 'source_evidence': edge['source_evidence']}
    g['summary'].update(grouped_working_design_identity_count=110, owner_confirmed_design_equivalence_relationships=2)
    g['count_definition'] = before['count_definition'].split(' The112 retained')[0] + ' The112 retained identified component IDs project to110 working design groups after the separately owner-confirmed Decowaves1 and Decowaves2 White/Verdigris relationships. This is not a certified whole-library unique total.'
    summary = {'status': 'OWNER_DECOWAVES2_PAIR_DESIGN_EQUIVALENCE_IMPORTED', 'recorded_utc': now(),
               'recovering_thread': THREAD, 'source_thread': SOURCE_THREAD, 'owner_answer_timestamp': records[1]['timestamp'],
               'owner_answer_verbatim': 'wYes', 'normalized_answer': 'Yes', 'duplicate_answer_timestamp': records[2]['timestamp'],
               'owner_confirmed_pair_option_ids': PAIR, 'active_options': 188, 'retained_options': 189,
               'retained_component_id_records': 112, 'grouped_working_design_identities': 110,
               'new_design_equivalence_edges': 1, 'total_owner_design_equivalence_edges': 2,
               'component_ids_removed': 0, 'new_photo_bindings': 0, 'new_physical_verifications': 0,
               'terracotta_new_owner_photo_approval': False, 'native_or_platform_writes': 0}
    g['latest_decowaves2_owner_design_equivalence_import'] = summary
    write(H / 'canonical-master-register.json', g)
    write(H / 'import-summary.json', summary)
    write(H / 'owner-design-edge.json', edge)
    write(H / 'working-design-group-projection.json', projection)
    for name in [*copies.values(), 'guided_review.py', 'working-entry-owner-provenance-sidecar.json', 'current-primary-navigation-health.json', 'physical-checklist-label-alignment.json']:
        shutil.copy2(OLD / name, H / name)
changes = []
def diff(x, y, path):
    if path == ['current_working_design_group_projection'] and x != y:
        changes.append({'group': 'register', 'path': path, 'before_exists': True, 'before': x, 'current': y})
        return
    if isinstance(x, dict) and isinstance(y, dict):
        for key in sorted(x.keys() | y.keys()):
            if key not in x:
                changes.append({'group': 'register', 'path': path + [key], 'before_exists': False, 'current': y[key]})
            elif key not in y:
                raise AssertionError('Unexpected deletion at ' + str(path + [key]))
            else:
                diff(x[key], y[key], path + [key])
    elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
        for index, (a, b) in enumerate(zip(x, y)):
            diff(a, b, path + [index])
    elif x != y:
        changes.append({'group': 'register', 'path': path, 'before_exists': True, 'before': x, 'current': y})
diff(before, g, [])
write(H / 'authorized-current-field-changes.json', changes)
write(H / 'projection-index.json', {'old_output': str(oldout), 'new_output': str(OUT), 'pair_option_ids': PAIR, 'pair_component_ids': COMPONENTS})
evidence = {str(path): {'sha256': sha(path)} for path in [H / 'transcript-evidence.json', question_path, H / 'live-pair-metadata.json']}
write(H / 'evidence-manifest.json', evidence)
write(H / 'source-evidence-verification.json', {'status': 'PASS', 'exact_transcript_records_read_back': 3,
      'duplicate_answer_deduplicated': True, 'answer_spelling_preserved': True, 'owner_design_scope_only': PAIR,
      'new_native_reads': 4, 'native_read_scope': 'Two stable file IDs and their containing folders; no binary reads or live sandbox testing',
      'new_physical_verifications': 0})
write(H / 'WORK_STATE.json', {'status': 'PREPARED_NOT_PUBLISHED', 'scope': summary})
(H / 'node_modules').symlink_to('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules', target_is_directory=True)
print(json.dumps({**summary, 'declared_metadata_changes': len(changes)}))
