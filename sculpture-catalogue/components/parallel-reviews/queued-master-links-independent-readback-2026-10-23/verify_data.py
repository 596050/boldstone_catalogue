import collections, csv, datetime, hashlib, json, re
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
CAT = HERE.parents[2]
JOB = CAT / 'components/reconciliation/queued-master-links-and-egyptian-palm3-2026-10-23'
OUT = CAT / 'outputs/queued-master-links-and-egyptian-palm3-2026-10-23'
def load(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def check(ok, msg):
    if not ok: raise AssertionError(msg)
def rows(name):
    with (OUT / name).open(encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))
def backup_hits(value, p='', old=False):
    if isinstance(value, dict):
        for k,v in value.items():
            yield from backup_hits(v, p+'.'+k, old or k.startswith('historical_') or k.startswith('candidate_review_before_owner_'))
    elif isinstance(value, list):
        for i,v in enumerate(value): yield from backup_hits(v, p+'['+str(i)+']', old)
    elif isinstance(value,str) and re.search(r'BOLDSTONE[_ ]BACKUP',unquote(value),re.I):
        yield {'path':p,'historical':old}

reg_path=JOB/'canonical-master-register.json'
start_sha=sha(reg_path)
reg=load(reg_path); before=load(JOB/'inputs/master_register.before')
current={o['product_id']:o for o in reg['options']}; prior={o['product_id']:o for o in before['options']}
check(set(current)==set(prior) and len(current)==188, 'Option identities/count')
check(reg['components']==before['components'] and len(reg['components'])==112, 'Component definitions/count')
target='BSI-E0FAA8F7CB6D'
check(all(o==prior[k] for k,o in current.items() if k!=target),'Unrelated option objects changed')
fields=['name','retained_names','canonical_key','canonical_design_id','canonical_component_id','option_family_id','family','sale_unit','specifications','master_fields','selling_details','current_commercial_policy','offered_fixing_choices','six_working_fields_recorded','physical_specifications_verified','platform_publication_performed','confirmed_arrangement_ids']
for k,o in current.items():
    for field in fields: check(o.get(field)==prior[k].get(field),'Business field changed '+k+'.'+field)
o=current[target]; c=o['current_garden_component_confirmation']
check(o['context_file_id']=='id:cnqzTNngPVsAAAAAAAylFA','Garden native identity')
check(o['context_folder_id']=='id:cnqzTNngPVsAAAAAAAylCQ','Garden parent identity')
check(c['scope']=='COMPONENT_IDENTITY_ONLY' and 'SECOND panel from LEFT' in c['position'],'Owner component/position scope')
check(c['reference']['source_qualified_visual_binding'] and not c['reference']['scene_authenticity_verified'],'Qualified context scope')
check(not o['primary_image_role_correction']['in_situ'],'Product primary misused as installation')
check(o['primary_image_role_correction']['primary_file_id']=='id:cnqzTNngPVsAAAAAAAykzQ','Excluded primary identity')
counts={role:dict(collections.Counter(x['photo_coverage'][role] for x in current.values())) for role in ['individual','in_situ','series']}
check(counts['individual']=={'Available':177,'No verified image':1,'Unbound identity':1,'Group only':9},'Individual photo totals')
check(counts['in_situ']=={'Available':136,'No verified image':52},'Installation photo totals')
check(counts['series']=={'Optional / no fixed set':54,'Available':116,'No verified image':18},'Series photo totals')

native=load(JOB/'current-native-reference-map.json')['current_objects']
fresh=load(JOB/'fresh-folder-evidence.json')
files_checked=0; folders_checked=0
for slug in ['barbados','sally']:
    overlay=load(JOB/('inputs/'+slug+'.before'))
    check(overlay['status']=='COMPLETE_VERIFIED','Unfinished native overlay')
    prefixes=[x['current_path'] for x in overlay['prefix_maps']]
    for item in overlay['objects']:
        display=re.sub(r'^ns:\d+/', '', item['current_path'])
        if not any(display==p or display.startswith(p+'/') for p in prefixes): continue
        live=native[item['file_id']]
        check(live['path']==item['current_path'] and live['parent_id']==item['current_parent_id'],'Native path/parent map '+item['file_id'])
        check(live['name']==item['current_name'] and live['size']==item['size'],'Native name/size map')
        if item['object_type']=='file':
            files_checked+=1
            hits=[e for f in fresh.values() for e in f['listing']['entries'] if e['file_id']==item['file_id']]
            check(len(hits)==1 and hits[0]['path']==item['current_path'] and hits[0]['file']['size']==item['size'],'Fresh file listing mismatch')
        else:
            folders_checked+=1
            hits=[f for f in fresh.values() if f['metadata']['folder']['id']==item['file_id']]
            check(len(hits)==1 and not hits[0]['listing'].get('has_more'),'Fresh folder pagination incomplete')
check((files_checked,folders_checked)==(13,2),'Workshop native coverage count')
expected={'Missing_Individual_Images.csv':2,'Missing_In_Situ_Images.csv':52,'Missing_Series_Images.csv':18,'Missing_Pictures_Required.csv':72,'Resolved_Image_Associations.csv':82,'Existing_Images_to_Check.csv':1}
for name,n in expected.items(): check(len(rows(name))==n,'CSV total '+name)
required=rows('Missing_Pictures_Required.csv')
check(len({(x['option_id'],x['role']) for x in required})==72,'Duplicate required photo actions')
check(dict(collections.Counter(x['action_type'] for x in required))=={'Find / capture':71,'Verify existing image':1},'Required photo action types')
check(target not in {x['option_id'] for x in rows('Missing_In_Situ_Images.csv')},'Garden context still open')
check({x['option_id'] for x in rows('Missing_Individual_Images.csv')}=={'BSI-C41824131174','BSI-04D6E8690F30'},'Individual queue identities')
check({'BSI-C41824131174','BSI-3635E3DC3434'} <= {x['option_id'] for x in rows('Missing_Series_Images.csv')},'Acanthus series gaps incorrectly closed')
check(any(x['option_id']=='BSI-04D6E8690F30' and 'deferred' in x['action'].lower() for x in rows('Missing_Individual_Images.csv')),'Frozen Fish deferral')
wall=load(CAT/'components/parallel-reviews/wall-circle-in-situ-review-2026-10-23/review-state.json')
check(wall['status']=='DEFERRED_BY_OWNER' and not any(x['owner_approved'] for x in wall['cases']),'Wall Circle review hold')
source_scans=[]
for name in ['canonical-master-register.json','current-assets.json','current-native-reference-map.json','guided-owner-review-state.json','image-coverage-current.json','photo-review-queue.json']:
    h=list(backup_hits(load(JOB/name)))
    check(not any(not x['historical'] for x in h),'Current backup source in '+name)
    source_scans.append({'file':name,'sha256':sha(JOB/name),'active_backup_references':0,'historical_audit_mentions':len(h)})
report_files=[]
for p in OUT.iterdir():
    if p.suffix in ['.html','.csv']:
        check(not re.search(r'BOLDSTONE[_ ]BACKUP',unquote(p.read_text()),re.I),'Backup source in report '+p.name)
        report_files.append({'name':p.name,'sha256':sha(p)})
pointer=load(CAT/'current-master.json');published=(CAT/pointer['register']).resolve()==reg_path.resolve()
if published:
    check(pointer['register_sha256']==start_sha,'Published register SHA')
    check(pointer['workbook_sha256']==sha(CAT/pointer['workbook']),'Published workbook SHA')
    for key,n in [('current_options',188),('individual_gaps',2),('in_situ_gaps',52),('series_gaps',18),('required_actions',72)]:
        check(pointer['current_image_review_links']['counts'][key]==n,'Published count '+key)
check(sha(reg_path)==start_sha,'Register changed during readback')
result={'status':'PASS_PUBLISHED_SCOPED_DATA_AND_REPORTS' if published else 'PASS_PREPARED_SCOPED_DATA_AND_REPORTS','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'register':str(reg_path),'register_sha256':start_sha,'published_pointer_matches':published,'options':188,'components':112,'unrelated_options_identical':187,'all_188_names_specs_commercial_fields_preserved':True,'workshop_images_mapped':files_checked,'workshop_folders_mapped':folders_checked,'egyptian_component_position':'SECOND panel from LEFT','owner_decision_scope':'COMPONENT_IDENTITY_ONLY','photo_status_counts':counts,'required_picture_actions':72,'resolved_picture_actions':82,'acanthus_three_requested_photo_gaps_preserved':True,'source_scans':source_scans,'report_files':report_files,'canonical_writes':False,'dropbox_writes':False,'workbook_export_performed':False}
name='published-data-readback.json' if published else 'prepared-data-readback.json'
(HERE/name).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['source_scans','report_files','photo_status_counts']}))
