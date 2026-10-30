"""Reuse the established scoped authoring and report workflow for one context role."""
from pathlib import Path
H=Path(__file__).resolve().parent;O=H.parent/'four-queued-links-and-strata-owner-context-2026-10-23'
s=(O/'prepare_workbook.py').read_text().replace("out=B/'outputs/four-queued-links-and-strata-owner-context-2026-10-23';oldout=B/'outputs/acanthus-sandstone-retirement-2026-10-23'","out=B/'outputs/"+H.name+"';oldout=B/'outputs/"+O.name+"'")
s=s.replace("oid='BSI-7B6291B7C7F9'","oid='BSI-CF0CC1EB8F96'").replace('Owner-designated wall setting','Owner-accepted outdoor display').replace('Owner wall-setting approval','Owner outdoor-display approval')
s=s.replace("('Photo Coverage','D4'):139","('Photo Coverage','D4'):140").replace("('Missing Pictures','B4'):65","('Missing Pictures','B4'):64")
start=s.index('for sn,text in {');end=s.index('for key,x in changes.items():',start)
s=s[:start]+"for sn,text in {'Master Catalogue':'187 active individual options and one retired history row across112 component identities. Moon/Shellwave/workshop links match the live stable-ID readback. Leaf Curve White and Gold Leaf001 is an owner-accepted outdoor-display reference.','Photo Coverage':'177 complete individual references;10 technical gaps include9 owner-accepted qualified exceptions and one deferred Frozen Fish identity. Current gaps:47 in situ and17 series. Leaf Curve001 is outdoor display. Permanent/client installation and physical specifications remain unverified. Sandstone remains retired.','Missing Pictures':'208 retained rows:65 required open actions,54 optional,86 resolved and3 retired. Current gaps:one deferred individual/identity entry,47 in situ and17 series. Sandstone has no active tasks.'}.items():setcell(sn,'A3',text)\n"+s[end:]
s=s.replace('baseline-strata','baseline-leaf-curve').replace('02-strata-wall-setting','02-leaf-curve-outdoor-display').replace('03-strata-source-limits','03-leaf-curve-source-limits').replace('strata_workbook_row','leaf_curve_workbook_row')
(H/'prepare_workbook.py').write_text(s)
s=(O/'author_workbook.mjs').read_text().replace('BSI-7B6291B7C7F9','BSI-CF0CC1EB8F96').replace("138,'Context count responds","139,'Context count responds").replace("66,'Owner-directed task","65,'Owner-directed task").replace('wall-setting','outdoor-display').replace('Wall-setting','Outdoor-display').replace('FOUR_LINK_AND_STRATA','LEAF_CURVE_CONTEXT')
(H/'author_workbook.mjs').write_text(s)
s=(O/'build_reports.py').read_text().replace(O.name,H.name)
s=s.replace('[208,66,1,48,17,1,85,54]','[208,65,1,47,17,1,86,54]').replace('48 in situ','47 in situ').replace("'in_situ_gaps':48","'in_situ_gaps':47").replace("'required_actions':66","'required_actions':65").replace("'find_capture':65","'find_capture':64").replace("'resolved_actions':85","'resolved_actions':86")
s=s.replace('Four verified Moon/Shellwave/workshop path overlays are imported by stable native ID. Strata White003 is owner-directed qualified wall-setting context: complete White panel and surrounding brickwork, with wider room/garden and authenticated installation unverified. Earlier qualified image bindings are retained.','The saved Moon/Shellwave/workshop links match the fresh stable-ID readback. Leaf Curve White and Gold Leaf001 is an owner-accepted whole outdoor-display photograph. Its permanent/client installation and physical specifications remain unverified. Earlier qualified image bindings are retained.')
s=s.replace('Owner-directed Strata White wall-setting reference','Owner-accepted Leaf Curve outdoor-display reference').replace('Current folder changes and live references','Verified Moon and Shellwave and workshop links')
(H/'build_reports.py').write_text(s)
s=(O/'verify_workbook.py').read_text().replace("['required_picture_actions']==66","['required_picture_actions']==65").replace('Current66 required','Current65 required').replace('Four stable-ID Moon/Shellwave/workshop path overlays plus one owner-directed Strata White wall-setting role; Sandstone retirement and all working specifications preserved','One owner-accepted Leaf Curve outdoor-display role; previously imported folder links, Sandstone retirement and all working specifications preserved')
(H/'verify_workbook.py').write_text(s)
s=(O/'guided_review.py').read_text().replace(O.name,H.name)
(H/'guided_review.py').write_text(s)
print('LEAF_CURVE_CONTEXT_WORKFLOW_STAGED')
