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
const sheetNames = ['Wall Sculptures', 'Images', 'Specification Sources', 'Manufacturing Costs', 'Cost Rates', 'Cost Finishes'];
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
  'Listing decision', 'Review progress', 'Product ID', 'Component ID', 'Sale unit', 'Description', 'Review notes', 'Production material', 'Casting cost', 'Surface cost', 'Fixing cost', 'Overheads', 'Other parts', 'Labour cost', 'Manufacturing total', 'Cost detail'];
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
    p.id, p.component_id || '', text(f['Sale unit']), text(f.Description), text(p.notes), p.costing.material_label, p.costing.material_cost, p.costing.finish_cost, p.costing.fixing_cost, p.costing.overhead_cost, p.costing.other_cost, p.costing.labour_cost, p.costing.total_cost, addLink('Wall Sculptures',row,39,`'Manufacturing Costs'!A${row}`,'View calculation',true)];
});
const primarySet = data.products.filter(p => p.photos.primary_id).length;
const main = makeSheet('Wall Sculptures', 'BOLDSTONE | Wall sculpture catalogue',
  `${data.summary.products} components | ${data.summary.families} catalogue families | ${primarySet} primary photos set | ${data.summary.unique_images.toLocaleString('en-GB')} unique retained images`,
  mainHeaders, mainRows, [6,25,42,30,25,42,38,14,36,21,18,18,17,13,13,16,15,15,20,17,18,18,18,22,19,19,25,25,55,65,65,32,17,17,17,17,17,17,20,23]);
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
  'Original source qualifications are retained here. Current app values are shown on Wall Sculptures; listing descriptions are completed from the recorded specification values.',
  sourceHeaders, sourceRows, [25,42,25,23,26,65,20,24,80,60,95,65,75,24]);
sources.getRange(`N8:N${sourceRows.length + 7}`).setNumberFormat('yyyy-mm-dd hh:mm:ss');

// The same model as the app, expressed as editable inputs and Excel formulas.
const cfg=data.cost_settings,rateRefs=new Map();
const globals=[['reference_width_cm','Reference width','cm'],['reference_height_cm','Reference height','cm'],['reference_depth_cm','Reference depth','cm'],['labour_hourly','Labour hourly rate','GBP/hour'],['casting_minutes','Casting time','minutes/reference'],['fixing_minutes','Time per fixing','minutes/fixing'],['fixing_unit','Fixing cost','GBP/fixing'],['overhead_reference','Overhead cost','GBP/reference']];
const rateRows=globals.map(([key,label,unit])=>[key,'Global',label,cfg[key],null,unit,'Editable production assumption','']);
for(const group of ['materials','finishes'])for(const [key,v]of Object.entries(cfg[group]))rateRows.push([key,group,v.label,v.rate,v.minutes,group==='materials'?'GBP/reference casting':'GBP/reference face',text(v.basis),v.source]);
rateRows.forEach((r,i)=>{rateRefs.set(r[0],i+8);if(r[7])r[7]=addLink('Cost Rates',i+8,7,r[7],'Supplier / basis');});
const ratesSheet=makeSheet('Cost Rates','BOLDSTONE | Editable manufacturing rates',text(cfg.notes),['Key','Group','Name','Rate / value','Additional minutes','Units','Calculation basis','Source'],rateRows,[25,17,42,18,19,28,115,26]);
ratesSheet.getRange(`D8:D${rateRows.length+7}`).format.font.color='#184DB3';
ratesSheet.getRange(`E${8+globals.length}:E${rateRows.length+7}`).format.font.color='#184DB3';
ratesSheet.getRange(`D8:E${rateRows.length+7}`).setNumberFormat('0.00');
const rr=(key,col='D')=>`'Cost Rates'!$${col}$${rateRefs.get(key)}`;
const matStart=8+globals.length, matEnd=matStart+Object.keys(cfg.materials).length-1;
const finStart=matEnd+1, finEnd=finStart+Object.keys(cfg.finishes).length-1;
const lookup=(keyCell,group,column)=>`VLOOKUP(${keyCell},'Cost Rates'!$A$${group==='materials'?matStart:finStart}:$E$${group==='materials'?matEnd:finEnd},${column},FALSE)`;
// Normalize sub-nanopound floating noise before half-up penny rounding.
const penny=expression=>`ROUND(ROUND(${expression},9)+0.0000000001,2)`;
const finishRows=[],costRows=[];
for(const p of data.products){
 const c=p.costing,i=c.inputs,r=costRows.length+8,f=fieldsOf(p);
 for(const item of i.finishes){const rate=cfg.finishes[item.id];finishRows.push([p.id,p.name,item.id,rate.label,item.coverage,c.face_scale,rate.rate,c.finish_lines.find(x=>x.id===item.id).cost,rate.minutes,rate.minutes*item.coverage*c.face_scale]);}
 costRows.push([p.family,p.name,p.id,i.width_cm,i.height_cm,i.depth_cm,i.shape_factor,i.casting_factor,i.material,c.material_label,i.fixing_count,i.labour_hours_override,i.other_cost,c.face_scale,c.casting_scale,cfg.materials[i.material].rate,c.material_cost,c.finish_cost,c.fixing_cost,c.overhead_cost,c.labour_hours,c.labour_cost,c.subtotal_before_labour,c.total_cost,c.alternatives.gfrc,c.alternatives.jesmonite,c.alternatives.moulding_paste,c.alternatives.gypsum,text(f['Material / finish']),text(i.notes)]);
}
const costHeaders=['Family','Sculpture','Product ID','Face dimension 1 (cm)','Face dimension 2 (cm)','Depth (cm)','Footprint factor','Casting factor','Material key','Production material','Fixing quantity','Hours override','Other parts (£)','Face scale','Casting scale','Material rate (£)','Casting (£)','Surface (£)','Fixings (£)','Overheads (£)','Labour hours','Labour (£)','Before labour (£)','Manufacturing total (£)','GFRC alternative (£)','Jesmonite alternative (£)','Paste alternative (£)','Gypsum alternative (£)','Recorded sculpture material','Calculation notes'];
const costSheet=makeSheet('Manufacturing Costs','BOLDSTONE | Manufacturing cost per sculpture','Blue cells are inputs. Change quantities or Cost Rates to recalculate. Selling prices stay separate. This is a production model, not a measured bill of materials.',costHeaders,costRows,[25,42,25,18,18,16,19,18,23,35,18,18,18,16,18,19,19,19,19,19,18,19,20,25,23,24,24,24,65,115]);
const finishSheet=makeSheet('Cost Finishes','BOLDSTONE | Surface coverage and costs','Coverage 1 means the whole face. Mixed finishes default to shared coverage; overlapping layers can exceed 1. Verdigris includes its base treatment.', ['Product ID','Sculpture','Finish key','Surface effect','Coverage fraction','Face scale','Rate / reference (£)','Surface cost (£)','Minutes / reference','Surface minutes'],finishRows,[25,42,25,38,22,18,24,23,23,23]);
const lastFinish=finishRows.length+7;
finishRows.forEach((row,index)=>{const r=index+8,cr=data.products.findIndex(p=>p.id===row[0])+8;
 finishSheet.getRange(`D${r}`).formulas=[[`=${lookup('C'+r,'finishes',3)}`]];
 finishSheet.getRange(`F${r}:J${r}`).formulas=[[`='Manufacturing Costs'!N${cr}`,`=${lookup('C'+r,'finishes',4)}`,`=${penny(`E${r}*F${r}*G${r}`)}`,`=${lookup('C'+r,'finishes',5)}`,`=E${r}*F${r}*I${r}`]];
});
const sums=(r,col)=>`SUMIF('Cost Finishes'!$A$8:$A$${lastFinish},C${r},'Cost Finishes'!$${col}$8:$${col}$${lastFinish})`;
costRows.forEach((row,index)=>{const r=index+8,p=data.products[index],i=p.costing.inputs;
 const hours=key=>`IF(ISBLANK(L${r}),((${rr('casting_minutes')}+${key?rr(key,'E'):lookup('I'+r,'materials',5)})*MAX(0.5,SQRT(O${r}))+${sums(r,'J')}+K${r}*${rr('fixing_minutes')})/60,L${r})`;
 costSheet.getRange(`J${r}`).formulas=[[`=${lookup('I'+r,'materials',3)}`]];
 costSheet.getRange(`N${r}:AB${r}`).formulas=[[
  `=D${r}*E${r}*G${r}/(${rr('reference_width_cm')}*${rr('reference_height_cm')})`,
  `=N${r}*F${r}/${rr('reference_depth_cm')}*H${r}`,
  `=${lookup('I'+r,'materials',4)}`,`=${penny(`O${r}*P${r}`)}`,`=${sums(r,'H')}`,`=${penny(`K${r}*${rr('fixing_unit')}`)}`,
  `=${penny(`${rr('overhead_reference')}*MAX(1,SQRT(N${r}))`)}`,`=${hours(null)}`,`=${penny(`U${r}*${rr('labour_hourly')}`)}`,
  `=${penny(`SUM(Q${r}:T${r})+M${r}`)}`,`=${penny(`W${r}+V${r}`)}`,
  ...['gfrc','jesmonite','moulding_paste','gypsum'].map(key=>`=${penny(`X${r}-Q${r}-V${r}+${penny(`O${r}*${rr(key)}`)}+${penny(`(${hours(key)})*${rr('labour_hourly')}`)}`)}`)
 ]];
 main.getRange(`AF${r}`).formulas=[[`='Manufacturing Costs'!J${r}`]];
 main.getRange(`AG${r}:AM${r}`).formulas=[['Q','R','S','T','M','V','X'].map(col=>`='Manufacturing Costs'!${col}${r}`)];
});
costSheet.getRange(`D8:M${costRows.length+7}`).format.font.color='#184DB3';
costSheet.getRange(`J8:J${costRows.length+7}`).format.font.color=INK;
finishSheet.getRange(`C8:C${finishRows.length+7}`).format.font.color='#184DB3';
finishSheet.getRange(`E8:E${finishRows.length+7}`).format.font.color='#184DB3';
costSheet.getRange(`N8:AB${costRows.length+7}`).setNumberFormat('0.00');
finishSheet.getRange(`E8:J${finishRows.length+7}`).setNumberFormat('0.00');
main.getRange(`AG8:AM${mainRows.length+7}`).setNumberFormat('"£"#,##0.00');
costSheet.getRange(`X8:X${costRows.length+7}`).format.fill=SAGE;
costSheet.getRange(`I8:I${costRows.length+7}`).dataValidation={allowBlank:false,list:{inCellDropDown:true,source:Object.keys(cfg.materials)}};
finishSheet.getRange(`C8:C${finishRows.length+7}`).dataValidation={allowBlank:false,list:{inCellDropDown:true,source:Object.keys(cfg.finishes)}};
const decimalRule=(range,min,max,allowBlank=false)=>range.dataValidation={ignoreBlanks:allowBlank,rule:{type:'decimal',operator:'between',formula1:min,formula2:max},errorAlert:{style:'stop',title:'Invalid value',message:`Enter a number from ${min} to ${max}.`}};
decimalRule(costSheet.getRange(`D8:F${costRows.length+7}`),0.01,10000);
decimalRule(costSheet.getRange(`G8:H${costRows.length+7}`),0.000001,100);
decimalRule(costSheet.getRange(`L8:L${costRows.length+7}`),0,10000,true);
decimalRule(costSheet.getRange(`M8:M${costRows.length+7}`),0,1000000);
decimalRule(finishSheet.getRange(`E8:E${finishRows.length+7}`),0,5);
costSheet.getRange(`K8:K${costRows.length+7}`).dataValidation={ignoreBlanks:false,rule:{type:'whole',operator:'between',formula1:0,formula2:1000}};
decimalRule(ratesSheet.getRange(`D${matStart}:E${finEnd}`),0,1000000);
decimalRule(ratesSheet.getRange('D8:D10'),0.01,10000);
decimalRule(ratesSheet.getRange('D11:D15'),0,1000000);

for (const link of links) {
  wb.worksheets.getItem(link.sheet).getRange(link.cell).format.font = {name:'Arial', size:10, color:'#28634B', underline:'single'};
}

wb.recalculate();
const editChecks=[];
const cellValue=(s,address)=>s.getRange(address).values[0][0];
const equal=(a,b)=>{if(Math.abs(a-b)>0.005)throw new Error(`Recalculation mismatch: ${a} / ${b}`);};
const originalTotal=cellValue(costSheet,'X8'), originalMaterial=costRows[0][8], originalFinish=finishRows[0][2];
const labourCell='D'+rateRefs.get('labour_hourly');
ratesSheet.getRange(labourCell).values=[[cfg.labour_hourly+5]];
wb.recalculate();
equal(cellValue(costSheet,'V8'),Math.round(cellValue(costSheet,'U8')*(cfg.labour_hourly+5)*100)/100);
equal(cellValue(main,'AM8'),cellValue(costSheet,'X8'));
editChecks.push('Global labour rate changes component and main catalogue totals');
ratesSheet.getRange(labourCell).values=[[cfg.labour_hourly]];
costSheet.getRange('I8').values=[['jesmonite']];
wb.recalculate();
equal(cellValue(costSheet,'X8'),costRows[0][25]);
if(cellValue(costSheet,'J8')!==cfg.materials.jesmonite.label)throw new Error('Material label did not follow selection');
editChecks.push('Material key changes label, rate and total');
costSheet.getRange('I8').values=[[originalMaterial]];
finishSheet.getRange('C8').values=[['rust']];
wb.recalculate();
equal(cellValue(finishSheet,'G8'),cfg.finishes.rust.rate);
equal(cellValue(finishSheet,'I8'),cfg.finishes.rust.minutes);
equal(cellValue(costSheet,'R8'),Math.round(finishRows[0][4]*finishRows[0][5]*cfg.finishes.rust.rate*100)/100);
editChecks.push('Finish key changes label, rate, labour time and component surface cost');
finishSheet.getRange('C8').values=[[originalFinish]];
costSheet.getRange('L8').values=[[0]];
wb.recalculate();
equal(cellValue(costSheet,'V8'),0);equal(cellValue(costSheet,'X8'),cellValue(costSheet,'W8'));
editChecks.push('Zero labour override is respected');
costSheet.getRange('L8').values=[[costRows[0][11]]];
wb.recalculate();equal(cellValue(costSheet,'X8'),originalTotal);
editChecks.push('All original input values restored before export');
await fs.writeFile(path.join(dir,'recalculation-checks.json'),JSON.stringify({status:'PASS',checks:editChecks},null,2));
const errors = await wb.inspect({kind:'match', searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!', options:{useRegex:true, maxResults:100}, maxChars:3000});
await fs.writeFile(path.join(dir, 'formula-scan.jsonl'), errors.ndjson);
const inspection = await wb.inspect({kind:'table', range:'Wall Sculptures!A7:P12', include:'values,formulas', tableMaxRows:6, tableMaxCols:16, maxChars:5500});
await fs.writeFile(path.join(dir, 'workbook-inspection.jsonl'), inspection.ndjson);
for (const [sheetName, range, file] of [['Wall Sculptures','A1:J13','catalogue-preview.png'],['Images','A1:N12','images-preview.png'],['Specification Sources','A1:H11','sources-preview.png'],['Manufacturing Costs','A1:H13','costs-preview.png'],['Manufacturing Costs','P7:AB13','cost-totals-preview.png'],['Cost Rates','A1:H15','rates-preview.png'],['Cost Finishes','A1:J13','finishes-preview.png']]) {
  const preview = await wb.render({sheetName, range, scale:1.3, format:'png'});
  await fs.writeFile(path.join(dir, file), new Uint8Array(await preview.arrayBuffer()));
}
const xlsx = path.join(dir, 'catalogue_wall_sculptures.xlsx');
await (await SpreadsheetFile.exportXlsx(wb)).save(xlsx);
await fs.writeFile(path.join(dir, 'hyperlinks.json'), JSON.stringify(links));
await fs.writeFile(path.join(dir, 'expected-workbook.json'), JSON.stringify({created_utc:data.created_utc, summary:data.summary, sheets:sheetNames.map(name=>manifests.find(s=>s.name===name))}));
execFileSync('/usr/bin/python3', [path.join(dir,'native_links.py'), xlsx], {stdio:'inherit'});
console.log(JSON.stringify({output:xlsx, hyperlinks:links.length, primary_photos:primarySet}));
