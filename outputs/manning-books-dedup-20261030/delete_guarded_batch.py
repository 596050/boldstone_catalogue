from datetime import datetime, timezone
from pathlib import Path
import argparse, hashlib, json, os, sys, time

PROJECT=Path('/Users/tprice/Documents/boldstone')
OUT=Path(__file__).resolve().parent
SHA='89da063cb5402204dfc8ac55ad4dced916e2eb3392559133ff183a6b3054846c'
ROOT='/TOM Apps/Manning Books'
parser=argparse.ArgumentParser()
parser.add_argument('--batch',type=int,required=True,choices=range(1,5))
parser.add_argument('--apply',action='store_true')
args=parser.parse_args()
if not args.apply:raise SystemExit('Use --apply for the exact user-approved deletion batch.')
body=(OUT/'deletion-review.json').read_bytes()
assert hashlib.sha256(body).hexdigest()==SHA
plan=json.loads(body)
assert len(plan['removals'])==4403 and len(plan['keepers'])==179 and not plan['folders']
assert sum(r['size'] for r in plan['removals'])==69700643226
assert json.loads((OUT/'deletion-preflight.json').read_text())['status']=='PASS'
previous=json.loads((OUT/f'deletion-batch-{args.batch-1}-completion.json').read_text())
assert previous['status']=='completed' and previous['result_type']=='delete'
assert all(r['entry_status']=='success' for r in previous['delete_result']['entries']), 'Resolve the prior batch before another submission'
rows=plan['removals'][args.batch*1000:(args.batch+1)*1000]
request_path=OUT/f'deletion-batch-{args.batch}-request.json'
state_path=OUT/f'deletion-batch-{args.batch}-native-state.json'
completion_path=OUT/f'deletion-batch-{args.batch}-completion.json'
assert not request_path.exists() and not state_path.exists() and not completion_path.exists(), 'Existing submission record: inspect it; do not resubmit'
sys.path.insert(0,str(PROJECT/'catalogue-review'))
from delete_dropbox import connection
from dropbox.common import PathRoot
from dropbox.files import DeleteArg,FileMetadata

def stamp():return datetime.now(timezone.utc).isoformat()
def save(path,data):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    os.replace(temporary,path)
def listing(c):
    p=c.files_list_folder('',recursive=True,limit=2000,include_deleted=False)
    a=list(p.entries)
    while p.has_more:p=c.files_list_folder_continue(p.cursor);a.extend(p.entries)
    return {m.id:m for m in a if hasattr(m,'id')}
def assert_binding(m,r):
    assert isinstance(m,FileMetadata), ('not a file',r['id'])
    assert all(getattr(m,k)==r[k] for k in ('id','rev','size','content_hash','path_lower')), ('metadata changed',r['id'])

with connection(PROJECT) as (client, verified_catalogue_root):
    scoped=client.with_path_root(PathRoot.namespace_id('10782830832'))
    root=scoped.files_get_metadata('id:cnqzTNngPVsAAAAAAAgI_w')
    assert root.id=='id:cnqzTNngPVsAAAAAAAgI_w' and root.name=='Manning Books'
    current=listing(scoped)
    for r in rows+plan['keepers']:assert_binding(current.get(r['id']),r)
    request={'manifest_sha256':SHA,'batch_index':args.batch,'status':'SUBMITTING','method':'Dropbox files/delete_batch with parent_rev guards','submitted_utc':stamp(),'ids':[r['id'] for r in rows],'parent_revs':{r['id']:r['rev'] for r in rows},'user_authorization':'do it: - Remove 4,403 files, totalling 69.7 GB'}
    with request_path.open('x') as stream:json.dump(request,stream,indent=2)
    state={'status':'SUBMITTING','batch':args.batch,'files':len(rows),'started_utc':stamp()}
    save(state_path,state)
    try:
        launch=scoped.files_delete_batch([DeleteArg(path=r['id'],parent_rev=r['rev']) for r in rows])
    except Exception as exc:
        state.update(status='SUBMISSION_UNCONFIRMED_DO_NOT_RETRY',error_type=type(exc).__name__,error=str(exc),updated_utc=stamp())
        save(state_path,state)
        raise
    if launch.is_complete():
        result=launch.get_complete()
    elif launch.is_async_job_id():
        job=launch.get_async_job_id()
        state.update(status='IN_PROGRESS',async_job_id=job,updated_utc=stamp())
        save(state_path,state)
        print(json.dumps({'batch':args.batch,'status':'IN_PROGRESS','files':len(rows)}),flush=True)
        polls=0
        while True:
            time.sleep(5)
            checked=scoped.files_delete_batch_check(job)
            polls+=1
            if checked.is_complete():result=checked.get_complete();break
            if checked.is_failed():
                state.update(status='ASYNC_JOB_FAILED',error=str(checked.get_failed()),updated_utc=stamp())
                save(state_path,state)
                raise RuntimeError(state['error'])
            state.update(status='IN_PROGRESS',polls=polls,updated_utc=stamp())
            save(state_path,state)
            if polls%6==0:print(json.dumps({'batch':args.batch,'status':'IN_PROGRESS','polls':polls}),flush=True)
    else:raise RuntimeError('Unexpected delete launch tag: inspect the submission record before any further action')
    assert len(result.entries)==len(rows)
    records=[]
    for i,(entry,r) in enumerate(zip(result.entries,rows)):
        if entry.is_success():
            m=entry.get_success().metadata
            assert_binding(m,r)
            displayed=m.path_display if m.path_display.startswith(ROOT+'/') else ROOT+m.path_display
            obj={'name':m.name,'file_id':m.id,'object_type':'file','path_display':displayed,'native_path_display':m.path_display,'file':{'size':m.size},'modified_time':m.server_modified.isoformat(),'rev':m.rev,'content_hash':m.content_hash}
            records.append({'entry_index':i,'entry_status':'success','object':obj})
        else:
            records.append({'entry_index':i,'entry_status':'failed','failure':{'error_code':'native_api_failure','message':str(entry.get_failure())}})
    receipt={'isError':False,'status':'completed','result_type':'delete','method':'Dropbox files/delete_batch with parent_rev guards','completed_utc':stamp(),'delete_result':{'entries':records}}
    save(completion_path,receipt)
    counts={s:sum(e['entry_status']==s for e in records) for s in ('success','failed')}
    state.update(status='COMPLETED',counts=counts,completed_utc=stamp())
    save(state_path,state)
    print(json.dumps({'batch':args.batch,'status':'COMPLETED','counts':counts}),flush=True)
    if counts['failed']:raise SystemExit(2)
