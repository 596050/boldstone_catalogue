import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(fileURLToPath(import.meta.url));
const changes=JSON.parse(await fs.readFile(path.join(out,'workbook-changes.json'),'utf8'));
const book=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
const main=book.worksheets.getItem('Wall Sculptures'),cost=book.worksheets.getItem('Manufacturing Costs');
for (const [sheetName,range,label] of [['Wall Sculptures','AF7:AM10','manufacturing'],['Manufacturing Costs','U7:X11','labour']]) {
  const b=await book.render({sheetName,range,scale:1.2,format:'png'});
  await fs.writeFile(path.join(out,`before-${label}.png`),new Uint8Array(await b.arrayBuffer()));
}
main.getRange('BA7:BA188').copyFrom(main.getRange('AM7:AM188'),'all');
const upload=book.worksheets.getItem('Upload Plan');
for(const col of ['AD','AE'])upload.getRange(`${col}7:${col}188`).copyFrom(upload.getRange('R7:R188'),'all');
for(const p of changes.patches){
  const range=book.worksheets.getItem(p.sheet).getRange(p.cell);
  if(typeof p.value==='string'&&p.value.startsWith('='))range.formulas=[[p.value]];
  else range.values=[[p.sheet==='Specification Sources'&&/^N\d+$/.test(p.cell)&&p.value?new Date(p.value+'Z'):p.value??'']];
}
const images=book.worksheets.getItem('Images'),last=changes.image_rows.length+7;
images.getRange(`A8:AJ${last}`).values=changes.image_rows.map(r=>r.map((v,i)=>i===19?'':v??''));
images.getRange(`T8:T${last}`).formulas=changes.image_rows.map(r=>[r[19]||'']);
images.getRange(`A8487:AJ${last}`).format={font:{name:'Arial',size:10,color:'#24332D'},wrapText:true,verticalAlignment:'center',rowHeight:120};
images.getRange(`T8:T${last}`).setNumberFormat('0.00');
for(const [s,name,range] of [[main,'WallSculpturesTable','A7:BA188'],[upload,'UploadPlanTable','A7:AE188'],[images,'ImagesTable',`A7:AJ${last}`]]){
  const table=s.tables.items.find(t=>t.name===name);if(!table)throw Error('Missing '+name);
  const style=table.style;table.delete();s.tables.add(range,true,name).style=style;
}
main.getRange('AM7:AM188').format.columnWidth=29;
main.getRange('BA7:BA188').format.columnWidth=29;
cost.getRange('W7:X188').format.columnWidth=30;
cost.getRange('Y7:AB188').format.columnWidth=28;
for(const col of ['R','AD','AE'])upload.getRange(`${col}7:${col}188`).format.columnWidth=30;
for(const s of [main,cost,upload])s.getRange('A7:BA7').format.rowHeight=55;
book.recalculate();
// Exercise the dependency: labour changes the total/price, never manufacturing.
const rates=book.worksheets.getItem('Cost Rates'),rate=rates.getRange('D11').values[0][0];
const read=()=>({manufacturing:main.getRange('AM8').values[0][0],labour:main.getRange('AL8').values[0][0],total:main.getRange('BA8').values[0][0],price:main.getRange('H8').values[0][0]});
const before=read();rates.getRange('D11').values=[[Number(rate)+1]];book.recalculate();const increased=read();
if(before.manufacturing!==increased.manufacturing||!(increased.labour>before.labour)||!(increased.price>before.price))throw Error('Labour dependency failed');
rates.getRange('D11').values=[[rate]];book.recalculate();const restored=read();
if(JSON.stringify(before)!==JSON.stringify(restored))throw Error('Temporary labour-rate edit did not restore');
await fs.writeFile(path.join(out,'labour-dependency-check.json'),JSON.stringify({status:'PASS',before,increased,restored},null,2));
for(const [sheetName,range,label] of [['Wall Sculptures','AF7:AM10','manufacturing'],['Manufacturing Costs','U7:X11','labour'],['Upload Plan','AD7:AE11','upload-totals'],['Images','E7:M10','images']]){
  const b=await book.render({sheetName,range,scale:1.2,format:'png'});
  await fs.writeFile(path.join(out,`after-${label}.png`),new Uint8Array(await b.arrayBuffer()));
}
const errors=await book.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
await fs.writeFile(path.join(out,'formula-scan.jsonl'),errors.ndjson);
await(await SpreadsheetFile.exportXlsx(book)).save(path.join(out,'catalogue_wall_sculptures.xlsx'));
console.log(JSON.stringify({edited:true,products:181,imageRows:changes.image_rows.length,labourDependency:'PASS'}));
