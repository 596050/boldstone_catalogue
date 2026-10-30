"""Record an owner-rejected navigation proposal without changing catalogue data."""
import copy,hashlib,json,os
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];ROOT=B.parent
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();now=lambda:datetime.now(timezone.utc).isoformat();rel=lambda p:str(Path(p).relative_to(B))
def write(p,x):
 p=Path(p);tmp=p.with_name(p.name+'.withdrawal-tmp');tmp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');os.replace(tmp,p)
assert not(H/'publication-receipt.json').exists()
pointer=B/'current-master.json';old=read(pointer);assert sha(pointer)=='b207193239cad787ecd35807f8ddcae4da6fb50744b7111ff4c445ed73ae3fe8'
session=Path('/Users/tprice/.codex/sessions/2026/10/20/rollout-2026-10-20T15-20-57-01a159af-d182-7393-9201-a2ac7ccba14a.jsonl')
with session.open('rb')as f:
 first=json.loads(f.readline());assert first['type']=='session_meta'and first['payload']['id']=='01a159af-d182-7393-9201-a2ac7ccba14a'
 f.seek(522981218);line=f.readline()
assert hashlib.sha256(line).hexdigest()=='95ce2d48a16817934bd4f40aab8ddef476b2eb1a8f055a0a8fccb2e6544764e2'
event=json.loads(line);assert event['type']=='response_item'and event['payload']['role']=='user'
text='\n'.join(x.get('text','')for x in event['payload']['content']);assert text.startswith('These are not entirely correct selections for in situ:')
evidence={'source_thread_id':first['payload']['id'],'transcript_path':str(session),'record_byte_offset':522981218,'record_line_sha256':hashlib.sha256(line).hexdigest(),'source_timestamp_utc':event['timestamp'],'recorded_utc':now(),'owner_message_verbatim':text,'scope':'Exact nine-photo Moonwave proposal is not approved. No alternative classification is inferred.'};write(H/'owner-withdrawal-evidence.json',evidence)
D=ROOT/'reports/dropbox-moonwave-nine-in-situ-review-20261024T144130Z';assert sha(D/'review-seal.json')=='748bd16db2130c3a35e38e6aee4665cac8d122116b88792a178c28eb923310a4'
controls=[B/'components/reviews/specification_review_progress.json',B/'components/checkpoint.json',B/'checkpoint.json'];inputs={'pointer':pointer,'register':B/old['register'],'workbook':B/old['workbook'],**{f'control_{i}':p for i,p in enumerate(controls)}}
(H/'inputs').mkdir(exist_ok=True);m={}
for k,p in inputs.items():
 snap=H/'inputs'/(k+'.before');snap.write_bytes(p.read_bytes());m[k]={'path':str(p),'snapshot':str(snap),'sha256':sha(p)}
write(H/'input-manifest.json',m)
decision={'status':'WITHDRAWN_OWNER_REJECTED_SELECTION_REVIEW_REQUIRED','recorded_utc':now(),'owner_source_timestamp_utc':event['timestamp'],'owner_evidence':rel(H/'owner-withdrawal-evidence.json'),'owner_evidence_sha256':sha(H/'owner-withdrawal-evidence.json'),'proposal_review':str(D/'review-nine-proposed-moonwave-moves.html'),'proposal_review_seal':str(D/'review-seal.json'),'proposal_review_seal_sha256':sha(D/'review-seal.json'),'native_moves_applied':0,'withdrawn_expected_folder_count_projection':'White86 to77 and InSitu13 to22 must not be used as current counts','replacement_review_owner_thread':'01a159af-d182-7393-9201-a2ac7ccba14a','new_owner_question_in_this_thread':False,'current_role_selections_and_specs_changed':False}
p=copy.deepcopy(old);p.update(recorded_utc=now(),publication_receipt=rel(H/'publication-receipt.json'),latest_moonwave_proposal_withdrawal=decision)
p['next_catalogue_actions']=copy.deepcopy(old['next_catalogue_actions']);p['next_catalogue_actions'][0]='The nine-photo Moonwave move proposal is WITHDRAWN after the owner rejected its selections. No moves applied. The directory session owns the replacement mounted-view versus detail review and its single owner question. Do not use the withdrawn proposed folder counts or apply that plan.'
p['latest_master_metadata_change']={'status':'OWNER_WITHDRAWAL_RECORDED_METADATA_ONLY','path':rel(H/'publication-receipt.json'),'catalogue_register_workbook_and_audit_unchanged':True}
assert p['register_sha256']==old['register_sha256']and p['workbook_sha256']==old['workbook_sha256']
write(H/'prepared-pointer.json',p);updates={}
for dest in controls:
 d=read(dest);assert d['current_master_catalogue']==old;d.update(updated_utc=now(),current_master_catalogue=copy.deepcopy(p),next_catalogue_actions=copy.deepcopy(p['next_catalogue_actions']),latest_moonwave_proposal_withdrawal=copy.deepcopy(decision),latest_master_metadata_change=copy.deepcopy(p['latest_master_metadata_change']));updates[dest]=d
for k,x in m.items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
for dest,d in updates.items():write(dest,d)
write(pointer,p)
assert read(pointer)==p and sha(B/p['register'])==old['register_sha256']and sha(B/p['workbook'])==old['workbook_sha256']
for dest,d in updates.items():assert read(dest)==d and d['current_master_catalogue']==p
r={'status':'PASS_PUBLISHED_METADATA_ONLY_OWNER_WITHDRAWAL','recorded_utc':p['recorded_utc'],'preceding_publication_receipt':old['publication_receipt'],'preceding_pointer_sha256':m['pointer']['sha256'],'current_master_pointer_sha256':sha(pointer),'register':str(B/p['register']),'register_sha256':p['register_sha256'],'workbook':str(B/p['workbook']),'workbook_sha256':p['workbook_sha256'],'catalogue_data_and_workbook_unchanged':True,'controls_sha256':{str(x):sha(x)for x in controls},'decision':decision,'active_options':188,'retained_component_ids':112,'working_design_groups':110,'native_or_platform_writes':0};write(H/'publication-receipt.json',r);print(json.dumps(r,indent=2))
