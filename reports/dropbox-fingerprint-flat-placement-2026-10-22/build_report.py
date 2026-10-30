from pathlib import Path
import json, html, os
from urllib.parse import quote

BASE=Path(__file__).resolve().parent
overlay=json.loads((BASE/'catalogue-placement-overlay.json').read_text())
plan=json.loads((BASE/'plan-and-before-inventory.json').read_text())
e=html.escape
def link(url,label):
    return '<a href="'+e(url,quote=True)+'">'+e(label)+'</a>'
def folder_url(path):
    return 'https://www.dropbox.com/home'+quote(path,safe='/')
groups=''.join('<tr><td>'+link(g['url'],g['name'])+'</td><td>'+str(g['uploaded_photo_count'])+'</td><td><code>'+e(g['file_id'])+'</code></td></tr>' for g in overlay['groups'])
moves=''.join('<tr><td>'+link(folder_url(m['destination_path']),Path(m['destination_path']).name)+'</td><td><code>'+e(m['source_id'])+'</code></td></tr>' for m in plan['move_entries'])
cards=[]
for p in overlay['photos']:
    img=quote(os.path.relpath(p['source_local_path'],BASE),safe='/')
    members=', '.join(str(n) for n in p['left_to_right_component_numbers'])
    cards.append('<article><a href="'+e(p['file']['url'],quote=True)+'"><img loading="lazy" src="'+e(img,quote=True)+'" alt="'+e(p['finish']+' photo '+str(p['image_number']),quote=True)+'"></a><h3>'+e(p['finish']+' '+str(p['image_number']))+'</h3><p>'+link(p['file']['url'],p['file']['name'])+'</p><p>Left to right: '+members+'. '+e(p['image_role'])+'.</p><p>'+link(p['folder']['url'],'Containing folder')+'</p><p class="small">'+e(p['file']['file_id'])+' · '+format(p['file']['bytes'],',')+' bytes<br>Original bytes verified</p></article>')
catalogue=''
if (BASE/'completion-status.json').exists():
    completion=json.loads((BASE/'completion-status.json').read_text())
    workbook=quote(os.path.relpath(completion['master_workbook'],BASE),safe='/')
    catalogue='<h2>Published catalogue update</h2><p>'+link(workbook,'Open the master catalogue')+' — Fingerprint Current contains six numbered finish records; Fingerprint Photos contains all 26 photograph mappings. All 82 new native links were verified in the saved workbook.</p><p>The legacy Left/Right identity decision remains pending: '+link('identity-comparison.html','review the comparison')+'. Existing specifications remain preserved.</p>'
body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fingerprint placement verification</title><style>
body{font:16px/1.5 system-ui,sans-serif;color:#25342e;background:#f6f4ee;margin:0;padding:36px;max-width:1280px;margin:auto}h1{font-size:32px;margin-bottom:8px}h2{margin-top:36px}a{color:#175b46}code,.small{font-size:12px;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;border-bottom:1px solid #ddd;padding:10px;vertical-align:top}thead{background:#e5ece4}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:18px}article{background:white;padding:16px;border:1px solid #d9dfd6;border-radius:8px}article img{width:100%;height:200px;object-fit:contain;background:#efeee8}article h3{margin:10px 0}article p{margin:6px 0;overflow-wrap:anywhere}.status{background:#e2eee4;padding:16px;border-left:5px solid #38674a}.note{color:#59625d}footer{border-top:1px solid #ccc;padding-top:20px;margin-top:36px}</style><body>
<h1>Fingerprint: verified Dropbox placement</h1><p>22 October 2026</p><div class="status"><strong>14 folders moved · 6 folders created · 26 original photographs uploaded</strong><br>All 26 native content hashes match the source photographs. All 13 existing images and 14 moved folder IDs were preserved.</div>
<p>'''+link(overlay['family_folder']['url'],'Open Fingerprint in Dropbox')+'''</p>
<p>All content folders are now direct children of Fingerprint. The former Fingerprint Concentric container remains empty. Group and detail photographs retain their recorded coverage roles.</p>
'''+catalogue+'''<h2>Seven photograph groups</h2><table><thead><tr><th>Current folder</th><th>New photographs</th><th>Dropbox ID</th></tr></thead><tbody>'''+groups+'''</tbody></table>
<h2>The 26 uploaded originals</h2><div class="grid">'''+''.join(cards)+'''</div>
<h2>The 14 moved folders</h2><p>Each folder moved from Fingerprint/Fingerprint Concentric to Fingerprint, without renaming or changing its Dropbox ID.</p><table><thead><tr><th>Current direct child</th><th>Preserved Dropbox ID</th></tr></thead><tbody>'''+moves+'''</tbody></table>
<h2>Verification records</h2><p>'''+link('verification.json','Placement verification')+' · '+link('content-hash-verification.json','Original-byte verification')+' · '+link('catalogue-placement-overlay.json','Catalogue evidence and current links')+'''</p>
<p class="note">Catalogue alias reconciliation is handled by the main catalogue writer. This placement report does not infer a legacy Left/Right identity, measured specifications, or isolated-photo qualification from group photographs.</p>
<footer><p>Reversal: the 14 folders can be moved back to the preserved empty parent. The 26 added photographs and six new folders can be removed on explicit request using their recorded paths and IDs. Existing photographs were not overwritten or deleted.</p></footer></body></html>'''
(BASE/'placement-report.html').write_text(body)
print(json.dumps({'report':str(BASE/'placement-report.html'),'photo_cards':len(cards),'group_rows':len(overlay['groups']),'move_rows':len(plan['move_entries'])}))
