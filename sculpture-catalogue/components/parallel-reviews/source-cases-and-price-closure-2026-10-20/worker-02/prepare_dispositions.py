from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib
import json

W = Path(__file__).resolve().parent
C = W.parents[2]
A = json.loads((W / 'SOURCE_CASES_AT_ALLOCATION.json').read_text())
POLICIES = json.loads((W / 'OWNER_POLICIES_AT_ALLOCATION.json').read_text())
REG = json.loads((C / 'evidence/component_register.json').read_text())
ASSETS = {a['id']: a for a in REG['assets']}
NOW = datetime.now(timezone.utc).isoformat()


def write(name, value):
    (W / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def dropbox_hash(data):
    chunks = [hashlib.sha256(data[i:i + 4 * 1024 * 1024]).digest()
              for i in range(0, len(data), 4 * 1024 * 1024)]
    return hashlib.sha256(b''.join(chunks)).hexdigest()


def original_path(a):
    candidates = [a.get('full'), a.get('origin_evidence', {}).get('original_path')]
    return next(Path(p) for p in candidates if p and Path(p).is_file())


def image_record(a, role):
    p = original_path(a)
    data = p.read_bytes()
    content_hash = dropbox_hash(data)
    return {
        'file_id': a['id'], 'folder_id': a['folder_id'],
        'source_name': a['name'], 'source_group': a['group'],
        'original_path': str(p), 'bytes': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'dropbox_content_hash': content_hash,
        'cached_register_content_hash': a['content_hash'],
        'content_hash_matches_cached_source': content_hash == a['content_hash'],
        'size_matches_cached_source': len(data) == a['bytes'],
        'visual_inspection': {
            'reviewed_utc': NOW, 'role': role,
            'method': 'tools.view_image loaded the cached original; the tool may fit the rendering to the display.',
            'full_original_loaded': True, 'new_download': False,
            'generative_edit_or_external_upload': False,
        },
        'metadata_status': 'LOCAL_CACHED_SOURCE_IDENTITY_CHECK; NO_NEW_LIVE_METADATA_READ',
    }


SOURCE_IMAGES = [image_record(a, 'SOURCE_REFERENCE') for a in A['assets']]
COMPARATOR_IDS = [
    'id:cnqzTNngPVsAAAAAAAt_fw',
    'id:cnqzTNngPVsAAAAAAAufFw',
    'id:cnqzTNngPVsAAAAAAAygZw',
    'id:cnqzTNngPVsAAAAAAAygcw',
    'id:cnqzTNngPVsAAAAAAAygfg',
    'id:cnqzTNngPVsAAAAAAAylRA',
]
COMPARATORS = [image_record(ASSETS[i], 'EXISTING_OWNER_KEPT_FINISH_COMPARATOR')
               for i in COMPARATOR_IDS]
write('IMAGE_REVIEW.json', {
    'schema': 'boldstone.cached-original-source-case-review.v1',
    'prepared_utc': NOW, 'source_originals': SOURCE_IMAGES,
    'existing_finish_comparators': COMPARATORS,
    'source_original_count': len(SOURCE_IMAGES),
    'comparator_original_count': len(COMPARATORS),
    'all_cached_originals_visually_inspected': True,
    'visual_inspection_limit': 'Composition, visible relief and reference role only; chemistry, measured dimensions, same physical cast, installed hardware, stock and scene provenance are not independently certified.',
})

GPOL = 'components/reviews/specification_review_progress.json:group_photo_review_policy'
REGREF = 'components/evidence/component_register.json:'
EVIDENCE = '/Users/tprice/Library/Application Support/BoldstoneImageConsistency/product-evidence-resolution-20261016T201618Z'
GROUP_FINDINGS = {
    'G013': {
        'reference_type': 'SURFACE_DETAIL_REFERENCE',
        'display_name': 'Acanthus family — marbled green and white surface details',
        'observation': 'Both full cached source files are close surface details. Raised pale areas and green veining/marbling are visible, but neither provides the complete outer boundary or two-leaf relief geometry.',
        'reason': 'The source folder attribution is insufficient to establish a separately sellable Acanthus Two Leaves Green/White variant. The complete owner-kept Pale Blue and White reference has its own file and approval; no exact owner equivalence or source binding covers these green/white details. Retain the details without declaring either an alias or an extra product.',
        'finish_evidence': 'Green/white marbled appearance is directly visible; binder, pigment, coating and chemical finish remain unverified.',
        'comparison_file_ids': ['id:cnqzTNngPVsAAAAAAAt_fw'],
        'basis_refs': [REGREF + 'groups.G013', 'components/reviews/parallel-import-2026-10-19-batch34/identity-approval.json'],
        'decomposition_deferred': False,
    },
    'G015': {
        'reference_type': 'SURFACE_DETAIL_REFERENCE',
        'display_name': 'Acanthus family — metallic surface detail',
        'observation': 'The full source is a close view of several sweeping metallic grey and warm brown bands. It omits the complete outer panel and whole relief design.',
        'reason': 'No complete individual design or exact owner allocation binds this detail to Acanthus Two Leaves. The separately kept Acanthus One Leaf Left Pewter approval is attached to AufFw and its stated workshop target; it does not identify this different file. Appearance and lighting cannot establish an alias. Close this source configuration as a detail reference rather than create a new Two Leaves Pewter product.',
        'finish_evidence': 'Metallic grey/brown appearance only. The source Pewter label is retained as a historical label, without certifying pewter metal or equivalence to another photographed finish.',
        'comparison_file_ids': ['id:cnqzTNngPVsAAAAAAAufFw'],
        'basis_refs': [REGREF + 'groups.G015', 'components/reviews/parallel-import-2026-10-19-batch17/decisions/BC-AC-ONE/AC-ONE-LEFT-PEWTER/identity-approval.json', 'components/reviews/parallel-import-2026-10-19-batch88/AC-ONE-LEFT-PEWTER-context-evidence.json'],
        'decomposition_deferred': False,
    },
    'G137': {
        'reference_type': 'GROUP_COLLECTION_CONTEXT',
        'display_name': 'Palm Forms — Silver Pewter effect, grouped display',
        'observation': 'The full original depicts a tall curved panel and a smaller square arc panel together against timber. Both are visible as members of one grouped display.',
        'reason': 'The maker portfolio documents Palm Forms with a Silver Pewter metal effect at group level. The current owner policy retains together-pictured sculptures as context without requiring individual identification. No existing owner decision allocates these two members to current Egyptian Palm One and Deco Two Leaves product identities. Close both legacy individual finish candidates by reusing one source-group reference, without reopening decomposition.',
        'finish_evidence': 'Documented Silver Pewter effect for Palm Forms at group scope; not proof of solid pewter, substrate composition or a separate formal numbered model.',
        'comparison_file_ids': [],
        'basis_refs': [REGREF + 'groups.G137.source_decision', EVIDENCE + '/documents/interior-exterior-projects.txt:p1', EVIDENCE + '/documents/metal-effects-2025.txt:p1', GPOL],
        'decomposition_deferred': True,
    },
    'G140': {
        'reference_type': 'GROUP_SCENE_REFERENCE',
        'display_name': 'Two Palms — golden pair in styled interior references',
        'observation': 'All three full originals depict two gold-coloured curved panels together in styled room renditions; one is a closer pair view. None is an isolated individual product reference.',
        'reason': 'Retain the pair as group/scene context under the owner policy. Neither an exact member-to-current Egyptian Palm Two allocation nor an owner finish-equivalence decision is documented for these files. The sold Golden Palm single and its Gold Leaf name do not transfer to a second member in a scene. No extra individual Gold Leaf variant or authenticated client installation is inferred.',
        'finish_evidence': 'Golden appearance is visible. Source Gold Leaf wording is historical and does not certify leaf chemistry for this scene. The universal manufacture policy is preserved; scene provenance and individual finish binding remain separate.',
        'comparison_file_ids': [],
        'basis_refs': [REGREF + 'groups.G140.source_decision', 'components/reviews/parallel-import-2026-10-17-batch2/decisions/BC-EG-1/EG-1-GOLD-LEAF/identity-approval.json', GPOL],
        'decomposition_deferred': True,
    },
}

for gid in ['G205', 'G222', 'G223']:
    GROUP_FINDINGS[gid] = {
        'reference_type': 'GROUP_COLLECTION_CONTEXT',
        'display_name': 'Moon Crater Phase — rust/brown grouped references (' + gid + ')',
        'observation': ('Eight originals show the four-panel rust/brown display and a neutral-background rendition.' if gid == 'G205' else 'Five originals show a two-panel portion of the same rust/brown display, including close group views and neutral-background renditions. Other pieces may be partly visible at the frame edge.'),
        'reason': 'Together-pictured panels are retained as group context under the owner policy; the current task does not reopen individual decomposition. The existing MCP1–4 Verdigris and Rust names were kept for separate selected individual references. No exact owner finish-equivalence decision binds this rust/brown group to those references, and hue under different lighting is insufficient. Close the legacy Rust-only individual candidates as group references without creating four new products or merging their finishes.',
        'finish_evidence': 'Rust/brown appearance is visible. Actual patination recipe, metal content and binder are not established. Historical White manufacturing geometry does not certify the material or finish of these photographed panels.',
        'comparison_file_ids': ['id:cnqzTNngPVsAAAAAAAygZw', 'id:cnqzTNngPVsAAAAAAAygcw', 'id:cnqzTNngPVsAAAAAAAygfg', 'id:cnqzTNngPVsAAAAAAAylRA'],
        'basis_refs': [REGREF + 'groups.' + gid, REGREF + 'groups.G205.source_decision', 'manufacture-stevensons:rows39,41-44 GEOMETRY_SCOPE_ONLY', GPOL, 'components/reviews/moon-crater-phase-review-2026-10-19/mcp1-verdigris-rust/identity-approval.json', 'components/reviews/moon-crater-phase-review-2026-10-19/mcp2-verdigris-rust/identity-approval.json', 'components/reviews/moon-crater-phase-review-2026-10-19/mcp3-verdigris-rust/identity-approval.json', 'components/reviews/parallel-import-2026-10-19-batch45/identity-approval.json'],
        'decomposition_deferred': True,
    }

GROUPS = {g['group_ref']: g for g in A['groups']}
REFERENCES = []
for gid, finding in GROUP_FINDINGS.items():
    g = GROUPS[gid]
    REFERENCES.append({
        'reference_group_key': gid, 'source_folder_id': g['id'],
        'source_folder_path': g['path'],
        'source_file_ids': [a['id'] for a in A['assets'] if a['folder_id'] == g['id']],
        'source_file_count': sum(a['folder_id'] == g['id'] for a in A['assets']),
        'proposed_disposition': 'CONTEXT_REFERENCE_ONLY',
        'is_new_individual_product': False, **finding,
    })

CONFIG_GROUPS = {
    'CFG-F9E6B70398': ['G013'], 'CFG-615FA0A6B1': ['G015'],
    'CFG-837B6C4244': ['G137'], 'CFG-D8CA2AC5E9': ['G137'],
    'CFG-741F99704E': ['G140'], 'CFG-862A5C541F': ['G205'],
    'CFG-99FCC64095': ['G205', 'G222', 'G223'],
    'CFG-F2CBD96996': ['G205', 'G222'],
    'CFG-19FF96CC5A': ['G205', 'G223'],
}
CASES = []
for src in A['cases']:
    cfg = src['configuration_id']
    groups = CONFIG_GROUPS[cfg]
    refs = [next(r for r in REFERENCES if r['reference_group_key'] == gid) for gid in groups]
    CASES.append({
        'configuration_id': cfg, 'source_component_id': src['source_component_id'],
        'source_component_name_retained': src['source_component_name'],
        'source_appearance_label_retained': src['baseline_finish_appearance_retained'],
        'source_group_refs': groups,
        'source_folder_ids': [GROUPS[gid]['id'] for gid in groups],
        'baseline_example_file_ids': src['source_file_ids'],
        'reviewed_source_file_ids': list(dict.fromkeys(i for r in refs for i in r['source_file_ids'])),
        'proposed_disposition': 'CONTEXT_REFERENCE_ONLY',
        'proposed_review_status': 'CLOSED_AS_REFERENCE_IN_CURRENT_CATALOGUE_SCOPE',
        'reference_types': sorted({r['reference_type'] for r in refs}),
        'proposed_reference_group_keys': groups,
        'proposed_alias_target_scope': None,
        'proposed_individual_product_target_ids': [],
        'new_working_variant': False, 'new_name_or_identity_approval': False,
        'new_working_specification_acceptance': False,
        'new_product_count': 0,
        'exact_reason': refs[0]['reason'],
        'finish_evidence_scope': refs[0]['finish_evidence'],
        'source_refs': [REGREF + 'configurations.' + cfg] + list(dict.fromkeys(b for r in refs for b in r['basis_refs'])),
        'conditional_six_field_variant_draft': None,
        'draft_not_applicable_reason': 'This source case is closed as detail/group/scene context, with no newly supported individual variant scope to which six individual specifications could apply.',
        'owner_question_required': False,
        'new_source_evidence_needed_for_this_disposition': False,
        'deferred_group_decomposition_reopened': False,
        'existing_individual_approvals_and_specs_preserved': True,
        'source_offer_updates_proposed': [],
        'chemical_finish_or_same_cast_certified': False,
        'manufacture_policy_retained': 'Owner statement that all sculptures were physically made remains applicable; reference-only scope does not declare any depicted design unmanufactured.',
        'reopen_only_if_scope_changes': 'Only if a later owner instruction asks for individual allocation, or an exact standalone/source binding is supplied. This is not an active evidence request or repeated confirmation question.',
    })

write('proposed_dispositions.json', {
    'schema': 'boldstone.source-finish-reference-proposed-dispositions.v1',
    'worker_number': 2, 'prepared_utc': NOW,
    'authority': 'Prepared for the sole final writer in session 01a144ab-1a7c-7223-a403-73a4d53d70ff; no shared imports or owner events created by this worker.',
    'review_state': 'READY_FOR_FINAL_WRITER_IMPORT',
    'counts': {'source_cases': 9, 'unique_source_reference_groups': 7,
               'source_original_images_viewed': 25, 'accepted_finish_comparators_viewed': 6,
               'existing_named_finish_aliases_proposed': 0,
               'individually_supported_new_working_variants': 0,
               'context_reference_only_closures': 9,
               'new_products': 0, 'new_specification_acceptances': 0,
               'new_owner_questions': 0, 'remote_calls': 0, 'shared_writes': 0},
    'cases': CASES, 'reference_groups': REFERENCES,
    'policy_application': {
        'group_reference': {'policy_id': POLICIES['group_photo_review_policy']['decision_id'],
                            'instruction_exact': POLICIES['group_photo_review_policy']['owner_instruction_exact'],
                            'application': 'Seven source cases showing grouped works are retained as context, without a new member allocation or finish-equivalence event.'},
        'manufacture': {'policy_id': POLICIES['physical_manufacture_review_policy']['policy_id'],
                        'application': 'Preserved as owner stated; no physical-manufacture question is repeated.'},
        'working_specification': {'policy_id': POLICIES['working_specification_acceptance_policy']['policy_id'],
                                  'application': 'Standing affirmative authority remains active. No new individual six-field card is created from a reference-only case.'},
        'fixing_choice': {'policy_id': POLICIES['global_fixing_choice_policy']['policy_id'],
                         'application': 'Keyhole/French cleat choice remains on catalogue products. Reference media does not become a new sculpture by inheriting this policy.'},
        'approximate_weight': {'policy_id': POLICIES['global_approximate_weight_policy']['policy_id'],
                               'application': 'Existing applicable working weights remain preserved. No set mass is split and no new individual mass is invented for reference-only sources.'},
    },
    'raw_history_preserved': True,
    'remote_evidence_requests': [],
    'limitations': [
        'A closed source-reference question is not a certificate that every finish or potential individual product in the family has been identified.',
        'No chemical finish equivalence, exact mould/cast match, measured specification, actual stock, source-offer identity, client installation or scene authenticity is certified.',
        'All existing accepted individual records, names, specification policies and historical source assertions remain unchanged.',
    ],
})

write('conditional_variant_drafts.json', {
    'schema': 'boldstone.conditional-source-variant-drafts.v1',
    'prepared_utc': NOW, 'drafts': [], 'draft_count': 0,
    'reason': 'No additional individually supported product scope survives this review: two surface-detail cases and seven together-pictured context cases are closed as references. Six-field product proposals would assign specifications to an unestablished individual scope.',
    'six_field_keys_for_any_future_supported_variant': ['dimensions', 'weight', 'material_finish', 'fixing', 'individual_price', 'availability'],
    'repeat_blanket_confirmations_required': False,
})

assert len(CASES) == 9 and len({c['configuration_id'] for c in CASES}) == 9
assert set(CONFIG_GROUPS) == {c['configuration_id'] for c in A['cases']}
assert len(SOURCE_IMAGES) == 25 and len(COMPARATORS) == 6
assert all(i['content_hash_matches_cached_source'] and i['size_matches_cached_source'] for i in SOURCE_IMAGES + COMPARATORS)
assert all(c['proposed_disposition'] == 'CONTEXT_REFERENCE_ONLY' and not c['new_working_variant'] for c in CASES)
assert all(set(c['reviewed_source_file_ids']) <= {i['file_id'] for i in SOURCE_IMAGES} for c in CASES)
assert all(set(c['baseline_example_file_ids']) <= set(c['reviewed_source_file_ids']) for c in CASES)
assert all(not c['deferred_group_decomposition_reopened'] and not c['owner_question_required'] for c in CASES)
current_progress = json.loads((C / 'reviews/specification_review_progress.json').read_text())
policy_stability = {k: v == current_progress.get(k) for k, v in POLICIES.items()}
assert all(policy_stability.values()), 'Relevant owner policy changed after allocation.'
files = ['INPUT_MANIFEST.json', 'SOURCE_CASES_AT_ALLOCATION.json',
         'OWNER_POLICIES_AT_ALLOCATION.json', 'RELEVANT_OWNER_DECISIONS.json',
         'IMAGE_REVIEW.json', 'proposed_dispositions.json', 'conditional_variant_drafts.json']
write('VALIDATION.json', {
    'schema': 'boldstone.source-case-disposition-validation.v1',
    'validated_utc': NOW, 'result': 'PASS_NINE_CASES_REFERENCE_SCOPE_AND_ORIGINAL_IDENTITY',
    'cases': 9, 'reference_groups': 7, 'source_originals': 25,
    'comparator_originals': 6, 'all31_cached_byte_size_and_content_hash_checks_pass': True,
    'source_originals_visually_inspected': 25, 'comparator_originals_visually_inspected': 6,
    'policy_stability': policy_stability,
    'checks': ['All nine assigned configuration IDs exactly once.',
               'Every baseline example is included in inspected source files.',
               'All 25 originals in seven source groups and six accepted-finish comparators viewed.',
               'All 31 original files match cached source byte size and Dropbox content hash.',
               'No source reference converted into a product or chemical-finish alias.',
               'Existing owner group/collection scope and all four global sculpture policies preserved.',
               'No new identity event, working-specification acceptance, remote call or shared write.'],
    'outputs': [{'path': str(W / f), 'sha256': hashlib.sha256((W / f).read_bytes()).hexdigest()} for f in files],
})
print(json.dumps({'cases': len(CASES), 'dispositions': dict(Counter(c['proposed_disposition'] for c in CASES)),
                  'original_hash_checks': len(SOURCE_IMAGES) + len(COMPARATORS),
                  'validation': 'PASS', 'output': str(W / 'proposed_dispositions.json')}, indent=2))
