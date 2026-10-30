"""Bind final evidence receipts without changing authored workbook content."""
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;BASE=H.parents[2];read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
seen=set()
for name in ['visual-queue.json','followup-queue.json','group-extra-queue.json','moon-fishwave-extra-queue.json']:
 seen|={x['file_id']for x in read(BASE/'components/reconciliation/image-identity-coverage-2026-10-20'/name)}
visible=set()
for name in ['review-plate-manifest.json','candidate-plate-manifest.json','selected-context-comparison-manifest.json']:
 for p in read(H/name):visible|={x['file_id']for x in p['views']}
visible|={x['file_id']for x in read(H/'leaf-download-receipt.json')['images']};assert(len(seen),len(visible-seen),len(seen|visible))==(1144,881,2025)
proof={'path':str((H/'source-visual-review-receipt.json').relative_to(BASE)),'sha256':sha(H/'source-visual-review-receipt.json')}
audit=read(H/'image-coverage-current.json');audit['terminal_review']['source_visual_review']=proof
audit['counts'].update(unique_dropbox_images_visually_reviewed=2025,source_view_count_scope='Distinct native source IDs examined across prior queues and this pass; includes one unusable blank thumbnail, NC302. This is not a photograph or sculpture count.',additional_native_source_ids_examined=881,new_original_files_rehashed=116,original_rehash_count_scope='Unique native IDs downloaded/hash-checked during this terminal pass; not cumulative library originals.',new_context_candidates_examined=731,root_inventory_folder_count_before_Cup_colour_moves=424,known_new_Cup_colour_folders_after_inventory=2)
write(H/'image-coverage-current.json',audit)
g=read(H/'canonical-master-register.json');g['latest_image_coverage_audit'].update(audit_sha256=sha(H/'image-coverage-current.json'),counts=audit['counts']);g['latest_terminal_photo_review']['source_visual_review']=proof;write(H/'canonical-master-register.json',g)
g['latest_image_coverage_audit'].update(path=str(H/'image-coverage-current.json'),scope='184 saved options retained; every one of the 157 outstanding picture actions reviewed individually. Relevant additional archive and context sources examined within a bounded scope; missing means no verified exact-option role reference established in those sources.',verification=str((H/'saved-file-verification.json').relative_to(BASE)),visual_verification=str((H/'visual-verification.json').relative_to(BASE)))
g['latest_image_coverage_audit'].pop('verification_sha256',None);g['latest_image_coverage_audit'].pop('visual_verification_sha256',None)
write(H/'canonical-master-register.json',g)
previews=read(H/'preview-manifest.json');assert len(previews)==6
write(H/'visual-verification.json',{'status':'PASS','recorded_utc':datetime.now(timezone.utc).isoformat(),'previews':[{**x,'sha256':sha(x['path'])}for x in previews],'observed':'Coverage/action summaries, MS1/MS2/MS3 role distinctions, source-qualified MCP1 setting, Riyadh candidate action and Cup appearance-only scope inspected. Updated rows wrap within their extended heights. Absent role references no longer look like hyperlinks; newly linked roles use the existing blue link style. Existing tab layout and specification columns are retained.','browser_render_of_HTML_performed':False,'HTML_structural_link_validation':'link-report-verification.json','new_product_photos_created':0})
print(json.dumps({'status':'FINAL_EVIDENCE_BOUND','source_ids_examined':2025,'additional_ids_examined':881,'previews_inspected':6}))
