"""Apply the frozen owner receipts once, with scope and current-ID guards."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = ROOT / 'components/reviews'


def read(p):
    return json.loads(p.read_text())


def write(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name + '.tmp')
    t.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    t.replace(p)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return str(p.relative_to(ROOT))


def main():
    receipt_path = HERE / 'import-receipt.json'
    if receipt_path.exists():
        assert read(receipt_path)['status'] == 'APPLIED_AND_VERIFIED'
        print('ALREADY_APPLIED')
        return
    now = datetime.now(timezone.utc).isoformat()
    manifest = read(HERE / 'source-manifest.json')
    metadata = read(HERE / 'current-reference-check.json')
    current = {x['request_id']: x for x in metadata['metadata']}
    moved = read(HERE / 'moved-spiral-parent-refresh.json')
    moved_parents = {x['folder']['path_display']: x['folder'] for x in moved['parents']}
    moved_downloads = {x['id']: x for x in read(HERE / 'moved-spiral-download-receipts.json')}
    current_links = {x['path_display']: x['copy_link_url'] for x in moved['previews']}
    model = read(ROOT / 'components/evidence/component_register.json')
    source_names = {x['component_id']: x['name'] for x in model['components']}
    for f in manifest['files']:
        assert sha(ROOT / f['snapshot']) == f['sha256']
    refs, prepared = [], []
    for d in manifest['decisions']:
        if d['kind'] == 'variant_dimensions':
            continue
        v = read(ROOT / d['review_snapshot'])
        f = current[d['primary_file_id']]['file']
        old_folder = current[d['primary_folder_id']]['folder']
        expected, expected_folder = d['primary_expected'], d['folder_expected']
        assert f['id'] == d['primary_file_id']
        assert f['size'] == expected.get('size', expected.get('bytes'))
        expected_path = expected.get('path', expected.get('path_display'))
        historical_folder_path = expected_folder.get('path', expected_folder.get('path_display'))
        assert old_folder['path_display'] == historical_folder_path
        changed = f['rev'] != expected['rev'] or f['path_display'] != expected_path
        if changed:
            download = moved_downloads[f['id']]
            actual = Path(download['local_path']).read_bytes()
            dbhash = hashlib.sha256(b''.join(hashlib.sha256(actual[i:i+4194304]).digest() for i in range(0,len(actual),4194304))).hexdigest()
            assert dbhash == download['content_hash'] == expected['content_hash']
            assert len(actual) == f['size']
            parent = moved_parents[f['path_display'].rsplit('/',1)[0]]
            image_url, folder_url = current_links[f['path_display']], current_links[parent['path_display']]
        else:
            parent = old_folder
            assert f['path_display'] == expected_path
            image_url, folder_url = d['image_url'], d['folder_url']
        assert f['path_display'].rsplit('/',1)[0] == parent['path_display']
        live = {'file_id': f['id'], 'folder_id': parent['id'], 'file_path': f['path_display'], 'folder_path': parent['path_display'], 'rev': f['rev'], 'bytes': f['size'], 'image_url': image_url, 'folder_url': folder_url, 'checked_utc': metadata['checked_utc'], 'moved_since_owner_card': changed, 'historical_file_path': expected_path, 'historical_folder_id': d['primary_folder_id'], 'historical_folder_path': historical_folder_path, 'same_image_bytes_verified_for_move': changed}
        refs.append({'name': d['name'], 'component_id': d['component_id'], **live})
        prepared.append((d, v, live))
    assert len(prepared) == 22 and len(refs) == 22
    assert sum(x['moved_since_owner_card'] for x in refs) == 2

    paths = {'user':REVIEWS/'user_classifications.json','progress':REVIEWS/'specification_review_progress.json','walkthrough':REVIEWS/'walkthrough_checkpoint.json','component':ROOT/'components/checkpoint.json','root':ROOT/'checkpoint.json'}
    docs = {k: read(p) for k,p in paths.items()}
    user, progress, cp, component = [docs[k] for k in ['user','progress','walkthrough','component']]
    assert cp['current_component_id'] == 'BC-FDW-2' and cp['current_answer_recorded']
    assert not cp['current_specification_answer_recorded']
    assert docs['root']['current_component_review'] == component
    active_keys = [k for k in cp if k.startswith('current_')] + ['state','answer_state','question_scope','proposed_name','primary_image','containing_folder','next_review_after_keep','active_family','family_review_order','last_completed_component_id','last_completed_review_number','last_identity_approval']
    active_before = {k: copy.deepcopy(cp[k]) for k in active_keys}
    protected_paths = [ROOT/'components/evidence/component_register.json',ROOT/cp['register_workbook'],ROOT/cp['current_review_record']]
    protected = {str(p):sha(p) for p in protected_paths}
    prior_lists = {k: copy.deepcopy(user.get(k,[])) for k in ['decisions','specification_decisions','dimension_decisions','build_variant_decisions','size_finish_variant_decisions','family_decisions']}
    prior_progress = copy.deepcopy(progress['reviews'])
    before_hashes = {k:sha(p) for k,p in paths.items()}
    write(HERE/'before-import.json', {'recorded_utc':now,'files':{rel(paths[k]):v for k,v in docs.items()},'protected_sha256':protected,'shared_before_sha256':before_hashes})
    imported = []
    for d,v,live in prepared:
        cid, kind = d['component_id'], d['kind']
        variant, build = d.get('variant_id'), d.get('build_variant_id')
        full = bool(d['specifications_approved'])
        if kind == 'component_identity':
            target_list = user['decisions']
            decision_id = f'{cid}:identity:keep'
            target = progress['reviews'].setdefault(cid, {})
        else:
            parent = progress['reviews'].setdefault(cid, {'canonical_name':source_names[cid],'identity_confirmed':False,'specifications_approved':False,'physical_specs_verified':False,'scope':'Source parent identity unchanged. Owner decisions below apply only to the specified depicted finish or build configuration.'})
            if kind == 'size_finish_variant_identity':
                target_list = user.setdefault('size_finish_variant_decisions',[])
                decision_id = f'{cid}:{variant}:identity:keep'
                target = parent.setdefault('size_finish_variants',{}).setdefault(variant,{})
            else:
                target_list = user.setdefault('build_variant_identity_decisions',[])
                decision_id = f'{cid}:{build}:identity:keep'
                target = parent.setdefault('build_variants',{}).setdefault(build,{})
        assert not any(x['decision_id'] == decision_id for x in target_list)
        slug = variant or build or 'component'
        dest = HERE/'decisions'/cid/slug
        identity_path = dest/'identity-approval.json'
        approval = {'schema_version':1,'decision_id':decision_id,'recorded_utc':d['recorded_utc'],'imported_utc':now,'component_id':cid,'size_finish_variant_id':variant,'build_variant_id':build,'review_number':d['review_number'],'canonical_name':d['name'],'confirmed_name':d['name'],'proposed_name_at_review':d['name'],'action':'keep name and depicted identity','status':'USER CONFIRMED NAME AND IDENTITY ONLY' if not full else 'NAME KEPT; WORKING PROPOSALS APPROVED IN SEPARATE VARIANT RECEIPT','identity_confirmed':True,'user_statement':d['statement'],'source_owner_session':d['owner_session'],'source_decision_id':d['source_decision_id'],'source_receipt_snapshot':d['receipt'],'source_receipt_sha256':d['source_receipt_sha256'],'proposal_source':d['review_snapshot'],'proposal_source_sha256':d['pre_answer_review_sha256'],'authoritative_user_evidence':d['authoritative_user_evidence'],'evidence_file_id':live['file_id'],'primary_file_id':live['file_id'],'containing_folder_id':live['folder_id'],'primary_folder_id':live['folder_id'],'evidence_file_ids':[live['file_id']],'containing_folder_ids':[live['folder_id']],'image_link':live['image_url'],'folder_link':live['folder_url'],'current_dropbox_reference':live,'scope':'Only this depicted individual/component/finish/build name and identity are kept here. Source claims, guesses, physical measurements, materials, fixing capacity, stock, lead time and platform mapping retain their separate uncertainty. The source parent name and other variants are not renamed.','confirmed_fields':['depicted name','depicted individual identity'],'specifications_approved':False,'proposals_approved':False,'approved_proposal_ids':[],'physical_specs_verified':False,'remote_files_changed':False,'live_platform_records_changed':False,'workbook_status':'Unchanged; review overlay only'}
        write(identity_path,approval)
        target_list.append(approval|{'approval_record':rel(identity_path)})
        items=[]
        for x in v['specification_review_items']:
            item=copy.deepcopy(x)
            item['display']=x.get('display',x.get('displayed_detail',x.get('proposal','')))
            item['owner_approved']=full
            item['physical_specs_verified']=False
            items.append(item)
        target.update({'reviewed_utc':now,'identity_confirmed':True,'identity_confirmed_utc':d['recorded_utc'],'canonical_name':d['name'],'proposed_name':d['name'],'size_finish_variant_id':variant,'build_variant_id':build,'identity_approval':rel(identity_path),'specification_proposals':items,'specifications_approved':full,'proposals_approved':full,'physical_specs_verified':False,'source_specifications_recorded':True,'review_record':d['review_snapshot'],'primary_image_id':live['file_id'],'primary_folder_id':live['folder_id'],'image_link':live['image_url'],'folder_link':live['folder_url'],'current_dropbox_reference':live,'platform_mapping':copy.deepcopy(v.get('platform_mapping',v.get('platform_evidence',{}))),'source_conflicts':copy.deepcopy(v.get('source_conflicts',[])),'missing_photographs':copy.deepcopy(v.get('missing_photographs',[])),'remaining_unknowns':copy.deepcopy(v.get('open_questions',v.get('missing_specifications',[]))),'source_owner_session':d['owner_session'],'workbook_contains_import':False})
        if full:
            assert variant == 'DP-SPIRAL-GOLD-45x40'
            sr=read(ROOT/d['receipt'])
            spec={'schema_version':1,'decision_id':f'{cid}:{variant}:specifications:keep','recorded_utc':d['recorded_utc'],'imported_utc':now,'component_id':cid,'size_finish_variant_id':variant,'canonical_name':d['name'],'user_statement':d['statement'],'status':'USER APPROVED THIS VARIANT WORKING PROPOSALS; ESTIMATES REMAIN ESTIMATES','scope':'Only corrected-size Golden Spiral. Owner-confirmed45×40×5cm plus five remaining working groups retained. GBP250 accepted as working individual price for the corrected size. Approximately10kg(range8–12),chemistry,hardware and availability remain estimates/unknowns. No acceptance of Timeless white specifications or all parent variants.','approved_proposal_ids':d['approved_proposal_ids'],'approved_specification_items':items,'approved_details':sr['approved_details'],'proposals_approved':True,'physical_specs_verified':False,'source_receipt_snapshot':d['receipt'],'authoritative_user_evidence':d['authoritative_user_evidence'],'primary_file_id':live['file_id'],'primary_folder_id':live['folder_id'],'image_link':live['image_url'],'folder_link':live['folder_url'],'retained_limits':sr['retained_limits']}
            spec_path=dest/'specification-approval.json';write(spec_path,spec)
            user.setdefault('size_finish_variant_specification_decisions',[]).append(spec|{'approval_record':rel(spec_path)})
            target.update({'specification_approval':rel(spec_path),'approved_specification_items':items,'specification_proposals_status':spec['status']})
        else:
            q=cp.setdefault('pending_specification_reviews',[])
            key=(cid,variant,build)
            assert not any((x.get('component_id'),x.get('size_finish_variant_id'),x.get('build_variant_id'))==key for x in q)
            q.append({'component_id':cid,'size_finish_variant_id':variant,'build_variant_id':build,'canonical_name':d['name'],'identity_approved':True,'specifications_approved':False,'pending_fields':[x.get('field',x.get('group')) for x in items],'review_record':d['review_snapshot'],'identity_approval':rel(identity_path),'image_link':live['image_url'],'folder_link':live['folder_url']})
        imported.append({'component_id':cid,'kind':kind,'size_finish_variant_id':variant,'build_variant_id':build,'name':d['name'],'identity_approval':rel(identity_path),'working_specifications_approved':full,'source_receipt':d['source_receipt'],'authoritative_user_line':d['authoritative_user_evidence']['line']})

    dimension=next(d for d in manifest['decisions'] if d['kind']=='variant_dimensions')
    source=read(ROOT/dimension['receipt']);cid=dimension['component_id'];variant=dimension['variant_id']
    live=next(x for x in refs if x['name']==dimension['name'])
    decision={'schema_version':1,'decision_id':f'{cid}:{variant}:dimensions:owner-stated','recorded_utc':dimension['recorded_utc'],'imported_utc':now,'component_id':cid,'size_finish_variant_id':variant,'canonical_name':dimension['name'],'action':'confirm the dimensions of the same pictured gold object','user_statement':dimension['statement'],'confirmed_dimensions_cm':source['confirmed_dimensions_cm'],'dimension_order':source['dimension_order'],'previous_listing_dimensions_cm':source['previous_listing_dimensions_cm'],'previous_source_variant_alias':source['source_variant_id'],'source_listing_size_conflict_retained':True,'superseded_weight_guess':'6kg(range5–7); retired with30×30size applicability','current_weight_guess':'10kg(range8–12); not weighed','status':'OWNER CONFIRMED DIMENSIONS','physical_specs_verified':False,'source_receipt_snapshot':dimension['receipt'],'authoritative_user_evidence':dimension['authoritative_user_evidence'],'primary_file_id':live['file_id'],'primary_folder_id':live['folder_id'],'current_dropbox_reference':live,'image_link':live['image_url'],'folder_link':live['folder_url'],'physical_stock_inferred':False}
    dim_path=HERE/'decisions'/cid/variant/'dimension-approval.json';write(dim_path,decision)
    assert not any(x['decision_id']==decision['decision_id'] for x in user['dimension_decisions'])
    user['dimension_decisions'].append(decision|{'approval_record':rel(dim_path)})
    progress['reviews'][cid]['size_finish_variants'][variant].update({'dimension_approval':rel(dim_path),'owner_confirmed_dimensions_cm':source['confirmed_dimensions_cm'],'dimension_order':source['dimension_order'],'same_pictured_object_not_new_stock_item':True,'previous_source_variant_alias':source['source_variant_id']})

    parent_names=len({x['component_id'] for x in user['decisions']})
    build_names=user.get('build_variant_identity_decisions',[])
    all_identity_lists=[user['decisions'],user['size_finish_variant_decisions'],user.get('build_variant_decisions',[]),build_names]
    counts=user['identity_confirmation_counts']
    counts.update({'component_designs':parent_names,'explicit_size_finish_variant_names':len({(x['component_id'],x['size_finish_variant_id']) for x in user['size_finish_variant_decisions'] if x.get('identity_confirmed')}),'explicit_build_variant_decisions':len(user.get('build_variant_decisions',[]))+len(build_names),'components_with_any_identity_scope':len({x['component_id'] for seq in all_identity_lists for x in seq})})
    regular_groups=sum(len(x['approved_proposal_ids']) for x in user['specification_decisions'])
    build_groups=sum(len(x['approved_proposal_ids']) for x in user.get('build_variant_decisions',[]))
    variant_groups=sum(len(x['approved_proposal_ids']) for x in user.get('size_finish_variant_specification_decisions',[]))
    user['specification_approval_counts']={'components':len({x['component_id'] for x in user['specification_decisions']}),'component_proposal_groups':regular_groups,'build_variant_approvals':sum(bool(x.get('proposals_approved')) for x in user.get('build_variant_decisions',[])),'build_variant_proposal_groups':build_groups,'size_finish_variant_approvals':len(user.get('size_finish_variant_specification_decisions',[])),'size_finish_variant_proposal_groups':variant_groups,'proposal_groups':regular_groups+build_groups+variant_groups}
    user['dimension_confirmation_counts']={'components':len({x['component_id'] for x in user['dimension_decisions']}),'face_size_decisions':len(user['dimension_decisions'])}
    user['updated_utc']=progress['updated_utc']=now
    progress['latest_parallel_import']=rel(receipt_path)
    queued={x['receipt'] for x in cp['parallel_import_queue']}
    for x in manifest['queue_entries']:
        if x['receipt'] not in queued:
            cp['parallel_import_queue'].append(copy.deepcopy(x));queued.add(x['receipt'])
    consumed={x['receipt'] for x in manifest['queue_entries']}
    for x in cp['parallel_import_queue']:
        if x['receipt'] in consumed:
            x.update({'status':'IMPORTED WITH EXACT OWNER SCOPE; WORKBOOK EXPORT PENDING','approval_imported':True,'import_receipt':rel(receipt_path),'imported_utc':now})
    cids=sorted({d['component_id'] for d in manifest['decisions']})
    for x in cp['parallel_owner_reviews']:
        if x['component_id'] in cids:
            x.update({'status':'RECEIVED OWNER ANSWERS IMPORTED; OTHER VARIANTS AND SPECIFICATION GAPS MAY REMAIN','import_receipt':rel(receipt_path)})
    summary={'recorded_utc':now,'receipt':rel(receipt_path),'component_ids':cids,'identity_receipts':22,'dimension_receipts':1,'full_working_variant_receipts':1,'name_only_specification_approvals_inferred':False,'active_review_preserved':True,'workbook_export_pending':True}
    cp['last_parallel_import']=summary
    cp['next_serialized_parallel_import'].update({'status':'APPLIED_AND_VERIFIED','receipt':rel(receipt_path),'completed_utc':now,'bounded_queue_cutoff_utc':manifest['cutoff_utc']})
    cp['updated_utc']=now
    component.update({'parallel_import_queue':copy.deepcopy(cp['parallel_import_queue']),'parallel_owner_reviews':copy.deepcopy(cp['parallel_owner_reviews']),'last_parallel_import':copy.deepcopy(summary),'updated_utc':now})
    component['interactive_review_state'].update({'explicit_identity_confirmations':parent_names,'components_with_any_identity_scope':counts['components_with_any_identity_scope'],'explicit_size_finish_variant_names_confirmed':counts['explicit_size_finish_variant_names'],'explicit_build_variant_names':len(build_names),'explicit_specification_approvals':user['specification_approval_counts']['components'],'approved_proposal_groups':regular_groups+build_groups+variant_groups})
    docs['root']['current_component_review']=copy.deepcopy(component)
    assert {k:cp[k] for k in active_keys}==active_before
    for k,v in prior_lists.items():assert user[k][:len(v)]==v,k
    for cid,v in prior_progress.items():assert progress['reviews'][cid]==v,cid
    assert user['specification_approval_counts']['components']==8 and regular_groups==49 and build_groups==6 and variant_groups==6
    assert all(sha(Path(p))==digest for p,digest in protected.items())
    assert all(sha(paths[k])==digest for k,digest in before_hashes.items()),'Shared writer collision'
    write(HERE/'verified-current-references.json',{'checked_utc':now,'records':refs,'unchanged_reference_cards':20,'moves_verified_by_identical_bytes':2})
    for k,p in paths.items():write(p,docs[k])
    for k,p in paths.items():assert read(p)==docs[k]
    assert read(paths['root'])['current_component_review']==read(paths['component'])
    assert all(sha(Path(p))==digest for p,digest in protected.items())
    receipt={'status':'APPLIED_AND_VERIFIED','recorded_utc':now,**summary,'imported':imported,'counts':{'identity':counts,'specification':user['specification_approval_counts'],'dimensions':user['dimension_confirmation_counts']},'protected_sha256':protected,'shared_after_sha256':{k:sha(p) for k,p in paths.items()},'source_model_workbook_unchanged':True,'physical_specs_verified':False,'remote_files_changed':False,'live_platform_records_changed':False}
    write(receipt_path,receipt)
    event={'event_id':'parallel-import:bounded-batch2:2026-10-17','event':'VERIFIED_OWNER_RECEIPTS_IMPORTED','recorded_utc':now,'import_receipt':rel(receipt_path),'identity_receipts':22,'dimension_receipts':1,'full_variant_working_approvals':1,'current_component_id':'BC-FDW-2','current_answer_changed':False,'remote_files_changed':False}
    for p in [REVIEWS/'identity_review_journal.jsonl',ROOT/'review_journal.jsonl']:
        with p.open('a') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
    print(json.dumps({'status':receipt['status'],'identity_receipts':22,'components_touched':len(cids),'source_model_workbook_unchanged':True,'counts':receipt['counts']},ensure_ascii=False))


if __name__=='__main__':main()
