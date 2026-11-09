"""Read-only preflight for the catalogue's Google Sheets import boundary."""
import argparse
from collections import Counter
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import posixpath
import tempfile
import xml.etree.ElementTree as E
import zipfile


def inspect(path):
    # Sheet filenames are relationship targets, not necessarily sheet1.xml.
    # https://learn.microsoft.com/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document
    data = Path(path).read_bytes()
    main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    strict = 'http://purl.oclc.org/ooxml/spreadsheetml/main'
    typed_dates = Counter()
    errors = []
    holds = []
    formulas = sheets = 0
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                raise ValueError('The workbook archive contains duplicate part names.')
            workbook = E.fromstring(archive.read('xl/workbook.xml'))
            namespace = next((n for n in (main, strict) if workbook.tag == '{'+n+'}workbook'), None)
            if namespace is None:
                raise ValueError('A supported SpreadsheetML workbook is required.')
            ns = {'s': namespace}
            references = workbook.findall('s:sheets/s:sheet', ns)
            if not references:
                raise ValueError('The workbook contains no referenced worksheets.')
            relations = E.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
            by_id = {}
            for relation in relations:
                identity = relation.get('Id')
                if not identity or identity in by_id:
                    raise ValueError('Workbook relationship IDs are missing or duplicated.')
                by_id[identity] = relation
            seen = set()
            for sheet in references:
                identity = next((value for key, value in sheet.attrib.items() if key.endswith('}id')), None)
                relation = by_id.get(identity)
                if (relation is None or not relation.get('Type', '').endswith('/worksheet')
                        or relation.get('TargetMode') == 'External'):
                    raise ValueError('A sheet has a missing, external or unsupported worksheet relationship.')
                target = relation.get('Target', '')
                if not target or '\\' in target:
                    raise ValueError('A worksheet relationship has an invalid target.')
                part = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl', target))
                if part.startswith('../') or part in ('.', '..') or part in seen:
                    raise ValueError('Worksheet relationships escape the package or repeat a part.')
                seen.add(part)
                with archive.open(part) as stream:
                    parser = E.iterparse(stream, events=('start', 'end'))
                    _, root = next(parser)
                    if root.tag != '{'+namespace+'}worksheet':
                        raise ValueError('A worksheet relationship points to an unsupported XML part.')
                    sheets += 1
                    for event, cell in parser:
                        if event != 'end':
                            continue
                        if cell.tag == '{'+namespace+'}c':
                            formulas += cell.find('s:f', ns) is not None
                            if cell.get('t') == 'd':
                                typed_dates[part] += 1
                            elif cell.get('t') == 'e':
                                errors.append({'part': part, 'cell': cell.get('r')})
                            cell.clear()
                        elif cell.tag == '{'+namespace+'}row':
                            cell.clear()
    except (zipfile.BadZipFile, KeyError, E.ParseError, ValueError, StopIteration) as error:
        holds.append('The source workbook package could not be fully inspected: ' + str(error))
    if typed_dates:
        holds.append('OOXML typed dates are valid Excel but can be dropped by Google import. Preserve their UTC instants in numeric Excel-date cells before import.')
    if errors:
        holds.append('Source workbook contains formula error cells; reconcile before import.')
    return dict(status='HOLD_GOOGLE_IMPORT' if holds else 'PASS_GOOGLE_IMPORT_PREFLIGHT',
                sha256=hashlib.sha256(data).hexdigest(), sheets=sheets,
                formulas=formulas, typed_date_cells=sum(typed_dates.values()),
                typed_dates_by_part=dict(typed_dates), formula_error_cells=errors,
                holds=holds, live_writes=0,
                limitation='Preflight is not native conversion verification. Export the resulting private Google document and compare every populated value/formula/table/date before declaring completion.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.report and (args.report.resolve() == args.workbook.resolve() or
                            (args.report.exists() and args.report.samefile(args.workbook))):
            raise ValueError('The report must not overwrite the source workbook.')
        result = inspect(args.workbook)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(prefix='.'+args.report.name+'-', dir=args.report.parent)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                    json.dump(result, stream, indent=2)
                    stream.write('\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, args.report)
            finally:
                Path(temporary).unlink(missing_ok=True)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error)+'\n')
    print(json.dumps(result))
    return 2 if result['holds'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
