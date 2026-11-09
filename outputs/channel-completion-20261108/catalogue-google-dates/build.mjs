import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
const final=process.argv.includes('--final');
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
if(!final){
  for(const p of plan.patches){
    const range=book.worksheets.getItem(p.sheet).getRange(p.cell);
    range.values=[[p.value]];
    range.format.numberFormat=p.style==='utc'?'yyyy-mm-dd hh:mm:ss.000':'@';
  }
  await book.recalculate();
  for(const p of plan.patches){
    let v=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];
    if(v instanceof Date)v=(v.getTime()-Date.UTC(1899,11,30))/86400000;
    if(typeof p.value==='number' ? Math.abs(v-p.value)>1e-8 : v!==p.value)throw Error('Authored mismatch '+p.sheet+'!'+p.cell);
  }
  await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
}
for(const p of plan.previews){
  const png=await book.render({sheetName:p.sheet,range:p.range,scale:1,format:'png'});
  await fs.writeFile(out+'/'+(final?'final':'after')+'-'+p.name+'.png',new Uint8Array(await png.arrayBuffer()));
}
console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',patches:plan.patches.length}));
