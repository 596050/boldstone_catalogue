"""Freeze the four-design packet and verify exact owner/weight/arrangement evidence."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rel=lambda p:str(p.relative_to(ROOT))


def main():
    output=HERE/'source-manifest.json'
    assert not output.exists()
    source=ROOT/'components/parallel-reviews/moonphases-2026-10-19/four-design-keeps-import-20261019'
    package_path=source/'IMPORT_PACKAGE.json'
    seal_path=source/'SEALED_PACKAGE_MANIFEST.json'
    assert sha(package_path)==sha(HERE/'received-package.source.json')=='fdcae9405872cb924fe9a48323e581c6ad3ca8036f99e30150aa12f7d5a07b04'
    assert sha(seal_path)=='ab2303629987e8be93d3e27fc87ad8ebd76c1444915f654df2e7a3dd49bba4c5'
    package=read(package_path)
    assert package['current_design_count']==4 and package['source_keep_binding_count']==10
    assert package['unique_current_finish_variant_count_from_keeps']==8 and package['Silver']['do_not_import_as_new_owner_keep']
    files={}

    def freeze(path,digest,original=None):
        path=Path(path).resolve()
        assert sha(path)==digest,str(path)
        key=str(Path(original).resolve()) if original else str(path)
        if key not in files:
            dest=HERE/'sources'/(digest+path.suffix)
            dest.parent.mkdir(exist_ok=True)
            if dest.exists():
                assert sha(dest)==digest
            else:
                dest.write_bytes(path.read_bytes())
            files[key]={'source':key,'frozen_peer_source':str(path),'snapshot':rel(dest),'sha256':digest,'bytes':path.stat().st_size}
        return files[key]['snapshot']

    def snap(path):
        return files[str(Path(path).resolve())]['snapshot']

    freeze(package_path,sha(package_path))
    freeze(seal_path,sha(seal_path))
    for entry in read(seal_path)['files']:
        freeze(entry['path'],entry['sha256'])
    frozen=read(Path(package['frozen_sources']['path']))
    assert len(frozen['files'])==55
    for entry in frozen['files']:
        freeze(entry['frozen_path'],entry['sha256'],entry['source_path'])
    add_seal=ROOT/'components/parallel-reviews/moonphases-2026-10-19/water-feature-white-arrangement/name-import-addendum-20261019/SEALED_ADDENDUM_MANIFEST.json'
    assert sha(add_seal)=='f003fe3c716ceb449211262da1391b6fb63e1fa4b968ccbbeda6883c536355ab'
    add_manifest=read(add_seal)
    freeze(add_seal,sha(add_seal))
    for entry in add_manifest['files']:
        freeze(entry['path'],entry['sha256'])
    add=read(Path(add_manifest['package']['path']))
    for entry in add['sources']:
        freeze(entry['frozen'],entry['sha256'],entry['source'])
    assert add['all_six_fields_pending'] and add['30kg_reference_not_owner_estimate_acceptance']
    assert add['Silver_no_new_keep_created']
    evidence=read(Path(package['exact_owner_transcript_evidence']['path']))
    expected={x['line']:x for x in evidence['messages']}
    add_owner=add['owner_decision']['owner_evidence']
    expected[add_owner['line']]=add_owner
    verified={}
    with Path(evidence['transcript']).open('rb') as stream:
        first=json.loads(next(stream))
        assert first['payload']['id']==package['source_owner_session']
        for line,raw in enumerate(stream,start=2):
            if line>max(expected):
                break
            if line not in expected:
                continue
            e=expected[line]
            actual=json.loads(raw)
            payload=actual['payload']
            assert actual['type']=='response_item' and payload['type']=='message' and payload['role']==e['role']
            text='\n'.join(x.get('text','') for x in payload['content'] if x.get('type') in ['input_text','output_text','text'])
            assert text==e['text'] and actual['timestamp']==e['timestamp']
            digest=hashlib.sha256(text.encode()).hexdigest()
            assert digest==e.get('text_sha256',e.get('text_sha256_utf8'))
            if e.get('raw_line_sha256'):
                assert e['raw_line_sha256'] in [hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.rstrip(b'\r\n')).hexdigest()]
            verified[line]={'line':line,'role':e['role'],'timestamp':actual['timestamp'],'message_id':payload.get('id'),
                'text':text,'text_sha256':digest,'raw_line_sha256':hashlib.sha256(raw).hexdigest(),'transcript':evidence['transcript']}
    assert len(verified)==15 and sum(x['role']=='user' for x in verified.values())==14
    decisions=[]
    refs={}
    for binding in package['source_keep_bindings']:
        review=read(ROOT/snap(binding['original_review']['path']))
        owner=read(ROOT/snap(binding['original_owner_keep']['path']))
        assert sha(ROOT/snap(binding['original_review']['path']))==binding['original_review']['sha256']
        assert owner['review_json_sha256']==binding['original_review']['sha256']
        assert owner['approved_name']==binding['historical_name'] and owner['specification_fields_approved']==[]
        assert review['primary_image']['id']==binding['primary_asset_id'] and review['primary_image']['content_hash']==binding['primary_asset_content_hash']
        assert review['primary_image']['size']==binding['primary_asset_bytes']
        assert len(review['specifications'])==6
        card=next(x['snapshot'] for x in files.values() if x['sha256']==owner['review_card_sha256'] and Path(x['source']).suffix=='.md')
        assert sha(ROOT/card)==owner['review_card_sha256']
        if review.get('card_sha256'):
            assert review['card_sha256']==owner['review_card_sha256']
        for message in binding['source_owner_evidence']:
            assert verified[message['line']]['text']==message['text']
        primary,folder=review['primary_image'],review.get('primary_folder',review.get('folder'))
        assert folder is not None
        refs[primary['id']]={'kind':'file','expected':primary}
        refs[folder['id']]={'kind':'folder','expected':folder}
        decisions.append({'binding':binding,'review_snapshot':snap(binding['original_review']['path']),
            'owner_snapshot':snap(binding['original_owner_keep']['path']),'card_snapshot':card})
    weight=package['conditional_weight_acceptance']
    w=read(ROOT/snap(weight['exact_source_receipt']['path']))
    assert w['component_id']=='BC-MP-2' and w['accepted_nominal_estimated_kg']==6 and w['accepted_rough_working_range_kg']==[4,9]
    assert not w['physical_weight_measured'] and not w['physical_dimensions_confirmed'] and not w['actual_material_confirmed']
    assert w['other_specification_fields_approved']==[] and verified[w['owner_evidence']['line']]['text']=='okay'
    assert verified[w['preceding_assistant_final_line']]['role']=='assistant'
    assert '6' in verified[w['preceding_assistant_final_line']]['text']
    add_review_path=next(x['source'] for x in add['sources'] if x['source'].endswith('/REVIEW.json'))
    add_review=read(ROOT/snap(add_review_path))
    assert add_review['proposed_name']==add['approved_name']
    for kind,key in [('file','primary_image'),('folder','primary_folder')]:
        entry=add_review[key]
        refs[entry['id']]={'kind':kind,'expected':entry}
    result={'schema_version':1,'created_utc':datetime.now(timezone.utc).isoformat(),'source_package':rel(package_path),
        'source_package_sha256':sha(package_path),'package_snapshot':snap(package_path),'files':list(files.values()),
        'source_decisions':decisions,'verified_messages':list(verified.values()),'current_reference_targets':refs,
        'weight_receipt_snapshot':snap(weight['exact_source_receipt']['path']),
        'arrangement_addendum_snapshot':snap(add_manifest['package']['path']),'arrangement_review_snapshot':snap(add_review_path),
        'current_design_count':4,'source_keep_bindings':10,'current_finish_aliases':8,'Silver_explicit_keep':False,
        'physical_mould_cast_stock_counts_verified':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'PASS_SOURCE_AND_EXACT_MESSAGES','frozen_sources':len(files),'verified_messages':len(verified),
        'source_keep_bindings':10,'current_designs':4,'current_finish_aliases':8,'reference_heads_required':len(refs)}))


if __name__=='__main__':
    main()
