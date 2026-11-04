"""Add owner-directed edition defaults and explicitly qualified year estimates.

This edits catalogue targets only. It never changes dated platform observations,
claims that a cast has been made, allocates serial numbers, or publishes listings.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'catalogue-review/scripts'))
from import_saatchi_snapshot import Xlsx, column, column_index


def prepare(out):
    source = Xlsx(out / 'previous-catalogue.xlsx')
    app = json.loads((out / 'app-after.json').read_text())
    packet = json.loads((ROOT / 'outputs/saatchi-publication-20261104/176-publication-packet.json').read_text())
    records = packet['records']
    target_ids = {r['catalogue_id'] for r in records}
    assert len(records) == len(target_ids) == 176
    products = {p['id']: p for p in app['products']}
    assert target_ids <= products.keys()
    rows = {source.value('Wall Sculptures', f'AA{r}'): r for r in range(8, 189)}
    assert set(rows) == set(products) and len(rows) == 181
    headers = {source.value('Wall Sculptures', a): re.sub(r'\d', '', a)
               for a in source.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7', a)}
    assert len(headers) in (430, 444) and len({h.casefold() for h in headers}) == len(headers)
    legacy = ['saatchi_offering_type', 'saatchi_edition_type', 'saatchi_edition_size',
             'saatchi_edition_size_basis', 'saatchi_edition_scope', 'saatchi_edition_registry_key',
             'saatchi_edition_quantity_status', 'saatchi_creation_year',
             'saatchi_creation_year_status', 'saatchi_creation_year_basis',
             'saatchi_creation_year_is_estimate', 'saatchi_creation_year_verified',
             'saatchi_edition_update_state', 'saatchi_edition_instruction_date']
    edition_columns = [h.replace('saatchi_', 'saatchi_art_', 1) for h in legacy]
    renames = []
    if set(legacy) <= headers.keys():
        assert not set(edition_columns) & headers.keys()
        for old, new in zip(legacy, edition_columns):
            renames.append(dict(before=old, value=new, column=headers[old]))
            headers[new] = headers.pop(old)
        added = []
    elif set(edition_columns) <= headers.keys():
        added = []
    else:
        assert not (set(legacy) | set(edition_columns)) & headers.keys()
        first = max(map(column_index, headers.values())) + 1
        added = edition_columns
        headers.update({h: column(first + i) for i, h in enumerate(added)})
    first = min(column_index(headers[h]) for h in edition_columns)
    patches = []
    def put(sheet, address, value, fmt=None):
        patches.append(dict(sheet=sheet, cell=address, before=source.value(sheet, address),
                            value=value, formula=None, format=fmt))
    for h in added + [r['value'] for r in renames]:
        put('Wall Sculptures', headers[h] + '7', h, 'header')
    updated = []
    for record in records:
        pid = record['catalogue_id']; r = rows[pid]
        fields = {f['key']: f['value'] for f in products[pid]['fields'] + products[pid]['listing_fields']}
        sku = fields['Seller SKU']
        assert products[pid]['listing_decision'] == 'include'
        assert source.value('Wall Sculptures', f'AQ{r}') == sku == record['sku']
        observed_year = source.value('Wall Sculptures', headers['saatchi_observed_year_produced'] + str(r))
        if observed_year is not None:
            assert isinstance(observed_year, int) and 1900 <= observed_year <= 2026
        estimated = observed_year is None
        year = 2026 if estimated else observed_year
        data = dict(
            saatchi_offering_type='Made-to-order cast',
            saatchi_edition_type='Limited Edition',
            saatchi_edition_size=50,
            saatchi_edition_size_basis='Saatchi Art planning default chosen under the owner instruction of 4 November 2026 to use Limited Edition and estimate the limit. Applies only to Saatchi Art fields, not a catalogue-wide production or stock rule.',
            saatchi_edition_scope='Saatchi Art only: default edition size 50 per component and finish (Seller SKU). Does not set an edition type, production cap or inventory limit for any other channel or the core product record.',
            saatchi_edition_registry_key=sku + '-SAATCHI-LE',
            saatchi_edition_quantity_status='Existing casts, sales, serial numbers and remaining availability are unknown. No edition number, produced quantity or available stock has been inferred.',
            saatchi_creation_year=year,
            saatchi_creation_year_status='Estimated planning year; not verified' if estimated else 'Recorded in supplied Saatchi snapshot; not independently verified',
            saatchi_creation_year_basis='2026 is the current made-to-order production planning year. Actual cast creation and original design dates are unknown. Do not present this estimate as a confirmed historical creation date.' if estimated else 'Preserved saatchi_observed_year_produced from the supplied 3 November 2026 Saatchi snapshot. This is a dated platform observation, not proof of original design date or the production date of a future cast.',
            saatchi_creation_year_is_estimate=estimated,
            saatchi_creation_year_verified=False,
            saatchi_edition_update_state='Saatchi Art catalogue target only. Existing native Saatchi listing must be updated in place; no live change or new publication is claimed. Reconcile edition facts before publishing. Other channel settings are unchanged.',
            saatchi_edition_instruction_date='2026-11-04')
        data = {h.replace('saatchi_', 'saatchi_art_', 1): v for h, v in data.items()}
        for h, v in data.items():
            put('Wall Sculptures', headers[h] + str(r), v, '0' if isinstance(v, int) and not isinstance(v, bool) else '@' if h.endswith('registry_key') else None)
        put('Wall Sculptures', headers['saatchi_unverified_information'] + str(r),
            'Edition type and size are Saatchi Art-only targets in saatchi_art_ fields. No edition or production limit is imposed on other channels or core product records. Actual creation year, prior production, edition numbering, available/sold quantities, signature, measured final packing and eligibility remain unverified. Dated observations are unchanged.')
        put('Wall Sculptures', headers['saatchi_update_state'] + str(r),
            'Prepared Saatchi catalogue targets. Edition and year settings are exclusively in saatchi_art_ fields and apply only to Saatchi Art. Update an existing native artwork in place where bound; reconcile native inventory before any creation. No live update is claimed.')
        updated.append(dict(catalogue_id=pid, sku=sku, row=r, year=year, year_is_estimate=estimated,
                            edition_size=50, existing_native_artwork_id=record.get('native_id'),
                            values=data))
    notes = [
        ['Saatchi Art edition defaults', 'Value', 'Basis and use'],
        ['Offering', 'Limited Edition made-to-order cast', 'Saatchi Art-specific target only. The owner restricted these settings to saatchi_art_ fields on 4 November 2026.'],
        ['Saatchi Art edition size', 50, 'Default of 50 per component and finish for Saatchi Art only. No edition type, production cap or inventory limit applies to other channels or core product records.'],
        ['Year estimates', 78, '2026 planning estimate for 78 products without a source year. These values are explicitly unverified; do not state them as historical fact.'],
        ['Recorded years preserved', '97 at 2026; Icarus at 2024', '98 dated Saatchi snapshot years retained. Platform observations do not independently verify the original design date or the production year of a future cast.'],
        ['Saatchi Art edition register', 'Reconcile edition facts before publishing', 'Saatchi Art-specific registry key only. No catalogue-wide or cross-channel edition counter is created. No serial numbers, manufactured quantities or available stock assigned.'],
        ['Observed One-of-a-kind', '98 observations preserved', 'The source snapshot records 98 as One-of-a-kind. Limited Edition is the new catalogue target and has not yet been applied to native Saatchi listings.'],
        ['Scope', '176 publication products', 'All 181 component rows and the other five products are retained. No excluded or deferred product is newly included. App specifications and live listings are unchanged.'],
        ['Saatchi creation-year guidance', 'Actual year of creation', 'https://support.saatchiart.com/hc/en-us/articles/48922156110363-Upload-Your-Artwork']]
    for j, row in enumerate(notes, 70):
        for c, v in zip(('J', 'K', 'L'), row):
            assert source.value('Platform Review', c + str(j)) in (None, '') or len(headers) == 444
            put('Platform Review', c + str(j), v, 'header' if j == 70 else '0' if isinstance(v, int) else None)
    counts = Counter((r['year'], r['year_is_estimate']) for r in updated)
    assert counts == {(2026, False): 97, (2024, False): 1, (2026, True): 78}
    assert len({r['existing_native_artwork_id'] for r in updated if r['existing_native_artwork_id']}) == 99
    plan = dict(scope='Restrict edition and creation-year targets to Saatchi Art-only saatchi_art_ fields for 176 products. Edition size 50 applies only to Saatchi Art. Remove the previous cross-channel scope. Preserve all dated observations, five other component records, prices, images, app data and other channel fields. No native platform changes.',
                prepared_utc=datetime.now(timezone.utc).isoformat(), target_records=176,
                edition_default=50, recorded_years=98, estimated_years=78, patches=patches,
                headers=headers, added_master_columns=added, edition_columns=edition_columns,
                header_renames=renames, first_master_column=first,
                last_master_column=len(headers), records=updated,
                notes_first_row=70, notes_last_row=78,
                row_format_updates=[dict(sheet='Platform Review', row=r, height=36 if r == 70 else 85) for r in range(70, 79)])
    (out / 'editions-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    by_id = {r['catalogue_id']: r for r in updated}
    packet['catalogue_edition_update_utc'] = plan['prepared_utc']
    packet['edition_instruction'] = 'Saatchi Art-only targets: Limited Edition, default size 50 per component and finish. No edition or production rule is imposed on other channels or core product records. Historical casts and remaining availability unverified.'
    packet['edition_scope'] = 'Saatchi Art only'
    packet['catalogue_edition_plan'] = str(out / 'editions-plan.json')
    for r in packet['records']:
        target = by_id[r['catalogue_id']]
        r.update(edition_type='Limited Edition', edition_cap=50,
                 edition_scope='Saatchi Art only',
                 edition_registry_key=target['values']['saatchi_art_edition_registry_key'],
                 creation_year=target['year'], creation_year_is_estimate=target['year_is_estimate'],
                 creation_year_basis=target['values']['saatchi_art_creation_year_basis'],
                 creation_year_verified=False, publish_ready=False)
        r['blockers'] = [b for b in r['blockers'] if b != 'Native edition format requires owner-defined original/edition facts']
        r['blockers'].append('Reconcile earlier casts and edition numbering; no available stock inferred')
    (out / 'publication-packet.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: plan[k] for k in ('target_records', 'edition_default', 'recorded_years', 'estimated_years', 'first_master_column', 'last_master_column')}))


def verify(out):
    plan = json.loads((out / 'editions-plan.json').read_text())
    before = Xlsx(out / 'previous-catalogue.xlsx'); after = Xlsx(out / 'catalogue_wall_sculptures.xlsx')
    assert before.paths == after.paths
    changed = {(p['sheet'], p['cell']): p for p in plan['patches']}
    for (s, a), p in changed.items():
        assert before.value(s, a) == p['before'] and after.value(s, a) == p['value'], (s, a)
        assert after.formula(s, a) is None
    cells = formulas = 0
    for sheet in before.paths:
        for a in set(before.cells[sheet]) | set(after.cells[sheet]):
            if (sheet, a) in changed:
                continue
            assert before.value(sheet, a) == after.value(sheet, a), (sheet, a, 'unrelated value')
            assert before.formula(sheet, a) == after.formula(sheet, a), (sheet, a, 'unrelated formula')
            cells += 1; formulas += bool(before.formula(sheet, a))
    headers = plan['headers']
    targets = {r['catalogue_id'] for r in plan['records']}
    assert len(targets) == 176
    for r in range(8, 189):
        pid = after.value('Wall Sculptures', f'AA{r}')
        if pid not in targets:
            assert all(after.value('Wall Sculptures', headers[h] + str(r)) in (None, '') for h in plan['edition_columns'])
    assert not any(after.value('Wall Sculptures', a) in [r['before'] for r in plan['header_renames']]
                   for a in after.cells['Wall Sculptures'] if re.fullmatch(r'[A-Z]+7', a))
    for r in plan['records']:
        scope = after.value('Wall Sculptures', headers['saatchi_art_edition_scope'] + str(r['row']))
        assert scope.startswith('Saatchi Art only:') and 'across all sales channels' not in scope
        assert after.value('Wall Sculptures', headers['saatchi_art_edition_size'] + str(r['row'])) == 50
        assert after.value('Wall Sculptures', headers['saatchi_art_creation_year'] + str(r['row'])) == r['year']
    table_headers = []
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    for name, body in after.parts.items():
        if name.startswith('xl/tables/') and name.endswith('.xml'):
            table = ET.fromstring(body)
            names = [c.get('name') for c in table.findall('s:tableColumns/s:tableColumn', ns)]
            if 'saatchi_art_edition_size' in names:
                table_headers.append(names)
    expected_headers = [h for h, c in sorted(headers.items(), key=lambda x: column_index(x[1]))]
    assert table_headers == [expected_headers], 'Excel table headers differ from worksheet headers'
    for sheet in after.paths:
        for a in after.cells[sheet]:
            value = after.value(sheet, a)
            if isinstance(value, str):
                assert not any(t in value for t in ['counted across all sales channels', 'shared across channels', 'shared across all channels', 'Maintain one count across channels']), (sheet, a, value)
    receipt = dict(status='PASS', target_records=176, edition_default=50, years_preserved=98,
                   years_explicitly_estimated=78, unrelated_cells_checked=cells,
                   unrelated_formulas_preserved=formulas, no_native_platform_writes=True,
                   renamed_fields=len(plan['header_renames']), edition_scope='Saatchi Art only',
                   sha256=hashlib.sha256((out / 'catalogue_wall_sculptures.xlsx').read_bytes()).hexdigest())
    (out / 'independent-verification.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('out', type=Path)
    parser.add_argument('--verify', action='store_true'); args = parser.parse_args()
    (verify if args.verify else prepare)(args.out.resolve())
