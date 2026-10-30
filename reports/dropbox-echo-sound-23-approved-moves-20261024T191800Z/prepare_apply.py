import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

P=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
PLAN=ROOT/'reports/dropbox-echo-sound-exact-filing-plan-20261024T184806Z'
SOURCE=ROOT/'reports/dropbox-wall-only-chiswick-echo-bone-review-20261024T183336Z'
SCOPE='/BOLDSTONE MASTER/Products/01 Wall Sculptures'
def read(path):return json.loads(Path(path).read_text())
def write(name,data):(P/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fq(path):return path.split('/',1)[1] if path.startswith('ns:') else path
def hashes(data):return hashlib.sha256(data).hexdigest(),hashlib.sha256(b''.join(hashlib.sha256(data[i:i+4194304]).digest() for i in range(0,len(data),4194304))).hexdigest()

seal=read(PLAN/'plan-seal.json')
for r in seal['files']:
    f=PLAN/r['path'];assert f.stat().st_size==r['size'] and sha(f)==r['sha256']
proposal=read(PLAN/'exact-23-move-proposal.json')
assert sha(PLAN/'exact-23-move-proposal.json')=='7058d0280986adc2190be172a0274dce5f3513c88e95a1b87ceb60f04b33d97f'
before=read(P/'fresh-native-before-and-approved-proposal.json')
assert before['proposal']==proposal
current=before['listing'];prior=read(PLAN/'fresh-closing-native-listing.json')['listing']
assert not current['has_more'] and not prior['has_more']
native={x['file_id']:x for x in current['entries']}
assert native=={x['file_id']:x for x in prior['entries']}
assert len(native)==189
files={k:v for k,v in native.items() if v['object_type']=='file'}
folders={k:v for k,v in native.items() if v['object_type']=='folder'}
assert len(files)==180 and len(folders)==9
assert all(fq(x['path']).startswith(SCOPE+'/Echo Sound/') for x in native.values())
metadata={x.get('file',x.get('folder',{})).get('id'):x for x in before['metadata']}
selected=proposal['moves'];assert len(selected)==23
for move in selected:
    n=files[move['file_id']];m=metadata[move['file_id']]
    assert m['metadata_type']=='file' and m['file']['name']==move['original_name']
    assert fq(n['path'])==m['file']['path_display']==move['source_folder_path']+'/'+move['original_name']
    assert n['file']['size']==m['file']['size']==move['size']
    assert fq(folders[move['destination_folder_id']]['path'])==move['destination_folder_path']
    assert metadata[move['destination_folder_id']]['metadata_type']=='folder'
    assert metadata[move['destination_folder_id']]['folder']['path_display']==move['destination_folder_path']
    assert not any(fq(x['path']).lower()==move['destination_path'].lower() for x in native.values())

nativehash={r['id']:r for r in read(P/'fresh-prewrite-native-hash-metadata.json')}
originals=read(SOURCE/'echo-sound-verified-originals-and-links.json')
assert set(nativehash)==set(files)=={r['id'] for r in originals}
verified=[]
for r in originals:
    n=nativehash[r['id']];data=Path(r['local_path']).read_bytes();sh,dh=hashes(data)
    assert len(data)==r['size']==n['size']==files[r['id']]['file']['size']
    assert sh==r['sha256'] and dh==r['dropbox_content_hash']==n['content_hash']
    assert n['name']==files[r['id']]['name'] and n['path']==files[r['id']]['path']
    verified.append({'file_id':r['id'],'name':r['name'],'local_path':r['local_path'],'size':len(data),'sha256':sh,'dropbox_content_hash':dh,'fresh_native_hash_match':True})
assert sum(r['size'] for r in verified)==1092139502
write('all-180-original-prewrite-hashes.json',verified)

pointer_path=ROOT/'sculpture-catalogue/current-master.json';pointer=read(pointer_path)
register_path=ROOT/'sculpture-catalogue'/pointer['register'];register=read(register_path)
options=[o for o in register['options'] if o.get('family')=='Echo Sound']
prior_options=read(PLAN/'protected-selected-options-current.json')['options']
assert options==prior_options
protected={o[k] for o in options for k in ['file_id','context_file_id']}
assert not protected.intersection(m['file_id'] for m in selected)
write('protected-catalogue-references-before.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'pointer':pointer,'pointer_sha256':sha(pointer_path),'register_sha256':sha(register_path),'options':options,'source_offer_edges':[x for x in register.get('source_offer_edges',[]) if any(v in json.dumps(x) for v in protected)]})
write('reversion-plan-not-executed.json',{'status':'NOT_EXECUTED','operation':'move','entries':[{'source_path':m['file_id'],'destination_path':m['undo_destination_path']} for m in selected],'folders_to_create':[]})
request={'autorename':False,'entries':[{'source_path':m['file_id'],'destination_path':m['destination_path']} for m in selected]}
write('approved-move-request.json',request)
guard={'recorded_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_READY_TO_APPLY_EXACT_23_OWNER_APPROVED_MOVES','sealed_proposal_sha256':sha(PLAN/'exact-23-move-proposal.json'),'owner_approval_receipt_sha256':sha(P/'owner-approval.json'),'native_objects':189,'family_files':180,'family_folders':9,'family_bytes':1092139502,'actual_existing_originals_rehashed':180,'fresh_native_content_hash_matches':180,'new_binary_downloads':0,'metadata_objects':25,'full_selected_option_records_unchanged':4,'selected_file_ids_in_move_set':0,'destination_collisions':0,'move_entries':23,'folders_to_create':[]}
write('prewrite-guard-validation.json',guard)
print(json.dumps(guard,indent=2))
