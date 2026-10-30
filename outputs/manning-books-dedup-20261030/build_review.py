from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib, html, json, re, unicodedata

OUT = Path(__file__).resolve().parent
ROOT = '/TOM Apps/Manning Books'
native = json.loads((OUT/'native-inventory.json').read_text())
connector = json.loads((OUT/'inventory.json').read_text())
remote = {r['file_id']:r for r in connector['entries'] if r['object_type']=='file'}
files = [r for r in native['entries'] if r['object_type']=='file']
assert {r['id'] for r in files} == set(remote)
verified = {r['id']:r for r in json.loads((OUT/'verified-metadata.json').read_text()) if r.get('success')}
inspections = {}
for name in ('pdf-inspections.json','pdf-inspections-extra.json'):
    for r in json.loads((OUT/name).read_text()):
        if r.get('success'): inspections[r['id']] = r

ALIASES = {
 'Business-Friendly DSLs':'Building User-Friendly DSLs',
 'Build a Robo Advisor with Python (From Scratch)':'Build a Robo-Advisor with Python (From Scratch)',
 'Think Like a Data Analyst':'Effective Data Analysis',
 'Mastering Unlabeled Data':'Unsupervised Learning with Generative AI',
 'Statistics Playbook':'Statistics Slam Dunk',
 'Continuous Delivery for Kubernetes':'Platform Engineering on Kubernetes',
 'Tiny C# Projects':'C# by Example',
 'Effective Go':'Go by Example',
 'Edge Computing Technology and Applications':'Edge Computing',
 "Software Engineer's Guide to Deep Learning System Design":'Designing Deep Learning Systems',
 'Implementing and Exploiting Cryptography':'Hacking Cryptography',
 'Causal Machine Learning':'Causal AI',
 'AI Coding':'AI Assistant Coding',
 'Bootstrapping Microservices with Docker, Kubernetes, and Terraform':'Bootstrapping Microservices',
 'dotNET Core in Action':'dotNET in Action',
}
EDITION_NUMBERS = {'Second':2, 'Third':3, 'Fourth':4}

def clean(s):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKC',s) if unicodedata.category(c)!='Cf').split())

def title(r):
    parent = r['path_display'].rsplit('/',1)[0]
    if parent:
        return clean(parent.rsplit('/',1)[-1])
    stem = re.sub(r'\.pdf$','',r['name'],flags=re.I)
    stem = re.sub(r' \(\d+\)$','',stem)
    stem = re.sub(r'_v\d+_MEAP$','',stem,flags=re.I)
    return clean(stem.replace('_',' '))

def classify(r):
    original = title(r)
    match = re.search(r', (Second|Third|Fourth) Edition$',original)
    edition = EDITION_NUMBERS[match[1]] if match else 1
    base = original[:match.start()] if match else original
    family = ALIASES.get(base,base)
    r.update(original_title=original,book=family,edition=edition,
             meap_version=int(re.search(r'_v(\d+)_MEAP',r['name'],re.I)[1]) if re.search(r'_v(\d+)_MEAP',r['name'],re.I) else None,
             published=not bool(re.search(r'_MEAP',r['name'],re.I)),
             namespace_path=remote[r['id']]['path'],display_path=ROOT+r['path_display'],
             sharing='Inside shared Manning Books folder; no direct shared links found in account inventory')
    listed = remote[r['id']]
    assert r['size']==listed.get('file',{}).get('size',0)
    assert r['name']==listed['name']
    return family.casefold()

def rank(r):
    return (r['edition'],r['published'],r['meap_version'] or 0,r['server_modified'],r['id'])

def field(r,key):
    return next((line.split(':',1)[1].strip() for line in inspections[r['id']]['pdfinfo'].splitlines() if line.startswith(key+':')),'')

groups = defaultdict(list)
for r in files: groups[classify(r)].append(r)
keepers,removals,books = [],[],[]
for key,rows in sorted(groups.items()):
    good = [r for r in rows if r['size']>0]
    assert good, key
    keeper = max(good,key=rank)
    assert keeper['id'] in inspections, ('Keeper PDF not inspected',keeper['name'])
    keeper['pdf_title'] = field(keeper,'Title')
    keeper['pdf_author'] = field(keeper,'Author')
    keeper['pdf_pages'] = int(field(keeper,'Pages'))
    keeper['action']='KEEP'
    keepers.append(keeper)
    deleted=[]
    for r in rows:
        if r['id']==keeper['id']:continue
        if not r['size']: reason='Empty PDF; retain a non-empty readable copy of this title.'
        elif r['content_hash']==keeper['content_hash']:reason='Byte-identical duplicate of the retained PDF.'
        elif r['edition']<keeper['edition']:reason='Superseded by a newer edition present in this folder collection.'
        elif r['published'] is False and keeper['published']:reason='MEAP draft superseded by the published release (including confirmed title changes).'
        elif (r['meap_version'] or 0)<(keeper['meap_version'] or 0):reason='Older MEAP version of the same book (including confirmed title changes).'
        else:reason='Earlier download of the same stated edition and version; the newest download is retained. PDF bytes can differ.'
        r.update(action='REMOVE',reason=reason,keeper_id=keeper['id'],keeper_path=keeper['display_path'])
        removals.append(r);deleted.append(r)
    books.append({'book':keeper['book'],'original_titles':sorted({r['original_title'] for r in rows}), 'keeper':keeper['display_path'],'keeper_id':keeper['id'],'edition':keeper['edition'],'meap_version':keeper['meap_version'],'published':keeper['published'],'pdf_pages':keeper['pdf_pages'],'remove_count':len(deleted),'remove_bytes':sum(r['size'] for r in deleted)})

assert len(keepers)+len(removals)==len(files)==4582
assert len({r['id'] for r in keepers})==len(keepers)
assert not ({r['id'] for r in keepers}&{r['id'] for r in removals})
assert all(r['id'] in verified and verified[r['id']]['rev']==r['rev'] for r in files), 'Metadata verification not complete'
summary={'status':'AWAITING_EXACT_ITEM_DELETION_CONFIRMATION','scope':ROOT,'files_reviewed':len(files),'folders_reviewed':sum(r['object_type']=='folder' for r in native['entries']),'keep_files':len(keepers),'remove_files':len(removals),'keep_bytes':sum(r['size'] for r in keepers),'remove_bytes':sum(r['size'] for r in removals),'empty_pdfs':sum(not r['size'] for r in files),'direct_shared_links_in_scope':len(native['relevant_shared_links']),'individually_revision_verified':len(verified),'title_groups_with_pdf_opening_pages_inspected':len(inspections),'generated_utc':datetime.now(timezone.utc).isoformat(),'mutations_performed':0,'folder_deletions_proposed':0}
manifest={'summary':summary,'selection_policy':['Newest edition present in the supplied Dropbox collection, including a newer MEAP edition in preference to an older complete edition.','Within an edition, prefer published release; otherwise use the highest stated MEAP version.','Use newest server modification time to choose between downloads of the same stated edition and version.','Exclude zero-byte PDFs as keepers.','Merge only title changes supported by PDF title, author, welcome text or matching contents. Preserve distinct books, anthologies and samples.','Keep existing names and locations. No Dropbox files have been changed.'], 'confirmed_title_aliases':ALIASES,'books':books,'keepers':keepers,'removals':removals,'folders':[],'notes':['Most repeated downloads have different PDF bytes. These are classified by stated book edition/version, not called byte-identical copies.','An older complete edition can contain chapters absent from a newer MEAP. The exact older editions proposed for removal are listed.','The two AI Coding / AI Assistant Coding six-page PDFs have identical normalized full text, despite differing bytes.','Distinct works by the same author are preserved, including Rust Design Patterns / Code Like a Pro in Rust and Get Programming with F# / F# in Action.','The folder is shared. Deleting files affects everyone with access. No direct file or folder shared links were found in the account link inventory.','Before an approved deletion, recheck file identity/revision and retained keeper identity/revision. Skip changed or newly added files.','No backup copy was created. Dropbox deleted-file recovery is available subject to the account retention period.']}
payload=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
(OUT/'deletion-review.json').write_bytes(payload)
digest=hashlib.sha256(payload).hexdigest()
(OUT/'review-integrity.json').write_text(json.dumps({'deletion_review_sha256':digest,'summary':summary},indent=2)+'\n')

esc=html.escape
fmt=lambda b:f'{b/1_000_000_000:.2f} GB ({b/1024**3:.2f} GiB)'
parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Manning Books deletion review</title><style>body{font:15px/1.5 system-ui,sans-serif;max-width:1320px;margin:40px auto;padding:0 24px;color:#182433;background:#f6f8fb}h1{font-size:32px}h2{margin-top:34px}article{background:white;padding:20px;margin:12px 0;border:1px solid #d9e1eb;border-radius:8px}.status{background:#fff1ce;padding:16px;border-radius:8px}input{font:inherit;padding:12px;width:min(96%,650px);border:1px solid #91a2b7;border-radius:6px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:10px;text-align:left;vertical-align:top;border-bottom:1px solid #e0e6ed}td.path{max-width:530px;overflow-wrap:anywhere}small,.muted{color:#526379}.keep{color:#10603e}.remove{color:#9d3225}.tag{font-size:12px;padding:4px 6px;background:#eaf0f7;border-radius:4px}summary{cursor:pointer;font-weight:600}code{overflow-wrap:anywhere}a{color:#0758af}li{margin:5px 0}</style><h1>Manning Books: keep and removal review</h1>']
parts.append(f'<p class="status"><strong>Awaiting approval. No Dropbox changes have been made.</strong><br>Exact proposed operation: delete {len(removals):,} PDF files listed below. Keep {len(keepers):,} PDFs. No folders are proposed for deletion.</p><p>Scope: <a href="https://www.dropbox.com/home/TOM%20Apps/Manning%20Books">{ROOT}</a><br>Reviewed {len(files):,} files in {summary["folders_reviewed"]} folders. Removal size: <strong>{fmt(summary["remove_bytes"])}</strong>. Keep size: {fmt(summary["keep_bytes"])}.</p>')
parts.append('<h2>Selection rules</h2><ol>'+''.join('<li>'+esc(s)+'</li>' for s in manifest['selection_policy'])+'</ol><p><strong>Newer MEAP editions are retained over older complete editions.</strong> Review those edition replacements before approving. The folder is shared, so removal applies to everyone with access.</p>')
parts.append('<h2>Verification and exceptions</h2><ul>'+''.join('<li>'+esc(s)+'</li>' for s in manifest['notes'])+f'<li>All {len(files):,} file identities, revisions, sizes and content hashes were individually checked. Every retained PDF was downloaded, opened with pdfinfo, and its first eight pages extracted for title/version inspection.</li></ul><p><a href="deletion-review.json">Exact machine-readable deletion manifest</a> · <a href="native-inventory.json">Full Dropbox inventory</a> · <a href="verified-metadata.json">Individual metadata verification</a></p>')
parts.append(f'<p class="muted">Manifest SHA-256: <code>{digest}</code><br>Generated {esc(summary["generated_utc"])}. The plan includes only the IDs and revisions in this manifest. Later additions are outside this plan.</p><h2>Review by book</h2><p>Search by title or filename. Expand a book to view every exact file proposed for removal, its modified time, sharing status, and replacement.</p><input id="search" type="search" placeholder="Filter books or filenames" aria-label="Filter books or filenames"><p id="count" class="muted"></p>')
bybook=defaultdict(list)
for r in removals:bybook[r['book']].append(r)
for k in keepers:
    rows=sorted(bybook[k['book']],key=lambda r:r['display_path'].casefold())
    searchable=' '.join([k['book'],k['display_path']]+[r['display_path'] for r in rows]).casefold()
    version=f'Edition {k["edition"]}; '+('published release' if k['published'] else f'MEAP v{k["meap_version"]}')
    parts.append(f'<article data-search="{esc(searchable,quote=True)}"><h3>{esc(k["book"])}</h3><p><span class="tag">{esc(version)}</span> <span class="tag">{k["pdf_pages"]} pages</span></p><p class="keep"><strong>KEEP</strong> {esc(k["display_path"])}</p><small>Modified {esc(k["server_modified"])} UTC · {k["size"]:,} bytes · {esc(k.get("pdf_author", ""))}</small><details><summary class="remove">Remove {len(rows)} earlier or redundant files · {fmt(sum(r["size"] for r in rows))}</summary><table><thead><tr><th>Exact file path / identity</th><th>Modified UTC / size</th><th>Reason and sharing</th></tr></thead><tbody>')
    for r in rows:
        parts.append(f'<tr><td class="path">{esc(r["display_path"])}<br><small>{esc(r["id"])} · rev {esc(r["rev"])}</small></td><td>{esc(r["server_modified"])}<br>{r["size"]:,} bytes<br>Type: file (PDF)</td><td>{esc(r["reason"])}<br><small>{esc(r["sharing"])}</small></td></tr>')
    parts.append('</tbody></table></details></article>')
parts.append('<p>After an approved deletion, Dropbox recovery is documented at <a href="https://help.dropbox.com/delete-restore/recover-deleted-files-folders">Recover deleted files and folders</a>, subject to account retention. This review itself does not delete or restore anything.</p><script>const input=document.querySelector("#search"),articles=[...document.querySelectorAll("article")];function filter(){let n=0;for(const a of articles){a.hidden=!a.dataset.search.includes(input.value.toLocaleLowerCase());if(!a.hidden)n++}document.querySelector("#count").textContent=n+" books shown"}input.addEventListener("input",filter);filter()</script></html>')
(OUT/'review.html').write_text(''.join(parts))
print(json.dumps({'summary':summary,'manifest_sha256':digest,'merged_groups':[b for b in books if len(b['original_titles'])>1]},indent=2,ensure_ascii=False))
