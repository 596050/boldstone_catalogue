import collections, csv, datetime, hashlib, json, re
from pathlib import Path
from urllib.parse import unquote

HERE=Path(__file__).resolve().parent
CAT=HERE.parents[2]
JOB=CAT/'components/reconciliation/guided-acanthus-photo-and-spec-review-2026-10-23'
OUT=CAT/'outputs/guided-acanthus-photo-and-spec-review-2026-10-23'
REVIEW=HERE.parent/'acanthus-master-photo-search-2026-10-23'
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(ok,msg):
    if not ok:raise AssertionError(msg)
def backup_hits(v,old=False):
    if isinstance(v,dict):
        for k,x in v.items():yield from backup_hits(x,old or k.startswith('historical_') or k.startswith('candidate_review_before_owner_'))
    elif isinstance(v,list):
        for x in v:yield from backup_hits(x,old)
    elif isinstance(v,str) and re.search(r'BOLDSTONE[_ ]BACKUP',unquote(v),re.I) and not old:yield v
def rows(name):
    with (OUT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

regpath=JOB/'canonical-master-register.json';startsha=sha(regpath)
r=load(regpath);b=load(JOB/'inputs/master_register.before');a=load(REVIEW/'owner-image-approval.json')
cur={x['product_id']:x for x in r['options']};before={x['product_id']:x for x in b['options']}
targets={'BSI-A9FE7D79863A','BSI-70ECBB049292'}
check(set(cur)==set(before) and len(cur)==188,'Product IDs/count')
check(r['components']==b['components'] and len(r['components'])==112,'Component records')
check(all(o==before[k] for k,o in cur.items() if k not in targets),'Unrelated option objects changed')
fields=['name','canonical_key','family','sale_unit','master_fields','specifications','selling_details','offered_fixing_choices','physical_specifications_verified','file_id','folder_id','image_url','folder_url']
for k,o in cur.items():
    for field in fields:check(o.get(field)==before[k].get(field),'Protected field changed '+k+'.'+field)
    for role in ['individual','series']:check(o['photo_coverage'][role]==before[k]['photo_coverage'][role],'Unapproved photo role change')
bronze=cur['BSI-A9FE7D79863A'];binding=bronze['current_owner_approved_courtyard_reference']
check(binding['decision_id']==a['decision_id'],'Exact owner decision binding')
check(binding['member_position']=='RIGHT-HAND SQUARE PANEL','Component position')
check(bronze['context_file_id']=='id:cnqzTNngPVsAAAAAAAuf1w' and bronze['context_folder_id']=='id:cnqzTNngPVsAAAAAAAyhzw','Current source IDs')
check(bronze['current_photo_task_review']['roles']['in_situ']['owner_exact_image_role_approved'],'Explicit owner image approval flag')
check(not binding['reference']['physical_cast_or_size_certified'] and not binding['reference']['scene_authenticity_verified'],'Unsupported physical/provenance upgrade')
check('left panel is context only' in binding['qualification'].lower(),'Other panel context limit')
check(cur['BSI-C41824131174']['photo_coverage']['individual']=='No verified image','Sandstone individual gap closed incorrectly')
for pid in ['BSI-C41824131174','BSI-3635E3DC3434']:check(cur[pid]['photo_coverage']['series']=='No verified image','Acanthus series gap closed incorrectly')
counts={role:dict(collections.Counter(o['photo_coverage'][role] for o in cur.values()))for role in ['individual','in_situ','series']}
check(counts['individual']=={'Available':177,'No verified image':1,'Unbound identity':1,'Group only':9},'Individual counts')
check(counts['in_situ']=={'Available':138,'No verified image':50},'Installation counts')
check(counts['series']=={'Optional / no fixed set':54,'Available':116,'No verified image':18},'Series counts')
check(not list(backup_hits(r)),'Active backup reference')
check(sha(REVIEW/'originals/cnqzTNngPVsAAAAAAAuf1w.jpg')==a['source_content_checks'][0]['sha256'],'Accepted original SHA')
source=a['source_owner_event'];raw=(REVIEW/'owner-use-image-event.json').read_bytes().rstrip(b'\r\n');check(hashlib.sha256(raw).hexdigest()==source['event_sha256'],'Exact owner event SHA')
csv_checks={}
if (OUT/'Missing_In_Situ_Images.csv').exists():
    expected={'Missing_Individual_Images.csv':2,'Missing_In_Situ_Images.csv':50,'Missing_Series_Images.csv':18,'Missing_Pictures_Required.csv':70,'Resolved_Image_Associations.csv':84}
    for name,n in expected.items():
        found=rows(name);check(len(found)==n,'Report count '+name);csv_checks[name]=n
    check(not targets.intersection({x['option_id'] for x in rows('Missing_In_Situ_Images.csv')}),'Approved targets still in open installation queue')
pointer=load(CAT/'current-master.json');published=(CAT/pointer['register']).resolve()==regpath.resolve()
if published:
    check(pointer['register_sha256']==startsha,'Published register SHA')
    check(pointer['workbook_sha256']==sha(CAT/pointer['workbook']),'Published workbook SHA')
    check(pointer['current_option_count']==188,'Published count label')
    for k,n in [('current_options',188),('individual_gaps',2),('in_situ_gaps',50),('series_gaps',18),('required_actions',70)]:check(pointer['current_image_review_links']['counts'][k]==n,'Pointer photo count '+k)
    check(bool(csv_checks),'Published reports missing')
check(sha(regpath)==startsha,'Register changed during readback')
receipt={'status':'PASS_PUBLISHED_BRONZE_AND_FOUNTAIN_CONTEXT_IMPORT' if published else 'PASS_PREPARED_BRONZE_AND_FOUNTAIN_CONTEXT_IMPORT','recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'register_sha256':startsha,'published':published,'bronze_owner_decision_id':a['decision_id'],'bronze_source_file_id':bronze['context_file_id'],'target_member_position':binding['member_position'],'owner_approval_packet_sha256':sha(REVIEW/'owner-image-approval.json'),'all188option_ids_names_specs_and_primaries_preserved':True,'all112component_records_preserved':True,'unrelated_options_identical':186,'three_requested_acanthus_photo_gaps_preserved':True,'counts':counts,'csv_counts':csv_checks,'canonical_writes':False,'workbook_export_performed':False,'dropbox_writes':False}
(HERE/('published-import-readback.json' if published else 'prepared-import-readback.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
