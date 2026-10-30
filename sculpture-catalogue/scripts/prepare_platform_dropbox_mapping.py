"""Bridge confirmed platform pairs to current Dropbox metadata and scoped image evidence."""
import json
from collections import Counter
from pathlib import Path

project=Path(__file__).resolve().parents[1];ev=project/'evidence'
platform=json.loads((ev/'platform_comparison_2026-10-16.json').read_text())
catalogue=json.loads((ev/'catalogue_model.json').read_text())
source=json.loads((ev/'catalogue_source_tables_2026-10-15.json').read_text())
inputs=json.loads((ev/'platform_dropbox_link_inputs.json').read_text())
live=json.loads((ev/'platform_dropbox_live_metadata_2026-10-16.json').read_text())
metadata={r['id']:r for r in live['entries']}
decisions={r['asset_id']:r for r in json.loads((ev/'established_image_decisions.json').read_text())}
cache=json.loads((ev/'image_review_cache_index.json').read_text())
historical={r['Shopify handle']:r for r in source['Historical Products']}
group_by_id={r['group_id']:r for r in catalogue['groups']}
pair_by_id={r['match_id']:r for r in platform['matches']}
records=[]
for r in inputs['records']:
    pair=pair_by_id[r['match_id']];family=r['family_links'];members=r['member_links'];gallery=r['gallery_links']
    for link in family:
        assert metadata[link['family_id']]['metadata_type']=='folder'
    for link in members+gallery:
        file=metadata[link['asset_id']];folder=metadata[link['leaf_id']]
        assert file['metadata_type']=='file' and folder['metadata_type']=='folder'
        assert file['path_display'].rsplit('/',1)[0].casefold()==folder['path_display'].casefold()
        assert cache[file['id']]['hash_verified']
        assert cache[file['id']]['sha256']==decisions[file['id']]['current_source_sha256'],'Image bytes changed since visual review'
        assert Path(cache[file['id']]['local_path']).stat().st_size==file['size']
    status='Member / arrangement image confirmed' if members else 'Gallery reference only; arrangement unresolved' if gallery else 'Family reference only; individual unresolved'
    old=historical.get(pair['sh_handle'],{})
    parts=int(old['Parts']) if old.get('Parts','').isdigit() else None
    component_state='Whole-set image linked; individual components still require separate identification' if members and parts and parts>1 else 'Single-piece image linked; source dimensions and physical specification remain unmeasured' if members and parts==1 else 'Individual component mapping pending'
    notes=list(dict.fromkeys('Earlier image-review note: '+link['detail'] for link in members+gallery if link['detail']))
    for link in members+gallery:
        before=group_by_id[link['group_id']]['group_name'];now=metadata[link['leaf_id']]['name']
        if before!=now:notes.append('Current folder name is '+now+'. The stable folder ID is unchanged from the earlier label '+before+'.')
    if not members:notes.append('Family references narrow the search; they do not establish a specific design, finish, size or sale arrangement.')
    if members:notes.append('Only the reviewed image/member arrangement is linked. Other files or finishes in that folder are not automatically assigned the offer specifications.')
    if any('In Situ' in metadata[link['leaf_id']]['name'] for link in members):notes.append('Context-image correspondence does not independently establish a real installation.')
    records.append(dict(match_id=r['match_id'],sku=pair['sku'],sq_id=pair['sq_id'],sq_title=pair['sq_title'],sh_handle=pair['sh_handle'],sh_title=pair['sh_title'],status=status,
        family_names=list(dict.fromkeys(metadata[x['family_id']]['name'] for x in family)),family_ids=list(dict.fromkeys(x['family_id'] for x in family)),family_paths=list(dict.fromkeys(metadata[x['family_id']]['path_display'] for x in family)),
        group_names=[metadata[x['leaf_id']]['name'] for x in members],group_ids=[x['group_id'] for x in members],member_folder_ids=[x['leaf_id'] for x in members],member_paths=[metadata[x['leaf_id']]['path_display'] for x in members],file_ids=[x['asset_id'] for x in members],file_paths=[metadata[x['asset_id']]['path_display'] for x in members],
        gallery_group_names=[metadata[x['leaf_id']]['name'] for x in gallery],gallery_folder_ids=[x['leaf_id'] for x in gallery],gallery_paths=[metadata[x['leaf_id']]['path_display'] for x in gallery],gallery_file_ids=[x['asset_id'] for x in gallery],
        source_parts=parts,source_each_cm=old.get('Each component (cm)',''),source_overall_cm=old.get('Overall (cm)',''),source_finish=old.get('Finish stated in export',''),component_state=component_state,cautions='\n'.join(notes),
        next_action='Identify each constituent sculpture and its full-front image, then scope component versus assembled specifications' if members and parts and parts>1 else 'Review the remaining folder media and adopt only specifications that apply to this design, finish and size' if members else 'Compare primary native product images against individual Dropbox members; resolve finish, size and full arrangement before accepting the link',
        metadata_checked_utc=live['checked_utc']))
counts=dict(platform_pairs=len(records),family_references=sum(bool(r['family_ids']) for r in records),member_arrangement_image_links=sum(bool(r['member_folder_ids']) for r in records),gallery_only=sum(bool(r['gallery_folder_ids']) and not r['member_folder_ids'] for r in records),family_only=sum(not r['gallery_folder_ids'] and not r['member_folder_ids'] for r in records),individual_mapping_unresolved=sum(not r['member_folder_ids'] for r in records),current_metadata_items=len(metadata),current_file_hashes_verified=sum(r['metadata_type']=='file' for r in metadata.values()))
assert (counts['platform_pairs'],counts['family_references'],counts['member_arrangement_image_links'],counts['gallery_only'],counts['family_only'])==(37,37,13,4,20)
result=dict(source_sha256=platform['source_sha256'],checked_utc=live['checked_utc'],counts=counts,records=records,metadata=list(metadata.values()),method='Connect the exact-SKU platform pair to its source sale arrangement, then identify each component design, finish and size. Current stable Dropbox folder/file IDs and scoped visual evidence preserve the link despite renames. Family and gallery references remain separate from confirmed member/arrangement image correspondence.')
(ev/'platform_dropbox_mapping_2026-10-16.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(counts))
