"""Apply explicit catalogue names and separately labelled user-requested guesses."""
import hashlib
import json
from pathlib import Path


def apply_component_review_updates(model, root):
    root = Path(root)
    draft_path = root / 'reviews/acanthus-component-review-2026-10-17/one-leaf-left-specification-proposals.json'
    if not draft_path.exists():
        return model
    draft = json.loads(draft_path.read_text())
    cid = draft['component_id']
    assert cid == 'BC-AC-ONE' and len(draft['proposals']) == 7
    component = next(c for c in model['components'] if c['component_id'] == cid)
    old_name = component['name']
    name = draft['canonical_name']
    aliases = component.setdefault('prior_catalogue_names', [])
    for alias in [draft['previous_name'], old_name]:
        if alias != name and alias not in aliases:
            aliases.append(alias)
    component.update(name=name, user_name_status='USER CONFIRMED RENAME',
                     specification_draft_ref=str(draft_path),
                     draft_specification_status='Seven user-requested estimates awaiting user check; actual source fields unchanged')
    for collection in ['configurations', 'bom', 'inferences']:
        for row in model[collection]:
            if row.get('component_id') == cid:
                row['component_name'] = name
    # The clear standalone image supersedes an earlier observation from mixed samples.
    for row in model['inferences']:
        if row.get('component_id') == cid and row['field'] == 'Visible component form / proportion':
            row.setdefault('superseded_visual_proposal', row['proposal'])
            row['proposal'] = 'Square white-looking panel with one broad curved raised band; approximately 1:1 face aspect. Left is the user-selected name/orientation label.'
            row['basis'] = 'Standalone One Leaf White source image id:cnqzTNngPVsAAAAAAAt-VQ, reviewed separately from mixed workshop samples; no calibrated scale.'
            row['example_file_ids'] = draft['primary_file_id']
    ids = {r['proposal_id'] for r in draft['proposals']}
    model['inferences'] = [r for r in model['inferences'] if r.get('proposal_id') not in ids]
    for proposal in draft['proposals']:
        model['inferences'].append(dict(component_id=cid, component_name=name,
                                        proposal_id=proposal['proposal_id'], field=proposal['field'],
                                        proposal=proposal['display'], basis=proposal['basis'],
                                        confidence=proposal['confidence'], status='DRAFT ESTIMATE / AWAITING USER CHECK',
                                        needed=proposal['needed'], folder_ids=draft['primary_folder_id'],
                                        example_file_ids=draft['primary_file_id']))
    model.setdefault('review_specification_drafts', {})[cid] = draft
    model['counts']['inference_records'] = len(model['inferences'])
    model['review_updated_utc'] = draft['prepared_utc']
    model['refresh_slug'] = 'acanthus-one-leaf-left-review-2026-10-17'
    model['review_caption'] = 'Acanthus One Leaf Left: name updated and seven estimates for review, 17 October 2026. Source specifications remain separate.'
    model['refresh_sources'] = [s for s in model.get('refresh_sources', []) if s.get('id') != 'AC-ONE-LEFT-REVIEW']
    model['refresh_sources'].append(dict(label='Acanthus One Leaf Left: user-requested estimates',
                                         kind='Provisional review draft; not verified source specifications', id='AC-ONE-LEFT-REVIEW',
                                         path=str(draft_path), local=str(draft_path),
                                         hash=hashlib.sha256(draft_path.read_bytes()).hexdigest(),
                                         scope='Name explicitly supplied by user. Seven guesses awaiting user check. Native values, stock and platform IDs unchanged.'))
    return model
