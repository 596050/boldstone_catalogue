import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, '../../..');
const data = JSON.parse(await fs.readFile(path.join(here, 'canonical-count-register.json'), 'utf8'));
const output = path.join(base, 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Individual_Sculptures_List_and_Count_2026-10-20.xlsx');
const wb = Workbook.create();
const names = ['Components', 'Listing Options', 'Sets and Context', 'Aliases', 'References and Gaps', 'Source Mapping'];
const sheets = Object.fromEntries(names.map(name => [name, wb.worksheets.add(name)]));
const expected = {}, links = [], formulas = [];
const green = '#334E40', ink = '#26392E', muted = '#647167';
const col = n => { let v = ''; for (n++; n; n = Math.floor((n - 1) / 26)) v = String.fromCharCode(65 + (n - 1) % 26) + v; return v; };
const literal = x => typeof x === 'string' && x.startsWith('=') ? "'" + x : x ?? '';
const link = (url, label = 'Image') => url ? { url, label } : '';
const display = x => x && typeof x === 'object' && 'url' in x ? x.label : literal(x);
const quote = x => String(x).replaceAll('"', '""');
const human = x => String(x ?? '').toLowerCase().replaceAll('_', ' ').replace(/^./, x => x.toUpperCase());
const comp = Object.fromEntries(data.components.map(x => [x.component_id, x]));
const option = Object.fromEntries(data.options.map(x => [x.product_id, x]));
const componentNames = ids => ids.map(id => comp[id] ? `${comp[id].name} [${id}]` : id).join('\n');
const native = x => typeof x === 'number' ? x : x === '' || x == null ? '' : Number(x);

function add(name, title, note, headers, rows, widths) {
  const s = sheets[name], last = 9 + rows.length;
  s.showGridLines = false;
  s.tabColor = name === 'Components' || name === 'Listing Options' ? green : '#92A196';
  s.getRangeByIndexes(0, 0, last, headers.length).format.font = { name: 'Arial', size: 10, color: ink };
  s.getRangeByIndexes(0, 0, last, headers.length).format.verticalAlignment = 'center';
  s.getRange('A2:F2').merge();
  s.getRange('A2').values = [[title]];
  s.getRange('A2:F2').format = { font: { name: 'Arial', size: 17, bold: true, color: green }, rowHeight: 32 };
  s.getRange('A3:H3').merge();
  s.getRange('A3').values = [[note]];
  s.getRange('A3:H3').format = { font: { name: 'Arial', size: 10, color: muted }, wrapText: true, rowHeight: 40 };
  s.getRangeByIndexes(8, 0, 1, headers.length).values = [headers];
  if (rows.length) s.getRangeByIndexes(9, 0, rows.length, headers.length).values = rows.map(row => row.map(display));
  const table = s.tables.add(`A9:${col(headers.length - 1)}${last}`, true, 'Count_' + name.replaceAll(' ', '_'));
  table.style = 'TableStyleLight1';
  table.showFilterButton = true;
  s.getRangeByIndexes(8, 0, 1, headers.length).format = { fill: green, font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, wrapText: true, horizontalAlignment: 'center', rowHeight: 38 };
  widths.forEach((width, j) => s.getRangeByIndexes(0, j, last, 1).format.columnWidth = width);
  if (rows.length) s.getRangeByIndexes(9, 0, rows.length, headers.length).format.wrapText = true;
  rows.forEach((row, i) => {
    const lines = Math.max(...row.map((value, j) => String(display(value)).split('\n').reduce((n, part) => n + Math.max(1, Math.ceil(part.length / Math.max(10, widths[j] * .9))), 0)));
    s.getRangeByIndexes(i + 9, 0, 1, headers.length).format.rowHeight = Math.max(38, Math.min(409, lines * 13 + 10));
    row.forEach((value, j) => {
      if (value && typeof value === 'object' && 'url' in value) {
        const cell = `${col(j)}${i + 10}`;
        s.getRange(cell).format.font = { name: 'Arial', size: 10, color: '#245F9E', underline: 'single' };
        links.push({ sheet: name, cell, target: value.url, label: value.label });
      }
    });
  });
  s.freezePanes.freezeRows(9);
  s.freezePanes.freezeColumns(2);
  expected[name] = { first: 10, last, headers, rows: rows.map(row => row.map(display)), widths };
  return s;
}

const componentRows = data.components.map(x => [x.component_id, x.name, x.family, x.option_count, x.scope_note,
  link(x.image_url, x.component_id === 'BC-CR-RING' ? 'Right panel' : 'Image'), link(x.folder_url, 'Folder'),
  x.file_id, x.folder_id, x.source_component_ids.join('\n'), x.retained_names.join('\n')]);
add('Components', 'Individual sculpture components',
  'Counted by catalogue identity. Finish, size and build choices appear on Listing Options. These are catalogue records; physical casts, moulds and stock are not counted here.',
  ['Component ID', 'Component name', 'Family / series', 'Sale options', 'Identity and option scope', 'Example', 'Containing folder', 'Dropbox file ID', 'Dropbox folder ID', 'Original component IDs', 'Retained names'],
  componentRows, [28, 51, 32, 14, 76, 16, 19, 40, 40, 35, 83]);

const sourceType = x => x.unbound_size_option ? 'Source-only Long size option' : x.option_family_id ? 'Wall Circle kept visual' : x.owner_name_keep_recorded === false ? 'Source-supported Ring option' : 'Owner-kept option';
const optionRows = data.options.map(x => [x.canonical_component_id ?? (x.option_family_id ? 'Wall Circle option family' : 'Long size option — parent unbound'),
  x.product_id, x.name, sourceType(x), x.size_class || 'No separate size label', x.build_class,
  x.specifications['Dimensions / depth'].display, (x.orientation_options ?? []).join(' / '), x.offered_fixing_choices.join(' or '),
  link(x.image_url, x.source_component_id === 'BC-CR-RING' ? 'Right panel in pair' : 'Image'), link(x.folder_url, 'Folder'),
  x.file_id || 'Unbound', x.folder_id || 'Unbound', x.source_scopes.join('\n'),
  x.image_role || (x.historical_primary_link ? 'Current path updated by stable ID; earlier source links retained' : 'Reviewed reference; image provenance and actual specimen specifications retain source qualifications'),
  x.readiness_note || 'Working specification estimates and source conflicts retained; listing publication and physical stock are unverified']);
add('Listing Options', 'Individual sale options',
  'One row per individually described finish, size or build. Seven Wall Circle visuals remain distinct from the overlapping 144 native website combinations. Long has no exact current image binding.',
  ['Component / family target', 'Option ID', 'Individual listing name', 'Identity basis', 'Size option', 'Build scope', 'Dimensions / depth — source or working detail', 'Orientation choices', 'Offered fixing choices', 'Example image', 'Containing folder', 'Dropbox file ID', 'Dropbox folder ID', 'Original scopes', 'Image scope', 'Remaining qualifications'],
  optionRows, [37, 25, 61, 35, 40, 57, 86, 35, 37, 23, 19, 40, 40, 61, 95, 102]);

const sourceSetRows = data.source_sets.map(x => {
  const offer = x.source_offer;
  const current = x.current_primary_reference ?? {};
  const ids = [...new Set(x.members.flatMap(m => m.canonical_component_targets))];
  return [x.offer_ref, offer.title, 'Platform set / proposed multi-component offer', componentNames(ids), native(offer.native_parts), x.members.length,
    x.relationship_status + '. Exact current finish/size/specimen mapping is not upgraded.', link(offer.source_url, 'Platform source'), link(current.image_url, 'Source reference'), link(current.folder_url, 'Folder'),
    current.file_id || offer.image_file_id || '', current.folder_id || offer.image_folder_id || '', x.members.map(m => `${m.bom_id}: ${m.source_component_id}; position ${m.position}; quantity ${m.quantity}`).join('\n')];
});
const contextRows = data.arrangement_context_references.map(x => {
  const images = x.images ?? [];
  return [x.reference_id, x.name, x.confirmed_member_option_ids.length ? 'Confirmed arrangement of existing components' : 'Group / project context only',
    x.confirmed_member_option_ids.map(id => `${option[id].name} [${id}]`).join('\n') || 'Individual components not established; context retained', '', '',
    x.confirmed_member_option_ids.length ? 'Existing components reused; no additional individual count' : x.component_identification,
    '', link(x.image_url, 'Context image'), link(x.folder_url, 'Folder'),
    [...new Set(images.map(i => i.file_id).filter(Boolean))].join('\n'), [...new Set(images.map(i => i.folder_id).filter(Boolean))].join('\n'), x.source_reference_ids.join('\n')];
});
add('Sets and Context', 'Sets, arrangements and group context',
  '28 source offers have multiple native or proposed components; 27 arrangement/context references are kept separately. These layers can overlap and create no additional individual sculptures.',
  ['Reference ID', 'Set / arrangement / context', 'Record type', 'Identified component targets', 'Native piece count', 'Source BOM positions', 'Relationship and count treatment', 'Platform page', 'Context image', 'Containing folder', 'Dropbox file IDs', 'Dropbox folder IDs', 'Original member / reference IDs'],
  [...sourceSetRows, ...contextRows], [37, 63, 46, 85, 17, 19, 99, 20, 22, 19, 43, 43, 93]);

add('Aliases', 'Names and source identities consolidated',
  'Each row records an alias or orientation relationship. Targets are retained identities, options or references. Alias rows contribute zero additional sculptures.',
  ['Alias / earlier name', 'Original key', 'Canonical targets', 'Relationship', 'Reason and limits', 'Image', 'Folder', 'Dropbox file ID', 'Dropbox folder ID'],
  data.aliases.map(x => [x.source_name || x.source, x.source, x.targets.join('\n'), human(x.relationship), x.reason,
    link(x.image_url), link(x.folder_url, 'Folder'), x.file_id, x.folder_id]),
  [55, 57, 58, 48, 119, 19, 19, 40, 40]);

add('References and Gaps', 'Source reference decisions and remaining image gaps',
  'Nine additional finish sources are closed as detail, scene or group context. Included Ring and Long options retain their photo gaps. Group-only components are not inferred.',
  ['Case ID', 'Sculpture / source appearance', 'Case type', 'Evidence and remaining limits', 'Current count treatment', 'Example / context', 'Containing folder', 'Original scopes / configurations'],
  data.exceptions.map(x => [x.candidate_id, x.name, x.exception_type, x.required_information, x.count_treatment,
    link(x.image_url, x.candidate_id === 'GAP-BC-CR-RING' ? 'Right panel in pair' : 'Source reference'), link(x.folder_url, 'Folder'),
    (x.source_scopes ?? x.source_configuration_ids ?? []).join('\n')]),
  [38, 64, 49, 118, 108, 24, 19, 72]);

const reviewRows = data.source_review_reconciliation.map(x => {
  const source = data.original_review_specification_assertions.find(s => s[0] + '|' + s[1] === x.source_scope);
  return ['Review row', x.source_scope, x.source_title, human(x.disposition), componentNames(x.component_targets), x.targets.join('\n'), x.reason,
    link(x.image_url), link(x.folder_url, 'Folder'), source?.[9] ?? '', source?.[10] ?? '', x.individual_count_increment];
});
const modelRows = data.source_component_dispositions.map(x => ['Source component ID', x.source_component_id, x.source_name, x.treatment,
  componentNames(x.component_targets), x.option_family_target || '', 'Crosswalk of the source model identifier; never added to the overlapping review-row count.', '', '',
  x.source_file_ids.join('\n'), x.source_folder_ids.join('\n'), 0]);
add('Source Mapping', 'Source rows mapped to counted identities',
  'All 278 review rows and all 125 source component IDs have a disposition. Review increments total 177; seven supplemental Wall Circle entries complete 184. Current links resolve by stable ID; historical source IDs remain labelled.',
  ['Source layer', 'Source key', 'Earlier / source title', 'Disposition', 'Component targets', 'Option / family / reference targets', 'Reason', 'Source image', 'Source folder', 'Historical Dropbox file IDs', 'Historical Dropbox folder IDs', 'Review option increment'],
  [...reviewRows, ...modelRows], [27, 59, 65, 60, 87, 68, 122, 19, 19, 55, 55, 22]);

const componentsSheet = sheets.Components;
const componentLast = expected.Components.last, optionLast = expected['Listing Options'].last;
const summaryCells = [
  ['A4', 'Identified components', 'B4', `=COUNTA(A10:A${componentLast})`, data.summary.identified_component_identities],
  ['C4', 'Options on components', 'D4', `=SUM(D10:D${componentLast})`, data.summary.individual_options_on_identified_components],
  ['E4', 'All individual sale options', 'F4', `=COUNTA('Listing Options'!B10:B${optionLast})`, data.summary.individual_named_working_options],
  ['G4', 'Source-only Long option', 'H4', `=COUNTIF('Listing Options'!D10:D${optionLast},"Source-only Long size option")`, 1],
];
for (const [labelCell, label, resultCell, formula, expectedValue] of summaryCells) {
  componentsSheet.getRange(labelCell).values = [[label]];
  componentsSheet.getRange(labelCell).format = { wrapText: true, rowHeight: 42, font: { name: 'Arial', size: 10, color: muted } };
  componentsSheet.getRange(resultCell).formulas = [[formula]];
  componentsSheet.getRange(resultCell).format.font = { name: 'Arial', size: 16, bold: true, color: green };
  componentsSheet.getRange(resultCell).format.horizontalAlignment = 'center';
  componentsSheet.getRange(resultCell).setNumberFormat('#,##0');
  formulas.push({ sheet: 'Components', cell: resultCell, formula, expected: expectedValue });
}
componentsSheet.getRange(`D10:D${componentLast}`).formulas = data.components.map((x, i) => {
  const formula = `=COUNTIF('Listing Options'!$A$10:$A$${optionLast},A${i + 10})`;
  formulas.push({ sheet: 'Components', cell: 'D' + (i + 10), formula, expected: x.option_count });
  return [formula];
});
componentsSheet.getRange(`D10:D${componentLast}`).setNumberFormat('0');
componentsSheet.getRange(`D10:D${componentLast}`).format.horizontalAlignment = 'center';
sheets['Sets and Context'].getRange(`E10:F${expected['Sets and Context'].last}`).format.horizontalAlignment = 'center';
componentsSheet.getRange('A6:H6').merge();
componentsSheet.getRange('A6').values = [['184 sale-option records = 176 options on 111 identified component identities + 7 Wall Circle visual options + 1 documented Long size option with no exact current photograph.']];
componentsSheet.getRange('A6:H6').format = { wrapText: true, rowHeight: 40, fill: '#EAF0EB', font: { name: 'Arial', size: 11, bold: true, color: green } };
componentsSheet.getRange('A7:H7').merge();
componentsSheet.getRange('A7').values = [['The complete unique-design total remains open for Wall Circle, the Long option’s geometry parent, historical DR3 and unidentified group contents. Nine extra finish sources are closed as context. Sets, aliases and repeated photographs are excluded.']];
componentsSheet.getRange('A7:H7').format = { wrapText: true, rowHeight: 40, font: { name: 'Arial', size: 10, color: muted } };
wb.recalculate();

await fs.writeFile(path.join(here, 'workbook-inspection.ndjson'), (await wb.inspect({ kind: 'region', sheetId: 'Components', range: 'A4:H7', maxChars: 3500, tableMaxRows: 4, tableMaxCols: 8 })).ndjson);
await fs.writeFile(path.join(here, 'formula-error-scan.ndjson'), (await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 30 }, summary: 'Formula errors' })).ndjson);
await fs.mkdir(path.dirname(output), { recursive: true });
const exported = await SpreadsheetFile.exportXlsx(wb);
await exported.save(output);
await fs.writeFile(path.join(here, 'expected-workbook.json'), JSON.stringify({ sheets: expected, formulas, hyperlinks: links }, null, 2));
execFileSync('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python',
  [path.join(here, 'native_links_and_verify.py'), '--attach', '--book', output], { stdio: 'inherit' });

// Inspect and render the saved deliverable rather than just the in-memory book.
const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const renderPlan = [
  ['Components', 'A2:H12'], ['Components', 'E9:K12'],
  ['Listing Options', 'A9:F12'], ['Listing Options', 'G9:P11'],
  ['Sets and Context', 'A9:G12'], ['Sets and Context', 'H9:M12'],
  ['Aliases', 'A9:E13'], ['Aliases', 'F9:I13'],
  ['References and Gaps', 'A9:E12'], ['References and Gaps', 'F9:H13'],
  ['Source Mapping', 'A9:F12'], ['Source Mapping', 'G9:L12'],
];
for (const cid of ['BC-CR-RING', 'BC-FFL-1', 'BC-MCP-4']) {
  const i = data.options.findIndex(x => x.canonical_key.startsWith(cid + '|'));
  if (i >= 0) renderPlan.push(['Listing Options', `A${i + 10}:G${i + 10}`]);
}
await fs.mkdir(path.join(here, 'previews'), { recursive: true });
const previews = [];
for (let i = 0; i < renderPlan.length; i++) {
  const [sheetName, range] = renderPlan[i];
  const blob = await saved.render({ sheetName, range, scale: 1, format: 'png' });
  const dest = path.join(here, 'previews', `${String(i + 1).padStart(2, '0')}-${sheetName.replaceAll(' ', '_')}.png`);
  await fs.writeFile(dest, new Uint8Array(await blob.arrayBuffer()));
  previews.push({ sheet: sheetName, range, path: dest });
}
await fs.writeFile(path.join(here, 'preview-manifest.json'), JSON.stringify(previews, null, 2));
const digest = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex');
const receipt = { status: 'EXPORTED_AWAITING_SAVED_FILE_AND_VISUAL_VERIFICATION', output,
  workbook_sha256: await digest(output), register_sha256: await digest(path.join(here, 'canonical-count-register.json')),
  sheet_data_rows: Object.fromEntries(Object.entries(expected).map(([name, x]) => [name, x.rows.length])),
  formula_count_checks: formulas.length, native_image_folder_and_source_links: links.length, saved_workbook_previews: previews.length };
await fs.writeFile(path.join(here, 'export-receipt.json'), JSON.stringify(receipt, null, 2));
console.log(JSON.stringify(receipt));
