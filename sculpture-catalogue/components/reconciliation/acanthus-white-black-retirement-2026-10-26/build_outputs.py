"""Current 187-option readers and neutral exports, with immutable source cutoffs."""
from pathlib import Path
from urllib.parse import quote
from collections import Counter
from datetime import datetime, timezone
import argparse, csv, hashlib, html, json

H=Path(__file__).resolve().parent
B=H.parents[2]
OUT=B/'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/acanthus-white-black-retirement-2026-10-26'
OID='BSI-B0D0CCA7E318'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
dump=lambda p,v:Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
esc=lambda s:html.escape(str(s),quote=True)
parser=argparse.ArgumentParser();parser.add_argument('--native-snapshot',required=True,type=Path);a=parser.parse_args()
g=read(H/'canonical-master-register.json');old=read(H/'inputs/register.json');p=read(H/'inputs/pointer.json')
active=[o for o in g['options'] if o['product_id'] in g['active_option_ids']]
assert len(active)==187 and OID not in {o['product_id'] for o in active}
assert all(o==next(r for r in old['options'] if r['product_id']==o['product_id']) for o in active)
assert read(H/'saved-workbook-verification.json')['status']=='PASS'
state=read(a.native_snapshot)
assert state['scope']['root_path']=='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
assert state['scope']['namespace']=='202238505' and state['scan']['has_more'] is False and state['native_writes']==0
records=state['records'];images={k:v for k,v in records.items() if v['kind']=='file'}
folders={k:v for k,v in records.items() if v['kind']=='folder'}
assert len(images)==state['image_count'] and all(k==v['id'] for k,v in records.items())
case_normalizations=[]
for r in images.values():
    assert r['folder_id'] in folders and str(Path(r['path']).parent).casefold()==folders[r['folder_id']]['path'].casefold()
    if str(Path(r['path']).parent)!=folders[r['folder_id']]['path']:
        case_normalizations.append({'file_id':r['id'],'folder_id':r['folder_id'],'reported_file_path':r['path'],
            'stable_id_parent_path':folders[r['folder_id']]['path']})
    assert r['path'].startswith(state['scope']['root_path']+'/')
owned=[r['target'] for r in read(H/'native-readback.json')['rows']]
assert all(fid not in records for fid in owned)
snapshot={'path':str(a.native_snapshot.resolve()),'sha256':sha(a.native_snapshot),'generation':state['generation'],
    'checked_utc':state['checked_utc'],'images':len(images),'folders_including_root':len(folders),
    'basis':'Immutable app Dropbox-sync snapshot; exact retired folder/three files separately checked NOT_FOUND by catalogue publisher.',
    'root_independent_full_native_rescan':False,'native_writes_by_publisher':0}
overlay={fid:{**r,'file_id':fid,'object_type':'file','display_path':r['path'],'current_wall_snapshot_present':True,
    'image_url':'https://www.dropbox.com/preview'+quote(folders[r['folder_id']]['path']+'/'+r['name'],safe='/'),
    'folder_url':'https://www.dropbox.com/home'+quote(folders[r['folder_id']]['path'],safe='/')} for fid,r in images.items()}
for fid,r in folders.items():overlay[fid]={**r,'folder_id':fid,'object_type':'folder','display_path':r['path'],
    'current_wall_snapshot_present':True,'folder_url':'https://www.dropbox.com/home'+quote(r['path'],safe='/')}
dump(H/'current-native-overlay.json',{'schema':'boldstone.retirement-current-native/v1','source_snapshot':snapshot,
    'current_objects':overlay,'retired_owned_ids_not_found':owned,'case_only_parent_url_normalizations':case_normalizations,
    'no_image_identity_or_review_selection_import':True})
def reference(o,context=False):
    ref=o if o.get('file_id') else o.get('owner_confirmed_design_reference',{})
    fid=o.get('context_file_id') if context else ref.get('file_id')
    folder=o.get('context_folder_id') if context else ref.get('folder_id')
    native=overlay.get(fid,{})
    current_folder=native.get('folder_id') or folder
    folder_native=overlay.get(current_folder,{})
    return {'file_id':fid or '', 'folder_id':current_folder or '', 'native_image_present':fid in images,
        'image_url':native.get('image_url',''), 'folder_url':folder_native.get('folder_url',''),
        'historical_image_url':ref.get('image_url',''),'historical_folder_url':ref.get('folder_url','')}
def write_csv(name,rows,columns):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader();w.writerows(rows)
fields=list(active[0]['master_fields'])
option_rows=[];field_rows=[];photo_rows=[]
for o in active:
    pid=o['product_id'];r=reference(o);c=reference(o,True)
    row={'option_id':pid,'name':o['name'],'family':o['family'],'component_id':o['canonical_component_id'],
        'individual_reference_scope':o['photo_coverage']['individual'],'primary_file_id':o.get('file_id',''),
        'primary_folder_id':o.get('folder_id',''),'reference_file_id':r['file_id'],'reference_folder_id':r['folder_id'],
        'image_url':r['image_url'],'folder_url':r['folder_url'],'native_image_present_at_cutoff':r['native_image_present']}
    for key,v in o['master_fields'].items():
        row[key]=v['display'];row[key+' evidence state']=v['state']
        field_rows.append({'option_id':pid,'name':o['name'],'field':key,'working_display':v['display'],
            'evidence_state':v['state'],'basis':v['basis'],'physical_verification':v['physical_verification']})
    option_rows.append(row)
    photo_rows.append({'option_id':pid,'name':o['name'],'family':o['family'],
        **o['photo_coverage'],'file_id':r['file_id'],'folder_id':r['folder_id'],'image_url':r['image_url'],
        'folder_url':r['folder_url'],'native_individual_reference_present':r['native_image_present'],
        'context_file_id':c['file_id'],'context_folder_id':c['folder_id'],'context_image_url':c['image_url'],
        'context_folder_url':c['folder_url'],'native_context_reference_present':c['native_image_present'],
        'in_situ_owner_hold':pid in g['current_global_context_owner_hold']['all_held_option_ids']})
assert len(field_rows)==1122
write_csv('Current_Individual_Options_187.csv',option_rows,list(option_rows[0]))
write_csv('Specification_Verification_Checklist_1122_Fields.csv',field_rows,list(field_rows[0]))
photo_columns=['option_id','name','family','individual','in_situ','series','file_id','folder_id','image_url','folder_url',
    'native_individual_reference_present','context_file_id','context_folder_id','context_image_url','context_folder_url',
    'native_context_reference_present','in_situ_owner_hold']
write_csv('Photo_Coverage_187.csv',photo_rows,photo_columns)
write_csv('Held_In_Situ_Cases_22.csv',[r for r in photo_rows if r['in_situ_owner_hold']],photo_columns)
with (B/p['current_missing_picture_lists']['held_series_cases_csv']).open(encoding='utf-8-sig',newline='') as f:
    series_hold=list(csv.DictReader(f))
assert len(series_hold)==1 and all(r['option_id'] in g['active_option_ids'] for r in series_hold)
write_csv('Held_Series_Cases_1.csv',[r for r in photo_rows if r['option_id']==series_hold[0]['option_id']],photo_columns)
optional_series=[r for r in photo_rows if r['series'].startswith('Optional')]
write_csv('Optional_Series_Images_'+str(len(optional_series))+'.csv',optional_series,photo_columns)
technical=[r for r in photo_rows if r['individual']!='Available']
write_csv('Technical_Individual_References_11.csv',technical,photo_columns)
for role in ['Individual','In_Situ','Series']:
    write_csv('Active_'+role+'_Photograph_Requests_0.csv',[],photo_columns)
write_csv('Native_Absent_Source_References.csv',[r for r in photo_rows if not r['native_individual_reference_present']],photo_columns)
write_csv('Current_Wall_Images_'+str(len(images))+'.csv',[overlay[fid] for fid in images],
    ['file_id','name','folder_id','path','image_url','folder_url','rev','bytes','content_hash'])
write_csv('Current_Working_Design_Groups_110.csv',[
    {k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v for k,v in r.items()}
    for r in g['current_working_design_group_projection']['groups']],
    list(g['current_working_design_group_projection']['groups'][0]))
with (B/p['current_specification_verification']['actual_physical_measurement_input']).open(encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f);input_columns=reader.fieldnames;physical=[r for r in reader if r['option_id'] in g['active_option_ids']]
assert len(physical)==187 and {r['option_id'] for r in physical}==set(g['active_option_ids'])
by_id={o['product_id']:o for o in active}
for r in physical:
    native=reference(by_id[r['option_id']]);r.update(individual_image=native['image_url'],containing_folder=native['folder_url'],file_id=native['file_id'],folder_id=native['folder_id'])
write_csv('Physical_Verification_Input_187_Options.csv',physical,input_columns)
treatment=read(H/'listing-treatment-register.json')
assert {r['product_id'] for r in treatment['options']}==set(g['active_option_ids'])
treatment_columns=['product_id','name','family','canonical_component_id','listing_treatment','reason','status',
    'selected_squarespace_product_id','selected_squarespace_variant_id','selected_existing_source_sku',
    'selected_local_shopify_handle','proposed_listing_sku','proposed_sku_state','proposed_handle','native_execution_allowed']
write_csv('Active_Listing_Treatments_187.csv',treatment['options'],treatment_columns)
css='body{font:17px/1.5 Arial;max-width:1150px;margin:32px auto;padding:0 18px;color:#222}a{color:#075993}article{border:1px solid #ccc;margin:20px 0;padding:18px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #ddd}th{width:22%}.scope{background:#f0f3ed;padding:15px}.missing{background:#fff0dd;padding:12px}small{overflow-wrap:anywhere}details{margin:8px 0}'
nav='<p><a href="index.html">Current master</a> · <a href="all-options.html">187 active options</a> · <a href="specifications-to-verify.html">Specifications</a> · <a href="photograph-checklist.html">Photographs</a> · <a href="listing-treatments.html">Listing treatments</a> · <a href="retired-history.html">Retired history</a> · <a href="http://127.0.0.1:8767">Live app</a></p>'
scope='<p class="scope">187 active sculpture options; 189 retained records, including two owner-retired finishes. Dropbox navigation uses stable IDs at sync generation '+str(state['generation'])+' ('+esc(state['checked_utc'])+'). The live app continues refreshing. Working specifications, actual physical verification and platform matches retain their separate evidence states.</p>'
def page(title,body):return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style><body><h1>'+esc(title)+'</h1>'+scope+nav+body+'</body></html>'
def links(o):
    r=reference(o)
    image='<a href="'+esc(r['image_url'])+'">Dropbox image</a>' if r['image_url'] else '<span>Recorded individual reference absent at this cutoff</span>'
    folder='<a href="'+esc(r['folder_url'])+'">Actual containing folder</a>' if r['folder_url'] else '<span>Recorded folder absent at this cutoff</span>'
    return '<p>'+image+' · '+folder+' · <a href="http://127.0.0.1:8767/#'+esc(o['product_id'])+'">Review in app</a></p><small>File '+esc(r['file_id'])+' · folder '+esc(r['folder_id'])+'</small>'
def spec_table(o):
    return '<table><tr><th>Field</th><th>Working detail</th><th>Evidence</th></tr>'+''.join('<tr><th>'+esc(k)+'</th><td>'+esc(v['display']).replace('\n','<br>')+'</td><td>'+esc(v['state']).replace('\n','<br>')+'</td></tr>' for k,v in o['master_fields'].items())+'</table>'
cards=[];spec_cards=[];photo_cards=[];treatment_cards=[]
for o in active:
    pid=o['product_id'];head='<article id="'+esc(pid)+'"><h2>'+esc(o['name'])+'</h2>'+links(o)
    roles=o['photo_coverage'];coverage='<p>Individual: '+esc(roles['individual'])+'<br>In situ: '+esc(roles['in_situ'])+'<br>Series: '+esc(roles['series'])+'</p>'
    cards.append(head+coverage+spec_table(o)+'</article>')
    spec_cards.append(head+spec_table(o)+'<p>Enter actual measurements, bare-panel weight, maker material and fitted-fixing inspection in the blank input file. A populated working field is not a physical verification.</p></article>')
    c=reference(o,True);context='<p><a href="'+esc(c['image_url'])+'">Recorded context image</a> · <a href="'+esc(c['folder_url'])+'">Context folder</a></p>' if c['image_url'] else '<p>Recorded context file absent or unbound at this cutoff.</p>'
    hold='<p>Owner hold retained. Do not repeat the missing in situ request until resumed.</p>' if pid in g['current_global_context_owner_hold']['all_held_option_ids'] else ''
    photo_cards.append(head+coverage+context+hold+'<p>Group references retain their individual-component, variation and scene-origin qualifications. No exact crop or replacement-primary choice is created.</p></article>')
    t=next(r for r in treatment['options'] if r['product_id']==pid)
    treatment_cards.append(head+'<p>'+esc(t['listing_treatment'])+'</p><p>'+esc(t['reason'])+'</p><details><summary>Local platform and proposed identifiers</summary><table>'+''.join('<tr><th>'+esc(k)+'</th><td>'+esc(t.get(k,''))+'</td></tr>' for k in treatment_columns if k not in {'product_id','name','family','canonical_component_id','listing_treatment','reason'})+'</table></details></article>')
(OUT/'all-options.html').write_text(page('187 active sculpture options',''.join(cards)))
(OUT/'specifications-to-verify.html').write_text(page('187 options: specification evidence and physical input','<p><a href="Physical_Verification_Input_187_Options.csv">Actual measurement input</a> · <a href="Specification_Verification_Checklist_1122_Fields.csv">1,122 current field groups</a></p>'+''.join(spec_cards)))
(OUT/'photograph-checklist.html').write_text(page('Photograph coverage for 187 active options','<p>Native availability is checked separately from the retained source-role classification. The 22 existing in situ owner holds and separately held series question remain unchanged.</p>'+''.join(photo_cards)))
(OUT/'listing-treatments.html').write_text(page('187 local listing treatments','<p>Neutral local plan. Proposed SKUs/handles are not observed live native records. No Squarespace or Shopify writes were performed.</p>'+''.join(treatment_cards)))
retired=[o for o in g['options'] if o['product_id'] in g['retired_option_ids']]
(OUT/'retired-history.html').write_text(page('Two owner-retired options: retained history',''.join('<article id="'+esc(o['product_id'])+'"><h2>'+esc(o['name'])+'</h2><p>'+esc(o['product_id'])+' · Retired. No active listing, photograph or measurement task.</p><small>Historical file '+esc(o.get('file_id',''))+' · folder '+esc(o.get('folder_id',''))+'</small></article>' for o in retired)))
(OUT/'index.html').write_text(page('Current sculpture master: 187 active options','<p>Acanthus Two Leaves - White and Black is retired. Its owned folder and three files are absent; other Acanthus finishes and shared source evidence are retained.</p><p><a href="Current_Individual_Options_187.csv">187-option CSV</a> · <a href="Active_Listing_Treatments_187.csv">187 local listing treatments</a> · <a href="Photo_Coverage_187.csv">Photo coverage CSV</a></p><p><a href="Boldstone_Wall_Sculptures_Unified_2026-10-26.xlsx">Comprehensive workbook</a></p><p>The related Bronze source offer O069 is retained. There is no exact mapped White and Black native offer; live platform removal has not been established.</p>'))
summary={'schema':'boldstone.current187-retirement/v1','created_utc':datetime.now(timezone.utc).isoformat(),
    'active_options':187,'retained_option_records':189,'retired_option_records':2,'current_specification_field_groups':1122,
    'retained_specification_field_groups':1134,'original_source_assertions_preserved':1668,'component_id_records':112,
    'working_design_groups':110,'native_snapshot':snapshot,'source_register':str(H/'canonical-master-register.json'),
    'source_register_sha256':sha(H/'canonical-master-register.json'),'option_order':g['active_option_ids'],
    'individual_source_statuses':dict(Counter(r['individual'] for r in photo_rows)),
    'in_situ_source_statuses':dict(Counter(r['in_situ'] for r in photo_rows)),
    'series_source_statuses':dict(Counter(r['series'] for r in photo_rows)),
    'listing_treatments':dict(Counter(r['listing_treatment'] for r in treatment['options'])),
    'in_situ_owner_holds':sum(r['in_situ_owner_hold'] for r in photo_rows),
    'series_owner_holds':len(series_hold),'optional_series_references':len(optional_series),
    'active_individual_photograph_requests':0,'active_in_situ_photograph_requests':0,'active_series_photograph_requests':0,
    'individual_reference_native_present':sum(r['native_individual_reference_present'] for r in photo_rows),
    'physical_verifications_added':0,'native_and_platform_writes':0,'app_review_state_writes':0}
dump(OUT/'current-count-summary.json',summary)
outputs={str(f):sha(f) for f in OUT.iterdir() if f.is_file() and not f.name.endswith('.inspect.ndjson')}
dump(H/'output-manifest.json',{'status':'CURRENT187_OUTPUTS_PREPARED','output_directory':str(OUT),'summary':summary,
    'native_overlay':str(H/'current-native-overlay.json'),'native_overlay_sha256':sha(H/'current-native-overlay.json'),'outputs':outputs})
print(json.dumps({k:summary[k] for k in ['active_options','retained_option_records','retired_option_records','current_specification_field_groups','native_snapshot','individual_source_statuses','in_situ_owner_holds','individual_reference_native_present']},indent=2))
