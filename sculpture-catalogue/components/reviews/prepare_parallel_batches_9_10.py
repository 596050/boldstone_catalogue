"""Freeze two sealed peer packets and independently check their owner messages."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PEERS = ROOT / 'components/parallel-reviews'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: str(p.relative_to(ROOT))
CONFIGS = [
    (9, 'crater-fishwave-ring-2026-10-19', '9b1b905e64256679e0240bcf6795c85702faf43d815722e1023b72cb542b710d'),
    (10, 'moonshell-lava-corner-wall-2026-10-19', '05eb67a125d1d3605d0f8c9772760a18b466f8917182e08243279cb4840c8762'),
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def prepare(number, lane, expected):
    here = ROOT / f'components/reviews/parallel-import-2026-10-19-batch{number}'
    if (here / 'source-manifest.json').exists():
        assert read(here / 'source-manifest.json')['source_package_sha256'] == expected
        print(json.dumps({'batch':number,'status':'SOURCE_ALREADY_FROZEN_NO_WRITE'}))
        return
    source = PEERS / lane / 'IMPORT_PACKAGE.json'
    assert sha(source) == expected
    package = read(source)
    here.mkdir(exist_ok=True)
    received = here / 'received-package.source.json'
    if received.exists():
        assert sha(received) == expected
    else:
        received.write_bytes(source.read_bytes())
    assert package['shared_master_writes_by_this_session'] is False and package['remote_mutations'] == 0
    assert len(package['items']) == (5 if number == 9 else 3)
    assert package['fully_confirmed_specification_item_count'] == 0
    files = {}

    def freeze(path, digest=None, size=None):
        path = Path(path).resolve()
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        assert digest is None or actual == digest, str(path)
        assert size is None or len(raw) == size, str(path)
        if str(path) not in files:
            dest = (here / 'sources' / path.relative_to(PEERS)) if path.is_relative_to(PEERS) else (here / 'sources/external-media' / (actual + path.suffix))
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                assert dest.read_bytes() == raw
            else:
                dest.write_bytes(raw)
            files[str(path)] = {'source':str(path),'snapshot':rel(dest),'sha256':actual,'bytes':len(raw)}
        return files[str(path)]['snapshot']

    freeze(source, expected)
    for item in package['items']:
        for artifact in item['artifacts']:
            freeze(artifact['path'],artifact['sha256'],artifact.get('bytes'))
    for artifact in package['root_artifacts']:
        freeze(artifact['path'],artifact['sha256'],artifact.get('bytes'))
    for path,digest in package['referenced_image_hashes'].items():
        freeze(path,digest)
    for key in ['coordinator_acknowledgement','source_snapshot_path','batch_validation_path']:
        hashkey = key + '_sha256' if key == 'coordinator_acknowledgement' else key.removesuffix('_path') + '_sha256'
        freeze(package[key],package[hashkey])
    statements = []
    for item in package['items']:
        a = read(Path(item['approval_path']))
        statements.append(a['source_user_statement'])
    for item in package.get('arrangements',[]):
        statements.append(read(Path(item['path']))['source_user_statement'])
    requests = {}
    for e in statements:
        path = e['transcript_path']
        requests[(path,e['line'])] = ('user',e)
        preceding = e['preceding_review_card']
        requests[(path,preceding['line'])] = ('assistant',preceding)
    messages = {}
    for transcript in {x[0] for x in requests}:
        targets = {line for path,line in requests if path == transcript}
        with Path(transcript).open('rb') as f:
            first = json.loads(next(f))
            assert first['type'] == 'session_meta' and first['payload']['id'] == package['owner_session']
            for line,raw in enumerate(f,start=2):
                if line > max(targets):
                    break
                if line not in targets:
                    continue
                obj = json.loads(raw)
                payload = obj['payload']
                role,e = requests[(transcript,line)]
                assert obj['type'] == 'response_item' and payload['type'] == 'message' and payload['role'] == role
                text = '\n'.join(x.get('text','') for x in payload['content'] if x.get('type') in ['input_text','output_text','text'])
                declared_text = e['text']
                omitted_footer = text != declared_text
                if omitted_footer:
                    assert role == 'assistant' and text.startswith(declared_text + '\n\n<oai-mem-citation>')
                    assert text.endswith('</oai-mem-citation>') and text.split('\n\n<oai-mem-citation>')[0] == declared_text
                assert hashlib.sha256(declared_text.encode()).hexdigest() == e['text_sha256']
                assert obj['timestamp'] == e['timestamp']
                messages[(transcript,line)] = {'transcript_path':transcript,'line':line,'role':role,'timestamp':obj['timestamp'],
                    'message_id':payload.get('id'),'text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),
                    'source_substantive_text_sha256':e['text_sha256'],'source_only_omitted_memory_citation_footer':omitted_footer,
                    'raw_line_sha256':hashlib.sha256(raw).hexdigest()}
    assert len(messages) == (10 if number == 9 else 8)
    decisions = []
    for item in package['items']:
        a,w = read(Path(item['approval_path'])),read(Path(item['working_entry_path']))
        before_path = Path(item['approval_path']).parent / 'component-review.before-keep.json'
        old = read(before_path)
        assert sha(before_path) == a['source_review_sha256']
        assert sha(Path(item['approval_path'])) == item['approval_sha256'] and sha(Path(item['working_entry_path'])) == item['working_entry_sha256']
        assert a['name_and_visual_identity_kept'] and not a['physical_specs_verified'] and not a['fully_confirmed_specification_groups']
        assert a['decision_id'] == item['decision_id'] and w['working_name'] == old['working_name'] == a['working_name'] == item['working_name']
        assert len(old['specification_review_items']) == len(w['specification_review_items']) == 6
        assert old['primary_image']['file_id'] == w['primary_image']['file_id']
        assert old['containing_folder']['folder_id'] == w['containing_folder']['folder_id']
        evidence = a['source_user_statement']
        owner = messages[(evidence['transcript_path'],evidence['line'])]
        prior = evidence['preceding_review_card']
        card = messages[(evidence['transcript_path'],prior['line'])]
        assert prior['line'] < evidence['line'] and item['working_name'] in card['text']
        assert owner['text'].startswith('Keep “' + item['working_name'] + '”')
        primary,folder = w['primary_image'],w['containing_folder']
        image_url = next(primary[k] for k in ['open_in_dropbox_url','url','shared_link'] if isinstance(primary.get(k),str) and primary[k] in card['text'])
        folder_url = next(folder[k] for k in ['open_in_dropbox_url','url','shared_link'] if isinstance(folder.get(k),str) and folder[k] in card['text'])
        raw = Path(primary['local_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == primary['sha256'] and len(raw) == primary['size']
        assert hashlib.sha256(b''.join(hashlib.sha256(raw[i:i+4194304]).digest() for i in range(0,len(raw),4194304))).hexdigest() == primary['content_hash']
        media_snapshot = freeze(primary['local_path'],primary['sha256'],primary['size'])
        decisions.append({'component_id':item['component_id'],'variant_id':item['configuration_key'],
            'scope_kind':'build_variant_identity' if item['configuration_key']=='MOON-CRATER-WHITE-BASIN' else 'size_finish_variant',
            'name':item['working_name'],'source_decision_id':item['decision_id'],'receipt_snapshot':freeze(item['approval_path']),
            'receipt_sha256':item['approval_sha256'],'pre_answer_review':freeze(before_path),'pre_answer_review_sha256':sha(before_path),
            'working_entry':freeze(item['working_entry_path']),'working_entry_sha256':item['working_entry_sha256'],
            'primary_expected':primary,'folder_expected':folder,'image_url':image_url,'folder_url':folder_url,
            'media_snapshot':media_snapshot,'review_number':w['review_number'],'owner_session':package['owner_session'],
            'authoritative_owner_evidence':owner,'preceding_review_card_evidence':card,'owner_confirmed_fields':item['owner_confirmed_fields']})
    arrangements = []
    for entry in package.get('arrangements',[]):
        a = read(Path(entry['path']))
        assert not a['specifications_explicitly_confirmed'] and not a['same_measured_size_confirmed'] and not a['same_actual_cast_or_mould_confirmed']
        e = a['source_user_statement']
        assert messages[(e['transcript_path'],e['line'])]['text'] == 'This is a combined Moonshell Lava 1 White and Moonshell Lava 2 White'
        assert sha(Path(a['source_review_path'])) == a['source_review_sha256']
        image = a['depicted_primary_image']
        freeze(image['local_path'],image['sha256'],image['size'])
        arrangements.append({'snapshot':freeze(entry['path'],entry['sha256']),'owner':messages[(e['transcript_path'],e['line'])],
            'preceding_card':messages[(e['transcript_path'],e['preceding_review_card']['line'])],
            'primary_expected':image,'folder_expected':a['containing_folder']})
    manifest = {'schema_version':1,'created_utc':datetime.now(timezone.utc).isoformat(),'batch':number,'source_package':rel(source),
        'source_package_sha256':expected,'files':list(files.values()),'decisions':decisions,'verified_messages':list(messages.values()),
        'arrangements':arrangements,'position_resolution_snapshots':[freeze(x['path'],x['sha256']) for x in package.get('identity_resolutions',[])],
        'source_package_snapshot':rel(received),'import_constraints':package['import_constraints'],'outstanding_followups':package['outstanding_followups'],
        'new_complete_specification_approvals':0,'current_reference_targets':sorted({d['primary_expected']['file_id'] for d in decisions}|{d['folder_expected']['folder_id'] for d in decisions}|{a['primary_expected']['file_id'] for a in arrangements}|{a['folder_expected']['folder_id'] for a in arrangements})}
    write(here / 'source-manifest.json',manifest)
    print(json.dumps({'batch':number,'status':'PASS_FROZEN_SOURCE_AND_EXACT_MESSAGES','frozen_files':len(files),'messages_verified':len(messages),'canonical_name_receipts':len(decisions),'arrangements':len(arrangements),'current_reference_targets':manifest['current_reference_targets']}))


if __name__=='__main__':
    for config in CONFIGS:
        prepare(*config)
