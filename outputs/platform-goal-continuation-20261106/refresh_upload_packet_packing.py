"""Give prepared uploads the verified separate packing model, preserving sources."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).parent
model = json.loads((OUT / 'packing/plan.json').read_text())
receipt = json.loads((OUT / 'packing/dropbox-receipt.json').read_text())
assert receipt['status'] == 'PASS_DROPBOX_REVISION_UPDATE_AND_BYTE_READBACK'
cases = {r['catalogue_id']: r for r in model['records']}
updates = []
for name in ['ammonite-upload-packet.json', 'moon-fish-upload-packet.json', 'lunar-phase-iv-upload-packet.json', 'context-upload-packets.json']:
    path = OUT / name
    records = json.loads(path.read_text())
    for record in records:
        case = cases[record['catalogue_id']]
        assert case['sku'] == record['sku'] and case['status'] == 'PLANNING_ESTIMATE'
        record.update(target_artwork_price_usd=case['asking_usd'], native_packaging='Crate', native_packed_weight_kg_estimate=case['packed_kg'], packed_dimensions_cm_estimate=case['packed_cm'], packing_allowance_gbp=case['packing_allowance_gbp'], packing_estimate_qualification='Editable Saatchi-only crate planning estimate. Separate material, reinforcement, liner, wrap, screws, procurement and contingency allowances. Labour is zero. Weigh, measure and photograph the actual completed crate before collection.', packing_model_source=str(OUT / 'packing/catalogue_wall_sculptures.xlsx'), packing_model_source_sha256=receipt['sha256'], packing_model_dropbox_revision=receipt['current']['rev'])
        updates.append(dict(sku=record['sku'], catalogue_id=record['catalogue_id'], asking_usd=case['asking_usd'], packing_gbp=case['packing_allowance_gbp'], packed_kg=case['packed_kg'], native_id=record.get('native_artwork_id')))
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
(OUT / 'upload-packet-packing-refresh.json').write_text(json.dumps(dict(status='PASS', records=updates, native_price_updates_implied=False), indent=2) + '\n')
print(json.dumps(dict(status='PASS_PREPARED_PACKET_PACKING_REFRESH', records=len(updates), native_updates_implied=False)))
