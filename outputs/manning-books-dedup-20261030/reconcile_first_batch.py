from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,sys,time

PROJECT=Path('/Users/tprice/Documents/boldstone');OUT=Path(__file__).resolve().parent
SHA='89da063cb5402204dfc8ac55ad4dced916e2eb3392559133ff183a6b3054846c'
body=(OUT/'deletion-review.json').read_bytes();assert hashlib.sha256(body).hexdigest()==SHA
plan=json.loads(body);rows=plan['removals'][:1000]
req=json.loads((OUT/'deletion-batch-0-request.json').read_text());assert req['ids']==[r['id'] for r in rows]
submitted=json.loads((OUT/'deletion-batch-0-response.json').read_text());assert submitted['status']=='in_progress'
sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.files import DeletedMetadata
from dropbox.exceptions import RateLimitError
results=[]
with connection(PROJECT) as (client,verified_catalogue_root):
    c=client.with_path_root(PathRoot.namespace_id('10782830832'))
    root=c.files_get_metadata('id:cnqzTNngPVsAAAAAAAgI_w')
    assert root.id=='id:cnqzTNngPVsAAAAAAAgI_w' and root.name=='Manning Books'
    def check(pair):
        i,r=pair
        try:
            for attempt in range(3):
                try:m=c.files_get_metadata(r['id'],include_deleted=True);break
                except RateLimitError as exc:
                    if attempt==2:raise
                    time.sleep(min(max(exc.backoff or 1,1),55))
            assert isinstance(m,DeletedMetadata), 'File is not deleted'
            assert m.path_lower==r['path_lower'] and m.name==r['name'], 'Deleted identity path differs from review'
            return {'entry_index':i,'entry_status':'success','confirmation_source':'Native Dropbox files/get_metadata(include_deleted=True) requested by stable file ID','deleted_metadata':{'tag':'deleted','name':m.name,'path_display':m.path_display,'path_lower':m.path_lower},'checked_utc':datetime.now(timezone.utc).isoformat(),'object':{'file_id':r['id'],'object_type':'file','name':r['name'],'path_display':r['display_path'],'file':{'size':r['size']},'metadata_source':'Approved and individually verified pre-deletion file metadata; deletion state separately confirmed by native DeletedMetadata'}}
        except Exception as exc:
            return {'entry_index':i,'entry_status':'failed','failure':{'error_code':type(exc).__name__,'message':str(exc)}}
    with ThreadPoolExecutor(max_workers=10) as pool:
        for future in as_completed([pool.submit(check,pair) for pair in enumerate(rows)]):
            results.append(future.result())
            if len(results)%100==0:print(json.dumps({'first_batch_deleted_records_verified':len(results),'errors':sum(r['entry_status']!='success' for r in results)}),flush=True)
results.sort(key=lambda r:r['entry_index'])
receipt={'isError':False,'status':'completed','result_type':'delete','receipt_kind':'NATIVE_DELETED_METADATA_RECONCILIATION','method':'MCP asynchronous deletion; all exact file identities confirmed deleted through native Dropbox metadata','mcp_terminal_job_receipt':'Unavailable: check_job_status returned INVALID_ARGUMENT twice after the approved files had disappeared. No deletion was resubmitted.','completed_utc':datetime.now(timezone.utc).isoformat(),'delete_result':{'entries':results}}
(OUT/'deletion-batch-0-reconciliation.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
assert len(results)==1000 and all(r['entry_status']=='success' for r in results), 'First batch not fully reconciled'
completion=OUT/'deletion-batch-0-completion.json'
with completion.open('x') as stream:json.dump(receipt,stream,indent=2,ensure_ascii=False)
print(json.dumps({'status':'PASS_1000_EXACT_IDENTITIES_CONFIRMED_DELETED','deleted':1000}),flush=True)
