import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook} from '@oai/artifact-tool';

const out=path.resolve(process.argv[2]);
const packet=JSON.parse(await fs.readFile(path.join(out,'bonanza-import.json'),'utf8'));
const book=Workbook.create();
const sheet=book.worksheets.add('Bonanza import');
const input=[packet.headers,...packet.rows];
const range=sheet.getRangeByIndexes(0,0,input.length,packet.headers.length);
range.values=input;
await book.recalculate();
const actual=range.values;
if(JSON.stringify(actual)!==JSON.stringify(input)) throw Error('Artifact values differ from import packet');
if(new Set(actual.slice(1).map(r=>r[0])).size!==176) throw Error('Duplicate SKU');
if(new Set(actual.slice(1).map(r=>r[1])).size!==176) throw Error('Duplicate title');
for(const r of actual.slice(1)){
 if(r[1].length>80||!(r[2]>0)||!r[3].includes('gypsum-based material')||!r[3].includes('Sally Price')||r[4]!==553||r[5]!==1) throw Error('Incomplete product');
 if(r.slice(6,10).filter(Boolean).some(u=>!u.startsWith('https://images.squarespace-cdn.com/'))) throw Error('Unexpected image host');
}
// The documented Artifact API has no CSV exporter in this runtime. Serialize
// its authored and validated cell values as plain CSV without a UTF-8 BOM.
const encode=v=>'"'+String(v??'').replaceAll('"','""')+'"';
const csv=actual.map((r,i)=>r.map((v,j)=>encode(i>0&&j===2?Number(v).toFixed(2):v)).join(',')).join('\r\n')+'\r\n';
const file=path.join(out,'boldstone_bonanza_176.csv');
await fs.writeFile(file,csv,'utf8');
const imported=await Workbook.fromCSV(csv,{sheetName:'Readback'});
const back=imported.worksheets.getItemAt(0).getRangeByIndexes(0,0,177,13).values;
for(let i=0;i<177;i++) for(let j=0;j<13;j++){
 if(j===2&&i>0 ? Number(back[i][j])!==Number(actual[i][j]) : String(back[i][j]??'')!==String(actual[i][j]??'')) throw Error(`CSV readback differs ${i},${j}`);
}
await fs.writeFile(path.join(out,'bonanza-csv-verification.json'),JSON.stringify({status:'PASS',products:176,uniqueSkus:176,uniqueTitles:176,requiredFieldsVerified:true,artifactReadback:true,imagesPerProductMaximum:4,currency:'USD',file},null,2));
console.log(JSON.stringify({status:'PASS',products:176,file}));
