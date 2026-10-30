from pathlib import Path
import hashlib,json,datetime

W=Path(__file__).resolve().parent
ROOT=Path('/Users/tprice/Documents/boldstone')
PACKET=ROOT/'sculpture-catalogue/components/reconciliation/six-native-deletions-and-app-review-2026-10-25/workbook-cutoff-packet.json'
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=read(PACKET);v=read(W/'validation.json');r=read(W/'final-readback.json')
assert sha(p['output_workbook'])==v['sha256']
assert sha(p['baseline_workbook'])==p['baseline_workbook_sha256']
assert sha(p['overlay_path'])==p['overlay_sha256']
assert len(r['previews'])==7
visual={
 'status':'PASS_VISUAL_REVIEW_OF_SAVED_WORKBOOK',
 'reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'observations':[
  'Availability summary shows six deleted files, 6354 after these six only, and 442 unchanged folders.',
  'Six deletion rows and four verified surviving references are visible with clear primary-status text.',
  'Icarus product and Wall Sculptures availability notes fit their existing cells; image and folder actions remain.',
  'Overview, guide and coverage notes display the correct counts and cutoff without overlapping text.',
  'Existing source formatting and record counts remain intact.'
 ],
 'previews':[{**x,'sha256':sha(x['path'])} for x in r['previews']],
}
(W/'visual-review.json').write_text(json.dumps(visual,indent=2)+'\n')
guards={
 ROOT/'sculpture-catalogue/current-master.json':'8840bcc0389a0a37d85278b41f966a5d909cd59879ee3d77ca29278ab3bb76bb',
 ROOT/'sculpture-catalogue/components/reconciliation/matched-listing-master-2026-10-25/canonical-master-register.json':'9b4b15ca857bea027637b3dd1474bfb98c87746bb842b49003b526da6770e748',
 ROOT/'sculpture-catalogue/components/parallel-reviews/all-record-image-matching-20261024-B/published-projections/20261025T121532991771Z/complete-image-platform-register.sqlite':'26a09ffd64380e7c87dde27882b503d022bf8275510909f965718ee36aa9b591',
 ROOT/'sculpture-catalogue/outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Master_Catalogue_2026-10-20.xlsx':'178d00ee841c1035a923904dcabc0b7a85264803ff5351bbb3c42c48a327528a',
}
for file,h in guards.items():assert sha(file)==h,str(file)
support=['authoring-receipt.json','assembly-receipt.json','validation.json','exact-baseline-delta.json','final-readback.json','visual-review.json','build-v4.mjs','assemble-v4.py','verify-v4.py','seal-v4.py']
seal={
 'status':'SEALED_AVAILABILITY_ONLY_V4_READY_FOR_PUBLISHER_REVIEW',
 'sealed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'workbook':p['output_workbook'],'workbook_sha256':v['sha256'],
 'baseline_workbook':p['baseline_workbook'],'baseline_sha256':p['baseline_workbook_sha256'],
 'packet':str(PACKET),'packet_sha256':sha(PACKET),
 'overlay':p['overlay_path'],'overlay_sha256':p['overlay_sha256'],
 'review_event_cutoff':347,'last_confirmed_native_event':342,
 'timing_qualification':'Icarus 007 was outside the previous explicit five-ID review set. Its deletion events 341/342 preceded snapshot 345. This v4 includes all six verified deletions in snapshot 347.',
 'counts':{'sheets':23,'source_sheets':22,'primary_rows':413,'source_cells_compared':341850,'source_hyperlinks_unchanged':44617,'source_formulas_unchanged':20,'source_tables_unchanged':22,'total_tables':24,'deleted_native_files':6,'verified_surviving_reference_files':4,'baseline_files':6360,'files_after_six_only':6354,'baseline_folders':442},
 'exact_metadata_changes':v['exact_metadata_deltas'],
 'source_hyperlink_changes':[],
 'native_availability_sheet_rebuilt':True,
 'app_specification_overlay_imported':False,
 'canonical_published':False,
 'no_canonical_app_native_platform_writes':True,
 'protected_source_hashes':{str(k):h for k,h in guards.items()},
 'evidence':{str(W/file):sha(W/file) for file in support},
 'visual_previews':visual['previews'],
}
dest=W/'sealed-handoff.json'
assert not dest.exists(),'Do not overwrite an existing seal'
dest.write_text(json.dumps(seal,indent=2)+'\n')
print(json.dumps({'status':seal['status'],'handoff':str(dest),'handoff_sha256':sha(dest),'workbook_sha256':v['sha256']},indent=2))
