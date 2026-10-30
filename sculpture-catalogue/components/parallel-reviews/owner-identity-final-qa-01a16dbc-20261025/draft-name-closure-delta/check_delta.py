"""Nine-cell addendum only, reusing the sealed final identity and95/8 audit."""
from pathlib import Path
import ast, collections, copy, datetime, decimal, hashlib, json, posixpath, zipfile
from xml.etree import ElementTree as E
Q=Path(__file__).resolve().parent; P=Q.parent
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=read(Q/'final-inputs.json'); checks=collections.Counter(); failures=[]
def check(ok,category,context=''):
    checks[category]+=1
    if not ok:failures.append({'category':category,'context':str(context)[:1000]})

seal=read(P/'sealed-final-candidate-qa.json')
for p,h in seal['files'].items():check(sha(p)==h,'original_3997_check_QA_artifact_unchanged',p)
check(sha(P/'sealed-final-candidate-qa.json')=='4d679a794d9a430d71dbee82ee5e30391ab574cf868c573a4abf5d4f62648b4c','prior_full_QA_seal')
check(sha(Q/'master-workbook.pending')==manifest['final_workbook_sha256'],'explicit_final_workbook_hash')
for name, item in manifest['source_files'].items():
    check(sha(item['source'])==item['sha256'] and sha(Q/name)==item['sha256'],'frozen_final_addendum_input_hash',name)
oldplan=read(P/'frozen-inputs/workbook-edit-plan.json'); plan=read(Q/'workbook-edit-plan.json')
key=lambda x:(x['sheet'],x['cell'])
old_changes={key(x):x for x in oldplan['cell_changes']}; new_changes={key(x):x for x in plan['cell_changes']}
extra={k:v for k,v in new_changes.items() if k not in old_changes}
check(len(old_changes)==95 and len(new_changes)==104 and len(extra)==9,'exact_95_plus_9_authored_scope')
check(set(extra)=={('Draft Listings',c+str(r)) for c in ['M','N','O'] for r in [103,104,105]},'exact_nine_draft_cells')
check(all(new_changes.get(k)==v for k,v in old_changes.items()),'all_prior_95_planned_changes_identical')
check(plan['calculated_value_changes']==oldplan['calculated_value_changes'] and len(plan['calculated_value_changes'])==8,'all_prior_8_calculated_changes_identical')

# Reuse only the already verified, hash-bound native XML reader functions.
# Do not execute the earlier audit or rewrite its sealed reports.
tree=ast.parse((P/'check_candidate.py').read_text())
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'canon','relationship_semantics','value','workbook'}]
env={'E':E,'collections':collections,'copy':copy,'zipfile':zipfile,'decimal':decimal,'posixpath':posixpath,
     'NS':'{http://schemas.openxmlformats.org/spreadsheetml/2006/main}',
     'REL':'{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'}
exec(compile(ast.Module(body=functions,type_ignores=[]),'sealed-native-reader-functions','exec'),env)
book=env['workbook']; canon=env['canon']; rels=env['relationship_semantics']
a=book(P/'frozen-inputs/master-workbook.pending'); b=book(Q/'master-workbook.pending')
changed={k for k in set(a[3])|set(b[3]) if a[3].get(k)!=b[3].get(k)}
check(changed==set(extra),'saved_workbook_only_nine_value_deltas',sorted(changed-set(extra)))
for k,x in extra.items():check(a[3].get(k)==x['before'] and b[3].get(k)==x['value'] and k not in b[4],'exact_nine_authored_saved_values',k)
check(a[4]==b[4] and len(b[4])==3407,'all_formula_text_and_attributes_unchanged')
check(a[5]==b[5],'all_cell_styles_unchanged')
check(a[6]==b[6],'all_layout_and_native_structures_unchanged')
check(a[7]==b[7] and sum(sum(x.values()) for x in b[7].values())==12206,'all_12206_native_hyperlink_destinations_unchanged')
check(list(a[2])==list(b[2]) and len(b[2])==28,'all_28_sheets_order_and_names_unchanged')
check(set(a[0].namelist())==set(b[0].namelist()),'native_package_part_set_unchanged')
display_changes={k for k in set(a[8])|set(b[8]) if a[8].get(k)!=b[8].get(k)}
check(display_changes<=set(extra),'only_planned_addendum_display_labels_may_change',display_changes)
for k in display_changes:check(a[8].get(k)==a[3].get(k) and b[8].get(k)==b[3].get(k),'addendum_display_label_matches_planned_value',k)
for part in a[0].namelist():
    if a[0].read(part)==b[0].read(part) or part in a[2].values():continue
    if part.endswith('.rels'):
        check(collections.Counter(rels(a[0],part).values())==collections.Counter(rels(b[0],part).values()),'regenerated_relationship_IDs_resolve_to_same_destinations',part)
    elif part=='xl/workbook.xml':
        check(canon(E.fromstring(a[0].read(part)),rels(a[0],'xl/_rels/workbook.xml.rels'))==canon(E.fromstring(b[0].read(part)),rels(b[0],'xl/_rels/workbook.xml.rels')),'workbook_structure_unchanged',part)
    elif part.endswith('.xml'):
        check(canon(E.fromstring(a[0].read(part)))==canon(E.fromstring(b[0].read(part))),'other_changed_XML_semantics_unchanged',part)
    else:check(False,'unexpected_non_XML_change',part)

check(manifest['register_sha256']=='83e9dc5ae1e576a75afbaf8acffb0f37e2885ab72170946b8cc0b3a105158f90','register_3997_check_QA_unchanged')
check(sha(manifest['register_path'])==manifest['register_sha256'],'current_register_matches_sealed_QA')
artifact=read(Q/'artifact-delta-readback.json')
check(artifact['status']=='PASS' and artifact['additional_value_reads']==9 and artifact['prior_95_value_reads_repeated'] is False and artifact['candidate_bytes_unchanged'] is True,'nine_independent_artifact_reads_only')
check(sha(artifact['preview']['path'])==artifact['preview']['sha256'],'changed_draft_range_preview_hash')
for x in artifact['results']:
    check('which18pattern' not in x['actual'].replace(' ','').lower() and 'whichofthe18' not in x['actual'].replace(' ','').lower(),'no_repeat_old_18_pattern_question',x['cell'])
for p,h in read(P/'frozen-input-manifest.json')['protected_published_files'].items():check(sha(p)==h,'published_baseline_unchanged_during_final_delta',p)
for name,item in manifest['source_files'].items():check(sha(item['source'])==item['sha256'],'final_inputs_unchanged_at_end',name)
result={'status':'PASS' if not failures else 'FAIL','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'final_workbook_sha256':manifest['final_workbook_sha256'],'final_register_sha256':manifest['register_sha256'],
 'workbook_sha256':manifest['final_workbook_sha256'],'register_sha256':manifest['register_sha256'],
 'prior_QA_checks_reused':3997,'delta_checks_passed':sum(checks.values())-len(failures),'checks_passed':3997+sum(checks.values())-len(failures),'check_categories':dict(checks),'failures':failures,
 'authored_cell_changes':104,'calculated_cache_changes':8,'additional_artifact_value_reads':9,'prior_95_artifact_value_reads_repeated':False,'new_draft_cells':sorted([k[1] for k in extra]),
 'native_Excel_runtime_evaluated':False,'full_gallery_review_repeated':False,'live_calls':0,'canonical_writes':0,'owner_questions_reissued':0}
(Q/'independent-delta-readback.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','checks_passed','delta_checks_passed','failures','final_workbook_sha256']}))
