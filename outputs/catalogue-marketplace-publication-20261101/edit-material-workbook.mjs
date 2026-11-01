import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(new URL(import.meta.url).pathname);
const changes=JSON.parse(await fs.readFile(path.join(out,'material-workbook-patches.json'),'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
for(const stage of ['before','after']){
  if(stage==='after')for(const p of changes.patches)book.worksheets.getItem(p.sheet).getRange(p.cell).values=[[p.value]];
  const preview=await book.render({sheetName:'Wall Sculptures',range:'C7:G10',scale:1,format:'png'});
  await fs.writeFile(path.join(out,`material-workbook-${stage}.png`),new Uint8Array(await preview.arrayBuffer()));
}
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'material-workbook-authored.xlsx'));
console.log(JSON.stringify({authored:changes.patches.length,products:changes.products}));
