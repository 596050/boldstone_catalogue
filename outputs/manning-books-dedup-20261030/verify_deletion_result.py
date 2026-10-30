from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib, html, json, sys

PROJECT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).resolve().parent
body=(OUT/'deletion-review.json').read_bytes()
SHA='89da063cb5402204dfc8ac55ad4dced916e2eb3392559133ff183a6b3054846c'
assert hashlib.sha256(body).hexdigest()==SHA
plan=json.loads(body)
removed={r['id']:r for r in plan['removals']}
keepers={r['id']:r for r in plan['keepers']}
successes=[]
failures=[]
for i in range(5):
    req=json.loads((OUT/f'deletion-batch-{i}-request.json').read_text())
    response=json.loads((OUT/f'deletion-batch-{i}-completion.json').read_text())
    assert req['manifest_sha256']==SHA
    assert not response.get('isError') and response['status']=='completed' and response['result_type']=='delete'
    entries=response['delete_result']['entries']
    assert len(entries)==len(req['ids'])
    assert {r['entry_index'] for r in entries}==set(range(len(req['ids'])))
    for entry in entries:
        fid=req['ids'][entry['entry_index']]
        original=removed[fid]
        if entry['entry_status']!='success':
            failures.append({'id':fid,'path':original['display_path'],'failure':entry.get('failure')})
            continue
        obj=entry['object']
        assert obj['file_id']==fid and obj['object_type']=='file' and obj['file'].get('size',0)==original['size']
        successes.append({'id':fid,'path':obj.get('path_display') or obj.get('path') or fid,'approved_path':original['display_path'],'size':original['size'],'keeper_id':original['keeper_id'],'keeper_path':original['keeper_path'],'book':original['book'],'entry_status':'success','batch':i,'confirmation_source':entry.get('confirmation_source','Dropbox terminal delete-batch receipt'),'deleted_metadata':entry.get('deleted_metadata'),'receipt_object':obj})
assert len({r['id'] for r in successes})==len(successes)
assert set(r['id'] for r in successes)<=set(removed)

sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.files import FileMetadata
def info(m):
    d={'id':m.id,'name':m.name,'object_type':'file' if isinstance(m,FileMetadata) else 'folder','path_display':m.path_display,'path_lower':m.path_lower}
    for key in ('rev','size','content_hash'):
        if hasattr(m,key):d[key]=getattr(m,key)
    return d
with connection(PROJECT) as (client, verified_catalogue_root):
    scoped=client.with_path_root(PathRoot.namespace_id('10782830832'))
    root=scoped.files_get_metadata('id:cnqzTNngPVsAAAAAAAgI_w')
    assert root.id=='id:cnqzTNngPVsAAAAAAAgI_w' and root.name=='Manning Books'
    page=scoped.files_list_folder('',recursive=True,limit=2000,include_deleted=False)
    entries=list(page.entries)
    while page.has_more:
        page=scoped.files_list_folder_continue(page.cursor)
        entries.extend(page.entries)
    current={r.id:info(r) for r in entries if hasattr(r,'id')}
    original_inventory=json.loads((OUT/'native-inventory.json').read_text())
    expected_folders={r['id'] for r in original_inventory['entries'] if r['object_type']=='folder'}
    current_folders={fid for fid,r in current.items() if r['object_type']=='folder'}
    missing_folders=sorted(expected_folders-current_folders)
    keeper_errors=[]
    for fid,k in keepers.items():
        now=current.get(fid)
        if not now:keeper_errors.append({'id':fid,'error':'missing'})
        else:
            wrong=[key for key in ('rev','size','content_hash','path_lower') if now.get(key)!=k[key]]
            if wrong:keeper_errors.append({'id':fid,'changed_fields':wrong})
    still_present=[fid for fid in removed if fid in current]
    extras=[r for fid,r in current.items() if r['object_type']=='file' and fid not in keepers and fid not in removed]
    passed=len(successes)==4403 and not failures and not keeper_errors and not still_present and not missing_folders
    summary={'status':'PASS_EXACT_APPROVED_DELETION_AND_READBACK' if passed else 'PARTIAL_OR_READBACK_CONCERN','approved_manifest_sha256':SHA,'completed_utc':datetime.now(timezone.utc).isoformat(),'approved_files':4403,'deleted_files':len(successes),'deleted_bytes':sum(r['size'] for r in successes),'keepers_verified':len(keepers)-len(keeper_errors),'current_files':sum(r['object_type']=='file' for r in current.values()),'folders_preserved':len(expected_folders&current_folders),'failed_files':len(failures),'pending_files':0,'skipped_files':0,'missing_or_changed_keepers':keeper_errors,'approved_removals_still_present':still_present,'missing_original_folders':missing_folders,'new_files_preserved':extras,'folders_deleted':0}
    receipt_notes=['The connector accepted the first 1,000-file asynchronous deletion, but its completion-status endpoint returned INVALID_ARGUMENT. Every one of those exact file IDs was independently confirmed deleted using native Dropbox DeletedMetadata. That batch was never resubmitted.','The remaining batches used Dropbox files/delete_batch with parent_rev guards and terminal per-file receipts.']
    result={'summary':summary,'receipt_notes':receipt_notes,'deleted_files':successes,'failed_files':failures,'retained_files':[keepers[fid] for fid in keepers if fid in current],'current_inventory':list(current.values()),'recovery_url':'https://help.dropbox.com/delete-restore/recover-deleted-files-folders'}
    (OUT/'deletion-result.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(summary,indent=2))
    if not passed:raise SystemExit(2)
    e=html.escape
    parts=['<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Manning Books deletion receipt</title><style>body{font:15px/1.5 system-ui;max-width:1300px;margin:40px auto;padding:0 24px;color:#182433}table{border-collapse:collapse;width:100%;font-size:13px}th,td{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #d9e1eb}td{overflow-wrap:anywhere;max-width:650px}input{font:inherit;padding:10px;width:min(95%,640px)}.success{padding:18px;background:#e8f5ec}small{color:#536478}</style><h1>Manning Books: completed deletion</h1>']
    parts.append(f'<p class="success"><strong>Deleted {len(successes):,} approved PDFs ({summary["deleted_bytes"]/1e9:.2f} GB).</strong><br>Verified all 179 retained PDFs with unchanged identities, revisions, sizes and content hashes. All 209 folders remain. Failed: 0. Skipped: 0. Pending: 0.</p><p>Completed {e(summary["completed_utc"])}<br>Manifest SHA-256: <code>{SHA}</code></p><p><a href="deletion-result.json">Full machine-readable receipt and final inventory</a> · <a href="review.html">Original exact-item review</a> · <a href="https://www.dropbox.com/home/TOM%20Apps/Manning%20Books">Open Manning Books</a></p><p>Deleted files can be restored using <a href="https://help.dropbox.com/delete-restore/recover-deleted-files-folders">Dropbox Deleted files recovery</a>, subject to the account retention period.</p><h2>Exact deleted files</h2><p>Each row is supported by a terminal batch receipt or a native deleted-file record, plus absence from a fresh folder listing.</p><input id="search" placeholder="Filter book or path" aria-label="Filter deleted files"><p id="count"></p><table><thead><tr><th>Book</th><th>Deleted path and identity</th><th>Retained replacement</th><th>Bytes</th></tr></thead><tbody>')
    parts.append('<tr><td colspan="4"><strong>Receipt note:</strong> '+e(receipt_notes[0])+'</td></tr>')
    for r in sorted(successes,key=lambda x:x['approved_path'].casefold()):
        parts.append(f'<tr class="file" data-search="{e((r["book"]+" "+r["path"]).casefold(),quote=True)}"><td>{e(r["book"])}</td><td>{e(r["path"])}<br><small>{e(r["id"])} · success</small></td><td>{e(r["keeper_path"])}</td><td>{r["size"]:,}</td></tr>')
    parts.append('</tbody></table><h2>Retained files</h2><table><thead><tr><th>Book</th><th>Verified retained path</th><th>Version</th></tr></thead><tbody>')
    for k in plan['keepers']:
        version=f'Edition {k["edition"]}; '+('published' if k['published'] else f'MEAP v{k["meap_version"]}')
        parts.append(f'<tr><td>{e(k["book"])}</td><td>{e(k["display_path"])}<br><small>{e(k["id"])} · rev {e(k["rev"])}</small></td><td>{e(version)}</td></tr>')
    parts.append('</tbody></table><script>const input=document.querySelector("#search"),rows=[...document.querySelectorAll("tr.file")];function filter(){let n=0;for(const r of rows){r.hidden=!r.dataset.search.includes(input.value.toLocaleLowerCase());if(!r.hidden)n++}document.querySelector("#count").textContent=n+" deleted files shown"}input.addEventListener("input",filter);filter()</script></html>')
    (OUT/'deletion-result.html').write_text(''.join(parts))
