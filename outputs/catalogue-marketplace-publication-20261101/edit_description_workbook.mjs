import fs from 'node:fs/promises';
import path from 'node:path';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const out=path.resolve(process.argv[2]);
const patches=JSON.parse(await fs.readFile(path.join(out,'patches.json'),'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
await fs.writeFile(path.join(out,'before.png'),new Uint8Array(await(await book.render({sheetName:'Website Copy',range:'A7:B10',scale:1,format:'png'})).arrayBuffer()));
for(const patch of patches.patches){
  const cell=book.worksheets.getItem(patch.sheet).getRange(patch.cell);
  cell.format.numberFormat='@';
  cell.values=[[String(patch.value)]];
}
book.worksheets.getItem('Website Copy').getRange('A8:B188').format.rowHeight=409.5;
await book.recalculate();
await fs.writeFile(path.join(out,'after.png'),new Uint8Array(await(await book.render({sheetName:'Website Copy',range:'A7:B10',scale:1,format:'png'})).arrayBuffer()));
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'authored.xlsx'));
console.log(JSON.stringify({authored_description_and_audit_cells:patches.patches.length}));
