import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const wb = Workbook.create();
if (process.argv.includes('--help-links')) {
  console.log(wb.help('range.hyperlink', {include:'index,examples,notes', maxChars:5000}).ndjson);
  process.exit(0);
}
const dir = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(await fs.readFile(path.join(dir, 'catalogue-snapshot.json'), 'utf8'));
const links = [];
const manifests = [];
const FOREST = '#263C32', SAGE = '#EBF0E9', INK = '#24332D', MUTED = '#637067';
const clean = v => typeof v === 'string' ? v.replaceAll('—', '-').replaceAll('–', '-') : v;
const text = v => v == null ? '' : typeof v === 'string' ? clean(v) : JSON.stringify(v);
const list = arr => (arr || []).map(text).join('; ');
const yn = b => b ? 'Yes' : 'No';
const literal = v => typeof v === 'string' && v.startsWith('=') ? "'" + v : v;
const col = n => { let s = ''; for (n++; n; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; };
const asOf = new Date(data.created_utc).toLocaleString('en-GB', {timeZone:'Europe/London', dateStyle:'medium', timeStyle:'short'});
const sheetNames = ['Wall Sculptures', 'Images', 'Specification Sources'];
for (const name of sheetNames) wb.worksheets.add(name);
const addLink = (sheet, row, column, url, label, internal = false) => {
  if (!url) return '';
  links.push({sheet, cell: `${col(column)}${row}`, url, label, internal});
  return label;
};
const firstImageRow = new Map();
data.images.forEach((r, i) => { if (r.product_id && !firstImageRow.has(r.product_id)) firstImageRow.set(r.product_id, i + 8); });
const imageById = new Map(data.images.map(r => [r.image.id, r.image]));
const fieldsOf = p => Object.fromEntries([...p.fields, ...p.listing_fields].map(f => [f.key, f.value]));
const priceNumber = value => {
  const s = text(value), hits = [...s.matchAll(/£\s*([\d,]+(?:\.\d{1,2})?)/g)];
  return hits.length === 1 && !/£\s*[\d,.]+\s*-\s*\d/.test(s) ? Number(hits[0][1].replaceAll(',', '')) : null;
};
function makeSheet(name, title, note, headers, rows, widths, frozenColumns = 3) {
  const s = wb.worksheets.getItem(name), end = rows.length + 7, last = col(headers.length - 1);
  s.showGridLines = false;
  s.tabColor = name === 'Wall Sculptures' ? FOREST : '#8B9B89';
  s.getRange(`A1:${last}${end}`).format = {font:{name:'Arial', size:10, color:INK}, verticalAlignment:'center'};
  s.getRange('A2').values = [[title]];
  s.getRange('A2').format.font = {name:'Arial', size:14, bold:true, color:FOREST};
  s.getRange('A2:L3').format.borders = {bottom:{style:'thin', color:'#9DAB9C'}};
  s.getRange('A2:L2').format.rowHeight = 26;
  s.getRange('A4').values = [[`App snapshot: ${asOf} UK time. Workbook edits do not update the app.`]];
  s.getRange('A5').values = [[note]];
  s.getRange('A4:L5').format.font = {name:'Arial', size:10, color:MUTED};
  s.getRange(`A7:${last}7`).values = [headers];
  s.getRange(`A8:${last}${end}`).values = rows.map(row => row.map(literal));
  const table = s.tables.add(`A7:${last}${end}`, true, name.replaceAll(' ', '') + 'Table');
  table.style = 'TableStyleLight9';
  table.showFilterButton = true;
  s.getRange(`A7:${last}7`).format = {fill:FOREST, font:{name:'Arial', size:10, bold:true, color:'#FFFFFF'},
    horizontalAlignment:'center', verticalAlignment:'center', wrapText:true, rowHeight:34,
    borders:{insideVertical:{style:'thin', color:'#FFFFFF'}}};
  s.getRange(`A8:${last}${end}`).format = {rowHeight:40, wrapText:true, verticalAlignment:'center'};
  for (let c = 0; c < widths.length; c++) s.getRange(`${col(c)}7:${col(c)}${end}`).format.columnWidth = widths[c];
  for (let i = 0; i < rows.length; i++) {
    const sizingValues = name === 'Wall Sculptures' ? rows[i].slice(0,11) : rows[i];
    const lines = Math.max(...sizingValues.map((v,c) => typeof v === 'string'
      ? v.split('\n').reduce((n,line) => n + Math.max(1, Math.ceil(line.length / (widths[c] * 0.88))), 0) : 1));
    const height = Math.max(40, Math.min(409, lines * 12 + 8));
    if (height > 40) s.getRange(`A${i+8}:${last}${i+8}`).format.rowHeight = height;
  }
  s.freezePanes.freezeRows(7);
  s.freezePanes.freezeColumns(frozenColumns);
  // Native two-axis panes and hyperlink relationships are added by the small
  // OOXML supplement because the documented artifact API has no hyperlink setter.
  manifests.push({name, headers, row_count:rows.length, rows, freeze_rows:7, freeze_columns:frozenColumns});
  console.log(JSON.stringify({sheet:name, rows:rows.length, columns:headers.length}));
  return s;
}

const mainHeaders = ['No.', 'Family', 'Sculpture', 'Dimensions / depth', 'Weight', 'Material / finish', 'Fixings',
  'Price (GBP)', 'Price wording', 'Availability', 'Lead time', 'Primary status', 'Primary photo', 'Listing photos',
  'In situ photos', 'In situ shortfall (target 2)', 'Associated images', 'Related candidates', 'All image rows',
  'First listing photo', 'In situ photo 1', 'In situ photo 2', 'Dropbox folder', 'Open in app (this Mac)',
  'Listing decision', 'Review progress', 'Product ID', 'Component ID', 'Sale unit', 'Description', 'Review notes'];
const mainRows = data.products.map((p, i) => {
  const row = i + 8, f = fieldsOf(p), photos = p.photos;
  const imageLink = (id, c, label) => addLink('Wall Sculptures', row, c, imageById.get(id)?.url, label);
  return [i + 1, text(f.Family || p.family), text(p.name), text(f['Dimensions / depth']), text(f.Weight),
    text(f['Material / finish']), text(f.Fixing), priceNumber(f.Price), text(f.Price), text(f.Availability), text(f['Lead time']),
    {set:'Set', missing:'Not set', needs_review:'Needs review'}[photos.primary_listing.status],
    imageLink(photos.primary_id, 12, 'Open primary'), photos.listing_ids.length, photos.in_situ_ids.length,
    Math.max(0, 2 - photos.in_situ_ids.length), p.associated_count, p.candidate_count,
    firstImageRow.has(p.id) ? addLink('Wall Sculptures', row, 18, `'Images'!A${firstImageRow.get(p.id)}`, 'View image rows', true) : '',
    imageLink(photos.listing_ids[0], 19, 'Open listing'), imageLink(photos.in_situ_ids[0], 20, 'Open in situ 1'),
    imageLink(photos.in_situ_ids[1], 21, 'Open in situ 2'), addLink('Wall Sculptures', row, 22, p.folder_url, 'Open folder'),
    addLink('Wall Sculptures', row, 23, p.app_url, 'Open component'), p.listing_decision, p.review_status,
    p.id, p.component_id || '', text(f['Sale unit']), text(f.Description), text(p.notes)];
});
const primarySet = data.products.filter(p => p.photos.primary_id).length;
const main = makeSheet('Wall Sculptures', 'BOLDSTONE | Wall sculpture catalogue',
  `${data.summary.products} components | ${data.summary.families} catalogue families | ${primarySet} primary photos set | ${data.summary.unique_images.toLocaleString('en-GB')} unique retained images`,
  mainHeaders, mainRows, [6,25,42,30,25,42,38,14,36,21,18,18,17,13,13,16,15,15,20,17,18,18,18,22,19,19,25,25,55,65,65]);
main.getRange(`AC8:AE${mainRows.length + 7}`).format.wrapText = false;
main.getRange(`H8:H${mainRows.length + 7}`).setNumberFormat('"£"#,##0.00');
for (const c of ['A','N','O','P','Q','R']) main.getRange(`${c}8:${c}${mainRows.length + 7}`).setNumberFormat('#,##0');
main.getRange(`L8:L${mainRows.length + 7}`).conditionalFormats.add('containsText', {text:'Not set', format:{fill:'#FFF0CF', font:{color:'#78551E'}}});
main.getRange(`L8:L${mainRows.length + 7}`).conditionalFormats.add('containsText', {text:'Needs review', format:{fill:'#FBE3DC', font:{color:'#843C30'}}});
main.getRange(`P8:P${mainRows.length + 7}`).conditionalFormats.add('cellIs', {operator:'greaterThan', formula:0, format:{fill:'#FFF0CF'}});

const imageHeaders = ['Family', 'Sculpture', 'Product ID', 'Association', 'File name', 'Image', 'Containing folder',
  'Primary listing', 'Listing', 'Advertising', 'Reference', 'In situ', 'Image types', 'Selected purposes', 'Review decision',
  'Listing order', 'Original width (px)', 'Original height (px)', 'Original bytes', 'Original MiB', 'Dimensions basis',
  'Shared tags', 'Collection', 'Rights', 'Alt text', 'Caption', 'Requested edit', 'Notes', 'Source', 'Stable image ID',
  'Dropbox path', 'Dropbox revision', 'Dropbox content hash', 'Association evidence', 'Excluded', 'Review warnings'];
const imageRows = data.images.map((r, i) => {
  const a = r.image, c = r.choice, m = r.metadata, o = a.original || {}, row = i + 8;
  const types = a.effective_types || m.types || a.types || [];
  const uses = a.selected_uses || (c.decision === 'reviewed' ? c.uses || [] : []);
  const dimensions = o.dimensions || [];
  const active = r.scope === 'Associated' && !a.excluded;
  return [text(r.product_family), text(r.product_name), r.product_id, r.scope, text(a.name),
    addLink('Images', row, 5, a.url, 'Open image'), addLink('Images', row, 6, a.folder_url, 'Open folder'),
    yn(active && a.primary_eligible), yn(active && uses.includes('listing')), yn(uses.includes('advertising')),
    yn(uses.includes('reference')), yn(types.includes('in_situ')), types.map(t => data.image_types[t] || t).join('; '),
    list(uses), c.decision || 'pending', Number.isFinite(c.order) ? c.order : null,
    dimensions[0] ?? null, dimensions[1] ?? null, o.bytes ?? null, null, text(o.dimension_basis), list(m.tags),
    text(m.collection), m.rights || 'unknown', text(c.alt), text(c.caption), text(c.edit_notes), list([c.notes, m.notes].filter(Boolean)),
    a.source, a.id, a.provenance?.path || '', a.provenance?.revision || '', o.dropbox_content_hash || '',
    list(a.association?.qualifications), yn(c.decision === 'exclude'), list(a.withheld_reasons)];
});
const images = makeSheet('Images', 'BOLDSTONE | Image links and current uses',
  'Filter by sculpture and association. Related candidates and library-only images are not approved listing choices. One file can appear against several sculptures.',
  imageHeaders, imageRows, [25,42,25,24,60,17,18,15,13,15,13,13,37,25,20,13,16,16,18,15,58,35,25,18,50,50,50,60,16,35,85,29,70,65,14,50]);
const sizeFormulas = imageRows.map((r,i) => [r[18] == null ? '' : `=S${i+8}/1048576`]);
images.getRange(`T8:T${imageRows.length + 7}`).formulas = sizeFormulas;
images.getRange(`P8:S${imageRows.length + 7}`).setNumberFormat('#,##0');
images.getRange(`T8:T${imageRows.length + 7}`).setNumberFormat('0.00');
images.getRange(`H8:L${imageRows.length + 7}`).conditionalFormats.add('containsText', {text:'Yes', format:{fill:SAGE, font:{bold:true, color:FOREST}}});
images.getRange(`AI8:AI${imageRows.length + 7}`).conditionalFormats.add('containsText', {text:'Yes', format:{fill:'#FBE3DC', font:{color:'#843C30'}}});

const sourceHeaders = ['Family', 'Sculpture', 'Product ID', 'Section', 'Specification field', 'Current app value',
  'Review decision', 'Saved qualification', 'Original source value', 'Original qualification', 'Source basis',
  'Evidence', 'Review notes', 'Updated (UTC)'];
const sourceRows = data.products.flatMap(p => [...p.fields, ...p.listing_fields].map(f => [text(p.family), text(p.name), p.id,
  f.section, f.label, text(f.value), f.decision, f.certainty, text(f.source_value), text(f.qualification), text(f.basis),
  text(f.evidence), text(f.notes), f.updated_at ? new Date(f.updated_at) : null]));
const sources = makeSheet('Specification Sources', 'BOLDSTONE | Specification sources',
  'Original source qualifications are retained here. Current app values are shown on Wall Sculptures; blank descriptions remain blank.',
  sourceHeaders, sourceRows, [25,42,25,23,26,65,20,24,80,60,95,65,75,24]);
sources.getRange(`N8:N${sourceRows.length + 7}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');
for (const link of links) {
  wb.worksheets.getItem(link.sheet).getRange(link.cell).format.font = {name:'Arial', size:10, color:'#28634B', underline:'single'};
}

wb.recalculate();
const errors = await wb.inspect({kind:'match', searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options:{useRegex:true, maxResults:100}, maxChars:3000});
await fs.writeFile(path.join(dir, 'formula-scan.jsonl'), errors.ndjson);
const inspection = await wb.inspect({kind:'table', range:'Wall Sculptures!A7:P12', include:'values,formulas', tableMaxRows:6, tableMaxCols:16, maxChars:5500});
await fs.writeFile(path.join(dir, 'workbook-inspection.jsonl'), inspection.ndjson);
for (const [sheetName, range, file] of [['Wall Sculptures','A1:J13','catalogue-preview.png'],['Images','A1:N12','images-preview.png'],['Specification Sources','A1:H11','sources-preview.png']]) {
  const preview = await wb.render({sheetName, range, scale:1.3, format:'png'});
  await fs.writeFile(path.join(dir, file), new Uint8Array(await preview.arrayBuffer()));
}
const xlsx = path.join(dir, 'catalogue_wall_sculptures.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(xlsx);
await fs.writeFile(path.join(dir, 'hyperlinks.json'), JSON.stringify(links));
await fs.writeFile(path.join(dir, 'expected-workbook.json'), JSON.stringify({created_utc:data.created_utc, summary:data.summary, sheets:manifests}));
execFileSync('/usr/bin/python3', [path.join(dir,'native_links.py'), xlsx], {stdio:'inherit'});
console.log(JSON.stringify({output:xlsx, hyperlinks:links.length, primary_photos:primarySet}));
