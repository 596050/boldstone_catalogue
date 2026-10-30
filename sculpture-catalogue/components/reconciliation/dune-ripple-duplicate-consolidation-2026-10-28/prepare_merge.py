"""Exact owner-directed duplicate consolidation, retaining source evidence."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import json,hashlib,sqlite3
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
m=read(H/'input-manifest.json');CUT=Path(m['input_directory']);s=m['sources']
KEEP='BSI-9299D69FEF08';DUP='BSI-4536FDCA0DA9'
decision=read(s['owner_owner-merge-decision']['snapshot'])
comparison=read(s['owner_merge-review-comparison']['snapshot'])
assert decision['keep_option_id']==KEEP and decision['retire_option_id']==DUP
assert comparison['same_folder'] and comparison['old_only_ids']==[] and comparison['union_image_associations']==60
original=read(s['register']['snapshot']);g=deepcopy(original);o={r['product_id']:r for r in g['options']};keep=o[KEEP];old=o[DUP]
assert keep['folder_id']==old['folder_id']=='id:cnqzTNngPVsAAAAAAAyj9w'
assert keep['canonical_component_id']==old['canonical_component_id']=='BC-DR-SPIRAL'
app=read(s['owner_'+KEEP+'-before']['snapshot']);overview=read(s['owner_'+KEEP+'-overview-before']['snapshot'])
oldapp=read(s['owner_'+DUP+'-before']['snapshot'])
assert not [r for r in oldapp['reviews'] if r['kind'] in {'image','product','assignment'}]
assert overview['primary_id']=='id:cnqzTNngPVsAAAAAAAyegw' and set(overview['listing_ids'])=={'id:cnqzTNngPVsAAAAAAAyegw','id:cnqzTNngPVsAAAAAAAygqQ'}
reviewdb=sqlite3.connect(Path(s['app_review_cut']['snapshot']).as_uri()+'?mode=ro',uri=True);reviewdb.row_factory=sqlite3.Row
for r in app['reviews']:
    if r['kind'] in {'product','image','field'}:
        q=dict(reviewdb.execute('SELECT * FROM reviews WHERE kind=? AND product_id=? AND item_id=?',(r['kind'],r['product_id'],r['item_id'])).fetchone())
        assert json.loads(q['data'])==r['data'] and q['version']==r['version'],'Keeper review changed after supplied decision packet'
savedprimary=next(r for r in app['reviews'] if r['kind']=='image' and r['item_id']==overview['primary_id'])
assert savedprimary['data']['primary'] and 'listing' in savedprimary['data']['uses']
reviewdb.close()
overlay=read(CUT/'current-image-overlay.json');files={r['file_id']:r for r in overlay}
fid=overview['primary_id'];assert fid in files and files[fid]['content_hash']==savedprimary['data']['reviewed_content_hash']
record={**decision,'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'RETIRED_DUPLICATE_RETAINED_IN_HISTORY','option_id':DUP,'replacement_option_id':KEEP,'instruction_path':s['owner_owner-merge-decision']['path'],'instruction_sha256':s['owner_owner-merge-decision']['sha256']}
keep['name']=decision['keep_name']
keep['retained_names']=list(dict.fromkeys(keep.get('retained_names',[])+[o[KEEP]['name']]+old.get('retained_names',[])+[old['name'],oldapp['name']]))
for key in ['source_scopes','related_platform_offer_refs','source_supported_platform_scope_refs']:
    keep[key]=list(dict.fromkeys(keep.get(key,[])+old.get(key,[])))
keep['file_id']=fid;keep['folder_id']=files[fid]['folder_id'];keep['image_url']=files[fid]['image_url'];keep['folder_url']=files[fid]['folder_url']
keep['current_primary_selection']={'basis':'Exact existing keeper Primary and Listing choice preserved by the owner-directed merge','review_version':savedprimary['version'],'review_updated_at':savedprimary['updated_at'],'decision_source_register_sha256':savedprimary['source_hash'],'scope':'Image selection only. Current keeper fields and their uncertainty retained; no native or physical verification inferred.'}
keep['current_saved_listing_images']=[{'file_id':r['item_id'],'folder_id':files[r['item_id']]['folder_id'],'image_url':files[r['item_id']]['image_url'],'folder_url':files[r['item_id']]['folder_url'],'review_version':r['version'],'review_updated_at':r['updated_at'],'review_data':r['data'],'decision_source_register_sha256':r['source_hash']} for r in app['reviews'] if r['kind']=='image' and r['item_id'] in overview['listing_ids']]
keep['photo_coverage']['individual']='Available'
keep['owner_duplicate_consolidations']=deepcopy(keep.get('owner_duplicate_consolidations',[]))+[record]
keep['merged_duplicate_reference_qualifications']=[{'source_option_id':DUP,'file_id':x['id'],'prior_tier':x['old_tier'],'scope':'Carry the prior accepted reference and its original limits. Candidate relationships remain candidates; context hold and current series selection remain separate.'} for x in comparison['shared_tier_changes']]
keep['merged_source_platform_scope']={'source_option_id':DUP,'source_scopes':old['source_scopes'],'related_platform_offer_refs':old['related_platform_offer_refs'],'source_supported_platform_scope_refs':old['source_supported_platform_scope_refs'],'prior_platform_scope_note':old.get('platform_scope_note'),'source_current_listing_reconciliation':deepcopy(old.get('current_listing_reconciliation')),'scope':'Retained duplicate-source evidence. No exact current size/build/finish SKU match, live price or stock is upgraded by this merge.'}
old['counted_as_individual_option']=False;old['count_class']='Retired duplicate - historical identity retained';old['catalogue_retirement']=record
old['photo_coverage']={**old['photo_coverage'],'individual':'Retired / not applicable','in_situ':'Retired / not applicable','series':'Retired / not applicable'}
g['active_option_ids']=[pid for pid in original['active_option_ids'] if pid!=DUP]
g['retired_option_ids']=original['retired_option_ids']+[DUP]
g['catalogue_retirements']=original['catalogue_retirements']+[record];g['latest_catalogue_retirement']=record
g['aliases'].append({'alias_id':decision['decision_id'],'source':old['name'],'source_option_id':DUP,'targets':[KEEP],'target_option_ids':[KEEP],'relationship':'Owner-confirmed duplicate catalogue option','reason':decision['owner_quote'],'evidence':s['owner_owner-merge-decision']['path'],'individual_count_increment':0,'scope':'Exact Dune Ripple2 Verdigris/Copper alias only; preserve keeper specifications, review choices and qualified source associations.'})
active=set(g['active_option_ids'])
g['summary'].update(individual_options_on_identified_components=178,individual_named_working_options=185,current_option_records=185,current_field_groups=1110,options_with_six_working_fields=185,retired_option_records=4,individual_options_with_dropbox_reference=sum(r['product_id'] in active and bool(r.get('file_id')) for r in g['options']))
g['latest_dune_ripple_duplicate_consolidation']={'decision':record,'comparison':s['owner_merge-review-comparison'],'keeper_review_scope':{'source':s['owner_'+KEEP+'-before'],'primary_file_id':fid,'listing_ids':overview['listing_ids'],'product_status':'reviewed/include','review_writes_by_root':0},'active_options':185,'retained_options':189,'retired_options':4,'all_original_working_and_source_specifications_unchanged':True,'unrelated_pending_imports_applied':False,'native_or_platform_writes':0}
allowed_keep={'name','retained_names','source_scopes','related_platform_offer_refs','source_supported_platform_scope_refs','file_id','folder_id','image_url','folder_url','current_primary_selection','current_saved_listing_images','photo_coverage','owner_duplicate_consolidations','merged_duplicate_reference_qualifications','merged_source_platform_scope'}
allowed_old={'counted_as_individual_option','count_class','catalogue_retirement','photo_coverage'}
for a,b in zip(original['options'],g['options']):
    changed={k for k in set(a)|set(b) if a.get(k)!=b.get(k)}
    assert changed <= (allowed_keep if a['product_id']==KEEP else allowed_old if a['product_id']==DUP else set())
    assert a['specifications']==b['specifications'] and a.get('master_fields')==b.get('master_fields')
assert len(active)==185 and len(g['options'])==189 and len(g['retired_option_ids'])==4
assert g['original_review_specification_assertions']==original['original_review_specification_assertions']
for r in overlay:
    r['selected_references']=[x for x in r['selected_references'] if x['product_id']!=DUP]
    for x in r['selected_references']:
        if x['product_id']==KEEP:x['name']=keep['name']
    if r['file_id']==fid:r['selected_references'].append({'product_id':KEEP,'name':keep['name'],'role':'primary'})
write(H/'canonical-master-register.json',g);write(H/'current-image-overlay.json',overlay)
write(H/'merge-decision.json',record)
write(H/'register-preparation.json',{'status':'EXACT_DUNE_RIPPLE_DUPLICATE_PREPARED','keep':KEEP,'retire':DUP,'active_options':185,'retained_records':189,'retired_records':4,'working_fields':1110,'primary_references':g['summary']['individual_options_with_dropbox_reference'],'primary_requests':sum(r['product_id'] in active and not r.get('file_id') and bool(r.get('historical_primary_reference')) for r in g['options']),'qualified_reference_ids':[x['id'] for x in comparison['shared_tier_changes']],'keeper_original_specifications_unchanged':True,'all_original_assertions':1668,'other_options_changed':0})
print(json.dumps(read(H/'register-preparation.json'),indent=2))
