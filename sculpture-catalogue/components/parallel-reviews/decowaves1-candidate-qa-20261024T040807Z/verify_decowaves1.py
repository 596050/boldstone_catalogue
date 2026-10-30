import json, csv, copy, hashlib, zipfile, posixpath
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
BASE=Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
C=BASE/'components/reconciliation/decowaves1-owner-design-group-master-2026-10-24'
OUT=BASE/'outputs/decowaves1-owner-design-group-master-2026-10-24'
OWN=Path(__file__).parent
REG='164211ed960d363e3e249142096997821ff80c63404a5ee8db6254959f9a42e5'
BOOK='01b4a6df99f1a5a786d78bb294766451c0f1d5c0c9792dfef2a512f40c8c3c27'
SEAL='e7cc9132d00e708a766a0d07114cc78c32ca36f4b8398adb6d02d8fa62147e05'
PAIR={'BSI-612EF4DBB555','BSI-8CC6C8AABCB7'}
COMP={'BC-DECO-1','BC-FDW-1'}
NUMBER2={'BSI-FE830AE502C3','BSI-837E9B0B3B36'}
TERRA='BSI-BFB0D3D29852'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,d):(OWN/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def get(o,p):
 for k in p:o=o[k]
 return o
checks=[]
def check(n,ok,detail=None):checks.append({'name':n,'passed':bool(ok),'details':detail})
m=load(C/'input-manifest.json');old=load(m['master_register']['snapshot']);new=load(C/'canonical-master-register.json')
edge=load(C/'owner-design-edge.json');proj=load(C/'working-design-group-projection.json')
plan=load(C/'workbook-edit-plan.json');changes=load(C/'authorized-current-field-changes.json')
scope=load(m['owner_evidence_0']['snapshot']);trans=load(m['owner_evidence_2']['snapshot']);supp=load(m['owner_evidence_3']['snapshot'])
oldops={x['product_id']:x for x in old['options']};newops={x['product_id']:x for x in new['options']}
frozen=[C/'canonical-master-register.json',C/'master-workbook.pending',C/'authorized-current-field-changes.json',C/'workbook-edit-plan.json',C/'owner-design-edge.json',C/'working-design-group-projection.json',OUT/'Owner_Decowaves1_Design_Equivalence_2.csv',OUT/'Current_Working_Design_Groups_111.csv',OUT/'decowaves1-owner-design-equivalence.html']
initial={str(p):sha(p) for p in frozen}
check('exact_frozen_candidate_hashes',sha(C/'canonical-master-register.json')==REG and sha(C/'master-workbook.pending')==BOOK)
check('baseline_matches_published_navigation_release',sha(m['master_register']['snapshot'])==m['master_register']['sha256']=='932ffe756c75528ae4ff9d357de5ce817afccc330694a853064f55dbe58ab8c4' and sha(m['master_workbook']['snapshot'])==m['master_workbook']['sha256']=='14db11f6cf634a388c32c71dfdfe2d425d3621572e7937470baaff9f84503bf5')
check('owner_seal_and_evidence_files_match',sha(m['owner_evidence_0']['snapshot'])==SEAL and all(sha(x['path'])==x['sha256'] for x in scope['files']) and all(sha(v['snapshot'])==v['sha256'] for k,v in m.items() if k.startswith('owner_evidence_')))
transcript_reads=[]
with Path(trans['source_path']).open('rb') as fh:
 for record in trans['records']:
  fh.seek(record['byte_offset']);raw=fh.read(record['byte_length']);actual=json.loads(raw)
  transcript_reads.append({'kind':record['kind'],'raw_line_sha256':hashlib.sha256(raw).hexdigest(),'expected_sha256':record['raw_line_sha256'],'timestamp':actual['timestamp'],'same_record':actual==record['source_record']})
check('exact_two_transcript_lines_verified_by_offset_and_hash',len(transcript_reads)==2 and all(x['same_record'] and x['raw_line_sha256']==x['expected_sha256'] for x in transcript_reads))
q=next(x for x in trans['records'] if x['kind']=='presented_question');a=next(x for x in trans['records'] if x['kind']=='owner_yes')
check('question_and_owner_answer_clocks_exact',q['timestamp']==supp['owner_question_timestamp']=='2026-10-24T02:37:00.546Z' and a['timestamp']==supp['owner_answer_timestamp']==edge['owner_answer_timestamp']=='2026-10-24T03:55:40.011Z' and q['timestamp']<a['timestamp'])
check('answer_is_exact_owner_Yes_for_displayed_number1_pair',a['source_record']['payload']['role']=='user' and a['text_verbatim']==supp['owner_answer_verbatim']==edge['owner_answer_verbatim']=='Yes' and all(oldops[oid]['image_url'] in q['text_verbatim'] and oldops[oid]['folder_url'] in q['text_verbatim'] for oid in PAIR) and all(oldops[oid]['image_url'] not in q['text_verbatim'] for oid in NUMBER2|{TERRA}))
expected=copy.deepcopy(old)
for x in changes:
 assert x['group']=='register'
 parent=get(expected,x['path'][:-1]);k=x['path'][-1]
 if x['before_exists']:assert parent[k]==x['before'],x['path']
 else:assert k not in parent,x['path']
 parent[k]=copy.deepcopy(x['current'])
check('whole_register_has_only_21_logged_changes',len(changes)==21 and expected==new)
cleanops=copy.deepcopy(newops)
for oid in PAIR:cleanops[oid].pop('current_owner_design_equivalence',None)
check('all_189_option_objects_preserved_except_exact_pair_edge',len(newops)==189 and cleanops==oldops and [x['product_id'] for x in new['options']]==[x['product_id'] for x in old['options']])
check('terracotta_and_both_number2_complete_records_unchanged',all(newops[oid]==oldops[oid] for oid in NUMBER2|{TERRA}))
oldcomps={x['component_id']:x for x in old['components']};cleancomps={x['component_id']:copy.deepcopy(x) for x in new['components']}
for cid in COMP:cleancomps[cid].pop('current_owner_design_group',None);cleancomps[cid]['scope_note']=oldcomps[cid]['scope_note']
check('all112_component_ids_memberships_and_fields_retained',len(cleancomps)==112 and cleancomps==oldcomps and [x['component_id'] for x in new['components']]==[x['component_id'] for x in old['components']])
check('exact_additive_pair_edge_only',new['current_owner_design_equivalence_edges']==[edge] and set(edge['owner_confirmed_option_ids'])==PAIR and set(edge['component_ids'])==set(edge['retained_component_ids'])==COMP and edge['source_evidence']['sha256']==SEAL and edge['no_physical_mould_cast_or_specification_transfer'] and edge['number2_confirmed'] is False and edge['terracotta_owner_photo_approval'] is False)
check('pair_edge_references_current_ids_and_links',len(edge['exact_pair_references'])==2 and all(all(r[k]==oldops[r['product_id']][k] for k in ['name','canonical_design_id','canonical_component_id','file_id','folder_id','image_url','folder_url']) for r in edge['exact_pair_references']))
preserve_keys=['source_offer_edges','source_platform_offer_coverage','current_authenticated_squarespace_inventory_observation','latest_authenticated_source_observation_import','listing_resolution_native_action_drafts','current_listing_resolution','current_listing_resolution_details','current_primary_navigation_health']
check('all_platform_sources_history_and_native_health_preserved',all(old[k]==new[k] for k in preserve_keys))
check('physical_source_and_photo_review_payloads_byte_identical',all(sha(C/filename)==sha(m[key]['snapshot']) for filename,key in [('physical-source-audit.json','physical_audit'),('photo-review-queue.json','report_reviews'),('photo-source-review.json','photo_source'),('guided-owner-review-state.json','review_state'),('pending-followups.json','pending')]))
check('native_health_file_byte_identical',sha(C/'current-primary-navigation-health.json')==sha(BASE/'components/reconciliation/current-primary-navigation-health-master-2026-10-24/current-primary-navigation-health.json'))
expected_map={cid:('BC-DECO-1' if cid=='BC-FDW-1' else cid) for cid in oldcomps}
check('group_projection_maps_only_approved_two_components',proj['component_id_to_working_group']==expected_map and len(set(expected_map.values()))==111 and new['current_working_design_group_projection']==proj)
groups={x['working_design_group_id']:x for x in proj['groups']}
check('112component_records_form111groups_no_disappearing_ids',len(groups)==111 and Counter(cid for g in groups.values() for cid in g['retained_component_ids'])==Counter(oldcomps.keys()))
groupfails=[]
for gid,g in groups.items():
 cids={cid for cid,target in expected_map.items() if target==gid}
 options={oid for cid in cids for oid in oldcomps[cid]['option_ids']}
 if set(g['retained_component_ids'])!=cids or set(g['active_option_ids'])!=options:groupfails.append(gid)
 if set(g['owner_directly_confirmed_option_ids'])!=(PAIR if gid=='BC-DECO-1' else set()):groupfails.append(gid+':owner_scope')
check('projection_preserves_existing_membership_and_exact_owner_pair',not groupfails,groupfails)
check('terracotta_existing_group_membership_not_new_owner_confirmation',TERRA in groups['BC-DECO-1']['active_option_ids'] and TERRA not in groups['BC-DECO-1']['owner_directly_confirmed_option_ids'] and 'without a new Terracotta' in groups['BC-DECO-1']['grouping_basis'])
check('counts_separate_working_groups_from_retained_ids_and_stock',proj['retained_component_identity_record_count']==112 and proj['grouped_working_design_identity_count']==111 and proj['active_individual_finish_option_count']==188 and proj['retained_option_record_count']==189 and proj['whole_library_unique_design_count'] is None and 'not a whole-library' in proj['scope'])
def csvread(name):
 with (OUT/name).open(encoding='utf-8-sig',newline='') as fh:return list(csv.DictReader(fh))
pairs=csvread('Owner_Decowaves1_Design_Equivalence_2.csv');grows=csvread('Current_Working_Design_Groups_111.csv')
check('pair_csv_exact2_links_ids_clocks_no_transfer',len(pairs)==2 and {r['option_id'] for r in pairs}==PAIR and all(all(r[k]==newops[r['option_id']][k] for k in ['name','image_url','folder_url','file_id','folder_id']) and r['owner_answer_utc']==a['timestamp'] and r['specifications_transferred']==r['number2_confirmed']=='False' and r['component_id_retained']==newops[r['option_id']]['canonical_component_id'] for r in pairs))
gfail=[]
for r in grows:
 g=groups[r['working_design_group_id']]
 for k in ['retained_component_ids','active_option_ids','owner_directly_confirmed_option_ids']:
  got=[] if not r[k] else r[k].split(' | ')
  if got!=g[k]:gfail.append((r['working_design_group_id'],k))
check('111group_csv_exact_membership_and_owner_scope',len(grows)==111 and {r['working_design_group_id'] for r in grows}==set(groups) and not gfail,gfail)
class HTML(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.text=[];self.articles={};self.cur=None
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='a':self.links.append(a.get('href'))
  if t=='article':self.cur=a.get('id');self.articles[self.cur]=[]
 def handle_data(self,d):
  self.text.append(d)
  if self.cur:self.articles[self.cur].append(d)
 def handle_endtag(self,t):
  if t=='article':self.cur=None
h=HTML();h.feed((OUT/'decowaves1-owner-design-equivalence.html').read_text());text=' '.join(h.text)
check('html_exact_pair_image_folder_links',all(newops[oid][k] in h.links for oid in PAIR for k in ['image_url','folder_url']) and all(newops[oid]['image_url'] not in h.links for oid in NUMBER2|{TERRA}))
check('html_qualified_counts_scope_and_both_csv_downloads',all(s in text for s in ['111 working','112 retained','188 active','Number2 remains unanswered','owner did not newly review its photograph','whole-library unique-design total remains unknown']) and all(n in h.links for n in ['Current_Working_Design_Groups_111.csv','Owner_Decowaves1_Design_Equivalence_2.csv']))
# The six accepted displays are compared literally, including estimate and conflict labels.
check('html_retains_all12_working_specification_displays',all(v['display'] in text for oid in PAIR for v in newops[oid]['master_fields'].values()))

N={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def read_xlsx(path):
 with zipfile.ZipFile(path) as z:
  ss=[]
  if 'xl/sharedStrings.xml' in z.namelist():ss=[''.join(t.text or '' for t in si.findall('.//s:t',N)) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',N)]
  wr={x.attrib['Id']:x.attrib['Target'] for x in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
  result={};heights={}
  for sh in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',N):
   name=sh.attrib['name'];t=wr[sh.attrib['{'+N['r']+'}id']];p=t.lstrip('/') if t.startswith('/') else posixpath.normpath('xl/'+t);root=ET.fromstring(z.read(p));cells={}
   for c in root.findall('.//s:sheetData/s:row/s:c',N):
    v=c.findtext('s:v',None,N);typ=c.attrib.get('t')
    if typ=='s':v=ss[int(v)] if v is not None else None
    elif typ=='inlineStr':v=''.join(x.text or '' for x in c.findall('.//s:t',N))
    f=c.findtext('s:f',None,N)
    if v is not None or f is not None:cells[c.attrib['r']]={'value':None if f is not None else v,'formula':f}
   rp=posixpath.dirname(p)+'/_rels/'+posixpath.basename(p)+'.rels'
   rels={x.attrib['Id']:x.attrib.get('Target') for x in ET.fromstring(z.read(rp))} if rp in z.namelist() else {}
   for h in root.findall('s:hyperlinks/s:hyperlink',N):cells.setdefault(h.attrib['ref'],{'value':None,'formula':None})['hyperlink']=rels.get(h.attrib.get('{'+N['r']+'}id')) or h.attrib.get('location')
   result[name]=cells;heights[name]={int(r.attrib['r']):float(r.attrib['ht']) for r in root.findall('s:sheetData/s:row',N) if 'ht' in r.attrib}
  return result,heights
w0,rh0=read_xlsx(m['master_workbook']['snapshot']);w1,rh1=read_xlsx(C/'master-workbook.pending')
check('28workbook_sheets_order_retained',list(w0)==list(w1) and len(w1)==28)
expected_w=copy.deepcopy(w0);planfails=[]
for x in plan['cell_changes']:
 cell=expected_w[x['sheet']][x['cell']]
 if cell['value']!=str(x['before']):planfails.append((x['sheet'],x['cell']))
 cell['value']=str(x['value'])
oldprefix=str(BASE/'outputs/current-primary-navigation-health-master-2026-10-24')+'/'
newprefix=str(OUT)+'/'
planned_links={(x['sheet'],x['cell']):x['target'] for x in plan['hyperlinks']}
localchanges=[];linkscopefails=[]
for s,cells in w0.items():
 for addr,cell in cells.items():
  before=cell.get('hyperlink');after=w1[s].get(addr,{}).get('hyperlink')
  if before==after:continue
  rebase=isinstance(before,str) and before.startswith(oldprefix) and after==newprefix+before[len(oldprefix):]
  new_review=(s,addr)==('Master Catalogue','A3') and before==oldprefix+'current-primary-navigation-health.html' and after==newprefix+'decowaves1-owner-design-equivalence.html'
  valid=(rebase or new_review) and planned_links.get((s,addr))==after and Path(after.split('#',1)[0]).is_file()
  localchanges.append({'sheet':s,'cell':addr,'before':before,'after':after,'same_file_and_fragment_rebase':rebase,'planned_new_review':new_review,'valid':valid})
  if valid:expected_w[s][addr]['hyperlink']=after
  else:linkscopefails.append({'sheet':s,'cell':addr,'before':before,'after':after})
check('exact69local_report_rebases_and1declared_review_link',len(localchanges)==70 and sum(x['same_file_and_fragment_rebase'] for x in localchanges)==69 and sum(x['planned_new_review'] for x in localchanges)==1 and not linkscopefails,linkscopefails)
check('exact9planned_values_plus_declared_local_links_only',len(plan['cell_changes'])==9 and not planfails and expected_w==w1,{'before_value_mismatches':planfails,'unexpected_sheets':[s for s in w1 if expected_w[s]!=w1[s]]})
expected_rh=copy.deepcopy(rh0)
for x in plan['row_heights']:expected_rh[x['sheet']][x['row']]=float(x['height'])
check('exact3row_height_adjustments_only',len(plan['row_heights'])==3 and expected_rh==rh1)
f0={(s,a):c['formula'] for s,cells in w0.items() for a,c in cells.items() if c['formula'] is not None}
f1={(s,a):c['formula'] for s,cells in w1.items() for a,c in cells.items() if c['formula'] is not None}
l0={(s,a):c['hyperlink'] for s,cells in w0.items() for a,c in cells.items() if c.get('hyperlink')}
l1={(s,a):c['hyperlink'] for s,cells in w1.items() for a,c in cells.items() if c.get('hyperlink')}
expected_links=dict(l0)
for change in localchanges:
 if change['valid']:expected_links[(change['sheet'],change['cell'])]=change['after']
check('all3407formulas_and_all_external_native_links_unchanged',f0==f1 and len(f1)==3407 and expected_links==l1 and len(l1)==12206,{'formula_count':len(f1),'hyperlink_count':len(l1),'declared_local_report_link_changes':len(localchanges)})
check('no_native_link_plan_or_new_sheets',not plan['native_link_changes'] and not plan['new_sheets'])
check('candidate_bytes_stable_through_readback',all(sha(p)==v for p,v in initial.items()))
result={'status':'PASS' if all(x['passed'] for x in checks) else 'FAIL','schema':'boldstone.independent.decowaves1-owner-design-group-qa.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),'checks':checks,'candidate_register':{'path':str(C/'canonical-master-register.json'),'sha256':sha(C/'canonical-master-register.json')},'candidate_workbook':{'path':str(C/'master-workbook.pending'),'sha256':sha(C/'master-workbook.pending')},'owner_seal_sha256':SEAL,'transcript_line_readbacks':transcript_reads,'frozen_artifacts':initial,'scope':'Exact number1 owner decision only. Independent JSON, bounded transcript-line readback, CSV/HTML and XLSX XML semantic comparison. No new source/native calls, shared writes, image-role review or physical claims.'}
save('candidate-readback.json',result)
seal={'status':result['status'],'schema':'boldstone.decowaves1-independent-qa-seal.v1','recorded_utc':result['recorded_utc'],'candidate_register_sha256':result['candidate_register']['sha256'],'candidate_workbook_sha256':result['candidate_workbook']['sha256'],'files':[{'path':str(OWN/n),'sha256':sha(OWN/n),'bytes':(OWN/n).stat().st_size} for n in ['verify_decowaves1.py','candidate-readback.json']],'shared_or_native_writes':0}
save('sealed-handoff.json',seal)
print(json.dumps({'status':result['status'],'checks_passed':result['checks_passed'],'checks_total':result['checks_total'],'failed':[x for x in checks if not x['passed']],'qa_path':str(OWN/'candidate-readback.json'),'qa_sha256':sha(OWN/'candidate-readback.json'),'seal_sha256':sha(OWN/'sealed-handoff.json')},ensure_ascii=False))
