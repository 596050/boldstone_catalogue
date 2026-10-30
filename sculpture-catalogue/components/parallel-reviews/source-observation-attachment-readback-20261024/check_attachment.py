"""Independently compare a hash-pinned master attachment to B's sealed proposal.

Scope excludes Wave/native image QA, workbook QA and renewed platform audits.
The only outputs are new receipts in this reviewer lane.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
LANE = Path(__file__).resolve().parent
PROPOSAL_DIR = ROOT / 'components/parallel-reviews/source-observation-proposal-20261024'
SEAL = PROPOSAL_DIR / 'sealed-handoff.json'
SEAL_SHA = '67be8d665cc990f30b825b38e78bbe2007381cc09fef4680df93bd83759dd23e'
KEY = 'current_authenticated_squarespace_inventory_observation'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def object_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def resolve(value, pointer):
    for token in pointer.lstrip('/').split('/'):
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--candidate', required=True)
    p.add_argument('--candidate-sha', required=True, help='Exact candidate bytes under review')
    p.add_argument('--candidate-state', choices=['OBSERVED_SNAPSHOT', 'MAIN_FROZEN_CANDIDATE'], default='OBSERVED_SNAPSHOT')
    args = p.parse_args()
    candidate = Path(args.candidate).resolve()
    if sha(candidate) != args.candidate_sha:
        raise SystemExit('Candidate differs from specified hash; no QA receipt written.')
    if sha(SEAL) != SEAL_SHA:
        raise SystemExit('B source proposal seal changed; no QA receipt written.')
    seal = json.loads(SEAL.read_text())
    proposal_path = PROPOSAL_DIR / 'source-observation-proposal.json'
    proposal_ref = next(x for x in seal['files'] if x['path'] == str(proposal_path))
    if sha(proposal_path) != proposal_ref['sha256']:
        raise SystemExit('B proposal bytes differ from seal; no QA receipt written.')
    proposed = json.loads(proposal_path.read_text())['proposed_value']
    register = json.loads(candidate.read_text())
    attached = register[KEY]
    imported = register['latest_authenticated_source_observation_import']
    entries = attached['retained_offer_observations']
    pairs = attached['historical_shopify_comparison']['pairs']
    override = attached['owner_interpretation_precedence']
    owner = resolve(register, override['json_pointer'])
    source_ref_results = []
    for item in entries:
        source = resolve(register, item['current_base_historical_source_pointer'])
        ident = item['observed_native_source_tuple']
        source_ref_results.append(source['offer_ref'] == item['offer_ref'] and source['sq_id'] == ident['product_id'] and source['sku'] == ident['sku_raw'])
    captured = datetime.fromisoformat(attached['squarespace_source_clock']['captured_utc'])
    imported_at = datetime.fromisoformat(imported['recorded_utc'])
    checks = {
        'attached_object_exactly_equals_sealed_proposed_value': attached == proposed,
        'all80_source_reference_pointers_still_resolve_to_same_offer_product_sku': len(source_ref_results) == 80 and all(source_ref_results),
        'all80_720_37_scope_counts_match_attachment': len(entries) == imported['source_product_sku_tuples'] == 80 and sum(len(x['fields']) for x in entries) == imported['source_field_observations'] == 720 and len(pairs) == imported['historical_shopify_pairs'] == 37,
        'import_wrapper_references_correct_proposal_seal': imported['sealed_proposal'] == str(SEAL) and imported['sealed_proposal_sha256'] == SEAL_SHA,
        'source_capture_clock_remains_separate_from_later_import_clock': captured < imported_at,
        'O028_override_pointer_resolves_to_same_owner_decision_and_one_design_two_depictions': owner['decision_id'] == override['decision_id'] and owner['current_interpretation']['unique_designs_depicted'] == 1 and owner['current_interpretation']['depicted_display_occurrences'] == 2 and owner['current_interpretation']['is_two_part_complementary_sculpture'] is False and owner['native_offer_sale_quantity_verified'] is False,
        'attachment_and_wrapper_do_not_upgrade_current_shopify_or_exact_configuration_or_physical_evidence': imported['current_shopify_inventory_verified'] is False and imported['new_identity_or_physical_configuration_matches'] == 0 and imported['existing_working_values_changed'] == 0 and imported['native_or_platform_writes'] == 0 and all(not e['exact_individual_configuration_certified_by_observation'] and not e['physical_specifications_verified_by_observation'] and not e['component_sku_assignment_proposed'] for e in entries) and all(not r['current_shopify_presence_verified'] for r in pairs),
        'candidate_and_proposal_bytes_stable_through_check': sha(candidate) == args.candidate_sha and sha(proposal_path) == proposal_ref['sha256'],
    }
    receipt = {
        'schema': 'boldstone.source-observation-attachment-readback.v1',
        'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS_HASH_PINNED_SOURCE_ATTACHMENT_ONLY' if all(checks.values()) else 'FAIL_HASH_PINNED_SOURCE_ATTACHMENT_ONLY',
        'candidate': {'path': str(candidate), 'sha256': args.candidate_sha, 'state_at_check': args.candidate_state},
        'source_proposal': proposal_ref,
        'source_seal': {'path': str(SEAL), 'sha256': SEAL_SHA},
        'expected_observation_object_sha256': object_sha(proposed),
        'attached_observation_object_sha256': object_sha(attached),
        'checks': checks, 'passed': sum(checks.values()), 'total': len(checks),
        'counts': {'source_tuples': len(entries), 'source_field_objects': sum(len(x['fields']) for x in entries), 'historical_shopify_pairs': len(pairs)},
        'scope': 'Independent readback of B source attachment only. Entire attached object compared with sealed proposal, including all raw field/comparison objects, clocks, qualifications and historical pair records. Main import wrapper and80 retained source-reference locators checked. No repeated source/platform/native or physical audit.',
        'not_covered': ['Wave image/navigation data', 'Other source/BOM/working-field preservation owned by A', 'Workbook styling/render/calculation', 'Final publication pointer/control closure'],
        'shared_writes': 0, 'native_or_platform_calls': 0,
        'checker': {'path': str(Path(__file__).resolve()), 'sha256': sha(__file__)},
    }
    output = LANE / f'candidate-readback-{args.candidate_sha[:8]}.json'
    with output.open('x') as f:
        json.dump(receipt, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({'status': receipt['status'], 'passed': receipt['passed'], 'total': receipt['total'], 'receipt': str(output), 'sha256': sha(output)}, indent=2))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
