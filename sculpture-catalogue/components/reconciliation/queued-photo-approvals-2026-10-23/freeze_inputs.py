import json,hashlib,shutil
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;B=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
p=read(B/'current-master.json');prior=(B/p['register']).parent;sources={'master_pointer':B/'current-master.json','master_workbook':B/p['workbook'],'master_register':B/p['register'],'audit':Path(p['latest_image_coverage_audit']['path']),'report_assets':prior/'current-assets.json','report_reviews':prior/'photo-review-queue.json','guided_state':prior/'guided-owner-review-state.json','pending_followups':B/p['queued_followup_packets']['path'],'review_progress':B/'components/reviews/specification_review_progress.json','component_checkpoint':B/'components/checkpoint.json','root_checkpoint':B/'checkpoint.json','squarespace_hold':B/'components/parallel-reviews/listing-execution-2026-10-21/SQUARESPACE_WRITE_HOLD.json'}
queue=read(sources['pending_followups']);targets=['BSI-B1DCB5B08396','BSI-725A77437026','BSI-D7C2FC84A86B','BSI-63B177B06578','BSI-ADD5F3BEFCF5','BSI-70BDE00F2855','BSI-923D5E50A898'];packets={}
for x in queue['entries']:
 if x.get('product_id')in targets and x['kind']in ['owner-image-approval','owner-image-role-approval']:
  f=Path(x['path']);assert sha(f)==x['sha256'];packets[x['product_id']]=str(f);sources['approval_'+x['product_id']]=f
  seal=f.with_name(f.stem+'-seal.json')
  if seal.is_file():
   d=read(seal);assert sha(f)==d['sha256'];sources['seal_'+x['product_id']]=seal
assert set(packets)==set(targets)
if not(H/'input-manifest.json').exists():
 m={}
 for k,f in sources.items():
  dest=H/'inputs'/(k+'.before');shutil.copy2(f,dest);m[k]={'path':str(f),'snapshot':str(dest),'sha256':sha(f)}
 write(H/'input-manifest.json',m);write(H/'scope.json',{'recorded_utc':datetime.now(timezone.utc).isoformat(),'target_option_ids':targets,'approvals':packets,'individual_qualified_reference_option_ids':targets[:4],'in_situ_option_ids':targets[4:],'new_components_or_options':0,'specification_or_commercial_value_changes':0,'Dropbox_or_platform_mutations':0,'scope':'Only the seven approvals explicitly requested in the current owner message; other queued approvals and folder changes remain outside this import'})
for k,x in read(H/'input-manifest.json').items():assert sha(x['path'])==sha(x['snapshot'])==x['sha256'],k
assert sha(B/p['workbook'])==p['workbook_sha256']and sha(B/p['register'])==p['register_sha256']
requests={}
for oid,f in packets.items():
 d=read(f)
 for r in d['approved_reference_roles']:
  s=r['source'];fid=s.get('id',s.get('file_id'));requests.setdefault(fid,{'file_id':fid,'name':s['name'],'path_display':s['path_display'],'size':s['size'],'rev':s.get('rev'),'sha256':s.get('sha256',s.get('source_sha256')),'content_hash':s.get('content_hash'),'target_option_ids':[]})['target_option_ids'].append(oid)
write(H/'source-requests.json',list(requests.values()));print(json.dumps({'status':'FROZEN','packets':len(packets),'unique_source_files':len(requests),'inputs':len(read(H/'input-manifest.json'))}))
