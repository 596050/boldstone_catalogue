"""Build the precise current image queue after superseding four historical offers."""
import copy,hashlib,json,shutil
from pathlib import Path
H=Path(__file__).resolve().parent;BASE=H.parents[2]
read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
write=lambda p,d:Path(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
old=BASE/'components/reconciliation/lava-moon-numbering-2026-10-22';m=read(H/'input-manifest.json');packet=read(H/'inputs/product_packet.before');retired=set(packet['legacy_disposition']['product_ids'])
for k,f in [('report_assets','current-assets.json'),('report_reviews','photo-review-queue.json')]:
 p=old/f;s=H/'inputs'/(k+'.before')
 if k not in m:shutil.copy2(p,s);m[k]={'path':str(p),'snapshot':str(s),'sha256':sha(p)}
write(H/'input-manifest.json',m)
assets=read(m['report_assets']['snapshot']);reviews=read(m['report_reviews']['snapshot']);kept=[x for x in reviews if x['option_id']not in retired];assert len(kept)==105
write(H/'photo-review-queue.json',kept);write(H/'superseded-photo-task-reviews.json',[x for x in reviews if x['option_id']in retired])
for p in packet['options']:
 r=p['original_individual_photo'];folder=p['original_image_folder'];src=BASE/'components/reconciliation/fingerprint-numbered-master-refresh-2026-10-22/native-originals'/(r['file_id'][3:]+'.jpeg');assets[r['file_id']]={'file_id':r['file_id'],'folder_id':folder['file_id'],'name':r['name'],'path':r['ns_path'],'image_url':r['url'],'folder_url':folder['url'],'full':str(src),'thumb':str(src),'source_sha256':p['original_photo_sha256']}
write(H/'current-assets.json',assets)
s=(old/'build_review_reports.py').read_text().replace('outputs/lava-moon-numbering-2026-10-22','outputs/fingerprint-product-finalization-master-2026-10-22')
s=s.replace('==[211,105,26,61,18,1,53,53]','==[205,101,22,61,18,1,51,53]').replace('assert len(review_rows)==111','assert len(review_rows)==105')
s=s.replace('105 remaining action rows','101 remaining action rows').replace('26 individual entries','22 individual entries').replace('53 retained resolved actions','51 current resolved actions')
s=s.replace('All 111 carried-forward actions reviewed; six further roles mapped.','The current list excludes six superseded Fingerprint action rows, preserved in history. Of those, four open individual capture requests are retired by catalogue scope, not photographs found. Six current Fingerprint options now have full original JPEG coverage.105 surviving carried-forward actions are represented; prior reviews remain qualified.')
s=s.replace('The 26 individual entries contain 17 possible exact crops','The 22 individual entries contain 13 possible exact crops').replace('Download all 111 reviews','Download105 current reviews')
s=s.replace("'required_actions':105,'find_capture':104","'required_actions':101,'find_capture':100").replace("'individual_gaps':26","'individual_gaps':22").replace("'exact_crop_candidates':17","'exact_crop_candidates':13").replace("'reviewed_action_rows':111","'reviewed_action_rows':105")
s=s.replace("'historical_resolved_actions':53","'current_resolved_actions':51,'historical_resolved_actions':53,'superseded_Fingerprint_actions_archived':6")
(H/'build_review_reports.py').write_text(s);print('CURRENT_IMAGE_REPORT_INPUTS_READY')
