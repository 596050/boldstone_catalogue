import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';

const out = path.resolve(process.argv[2]);
const plan = JSON.parse(await fs.readFile(path.join(out, 'editions-plan.json'), 'utf8'));
const preview = process.argv.includes('--preview');
const final = process.argv.includes('--verify-final');
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out, final ? 'catalogue_wall_sculptures.xlsx' : 'previous-catalogue.xlsx')));
const master = book.worksheets.getItem('Wall Sculptures');
if (preview) {
  const blob = await book.render({sheetName:'Wall Sculptures', range:'PO7:PQ10', scale:1.25, format:'png'});
  await fs.writeFile(path.join(out, 'before.png'), new Uint8Array(await blob.arrayBuffer()));
  console.log((await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:'PO7:PQ10',maxChars:1200,tableMaxRows:4,tableMaxCols:3})).ndjson);
  process.exit(0);
}
if (!final) {
  if (plan.added_master_columns.length) {
    master.getRangeByIndexes(6, plan.first_master_column - 1, 182, plan.added_master_columns.length).format = {font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top',columnWidth:32};
    master.getRangeByIndexes(6, plan.first_master_column - 1, 1, plan.added_master_columns.length).format = {fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'},rowHeight:75};
  }
  for (const p of plan.patches.filter(p => p.sheet === 'Wall Sculptures')) master.getRange(p.cell).values = [[p.value]];
  for (const h of ['saatchi_art_edition_size', 'saatchi_art_creation_year']) master.getRange(`${plan.headers[h]}8:${plan.headers[h]}188`).format.numberFormat = '0';
  const notes = book.worksheets.getItem('Platform Review');
  const rows = Array.from({length:9}, () => Array(3).fill(null));
  const ix = address => [...address.replace(/\d/g,'')].reduce((v,c) => v * 26 + c.charCodeAt(0) - 64, 0);
  for (const p of plan.patches.filter(p => p.sheet === 'Platform Review')) rows[Number(p.cell.match(/\d+/)[0])-70][ix(p.cell)-10] = p.value;
  notes.getRange('J70:L78').values = rows;
  notes.getRange('J70:L78').format = {font:{name:'Calibri',size:11},wrapText:true,verticalAlignment:'top'};
  notes.getRange('J70:L70').format = {fill:'#586F50',font:{name:'Calibri',size:11,bold:true,color:'#FFFFFF'}};
  for (const r of plan.row_format_updates) notes.getRange(`J${r.row}:L${r.row}`).format.rowHeight = r.height;
  await book.recalculate();
  for (const p of plan.patches) {
    const actual = book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];
    if (actual !== p.value) throw Error(`Readback mismatch ${p.sheet}!${p.cell}`);
  }
  await (await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
}
const yearRange = `${plan.headers.saatchi_art_creation_year}7:${plan.headers.saatchi_art_creation_year_verified}10`;
for (const [range, name] of [[`${plan.headers.saatchi_art_offering_type}7:${plan.headers.saatchi_art_edition_size}10`,'editions'],[yearRange,'years']]) {
  const blob = await book.render({sheetName:'Wall Sculptures',range,scale:1.15,format:'png'});
  await fs.writeFile(path.join(out,(final?'final-':'') + name + '.png'),new Uint8Array(await blob.arrayBuffer()));
}
const estimated = plan.records.find(r => r.year_is_estimate);
const estimatedBlob = await book.render({sheetName:'Wall Sculptures',range:`${plan.headers.saatchi_art_creation_year}${estimated.row}:${plan.headers.saatchi_art_creation_year_verified}${estimated.row}`,scale:1.15,format:'png'});
await fs.writeFile(path.join(out,(final?'final-':'')+'estimated-year.png'),new Uint8Array(await estimatedBlob.arrayBuffer()));
const blob = await book.render({sheetName:'Platform Review',range:'J70:L78',scale:1.15,format:'png'});
await fs.writeFile(path.join(out,(final?'final-':'')+'notes.png'),new Uint8Array(await blob.arrayBuffer()));
console.log((await book.inspect({kind:'region',sheetId:'Wall Sculptures',range:yearRange,maxChars:1800,tableMaxRows:4,tableMaxCols:5})).ndjson);
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',patches:plan.patches.length}));
