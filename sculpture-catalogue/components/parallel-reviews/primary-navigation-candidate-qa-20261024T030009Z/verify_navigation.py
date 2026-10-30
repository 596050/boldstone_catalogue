import json, csv, hashlib, copy, zipfile, posixpath
from pathlib import Path
from datetime import datetime, timezone
from html.parser import HTMLParser
from xml.etree import ElementTree as ET
BASE=Path('/Users/tprice/Documents/boldstone')
C=BASE/'sculpture-catalogue/components/reconciliation/current-primary-navigation-health-master-2026-10-24'
OUT=BASE/'sculpture-catalogue/outputs/current-primary-navigation-health-master-2026-10-24'
OWN=Path(__file__).parent
EXPECTED_REGISTER='932ffe756c75528ae4ff9d357de5ce817afccc330694a853064f55dbe58ab8c4'
EXPECTED_WORKBOOK='14db11f6cf634a388c32c71dfdfe2d425d3621572e7937470baaff9f84503bf5'
EXPECTED_PLAN='eb40a068237071d9df46beae8b47f2b4b3f4ee0dc49d2b08673fb90d86072e00'
EXPECTED_CHANGES='5ead57c8a405df64fefaecc531825be4ca948e9006e9f8e0b1eee676d9157dd0'
def load(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x): (OWN/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
checks=[]
def check(name,ok,details=None):
 checks.append({'name':name,'passed':bool(ok),'details':details})
 return bool(ok)
def pathget(o,p):
 for key in p:o=o[key]
 return o
def patch(o,changes):
 for x in changes:
  parent=pathget(o,x['path'][:-1]); key=x['path'][-1]
  if x['before_exists']: assert parent[key]==x['before'],x['path']
  else: assert key not in parent,x['path']
  parent[key]=copy.deepcopy(x['current'])
 return o
manifest=load(C/'input-manifest.json')
changes=load(C/'authorized-current-field-changes.json')
source=load(manifest['navigation_seal']['snapshot'])
source_files={Path(x['path']).name:Path(x['path']) for x in source['files']}
nav=load(source_files['navigation-review.json'])
proposal=load(source_files['correction-proposal.json'])
health=load(C/'current-primary-navigation-health.json')
old=load(manifest['master_register']['snapshot'])
new=load(C/'canonical-master-register.json')
plan=load(C/'workbook-edit-plan.json')
initial_hashes={str(p):sha(p) for p in [C/'canonical-master-register.json',C/'master-workbook.pending',C/'authorized-current-field-changes.json',C/'photo-review-queue.json',C/'current-primary-navigation-health.json',OUT/'Current_Primary_Navigation_48.csv',OUT/'current-primary-navigation-health.html']}
check('candidate_exact_frozen_register',sha(C/'canonical-master-register.json')==EXPECTED_REGISTER)
check('candidate_exact_frozen_workbook',sha(C/'master-workbook.pending')==EXPECTED_WORKBOOK)
check('candidate_exact_final_workbook_plan',sha(C/'workbook-edit-plan.json')==EXPECTED_PLAN)
check('final_authorized_changes_hash',sha(C/'authorized-current-field-changes.json')==EXPECTED_CHANGES)
check('baseline_register_identity',sha(manifest['master_register']['snapshot'])==manifest['master_register']['sha256']=='06acd3dc3abb1146d79845dc5c895ee164f0c87ab97800fbe4d0e04e5be88f96')
check('source_seal_and_all_evidence_bytes_unchanged',sha(manifest['navigation_seal']['snapshot'])==manifest['navigation_seal']['sha256']=='09928cf3dbed6ddc3efea7164bf978508ca7e6a7633bb42baa209274220e214d' and all(sha(x['path'])==x['sha256'] for x in source['files']))
group_files={'register':('master_register','canonical-master-register.json'),'audit':('audit','image-coverage-current.json'),'native_map':('native_map','current-native-reference-map.json'),'assets':('report_assets','current-assets.json')}
for group,(key,file) in group_files.items():
 expected=patch(load(manifest[key]['snapshot']),[x for x in changes if x['group']==group])
 check(group+'_only_declared_field_changes',expected==load(C/file))
oldops={o['product_id']:o for o in old['options']};newops={o['product_id']:o for o in new['options']}
check('all_189_option_ids_and_order_preserved',[o['product_id'] for o in old['options']]==[o['product_id'] for o in new['options']] and len(new['options'])==189)
mwc='BSI-70C7029C1DB1';bad={x['product_id'] for x in proposal['unavailable_primary_annotations']}
bad_expected={'BSI-D5A939264C82','BSI-65520F070145'}
check('only_two_expected_held_options_annotated',bad==bad_expected and {o['product_id'] for o in new['options'] if 'current_primary_navigation' in o}==bad)
cleanops=copy.deepcopy(newops)
for x in proposal['case_only_url_replacements']:cleanops[x['product_id']][x['json_pointer'].split('/')[-1]]=x['before']
for oid in bad:cleanops[oid].pop('current_primary_navigation',None)
check('all_option_fields_identical_except_two_urls_and_two_new_annotations',cleanops==oldops)
allowedpairs={(x['before'],x['after']) for x in proposal['case_only_url_replacements']}
caseonly=[x for x in changes if x['group']=='register' and isinstance(x['current'],str) and 'Moonwater%20Catcher' in x['current']]
check('all_18_current_register_url_projections_are_exact_case_only_pairs',len(caseonly)==18 and all((x['before'],x['current']) in allowedpairs for x in caseonly))
check('mwc_stable_selection_ids_preserved',all(newops[mwc][k]==oldops[mwc][k] for k in ['file_id','folder_id','context_file_id','context_folder_id']))
check('all_source_capture_and_platform_history_preserved',all(new[k]==old[k] for k in ['current_authenticated_squarespace_inventory_observation','latest_authenticated_source_observation_import','source_offer_edges','source_platform_offer_coverage','current_listing_resolution','current_listing_resolution_details','listing_resolution_native_action_drafts']))
for a in proposal['unavailable_primary_annotations']:
 o=newops[a['product_id']];n=o['current_primary_navigation']
 check(a['product_id']+'_annotation_matches_exact_source_and_keeps_hold',all(n[k]==v for k,v in a.items()) and n['source_photo_content_status_retained']==oldops[a['product_id']]['photo_coverage']['individual'] and n['folder_verified'] is True and n['global_deletion_inferred'] is False and n['web_url_openability_verified'] is False)
check('health_counts_and_rows_match_sealed_metadata_evidence',health['counts']==nav['counts'] and len(health['rows'])==48 and all({k:v for k,v in r.items() if k not in ['current_image_url','current_folder_url']}==s for r,s in zip(health['rows'],nav['rows'])))
check('health_current_links_match_candidate_options',all(r['current_image_url']==newops[r['product_id']]['image_url'] and r['current_folder_url']==newops[r['product_id']]['folder_url'] for r in health['rows']))
check('source_coverage_and_no_new_capture_scope_explicit',health['source_photo_coverage_unchanged'] and health['new_capture_requests']==health['new_image_selections']==health['native_mutations']==health['physical_verifications']==0 and 'not a whole-library' in health['scope'])
check('photo_review_history_byte_identical',sha(C/'photo-review-queue.json')==sha(manifest['report_reviews']['snapshot'])=='281f1835d6493c89e8e9ceb5a8394af9e3359a9ab49d825fe202ca3f6e4eb287')
check('physical_audit_byte_identical',sha(C/'physical-source-audit.json')==sha(manifest['physical_audit']['snapshot']))
with (OUT/'Current_Primary_Navigation_48.csv').open(encoding='utf-8-sig',newline='') as fh:csvrows=list(csv.DictReader(fh))
csvmap={x['option_id']:x for x in csvrows}
check('csv_exact_48_unique_options',len(csvrows)==len(csvmap)==48 and set(csvmap)=={x['product_id'] for x in nav['rows']})
csvfails=[]
for r in health['rows']:
 c=csvmap[r['product_id']]
 expect={'file_id':r['file_id'],'folder_id':r['folder_id'],'name':r['name'],'image_url':r['current_image_url'],'folder_url':r['current_folder_url'],'navigation_status':r['navigation_status'],'file_verified':str(r['file_verified_by_id']),'folder_verified':str(r['folder_verified_by_id']),'readback_utc':nav['recorded_utc']}
 csvfails += [{'id':r['product_id'],'field':k} for k,v in expect.items() if c[k]!=v]
check('csv_exact_identifiers_links_statuses_and_clock',not csvfails,csvfails)
class Cards(HTMLParser):
 def __init__(self):super().__init__();self.cards={};self.cur=None;self.anchor=None;self.alllinks=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='article':self.cur=a.get('id');self.cards[self.cur]={'links':[],'text':[]}
  if tag=='a':self.anchor={'href':a.get('href'),'text':''};self.alllinks.append(a.get('href'))
 def handle_data(self,d):
  if self.cur:self.cards[self.cur]['text'].append(d)
  if self.anchor:self.anchor['text']+=d
 def handle_endtag(self,tag):
  if tag=='a':
   if self.cur and self.anchor:self.cards[self.cur]['links'].append(self.anchor)
   self.anchor=None
  if tag=='article':self.cur=None
ht=(OUT/'current-primary-navigation-health.html').read_text();parsed=Cards();parsed.feed(ht)
check('html_has_exact_48_option_cards',set(parsed.cards)==set(csvmap))
htmlfails=[]
for r in health['rows']:
 c=parsed.cards[r['product_id']];links={x['href']:x['text'] for x in c['links']}
 if not {r['current_image_url'],r['current_folder_url']}<=set(links):htmlfails.append({'id':r['product_id'],'issue':'missing exact image/folder links'})
 if r['product_id'] in bad:
  label=links.get(r['current_image_url'],'').lower();cardtext=' '.join(c['text']).lower()
  if not any(word in label for word in ['unverified','unresolved']) or 'metadata verified' in label or 'owner holds are retained' not in cardtext or 'no alternate image selected' not in cardtext:
   htmlfails.append({'id':r['product_id'],'issue':'unresolved image lacks explicit qualification or hold protection'})
check('html_current_links_and_unverified_image_labels',not htmlfails,htmlfails)
check('html_csv_download_and_source_coverage_qualification','Current_Primary_Navigation_48.csv' in parsed.alllinks and 'does not assert a currently verified Dropbox file' in ht and 'not a whole-library' in ht)

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
class Xlsx:
 def __init__(self,path):
  self.z=zipfile.ZipFile(path);self.cache={}
  names=self.z.namelist()
  self.strings=[]
  if 'xl/sharedStrings.xml' in names:
   root=ET.fromstring(self.z.read('xl/sharedStrings.xml'))
   self.strings=[''.join(t.text or '' for t in s.findall('.//s:t',NS)) for s in root.findall('s:si',NS)]
  rels={r.attrib['Id']:r.attrib['Target'] for r in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels'))}
  self.sheets={}
  root=ET.fromstring(self.z.read('xl/workbook.xml'))
  for s in root.findall('s:sheets/s:sheet',NS):
   target=rels[s.attrib['{'+NS['r']+'}id']]
   self.sheets[s.attrib['name']]=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
 def sheet(self,name):
  if name in self.cache:return self.cache[name]
  path=self.sheets[name];root=ET.fromstring(self.z.read(path));cells={}
  for c in root.findall('.//s:sheetData/s:row/s:c',NS):
   v=c.findtext('s:v',None,NS);typ=c.attrib.get('t')
   if typ=='s':v=self.strings[int(v)] if v is not None else None
   elif typ=='inlineStr':v=''.join(t.text or '' for t in c.findall('.//s:t',NS))
   formula=c.findtext('s:f',None,NS)
   cells[c.attrib['r']]={'value':v,'formula':formula}
  rp=posixpath.dirname(path)+'/_rels/'+posixpath.basename(path)+'.rels'
  rels={r.attrib['Id']:r.attrib.get('Target') for r in ET.fromstring(self.z.read(rp))} if rp in self.z.namelist() else {}
  for h in root.findall('s:hyperlinks/s:hyperlink',NS):
   cells.setdefault(h.attrib['ref'],{})['hyperlink']=rels.get(h.attrib.get('{'+NS['r']+'}id')) or h.attrib.get('location')
  self.cache[name]=cells;return cells
 def cell(self,name,addr):return self.sheet(name).get(addr,{})
wb0=Xlsx(manifest['master_workbook']['snapshot']);wb1=Xlsx(C/'master-workbook.pending')
check('workbook_original_28_sheet_names_order_retained',list(wb0.sheets)==list(wb1.sheets) and len(wb1.sheets)==28)
linkfails=[]
for x in plan['native_link_changes']:
 a=wb0.cell(x['sheet'],x['cell']);b=wb1.cell(x['sheet'],x['cell'])
 if (x['before'],x['current']) not in allowedpairs or x['before'] not in [a.get('value'),a.get('hyperlink')] or x['current'] not in [b.get('value'),b.get('hyperlink')]:linkfails.append({'sheet':x['sheet'],'cell':x['cell'],'before':a,'after':b})
check('workbook_55_same_id_case_only_current_link_projections',len(plan['native_link_changes'])==55 and not linkfails,linkfails)
cellfails=[]
for x in plan['cell_changes']:
 a=wb0.cell(x['sheet'],x['cell']).get('value');b=wb1.cell(x['sheet'],x['cell']).get('value')
 if a!=str(x['before']) or b!=str(x['value']):cellfails.append({'sheet':x['sheet'],'cell':x['cell'],'baseline':a,'candidate':b})
check('workbook_10_planned_labels_and_health_notes_saved',len(plan['cell_changes'])==10 and not cellfails,cellfails)
check('photo_coverage_native_table_header_retained',wb1.cell('Photo Coverage','C9').get('value')==wb0.cell('Photo Coverage','C9').get('value')=='Individual full view')
badrows={'BSI-D5A939264C82':188,'BSI-65520F070145':190}
critical=[]
for oid,row in badrows.items():
 a=wb0.cell('Master Catalogue','N'+str(row));b=wb1.cell('Master Catalogue','N'+str(row))
 ok=b.get('value')=='Saved image (unverified)' and b.get('hyperlink')==a.get('hyperlink')==oldops[oid]['image_url']
 ok=ok and wb1.cell('Photo Coverage','C'+str(row)).get('value')==wb0.cell('Photo Coverage','C'+str(row)).get('value')=='Available'
 critical.append({'option_id':oid,'passed':ok})
check('workbook_keeps_saved_urls_and_source_available_separate_from_health',all(x['passed'] for x in critical),critical)
# Read every specification cell on rows belonging to the three changed navigation options.
s0=wb0.sheet('Specifications');s1=wb1.sheet('Specifications')
targetrows={''.join(c for c in address if c.isdigit()) for address,cell in s0.items() if cell.get('value') in {mwc,*bad}}
allowed_spec={(x['sheet'],x['cell']) for x in plan['native_link_changes'] if x['sheet']=='Specifications'}
specfails=[]
for addr,a in s0.items():
 row=''.join(c for c in addr if c.isdigit())
 if row in targetrows and ('Specifications',addr) not in allowed_spec and a!=s1.get(addr):specfails.append(addr)
check('three_options_all_18_working_specification_rows_preserved',len(targetrows)==18 and not specfails,{'rows':len(targetrows),'unexpected_changed_cells':specfails})
check('frozen_input_bytes_stable_through_independent_readback',all(sha(p)==v for p,v in initial_hashes.items()))
result={'status':'PASS' if all(x['passed'] for x in checks) else 'FAIL','schema':'boldstone.independent.primary-navigation-candidate-qa.v1','recorded_utc':datetime.now(timezone.utc).isoformat(),'reviewer_thread':'01a13fe6-495b-7253-b923-31823b4cbca8','candidate_register':{'path':str(C/'canonical-master-register.json'),'sha256':sha(C/'canonical-master-register.json')},'candidate_workbook':{'path':str(C/'master-workbook.pending'),'sha256':sha(C/'master-workbook.pending')},'source_seal_sha256':manifest['navigation_seal']['sha256'],'checks_passed':sum(x['passed'] for x in checks),'checks_total':len(checks),'checks':checks,'native_navigation_outcome':'46/48 selected file IDs and all48 folders verified in sealed metadata packet; two held references remain unresolved. No fresh native read performed.','scope':'Independent saved JSON comparison, selected workbook XML cells/hyperlinks,48row CSV and48HTML cards; no rendering claim, native mutation or shared-file write.','reviewed_frozen_artifacts':initial_hashes}
save('candidate-readback.json',result)
seal={'status':result['status'],'schema':'boldstone.primary-navigation-independent-qa-seal.v1','recorded_utc':result['recorded_utc'],'candidate_register_sha256':result['candidate_register']['sha256'],'candidate_workbook_sha256':result['candidate_workbook']['sha256'],'files':[{'path':str(OWN/n),'sha256':sha(OWN/n),'bytes':(OWN/n).stat().st_size} for n in ['verify_navigation.py','candidate-readback.json']],'shared_or_native_writes':0}
save('sealed-handoff.json',seal)
print(json.dumps({'status':result['status'],'passed':result['checks_passed'],'total':result['checks_total'],'failed':[x for x in checks if not x['passed']],'qa':str(OWN/'candidate-readback.json'),'qa_sha256':sha(OWN/'candidate-readback.json'),'seal_sha256':sha(OWN/'sealed-handoff.json')},ensure_ascii=False))
