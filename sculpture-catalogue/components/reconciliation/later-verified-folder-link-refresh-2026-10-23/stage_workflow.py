from pathlib import Path
H=Path(__file__).resolve().parent;O=H.parent/'moon-shellwave-links-leaf-curve-context-2026-10-23'
s=(O/'author_workbook.mjs').read_text().replace('BSI-CF0CC1EB8F96','BSI-83F1AACE15E9')
s=s.replace("photo.values=[['No verified image']];eq(value('Photo Coverage','D4'),139,'Context count responds to actual role status');photo.values=[['Available']];","photo.values=[['Available']];eq(value('Photo Coverage','D4'),140,'Context count responds to actual role status');photo.values=[['No verified image']];")
s=s.replace("task.values=[['Open']];eq(value('Missing Pictures','B4'),65,'Owner-directed task can reopen independently');task.values=[['Resolved']];","task.values=[['Resolved']];eq(value('Missing Pictures','B4'),64,'Unresolved-source action affects the summary');task.values=[['Open']];")
s=s.replace('LEAF_CURVE_CONTEXT_WORKBOOK_EXPORTED','NATIVE_LINK_REFRESH_WORKBOOK_EXPORTED').replace('Qualified outdoor-display role count','Current-source role count').replace('Current find/capture action count','Reopened-source action count')
(H/'author_workbook.mjs').write_text(s)
s=(O/'build_reports.py').read_text().replace(O.name,H.name).replace('[208,65,1,47,17,1,86,54]','[209,66,1,48,17,1,86,54]').replace('47 in situ','48 in situ').replace("'in_situ_gaps':47","'in_situ_gaps':48").replace("'required_actions':65","'required_actions':66").replace("'find_capture':64","'find_capture':65")
s=s.replace('The saved Moon/Shellwave/workshop links match the fresh stable-ID readback. Leaf Curve White and Gold Leaf001 is an owner-accepted whole outdoor-display photograph. Its permanent/client installation and physical specifications remain unverified. Earlier qualified image bindings are retained.','Later completed native folder changes are projected by verified stable IDs. Four historical Rust in-situ sources are unresolved in the checked current Master folder. The former001 context needs a current replacement. Leaf Curve remains an accepted whole outdoor-display photograph. All physical values and qualified earlier image associations are retained.')
s=s.replace('Owner-accepted Leaf Curve outdoor-display reference','New image-role approvals in this refresh (none)').replace('Imported_Context_Image_Bindings_1.csv','New_Context_Image_Approvals_0.csv').replace("'in_situ_roles_closed':1","'in_situ_roles_closed':0").replace("'owner_approval_packets_imported':1","'owner_approval_packets_imported':0,'reopened_current_source_roles':1,'unresolved_native_source_ids':4")
s=s.replace("d=read(p);body=''.join", "d=read(p);body=''.join")
s=s.replace("if d.get('specific_file_maps'):body+=", "if d.get('deleted_folders'):body+='<p>Owner removed the empty Sally family folder. Retain its historical alias and the distinct workshop folder and original photograph. No photo or identity was deleted by this import.</p>'\n if d.get('specific_file_maps'):body+=")
start=s.index('for p in pages:\n')
addition="""cards=[]
for c in a['coverage']:
 if c['in_situ']['status']!='Available':continue
 rr=c['in_situ'].get('reference')or{};basis=c['in_situ'].get('basis','Recorded source qualification retained. No new approval or physical verification is added by this folder refresh.')
 cards.append('<article id="'+esc(c['option_id'])+'"><h2>'+esc(c['name'])+'</h2><p>'+reflinks(rr)+'</p><p>'+esc(basis)+'</p><small>'+esc(str(rr.get('file_id',''))+' / '+str(rr.get('folder_id','')))+'</small></article>')
page('current-context-references.html','Recorded context photographs and their qualifications',''.join(cards),139)
missing=read(H/'unavailable-native-references.json');body='<article id="BSI-83F1AACE15E9"><h2>Rust and Verdigris Panel</h2><p>The previously linked in-situ001 needs a current replacement. Use this verified individual photograph for identification. No global deletion is inferred.</p><p>'+reflinks(cmap['BSI-83F1AACE15E9']['individual']['reference'])+'</p><table><tr><th>Historical source ID</th><th>Original name</th><th>Current readback</th></tr>'
for item in missing:body+='<tr><td>'+esc(item['file_id'])+'</td><td>'+esc(item['sealed_native_object']['current_name'])+'</td><td>'+esc(item['current_lookup_status'])+'</td></tr>'
body+='</table><p>Historical source objects and qualifications are retained in the source ledger. No restore, rename or deletion was performed by this catalogue import.</p></article>'
page('unavailable-native-references.html','Historical native sources needing a current replacement',body,1)
csvfile('Unresolved_Historical_Native_Source_IDs_4.csv',[{'file_id':x['file_id'],'historical_name':x['sealed_native_object']['current_name'],'current_status':x['current_lookup_status'],'metadata_error':x['metadata_error'],'global_deletion_inferred':False}for x in missing])
"""
s=s[:start]+addition+s[start:]
(H/'build_reports.py').write_text(s)
s=(O/'verify_workbook.py').read_text().replace("['required_picture_actions']==65","['required_picture_actions']==66").replace('Current65 required','Current66 required').replace("read(H/'source-evidence-verification.json')['status']=='PASS'","read(H/'source-evidence-verification.json')['status']=='PASS_WITH_EXPLICIT_SOURCE_GAP'").replace('One owner-accepted Leaf Curve outdoor-display role; previously imported folder links, Sandstone retirement and all working specifications preserved','Six prior native-change packets,535 current packet objects,349 file paths and21 folder paths refreshed; four historical Rust IDs unresolved and one in-situ request added. Leaf Curve approval, identities and working specifications retained')
(H/'verify_workbook.py').write_text(s)
(H/'guided_review.py').write_text((O/'guided_review.py').read_text().replace(O.name,H.name))
print('NATIVE_WORKFLOW_STAGED')
