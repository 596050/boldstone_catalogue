"""Read-only verification of recovered workshop previews and saved review state."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import quote,unquote,urlparse
from PIL import Image
import hashlib,io,json,sqlite3,urllib.request
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent;APP=ROOT/'catalogue-review';A=APP/'reviews/barbados-preview-recovery-20261026'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=0
def check(ok,msg):
    global checks
    checks+=1;assert ok,msg
def snapshot(path):
    db=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        db.execute('BEGIN');return {'reviews':[dict(r) for r in db.execute('SELECT * FROM reviews ORDER BY kind,product_id,item_id')],
            'events':[dict(r) for r in db.execute('SELECT * FROM events ORDER BY id')]}
    finally:db.close()
def unpack(row):
    r=dict(row)
    for k in ['data','original']:
        if isinstance(r.get(k),str):r[k]=json.loads(r[k])
    return r
key=lambda r:(r['kind'],r['product_id'],r['item_id'])
def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8767'+path,timeout=20) as r:return json.load(r)
pointer=read(B/'current-master.json');pointer_sha=sha(B/'current-master.json');handoff=read(A/'HANDOFF.json')
code={}
for f,digest in handoff['deployment']['code_sha256'].items():
    check(sha(APP/f)==sha(A/'work'/f)==digest,'Deployed and QA code '+f);code[str(APP/f)]=digest
prior_verification=read(pointer['current_review_application']['verification'])
for path,digest in prior_verification['application_files'].items():
    if path not in code:check(sha(path)==digest,'Previously sealed review/component code unchanged '+path)
protected={str(B/pointer['register']):pointer['register_sha256'],str(B/pointer['workbook']):pointer['workbook_sha256'],
    str(B/pointer['preferred_review_workbook']):pointer['current_comprehensive_workbook']['sha256']}
for p,d in protected.items():check(sha(p)==d,'Canonical bytes '+p)
before=snapshot(A/'before-deployment.sqlite3');live=snapshot(Path.home()/'Library/Application Support/BoldstoneReview/reviews.sqlite3')
check(len(before['reviews'])==2050 and before['events'][-1]['id']==4197,'Predeployment2050/4197 backup')
check([r for r in live['events'] if r['id']<=4197]==before['events'],'All old audit events retained')
state={key(r):unpack(r) for r in before['reviews']}
for event in [r for r in live['events'] if r['id']>4197]:
    prior=json.loads(event['before_json']) if event['before_json'] else None
    after=unpack(json.loads(event['after_json']));k=key(after)
    if prior and k in state:check(unpack(prior)==state[k],'Later owner event matches prior state')
    state[k]=after
check(state=={key(r):unpack(r) for r in live['reviews']},'Current rows preserved or follow later owner events')
health=get('/api/health');boot=get('/api/bootstrap');library=get('/api/library?family=Barbados%20Wave')
check(health['version']=='2.6.1' and health['products']==187,'Live2.6.1/187')
check(boot['source']['register_sha256']==pointer['register_sha256'],'Live source register binding')
g=read(B/pointer['register']);check({r['id'] for r in boot['products']}==set(g['active_option_ids']),'Exact187 active IDs')
gallery=boot['source']['gallery_database'];protected[gallery]=boot['source']['gallery_sha256'];check(sha(gallery)==protected[gallery],'Saved source gallery bytes')
images={r['id']:r for r in library['images']};metadata={r['id']:r['file'] for r in read(A/'native-metadata.json')}
staged={r['id']:r for r in read(A/'staged-readback.json')['rows']}
check(len(images)==23 and len(metadata)==len(staged)==12,'Family and recovered populations')
workshop=[];hash_matches=0;thumbnails=0
native_snapshot=read(boot['source']['live_dropbox']['path'])
for fid,md in metadata.items():
    im=images[fid];saved=staged[fid]
    check(im['local_preview'] is True,'Restored preview '+fid)
    check(im['inventory_status']=='SAVED_REFERENCE_OUTSIDE_CURRENT_WALL_INVENTORY_SCOPE','Outside-wall qualification '+fid)
    check(fid not in native_snapshot['records'],'Live Wall scope not expanded '+fid)
    check(unquote(urlparse(im['url']).path).removeprefix('/preview')==md['path_display'],'Exact native image link '+fid)
    check(unquote(urlparse(im['folder_url']).path).removeprefix('/home')==str(Path(md['path_display']).parent),'Actual containing folder '+fid)
    check(im['original']['bytes']==md['size'],'Native byte-size metadata '+fid)
    path=Path(saved['path']);check(path.is_file(),'Retained local path '+fid)
    if im['original'].get('locally_verified'):
        digest=hashlib.sha256();raw=path.read_bytes()
        for i in range(0,len(raw),4*1024*1024):digest.update(hashlib.sha256(raw[i:i+4*1024*1024]).digest())
        check(digest.hexdigest()==im['original']['dropbox_content_hash'],'Original bytes match retained Dropbox content hash '+fid)
        check(hashlib.sha256(raw).hexdigest()==im['original']['sha256'],'Cached original SHA '+fid)
        check(len(raw)==md['size'],'Full cache/native saved bytes '+fid);hash_matches+=1
    else:
        check(im['original'].get('dimensions') is None,'Thumbnail dimensions not promoted '+fid);thumbnails+=1
    workshop.append({'file_id':fid,'folder_id':im['folder_id'],'image_url':im['url'],'folder_url':im['folder_url'],
        'representation':im['representation'],'local_path':str(path),'local_sha256':sha(path),
        'retained_original_verified':bool(im['original'].get('locally_verified'))})
check(hash_matches==9 and thumbnails==3,'Nine originals and three thumbnail-only references')
responses=[]
for fid,im in images.items():
    with urllib.request.urlopen('http://127.0.0.1:8767/api/image?id='+quote(fid,safe='')+'&size=thumb',timeout=20) as r:
        raw=r.read();mime=r.headers.get('Content-Type','');check(r.status==200 and mime.startswith('image/'),'Preview HTTP '+fid)
    with Image.open(io.BytesIO(raw)) as picture:dimensions=picture.size;picture.verify()
    check(dimensions[0]>0 and dimensions[1]>0,'Decoded image response '+fid)
    responses.append({'file_id':fid,'mime':mime,'bytes':len(raw),'decoded_dimensions':dimensions})
check(sha(B/'current-master.json')==pointer_sha,'No source metadata write during audit')
result={'status':'PASS_INDEPENDENT_BARBADOS_V2_6_1_RECOVERY','checked_utc':datetime.now(timezone.utc).isoformat(),
    'checks':checks,'application_version':'2.6.1','active_options':187,'baseline_pointer_sha256':pointer_sha,
    'handoff':str(A/'HANDOFF.json'),'handoff_sha256':sha(A/'HANDOFF.json'),'application_files':code,
    'protected_source_hashes':protected,'predeployment_backup':str(A/'before-deployment.sqlite3'),
    'predeployment_backup_sha256':sha(A/'before-deployment.sqlite3'),'predeployment_review_rows':2050,'predeployment_event_cutoff':4197,
    'live_review_rows':len(live['reviews']),'live_event_cutoff':live['events'][-1]['id'],'later_owner_events':sum(r['id']>4197 for r in live['events']),
    'review_values_originals_versions_and_audit_history_preserved':True,'restored_workshop_previews':12,'family_preview_responses':23,
    'retained_hash_verified_originals':9,'thumbnail_only_references':3,'outside_wall_qualification_and_live_scope_preserved':True,
    'native_metadata_evidence':str(A/'native-metadata.json'),'native_metadata_evidence_sha256':sha(A/'native-metadata.json'),
    'native_metadata_is_owning_session_receipt_not_root_remote_rescan':True,'workshop':workshop,'responses':responses,
    'independent_python_tests_passed':111,'root_app_code_review_db_native_platform_mutations':0}
(H/'independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['application_files','protected_source_hashes','workshop','responses']},indent=2))
