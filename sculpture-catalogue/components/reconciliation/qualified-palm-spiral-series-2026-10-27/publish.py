"""Publish only the three qualified series roles and their workbook views."""
from common import *
from copy import deepcopy
from datetime import datetime,timezone
import os,urllib.request,urllib.error,sqlite3

pointer=BASE/'current-master.json';old=read(pointer);assert sha(pointer)==manifest['publication_parent_pointer_sha256']
qa=read(H/'independent-verification.json');assert qa['status']=='PASS_INDEPENDENT_PUBLICATION_READBACK'
plans=read(H/'workbook-edit-plan.json')['plans'];core,unified=[Path(p['output']) for p in plans]
for wb in qa['workbooks']:assert sha(wb['output'])==wb['sha256']
assert len(active)==186 and len(g['options'])==189
paths=read(H/'current-reader-paths.json');series=g['latest_qualified_series_review'];positions=series['positions'];rel=lambda p:str(Path(p).relative_to(BASE))
count=read(BASE/old['current_individual_sculpture_list']['count_summary']);count.update(open_series_replacements=3,current_series_references=read(H/'register-preparation.json')['current_series_references'],latest_qualified_series_option_ids=list(positions));write(OUT/'current-count-summary.json',count)
new=deepcopy(old);new.update(recorded_utc=datetime.now(timezone.utc).isoformat(),status='CURRENT186_WITH_THREE_QUALIFIED_SERIES_ROLES_APP_READBACK_PENDING',register=rel(H/'canonical-master-register.json'),register_sha256=sha(H/'canonical-master-register.json'),workbook=rel(core),workbook_sha256=sha(core),publication_receipt=rel(H/'publication-receipt.json'))
new['latest_corrections']+=' Three White Palm/Spiral series roles use the current original group photograph with exact visual positions. Scene provenance and scale remain unverified; Primary choices and all physical/commercial fields unchanged.'
new['latest_qualified_series_review']=deepcopy(series)
new['current_individual_sculpture_list'].update(register=new['register'],register_sha256=new['register_sha256'],workbook=rel(core),workbook_sha256=sha(core),publication_receipt=new['publication_receipt'],count_summary=rel(OUT/'current-count-summary.json'),count_summary_sha256=sha(OUT/'current-count-summary.json'),review=paths['specification_review'])
new['current_comprehensive_workbook'].update(path=rel(unified),sha256=sha(unified),verification=rel(H/'independent-verification.json'),verification_sha256=sha(H/'independent-verification.json'),validation_checks_passed=qa['checks'],status='CURRENT186_WITH_THREE_QUALIFIED_SERIES_ROLES')
db=H/'gallery-projection/complete-image-platform-register.sqlite';seal=H/'gallery-projection/sealed-handoff.json'
new['current_published_gallery_projection'].update(path=rel(seal),sha256=sha(seal),register_sha256=new['register_sha256'],database_sha256=sha(db),status='CURRENT186_WITH_EXACT_THREE_SERIES_ASSOCIATIONS',source_database=manifest['sources']['source_gallery'],readers={p.name:rel(p) for p in (H/'gallery-projection').glob('*.html')})
countsdb=sqlite3.connect(db)
new['current_published_gallery_projection']['counts']={t:countsdb.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in old['current_published_gallery_projection']['counts']}
countsdb.close()
new['current_image_review_links']={'index':rel(H/'gallery-projection/index.html'),'individual_options':rel(H/'gallery-projection/product-images.html'),'current_images_and_folders':rel(H/'gallery-projection/family-images.html'),'photograph_requests':paths['photograph_review'],'working_specifications':paths['specification_review'],'current_live_catalogue':'http://127.0.0.1:8767/#specifications'}
missing=new['current_missing_picture_lists'];missing['historical_before_three_series_roles']=deepcopy(old['current_missing_picture_lists']);missing.update(status='ONE_PRIMARY_THREE_DUNE_SERIES_REPLACEMENTS_AND_STANDING_HOLDS',coverage=paths['coverage'],active_series_source_requests=3,active_individual_requests_csv=paths['active_individual_requests_csv'],active_series_requests_csv=paths['active_series_requests_csv'],technical_individual_references=paths['technical_individual_references'],held_in_situ_cases_csv=paths['held_in_situ_cases_csv'])
new['current_working_specification_checklist'].update(path=paths['field_checklist'],sha256=sha(BASE/paths['field_checklist']),review=paths['specification_review'])
new['current_review_application'].update(new_published_register_sha256=new['register_sha256'],new_published_gallery_sha256=sha(db),source_rebase_required=True)
new['next_catalogue_actions']=['Select the surviving full-view Primary for Dune Ripple1 Verdigris and Rust; exact candidate remains with the root thread.','Find qualified series replacements for Dune Ripple2 Bronze and Verdigris, Dune Ripple2 Rust and Dune Ripple1 Verdigris and Rust.','Keep27 context requirements and the prior Copper series case held.','Verify physical dimensions/depth, weight, material and fitted fixing while retaining estimates.','Reconcile later native cleanup receipts at a separately frozen inventory cut.']
targets=[BASE/'components/reviews/specification_review_progress.json',BASE/'components/checkpoint.json',BASE/'checkpoint.json',pointer];before={p:p.read_bytes() for p in targets};payloads={}
backup=H/'publication-backups';backup.mkdir(exist_ok=True)
for i,p in enumerate(targets):
    (backup/(str(i)+'-'+p.name)).write_bytes(before[p]);value=read(p)
    if p!=pointer:assert value['current_master_catalogue']==old;value['current_master_catalogue']=new
    else:value=new
    payloads[p]=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
def put(p,data):
    tmp=p.with_name(p.name+'.root-series-pending');tmp.write_bytes(data);os.replace(tmp,p)
done=[]
try:
    for p in targets:
        assert p.read_bytes()==before[p];put(p,payloads[p]);done.append(p)
    for p in targets[:-1]:assert read(p)['current_master_catalogue']==new
except BaseException:
    for p in reversed(done):put(p,before[p])
    raise
receipt={'status':'THREE_QUALIFIED_SERIES_ROLES_PUBLISHED_APP_READBACK_PENDING','pointer_sha256':sha(pointer),'register_sha256':new['register_sha256'],'gallery_sha256':sha(db),'active_options':186,'retained_options':189,'new_qualified_series_roles':3,'open_primary_selections':1,'open_series_replacements':3,'held_context_cases':27,'held_series_cases':1,'physical_commercial_platform_or_primary_changes':0,'checks':qa['checks'],'workbooks':qa['workbooks'],'root_native_or_app_writes':0}
write(H/'publication-receipt.json',receipt);write(H/'STATUS.json',receipt)
print(json.dumps({k:v for k,v in receipt.items() if k!='workbooks'}))
