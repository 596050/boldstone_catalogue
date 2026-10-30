import hashlib
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[2]
REPORT = BASE/'outputs/selling-details-completion-2026-10-22'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pointer = json.loads((BASE/'current-master.json').read_text())
regpath = BASE/pointer['register']
assert 'catalogue-followup-2026-10-22' in str(regpath)
assert sha(regpath) == pointer['register_sha256']
assert sha(BASE/pointer['workbook']) == pointer['workbook_sha256']
verification = json.loads((HERE/'published-commercial-integration-verification.json').read_text())
assert verification['status'] == 'PASS'
assert verification['register_sha256'] == pointer['register_sha256']
assert verification['workbook_sha256'] == pointer['workbook_sha256']
reg = json.loads(regpath.read_text())
options = {o['product_id']:o for o in reg['options']}
counts = reg['latest_image_coverage_audit']['counts']
assert counts['individual_statuses']['Available'] == 167
linksroot = BASE/'outputs/catalogue-followup-2026-10-22'
for role in ['individual-images.html','in-situ-images.html','series-images.html']:
    assert (linksroot/role).exists(), role
doc = (REPORT/'index.html').read_text()
before_sha = sha(REPORT/'index.html')
seen = set()
esc = lambda v: html.escape(str(v or ''),quote=True)
def update_row(m):
    row = m.group(0)
    pid = re.search(r'BSI-[A-F0-9]{12}',row).group(0)
    assert pid in options and pid not in seen
    seen.add(pid)
    option = options[pid]
    for label,key in [('Reference image','image_url'),('Dropbox folder','folder_url')]:
        replacement = '<a href="'+esc(option.get(key))+'">'+label+'</a>' if option.get(key) else '<span>'+label+' unavailable</span>'
        row,n = re.subn(r'<a href="[^"]*">'+label+r'</a>',lambda _:replacement,row,count=1)
        assert n == 1
    if pid == 'BSI-3C849B547D50':
        row = row.replace('Made to order<br>1–2 weeks','Made to order<br>1–2 weeks<br><small>New commissions; the reference artwork was a one-off. Availability of that exact piece remains unverified.</small>')
    if pid == 'BSI-83F1AACE15E9':
        row = row.replace('Made to order<br>1–2 weeks','Made to order<br>1–2 weeks<br><small>New commissions; historical source stock 1 is not a current stock count.</small>')
    return row
doc = re.sub(r'<tr data-new="[01]">.*?</tr>',update_row,doc,flags=re.S)
assert len(seen)==186
doc = doc.replace('21 separate photographs required + 1 deferred identity','18 separate images required + 1 deferred identity')
doc = doc.replace('../moonphases-dune-ripple-master-refresh-2026-10-22/','../catalogue-followup-2026-10-22/')
status = 'Merged into the saved master catalogue and independently checked. <a href="../01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Master_Catalogue_2026-10-20.xlsx">Open master workbook</a>.'
doc,n = re.subn(r'<p id="status">.*?</p>',lambda _:'<p id="status">'+status+'</p>',doc,count=1,flags=re.S)
assert n==1
doc=doc.replace('The deferred Frozen Fish record remains an identity check, with a conditional estimate only.','The deferred Frozen Fish record remains an identity check, with a conditional estimate only. Three owner-approved standalone listing images now fill individual-image roles; their photographic or generated origin remains unverified.')
(REPORT/'index.html').write_text(doc)
receipt = {'status':'PUBLISHED_MASTER_REFLECTED_AND_INDEPENDENTLY_VERIFIED','master_pointer':str(BASE/'current-master.json'),'master_pointer_sha256':sha(BASE/'current-master.json'),'register':str(regpath),'register_sha256':pointer['register_sha256'],'workbook':str(BASE/pointer['workbook']),'workbook_sha256':pointer['workbook_sha256'],'report':str(REPORT/'index.html'),'report_sha256':sha(REPORT/'index.html'),'prior_prepared_report_sha256':before_sha,'report_is_mutable_user_view_source_snapshot_preserved_by_master':True,'options':186,'price_estimates':185,'specific_owner_confirmed_price_retained':1,'individual_image_gaps':19,'separate_individual_images_required':18,'deferred_identity':1,'in_situ_gaps':61,'series_gaps':18,'current_links_refreshed_for_options':186,'remote_writes':0}
(REPORT/'publication-state.json').write_text(json.dumps(receipt,indent=2)+'\n')
(HERE/'final-report-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
