"""Order43 existing source cases without new matching, auditing or master writes."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json

ROOT = Path('/Users/tprice/Documents/boldstone/sculpture-catalogue')
LANE = Path(__file__).resolve().parent
MASTER = ROOT / 'components/reconciliation/wave-moonshadow-mixed-scene-master-2026-10-24/canonical-master-register.json'
MASTER_SHA = '06acd3dc3abb1146d79845dc5c895ee164f0c87ab97800fbe4d0e04e5be88f96'
KEY = 'current_authenticated_squarespace_inventory_observation'
NOW = datetime.now(timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def objsha(v):
    return hashlib.sha256(json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def ref(p):
    return {'path': str(p), 'sha256': sha(p)}


def save(name, value):
    with (LANE / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


assert sha(MASTER) == MASTER_SHA
master = json.loads(MASTER.read_text())
pointer_before = ref(ROOT / 'current-master.json')
source = master[KEY]
notes = json.loads((LANE / 'comparison-notes.json').read_text())
paired = {offer for p in source['historical_shopify_comparison']['pairs'] for offer in p['documented_offer_refs']}
all_obs = {o['offer_ref']: (i, o) for i, o in enumerate(source['retained_offer_observations'])}
selected = [(i, o) for i, o in enumerate(source['retained_offer_observations']) if o['offer_ref'] not in paired]
assert len(paired) == 37 and len(selected) == 43
options = {o['product_id']: (i, o) for i, o in enumerate(master['options'])}
offers = {o['offer_ref']: (i, o) for i, o in enumerate(master['source_offer_edges'])}
edges = master['current_listing_match_evidence']['edges']
leaf_i, leaf = offers['O028']
classification_clocks = {
    'retained_source_relation_prepared_utc': master['current_listing_match_evidence']['prepared_utc'],
    'retained_resolution_prepared_utc': master['current_listing_resolution']['prepared_utc'],
    'authenticated_export_captured_utc': source['squarespace_source_clock']['captured_utc'],
    'current_master_publication': json.loads((ROOT / 'current-master.json').read_text())['recorded_utc'],
    'qualification': 'Retained20/21October relation grades and24October source observations are distinct. A later export observation does not newly certify an exact current option configuration.',
}
rows = []
for obs_i, obs in selected:
    offer_ref = obs['offer_ref']
    offer_i, edge = offers[offer_ref]
    historic = edge['source_offer']
    op_rows = []
    for oid in obs['existing_related_option_ids']:
        oi, option = options[oid]
        resolution = option.get('current_listing_resolution', {})
        relevant_edges = [(ei, e) for ei, e in enumerate(edges) if e['offer_ref'] == offer_ref and e['product_id'] == oid]
        assert relevant_edges, (offer_ref, oid)
        op_rows.append({
            'product_id': oid, 'name': option['name'], 'canonical_key': option['canonical_key'],
            'image_url': option['image_url'], 'folder_url': option['folder_url'],
            'file_id': option.get('file_id'), 'folder_id': option.get('folder_id'),
            'sale_unit': option['sale_unit'],
            'current_option_pointer': f'/options/{oi}',
            'retained_option_resolution': deepcopy(resolution),
            'retained_source_relations': [
                {'json_pointer': f'/current_listing_match_evidence/edges/{ei}',
                 **{k: deepcopy(e.get(k)) for k in ['relationship', 'dimension_grade', 'special_join_limits', 'source_match_flags_retained', 'source_cautions_retained', 'exact_current_configuration_certified']}}
                for ei, e in relevant_edges],
            'working_fields': {k: {'display': v['display'], 'state': v.get('state'),
                                  'physical_verification': v.get('physical_verification'),
                                  'source_object_sha256': objsha(v)} for k, v in option['master_fields'].items()},
            'working_fields_pointer': f'/options/{oi}/master_fields',
            'existing_technical_photo_coverage': deepcopy(option.get('photo_coverage')),
            'no_new_matching_or_physical_decision': True,
        })
    if offer_ref in notes:
        comparison = deepcopy(notes[offer_ref])
    else:
        names = '; '.join(x['name'] for x in op_rows)
        comparison = {
            'order': 100 + int(offer_ref[1:]), 'case': offer_ref + '-WORKING-CONFIGURATION',
            'route': 'Retained individual source association', 'compare_offers': [offer_ref],
            'next': f'For {names}, compare the retained source description dimensions/material with the accepted working dimensions/material shown below before selecting an exact size/finish/build variant. The existing source association remains recorded; actual dimensions and fitted hardware stay in the main session’s physical-evidence queue, without asking for them again here.',
        }
    comparators = []
    for other_ref in comparison['compare_offers']:
        ci, co = all_obs[other_ref]
        _, ce = offers[other_ref]
        raw = {f['csv_column']: f['current_csv_value_raw'] for f in co['fields']}
        comparators.append({
            'offer_ref': other_ref, 'captured_title': raw['Title'],
            'observed_native_source_tuple': deepcopy(co['observed_native_source_tuple']),
            'captured_price_raw': raw['Price'], 'captured_visibility_raw': raw['Visible'],
            'captured_stock_setting_raw': raw['Stock'],
            'source_url': co['observed_source_url'],
            'retained_source_description_dimensions_cm': ce['source_offer'].get('source_each_cm'),
            'evidence_pointer': f'/{KEY}/retained_offer_observations/{ci}',
            'source_price_is_not_current_working_price': True,
        })
    raw = {f['csv_column']: f['current_csv_value_raw'] for f in obs['fields']}
    rows.append({
        'offer_ref': offer_ref, 'captured_source_title': raw['Title'],
        'source_pair_status': 'NO_DOCUMENTED_HISTORICAL_SHOPIFY_PAIR_IN_THIS_SAVED_COMPARISON',
        'source_pair_status_does_not_establish_current_shopify_absence': True,
        'source_observation_pointer': f'/{KEY}/retained_offer_observations/{obs_i}',
        'retained_source_offer_pointer': f'/source_offer_edges/{offer_i}/source_offer',
        'source_record_locator': deepcopy(obs['source_record_locator']),
        'native_source_tuple': deepcopy(obs['observed_native_source_tuple']),
        'source_url': obs['observed_source_url'],
        'retained_source_sale_scope': historic.get('sale_unit_state'),
        'retained_native_parts_value': historic.get('native_parts'),
        'retained_proposed_bom_parts': historic.get('proposed_bom_pieces'),
        'retained_description_dimensions_cm': historic.get('source_each_cm'),
        'retained_description_overall_dimensions_cm': historic.get('source_overall_cm'),
        'member_scope_pointer': f'/source_offer_edges/{offer_i}/members',
        'member_scope_object_sha256': objsha(edge['members']),
        'related_current_options': op_rows,
        'next_comparison': comparison,
        'comparison_source_records': comparators,
        'owner_prompt_generated': False,
        'scope': 'Review ordering and existing evidence only; no new catalogue or platform classification.',
    })
rows.sort(key=lambda r: (r['next_comparison']['order'], r['offer_ref']))
case_counts = Counter(r['next_comparison']['case'] for r in rows)
for i, row in enumerate(rows, 1):
    row['review_position'] = i
    row['shared_comparison_source_count'] = case_counts[row['next_comparison']['case']]

packet = {
    'schema': 'boldstone.existing-unpaired43-source-triage.v1', 'recorded_utc': NOW,
    'status': 'READ_ONLY_ORDERED_EXISTING_SOURCE_REVIEW_NOT_IMPORTED',
    'baseline': ref(MASTER), 'pointer_at_start': pointer_before,
    'source_clocks': classification_clocks,
    'partition': {'retained_squarespace_source_records': 80, 'documented_historical_pairs': 37,
                  'unpaired_squarespace_source_records': 43, 'deferred_historical_shopify_draft': 1},
    'counts': {'source_rows': len(rows), 'distinct_comparison_groups': len(case_counts),
               'related_option_references': sum(len(x['related_current_options']) for x in rows),
               'unique_related_options': len({o['product_id'] for r in rows for o in r['related_current_options']}),
               'explicit_source_specific_notes': len(notes), 'retained_individual_source_review_rows': 43-len(notes)},
    'standing_boundaries': {
        'in_situ_holds_retained': 22, 'series_hold_retained': 'Dune Ripple2 Copper',
        'legacy_frozen_fish_identity_deferred': True, 'wall_circle_review_not_resumed': True,
        'physical_walkthrough_owner': 'Main session; current Acanthus One Leaf Left Pewter item',
        'four_listing_copy_drafts_already_complete': True,
        'leaf_O028_owner_override_pointer': f'/source_offer_edges/{leaf_i}/current_owner_depiction_correction',
        'leaf_O028_owner_override_sha256': objsha(leaf['current_owner_depiction_correction']),
        'leaf_O028_interpretation': 'One design shown twice; no confirmed two-cast quantity or per-copy source price.',
    },
    'rows': rows,
    'new_source_audits': 0, 'new_identity_matches': 0, 'new_absence_claims': 0,
    'shared_or_native_writes': 0, 'native_payloads': [], 'owner_questions': [],
}
save('ordered-source-review.json', packet)


def e(v):
    return escape(str(v if v is not None else 'Not recorded'), quote=True)


def a(url, label):
    return f'<a href="{e(url)}">{e(label)}</a>'


overview = ''.join(f'<li>{a("#"+r["offer_ref"],r["offer_ref"]+" — "+r["captured_source_title"])} <small>{e(r["next_comparison"]["route"])}</small></li>' for r in rows)
cards = []
for row in rows:
    case = row['next_comparison']
    op_html = []
    for op in row['related_current_options']:
        resolution = op['retained_option_resolution']
        qualifiers = list(dict.fromkeys(t for ed in op['retained_source_relations'] for t in (ed['special_join_limits'] or [])))
        cautions = list(dict.fromkeys(ed['source_cautions_retained'] for ed in op['retained_source_relations'] if ed['source_cautions_retained']))
        dims = op['working_fields']['Dimensions / depth']['display']
        material = op['working_fields']['Material / finish']['display']
        specs = ''.join(f'<tr><th>{e(k)}</th><td>{e(v["display"])}</td></tr>' for k,v in op['working_fields'].items())
        op_html.append(f'<section class="option"><h3>{e(op["name"])}</h3><p>{a(op["image_url"],"Image")} · {a(op["folder_url"],"Containing folder")}</p><p><strong>Working dimensions:</strong> {e(dims)}<br><strong>Working material:</strong> {e(material)}</p><p class="small">Saved option disposition: {e(resolution.get("current_source_resolution_disposition"))}. Retained qualified individual source record: {e(resolution.get("source_supported_individual_record_present"))}; this can concern another source record and does not settle this source’s exact configuration.</p><ul>{"".join("<li>"+e(q)+"</li>" for q in qualifiers+cautions)}</ul><details><summary>Six accepted working details</summary><table>{specs}</table></details></section>')
    comparison_table = ''.join(f'<tr><td>{e(c["offer_ref"])}</td><td>{a(c["source_url"],c["captured_title"])}</td><td>{e(c["retained_source_description_dimensions_cm"])}</td><td>{e(c["captured_price_raw"])}</td><td>{e(c["captured_visibility_raw"])}</td></tr>' for c in row['comparison_source_records'])
    cards.append(f'<article id="{e(row["offer_ref"])}"><h2>{row["review_position"]}. {e(row["offer_ref"])} — {e(row["captured_source_title"])}</h2><p class="badge">{e(case["route"])}</p><p><strong>Next comparison:</strong> {e(case["next"])}</p><p class="small">Comparison group {e(case["case"])}; {row["shared_comparison_source_count"]} source record(s). One shared case is not multiple owner questions.</p><p>Saved sale scope: {e(row["retained_source_sale_scope"])}. Retained native parts value: {e(row["retained_native_parts_value"])}; proposed BOM pieces: {e(row["retained_proposed_bom_parts"])}. These are recorded source fields, not physical counts or a newly verified sale unit.</p><details><summary>Source records for this comparison</summary><table><tr><th>Source</th><th>Captured listing</th><th>Retained description size, cm</th><th>Raw source price</th><th>Captured visible</th></tr>{comparison_table}</table><p class="small">Raw source price has no currency encoded in the CSV and is not adopted as a current component price. Captured visibility is not a live-shop check.</p></details>{"".join(op_html)}</article>')
page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>43 source records — configuration review</title><style>body{font:16px/1.5 system-ui;color:#21352c;max-width:1100px;margin:32px auto;padding:0 18px}a{color:#096546}article{border-top:3px solid #b8cdbf;margin:30px 0;padding-top:16px}.option{margin:16px 0;padding:14px;background:#f3f6f2;border-radius:6px}small,.small{font-size:13px;color:#526257}.badge{font-weight:650}table{border-collapse:collapse;width:100%;table-layout:fixed}th,td{text-align:left;vertical-align:top;border:1px solid #cad8cc;padding:8px;overflow-wrap:anywhere}details{margin:12px 0}summary{cursor:pointer;font-weight:600}.notice{padding:16px;background:#eaf2ed}li{margin:7px 0}</style><h1>43 source records: next configuration comparisons</h1>'
page += f'<p class="notice">Read-only preparation from the published master. These43 Squarespace sources have no documented pair in the historical Shopify comparison; that does not prove they are absent from Shopify today. They are source records, not43 new sculptures or missing catalogue products.</p><p>One next comparison is provided for each source. Shared cases are grouped. Current image/folder links come from the published catalogue; no new image, source or live-platform audit was performed. The main session owns decisions and the physical-specification walkthrough.</p><p>Source capture: {e(classification_clocks["authenticated_export_captured_utc"])}. The retained20/21October source-relation grades are kept alongside current working entries; they do not become new physical or exact-configuration evidence.</p><p>All22 context holds, the Dune Ripple2 Copper series hold, the deferred Frozen Fish question and Wall Circle deferral remain. Completed listing-copy drafts are not reopened. Leaf Form remains one design shown twice; source arrangement quantities and per-copy prices remain unconfirmed.</p><p>{a("ordered-source-review.json","Structured review and evidence pointers")}</p><details><summary>All43 source records in review order</summary><ol>{overview}</ol></details>'
page += ''.join(cards) + '</html>\n'
with (LANE / 'review.html').open('x') as f:
    f.write(page)

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag=='article': self.ids.extend(v for k,v in attrs if k=='id')
        if tag=='a': self.links.extend(v for k,v in attrs if k=='href')

parsed = Parser(); parsed.feed(page)
saved = json.loads((LANE/'ordered-source-review.json').read_text())
checks = {
    'all43_and_only43_unpaired_source_records_present': {x['offer_ref'] for x in saved['rows']} == {o['offer_ref'] for _,o in selected} and len(saved['rows'])==43,
    'one_next_comparison_per_source_and_all_comparator_refs_exist': all(x['next_comparison']['next'] and all(y in all_obs for y in x['next_comparison']['compare_offers']) for x in saved['rows']),
    'all_current_option_links_and_working_display_states_copied_exactly': all(all(op[k]==options[op['product_id']][1][k] for k in ['name','image_url','folder_url','file_id','folder_id']) and all(f['display']==options[op['product_id']][1]['master_fields'][key]['display'] and f['source_object_sha256']==objsha(options[op['product_id']][1]['master_fields'][key]) for key,f in op['working_fields'].items()) for row in saved['rows'] for op in row['related_current_options']),
    'all_saved_option_resolutions_unchanged': all(op['retained_option_resolution']==options[op['product_id']][1]['current_listing_resolution'] for row in saved['rows'] for op in row['related_current_options']),
    'no_new_prompt_match_absence_or_write_payload': saved['owner_questions']==[] and saved['native_payloads']==[] and saved['new_identity_matches']==saved['new_absence_claims']==saved['shared_or_native_writes']==0,
    'fortythree_html_cards_and_valid_local_index_anchors': len(parsed.ids)==43 and set(parsed.ids)=={x['offer_ref'] for x in rows} and all(x[1:] in parsed.ids for x in parsed.links if x.startswith('#')),
    'every_option_image_and_folder_link_is_in_review': all(op['image_url'] in parsed.links and op['folder_url'] in parsed.links for row in rows for op in row['related_current_options']),
    'source_master_bytes_and_published_pointer_unchanged': sha(MASTER)==MASTER_SHA and sha(ROOT/'current-master.json')==pointer_before['sha256'],
    'leaf_owner_override_and_existing_member_scope_references_preserved': saved['standing_boundaries']['leaf_O028_owner_override_sha256']==objsha(leaf['current_owner_depiction_correction']) and all(row['member_scope_object_sha256']==objsha(offers[row['offer_ref']][1]['members']) for row in rows),
}
validation = {'status':'PASS_SAVED_TRIAGE_READBACK' if all(checks.values()) else 'FAIL_SAVED_TRIAGE_READBACK', 'recorded_utc':NOW,'checks':checks,'passed':sum(checks.values()),'total':len(checks),'scope':'Own review serialization/reference checks only; no repeated platform/source audit, new classification or publication.'}
save('saved-readback.json',validation)
assert all(checks.values()), checks
seal={'status':'SEALED_READ_ONLY43_SOURCE_TRIAGE_NOT_IMPORTED','recorded_utc':NOW,'baseline':ref(MASTER),'counts':packet['counts'],
      'files':[ref(LANE/name) for name in ['ordered-source-review.json','review.html','comparison-notes.json','saved-readback.json','build_triage.py']],
      'scope':'Existing43 source classifications and one next comparison each, with current option links. Main alone owns decisions/master writes; no owner questions or native actions generated.','shared_or_native_writes':0}
save('sealed-handoff.json',seal)
print(json.dumps({'status':seal['status'],'counts':packet['counts'],'checks':str(validation['passed'])+'/'+str(validation['total']),'seal':ref(LANE/'sealed-handoff.json'),'review':str(LANE/'review.html')},indent=2))
