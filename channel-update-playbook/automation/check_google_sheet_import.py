"""Read-only preflight for the catalogue's Google Sheets import boundary."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as E
import zipfile


def inspect(path):
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    typed_dates = Counter()
    errors = []
    formulas = sheets = 0
    with zipfile.ZipFile(path) as archive:
        for part in archive.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml', part):
                continue
            sheets += 1
            with archive.open(part) as stream:
                for _, cell in E.iterparse(stream, events=('end',)):
                    if cell.tag != '{'+ns['s']+'}c':
                        continue
                    formulas += cell.find('s:f', ns) is not None
                    if cell.get('t') == 'd':
                        typed_dates[part] += 1
                    elif cell.get('t') == 'e':
                        errors.append({'part': part, 'cell': cell.get('r')})
                    cell.clear()
    holds = []
    if typed_dates:
        holds.append('OOXML typed dates are valid Excel but can be dropped by Google import. Preserve their UTC instants in numeric Excel-date cells before import.')
    if errors:
        holds.append('Source workbook contains formula error cells; reconcile before import.')
    return dict(status='HOLD_GOOGLE_IMPORT' if holds else 'PASS_GOOGLE_IMPORT_PREFLIGHT',
                sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), sheets=sheets,
                formulas=formulas, typed_date_cells=sum(typed_dates.values()),
                typed_dates_by_part=dict(typed_dates), formula_error_cells=errors,
                holds=holds, live_writes=0,
                limitation='Preflight is not native conversion verification. Export the resulting private Google document and compare every populated value/formula/table/date before declaring completion.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = inspect(args.workbook)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
    raise SystemExit(2 if result['holds'] else 0)
