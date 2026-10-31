import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {FileBlob, SpreadsheetFile} from '@oai/artifact-tool';
const out=path.dirname(fileURLToPath(import.meta.url));
const workbook=await SpreadsheetFile.importXlsx(await FileBlob.load(path.join(out,'previous-catalogue.xlsx')));
const main=workbook.worksheets.getItem('Wall Sculptures');
const apply=process.argv.includes('--apply');
if (apply) {
  const plan=JSON.parse(await fs.readFile(path.join(out,'website-final-plan.json'),'utf8'));
  const changes=JSON.parse(await fs.readFile(path.join(out,'workbook-changes.json'),'utf8'));
  const byid=new Map(plan.products.map(p=>[p.catalogue_id,p]));
  for(let row=8;row<189;row++) {
    const id=main.getRange(`AA${row}`).values[0][0], p=byid.get(id);
    if(!p || main.getRange(`C${row}`).values[0][0]!==p.catalogue_name) throw Error('Catalogue identity mismatch at '+row);
  }
  main.getRange('AV7:AV188').copyFrom(main.getRange('C7:C188'),'all');
  main.getRange('AV7').values=[['Retail / website name']];
  main.getRange('AV8:AV188').values=main.getRange('AA8:AA188').values.map(([id])=>[byid.get(id).retail_name]);
  main.getRange('AV7:AV188').format.columnWidth=49;
  main.getRange('AV7:AV188').format.wrapText=true;
  const upload=workbook.worksheets.getItem('Upload Plan');
  upload.getRange('Z7:Z188').copyFrom(upload.getRange('B7:B188'),'all');
  upload.getRange('Z7').values=[['Retail / website name']];
  upload.getRange('Z8:Z188').values=upload.getRange('C8:C188').values.map(([id])=>[byid.get(id).retail_name]);
  upload.getRange('Z7:Z188').format.columnWidth=49;
  upload.getRange('Z7:Z188').format.wrapText=true;
  for(const col of ['AW','AX','AY','AZ']) main.getRange(`${col}7:${col}188`).copyFrom(main.getRange('AV7:AV188'),'all');
  for(const col of ['AA','AB','AC']) upload.getRange(`${col}7:${col}188`).copyFrom(upload.getRange('Z7:Z188'),'all');
  for(const item of changes.patches) workbook.worksheets.getItem(item.sheet).getRange(item.cell).values=[[item.value??'']];
  const sources=workbook.worksheets.getItem('Specification Sources');
  const sourceEnd=changes.source_append_start+changes.source_append.length-1;
  sources.getRange(`A${changes.source_append_start}:N${sourceEnd}`).values=changes.source_append;
  sources.getRange(`A${changes.source_append_start}:N${sourceEnd}`).format.wrapText=true;
  main.getRange('AD8:AD188').format.verticalAlignment='top';
  const copy=workbook.worksheets.add('Website Copy');
  copy.showGridLines=false;
  copy.getRange('A1:E188').format.font={name:'Arial',size:11,color:'#243b30'};
  copy.getRange('A1:E188').format.verticalAlignment='top';
  copy.getRange('A2').values=[['Wall sculptures - customer-facing website copy']];
  copy.getRange('A2').format.font={name:'Arial',size:18,bold:true,color:'#243b30'};
  copy.getRange('A4').values=[[changes.website_copy_stamp]];
  copy.getRange('A5').values=[['Retail names and descriptions; internal material and costing records are on the other sheets.']];
  copy.getRange('A7:E7').values=[['Retail / website name','Customer-facing description','Website listing','Website context images','Catalogue ID']];
  copy.getRange('A8:E188').values=changes.website_copy_rows;
  copy.tables.add('A7:E188',true,'WebsiteCopyTable').style='TableStyleLight1';
  copy.getRange('A7:E7').format={fill:'#243b30',font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:36};
  for(const [col,width] of [['A',42],['B',115],['C',48],['D',20],['E',26]]) copy.getRange(`${col}1:${col}188`).format.columnWidth=width;
  copy.getRange('A8:E188').format.wrapText=true;
  for(let i=0;i<changes.website_copy_rows.length;i++) {
    const lines=changes.website_copy_rows[i][1].split('\n').reduce((n,s)=>n+Math.max(1,Math.ceil(s.length/105)),0);
    copy.getRange(`A${i+8}:E${i+8}`).format.rowHeight=Math.min(409,Math.max(260,lines*15+24));
  }
  copy.freezePanes.freezeRows(7);
  for (const [sheet, tableName, address] of [[main,'WallSculpturesTable','A7:AZ188'],[upload,'UploadPlanTable','A7:AC188'],[sources,'SpecificationSourcesTable',`A7:N${sourceEnd}`]]) {
    const old=sheet.tables.items.find(t=>t.name===tableName);
    if(!old) throw Error('Missing table '+tableName);
    const style=old.style; old.delete();
    const table=sheet.tables.add(address,true,tableName); table.style=style;
  }
  workbook.recalculate();
  const check=await workbook.inspect({kind:'region',sheetId:'Wall Sculptures',range:'AV7:AV14',maxChars:2400});
  await fs.writeFile(path.join(out,'retail-column-inspection.jsonl'),check.ndjson);
  const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},maxChars:2000});
  await fs.writeFile(path.join(out,'formula-scan.jsonl'),errors.ndjson);
}
for(const [sheetName,range,label] of apply?[['Wall Sculptures','AV7:AV15','retail-names'],['Upload Plan','Z7:AC10','upload-names'],['Website Copy','A7:B9','descriptions'],['Wall Sculptures','G7:G10','fixing-wording']]:[['Wall Sculptures','A1:H11','catalogue'],['Wall Sculptures','AS7:AU11','last-columns']]) {
  const image=await workbook.render({sheetName,range,scale:1.4,format:'png'});
  await fs.writeFile(path.join(out,`${apply?'after':'before'}-${label}.png`),new Uint8Array(await image.arrayBuffer()));
}
if(apply) await (await SpreadsheetFile.exportXlsx(workbook)).save(path.join(out,'catalogue_wall_sculptures.xlsx'));
console.log(apply?'Workbook edited and rendered':'Existing workbook rendered; no changes');
