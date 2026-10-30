"""Explicit observations made from all ten contact sheets and six focused boards.

Role describes the exported source photograph. It does not assign a variant or
confirm a manufactured finish, dimensions, fitted hardware, stock, or price.
"""

# review ID | role | native correspondence | SQ correspondence | observation
# F = visually corresponding photograph at displayed resolution.
# R = crop/framing/contrast rendition of the depicted photograph/composition.
# U = same scene/design candidate only; exact photograph unresolved.
# A = accept the explicitly displayed SQ photograph; X = reject numerical SQ top.
OBSERVATIONS = """
S001|detail|F|A|Close relief view; panel edges are outside the frame.
S002|group|F|A|Two panels with smooth and rough surfaces; shared product/finish context.
S003|individual|F|A|Complete smooth White panel in portrait orientation.
S004|installation|F|A|Blue-lit wider display; lighting does not establish a separate physical finish.
S005|installation|F|A|Wider blue-lit room display; creation origin not newly certified.
S006|group_detail|F|X|Cropped triptych detail in the blank-SKU Frozen Fish draft. No FFL1 identity or current size evidence; reject unrelated numerical SQ candidate.
S007|group|F|A|Spiral and Wave pair; preserve both components as an arrangement.
S008|detail|F|A|Close spiral relief detail; no full component boundary.
S009|detail|F|A|Close Wave relief detail.
S010|individual|R|A|Same Egyptian Palm panel and brick display, with framing differences; no exact encoded-file claim.
S011|individual|F|A|Complete round concavity on square panel. Source title Concave Moon is retained; current reference is Moon Water Catcher, not an automatic MCP4 alias.
S012|individual|F|A|Complete Moonwave panel against brick; close display image.
S013|detail|F|A|Moonwave spiral and upper relief detail.
S014|individual|R|A|Complete Moonwave against red wall; crop/color rendition differs.
S015|detail|F|A|Close Moonwave spiral detail.
S016|installation|U|A|Same red-wall room with lamp and chair, but candidate framing/relative positions differ. Retain scene candidate only until exact-photo proof.
S017|group|F|A|Four Raked Spiral panels shown in a horizontal row.
S018|installation|F|A|Wider garden setting of the nine-panel arrangement.
S019|group|F|X|Nine-panel garden arrangement, exact current Dropbox scene. Reject unrelated Golden Spiral SQ numerical candidate; no same-frame SQ correspondence established in the 445-entry comparison.
S020|installation|F|A|Wider glazed room and garden arrangement setting.
S021|group|U|A|White Ammonite pair against wood; current candidates show same design/setting with different framing and central gap. Exact-photo binding unresolved.
S022|group_detail|U|A|Ammonite pair detail; central gap and framing differ among current candidates. Exact-photo binding unresolved.
S023|group_detail|F|A|Ammonite paired detail including the central seam.
S024|installation|F|A|White Ammonite pair above a table in a fireplace room.
S025|installation|F|A|White Ammonite pair above seating in a lit interior.
S026|installation|F|A|Wider seating-area view with Ammonite pair.
S027|installation|F|A|Closer seating-area view with Ammonite pair.
S028|group|F|A|Two Echo Sound panels with the concentric relief joined visually.
S029|group|F|A|Same Echo Sound components in a different arrangement.
S030|group|F|A|Deco Palm and Spiral pair against brick.
S031|group|F|A|Two half-moon placements. Do not infer two distinct designs from the photograph.
S032|individual|F|A|Complete Fan Folds relief against brick; keep existing Fold Unfold association scope.
S033|individual|F|A|Complete Cultivation Folds relief against brick; keep existing Fold Unfold association scope.
S034|group|F|A|Two Frozen Decowaves long panels in a vertical arrangement.
S035|group|F|A|Two Frozen Decowaves long panels in a horizontal arrangement.
S036|installation|F|A|Two-panel garden wall display.
S037|installation|F|A|Wider two-panel garden wall display with planting.
S038|group|R|A|Three long panels; different contrast/color rendition of the group. No finish change inferred.
S039|group|F|A|Two-panel image reused in the Three Frozen Decowaves gallery and in the Two-panel gallery. Preserve visible pair scope.
S040|group|F|A|Two-panel image retained in the Three Frozen Decowaves product gallery; do not promote gallery title to visible panel count.
S041|individual|F|A|One complete long panel on a wider brick wall. Gallery membership alone does not assign a variant image.
S042|installation|F|A|Two-panel garden display reused in Three Frozen Decowaves gallery.
S043|installation|F|A|Wider two-panel garden display reused in Three Frozen Decowaves gallery.
S044|detail|F|A|Rough/Fossil Sand Ripple close surface detail.
S045|group|F|A|Same smooth-and-rough pair also appears in Smooth Sand Ripple gallery; cross-finish context only.
S046|group|F|A|Spiral with two Palm panels; three-panel arrangement.
S047|group|F|A|Two Leaf Form placements. Owner correction retains one existing White design shown twice; no new component identity.
S048|individual|F|A|One complete White Leaf Form panel.
S049|detail|F|A|Leaf Form relief detail.
S050|group|F|A|White Brancusi pair against brick.
S051|group|R|A|Sunlit White Brancusi pair corresponds to current 040, with crop/framing differences. Reject the numerical 084 view as exact-photo evidence.
S052|group_detail|F|A|White Brancusi pair detail including both panels.
S053|group_detail|F|A|Another White Brancusi pair detail.
S054|installation|F|A|Gold Leaf single-panel room reference reused in the White Brancusi pair gallery. Preserve Gold Leaf-only context.
S055|installation|F|A|Gold Leaf single-panel room reference; no White-finish image assignment.
S056|installation|F|A|Gold Leaf single-panel room reference with seating; origin not newly certified.
S057|group|F|A|Moonphases group on brick. Preserve existing numbered membership without converting the historical Five title to five verified new designs.
S058|group|R|A|Three Moonphase panels against wood, contrast rendition differs; no finish reassignment.
S059|group|R|A|Three Moonphase panels against brick with framing/contrast differences.
S060|group|R|A|Three Moonphase panels in a warm wall-display rendition; color alone does not establish Cream/White variant identity.
S061|installation|F|A|Three Moonphase panels above a garden bench.
S062|group|F|A|Closer three-panel wall arrangement.
S063|installation|F|A|Garden water display with spaced Moonphase panels.
S064|installation|F|A|Single Moonphase panel above a water outlet; no water-ready construction or measured specification inferred.
S065|installation|F|A|Wider garden water scene.
S066|group|R|A|Moon and Shellwave triptych, different framing/color rendition; group only.
S067|group_detail|F|A|Triptych close view; no isolated individual view inferred.
S068|group|F|A|Four separated Moon and Shellwave panel placements; arrangement context only.
S069|installation|F|A|Triptych in a room/green-wall scene study; creation origin unverified.
S070|installation|F|A|Triptych in a closer room scene study; creation origin unverified.
S071|group|F|A|Close triptych wall display, no wider installation verification.
S072|group|F|A|Moon and Shellwave spiral and half-moon pair; preserve current names 1 and 2.
S073|group_detail|F|A|Moon and Shellwave pair detail.
S074|installation|F|A|Moon and Shellwave pair in a room scene.
S075|group|F|A|Bone Spiral two-panel arrangement; separate from Bone Water Spiral.
S076|group_detail|F|A|Bone Spiral paired detail including seam.
S077|group|F|A|Bone Spiral pair on a wider brick background.
S078|installation|F|A|Bone Spiral pair in a sitting room.
S079|group|R|A|Spiralfish Wave and Tide paired relief composition, different framing/color rendition. No finish or cast identity inferred.
S080|detail|F|A|Spiralfish Wave and Tide spiral relief detail.
S081|detail|F|A|Close Spiralfish relief detail; an In Situ folder name does not make it an installation photograph.
S082|installation|F|A|Mixed sculpture room/gallery context; no new identities or stock counts assigned from the group.
S083|group_detail|F|A|Spiralfish paired relief detail with central seam.
S084|detail|F|A|Single Spiralfish relief close-up.
S085|individual|R|A|Complete Spiralmoon on brick, different framing/contrast rendition.
S086|detail|F|A|Spiralmoon relief detail.
S087|installation|F|A|Spiralmoon in a garden water setting; no water-ready material/fixing claim.
S088|installation|F|A|Wider mixed garden context with a small Spiralmoon display.
S089|installation|F|A|Wider mixed garden setting; target is small/partly obscured by branches. Keep contextual qualification; no new exact component assignment.
S090|installation|F|A|Single Spiralmoon in a wider brick-wall display.
S091|individual|F|A|Complete Leaf Growth panel against red wall.
S092|detail|F|A|Lower Leaf Growth close-up.
S093|detail|F|A|Middle Leaf Growth close-up.
S094|detail|F|A|Leaf Growth central/upper relief close-up.
S095|detail|F|A|Upper Leaf Growth close-up.
S096|individual|F|A|Complete Verdigris Dune Ripple Waves panel; no measurements inferred.
S097|individual|F|A|Gold Spiral relief on a patterned backdrop; retain actual current Dune Ripple reference despite historical product title.
S098|individual|F|A|Complete Moonspiral 2 White panel.
S099|installation|F|A|Two Moonspiral panels in a seating-room setting.
S100|individual|F|A|Complete Moonspiral panel posed at a beach; outdoor display, not installed hardware evidence.
S101|group|F|A|Mixed two-panel workshop/display photograph; do not create a component identity from group membership.
S102|group|F|A|Three Moonspiral panels in a row.
S103|group|F|A|Two Moonspiral panel placements.
S104|detail|F|A|Moonspiral 2 spiral detail.
S105|group|F|A|Egyptian Palm 1 and 2 White pair against brick.
S106|group|F|A|Egyptian Palm pair against a plain dark background.
S107|individual|F|A|Complete Gold Leaf Egyptian Palm single panel.
S108|group|F|A|Moon Fishwave arrangement/display view; retain existing component associations without new physical quantity claims.
S109|group|F|A|Moon Fishwave two-panel arrangement against brick.
S110|group|F|A|Wave Between Moonshadow three-panel arrangement.
S111|group|F|A|Mixed display with Wave and Moonshadow plus two lower panels; gallery context, no new component identities.
S112|individual|R|A|Swan Wing Folds matches retained Fold Unfold 1 source As7Gw with portrait crop versus wider current frame. Reject unrelated Moon Fishwave numerical candidate.
S113|detail|F|A|White and Gold Spiral close-up; finish pattern retained visually only.
S114|individual|F|A|Complete White and Gold Spiral panel on a dark pebble backdrop.
S115|detail|F|A|Second White and Gold Spiral close-up.
S116|individual|F|A|Complete White Timeless Spiral panel against a colored wall.
S117|group|F|A|Small Ammonite paired arrangement against white brick; panel specifications remain individual and qualified.
"""

OVERRIDE_NATIVE_IDS = {
    'S051': 'id:cnqzTNngPVsAAAAAAAuZfg',
    'S112': 'id:cnqzTNngPVsAAAAAAAs7Gw',
}

FOCUSED_REVIEW_IDS = {'S016', 'S021', 'S022', 'S051', 'S089', 'S112'}
