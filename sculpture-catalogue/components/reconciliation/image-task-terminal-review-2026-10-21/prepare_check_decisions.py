"""Curated decisions from primary-versus-candidate visual comparisons."""
import json
from pathlib import Path
H=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
items=read(H/'terminal-review-items.json'); plates=read(H/'review-plate-manifest.json')
proof={v['sequence']:p['path'] for p in plates if p['category']=='verification-pairs' for v in p['views']}
closed={
90:('RIGHT panel in the two-panel room scene. Broad plain moon and simple terminal hook match MS1; MS2 is at left.','RIGHT'),
91:('LEFT panel in the two-panel room scene. Double-volute inner spiral matches MS2; MS1 is at right.','LEFT'),
147:('LEFT member of the three-panel White Moonspirals group; plain broad moon and simple hook match MS1.','LEFT'),
148:('CENTRE member of the three-panel White Moonspirals group; double-volute inner spiral matches MS2.','CENTRE'),
149:('RIGHT member of the three-panel White Moonspirals group; compact volute and incised outer line match MS3.','RIGHT'),
150:('BOTTOM member of the Sand Ripple pair; rough/fossil surface and broken wave ridge paths match Fossil Sand Ripple.','BOTTOM'),
151:('TOP member of the Sand Ripple pair; smooth crests and knots match Smooth Sand Ripple.','TOP')}
excluded={
30:'The room scene contains two near-square altered/cropped broad-leaf panels. The kept Full / Acanthus and Moon reference is landscape with a different complete outer extent. Retain as family illustration, not an exact full-option installation.',
39:'The Gold room candidate has a straight rectangular cropped outer boundary. The primary Brancusi 1 has an irregular folded silhouette. It does not verify the complete kept component in situ.',
60:'The organ-room candidate shows rough/offset fingerprint reliefs, not the standard concentric composition-2 pair. It cannot establish this standard Left Verdigris component in situ.',
61:'The organ-room candidate shows rough/offset fingerprint reliefs, not the standard concentric composition-2 pair. It cannot establish this standard Right Verdigris component in situ.',
62:'The candidate is a product photograph propped on trestles. The 83 Bronze/Verdigris family views reviewed show close-ups or workshop-board/trestle displays, without a wider installed wall scene. The owner-confirmed dark indoor finish association is retained separately.',
92:'MS3 is absent from the linked two-panel room scene: its left member is MS2 and its right member MS1. This scene cannot fill the MS3 in-situ role.',
94:'The room candidate depicts a related large Moon Ripple / Chelsea form behind a plant, with a different curl and outline from the kept tall Moonwave. Family consolidation is not a component alias.',
101:'The tight two-panel board/display photograph verifies the series relationship, but lacks a wider room or garden installation context. It does not fill the in-situ role.',
102:'The blue-lit architectural treatment is a floor-to-ceiling multi-panel build. Its pattern, scale and configuration are not bound to the standard horizontal Smooth Sand Ripple option.',
115:'The Blue/Brown/Rust surface is used horizontally as a tabletop/workshop display. Matching patina does not establish a wall installation.'}
pending={
29:'The room scene resembles Acanthus Flower, but the small pictured object and source/version are not independently bound to the complete primary panel. Retain the design candidate; confirm exact full-outline source and scene provenance.',
41:'The room pair belongs to the Gold folded-panel family. The full irregular Brancusi 2 member outline and exact per-panel association remain insufficiently resolved in the scene.',
43:'The garden four-panel scene suggests Deco Two Leaves at LEFTMOST. Confirm the exact complete design/version and image source before binding; a montage or custom-size study does not measure the standard panel.',
44:'The garden four-panel scene suggests Palm Form Two THIRD FROM LEFT. Confirm the complete ridge pattern/version and image source before binding to this standard option.',
45:'The garden four-panel scene suggests Palm Form One at RIGHTMOST. Confirm the complete ridge pattern/version and image source before binding to this standard option.',
54:'The Gold Egyptian Palm room pair is a relevant family candidate, but the complete exact member pattern and per-panel association are not yet secure.',
56:'The four-member garden scene tentatively places Swan Wing Folds FIRST. Ridge paths, orientation and source/version must still be bound to the kept individual panel.',
57:'The four-member garden scene tentatively places Fan Folds SECOND. Ridge paths, orientation and source/version must still be bound to the kept individual panel.',
58:'The four-member garden scene tentatively places Cultivation Folds THIRD. Ridge paths, orientation and source/version must still be bound to the kept individual panel.',
59:'The four-member garden scene tentatively places Fold Unfold 4 FOURTH. Ridge paths, orientation and source/version must still be bound to the kept individual panel.',
66:'The garden scene matches the general White Frozen Fish fin form, but does not resolve whether it depicts the 70 x 15 or 100 x 22 cm build. Fin count and apparent aspect ratio do not certify scale.',
74:'The primary is a very long vertical Black/White marbled panel. The horizontal room candidate has related marbling, but aspect ratio/cropping and exact size/version remain unbound.',
103:'The garden-above-planter candidate has matching Battersea Shellmoon front geometry. Standard dry versus water-adapted configuration remains unverified; design similarity alone does not certify the build.',
104:'The garden candidate shows the related dry White Shellmoon form. No flow, plumbing or other water-adapted build evidence binds it to the Islington water-feature option.',
106:'The workshop/person display contains two Spice panels and partly obscures the left one. Exact ridge-pattern and position binding for Spice Texture 1 remains unresolved.',
107:'The right workshop board resembles Spice Texture 2, but partial occlusion and similar elongated forms prevent a confident complete-pattern binding. Do not infer member number from filename.',
130:'The four rotated landscape Fold/Unfold panels on the brick wall tentatively place Swan Wing third. Orientation and fine ridge paths do not yet securely bind the member.',
154:'The five workshop colour studies are a useful group reference, but the close Pewter finish crop is not uniquely position-bound. Lighting alone cannot assign the finish to a complete leaf.',
155:'The five workshop colour studies are a useful group reference, but the close Sandstone finish crop is not uniquely position-bound. Warm lighting alone cannot assign the finish to a complete leaf.',
156:'The two-member Spice display is partly obscured. A complete pattern-to-position binding for Spice Texture 1 remains needed before accepting the series link.',
157:'The two-member Spice display is partly obscured. A complete pattern-to-position binding for Spice Texture 2 remains needed before accepting the series link.'}
decisions=[]
for x in items:
 n=x['sequence']
 if x['prior_action']['action_type']!='Verify existing image':continue
 d={'sequence':n,'evidence_plates':[proof[n]],'review_scope':'Visual association and image role only; no physical-cast, measured-size, installed-hardware, finish-batch or real-installation certification.'}
 if n in closed:
  finding,position=closed[n];d.update(review_state='RESOLVED_VERIFIED_REFERENCE',finding=finding+' Working design/finish association accepted at the depicted position. Scene origin remains qualified; no dimensions, weight or price transferred from the arrangement.',position=position,new_photo_status='Available',next_action='None for this visual association; retain existing scene/source qualifications and all physical verification limits.')
 elif n in excluded:d.update(review_state='REVIEWED_CAPTURE_REQUIRED',finding=excluded[n],new_photo_status='No verified image',next_action='Find a complete exact-option wider installed scene, or photograph the kept component in an actual room/garden installation. Retain this rejected role candidate as historical context.')
 else:
  assert n in pending,n
  d.update(review_state='REVIEWED_BINDING_REQUIRED',finding=pending[n],new_photo_status='Verify existing image',next_action=pending[n])
 decisions.append(d)
assert len(decisions)==38
(H/'existing-image-review-decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'decisions':len(decisions),'resolved':len(closed),'excluded_role':len(excluded),'binding_required':len(pending)}))
