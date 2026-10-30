"""Read the saved XLSX package and verify all rows, source cells and links."""
import json,re,hashlib
from pathlib import Path
from datetime import datetime,timezone
from verify_export import load,MAIN

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
r=read(HERE/'export-receipt.json');data=read(HERE/'refresh-data.json');old,new=load(r['previous_workbook']),load(r['output']);p=read(HERE/'snapshot/reviews.json');u=read(HERE/'snapshot/decisions.json');cp=read(HERE/'snapshot/walkthrough.json');checks={}
def value(sheet,address):
 cell=new['sheets'][sheet]['cells'].get(address,('value',''));return cell[2] if cell[0]=='formula' else cell[1]
def column(i):
 text=''
 while i:i,digit=divmod(i-1,26);text=chr(65+digit)+text
 return text
allowed={(x['sheet'],x['address']) for x in r['allowed_existing_cell_changes']};failures=[];sourcecells=0
for name,sheet in old['sheets'].items():
 for address,cell in sheet['cells'].items():
  sourcecells+=1
  if (name,address) in allowed:continue
  actual=new['sheets'][name]['cells'].get(address,('value',''))
  if cell[:2]!=actual[:2]:failures.append((name,address))
checks.update({
 'all_unedited_original_populated_cells_and_formulas_retained':not failures and sourcecells==102078,
 'all14_original_tabs_in_original_order':list(new['sheets'])[:14]==list(old['sheets']) and len(old['sheets'])==14 and len(new['sheets'])==17,
 'original_freeze_panes_and_native_tables_preserved':all(new['sheets'][k]['pane']==v['pane'] for k,v in old['sheets'].items()) and all(new['tables'][k]['style']==v['style'] and new['tables'][k]['filter']==v['filter'] for k,v in old['tables'].items()),
 'immutable_source_register_and_model':sha(r['previous_workbook'])=='02532ec7664b39caa7b62755c8a45748d937045e801ce7fcd985a859faf62f6f' and sha(ROOT/'components/evidence/component_register.json')=='ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61',
 'saved_workbook_SHA_matches_receipt':sha(r['output'])==r['output_sha256'],
 'all_frozen_sources_unchanged':all(sha(x.get('snapshot',x['source']))==x['sha256'] for x in data['source_files']),
 'no_saved_formula_errors_or_unsupported_functions':not [(n,a) for n,s in new['sheets'].items() for a,c in s['cells'].items() if any(str(v) in ['#REF!','#DIV/0!','#VALUE!','#NAME?','#N/A','#NUM!','#NULL!','#SPILL!','#CALC!'] or 'is not implemented' in str(v) for v in c[1:])],
 'artifact_formula_scan_clear':'matched 0 entries' in r['formula_error_inspection'],
})
links=read(HERE/'native-hyperlinks.json')
linklabels={(x['sheet'],x['cell']):x['label'] for x in links}
checks['native_link_plan_unique_and_exact_saved_targets']=len({(x['sheet'],x['cell']) for x in links})==len(links)==r['native_hyperlinks_written'] and all(new['sheets'][x['sheet']]['hyperlinks'].get(x['cell'])==x['target'] for x in links)
checks['all_native_link_labels_saved']=all(value(x['sheet'],x['cell'])==x['label'] for x in links)
checks['all_original_native_links_preserved']=all(new['sheets'][n]['hyperlinks'].get(a)==url for n,s in old['sheets'].items() for a,url in s['hyperlinks'].items())
checks['total_native_link_count_exact']=sum(len(s['hyperlinks']) for s in new['sheets'].values())==len(links)+sum(len(s['hyperlinks']) for s in old['sheets'].values())
for name in new['sheets']:
 if name=='Summary':continue
 table=new['tables'][('T_'+re.sub('[^a-zA-Z]','',name)) if name in old['sheets'] else 'Current_'+name.replace(' ','')]
 checks['native_table_headers:'+name]=table['headers']==[value(name,column(i+1)+'6') for i in range(len(table['headers']))]
for name,info in r['new_sheets'].items():checks['native_table_range:'+name]=any(t['range'].endswith(str(info['last'])) and t['headers']==info['headers'] for t in new['tables'].values())
for name,rows,linkcols in [('Current Reviews',data['reviews'],[7,8,15,16]),('Reviewed Specifications',data['specifications'],[7,8]),('Group References',data['groups'],[6,7])]:
 for i,row in enumerate(rows,7):
  projected=[row[0],row[2],row[1],*row[3:]] if name!='Group References' else row
  errors=[]
  for k,v in enumerate(projected):
   expected=('Open image' if linkcols.index(k)%2==0 else 'Open folder') if k in linkcols and v else v
   expected=linklabels.get((name,column(k+1)+str(i)),expected)
   if value(name,column(k+1)+str(i))!=(expected if expected is not None else ''):errors.append(column(k+1))
  checks[f'complete_saved_row:{name}:{i}']=not errors
for i,entry in enumerate(data['additional_photograph_gaps'],7+data['baseline_photo_gaps']):
 vals=entry['values'];ref=entry['reference'];errors=[]
 for k,v in enumerate(vals):
  expected='Open example image' if k==11 and ref['image'] else ref['folder_id'] if k==9 and ref['folder'] else v
  if value('Photograph Gaps',column(k+1)+str(i))!=expected:errors.append(column(k+1))
 checks['complete_saved_scoped_photo_gap:'+vals[0]]=not errors and value('Photograph Gaps','K'+str(i))==ref['file_id']
checks.update({
 '278_overlapping_scopes_and1668_six_field_rows':len(data['reviews'])==278 and len(data['specifications'])==1668 and value('Summary','F6')==278,
 '1045_deduplicated_working_groups_not_a_sculpture_count':value('Summary','F7')==1045 and data['specification_approval_counts']==u['specification_approval_counts'] and value('Summary','E7')=='Scoped working proposal approvals',
 '22_group_references_and272_total_photograph_gaps':value('Summary','F10')==22 and len(data['groups'])==22 and data['baseline_photo_gaps']+len(data['additional_photograph_gaps'])==272 and r['added_photograph_gap_rows']==164,
 'final_individual_listing_count_stays_unverified':value('Summary','F12')=='Unverified',
 'source_platform_split_37matched43Squarespace_only1Shopify_only':data['platform_source_counts']=={'Squarespace only':43,'Squarespace + Shopify':37,'Shopify only':1} and len({value('Platform Mapping','A'+str(i)) for i in range(7,88)})==81,
 'all6663_stable_Dropbox_file_IDs_retained':{value('Dropbox Files','A'+str(i)) for i in range(7,6670)}=={x['id'] for x in read(HERE/'snapshot/model.json')['assets']},
 'all3052_source_specification_claims_retained':len({value('Specification Evidence','A'+str(i)) for i in range(7,3059)})==3052,
 'universal_manufacture_not_stock_or_specs':value('Summary','B31')=='Owner states all sculptures have been made' and 'current stock, image provenance and final counts remain separate' in value('Summary','C31'),
 'canonical_standing_working_policy_only_once':len(u['working_specification_acceptance_policy_decisions'])==1 and 'No separate reply is invented' in value('Summary','C32'),
 'fixing_and_weight_policies_only_once_each':len(u['global_fixing_choice_policy_decisions'])==len(u['global_approximate_weight_policy_decisions'])==1 and value('Summary','B33')=='Keyhole fixing or French cleat' and 'Azure' in value('Summary','C34'),
 'root_owner_current_answer_and_unknown_keyhole_count_retained':cp['current_answer_recorded'] and cp['current_price_answer_recorded'] and cp['current_availability_answer_recorded'] and not cp['current_fixing_count_answer_recorded'],
 'root_checkpoint_mirror_exact':read(HERE/'snapshot/root_checkpoint.json')['current_component_review']==read(HERE/'snapshot/component_checkpoint.json'),
 'all_allocated_working_reviews_imported_not_all_actual_specs_complete':cp['all_remaining_working_review_state']['six_field_working_scopes']==109 and cp['all_remaining_working_review_state']['reference_disposition_scopes']==2 and cp['all_remaining_working_review_state']['all_actual_specifications_complete'] is False,
 '1549_view_scope_preservation_checks_passed':read(HERE/'view-scope-readback-batch97.json')['status']=='PASS' and read(HERE/'view-scope-readback-batch97.json')['check_count']>=1500,
})
specs={tuple(x[:2])+(x[3],):x for x in data['specifications']};reviews={tuple(x[:2]):x for x in data['reviews']}
vr=('BC-MCP-4','MCP4-VERDIGRIS-RUST')
checks['MCP4_owner25x25_approx6depth4kg_plaster_faux_keyhole175_unlimited1week_exact_finish']=all(t in specs[vr+('Dimensions / depth',)][4] for t in ['25 × 25','6 cm']) and '4 kg dry' in specs[vr+('Weight',)][4] and 'Plaster composite' in specs[vr+('Material / finish',)][4] and 'Keyhole fixing' in specs[vr+('Fixing',)][4] and 'number, hardware and load capacity unconfirmed' in specs[vr+('Fixing',)][4] and '£175' in specs[vr+('Individual price',)][4] and all(t in specs[vr+('Availability',)][4] for t in ['unlimited','1 week'])
checks['Ammonite_all_four_individual_names_and_uncosted_prices']=all(reviews[(cid,'BASE')][2].startswith('Ammonite ') and 'uncosted working proposal' in specs[(cid,'BASE','Individual price')][4] and 'Neither proposal divides' in specs[(cid,'BASE','Individual price')][6] for cid in ['AM-S1','AM-S2','AM-L1','AM-L2'])
checks['Brancusi_White250proposal_not_Gold_or_pair']=all('£250 per White component' in specs[(cid,'BASE','Individual price')][4] and '£312.50' in specs[(cid,'BASE','Individual price')][4] and 'not divided' in specs[(cid,'BASE','Individual price')][6] for cid in ['BC-BR-1','BC-BR-2'])
checks['Azure7kg_net4to10_not15kg_shipping']=all(t in specs[('BC-AZURE','AZURE-BLUE-WHITE','Weight')][4] for t in ['7 kg net','4–10 kg','15 kg','shipping'])
checks['MoonCraterBasin_floor_support_not_certified_wall_mount']='support' in specs[('BC-MOON-CRATER','MOON-CRATER-WHITE-BASIN','Fixing')][4].lower() and '20' in specs[('BC-MOON-CRATER','MOON-CRATER-WHITE-BASIN','Weight')][4]
checks['Soundwave_working_depth_not_claimed_measured']='Six working fields accepted' in value('Summary','G9') and 'estimated depth remains unmeasured' in value('Summary','G9') and 'working' in reviews[('UGR-G310','SOUNDWAVE-WHITE-G310003')][5].lower()
checks['Silver_bronze_Spiralfish_detail_only_context_not_authenticated_room']=all('cropped' in reviews[(cid,vid)][14].lower() or 'detail' in reviews[(cid,vid)][14].lower() for cid,vid in [('BC-SF-1','SF1-BRONZE-PROVISIONAL'),('BC-SF-2','WT2-BRONZE-PROVISIONAL')])
checks['reference_header_and_Portman_no_duplicate_sale_units']=all('Reference disposition' in reviews[k][5] and 'no additional sale unit' in reviews[k][4] for k in [('BC-MCP-4','BASE'),('BC-PORTMAN-1','BASE')])
for i,row in enumerate(data['specifications'],7):
 if row[3]=='Weight':
  overlay=next(x for x in data['weight_policy_overlays'] if x['key']==row[:2]);checks['weight_projection:'+str(i)]=all(value('Reviewed Specifications',col+str(i))==overlay[key] for col,key in [('E','after_detail'),('F','after_state'),('G','after_basis')])
 if row[3]=='Fixing':
  checks['offered_fixing_choice_separate:'+str(i)]='Keyhole fixing or French cleat' in value('Reviewed Specifications','E'+str(i)) and 'existing or historical fitted hardware remains separate' in value('Reviewed Specifications','F'+str(i))
failures=[k for k,v in checks.items() if not v]
out=dict(status='PASS' if not failures else 'FAIL',checked_utc=datetime.now(timezone.utc).isoformat(),checks={k:'PASS' if v else 'FAIL' for k,v in checks.items()},check_count=len(checks),original_source_cells_compared=sourcecells,original_tabs_retained=14,new_review_tabs=3,platform_records=81,dropbox_file_ids=6663,source_specification_claims=3052,review_scope_rows=278,specification_entries=1668,output=r['output'],output_sha256=r['output_sha256'],visual_verification='PENDING')
(HERE/'independent-file-verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert not failures,failures[:20]
print(json.dumps({k:v for k,v in out.items() if k!='checks'}))
