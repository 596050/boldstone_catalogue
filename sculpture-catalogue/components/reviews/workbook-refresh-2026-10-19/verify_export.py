"""Independently inspect the saved XLSX and preserve source cells and native tables."""
import hashlib
import json
import posixpath
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
DOCREL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def decode(value):
    return re.sub(r'_x([0-9A-Fa-f]{4})_', lambda m: chr(int(m.group(1), 16)), value or '').replace('\r\n', '\n').replace('\r', '\n')


def load(path):
    with zipfile.ZipFile(path) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [decode(''.join(x.itertext())) for x in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        rels = {x.attrib['Id']: x.attrib['Target'] for x in ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))}
        sheets = {}
        for entry in workbook.find(MAIN + 'sheets'):
            target = rels[entry.attrib[DOCREL + 'id']]
            target = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            document = ET.fromstring(archive.read(target))
            cells = {}
            for cell in document.iter(MAIN + 'c'):
                formula = cell.find(MAIN + 'f')
                value = cell.find(MAIN + 'v')
                raw = value.text if value is not None else None
                kind = cell.attrib.get('t')
                if kind == 's': raw = shared[int(raw)] if raw else ''
                elif kind == 'inlineStr': raw = decode(''.join(cell.find(MAIN + 'is').itertext()))
                elif kind == 'b': raw = raw == '1'
                elif raw is not None and kind not in ['str', 'e']:
                    try: raw = float(raw)
                    except ValueError: raw = decode(raw)
                else: raw = decode(raw) if raw is not None else ''
                if formula is not None: cells[cell.attrib['r']] = ('formula', formula.text or '', raw)
                elif raw != '': cells[cell.attrib['r']] = ('value', raw)
            pane = document.find('.//' + MAIN + 'pane')
            link_container = document.find(MAIN + 'hyperlinks')
            link_relationship_path = posixpath.join(posixpath.dirname(target), '_rels', posixpath.basename(target) + '.rels')
            link_relationships = {}
            if link_relationship_path in archive.namelist():
                link_relationships = {x.attrib['Id']: x.attrib for x in ET.fromstring(archive.read(link_relationship_path))}
            hyperlinks = {}
            if link_container is not None:
                for link in link_container:
                    ref = link.attrib['ref']
                    assert ref not in hyperlinks
                    location = link.attrib.get('location')
                    if location:
                        hyperlinks[ref] = '#' + location
                    else:
                        relationship = link_relationships[link.attrib[DOCREL + 'id']]
                        assert relationship['Type'].endswith('/hyperlink') and relationship['TargetMode'] == 'External'
                        hyperlinks[ref] = relationship['Target']
            sheets[entry.attrib['name']] = {'cells': cells, 'pane': None if pane is None else pane.attrib,
                                            'document': document, 'xml_path': target, 'hyperlinks': hyperlinks}
        tables = {}
        for name in archive.namelist():
            if re.fullmatch(r'xl/tables/table\d+\.xml', name):
                table = ET.fromstring(archive.read(name))
                style = table.find(MAIN + 'tableStyleInfo')
                tables[table.attrib['name']] = {'range': table.attrib['ref'],
                    'headers': [x.attrib['name'] for x in table.find(MAIN + 'tableColumns')],
                    'style': None if style is None else style.attrib,
                    'filter': table.find(MAIN + 'autoFilter') is not None}
        return {'sheets': sheets, 'tables': tables}


def main():
    receipt = read(HERE / 'export-receipt.json')
    data = read(HERE / 'refresh-data.json')
    old, new = load(Path(receipt['previous_workbook'])), load(Path(receipt['output']))
    allowed = {(x['sheet'], x['address']) for x in receipt['allowed_existing_cell_changes']}
    failures, source_cells = [], 0
    for name, sheet in old['sheets'].items():
        assert name in new['sheets']
        for address, cell in sheet['cells'].items():
            source_cells += 1
            actual = new['sheets'][name]['cells'].get(address, ('value', ''))
            if (name, address) in allowed: continue
            same = cell[:2] == actual[:2]
            if not same: failures.append({'sheet': name, 'cell': address, 'before': str(cell)[:150], 'after': str(actual)[:150]})
    assert not failures, failures[:20]
    checks = {'original_tab_order_retained': list(new['sheets'])[:len(old['sheets'])] == list(old['sheets']),
              'all_unedited_source_cells_and_formulas_preserved': True,
              'original_freeze_panes_retained': all(new['sheets'][k]['pane'] == v['pane'] for k, v in old['sheets'].items()),
              'original_native_tables_preserved': all(k in new['tables'] and new['tables'][k]['style'] == v['style'] and new['tables'][k]['filter'] == v['filter'] for k, v in old['tables'].items()),
              'source_register_immutable': sha(Path(receipt['previous_workbook'])) == '02532ec7664b39caa7b62755c8a45748d937045e801ce7fcd985a859faf62f6f',
              'source_model_immutable': sha(ROOT / 'components/evidence/component_register.json') == 'ba65d17e6182ba6b89f30400d2f0236bc22a1478c29fb39be4d362a48d24fb61',
              'output_hash_matches_receipt': sha(Path(receipt['output'])) == receipt['output_sha256']}
    error_cells = [(name, address, cell) for name, sheet in new['sheets'].items() for address, cell in sheet['cells'].items()
                   if any(str(v) in ['#REF!', '#DIV/0!', '#VALUE!', '#NAME?', '#N/A', '#NUM!', '#NULL!', '#SPILL!', '#CALC!'] for v in cell[1:])]
    checks['no_saved_formula_errors'] = not error_cells
    checks['artifact_formula_scan_clear'] = 'matched 0 entries' in receipt['formula_error_inspection']
    checks['no_unsupported_function_diagnostics'] = all('is not implemented' not in str(part)
        for sheet in new['sheets'].values() for cell in sheet['cells'].values() for part in cell[1:])
    def value(sheet, address):
        cell = new['sheets'][sheet]['cells'][address]
        return cell[2] if cell[0] == 'formula' else cell[1]
    def column(index):
        text = ''
        while index:
            index, digit = divmod(index - 1, 26)
            text = chr(65 + digit) + text
        return text
    header_checks = []
    for name in new['sheets']:
        if name == 'Summary': continue
        table_name = ('T_' + re.sub('[^a-zA-Z]', '', name)) if name in old['sheets'] else 'Current_' + name.replace(' ', '')
        table = new['tables'][table_name]
        header_checks.append(table['headers'] == [value(name, column(i + 1) + '6') for i in range(len(table['headers']))])
    checks['all_native_table_headers_match_visible_cells'] = all(header_checks)
    link_plan = read(HERE / 'native-hyperlinks.json')
    checks['all_native_hyperlink_targets_match_plan'] = all(new['sheets'][x['sheet']]['hyperlinks'].get(x['cell']) == x['target'] for x in link_plan)
    checks['all_native_hyperlink_display_values_match'] = all(value(x['sheet'], x['cell']) == x['label'] for x in link_plan)
    checks['native_hyperlink_count_matches_receipt'] = len(link_plan) == receipt['native_hyperlinks_written'] and sum(len(s['hyperlinks']) for s in new['sheets'].values()) == sum(len(s['hyperlinks']) for s in old['sheets'].values()) + len(link_plan)
    checks['original_hyperlinks_preserved'] = all(new['sheets'][name]['hyperlinks'].get(cell) == url for name, sheet in old['sheets'].items() for cell, url in sheet['hyperlinks'].items())
    checks['review_scope_formula_recalculated'] = value('Summary', 'F6') == len(data['reviews'])
    checks['group_reference_formula_recalculated'] = value('Summary', 'F10') == len(data['groups'])
    checks['final_count_not_promoted'] = value('Summary', 'F12') == 'Unverified'
    checks['owner_global_manufacture_statement_saved_separate_from_stock_specs_and_counts'] = value('Summary', 'B31') == 'Owner states all sculptures have been made' and 'current stock, image provenance and final counts remain separate' in value('Summary', 'C31') and all('Owner states all catalogue sculptures have been made' in value(name, 'A3') for name in ['Current Reviews', 'Group References']) and data['physical_manufacture_review_policy']['evidence_level'] == 'OWNER_STATED_UNIVERSAL_MANUFACTURE'
    checks['all_81_platform_records_retained'] = len({value('Platform Mapping', 'A' + str(i)) for i in range(7, 88)}) == 81
    checks['all_6663_dropbox_file_ids_retained'] = {value('Dropbox Files', 'A' + str(i)) for i in range(7, 6670)} == {x['id'] for x in read(ROOT / 'components/evidence/component_register.json')['assets']}
    checks['all_3052_source_specification_claims_retained'] = len({value('Specification Evidence', 'A' + str(i)) for i in range(7, 3059)}) == 3052
    for name, info in receipt['new_sheets'].items():
        checks[name + '_native_table_row_count'] = any(t['range'].endswith(str(info['last'])) and t['headers'] == info['headers'] for t in new['tables'].values())
    specs = data['specifications']
    border = [x for x in specs if x[1] == 'MOONPHASE-CURRENT-1:WHITE-WITH-BORDER' and x[3] == 'Weight']
    checks['accepted_border_weight_scope_retained'] = len(border) == 1 and '4–9 kg' in border[0][4] and 'Owner accepted working proposal' in border[0][5]
    checks['border_weight_not_transferred_to_nested_two'] = all('Owner accepted working proposal' not in x[5] for x in specs if x[0] == 'MOONPHASE-CURRENT-2' and x[3] == 'Weight')
    soundwave = [x for x in specs if x[0] == 'UGR-G310' and x[3] == 'Dimensions / depth']
    checks['soundwave_owner_face_depth_separation'] = len(soundwave) == 1 and '80 × 60' in soundwave[0][4] and 'DEPTH_UNAPPROVED' in soundwave[0][5]
    checks['soundwave_name_kept'] = any(x[0] == 'UGR-G310' and x[4] == 'Owner kept this name' for x in data['reviews'])
    checks['soundwave_summary_matches_name_and_depth_state'] = value('Summary', 'G9') == 'Includes Soundwave 80 × 60 cm face. Its name is kept; depth remains an unapproved estimate.'
    checks['double_curl_name_and_manufacture_kept_estimates_unaccepted'] = any(x[0] == 'FINGERPRINT-DOUBLE-CURL-VERDIGRIS-G158013' and x[2] == 'Owner kept source name; owner says design was made' and 'estimates unaccepted' in x[5] for x in data['groups'])
    checks['all_review_rows_include_source_ID_and_context_columns'] = all(len(row) == 17 for row in data['reviews'])
    checks['context_columns_visible_for_every_scope'] = value('Current Reviews', 'N6') == 'Context images: status' and value('Current Reviews', 'O6') == 'Context images: type and limitations' and value('Current Reviews', 'P6') == 'Context example image' and value('Current Reviews', 'Q6') == 'Context containing folder' and all(value('Current Reviews', 'N' + str(i + 7)) == row[13] and value('Current Reviews', 'O' + str(i + 7)) == row[14] for i, row in enumerate(data['reviews']))
    checks['unknown_context_not_asserted_absent'] = all('does not mean they are absent' in row[14] or 'not been normalised' in row[14] for row in data['reviews'] if row[13] == 'Review pending')
    checks['Gold_context_types_and_links_saved'] = all(row[15] and row[16] and ('31 room presentations' if row[1] == 'BR-1-GOLD-LEAF' else 'G039 In Situ folder is empty') in row[14] for row in data['reviews'] if row[1] in ['BR-1-GOLD-LEAF', 'BR-2-GOLD-LEAF'])
    checks['Verdigris_and_Rust_context_links_scoped'] = all(row[15] and row[16] and 'Context file: id:' in row[14] for row in data['reviews'] if row[1] in ['MCP4-VERDIGRIS-25', 'MCP4-VERDIGRIS-RUST'])
    checks['all_current_alias_rows_have_image_and_folder_IDs'] = all(row[9] and row[10] for row in data['reviews'] if row[3] == 'Catalogue alias')
    checks['group_rule_and_source_approval_limits_visible'] = all('individual component identification deferred' in row[3] for row in data['groups'] if row[0].startswith('FINGERPRINT'))
    checks['forty_four_supplemental_photo_gap_rows_through_batch91_saved'] = receipt['added_photograph_gap_rows'] == 44 and {row['values'][0] for row in data['additional_photograph_gaps']} == {'AC-ONE-LEFT-SANDSTONE', 'AC-ONE-LEFT-PEWTER', 'SOURCE-G310003', 'BR-1-GOLD-LEAF', 'BR-2-GOLD-LEAF', 'MCP4-VERDIGRIS-RUST', 'MS1-WHITE', 'MS2-WHITE', 'MS3-WHITE', 'AC-TWO-BRONZE', 'AC-TWO-PALE-BLUE-WHITE', 'AC-TWO-WHITE-BLACK', 'FOUNTAIN-EG-WHITE', 'BC-FFL-1-SOURCE-ONLY', 'FOUNTAIN-EG-BRONZE-VERDIGRIS', 'FOUNTAIN-MED-WHITE', 'LEAF-CURVE-WHITE-GOLD', 'LEAF-GROWTH-WHITE', 'LEAF-GROWTH-WHITE-GOLD', 'LEAF-FORM-LF1-WHITE', 'LEAF-FORM-LF2-WHITE', 'LEAF-FORM-GOLD', 'MCP1-WHITE', 'MCP1-VERDIGRIS-RUST', 'MCP2-WHITE', 'MCP2-BLUE-SPLASHES', 'MCP2-VERDIGRIS-RUST', 'MCP3-WHITE', 'MCP3-VERDIGRIS-RUST', 'EMBED-SHELLS-WHITE', 'FACET-MOUND-GOLD-LEAF','PANEL-CURVES-BEIGE-PROCESS','PANEL-CURVES-MULTICOLOUR-PATINA','PLANT-WHITE','RAKED-SPIRAL1-BEIGE','RAKED-SPIRAL1-WHITE','RAKED-SPIRAL2-BEIGE','RAKED-SPIRAL2-WHITE','RAKED-SPIRAL3-BEIGE','RAKED-SPIRAL3-WHITE','CRATER-WIDE-DRIP-RUST','MFW-LEFT-WHITE','MFW-RIGHT-WHITE','MOON-RING-WHITE'}
    for n, file_id, folder_id in [(1, 'id:cnqzTNngPVsAAAAAAAyjwQ', 'id:cnqzTNngPVsAAAAAAAyjbA'), (2, 'id:cnqzTNngPVsAAAAAAAyjvw', 'id:cnqzTNngPVsAAAAAAAyjbw')]:
        vid = f'BR-{n}-GOLD-LEAF'
        entry = next((i, x) for i, x in enumerate(data['additional_photograph_gaps']) if x['values'][0] == vid)
        row = data['baseline_photo_gaps'] + 7 + entry[0]
        checks[vid + '_photo_gap_stable_IDs_saved'] = value('Photograph Gaps', 'A' + str(row)) == vid and value('Photograph Gaps', 'J' + str(row)) == folder_id and value('Photograph Gaps', 'K' + str(row)) == file_id
        checks[vid + '_rear_profile_room_gaps_saved'] = all(s in value('Photograph Gaps', 'I' + str(row)) for s in ['Rear/fixing', 'calibrated side/profile', 'full-component wide-room'])
        checks[vid + '_coverage_and_group_limits_saved'] = 'not a whole-library absence claim' in value('Photograph Gaps', 'H' + str(row)) and 'without decomposition' in value('Photograph Gaps', 'G' + str(row)) and any(x[1] == vid and 'Photo coverage:' in value('Current Reviews', 'L' + str(i + 7)) for i, x in enumerate(data['reviews']))
        checks[vid + '_individual_room_status_saved'] = ('31 room presentations' if n == 1 else 'Dedicated G039 In Situ folder is empty') in value('Photograph Gaps', 'F' + str(row))
    checks['source_platform_split_exact'] = data['platform_source_counts'] == {'Squarespace only': 43, 'Squarespace + Shopify': 37, 'Shopify only': 1}
    gold_specs = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-AC-FULL' and x[1] == 'AC-FULL-GOLD-LEAF']
    checks['Gold_finish_name_kept_under_existing_component'] = any(x[0] == 'BC-AC-FULL' and x[1] == 'AC-FULL-GOLD-LEAF' and x[2] == 'Acanthus and Moon — Gold Leaf' and x[4] == 'Owner kept this name' for x in data['reviews'])
    checks['Acanthus_Gold_six_working_groups_accepted_saved'] = len(gold_specs) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) and 'Scoped owner statement; full-group approval is separate' not in value('Reviewed Specifications', 'F' + str(i)) for i, _ in gold_specs)
    checks['Acanthus_Gold_price250_working_acceptance_resolved'] = any(x[3] == 'Individual price' and '£250 per panel — owner-accepted working price' in value('Reviewed Specifications', 'E' + str(i)) and 'unconfirmed' not in value('Reviewed Specifications', 'E' + str(i)) and 'PUBLIC_LISTING_PRICE_OWNER_ACCEPTED_AS_WORKING' in value('Reviewed Specifications', 'F' + str(i)) and 'NOT_OWNER_APPROVED' not in value('Reviewed Specifications', 'F' + str(i)) for i, x in gold_specs)
    checks['FourPanel_group_name_and_manufacture_separate_from_specs'] = any(x[0] == 'FINGERPRINT-FOUR-PANEL-VERDIGRIS-G158026' and x[1] == 'Fingerprint — Four Panel Arrangement (Verdigris)' and 'Owner kept source name' in x[2] and '80 × 80 × 4' in x[4] and 'estimates unaccepted' in x[5] for x in data['groups'])
    for variant, expected_name, price, price_status in [
        ('AC-TWO-WHITE-BLACK', 'Acanthus Two Leaves — White and Black', '£175', 'OWNER_ACCEPTED_WORKING_PRICE_PROPOSAL_NOT_OBSERVED_PLATFORM_PRICE')]:
        scoped = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-AC-TWO' and x[1] == variant]
        checks[variant + '_kept_under_existing_component'] = any(x[0] == 'BC-AC-TWO' and x[1] == variant and x[2] == expected_name and x[4] == 'Owner kept this name' for x in data['reviews'])
        checks[variant + '_six_working_groups_accepted'] = len(scoped) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in scoped)
        checks[variant + '_individual_price_scope_preserved'] = any(x[3] == 'Individual price' and price in value('Reviewed Specifications', 'E' + str(i)) and price_status in value('Reviewed Specifications', 'F' + str(i)) for i, x in scoped)
    checks['ThreePanel_name_manufacture_and_unaccepted_group_dimensions'] = any(x[0] == 'FINGERPRINT-THREE-PANEL-VERDIGRIS-G160006' and x[1] == 'Fingerprint — Three Panel Arrangement (Verdigris)' and 'Owner kept source name' in x[2] and '50 × 130 × 4' in x[4] and 'estimates unaccepted' in x[5] for x in data['groups'])
    checks['ThreePanel_exact_AI_declaration_limit_saved'] = any(x[0] == 'FINGERPRINT-THREE-PANEL-VERDIGRIS-G160006' and 'Image embeds an AI-creation declaration' in x[10] and 'unverified' in x[10] for x in data['groups'])
    checks['FourPanelRow_name_and_manufacture_kept_specs_unaccepted'] = any(x[0] == 'FINGERPRINT-FOUR-PANEL-ROW-VERDIGRIS-G160005' and 'Owner kept source name' in x[2] and 'owner says design was made' in x[2] and '50 × 180 × 4' in x[4] and '32 kg' in x[4] and '24–40' in x[4] and 'estimates unaccepted' in x[5] for x in data['groups'])
    checks['FourPanelRow_AI_declaration_does_not_authenticate_scene'] = any(x[0] == 'FINGERPRINT-FOUR-PANEL-ROW-VERDIGRIS-G160005' and 'Image embeds an AI-creation declaration' in x[10] and 'unverified' in x[10] for x in data['groups'])
    brancusi_gold = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-BR-1' and x[1] == 'BR-1-GOLD-LEAF']
    checks['Brancusi1_Gold_exact_name_and_source_ID_saved'] = any(x[0] == 'BC-BR-1' and x[1] == 'BR-1-GOLD-LEAF' and x[2] == 'Brancusi 1 — Gold Leaf' and x[4] == 'Owner kept this name' and x[9] == 'id:cnqzTNngPVsAAAAAAAyjwQ' and x[10] == 'id:cnqzTNngPVsAAAAAAAyjbA' for x in data['reviews'])
    checks['Brancusi1_Gold_six_working_specifications_accepted_estimates_retained'] = len(brancusi_gold) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in brancusi_gold) and all(any(label in value('Reviewed Specifications', 'E' + str(i)) for label in ['estimate', 'guess', 'proposal']) for i, _ in brancusi_gold) and value('Summary', 'F7') == data['specification_approval_counts']['proposal_groups']
    checks['Brancusi1_Gold_no_partial_approval_suffix_after_six_field_keep'] = all('full-group approval is separate' not in value('Reviewed Specifications', 'F' + str(i)) for i, _ in brancusi_gold)
    checks['Brancusi1_Gold_price325_is_new_proposal'] = any(x[3] == 'Individual price' and '£325' in value('Reviewed Specifications', 'E' + str(i)) and 'NOT_CURRENT_OFFER' in value('Reviewed Specifications', 'F' + str(i)) for i, x in brancusi_gold)
    checks['Brancusi1_Gold_thumbnail_and_prior_White_scope_visible'] = any(x[0] == 'BC-BR-1' and x[1] == 'BR-1-GOLD-LEAF' and 'Thumbnail-only' in x[11] for x in data['reviews']) and any(x[0] == 'BC-BR-1' and x[1] == 'BASE' and x[4] == 'Owner kept this name' for x in data['reviews'])
    checks['Brancusi1_base_specs_not_approved_or_Gold_price'] = all('Owner accepted working proposal' not in x[5] and '£325' not in x[4] for x in specs if x[0] == 'BC-BR-1' and x[1] == 'BASE')
    brancusi2_gold = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-BR-2' and x[1] == 'BR-2-GOLD-LEAF']
    checks['Brancusi2_Gold_exact_name_and_source_ID_saved'] = any(x[0] == 'BC-BR-2' and x[1] == 'BR-2-GOLD-LEAF' and x[2] == 'Brancusi 2 — Gold Leaf' and x[4] == 'Owner kept this name' and x[9] == 'id:cnqzTNngPVsAAAAAAAyjvw' and x[10] == 'id:cnqzTNngPVsAAAAAAAyjbw' for x in data['reviews'])
    checks['Brancusi2_Gold_six_working_specs_accepted_with_estimates_and_unknowns'] = len(brancusi2_gold) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) and 'full-group approval is separate' not in value('Reviewed Specifications', 'F' + str(i)) and any(label in value('Reviewed Specifications', 'E' + str(i)) for label in ['estimate', 'guess', 'proposal']) for i, _ in brancusi2_gold)
    checks['Brancusi2_Gold_price325_is_new_proposal'] = any(x[3] == 'Individual price' and '£325' in value('Reviewed Specifications', 'E' + str(i)) and 'NOT_CURRENT_OFFER' in value('Reviewed Specifications', 'F' + str(i)) for i, x in brancusi2_gold)
    checks['Brancusi2_Gold_thumbnail_and_prior_White_scope_visible'] = any(x[0] == 'BC-BR-2' and x[1] == 'BR-2-GOLD-LEAF' and 'Thumbnail-only' in x[11] for x in data['reviews']) and any(x[0] == 'BC-BR-2' and x[1] == 'BASE' and x[4] == 'Owner kept this name' for x in data['reviews'])
    checks['Brancusi2_base_specs_not_approved_or_Gold_price'] = all('Owner accepted working proposal' not in x[5] and '£325' not in x[4] for x in specs if x[0] == 'BC-BR-2' and x[1] == 'BASE')
    if data.get('canonical_consolidations', {}).get('BC-CONCAVE'):
        consolidation = data['canonical_consolidations']['BC-CONCAVE']
        review_rows = [(i + 7, x) for i, x in enumerate(data['reviews']) if x[0] == 'BC-MCP-4']
        checks['one_current_MCP4_design_no_separate_Concave'] = len([x for _, x in review_rows if x[1] == 'BASE']) == 1 and all(x[0] != 'BC-CONCAVE' for x in data['reviews'])
        former_row = next(i + 7 for i, x in enumerate(read(ROOT / 'components/evidence/component_register.json')['components']) if x['component_id'] == 'BC-CONCAVE')
        checks['historical_Concave_listing_explicitly_retired'] = value('Individual Sculptures', 'D' + str(former_row)) == 'Historical alias; use BC-MCP-4' and 'do not create a separate Concave Moon listing' in value('Individual Sculptures', 'E' + str(former_row))
        checks['three_preserved_MCP4_finishes_and_pending_Rust'] = {x[1] for _, x in review_rows if x[1] != 'BASE'} == {'MCP4-WHITE', 'MCP4-SILVER-BRONZE-25', 'MCP4-VERDIGRIS-25', 'MCP4-VERDIGRIS-RUST'}
        white = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-MCP-4' and x[1] == 'MCP4-WHITE']
        checks['White_six_prior_working_approvals_saved'] = len(white) == 6 and all('Owner accepted working proposal' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in white)
        checks['White25_face_and175_price_not50cm520'] = '25 ×25 cm' in white[0][1][4] and any('£175' in x[4] for _, x in white if x[3] == 'Individual price') and all('£520' not in value('Reviewed Specifications', 'E' + str(i)) for i, _ in white)
        checks['Silver_Bronze_and_Verdigris_estimates_remain_unapproved'] = all('Owner accepted working proposal' not in value('Reviewed Specifications', 'F' + str(i + 7)) for i, x in enumerate(specs) if x[0] == 'BC-MCP-4' and x[1] in ['MCP4-SILVER-BRONZE-25', 'MCP4-VERDIGRIS-25'])
        live = read(ROOT / 'components/reviews/concave-to-mcp4-consolidation-2026-10-19/after-live-metadata.json')
        live_files = {x['file']['id']: x['file'] for x in live['metadata'] if x.get('file')}
        model = read(ROOT / 'components/evidence/component_register.json')
        source_rows = {x['id']: i + 7 for i, x in enumerate(model['assets'])}
        checks['all47_current_Dropbox_paths_IDs_and_sizes_saved'] = all(value('Dropbox Files', 'I' + str(source_rows[fid])) == f['path_display'] and value('Dropbox Files', 'G' + str(source_rows[fid])) == f['size'] and value('Dropbox Files', 'H' + str(source_rows[fid])) == 'BC-MCP-4' for fid, f in live_files.items())
        group_rows = {x['group_ref']: i + 7 for i, x in enumerate(model['groups'])}
        checks['live_White_folder_counts8_and3_saved'] = value('Dropbox Groups', 'E' + str(group_rows['G219'])) == 8 and value('Dropbox Groups', 'E' + str(group_rows['G220'])) == 3
        checks['historical_empty_white_folder_IDs_retained'] = all(value('Dropbox Groups', 'E' + str(group_rows[g])) == 0 and 'EMPTY_HISTORICAL' in value('Dropbox Groups', 'H' + str(group_rows[g])) for g in ['G054', 'G055'])
        checks['new_alias_row_does_not_assert_mould_identity'] = any('Former catalogue name and source ID' in str(cell) and 'not a physical mould or stock merge' in str(cell) for cell in new['sheets']['Moulds and Aliases']['cells'].values())
        checks['MCP4_summary_canonical_name_and_root_folder_saved'] = value('Summary', 'B28') == 'Concave Moon is now Moon Crater Phase 4' and new['sheets']['Summary']['hyperlinks']['B29'] == consolidation['canonical_folder_url']
        if consolidation.get('Silver_vs_Silver_Bronze_finish_equivalence_confirmed'):
            silver = [(i + 7, row) for i, row in enumerate(data['reviews']) if row[0] == 'BC-MCP-4' and row[1] == 'MCP4-SILVER-BRONZE-25']
            checks['one_owner_confirmed_Silver_Bronze_finish_record'] = len(silver) == 1 and '18 file IDs' in value('Current Reviews', 'L' + str(silver[0][0])) and all(row[1] != 'MCP4-SILVER' for row in data['reviews'])
            checks['both_Silver_group_records_map_to_canonical_finish'] = all('Owner confirmed finish: Moon Crater Phase 4 — Silver and Bronze' in value('Dropbox Groups', 'H' + str(group_rows[g])) and 'MCP4-SILVER-BRONZE-25' in value('Dropbox Groups', 'H' + str(group_rows[g])) for g in ['G215', 'G051'])
            checks['both_Silver_stable_folder_IDs_retained'] = value('Dropbox Groups', 'D' + str(group_rows['G215'])) == 'id:cnqzTNngPVsAAAAAAAyirQ' and value('Dropbox Groups', 'D' + str(group_rows['G051'])) == 'id:cnqzTNngPVsAAAAAAAyglA'
            record = read(ROOT / 'components/reviews/parallel-import-2026-10-19-batch35/confirmed-finish-review.json')
            checks['all18_Silver_file_IDs_parents_and_component_saved'] = len(record['reference_files']) == 18 and all(value('Dropbox Files', 'A' + str(source_rows[x['file_id']])) == x['file_id'] and value('Dropbox Files', 'B' + str(source_rows[x['file_id']])) == x['folder_id'] and value('Dropbox Files', 'H' + str(source_rows[x['file_id']])) == 'BC-MCP-4' for x in record['reference_files'])
        if consolidation.get('native_vs_former_Concave_Verdigris_finish_equivalence_confirmed'):
            verdigris = [(i + 7, row) for i, row in enumerate(data['reviews']) if row[0] == 'BC-MCP-4' and row[1] == 'MCP4-VERDIGRIS-25']
            checks['one_owner_confirmed_Verdigris_finish_record'] = len(verdigris) == 1 and '15 file IDs and four containing folder IDs' in value('Current Reviews', 'L' + str(verdigris[0][0])) and all(row[1] != 'MCP4-VERDIGRIS' for row in data['reviews'])
            checks['all_four_Verdigris_group_records_canonical'] = all('Owner confirmed finish: Moon Crater Phase 4 — Verdigris (MCP4-VERDIGRIS-25)' in value('Dropbox Groups', 'H' + str(group_rows[g])) for g in ['G216', 'G217', 'G052', 'G053'])
            record = read(ROOT / 'components/reviews/parallel-import-2026-10-19-batch43/confirmed-finish-review.json')
            checks['all15_Verdigris_file_IDs_parents_and_component_saved'] = len(record['reference_files']) == 15 and all(value('Dropbox Files', 'A' + str(source_rows[x['file_id']])) == x['file_id'] and value('Dropbox Files', 'B' + str(source_rows[x['file_id']])) == x['folder_id'] and value('Dropbox Files', 'H' + str(source_rows[x['file_id']])) == 'BC-MCP-4' for x in record['reference_files'])
    rust = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-MCP-4' and x[1] == 'MCP4-VERDIGRIS-RUST']
    checks['Rust_name_kept_exact_example_saved'] = any(x[1] == 'MCP4-VERDIGRIS-RUST' and x[4] == 'Owner kept this name' and x[9] == 'id:cnqzTNngPVsAAAAAAAylRA' for x in data['reviews'])
    checks['all_four_MCP4_finish_names_kept'] = len([x for x in data['reviews'] if x[0] == 'BC-MCP-4' and x[1] != 'BASE' and x[4] == 'Owner kept this name']) == 4
    checks['Rust_photo_gap_name_matches_kept_name'] = all(x['values'][2] == 'Moon Crater Phase 4 — Verdigris and Rust' for x in data['additional_photograph_gaps'] if x['values'][0] == 'MCP4-VERDIGRIS-RUST')
    rust_dimensions = [(i, row) for i, row in rust if row[3] == 'Dimensions / depth']
    checks['Rust_owner_face25_and_approx_depth6_saved'] = len(rust_dimensions) == 1 and all('25 × 25 cm' in value('Reviewed Specifications', 'E' + str(i)) and 'approximately 6 cm' in value('Reviewed Specifications', 'E' + str(i)) and 'OWNER_CONFIRMED_FACE_AND_APPROXIMATE_DEPTH;NOT_INDEPENDENTLY_MEASURED' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in rust_dimensions)
    rust_weight = [(i, row) for i, row in rust if row[3] == 'Weight']
    checks['Rust_owner4kg_weight_saved_method_unknown_range_not_approved'] = len(rust_weight) == 1 and all('4 kg dry — owner-stated; weighing method unconfirmed' in value('Reviewed Specifications', 'E' + str(i)) and 'Owner: 4 kg' in value('Reviewed Specifications', 'E' + str(i)) and '3–5' not in value('Reviewed Specifications', 'E' + str(i)) and 'OWNER_STATED_DRY_WEIGHT;WEIGHING_METHOD_UNCONFIRMED;NOT_INDEPENDENTLY_WEIGHED' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in rust_weight)
    rust_material = [(i, row) for i, row in rust if row[3] == 'Material / finish']
    checks['Rust_owner_plaster_composite_and_faux_finish_saved'] = len(rust_material) == 1 and all('Plaster composite with a faux verdigris and rust finish — owner-stated' in value('Reviewed Specifications', 'E' + str(i)) and 'Sand/plaster' not in value('Reviewed Specifications', 'E' + str(i)) and 'OWNER_STATED_PLASTER_COMPOSITE_AND_FAUX_VERDIGRIS_RUST_FINISH;FORMULATION_UNCONFIRMED' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in rust_material)
    rust_fixing = [(i, row) for i, row in rust if row[3] == 'Fixing']
    checks['Rust_keyhole_type_saved_count_and_hardware_unconfirmed'] = len(rust_fixing) == 1 and all('Keyhole fixing — owner-stated; number, hardware and load capacity unconfirmed' in value('Reviewed Specifications', 'E' + str(i)) and 'OWNER_STATED_KEYHOLE_FIXING_TYPE;COUNT_HARDWARE_AND_LOAD_UNCONFIRMED' in value('Reviewed Specifications', 'F' + str(i)) and 'One concealed' not in value('Reviewed Specifications', 'E' + str(i)) for i, _ in rust_fixing)
    checks['Rust175_and_MTO_unlimited_one_week_accepted_saved'] = len(rust) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) and 'UNAPPROVED' not in value('Reviewed Specifications', 'F' + str(i)) for i, row in rust if row[3] in ['Individual price', 'Availability']) and any(row[3]=='Individual price' and '£175 per individual panel' in value('Reviewed Specifications','E'+str(i)) for i,row in rust) and any(row[3]=='Availability' and 'Made to order' in value('Reviewed Specifications','E'+str(i)) and 'stock: unlimited' in value('Reviewed Specifications','E'+str(i)) and 'lead time: 1 week' in value('Reviewed Specifications','E'+str(i)) for i,row in rust)
    checks['Rust_commercial_answer_status_and_dimension_count21_saved'] = any(x[1] == 'MCP4-VERDIGRIS-RUST' and 'Price175GBP and made-to-order policy accepted' in value('Current Reviews', 'F' + str(i + 7)) and 'unlimited stock and1week lead time owner-stated' in value('Current Reviews', 'F' + str(i + 7)) for i, x in enumerate(data['reviews'])) and value('Summary', 'F8') == 21
    moonphase_silver = [(i + 7, row) for i, row in enumerate(specs) if row[1] == 'MOONPHASE-CURRENT-4:SILVER']
    checks['Moonphase_Four_Silver_exact_name_and_source001_saved'] = any(row[1] == 'MOONPHASE-CURRENT-4:SILVER' and value('Current Reviews', 'B' + str(i + 7)) == 'Moonphase Four — Silver (MP4)' and value('Current Reviews', 'E' + str(i + 7)) == 'Owner kept this Silver finish name' and row[9] == 'id:cnqzTNngPVsAAAAAAAyfKA' and row[10] == 'id:cnqzTNngPVsAAAAAAAyfJQ' for i, row in enumerate(data['reviews']))
    checks['Moonphase_Silver_six_working_values_accepted_source_labels_retained'] = len(moonphase_silver) == 6 and all('PUBLIC_LISTING_CLAIM;OWNER_ACCEPTED_AS_WORKING;ACTUAL_SPECIMEN_APPLICABILITY_UNVERIFIED' in value('Reviewed Specifications', 'F' + str(i)) and 'Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) and 'Scoped owner statement; full-group approval is separate' not in value('Reviewed Specifications', 'F' + str(i)) for i, _ in moonphase_silver)
    silver_details = {row[3]: value('Reviewed Specifications', 'E' + str(i)) for i, row in moonphase_silver}
    checks['Moonphase_Silver_listing_values_not_other_scope_approvals'] = all(text in silver_details[field] for field, text in [('Dimensions / depth', '30 × 30 × 7 cm'), ('Weight', '8 kg'), ('Material / finish', 'Plaster'), ('Fixing', 'load rating unknown'), ('Individual price', '£87.79'), ('Availability', 'actual stock quantity and lead time unconfirmed')])
    checks['Moonphase_Silver_G243_current_four_historical_IDs_saved'] = any(row['group_ref'] == 'G243' and row['component_ids'] == ['BC-MP-1', 'BC-MP-5'] and 'Moonphase Four — Silver (MP4)' in row['assignment_status'] and 'six working specifications' in row['assignment_status'] and 'stock and scene provenance remain unverified' in row['assignment_status'] for row in data['group_updates'])
    checks['Moonphase_Silver_accepted_price_no_stale_owner_confirmation'] = 'owner-accepted working price' in silver_details['Individual price'] and 'awaiting' not in silver_details['Individual price']
    checks['Moonphase_Silver_approx_weight_and_unknowns_retained'] = 'Approximately 8 kg' in silver_details['Weight'] and 'silver-leaf content unconfirmed' in silver_details['Material / finish'] and 'hardware and load rating unknown' in silver_details['Fixing']
    checks['Acanthus_Gold_room_context_native_links_and_limits_saved'] = any(row[1] == 'AC-FULL-GOLD-LEAF' and row[13] == 'Available: on-wall and room presentation' and 'Exact physical-cast identity' in row[14] and 'id:cnqzTNngPVsAAAAAAAyh2A' in row[14] and 'id:cnqzTNngPVsAAAAAAAyh1w' in row[14] and new['sheets']['Current Reviews']['hyperlinks'].get('P' + str(i + 7)) == row[15] and new['sheets']['Current Reviews']['hyperlinks'].get('Q' + str(i + 7)) == row[16] for i, row in enumerate(data['reviews']))
    acanthus_details = {row[3]: value('Reviewed Specifications', 'E' + str(i)) for i, row in gold_specs}
    checks['Acanthus_Gold_source_values_and_unknowns_retained'] = all(text in acanthus_details[field] for field, text in [('Dimensions / depth', '50 × 30 × 6 cm'), ('Weight', 'Approximately 8 kg'), ('Material / finish', 'exact leaf composition unconfirmed'), ('Fixing', 'hardware and load rating unknown'), ('Availability', 'Made to order — proposal; listing says in stock, actual stock and lead time unconfirmed')])
    checks['Moonphase_Silver_on_wall_context_limits_and_native_links_saved'] = any(row[1] == 'MOONPHASE-CURRENT-4:SILVER' and 'on-wall' in row[14] and 'no wider-room or rear/fixing view' in row[14] and row[15] and row[16] and new['sheets']['Current Reviews']['hyperlinks'].get('P' + str(i + 7)) == row[15] and new['sheets']['Current Reviews']['hyperlinks'].get('Q' + str(i + 7)) == row[16] for i, row in enumerate(data['reviews']))
    checks['AsymmetricSpiral_name_manufacture_separate_from_estimates'] = any(x[0] == 'FINGERPRINT-ASYMMETRIC-SPIRAL-VERDIGRIS-G160003' and x[1] == 'Fingerprint — Asymmetric Spiral Panels (Verdigris)' and 'Owner kept source name' in x[2] and 'owner says design was made' in x[2] and '50 × 90 × 4' in x[4] and '16 kg' in x[4] and '12–20' in x[4] and 'estimates unaccepted' in x[5] for x in data['groups'])
    checks['AsymmetricSpiral_AI_and_group_scope_limits_saved'] = any(x[0] == 'FINGERPRINT-ASYMMETRIC-SPIRAL-VERDIGRIS-G160003' and 'Image embeds an AI-creation declaration' in x[10] and 'unverified' in x[10] and 'individual component identification deferred' in x[3] for x in data['groups'])
    checks['LoopedRidge_name_and_manufacture_kept_six_estimates_unaccepted'] = any(x[0] == 'FINGERPRINT-LOOPED-RIDGE-VERDIGRIS-G158032' and 'owner says design was made' in x[2] and 'Owner kept source name' in x[2] and '50 × 105 × 4' in x[4] and '19 kg' in x[4] and '14–24' in x[4] and 'estimates unaccepted' in x[5] for x in data['groups'])
    checks['LoopedRidge_AI_and_group_policy_limits_retained'] = any(x[0] == 'FINGERPRINT-LOOPED-RIDGE-VERDIGRIS-G158032' and 'Image embeds an AI-creation declaration' in x[10] and 'individual component identification deferred' in x[3] for x in data['groups'])
    chelsea_source = [(i + 7, x) for i, x in enumerate(specs) if x[0] == 'BC-CHELSEA' and x[1] == 'SOURCE-G233002']
    checks['MoonRipple_source_uses_existing_Chelsea_identity'] = any(x[0] == 'BC-CHELSEA' and x[1] == 'SOURCE-G233002' and x[2] == 'Chelsea Moonwave (Moon Ripple source002)' and x[4] == 'Owner confirmed same-design source alias' and x[9] == 'id:cnqzTNngPVsAAAAAAAylVg' and x[10] == 'id:cnqzTNngPVsAAAAAAAydYw' for x in data['reviews'])
    checks['MoonRipple_all_six_specs_unapproved_no250x100_inheritance'] = len(chelsea_source) == 6 and all('UNAPPROVED_SOURCE_SPECIFICATION;CHELSEA250x100_NOT_INHERITED' in value('Reviewed Specifications', 'F' + str(i)) for i, _ in chelsea_source)
    checks['MoonRipple_context_remains_candidate_with_links'] = any(x[1] == 'SOURCE-G233002' and x[13] == 'Candidate context: exact association pending' and x[15] and x[16] and 'not a new complete folder audit' in x[14] for x in data['reviews'])
    checks['MoonRipple_legacy_alias_not_new_design_saved'] = any(row[0] == 'BC-CHELSEA' and row[2] == 'Moon Ripple — White' and 'no separate Moon Ripple listing' in row[3] for row in data['catalogue_alias_rows'])
    checks['MoonRipple_source_folder_status_scoped'] = any(x['group_ref'] == 'G233' and 'source002 as Chelsea Moonwave' in x['assignment_status'] and 'Other folder members' in x['assignment_status'] for x in data['group_updates'])
    checks['MoonRipple_both_source_and_comparison_native_links_retained'] = any(x['sheet'] == 'Current Reviews' and x['label'] == 'Compare Chelsea image' and 'chelsea-moonwave-white__001.png' in x['target'] for x in link_plan) and any(x['sheet'] == 'Moulds and Aliases' and x['label'] == 'Open Chelsea reference folder' and 'Chelsea%20Moonwave%20White' in x['target'] for x in link_plan)
    checks['Fine_Ridge_kept_group_name_six_estimates_pending'] = any(row[0] == 'FINGERPRINT-FINE-RIDGE-VERDIGRIS-G158004' and row[1] == 'Fingerprint — Fine Ridge Panels (Verdigris)' and 'Owner kept source name' in row[2] and '60 × 70 × 4' in row[4] and '14 kg' in row[4] and '11–19' in row[4] and '£1,200' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhBw' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Fine_Ridge_case_level_AI_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-FINE-RIDGE-VERDIGRIS-G158004' and 'individual component identification deferred' in row[3] and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] for row in data['groups'])
    checks['Diagonal_Spiral_kept_group_name_six_estimates_pending'] = any(row[0] == 'FINGERPRINT-DIAGONAL-SPIRAL-VERDIGRIS-G158034' and row[1] == 'Fingerprint — Diagonal Spiral Panels (Verdigris)' and 'Owner kept source name' in row[2] and '60 × 105 × 4' in row[4] and '22 kg' in row[4] and '17–28' in row[4] and '£1,900' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhVA' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Diagonal_Spiral_exact_AI_declaration_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-DIAGONAL-SPIRAL-VERDIGRIS-G158034' and 'individual component identification deferred' in row[3] and 'Image embeds an AI-creation declaration' in row[10] and 'unverified' in row[10] for row in data['groups'])
    checks['Multiple_Spiral_name_kept_six_estimates_unaccepted'] = any(row[0] == 'FINGERPRINT-MULTIPLE-SPIRAL-VERDIGRIS-G158020' and row[1] == 'Fingerprint — Multiple Spiral Panels (Verdigris)' and 'Owner kept source name' in row[2] and '70 × 85 × 4' in row[4] and '21 kg' in row[4] and '16–26' in row[4] and '£1,700' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhEQ' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Multiple_Spiral_case_level_AI_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-MULTIPLE-SPIRAL-VERDIGRIS-G158020' and 'individual component identification deferred' in row[3] and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] for row in data['groups'])
    checks['Oval_Rings_name_kept_six_estimates_unaccepted'] = any(row[0] == 'FINGERPRINT-OVAL-RINGS-VERDIGRIS-G158017' and row[1] == 'Fingerprint — Oval Rings (Verdigris)' and 'Owner kept source name' in row[2] and '60 × 85 × 4' in row[4] and '18 kg' in row[4] and '13–23' in row[4] and '£1,500' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhDg' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Oval_Rings_case_level_AI_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-OVAL-RINGS-VERDIGRIS-G158017' and 'individual component identification deferred' in row[3] and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] for row in data['groups'])
    checks['Twin_Spirals_name_kept_six_estimates_unaccepted'] = any(row[0] == 'FINGERPRINT-TWIN-SPIRALS-VERDIGRIS-G158019' and row[1] == 'Fingerprint — Twin Spirals (Verdigris)' and 'Owner kept source name' in row[2] and '60 × 85 × 4' in row[4] and '18 kg' in row[4] and '13–23' in row[4] and '£1,500' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhDw' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Twin_Spirals_case_level_AI_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-TWIN-SPIRALS-VERDIGRIS-G158019' and 'individual component identification deferred' in row[3] and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] for row in data['groups'])
    checks['Oval_Rings_Curls_name_kept_six_estimates_unaccepted'] = any(row[0] == 'FINGERPRINT-OVAL-RINGS-CURLS-VERDIGRIS-G158018' and row[1] == 'Fingerprint — Oval Rings and Curls (Verdigris)' and 'Owner kept source name' in row[2] and '60 × 85 × 4' in row[4] and '18 kg' in row[4] and '13–23' in row[4] and '£1,500' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhUA' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Oval_Rings_Curls_case_level_AI_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-OVAL-RINGS-CURLS-VERDIGRIS-G158018' and 'individual component identification deferred' in row[3] and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] for row in data['groups'])
    checks['Offset_Spiral_alias_kept_six_estimates_unaccepted'] = any(row[0] == 'FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022' and row[1] == 'Fingerprint — Rough Concentric Panels (Verdigris)' and 'Historical label for this source: Fingerprint — Offset Spiral Panels (Verdigris)' in row[10] and 'Owner kept source name' in row[2] and '55 × 105 × 4' in row[4] and '20 kg' in row[4] and '15–26' in row[4] and '£1,700' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhEw' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhHw' for row in data['groups'])
    checks['Offset_Spiral_case_level_AI_and_group_limits_saved'] = any(row[0] == 'FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022' and 'individual component identification deferred' in row[3] and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] for row in data['groups'])
    checks['MS1_individual_wall_shared_room_context_and_native_links_saved'] = any(row[1] == 'MS1-WHITE' and row[13] == 'Available: on-wall and shared family room context' and 'not a complete family image audit' in row[14] and 'original bytes were not rehashed' in row[14] and 'id:cnqzTNngPVsAAAAAAAuc3w' in row[14] and 'id:cnqzTNngPVsAAAAAAAyi8w' in row[14] and new['sheets']['Current Reviews']['hyperlinks'].get('P' + str(i + 7)) == row[15] and new['sheets']['Current Reviews']['hyperlinks'].get('Q' + str(i + 7)) == row[16] for i, row in enumerate(data['reviews']))
    ms1_specs = [(i + 7, row) for i, row in enumerate(specs) if row[1] == 'MS1-WHITE']
    for variant in ['MS1-WHITE','MS2-WHITE','MS3-WHITE']:
        scoped = [(i + 7, row) for i, row in enumerate(specs) if row[1] == variant]
        checks[variant + '_six_working_values_accepted_conflicts_and_unknowns_retained'] = len(scoped) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) and 'Scoped owner statement; full-group approval is separate' not in value('Reviewed Specifications', 'F' + str(i)) for i, _ in scoped)
        details = {row[3]: value('Reviewed Specifications','E' + str(i)) for i,row in scoped}
        checks[variant + '_unresolved_weight_material_fixing_and_stock_limits_saved'] = '12–15 kg' in details['Weight'] and '20 kg' in details['Weight'] and 'actual cast material unconfirmed' in details['Material / finish'] and 'hardware type and load rating unknown' in details['Fixing'] and ('lead time unknown' in details['Availability'] or 'lead time remain unverified' in details['Availability'])
        checks[variant + '_accepted_working_price_with_archived_reference_saved'] = ('£800' if variant == 'MS2-WHITE' else '£875') in details['Individual price'] and 'owner-accepted working proposal' in details['Individual price'] and '646.71' in details['Individual price']
    checks['MS1_weight_and_price_conflicts_retained'] = any(row[3] == 'Weight' and '12–15' in value('Reviewed Specifications', 'E' + str(i)) and '20 kg' in value('Reviewed Specifications', 'E' + str(i)) for i, row in ms1_specs) and any(row[3] == 'Individual price' and '£875' in value('Reviewed Specifications', 'E' + str(i)) and '£646.71' in value('Reviewed Specifications', 'E' + str(i)) for i, row in ms1_specs)
    checks['MS1_scoped_photo_gap_row_not_false_context_absence'] = any(entry['values'][0] == 'MS1-WHITE' and 'Close individual on-wall view available' in entry['values'][5] and 'shared family context' in entry['values'][5] and 'Shared Moonspirals1-and2' in entry['values'][6] and 'Rear/fixing' in entry['values'][8] and entry['reference']['file_id'] == 'id:cnqzTNngPVsAAAAAAAt4RQ' and entry['reference']['folder_id'] == 'id:cnqzTNngPVsAAAAAAAyi7g' for entry in data['additional_photograph_gaps'])
    checks['Rough_Concentric_name_kept_six_estimates_unaccepted'] = any(row[0] == 'FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001' and row[1] == 'Fingerprint — Rough Concentric Panels (Verdigris)' and '50 × 95 × 4' in row[4] and '17 kg' in row[4] and '12–21' in row[4] and '£1,400' in row[4] and 'estimates unaccepted' in row[5] and row[8] == 'id:cnqzTNngPVsAAAAAAAyhPw' and row[9] == 'id:cnqzTNngPVsAAAAAAAyhOw' and 'original40cm measurement is not inherited' in row[10] for row in data['groups'])
    checks['Rough_Concentric_case_origin_no_exact_AI_or_model_claim_saved'] = any(row[0] == 'FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001' and 'Source-image origin' in row[10] and 'Image embeds an AI-creation declaration' not in row[10] and 'Relationship to the original Fingerprint model remains unconfirmed' in row[10] for row in data['groups'])
    checks['both_exact_duplicate_picture_canonical_name_alias_and_unaccepted_proposals_saved'] = len([row for row in data['groups'] if row[0] in ['FINGERPRINT-OFFSET-SPIRAL-VERDIGRIS-G158022','FINGERPRINT-ROUGH-CONCENTRIC-VERDIGRIS-G160001'] and row[1] == 'Fingerprint — Rough Concentric Panels (Verdigris)' and 'Same decoded picture pixels' in row[10] and 'Owner selected canonical image-reference name:' in row[10] and 'retained alias: Fingerprint — Offset Spiral Panels (Verdigris)' in row[10] and 'no separate physical sculpture inferred' in row[10] and 'differing size/weight/price proposals remain unaccepted' in row[10]]) == 2
    checks['MS2_and_MS3_context_statuses_and_native_links_saved'] = all(any(row[1] == variant and row[13] == status and file_id in row[14] and new['sheets']['Current Reviews']['hyperlinks'].get('P' + str(i + 7)) == row[15] and new['sheets']['Current Reviews']['hyperlinks'].get('Q' + str(i + 7)) == row[16] for i,row in enumerate(data['reviews'])) for variant,status,file_id in [('MS2-WHITE','Available: on-wall/outdoor and shared family room context','id:cnqzTNngPVsAAAAAAAuc3w'),('MS3-WHITE','Available: shared outdoor display context','id:cnqzTNngPVsAAAAAAA52SA')])
    checks['MS2_and_MS3_scoped_missing_photographs_saved'] = all(any(entry['values'][0] == variant and 'dedicated individual' in entry['values'][8] and 'Rear/fixing' in entry['values'][8] and entry['reference']['file_id'] == file_id for entry in data['additional_photograph_gaps']) for variant,file_id in [('MS2-WHITE','id:cnqzTNngPVsAAAAAAAsR5w'),('MS3-WHITE','id:cnqzTNngPVsAAAAAAAylJA')])
    bronze = [(i + 7, row) for i, row in enumerate(specs) if row[0] == 'BC-AC-TWO' and row[1] == 'AC-TWO-BRONZE']
    checks['Bronze_six_working_fields_saved_with_original_unknowns'] = len(bronze) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F' + str(i)) and 'Scoped owner statement; full-group approval is separate' not in value('Reviewed Specifications', 'F' + str(i)) for i, _ in bronze)
    bd = {row[3]: value('Reviewed Specifications', 'E' + str(i)) for i, row in bronze}
    checks['Bronze_weight_guess_fixing_cast_and_stock_limits_saved'] = '4–6 kg' in bd['Weight'] and 'guess' in bd['Weight'] and 'same cast as001 and load rating unconfirmed' in bd['Fixing'] and 'stock and lead time unknown' in bd['Availability']
    checks['Bronze_price7779_working_acceptance_saved'] = '£77.79' in bd['Individual price'] and 'owner-accepted working proposal' in bd['Individual price'] and 'owner selling price unconfirmed' not in bd['Individual price']
    checks['Bronze_context_rear_available_wider_room_and_series_unestablished'] = any(row[1] == 'AC-TWO-BRONZE' and row[13] == 'Available: close individual on-wall views and rear reference' and 'All6 direct-child' in row[14] and row[15] and row[16] and row[9] == 'id:cnqzTNngPVsAAAAAAAygFw' and row[10] == 'id:cnqzTNngPVsAAAAAAAygEg' for row in data['reviews']) and any(entry['values'][0] == 'AC-TWO-BRONZE' and 'rear reference exists' in entry['values'][8] and 'elsewhere unknown' in entry['values'][5] for entry in data['additional_photograph_gaps'])
    checks['FFL_source_only_gap_no_fabricated_image_or_IDs'] = any(entry['values'][0] == 'BC-FFL-1-SOURCE-ONLY' and 'Long100×22cm' in entry['values'][4] and 'same solo picture for Short and Long' in entry['values'][7] and 'No absence claim' in entry['values'][8] and not entry['reference']['image'] and not entry['reference']['file_id'] and not entry['reference']['folder_id'] for entry in data['additional_photograph_gaps'])
    checks['FFL_listing_action_respects_existing_manufacture_policy'] = value('Individual Sculptures', 'E64') == 'Locate a labelled/measured Long reference before completing the standalone listing; owner states all sculptures made' and 'seven groups /96asset metadata checked' in value('Individual Sculptures', 'Q64') and not new['sheets']['Individual Sculptures']['cells'].get('O64') and not new['sheets']['Individual Sculptures']['cells'].get('P64')
    checks['exact_source_canonical_alias_row_not_physical_merge_saved'] = any(row[0] == 'PIXEL-IDENTICAL-G158022-G160001' and row[1] == 'Fingerprint — Rough Concentric Panels (Verdigris)' and row[2] == 'Fingerprint — Offset Spiral Panels (Verdigris)' and 'not a physical mould or stock merge' in row[3] and 'conflicting unaccepted' in row[4] for row in data['catalogue_alias_rows'])
    for cid, variant, label in [('BC-AC-TWO', 'AC-TWO-PALE-BLUE-WHITE', 'PaleBlue'), ('BC-FOUNTAIN-EG', 'FOUNTAIN-EG-WHITE', 'FountainWhite')]:
        scoped = [(i+7, row) for i,row in enumerate(specs) if row[0] == cid and row[1] == variant]
        checks[label + '_six_working_fields_saved'] = len(scoped) == 6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications', 'F'+str(i)) and 'Scoped owner statement; full-group approval is separate' not in value('Reviewed Specifications', 'F'+str(i)) for i,_ in scoped)
        details = {row[3]: value('Reviewed Specifications', 'E'+str(i)) for i,row in scoped}
        if label == 'PaleBlue':
            checks['PaleBlue_estimated_size_weight_material_and_fixing_limits_saved'] = '30 × 30 × 6 cm — estimate' in details['Dimensions / depth'] and '4–6 kg' in details['Weight'] and 'composition unconfirmed' in details['Material / finish'] and 'rear, hardware and load rating unverified' in details['Fixing']
            checks['PaleBlue_175_accepted_working_price_and_MTO_unknowns_saved'] = '£175 per panel — owner-accepted working proposal' in details['Individual price'] and 'stock and lead time unknown' in details['Availability']
        else:
            checks['FountainWhite_owner15kg_historical16kg_AC730_and_fixing_limits_saved'] = '15 kg — owner-confirmed panel weight' in details['Weight'] and 'earlier16 kg draft estimate retained as historical' in details['Weight'] and 'Weighing method not recorded' in details['Weight'] and 'unresolved' not in details['Weight'] and 'AC730 is a working hypothesis' in details['Material / finish'] and 'type,count,attachment and rated load unknown' in details['Fixing']
            checks['FountainWhite_900_working_retail_625_dated_trade_and_MTO_limits_saved'] = '£900' in details['Individual price'] and 'owner-accepted working retail price' in details['Individual price'] and '625' in details['Individual price'] and 'dated' in details['Individual price'] and 'stock,reproduction capacity and lead time unknown' in details['Availability']
            checks['FountainWhite_active_statuses_no_stale_unapproved_labels'] = all('UNAPPROVED' not in value('Reviewed Specifications', 'F'+str(i)) for i,row in scoped if row[3] in ['Fixing','Availability'])
    checks['PaleBlue_context_and_new_scoped_photo_gaps_saved'] = any(row[1] == 'AC-TWO-PALE-BLUE-WHITE' and row[13] == 'Available: close individual on-wall image' and 'one-file folder' in row[14] and row[9] == 'id:cnqzTNngPVsAAAAAAAt_fw' and row[15] and row[16] for row in data['reviews']) and any(entry['values'][0] == 'AC-TWO-PALE-BLUE-WHITE' and 'Rear/fixing' in entry['values'][8] and 'elsewhere unknown' in entry['values'][8] for entry in data['additional_photograph_gaps'])
    checks['FountainWhite_context_dated_scope_and_new_gap_saved'] = any(row[0] == 'BC-FOUNTAIN-EG' and row[1] == 'FOUNTAIN-EG-WHITE' and row[13] == 'Available: outdoor/workshop display; prior paired context retained' and 'dated18October' in row[14] and 'id:cnqzTNngPVsAAAAAAAucqw' in row[14] and row[15] and row[16] for row in data['reviews']) and any(entry['values'][0] == 'FOUNTAIN-EG-WHITE' and 'propped on a bucket' in entry['values'][5] and 'Finished-panel rear/fixing' in entry['values'][8] for entry in data['additional_photograph_gaps'])
    checks['WhiteBlack_room_context_and_product_only_rear_profile_gaps_saved'] = any(row[1] == 'AC-TWO-WHITE-BLACK' and row[13] == 'Available: individual room presentations' and 'All3 direct-child' in row[14] and row[9] == 'id:cnqzTNngPVsAAAAAAAuRaQ' and row[10] == 'id:cnqzTNngPVsAAAAAAAyh4A' and row[15] and row[16] for row in data['reviews']) and any(entry['values'][0] == 'AC-TWO-WHITE-BLACK' and 'room presentations available' in entry['values'][5] and 'Product-only front, rear/fixing and calibrated side/profile' in entry['values'][8] and 'elsewhere unknown' in entry['values'][8] for entry in data['additional_photograph_gaps'])
    checks['standing_working_instruction_visible_separate_from_unknowns'] = value('Summary','A32')=='Working specifications' and 'under owner instruction' in value('Summary','B32') and 'No separate reply is invented' in value('Summary','C32') and data['working_specification_acceptance_policy']['policy_id'].endswith('LINE18928')
    checks['working_group_count330_and152_photo_gaps_saved'] = value('Summary','F7')==330 and data['specification_approval_counts']['proposal_groups']==330 and data['baseline_photo_gaps']+len(data['additional_photograph_gaps'])==152
    checks['WhiteBlack_price_basis_clarified_without_source_rewrite'] = any(row[1]=='AC-TWO-WHITE-BLACK' and row[3]=='Individual price' and 'Owner subsequently accepted £175' in value('Reviewed Specifications','G'+str(i+7)) and 'or owner approval' not in value('Reviewed Specifications','G'+str(i+7)) for i,row in enumerate(specs))
    newer_scopes=[('BC-FOUNTAIN-EG','FOUNTAIN-EG-BRONZE-VERDIGRIS'),('BC-FOUNTAIN-MED','FOUNTAIN-MED-WHITE'),('BC-LEAF-CURVE','LEAF-CURVE-WHITE-GOLD'),('BC-LEAF-GROWTH','LEAF-GROWTH-WHITE'),('BC-LEAF-GROWTH','LEAF-GROWTH-WHITE-GOLD'),('BC-LEAF-FORM','LEAF-FORM-LF1-WHITE'),('BC-LEAF-FORM','LEAF-FORM-LF2-WHITE'),('BC-LEAF-FORM','LEAF-FORM-GOLD')]
    new_details={}
    for cid,vid in newer_scopes:
        scoped=[(i+7,row) for i,row in enumerate(specs) if row[0]==cid and row[1]==vid];new_details[vid]={row[3]:value('Reviewed Specifications','E'+str(i)) for i,row in scoped}
        checks[vid+'_six_working_fields_and_original_unknowns_saved']=len(scoped)==6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications','F'+str(i)) and 'UNAPPROVED' not in value('Reviewed Specifications','F'+str(i)) for i,row in scoped) and any(term in new_details[vid]['Availability'] for term in ['unknown','unconfirmed']) and all(term not in new_details[vid]['Availability'] for term in ['stock: unlimited','lead time: 1 week'])
        if vid.startswith('LEAF-'):
            checks[vid+'_standing_policy_without_individual_reply_saved']=all('Accepted under standing owner instruction; no individual reply recorded' in value('Reviewed Specifications','F'+str(i)) for i,row in scoped)
        rr=[(i+7,row) for i,row in enumerate(data['reviews']) if row[0]==cid and row[1]==vid];assert len(rr)==1
        ri,row=rr[0];checks[vid+'_exact_primary_and_scoped_photograph_gap_saved']=bool(row[9] and row[10]) and any(entry['values'][0]==vid and entry['values'][9]==row[10] and entry['values'][10]==row[9] and 'elsewhere unknown' in entry['values'][8] for entry in data['additional_photograph_gaps'])
        checks[vid+'_context_native_links_or_explicit_detail_only_saved']=(not row[15] and not row[16] and 'cropped Gold details only' in row[13]) if vid=='LEAF-GROWTH-WHITE-GOLD' else bool(row[15] and row[16] and new['sheets']['Current Reviews']['hyperlinks'].get('P'+str(ri))==row[15] and new['sheets']['Current Reviews']['hyperlinks'].get('Q'+str(ri))==row[16])
    checks['FountainBronze15kg_not_ownerWhite15kg']= 'guess' in new_details['FOUNTAIN-EG-BRONZE-VERDIGRIS']['Weight'] and '£900–£1,200' in new_details['FOUNTAIN-EG-BRONZE-VERDIGRIS']['Individual price'] and 'no exact coloured offer or owner price approval' not in new_details['FOUNTAIN-EG-BRONZE-VERDIGRIS']['Individual price']
    checks['Growth18vs12_conflict_and_Gold_conditional_not_measured_range']=all(term in new_details['LEAF-GROWTH-WHITE']['Weight'] for term in ['18kg','12kg','unresolved']) and 'conditional' in new_details['LEAF-GROWTH-WHITE-GOLD']['Dimensions / depth'] and 'conditional' in new_details['LEAF-GROWTH-WHITE-GOLD']['Weight']
    checks['LeafForm_individual_prices_and_Gold_unknown_recipe_saved']=all(price in new_details[vid]['Individual price'] for vid,price in [('LEAF-FORM-LF1-WHITE','£350'),('LEAF-FORM-LF2-WHITE','£350'),('LEAF-FORM-GOLD','£400')]) and 'actual gold-leaf content and metal content unknown' in new_details['LEAF-FORM-GOLD']['Material / finish']
    checks['Leaf_photo_gap_finish_labels_readable_with_stable_scope_IDs']=all(any(entry['values'][0]==vid and value('Photograph Gaps','D'+str(data['baseline_photo_gaps']+7+i))==label for i,entry in enumerate(data['additional_photograph_gaps'])) for vid,label in [('LEAF-CURVE-WHITE-GOLD','White and Gold Leaf'),('LEAF-GROWTH-WHITE','White'),('LEAF-GROWTH-WHITE-GOLD','White and Gold Leaf'),('LEAF-FORM-LF1-WHITE','White'),('LEAF-FORM-LF2-WHITE','White'),('LEAF-FORM-GOLD','Gold')])
    next_scopes=[('BC-MCP-1','MCP1-WHITE'),('BC-MCP-1','MCP1-VERDIGRIS-RUST'),('BC-MCP-2','MCP2-WHITE'),('BC-MCP-2','MCP2-BLUE-SPLASHES'),('BC-MCP-2','MCP2-VERDIGRIS-RUST'),('BC-MCP-3','MCP3-WHITE'),('BC-MCP-3','MCP3-VERDIGRIS-RUST'),('BC-EMBED-SHELLS','EMBED-SHELLS-WHITE'),('BC-FACET-MOUND','FACET-MOUND-GOLD-LEAF')]
    next_details={}
    for cid,vid in next_scopes:
        scoped=[(i+7,row) for i,row in enumerate(specs) if row[0]==cid and row[1]==vid];details={row[3]:value('Reviewed Specifications','E'+str(i)) for i,row in scoped};next_details[vid]=details
        checks[vid+'_six_working_fields_no_measurement_or_inventory_promotion']=len(scoped)==6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications','F'+str(i)) for i,row in scoped) and any(term in details['Availability'] for term in ['unknown','unconfirmed']) and all(term not in details['Availability'] for term in ['stock: unlimited','lead time: 1 week'])
        checks[vid+'_standing_acceptance_and_later_owner_fixing_fact_distinct']=all(('fixing type subsequently owner-stated' if vid in ['EMBED-SHELLS-WHITE','FACET-MOUND-GOLD-LEAF'] and row[3]=='Fixing' else 'no individual reply recorded') in value('Reviewed Specifications','F'+str(i)) for i,row in scoped)
        rr=[(i+7,row) for i,row in enumerate(data['reviews']) if row[0]==cid and row[1]==vid];assert len(rr)==1
        ri,row=rr[0];checks[vid+'_exact_primary_scoped_photo_gap_and_context_links_saved']=bool(row[9] and row[10] and row[15] and row[16]) and new['sheets']['Current Reviews']['hyperlinks'].get('P'+str(ri))==row[15] and new['sheets']['Current Reviews']['hyperlinks'].get('Q'+str(ri))==row[16] and any(entry['values'][0]==vid and entry['values'][9]==row[10] and entry['values'][10]==row[9] and 'elsewhere unknown' in entry['values'][8].lower() for entry in data['additional_photograph_gaps'])
    checks['Moon_White_weight_sources_unresolved_and_price150_distinct_from_MCP4_175']=all(all(term in next_details[f'MCP{i}-WHITE']['Weight'] for term in ['2–4kg','trade4kg','retail5kg','unweighed']) and '£150' in next_details[f'MCP{i}-WHITE']['Individual price'] for i in [1,2,3])
    checks['Blue350_is_working_comparison_not_exact_Blue_offer']='£350' in next_details['MCP2-BLUE-SPLASHES']['Individual price'] and 'exact Blue offer unconfirmed' in next_details['MCP2-BLUE-SPLASHES']['Individual price']
    checks['Moon_Rust350_395_keep_current_image_association_unverified']=all(price in next_details[vid]['Individual price'] and 'current exact-image correspondence unverified' in next_details[vid]['Individual price'] for vid,price in [('MCP2-VERDIGRIS-RUST','£350'),('MCP3-VERDIGRIS-RUST','£395')])
    checks['Embedded_owner70x15_depth_guess_and_revised_weight_price_saved']='70 H × 15 W cm — owner-stated' in next_details['EMBED-SHELLS-WHITE']['Dimensions / depth'] and 'depth 5–7 cm is a working guess' in next_details['EMBED-SHELLS-WHITE']['Dimensions / depth'] and '4–6kg' in next_details['EMBED-SHELLS-WHITE']['Weight'] and '£250–£350' in next_details['EMBED-SHELLS-WHITE']['Individual price']
    checks['Faceted_size_weight_recipe_and_price_remain_estimates']='planning guess' in next_details['FACET-MOUND-GOLD-LEAF']['Dimensions / depth'] and '6–10kg' in next_details['FACET-MOUND-GOLD-LEAF']['Weight'] and 'binder and metal unknown' in next_details['FACET-MOUND-GOLD-LEAF']['Material / finish'] and '£500–£800' in next_details['FACET-MOUND-GOLD-LEAF']['Individual price']
    checks['two_owner_keyhole_types_do_not_establish_counts_or_load']=all('Keyhole fixing — owner-stated type; number, hardware, attachment and load capacity unconfirmed' in next_details[vid]['Fixing'] for vid in ['EMBED-SHELLS-WHITE','FACET-MOUND-GOLD-LEAF'])
    policy=data['global_fixing_choice_policy'];overlays={tuple(x['key']):x for x in data['fixing_choice_overlays']};fixing=[(i+7,row) for i,row in enumerate(specs) if row[3]=='Fixing'];choice=policy['catalogue_display'];choice_state='Owner instructed catalogue fixing choice; existing or historical fitted hardware remains separate';choice_basis='Owner instruction, 20 October 2026: choose either keyhole fixing or French cleat. This does not confirm installed hardware, number, material, attachment or load rating.'
    checks['global_keyhole_or_cleat_choice_summary_saved']=value('Summary','A33')=='Fixing choices' and value('Summary','B33')=='Keyhole fixing or French cleat' and 'Existing or historical fitted hardware stays recorded separately' in value('Summary','C33')
    checks['all278_fixing_rows_display_offered_choice_and_preserve_individual_hardware']=len(fixing)==len(overlays)==278 and all(value('Reviewed Specifications','E'+str(i))=='\n'.join(dict.fromkeys(v for v in [overlays[tuple(row[:2])]['before_detail'],choice] if v)) and value('Reviewed Specifications','F'+str(i))=='\n'.join(dict.fromkeys(v for v in [overlays[tuple(row[:2])]['before_state'],choice_state] if v)) and value('Reviewed Specifications','G'+str(i))=='\n'.join(dict.fromkeys(v for v in [overlays[tuple(row[:2])]['before_basis'],choice_basis] if v)) for i,row in fixing)
    checks['global_choice_not_both_installed_or_new_physical_measurements']=policy['choice_mode']=='CHOOSE_ONE_FOR_THE_SCULPTURE' and not policy['actual_installed_options_on_every_existing_cast_confirmed'] and not policy['both_types_simultaneously_fitted_to_every_sculpture_claimed'] and not policy['physical_specifications_independently_verified']
    batch91_scopes=[('BC-AC-ONE','AC-ONE-LEFT-SANDSTONE'),('BC-AC-ONE','AC-ONE-LEFT-PEWTER'),('BC-PANEL-CURVES','PANEL-CURVES-BEIGE-PROCESS'),('BC-PANEL-CURVES','PANEL-CURVES-MULTICOLOUR-PATINA'),('BC-PLANT','PLANT-WHITE'),('BC-RW-SPIRAL1','RAKED-SPIRAL1-BEIGE'),('BC-RW-SPIRAL1','RAKED-SPIRAL1-WHITE'),('BC-RW-WAVE','RAKED-SPIRAL2-BEIGE'),('BC-RW-WAVE','RAKED-SPIRAL2-WHITE'),('BC-RW-SPIRAL3','RAKED-SPIRAL3-BEIGE'),('BC-RW-SPIRAL3','RAKED-SPIRAL3-WHITE'),('BC-CRATER-WIDE','CRATER-WIDE-DRIP-RUST'),('BC-MFW-1','MFW-LEFT-WHITE'),('BC-MFW-2','MFW-RIGHT-WHITE'),('BC-MOON-RING','MOON-RING-WHITE')]
    for cid,vid in batch91_scopes:
        scoped=[(i+7,row) for i,row in enumerate(specs) if row[0]==cid and row[1]==vid]
        checks[vid+'_all_six_working_not_measured_saved']=len(scoped)==6 and all('Owner accepted working proposal; not physically verified' in value('Reviewed Specifications','F'+str(i)) and 'no individual reply recorded' in value('Reviewed Specifications','F'+str(i)) for i,row in scoped)
        rr=[(i+7,row) for i,row in enumerate(data['reviews']) if row[0]==cid and row[1]==vid];assert len(rr)==1
        ri,row=rr[0];gap=next(x for x in data['additional_photograph_gaps'] if x['values'][0]==vid)
        checks[vid+'_exact_image_folder_ID_and_scoped_gap_saved']=bool(row[9] and row[10]) and gap['values'][9:11]==[row[10],row[9]] and 'elsewhere unknown' in gap['values'][8] and new['sheets']['Current Reviews']['hyperlinks'].get('H'+str(ri))==row[7] and new['sheets']['Current Reviews']['hyperlinks'].get('I'+str(ri))==row[8]
    weights=[(i+7,x) for i,x in enumerate(specs) if x[3]=='Weight'];wo={tuple(x['key']):x for x in data['weight_policy_overlays']}
    checks['all278_weight_dispositions_and_saved_values_exact']=len(weights)==len(wo)==278 and all(all(value('Reviewed Specifications',col+str(i))==wo[tuple(row[:2])][key] for col,key in [('E','after_detail'),('F','after_state'),('G','after_basis')]) for i,row in weights)
    checks['214_current_applicable_weight_bodies_retained_not_stale87_values']=sum(x['disposition']=='EXISTING_SCOPED_APPROXIMATION_ACCEPTED' for x in wo.values())==214 and all(x['before_detail']==x['after_detail'] for x in wo.values() if x['disposition']=='EXISTING_SCOPED_APPROXIMATION_ACCEPTED')
    checks['nine_new_conditional_and_seven_recovered_weight_displays']=sum(x['disposition']=='NEW_CONDITIONAL_ESTIMATE_PREPARED' for x in wo.values())==9 and sum(x['disposition']=='EXISTING_ESTIMATE_DISPLAY_RECOVERY' for x in wo.values())==7
    checks['48_reference_deferred_rows_no_new_numeric_mass']=sum(x['disposition'] not in ['EXISTING_SCOPED_APPROXIMATION_ACCEPTED','NEW_CONDITIONAL_ESTIMATE_PREPARED','EXISTING_ESTIMATE_DISPLAY_RECOVERY'] for x in wo.values())==48 and all(x['before_detail']==x['after_detail'] for x in wo.values() if x['disposition'] not in ['EXISTING_SCOPED_APPROXIMATION_ACCEPTED','NEW_CONDITIONAL_ESTIMATE_PREPARED','EXISTING_ESTIMATE_DISPLAY_RECOVERY'])
    checks['global_weight_policy_summary_separate_from_scoped_approvals']=value('Summary','A34')=='Approximate weights' and 'Nine new estimates and seven recovered source displays' in value('Summary','C34') and value('Summary','E7')=='Scoped working proposal approvals' and data['global_approximate_weight_policy']['new_six_field_acceptances']==0
    checks['Knightsbridge_literal50cm_shell_model_uncertainty_saved']=all(t in wo[('BC-KNIGHT','KNIGHT-WHITE')]['after_basis'] for t in ['50cm','3m²','20–60kg','No50mm'])
    checks['Chelsea250x100_new100kg_model_only_BASE']=all(t in wo[('BC-CHELSEA','BASE')]['after_detail'] for t in ['100kg','75–140kg','250x100cm','Supersedes the25kg','does not apply to source002']) and wo[('BC-CHELSEA','SOURCE-G233002')]['after_detail']==wo[('BC-CHELSEA','SOURCE-G233002')]['before_detail']
    checks['Chelsea_existing_explicit_replacement_ID_now_displayed_preserving_history']=any(row[0]=='BC-CHELSEA' and row[1]=='BASE' and row[9]=='id:cnqzTNngPVsAAAAAAA53Gw' for row in data['reviews']) and 'id:cnqzTNngPVsAAAAAAAyj2w remains historical' in wo[('BC-CHELSEA','BASE')]['after_basis'] and data['current_reference_resolutions'][0]['same_native_revision_and_size_as_replacement_receipt']
    checks['Ammonite_four_individual_source_weight_conflicts_recovered']=all('each' in wo[(cid,'BASE')]['after_detail'] and ('6–8' if cid.startswith('AM-S') else '20–22') in wo[(cid,'BASE')]['after_detail'] for cid in ['AM-S1','AM-S2','AM-L1','AM-L2'])
    checks['Barbados_existing83kg_not_raw_unit_conversion']='83 kg' in wo[('BC-BAR-WAVE','BASE')]['after_detail']
    checks['Acanthus_two_supplemental_gaps_updated_without_duplicates']=all(sum(x['values'][0]==vid for x in data['additional_photograph_gaps'])==1 and 'Cropped detail primary' in next(x['values'][4] for x in data['additional_photograph_gaps'] if x['values'][0]==vid) for vid in ['AC-ONE-LEFT-SANDSTONE','AC-ONE-LEFT-PEWTER'])
    checks['Raked_beige_shared_pair_remains_positioned_not_isolated']=all('shared beige pair001' in next(x['values'][4] for x in data['additional_photograph_gaps'] if x['values'][0]==vid) for vid in ['RAKED-SPIRAL1-BEIGE','RAKED-SPIRAL2-BEIGE'])
    assert all(checks.values()), [k for k, v in checks.items() if not v]
    output = {'status': 'PASS', 'checked_utc': datetime.now(timezone.utc).isoformat(), 'checks': {k: 'PASS' for k in checks},
              'check_count': len(checks), 'original_source_cells_compared': source_cells,
              'original_tabs_retained': len(old['sheets']), 'new_review_tabs': len(new['sheets']) - len(old['sheets']),
              'platform_records': 81, 'dropbox_file_ids': 6663, 'source_specification_claims': 3052,
              'review_scope_rows': len(data['reviews']), 'specification_entries': len(data['specifications']),
              'output': receipt['output'], 'output_sha256': receipt['output_sha256'],
              'visual_verification': 'PENDING'}
    (HERE / 'independent-file-verification.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in output.items() if k not in ['checks']}))
    print('Summary instructions:', {a: value('Summary', a) for a in ['A21', 'A22', 'A23', 'A24', 'A25', 'A26'] if a in new['sheets']['Summary']['cells']})


if __name__ == '__main__':
    main()
