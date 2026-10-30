"""Describe narrow lifecycle edits to both current workbook views."""
from pathlib import Path
import importlib.util
import json
import re

H = Path(__file__).resolve().parent
B = H.parents[2]
read = lambda p: json.loads(Path(p).read_text())
spec = importlib.util.spec_from_file_location('native_book', B / 'components/reconciliation/acanthus-native-availability-2026-10-25/verify_workbook.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
manifest = read(H / 'input-manifest.json')
out = B / 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/acanthus-white-black-retirement-2026-10-26'
out.mkdir(parents=True, exist_ok=True)
reason = 'Owner retired Acanthus Two Leaves - White and Black on 26 October 2026. Historical identity, source values and IDs are retained. No current offer, photograph, measurement or draft-creation task.'
plans = []
for key, output in [('core_workbook', 'Boldstone_Sculpture_Master_Catalogue_2026-10-26.xlsx'),
                    ('comprehensive_workbook', 'Boldstone_Wall_Sculptures_Unified_2026-10-26.xlsx')]:
    book = module.Book(manifest[key]['snapshot'])
    edits = []
    def edit(sheet, cell, value=None, formula=None):
        before = book.sheet(sheet)[0].get(cell)
        if formula is not None:
            expected = ('formula', formula.lstrip('='))
        else:
            expected = ('number', str(value)) if isinstance(value, (int, float)) else ('text', value)
        if before != expected:
            edits.append({'sheet': sheet, 'cell': cell, 'before': list(before) if before else None,
                          **({'formula': formula} if formula is not None else {'value': value})})
    if key == 'core_workbook':
        edit('Master Catalogue', 'A3', '187 active options; 189 historical option rows retained, including two owner-retired finishes. Source evidence and specifications for all other options are preserved.')
        edit('Master Catalogue', 'A6', 'Counts exclude retired finishes and unbounded custom requests. Sandstone One Leaf and White and Black Two Leaves are history only. All current Frozen Fish stay 70 cm high x 15 cm wide.')
        edit('Master Catalogue', 'E4', 'Retained rows with six fields')
        edit('Master Catalogue', 'L20', 'Retired')
        edit('Master Catalogue', 'V20', reason)
        edit('Components', 'D14', formula='=COUNTIFS(\'Master Catalogue\'!$D$10:$D$198,A14,\'Master Catalogue\'!$L$10:$L$198,"<>Retired")')
        for row in range(70, 76):
            edit('Specifications', 'E' + str(row), 'Retired / historical detail')
        edit('Specifications', 'A3', '1,134 retained specification rows; 1,122 active field groups across 187 options. Retired option details remain historical.')
        for col in ['C', 'F', 'I']:
            edit('Photo Coverage', col + '20', 'Retired / not applicable')
        edit('Photo Coverage', 'L20', reason)
        edit('Photo Coverage', 'A3', '187 active options. Retired rows are history only; existing role, origin and owner-hold qualifications are preserved.')
        edit('Missing Pictures', 'F167', 'No action - owner-retired option.')
        edit('Missing Pictures', 'N167', 'Retired / not applicable')
        for col in ['C', 'D', 'H']:
            edit('Listing Reconciliation', col + '20', 'Retired / historical source evidence')
        edit('Listing Reconciliation', 'L20', 'No active task. O069 remains a separate Bronze source record; no exact White and Black listing is bound.')
        edit('Listing Reconciliation', 'W20', 'RETIRED_NO_ACTIVE_PLATFORM_ACTION')
        edit('Listing Resolution', 'C20', 'Retired / no current offer')
        edit('Listing Resolution', 'Q20', 'No active task - owner-retired option. Preserve shared source records.')
        edit('Draft Listings', 'C15', 'Retired option history')
        edit('Draft Listings', 'O15', 'Do not create or publish this retired option. Proposed identifiers remain historical only.')
        edit('Draft Listings', 'Q15', 'Retired')
        edit('Selling Details', 'E20', 'Retired / historical price')
        edit('Selling Details', 'K20', 'Excluded from current offers at owner request')
        edit('Selling Details', 'P20', 'Retired - no current listing task')
        edit('Selling Details', 'Q20', reason)
        expected = [{'sheet': 'Master Catalogue', 'cell': 'B4', 'value': 187},
                    {'sheet': 'Components', 'cell': 'D14', 'value': 4},
                    {'sheet': 'Master Catalogue', 'cell': 'L20', 'value': 'Retired'}]
        previews = [['Master Catalogue', 'A3:H6', 'core-counts'], ['Master Catalogue', 'K19:O20', 'core-retirement'],
                    ['Draft Listings', 'O14:Q15', 'core-draft-retired']]
    else:
        edit('Wall Sculptures', 'B19', 'Retired option history')
        edit('Wall Sculptures', 'C19', 'Retired at owner request')
        edit('Wall Sculptures', 'AC19', reason)
        edit('Wall Sculptures', 'AE19', 'No active variant-creation task. The related Bronze source is preserved as a separate record.')
        edit('Wall Sculptures', 'AH19', 'Owner-retired 26 October 2026; retained source history only.')
        edit('Products', 'A3', '187 active options + one retired option row in this source table; other historical retirement evidence is retained separately.')
        edit('Products', 'C16', 'Retired')
        edit('Products', 'Y16', 'No active offer or draft-creation task. The proposed SKU/handle is historical only.')
        edit('Products', 'AA16', 'Retired. Owned source folder and three images are native NOT_FOUND.')
        edit('Products', 'AF16', reason)
        for row in range(67, 73):
            edit('Specifications', 'D' + str(row), 'Retired')
        edit('Components', 'J11', 'Four active finish options. The owner-retired White and Black option is retained in historical member names and source evidence.')
        edit('Overview', 'B7', formula='=COUNTIFS(\'Products\'!A7:A194,"<>",\'Products\'!C7:C194,"<>Retired")')
        edit('Overview', 'C7', '187 active options. White and Black Two Leaves is retained as retired history.')
        edit('Overview', 'A3', 'Product register and complete saved source inventories - retirement update 26 October 2026')
        edit('Guide and sources', 'B19', 'Original fields are retained in Squarespace raw and Shopify raw, including HTML and continuation blanks. Owner-retired options are historical rows excluded from active counts and current exports.')
        expected = [{'sheet': 'Wall Sculptures', 'cell': 'B5', 'value': 187},
                    {'sheet': 'Overview', 'cell': 'B7', 'value': 187},
                    {'sheet': 'Products', 'cell': 'C16', 'value': 'Retired'}]
        previews = [['Wall Sculptures', 'A5:H5', 'unified-counts'], ['Products', 'A15:F16', 'unified-retirement'],
                    ['Overview', 'A6:C7', 'unified-active-count']]
    plans.append({'key': key, 'source': manifest[key]['snapshot'], 'output': str(out / output),
                  'edits': edits, 'expected': expected, 'previews': previews})
    book.close()
(H / 'workbook-edit-plan.json').write_text(json.dumps({'plans': plans}, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'workbooks': len(plans), 'edits': {p['key']: len(p['edits']) for p in plans}, 'output_directory': str(out)}, indent=2))
