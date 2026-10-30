"""Preserve the user's Ammonite panel split and size-specific source evidence."""
import hashlib
import json
from pathlib import Path


def apply_ammonite_update(model, root):
    root = Path(root)
    ev = root / 'evidence'
    refresh = ev / 'dropbox-refresh-2026-10-17'
    listing_path = refresh / 'ammonite_live_listing.json'
    media_path = refresh / 'ammonite_new_media.json'
    if not listing_path.exists() or not media_path.exists():
        return model
    listing = json.loads(listing_path.read_text())
    media = json.loads(media_path.read_text())
    assert not listing['parent']['has_more'] and all(not c['has_more'] for c in listing['children'])
    folders = {c['folder']['file_id']: c for c in listing['children']}
    # Size, member, new solo folder, representative file, original pair, original context.
    definitions = [
        ('Small', 1, 'id:cnqzTNngPVsAAAAAAA53Fw', 'id:cnqzTNngPVsAAAAAAA53GA', 'id:cnqzTNngPVsAAAAAAAyc8g', 'id:cnqzTNngPVsAAAAAAAyh9A'),
        ('Small', 2, 'id:cnqzTNngPVsAAAAAAA53GQ', 'id:cnqzTNngPVsAAAAAAA53Gg', 'id:cnqzTNngPVsAAAAAAAyc8g', 'id:cnqzTNngPVsAAAAAAAyh9A'),
        ('Large', 1, 'id:cnqzTNngPVsAAAAAAA53Ew', 'id:cnqzTNngPVsAAAAAAA53FA', 'id:cnqzTNngPVsAAAAAAAyh8g', 'id:cnqzTNngPVsAAAAAAAyh8w'),
        ('Large', 2, 'id:cnqzTNngPVsAAAAAAA53FQ', 'id:cnqzTNngPVsAAAAAAA53Fg', 'id:cnqzTNngPVsAAAAAAAyh8g', 'id:cnqzTNngPVsAAAAAAAyh8w'),
    ]
    expected = {g for row in definitions for g in [row[2], row[4], row[5]]}
    assert set(folders) == expected, 'Ammonite folder changes need another scoped review'
    groups = {g['id']: g for g in model['groups']}
    for gid in expected:
        if gid in groups:
            child = folders[gid]
            groups[gid].update(name=child['folder']['name'], path=child['folder']['path'], files=len(child['entries']))
    for n, (size, member, gid, fid, pair, context) in enumerate(definitions, 354):
        assert len(folders[gid]['entries']) == 1 and folders[gid]['entries'][0]['file_id'] == fid
        group = groups.get(gid)
        if group is None:
            group = dict(group_ref=f'G{n:03}', id=gid, family='Ammonite', case_number=None,
                         earlier_full_group_review=False, earlier_observations='', source_decision={})
            assert group['group_ref'] not in {g['group_ref'] for g in model['groups']}
            model['groups'].append(group)
            groups[gid] = group
        group.update(name=folders[gid]['folder']['name'], path=folders[gid]['folder']['path'], files=1,
                     selected=[fid], finish_appearance='White', role='Single component image',
                     component_ids=[f'BC-AM-{member}'], has_context=False, has_arrangement=False,
                     assignment_status='User-organised panel/size folder; reference design visually checked 17 October 2026',
                     review_basis=f'The supplied {size.lower()} member {member} reference was viewed. It depicts the {"left" if member == 1 else "right"} panel of the corresponding pair. Image production provenance is unconfirmed.',
                     refreshed_utc=listing['observed_utc'])
    assets = {a['id']: a for a in model['assets']}
    downloaded = {a['id']: a for a in media['files']}
    live_ids = set()
    for gid, child in folders.items():
        for entry in child['entries']:
            fid = entry['file_id']
            live_ids.add(fid)
            if fid not in assets:
                source = downloaded[fid]
                assets[fid] = dict(id=fid, content_hash=source['content_hash'], bytes=source['size'],
                                   thumb='', full=source['local_path'], origin_evidence={
                                       'local_sha256':source['sha256'], 'retrieved_utc':listing['observed_utc'],
                                       'provenance':'Supplied individual reference image; camera/render origin unconfirmed'})
                model['assets'].append(assets[fid])
            assert assets[fid]['bytes'] == entry['file']['size'], 'Retrieve changed Ammonite bytes before applying'
            assets[fid].update(folder_id=gid, group=child['folder']['name'], family='Ammonite', name=entry['name'], path=entry['path'])
    assert {a['id'] for a in model['assets'] if a['family']=='Ammonite'} == live_ids
    assert len(live_ids) == 269
    components = {c['component_id']: c for c in model['components']}
    source_index = json.loads((ev / 'evidence_index.json').read_text())
    maker = next(r['values'] for r in source_index['manufacturing_rows'] if r['row'] == 93)
    classifications_path = root / 'reviews/user_classifications.json'
    approved_names = {}
    if classifications_path.exists():
        for decision in json.loads(classifications_path.read_text())['decisions']:
            approved_names.update(decision.get('confirmed_size_variant_names', {}))
    price_candidates_path = ev / 'price-source-review-2026-10-17/component_source_candidates.json'
    price_candidates = json.loads(price_candidates_path.read_text())
    variants = []
    for size, member, gid, fid, pair, context in definitions:
        cid = f'BC-AM-{member}'
        side = 'left' if member == 1 else 'right'
        variant_id = f'AM-{size[0]}{member}'
        offer_ref = 'O048' if size == 'Small' else 'O018'
        weight = ('Trade draft: 5.5 kg each; retail draft: 6.5 kg each; maker: 6–8 kg calculated. Current specimen unweighed.'
                  if size=='Small' else 'Trade and retail drafts: estimated 20 kg each; maker Size B: calculated 20–22 kg each. Current specimen unweighed.')
        dimensions = ('Native: 52 × 25 × 5 cm; maker: 52 × 26 cm face, 5–7 cm side depth; trade/retail draft: 50 × 25 cm face. Version conflict remains.'
                      if size=='Small' else 'Native: 120 × 60 × 6 cm; trade/retail drafts: 120 × 60 cm face. Current cast unmeasured.')
        primary_refs = [fid, *groups[pair]['selected'], *groups[context]['selected']]
        applicable = [x for x in price_candidates if cid in x['component_ids'] and x['variant']==size+' Ammonite']
        variant = dict(variant_id=variant_id, component_id=cid, variant_name=approved_names.get(variant_id, f'Ammonite {size} {member} / {side.title()} Panel'),
                       size_class=size, member=member, offer_ref=offer_ref, primary_folder_id=gid,
                       primary_file_id=fid, folder_ids='\n'.join([gid,pair,context]), example_file_ids='\n'.join(primary_refs),
                       dimensions_available=dimensions, weight_available=weight,
                       material_available='Native: white marble stone finish. Historical maker '+('Size A' if size=='Small' else 'Size B')+' description: White Marble Stone Finish Jesmonite AC730. Current cast substrate/finish formulation unverified.',
                       fixing_available=('Historical Size A: one wall fixing per panel. Generic instructions: one small stainless-steel fixing, centre back in the top third, matching height across the series. Current position/load capacity unverified.' if size=='Small' else 'Historical Size B: two LARGE wall fixings set into the back of EACH panel. Exact positions, hardware/load specification and current cast applicability unverified.'),
                       individual_price=None, availability=None, care_packaging='No complete size-specific care/packaging record verified.',
                       draft_arrangement_price_sources=applicable, standalone_offer_refs=[], physical_specs_verified=False,
                       image_provenance='Supplied isolated reference; camera/render origin unconfirmed',
                       maker_panel_code=('AMS' if size=='Small' else 'AML')+str(member),
                       suitability_available=('Native small pair: interior and outdoor wall decor; current cast/finish suitability not certified.' if size=='Small' else 'Native large pair: large interior or garden wall; current cast/finish suitability not certified.'),
                       lead_time_available='No current panel-specific production lead time established.',
                       specification_gaps='Confirm current dimensions/depth and weight; resolve source versions; confirm substrate/finish and fixing hardware/load; obtain individual sale price, availability, lead time, care and packed dimensions/weight.',
                       photo_coverage='Individual reference identified; pair and in-situ/context folders retained for this size. No solo in-situ photograph or client-installation provenance certified.',
                       specification_sources=f'{offer_ref}: native Squarespace/Shopify pair; manufacture-stevensons:Sheet1!row93 (Size '+('A' if size=='Small' else 'B')+'); '+ '; '.join(f'{x["source_id"]}:p{x["page"]}' for x in applicable),
                       identity_status='USER CONFIRMED' if variant_id in approved_names else 'User-organised size variant; identity review pending')
        variants.append(variant)
        for row in model['bom']:
            if row['offer_ref']==offer_ref and row['component_id']==cid:
                row.update(component_name=components[cid]['name'], variant_id=variant_id,
                           variant_name=variant['variant_name'], folder_ids=variant['folder_ids'],
                           example_file_ids=variant['example_file_ids'], component_weight=weight,
                           panel_dimensions=dimensions, panel_material=variant['material_available'], panel_fixing=variant['fixing_available'],
                           panel_suitability=variant['suitability_available'], panel_care_packaging=variant['care_packaging'],
                           panel_lead_time=variant['lead_time_available'], panel_sources=variant['specification_sources'],
                           panel_gaps=variant['specification_gaps'], panel_photos=variant['photo_coverage'], maker_panel_code=variant['maker_panel_code'],
                           cautions=f'{size} size variant. Individual sale price/availability and physical specifications remain unconfirmed. Native whole-pair weight and price retain pair scope.')
    model['size_variants'] = [v for v in model.get('size_variants',[]) if v['component_id'] not in ['BC-AM-1','BC-AM-2']] + variants
    for cid in ['BC-AM-1','BC-AM-2']:
        c=components[cid]
        vv=[v for v in variants if v['component_id']==cid]
        c['name']=f'Ammonite {cid[-1]} / {"left" if cid.endswith("1") else "right"} panel'
        folder_ids=list(dict.fromkeys(gid for v in vv for gid in v['folder_ids'].splitlines()))
        examples=[v['primary_file_id'] for v in vv] + list(dict.fromkeys(fid for v in vv for fid in v['example_file_ids'].splitlines() if fid not in [x['primary_file_id'] for x in vv]))
        c.update(group_refs=[groups[g]['group_ref'] for g in folder_ids], folder_ids='\n'.join(folder_ids),
                 example_file_ids='\n'.join(examples), weight_available='Small: '+vv[0]['weight_available']+' Large: '+vv[1]['weight_available'],
                 notes='17 October 2026: user split Small 1/2 and Large 1/2 into four individual size variants. Stable design IDs BC-AM-1 and BC-AM-2 are retained. Small and large images/specifications remain separate size/version records; equivalence of exact mould/manufacture remains unverified. Original pair/context folders retain arrangement scope. Source panel sizes, weights and price versions require maker review.')
        template=c.setdefault('maker_fixing_template_claim',c['fixing_available'])
        c['fixing_available']='Small: '+vv[0]['fixing_available']+' Large: '+vv[1]['fixing_available']
        c['dimensions_available']='Small: '+vv[0]['dimensions_available']+' Large: '+vv[1]['dimensions_available']
        c['missing_specification_fields']='Confirm small and large cast dimensions/depth, weight and material; reconcile size/version claims; obtain size-specific fixing/load and care/packaging records; confirm individual price and availability for each size variant.'
        for row in model['configurations']:
            if row['component_id']==cid:
                row.update(component_name=c['name'], individual_front='Identified', solo_folder_ids='\n'.join(v['primary_folder_id']for v in vv),
                           all_folder_ids=c['folder_ids'], example_file_ids=c['example_file_ids'], size_variant_ids='\n'.join(v['variant_id']for v in vv),
                           photo_scope='Individual supplied references identified separately for small and large. Original pair/context associations retained; no solo in situ provenance verified.',
                           scene_provenance='Supplied isolated reference provenance unconfirmed; client-installation provenance not certified')
        for row in model['inferences']:
            if row['component_id']==cid:
                row.update(component_name=c['name'],folder_ids=c['folder_ids'],example_file_ids=c['example_file_ids'])
                if row['field']=='Historical side depth / approximate weight':
                    original=row.setdefault('original_proposal_before_size_split',row['proposal'])
                    row['proposal']=original+' Size scope: the 6–8 kg maker standard-A template is for the small version. Large maker Size B gives 20–22 kg each, versus 20 kg in trade/retail drafts. These are source estimates; no current cast was weighed.'
        for row in model['bom']:
            if row['component_id']==cid:row['component_name']=c['name']
    # Append new claims while preserving every original claim and its source wording.
    prefix='AMREFRESH-'
    model['claims']=[r for r in model['claims']if not r['claim_id'].startswith(prefix)]
    for number, record in enumerate(price_candidates,1):
        if not set(record['component_ids']) & {'BC-AM-1','BC-AM-2'}:continue
        scope=f'{record["variant"]}; white-standard draft; current cast not measured. Price is for the whole pair.'
        fields=[('Component face dimensions',record['component_face_dimensions_cm'],'cm'),
                ('Estimated weight of each component',record['estimated_weight_each_kg'],'kg'),
                ('Draft price of whole arrangement',record['gbp'],'GBP per pair')]
        for cid in record['component_ids']:
            for field,value,unit in fields:
                model['claims'].append(dict(claim_id=f'{prefix}{number:02}-{cid}-{field.split()[0]}',component_id=cid,
                                             field=field,value=str(value),unit=unit,scope=scope,status='DATED DRAFT SOURCE; NOT PHYSICAL VERIFICATION OR CURRENT PRICE',
                                             source_ref=f'{record["source_id"]}:page {record["page"]}; price-source-review-2026-10-17/component_source_candidates.json'))
    # Preserve the complete Size B construction and numbered mould description.
    model['claims'] = [r for r in model['claims'] if not r['claim_id'].startswith('AMPANEL-')]
    for cid in ['BC-AM-1', 'BC-AM-2']:
        for field, nativefield, suffix in [
            ('Large-size manufacturing description', 'Description of whole piece in Standard Size B ', 'DESCRIPTION'),
            ('Large-size mould numbering', 'SIZE B                        \nMould Description larger size', 'MOULDS'),
        ]:
            model['claims'].append(dict(claim_id=f'AMPANEL-{cid}-{suffix}', component_id=cid, field=field,
                                       value=maker[nativefield].strip(), unit='As stated',
                                       scope='Historical Size B 120 × 60 cm option; each-panel construction/fixings, not physical verification of a current cast',
                                       status='MAKER SOURCE; CURRENT CAST APPLICABILITY UNVERIFIED',
                                       source_ref=f'manufacture-stevensons:Sheet1!row93/{nativefield}'))
    new_classifications=[dict(file_id=fid,folder_id=gid,component_ids=[f'BC-AM-{member}'],variant_id=f'AM-{size[0]}{member}',
                              visible_design_positions=1,scope=f'{size} panel {member} supplied individual design reference; exact manufacture/specifications unconfirmed',observed_utc=listing['observed_utc'])
                         for size,member,gid,fid,pair,context in definitions]
    model['file_classifications']=[r for r in model.get('file_classifications',[])if r['file_id']not in {r['file_id']for r in new_classifications}]+new_classifications
    model['counts'].update(groups=len(model['groups']),files=len(model['assets']),specification_claims=len(model['claims']),
                           explicit_size_variant_records=len(model['size_variants']))
    model['updated_utc']=listing['observed_utc']
    model['refresh_slug']='ammonite-panel-specifications-2026-10-17'
    model['refresh_scope']='Baseline inventory/platform evidence: 16 October 2026. Bone Spiral and Ammonite folder/component mappings refreshed 17 October; other families/platform pages not refreshed.'
    model['refresh_sources']=[s for s in model.get('refresh_sources',[])if s.get('id')not in ['AM-S1; AM-S2; AM-L1; AM-L2','draft-trade-2025','draft-retail-2025-named']]
    model['refresh_sources'].append(dict(label='Ammonite individual panel split, 17 October 2026',kind='Scoped live Dropbox inventory and visual review',
                                        id='AM-S1; AM-S2; AM-L1; AM-L2',path=listing['user_url'],hash=hashlib.sha256(listing_path.read_bytes()).hexdigest(),
                                        scope='Eight folders, 269 files; four new individual references viewed. Two panel design IDs with four size variants.',local=str(listing_path)))
    intake=json.loads((ev/'price-source-review-2026-10-17/price_source_intake.json').read_text())
    for source in intake['sources']:
        if source['source_id']in ['draft-trade-2025','draft-retail-2025-named']:
            model['refresh_sources'].append(dict(label=source['filename'],kind='Local draft price/specification evidence',id=source['source_id'],path=source['path'],
                                                hash=source['sha256'],scope='Ammonite size-specific each-part estimates and whole-pair prices only; draft values retained separately.',local=source['path']))
    model['limitations']=[s for s in model['limitations']if not s.startswith('Ammonite update:')]
    model['limitations'].append('Ammonite update: four supplied panel/size references mapped separately on 17 October. Draft estimates are not measurements. Four individual selling variants need standalone prices, availability and size-specific manufacturing/fixing confirmation.')
    return model
