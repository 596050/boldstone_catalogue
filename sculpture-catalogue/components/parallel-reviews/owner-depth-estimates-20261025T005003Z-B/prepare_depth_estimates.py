"""Prepare the owner's requested estimates, without editing shared catalogue files."""
from pathlib import Path
from datetime import datetime, timezone
from html import escape
import copy
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())
save = lambda p, x: Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
now = datetime.now(timezone.utc).isoformat()
pointer_path = BASE/'current-master.json'
pointer = read(pointer_path)
register_path = BASE/pointer['register']
register = read(register_path)
assert sha(register_path)==pointer['register_sha256']
source_audit = BASE/'components/parallel-reviews/specification-double-check-20261025T004202Z-B/audit.json'
target_ids = set(read(source_audit)['dimension_gaps'])
opts = {o['product_id']:o for o in register['options']}
instruction = {
    'decision_id':'OWNER-REQUESTED-MISSING-DEPTH-ESTIMATES-2026-10-25',
    'recorded_utc':now,'source_thread_id':'01a13fe6-495b-7253-b923-31823b4cbca8',
    'owner_request_verbatim':'you estimate the depth',
    'context':'The preceding complete audit listed 14 active options with unresolved depth, including 3 with unresolved overall face dimensions.',
    'authority':'Owner explicitly requests estimates. Numerical values below are assistant estimates, not owner-reported measurements or independently confirmed specifications.',
    'scope':'Populate the missing working depth for exactly the 14 identified options. Keep estimates and ranges explicit. Retain existing face dimensions and face-size unknowns.',
    'not_inferred':['Owner measured these depths','Owner approved the exact numeric values individually','Base material or finish composition','New width or height for Azure or bordered Moonphases','Mounting stand-off or packing dimensions','New weights, hardware ratings, price, availability, image roles or identity relationships'],
}
save(HERE/'owner-instruction.json',instruction)
definition = 'Overall sculpture-body depth from the rear face of its panel/backing to the highest relief or integral border. Excludes mounting stand-off, separate brackets, plumbing and packaging. This is not uniform material thickness.'
images = {
    'chelsea':'/Users/tprice/Documents/boldstone/sculpture-catalogue/components/reconciliation/image-identity-coverage-2026-10-20/cache/cnqzTNngPVsAAAAAAA53Gw.original',
    'gleneagles':'/Users/tprice/Library/Application Support/BoldstoneImageConsistency/review-20261015T223009Z/thumbnails/73c6c4f294b95eb5ef23961ca79288e8937850304668d5f44458896b0e427f57.jpg',
    'lava':'/Users/tprice/Documents/boldstone/sculpture-catalogue/components/reconciliation/in-situ-folder-refresh-and-context-review-2026-10-23/originals/cnqzTNngPVsAAAAAAA6VpQ.png',
    'bordered_moonphase':'/Users/tprice/Documents/boldstone/reports/dropbox-moonphase-bordered-arrangement-review-2026-10-23/originals/moonphases__moonphases-with-borders-white__001.png',
    'azure':'/Users/tprice/Library/Application Support/BoldstoneImageConsistency/review-20261015T223009Z/thumbnails/27d1197d794c00bd1c385954f72d615421d7cafcabd391ceb82f5721f3172dee.jpg',
}
comparators = {
    pid:{'name':opts[pid]['name'],'dimensions':opts[pid]['master_fields']['Dimensions / depth']['display']}
    for pid in ['BSI-830A4594D176','BSI-A76B86DA7928','BSI-6581D83760F1','BSI-BCAB636141CC','BSI-8C0D9152DF73','BSI-41E5370B1314']
}
rows=[]
for pid in sorted(target_ids):
    o=opts[pid]
    before=copy.deepcopy(o['master_fields']['Dimensions / depth'])
    if pid=='BSI-F95020D6821C':
        group='Chelsea Moonwave'; image_key='chelsea'; nominal=10; interval=[6,14]
        display='250 cm high × 100 cm wide — owner confirmed. Overall sculpture-body depth approximately 10 cm; working range 6–14 cm — owner-authorized estimate, not measured.'
        basis='Rounded low-confidence planning depth for the large raised relief. Retains the earlier 10 cm depth hypothesis mentioned in the current Chelsea weight basis, compared with Chiswick Moon approximately 10 cm and Barbados Wave 8 cm. The reference helps identify relief form but is not calibrated dimensional evidence.'
        comparable_ids=['BSI-830A4594D176','BSI-A76B86DA7928']
    elif o['name'].startswith('Gleneagles Vine and Tendril'):
        group='Gleneagles Vine and Tendril 1–4';image_key='gleneagles';nominal=6;interval=[4,8]
        display='35 × 35 cm face per panel — owner instructed. Overall sculpture-body depth approximately 6 cm; working range 4–8 cm — owner-authorized estimate, not measured. Overall four-panel face arrangement remains 70 × 70 cm.'
        basis='A comparison-based working estimate for a 35 cm relief panel, using Leaf Form White 35 × 35 × 6 cm and Acanthus One Leaf Left 30 × 30 × 6 cm. The same nominal depth is a planning assumption for the four companion panels; component-specific maximum relief remains unmeasured.'
        comparable_ids=['BSI-6581D83760F1','BSI-BCAB636141CC']
    elif re.fullmatch(r'Lava Moon [123] — (White|Sandstone)',o['name']):
        group='Lava Moon 1–3, White and Sandstone';image_key='lava';nominal=8;interval=[5,12]
        display='80 cm wide × 240 cm high — owner confirmed for all Lava Moon panels. Overall sculpture-body depth approximately 8 cm; working range 5–12 cm — owner-authorized estimate, not measured.'
        basis='Low-confidence planning allowance for a large backed spiral-relief panel, compared with Barbados Wave 8 cm and Chiswick Moon approximately 10 cm. A common nominal is applied to the companion panels and finishes as an explicit estimate. The existing 30 mm average material thickness used for mass estimation is not maximum relief depth. Retained display imagery may be processed/derivative and is not used as a scale measurement.'
        comparable_ids=['BSI-A76B86DA7928','BSI-830A4594D176']
    elif pid in {'BSI-65A93033A200','BSI-4515726BBC18'}:
        group='Moonphase 1 and 2 with borders';image_key='bordered_moonphase';nominal=6;interval=[5,8]
        display='Bordered overall width and height remain unconfirmed. Overall sculpture-body depth approximately 6 cm; working range 5–8 cm — owner-authorized estimate, not measured. Historical core reference is approximately 30 × 30 cm; approximately 35 × 35 cm outer size remains a weight-model assumption, not an owner measurement.'
        basis='Conditional depth estimate from the unbordered White Moonphase maker range of 5–7 cm and 6 cm historical plaster description. The upper range allows for an unverified border/backing build. The photograph depicts a bordered relief but does not establish its true scale or whether the frame is integral. No new face dimensions or material claim is inferred.'
        comparable_ids=['BSI-8C0D9152DF73','BSI-41E5370B1314']
    elif pid=='BSI-3C849B547D50':
        group='Azure — Blue and White Marbled Panel';image_key='azure';nominal=3;interval=[2,5]
        display='Artwork width and height remain unconfirmed. Overall sculpture-body depth approximately 3 cm; working range 2–5 cm — low-confidence owner-authorized estimate, not measured. Historical shipping fields convert to approximately 100 × 16 × 4 cm; these remain shipping figures, not artwork dimensions.'
        basis='A conditional shallow-relief/backing planning estimate. The previous prepared 2–3 cm depth idea is reused only as an explicitly labelled hypothesis, with range widened to 2–5 cm because the support and back are unseen. The photographed poured/marbled surface suggests a shallow panel but supplies no reliable depth scale. The shipping height of approximately 4 cm is not treated as measured panel depth. No artwork width, height or substrate is inferred.'
        comparable_ids=[]
    else:
        raise AssertionError(pid)
    estimate={'nominal_cm':nominal,'range_cm':interval,'status':'OWNER_AUTHORIZED_ASSISTANT_ESTIMATE_NOT_MEASURED','definition':definition,'low_confidence':True,'basis':basis,'comparator_option_ids':comparable_ids,'individual_owner_numeric_confirmation':False,'physical_measurement':False}
    after=copy.deepcopy(before)
    after['display']=display
    after['state']=before.get('state','')+'\nOverall depth: owner-authorized working estimate under the 25 October 2026 request; not physically measured.'
    after['basis']=before.get('basis','')+'\nDepth estimate, 25 October 2026: '+basis+'\nDepth definition: '+definition
    after['prior_display']=before['display']
    after['working_recorded']=1
    after['physical_verification']=0
    after['depth_estimate']=estimate
    after.setdefault('source_references',[]).append({'path':str(HERE/'owner-instruction.json'),'sha256':sha(HERE/'owner-instruction.json'),'decision_id':instruction['decision_id']})
    rows.append({'product_id':pid,'name':o['name'],'group':group,'field':'Dimensions / depth','before':before,'after':after,'estimate':estimate,'image_url':o.get('image_url',''),'folder_url':o.get('folder_url',''),'visually_inspected_reference':{'path':images[image_key],'sha256':sha(images[image_key]),'scope':'Relief-form context only; not calibrated measurement or construction certification.'}})

assert {r['product_id'] for r in rows}==target_ids and len(rows)==14
assert all(r['after']['physical_verification']==0 and 'estimate' in r['after']['display'].lower() for r in rows)
assert all(r['estimate']['range_cm'][0]<=r['estimate']['nominal_cm']<=r['estimate']['range_cm'][1] for r in rows)
packet={
    'schema':'boldstone-owner-depth-estimate-packet-v1','recorded_utc':now,'decision_id':instruction['decision_id'],
    'owner_instruction':{'path':str(HERE/'owner-instruction.json'),'sha256':sha(HERE/'owner-instruction.json')},
    'base_pointer':{'path':str(pointer_path),'sha256':sha(pointer_path)},
    'base_register':{'path':str(register_path),'sha256':sha(register_path)},
    'base_workbook':{'path':str(BASE/pointer['workbook']),'sha256':pointer['workbook_sha256']},
    'audit':{'path':str(source_audit),'sha256':sha(source_audit)},
    'depth_definition':definition,'comparator_snapshots':comparators,'rows':rows,
    'scope_guards':{'only_target_14_dimension_depth_master_fields_authorized':True,'preserve_existing_face_size_and_unknowns':True,'retain_historical_source_assertions':True,'no_other_1134_minus_14_field_objects_changed':True,'no_weight_material_fixing_price_availability_changes':True,'no_identity_image_native_platform_changes':True,'new_physical_measurements':0},
    'expected_after':{'active_options':188,'current_working_field_groups':1128,'depth_estimate_fields_added':14,'all_188_options_have_working_depth':True,'face_size_gaps_remaining':['BSI-65A93033A200','BSI-4515726BBC18','BSI-3C849B547D50'],'base_material_gaps_remaining':27,'new_physical_verifications':0},
    'publisher_work':'Publish through Main. Update current Specifications and its dependent views, register, field checklist, current physical-evidence working-description projections and measurement-input working descriptions, with historical originals preserved. Keep measurement entry cells blank. Rebind the current image reader to the new register without changing associations. Retain photo deferrals.',
}
save(HERE/'depth-estimate-packet.json',packet)
cells=[]
for r in rows:
    e=r['estimate'];cells.append('<tr><td>'+escape(r['name'])+'</td><td>'+str(e['nominal_cm'])+' cm</td><td>'+str(e['range_cm'][0])+'–'+str(e['range_cm'][1])+' cm</td><td>'+escape(r['after']['display'])+'</td><td><a href="'+escape(r['image_url'],quote=True)+'">Image</a> · <a href="'+escape(r['folder_url'],quote=True)+'">Folder</a></td></tr>')
html='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Estimated sculpture depths</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:auto;padding:30px;color:#243035}table{border-collapse:collapse;width:100%}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid #ddd}th{background:#edf0f0}a{color:#165c78}</style></head><body><h1>Estimated sculpture depths</h1><p>Requested by the owner on 25 October 2026. All values below are working estimates, not physical measurements. A range is retained for each.</p><p>'+escape(definition)+'</p><table><thead><tr><th>Sculpture / finish</th><th>Estimate</th><th>Working range</th><th>Updated working dimensions</th><th>References</th></tr></thead><tbody>'+''.join(cells)+'</tbody></table><p>Prepared for publication in the shared master. Width and height remain unresolved for Azure and the two bordered Moonphases. Existing weights and material descriptions are retained.</p></body></html>'
(HERE/'depth-estimates.html').write_text(html)
seal={'status':'PREPARED_OWNER_AUTHORIZED_ESTIMATES_FOR_MAIN_PUBLICATION','sealed_utc':now,'canonical_register_modified':False,'rows':14,'expected_register_sha256':pointer['register_sha256'],'files':{str(HERE/f):sha(HERE/f) for f in ['owner-instruction.json','depth-estimate-packet.json','depth-estimates.html']}}
save(HERE/'sealed-depth-estimates.json',seal)
assert sha(register_path)==pointer['register_sha256'] and sha(pointer_path)==packet['base_pointer']['sha256']
print(json.dumps({'seal':str(HERE/'sealed-depth-estimates.json'),'seal_sha256':sha(HERE/'sealed-depth-estimates.json'),'packet':str(HERE/'depth-estimate-packet.json'),'rows':len(rows)},indent=2))
