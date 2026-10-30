"""Current photo coverage, open requests and qualified specification checklist."""
from common import *
from html import escape as e
from copy import deepcopy
import csv,sqlite3

def rel(p):return str(Path(p).relative_to(BASE))
def link(url,label):return '<a href="'+e(url,quote=True)+'">'+e(label)+'</a>' if url else e(label+' unbound')
def csvfile(name,rows):
    p=OUT/name
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['product_id','name','individual_status','primary_file_id','primary_folder_id','primary_image','containing_folder','context_status','context_file_id','context_image','context_folder','series_status','series_file_id','series_image','series_folder','qualification']);w.writeheader();w.writerows(rows)
    return rel(p)
rows=[];held=[];requests=[];fieldrows=[];series_requests=[]
for o in g['options']:
    if o['product_id'] not in active:continue
    s=o.get('current_series_reference',{})
    r={'product_id':o['product_id'],'name':o['name'],'individual_status':o['photo_coverage'].get('individual',''),'primary_file_id':o.get('file_id') or '', 'primary_folder_id':o.get('folder_id') or '', 'primary_image':o.get('image_url',''),'containing_folder':o.get('folder_url',''),'context_status':o.get('context_status',''),'context_file_id':o.get('context_file_id') or '', 'context_image':o.get('context_image_url',''),'context_folder':o.get('context_folder_url',''),'series_status':o['photo_coverage'].get('series',''),'series_file_id':s.get('file_id',''),'series_image':s.get('image_url',''),'series_folder':s.get('folder_url',''),'qualification':o.get('context_description','')}
    rows.append(r)
    if o['product_id'] in g['latest_verified_native_filename_import']['effective_context_owner_holds']:held.append(r)
    if o.get('historical_primary_reference'):requests.append(r)
    if o.get('historical_series_reference') and not s:series_requests.append(r)
    for k,v in o.get('master_fields',o['specifications']).items():
        fieldrows.append({'product_id':o['product_id'],'name':o['name'],'field':k,'working_value':v.get('display',''),'state':v.get('state',''),'basis':v.get('basis',''),'physical_verification':v.get('physical_verification',''),'image':o.get('image_url',''),'folder':o.get('folder_url','')})
paths={'coverage':csvfile('Photo_Coverage_186.csv',rows),'held_in_situ_cases_csv':csvfile(f'Held_In_Situ_Cases_{len(held)}.csv',held),'active_individual_requests_csv':csvfile(f'Active_Individual_Photograph_Requests_{len(requests)}.csv',requests),'active_series_requests_csv':csvfile(f'Active_Series_Photograph_Requests_{len(series_requests)}.csv',series_requests),'field_checklist':csvfile('Specification_Verification_Checklist_1116_Fields.csv',fieldrows)}
paths['technical_individual_references']=csvfile(f'Technical_Individual_References_{sum(r["individual_status"]!="Available" for r in rows)}.csv',[r for r in rows if r['individual_status']!='Available'])
style='<style>body{font:16px Arial;max-width:1100px;margin:32px auto;padding:0 20px;color:#243847}a{color:#17617d}p{line-height:1.5}article{padding:16px 0;border-top:1px solid #cbd4da}td,th{text-align:left;padding:8px;border-bottom:1px solid #dde3e7;vertical-align:top}table{border-collapse:collapse;width:100%}input{font:inherit;padding:10px;width:75%}.small{font-size:14px;color:#51636e}</style>'
def page(title,content):return '<!doctype html><meta charset="utf-8"><title>'+e(title)+'</title>'+style+'<h1>'+e(title)+'</h1><p class="small">Publication cut '+e(manifest['recorded_utc'])+'. Working estimates and source conflicts retain their labels. No new physical measurement or exact platform match is asserted.</p>'+content
cards=[]
for r in requests:
    candidate=files.get('id:cnqzTNngPVsAAAAAAAuQDA') if r['product_id']=='BSI-09C1A55D460D' else None
    candidate_link=('<p>'+link(candidate['image_url'],'Surviving whole-panel candidate')+' · '+link(candidate['folder_url'],'Candidate containing folder')+'</p><p class="small">Viewed as a full-panel candidate; no saved Primary approval or new physical/variant inference. File '+e(candidate['file_id'])+'</p>') if candidate else ''
    cards.append('<article><h2>'+e(r['name'])+'</h2><p>Former Primary was deleted by owner and verified absent. Choose a surviving full view or capture a separate photograph.</p><p>'+link(r['containing_folder'],'Containing folder')+'</p>'+candidate_link+'<p class="small">Historical file ID '+e(options[r['product_id']]['historical_primary_reference']['file_id'])+'</p></article>')
cards.append('<h2>Context replacements remain on owner hold</h2>')
for r in series_requests:
    o=options[r['product_id']]
    cards.insert(0,'<article><h2>'+e(r['name'])+' — series replacement</h2><p>A currently unavailable group photograph previously supplied this series reference. A surviving qualified group image is needed; component identity, finish and position must remain identifiable.</p><p>'+link(r['primary_image'],'Current individual / accepted group reference')+' · '+link(r['containing_folder'],'Containing folder')+' · '+link(o['historical_series_reference']['folder_url'],'Previous group folder')+'</p></article>')
for r in held:cards.append('<article><h3>'+e(r['name'])+'</h3><p>'+link(r['primary_image'],'Current example picture')+' · '+link(r['containing_folder'],'Containing folder')+'</p><p class="small">Held under the standing owner policy; no repeated photograph request.</p></article>')
(OUT/'remaining-photograph-requests.html').write_text(page('Current photograph requests and held cases','<p>Two Primary selections remain open in this review cut. The six recent series replacements remain mapped, and Golden Spiral has a qualified paired-display reference with its companion only partly visible. Frozen Fish exact legacy-image binding remains deferred; current faces stay 70 cm high × 15 cm wide. 28 context cases and one prior series case remain held. Optional-series policies and accepted group references are preserved.</p>'+''.join(cards)))
specs=[]
for o in sorted((x for x in g['options'] if x['product_id'] in active),key=lambda x:x['name']):
    fields=''.join('<tr><td>'+e(k)+'</td><td>'+e(str(v.get('display','')))+'<p class="small">'+e(str(v.get('state','')))+' | '+e(str(v.get('basis','')))+'</p></td></tr>' for k,v in o.get('master_fields',o['specifications']).items())
    specs.append('<article id="'+o['product_id']+'"><h2>'+e(o['name'])+'</h2><p>'+link(o.get('image_url'),'Example picture')+' · '+link(o.get('folder_url'),'Containing folder')+'</p><table>'+fields+'</table></article>')
(OUT/'specifications-to-verify.html').write_text(page('Working specifications and physical verification','<p>186 active options have all six working field groups recorded. Actual dimensions/depth, bare-panel weight, material and fitted fixing still require the separately recorded physical evidence. Offered fixing choices do not establish fitted hardware. Prices and availability retain their existing owner/estimate qualifications.</p><input aria-label="Filter specifications" placeholder="Filter by sculpture or specification">'+''.join(specs)+'<script>document.querySelector("input").addEventListener("input",ev=>{let q=ev.target.value.toLowerCase();document.querySelectorAll("article").forEach(x=>x.hidden=!x.textContent.toLowerCase().includes(q))})</script>'))
paths.update(photograph_review=rel(OUT/'remaining-photograph-requests.html'),specification_review=rel(OUT/'specifications-to-verify.html'))
write(H/'current-reader-paths.json',paths)
# Seal the final register binding after the readback-only summary correction.
dbpath=H/'gallery-projection/complete-image-platform-register.sqlite';db=sqlite3.connect(dbpath)
raw=json.loads(db.execute("SELECT value_json FROM metadata WHERE key='current_navigation_publication'").fetchone()[0])
if raw.get('register_sha256')!=sha(H/'canonical-master-register.json'):
    raw['register_sha256']=sha(H/'canonical-master-register.json');db.execute("UPDATE metadata SET value_json=? WHERE key='current_navigation_publication'",(json.dumps(raw),));db.commit()
db.close()
seal=read(H/'gallery-projection/sealed-handoff.json');seal['register_sha256']=sha(H/'canonical-master-register.json');seal['database_sha256']=sha(dbpath);write(H/'gallery-projection/sealed-handoff.json',seal)
gallery=read(H/'gallery-preparation.json');gallery.update(database_sha256=seal['database_sha256'],seal_sha256=sha(H/'gallery-projection/sealed-handoff.json'));write(H/'gallery-preparation.json',gallery)
print(json.dumps({'photo_rows':len(rows),'context_holds':len(held),'open_primary_requests':len(requests),'open_series_requests':len(series_requests),'working_field_rows':len(fieldrows)}))
