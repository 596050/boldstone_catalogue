"""Explicit human review decisions after viewing the current binary-verified images."""
import json
from pathlib import Path
project=Path(__file__).resolve().parents[1];ev=project/'evidence';reviews=project/'reviews'
model=json.loads((ev/'catalogue_model.json').read_text())
selected=json.loads((ev/'batch02_and_match_selection.json').read_text())['candidates']
receipts={r['id']:r for r in json.loads((ev/'additional_source_receipts.json').read_text())}

details={
'Bone Spiral wall sculpture':('The same illuminated two-panel Bone Spiral photograph is present in the source gallery and current Bone Spiral White group.',False),
'Brancusi wall sculpture':('The primary gallery image shows the same two-panel white Brancusi diptych. Dimensions and weight remain native-offer claims for the pair.',False),
'Deco Dune Ripple wall sculpture':('The primary image shows the same two tall panels in the current diptych group; do not apply the pair specifications to a single panel.',False),
'Golden Spiral wall sculpture':('Gallery image 2 shows the same single white-and-gold spiral panel. The Dropbox family is Deco Palm and Spiral, and the precise member is Spiral 1 White and Gold.',False),
'Japanese Raked Water Path wall sculpture':('The same four-panel horizontal arrangement is pictured. The folder label lists designs 1, 2 and 3; it still depicts four physical positions. Panel count is distinct from the count of different designs.',True),
'Mirror Moons wall sculpture':('Manual visual comparison supports the same two white half-moon panels and orientation. Tonal differences prevent a pixel-equivalence claim.',False),
'Moon and Shellwave wall sculpture':('Manual visual comparison supports the same two-panel Half Moon and Spiral White composition. Tonal differences prevent a pixel-equivalence claim.',False),
'Moon Fishwave wall sculpture':('Gallery image 2 shows the same two-panel white Moon Fishwave arrangement.',False),
'Moonphases Five wall sculpture':('The same five-panel horizontal arrangement is pictured, with a repeated phase. The current label names designs 1, 2, 3 and 4; four design numbers do not imply four installed panels.',True),
'Moonphases Three wall sculpture':('The same three-panel white arrangement appears in the garden scene. Scene correspondence does not independently prove a real installation or suitability.',True),
'Moonspiral wall sculpture':('Gallery image 4 matches a mixed collection photograph of two wider spiral/phase panels, while the offer primary depicts a tall Moonspiral. Keep this as a gallery reference; do not assign Moonspiral dimensions, weight or price to the mixed group.',True),
'Shellwave Between Two Concave Moons wall sculpture':('Gallery image 3 matches a four-panel composition in Four Spiral and Wave White, while the native offer title describes a three-part arrangement. This is alternative-arrangement evidence; do not apply whole-offer dimensions or weight to all four pictured panels.',True),
'Spiralfish Wave and Tide wall sculpture':('Gallery image 5 shows the same two-panel white relief and central seam. This directly supports the member arrangement; separate mixed gallery scenes remain unassigned.',False),
'Spiralmoon wall sculpture':('Gallery image 4 matches a garden scene in Mixed Sculptures Unclassified. A small spiral panel is visible, but its exact member identity and dimensions are not established by this scene. Retain a gallery reference only.',True),
'Three Frozen Decowaves wall sculpture':('Gallery image 3 shows two tall panels in Frozen Decowaves 1 and 2 White In Situ, while the native offer is Three Frozen Decowaves. This supports a two-component gallery reference, not the complete three-part offer.',True),
'Two Leaf Forms wall sculpture':('The same two-panel Leaf Form Two White arrangement is pictured. The current folder label does not enumerate both components; do not infer a single-panel sale from that label.',True),
'Wave Between Moonshadow wall sculpture':('The primary gallery image shows the same three-panel Wave and Moonshadow composition: two outer panels and one central spiral panel.',False),
}
gallery_only={'Moonspiral wall sculpture','Shellwave Between Two Concave Moons wall sculpture','Spiralmoon wall sculpture','Three Frozen Decowaves wall sculpture'}
decisions=[]
for r in selected:
    receipt=receipts[r['candidate']['id']];assert receipt['hash_verified']
    detail,caution=details[r['title']]
    accepted=r['title'] not in gallery_only
    decisions.append(dict(pid=r['pid'],title=r['title'],asset_id=receipt['id'],basis='VISUALLY CONFIRMED DIRECT MEMBER IMAGE' if accepted else 'CONFIRMED GALLERY REFERENCE; OFFER COMPOSITION UNRESOLVED',scope='Pictured member / arrangement only; native physical claims remain unmeasured' if accepted else 'Gallery asset correspondence only; no whole-offer specifications assigned to the pictured group',accepted_image=accepted,image_correspondence=True,detail=detail,caution=caution,ss_image_order=r['image_order'],ss_image_path=r['image_path'],current_source_sha256=receipt['sha256']))
(ev/'established_image_decisions.json').write_text(json.dumps(decisions,ensure_ascii=False,indent=2))

groups=[g for g in model['groups'] if g['family']=='Acanthus']
g_by_name={g['group_name']:g for g in groups}
family_media=json.loads((ev/'batch02_media.json').read_text())
designs=[
 dict(design_id='BSC-0002',title='Acanthus One Leaf',description='Single curved leaf/arc relief on a square panel. Mixed workshop photographs are retained separately.'),
 dict(design_id='BSC-0003',title='Acanthus Two Leaves',description='Two swept leaf/arc forms on a square relief panel. Finishes are separate records; finish names follow current folder labels.'),
 dict(design_id='BSC-0004',title='Acanthus and Moon / Acanthus Full',description='Rectangular relief of overlapping arcs/crescents. Portrait and landscape photographs are rotations of the same design, not additional measured sizes.'),
 dict(design_id='BSC-0005',title='Acanthus Flower',description='Square flower-like relief with a central pointed oval and side curves.'),
]
def sculpture(suffix,design,finish,names,offer='',dimensions='',weight='',material='',fixing='',price='',scope=''):
    gg=[g_by_name[n] for n in names]
    return dict(sculpture_id=design+'-'+suffix,design_id=design,title=next(d['title'] for d in designs if d['design_id']==design),finish=finish,leaf_ids=[g['leaf_id'] for g in gg],group_ids=[g['group_id'] for g in gg],files=sum(g['assets'] for g in gg),offer_keys=[offer] if offer else [],dimensions_cm=dimensions,weight_kg=weight,material=material,fixing=fixing,native_price=price,price_unit='Unencoded export currency' if price else '',source_scope=scope or ('Native Squarespace description; measurements and material are source claims, not physical checks' if offer else 'Images and folder label only; no matching native offer identified in the supplied wall datasets'),shopify_state='No matching native Shopify wall offer identified in supplied main, older or seed datasets',unresolved='Packed dimensions/weight not supplied; image-only finishes have no assigned material, size or weight.',review_state='SOURCE SPECIFICATIONS MAPPED; PHYSICAL CLAIMS UNMEASURED' if offer else 'VISUAL DESIGN / FINISH MAPPED; NATIVE SPECIFICATIONS NOT FOUND')
sculptures=[
 sculpture('WH','BSC-0002','White',['Acanthus One Leaf White']),
 sculpture('BR','BSC-0003','Bronze / brown surface effect',['Acanthus Two Leaves Bronze'],'SQ:6aa01abf4b08934e6b0d3d93','30 × 30 × 6','','Plaster','Recessed rear fixing','77.79'),
 sculpture('MG','BSC-0003','Marbled green and white (label; detail-only evidence)',['Acanthus Two Leaves Marbled Green and White']),
 sculpture('PB','BSC-0003','Pale blue and white',['Acanthus Two Leaves Pale Blue and White']),
 sculpture('PW','BSC-0003','Pewter (label; detail-only evidence)',['Acanthus Two Leaves Pewter']),
 sculpture('WH','BSC-0003','White',['Acanthus Two Leaves White','Acanthus Two Leaves White In Situ']),
 sculpture('WB','BSC-0003','White and black (context images only; production unconfirmed)',['Acanthus Two Leaves White and Black']),
 sculpture('GL','BSC-0004','Gold leaf as stated by Squarespace',['Acanthus and Moon Gold Leaf','Acanthus and Moon Gold Leaf In Situ'],'SQ:6aa01ad04190ef386f1d9f61','50 × 30 × 6','Approximately 8','Plaster','Recessed rear fixing','250.00'),
 sculpture('WH','BSC-0004','White',['Acanthus and Moon White','Acanthus and Moon White In Situ'],'SQ:6aa567506a2bd34c0d1272cd','50 × 30 × 6','Approximately 8','Plaster','Recessed rear fixing','175.00'),
 sculpture('WH','BSC-0005','White',['Acanthus Flower White','Acanthus Flower White In Situ'],'SQ:6aa57c795a77421307a3f036','30 × 30 × 6','Approximately 4','Plaster','Recessed rear fixing','175.00'),
]
live={r['product_id']:r for r in json.loads((ev/'live_acanthus_verification.json').read_text())}
for sc in sculptures:
    if sc['offer_keys']:
        current=live[sc['offer_keys'][0][3:]]
        sc.update(public_price=current['price'],public_price_currency=current['currency'],public_url=current['url'],public_observed=current['observed'])
        assert current['export_body_matches_live']
        sc['source_scope']+='; live body agrees on 2026-10-16, native ID and SKU verified'
    if sc['sculpture_id'] in ['BSC-0003-MG','BSC-0003-PW']:
        sc['review_state']='PROVISIONAL DESIGN FROM DETAIL; FULL MEMBER AND NATIVE SPECS OPEN'
    if sc['sculpture_id']=='BSC-0003-WB':
        sc['review_state']='DEPICTED DESIGN / FINISH; PHYSICAL VARIANT AND NATIVE SPECS OPEN'
group_decisions=[]
for g in groups:
    sc=next((s for s in sculptures if g['leaf_id'] in s['leaf_ids']),None)
    mixed=g['group_name'] in ['Acanthus and Moon and Others Together','Acanthus One Leaf Assorted Colours']
    issues=[]
    if mixed:issues.append('Mixed collection / workshop photograph or cropped detail; do not assign this whole group to one sculpture or finish')
    if 'Marbled Green' in g['group_name'] or 'Pewter' in g['group_name']:issues.append('Only surface/detail imagery is available; exact full member identity remains provisional')
    if 'White and Black' in g['group_name']:issues.append('Only context scenes are available; no independently documented physical variant')
    if 'In Situ' in g['group_name']:issues.append('Context-image provenance is not independently established')
    if not g['assets']:issues.append('Empty current folder; no current asset supports an additional sculpture')
    group_decisions.append(dict(leaf_id=g['leaf_id'],design_id=sc['design_id'] if sc else '',sculpture_id=sc['sculpture_id'] if sc else '',kind='Mixed / partial workshop reference' if mixed else 'Context / in-situ media' if 'In Situ' in g['group_name'] or 'White and Black' in g['group_name'] else g['kind'],issues=issues,media_state='ALL CURRENT FILES VIEWED' if g['assets'] else 'EMPTY FOLDER CONFIRMED',spec_state=sc['review_state'] if sc else 'MIXED REFERENCE; NO SINGLE SCULPTURE SPECIFICATIONS ASSIGNED',next_action='Resolve exact member and finish from full-front evidence' if mixed or any('provisional' in x for x in issues) else 'Confirm missing or conflicting source facts; retain source-only claim status'))
asset_roles=[]
for r in family_media:
    role='FULL / DETAIL / REAR REFERENCE VIEWED; NO SCALE MEASUREMENT'
    if 'In Situ' in r['group'] or 'White and Black' in r['group'] or r['file_id']=='id:cnqzTNngPVsAAAAAAAt4Xw':role='CONTEXT IMAGE VIEWED; REAL INSTALLATION / VISUALISATION PROVENANCE OPEN'
    if r['group'] in ['Acanthus and Moon and Others Together','Acanthus One Leaf Assorted Colours']:role='MIXED / PARTIAL REFERENCE VIEWED; NO ONE-TO-ONE SCULPTURE IDENTITY'
    if r['group'] in ['Acanthus Two Leaves Marbled Green and White','Acanthus Two Leaves Pewter']:role='DETAIL-ONLY DESIGN CANDIDATE; FULL MEMBER IDENTITY OPEN'
    asset_roles.append(dict(file_id=r['file_id'],role=role))
batch=dict(batch_id='CAT-FAM-002',family='Acanthus',review_state='ALL 76 FILES VIEWED; SOURCE SPECS MAPPED; IDENTITY / SOURCE QUESTIONS OPEN',scope='All 16 current groups accounted for, including one empty group. Four visual designs, ten design/finish records and two mixed-reference groups; detail-only finishes remain provisional.',designs=designs,sculptures=sculptures,groups=group_decisions,asset_roles=asset_roles,
 open_questions=[
 'Confirm full member identity for the marbled-green and pewter detail-only images and identify the pieces in mixed workshop photographs.',
 'Confirm whether white-and-black and other context images depict manufactured variants or visualisations.',
 'Confirm the bronze panel weight: its native description gives no kg value, its raw weight 11.02 has no encoded unit, and historical family brochures give conflicting square-panel weights.',
 'Confirm whether the 50 × 30 cm panel weighs approximately 8 kg as the current export states or 8.5 kg in older family brochure text; retain both until resolved.',
 'Clarify courtyard / exterior suitability and protective finish for the plaster offers; the lifestyle copy alone does not establish weather resistance.',
 'Provide packed dimensions/weight and measured product/fixing details where required. Native Unlimited stock and one-of-a-kind copy are not a count of manufactured stock.'
 ],next_batch='CAT-FAM-003: Ammonite',sources=[dict(id='BATCH02-SQ',observed='2026-10-16 review of 2026-10-15 export',url='',finding='Four native Squarespace offers mapped to specific Acanthus design/finish records. No matching native Shopify wall offers identified; no live store edit performed.')])
for row in live.values():batch['sources'].append(dict(id='LIVE-ACANTHUS-'+row['product_id'],observed=row['observed'],url=row['url'],finding='Live native product ID and SKU verified; full public description agrees with supplied export. Public price '+str(row['price'])+' '+row['currency']+'. Public InStock status does not establish manufactured quantity. Evidence: evidence/live_acanthus_verification.json'))
(reviews/'batch02.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2))
print(json.dumps(dict(direct_member_images=sum(r['accepted_image'] for r in decisions),gallery_references=sum(not r['accepted_image'] for r in decisions),acanthus_designs=len(designs),acanthus_sculpture_finish_records=len(sculptures),acanthus_groups=len(groups),acanthus_files=len(family_media))))
