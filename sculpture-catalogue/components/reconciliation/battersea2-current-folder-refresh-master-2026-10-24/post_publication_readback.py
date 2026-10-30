"""Read the published files and all three controls, without changing the catalogue."""
import hashlib,json,pathlib,subprocess
from datetime import datetime,timezone
H=pathlib.Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(pathlib.Path(p).read_text());sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');r=read(H/'publication-receipt.json');g=read(B/p['register']);a=read(H/'image-coverage-current.json');rep=read(H/'report-verification.json');checks={}
checks['published_register']=p['register_sha256']==sha(B/p['register'])=='478189cb199cdf1b7a9b1e633bc858474973f39587d069fa18a682b5aaa9af03'
checks['published_workbook']=p['workbook_sha256']==sha(B/p['workbook'])=='44d59675007368274cde2305186fc3a68cbf5ba398b571a67696aba77f0edd66'
checks['pointer_bytes']=sha(B/'current-master.json')==r['current_master_pointer_sha256']
checks['three_controls']=all(sha(path)==digest and read(path)['current_master_catalogue']==p for path,digest in r['controls_sha256'].items())
checks['counts']=len(g['active_option_ids'])==p['current_option_count']==188 and len(g['options'])==p['retained_option_count']==189 and len(g['components'])==112
source=read(H/'photo-source-review.json');owner_ids=[o['product_id']for o in g['options']if o.get('current_series_optionality_policy')]
checks['owner_policy_counter']=source['owner_optional_series_policies']==len(source['owner_optional_series_requests'])==len(owner_ids)==g['latest_active_photo_source_review']['owner_optional_series_policies']==16
checks['source_review_bound']=sha(H/'photo-source-review.json')==g['latest_active_photo_source_review']['sha256']
checks['role_counts']=source['role_counts']=={'Individual':1,'Display/context':0,'Series':0} and len(source['requests'])==1
rows=[json.loads(s)for s in subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).splitlines()if s]
checks['terminal_one_active_case']=len(rows)==1 and rows[0]['option_id']=='BSI-C3AA3700F7DA'and rows[0]['role']=='Individual'
checks['optional_and_open']=a['counts']['required_picture_actions']==25 and a['counts']['series_statuses']['Optional / no fixed set']==70 and a['counts']['series_statuses']['No verified image']==1
checks['report_counts']=rep['counts']['required_actions']==25 and rep['counts']['active_photograph_roles']==1 and rep['counts']['active_series_requests']==0
pages={pathlib.Path(x['path']).name:x for x in rep['pages']}
checks['html_role_scope']=pages['index.html']['cards']==25 and pages['series-images.html']['cards']==pages['remaining-photograph-requests.html']['cards']==1
checks['all_report_bytes']=all(sha(x['path'])==x['sha256']for x in rep['pages']+rep['csv_files']+rep['thumbnail_files'])
checks['no_physical_promotion']=all(not o['physical_specifications_verified']for o in g['options']if o['product_id']in g['active_option_ids'])
o=next(o for o in g['options']if o['product_id']=='BSI-1B70A9FB1B26')
checks['battersea_primary_unchanged']=o['file_id']=='id:cnqzTNngPVsAAAAAAAylqA' and o['folder_id']=='id:cnqzTNngPVsAAAAAAAyjEg'
checks['battersea_context_actual_parent']=o['context_file_id']=='id:cnqzTNngPVsAAAAAAAud0g' and o['context_folder_id']=='id:cnqzTNngPVsAAAAAAA6VsA'
assert all(checks.values()),checks
result={'status':'PASS_PUBLISHED_SOURCE_WORKBOOK_CONTROLS_AND_QUEUE_READBACK','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],'new_photo_or_physical_claims':0}
(H/'post-publication-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
