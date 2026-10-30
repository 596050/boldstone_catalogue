"""Check the published pointer, controls, count scopes and terminal projections."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(B/'current-master.json');r=read(H/'publication-receipt.json');m=read(H/'input-manifest.json');old=read(m['pointer']['snapshot']);g=read(B/p['register']);checks=[]
def check(ok,name):checks.append({'name':name,'passed':bool(ok)})
check(p['register']==str((H/'canonical-master-register.json').relative_to(B)),'Current release selected')
check(sha(B/p['register'])==p['register_sha256']==r['register_sha256'],'Register bytes match')
check(sha(B/p['workbook'])==p['workbook_sha256']==r['workbook_sha256'],'Workbook bytes match')
check(sha(B/'current-master.json')==r['current_master_pointer_sha256'],'Pointer bytes match')
for path,digest in r['controls_sha256'].items():check(sha(path)==digest and read(path)['current_master_catalogue']==p,'Control '+path)
check(p['current_option_count']==188 and p['retained_option_count']==189 and len(g['components'])==112,'Options and retained IDs preserved')
check(p['current_working_design_group_projection']['grouped_working_design_identity_count']==len(g['current_working_design_group_projection']['groups'])==111,'Working group projection111')
check(len(g['current_owner_design_equivalence_edges'])==1 and not g['current_owner_design_equivalence_edges'][0]['number2_confirmed'],'One number1-only owner edge')
check(g['latest_image_coverage_audit']['counts']==old['latest_image_coverage_audit']['counts'],'Source-photo counts unchanged')
check(p['current_primary_navigation_health']['unresolved_primaries']==2,'Prior native-primary warnings retained')
check(not p['all_actual_specifications_complete'],'Physical verification not upgraded')
for key in ['platform_write_holds','current_frozen_fish_size_policy','wall_sculpture_customisation_policy','current_individual_photo_capture_policy','current_global_context_owner_hold']:check(p[key]==old[key],'Preserved '+key)
physical=read(H/'physical-source-audit.json')['summary'];check(physical['active_options_reviewed']==188 and physical['physical_field_groups_reviewed']==752 and physical['new_qualified_comparator_field_groups_reviewed']==4,'Existing physical checklist scope and comparator qualification')
check(sha(H/'physical-source-audit.json')==m['physical_audit']['sha256'],'Physical ledger bytes unchanged')
walk=read(B.parent/'reports/catalogue-terminal-walkthrough-20261024/walkthrough-state.json');check(len(walk['items'])==12 and walk['register_sha256']==p['register_sha256']and walk['workbook_sha256']==p['workbook_sha256'],'Twelve-item walkthrough bound to published bytes')
source=read(B.parent/'reports/catalogue-terminal-walkthrough-20261024/source-comparison-readback.json');check(source['register_sha256']==p['register_sha256']and source['counts']['documented_pairs']==37 and source['counts']['unpaired_squarespace_source_records']==43,'Historical source comparison scope retained')
for path,digest in source['files'].items():check(sha(path)==digest,'Source comparison '+Path(path).name)
result={'status':'PASS'if all(x['passed']for x in checks)else'FAIL','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':sum(x['passed']for x in checks),'checks_total':len(checks),'checks':checks,'published_pointer_sha256':sha(B/'current-master.json'),'register_sha256':p['register_sha256'],'workbook_sha256':p['workbook_sha256']};(H/'post-publication-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k]for k in ['status','checks_passed','checks_total','published_pointer_sha256']}));assert result['status']=='PASS'
