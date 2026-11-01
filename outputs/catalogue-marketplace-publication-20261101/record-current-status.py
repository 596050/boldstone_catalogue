"""Durable handoff of verified results and uncertain external writes."""
from datetime import datetime,timezone
from pathlib import Path
import json
OUT=Path(__file__).resolve().parent
read=lambda name:json.loads((OUT/name).read_text())
market=read('marketplace-material-receipts.json');verified={r['catalogue_id'] for r in market}
catalogue=read('current-prepared-catalogue.json')['records']
ledger=json.loads((OUT.parent/'marketplace-completion-20261101/all-marketplace-receipts.json').read_text())
if isinstance(ledger,dict):ledger=ledger.get('records',ledger.get('receipts',[]))
remaining=[r for r in ledger if r['catalogue_id'] not in verified]
status={
 'recorded_utc':datetime.now(timezone.utc).isoformat(),
 'overall':'PARTIAL_NOT_ALL_PLATFORMS_UPDATED',
 'authority':'Owner approved displayed eBay terms for both staged uploads and requested gypsum-based material plus applied surface-effect wording across all wall-sculpture platforms, without duplicates.',
 'source':{'components':181,'included_public_records':len(catalogue),'applied_effect_public_records':sum(r['surface_effect'] for r in catalogue),'app_verification':'material-app-verification.json'},
 'dropbox':read('material-workbook-dropbox-receipt.json'),
 'squarespace':{'status':'176_EXISTING_PRODUCTS_UPDATED_AND_NATIVE_EXPORT_COMPARED','verification':'squarespace-material-verification.json','other_export_cells_unchanged':True},
 'google':{'status':'176_SUPPLEMENT_ROWS_ACCEPTED_MATCHED_NO_FEED_ERRORS','merchant_account':'5664655454','source_id':'10789003059','evidence':'google-material-upload.png','approval':'NOT_REVERIFIED'},
 'meta':{'status':'176_UPDATED_ZERO_FAILED','catalogue_id':'1638438493182970','supplement_id':'1699005968459486','evidence':'meta-material-upload.png'},
 'ebay':{'sapr_2972':{'new_drafts_accepted':157,'request_id':'12356778479','publication':'NOT_PUBLISHED','bulk_settings':'Promotion disabled and 10 working days dispatch applied; Save for later clicked. Verify persisted draft settings on return.','existing_wall_listings_material_update':'20_REMAINING'},'in6192':{'new_drafts_accepted':176,'request_id':'13338436334','state':'DRAFTS_ONLY','reimport':'DO_NOT_REIMPORT_ACCEPTED_ROWS'}},
 'facebook_marketplace':{'verified_unique_components':len(verified),'remaining_unverified':len(remaining),'receipt_file':'marketplace-material-receipts.json','uncertain_interrupted_batch':[r['catalogue_id'] for r in remaining[:4]],'next_action':'Reopen the existing records, verify SKU and saved copy before any retry. The interrupted batch may already contain saved updates.'},
 'tiktok':read('tiktok-off-sale-verification.json'),
 'wescover':{'existing_wall_records_copy_submitted':3,'public_approval':'NOT_REVERIFIED','new_unique_prepared':174,'new_uploaded':0,'existing_individuals_excluded':['BSI-A0FFC102A6F1','BSI-123AABD474C1']},
 'saatchi':{'existing_icarus_description':'UPDATED_AND_VERIFIED_PUBLISHED','existing_item_id':'14226583','other_new_records':'NOT_UPLOADED','open_issue':'Confirm a truthful made-to-order route compatible with dispatch requirements before publication.'},
 'chairish':{'new_wall_records':'NOT_UPLOADED'},
 'blocker':'Chrome browser-control connection disappeared; native Chrome control also timed out. Await reconnection before further UI mutations or verification.'
}
(OUT/'current-publication-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
(OUT/'marketplace-material-remaining.json').write_text(json.dumps(remaining,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'verified_marketplace':len(verified),'unverified_marketplace':len(remaining),'interrupted_ids':status['facebook_marketplace']['uncertain_interrupted_batch'],'overall':status['overall']}))
