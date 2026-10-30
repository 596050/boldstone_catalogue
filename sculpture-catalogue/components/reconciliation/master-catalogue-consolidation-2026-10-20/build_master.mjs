import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile, FileBlob } from '@oai/artifact-tool';

const here = path.dirname(fileURLToPath(import.meta.url));
const base = path.resolve(here, '../../..');
const data = JSON.parse(await fs.readFile(path.join(here, 'canonical-master-register.json'), 'utf8'));
const output = path.join(base, 'outputs/01a144ab-1a7c-7223-a403-73a4d53d70ff/Boldstone_Sculpture_Master_Catalogue_2026-10-20.xlsx');
if (process.argv.includes('--diagnose-lookup')) {
  const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
  const s = saved.worksheets.getItem('Master Catalogue');
  const allFields = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability'];
  saved.worksheets.getItem('Specifications').getRange('P10:P1113').values = data.options.flatMap(x => allFields.map(f => [x.product_id + '::' + f]));
  const key = '"' + data.options[0].product_id + '::Weight"';
  const source = "'Specifications'!$D$10:$D$1113", keys = "'Specifications'!$P$10:$P$1113";
  s.getRange('Z1:Z5').formulas = [[`=MATCH(${key},${keys},0)`],[`=INDEX(${source},2)`],[`=INDEX(${source},2,1)`],[`=INDEX(${source},MATCH(${key},${keys},0),1)`],[`=INDEX(${source},Z1,1)`]];
  saved.recalculate();
  console.log(JSON.stringify({ lookup_diagnostics: s.getRange('Z1:Z5').values })); process.exit(0);
}
if (process.argv.includes('--render-summary')) {
  const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
  const blob = await saved.render({ sheetName: 'Master Catalogue', range: 'A2:H9', scale: 1, format: 'png' });
  const dest = path.join(here, 'previews/29-Master_summary.png');
  await fs.writeFile(dest, new Uint8Array(await blob.arrayBuffer()));
  const manifest = JSON.parse(await fs.readFile(path.join(here, 'preview-manifest.json'), 'utf8'));
  if (!manifest.some(x => x.path === dest)) manifest.push({ sheet: 'Master Catalogue', range: 'A2:H9', path: dest });
  await fs.writeFile(path.join(here, 'preview-manifest.json'), JSON.stringify(manifest, null, 2));
  const receipt = JSON.parse(await fs.readFile(path.join(here, 'export-receipt.json'), 'utf8'));
  receipt.saved_preview_ranges = manifest.length;
  await fs.writeFile(path.join(here, 'export-receipt.json'), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify({ summary_preview: dest, workbook_unchanged: true })); process.exit(0);
}
const wb = Workbook.create();
let previousExpected, previousPreviews;
if (process.argv.includes('--reuse-unchanged-previews')) {
  previousExpected = JSON.parse(await fs.readFile(path.join(here, 'expected-workbook.json'), 'utf8'));
  previousPreviews = JSON.parse(await fs.readFile(path.join(here, 'preview-manifest.json'), 'utf8'));
}
const sheetNames = ['Master Catalogue', 'Specifications', 'Components', 'Sets and Context', 'Aliases', 'References and Gaps', 'Platform Sources', 'Source Mapping', 'Source Specifications'];
const sheets = Object.fromEntries(sheetNames.map(name => [name, wb.worksheets.add(name)]));
const expected = {}, links = [], formulas = [], overflow = [];
const fields = ['Dimensions / depth', 'Weight', 'Material / finish', 'Fixing', 'Individual price', 'Availability'];
const ink = '#28362D', green = '#344E40', muted = '#6D776F';
const col = n => { let s = ''; for (n++; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; };
const literal = x => typeof x === 'string' && x.startsWith('=') ? "'" + x : x ?? '';
const link = (url, label = 'Image') => url ? { url, label } : '';
const val = x => x && typeof x === 'object' && 'url' in x ? x.label : literal(x);
const unique = seq => [...new Set(seq.filter(Boolean))];
const human = x => String(x ?? '').toLowerCase().replaceAll('_', ' ').replace(/^./, x => x.toUpperCase());
const num = x => x === '' || x == null || !Number.isFinite(Number(x)) ? '' : Number(x);
const opt = Object.fromEntries(data.options.map(x => [x.product_id, x]));
const comp = Object.fromEntries(data.components.map(x => [x.component_id, x]));
const names = ids => ids.map(id => comp[id] ? `${comp[id].name} [${id}]` : id).join('\n');
const idType = x => x.unbound_size_option ? 'Documented Long size option; image and geometry parent unbound' : x.option_family_id ? 'Owner-kept Wall Circle visual; native pattern alias unresolved' : x.owner_name_keep_recorded === false ? 'Source-supported individual component' : 'Owner-kept component / option';
const lineCount = (text, width) => String(text ?? '').split('\n').reduce((n, line) => n + Math.max(1, Math.ceil(line.length / Math.max(10, width * .85))), 0);
const basisParts = (text, width) => {
  if (lineCount(text, width) <= 28) return [text, ''];
  let first = '';
  for (const part of String(text).match(/[^\n]*(?:\n|$)/g).filter(Boolean)) {
    if (lineCount(first + part, width) > 28) break;
    first += part;
  }
  if (!first) throw new Error('Long unbroken basis requires a different layout');
  return [first, text.slice(first.length)];
};

function add(name, title, note, headers, rows, widths) {
  const sheet = sheets[name], last = 9 + rows.length;
  sheet.showGridLines = false;
  sheet.tabColor = ['Master Catalogue', 'Specifications', 'Components'].includes(name) ? green : '#8A9B8D';
  sheet.getRangeByIndexes(0, 0, last, headers.length).format.font = { name: 'Arial', size: 10, color: ink };
  sheet.getRangeByIndexes(0, 0, last, headers.length).format.verticalAlignment = 'center';
  sheet.getRange('A2:F2').merge();
  sheet.getRange('A2').values = [[title]];
  sheet.getRange('A2:F2').format = { font: { name: 'Arial', size: 16, bold: true, color: green }, rowHeight: 32 };
  sheet.getRange('A3:H3').merge();
  sheet.getRange('A3').values = [[note]];
  sheet.getRange('A3:H3').format = { font: { name: 'Arial', size: 10, color: muted }, wrapText: true, rowHeight: 40 };
  sheet.getRangeByIndexes(8, 0, 1, headers.length).values = [headers];
  if (rows.length) sheet.getRangeByIndexes(9, 0, rows.length, headers.length).values = rows.map(row => row.map(val));
  const table = sheet.tables.add(`A9:${col(headers.length - 1)}${last}`, true, 'Master_' + name.replaceAll(' ', '_'));
  table.style = 'TableStyleLight1'; table.showFilterButton = true;
  sheet.getRangeByIndexes(8, 0, 1, headers.length).format = { fill: green, font: { name: 'Arial', size: 10, bold: true, color: '#FFFFFF' }, horizontalAlignment: 'center', wrapText: true, rowHeight: 38 };
  widths.forEach((width, j) => sheet.getRangeByIndexes(0, j, last, 1).format.columnWidth = width);
  if (rows.length) sheet.getRangeByIndexes(9, 0, rows.length, headers.length).format.wrapText = true;
  rows.forEach((row, i) => {
    const lines = Math.max(...row.map((x, j) => lineCount(val(x), widths[j])));
    const height = Math.max(40, lines * 13 + 10);
    if (height > 409) overflow.push({ sheet: name, row: i + 10, estimated_height: height });
    sheet.getRangeByIndexes(i + 9, 0, 1, headers.length).format.rowHeight = Math.min(409, height);
    row.forEach((x, j) => {
      if (x && typeof x === 'object' && 'url' in x) {
        const cell = `${col(j)}${i + 10}`;
        links.push({ sheet: name, cell, target: x.url, label: x.label });
        sheet.getRange(cell).format.font = { name: 'Arial', size: 10, color: '#245F9E', underline: 'single' };
      }
    });
  });
  sheet.freezePanes.freezeRows(9); sheet.freezePanes.freezeColumns(2);
  expected[name] = { first: 10, last, headers, rows: rows.map(row => row.map(val)), widths };
  return sheet;
}

const detailStart = {}, detailRows = [];
for (const x of data.options) {
  detailStart[x.product_id] = 10 + detailRows.length;
  for (const field of fields) {
    const f = x.master_fields[field];
    const [basis, continuation] = basisParts(f.basis, 136);
    detailRows.push([x.product_id, x.name, field, f.display, f.state, basis, f.source_scopes.join('\n'), f.prior_display,
      f.working_recorded, link(x.image_url, x.source_component_id === 'BC-CR-RING' ? 'Right panel in pair' : 'Image'), link(x.folder_url, 'Folder'),
      x.file_id || 'Unbound', x.folder_id || 'Unbound', f.proposal_ids.join('\n'), continuation, x.product_id + '::' + field, 1]);
  }
}
const mainRows = data.options.map(x => [x.product_id, x.name, x.family,
  x.canonical_component_id || (x.option_family_id ? 'BC-WALL-CIRCLE — option family' : 'Long size option — geometry parent unbound'),
  ...fields.map(f => x.master_fields[f].display), 6, 'Six working fields recorded', idType(x),
  link(x.image_url, x.source_component_id === 'BC-CR-RING' ? 'Right panel in pair' : 'Image'), link(x.folder_url, 'Folder'),
  link(`#'Specifications'!D${detailStart[x.product_id]}`, 'Six field details'), x.file_id || 'Unbound', x.folder_id || 'Unbound',
  (x.orientation_options ?? []).join(' / '), link(x.context_image_url, 'Context image'), link(x.context_folder_url, 'Context folder'),
  x.readiness_note || 'Accepted working descriptions retain source estimates and conflicts. Actual measurements, hardware and physical stock retain their own evidence status.',
  x.related_platform_offer_refs.join('\n'), x.platform_scope_note, x.source_scopes.join('\n')]);
add('Master Catalogue', 'Boldstone sculpture master catalogue',
  'One record per individual finish, size or build option. Specification values read from Specifications, where current descriptions and qualifications are maintained. Estimates and source conflicts remain labelled.',
  ['Option ID', 'Individual sculpture / option', 'Family / series', 'Component / option-family ID', ...fields, 'Working fields recorded', 'Working specification status',
    'Identity scope', 'Example image', 'Containing folder', 'Specification detail', 'Dropbox file ID', 'Dropbox folder ID', 'Orientation choices', 'Context image', 'Context folder', 'Remaining evidence limits', 'Related platform source IDs', 'Platform mapping scope', 'Original review scopes'],
  mainRows, [25, 58, 32, 42, 72, 67, 72, 88, 72, 76, 16, 35, 70, 24, 19, 24, 40, 40, 32, 22, 23, 118, 35, 94, 61]);
add('Specifications', 'Current working specification detail',
  'Six current field groups per option. Current acceptance is separate from the original source states. Earlier values, source qualifications and unresolved physical details remain visible.',
  ['Option ID', 'Individual sculpture / option', 'Specification', 'Current working description', 'Current review state', 'Basis and qualifications', 'Source scopes', 'Earlier working display', 'Working detail accepted', 'Example / context', 'Containing folder', 'Dropbox file ID', 'Dropbox folder ID', 'Proposal IDs', 'Basis continued', 'Field key', 'Working field usable'],
  detailRows, [25, 58, 26, 110, 83, 136, 61, 100, 18, 24, 19, 40, 40, 69, 136, 76, 27]);

add('Components', 'Individual component identities',
  '111 identified catalogue members. Finish, size and build options are counted on Master Catalogue. Wall Circle’s seven visual entries and the unbound Long size option are kept outside this distinct-identity total.',
  ['Component ID', 'Component name', 'Family / series', 'Sale options', 'Identity and option scope', 'Example', 'Containing folder', 'Dropbox file ID', 'Dropbox folder ID', 'Original component IDs', 'Retained names'],
  data.components.map(x => [x.component_id, x.name, x.family, x.option_count, x.scope_note,
    link(x.image_url, x.component_id === 'BC-CR-RING' ? 'Right panel' : 'Image'), link(x.folder_url, 'Folder'),
    x.file_id, x.folder_id, x.source_component_ids.join('\n'), x.retained_names.join('\n')]),
  [28, 54, 33, 15, 81, 18, 19, 40, 40, 38, 89]);

const setRows = data.source_sets.map(x => {
  const o = x.source_offer, p = x.current_primary_reference ?? {};
  return [x.offer_ref, o.title, 'Source set / proposed multi-component offer', names(unique(x.members.flatMap(m => m.canonical_component_targets))),
    num(o.native_parts), x.members.length, x.relationship_status + '. Exact current finish, size and specimen mapping retains its source limits.',
    link(o.source_url, 'Platform source'), link(p.image_url, 'Source reference'), link(p.folder_url, 'Folder'), p.file_id || o.image_file_id, p.folder_id || o.image_folder_id,
    x.members.map(m => `${m.bom_id}: ${m.source_component_id}; position ${m.position}; quantity ${m.quantity}`).join('\n')];
});
const contextRows = data.arrangement_context_references.map(x => [x.reference_id, x.name,
  x.confirmed_member_option_ids.length ? 'Confirmed arrangement of existing components' : 'Group / project context only',
  x.confirmed_member_option_ids.map(id => `${opt[id].name} [${id}]`).join('\n') || 'Individual components not established; context retained', '', '',
  x.confirmed_member_option_ids.length ? 'Existing components reused; no additional individual count' : x.component_identification,
  '', link(x.image_url, 'Context image'), link(x.folder_url, 'Folder'), x.file_id || unique((x.images ?? []).map(i => i.file_id)).join('\n'),
  x.folder_id || unique((x.images ?? []).map(i => i.folder_id)).join('\n'), x.source_reference_ids.join('\n')]);
add('Sets and Context', 'Sets, arrangements and group photographs',
  '28 source offers with multiple native or proposed components and 27 arrangement/context references. These overlapping source layers create no additional individual sculpture records.',
  ['Reference ID', 'Set / arrangement / context', 'Record type', 'Identified component targets', 'Native piece count', 'Source BOM positions', 'Relationship and count treatment', 'Platform page', 'Context image', 'Containing folder', 'Dropbox file IDs', 'Dropbox folder IDs', 'Original members / reference IDs'],
  [...setRows, ...contextRows], [39, 65, 47, 92, 17, 19, 107, 20, 24, 19, 45, 45, 100]);
add('Aliases', 'Retained names and source aliases',
  'Aliases and orientation relationships retain earlier names and source IDs without adding individual sculptures. Historical maker codes are not treated as a verified physical-mould inventory.',
  ['Alias / earlier name', 'Original key', 'Canonical targets', 'Relationship', 'Reason and limits', 'Image', 'Folder', 'Dropbox file ID', 'Dropbox folder ID'],
  data.aliases.map(x => [x.source_name || x.source, x.source, x.targets.join('\n'), human(x.relationship), x.reason, link(x.image_url), link(x.folder_url, 'Folder'), x.file_id, x.folder_id]),
  [58, 59, 61, 52, 126, 20, 19, 40, 40]);
add('References and Gaps', 'Reference decisions and remaining evidence gaps',
  'Nine extra finish sources are closed as detail, scene or group context. Ring and Long have six working fields recorded; their photographic and actual-specification gaps remain separate.',
  ['Case ID', 'Sculpture / source appearance', 'Case type', 'Evidence and remaining limits', 'Current count treatment', 'Example / context', 'Containing folder', 'Original scopes / configurations'],
  data.exceptions.map(x => [x.candidate_id, x.name, x.exception_type, x.required_information, x.count_treatment,
    link(x.image_url, x.candidate_id === 'GAP-BC-CR-RING' ? 'Right panel in pair' : 'Source reference'), link(x.folder_url, 'Folder'), (x.source_scopes ?? x.source_configuration_ids ?? []).join('\n')]),
  [39, 69, 55, 135, 117, 25, 19, 75]);

const coverage = Object.fromEntries(data.source_platform_offer_coverage.map(x => [x.offer_ref, x]));
const platformRows = data.source_offer_edges.map(x => {
  const o = x.source_offer, c = coverage[x.offer_ref], p = x.current_primary_reference ?? {};
  const overlay = data.master_platform_association_overlays?.[x.offer_ref];
  return ['Platform offer', x.offer_ref, o.title, o.sku, o.sq_id, o.sh_handle, num(o.native_price), o.native_currency,
    o.source_each_cm, o.source_overall_cm, o.source_set_weight_kg, [o.raw_length, o.raw_width, o.raw_height, o.raw_weight].map(v => v ?? '').join(' / '), o.raw_units,
    o.stock, 'Physical stock quantity unverified', unique(x.members.flatMap(m => m.canonical_component_targets)).join('\n'),
    (overlay?.related_option_ids ?? c.related_product_ids ?? []).join('\n'), overlay?.mapping_state ?? human(c.canonical_graph_coverage_state),
    overlay ? overlay.scope_note + ' Original source caution: ' + (o.cautions || c.source_cautions || 'None recorded') : o.cautions || c.scope_note || c.source_cautions,
    link(o.source_url, 'Platform source'), link(p.image_url, 'Source reference'), link(p.folder_url, 'Folder'), p.file_id || o.image_file_id, p.folder_id || o.image_folder_id, o.native_description];
});
for (const o of data.wall_circle_native_options) {
  platformRows.push(['Wall Circle native option', o.variant_id,
    [o.attributes.Pattern, o.attributes['Diameter Size'], o.attributes.Lighting].join('\n'), o.sku, '68dc0a35a7ac865209b39248', '', num(o.price.value), o.price.currency,
    '', '', '', [o.raw_dimensions_and_weight.len, o.raw_dimensions_and_weight.width, o.raw_dimensions_and_weight.height, o.raw_dimensions_and_weight.weight].join(' / '), o.raw_units,
    o.stock_setting.unlimited ? 'Unlimited source sale policy' : 'Source stock quantity: ' + o.stock_setting.qty_in_stock,
    'Physical stock quantity unverified', 'BC-WALL-CIRCLE — option family', '', 'Native option preserved; seven visual-name aliases unresolved',
    '18 patterns × 4 diameters × 2 lighting choices. Do not add these overlapping source rows to the seven approved visual entries.',
    link('https://boldstonesculpture.com/buy/p/wall-circle', 'Platform source'), link(o.image_url, 'Native source image'), '', o.image_id, '', '']);
}
add('Platform Sources', 'Squarespace, Shopify and native option sources',
  '81 preserved platform offer records plus 144 overlapping Wall Circle combinations. Shared SKU/platform identifiers remain intact. Raw units and set totals are retained; no new exact option match or live platform update is asserted.',
  ['Source layer', 'Offer / variant ID', 'Source product / option', 'Source SKU', 'Squarespace product ID', 'Shopify handle', 'Native source price', 'Native currency', 'Source each dimensions (cm)', 'Source set dimensions (cm)', 'Source set weight (kg)', 'Raw length / width / depth / weight', 'Raw unit qualification', 'Source sale / stock policy', 'Physical stock status', 'Related component IDs', 'Related current option IDs', 'Mapping state', 'Source cautions', 'Source page', 'Source image', 'Source folder', 'Source image ID', 'Dropbox folder ID', 'Native source description'],
  platformRows, [32, 43, 81, 25, 31, 47, 18, 35, 43, 43, 32, 48, 77, 43, 43, 61, 59, 79, 114, 23, 24, 21, 42, 40, 144]);
sheets['Platform Sources'].getRange(`G10:G${expected['Platform Sources'].last}`).setNumberFormat('#,##0.00');

const reviewRows = data.source_review_reconciliation.map(x => {
  const s = data.original_review_specification_assertions.find(s => s[0] + '|' + s[1] === x.source_scope);
  return ['Review row', x.source_scope, x.source_title, human(x.disposition), names(x.component_targets), x.targets.join('\n'), x.reason,
    link(x.image_url), link(x.folder_url, 'Folder'), s?.[9] ?? '', s?.[10] ?? '', x.individual_count_increment];
});
const modelRows = data.source_component_dispositions.map(x => ['Source component ID', x.source_component_id, x.source_name, x.treatment, names(x.component_targets), x.option_family_target || '',
  'Source identifier crosswalk; not added to the overlapping review-row count.', '', '', x.source_file_ids.join('\n'), x.source_folder_ids.join('\n'), 0]);
add('Source Mapping', 'Review rows mapped to individual identities',
  'All 278 review rows and 125 source component IDs retain their dispositions. Review increments total 177; seven supplemental Wall Circle entries complete the 184 option records. Current links resolve by stable ID.',
  ['Source layer', 'Source key', 'Earlier / source title', 'Disposition', 'Component targets', 'Option / family / reference targets', 'Reason', 'Current source image', 'Current source folder', 'Historical file IDs', 'Historical folder IDs', 'Review option increment'],
  [...reviewRows, ...modelRows], [28, 61, 68, 65, 93, 70, 129, 22, 22, 58, 58, 21]);
add('Source Specifications', 'Original review specification records',
  'The 1,668 original field records remain unchanged. Their recorded source states and historical URLs are evidence history. Current image/folder links resolve by stable ID; the current six-field descriptions are on Specifications.',
  ['Source component ID', 'Source scope', 'Source sculpture / option', 'Field', 'Original recorded description', 'Original review state', 'Original basis', 'Current image', 'Current folder', 'Original Dropbox file ID', 'Original Dropbox folder ID', 'Original proposal ID', 'Historical image URL (recorded)', 'Historical folder URL (recorded)', 'Original notes', 'Original basis continued'],
  data.original_review_specification_assertions.map((s, i) => {
    const p = data.original_specification_current_references[i];
    const [basis, continuation] = basisParts(s[6], 137);
    return [s[0], s[1], s[2], s[3], s[4], s[5], basis, link(p.image_url), link(p.folder_url, 'Folder'), s[9], s[10], s[11], s[7], s[8], s[12], continuation];
  }), [29, 43, 66, 27, 113, 101, 137, 22, 20, 40, 40, 68, 125, 116, 98, 137]);

const master = sheets['Master Catalogue'], last = expected['Master Catalogue'].last, detailLast = expected.Specifications.last;
const usableFormulas = detailRows.map((_, i) => {
  const row = i + 10, formula = `=IF(AND(I${row}=1,COUNTBLANK(D${row})=0,COUNTIFS($P$10:$P$${detailLast},P${row})=1),1,0)`;
  formulas.push({ sheet: 'Specifications', cell: 'Q' + row, formula, expected: 1 });
  return [formula];
});
sheets.Specifications.getRange(`Q10:Q${detailLast}`).formulas = usableFormulas;
for (let i = 0; i < data.options.length; i++) {
  const row = i + 10;
  for (let j = 0; j < fields.length; j++) {
    const key = `$A${row}&"::${fields[j]}"`;
    const formula = `=IF(COUNTIFS('Specifications'!$P$10:$P$${detailLast},${key},'Specifications'!$Q$10:$Q$${detailLast},1)=1,INDEX('Specifications'!$D$10:$D$${detailLast},MATCH(${key},'Specifications'!$P$10:$P$${detailLast},0)),"Working detail missing, unaccepted or duplicated")`;
    const cell = col(j + 4) + row;
    master.getRange(cell).formulas = [[formula]];
    formulas.push({ sheet: 'Master Catalogue', cell, formula, expected: data.options[i].master_fields[fields[j]].display });
  }
  const formula = `=COUNTIFS('Specifications'!$A$10:$A$${detailLast},A${row},'Specifications'!$Q$10:$Q$${detailLast},1)`;
  master.getRange('K' + row).formulas = [[formula]];
  formulas.push({ sheet: 'Master Catalogue', cell: 'K' + row, formula, expected: 6 });
  const status = `=IF(K${row}=6,"Six working fields recorded","Working details incomplete")`;
  master.getRange('L' + row).formulas = [[status]];
  formulas.push({ sheet: 'Master Catalogue', cell: 'L' + row, formula: status, expected: 'Six working fields recorded' });
}
for (let i = 0; i < data.components.length; i++) {
  const row = i + 10, formula = `=COUNTIFS('Master Catalogue'!$D$10:$D$${last},A${row})`;
  sheets.Components.getRange('D' + row).formulas = [[formula]];
  formulas.push({ sheet: 'Components', cell: 'D' + row, formula, expected: data.components[i].option_count });
}
const summary = [
  ['A4', 'Individual sale options', 'B4', `=COUNTA(A10:A${last})`, 184],
  ['C4', 'Component identities', 'D4', `=COUNTA('Components'!A10:A${expected.Components.last})`, 111],
  ['E4', 'Six working fields recorded', 'F4', `=COUNTIFS(K10:K${last},6)`, 184],
  ['G4', 'Dropbox references', 'H4', `=COUNTIFS(Q10:Q${last},"<>Unbound")`, 183]
];
for (const [labelCell, label, valueCell, formula, number] of summary) {
  master.getRange(labelCell).values = [[label]];
  master.getRange(labelCell).format = { wrapText: true, rowHeight: 42, font: { name: 'Arial', size: 10, color: muted } };
  master.getRange(valueCell).formulas = [[formula]];
  master.getRange(valueCell).format = { horizontalAlignment: 'center', font: { name: 'Arial', size: 16, bold: true, color: green } };
  master.getRange(valueCell).setNumberFormat('#,##0');
  formulas.push({ sheet: 'Master Catalogue', cell: valueCell, formula, expected: number });
}
master.getRange('A6:H6').merge();
master.getRange('A6').values = [['184 sale options comprise 176 options on 111 identified components, seven Wall Circle visual entries and one documented Long size option with no exact current photograph. Sets, aliases and group context are separate.']];
master.getRange('A6:H6').format = { wrapText: true, rowHeight: 40, fill: '#EAF0EB', font: { name: 'Arial', size: 11, bold: true, color: green } };
master.getRange('A7:H7').merge();
master.getRange('A7').values = [['Working specifications include accepted estimates. Actual measurements, physical stock and unresolved photo/geometry relationships retain their recorded qualifications. The complete catalogue-wide unique-design total remains open.']];
master.getRange('A7:H7').format = { wrapText: true, rowHeight: 40, font: { name: 'Arial', size: 10, color: muted } };
master.getRange(`K10:K${last}`).setNumberFormat('0');
master.getRange(`K10:K${last}`).format.horizontalAlignment = 'center';
master.getRange(`K10:K${last}`).conditionalFormats.add('cellIs', { operator: 'notEqual', formula: 6, format: { fill: '#FFF3D6', font: { color: '#9C440D' } } });
sheets.Components.getRange(`D10:D${expected.Components.last}`).format.horizontalAlignment = 'center';
sheets['Sets and Context'].getRange(`E10:F${expected['Sets and Context'].last}`).format.horizontalAlignment = 'center';

// A temporary change checks that the recorded-field summaries follow their input.
const originalDescription = detailRows[0][3];
sheets.Specifications.getRange('D10').values = [['Temporary verification description']];
if (master.getRange('E10').values[0][0] !== 'Temporary verification description') throw new Error('Catalogue description did not follow the specification source');
sheets.Specifications.getRange('D10').values = [['']];
if (master.getRange('E10').values[0][0] !== 'Working detail missing, unaccepted or duplicated' || master.getRange('K10').values[0][0] !== 5) throw new Error('Missing specification was not exposed');
sheets.Specifications.getRange('D10').values = [[originalDescription]];
sheets.Specifications.getRange('I10').values = [[0]];
const changed = master.getRange('K10').values[0][0], changedSummary = master.getRange('F4').values[0][0];
if (changed !== 5 || changedSummary !== 183) throw new Error('Working-field count dependency did not update');
sheets.Specifications.getRange('I10').values = [[1]];
wb.recalculate();
await fs.writeFile(path.join(here, 'formula-dependency-check.json'), JSON.stringify({ status: 'PASS', specification_edit_updates_catalogue: true, blank_description_exposes_missing_field: true, temporary_flag: 0, component_field_count: changed, complete_option_count: changedSummary, restored_flag: 1, original_description_restored: true }, null, 2));
await fs.writeFile(path.join(here, 'workbook-inspection.ndjson'), (await wb.inspect({ kind: 'region', sheetId: 'Master Catalogue', range: 'A4:H7', maxChars: 3000, tableMaxRows: 4, tableMaxCols: 8 })).ndjson);
await fs.writeFile(path.join(here, 'formula-error-scan.ndjson'), (await wb.inspect({ kind: 'match', searchTerm: '#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options: { useRegex: true, maxResults: 30 }, summary: 'Formula error scan' })).ndjson);
await fs.writeFile(path.join(here, 'row-fit-check.json'), JSON.stringify({ status: overflow.length ? 'REQUIRES_REVIEW' : 'PASS', overflow }, null, 2));
if (overflow.length) throw new Error('Rows exceed Excel height; inspect row-fit-check.json');
await fs.mkdir(path.dirname(output), { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(wb); await xlsx.save(output);
await fs.writeFile(path.join(here, 'expected-workbook.json'), JSON.stringify({ sheets: expected, formulas, hyperlinks: links }, null, 2));
execFileSync('/Users/tprice/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python', [path.join(here, 'verify_master.py'), '--attach', '--book', output], { stdio: 'inherit' });
const saved = await SpreadsheetFile.importXlsx(await FileBlob.load(output));
const plan = [
  ['Master Catalogue', 'A2:F12'], ['Master Catalogue', 'G9:L12'], ['Master Catalogue', 'M9:R12'], ['Master Catalogue', 'S9:Y12'],
  ['Specifications', 'A9:F12'], ['Specifications', 'G9:Q12'],
  ['Components', 'A9:F12'], ['Components', 'G9:K12'],
  ['Sets and Context', 'A9:G12'], ['Sets and Context', 'H9:M12'],
  ['Aliases', 'A9:E12'], ['References and Gaps', 'A9:E12'],
  ['Platform Sources', 'A9:H12'], ['Platform Sources', 'I9:Q11'], ['Platform Sources', 'R9:Y11'],
  ['Source Mapping', 'A9:F12'], ['Source Mapping', 'G9:L12'],
  ['Source Specifications', 'A9:G11'], ['Source Specifications', 'H9:P11']
];
for (const id of ['BC-BONE-1|BASE', 'BC-FFL-1|BASE', 'BC-MCP-4|MCP4-VERDIGRIS-RUST', 'BC-WALL-CIRCLE|WC-06']) {
  const i = data.options.findIndex(x => x.canonical_key === id);
  if (i >= 0) plan.push(['Master Catalogue', `E${i + 10}:L${i + 10}`]);
}
const longestBasis = detailRows.map((row, i) => ({ row: i + 10, length: String(row[5]).length })).sort((a, b) => b.length - a.length)[0].row;
plan.push(['Specifications', `D${longestBasis}:H${longestBasis}`]);
plan.push(['Specifications', 'F237:F237'], ['Specifications', 'O237:O237'], ['Source Specifications', 'G909:G909'], ['Source Specifications', 'P909:P909']);
for (const ref of ['O001', 'O034']) {
  const i = data.source_offer_edges.findIndex(x => x.offer_ref === ref);
  plan.push(['Platform Sources', `P${i + 10}:S${i + 10}`]);
}
for (const key of ['BC-BONE-1|BASE', 'BC-WALL-CIRCLE|WC-06']) {
  const i = data.options.findIndex(x => x.canonical_key === key);
  plan.push(['Master Catalogue', `W${i + 10}:X${i + 10}`]);
}
await fs.mkdir(path.join(here, 'previews'), { recursive: true });
const previews = [];
for (let i = 0; i < plan.length; i++) {
  const [sheetName, range] = plan[i];
  if (previousExpected && JSON.stringify(previousExpected.sheets[sheetName]) === JSON.stringify(expected[sheetName]) &&
      JSON.stringify(previousExpected.formulas.filter(x => x.sheet === sheetName)) === JSON.stringify(formulas.filter(x => x.sheet === sheetName))) {
    const previous = previousPreviews.find(x => x.sheet === sheetName && x.range === range);
    if (previous) { previews.push({ ...previous, unchanged_view_reused: true }); continue; }
  }
  const blob = await saved.render({ sheetName, range, scale: 1, format: 'png' });
  const dest = path.join(here, 'previews', `${String(i + 1).padStart(2, '0')}-${sheetName.replaceAll(' ', '_')}.png`);
  await fs.writeFile(dest, new Uint8Array(await blob.arrayBuffer())); previews.push({ sheet: sheetName, range, path: dest });
}
await fs.writeFile(path.join(here, 'preview-manifest.json'), JSON.stringify(previews, null, 2));
const hash = async p => crypto.createHash('sha256').update(await fs.readFile(p)).digest('hex');
const receipt = { status: 'EXPORTED_PENDING_VISUAL_VERIFICATION', output, workbook_sha256: await hash(output), master_register_sha256: await hash(path.join(here, 'canonical-master-register.json')),
  sheet_data_rows: Object.fromEntries(Object.entries(expected).map(([k, v]) => [k, v.rows.length])), native_hyperlinks: links.length, saved_preview_ranges: previews.length };
await fs.writeFile(path.join(here, 'export-receipt.json'), JSON.stringify(receipt, null, 2)); console.log(JSON.stringify(receipt));
