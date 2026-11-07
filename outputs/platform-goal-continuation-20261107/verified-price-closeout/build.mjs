import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const mode=process.argv[2];
const final=mode==='--final';
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(out+(final?'/catalogue_wall_sculptures.xlsx':'/previous-catalogue.xlsx')));
const previews=JSON.parse(await fs.readFile(out+'/plan.json','utf8')).previews;
async function render(p,prefix){const blob=await book.render({sheetName:'Wall Sculptures',range:p.range,scale:1,format:'png'});await fs.writeFile(out+'/'+prefix+'-'+p.name+'.png',new Uint8Array(await blob.arrayBuffer()));}
if(mode==='--before'){
  for(const p of previews)await render(p,'before');
  console.log(JSON.stringify({status:'BEFORE_RENDERED'}));
}else{
  const plan=JSON.parse(await fs.readFile(out+'/plan.json','utf8'));
  if(!final){
    for(const p of plan.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
    for(const r of plan.row_heights||[])book.worksheets.getItem(r.sheet).getRange('A'+r.row+':XB'+r.row).format.rowHeight=r.value;
    await book.recalculate();
    const readback=[];
    for(const p of plan.patches){const raw=book.worksheets.getItem(p.sheet).getRange(p.cell).values[0][0];const value=raw instanceof Date?raw.toISOString():raw;if(value!==p.value)throw Error('Readback mismatch '+p.cell);readback.push({cell:p.cell,value});}
    await fs.writeFile(out+'/authored-readback.json',JSON.stringify(readback,null,2));
    await(await SpreadsheetFile.exportXlsx(book)).save(out+'/authored.xlsx');
  }
  for(const p of plan.previews)await render(p,final?'final':'after');
  console.log(JSON.stringify({status:final?'FINAL_RENDERED':'AUTHORED',cells:plan.patches.length}));
}
