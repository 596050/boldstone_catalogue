import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const work=path.dirname(new URL(import.meta.url).pathname);
const d=JSON.parse(await fs.readFile(path.join(work,'unified-data.json'),'utf8'));
const bytes=await fs.readFile(d.output);
const hash=crypto.createHash('sha256').update(bytes).digest('hex');
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(d.output));
const s=wb.worksheets.getItemAt(0);
if(s.name!==d.sheet)throw new Error('Unified primary sheet does not open first');
const inspection=await wb.inspect({kind:'sheet',include:'id,name',maxChars:10000});
await fs.writeFile(path.join(work,'saved-sheet-inspection.ndjson'),inspection.ndjson);
for(const [cell,expected] of Object.entries(d.expected_formula_values))if(s.getRange(cell).values[0][0]!==expected)throw new Error('Saved summary differs at '+cell);
const circle=d.rows.findIndex(r=>r[1]==='Other website variant')+9;
for(const [range,rows] of [['A9:AH10',d.rows.slice(0,2)],[`E${circle}:K${circle+2}`,d.rows.slice(circle-9,circle-6).map(r=>r.slice(4,11))],['A421:AH421',d.rows.slice(412)]]){
  const actual=s.getRange(range).values;
  for(let i=0;i<rows.length;i++)for(let j=0;j<rows[i].length;j++)if((actual[i][j]??'')!==(rows[i][j]??''))throw new Error('Readback differs at '+range+' '+i+','+j);
}
const previews=[];
for(const [label,range] of [['saved-opening','A1:E14'],['saved-source-variant',`E${circle}:G${circle+2}`],['saved-source-price',`J${circle}:K${circle+2}`],['saved-image-counts',`Y${circle}:Z${circle+2}`],['saved-scope-review','A421:E421'],['saved-scope-specifications','F421:K421'],['saved-scope-links','L421:O421']]){
 const target=path.join(work,'previews',label+'.png');
 const preview=await wb.render({sheetName:d.sheet,range,scale:1,format:'png'});
 await fs.writeFile(target,new Uint8Array(await preview.arrayBuffer()));
 previews.push({path:target,range});
}
const after=crypto.createHash('sha256').update(await fs.readFile(d.output)).digest('hex');
if(after!==hash)throw new Error('Read-only inspection changed deliverable');
const receipt={status:'PASS_FINAL_XLSX_REOPENED_READ_ONLY',output:d.output,sha256:hash,firstSheet:s.name,summaryValues:d.expected_formula_values,previews};
await fs.writeFile(path.join(work,'saved-readback-receipt.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify(receipt));
