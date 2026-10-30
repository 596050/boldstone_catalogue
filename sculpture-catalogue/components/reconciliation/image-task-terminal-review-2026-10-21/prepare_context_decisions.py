"""Item-specific outcomes for all 93 missing-context actions."""
import json
from pathlib import Path
H=Path(__file__).resolve().parent;read=lambda p:json.loads(Path(p).read_text())
items=read(H/'terminal-review-items.json');byseq={x['sequence']:x for x in items};assets=read(H/'current-assets.json')
plates=read(H/'review-plate-manifest.json');mp={v['sequence']:p['path']for p in plates if p['category']=='missing-context'for v in p['views']}
cp=read(H/'candidate-plate-manifest.json');nc={v['label']:{**v,'plate':p['path']}for p in cp if p['category']=='new-context'for v in p['views']}
sp={v['sequence']:p['path']for p in read(H/'selected-context-comparison-manifest.json')for v in p['views']}
def ref(fid):return{k:assets[fid].get(k,'')for k in ['file_id','folder_id','name','path','image_url','folder_url']}
groups=[
([27],'The complete White fin-panel image still lacks a 100 x 22 cm size witness. Returned legacy Fish files show triptychs or details, without a wider scene bound to the exact Long size.'),
([28,42],'The available White rough concentric pair is a product/group reference. The newly found Cup Ring isolated archive export supplies an individual view, not a wider installation. Processed Cup PNG lineage and physical finish claims remain separate.'),
([31,34],'The reference is a single White leaf panel on a product/workshop board. The additional Acanthus room candidate is a different Gold landscape design and cannot fill this exact White component role.'),
([32,33],'The source is a close finish detail without the complete leaf outline. The five workshop colour studies remain unbound by finish/position; the additional Gold room scene does not identify this option.'),
([35],'The Bronze Two Leaves reference is a single panel against bare stone. No wider exact Bronze room/garden scene was established; White and Gold family scenes are different finish options.'),
([36],'The Pale Blue/White marbled Two Leaves source is a standalone front view. No reviewed wider scene is bound to this exact marbled surface/design combination.'),
([47,48],'The source shows the kept Terracotta Decowaves member alone. Additional legacy garden pairs are White Frozen Decowaves; their warm lighting is not evidence of a Terracotta finish.'),
([49,50,51,52],'The linked metal/patina option is shown alone. The extra Dune Ripple scenes depict Gold, Rust, plain Verdigris or White variants; none establishes this exact retained finish combination in a wider scene.'),
([55],'The primary is the Three Leaves White panel. The extra Egyptian Palm scenes depict the extended multi-rib version; counting a related family photograph as the three-leaf build would change the component identity.'),
([63,67],'The White Fish triptych is a tight group view on brick. Returned archive copies show the same group/details without a wider room/garden scene bound to this individual member.'),
([64,65],'The coloured Frozen Fish Two source is a solo panel on bare stone. The White triptych and White garden scene cannot verify this exact Terracotta/Verdigris option.'),
([68,69,70],'The White Lava Moon reference is the complete three-strip product arrangement. Returned legacy images provide group/detail views; none establishes a wider White installation for this specific strip.'),
([71],'Extra White/Gold Leaf Curve files include complete and wider bare-brick product views. They do not show a room/garden setting with the exact kept panel.'),
([72],'Extra White Leaf Growth files show the panel on a red/grey display board or tight brick wall. The legacy Leaf Growth folder contains five White full/detail files, without a wider installed scene.'),
([73],'The White/Gold Leaf Growth reference remains a gold-leaf detail crop. The five directly listed legacy Leaf Growth files are White; they do not supply a complete Gold-finish scene.'),
([76,77,78,79,80,81,82,83],'The exact phase/finish reference is a standalone product view. Additional Moon Crater scenes include MCP1 Verdigris/Rust and MCP4 Verdigris, but do not establish this retained phase/finish combination. No finish transfer or phase renumbering was applied.'),
([84],'The Drip Rust wide-lip crater is shown alone. Related narrow-lip phases and their room scenes have different geometry/finish and cannot fill this option role.'),
([85],'The Moon Ring source is a single White relief on a display surface. No wider exact Moon Ring room/garden image was established in the reviewed references.'),
([86,87],'The current option includes an explicit border. The additional White Moonphase garden/bathroom groups show unbordered designs, so they do not establish this bordered variant.'),
([88],'The Silver MP4 source is a solo curved panel. Additional MP4 family scenes are White and do not verify the Silver option in a room/garden.'),
([89],'The Lava Corner Curve source is a small square product view. Other legacy lava/moon shapes are different reliefs, not a complete exact-option setting.'),
([93],'The additional Water Catcher file repeats a tight solo image against brick. It does not provide a wider room/garden view.'),
([95],'The Beige Panel Curves reference is a standalone panel on a plain surface. No exact wider installation was established from the reviewed sources.'),
([96],'The textured Gold Leaf panel is photographed closely against foliage. It is useful as a product view, without wider room/garden setting or installation evidence.'),
([97],'The extra Plant Form files repeat the tight White solo relief on brick. They do not supply wider room/garden context.'),
([105],'The White Soundwave source is a complete standalone landscape relief. Related Spiralmoon/Spiralfish settings depict different outlines and configurations; no exact Soundwave setting was established.'),
([108,109],'The Bronze Spiralfish member is represented only by finish details. Additional gallery/garden pair scenes are White and do not establish this Bronze component in context.'),
([110],'The Quarter Moon source is a complete individual White square. Additional Spiralmoon groups have different long end panels and are not an exact Quarter Moon size/version binding.'),
([113],'The White Strata source is a solo brick-wall product view. The extra pool setting depicts Blue Wash Verdigris; its finish cannot be transferred to White.'),
([114],'The Rust/Blue panel is propped on the floor against a display board. The surrounding workspace does not establish a wall installation or a composed room/garden presentation.'),
([116,117,118,119,120],'The marbled Wall Circle reference is an isolated circular product image, with backlighting on some files. No wider exact-pattern setting was established. Native RGB/size tuples and physical finish/cast identity remain separate; no additional circle options were created.'),
([121],'The exact Full / Acanthus and Moon landscape relief is shown alone. Near-square room crops and the small five-finish leaf study do not establish this full option in an identifiable series arrangement.'),
([122],'The Brancusi Totem source shows the retained tall folded work. Extra scenes include unrelated tall Egyptian rib panels; no complete, unambiguously identified Totem series arrangement was established.'),
([124,125,126],'The specific Dune Ripple Spiral finish is shown alone. The newly located Golden Spiral group contains a different White/Gold spiral beside a Gold landscape Dune panel; it does not depict this exact retained Dune Spiral option.'),
([129],'The marbled Black/White Egyptian Palm source is a single panel in a room presentation. No exact-finish multi-component group was established; White and Gold groups are not this finish.'),
([134],'All 83 Bronze/Verdigris Fountain Palm views examined are solo product, detail or propped display images. The dark indoor picture belongs to the same finish, as owner confirmed, but does not establish a multi-component series.'),
([135,136],'The Terracotta/Verdigris Frozen Fish Two references are solo views. The known White Fish triptych is a different finish and does not fill the exact coloured option series role.'),
([137],'Additional Leaf Form group photographs show the White pair. Warm exhibition lighting does not establish Gold LF2; no exact Gold member series binding was found.'),
([138],'The Black/White Half Moon source is a standalone marbled panel. White plain-moon/spiral pairs are a different finish and configuration, not an exact marbled series binding.'),
([140,141,142,143,144,145],'The exact Moon Crater phase/finish source is a solo product image. Additional grouped MCP4 Verdigris photographs do not establish this exact retained phase and finish as a member; no Verdigris/Rust or Silver/Bronze equivalence was inferred.'),
([146],'The Silver MP4 reference is a solo panel. The additional numbered Moonphase groups are White and do not verify Silver as a series member.'),
([152,153],'The Bronze Spiralfish component is shown only as a finish-detail crop. The additional full pairs and garden installations are White; no complete Bronze member-to-position series binding was established.')]
findings={n:text for ns,text in groups for n in ns};assert len(findings)==75
closed={
37:(None,'The current primary file already shows the complete Barbados Wave in an outdoor bath/garden setting. Reclassify the same native file as a source-qualified context presentation; no new image was created.','SINGLE panel above bath'),
46:('NC216','The complete White/Gold Golden Spiral is staged on a stone bench in a wider garden scene. It supplies garden-presentation coverage; it is visibly a staged display, not proof of a wall installation.','SINGLE panel on stone bench'),
53:('NC369','The Rust Waves component is the full panel at LOWER RIGHT / FOREGROUND, beside the Rust Spiral at upper left. Relief wave paths and finish match the retained Rust Waves option.','LOWER RIGHT / FOREGROUND'),
75:('NC538','The room presentation depicts the retained MCP1 Verdigris/Rust circular relief, with matching rim and patina distribution. Source-qualified illustration only; displayed scale and real installation are unverified.','SINGLE panel above sofa'),
111:('NC706','The White Spiralmoon is the single full square panel mounted above the garden fountain. The broad circular relief and terminal volute match the primary. This does not establish a water-adapted sculpture build.','SINGLE square above garden fountain'),
112:('NC731','The pool-wall presentation depicts the Blue Wash Verdigris Strata grid/curved-ridge design. It supplies a qualified setting reference; scene origin, real cast, installation and displayed scale remain unverified.','SINGLE panel on wall beside pool'),
123:('NC155','The White/Gold Golden Spiral is the complete RIGHT panel in the two-work countertop display; the Gold landscape Dune Ripple is at left. This establishes an image-level group association, not a fixed sellable set or shared specifications.','RIGHT'),
127:('NC369','The Rust Waves component is LOWER RIGHT / FOREGROUND, with the Rust Spiral at upper left. This identifies its position in the Rust Dune Ripple arrangement without merging the two individual products.','LOWER RIGHT / FOREGROUND')}
pending={
38:('NC032','A new White folded-panel garden presentation is relevant, but the flowing central folds differ from the primary photograph. Exact Brancusi 1 design/version and source-image binding remain to be confirmed.'),
40:('NC035','The new four-panel White garden presentation offers a Brancusi-family candidate. Bind which complete panel is Brancusi 2 and verify the fold outline/version before accepting it.'),
98:('NC671','The night-time Riyadh site photograph shows repeated vertical wave reliefs around the pool, including the far-left wall. The specific landscape product reference versus the installed rotation/custom build remains unbound; confirm the exact Dune Ripple panel position.'),
99:('NC671','The Riyadh pool photograph includes spiral reliefs, including the panel immediately right of the far-left wave panel. Bind the exact Shellmoon component/build and orientation; do not transfer dimensions from the whole site.'),
100:('NC671','The Riyadh pool photograph includes plain curved moon panels between wave and spiral forms. Identify the exact Plain Moon panel position/build from the original site record before accepting the current option link.'),
128:(None,'The linked Gold Egyptian Palm room pair is an existing series candidate, currently used in the in-situ verification task. Bind which complete Gold member is Egyptian Palm One before accepting the series association.'),
131:(None,'The four-member Fold/Unfold brick-wall group is an existing series candidate. Fan Folds may be present, but the rotated ridge pattern and exact member position remain unverified.'),
132:(None,'The four-member Fold/Unfold brick-wall group is an existing series candidate. Cultivation Folds may be present, but the rotated ridge pattern and exact member position remain unverified.'),
133:(None,'The four-member Fold/Unfold brick-wall group is an existing series candidate. Bind Fold Unfold 4 by complete ridge paths and orientation before accepting its member position.'),
139:(None,'The current primary depicts the two-tier White water-feature assembly. A group photograph exists, but this option is not separately bound to a specific individual tier/panel. Resolve that component assignment before requesting another group photograph.')}
def candidate_for(n,label):
 if label:return ref(nc[label]['file_id'])
 if n==128:return byseq[54]['prior_action']['reference']
 if n in [131,132,133]:return byseq[130]['prior_action']['reference']
 return byseq[n]['prior_action']['reference']
out=[]
for x in items:
 n=x['sequence']
 if x['review_state']!='QUEUED':continue
 d={'sequence':n,'evidence_plates':[mp[n]],'review_scope':'Primary reference plus relevant returned archive/context candidates reviewed. This is a bounded search, not proof of whole-Dropbox absence; catalogue and physical claims remain separate.'}
 if n in closed:
  label,finding,position=closed[n];newref=candidate_for(n,label);d.update(review_state='RESOLVED_VERIFIED_REFERENCE',finding=finding,position=position,new_photo_status='Available',new_reference=newref,next_action='No further action for this image role. Retain scene provenance, staging and physical-verification qualifications.')
  if label:d['evidence_plates'].append(nc[label]['plate'])
  if n in sp:d['evidence_plates'].append(sp[n])
  if n==111:d['evidence_plates'].append(nc['NC706']['plate'])
 elif n in pending:
  label,finding=pending[n];d.update(review_state='REVIEWED_BINDING_REQUIRED',finding=finding,new_photo_status='Verify existing image',new_reference=candidate_for(n,label),next_action=finding)
  if label:d['evidence_plates'].append(nc[label]['plate'])
  elif n in [128,131,132,133]:d['evidence_plates'].append(next(p['path']for p in plates if p['category']=='verification-pairs'and any(v['sequence']==(54 if n==128 else 130)for v in p['views'])))
 else:
  assert n in findings,n
  finding=findings[n];d.update(review_state='REVIEWED_CAPTURE_REQUIRED',finding=finding,new_photo_status='No verified image',next_action=('Photograph '+x['name']+' in a wider room/garden setting, with the full component visible and its finish identified.'if x['requested_role']=='In situ'else'Photograph '+x['name']+' with its identified series companions, keeping all outlines visible and recording this component position; retain a separate individual product record.'))
  familyplates=[p['path']for p in cp if p['category']=='new-context'and any(v['family'].lower()==x['family'].lower()for v in p['views'])]
  d['evidence_plates']+=familyplates
 if n in [72,73]:d['evidence_plates'].append(str(H/'plates/legacy-leaf-growth.jpg'))
 d['evidence_plates']=list(dict.fromkeys(d['evidence_plates']));out.append(d)
assert len(out)==93
(H/'missing-context-review-decisions.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'decisions':len(out),'resolved':len(closed),'binding_required':len(pending),'capture_required':len(out)-len(closed)-len(pending)}))
