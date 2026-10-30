"""Record the scoped visual review of111 carried-forward photograph actions."""
import json,hashlib,collections,copy
from pathlib import Path
from datetime import datetime,timezone
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text());write=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');now=lambda:datetime.now(timezone.utc).isoformat();assets=read(H/'current-assets.json');queue=read(H/'photo-review-queue.json')
bindings=[
 {'option_id':'BSI-9C7406B46836','role':'In situ','file_id':'id:cnqzTNngPVsAAAAAAAyh1Q','position':'Both landscape reliefs on the wall above the booth','finding':'The second White Acanthus room file shows the full landscape relief twice above a booth. Both retain the pointed central leaf, left rising blade and two right-hand quarter-circle bands of the kept Full / Acanthus and Moon primary. The previously rejected near-square room file remains rejected. This newly bound file preserves the full landscape extent.','qualification':'Source-qualified room presentation. Real installation, actual cast, exact scale and finish batch are not certified.'},
 {'option_id':'BSI-9C7406B46836','role':'Series','file_id':'id:cnqzTNngPVsAAAAAAAyh1Q','position':'Left and right repeated Full / Acanthus and Moon reliefs','finding':'Two complete White Full / Acanthus and Moon reliefs appear together in the booth-wall scene. Repeated positions reuse the existing component identity; they do not create additional designs or catalogue options.','qualification':'Repeated-component arrangement reference; no set dimensions, price or physical stock allocation.'},
 {'option_id':'BSI-489226D6FF87','role':'Series','file_id':'id:cnqzTNngPVsAAAAAAAyiCA','position':'Five repeated Totems; far-left member has a complete unobscured outline','finding':'The living-wall scene contains five repeated tall White Totem strips. Their alternating three-lobed folded profile, continuous centre ridge and concave side channels match the retained isolated Totem. The far-left member is fully visible. Other foreground-obscured members remain arrangement context.','qualification':'Source-qualified scene, with repeated copies of one existing design. Real manufacture, installation, size and quantity are not established by the composition.'},
 {'option_id':'BSI-6D48F324B10C','role':'In situ','file_id':'id:cnqzTNngPVsAAAAAAAyhHA','position':'LEFT panel above the organ','finding':'The eighth organ-room file shows the standard concentric Verdigris pair. The Left member has the arc centre on its inner right edge; the Right member has the complementary inner-left centre. Their ridge paths, rough bronze crests and blue-green troughs match the retained composition-2 primary. This is a different file from the previously rejected offset/rough arrangement.','qualification':'Visual design-and-finish room reference; source rendering/photomontage origin, scale and the same physical cast are unverified. No new component, finish or dimensions inferred.'},
 {'option_id':'BSI-59CBB4D2FA9E','role':'In situ','file_id':'id:cnqzTNngPVsAAAAAAAyhHA','position':'RIGHT panel above the organ','finding':'The eighth organ-room file shows the standard concentric Verdigris pair. The Right member has its arc centre on the inner left edge and the sweeping outer ridges of the retained Right component. The pair is complete in the room composition; the previously rejected offset/rough file remains historical context.','qualification':'Visual design-and-finish room reference; source rendering/photomontage origin, scale and the same physical cast are unverified. No new component, finish or dimensions inferred.'},
 {'option_id':'BSI-E5B3990ECDDC','role':'In situ','file_id':'id:cnqzTNngPVsAAAAAAAs6dw','position':'Single portrait relief on red wall above the wooden chair','finding':'The fifth Moonwave room photograph shows the complete White portrait panel beside a floor lamp and above a wooden chair. Its broad upper crescent and lower inward curl match the retained brick-wall Moonwave primary. It is not the different Moon Ripple / Chelsea form rejected in the earlier review.','qualification':'Exact design-level room reference. Actual cast dimensions, same-cast provenance and installation authenticity retain their existing evidence limits.'}
]
for i,x in enumerate(bindings,1):
 a=assets[x['file_id']];x.update(binding_id='PHOTO-GAP-2026-10-22-'+str(i).zfill(2),recorded_utc=now(),reference={k:a[k]for k in ['file_id','folder_id','name','path','image_url','folder_url']},current_original_sha256=a['current_original_sha256'],current_native_content_hash=a['current_native_content_hash'],specification_changes=0,new_options=0,new_product_photographs=0)
bytask={x['option_id']+'::'+x['role']:x for x in bindings}
crop_positions={
 'BSI-6D48F324B10C':'Left panel of the concentric Verdigris pair',
 'BSI-5A81C695D1AB':'Left panel of the White pair',
 'BSI-59CBB4D2FA9E':'Right panel of the concentric Verdigris pair',
 'BSI-51CF74303593':'Right panel of the White pair',
 'BSI-86E6AEA0EB98':'Left member of the White fish triptych; retained FFS1 identity',
 'BSI-60CAC1435616':'Right member of the White fish triptych; retained FFS3 identity',
 'BSI-53239DE28BCA':'Top-left member of the four-panel Vine and Tendril arrangement',
 'BSI-49CB2EDD232C':'Top-right member of the four-panel Vine and Tendril arrangement',
 'BSI-48D13D8D7E67':'Bottom-left member of the four-panel Vine and Tendril arrangement',
 'BSI-8957C5C51828':'Bottom-right member of the four-panel Vine and Tendril arrangement',
 'BSI-7357A558C9E8':'Left third of the White Lava Moon triptych',
 'BSI-791ADD96D660':'Centre third of the White Lava Moon triptych',
 'BSI-2246CBC9C94E':'Right third of the White Lava Moon triptych',
 'BSI-D886F539DD3E':'Upper outlet-bearing spiral only; exclude lower Moon and Shellwave2',
 'BSI-B1DCB5B08396':'One of the two matching MP4 flanks in the White-and-Gold4/2/4 group; retain the centre MP2 separately',
 'BSI-95ECE169007F':'Left Beige Raked Spiral1 panel',
 'BSI-6C2DDC69FB83':'Right Beige Raked Spiral2 panel'
}
detail_actions={
 'BSI-3635E3DC3434':'Photograph the complete Pewter panel alone. Owner identifies the workshop group BACK RIGHT panel, but the foreground panel obscures part of its outline. The existing detail does not recover the hidden edge.',
 'BSI-C41824131174':'Photograph the complete Sandstone panel alone. Owner identifies BACK CENTRE in the workshop group, but containers/adjacent objects obscure part of its outline. Keep the close-up as a detail image.',
 'BSI-B42C439049D7':'Photograph the complete Leaf Growth panel in its White and Gold Leaf finish. Current gold-leaf close-ups do not show the complete outer outline; a White-only image cannot supply this finish.',
 'BSI-718DFFB7EC5D':'Photograph the entire Bronze Spiralfish Wave & Tide1 panel straight on. The Bronze source is a close-up; White pair scenes cannot supply a full view of this Bronze option.',
 'BSI-54F871DCF4CA':'Photograph the entire Bronze Spiralfish Wave & Tide2 panel straight on. The Bronze source is a close-up; White pair scenes cannot supply a full view of this Bronze option.'
}
for x in queue:
 pid=x['option_id'];role=x['role'];x['reviewed_utc']=now();x['scope']='Current product-tree inventory complete at6633files/427folders;111 task subjects and551 further source candidates inspected. Whole-Dropbox absence is not asserted.'
 if x['task_id']in bytask:
  d=bytask[x['task_id']];x.update(review_state='RESOLVED_EXISTING_SOURCE_REFERENCE',finding=d['finding'],qualification=d['qualification'],new_reference=d['reference'],binding_id=d['binding_id'],next_action='Use the linked complete existing scene for this role; preserve its source/provenance qualifications.')
 elif pid=='BSI-04D6E8690F30':
  x.update(review_state='DEFERRED_LEGACY_BINDING_SIZE_FIXED',finding='Owner reaffirms all current Frozen Fish at70cm high×15cm wide and directs the work to photographs. No FFL1/FFS2 merge or identity answer is inferred.',next_action='Keep70×15cm as the current default and leave the historical design/alias binding aside. Do not ask again as a prerequisite to the photograph work.')
 elif role=='Individual'and pid in crop_positions:
  x.update(review_state='EXACT_CROP_CANDIDATE_PENDING_OWNER_CRITERION',component_position=crop_positions[pid],finding='The complete source-scoped component appears in a group image. A separate lossless pixel crop may supply an individual listing view if the owner accepts this approach and final per-crop outline/resolution checks pass.',next_action='Review the proposed exact component crop. Preserve the complete source image as the arrangement reference; do not reconstruct, recolour, stretch or remove occlusions.',crop_created=False)
 elif role=='Individual'and pid in detail_actions:
  x.update(review_state='SEPARATE_PHOTOGRAPH_REQUIRED',finding='Only a detail view or a partly obscured group member is bound for this exact finish.',next_action=detail_actions[pid])
 elif role=='Individual':
  x.update(review_state='SEPARATE_PHOTOGRAPH_REQUIRED',finding='The low-light Sandstone Lava Moon group does not provide a clean isolated view with an independently clear complete panel outline. A tight crop would retain darkness/foreground obstruction and inadequate separation.',next_action='Photograph this Sandstone Lava Moon member alone, with all four edges visible and neighbouring panels excluded. Retain its Left/Centre/Right identity and existing source group.')
 elif role=='In situ':
  x.update(review_state='CONTEXT_PHOTOGRAPH_REQUIRED',finding=x['previous_action']['qualification'],next_action='Take a wider room or garden photograph showing '+x['name']+' in its listed finish, with the complete component visible and enough surroundings to show placement. Keep the current close-up/primary reference separately.')
 else:
  x.update(review_state='SERIES_PHOTOGRAPH_REQUIRED',finding=x['previous_action']['qualification'],next_action='Photograph '+x['name']+' with identified companion components. Keep every full outline visible and record this option\'s exact position and finish. A different finish or unrelated family composition does not close this role.')
 x['source_reference']={**x['source_reference'],**{k:assets[x['source_reference']['file_id']][k]for k in ['file_id','folder_id','name','path','image_url','folder_url']}}
write(H/'new-photo-bindings.json',bindings);write(H/'photo-review-queue.json',queue)
summary={'status':'ALL111_CARRIED_ACTIONS_REVIEWED','recorded_utc':now(),'actions_reviewed':len(queue),'new_visual_role_bindings':len(bindings),'roles_resolved':dict(collections.Counter(x['role']for x in bindings)),'review_states':dict(collections.Counter(x['review_state']for x in queue)),'candidate_context_views_inspected':551,'task_subject_views_inspected':111,'current_native_product_tree_files':6633,'current_native_product_tree_folders':427,'new_listing_images_created':0,'native_mutations':0,'all_frozen_fish_current_default':'70 H×15 W cm','legacy_frozen_identity_deferred':True,'crop_policy_answer_required_for_derivatives':True}
write(H/'photo-review-summary.json',summary);print(json.dumps(summary))
