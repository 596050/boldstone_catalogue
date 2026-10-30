import json,hashlib,copy,ast,zipfile,posixpath,re
from pathlib import Path
from datetime import datetime,timezone
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
BASE=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
C=BASE/'components/reconciliation/decowaves1-owner-design-group-master-2026-10-24'
OUT=BASE/'outputs/decowaves1-owner-design-group-master-2026-10-24'
OWN=Path(__file__).parent;OLD=OWN/'before-label-correction';ROOTOLD=C/'prior-physical-label-export'
REG='164211ed960d363e3e249142096997821ff80c63404a5ee8db6254959f9a42e5'
BOOK='d74b32a3a7a9073c0d3e62c0660dd03fbf22cb521273a0f0a323a58ea7e7fb54'
PLAN='46db738cb0ea204f041ee3f9b669bb3f8a4f70a223f68c186cd58aa6497b9ba5'
LEDGER='0b00d1a5ae0ac475ba1f2e1f74c0f825f1d750c960a82bdb19bd7da81eb92d80'
PHYSICAL='8da96ac66d4525edd6d3283239875ddb8633b12cf87c077155c0b9c800a741d4'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,d):(OWN/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
checks=[]
def check(n,ok,d=None):checks.append({'name':n,'passed':bool(ok),'details':d})
prior=load(OLD/'candidate-readback.json');priorseal=load(OLD/'sealed-handoff.json')
oldplan=load(ROOTOLD/'workbook-edit-plan.json');plan=load(C/'workbook-edit-plan.json')
frozen_paths=[C/'canonical-master-register.json',C/'master-workbook.pending',C/'workbook-edit-plan.json',C/'physical-source-audit.json',C/'report-verification.json',OUT/'physical-evidence-review.html']
initial={str(p):sha(p) for p in frozen_paths}
check('prior32PASS_retained_exact',sha(OLD/'candidate-readback.json')=='a621397a29201afb9f6f3abbef0aeb5254bb3e7d10636deeb26f1417592e94cc' and prior['status']=='PASS' and prior['checks_passed']==prior['checks_total']==32)
check('prior_workbook_recovered_matches_tested01b4_bytes',sha(ROOTOLD/'master-workbook.pending')==prior['candidate_workbook']['sha256']=='01b4a6df99f1a5a786d78bb294766451c0f1d5c0c9792dfef2a512f40c8c3c27')
check('prior_plan_recovered_matches32PASS_input',sha(ROOTOLD/'workbook-edit-plan.json')==prior['frozen_artifacts'][str(C/'workbook-edit-plan.json')])
check('frozen_final_register_workbook_plan_hashes',sha(C/'canonical-master-register.json')==REG==prior['candidate_register']['sha256'] and sha(C/'master-workbook.pending')==BOOK and sha(C/'workbook-edit-plan.json')==PLAN)
unchanged={k:v for k,v in prior['frozen_artifacts'].items() if k not in [str(C/'master-workbook.pending'),str(C/'workbook-edit-plan.json')]}
check('all_other_prior_frozen_artifacts_unchanged',all(sha(p)==v for p,v in unchanged.items()))
extra=[x for x in plan['cell_changes'] if (x['sheet'],x['cell'])==('Specifications','A3')]
retained=[x for x in plan['cell_changes'] if (x['sheet'],x['cell'])!=('Specifications','A3')]
check('exact_old9cells_plus1label_cell',len(plan['cell_changes'])==10 and len(extra)==1 and retained==oldplan['cell_changes'])
check('added_label_matches_existing188_752_4scope_no_new_evidence',len(extra)==1 and '188 options and752 physical field groups' in extra[0]['value'] and '4 water-build comparator-only fields' in extra[0]['value'] and 'no new measured or inspected evidence' in extra[0]['value'])
check('old3row_heights_and_all_planned_links_and_formulas_retained',plan['row_heights']==oldplan['row_heights'] and len(plan['row_heights'])==3 and plan['hyperlinks']==oldplan['hyperlinks'] and plan['formula_changes']==oldplan['formula_changes'] and plan['native_link_changes']==oldplan['native_link_changes']==[])
N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
helper_path=OLD/'verify_decowaves1.py'
expected_helper=next(x['sha256'] for x in priorseal['files'] if x['path'].endswith('/verify_decowaves1.py'))
check('independent_readonly_xml_helper_unchanged',sha(helper_path)==expected_helper)
node=next(x for x in ast.parse(helper_path.read_text()).body if isinstance(x,ast.FunctionDef) and x.name=='read_xlsx')
exec(compile(ast.Module(body=[node],type_ignores=[]),'preserved_independent_readonly_xlsx_reader','exec'))
wb0,heights0=read_xlsx(ROOTOLD/'master-workbook.pending');wb1,heights1=read_xlsx(C/'master-workbook.pending')
delta=[]
for sheet in wb1:
 for address in wb0[sheet].keys()|wb1[sheet].keys():
  if wb0[sheet].get(address)!=wb1[sheet].get(address):delta.append({'sheet':sheet,'cell':address,'before':wb0[sheet].get(address),'after':wb1[sheet].get(address)})
expected=copy.deepcopy(wb0)
expected['Specifications']['A3']['value']=extra[0]['value']
check('all28sheets_semantically_identical_except_single_label',list(wb0)==list(wb1) and len(wb1)==28 and expected==wb1 and len(delta)==1,delta)
check('row_heights_identical_to_prior_passed_candidate',heights0==heights1)
check('formula_and_all_native_external_local_hyperlinks_unchanged_from_prior_candidate',all(c.get('formula')==wb1[s][a].get('formula') and c.get('hyperlink')==wb1[s][a].get('hyperlink') for s,cells in wb0.items() for a,c in cells.items()))
ledger=load(C/'physical-source-audit.json')
check('existing_physical_ledger_exact_bytes_unchanged',sha(C/'physical-source-audit.json')==LEDGER)
check('ledger_scope_is188options752fields4comparator_no_new_measurements',len(ledger['options'])==ledger['summary']['active_options_reviewed']==188 and len(ledger['field_rows'])==ledger['summary']['physical_field_groups_reviewed']==752 and ledger['summary']['new_qualified_comparator_field_groups_reviewed']==4 and ledger['summary']['new_independent_physical_source_assertions']==ledger['summary']['new_physical_verifications']==ledger['summary']['rows_with_entered_measurements']==0)
oldprefix=str(BASE/'outputs/current-primary-navigation-health-master-2026-10-24')+'/'
newprefix=str(OUT)+'/'
def norm(s):return s.replace(oldprefix,'{current-release}/').replace(newprefix,'{current-release}/')
class Page(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.cards={};self.cur=None;self.opening=[];self.links=[];self.instyle=False
 def handle_starttag(self,t,attrs):
  d=dict(attrs)
  if t=='style':self.instyle=True
  if t=='article':self.cur=d.get('id');self.cards[self.cur]=[]
  if self.cur:self.cards[self.cur].append(['start',t,[(k,norm(v or '')) for k,v in attrs]])
  if t=='a':self.links.append(d.get('href'))
 def handle_endtag(self,t):
  if self.cur:self.cards[self.cur].append(['end',t])
  if t=='article':self.cur=None
  if t=='style':self.instyle=False
 def handle_data(self,d):
  if self.cur:self.cards[self.cur].append(['text',norm(d)])
  elif not self.instyle:self.opening.append(d)
page0=Page();page1=Page()
page0.feed((BASE/'outputs/current-primary-navigation-health-master-2026-10-24/physical-evidence-review.html').read_text())
page1.feed((OUT/'physical-evidence-review.html').read_text())
opening=' '.join(page1.opening)
check('final_physical_report_exact_frozen_hash',sha(OUT/'physical-evidence-review.html')==PHYSICAL)
check('all188_physical_cards_unchanged_except_release_navigation',len(page0.cards)==len(page1.cards)==188 and page0.cards==page1.cards,{'prior_cards':len(page0.cards),'final_cards':len(page1.cards),'changed_ids':[k for k,v in page1.cards.items() if page0.cards.get(k)!=v]})
check('report_opening_correct_scope_and_qualifications',all(s in opening for s in ['188 options and752 physical field groups','4 comparator-only water-build fields','no independent physical source assertions','188-row measurement input is empty','No option gains a new physical verification']) and not any(s in opening for s in ['All748','187-row','187 active options']))
proj=load(C/'working-design-group-projection.json')
check('111group_number1_only_projection_unchanged',proj['grouped_working_design_identity_count']==111 and proj['retained_component_identity_record_count']==112 and proj['active_individual_finish_option_count']==188 and proj['one_equivalence_group']==['BC-DECO-1','BC-FDW-1'])
check('final_report_verification_hash_matches_freeze',sha(C/'report-verification.json')=='8f6f04bdf471e39f55d10157c2b60b0c5fdc943cff38e1bc61f0e1de65d9f5cf')
check('frozen_artifacts_stable_through_addendum',all(sha(p)==v for p,v in initial.items()))
result={'status':'PASS' if all(x['passed'] for x in checks) else 'FAIL','schema':'boldstone.decowaves1.final-label-qa-addendum.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),'checks':checks,'prior_independent_qa':{'path':str(OLD/'candidate-readback.json'),'sha256':sha(OLD/'candidate-readback.json'),'checks_passed':32,'status':'PASS'},'candidate_register':{'path':str(C/'canonical-master-register.json'),'sha256':sha(C/'canonical-master-register.json')},'candidate_workbook':{'path':str(C/'master-workbook.pending'),'sha256':sha(C/'master-workbook.pending')},'frozen_artifacts':{**unchanged,**initial},'recovered_prior_workbook':{'path':str(ROOTOLD/'master-workbook.pending'),'sha256':sha(ROOTOLD/'master-workbook.pending')},'scope':'Retain32prior independent checks; exact final one-label workbook delta and physical-report scope correction only. No source/specification/native-image changes or physical-verification upgrade.'}
save('final-label-addendum.json',result)
seal={'status':result['status'],'schema':'boldstone.decowaves1.final-independent-qa-seal.v1','recorded_utc':result['recorded_utc'],'candidate_register_sha256':result['candidate_register']['sha256'],'candidate_workbook_sha256':result['candidate_workbook']['sha256'],'prior_independent_checks':32,'addendum_checks':len(checks),'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in [OWN/'verify_final_label_addendum.py',OWN/'final-label-addendum.json',OLD/'candidate-readback.json',OLD/'sealed-handoff.json',OLD/'verify_decowaves1.py']],'shared_or_native_writes':0}
save('sealed-final-handoff.json',seal)
print(json.dumps({'status':result['status'],'passed':result['checks_passed'],'total':result['checks_total'],'failed':[x for x in checks if not x['passed']],'qa_path':str(OWN/'final-label-addendum.json'),'qa_sha256':sha(OWN/'final-label-addendum.json'),'seal_sha256':sha(OWN/'sealed-final-handoff.json')},ensure_ascii=False))
