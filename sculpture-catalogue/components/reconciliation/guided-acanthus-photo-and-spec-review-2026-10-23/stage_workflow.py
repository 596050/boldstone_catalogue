"""Reuse the established narrow-edit workflow with this release's scope."""
from pathlib import Path
H=Path(__file__).resolve().parent;O=H.parent/'queued-master-links-and-egyptian-palm3-2026-10-23';old=O.name;new=H.name
for name in ['prepare_workbook.py','author_workbook.mjs','verify_workbook.py','build_reports.py']:
 s=(O/name).read_text()
 if name=='prepare_workbook.py':
  s=s.replace("oldout=B/'outputs/master-only-source-correction-2026-10-23'","oldout=B/'outputs/"+old+"'").replace(old,new,1)
  s=s.replace("oid='BSI-E0FAA8F7CB6D'","oid='BSI-70ECBB049292'")
  s=s.replace('Qualified garden context — second from left','Owner-designated display context').replace('Component confirmation and source limits','Display context and source limits')
  s=s.replace('series Optional / no fixed set.','series No verified image.')
  s=s.replace("('Photo Coverage','D4'):136","('Photo Coverage','D4'):137").replace("('Missing Pictures','B4'):71","('Missing Pictures','B4'):70")
  start=s.index("for sn,text in {");end=s.index("for key,x in changes.items():",start)
  s=s[:start]+"for sn,text in {'Master Catalogue':'188 individual options across112 working component identities. Fountain Palm082 is a qualified owner-designated display context;14 actual containing folders refreshed by stable file ID. Specifications and accepted estimates retain their qualifications.','Photo Coverage':'Current Master sources only:177 complete individual references;11 technical gaps including9 accepted qualified listing exceptions and2 open individual/identity entries. Current gaps:51 in situ and18 series. Fountain Palm082 is display context; authenticated installation is unverified.','Missing Pictures':'208 retained action rows:71 required open actions,54 optional and83 resolved. Current gaps:2 individual/identity entries,51 in situ and18 series. Owner deferrals remain in force.'}.items():setcell(sn,'A3',text)\n"+s[end:]
  s=s.replace('baseline-egyptian3','baseline-fountain').replace('02-egyptian3-garden-reference','02-fountain-display-reference').replace('03-egyptian3-source-limits','03-fountain-source-limits').replace('egyptian3_workbook_row','fountain_workbook_row')
 elif name=='verify_workbook.py':
  s=s.replace("['required_picture_actions']==72","['required_picture_actions']==71").replace('Current72 required','Current71 required')
  s=s.replace('Two workshop-name overlays and one owner-confirmed garden component with qualified context; no explicit role approval or physical change','Fourteen same-ID actual-parent moves and one owner-designated Fountain display context; specifications unchanged')
 elif name=='build_reports.py':
  s=s.replace(old,new).replace('[208,72,2,52,18,1,82,54]','[208,71,2,51,18,1,83,54]')
  s=s.replace('52 in situ','51 in situ').replace("'in_situ_gaps':52","'in_situ_gaps':51").replace("'required_actions':72","'required_actions':71").replace("'find_capture':71","'find_capture':70").replace("'resolved_actions':82","'resolved_actions':83")
  s=s.replace('Barbados and Sally workshop-folder links are refreshed by stable ID. Egyptian Palm3 is confirmed as second from left in the garden scene and has a qualified in situ association; the owner confirmation is component identity only, with image origin and physical provenance unverified.','Fountain Palm082 is a qualified owner-designated display context;14 existing files have verified current containing folders. The photograph shows a display board, with no authenticated permanent installation claim. Acanthus brochure conflicts are recorded separately; no physical values are upgraded.')
  s=s.replace('Recorded component identity confirmation','Recorded owner context designation').replace('Confirmed garden component and qualified image role','Owner-designated Fountain display context')
  marker="page('completed-changes.html'"
  at=s.index(marker);s=s[:at]+"foldercards.append('<article><h2>Fountain Palm — Bronze and Verdigris</h2><p>14 existing photographs now have verified containing-folder ID id:cnqzTNngPVsAAAAAAA6Vqw;83 original file IDs retained. Individual image001 remains in its original product folder. No native changes performed by this import.</p></article>')\n"+s[at:]
  marker="for p in pages:\n";at=s.index(marker)
  extra="""spec_review=read(H/'specification-evidence-review.json');body='<section><h2>Acanthus brochure evidence</h2><p>'+esc(spec_review['conclusion'])+'</p><table><tr><th>Master source</th><th>Page</th><th>Source claim</th><th>Scope</th></tr>'
for x in spec_review['sources']:
 dp='/' + x['path'].split('//',1)[1].lstrip('/');u='https://www.dropbox.com/preview'+__import__('urllib.parse',fromlist=['quote']).quote(dp,safe='/');body+='<tr><td>'+link(u,Path(dp).name)+'<br><small>'+esc(x['file_id'])+'</small></td><td>2</td><td>30 × 30 cm face; '+str(x['listed_weight_kg'])+' kg</td><td>'+esc(x['scope'])+'</td></tr>'
body+='</table><p>'+esc(spec_review['rear_observation']['visible_fixing']+' '+spec_review['rear_observation']['limits'])+'</p><p>Still pending: Sandstone individual photograph; Sandstone and Pewter series photographs; Bronze courtyard owner decision. Source review is bounded and does not prove global absence.</p></section>'
page('specification-evidence-review.html','Acanthus source evidence and unresolved physical checks',body,0)
"""
  s=s[:at]+extra+s[at:]
 (H/name).write_text(s)
print('WORKFLOW_STAGED')
