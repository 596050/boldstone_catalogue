import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const out = path.dirname(new URL(import.meta.url).pathname);
const plan = JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const final = process.argv[2] === 'final';
const book = await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const sheet = book.worksheets.getItem('Wall Sculptures');
if (!final) {
  for (const p of plan.previews) {
    const img = await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1.1,format:'png'});
    await fs.writeFile(out+'/before-'+p.name+'.png',new Uint8Array(await img.arrayBuffer()));
  }
  for (const p of plan.patches) {
    sheet.getRange(p.cell).values = [[p.value]];
    if (p.formula) sheet.getRange(p.cell).formulas = [['='+p.formula]];
  }
  book.recalculate();
  for (const p of plan.patches) {
    const raw = sheet.getRange(p.cell).values[0][0];
    const v = raw instanceof Date ? (raw.getTime()-Date.UTC(1899,11,30))/86400000 : raw;
    const ok = typeof p.value === 'number' ? typeof v === 'number' && Math.abs(v-p.value)<1e-6 : v===p.value;
    if (!ok) throw Error('Artifact cell mismatch '+p.cell);
  }
  await (await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
}
for (const p of plan.previews) {
  const img = await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1.1,format:'png'});
  await fs.writeFile(out+'/'+(final?'final-':'authored-')+p.name+'.png',new Uint8Array(await img.arrayBuffer()));
}
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'ARTIFACT_AUTHORED',cells:plan.patches.length}));
