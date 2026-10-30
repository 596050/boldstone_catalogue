"""Apply preserved, scoped catalogue refreshes without changing source claims."""
import hashlib
import json
from pathlib import Path


def _apply_bone_updates(model, root):
    root = Path(root)
    ev = root / 'evidence'
    refresh = ev / 'dropbox-refresh-2026-10-17'
    listing_path = refresh / 'bone_spiral_live_listing.json'
    media_path = refresh / 'bone_spiral_new_media.json'
    if not listing_path.exists() or not media_path.exists():
        return model
    listing = json.loads(listing_path.read_text())
    media = json.loads(media_path.read_text())
    assert not listing['parent']['has_more']
    assert all(not child['has_more'] for child in listing['children'])
    folders = {child['folder']['file_id']: child for child in listing['children']}
    paired = 'id:cnqzTNngPVsAAAAAAAyh_g'
    context = 'id:cnqzTNngPVsAAAAAAAyh_A'
    solo1 = 'id:cnqzTNngPVsAAAAAAA53Cg'
    solo2 = 'id:cnqzTNngPVsAAAAAAA53Cw'
    context2 = 'id:cnqzTNngPVsAAAAAAA53DA'
    front1 = 'id:cnqzTNngPVsAAAAAAA53EA'
    front2 = 'id:cnqzTNngPVsAAAAAAA53EQ'
    new_pair = 'id:cnqzTNngPVsAAAAAAA53Eg'
    component_ids = ['BC-BONE-1', 'BC-BONE-2']
    spec = {
        paired: ('G026', component_ids, 'Arrangement image', False, True,
                 ['id:cnqzTNngPVsAAAAAAAuVrg', new_pair],
                 'Two-panel design reference. Existing images were indexed previously; the new pair reference was viewed. Not every file was reclassified.'),
        context: ('G027', component_ids, 'Context image', True, True,
                  ['id:cnqzTNngPVsAAAAAAAyjQw', 'id:cnqzTNngPVsAAAAAAAuhLQ'],
                  'All 8 remaining files viewed on a contact sheet. Seven depict the pair; the exhibition view shows the wide panel. Scene provenance is not certified.'),
        solo1: ('G351', [component_ids[0]], 'Single component image', False, False,
                [front1], 'The one supplied reference image was viewed. Narrow design, corresponding to the left panel in the standard pair. Image production provenance unconfirmed.'),
        solo2: ('G352', [component_ids[1]], 'Single component image', False, False,
                [front2], 'The one supplied reference image was viewed. Wide spiral design, corresponding to the right panel in the standard pair. Image production provenance unconfirmed.'),
        context2: ('G353', [component_ids[1]], 'Single component and context images', True, True,
                   ['id:cnqzTNngPVsAAAAAAAs34Q', 'id:cnqzTNngPVsAAAAAAA51OA'],
                   'All 67 files viewed across six contact sheets: 51 individual wide-panel front/detail/workshop photographs, four two-wide-panel views and 12 garden views of three repeated/rotated wide-panel positions. These compositions do not create additional component designs or change the standard two-piece sale BOM.'),
    }
    assert set(folders) == set(spec), 'Unexpected Bone Spiral folder structure; review new changes'
    groups = {g['id']: g for g in model['groups']}
    for folder_id, (ref, cids, role, has_context, has_arrangement, selected, basis) in spec.items():
        child = folders[folder_id]
        g = groups.get(folder_id)
        if g is None:
            g = dict(group_ref=ref, id=folder_id, family='Bone Spiral', case_number=None,
                     earlier_full_group_review=False, earlier_observations='', source_decision={})
            model['groups'].append(g)
            groups[folder_id] = g
        g.update(name=child['folder']['name'], path=child['folder']['path'],
                 files=len(child['entries']), selected=selected, finish_appearance='White',
                 role=role, component_ids=cids, has_context=has_context,
                 has_arrangement=has_arrangement,
                 assignment_status='User-organised folders; component designs visually checked 17 October 2026',
                 review_basis=basis, refreshed_utc=listing['observed_utc'])
        assert set(selected) <= {e['file_id'] for e in child['entries']}

    existing_assets = {a['id']: a for a in model['assets']}
    downloaded = {a['id']: a for a in media['files']}
    live_ids = set()
    for folder_id, child in folders.items():
        for entry in child['entries']:
            fid = entry['file_id']
            live_ids.add(fid)
            a = existing_assets.get(fid)
            if a is None:
                record = downloaded[fid]
                a = dict(id=fid, content_hash=record['content_hash'], bytes=record['size'],
                         thumb='', full=record['local_path'], origin_evidence={
                             'retrieved_utc': listing['observed_utc'],
                             'local_sha256': record['sha256'],
                             'provenance': 'New supplied reference image; camera/render origin not confirmed'})
                model['assets'].append(a)
                existing_assets[fid] = a
            assert a['bytes'] == entry['file']['size'], 'File bytes changed; retrieve before applying'
            a.update(folder_id=folder_id, name=entry['name'], path=entry['path'],
                     group=child['folder']['name'], family='Bone Spiral')
    # A removal or an unrecognised new asset requires an explicit evidence review.
    assert {a['id'] for a in model['assets'] if a['family'] == 'Bone Spiral'} == live_ids

    names = {component_ids[0]: 'Bone Spiral 1 / narrow panel (BS1)',
             component_ids[1]: 'Bone Spiral 2 / wide panel (BS2)'}
    refs = {component_ids[0]: [solo1, paired, context],
            component_ids[1]: [solo2, paired, context, context2]}
    examples = {component_ids[0]: [front1, 'id:cnqzTNngPVsAAAAAAAuVrg', 'id:cnqzTNngPVsAAAAAAAyjQw'],
                component_ids[1]: [front2, 'id:cnqzTNngPVsAAAAAAAs34Q', 'id:cnqzTNngPVsAAAAAAAuVrg', 'id:cnqzTNngPVsAAAAAAA51OA', 'id:cnqzTNngPVsAAAAAAAuhLQ']}
    for c in model['components']:
        cid = c['component_id']
        if cid not in names:
            continue
        c.update(name=names[cid], group_refs=[groups[gid]['group_ref'] for gid in refs[cid]],
                 folder_ids='\n'.join(refs[cid]), example_file_ids='\n'.join(examples[cid]))
        c['notes'] = ('Unequal source dimensions: 55×30 and 55×55 cm. Never split the overall 85 cm width equally. '
                      '17 October 2026: adopted the user-organised numbered folder names and separate reference images. '
                      'BC-BONE-1 and BC-BONE-2 retain their existing identities. New images are design references, '
                      'not physical measurements or proof of manufacture. ' +
                      ('No solo in situ view of BS1 was identified; BS1 appears with BS2 in pair context images.'
                       if cid == component_ids[0] else
                       'Individual front/detail photographs are also in the BS2 In Situ folder. Other views show the BS2 design repeated twice or three times with different orientations.'))
    for collection in ['configurations', 'bom', 'inferences']:
        for row in model[collection]:
            cid = row.get('component_id')
            if cid not in names:
                continue
            row['component_name'] = names[cid]
            row['folder_ids' if collection != 'configurations' else 'all_folder_ids'] = '\n'.join(refs[cid])
            row['example_file_ids'] = '\n'.join(examples[cid])
            if collection == 'configurations':
                row.update(individual_front='Identified',
                           solo_folder_ids=solo1 if cid == component_ids[0] else '\n'.join([solo2, context2]),
                           context_folder_ids='\n'.join([context] + ([context2] if cid == component_ids[1] else [])),
                           series_folder_ids='\n'.join([paired, context] + ([context2] if cid == component_ids[1] else [])),
                           in_situ='Context image identified', series='Arrangement image identified',
                           photo_scope=('Individual reference image and context/series designs checked 17 October 2026. ' +
                                        ('BS1 context is within the pair; no solo BS1 context image identified.' if cid == component_ids[0] else
                                         'BS2 has individual front/detail photographs, pair/exhibition context and arrangements with two or three repeated BS2 positions.')),
                           scene_provenance='New reference image production unconfirmed; client-installation provenance not certified')
    assets = {a['id']: a for a in model['assets']}
    for offer in model['platform_records']:
        if offer['offer_ref'] == 'O034':
            assert offer['sku'] == 'BS-2P-55.85' and offer['native_parts'] == 2
            offer['image_path'] = assets[offer['image_file_id']]['path']

    observations = []
    for gid in [context, context2, solo1, solo2, paired]:
        for entry in folders[gid]['entries']:
            fid = entry['file_id']
            if gid == paired and fid != new_pair:
                continue
            if gid == context2 and entry['name'].split('__')[-1].split('.')[0] in {'005','006','024','025'} and '__bone-spiral-white__' in entry['name']:
                cids, quantity, scope = [component_ids[1]], 2, 'Two repeated/rotated wide-panel design positions; not the unequal BS1 plus BS2 pair'
            elif gid == context2 and '__bone-spiral-white-in-situ__' in entry['name']:
                cids, quantity, scope = [component_ids[1]], 3, 'Garden view: three repeated wide-design positions; not distinct component models'
            elif gid == context2:
                cids, quantity, scope = [component_ids[1]], 1, 'Individual wide-panel front/detail photograph; close-ups do not establish a physical stock count'
            elif gid == context and fid == 'id:cnqzTNngPVsAAAAAAAuhLQ':
                cids, quantity, scope = [component_ids[1]], 1, 'Wide design visible in exhibition context; other works not classified'
            elif gid in [context, paired]:
                cids, quantity, scope = component_ids, 2, 'Standard unequal two-panel composition'
            else:
                cids, quantity, scope = spec[gid][1], 1, 'Supplied individual reference image; production provenance unconfirmed'
            observations.append(dict(file_id=fid, folder_id=gid, component_ids=cids,
                                     visible_design_positions=quantity, scope=scope,
                                     observed_utc=listing['observed_utc']))
    model['file_classifications'] = [r for r in model.get('file_classifications', []) if r.get('folder_id') not in spec] + observations
    model['counts'].update(groups=len(model['groups']), files=len(model['assets']),
                           component_finish_groups_without_context=sum(x['in_situ'] == 'No context image identified' for x in model['configurations'] if x['component_id'] not in ['BC-WALL-CIRCLE', 'BC-FFL-1']),
                           component_finish_groups_without_series=sum(x['series'] == 'No arrangement image identified' for x in model['configurations'] if x['component_id'] not in ['BC-WALL-CIRCLE', 'BC-FFL-1']))
    model['updated_utc'] = listing['observed_utc']
    model['refresh_scope'] = 'Baseline catalogue inventory and platform evidence from 16 October 2026; Bone Spiral folder/file mapping refreshed 17 October 2026 only.'
    model['refresh_sources'] = [dict(label='Bone Spiral folder split, 17 October 2026',
                                    kind='Scoped live Dropbox inventory and visual review',
                                    id='BC-BONE-1; BC-BONE-2', path=listing['user_url'],
                                    hash=hashlib.sha256(listing_path.read_bytes()).hexdigest(),
                                    scope=f'Five current folders, 153 files, {len(observations)} file-specific visual observations; other families and platform pages not refreshed',
                                    local=str(listing_path))]
    model['limitations'] = [s for s in model['limitations'] if not s.startswith(('All 350 groups', 'Baseline: 350 groups'))]
    model['limitations'].append('Baseline: 350 groups reviewed through representative imagery on 16 October 2026. Bone Spiral refreshed to 5 groups / 153 assets on 17 October. Other family paths and platform data have not been refreshed.')
    return model


def apply_updates(model, root):
    from apply_ammonite_update import apply_ammonite_update
    from apply_component_review_updates import apply_component_review_updates
    return apply_component_review_updates(apply_ammonite_update(_apply_bone_updates(model, root), root), root)


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    p = root / 'evidence/component_register.json'
    model = apply_updates(json.loads(p.read_text()), root)
    p.write_text(json.dumps(model, ensure_ascii=False))
    print(json.dumps({'updated': model['updated_utc'], 'groups': model['counts']['groups'], 'files': model['counts']['files']}))
