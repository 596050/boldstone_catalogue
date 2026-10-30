"""Verify published source bindings, controls and all retained owner holds."""
import hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');r=read(H/'publication-receipt.json');g=read(B/p['register']);a=read(H/'image-coverage-current.json');rep=read(H/'report-verification.json');saved=read(H/'saved-file-verification.json');checks={}
checks['published_register']=p['register_sha256']==r['register_sha256']==saved['register_sha256']==sha(B/p['register'])
checks['published_workbook']=p['workbook_sha256']==r['workbook_sha256']==saved['workbook_sha256']==sha(B/p['workbook'])
checks['pointer_bytes']=sha(B/'current-master.json')==r['current_master_pointer_sha256']
checks['three_controls']=all(sha(path)==digest and read(path)['current_master_catalogue']==p for path,digest in r['controls_sha256'].items())
checks['counts']=len(g['active_option_ids'])==p['current_option_count']==188 and len(g['options'])==p['retained_option_count']==189 and len(g['components'])==112
source=read(H/'photo-source-review.json');owner_ids=[o['product_id']for o in g['options']if o.get('current_series_optionality_policy')]
checks['owner_policy_counter']=source['owner_optional_series_policies']==len(source['owner_optional_series_requests'])==len(owner_ids)==g['latest_active_photo_source_review']['owner_optional_series_policies']==16
checks['source_review_bound']=sha(H/'photo-source-review.json')==g['latest_active_photo_source_review']['sha256']
checks['role_counts']=source['role_counts']=={'Individual':0,'Display/context':0,'Series':0}and not source['requests']
checks['terminal_no_active_case']=not subprocess.check_output(['python3',str(H/'guided_review.py'),'--list'],text=True).strip()
checks['optional_and_held']=a['counts']['required_picture_actions']==24 and a['counts']['series_statuses']['Optional / no fixed set']==70 and a['counts']['series_statuses']['No verified image']==1
checks['report_counts']=rep['counts']['required_actions']==24 and rep['counts']['active_photograph_roles']==rep['counts']['active_series_requests']==0
pages={Path(x['path']).name:x for x in rep['pages']};checks['html_role_scope']=pages['index.html']['cards']==24 and pages['series-images.html']['cards']==1 and pages['remaining-photograph-requests.html']['cards']==0 and pages['all-current-spiralmoon-images.html']['cards']==82
checks['all_report_bytes']=all(sha(x['path'])==x['sha256']for x in rep['pages']+rep['csv_files']+rep['thumbnail_files'])
checks['no_physical_promotion']=all(not o['physical_specifications_verified']for o in g['options']if o['product_id']in g['active_option_ids'])
o=next(o for o in g['options']if o['product_id']=='BSI-10BFED6B265B');checks['spiralmoon_primary_same_file_actual_parent']=o['file_id']=='id:cnqzTNngPVsAAAAAAAuXEw'and o['folder_id']=='id:cnqzTNngPVsAAAAAAAyjFg'
checks['spiralmoon_context_unchanged']=o['context_file_id']=='id:cnqzTNngPVsAAAAAAArqFA'and o['context_folder_id']=='id:cnqzTNngPVsAAAAAAAyjFg'
assets=read(H/'current-assets.json');repairs=read(H/'auxiliary-current-asset-navigation-repairs.json');checks['auxiliary_repairs']=len(repairs)==4 and all(assets[x['file_id']][x['field']]==x['current']for x in repairs)
state=read(H/'guided-owner-review-state.json');checks['holds_preserved']=len(state['held_in_situ_ids'])==22 and state['held_series_ids']==['BSI-C3573D23A4B7']and state['deferred_individual_ids']==['BSI-04D6E8690F30']
assert all(checks.values()),checks
result={'status':'PASS_PUBLISHED_SOURCE_WORKBOOK_CONTROLS_AND_QUEUE_READBACK','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks':checks,'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256'],'new_photo_or_physical_claims':0};(H/'post-publication-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
