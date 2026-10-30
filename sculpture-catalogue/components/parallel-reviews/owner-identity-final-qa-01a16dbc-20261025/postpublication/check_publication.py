"""Bounded exact published-byte and control binding; no workbook/gallery rerun."""
from pathlib import Path
import collections, datetime, hashlib, json
B=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
H=B/'components/reconciliation/owner-identity-decisions-master-2026-10-25'
Q=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
counts=collections.Counter(); failures=[]; inputs={}
def check(ok,category,context=''):
    counts[category]+=1
    if not ok:failures.append({'category':category,'context':str(context)})
def resolve(p):
    p=Path(p);return p if p.is_absolute() else B/p
def bind(p,h,category):
    p=resolve(p);check(p.is_file() and sha(p)==h,category,p);inputs[str(p)]=h
expected='11424f7a0b84ddff678694e803f1aa09a9824d8540281d9165eba1769587b520'
bind(B/'current-master.json',expected,'explicit_published_pointer')
bind(H/'publication-receipt.json','bf572e23869635fc89e51ced70bf5f4971bdc92f73d3db6bf5851339bb65da4c','published_receipt')
p=read(B/'current-master.json');r=read(H/'publication-receipt.json')
check(r['status']=='PASS_FOUR_OWNER_IDENTITY_DECISIONS_PUBLISHED_AND_READ_BACK' and r['current_master_pointer_sha256']==expected,'receipt_terminal_status')
check(resolve(p['publication_receipt'])==H/'publication-receipt.json','pointer_publication_receipt_route')
check(r['preceding_pointer_sha256']=='70dc1eb626e6d975b2edb2202ac0bb64a5d02eb51dcc87324697e8992df6b2b8','preceding_published_baseline')
for key,h in [('workbook','bc66ecd88480db8bc3e9274101c6fd7b49acefe7af88f0629693f349ede68511'),('register','83e9dc5ae1e576a75afbaf8acffb0f37e2885ab72170946b8cc0b3a105158f90')]:
    check(p[key+'_sha256']==r[key+'_sha256']==h and resolve(p[key])==resolve(r[key]),'exact_reviewed_data_reference',key)
    bind(p[key],h,'exact_reviewed_published_file_bytes')
snap=Q/'published-snapshots';snap.mkdir(exist_ok=False)
for path in [B/'current-master.json',H/'publication-receipt.json']+[Path(x) for x in r['controls_sha256']]:
    (snap/path.relative_to(B).as_posix().replace('/','__')).write_bytes(path.read_bytes())
for path,h in r['controls_sha256'].items():
    bind(path,h,'published_control_hash')
    c=read(path)
    check(c['current_master_catalogue']==p,'all_three_full_embedded_pointers_equal',path)
    check(c['current_master_workbook']==p['workbook'] and c['current_master_register']==p['register'],'control_scalar_routes_equal',path)
    check(c['latest_owner_identity_decision_import']==p['latest_owner_identity_decision_import'],'control_owner_import_metadata_equal',path)
qa=r['independent_qa']
bind(qa['path'],qa['sha256'],'final_4124_check_QA_readback')
bind(qa['seal_path'],qa['seal_sha256'],'final_QA_seal')
qr=read(qa['path'])
check(qr['status']=='PASS' and qr['workbook_sha256']==r['workbook_sha256'] and qr['register_sha256']==r['register_sha256'] and qa['checks_passed_total']==qr['checks_passed']==4124,'published_bytes_match_independently_checked_candidate')
imported=p['latest_owner_identity_decision_import']
check(set(r['owner_decisions'])=={x['decision_id'] for x in imported['decisions']}=={'LEGACY-FFL1-FFS2-RELIEF','WC-03-PATTERN','WC-06-PATTERN','WC-07-PATTERN'},'all_four_exact_decisions_published')
check(imported['remaining_owner_decision_ids']==[],'no_remaining_prompts_in_four_decision_workflow')
for a in imported['decisions']:
    bind(a['seal'],a['seal_sha256'],'published_exact_owner_answer_seal')
    bind(a['answer_path'],a['answer_sha256'],'published_exact_owner_answer_file')
check((r['active_options'],r['retained_options'],r['component_records'],r['working_design_groups'],r['context_holds'],r['series_holds'])==(188,189,112,110,22,1),'counts_and_photography_holds_retained')
check(r['new_selected_primary_images']==r['new_physical_or_commercial_numeric_values']==r['new_native_link_targets']==r['external_writes']==0,'no_scope_promotions')
check((r['authored_cell_changes'],r['formulas'],r['native_hyperlinks'])==(104,3407,12206),'published_workbook_delta_metadata')
check(resolve(p['current_image_review_links']['all_links']).is_file(),'published_current_catalogue_entrypoint_exists')
for path,h in inputs.items():check(sha(path)==h,'bound_inputs_unchanged_at_end',path)
result={'status':'PASS' if not failures else 'FAIL','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks_passed':sum(counts.values())-len(failures),'checks_total':sum(counts.values()),'check_categories':dict(counts),'failures':failures,
 'pointer_sha256':expected,'workbook_sha256':r['workbook_sha256'],'register_sha256':r['register_sha256'],'input_hashes':inputs,'snapshots':{str(x):sha(x) for x in snap.iterdir()},
 'scope':'Exact publication pointer/control/receipt/file hashes only. Earlier4124 candidate checks reused; no workbook or gallery rerun. B reader rebase is a subsequent metadata link update.',
 'live_calls':0,'canonical_writes':0,'owner_questions_reissued':0}
(Q/'independent-publication-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks_passed','checks_total','failures','pointer_sha256']}))
