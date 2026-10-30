"""Supersede active legacy identity flags while retaining their dated history."""
import copy
import hashlib
import json
from pathlib import Path

KEYS = ['unbound_identity','readiness_note','image_role','remaining_evidence_gaps',
    'current_legacy_identity_disposition','current_photo_task_review','current_listing_reconciliation','current_listing_resolution']
def align(legacy,resolution,recorded_utc):
    history = legacy['owner_identity_resolution_history']
    history.setdefault('current_state_before_owner_identity',{key:copy.deepcopy(legacy.get(key)) for key in KEYS})
    legacy['unbound_identity'] = False
    legacy['unbound_primary_photo_reference'] = True
    legacy['readiness_note'] = 'Owner confirms the existing FFS2 relief design. Current70×15cm face retained. Separate legacy source/option record retained; exact native offer and physical cast remain unverified.'
    legacy['image_role'] = 'Shared relief-design reference; no separate legacy primary selected'
    legacy['remaining_evidence_gaps'] = 'Actual cast measurements/weight, fitted hardware and exact legacy source/platform variant remain unverified. Do not repeat the resolved FFL1/FFS2 relief question.'
    disposition = legacy['current_legacy_identity_disposition']
    disposition.setdefault('size_owner_decision_id',disposition['owner_decision_id'])
    disposition.update(owner_decision_id=resolution['decision_id'],status='OWNER_CONFIRMED_SAME_RELIEF_DESIGN',
        same_as_FFS2_not_assumed=False,same_as_FFS2_owner_confirmed=True,
        next_action='Check the exact existing source/platform offer separately before any additional variant; retain the shared design reference and all physical qualifications.')
    photo = legacy['current_photo_task_review']
    photo.setdefault('prior_source_review_recorded_utc',photo['recorded_utc'])
    photo['recorded_utc'] = recorded_utc
    photo['owner_identity_resolution'] = resolution
    photo['roles']['individual'].update(state='OWNER_DESIGN_RELATIONSHIP_RESOLVED',
        finding='Owner confirms FFL1 and FFS2 share the relief design; the existing FFS2 image is a qualified shared-design reference.',
        next_action='No repeat identity or capture request. Retain the absence of a separately selected legacy primary and the historical photograph/size limits.')
    photo['roles']['in_situ'].update(state='OWNER_CONTEXT_HOLD_RETAINED',
        finding='Current relief relationship resolved; legacy context coverage remains unverified and the existing owner context deferral remains in place.',
        next_action='Retain the existing context hold; no new photograph request.')
    for key in ['current_listing_reconciliation','current_listing_resolution']:
        legacy[key]['next_action'] = 'Owner confirms FFL1 and FFS2 share the relief. Check the exact existing native offer/configuration before any additional variant; no repeated identity question, SKU transfer or duplicate listing is inferred.'
        legacy[key]['current_owner_identity_resolution'] = resolution

if __name__ == '__main__':
    h = Path(__file__).resolve().parent
    read = lambda p: json.loads(p.read_text())
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    path = h/'canonical-master-register.json'
    before = path.read_bytes()
    g = json.loads(before)
    option = next(x for x in g['options'] if x['product_id'] == 'BSI-04D6E8690F30')
    working = copy.deepcopy(option['master_fields'])
    packet = read(Path(option['current_owner_identity_resolution']['answer_path']))
    align(option,option['current_owner_identity_resolution'],packet['recorded_utc'])
    assert option['master_fields'] == working
    prior = h/'inputs/register-before-current-state-alignment.json'
    assert not prior.exists()
    prior.write_bytes(before)
    path.write_text(json.dumps(g,ensure_ascii=False,indent=2)+'\n')
    receipt = {'status':'PASS_REGISTER_CURRENT_IDENTITY_STATE_ALIGNMENT_ONLY','before_register_sha256':sha(prior),
        'after_register_sha256':sha(path),'unchanged_workbook_sha256':sha(h/'master-workbook.pending'),
        'unchanged_all1134_current_working_field_objects':True,'old_identity_flags_preserved_as_history':True,
        'owner_identity_resolved':True,'separate_primary_photo_unbound':True}
    (h/'current-state-alignment-addendum.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))
